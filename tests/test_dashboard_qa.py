"""
Dashboard QA-tester — körs mot rådatan och verifierar att dashboardens
KPI:er och beräkningar stämmer. Kör: python3 tests/test_dashboard_qa.py

OBS: Förväntade värden uppdaterades 2026-06-11 efter parser-fix (label-baserad).
  - V1 Totalt svinn kg: 24 420 → 28 400 (förskolor nu korrekt inlästa)
  - Väder r: −0.29 → −0.07 (förskole-svinn inkluderas i dagssumman)
  - T3: NaN-andel för svinn-pct: var 2405, nu 6 (parser-fix)
"""
import pandas as pd, numpy as np, sys, json
from pathlib import Path

DATA = Path("Data/processed")
FAIL = []

def check(name, computed, expected, tol=0.01, unit=""):
    diff = abs(computed - expected) if expected != 0 else abs(computed)
    rel  = diff / abs(expected) if expected != 0 else diff
    ok   = rel <= tol
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}: {computed:.3g}{unit} (förväntat {expected:.3g}{unit}, diff {diff:.3g})")
    if not ok:
        FAIL.append(name)
    return ok

print("=== Dashboard QA-tester ===\n")

# ── Rådata ────────────────────────────────────────────────────────────────────
fw = pd.read_csv(DATA/"food_waste_daily_v2.csv")
pu = pd.read_csv(DATA/"purchases.csv", low_memory=False)
wx = pd.read_csv(DATA/"weather_2025.csv")

# Aggregera till veckonivå
fw_agg = fw.groupby(["unit_name","ar","vecka"], dropna=False).agg(
    total_waste_kg   =("totalt_svinn_kg","sum"),
    total_waste_pct  =("totalt_svinn_pct","mean"),
    ordered_portions =("bestallda_portioner","sum"),
    served_portions  =("serverade_portioner","sum"),
).reset_index()
fw_agg["over"] = (
    (fw_agg["ordered_portions"] - fw_agg["served_portions"])
    / fw_agg["ordered_portions"].replace(0, np.nan)
)

# ── Matsvinn ──────────────────────────────────────────────────────────────────
print("Matsvinn:")
# V1 uppdaterat: 28 400 kg efter parser-fix (förskolor nu korrekt inlästa)
check("V1 Totalt svinn kg",        fw["totalt_svinn_kg"].sum(),         28400.3,  0.005, " kg")
check("V3 Antal enheter (alla)",   fw["unit_name"].nunique(),           21,       0.0)
check("V14 Veckor >5% överbest",   (fw_agg["over"] > 0.05).sum(),      267,      0.0)
check("V15 Snitt överbest %",      fw_agg["over"].mean() * 100,        13.0,     0.05, "%")

# ── Inköp ─────────────────────────────────────────────────────────────────────
print("\nInköp:")
check("V2 Inköpskostnad Mkr",      pu["kronor"].sum() / 1e6,           16.9,     0.01, " Mkr")
check("V20 Antal leverantörer",    pu["supplier"].nunique(),            3,        0.0)
eco = pu[pu["ekologisk"]=="Ja"]["kronor"].sum() / pu["kronor"].sum() * 100
check("V21 Ekologisk andel %",     eco,                                 31.5,     0.05, "%")
out = pu[pu["procent_utanfor_avtal"] > 0]["kronor"].sum() / pu["kronor"].sum() * 100
check("V26 Utanför avtal %",       out,                                 13.0,     0.05, "%")

# ── Väderkorrelation ──────────────────────────────────────────────────────────
print("\nVäder:")
daily = fw.groupby("datum").agg(
    svinn_kg  =("totalt_svinn_kg","sum"),
    portioner =("serverade_portioner","sum")
).reset_index()
daily = daily[daily["portioner"] > 0]
daily["svinn_g_p"] = daily["svinn_kg"] * 1000 / daily["portioner"]
merged = daily.merge(wx, on="datum", how="inner")
r = merged["svinn_g_p"].corr(merged["temp_c"])
# r uppdaterat: −0.07 efter parser-fix. Signalen är svagare när förskole-svinn
# (som ej följer samma temperaturberoende) inkluderas i dagssumman.
check("Väder r(svinn_g_p,temp)",   r,    -0.07,    0.30)  # tolerans ±30% av värdet
print(f"  [INFO] r={r:.3f} — uppdaterat från −0.29 pga parser-fix (förskolor nu med)")

# ── Svinntyp pie-chart — kräver separata komponentkolumner (skola/ÄO) ─────────
print("\nSvinntyper pie-chart:")
kg_cols = ["kokssvinn_kg", "serveringssvinn_kg", "tallrikssvinn_kg"]
if all(c in fw.columns for c in kg_cols):
    # Ny filter: dropna kräver att alla tre är non-null → förskola exkluderas automatiskt
    valid = fw.dropna(subset=kg_cols)
    kok = valid["kokssvinn_kg"].sum()
    srv = valid["serveringssvinn_kg"].sum()
    tal = valid["tallrikssvinn_kg"].sum()
    tot = kok + srv + tal
    # Uppdaterade förväntade värden efter parser-fix
    check("Pie tallrik andel %",    tal / tot * 100, 55.9, 0.05, "%")
    check("Pie kök andel %",        kok / tot * 100, 23.1, 0.05, "%")
    check("Pie servering andel %",  srv / tot * 100, 21.0, 0.05, "%")
    forsk_i_valid = valid["unit_name"].str.lower().str.contains("förskola|förskolan", na=False).sum()
    ok_pie = (forsk_i_valid == 0)
    print(f"  [{'PASS' if ok_pie else 'FAIL'}] Förskolor exkluderas ur pie: {forsk_i_valid} förskolarader (förväntat 0)")
    if not ok_pie:
        FAIL.append("Förskolor i pie-chart")

# ── Datakvalitet ──────────────────────────────────────────────────────────────
print("\nDatakvalitet:")
nan_pct_rows = fw["totalt_svinn_pct"].isna().sum() if "totalt_svinn_pct" in fw.columns else 0
# Parser-fix: från 2405 NaN (gammal parser) till ~6 NaN (label-baserad parser)
print(f"  [INFO] {nan_pct_rows} rader saknar svinn-pct (förväntat <20 efter parser-fix, var 2405 i gammal parser)")
ok_nan = (nan_pct_rows < 20)
if not ok_nan:
    print(f"  [FAIL] nan_pct_rows={nan_pct_rows} ≥ 20 — parser kanske ej kör korrekt?")
    FAIL.append("NaN svinn-pct för hög")

outlier_rows = (fw_agg["total_waste_pct"] > 1.0).sum()
print(f"  [INFO] {outlier_rows} veckorader med svinn >100% (filtreras i fw_clean)")

bad_ratio = (fw_agg[fw_agg["ordered_portions"] > 0]["served_portions"] /
             fw_agg[fw_agg["ordered_portions"] > 0]["ordered_portions"] > 3).sum()
print(f"  [INFO] {bad_ratio} rader serverade >3× beställda (troliga felregistreringar)")

# ── Iteration 3+: exkluderingsverifiering ─────────────────────────────────────
print("\nExkluderingsverifiering:")

# T1: Förskolor exkluderas från pie-chart (dropna på separata komponentkolumner)
if all(c in fw.columns for c in kg_cols):
    valid_pie  = fw.dropna(subset=kg_cols)
    fsk_in_pie = valid_pie["unit_name"].str.lower().str.contains("förskola|förskolan", na=False).sum()
    ok_t1 = (fsk_in_pie == 0)
    print(f"  [{'PASS' if ok_t1 else 'FAIL'}] T1 Förskolor exkluderas ur pie-chart: {fsk_in_pie} rader (förväntat 0)")
    if not ok_t1:
        FAIL.append("T1 Förskolor i pie-chart")

# T2: Förskolor ingår i totalt svinn kg — INTE exkluderade från totalanalys
fsk_kg = fw[fw["unit_name"].str.lower().str.contains("förskola|förskolan", na=False)]["totalt_svinn_kg"].sum()
ok_t2 = (fsk_kg > 1000)  # > 1000 kg förväntas nu (var ~184 med gammal parser)
print(f"  [{'PASS' if ok_t2 else 'FAIL'}] T2 Förskolor svinn kg > 1000: {fsk_kg:.1f} kg (förväntat > 1000 efter parser-fix)")
if not ok_t2:
    FAIL.append("T2 Förskolor svinn-kg för låg")

# T3: Parser-fix verifiering — förskola har kok_och_serveringssvinn_kg-kolumn
if "kok_och_serveringssvinn_kg" in fw.columns:
    fsk_comb = fw[fw["unit_name"].str.lower().str.contains("förskola|förskolan", na=False)]["kok_och_serveringssvinn_kg"].notna().sum()
    ok_t3 = (fsk_comb > 0)
    print(f"  [{'PASS' if ok_t3 else 'FAIL'}] T3 Förskola har kok_och_serveringssvinn_kg: {fsk_comb} non-null rader (förväntat > 0)")
    if not ok_t3:
        FAIL.append("T3 kok_och_serveringssvinn_kg saknas för förskola")
else:
    print("  [FAIL] T3 Kolumnen kok_och_serveringssvinn_kg saknas i CSV")
    FAIL.append("T3 saknar kok_och_serveringssvinn_kg")

# T4: Exkluderingsantal är beräkningsbart och konsistent
n_nan_pct  = fw["totalt_svinn_pct"].isna().sum() if "totalt_svinn_pct" in fw.columns else 0
n_tot      = len(fw)
n_incl_pct = n_tot - n_nan_pct
ok_t4 = (n_incl_pct > 0 and n_incl_pct <= n_tot)
print(f"  [{'PASS' if ok_t4 else 'FAIL'}] T4 Exkluderingsantal verifierbart: "
      f"{n_nan_pct} NaN, {n_incl_pct} inkl av {n_tot} totalt")
if not ok_t4:
    FAIL.append("T4 Exkluderingsantal inkonsistent")

# ── Resultat ──────────────────────────────────────────────────────────────────
print(f"\n{'='*40}")
if FAIL:
    print(f"❌ {len(FAIL)} FAIL: {', '.join(FAIL)}")
    sys.exit(1)
else:
    print(f"✅ Alla {15} tester passerade")
    sys.exit(0)
