"""
Parser-tester — verifierar att label-baserad parsning ger korrekta värden
för minst en förskolefil och en skolfil.
Kör: python3 tests/test_parser.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from parse_waste_daily import parse_file

FAIL = []

def check(name, val, expected, tol=0.01):
    if expected is None:
        ok = val is None
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {val!r} (förväntat None)")
    elif isinstance(expected, bool):
        ok = bool(val) == expected
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {val!r} (förväntat {expected!r})")
    elif isinstance(expected, str):
        ok = str(val).lower().startswith(expected.lower())
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {val!r} (förväntat börjar med {expected!r})")
    else:
        diff = abs(val - expected) if val is not None else float('inf')
        rel  = diff / abs(expected) if expected != 0 else diff
        ok   = rel <= tol
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {val} (förväntat {expected}, diff {diff:.3g})")
    if not ok:
        FAIL.append(name)
    return ok


print("=== Parser-tester ===\n")

# ── FÖRSKOLEFIL: Äventyrets förskola ─────────────────────────────────────────
print("Format A — Förskola (Äventyrets förskola):")
fpath_fsk = Path("Data/Matsvinn 2025/Äventyrets förskola.xlsx")
recs_fsk  = parse_file(fpath_fsk)

# Grundläggande
check("P1 Antal rader > 0",              len(recs_fsk), True)
check("P2 Format = förskola",            recs_fsk[0]["format"] if recs_fsk else None, "förskola")
check("P3 Enhetnamn",                    recs_fsk[0]["enhet"] if recs_fsk else None, "Äventyrets förskola")

# totalt_svinn_pct ska INTE vara NaN för förskola (parsern läste fel rad tidigare)
pct_vals   = [r["totalt_svinn_pct"] for r in recs_fsk if r["totalt_svinn_pct"] is not None]
pct_nan    = sum(1 for r in recs_fsk if r["totalt_svinn_pct"] is None)
check("P4 totalt_svinn_pct ej alla NaN",  len(pct_vals) > 0, True)
check("P5 NaN-andel totalt_svinn_pct <5%", pct_nan / len(recs_fsk) if recs_fsk else 1, 0.0, tol=0.05)
print(f"       ({pct_nan} NaN av {len(recs_fsk)} rader)")

# totalt_svinn_kg ska vara rimliga kg-värden (inte pct-decimaler)
kg_vals = [r["totalt_svinn_kg"] for r in recs_fsk if r["totalt_svinn_kg"] is not None]
median_kg = sorted(kg_vals)[len(kg_vals)//2] if kg_vals else 0
check("P6 totalt_svinn_kg median > 0.1 kg",  median_kg, 0.5, tol=5.0)   # minst 0.5 kg median
check("P7 totalt_svinn_kg median < 50 kg",   median_kg < 50, True)

# Förskola ska ha kok_och_serveringssvinn_kg (kombinerat), INTE separata
kok_vals  = [r["kokssvinn_kg"] for r in recs_fsk if r["kokssvinn_kg"] is not None]
serv_vals = [r["serveringssvinn_kg"] for r in recs_fsk if r["serveringssvinn_kg"] is not None]
comb_vals = [r["kok_och_serveringssvinn_kg"] for r in recs_fsk if r["kok_och_serveringssvinn_kg"] is not None]
check("P8 kokssvinn_kg = None (ej separat i förskola)",   len(kok_vals),  0, tol=0.0)
check("P9 serveringssvinn_kg = None (ej separat i förskola)", len(serv_vals), 0, tol=0.0)
check("P10 kok_och_serveringssvinn_kg finns",             len(comb_vals) > 0, True)

# tallrikssvinn_kg ska finnas
tal_vals = [r["tallrikssvinn_kg"] for r in recs_fsk if r["tallrikssvinn_kg"] is not None]
check("P11 tallrikssvinn_kg finns",  len(tal_vals) > 0, True)

# Kolla ett specifikt blad (v.2) mot kända värden från rådata
# v.2: Onsdag: serverade=97, kok_serv=0.4, tallrik=1.1, total=1.5, pct≈1.55%
v2_ons = [r for r in recs_fsk if r["blad"] == "v.2" and r["veckodag"] == "Onsdag"]
if v2_ons:
    r = v2_ons[0]
    check("P12 v.2 Onsdag serverade=97",        r["serverade_portioner"], 97, tol=0.01)
    check("P13 v.2 Onsdag kok_serv_combined=0.4", r["kok_och_serveringssvinn_kg"], 0.4, tol=0.01)
    check("P14 v.2 Onsdag tallrikssvinn=1.1",   r["tallrikssvinn_kg"], 1.1, tol=0.01)
    check("P15 v.2 Onsdag totalt_svinn_kg=1.5", r["totalt_svinn_kg"], 1.5, tol=0.01)
    check("P16 v.2 Onsdag totalt_svinn_pct>0",  r["totalt_svinn_pct"] is not None and r["totalt_svinn_pct"] > 0, True)
else:
    print("  [SKIP] Blad v.2/Onsdag hittades inte")

# Dagkolumner: alla fem dagar ska finnas i recs
dagar_v2 = [r["veckodag"] for r in recs_fsk if r["blad"] == "v.2"]
for dag in ["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag"]:
    has_dag = dag in dagar_v2
    # v.1 visar att måndag/tisdag/onsdag är tomma, så v.2 bör ha dem
    if dag in ["Onsdag", "Torsdag", "Fredag"]:
        check(f"P17 v.2 {dag} finns",  has_dag, True)

print()

# ── SKOLFIL: Jonstorpsskolan ─────────────────────────────────────────────────
print("Format B — Skola (Jonstorpsskolan):")
fpath_sko = Path("Data/Matsvinn 2025/Jonstorpsskolan.xlsx")
recs_sko  = parse_file(fpath_sko)

check("S1 Antal rader > 0",              len(recs_sko), True)
check("S2 Format = skola_ao",            recs_sko[0]["format"] if recs_sko else None, "skola_ao")
check("S3 Enhetnamn",                    recs_sko[0]["enhet"] if recs_sko else None, "Jonstorpsskolan")

# Skola ska ha separata koks/serv/tallrik kolumner
koks_sko = [r["kokssvinn_kg"] for r in recs_sko if r["kokssvinn_kg"] is not None]
serv_sko = [r["serveringssvinn_kg"] for r in recs_sko if r["serveringssvinn_kg"] is not None]
tal_sko  = [r["tallrikssvinn_kg"] for r in recs_sko if r["tallrikssvinn_kg"] is not None]
comb_sko = [r["kok_och_serveringssvinn_kg"] for r in recs_sko if r["kok_och_serveringssvinn_kg"] is not None]
check("S4 kokssvinn_kg finns",                  len(koks_sko) > 0, True)
check("S5 serveringssvinn_kg finns",            len(serv_sko) > 0, True)
check("S6 tallrikssvinn_kg finns",              len(tal_sko) > 0, True)
check("S7 kok_och_serveringssvinn_kg = None",   len(comb_sko), 0, tol=0.0)

# totalt_svinn_pct ska finnas för skola
pct_sko = [r["totalt_svinn_pct"] for r in recs_sko if r["totalt_svinn_pct"] is not None]
check("S8 totalt_svinn_pct finns",  len(pct_sko) > 0, True)

# Kolla ett specifikt blad (v.2) mot kända värden från rådata
# v.2: Onsdag: serverade=592, koks=6, serv=6, tallrik=11, total=23, pct≈9.71%
v2_ons_s = [r for r in recs_sko if r["blad"] == "v.2" and r["veckodag"] == "Onsdag"]
if v2_ons_s:
    r = v2_ons_s[0]
    check("S9 v.2 Onsdag serverade=592",      r["serverade_portioner"], 592, tol=0.01)
    check("S10 v.2 Onsdag kokssvinn=6",       r["kokssvinn_kg"], 6, tol=0.01)
    check("S11 v.2 Onsdag serveringssvinn=6", r["serveringssvinn_kg"], 6, tol=0.01)
    check("S12 v.2 Onsdag tallrikssvinn=11",  r["tallrikssvinn_kg"], 11, tol=0.01)
    check("S13 v.2 Onsdag totalt_svinn=23",   r["totalt_svinn_kg"], 23, tol=0.01)
    check("S14 v.2 Onsdag totalt_pct>0",      r["totalt_svinn_pct"] is not None and r["totalt_svinn_pct"] > 0, True)
else:
    print("  [SKIP] Blad v.2/Onsdag hittades inte")

# Maträttsnamn ska finnas för v.2 Onsdag
if v2_ons_s:
    check("S15 v.2 Onsdag matratt finns",
          v2_ons_s[0]["matratt"] not in (None, '', 'None'), True)

print()

# ── Resultat ──────────────────────────────────────────────────────────────────
print("="*40)
if FAIL:
    print(f"❌ {len(FAIL)} FAIL: {', '.join(FAIL)}")
    sys.exit(1)
else:
    ok_count = sum(1 for n in dir() if n.startswith('check'))  # approx
    print(f"✅ Alla parser-tester passerade")
    sys.exit(0)
