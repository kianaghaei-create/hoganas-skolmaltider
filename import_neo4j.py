"""
Importerar Höganäs skolmåltidsdata till Neo4j med korrekt granularitet.

Nodstruktur:
  Enhet -[HAR_DAG]-> Dag (per dag, med rättnamn + svinn)
  Enhet -[KOPER]-> Inkop -[FRAN]-> Leverantor
                         -[TILLHOR]-> Varugrupp
  Enhet -[SERVERAR]-> Portion

Join-logik svinn↔rätt:
  food_waste_daily (unit_name + week + weekday)
  join på enhet-kategori (skola/ao) + week + weekday
  menu_nutrition (menu_type + week + weekday → dish_name)
"""
from neo4j import GraphDatabase
import pandas as pd
from pathlib import Path

URI  = "bolt://localhost:7687"
AUTH = ("neo4j", "hoganas2025")
DATA = Path("Data/processed")

driver = GraphDatabase.driver(URI, auth=AUTH)

def run(q, params=None):
    with driver.session() as s:
        s.run(q, params or {})

def run_many(q, rows):
    with driver.session() as s:
        s.run(q, {"rows": rows})

# ── Rensa allt ──────────────────────────────────────────────────────────────
print("Rensar befintlig data...")
run("MATCH (n) DETACH DELETE n")

print("Skapar index...")
run("CREATE INDEX enhet_namn IF NOT EXISTS FOR (e:Enhet) ON (e.namn)")

# ── Ladda rådata ─────────────────────────────────────────────────────────────
fw = pd.read_parquet(DATA / "food_waste_daily.parquet")
mn = pd.read_parquet(DATA / "menu_nutrition.parquet")
pu = pd.read_csv(DATA / "purchases.csv", low_memory=False)
po = pd.read_parquet(DATA / "portions.parquet")

# ── Kategorisera enheter ─────────────────────────────────────────────────────
AO_ENHETER = {"Nyhamnsgården", "Väsbyhemmet", "Vikhaga"}

def enhet_kategori(namn: str) -> str:
    if namn in AO_ENHETER:
        return "ao"
    if "förskola" in namn.lower():
        return "förskola"
    return "skola"

# ── Bygg meny-lookup: (menu_type, vecka, veckodag) → [rättnamn] ──────────────
dag_norm = {"måndag": "Måndag", "tisdag": "Tisdag", "onsdag": "Onsdag",
            "torsdag": "Torsdag", "fredag": "Fredag",
            "Måndag": "Måndag", "Tisdag": "Tisdag", "Onsdag": "Onsdag",
            "Torsdag": "Torsdag", "Fredag": "Fredag"}

# Menyn lagrar veckodag som siffra (1=Mån, 2=Tis, 3=Ons, 4=Tor, 5=Fre)
dag_num_to_name = {1: "Måndag", 2: "Tisdag", 3: "Onsdag", 4: "Torsdag", 5: "Fredag",
                   1.0: "Måndag", 2.0: "Tisdag", 3.0: "Onsdag", 4.0: "Torsdag", 5.0: "Fredag"}

mn_clean = mn.dropna(subset=["week", "weekday", "dish_name"]).copy()
mn_clean["weekday"] = mn_clean["weekday"].map(dag_num_to_name).fillna(
                      mn_clean["weekday"].map(dag_norm)).fillna(mn_clean["weekday"])
mn_clean["week"]    = mn_clean["week"].astype(int)

menu_lookup = {}
for _, r in mn_clean.iterrows():
    key = (r["menu_type"], int(r["week"]), r["weekday"])
    menu_lookup.setdefault(key, []).append(r["dish_name"])

print(f"  Meny-lookup: {len(menu_lookup)} kombinationer (menu_type + vecka + veckodag)")

# ── ENHETER ──────────────────────────────────────────────────────────────────
print("Importerar enheter...")
units = (set(fw["unit_name"].dropna()) |
         set(po["unit_name"].dropna()) |
         set(pu["unit_name_std"].dropna() if "unit_name_std" in pu.columns else []))

run_many(
    "UNWIND $rows AS row MERGE (e:Enhet {namn: row.namn}) SET e.kategori = row.kategori",
    [{"namn": u, "kategori": enhet_kategori(u)} for u in units]
)
print(f"  {len(units)} enheter")

# ── SVINN PER DAG med rättnamn ───────────────────────────────────────────────
print("Importerar dagligt svinn med rättnamn...")
fw_rows = []
for _, r in fw.iterrows():
    enhet = r["unit_name"]
    week  = int(r["week"]) if pd.notna(r["week"]) else 0
    wday  = dag_norm.get(str(r["weekday"]), str(r["weekday"])) if pd.notna(r.get("weekday")) else ""
    kat   = enhet_kategori(enhet)
    menu_kat = "ao" if kat == "ao" else "skola"

    # Rättnamn: svinnfilen prioriteras, annars meny-join
    dish_raw = r.get("dish_name_raw")
    if pd.notna(dish_raw) and str(dish_raw).strip():
        ratt       = str(dish_raw).strip()
        ratt_kalla = "svinnfil"
    else:
        ratter     = menu_lookup.get((menu_kat, week, wday), [])
        ratt       = "; ".join(ratter) if ratter else None
        ratt_kalla = "meny" if ratt else "saknas"

    fw_rows.append({
        "enhet":         enhet,
        "vecka":         week,
        "veckodag":      wday,
        "veckodag_num":  int(r["weekday_num"]) if pd.notna(r.get("weekday_num")) else 0,
        "ratt":          ratt,
        "ratt_kalla":    ratt_kalla,
        "bestallda":     float(r["ordered_portions"]) if pd.notna(r.get("ordered_portions")) else 0,
        "serverade":     float(r["served_portions"])  if pd.notna(r.get("served_portions"))  else 0,
        "koks_kg":       float(r["kitchen_waste_kg"]) if pd.notna(r.get("kitchen_waste_kg")) else 0,
        "servering_kg":  float(r["serving_waste_kg"]) if pd.notna(r.get("serving_waste_kg")) else 0,
        "tallrik_kg":    float(r["plate_waste_kg"])   if pd.notna(r.get("plate_waste_kg"))   else 0,
        "total_kg":      float(r["total_waste_kg"])   if pd.notna(r.get("total_waste_kg"))   else 0,
        "portions_vikt": float(r["portion_weight_g"]) if pd.notna(r.get("portion_weight_g")) else 0,
    })

run_many("""
UNWIND $rows AS row
MERGE (e:Enhet {namn: row.enhet})
CREATE (d:Dag {
    vecka:               row.vecka,
    veckodag:            row.veckodag,
    veckodag_num:        row.veckodag_num,
    ratt:                row.ratt,
    ratt_kalla:          row.ratt_kalla,
    bestallda_portioner: row.bestallda,
    serverade_portioner: row.serverade,
    koks_svinn_kg:       row.koks_kg,
    serverings_svinn_kg: row.servering_kg,
    tallriks_svinn_kg:   row.tallrik_kg,
    total_svinn_kg:      row.total_kg,
    portions_vikt_g:     row.portions_vikt
})
MERGE (e)-[:HAR_DAG]->(d)
""", fw_rows)

with_dish   = sum(1 for r in fw_rows if r["ratt"])
from_waste  = sum(1 for r in fw_rows if r["ratt_kalla"] == "svinnfil")
from_menu   = sum(1 for r in fw_rows if r["ratt_kalla"] == "meny")
missing     = sum(1 for r in fw_rows if r["ratt_kalla"] == "saknas")
print(f"  {len(fw_rows)} dagar importerade")
print(f"  {from_waste} rättnamn från svinnfil")
print(f"  {from_menu} rättnamn från meny-join")
print(f"  {missing} dagar utan rättnamn (enhet fyllde inte i)")

# ── INKÖP ────────────────────────────────────────────────────────────────────
print("Importerar inköp...")
pu_rows = []
for _, r in pu.iterrows():
    pu_rows.append({
        "enhet":         str(r.get("unit_name_std") or r.get("enhet", "Okänd")),
        "leverantor":    str(r["supplier"]) if pd.notna(r.get("supplier")) else "Okänd",
        "varugrupp":     str(r["varugrupp"]) if pd.notna(r.get("varugrupp")) else "Okänd",
        "artikel":       str(r["article_name"]) if pd.notna(r.get("article_name")) else "Okänd",
        "kronor":        float(r.get("kronor") or 0),
        "kilo":          float(r.get("kilo") or 0),
        "ekologisk":     str(r.get("ekologisk", "Nej")),
        "utanfor_avtal": float(r.get("procent_utanfor_avtal") or 0),
        "manad":         int(r["month"]) if pd.notna(r.get("month")) else 0,
        "ar":            int(r["year"])  if pd.notna(r.get("year"))  else 2025,
        "varuomrade":    str(r.get("varuomrade", "")),
        "land":          str(r.get("produktens_tillverkningsland", "")),
    })

for i in range(0, len(pu_rows), 500):
    run_many("""
UNWIND $rows AS row
MERGE (e:Enhet {namn: row.enhet})
MERGE (l:Leverantor {namn: row.leverantor})
MERGE (vg:Varugrupp {namn: row.varugrupp})
CREATE (i:Inkop {
    artikel: row.artikel, kronor: row.kronor, kilo: row.kilo,
    ekologisk: row.ekologisk, utanfor_avtal_pct: row.utanfor_avtal,
    manad: row.manad, ar: row.ar,
    varuomrade: row.varuomrade, tillverkningsland: row.land
})
MERGE (e)-[:KOPER]->(i)
MERGE (i)-[:FRAN]->(l)
MERGE (i)-[:TILLHOR]->(vg)
""", pu_rows[i:i+500])
print(f"  {len(pu_rows)} inköp importerade")

# ── PORTIONER ────────────────────────────────────────────────────────────────
print("Importerar portioner...")
po_rows = [{"enhet": str(r["unit_name"]),
            "ar":    int(r["year"])  if pd.notna(r.get("year"))  else 2025,
            "manad": int(r["month"]) if pd.notna(r.get("month")) else 0,
            "typ":   str(r.get("portion_type", "okänd")),
            "antal": float(r.get("count") or 0)}
           for _, r in po.iterrows()]
run_many("""
UNWIND $rows AS row
MERGE (e:Enhet {namn: row.enhet})
CREATE (p:Portion {ar: row.ar, manad: row.manad, typ: row.typ, antal: row.antal})
MERGE (e)-[:SERVERAR]->(p)
""", po_rows)
print(f"  {len(po_rows)} portioner importerade")

# ── VERIFIERA ────────────────────────────────────────────────────────────────
print("\nVerifierar...")
with driver.session() as s:
    counts = s.run("MATCH (n) RETURN labels(n)[0] AS typ, count(n) AS antal ORDER BY antal DESC")
    print("\n✅ Neo4j innehåller nu:")
    for row in counts:
        print(f"  {row['typ']}: {row['antal']}")

    sample = s.run("""
MATCH (e:Enhet)-[:HAR_DAG]->(d:Dag)
WHERE d.ratt IS NOT NULL AND d.total_svinn_kg > 0
RETURN e.namn AS enhet, d.vecka AS vecka, d.veckodag AS dag,
       d.ratt AS ratt, d.total_svinn_kg AS svinn_kg
ORDER BY d.total_svinn_kg DESC LIMIT 5
""")
    print("\nTop 5 dagar med högst svinn och rättnamn:")
    for r in sample:
        print(f"  {r['enhet']} v{r['vecka']} {r['dag']}: {r['ratt'][:40]} → {r['svinn_kg']} kg")

driver.close()
print("\n✅ Import klar!")
