"""
Kvadrant funnel audit — spårar varje steg från alla matratt_norm
i svinndatan till de rätter som visas i kvadrantdiagrammet.

Output:
  Data/analysis/kvadrant_funnel.json   — tratt-siffror per steg
  Data/analysis/kvadrant_exclusion_audit.csv — alla exkluderade rätter

Kör: python3 scripts/kvadrant_funnel_audit.py
"""
import pandas as pd
import numpy as np
import json
from pathlib import Path

DATA = Path("Data/processed")
ANA  = Path("Data/analysis")
CFG  = Path("Data/config")

fw = pd.read_csv(DATA / "food_waste_daily_v2.csv")
nr = pd.read_parquet(DATA / "naring.parquet")
mp = pd.read_csv(CFG / "dish_name_mapping.csv")

# ── Näringslookup ──────────────────────────────────────────────────────────────
nr_agg = nr.groupby("ratt", as_index=False).agg(
    protein_g   =("protein_g",    "mean"),
    energi_kcal =("energi_kcal",  "mean"),
    fett_g      =("fett_g",       "mean"),
    kolhydrater_g=("kolhydrater_g","mean"),
)
nr_norm  = {r.lower().replace(" ", ""): r for r in nr_agg["ratt"]}
nr_exact = {r.lower(): r for r in nr_agg["ratt"]}
mapping      = dict(zip(mp["waste_dish_name"].str.lower(), mp["nutrition_dish_name"]))
mapping_type = dict(zip(mp["waste_dish_name"].str.lower(), mp["match_type"]))
nr_dict = nr_agg.set_index("ratt").to_dict("index")

def match_dish(name):
    lo = str(name).lower().strip()
    if lo in nr_exact:
        return nr_exact[lo], "exact"
    lo_norm = lo.replace(" ", "")
    if lo_norm in nr_norm:
        return nr_norm[lo_norm], "normalized"
    if lo in mapping:
        return mapping[lo], mapping_type.get(lo, "manual_override")
    return None, "unmatched"

# ── Steg A: Alla unika matratt_norm ───────────────────────────────────────────
step_a = fw["matratt_norm"].dropna().unique()

# ── Steg B: Rader med svinn>0 och portioner>0 ─────────────────────────────────
fw_b = fw.dropna(subset=["matratt_norm", "serverade_portioner", "totalt_svinn_kg"]).copy()
fw_b = fw_b[(fw_b["serverade_portioner"] > 0) & (fw_b["totalt_svinn_kg"] > 0)]
fw_b["svinn_g_p"] = fw_b["totalt_svinn_kg"] * 1000 / fw_b["serverade_portioner"]
fw_b["tallrik_g_p"] = fw_b["tallrikssvinn_kg"].fillna(0) * 1000 / fw_b["serverade_portioner"]
step_b_names = fw_b["matratt_norm"].unique()

# ── Steg C: minst 2 observationer ─────────────────────────────────────────────
fw_agg = fw_b.groupby("matratt_norm").agg(
    obs         =("svinn_g_p",       "count"),
    svinn_g_p   =("svinn_g_p",       "mean"),
    tallrik_g_p =("tallrik_g_p",     "mean"),
    total_kg    =("totalt_svinn_kg",  "sum"),
).reset_index()

step_c = fw_agg[fw_agg["obs"] >= 2].copy()
step_c["nutrition_dish"], step_c["match_status"] = zip(
    *step_c["matratt_norm"].apply(match_dish)
)

# ── Steg D: Matchning ──────────────────────────────────────────────────────────
step_d_exact    = step_c[step_c["match_status"] == "exact"]
step_d_norm     = step_c[step_c["match_status"] == "normalized"]
step_d_manual   = step_c[step_c["match_status"] == "manual_override"]
step_d_unmatched= step_c[step_c["match_status"] == "unmatched"]
step_d_matched  = step_c[step_c["match_status"] != "unmatched"]

# ── Steg E: protein >= 5g ─────────────────────────────────────────────────────
step_d_matched = step_d_matched.copy()
step_d_matched["protein_g"]    = step_d_matched["nutrition_dish"].map(
    lambda x: nr_dict.get(x, {}).get("protein_g", None) if x else None)
step_d_matched["energi_kcal"]  = step_d_matched["nutrition_dish"].map(
    lambda x: nr_dict.get(x, {}).get("energi_kcal", None) if x else None)

step_e = step_d_matched[step_d_matched["protein_g"].fillna(0) >= 5]
step_e_fail = step_d_matched[step_d_matched["protein_g"].fillna(0) < 5]

# ── Steg F: kcal >= 150 ───────────────────────────────────────────────────────
step_f = step_e[step_e["energi_kcal"].fillna(0) >= 150]
step_f_fail = step_e[step_e["energi_kcal"].fillna(0) < 150]

# ── Steg G: faktiska rätter i JSON (aggregerat på nutrition_dish) ──────────────
kv_json = json.loads((ANA / "svinn_naring_kvadrant.json").read_text())
step_g_names = {r["komponent"] for r in kv_json}

# ── Tratt-sammanfattning ───────────────────────────────────────────────────────
# Rätter vars nutrition_dish är i step_g
step_g_matratt = step_f[step_f["nutrition_dish"].isin(step_g_names)]

funnel = {
    "generated": "2026-06-11",
    "steps": [
        {"step": "A", "label": "Alla unika matratt_norm i svinndatan",
         "ratter": int(len(step_a)), "obs": int(fw["matratt_norm"].notna().sum())},
        {"step": "B", "label": "Har svinn>0 och portioner>0",
         "ratter": int(len(step_b_names)),
         "obs": int(len(fw_b))},
        {"step": "C", "label": "Minst 2 observationer",
         "ratter": int(len(step_c)),
         "obs": int(step_c["obs"].sum())},
        {"step": "D_exact", "label": "Matchad exact mot näringsfilen",
         "ratter": int(len(step_d_exact)),
         "obs": int(step_d_exact["obs"].sum())},
        {"step": "D_normalized", "label": "Matchad normalized (lowercase/stripped)",
         "ratter": int(len(step_d_norm)),
         "obs": int(step_d_norm["obs"].sum())},
        {"step": "D_manual", "label": "Matchad manual_override (dish_name_mapping.csv)",
         "ratter": int(len(step_d_manual)),
         "obs": int(step_d_manual["obs"].sum())},
        {"step": "D_unmatched", "label": "Omatchad (för generisk eller okänd förkortning)",
         "ratter": int(len(step_d_unmatched)),
         "obs": int(step_d_unmatched["obs"].sum())},
        {"step": "E_fail", "label": "Matchad men protein < 5g (trolig felmatchning)",
         "ratter": int(len(step_e_fail)),
         "obs": int(step_e_fail["obs"].sum()) if len(step_e_fail) > 0 else 0},
        {"step": "F_fail", "label": "Matchad men kcal < 150 (trolig felmatchning)",
         "ratter": int(len(step_f_fail)),
         "obs": int(step_f_fail["obs"].sum()) if len(step_f_fail) > 0 else 0},
        {"step": "G", "label": "Visas i kvadrantdiagrammet",
         "ratter": int(len(kv_json)),
         "obs": int(sum(r.get("obs", 0) for r in kv_json))},
    ],
    "matching_coverage": {
        "total_obs_ge2": int(len(step_c)),
        "matched": int(len(step_d_matched)),
        "unmatched": int(len(step_d_unmatched)),
        "match_rate_pct": round(len(step_d_matched) / len(step_c) * 100, 1),
    },
    "top10_excluded_by_waste_kg": [],
}

# ── Topp 10 exkluderade på total svinn kg ─────────────────────────────────────
excluded_c = step_c[~step_c["nutrition_dish"].isin(step_g_names)].copy()

def exclusion_reason(row):
    if row["match_status"] == "unmatched":
        return "unmatched_nutrition"
    if row.get("protein_g") is not None and row.get("protein_g") < 5:
        return "protein_below_5"
    if row.get("energi_kcal") is not None and row.get("energi_kcal") < 150:
        return "energy_below_150"
    return "aggregated_into_other_dish"

excluded_c["protein_g"] = excluded_c["nutrition_dish"].map(
    lambda x: nr_dict.get(x, {}).get("protein_g", None) if x else None)
excluded_c["energi_kcal"] = excluded_c["nutrition_dish"].map(
    lambda x: nr_dict.get(x, {}).get("energi_kcal", None) if x else None)
excluded_c["exclusion_reason"] = excluded_c.apply(exclusion_reason, axis=1)

top10 = excluded_c.sort_values("total_kg", ascending=False).head(10)
funnel["top10_excluded_by_waste_kg"] = [
    {
        "matratt_norm":    r["matratt_norm"],
        "obs":             int(r["obs"]),
        "total_kg":        round(float(r["total_kg"]), 1),
        "svinn_g_p":       round(float(r["svinn_g_p"]), 1),
        "match_status":    r["match_status"],
        "nutrition_dish":  r["nutrition_dish"] if r["nutrition_dish"] else "",
        "protein_g":       round(float(r["protein_g"]), 1) if r["protein_g"] is not None else None,
        "energi_kcal":     round(float(r["energi_kcal"]), 1) if r["energi_kcal"] is not None else None,
        "exclusion_reason":r["exclusion_reason"],
    }
    for _, r in top10.iterrows()
]

(ANA / "kvadrant_funnel.json").write_text(json.dumps(funnel, ensure_ascii=False, indent=2))
print(f"✅ kvadrant_funnel.json sparad")

# ── Exkluderingslista — alla rätter som inte visas i diagrammet ─────────────────
# Inkludera även obs<2-rätter
fw_all_agg = fw_b.groupby("matratt_norm").agg(
    obs         =("svinn_g_p",      "count"),
    svinn_g_p   =("svinn_g_p",      "mean"),
    total_kg    =("totalt_svinn_kg", "sum"),
).reset_index()
fw_all_agg["nutrition_dish"], fw_all_agg["match_status"] = zip(
    *fw_all_agg["matratt_norm"].apply(match_dish)
)
fw_all_agg["protein_g"]   = fw_all_agg["nutrition_dish"].map(
    lambda x: nr_dict.get(x, {}).get("protein_g", None) if x else None)
fw_all_agg["energi_kcal"] = fw_all_agg["nutrition_dish"].map(
    lambda x: nr_dict.get(x, {}).get("energi_kcal", None) if x else None)

# Rätter vars nutrition_dish finns i kv_json = inkluderade
included_nutrition = step_g_names

def full_exclusion_reason(row):
    if row["obs"] < 2:
        return "fewer_than_2_observations"
    if row["match_status"] == "unmatched":
        return "unmatched_nutrition"
    if row["protein_g"] is not None and row["protein_g"] < 5:
        return "protein_below_5"
    if row["energi_kcal"] is not None and row["energi_kcal"] < 150:
        return "energy_below_150"
    if row["nutrition_dish"] in included_nutrition:
        return ""  # inkluderad
    return "aggregated_into_other_dish"

fw_all_agg["exclusion_reason"] = fw_all_agg.apply(full_exclusion_reason, axis=1)

excluded_all = fw_all_agg[fw_all_agg["exclusion_reason"] != ""].copy()
excluded_all = excluded_all.sort_values("total_kg", ascending=False)

excluded_all.rename(columns={"nutrition_dish": "matched_nutrition_dish"})[
    ["matratt_norm","obs","total_kg","svinn_g_p","match_status",
     "matched_nutrition_dish","protein_g","energi_kcal","exclusion_reason"]
].to_csv(ANA / "kvadrant_exclusion_audit.csv", index=False, float_format="%.1f")
print(f"✅ kvadrant_exclusion_audit.csv sparad ({len(excluded_all)} rader)")

# ── Utskrift ───────────────────────────────────────────────────────────────────
print()
print("=== KVADRANT FUNNEL AUDIT ===")
for s in funnel["steps"]:
    bar = "█" * (s["ratter"] // 5) if s["ratter"] > 0 else ""
    print(f"  {s['step']:<15} {s['ratter']:4} rätter  {s.get('obs',0):5} obs   {s['label']}")

print()
mc = funnel["matching_coverage"]
print(f"Matchningsgrad: {mc['matched']}/{mc['total_obs_ge2']} = {mc['match_rate_pct']}% av rätter med obs>=2")
print()
print("Topp 10 exkluderade (total svinn kg):")
for r in funnel["top10_excluded_by_waste_kg"]:
    print(f"  {r['matratt_norm']:<25} {r['total_kg']:7.1f}kg  obs={r['obs']:3}  {r['exclusion_reason']}")
