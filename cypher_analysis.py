"""
Kör förberedda Cypher-analyser mot lokal Neo4j och sparar verifierade
resultat som JSON i Data/analysis/. Används av AI-assistenten som
förankrad kontext — ingen live-querying i produktion.
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

# ── 1. Rätter med högst svinn (direkt koppling, ej approximation) ────────────
print("\n1. Rätter med högst totalt svinn...")
save("ratter_hog_svinn", cypher("""
MATCH (e:Enhet)-[:HAR_DAG]->(d:Dag)
WHERE d.ratt IS NOT NULL AND d.total_svinn_kg > 0
WITH d.ratt AS ratt,
     count(*) AS antal_dagar,
     round(avg(d.total_svinn_kg), 2) AS snitt_svinn_kg,
     round(sum(d.total_svinn_kg), 1) AS totalt_svinn_kg,
     round(avg(CASE WHEN d.serverade_portioner > 0
               THEN d.total_svinn_kg / d.serverade_portioner ELSE null END), 4) AS svinn_kg_per_portion
ORDER BY totalt_svinn_kg DESC
LIMIT 30
RETURN ratt, antal_dagar, snitt_svinn_kg, totalt_svinn_kg,
       round(svinn_kg_per_portion * 1000, 1) AS svinn_gram_per_portion
"""), "Rätter med högst svinn")

# ── 2. Rätter med högst svinn per serverad portion ───────────────────────────
print("2. Rätter med högst svinn per portion...")
save("ratter_svinn_per_portion", cypher("""
MATCH (e:Enhet)-[:HAR_DAG]->(d:Dag)
WHERE d.ratt IS NOT NULL AND d.serverade_portioner > 10 AND d.total_svinn_kg > 0
WITH d.ratt AS ratt,
     count(*) AS antal_dagar,
     round(avg(d.total_svinn_kg / d.serverade_portioner) * 1000, 1) AS snitt_gram_per_portion,
     round(sum(d.total_svinn_kg), 1) AS totalt_svinn_kg
WHERE antal_dagar >= 3
RETURN ratt, antal_dagar, snitt_gram_per_portion, totalt_svinn_kg
ORDER BY snitt_gram_per_portion DESC
LIMIT 25
"""), "Rätter med högst svinn per portion")

# ── 3. Rätter med lägst svinn (bäst praxis) ─────────────────────────────────
print("3. Rätter med lägst svinn per portion (bäst praxis)...")
save("ratter_lag_svinn", cypher("""
MATCH (e:Enhet)-[:HAR_DAG]->(d:Dag)
WHERE d.ratt IS NOT NULL AND d.serverade_portioner > 10 AND d.total_svinn_kg > 0
WITH d.ratt AS ratt,
     count(*) AS antal_dagar,
     round(avg(d.total_svinn_kg / d.serverade_portioner) * 1000, 1) AS snitt_gram_per_portion,
     round(sum(d.total_svinn_kg), 1) AS totalt_svinn_kg
WHERE antal_dagar >= 5
RETURN ratt, antal_dagar, snitt_gram_per_portion, totalt_svinn_kg
ORDER BY snitt_gram_per_portion ASC
LIMIT 20
"""), "Rätter med lägst svinn")

# ── 4. Svinn per veckodag ────────────────────────────────────────────────────
print("4. Svinn per veckodag...")
save("svinn_per_veckodag", cypher("""
MATCH (e:Enhet)-[:HAR_DAG]->(d:Dag)
WHERE d.veckodag <> '' AND d.total_svinn_kg > 0 AND d.serverade_portioner > 0
WITH d.veckodag AS veckodag, d.veckodag_num AS num,
     round(avg(d.total_svinn_kg / d.serverade_portioner) * 1000, 1) AS snitt_gram_per_portion,
     round(avg(d.total_svinn_kg), 2) AS snitt_svinn_kg,
     count(*) AS observationer
RETURN veckodag, snitt_gram_per_portion, snitt_svinn_kg, observationer
ORDER BY num
"""), "Svinn per veckodag")

# ── 5. Enheter — svinnranking med rättstatistik ──────────────────────────────
print("5. Enheter svinnranking...")
save("enheter_svinn_ranking", cypher("""
MATCH (e:Enhet)-[:HAR_DAG]->(d:Dag)
WHERE d.total_svinn_kg > 0
WITH e.namn AS enhet, e.kategori AS kategori,
     count(d) AS antal_dagar,
     round(sum(d.total_svinn_kg), 1) AS total_svinn_kg,
     round(avg(d.total_svinn_kg), 2) AS snitt_svinn_kg_per_dag,
     round(avg(CASE WHEN d.serverade_portioner > 0
               THEN d.total_svinn_kg / d.serverade_portioner ELSE null END) * 1000, 1) AS snitt_gram_per_portion,
     sum(CASE WHEN d.ratt IS NOT NULL THEN 1 ELSE 0 END) AS dagar_med_ratt
RETURN enhet, kategori, antal_dagar, total_svinn_kg,
       snitt_svinn_kg_per_dag, snitt_gram_per_portion,
       round(toFloat(dagar_med_ratt) / antal_dagar * 100, 0) AS rattnamn_tackning_pct
ORDER BY snitt_gram_per_portion DESC
"""), "Enheter svinnranking")

# ── 6. Tallrikssvinn vs serveringssvinn per enhet ───────────────────────────
print("6. Svinntyper per enhet...")
save("svinntyper_per_enhet", cypher("""
MATCH (e:Enhet)-[:HAR_DAG]->(d:Dag)
WHERE d.total_svinn_kg > 0 AND d.serverade_portioner > 0
WITH e.namn AS enhet,
     round(avg(d.tallriks_svinn_kg / d.serverade_portioner) * 1000, 1) AS tallrik_gram_per_portion,
     round(avg(d.serverings_svinn_kg / d.serverade_portioner) * 1000, 1) AS servering_gram_per_portion,
     round(avg(d.koks_svinn_kg / d.serverade_portioner) * 1000, 1) AS koks_gram_per_portion,
     count(d) AS dagar
WHERE dagar >= 10
RETURN enhet, tallrik_gram_per_portion, servering_gram_per_portion,
       koks_gram_per_portion, dagar
ORDER BY tallrik_gram_per_portion DESC
"""), "Svinntyper per enhet")

# ── 7. Leverantörer ──────────────────────────────────────────────────────────
print("7. Leverantörer...")
save("leverantorer_kostnad", cypher("""
MATCH (e:Enhet)-[:KOPER]->(i:Inkop)-[:FRAN]->(l:Leverantor)
WHERE l.namn <> 'Okänd'
WITH l.namn AS leverantor,
     round(sum(i.kronor) / 1000000, 2) AS total_mkr,
     round(sum(i.kilo) / 1000, 1) AS total_ton,
     count(DISTINCT e) AS antal_enheter,
     count(i) AS antal_inkop
RETURN leverantor, total_mkr, total_ton, antal_enheter, antal_inkop
ORDER BY total_mkr DESC
"""), "Leverantörskostnader")

# ── 8. Avtalstrohet per enhet ────────────────────────────────────────────────
print("8. Avtalstrohet per enhet...")
save("avtalstrohet_per_enhet", cypher("""
MATCH (e:Enhet)-[:KOPER]->(i:Inkop)
WITH e.namn AS enhet,
     round(sum(i.kronor) / 1000, 0) AS total_tkr,
     round(avg(i.utanfor_avtal_pct) * 100, 1) AS snitt_utanfor_avtal_pct,
     round(sum(CASE WHEN i.utanfor_avtal_pct > 0 THEN i.kronor ELSE 0 END) / 1000, 0) AS tkr_utanfor_avtal
WHERE total_tkr > 0
RETURN enhet, total_tkr, snitt_utanfor_avtal_pct, tkr_utanfor_avtal
ORDER BY snitt_utanfor_avtal_pct DESC
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
MATCH (e:Enhet)-[:HAR_DAG]->(d:Dag)
WHERE d.ratt IS NOT NULL AND d.serverade_portioner > 5 AND d.total_svinn_kg > 0
WITH e.namn AS enhet, d.ratt AS ratt,
     count(*) AS ganger,
     round(avg(d.total_svinn_kg / d.serverade_portioner) * 1000, 1) AS snitt_gram_per_portion,
     round(sum(d.total_svinn_kg), 1) AS totalt_kg
WHERE ganger >= 2
WITH enhet, collect({ratt: ratt, gram: snitt_gram_per_portion, kg: totalt_kg, ganger: ganger})
     AS ratter_lista
RETURN enhet,
       [r IN ratter_lista | r.ratt + ' (' + toString(r.gram) + 'g/p)'][0..5] AS topp5_ratter
ORDER BY enhet
"""), "Rätter per enhet topp svinn")

driver.close()
print(f"\n✅ Alla {len(list(OUT.glob('*.json')))} analyser sparade i {OUT}/")
