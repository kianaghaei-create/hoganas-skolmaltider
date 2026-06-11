"""
Kör förberedda Cypher-analyser mot lokal Neo4j och sparar verifierade
resultat som JSON i Data/analysis/. Används av AI-assistenten som
förankrad kontext — ingen live-querying i produktion.

Uppdaterad 2026-06-11: anpassad till nya egenskapsnamn efter Neo4j-reimport
från food_waste_daily_v2.csv. Egenskapsnamn matchar nu CSV-kolumner direkt.
"""
from neo4j import GraphDatabase
import json
import pandas as pd
import numpy as np
from pathlib import Path

URI  = "bolt://localhost:7687"
AUTH = ("neo4j", "hoganas2025")

OUT = Path("Data/analysis")
OUT.mkdir(parents=True, exist_ok=True)

driver = GraphDatabase.driver(URI, auth=AUTH)

def cypher(q, params=None):
    with driver.session() as s:
        return [dict(r) for r in s.run(q, params or {})]

def save(name, data, label):
    path = OUT / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✅ {label}: {len(data)} rader → {path.name}")
    return data

# Veckodagsordning som CASE (veckodag_num finns ej på Dag)
WEEKDAY_ORDER = """
CASE d.veckodag
  WHEN 'Måndag'  THEN 1
  WHEN 'Tisdag'  THEN 2
  WHEN 'Onsdag'  THEN 3
  WHEN 'Torsdag' THEN 4
  WHEN 'Fredag'  THEN 5
  ELSE 6
END
"""

# ── 1. Rätter med högst svinn (alla enheter) ─────────────────────────────────
print("\n1. Rätter med högst totalt svinn...")
save("ratter_hog_svinn", cypher(f"""
MATCH (d:Dag)
WHERE d.matratt_norm IS NOT NULL AND d.totalt_svinn_kg > 0
WITH d.matratt_norm AS ratt,
     count(*) AS antal_dagar,
     round(avg(d.totalt_svinn_kg), 2) AS snitt_svinn_kg,
     round(sum(d.totalt_svinn_kg), 1) AS totalt_svinn_kg,
     round(avg(CASE WHEN d.serverade_portioner > 0
               THEN d.totalt_svinn_kg / d.serverade_portioner ELSE null END), 4) AS svinn_kg_per_portion
ORDER BY totalt_svinn_kg DESC
LIMIT 30
RETURN ratt, antal_dagar, snitt_svinn_kg, totalt_svinn_kg,
       round(svinn_kg_per_portion * 1000, 1) AS svinn_gram_per_portion
"""), "Rätter med högst svinn")

# ── 2. Rätter med högst svinn per serverad portion ───────────────────────────
print("2. Rätter med högst svinn per portion...")
save("ratter_svinn_per_portion", cypher("""
MATCH (d:Dag)
WHERE d.matratt_norm IS NOT NULL AND d.serverade_portioner > 10 AND d.totalt_svinn_kg > 0
WITH d.matratt_norm AS ratt,
     count(*) AS obs,
     round(avg(d.totalt_svinn_kg / d.serverade_portioner) * 1000, 1) AS gram_per_portion,
     round(sum(d.totalt_svinn_kg), 1) AS totalt_kg
WHERE obs >= 3
RETURN ratt, obs, gram_per_portion, totalt_kg
ORDER BY gram_per_portion DESC
LIMIT 25
"""), "Rätter med högst svinn per portion")

# ── 3. Rätter med lägst svinn (bäst praxis) ─────────────────────────────────
print("3. Rätter med lägst svinn per portion (bäst praxis)...")
save("ratter_lag_svinn", cypher("""
MATCH (d:Dag)
WHERE d.matratt_norm IS NOT NULL AND d.serverade_portioner > 10 AND d.totalt_svinn_kg > 0
WITH d.matratt_norm AS ratt,
     count(*) AS obs,
     round(avg(d.totalt_svinn_kg / d.serverade_portioner) * 1000, 1) AS gram_per_portion,
     round(sum(d.totalt_svinn_kg), 1) AS totalt_kg
WHERE obs >= 5
RETURN ratt, obs, gram_per_portion, totalt_kg
ORDER BY gram_per_portion ASC
LIMIT 20
"""), "Rätter med lägst svinn")

# ── 4. Svinn per veckodag ────────────────────────────────────────────────────
print("4. Svinn per veckodag...")
save("svinn_per_veckodag", cypher(f"""
MATCH (d:Dag)
WHERE d.veckodag IS NOT NULL AND d.totalt_svinn_kg > 0 AND d.serverade_portioner > 0
WITH d.veckodag AS dag,
     {WEEKDAY_ORDER} AS num,
     round(avg(d.totalt_svinn_kg / d.serverade_portioner) * 1000, 1) AS gram_per_portion,
     round(avg(d.totalt_svinn_kg), 2) AS snitt_kg,
     count(*) AS obs
RETURN dag, gram_per_portion, snitt_kg, obs
ORDER BY num
"""), "Svinn per veckodag")

# ── 5. Enheter — svinnranking ────────────────────────────────────────────────
print("5. Enheter svinnranking...")
save("enheter_svinn_ranking", cypher("""
MATCH (d:Dag)
WHERE d.totalt_svinn_kg > 0 AND d.format IS NOT NULL
WITH d.enhet AS enhet, d.format AS format,
     count(d) AS dagar,
     round(sum(d.totalt_svinn_kg), 1) AS total_kg,
     round(avg(d.totalt_svinn_kg), 2) AS snitt_kg_per_dag,
     round(avg(CASE WHEN d.serverade_portioner > 0
               THEN d.totalt_svinn_kg / d.serverade_portioner ELSE null END) * 1000, 1) AS gram_per_portion,
     round(avg(CASE WHEN d.totalt_svinn_pct IS NOT NULL AND d.totalt_svinn_pct <= 1.0
               THEN d.totalt_svinn_pct ELSE null END) * 100, 1) AS snitt_svinn_pct
RETURN enhet, format, dagar, total_kg, snitt_kg_per_dag, gram_per_portion, snitt_svinn_pct
ORDER BY gram_per_portion DESC
"""), "Enheter svinnranking")

# ── 6. Svinntyper per enhet (enbart skola/ÄO — förskola saknar separata kolumner) ─
print("6. Svinntyper per enhet (skola/ÄO)...")
save("svinntyper_per_enhet", cypher("""
MATCH (d:Dag)
WHERE d.format = 'skola_ao'
  AND d.totalt_svinn_kg > 0
  AND d.serverade_portioner > 0
  AND d.tallrikssvinn_kg IS NOT NULL
  AND d.serveringssvinn_kg IS NOT NULL
  AND d.kokssvinn_kg IS NOT NULL
WITH d.enhet AS enhet,
     round(avg(d.tallrikssvinn_kg / d.serverade_portioner) * 1000, 1) AS tallrik_g_p,
     round(avg(d.serveringssvinn_kg / d.serverade_portioner) * 1000, 1) AS servering_g_p,
     round(avg(d.kokssvinn_kg / d.serverade_portioner) * 1000, 1) AS koks_g_p,
     count(d) AS dagar
WHERE dagar >= 10
RETURN enhet, tallrik_g_p, servering_g_p, koks_g_p, dagar
ORDER BY tallrik_g_p DESC
"""), "Svinntyper per enhet")

# ── 7. Leverantörer ──────────────────────────────────────────────────────────
print("7. Leverantörer...")
save("leverantorer_kostnad", cypher("""
MATCH (e:Enhet)-[:KOPER]->(i:Inkop)-[:FRAN]->(l:Leverantor)
WHERE l.namn <> 'Okänd'
WITH l.namn AS leverantor,
     round(sum(i.kronor) / 1000000, 2) AS total_mkr,
     round(sum(i.kilo) / 1000, 1) AS total_ton,
     count(DISTINCT e) AS enheter,
     count(i) AS inkop
RETURN leverantor, total_mkr, total_ton, enheter, inkop
ORDER BY total_mkr DESC
"""), "Leverantörskostnader")

# ── 8. Avtalstrohet per enhet ────────────────────────────────────────────────
print("8. Avtalstrohet per enhet...")
save("avtalstrohet_per_enhet", cypher("""
MATCH (e:Enhet)-[:KOPER]->(i:Inkop)
WITH e.namn AS enhet,
     round(sum(i.kronor) / 1000, 1) AS total_tkr,
     round(sum(CASE WHEN i.utanfor_avtal_pct > 0 THEN i.kronor ELSE 0 END) / 1000, 1) AS tkr_utanfor
WHERE total_tkr > 0
RETURN enhet, total_tkr, tkr_utanfor,
       round(tkr_utanfor / total_tkr * 100, 1) AS pct_utanfor
ORDER BY pct_utanfor DESC
LIMIT 15
"""), "Avtalstrohet per enhet")

# ── 9. Ekologisk andel per enhet ─────────────────────────────────────────────
print("9. Ekologisk andel per enhet...")
save("ekologisk_andel", cypher("""
MATCH (e:Enhet)-[:KOPER]->(i:Inkop)
WITH e.namn AS enhet,
     sum(i.kronor) AS total_kr,
     sum(CASE WHEN i.ekologisk = 'Ja' THEN i.kronor ELSE 0 END) AS eko_kr
WHERE total_kr > 0
RETURN enhet,
       round(eko_kr / total_kr * 100, 1) AS eko_andel_pct,
       round(total_kr / 1000, 0) AS total_tkr
ORDER BY eko_andel_pct DESC
"""), "Ekologisk andel per enhet")

# ── 10. Varugrupper kostnad ──────────────────────────────────────────────────
print("10. Varugrupper kostnad...")
save("varugrupper_kostnad", cypher("""
MATCH (i:Inkop)-[:TILLHOR]->(vg:Varugrupp)
WITH vg.namn AS varugrupp,
     round(sum(i.kronor) / 1000, 0) AS total_tkr,
     round(sum(i.kilo), 0) AS total_kg,
     count(i) AS antal_inkop
ORDER BY total_tkr DESC
LIMIT 20
RETURN varugrupp, total_tkr, total_kg, antal_inkop
"""), "Varugrupper kostnad")

# ── 11. Rätter per enhet — topp svinn ────────────────────────────────────────
print("11. Rätter per enhet med högst svinn...")
save("ratter_per_enhet_topp", cypher("""
MATCH (d:Dag)
WHERE d.matratt_norm IS NOT NULL AND d.serverade_portioner > 5 AND d.totalt_svinn_kg > 0
WITH d.enhet AS enhet, d.matratt_norm AS ratt,
     count(*) AS ganger,
     round(avg(d.totalt_svinn_kg / d.serverade_portioner) * 1000, 1) AS snitt_gram_per_portion,
     round(sum(d.totalt_svinn_kg), 1) AS totalt_kg
WHERE ganger >= 2
WITH enhet, collect({ratt: ratt, gram: snitt_gram_per_portion, kg: totalt_kg, ganger: ganger})
     AS ratter_lista
RETURN enhet,
       [r IN ratter_lista | r.ratt + ' (' + toString(r.gram) + 'g/p)'][0..5] AS topp
ORDER BY enhet
"""), "Rätter per enhet topp svinn")

# ── 12. Tallrikssvinn per rätt (skola/ÄO) ───────────────────────────────────
print("12. Rätter med högst tallrikssvinn per portion...")
save("ratter_tallrikssvinn", cypher("""
MATCH (d:Dag)
WHERE d.format = 'skola_ao'
  AND d.matratt_norm IS NOT NULL
  AND d.serverade_portioner > 10
  AND d.tallrikssvinn_kg IS NOT NULL
  AND d.tallrikssvinn_kg > 0
WITH d.matratt_norm AS ratt,
     count(*) AS obs,
     round(avg(d.tallrikssvinn_kg / d.serverade_portioner) * 1000, 1) AS tallrik_gram_per_portion,
     round(sum(d.tallrikssvinn_kg), 1) AS totalt_tallrik_kg
WHERE obs >= 3
RETURN ratt, obs, tallrik_gram_per_portion, totalt_tallrik_kg
ORDER BY tallrik_gram_per_portion DESC
LIMIT 25
"""), "Rätter med högst tallrikssvinn")

# ── 13. Överbeställning per rätt ─────────────────────────────────────────────
print("13. Rätter med störst överbeställning...")
save("overbestallning_per_ratt", cypher("""
MATCH (d:Dag)
WHERE d.matratt_norm IS NOT NULL
  AND d.bestallda_portioner > 0
  AND d.serverade_portioner > 0
WITH d.matratt_norm AS ratt,
     count(*) AS obs,
     round(avg((d.bestallda_portioner - d.serverade_portioner)
               / d.bestallda_portioner * 100), 1) AS snitt_over_pct,
     round(sum(d.bestallda_portioner - d.serverade_portioner), 0) AS total_over_portioner
WHERE obs >= 3
RETURN ratt, obs, snitt_over_pct, total_over_portioner
ORDER BY snitt_over_pct DESC
LIMIT 20
"""), "Rätter med störst överbeställning")

# ── 14. Svinn + näring kvadrant (Python-baserad matchning via dish_name_mapping) ─
print("14. Svinn + näring kvadrantanalys (Python-join med dish_name_mapping.csv)...")

# Ladda rådata
_fw = pd.read_csv("Data/processed/food_waste_daily_v2.csv")
_nr = pd.read_parquet("Data/processed/naring.parquet")
_mp = pd.read_csv("Data/config/dish_name_mapping.csv")

# Rader med svinn och portioner
_fw_kv = _fw.dropna(subset=["matratt_norm", "serverade_portioner", "totalt_svinn_kg"]).copy()
_fw_kv = _fw_kv[(_fw_kv["serverade_portioner"] > 0) & (_fw_kv["totalt_svinn_kg"] > 0)]
_fw_kv["svinn_g_p_rad"] = _fw_kv["totalt_svinn_kg"] * 1000 / _fw_kv["serverade_portioner"]
_fw_kv["tallrik_g_p_rad"] = (
    _fw_kv["tallrikssvinn_kg"].fillna(0) * 1000 / _fw_kv["serverade_portioner"]
)

# Näringstabell: aggregera per rättnamn (tar medelvärde om duplicates)
_nr_agg = _nr.groupby("ratt", as_index=False).agg(
    protein_g=("protein_g", "mean"),
    energi_kcal=("energi_kcal", "mean"),
    fett_g=("fett_g", "mean"),
    kolhydrater_g=("kolhydrater_g", "mean"),
)

# Bygg normaliserings-lookup: ratt_lower → ratt (original namn)
_nr_norm = {r.lower().replace(" ", ""): r for r in _nr_agg["ratt"]}
_nr_exact = {r.lower(): r for r in _nr_agg["ratt"]}

# Bygg mapping-lookup från dish_name_mapping.csv (waste_dish_name → nutrition_dish_name)
_mapping = dict(zip(_mp["waste_dish_name"].str.lower(), _mp["nutrition_dish_name"]))
_mapping_type = dict(zip(_mp["waste_dish_name"].str.lower(), _mp["match_type"]))

def _match_dish(name: str):
    """Returnerar (nutrition_dish_name, match_status) eller (None, 'unmatched')."""
    if not isinstance(name, str):
        return None, "unmatched"
    lo = name.lower().strip()
    # 1. Exakt match på rättnamn i näringsfilen
    if lo in _nr_exact:
        return _nr_exact[lo], "exact"
    # 2. Normaliserad match (lowercase + strip spaces)
    lo_norm = lo.replace(" ", "")
    if lo_norm in _nr_norm:
        return _nr_norm[lo_norm], "normalized"
    # 3. Mapping-tabell
    if lo in _mapping:
        return _mapping[lo], _mapping_type.get(lo, "manual_override")
    return None, "unmatched"

# Matcha varje matratt_norm
_fw_kv["nutrition_dish_name"], _fw_kv["match_status"] = zip(
    *_fw_kv["matratt_norm"].apply(_match_dish)
)

# Aggregera per matchat näringsnyckel
_matched = _fw_kv.dropna(subset=["nutrition_dish_name"]).copy()
_agg = _matched.groupby("nutrition_dish_name", as_index=False).agg(
    obs=("svinn_g_p_rad", "count"),
    svinn_g_p=("svinn_g_p_rad", "mean"),
    tallrik_g_p=("tallrik_g_p_rad", "mean"),
    match_status=("match_status", "first"),
    waste_dish_name=("matratt_norm", "first"),
)

# Lägg till näringsvärden
_agg = _agg.merge(_nr_agg.rename(columns={"ratt": "nutrition_dish_name"}),
                  on="nutrition_dish_name", how="left")

# Filtrera: protein≥5, kcal≥150, obs≥2
_agg = _agg[
    (_agg["obs"] >= 2) &
    (_agg["protein_g"] >= 5) &
    (_agg["energi_kcal"] >= 150)
].copy()

# Avrunda
for col in ["svinn_g_p", "tallrik_g_p", "protein_g", "energi_kcal", "fett_g", "kolhydrater_g"]:
    _agg[col] = _agg[col].round(1)

# Beräkna medianer för kvadrantindelning
_sv_med = float(np.median(_agg["svinn_g_p"])) if len(_agg) > 0 else 30.0
_pr_med = float(np.median(_agg["protein_g"])) if len(_agg) > 0 else 20.0

def _kvadrant(sv, pr):
    if sv >= _sv_med and pr < _pr_med:
        return "hog_svinn_lag_protein"
    if sv < _sv_med and pr >= _pr_med:
        return "lag_svinn_hog_protein"
    if sv >= _sv_med and pr >= _pr_med:
        return "hog_svinn_hog_protein"
    return "lag_svinn_lag_protein"

_agg["kvadrant"] = _agg.apply(lambda r: _kvadrant(r["svinn_g_p"], r["protein_g"]), axis=1)

# Sortera och konvertera till lista av dict
kv_clean = (
    _agg
    .sort_values("svinn_g_p", ascending=False)
    .rename(columns={
        "nutrition_dish_name": "komponent",
        "protein_g": "protein",
        "energi_kcal": "kcal",
        "fett_g": "fett",
        "kolhydrater_g": "kh",
    })
    [["komponent","waste_dish_name","match_status","obs","svinn_g_p","tallrik_g_p","protein","kcal","fett","kh","kvadrant"]]
    .to_dict("records")
)

# Statistik
_n_exact    = sum(1 for r in kv_clean if r["match_status"] == "exact")
_n_norm     = sum(1 for r in kv_clean if r["match_status"] == "normalized")
_n_manual   = sum(1 for r in kv_clean if r["match_status"] == "manual_override")
print(f"  {len(kv_clean)} rätter: {_n_exact} exact, {_n_norm} normalized, {_n_manual} manual_override")
save("svinn_naring_kvadrant", kv_clean, f"Svinn+näring kvadrant ({len(kv_clean)} rätter, Python-join)")

# ── 14b. Kvadrant funnel audit ────────────────────────────────────────────────
print("14b. Kvadrant funnel audit...")

# Alla rader med svinn och portioner (oavsett obs-antal)
_fw_all = pd.read_csv("Data/processed/food_waste_daily_v2.csv")
_fw_all_b = _fw_all.dropna(subset=["matratt_norm", "serverade_portioner", "totalt_svinn_kg"]).copy()
_fw_all_b = _fw_all_b[(_fw_all_b["serverade_portioner"] > 0) & (_fw_all_b["totalt_svinn_kg"] > 0)]
_fw_all_b["_sgp"] = _fw_all_b["totalt_svinn_kg"] * 1000 / _fw_all_b["serverade_portioner"]

_fw_all_agg = _fw_all_b.groupby("matratt_norm").agg(
    obs     =("_sgp",            "count"),
    svinn_g_p=("_sgp",           "mean"),
    total_kg =("totalt_svinn_kg", "sum"),
).reset_index()
_fw_all_agg["nutrition_dish"], _fw_all_agg["match_status"] = zip(
    *_fw_all_agg["matratt_norm"].apply(_match_dish)
)
_nr_dict = _nr_agg.rename(columns={"ratt": "nutrition_dish_name"}).set_index("nutrition_dish_name").to_dict("index")
_fw_all_agg["protein_g"]   = _fw_all_agg["nutrition_dish"].map(lambda x: _nr_dict.get(x,{}).get("protein_g") if x else None)
_fw_all_agg["energi_kcal"] = _fw_all_agg["nutrition_dish"].map(lambda x: _nr_dict.get(x,{}).get("energi_kcal") if x else None)

_step_c = _fw_all_agg[_fw_all_agg["obs"] >= 2]
_d_exact   = _step_c[_step_c["match_status"] == "exact"]
_d_norm    = _step_c[_step_c["match_status"] == "normalized"]
_d_manual  = _step_c[_step_c["match_status"] == "manual_override"]
_d_unmatch = _step_c[_step_c["match_status"] == "unmatched"]
_d_matched = _step_c[_step_c["match_status"] != "unmatched"]
_e_fail    = _d_matched[_d_matched["protein_g"].fillna(0) < 5]
_f_fail    = _d_matched[(_d_matched["protein_g"].fillna(0) >= 5) & (_d_matched["energi_kcal"].fillna(0) < 150)]

_g_names   = {r["komponent"] for r in kv_clean}

_funnel = {
    "generated": "2026-06-11",
    "steps": [
        {"step": "A", "label": "Alla unika matratt_norm i svinndatan",
         "ratter": int(_fw_all["matratt_norm"].nunique()),
         "obs":    int(_fw_all["matratt_norm"].notna().sum())},
        {"step": "B", "label": "Har svinn>0 och portioner>0",
         "ratter": int(_fw_all_b["matratt_norm"].nunique()),
         "obs":    int(len(_fw_all_b))},
        {"step": "C", "label": "Minst 2 observationer",
         "ratter": int(len(_step_c)),
         "obs":    int(_step_c["obs"].sum())},
        {"step": "D_exact",      "label": "Matchad exact",
         "ratter": int(len(_d_exact)),   "obs": int(_d_exact["obs"].sum())},
        {"step": "D_normalized", "label": "Matchad normalized",
         "ratter": int(len(_d_norm)),    "obs": int(_d_norm["obs"].sum())},
        {"step": "D_manual",     "label": "Matchad manual_override",
         "ratter": int(len(_d_manual)),  "obs": int(_d_manual["obs"].sum())},
        {"step": "D_unmatched",  "label": "Omatchad (generisk förkortning)",
         "ratter": int(len(_d_unmatch)), "obs": int(_d_unmatch["obs"].sum())},
        {"step": "E_fail",       "label": "Protein < 5g",
         "ratter": int(len(_e_fail)),    "obs": int(_e_fail["obs"].sum()) if len(_e_fail) else 0},
        {"step": "F_fail",       "label": "Kcal < 150",
         "ratter": int(len(_f_fail)),    "obs": int(_f_fail["obs"].sum()) if len(_f_fail) else 0},
        {"step": "G",            "label": "Visas i kvadrantdiagrammet",
         "ratter": int(len(kv_clean)),
         "obs":    int(sum(r["obs"] for r in kv_clean))},
    ],
    "matching_coverage": {
        "total_obs_ge2":    int(len(_step_c)),
        "matched":          int(len(_d_matched)),
        "unmatched":        int(len(_d_unmatch)),
        "match_rate_pct":   round(len(_d_matched) / len(_step_c) * 100, 1) if len(_step_c) else 0,
    },
    "top10_excluded_by_waste_kg": [],
}

# Top 10 exkluderade (obs>=2 men inte i G)
_excl_c = _step_c[~_step_c["nutrition_dish"].isin(_g_names)].sort_values("total_kg", ascending=False)
def _exc_reason(row):
    if row["match_status"] == "unmatched":
        return "unmatched_nutrition"
    if (row["protein_g"] or 0) < 5:
        return "protein_below_5"
    if (row["energi_kcal"] or 0) < 150:
        return "energy_below_150"
    return "aggregated_into_other_dish"

_funnel["top10_excluded_by_waste_kg"] = [
    {"matratt_norm": r["matratt_norm"], "obs": int(r["obs"]),
     "total_kg": round(float(r["total_kg"]), 1),
     "svinn_g_p": round(float(r["svinn_g_p"]), 1),
     "match_status": r["match_status"],
     "nutrition_dish": r["nutrition_dish"] or "",
     "protein_g": round(float(r["protein_g"]), 1) if r["protein_g"] is not None else None,
     "energi_kcal": round(float(r["energi_kcal"]), 1) if r["energi_kcal"] is not None else None,
     "exclusion_reason": _exc_reason(r)}
    for _, r in _excl_c.head(10).iterrows()
]

save("kvadrant_funnel", _funnel, "Kvadrant funnel audit (A→G)")

# Exkluderingslista CSV
def _full_exc_reason(row):
    if row["obs"] < 2:
        return "fewer_than_2_observations"
    if row["match_status"] == "unmatched":
        return "unmatched_nutrition"
    if (row["protein_g"] or 0) < 5:
        return "protein_below_5"
    if (row["energi_kcal"] or 0) < 150:
        return "energy_below_150"
    if row["nutrition_dish"] in _g_names:
        return ""
    return "aggregated_into_other_dish"

_fw_all_agg["exclusion_reason"] = _fw_all_agg.apply(_full_exc_reason, axis=1)
_exc_csv = _fw_all_agg[_fw_all_agg["exclusion_reason"] != ""].copy()
_exc_csv = _exc_csv.sort_values("total_kg", ascending=False)
_exc_csv.rename(columns={"nutrition_dish": "matched_nutrition_dish"})[
    ["matratt_norm","obs","total_kg","svinn_g_p","match_status",
     "matched_nutrition_dish","protein_g","energi_kcal","exclusion_reason"]
].to_csv(OUT / "kvadrant_exclusion_audit.csv", index=False, float_format="%.1f")
print(f"  ✅ kvadrant_exclusion_audit.csv: {len(_exc_csv)} exkluderade rätter")

# ── 15. Svinn + näring per rätt (utökad tabell) ──────────────────────────────
print("15. Svinn + näring per rätt (utökad)...")
save("svinn_naring_per_ratt", cypher("""
MATCH (d:Dag)-[:SERVERADE]->(r:Ratt)-[:HAR_NARING]->(n:Naring)
WHERE d.serverade_portioner > 0 AND d.totalt_svinn_kg > 0
  AND n.protein_g >= 5 AND n.energi_kcal >= 150
WITH n.ratt AS ratt,
     count(*) AS obs,
     round(avg(d.totalt_svinn_kg / d.serverade_portioner) * 1000, 1) AS svinn_g_p,
     round(avg(d.tallrikssvinn_kg / d.serverade_portioner) * 1000, 1) AS tallrik_g_p,
     round(avg(n.protein_g), 1) AS protein,
     round(avg(n.energi_kcal), 1) AS kcal,
     round(avg(n.fett_g), 1) AS fett,
     round(avg(n.kolhydrater_g), 1) AS kh
WHERE obs >= 2
RETURN ratt, svinn_g_p, tallrik_g_p, protein, kcal, fett, kh, obs
ORDER BY svinn_g_p DESC
"""), "Svinn + näring per rätt")

# ── 16. Konsumerad näring per rätt ───────────────────────────────────────────
print("16. Konsumerad näring per rätt...")
save("konsumerad_naring", cypher("""
MATCH (d:Dag)-[:SERVERADE]->(r:Ratt)-[:HAR_NARING]->(n:Naring)
WHERE d.serverade_portioner > 0 AND n.protein_g >= 5 AND n.energi_kcal >= 150
WITH n.ratt AS ratt,
     count(*) AS obs,
     round(avg(n.protein_g), 1) AS protein_serverad_g,
     round(avg(n.energi_kcal), 1) AS kcal_serverad,
     round(avg(d.totalt_svinn_pct), 3) AS svinn_pct,
     round(avg(d.totalt_svinn_kg / d.serverade_portioner) * 1000, 1) AS svinn_g_p,
     round(avg(n.protein_g * (1 - coalesce(d.totalt_svinn_pct, 0))), 1) AS protein_konsumerad_g,
     round(avg(n.energi_kcal * (1 - coalesce(d.totalt_svinn_pct, 0))), 1) AS kcal_konsumerad
WHERE obs >= 2
RETURN ratt, protein_konsumerad_g, kcal_konsumerad, protein_serverad_g, kcal_serverad,
       svinn_pct, obs, svinn_g_p
ORDER BY protein_konsumerad_g DESC
LIMIT 30
"""), "Konsumerad näring per rätt")

# ── 17. Rätter med ofta högt svinn ───────────────────────────────────────────
print("17. Rätter med ofta högt svinn...")
save("ratter_ofta_hog_svinn", cypher("""
MATCH (d:Dag)-[:SERVERADE]->(rt:Ratt)
WHERE d.totalt_svinn_pct IS NOT NULL AND d.totalt_svinn_pct > 0
  AND d.totalt_svinn_pct <= 1.0
WITH rt.namn AS ratt,
     count(*) AS antal_ganger_serverad,
     round(avg(d.totalt_svinn_pct) * 100, 2) AS snitt_svinn_pct
WITH ratt, antal_ganger_serverad, snitt_svinn_pct,
     round(snitt_svinn_pct * antal_ganger_serverad, 1) AS svinn_index
WHERE antal_ganger_serverad >= 3 AND snitt_svinn_pct > 5
RETURN ratt, 'alla' AS menytyp, antal_ganger_serverad, snitt_svinn_pct, svinn_index
ORDER BY svinn_index DESC
LIMIT 20
"""), "Rätter med ofta högt svinn")

driver.close()
print(f"\n✅ Alla {len(list(OUT.glob('*.json')))} analyser sparade i {OUT}/")
