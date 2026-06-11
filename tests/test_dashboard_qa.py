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

# ── Resultat ──────────────────────────────────────────────────────────────────
print(f"\n{'='*40}")
if FAIL:
    print(f"❌ {len(FAIL)} FAIL: {', '.join(FAIL)}")
    sys.exit(1)
else:
    print(f"✅ Alla {8} tester passerade")
    sys.exit(0)
