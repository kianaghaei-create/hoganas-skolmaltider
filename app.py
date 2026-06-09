"""Streamlit BI dashboard — Höganäs skolmåltidsanalys med OpenAI AI-assistent."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Höganäs Skolmåltider",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Password gate ──────────────────────────────────────────────────────────────
APP_PASSWORD = (
    st.secrets.get("APP_PASSWORD")
    or os.environ.get("APP_PASSWORD")
    or ""
)

if APP_PASSWORD:
    if not st.session_state.get("authenticated"):
        st.markdown("<br><br>", unsafe_allow_html=True)
        col_a, col_b, col_c = st.columns([1, 1.2, 1])
        with col_b:
            st.markdown("### 🍽️ Höganäs Skolmåltider")
            st.caption("Kostanalys 2025 — ange lösenord för att fortsätta")
            pwd = st.text_input("Lösenord", type="password", placeholder="Ange lösenord…")
            if st.button("Logga in", use_container_width=True, type="primary"):
                if pwd == APP_PASSWORD:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Fel lösenord. Försök igen.")
        st.stop()

# ── Minimal CSS — only what config.toml can't do ──────────────────────────────
st.markdown("""
<style>
/* KPI metric cards */
.kpi-card {
    background: #ffffff;
    border-radius: 12px;
    padding: 20px 24px 16px;
    border-left: 4px solid;
    box-shadow: 0 1px 6px rgba(0,0,0,.07);
    margin-bottom: 4px;
}
.kpi-label { font-size: 0.72rem; font-weight: 600; color: #8896a6;
             text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; }
.kpi-value { font-size: 1.95rem; font-weight: 700; line-height: 1.1; }
.kpi-sub   { font-size: 0.75rem; color: #a0aec0; margin-top: 6px; }

/* Chart wrapper cards */
.chart-box {
    background: #ffffff;
    border-radius: 12px;
    padding: 20px 20px 8px;
    box-shadow: 0 1px 6px rgba(0,0,0,.07);
    margin-bottom: 16px;
}
/* Tighten Streamlit's default padding a bit */
[data-testid="stVerticalBlock"] { gap: 0.6rem; }
</style>
""", unsafe_allow_html=True)

# ── OpenAI ─────────────────────────────────────────────────────────────────────
try:
    import openai as _oai
    OPENAI_KEY = (
        st.secrets.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ""
    )
    _oai.api_key = OPENAI_KEY
    OPENAI_AVAILABLE = bool(OPENAI_KEY)
except Exception:
    OPENAI_AVAILABLE = False

# ── Data ───────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "Data" / "processed"

@st.cache_data
def load_data():
    out = {}
    for name in ["purchases", "food_waste", "portions", "menu_nutrition", "preschool_billing"]:
        p = DATA_DIR / f"{name}.csv"
        if p.exists():
            out[name] = pd.read_csv(p, low_memory=False)
    return out

data       = load_data()
purchases  = data.get("purchases",         pd.DataFrame())
food_waste = data.get("food_waste",         pd.DataFrame())
portions   = data.get("portions",           pd.DataFrame())
menu_nutr  = data.get("menu_nutrition",     pd.DataFrame())
preschool  = data.get("preschool_billing",  pd.DataFrame())

# Derived: clean food-waste rows (remove obvious data-entry errors)
fw_clean = food_waste[food_waste["total_waste_pct"] <= 1.0].copy() if not food_waste.empty else food_waste.copy()

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🍽️ Höganäs")
    st.caption("Skolmåltidsanalys 2025")
    st.divider()
    page = st.radio(
        "Navigera",
        [
            "📊 Översikt",
            "🗑️ Svinnanalys",
            "🎯 Beställningsprecision",
            "🛒 Inköp & ekonomi",
            "📋 Avtalstrohet",
            "⚠️ Datakvalitet",
            "🤖 AI-assistent",
        ],
        label_visibility="collapsed",
    )

# ── Helper: KPI card ───────────────────────────────────────────────────────────
def kpi(label: str, value: str, sub: str = "", color: str = "#3B82F6"):
    st.markdown(f"""
    <div class="kpi-card" style="border-color:{color}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value" style="color:{color}">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """, unsafe_allow_html=True)

def fmt_sek(v):
    return f"{v/1_000_000:.1f} Mkr" if v >= 1_000_000 else f"{v/1_000:.0f} tkr"

PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="sans-serif", color="#4a5568"),
    margin=dict(t=20, b=20, l=10, r=10),
    xaxis=dict(showgrid=True, gridcolor="#f0f0f0", zeroline=False),
    yaxis=dict(showgrid=True, gridcolor="#f0f0f0", zeroline=False),
)

# ══════════════════════════════════════════════════════════════════════════════
# ÖVERSIKT
# ══════════════════════════════════════════════════════════════════════════════
if page == "📊 Översikt":
    st.title("Översikt")
    st.caption("Höganäs skolmåltidsanalys 2025 — helårsdata")

    # Global filters
    col_f1, col_f2, _, _ = st.columns([2, 2, 2, 2])
    units_all = sorted(food_waste["unit_name"].dropna().unique()) if not food_waste.empty else []
    with col_f1:
        sel_unit = st.selectbox("Enhet", ["Alla"] + units_all)
    with col_f2:
        months_all = sorted(purchases["month"].dropna().unique().tolist()) if not purchases.empty else []
        sel_month  = st.selectbox("Månad", ["Alla"] + [str(int(m)) for m in months_all])

    fw_f = fw_clean if sel_unit == "Alla" else fw_clean[fw_clean["unit_name"] == sel_unit]
    pu_f = purchases if sel_unit == "Alla" else purchases[purchases.get("unit_name_std", purchases.get("enhet", pd.Series(dtype=str))).str.lower().str.contains(sel_unit.lower(), na=False)]
    if sel_month != "Alla":
        pu_f = pu_f[pu_f["month"] == int(sel_month)]

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        total_kg = food_waste["total_waste_kg"].sum() if "total_waste_kg" in food_waste.columns else 0
        kpi("Totalt matsvinn", f"{total_kg:,.0f} kg".replace(",", " "), "Alla enheter, helår 2025", "#EF4444")
    with c2:
        total_sek = purchases["kronor"].sum() if not purchases.empty else 0
        kpi("Total inköpskostnad", fmt_sek(total_sek), "Råvaruinköp, helår 2025", "#8B5CF6")
    with c3:
        n_units = food_waste["unit_name"].nunique() if not food_waste.empty else 0
        kpi("Antal enheter", str(n_units), "Skolor, förskolor, äldreomsorg", "#3B82F6")
    with c4:
        # Data quality: count distinct units with persistent over-ordering (> 20% of their weeks flagged)
        if "over_order_ratio" in food_waste.columns:
            per_unit = food_waste.groupby("unit_name").apply(
                lambda g: (g["over_order_ratio"] > 0.15).mean()
            )
            dq_flags = int((per_unit > 0.30).sum())
        else:
            dq_flags = 0
        kpi("Datakvalitetsflaggor", f"{dq_flags} kritiska" if dq_flags else "Inga", "Kräver uppföljning", "#F59E0B")

    st.markdown("<br>", unsafe_allow_html=True)

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown('<div class="chart-box">', unsafe_allow_html=True)
        st.subheader("Svinn per enhet — kg per beställd portion")
        if not food_waste.empty and "ordered_portions" in food_waste.columns:
            wu = (
                fw_f.groupby("unit_name")
                .apply(lambda g: g["total_waste_kg"].sum() / g["ordered_portions"].sum() if g["ordered_portions"].sum() > 0 else 0)
                .reset_index(name="kg_per_portion")
                .sort_values("kg_per_portion", ascending=True)
                .tail(15)
            )
            fig = px.bar(wu, x="kg_per_portion", y="unit_name", orientation="h",
                         color="kg_per_portion", color_continuous_scale=["#FEE2E2", "#EF4444"],
                         labels={"kg_per_portion": "kg/portion", "unit_name": ""})
            fig.update_layout(**PLOT_LAYOUT, showlegend=False, coloraxis_showscale=False)
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_b:
        st.markdown('<div class="chart-box">', unsafe_allow_html=True)
        st.subheader("Inköp per månad (SEK)")
        if not pu_f.empty:
            mp = pu_f.groupby(["year", "month"])["kronor"].sum().reset_index()
            mp["period"] = mp["year"].astype(str) + "-" + mp["month"].astype(str).str.zfill(2)
            mp = mp.sort_values("period")
            fig2 = px.bar(mp, x="period", y="kronor",
                          labels={"period": "", "kronor": "SEK"},
                          color_discrete_sequence=["#8B5CF6"])
            fig2.update_layout(**PLOT_LAYOUT)
            st.plotly_chart(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SVINNANALYS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🗑️ Svinnanalys":
    st.title("Svinnanalys")
    st.caption("Detaljerad analys av matsvinn per enhet, vecka och typ")

    units_list = sorted(fw_clean["unit_name"].dropna().unique()) if not fw_clean.empty else []
    sel = st.multiselect("Filtrera enheter", units_list, default=units_list[:8])
    df_fw = fw_clean[fw_clean["unit_name"].isin(sel)] if sel else fw_clean

    c1, c2, c3 = st.columns(3)
    with c1:
        kpi("Snitt svinn %", f"{df_fw['total_waste_pct'].median()*100:.1f} %", "Median (filtrerat urval)", "#EF4444")
    with c2:
        total_kg = df_fw["total_waste_kg"].sum() if "total_waste_kg" in df_fw.columns else 0
        kpi("Totalt svinn kg", f"{total_kg:,.0f} kg".replace(",", " "), "Filtrerat urval", "#F97316")
    with c3:
        worst = df_fw.groupby("unit_name")["total_waste_pct"].median().idxmax() if not df_fw.empty else "–"
        kpi("Högst svinn", worst, "Enhet med högst median", "#8B5CF6")

    st.markdown("<br>", unsafe_allow_html=True)
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown('<div class="chart-box">', unsafe_allow_html=True)
        st.subheader("Svinn % per vecka")
        fig = px.line(df_fw.sort_values("week"), x="week", y="total_waste_pct",
                      color="unit_name",
                      labels={"week": "Vecka", "total_waste_pct": "Svinn %", "unit_name": "Enhet"})
        fig.update_layout(**PLOT_LAYOUT)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_b:
        st.markdown('<div class="chart-box">', unsafe_allow_html=True)
        st.subheader("Svinntyper (medelvärde)")
        waste_cols = {"kitchen_waste_pct": "Kök", "serving_waste_pct": "Servering", "plate_waste_pct": "Tallrik"}
        avail = {v: df_fw[k].mean() for k, v in waste_cols.items() if k in df_fw.columns}
        if avail:
            fig2 = px.pie(values=list(avail.values()), names=list(avail.keys()), hole=0.45,
                          color_discrete_sequence=["#EF4444", "#F97316", "#FBBF24"])
            fig2.update_layout(**PLOT_LAYOUT)
            st.plotly_chart(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="chart-box">', unsafe_allow_html=True)
    st.subheader("Säsongsmönster — svinn per vecka (medel)")
    seasonal = fw_clean.groupby("week")["total_waste_pct"].median().reset_index()
    fig3 = px.area(seasonal, x="week", y="total_waste_pct",
                   labels={"week": "Vecka", "total_waste_pct": "Svinn % (median)"},
                   color_discrete_sequence=["#EF4444"])
    fig3.update_layout(**PLOT_LAYOUT)
    st.plotly_chart(fig3, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# BESTÄLLNINGSPRECISION
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🎯 Beställningsprecision":
    st.title("Beställningsprecision")
    st.caption("Hur väl stämmer beställda portioner mot faktiskt serverade?")

    if food_waste.empty or "ordered_portions" not in food_waste.columns:
        st.warning("Ingen portionsdata att visa.")
    else:
        fw_p = food_waste.copy()
        fw_p["precision_pct"] = (
            fw_p["served_portions"] / fw_p["ordered_portions"]
        ).clip(0, 2) * 100 if "served_portions" in fw_p.columns else None

        c1, c2, c3 = st.columns(3)
        with c1:
            over = (fw_p["over_order_ratio"] > 0.05).sum() if "over_order_ratio" in fw_p.columns else 0
            kpi("Veckor med överbeställning", str(int(over)), "> 5% över behovet", "#EF4444")
        with c2:
            avg_over = fw_p["over_order_ratio"].mean() * 100 if "over_order_ratio" in fw_p.columns else 0
            kpi("Snitt överbeställning", f"{avg_over:.1f} %", "Beställt vs serverat", "#F97316")
        with c3:
            exact = (fw_p["over_order_ratio"].abs() <= 0.02).sum() if "over_order_ratio" in fw_p.columns else 0
            kpi("Exakta beställningar", str(int(exact)), "Inom ±2 % av behovet", "#10B981")

        st.markdown("<br>", unsafe_allow_html=True)
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown('<div class="chart-box">', unsafe_allow_html=True)
            st.subheader("Överbeställningsgrad per enhet")
            if "over_order_ratio" in fw_p.columns:
                by_unit = fw_p.groupby("unit_name")["over_order_ratio"].mean().reset_index()
                by_unit["over_pct"] = by_unit["over_order_ratio"] * 100
                by_unit = by_unit.sort_values("over_pct", ascending=True)
                fig = px.bar(by_unit, x="over_pct", y="unit_name", orientation="h",
                             color="over_pct",
                             color_continuous_scale=["#D1FAE5", "#10B981", "#EF4444"],
                             labels={"over_pct": "Överbeställning %", "unit_name": ""})
                fig.update_layout(**PLOT_LAYOUT, showlegend=False, coloraxis_showscale=False)
                st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col_b:
            st.markdown('<div class="chart-box">', unsafe_allow_html=True)
            st.subheader("Beställda vs serverade portioner")
            if "served_portions" in fw_p.columns:
                week_sum = fw_p.groupby("week")[["ordered_portions", "served_portions"]].mean().reset_index()
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=week_sum["week"], y=week_sum["ordered_portions"],
                                          name="Beställda", line=dict(color="#3B82F6")))
                fig2.add_trace(go.Scatter(x=week_sum["week"], y=week_sum["served_portions"],
                                          name="Serverade", line=dict(color="#10B981")))
                fig2.update_layout(**PLOT_LAYOUT, xaxis_title="Vecka", yaxis_title="Portioner")
                st.plotly_chart(fig2, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# INKÖP & EKONOMI
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🛒 Inköp & ekonomi":
    st.title("Inköp & ekonomi")
    st.caption("Råvaruinköp, leverantörer och kostnadsutveckling 2025")

    if purchases.empty:
        st.warning("Ingen inköpsdata.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            kpi("Total inköpskostnad", fmt_sek(purchases["kronor"].sum()), "Råvaror 2025", "#8B5CF6")
        with c2:
            n_sup = purchases["supplier"].nunique()
            kpi("Antal leverantörer", str(n_sup), "Unika leverantörer", "#3B82F6")
        with c3:
            if "ekologisk" in purchases.columns:
                eco_pct = purchases[purchases["ekologisk"] == "Ja"]["kronor"].sum() / purchases["kronor"].sum() * 100
                kpi("Ekologisk andel", f"{eco_pct:.1f} %", "Andel av inköpsvärde", "#10B981")

        st.markdown("<br>", unsafe_allow_html=True)
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown('<div class="chart-box">', unsafe_allow_html=True)
            st.subheader("Topp 10 varugrupper")
            top_g = purchases.groupby("varugrupp")["kronor"].sum().nlargest(10).reset_index().sort_values("kronor")
            fig = px.bar(top_g, x="kronor", y="varugrupp", orientation="h",
                         color_discrete_sequence=["#8B5CF6"],
                         labels={"kronor": "SEK", "varugrupp": ""})
            fig.update_layout(**PLOT_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col_b:
            st.markdown('<div class="chart-box">', unsafe_allow_html=True)
            st.subheader("Topp 10 leverantörer")
            top_s = purchases.groupby("supplier")["kronor"].sum().nlargest(10).reset_index().sort_values("kronor")
            fig2 = px.bar(top_s, x="kronor", y="supplier", orientation="h",
                          color_discrete_sequence=["#3B82F6"],
                          labels={"kronor": "SEK", "supplier": ""})
            fig2.update_layout(**PLOT_LAYOUT)
            st.plotly_chart(fig2, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        col_c, col_d = st.columns(2)

        with col_c:
            st.markdown('<div class="chart-box">', unsafe_allow_html=True)
            st.subheader("Kostnadsutveckling per månad")
            mp = purchases.groupby(["year", "month"])["kronor"].sum().reset_index()
            mp["period"] = mp["year"].astype(str) + "-" + mp["month"].astype(str).str.zfill(2)
            mp = mp.sort_values("period")
            fig3 = px.line(mp, x="period", y="kronor",
                           labels={"period": "", "kronor": "SEK"},
                           color_discrete_sequence=["#8B5CF6"])
            fig3.update_layout(**PLOT_LAYOUT)
            st.plotly_chart(fig3, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col_d:
            st.markdown('<div class="chart-box">', unsafe_allow_html=True)
            st.subheader("Ekologiskt vs konventionellt")
            if "ekologisk" in purchases.columns:
                eco = purchases.groupby("ekologisk")["kronor"].sum().reset_index()
                eco["label"] = eco["ekologisk"].map({"Ja": "Ekologisk", "Nej": "Konventionell"}).fillna("Okänd")
                fig4 = px.pie(eco, values="kronor", names="label", hole=0.45,
                              color_discrete_sequence=["#10B981", "#E5E7EB", "#8B5CF6"])
                fig4.update_layout(**PLOT_LAYOUT)
                st.plotly_chart(fig4, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# AVTALSTROHET
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Avtalstrohet":
    st.title("Avtalstrohet")
    st.caption("Andel inköp utanför upphandlade avtal")

    if purchases.empty or "procent_utanfor_avtal" not in purchases.columns:
        st.warning("Ingen avtalsdata tillgänglig.")
    else:
        pu_a = purchases.copy()
        outside = pu_a[pu_a["procent_utanfor_avtal"] > 0]

        c1, c2, c3 = st.columns(3)
        with c1:
            out_pct = outside["kronor"].sum() / pu_a["kronor"].sum() * 100
            kpi("Utanför avtal", f"{out_pct:.1f} %", "Andel av total kostnad", "#EF4444")
        with c2:
            kpi("Inom avtal", f"{100-out_pct:.1f} %", "Andel av total kostnad", "#10B981")
        with c3:
            n_rows = len(outside)
            kpi("Antal rader utanför avtal", f"{n_rows:,}".replace(",", " "), "Inköpstransaktioner", "#F59E0B")

        st.markdown("<br>", unsafe_allow_html=True)
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown('<div class="chart-box">', unsafe_allow_html=True)
            st.subheader("Avtalstrohet per enhet")
            by_unit = pu_a.groupby("enhet").apply(
                lambda g: g[g["procent_utanfor_avtal"] > 0]["kronor"].sum() / g["kronor"].sum() * 100
                if g["kronor"].sum() > 0 else 0
            ).reset_index(name="utanfor_pct").sort_values("utanfor_pct", ascending=False).head(15)
            fig = px.bar(by_unit.sort_values("utanfor_pct"), x="utanfor_pct", y="enhet",
                         orientation="h",
                         color="utanfor_pct", color_continuous_scale=["#D1FAE5", "#FEF3C7", "#EF4444"],
                         labels={"utanfor_pct": "% utanför avtal", "enhet": ""})
            fig.update_layout(**PLOT_LAYOUT, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col_b:
            st.markdown('<div class="chart-box">', unsafe_allow_html=True)
            st.subheader("Utanför avtal per varugrupp (SEK)")
            by_grp = outside.groupby("varugrupp")["kronor"].sum().nlargest(10).reset_index().sort_values("kronor")
            fig2 = px.bar(by_grp, x="kronor", y="varugrupp", orientation="h",
                          color_discrete_sequence=["#F59E0B"],
                          labels={"kronor": "SEK", "varugrupp": ""})
            fig2.update_layout(**PLOT_LAYOUT)
            st.plotly_chart(fig2, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# DATAKVALITET
# ══════════════════════════════════════════════════════════════════════════════
elif page == "⚠️ Datakvalitet":
    st.title("Datakvalitet")
    st.caption("Flaggor och avvikelser som kräver uppföljning")

    issues = []

    # Food waste: missing plate_waste
    if not food_waste.empty and "plate_waste_pct" in food_waste.columns:
        missing_plate = food_waste["plate_waste_pct"].isna().sum()
        if missing_plate:
            issues.append({"Typ": "Saknade värden", "Tabell": "Matsvinn", "Beskrivning": f"{missing_plate} rader saknar tallriksvinn", "Allvarlighet": "Varning"})

    # Outlier waste
    if not food_waste.empty:
        outliers = (food_waste["total_waste_pct"] > 1.0).sum()
        if outliers:
            issues.append({"Typ": "Extremvärde", "Tabell": "Matsvinn", "Beskrivning": f"{outliers} rader med svinn > 100 %", "Allvarlighet": "Kritisk"})

    # Purchases: missing supplier
    if not purchases.empty:
        miss_sup = purchases["supplier"].isna().sum()
        if miss_sup:
            issues.append({"Typ": "Saknade värden", "Tabell": "Inköp", "Beskrivning": f"{miss_sup} rader saknar leverantör", "Allvarlighet": "Varning"})

    # Preschool: diff portions
    if not preschool.empty and "diff_portions" in preschool.columns:
        big_diff = (preschool["diff_portions"].abs() > 50).sum()
        if big_diff:
            issues.append({"Typ": "Avvikelse", "Tabell": "Förskoledebitering", "Beskrivning": f"{big_diff} rader med portionsavvikelse > 50", "Allvarlighet": "Kritisk"})

    critical = sum(1 for i in issues if i["Allvarlighet"] == "Kritisk")
    warnings = sum(1 for i in issues if i["Allvarlighet"] == "Varning")

    c1, c2, c3 = st.columns(3)
    with c1:
        kpi("Kritiska flaggor", str(critical), "Kräver omedelbar åtgärd", "#EF4444")
    with c2:
        kpi("Varningar", str(warnings), "Bör kontrolleras", "#F59E0B")
    with c3:
        kpi("Totalt kontrollerade tabeller", "5", "purchases, food_waste, portions, menu, preschool", "#3B82F6")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="chart-box">', unsafe_allow_html=True)
    st.subheader("Flaggor")
    if issues:
        df_issues = pd.DataFrame(issues)
        def color_row(row):
            c = "#FEE2E2" if row["Allvarlighet"] == "Kritisk" else "#FEF3C7"
            return [f"background-color: {c}"] * len(row)
        st.dataframe(
            df_issues.style.apply(color_row, axis=1),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("Inga flaggor hittades!")
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# AI-ASSISTENT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🤖 AI-assistent":
    st.title("AI-assistent")
    st.caption("Ställ frågor om skolmåltidsdata. Drivs av OpenAI GPT-4o mini.")

    if not OPENAI_AVAILABLE:
        st.error("OpenAI API-nyckel saknas. Lägg till `OPENAI_API_KEY` i Streamlit Secrets.")
        st.stop()

    @st.cache_data
    def build_system_prompt() -> str:
        # ── Compute rich statistics to inject as context ──────────────────────
        ctx = {}

        if not fw_clean.empty:
            ctx["fw_units"]   = fw_clean["unit_name"].nunique()
            ctx["fw_median"]  = fw_clean["total_waste_pct"].median() * 100
            ctx["fw_kg"]      = food_waste["total_waste_kg"].sum() if "total_waste_kg" in food_waste.columns else 0
            by_unit           = fw_clean.groupby("unit_name")["total_waste_pct"].median() * 100
            ctx["fw_worst5"]  = by_unit.nlargest(5).to_dict()
            ctx["fw_best5"]   = by_unit.nsmallest(5).to_dict()
            if "over_order_ratio" in food_waste.columns:
                ctx["over_mean"] = food_waste["over_order_ratio"].mean() * 100
                ctx["over_worst"] = food_waste.groupby("unit_name")["over_order_ratio"].mean().nlargest(5).to_dict()
            if "plate_waste_pct" in fw_clean.columns:
                ctx["plate_median"] = fw_clean["plate_waste_pct"].median() * 100
            if "serving_waste_pct" in fw_clean.columns:
                ctx["serving_median"] = fw_clean["serving_waste_pct"].median() * 100

        if not purchases.empty:
            ctx["pu_total"]      = purchases["kronor"].sum()
            ctx["pu_suppliers"]  = purchases["supplier"].nunique()
            ctx["pu_top5_sup"]   = purchases.groupby("supplier")["kronor"].sum().nlargest(5).to_dict()
            ctx["pu_top5_grp"]   = purchases.groupby("varugrupp")["kronor"].sum().nlargest(5).to_dict()
            if "ekologisk" in purchases.columns:
                ctx["eco_pct"]   = purchases[purchases["ekologisk"]=="Ja"]["kronor"].sum() / purchases["kronor"].sum() * 100
            if "procent_utanfor_avtal" in purchases.columns:
                ctx["out_pct"]   = purchases[purchases["procent_utanfor_avtal"]>0]["kronor"].sum() / purchases["kronor"].sum() * 100
                ctx["out_top5"]  = purchases.groupby("enhet").apply(
                    lambda g: g[g["procent_utanfor_avtal"]>0]["kronor"].sum() / g["kronor"].sum() * 100
                    if g["kronor"].sum() > 0 else 0
                ).nlargest(5).to_dict()

        if not portions.empty:
            ctx["por_total"] = int(portions["count"].sum())
            ctx["por_top5"]  = portions.groupby("unit_name")["count"].sum().nlargest(5).to_dict()

        # ── Build prompt ──────────────────────────────────────────────────────
        p = """Du är en senior dataanalytiker och kostexpert för Höganäs kommuns kostverksamhet.
Du har djup kunskap om skolmåltider, offentlig upphandling, livsmedelssvinn och kommunal ekonomi.

INSTRUKTIONER:
- Svara alltid på svenska
- Ge detaljerade, analytiska svar med konkreta siffror från datan
- Lyft alltid fram 2-3 handlingsbara rekommendationer
- Jämför enheter mot varandra och mot genomsnittet
- Kvantifiera ekonomisk potential där möjligt (t.ex. "om X reduceras med 20% sparas Y kr")
- Strukturera längre svar med rubriker och punktlistor
- Om du inte har tillräcklig data för att svara säkert, säg det tydligt

KONTEXT — Höganäs kommuns kostverksamhet 2025:
"""
        if "fw_units" in ctx:
            p += f"""
## Matsvinn
- Totalt: {ctx['fw_kg']:,.0f} kg svinn över {ctx['fw_units']} enheter hela 2025
- Median svinnandel: {ctx['fw_median']:.1f}% per vecka
- Tallrikssvinn (median): {ctx.get('plate_median', 0):.1f}%
- Serveringssvinn (median): {ctx.get('serving_median', 0):.1f}%
- Enheter med HÖGST svinn (median %): {', '.join(f"{k}: {v:.1f}%" for k,v in ctx['fw_worst5'].items())}
- Enheter med LÄGST svinn (median %): {', '.join(f"{k}: {v:.1f}%" for k,v in ctx['fw_best5'].items())}
"""
        if "over_mean" in ctx:
            p += f"""- Snitt överbeställning: {ctx['over_mean']:.1f}% (beställt vs faktiskt serverat)
- Enheter med högst överbeställning: {', '.join(f"{k}: {v*100:.1f}%" for k,v in ctx['over_worst'].items())}
"""
        if "pu_total" in ctx:
            p += f"""
## Inköp & ekonomi
- Total inköpskostnad 2025: {ctx['pu_total']/1e6:.1f} Mkr från {ctx['pu_suppliers']} leverantörer
- Topp 5 leverantörer (SEK): {', '.join(f"{k}: {v/1e6:.1f}Mkr" for k,v in ctx['pu_top5_sup'].items())}
- Topp 5 varugrupper (SEK): {', '.join(f"{k}: {v/1e3:.0f}tkr" for k,v in ctx['pu_top5_grp'].items())}
- Ekologisk andel: {ctx.get('eco_pct', 0):.1f}% av inköpsvärdet
"""
        if "out_pct" in ctx:
            p += f"""
## Avtalstrohet
- {ctx['out_pct']:.1f}% av inköpen görs utanför upphandlade avtal
- Enheter med störst avvikelse: {', '.join(f"{k}: {v:.1f}%" for k,v in ctx['out_top5'].items())}
"""
        if "por_total" in ctx:
            p += f"""
## Portioner
- Totalt {ctx['por_total']:,} portioner serverade 2025
- Enheter med flest portioner: {', '.join(f"{k}: {int(v):,}" for k,v in ctx['por_top5'].items())}
"""
        return p

    SYSTEM_PROMPT = build_system_prompt()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Suggested questions
    if not st.session_state.messages:
        st.markdown("**Föreslagna frågor:**")
        suggestions = [
            "Vilka enheter har mest matsvinn och vad kan vi göra åt det?",
            "Hur ser avtalstroheten ut och var är riskerna störst?",
            "Vilka leverantörer kostar mest och finns det besparingsmöjligheter?",
            "Hur varierar matsvinnet under året och finns det säsongsmönster?",
        ]
        cols = st.columns(2)
        for i, s in enumerate(suggestions):
            with cols[i % 2]:
                if st.button(s, key=f"sug_{i}", use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": s})
                    st.rerun()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Skriv din fråga här…"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        with st.chat_message("assistant"):
            with st.spinner("Analyserar…"):
                try:
                    import openai
                    client = openai.OpenAI(api_key=OPENAI_KEY)
                    resp = client.chat.completions.create(
                        model="o4-mini",
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            *st.session_state.messages,
                        ],
                    )
                    answer = resp.choices[0].message.content
                except Exception as e:
                    answer = f"⚠️ Fel: {e}"
            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})

    if st.session_state.messages:
        if st.button("Rensa konversation", type="secondary"):
            st.session_state.messages = []
            st.rerun()
