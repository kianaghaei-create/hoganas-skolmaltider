"""
Kör förberedda Cypher-analyser mot lokal Neo4j och sparar verifierade
resultat som JSON i Data/analysis/. Används av AI-assistenten som
förankrad kontext — ingen live-querying i produktion.

Uppdaterad 2026-06-11: anpassad till nya egenskapsnamn efter Neo4j-reimport
från food_waste_daily_v2.csv. Egenskapsnamn matchar nu CSV-kolumner direkt.
"""
from neo4j import GraphDatabase
import json
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

# ── 14. Svinn + näring kvadrant (via SERVERADE→Ratt→HAR_NARING→Naring) ──────
print("14. Svinn + näring kvadrantanalys (alla verksamhetstyper)...")
# Filtrerar bort troliga felmatchningar: protein<5g eller kcal<150
raw_kv = cypher("""
MATCH (d:Dag)-[:SERVERADE]->(r:Ratt)-[:HAR_NARING]->(n:Naring)
WHERE d.serverade_portioner > 0 AND d.totalt_svinn_kg > 0
  AND n.protein_g >= 5 AND n.energi_kcal >= 150
WITH n.ratt AS komponent,
     count(*) AS obs,
     round(avg(d.totalt_svinn_kg / d.serverade_portioner) * 1000, 1) AS svinn_g_p,
     round(avg(d.tallrikssvinn_kg / d.serverade_portioner) * 1000, 1) AS tallrik_g_p,
     round(avg(n.protein_g), 1) AS protein,
     round(avg(n.energi_kcal), 1) AS kcal,
     round(avg(n.fett_g), 1) AS fett,
     round(avg(n.kolhydrater_g), 1) AS kh
WHERE obs >= 2
RETURN komponent, obs, svinn_g_p, tallrik_g_p, protein, kcal, fett, kh
ORDER BY svinn_g_p DESC
""")

# Beräkna medianer för kvadrantindelning
svinn_vals = sorted([r["svinn_g_p"] for r in raw_kv if r.get("svinn_g_p")])
prot_vals  = sorted([r["protein"]   for r in raw_kv if r.get("protein")])
if svinn_vals and prot_vals:
    svinn_med = svinn_vals[len(svinn_vals)//2]
    prot_med  = prot_vals[len(prot_vals)//2]
else:
    svinn_med, prot_med = 30, 20

for r in raw_kv:
    sv = r.get("svinn_g_p", 0) or 0
    pr = r.get("protein", 0) or 0
    if sv >= svinn_med and pr < prot_med:
        r["kvadrant"] = "hog_svinn_lag_protein"
    elif sv < svinn_med and pr >= prot_med:
        r["kvadrant"] = "lag_svinn_hog_protein"
    elif sv >= svinn_med and pr >= prot_med:
        r["kvadrant"] = "hog_svinn_hog_protein"
    else:
        r["kvadrant"] = "lag_svinn_lag_protein"

# Ta bort känt matchningsfel
kv_clean = [r for r in raw_kv
            if not str(r.get("komponent","")).lower().startswith("fiskgratäng serveras med potatismos")]
save("svinn_naring_kvadrant", kv_clean, f"Svinn+näring kvadrant ({len(kv_clean)} rätter)")

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
