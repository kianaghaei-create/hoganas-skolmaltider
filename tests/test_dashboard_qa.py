"""
Dashboard QA-tester — körs mot rådatan och verifierar att dashboardens
KPI:er och beräkningar stämmer. Kör: python tests/test_dashboard_qa.py
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
check("V1 Totalt svinn kg",        fw["totalt_svinn_kg"].sum(),         24419.5,  0.005, " kg")
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
check("Väder r(svinn_g_p,temp)",   r,                                   -0.29,    0.10)

# ── Svinntyp pie-chart — komponentfilter ──────────────────────────────────────
print("\nSvinntyper pie-chart:")
kg_cols = ["kokssvinn_kg", "serveringssvinn_kg", "tallrikssvinn_kg"]
if all(c in fw.columns for c in kg_cols):
    fw_pie = fw.copy()
    fw_pie["_komp_sum"] = fw_pie[kg_cols].sum(axis=1)
    fw_pie["_rel_diff"] = (
        (fw_pie["_komp_sum"] - fw_pie["totalt_svinn_kg"].fillna(0)).abs()
        / fw_pie["totalt_svinn_kg"].replace(0, float("nan"))
    )
    valid = fw_pie[fw_pie["_rel_diff"] < 0.2]
    kok = valid["kokssvinn_kg"].sum()
    srv = valid["serveringssvinn_kg"].sum()
    tal = valid["tallrikssvinn_kg"].sum()
    tot = kok + srv + tal
    check("Pie tallrik andel %", tal / tot * 100, 54.7, 0.05, "%")
    check("Pie kök andel %",     kok / tot * 100, 25.2, 0.05, "%")
    check("Pie servering andel %", srv / tot * 100, 20.7, 0.05, "%")
    forsk_in_valid = valid["unit_name"].str.lower().str.contains("förskola|förskolan", na=False).sum()
    print(f"  [INFO] Förskoleierader i validerat dataset: {forsk_in_valid} (förväntat ~0)")

# ── Datakvalitet ──────────────────────────────────────────────────────────────
print("\nDatakvalitet:")
nan_pct_rows = fw_agg["total_waste_pct"].isna().sum()
assert nan_pct_rows > 0, "Förväntar NaN-rader för förskolor"
print(f"  [INFO] {nan_pct_rows} veckorader saknar svinn% (förskolor) — dokumenterat i DK-sidan")

outlier_rows = (fw_agg["total_waste_pct"] > 1.0).sum()
print(f"  [INFO] {outlier_rows} rader med svinn >100% (filtreras i fw_clean)")

bad_ratio = (fw_agg[fw_agg["ordered_portions"] > 0]["served_portions"] /
             fw_agg[fw_agg["ordered_portions"] > 0]["ordered_portions"] > 3).sum()
print(f"  [INFO] {bad_ratio} rader serverade >3× beställda (troliga felregistreringar)")

# ── Iteration 3: exkluderingsverifiering ──────────────────────────────────────
print("\nExkluderingsverifiering (iter 3):")

# T1: Förskolor exkluderas från pie-chart (komponentfilter)
if all(c in fw.columns for c in kg_cols):
    fw_t = fw.copy()
    fw_t["_ks"]  = fw_t[kg_cols].sum(axis=1)
    fw_t["_rd"]  = (fw_t["_ks"] - fw_t["totalt_svinn_kg"].fillna(0)).abs() / fw_t["totalt_svinn_kg"].replace(0, float("nan"))
    valid_pie    = fw_t[fw_t["_rd"] < 0.2]
    fsk_in_pie   = valid_pie["unit_name"].str.lower().str.contains("förskola|förskolan", na=False).sum()
    ok_t1 = (fsk_in_pie == 0)
    print(f"  [{'PASS' if ok_t1 else 'FAIL'}] T1 Förskolor exkluderas ur pie-chart: {fsk_in_pie} förskolarader i validerat dataset (förväntat 0)")
    if not ok_t1:
        FAIL.append("T1 Förskolor i pie-chart")

# T2: Förskolor ingår i totalt svinn kg — INTE exkluderade från totalanalys
fsk_kg = fw[fw["unit_name"].str.lower().str.contains("förskola|förskolan", na=False)]["totalt_svinn_kg"].sum()
ok_t2 = (fsk_kg > 0)
print(f"  [{'PASS' if ok_t2 else 'FAIL'}] T2 Förskolor ingår i totalt svinn kg: {fsk_kg:.1f} kg (förväntat > 0)")
if not ok_t2:
    FAIL.append("T2 Förskolor saknas ur total svinn")

# T3: Exkluderingsantal är beräkningsbart och konsistent
_pct_col   = "totalt_svinn_pct" if "totalt_svinn_pct" in fw.columns else "total_waste_pct"
n_nan_pct  = fw[_pct_col].isna().sum() if _pct_col in fw.columns else 0
n_tot      = len(fw)
n_incl_pct = n_tot - n_nan_pct
ok_t3 = (n_nan_pct > 0 and n_incl_pct > 0 and n_incl_pct < n_tot)
print(f"  [{'PASS' if ok_t3 else 'FAIL'}] T3 Exkluderingsantal verifierbart: "
      f"{n_nan_pct} exkl (NaN pct), {n_incl_pct} inkl av {n_tot} totalt")
if not ok_t3:
    FAIL.append("T3 Exkluderingsantal inkonsistent")

# ── Resultat ──────────────────────────────────────────────────────────────────
print(f"\n{'='*40}")
if FAIL:
    print(f"❌ {len(FAIL)} FAIL: {', '.join(FAIL)}")
    sys.exit(1)
else:
    print(f"✅ Alla {14} tester passerade")
    sys.exit(0)
