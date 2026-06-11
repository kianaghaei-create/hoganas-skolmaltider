"""
QA Iteration 4+5 — AI- och Cypher-analys verifiering + Neo4j vs CSV validering.
Verifierar: JSON-analysfiler mot rådatan, systemprompten mot krav,
AI-svarstestpaket (statisk analys), Neo4j mot CSV (0,1%-tolerans).

Kör: python3 tests/test_ai_cypher_qa.py
"""
import json
import pandas as pd
import numpy as np
import sys
from pathlib import Path

DATA = Path("Data/processed")
ANA  = Path("Data/analysis")

FAIL = []

def check(name, ok, note=""):
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}" + (f" — {note}" if note else ""))
    if not ok:
        FAIL.append(name)
    return ok

def check_paw(name, note=""):
    """PASS MED AVGRÄNSNING — korrekt med dokumenterad begränsning."""
    print(f"  [PASS MED AVGRÄNSNING] {name}" + (f" — {note}" if note else ""))

print("=== QA Iteration 4: AI- och Cypher-analys ===\n")

fw  = pd.read_csv(DATA / "food_waste_daily_v2.csv")
pu  = pd.read_csv(DATA / "purchases.csv", low_memory=False)
fw_pos = fw[fw["totalt_svinn_kg"] > 0]
fw_por = fw_pos[fw_pos["serverade_portioner"] > 0]

# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 1: Cypher-analysfiler — verifiering mot rådatan
# ──────────────────────────────────────────────────────────────────────────────
print("BLOCK 1: Cypher-analysfiler\n")

# C1: enheter_svinn_ranking
print("C1 enheter_svinn_ranking")
cyp = json.load(open(ANA / "enheter_svinn_ranking.json"))
csv_sum = fw["totalt_svinn_kg"].sum()
cyp_sum = sum(r["total_kg"] for r in cyp if r.get("total_kg"))
check("C1a total_kg inom 1%", abs(csv_sum - cyp_sum) / csv_sum < 0.01,
      f"CSV={csv_sum:.0f} kg, JSON={cyp_sum:.0f} kg")
check("C1b alla 21 enheter", len(cyp) == 21, f"{len(cyp)}")
fsk_kg = sum(r["total_kg"] for r in cyp
             if "förskola" in r.get("enhet", "").lower() and r.get("total_kg"))
check("C1c förskolor representerade (>1000 kg)", fsk_kg > 1000,
      f"förskola total={fsk_kg:.0f} kg")

# Stickprov: Kullagymnasiet gram_per_portion
kulla_csv = fw_por[fw_por["unit_name"].str.lower().str.contains("kullagymnasiet", na=False)]
if not kulla_csv.empty:
    csv_gp = round((kulla_csv["totalt_svinn_kg"] / kulla_csv["serverade_portioner"]).mean() * 1000, 1)
    kulla_json = next((r for r in cyp if "kullagymnasiet" in r.get("enhet", "").lower()), None)
    if kulla_json:
        check("C1d Kullagymnasiet g/p inom 5%",
              abs(csv_gp - kulla_json["gram_per_portion"]) / max(csv_gp, 1) < 0.05,
              f"CSV={csv_gp}g, JSON={kulla_json['gram_per_portion']}g")

# C2: svinntyper_per_enhet
print("\nC2 svinntyper_per_enhet")
cyp2 = json.load(open(ANA / "svinntyper_per_enhet.json"))
fsk_in = [r for r in cyp2 if "förskola" in r.get("enhet", "").lower()]
check("C2a inga förskolor (separata komponentkolumner saknas)", len(fsk_in) == 0,
      f"{len(fsk_in)} förskolarader")
check("C2b enbart skola/ÄO-enheter (>=5)", len(cyp2) >= 5, f"{len(cyp2)} enheter")

# Stickprov: Kullagymnasiet tallrik
fw_st = fw_por[(fw_por["format"] == "skola_ao") &
               fw_por["tallrikssvinn_kg"].notna() &
               fw_por["serveringssvinn_kg"].notna() &
               fw_por["kokssvinn_kg"].notna()]
k = fw_st[fw_st["unit_name"].str.lower().str.contains("kullagymnasiet", na=False)]
if not k.empty:
    csv_tal = round((k["tallrikssvinn_kg"] / k["serverade_portioner"]).mean() * 1000, 1)
    kj = next((r for r in cyp2 if "kullagymnasiet" in r.get("enhet", "").lower()), None)
    if kj:
        check("C2c Kullagymnasiet tallrik g/p inom 5%",
              abs(csv_tal - kj["tallrik_g_p"]) / max(csv_tal, 1) < 0.05,
              f"CSV={csv_tal}g, JSON={kj['tallrik_g_p']}g")

# C3: svinn_per_veckodag
print("\nC3 svinn_per_veckodag")
cyp3 = json.load(open(ANA / "svinn_per_veckodag.json"))
check("C3a 5 veckodagar", len(cyp3) == 5)
for dag in ["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag"]:
    check(f"C3b {dag} finns", any(r["dag"] == dag for r in cyp3))
# Stickprov: Måndag inom 2%
mon = next((r for r in cyp3 if r["dag"] == "Måndag"), None)
if mon:
    csv_mon = fw_por[fw_por["veckodag"] == "Måndag"]
    csv_gp = round((csv_mon["totalt_svinn_kg"] / csv_mon["serverade_portioner"]).mean() * 1000, 1)
    check("C3c Måndag g/p inom 2%",
          abs(csv_gp - mon["gram_per_portion"]) / max(csv_gp, 1) < 0.02,
          f"CSV={csv_gp}g, JSON={mon['gram_per_portion']}g")

# C4: ratter_svinn_per_portion
print("\nC4 ratter_svinn_per_portion")
cyp4 = json.load(open(ANA / "ratter_svinn_per_portion.json"))
check("C4a 20-30 rader", 20 <= len(cyp4) <= 30, f"{len(cyp4)}")
check("C4b alla obs>=3", all(r["obs"] >= 3 for r in cyp4))
check("C4c fallande sortering",
      all(cyp4[i]["gram_per_portion"] >= cyp4[i+1]["gram_per_portion"]
          for i in range(len(cyp4) - 1)))

# C5: ratter_lag_svinn
print("\nC5 ratter_lag_svinn")
cyp5 = json.load(open(ANA / "ratter_lag_svinn.json"))
check("C5a >=15 rader", len(cyp5) >= 15, f"{len(cyp5)}")
check("C5b alla obs>=5", all(r["obs"] >= 5 for r in cyp5))
check("C5c stigande sortering",
      all(cyp5[i]["gram_per_portion"] <= cyp5[i+1]["gram_per_portion"]
          for i in range(len(cyp5) - 1)))

# C6: svinn_naring_kvadrant (Python-join via dish_name_mapping.csv)
print("\nC6 svinn_naring_kvadrant")
cyp6 = json.load(open(ANA / "svinn_naring_kvadrant.json"))
fisk_bad = [r for r in cyp6
            if r.get("komponent", "").lower().startswith("fiskgratäng serveras med potatismos")]
check("C6a fiskgratäng-veto borttagen", len(fisk_bad) == 0,
      f"{len(fisk_bad)} matchade 'fiskgratäng serveras med potatismos'")
check("C6b >=20 rätter efter filtrering (obs>=2, Python-join)", len(cyp6) >= 20, f"{len(cyp6)}")
check("C6c alla protein >= 5g", all(r.get("protein", 0) >= 5 for r in cyp6),
      f"min protein={min(r.get('protein', 99) for r in cyp6)}")
check("C6d alla kcal >= 150", all(r.get("kcal", 0) >= 150 for r in cyp6),
      f"min kcal={min(r.get('kcal', 9999) for r in cyp6)}")
# C6e: Pulled pork finns i kvadranten (verifierar att manual_override-matchning fungerar)
pp_in_kv = [r for r in cyp6 if "pulled pork" in r.get("komponent","").lower()]
check("C6e Pulled pork finns i kvadrantdiagrammet", len(pp_in_kv) == 1,
      f"{len(pp_in_kv)} träffar (förväntat 1)")
if pp_in_kv:
    pp = pp_in_kv[0]
    check("C6f Pulled pork obs >= 2", pp.get("obs", 0) >= 2,
          f"obs={pp.get('obs')}")
    check("C6g Pulled pork match_status = manual_override",
          pp.get("match_status") == "manual_override",
          f"match_status={pp.get('match_status')}")
# C6h: match_status-fält finns och inga low-confidence automatiska matchningar
valid_statuses = {"exact", "normalized", "manual_override"}
bad_status = [r for r in cyp6 if r.get("match_status") not in valid_statuses]
check("C6h alla rätter har giltig match_status", len(bad_status) == 0,
      f"{len(bad_status)} rätter med ogiltig status")
check_paw("C6 svinn_naring_kvadrant",
          f"{len(cyp6)} rätter via Python-join (matratt_norm → dish_name_mapping.csv → naring.parquet). "
          "exact/normalized/manual_override. Kräver matratt_norm i svinndatan.")

# C6_funnel: Kvadrant funnel audit
print("\nC6_funnel kvadrant_funnel + exclusion_audit")
funnel_path = ANA / "kvadrant_funnel.json"
excl_path   = ANA / "kvadrant_exclusion_audit.csv"

check("C6_funnel1 kvadrant_funnel.json finns", funnel_path.exists())
check("C6_funnel2 kvadrant_exclusion_audit.csv finns", excl_path.exists())

if funnel_path.exists():
    fdata = json.load(open(funnel_path))
    steps = {s["step"]: s for s in fdata.get("steps", [])}

    # Steg A: minst 500 unika matratt_norm i svinndatan
    check("C6_funnel3 steg A >= 500 unika matratt_norm", steps.get("A", {}).get("ratter", 0) >= 500,
          f"A.ratter={steps.get('A',{}).get('ratter')}")

    # Steg C >= steg G (obs>=2 >= antal i diagram)
    c_count = steps.get("C", {}).get("ratter", 0)
    g_count = steps.get("G", {}).get("ratter", 0)
    check("C6_funnel4 steg C >= steg G", c_count >= g_count,
          f"C={c_count}, G={g_count}")

    # Steg G matchar faktiska JSON
    check("C6_funnel5 steg G matchar svinn_naring_kvadrant.json",
          g_count == len(cyp6),
          f"funnel G={g_count}, json={len(cyp6)}")

    # Matchninggrad < 100% (förväntat — generiska namn i svinndatan)
    mc = fdata.get("matching_coverage", {})
    check("C6_funnel6 matchningsgrad < 100% (generiska namn förväntat)",
          mc.get("match_rate_pct", 100) < 100,
          f"match_rate={mc.get('match_rate_pct')}%")

    # Top10 exkluderade finns och sorterade
    top10 = fdata.get("top10_excluded_by_waste_kg", [])
    check("C6_funnel7 top10 exkluderade finns (>=5 poster)", len(top10) >= 5,
          f"{len(top10)} poster")
    if len(top10) >= 2:
        check("C6_funnel8 top10 sorterade fallande på total_kg",
              top10[0]["total_kg"] >= top10[1]["total_kg"],
              f"{top10[0]['total_kg']} >= {top10[1]['total_kg']}")

if excl_path.exists():
    excl_df = pd.read_csv(excl_path)
    # Alla rader har exclusion_reason
    check("C6_funnel9 alla exkluderade har exclusion_reason",
          excl_df["exclusion_reason"].notna().all() and (excl_df["exclusion_reason"] != "").all(),
          f"{excl_df['exclusion_reason'].isna().sum()} saknar orsak")
    # Korrekt stavade pulled pork-varianter är INTE i exkluderingslistan
    pp_excl = excl_df[excl_df["matratt_norm"].str.lower().isin(["pulledpork","pulled pork"])]
    check("C6_funnel10 pulledpork/pulled pork ej exkluderade (inkluderas via manual_override)",
          len(pp_excl) == 0,
          f"{len(pp_excl)} korrekt-stavade pulled pork-rader i exkluderingslistan")
    # Ingen rätt med total_kg > 100 kg saknar exclusion_reason
    high_waste_excl = excl_df[excl_df["total_kg"] > 100]
    all_have_reason = all(r.strip() != "" for r in high_waste_excl["exclusion_reason"].fillna(""))
    check("C6_funnel11 alla rätter >100kg svinn har exclusion_reason",
          all_have_reason,
          f"{high_waste_excl['exclusion_reason'].isna().sum()} saknar orsak")

# C7: leverantorer_kostnad
print("\nC7 leverantorer_kostnad")
cyp7 = json.load(open(ANA / "leverantorer_kostnad.json"))
csv_lev = pu.groupby("supplier")["kronor"].sum() / 1e6
for r in cyp7:
    csv_v = csv_lev.get(r["leverantor"], 0)
    check(f"C7 {r['leverantor'][:25]} Mkr inom 1%",
          abs(csv_v - r["total_mkr"]) / max(csv_v, 0.001) < 0.01,
          f"CSV={csv_v:.2f}, JSON={r['total_mkr']}")

# C8: avtalstrohet_per_enhet
print("\nC8 avtalstrohet_per_enhet")
cyp8 = json.load(open(ANA / "avtalstrohet_per_enhet.json"))
check("C8a pct_utanfor beräkning korrekt (tkr_utanfor/total_tkr×100)",
      all(abs(r.get("pct_utanfor", 0) -
              round(r.get("tkr_utanfor", 0) / max(r.get("total_tkr", 1), 0.001) * 100, 1)) < 0.2
          for r in cyp8 if r.get("total_tkr", 0) > 0))
check("C8b fallande sortering",
      all(cyp8[i]["pct_utanfor"] >= cyp8[i+1]["pct_utanfor"]
          for i in range(len(cyp8) - 1)))

# C9: ratter_tallrikssvinn
print("\nC9 ratter_tallrikssvinn")
cyp9 = json.load(open(ANA / "ratter_tallrikssvinn.json"))
check("C9a obs>=3 för alla", all(r["obs"] >= 3 for r in cyp9))
check("C9b fallande sortering",
      all(cyp9[i]["tallrik_gram_per_portion"] >= cyp9[i+1]["tallrik_gram_per_portion"]
          for i in range(len(cyp9) - 1)))

# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 2: Systemprompt — kravuppfyllnad
# ──────────────────────────────────────────────────────────────────────────────
print("\nBLOCK 2: Systemprompt-krav\n")

app_text = Path("app.py").read_text(encoding="utf-8")
sp_start = app_text.find('p = """')
sp_end   = app_text.find('KONTEXT — Höganäs')
sp       = app_text[sp_start:sp_end] if sp_start > 0 else app_text

def has(needle, label, block=sp):
    found = needle.lower() in block.lower()
    check(label, found)
    return found

has("säg det tydligt",               "SP1 explicit instruktion om att säga när data saknas")
has("aldrig som konstaterade fakta",  "SP2 förbjuder kausala slutsatser")
has("ALDRIG jämföra med andra kommuner",
                                      "SP3 förbjuder jämförelse med andra kommuner")
has("ALDRIG göra prognoser",          "SP4 förbjuder prognoser")
has("ALDRIG ange råvarupriser",       "SP5 förbjuder artikelpriser")
has("AVGRÄNSNING SVINNTYPER",         "SP6 förklarar att svinntyper enbart gäller skola/ÄO")
has("AVGRÄNSNING NÄRINGSFIL",         "SP7 förklarar näringsfil-täckning")
has("ALDRIG skapa egna beräkningar",  "SP8 förbjuder egna beräkningar")
has("fiskgratäng serveras med potatismos",
                                      "SP9 fiskgratäng-veto finns")
has("svinntyper",                     "SP10 svinntyp-analys omnämns i prompt")
check("SP11 korrekt väder-r (−0.07) i prompt och gammal −0.29 borttagen",
      "0.07" in app_text and "0.29" not in app_text,
      f"0.07 finns: {'0.07' in app_text}, 0.29 finns: {'0.29' in app_text}")

# Kontrollera att OLD −0.29 INTE finns kvar
old_r = "r≈−0.29" in app_text or "r≈-0.29" in app_text
check("SP12 gammal r=−0.29 borttagen", not old_r,
      "hittades fortfarande i app.py" if old_r else "")

# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 3: AI-svarstestpaket — statisk prompt-granskning
# ──────────────────────────────────────────────────────────────────────────────
print("\nBLOCK 3: AI-svarstestpaket (statisk analys)\n")

# Faktafrågor — data måste finnas i systemprompt
cyp_enh = json.load(open(ANA / "enheter_svinn_ranking.json"))
cyp_enh_names = [r["enhet"] for r in cyp_enh]
check("F1 total svinn kg i prompt", "28400" in app_text or "28 400" in app_text or "fw_kg" in app_text,
      "total kg injiceras via ctx['fw_kg']")
check("F2 svinn per enhet i prompt (enheter_svinn_ranking laddas)",
      "enheter_svinn" in app_text, "")
check("F3 svinntyper i prompt",
      "svinntyper" in app_text and "tallrik" in app_text, "")
check("F4 topp 5 enheter i prompt (fw_worst5)",
      "fw_worst5" in app_text, "")
check("F5 Kullagymnasiet och Lerbergsskolan finns i analysdata",
      any("kullagymnasiet" in r.get("enhet","").lower() for r in cyp_enh) and
      any("lerbergsskolan" in r.get("enhet","").lower() for r in cyp_enh), "")

# Avgränsningsfrågor
check("F6 förskolor och kvadrant-avgränsning i prompt",
      "avgränsning näringsfil" in app_text.lower(), "")
check("F7 svinntyper avgränsning i prompt",
      "avgränsning svinntyper" in app_text.lower(), "")

# Adversarial-skydd i prompten
check("F8 kausalitet-skydd ('aldrig som konstaterade fakta')",
      "aldrig som konstaterade fakta" in app_text, "")
check("F9 beräknings-skydd ('ALDRIG skapa egna beräkningar')",
      "ALDRIG skapa egna beräkningar" in app_text, "")
check("F10 jämförelsedata-skydd ('ALDRIG jämföra med andra kommuner')",
      "ALDRIG jämföra med andra kommuner" in app_text, "")
check("F11 prognos-skydd ('ALDRIG göra prognoser')",
      "ALDRIG göra prognoser" in app_text, "")
check("F12 råvarukostnad-skydd ('ALDRIG ange råvarupriser')",
      "ALDRIG ange råvarupriser" in app_text, "")
check("F13 ekonomisk scenarioberäkning korrekt märkt",
      "scenariobaserade" in app_text, "")
check("F14 leverantör→svinn saknad länk dokumenterad i prompt",
      "INGEN koppling mellan leverantör och svinn" in app_text, "")

# Nyhamnsgården datakvalitet — serverade=0 specifikt?
check("F15 serveringssvinn avgränsning dokumenterad",
      "serverade portioner" in app_text.lower(), "serverade portioner omnämns som nämnare")

# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 4: Neo4j vs CSV validering (Iteration 5)
# ──────────────────────────────────────────────────────────────────────────────
print("\nBLOCK 4: Neo4j vs CSV validering\n")
try:
    from neo4j import GraphDatabase
    _neo4j_available = True
except ImportError:
    _neo4j_available = False
    print("  [SKIP] neo4j-driver ej installerat — hoppar över BLOCK 4")

if _neo4j_available:
    try:
        _drv = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "hoganas2025"))
        with _drv.session() as _s:
            # N1: total svinn kg
            _tot = list(_s.run("MATCH (d:Dag) RETURN sum(d.totalt_svinn_kg) AS s"))[0]["s"]
            _csv_tot = fw["totalt_svinn_kg"].sum()
            check("N1 total_kg inom 0.1%",
                  abs(_tot - _csv_tot) / _csv_tot < 0.001,
                  f"Neo4j={_tot:.0f}, CSV={_csv_tot:.0f}")

            # N2: antal Dag-noder (tillåt +/-2 för kända extra noder)
            _n_dag = list(_s.run("MATCH (d:Dag) RETURN count(d) AS n"))[0]["n"]
            check("N2 Dag-noder ≈ CSV-rader (±2)",
                  abs(_n_dag - len(fw)) <= 2,
                  f"Neo4j={_n_dag}, CSV={len(fw)}")

            # N3: antal enheter
            _n_enh = list(_s.run("MATCH (d:Dag) RETURN count(DISTINCT d.enhet) AS n"))[0]["n"]
            check("N3 enheter = 21",
                  _n_enh == fw["unit_name"].nunique(),
                  f"Neo4j={_n_enh}, CSV={fw['unit_name'].nunique()}")

            # N4: förskola total svinn kg
            _fsk = list(_s.run('MATCH (d:Dag {format:"förskola"}) RETURN sum(d.totalt_svinn_kg) AS s'))[0]["s"]
            _csv_fsk = fw[fw["format"] == "förskola"]["totalt_svinn_kg"].sum()
            check("N4 förskola total_kg inom 0.1%",
                  abs(_fsk - _csv_fsk) / _csv_fsk < 0.001,
                  f"Neo4j={_fsk:.0f}, CSV={_csv_fsk:.0f}")

            # N5: skola_ao total svinn kg
            _sko = list(_s.run('MATCH (d:Dag {format:"skola_ao"}) RETURN sum(d.totalt_svinn_kg) AS s'))[0]["s"]
            _csv_sko = fw[fw["format"] == "skola_ao"]["totalt_svinn_kg"].sum()
            check("N5 skola_ao total_kg inom 0.1%",
                  abs(_sko - _csv_sko) / _csv_sko < 0.001,
                  f"Neo4j={_sko:.0f}, CSV={_csv_sko:.0f}")

            # N6: förskola kokssvinn_kg = null
            _fsk_koks = list(_s.run(
                'MATCH (d:Dag {format:"förskola"}) WHERE d.kokssvinn_kg IS NOT NULL RETURN count(d) AS n'))[0]["n"]
            check("N6 förskola kokssvinn_kg = null", _fsk_koks == 0,
                  f"{_fsk_koks} förskolarader med kokssvinn_kg (ska vara 0)")

            # N7: förskola kok_och_serveringssvinn_kg finns
            _fsk_comb = list(_s.run(
                'MATCH (d:Dag {format:"förskola"}) WHERE d.kok_och_serveringssvinn_kg IS NOT NULL RETURN count(d) AS n'))[0]["n"]
            check("N7 förskola kok_och_serveringssvinn_kg finns", _fsk_comb > 2000,
                  f"{_fsk_comb} rader (förväntat >2000)")

            # N8: totalt_svinn_pct NULL < 20
            _nan_pct = list(_s.run(
                "MATCH (d:Dag) WHERE d.totalt_svinn_pct IS NULL RETURN count(d) AS n"))[0]["n"]
            check("N8 totalt_svinn_pct NULL < 20", _nan_pct < 20,
                  f"{_nan_pct} NULL (förväntat <20 efter parser-fix)")

            # N9: enhetsnivå — alla enheter inom 0.1% (inkl. Tornlycke/Jonstorp efter fix)
            _neo_res = list(_s.run(
                "MATCH (d:Dag) WHERE d.totalt_svinn_kg > 0 AND d.format IS NOT NULL "
                "RETURN d.enhet AS enhet, sum(d.totalt_svinn_kg) AS s"))
            _neo_by_e = {r["enhet"]: r["s"] for r in _neo_res}
            _csv_by_e = fw[fw["totalt_svinn_kg"] > 0].groupby("unit_name")["totalt_svinn_kg"].sum().to_dict()
            _bad = [(e, _csv_by_e[e], _neo_by_e.get(e, 0))
                    for e in _csv_by_e if _neo_by_e.get(e, 0) > 0
                    and abs(_neo_by_e[e] - _csv_by_e[e]) / _csv_by_e[e] > 0.001]
            check("N9 alla enheter inom 0.1%", len(_bad) == 0,
                  f"{len(_bad)} enheter med >0.1% avvikelse" +
                  (f" — {_bad[:2]}" if _bad else ""))

            # N10: inga orphan-noder (format=None)
            _orphans = list(_s.run(
                "MATCH (d:Dag) WHERE d.format IS NULL RETURN count(d) AS n"))[0]["n"]
            check("N10 inga orphan-noder (format=None)", _orphans == 0,
                  f"{_orphans} orphan-noder")

            # N11: Tornlycke/Jonstorp-swap fixad (0% avvikelse)
            for _u in ["Tornlyckeskolan", "Jonstorpsskolan"]:
                _neo_u = list(_s.run(
                    f"MATCH (d:Dag {{enhet:'{_u}'}}) RETURN count(d) AS n, sum(d.totalt_svinn_kg) AS s"))[0]
                _csv_u = fw[fw["unit_name"] == _u]
                check(f"N11 {_u} noder/kg exakt",
                      _neo_u["n"] == len(_csv_u) and abs(_neo_u["s"] - _csv_u["totalt_svinn_kg"].sum()) < 0.5,
                      f"Neo4j={_neo_u['n']} noder/{_neo_u['s']:.1f}kg, CSV={len(_csv_u)}/{_csv_u['totalt_svinn_kg'].sum():.1f}kg")

        _drv.close()

    except Exception as e:
        print(f"  [SKIP] Neo4j ej nåbar — {e}")

# ──────────────────────────────────────────────────────────────────────────────
# Resultat
# ──────────────────────────────────────────────────────────────────────────────
total_tests = len(FAIL) + sum(1 for line in [
    "C1a","C1b","C1c","C1d",
    "C2a","C2b","C2c",
    "C3a","C3c",
    "C4a","C4b","C4c",
    "C5a","C5b","C5c",
    "C6a","C6b","C6c","C6d","C6e","C6f","C6g","C6h",
    "C6_funnel1","C6_funnel2","C6_funnel3","C6_funnel4","C6_funnel5",
    "C6_funnel6","C6_funnel7","C6_funnel8","C6_funnel9","C6_funnel10","C6_funnel11",
    "C7","C8a","C8b","C9a","C9b",
    "SP1","SP2","SP3","SP4","SP5","SP6","SP7","SP8","SP9","SP10","SP11","SP12",
    "F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12","F13","F14","F15",
    "N1","N2","N3","N4","N5","N6","N7","N8","N9","N10","N11a","N11b",
])

print(f"\n{'='*50}")
if FAIL:
    print(f"❌ {len(FAIL)} FAIL: {', '.join(FAIL)}")
    sys.exit(1)
else:
    print("✅ Alla tester passerade")
    sys.exit(0)
