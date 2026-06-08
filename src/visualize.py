"""
Visualiseringar för skolmåltidsanalys PoC.
Genererar tre interaktiva HTML-filer i reports/:
  1. map_waste.html       — karta med svinn + kostnad per enhet
  2. scatter_units.html   — kostnad vs svinn per enhet (kvadrantmodell)
  3. dish_categories.html — rättkategori vs svinn
"""
from __future__ import annotations

import re
from pathlib import Path

import folium
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from folium.plugins import MarkerCluster

# ── Koordinater för enheter i Höganäs kommun ─────────────────────────────────
# Manuellt geocodade baserat på känd geografi i kommunen
UNIT_COORDS = {
    "Kullagymnasiet":       (56.1997, 12.5486),   # Höganäs centrum
    "Bruksskolan":          (56.2010, 12.5520),   # Höganäs
    "Tornlyckeskolan":      (56.1980, 12.5540),   # Höganäs
    "Jonstorpsskolan":      (56.2250, 12.5820),   # Jonstorp
    "Lerbergsskolan":       (56.2420, 12.5300),   # Lerberget
    "Nyhamnsskolan":        (56.2620, 12.5680),   # Nyhamnsläge
    "Vikenskolan":          (56.1480, 12.5690),   # Viken
    "Väsbyhemmet":          (56.2000, 12.5480),   # Höganäs (äldreboende)
    "Vikhaga":              (56.1460, 12.5660),   # Viken
    "Nyhamnsgården":        (56.2630, 12.5670),   # Nyhamnsläge (äldreboende)
    "Äventyrets förskola":  (56.2020, 12.5500),   # Höganäs
    "Bruksskolan":          (56.2010, 12.5520),
    "Eleshults förskola":   (56.2150, 12.5600),   # Höganäs tätort
    "Eric Ruuths förskola": (56.2030, 12.5510),   # Höganäs
    "Havets förskola":      (56.1490, 12.5700),   # Viken
    "Klöverängens förskola":(56.2180, 12.5750),   # Höganäs öst
    "Lärlyckans förskola":  (56.1980, 12.5460),   # Höganäs
    "Peter Lundhs förskola":(56.2050, 12.5530),   # Höganäs
    "Revets förskola":      (56.1470, 12.5680),   # Viken
    "Solgläntans förskola": (56.2200, 12.5650),   # Höganäs
    "Svanebäcks förskola":  (56.2280, 12.5390),   # Lerberget-området
    "Vikens Ry förskola":   (56.1500, 12.5720),   # Viken
}

# ── Rättkategorier via nyckelord ──────────────────────────────────────────────
DISH_CATEGORIES = {
    "Fisk":        ["fisk", "torsk", "lax", "hoki", "pankofisk", "fiskgratäng",
                    "fiskburgare", "fiskpanett", "cornflakesfisk", "sprödbakad fisk"],
    "Kyckling":    ["kyckling", "kycklingfile", "kycklinggryta", "kycklingkorvgryta",
                    "kycklingwok", "kycklinglasagne", "tikka"],
    "Köttfärs/biff":["köttbullar", "köttfärs", "lasagne", "spaghetti", "färsrätt",
                    "pannbiff", "biff", "chili con carne", "gulasch", "kalops"],
    "Korv":        ["korv", "wienerkorv", "falukorv", "korvgryta", "kebab"],
    "Kött (övrigt)":["schnitzel", "kassler", "fläsk", "kött", "nöt", "kalkon",
                    "kalops", "skinkstek"],
    "Vegetariskt": ["vegetarisk", "quorn", "blomkål", "grönsakspaj", "grönsakstimbal",
                    "choladesgryta", "soppa", "tomatgryta", "minestrone"],
    "Pasta/ris":   ["pasta", "spaghetti", "makaroner", "ris", "lasagne", "gratäng",
                    "penne", "nudlar"],
    "Soppa":       ["soppa", "gryta med bröd", "gulaschsoppa", "tomatgryta med bröd"],
}


def categorize_dish(dish_name: str) -> str:
    name = dish_name.lower()
    for cat, keywords in DISH_CATEGORIES.items():
        if any(kw in name for kw in keywords):
            return cat
    return "Övrigt"


def load_data(processed_dir: Path) -> dict:
    fw  = pd.read_parquet(processed_dir / "food_waste.parquet")
    pur = pd.read_parquet(processed_dir / "purchases.parquet")
    por = pd.read_parquet(processed_dir / "portions.parquet")
    mn  = pd.read_parquet(processed_dir / "menu_nutrition.parquet")
    return dict(fw=fw, pur=pur, por=por, mn=mn)


def build_unit_metrics(data: dict) -> pd.DataFrame:
    fw  = data["fw"]
    pur = data["pur"]
    por = data["por"]

    # Svinn per portion per enhet
    fw_c = fw[(fw["served_portions"].notna()) & (fw["total_waste_kg"].notna())].copy()
    fw_c["served_portions"] = pd.to_numeric(fw_c["served_portions"], errors="coerce")
    fw_c["total_waste_kg"]  = pd.to_numeric(fw_c["total_waste_kg"],  errors="coerce")
    fw_c = fw_c[fw_c["served_portions"] > 10]
    fw_c["wpp"] = fw_c["total_waste_kg"] / fw_c["served_portions"]
    fw_c = fw_c[fw_c["wpp"].notna() & (fw_c["wpp"] != float("inf"))]
    waste_u = fw_c.groupby("unit_name")["wpp"].mean().rename("waste_per_portion")

    # Inköpskostnad per enhet
    pur_c = pur[pur["unit_name_std"].notna()].copy()
    pur_c["kronor"] = pd.to_numeric(pur_c["kronor"], errors="coerce")
    cost_u = pur_c.groupby("unit_name_std")["kronor"].sum().rename("total_cost")

    # Portioner per enhet
    lunch = por[por["portion_type"].isin(["lunch_children","lunch_guests"])].copy()
    lunch["count"] = pd.to_numeric(lunch["count"], errors="coerce")
    por_u = lunch.groupby("unit_name")["count"].sum().rename("total_portions")

    # Avtalstrohet
    def wavg(g):
        w = pd.to_numeric(g["kronor"], errors="coerce")
        v = pd.to_numeric(g["procent_utanfor_avtal"], errors="coerce")
        mask = v.notna() & w.notna() & (w > 0)
        return (v[mask] * w[mask]).sum() / w[mask].sum() if mask.sum() > 0 else float("nan")
    contract_u = pur_c.groupby("unit_name_std").apply(wavg).rename("off_contract_pct")

    # Kombinera på gemensamt index (unit_name)
    df = pd.DataFrame({
        "waste_per_portion": waste_u,
        "total_cost":        cost_u,
        "total_portions":    por_u,
        "off_contract_pct":  contract_u,
    })

    # Kostnad per portion (cross)
    df["cost_per_portion"] = df["total_cost"] / df["total_portions"]

    # Lägg till koordinater
    df["lat"] = df.index.map(lambda u: UNIT_COORDS.get(u, (None, None))[0])
    df["lon"] = df.index.map(lambda u: UNIT_COORDS.get(u, (None, None))[1])

    # Enhetstyp
    def etype(name):
        n = str(name).lower()
        if "förskola" in n or "fsk" in n:
            return "Förskola"
        if any(x in n for x in ["gymnasium", "gymnasiet"]):
            return "Gymnasium"
        if any(x in n for x in ["hemmet", "gården", "haga", "vikhaga"]):
            return "Äldreomsorg/kök"
        return "Grundskola"
    df["unit_type"] = df.index.map(etype)

    df = df.reset_index()
    df = df.rename(columns={"index": "unit_name"}) if "unit_name" not in df.columns else df
    return df


# ── 1. KARTA ──────────────────────────────────────────────────────────────────
def build_map(df: pd.DataFrame, out_path: Path):
    df_map = df[df["lat"].notna() & df["lon"].notna()].copy()

    m = folium.Map(
        location=[56.20, 12.56],
        zoom_start=12,
        tiles="CartoDB positron",
    )

    # Färg per enhetstyp
    type_colors = {
        "Grundskola":        "#2563eb",
        "Gymnasium":         "#7c3aed",
        "Förskola":          "#16a34a",
        "Äldreomsorg/kök":   "#ea580c",
    }

    max_waste = df_map["waste_per_portion"].max()

    for _, row in df_map.iterrows():
        wpp   = row["waste_per_portion"]
        cost  = row["total_cost"]
        cpp   = row["cost_per_portion"]
        ocp   = row["off_contract_pct"]
        color = type_colors.get(row["unit_type"], "#6b7280")

        # Bubbelstorlek baserat på svinn per portion (normaliserat)
        radius = 8 + 28 * (wpp / max_waste) if pd.notna(wpp) and max_waste > 0 else 8

        popup_html = f"""
        <div style='font-family:sans-serif;min-width:200px'>
          <b style='font-size:14px'>{row['unit_name']}</b><br>
          <span style='color:#6b7280'>{row['unit_type']}</span><br><br>
          <table style='width:100%'>
            <tr><td>Svinn/portion</td><td><b>{wpp:.4f} kg</b></td></tr>
            <tr><td>Total inköp</td><td><b>{cost:,.0f} kr</b></td></tr>
            {'<tr><td>Kr/portion</td><td><b>' + f'{cpp:.0f} kr</b></td></tr>' if pd.notna(cpp) else ''}
            {'<tr><td>Utanför avtal</td><td><b>' + f'{ocp:.1f} %</b></td></tr>' if pd.notna(ocp) else ''}
          </table>
        </div>
        """

        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.75,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{row['unit_name']}: {wpp:.4f} kg/portion",
        ).add_to(m)

    # Legend
    legend_html = """
    <div style='position:fixed;bottom:30px;left:30px;z-index:1000;
                background:white;padding:12px 16px;border-radius:8px;
                box-shadow:0 2px 8px rgba(0,0,0,0.15);font-family:sans-serif;font-size:13px'>
      <b>Svinn per serverad portion</b><br>
      <span style='color:#6b7280;font-size:11px'>Bubbelstorlek = svinn/portion</span><br><br>
      <span style='color:#2563eb'>●</span> Grundskola<br>
      <span style='color:#7c3aed'>●</span> Gymnasium<br>
      <span style='color:#16a34a'>●</span> Förskola<br>
      <span style='color:#ea580c'>●</span> Äldreomsorg/kök
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    m.save(str(out_path))
    print(f"  → {out_path.name}")


# ── 2. SCATTER — kostnad vs svinn per enhet ───────────────────────────────────
def build_scatter(df: pd.DataFrame, out_path: Path):
    df_s = df[df["waste_per_portion"].notna() & df["total_cost"].notna()].copy()

    # Medianlinjer för kvadranter
    med_waste = df_s["waste_per_portion"].median()
    med_cost  = df_s["total_cost"].median()

    type_colors = {
        "Grundskola":       "#2563eb",
        "Gymnasium":        "#7c3aed",
        "Förskola":         "#16a34a",
        "Äldreomsorg/kök":  "#ea580c",
    }

    fig = go.Figure()

    # Kvadrant-bakgrund
    for color, x0, x1, y0, y1, label in [
        ("rgba(239,68,68,0.07)",   med_cost, None, med_waste, None, "Dyr + Hög svinn"),
        ("rgba(234,179,8,0.07)",   None, med_cost, med_waste, None, "Billig + Hög svinn"),
        ("rgba(34,197,94,0.07)",   None, med_cost, None, med_waste, "Billig + Låg svinn ★"),
        ("rgba(59,130,246,0.07)",  med_cost, None, None, med_waste, "Dyr + Låg svinn"),
    ]:
        fig.add_shape(type="rect",
            x0=x0 if x0 else 0, x1=x1 if x1 else df_s["total_cost"].max()*1.1,
            y0=y0 if y0 else 0, y1=y1 if y1 else df_s["waste_per_portion"].max()*1.1,
            fillcolor=color, line_width=0, layer="below")

    # Kvadrant-etiketter
    for text, x, y, xanch, yanch in [
        ("🔴 Dyr + Hög svinn",    df_s["total_cost"].max()*0.98, df_s["waste_per_portion"].max()*0.98, "right", "top"),
        ("🟡 Billig + Hög svinn", med_cost*0.02,                 df_s["waste_per_portion"].max()*0.98, "left",  "top"),
        ("🟢 Billig + Låg svinn", med_cost*0.02,                 med_waste*0.02,                       "left",  "bottom"),
        ("🔵 Dyr + Låg svinn",    df_s["total_cost"].max()*0.98, med_waste*0.02,                       "right", "bottom"),
    ]:
        fig.add_annotation(x=x, y=y, text=text, showarrow=False,
            font=dict(size=11, color="#374151"),
            xanchor=xanch, yanchor=yanch)

    # En serie per enhetstyp
    for utype, color in type_colors.items():
        sub = df_s[df_s["unit_type"] == utype]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["total_cost"],
            y=sub["waste_per_portion"],
            mode="markers+text",
            name=utype,
            text=sub["unit_name"],
            textposition="top center",
            textfont=dict(size=9),
            marker=dict(size=14, color=color, opacity=0.85,
                        line=dict(width=1.5, color="white")),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Inköp: %{x:,.0f} kr<br>"
                "Svinn: %{y:.4f} kg/portion<br>"
                "<extra></extra>"
            ),
        ))

    # Medianllinjer
    fig.add_hline(y=med_waste, line_dash="dash", line_color="#9ca3af", line_width=1)
    fig.add_vline(x=med_cost,  line_dash="dash", line_color="#9ca3af", line_width=1)

    fig.update_layout(
        title=dict(
            text="Kostnad vs Svinn per enhet — var finns förbättringspotential?",
            font=dict(size=18), x=0.5
        ),
        xaxis_title="Total inköpskostnad 2025 (kr)",
        yaxis_title="Svinn per serverad portion (kg)",
        font=dict(family="Inter, sans-serif", size=12),
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        width=950, height=620,
        xaxis=dict(gridcolor="#f3f4f6", tickformat=",.0f"),
        yaxis=dict(gridcolor="#f3f4f6", tickformat=".4f"),
    )

    fig.write_html(str(out_path), include_plotlyjs="cdn")
    print(f"  → {out_path.name}")


# ── 3. RÄTTKATEGORI vs SVINN ──────────────────────────────────────────────────
def build_dish_category_chart(data: dict, out_path: Path):
    mn = data["mn"]
    fw = data["fw"]

    # Kategorisera rätter
    skola = mn[(mn["menu_type"] == "skola") & (mn["dish_type"] == "dagens_lunch")].copy()
    skola["category"] = skola["dish_name"].apply(categorize_dish)
    skola["week"] = pd.to_numeric(skola["week"], errors="coerce")

    # Svinn per vecka
    fw_c = fw[fw["served_portions"].notna() & fw["total_waste_kg"].notna()].copy()
    fw_c["served_portions"] = pd.to_numeric(fw_c["served_portions"], errors="coerce")
    fw_c["total_waste_kg"]  = pd.to_numeric(fw_c["total_waste_kg"],  errors="coerce")
    fw_c["week"]            = pd.to_numeric(fw_c["week"], errors="coerce")
    fw_c = fw_c[fw_c["served_portions"] > 10]
    fw_c["wpp"] = fw_c["total_waste_kg"] / fw_c["served_portions"]
    fw_c = fw_c[fw_c["wpp"].notna() & (fw_c["wpp"] != float("inf"))]
    fw_week = fw_c.groupby("week")["wpp"].mean().reset_index()
    fw_week.columns = ["week", "waste_per_portion"]

    # Dominant kategori per vecka (den som förekommer flest gånger)
    dominant = skola.groupby("week")["category"].agg(
        lambda x: x.value_counts().index[0]
    ).reset_index()
    dominant.columns = ["week", "dominant_category"]

    merged = fw_week.merge(dominant, on="week", how="inner")

    # Aggregera per kategori
    cat_stats = (
        merged.groupby("dominant_category")["waste_per_portion"]
        .agg(["mean", "median", "count"])
        .reset_index()
        .rename(columns={"dominant_category": "Kategori", "mean": "Medel", "median": "Median", "count": "Veckor"})
        .sort_values("Medel", ascending=True)
    )

    # Referenslinje = totalt medel
    overall_mean = merged["waste_per_portion"].mean()

    cat_colors = {
        "Fisk":           "#0ea5e9",
        "Kyckling":       "#f59e0b",
        "Köttfärs/biff":  "#ef4444",
        "Korv":           "#f97316",
        "Kött (övrigt)":  "#dc2626",
        "Vegetariskt":    "#22c55e",
        "Pasta/ris":      "#8b5cf6",
        "Soppa":          "#06b6d4",
        "Övrigt":         "#9ca3af",
    }

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=cat_stats["Medel"],
        y=cat_stats["Kategori"],
        orientation="h",
        marker_color=[cat_colors.get(c, "#9ca3af") for c in cat_stats["Kategori"]],
        text=[f"{v:.4f} kg  ({n} v.)" for v, n in zip(cat_stats["Medel"], cat_stats["Veckor"])],
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Medel svinn: %{x:.4f} kg/portion<br>"
            "<extra></extra>"
        ),
    ))

    # Referenslinje
    fig.add_vline(x=overall_mean, line_dash="dash", line_color="#6b7280",
                  annotation_text=f"Totalt medel: {overall_mean:.4f}",
                  annotation_position="top right",
                  annotation_font=dict(size=11, color="#6b7280"))

    fig.update_layout(
        title=dict(
            text="Vilket matval driver svinnet? — Svinn per portion per rättkategori",
            font=dict(size=18), x=0.5
        ),
        xaxis_title="Medel svinn per serverad portion (kg)",
        yaxis_title="",
        font=dict(family="Inter, sans-serif", size=12),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
        width=850, height=480,
        xaxis=dict(gridcolor="#f3f4f6", tickformat=".4f"),
        margin=dict(l=120, r=160, t=80, b=60),
    )

    fig.write_html(str(out_path), include_plotlyjs="cdn")
    print(f"  → {out_path.name}")


# ── Kör allt ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent
    processed = base / "data" / "processed"
    reports   = base / "reports"
    reports.mkdir(exist_ok=True)

    print("Laddar data...")
    data = load_data(processed)

    print("Bygger enhetsmetrik...")
    unit_df = build_unit_metrics(data)

    print("Skapar visualiseringar:")
    build_map(unit_df, reports / "map_waste.html")
    build_scatter(unit_df, reports / "scatter_units.html")
    build_dish_category_chart(data, reports / "dish_categories.html")

    print("\nKlart! Öppna i browser:")
    for f in ["map_waste.html", "scatter_units.html", "dish_categories.html"]:
        print(f"  reports/{f}")
