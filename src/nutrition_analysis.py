"""
Nutritionsanalys — vad får eleverna faktiskt i sig?

Kopplar:
  näringsvärde per rätt × (1 - svinnprocent) = faktiskt konsumerad näring
  faktiskt konsumerad näring / inköpskostnad  = näring per spenderad krona

NNR-rekommendation för skollunch (25% av dagsbehov):
  Energi:    538 kcal
  Protein:   19.25 g
  Järn:      2.75 mg   (flickor behöver mer, men snitt)
  D-vitamin: 2.5 µg
  Kalcium:   275 mg
  Omega-3:   0.5 g
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BASE       = Path(__file__).resolve().parent.parent
PROCESSED  = BASE / "data" / "processed"
REPORTS    = BASE / "reports"

NNR = {
    "Energi (kcal)":    538,
    "Protein (g)":      19.25,
    "Järn (mg)":        2.75,
    "Vitamin D (µg)":   2.5,
    "Kalcium (mg)":     275,
    "Omega-3 (g)":      0.5,   # approximation från Linolensyra+EPA+DHA
}

KEY_NUTRIENTS = list(NNR.keys())


# ── Läs in näringsfiler ───────────────────────────────────────────────────────
def parse_nutrition(path: Path, menu_type: str) -> pd.DataFrame:
    import openpyxl
    wb   = openpyxl.load_workbook(path, data_only=True)
    ws   = wb["Blad1"]
    rows = list(ws.iter_rows(values_only=True))
    hdrs = [str(v).strip() if v else "" for v in rows[6]]

    records = []
    for row in rows[7:]:
        if row[3] != "Lunch":
            continue
        if not row[7] or float(row[7] or 0) == 0:
            continue
        rec = {
            "date":      row[0],
            "week":      int(row[1]) if row[1] else None,
            "weekday":   row[2],
            "dish_type": str(row[4]).strip() if row[4] else "",
            "dish_name": str(row[5]).strip() if row[5] else "",
            "menu_type": menu_type,
        }
        for i, h in enumerate(hdrs[7:], 7):
            if h and row[i] is not None:
                rec[h] = row[i]
        records.append(rec)

    df = pd.DataFrame(records)

    # Bygg Omega-3 = Linolensyra + EPA + DHA
    o3_cols = ["Linolensyra, Omega-3 18:3 (g)", "Eikosapentaensyra 20:5 (g)", "Cervonsyra 22:6 (g)"]
    for c in o3_cols:
        if c not in df.columns:
            df[c] = 0
    df["Omega-3 (g)"] = df[o3_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1)

    return df


# ── Beräkna konsumtionsgrad per vecka ────────────────────────────────────────
def consumption_rate_by_week(fw: pd.DataFrame) -> pd.Series:
    """1 - total_waste_pct, medel över alla enheter per vecka."""
    f = fw.copy()
    f["week"]           = pd.to_numeric(f["week"], errors="coerce")
    f["total_waste_pct"]= pd.to_numeric(f["total_waste_pct"], errors="coerce")
    f = f[f["total_waste_pct"].notna() & (f["total_waste_pct"] < 1) & f["week"].notna()]
    rate = 1 - f.groupby("week")["total_waste_pct"].mean()
    return rate  # index=week, value=consumption_rate (0-1)


# ── Faktisk näringsleverans per rätt per vecka ────────────────────────────────
def compute_delivered_nutrition(nutr: pd.DataFrame, cons_rate: pd.Series) -> pd.DataFrame:
    df = nutr[nutr["menu_type"] == "skola"].copy()
    df["consumption_rate"] = df["week"].map(cons_rate)
    df["consumption_rate"] = df["consumption_rate"].fillna(cons_rate.mean())

    for n in KEY_NUTRIENTS:
        if n in df.columns:
            df[f"{n}_consumed"] = pd.to_numeric(df[n], errors="coerce") * df["consumption_rate"]

    return df


# ── Näring per spenderad krona ────────────────────────────────────────────────
def nutrition_per_kr(nutr_df: pd.DataFrame, pur: pd.DataFrame) -> pd.DataFrame:
    """
    Approximation: total inköpskostnad per månad / antal serverade luncher per månad
    = kostnad per lunch. Koppla sedan till konsumerad näring per lunch.
    """
    pur_c = pur[pur["unit_name_std"].notna()].copy()
    pur_c["kronor"] = pd.to_numeric(pur_c["kronor"], errors="coerce")
    pur_c["month"]  = pd.to_numeric(pur_c["month"],  errors="coerce")

    total_cost_per_month = pur_c.groupby("month")["kronor"].sum()

    # Portioner per månad (från näringsdatans datum)
    nutr_df["month"] = pd.to_datetime(nutr_df["date"], errors="coerce").dt.month
    portions_per_month = nutr_df.groupby("month").size() / 5  # /5 vardagar per vecka

    cost_per_portion = (total_cost_per_month / portions_per_month).rename("cost_per_portion_approx")

    nutr_df = nutr_df.join(cost_per_portion, on="month")

    for n in KEY_NUTRIENTS:
        col = f"{n}_consumed"
        if col in nutr_df.columns:
            nutr_df[f"{n}_per_kr"] = nutr_df[col] / nutr_df["cost_per_portion_approx"]

    return nutr_df


# ── Kategorisera rätter ───────────────────────────────────────────────────────
CATEGORIES = {
    "Fisk":          ["fisk", "torsk", "lax", "hoki", "seafood", "räk"],
    "Kyckling":      ["kyckling", "tikka", "kycklingfile"],
    "Köttfärs":      ["köttbullar", "köttfärs", "lasagne", "spaghetti", "färssås", "pannbiff", "biff"],
    "Korv":          ["korv", "wienerkorv", "falukorv"],
    "Vegetariskt":   ["vegetarisk", "quorn", "blomkål", "grönsakspaj", "veg", "tomat"],
    "Pasta/soppa":   ["pasta", "penne", "makaroner", "soppa", "gryta", "nudlar"],
}

def categorize(name: str) -> str:
    n = str(name).lower()
    for cat, kws in CATEGORIES.items():
        if any(k in n for k in kws):
            return cat
    return "Övrigt"


# ── Visualiseringar ───────────────────────────────────────────────────────────
def build_nutrition_charts(delivered: pd.DataFrame, pur: pd.DataFrame):
    delivered["category"] = delivered["dish_name"].apply(categorize)

    # ── 1. NNR-uppfyllnad per vecka ───────────────────────────────────────────
    weekly = []
    for week, grp in delivered.groupby("week"):
        row = {"week": week}
        for n in KEY_NUTRIENTS:
            col = f"{n}_consumed"
            if col in grp.columns:
                avg = pd.to_numeric(grp[col], errors="coerce").mean()
                row[n] = avg / NNR[n] * 100  # % av rekommendation
        weekly.append(row)
    weekly_df = pd.DataFrame(weekly).sort_values("week")

    fig1 = go.Figure()
    colors = ["#2563eb","#16a34a","#dc2626","#f59e0b","#8b5cf6","#0ea5e9"]
    for i, n in enumerate(KEY_NUTRIENTS):
        if n in weekly_df.columns:
            fig1.add_trace(go.Scatter(
                x=weekly_df["week"], y=weekly_df[n],
                name=n.split(" (")[0],
                line=dict(color=colors[i], width=2),
                hovertemplate=f"<b>{n.split(' (')[0]}</b><br>Vecka %{{x}}: %{{y:.0f}}% av NNR<extra></extra>",
            ))
    fig1.add_hline(y=100, line_dash="dash", line_color="#374151",
                   annotation_text="NNR 100%", annotation_position="right")
    fig1.update_layout(
        title=dict(text="Faktisk näringsleverans till elever — % av NNR-rekommendation per vecka",
                   font=dict(size=17), x=0.5),
        xaxis_title="Vecka", yaxis_title="% av rekommendation",
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        width=1000, height=520,
        xaxis=dict(gridcolor="#f3f4f6"),
        yaxis=dict(gridcolor="#f3f4f6", range=[0, 180]),
    )
    fig1.write_html(str(REPORTS / "nutrition_nnr.html"), include_plotlyjs="cdn")
    print("  → nutrition_nnr.html")

    # ── 2. Näring per kategori — vad konsumeras vs slängs ────────────────────
    cat_stats = []
    for cat, grp in delivered.groupby("category"):
        row = {"Kategori": cat, "Antal rätter": len(grp)}
        for n in KEY_NUTRIENTS:
            served_col  = n
            consumed_col = f"{n}_consumed"
            if served_col in grp.columns and consumed_col in grp.columns:
                served   = pd.to_numeric(grp[served_col],  errors="coerce").mean()
                consumed = pd.to_numeric(grp[consumed_col],errors="coerce").mean()
                row[f"{n}_served"]   = served
                row[f"{n}_consumed"] = consumed
                row[f"{n}_wasted"]   = served - consumed
                row[f"{n}_pct_nnr"]  = consumed / NNR[n] * 100
        cat_stats.append(row)
    cat_df = pd.DataFrame(cat_stats)

    # Protein: serverat vs konsumerat per kategori
    fig2 = go.Figure()
    cat_order = cat_df.sort_values("Protein (g)_consumed", ascending=True)["Kategori"].tolist()

    fig2.add_trace(go.Bar(
        y=cat_order,
        x=[cat_df[cat_df["Kategori"]==c]["Protein (g)_consumed"].values[0] for c in cat_order],
        name="Konsumerat av elev", orientation="h",
        marker_color="#16a34a", opacity=0.9,
        hovertemplate="<b>%{y}</b><br>Konsumerat: %{x:.1f} g protein<extra></extra>",
    ))
    fig2.add_trace(go.Bar(
        y=cat_order,
        x=[cat_df[cat_df["Kategori"]==c]["Protein (g)_wasted"].values[0] for c in cat_order],
        name="Slängt (svinn)", orientation="h",
        marker_color="#ef4444", opacity=0.7,
        hovertemplate="<b>%{y}</b><br>Slängt: %{x:.1f} g protein<extra></extra>",
    ))
    fig2.add_vline(x=NNR["Protein (g)"], line_dash="dash", line_color="#374151",
                   annotation_text=f"NNR {NNR['Protein (g)']}g", annotation_position="top right")
    fig2.update_layout(
        barmode="stack",
        title=dict(text="Protein per rättkategori — vad konsumeras vs slängs av eleven?",
                   font=dict(size=17), x=0.5),
        xaxis_title="Protein per portion (g)",
        yaxis_title="",
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        width=850, height=480,
        xaxis=dict(gridcolor="#f3f4f6"),
    )
    fig2.write_html(str(REPORTS / "nutrition_protein.html"), include_plotlyjs="cdn")
    print("  → nutrition_protein.html")

    # ── 3. D-vitamin och järn — de kritiska bristämnena ──────────────────────
    fig3 = make_subplots(rows=1, cols=2,
                          subplot_titles=["D-vitamin — % av NNR per kategori",
                                          "Järn — % av NNR per kategori"])

    cat_order_d = cat_df.sort_values("Vitamin D (µg)_pct_nnr", ascending=True)["Kategori"].tolist()
    cat_order_fe = cat_df.sort_values("Järn (mg)_pct_nnr", ascending=True)["Kategori"].tolist()

    def bar_color(val):
        if val >= 100: return "#16a34a"
        if val >= 70:  return "#f59e0b"
        return "#ef4444"

    for cat in cat_order_d:
        val = cat_df[cat_df["Kategori"]==cat]["Vitamin D (µg)_pct_nnr"].values[0]
        fig3.add_trace(go.Bar(
            y=[cat], x=[val], orientation="h", showlegend=False,
            marker_color=bar_color(val), name=cat,
            hovertemplate=f"<b>{cat}</b><br>D-vitamin: {val:.0f}% av NNR<extra></extra>",
        ), row=1, col=1)

    for cat in cat_order_fe:
        val = cat_df[cat_df["Kategori"]==cat]["Järn (mg)_pct_nnr"].values[0]
        fig3.add_trace(go.Bar(
            y=[cat], x=[val], orientation="h", showlegend=False,
            marker_color=bar_color(val), name=cat,
            hovertemplate=f"<b>{cat}</b><br>Järn: {val:.0f}% av NNR<extra></extra>",
        ), row=1, col=2)

    fig3.add_vline(x=100, line_dash="dash", line_color="#374151", row=1, col=1)
    fig3.add_vline(x=100, line_dash="dash", line_color="#374151", row=1, col=2)

    fig3.update_layout(
        title=dict(text="Kritiska bristämnen — hur mycket D-vitamin och järn konsumerar eleverna?",
                   font=dict(size=17), x=0.5),
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=12),
        width=1000, height=440,
    )
    fig3.update_xaxes(gridcolor="#f3f4f6", title_text="% av NNR")
    fig3.write_html(str(REPORTS / "nutrition_micronutrients.html"), include_plotlyjs="cdn")
    print("  → nutrition_micronutrients.html")

    # ── 4. Prediktion: svinnrisk per rättkategori + näringsvärde ─────────────
    # Kombinera svinn-risk med näringsleverans
    pred_data = []
    for cat, grp in delivered.groupby("category"):
        cons_rate = grp["consumption_rate"].mean()
        protein   = pd.to_numeric(grp["Protein (g)_consumed"], errors="coerce").mean()
        energy    = pd.to_numeric(grp["Energi (kcal)_consumed"], errors="coerce").mean()
        dvit      = pd.to_numeric(grp["Vitamin D (µg)_consumed"], errors="coerce").mean()
        n_dishes  = len(grp)
        pred_data.append({
            "Kategori":         cat,
            "Konsumtionsgrad":  cons_rate * 100,
            "Protein (g)":      protein,
            "Energi (kcal)":    energy,
            "D-vitamin (µg)":   dvit,
            "Antal rätter":     n_dishes,
        })
    pred_df = pd.DataFrame(pred_data)

    fig4 = go.Figure()
    colors_cat = {
        "Fisk": "#0ea5e9", "Kyckling": "#f59e0b", "Köttfärs": "#ef4444",
        "Korv": "#f97316", "Vegetariskt": "#22c55e", "Pasta/soppa": "#8b5cf6", "Övrigt": "#9ca3af"
    }
    for _, row in pred_df.iterrows():
        fig4.add_trace(go.Scatter(
            x=[row["Konsumtionsgrad"]],
            y=[row["Protein (g)"]],
            mode="markers+text",
            text=[row["Kategori"]],
            textposition="top center",
            marker=dict(
                size=row["D-vitamin (µg)"] * 12 + 12,
                color=colors_cat.get(row["Kategori"], "#9ca3af"),
                opacity=0.85,
                line=dict(width=1.5, color="white"),
            ),
            name=row["Kategori"],
            hovertemplate=(
                f"<b>{row['Kategori']}</b><br>"
                f"Konsumerat: {row['Konsumtionsgrad']:.1f}%<br>"
                f"Protein: {row['Protein (g)']:.1f} g<br>"
                f"D-vitamin: {row['D-vitamin (µg)']:.2f} µg<br>"
                f"Antal rätter: {row['Antal rätter']}<extra></extra>"
            ),
            showlegend=False,
        ))

    fig4.add_vline(x=90, line_dash="dash", line_color="#9ca3af",
                   annotation_text="90% konsumerat", annotation_position="bottom right",
                   annotation_font=dict(size=10))
    fig4.add_hline(y=NNR["Protein (g)"], line_dash="dash", line_color="#9ca3af",
                   annotation_text=f"NNR protein {NNR['Protein (g)']}g",
                   annotation_position="right", annotation_font=dict(size=10))

    fig4.update_layout(
        title=dict(
            text="Näringsvärde vs konsumtionsgrad — bubbelstorlek = D-vitamin<br>"
                 "<sub>Övre höger = hög näring + äts upp. Nedre vänster = låg näring + kastas.</sub>",
            font=dict(size=16), x=0.5
        ),
        xaxis_title="Konsumtionsgrad (% av serverat som äts)",
        yaxis_title="Protein per portion (g)",
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=12),
        width=850, height=560,
        xaxis=dict(gridcolor="#f3f4f6", range=[80, 100]),
        yaxis=dict(gridcolor="#f3f4f6"),
    )
    fig4.write_html(str(REPORTS / "nutrition_value_vs_consumption.html"), include_plotlyjs="cdn")
    print("  → nutrition_value_vs_consumption.html")

    return weekly_df, cat_df, pred_df


# ── Skriv insikter till Markdown ──────────────────────────────────────────────
def write_nutrition_insights(weekly_df: pd.DataFrame, cat_df: pd.DataFrame, pred_df: pd.DataFrame):
    lines = [
        "# Nutritionsanalys — faktisk näringsleverans till elever",
        "",
        "> Frågan är inte hur mycket mat som kastas — utan hur mycket näring eleverna faktiskt får i sig.",
        "",
        "## NNR-uppfyllnad (konsumerad näring vs rekommendation)",
        "",
    ]

    for n in KEY_NUTRIENTS:
        if n in weekly_df.columns:
            avg = weekly_df[n].mean()
            lo  = weekly_df[n].min()
            hi  = weekly_df[n].max()
            flag = "✅" if avg >= 90 else ("⚠️" if avg >= 70 else "❌")
            lines.append(f"- **{n.split(' (')[0]}**: snitt {avg:.0f}% av NNR (min {lo:.0f}%, max {hi:.0f}%) {flag}")

    lines += ["", "## Näring per rättkategori — konsumerat vs slängt", ""]
    lines += ["| Kategori | Protein konsum. (g) | Protein slängt (g) | D-vit % NNR | Järn % NNR |",
              "|---|---:|---:|---:|---:|"]
    for _, row in cat_df.sort_values("Protein (g)_consumed", ascending=False).iterrows():
        lines.append(
            f"| {row['Kategori']} "
            f"| {row.get('Protein (g)_consumed', 0):.1f} "
            f"| {row.get('Protein (g)_wasted', 0):.1f} "
            f"| {row.get('Vitamin D (µg)_pct_nnr', 0):.0f}% "
            f"| {row.get('Järn (mg)_pct_nnr', 0):.0f}% |"
        )

    lines += ["", "## Nyckelinsikt", "",
              "Kommunen betalar för att barn ska få i sig näring. Det som kastar mest näring per kr är "
              "inte nödvändigtvis det dyraste — det är det som serveras men inte äts.",
              "",
              "**Nästa steg:** Identifiera vilka specifika rätter som kombinerar hög nutritionell densitet "
              "med hög konsumtionsgrad — och prioritera dem i menyplaneringen."]

    (REPORTS / "nutrition_insights.md").write_text("\n".join(lines), encoding="utf-8")
    print("  → nutrition_insights.md")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Laddar data...")
    fw  = pd.read_parquet(PROCESSED / "food_waste.parquet")
    pur = pd.read_parquet(PROCESSED / "purchases.parquet")

    print("Läser näringsfiler...")
    nutr_skola = parse_nutrition(
        BASE / "Utveckling - Näring - Skola, Dagens lunch, Vegetarisk lunch 2025.xlsx",
        "skola"
    )

    print(f"  Skola: {len(nutr_skola)} rätter med näringsvärden")

    print("Beräknar konsumtionsgrad per vecka...")
    cons_rate = consumption_rate_by_week(fw)
    print(f"  Snitt konsumtionsgrad: {cons_rate.mean()*100:.1f}%")

    print("Beräknar faktisk näringsleverans...")
    delivered = compute_delivered_nutrition(nutr_skola, cons_rate)

    print("Skapar visualiseringar:")
    REPORTS.mkdir(exist_ok=True)
    weekly_df, cat_df, pred_df = build_nutrition_charts(delivered, pur)

    print("Skriver insikter...")
    write_nutrition_insights(weekly_df, cat_df, pred_df)

    print("\nKlart! Öppna:")
    for f in ["nutrition_nnr.html", "nutrition_protein.html",
              "nutrition_micronutrients.html", "nutrition_value_vs_consumption.html",
              "nutrition_insights.md"]:
        print(f"  reports/{f}")
