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
    for name in ["purchases", "portions", "preschool_billing"]:
        p = DATA_DIR / f"{name}.csv"
        if p.exists():
            out[name] = pd.read_csv(p, low_memory=False)
    # Daglig svinnfil (master) — unit_name + enhet, datum per rätt
    daily_path = DATA_DIR / "food_waste_daily_v2.csv"
    if daily_path.exists():
        out["food_waste_daily"] = pd.read_csv(daily_path, low_memory=False)
    # Näringsfil — menu_type='skola'|'ao', exakt datum + näringsvärden
    # OBS: förskolor saknar näringskoppling (ingen standardiserad meny)
    naring_path = DATA_DIR / "naring.parquet"
    if naring_path.exists():
        out["naring"] = pd.read_parquet(naring_path)
    # Kalender — säsong, lov, röda dagar, dagar till/sedan lov
    kal_path = DATA_DIR / "kalender.csv"
    if kal_path.exists():
        out["kalender"] = pd.read_csv(kal_path, low_memory=False)
    # Väderdata — SMHI Helsingborg A, dygnsmedeltemp + nederbörd
    wx_path = DATA_DIR / "weather_2025.csv"
    if wx_path.exists():
        out["weather"] = pd.read_csv(wx_path, low_memory=False)
    return out

data          = load_data()
purchases     = data.get("purchases",         pd.DataFrame())
food_waste_d  = data.get("food_waste_daily",  pd.DataFrame())  # daglig per rätt, unit_name normaliserat
portions      = data.get("portions",          pd.DataFrame())
naring        = data.get("naring",            pd.DataFrame())  # skola+ÄO, ej förskola
preschool     = data.get("preschool_billing", pd.DataFrame())
kalender      = data.get("kalender",          pd.DataFrame())  # säsong, lov, röda dagar
weather       = data.get("weather",           pd.DataFrame())  # SMHI temp + nbd

# Bakåtkompatibelt aggregat för sidor som fortfarande använder veckonivå
food_waste = pd.DataFrame()
if not food_waste_d.empty and "total_waste_pct" in food_waste_d.columns:
    food_waste = food_waste_d.copy()
elif not food_waste_d.empty:
    # Aggregera daglig → veckonivå för äldre vyer
    _agg = food_waste_d.copy()
    for col in ["kokssvinn_pct","serveringssvinn_pct","tallrikssvinn_pct","totalt_svinn_pct"]:
        if col not in _agg.columns: _agg[col] = None
    food_waste = (_agg.groupby(["unit_name","ar","vecka"], dropna=False)
        .agg(
            kitchen_waste_pct  =("kokssvinn_pct",       "mean"),
            serving_waste_pct  =("serveringssvinn_pct", "mean"),
            plate_waste_pct    =("tallrikssvinn_pct",   "mean"),
            total_waste_pct    =("totalt_svinn_pct",    "mean"),
            total_waste_kg     =("totalt_svinn_kg",     "sum"),
            ordered_portions   =("bestallda_portioner", "sum"),
            served_portions    =("serverade_portioner", "sum"),
        ).reset_index()
        .rename(columns={"unit_name": "unit_name", "ar": "year", "vecka": "week"})
    )
    food_waste["over_order_ratio"] = (
        (food_waste["ordered_portions"] - food_waste["served_portions"]) /
        food_waste["ordered_portions"].replace(0, float("nan"))
    )

# Derived: clean food-waste rows
# Behåller rader med NaN i total_waste_pct (förskolor rapporterar ej %) men filtrerar >100% som outliers
fw_clean = food_waste[
    food_waste["total_waste_pct"].isna() | (food_waste["total_waste_pct"] <= 1.0)
].copy() if not food_waste.empty else food_waste.copy()

# ── Källmetadata ───────────────────────────────────────────────────────────────
import json as _json
from datetime import datetime as _dt

def _analysis_ts():
    """Senast uppdaterad bland analysfilerna."""
    files = list(Path("Data/analysis").glob("*.json"))
    if not files: return "okänt"
    ts = max(f.stat().st_mtime for f in files)
    return _dt.fromtimestamp(ts).strftime("%Y-%m-%d")

def source_label(källa: str, rader: int = 0, extra: str = ""):
    """Renderar en diskret källetikett under ett diagram."""
    rad_txt = f" · {rader:,} rader".replace(",", " ") if rader else ""
    extra_txt = f" · {extra}" if extra else ""
    st.caption(f"📂 Källa: {källa}{rad_txt}{extra_txt}")

def raw_expander(df: pd.DataFrame, label: str = "Visa rådata", max_rows: int = 500):
    """Expanderbar rådata-tabell med nedladdningsknapp."""
    with st.expander(f"🔍 {label}"):
        st.dataframe(df.head(max_rows), use_container_width=True)
        st.download_button(
            "⬇️ Ladda ner CSV",
            df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
            file_name=f"{label.lower().replace(' ','_')}.csv",
            mime="text/csv",
            key=f"dl_{label}_{len(df)}",
        )

_ANALYSIS_DATE = _analysis_ts()
_SVINN_FILER   = "Matsvinnfiler 2025 (Excel per enhet)"
_INKOP_FILER   = "Inköpsfiler jan–dec 2025 (Excel per månad)"
_NARING_FILER  = "Näringsfiler 2025 (Skola + ÄO)"

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
            "🔗 Graf-analys",
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
    source_label(_SVINN_FILER, len(food_waste), f"analyserad {_ANALYSIS_DATE}")

    # ── Datadefinitioner ─────────────────────────────────────────────────────
    with st.expander("ℹ️ Datadefinitioner och avgränsningar — läs innan du tolkar graferna"):
        st.markdown("""
**Verksamhetstyper i datan**

| Typ | Antal enheter | Svinn-% | Svinn-kg | Komponentkolumner |
|-----|--------------|---------|----------|------------------|
| Skolor | ~9 | ✅ Finns | ✅ Finns | ✅ Verifierade |
| Äldreomsorg (ÄO) | ~1 | ✅ Finns | ✅ Finns | ✅ Verifierade |
| Förskolor | 11 | ❌ Saknas i rådata | ✅ Finns | ⚠️ Ej tillförlitliga |

**Varför syns inte förskolor i svinn-%-grafer?**
Förskolor registrerar inte svinn-procent i de digitala svinnbladen. Kolumnen `total_waste_pct` är tom (NaN) för dessa enheter. Svinn i kilogram (`totalt_svinn_kg`) finns och används i alla kg-baserade analyser.

**Varför syns förskolor inte i svinntyp-diagrammet (kök/servering/tallrik)?**
Komponentkolumnerna `kokssvinn_kg`, `serveringssvinn_kg` och `tallrikssvinn_kg` är opålitliga för förskolor — summan av dessa kolumner uppgår till ~8 211 kg för enheter vars `totalt_svinn_kg` bara är 183 kg. Det är ett faktafel i rådata, troligen en registreringsinkonsekvens. Dessa kolumner används **bara** i grafer där de är verifierade (avvikelse < 20 % mot totalt_svinn_kg).

**Vad menas med svinn per portion?**
`svinn_g_p = totalt_svinn_kg × 1 000 / serverade_portioner` — **serverade** portioner, inte beställda. Detta är ett mått på faktisk matförlust per person som ätit.

**Vad är kvadrantanalysen?**
Rätter matchas mot näringsvärden från en separat näringsfil. Näringsfilen täcker **enbart skolor och äldreomsorg** — inga förskolor. Rätter med protein < 5 g eller energi < 150 kcal är exkluderade som troliga felmatchningar (3 rätter borttagna, 116 kvar).

**Beställningsprecision — viktig begränsning**
70 % av värdena i `bestallda_portioner` är identiska med `serverade_portioner` i rådata — de är alltså en kopia, inte en verklig prognos. Beställningsprecisionsanalysen är fullt trovärdig för de 26 % av rader där det finns en genuin skillnad.
        """)
        n_fw = len(food_waste_d) if not food_waste_d.empty else 0
        n_fsk = food_waste_d["unit_name"].str.lower().str.contains("förskola|förskolan", na=False).sum() if not food_waste_d.empty else 0
        n_skola = n_fw - n_fsk
        st.markdown(f"**Rådata matsvinn:** {n_fw:,} rader totalt — varav ~{n_fsk:,} rader från förskolor, ~{n_skola:,} rader från skolor/ÄO.".replace(",", " "))

    units_list = sorted(fw_clean["unit_name"].dropna().unique()) if not fw_clean.empty else []
    sel = st.multiselect("Filtrera enheter", units_list, default=units_list)
    df_fw = fw_clean[fw_clean["unit_name"].isin(sel)] if sel else fw_clean

    all_kg = food_waste["total_waste_kg"].sum() if not food_waste.empty and "total_waste_kg" in food_waste.columns else 0
    c1, c2, c3 = st.columns(3)
    with c1:
        valid_pct = df_fw["total_waste_pct"].dropna()
        pct_val = f"{valid_pct.median()*100:.1f} %" if len(valid_pct) > 0 else "Saknas"
        n_with = len(valid_pct.index.unique()) if hasattr(valid_pct.index, 'unique') else len(valid_pct)
        kpi("Snitt svinn %", pct_val, f"Median — {len(sel)} enheter (förskolor saknar %-data)", "#EF4444")
    with c2:
        total_kg = df_fw["total_waste_kg"].sum() if "total_waste_kg" in df_fw.columns else 0
        sub = "Filtrerat urval" if total_kg < all_kg * 0.99 else "Alla enheter"
        kpi("Totalt svinn kg", f"{total_kg:,.0f} kg".replace(",", " "), sub, "#F97316")
    with c3:
        worst = df_fw.groupby("unit_name")["total_waste_pct"].median().idxmax() if not df_fw.empty else "–"
        kpi("Högst svinn", worst, "Enhet med högst median", "#8B5CF6")

    st.markdown("<br>", unsafe_allow_html=True)
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown('<div class="chart-box">', unsafe_allow_html=True)
        st.subheader("Svinn % per vecka — skolor och äldreomsorg")
        fig = px.line(df_fw.sort_values("week"), x="week", y="total_waste_pct",
                      color="unit_name",
                      labels={"week": "Vecka", "total_waste_pct": "Svinn %", "unit_name": "Enhet"})
        fig.update_layout(**PLOT_LAYOUT)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Förskolor visas inte här — de rapporterar inte svinn-% i rådata. "
                   "Förskolor ingår i totalt svinn-kg-analysen.")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_b:
        st.markdown('<div class="chart-box">', unsafe_allow_html=True)
        st.subheader("Svinntyper (kg-fördelning) — skolor och äldreomsorg")
        # Komponentkolumnerna (kokssvinn_kg etc.) är opålitliga för förskolor —
        # förskoledata har komponent-summor ~44× högre än totalt_svinn_kg.
        # Pie-chartet använder ENBART enheter där komponent_sum ≈ totalt_svinn_kg (diff <20%).
        kg_cols = {"kokssvinn_kg": "Kök", "serveringssvinn_kg": "Servering", "tallrikssvinn_kg": "Tallrik"}
        raw_fw = food_waste_d.copy()
        if not raw_fw.empty and sel:
            raw_fw = raw_fw[raw_fw["unit_name"].isin(sel)]
        # Filtrera till rader med trovärdig komponentdata
        if all(c in raw_fw.columns for c in kg_cols):
            raw_fw = raw_fw.copy()
            raw_fw["_komp_sum"] = raw_fw[list(kg_cols.keys())].sum(axis=1)
            raw_fw["_rel_diff"] = (
                (raw_fw["_komp_sum"] - raw_fw["totalt_svinn_kg"].fillna(0)).abs()
                / raw_fw["totalt_svinn_kg"].replace(0, float("nan"))
            )
            valid_fw = raw_fw[raw_fw["_rel_diff"] < 0.2]
            n_valid = len(valid_fw["unit_name"].unique()) if not valid_fw.empty else 0
            avail_kg = {v: valid_fw[k].sum() for k, v in kg_cols.items()
                        if k in valid_fw.columns and valid_fw[k].sum() > 0}
            if avail_kg:
                fig2 = px.pie(values=list(avail_kg.values()), names=list(avail_kg.keys()), hole=0.45,
                              color_discrete_sequence=["#EF4444", "#F97316", "#FBBF24"])
                fig2.update_layout(**PLOT_LAYOUT)
                st.plotly_chart(fig2, use_container_width=True)
                st.caption(f"Källa: food_waste_daily_v2.csv — kg-komponenter, {n_valid} enheter med verifierad komponentdata. "
                           f"Förskolor exkluderas (komponentkolumner ej tillförlitliga i rådata).")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="chart-box">', unsafe_allow_html=True)
    st.subheader("Säsongsmönster — svinn-% per vecka (median, skolor och ÄO)")
    seasonal = fw_clean.groupby("week")["total_waste_pct"].median().reset_index()
    fig3 = px.area(seasonal, x="week", y="total_waste_pct",
                   labels={"week": "Vecka", "total_waste_pct": "Svinn % (median)"},
                   color_discrete_sequence=["#EF4444"])
    fig3.update_layout(**PLOT_LAYOUT)
    st.plotly_chart(fig3, use_container_width=True)
    st.caption("Baserat på svinn-% — enbart skolor och äldreomsorg. Förskolor saknar svinn-%-data och ingår inte i denna graf.")
    st.markdown('</div>', unsafe_allow_html=True)

    raw_expander(df_fw[["unit_name","week","total_waste_pct","total_waste_kg",
                        "plate_waste_pct","serving_waste_pct","kitchen_waste_pct"]].rename(columns={
        "unit_name":"Enhet","week":"Vecka","total_waste_pct":"Svinn %","total_waste_kg":"Svinn kg",
        "plate_waste_pct":"Tallrik %","serving_waste_pct":"Servering %","kitchen_waste_pct":"Kök %"
    }), "Rådata svinnanalys")

    # ── Svinn vs Protein kvadrantdiagram ─────────────────────────────────────
    import json as _json
    _kv_path = Path("Data/analysis/svinn_naring_kvadrant.json")
    if _kv_path.exists():
        st.markdown('<div class="chart-box">', unsafe_allow_html=True)
        st.subheader("Svinn vs Protein per rätt — kvadrantanalys")
        st.caption("Baserat på matchning av svinndata mot näringsfil. Bubbelstorlek = antal observationer (liten ≈ 2, stor ≈ 10+). "
                   "Täcker enbart skolor och äldreomsorg — näringsfilen saknar förskoledata. "
                   "116 rätter efter filtrering (3 borttagna: protein < 5 g eller kcal < 150 som troliga felmatchningar).")

        kv_color_map = {
            "hog_svinn_lag_protein":  "#EF4444",
            "hog_svinn_hog_protein":  "#F97316",
            "lag_svinn_hog_protein":  "#22C55E",
            "lag_svinn_lag_protein":  "#94A3B8",
        }
        kv_label_map = {
            "hog_svinn_lag_protein":  "❌ Dubbel förlust",
            "hog_svinn_hog_protein":  "⚠️ Högt svinn, högt protein",
            "lag_svinn_hog_protein":  "✅ Optimal",
            "lag_svinn_lag_protein":  "⚠️ Lågt svinn, lågt protein",
        }

        kv_df = pd.DataFrame(_json.loads(_kv_path.read_text()))
        name_col = "komponent" if "komponent" in kv_df.columns else "ratt"
        kv_df["ratt_visning"] = kv_df[name_col]
        kv_df["Kategori"] = kv_df["kvadrant"].map(kv_label_map)

        med_svinn   = kv_df["svinn_g_p"].median()
        med_protein = kv_df["protein"].median()

        fig_kv = px.scatter(
            kv_df, x="protein", y="svinn_g_p",
            color="Kategori",
            size="obs", size_max=28,
            hover_name="ratt_visning",
            hover_data={"protein": ":.1f", "svinn_g_p": ":.1f", "kcal": ":.0f",
                        "obs": True, "Kategori": False, "ratt_visning": False},
            labels={"protein": "Protein per portion (g)", "svinn_g_p": "Svinn per portion (g)", "kcal": "Energi (kcal)", "obs": "Observationer"},
            color_discrete_map={v: kv_color_map[k] for k, v in kv_label_map.items()},
        )
        # Kvadrantlinjer
        fig_kv.add_hline(y=med_svinn,   line_dash="dot", line_color="#64748B", line_width=1,
                         annotation_text=f"Median svinn {med_svinn:.0f}g", annotation_position="top right")
        fig_kv.add_vline(x=med_protein, line_dash="dot", line_color="#64748B", line_width=1,
                         annotation_text=f"Median protein {med_protein:.0f}g", annotation_position="top right")
        # Kvadrantetiketter — korrigerade
        x_max = kv_df["protein"].max() * 1.05
        y_max = kv_df["svinn_g_p"].max() * 1.05
        for txt, x, y, color in [
            ("DUBBEL FÖRLUST",     med_protein * 0.25, y_max * 0.92, "#EF4444"),
            ("HÖGT SVINN,\nBRA RÄTT", x_max * 0.75,   y_max * 0.92, "#F97316"),
            ("OPTIMAL",            x_max * 0.75,       med_svinn * 0.3, "#22C55E"),
            ("LÅGT VÄRDE",         med_protein * 0.25, med_svinn * 0.3, "#94A3B8"),
        ]:
            fig_kv.add_annotation(text=f"<b>{txt}</b>", x=x, y=y, showarrow=False,
                                  font=dict(size=9, color=color), opacity=0.55)
        # Bubbelskala-förklaring
        fig_kv.add_annotation(
            text="<b>Bubbelstorlek</b><br>● liten = 2 obs<br>● stor = 10+ obs",
            x=x_max * 0.02, y=y_max * 0.98, showarrow=False, align="left",
            font=dict(size=9, color="#64748B"),
            bgcolor="rgba(255,255,255,0.7)", bordercolor="#E2E8F0", borderwidth=1,
        )
        fig_kv.update_layout(**PLOT_LAYOUT, height=500,
                              legend=dict(orientation="h", yanchor="bottom", y=-0.28))
        st.plotly_chart(fig_kv, use_container_width=True)

        col_kv1, col_kv2 = st.columns(2)
        with col_kv1:
            st.markdown("**❌ Dubbel förlust** — åtgärda i första hand:")
            for r in kv_df[kv_df["kvadrant"]=="hog_svinn_lag_protein"].sort_values("svinn_g_p", ascending=False).head(6).itertuples():
                st.markdown(f"- {r.ratt_visning} &nbsp; `{r.svinn_g_p}g svinn` `{r.protein}g prot`")
        with col_kv2:
            st.markdown("**✅ Optimal** — prioritera i menyn:")
            for r in kv_df[kv_df["kvadrant"]=="lag_svinn_hog_protein"].sort_values("protein", ascending=False).head(6).itertuples():
                st.markdown(f"- {r.ratt_visning} &nbsp; `{r.svinn_g_p}g svinn` `{r.protein}g prot`")

        st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# BESTÄLLNINGSPRECISION
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🎯 Beställningsprecision":
    st.title("Beställningsprecision")
    st.caption("Hur väl stämmer beställda portioner mot faktiskt serverade?")

    st.info(
        "⚠️ **Databegränsning:** Ungefär 70 % av värdena i 'Beställda portioner' är identiska "
        "med 'Serverade portioner' i rådata — dessa rader är alltså en kopia, inte en verklig "
        "förhandsbeställning. Analysen är fullt tillförlitlig för de ~26 % av rader där genuina "
        "skillnader finns. 2 rader innehåller troliga felregistreringar (serverade >3× beställda) "
        "som skapar synliga toppar i grafen.",
        icon=None,
    )

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
                week_sum = fw_p.groupby("week")[["ordered_portions", "served_portions"]].sum().reset_index()
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
    source_label(_INKOP_FILER, len(purchases), f"analyserad {_ANALYSIS_DATE}")

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

        _pu_cols = ["enhet","supplier","varugrupp","kronor","kilo","ekologisk","procent_utanfor_avtal","source_file"]
        raw_expander(purchases[[c for c in _pu_cols if c in purchases.columns]], "Rådata inköp")

# ══════════════════════════════════════════════════════════════════════════════
# AVTALSTROHET
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Avtalstrohet":
    st.title("Avtalstrohet")
    st.caption("Andel inköp utanför upphandlade avtal")
    source_label(_INKOP_FILER, len(purchases), f"analyserad {_ANALYSIS_DATE}")

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
    st.caption("Flaggor, avgränsningar och radräkning per analys")

    # ── Radräkningsöversikt ───────────────────────────────────────────────────
    st.markdown("### Datakällor — radräkning och täckning")
    n_fw_raw  = len(food_waste_d) if not food_waste_d.empty else 0
    n_fw_fsk  = food_waste_d["unit_name"].str.lower().str.contains("förskola|förskolan", na=False).sum() if not food_waste_d.empty else 0
    n_fw_nan  = food_waste_d["total_waste_pct"].isna().sum() if not food_waste_d.empty and "total_waste_pct" in food_waste_d.columns else 0
    n_fw_out  = (food_waste_d["total_waste_pct"] > 1.0).sum() if not food_waste_d.empty and "total_waste_pct" in food_waste_d.columns else 0
    n_pu      = len(purchases) if not purchases.empty else 0
    n_nar     = len(naring) if not naring.empty else 0

    col_r1, col_r2, col_r3 = st.columns(3)
    with col_r1:
        kpi("Matsvinnfil (rader)", f"{n_fw_raw:,}".replace(",", " "),
            f"Varav förskolor: ~{n_fw_fsk:,} rader".replace(",", " "), "#3B82F6")
    with col_r2:
        kpi("Inköpsfil (rader)", f"{n_pu:,}".replace(",", " "),
            "Alla enheter, helår 2025", "#8B5CF6")
    with col_r3:
        kpi("Näringsfil (rätter)", f"{n_nar:,}".replace(",", " "),
            "Skolor + ÄO — förskolor saknas", "#10B981")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Analysmatris ──────────────────────────────────────────────────────────
    st.markdown("### Verifieringsmatris — vilka enheter ingår i vilken analys")
    matris = [
        {"Analys": "Totalt svinn kg (KPI)", "Inkluderar": "Alla 21 enheter (skolor, ÄO, förskolor)", "Exkluderar": "–", "Mått": "totalt_svinn_kg", "Status": "✅ Fullt verifierad"},
        {"Analys": "Svinn % per vecka (linjegraf)", "Inkluderar": "Skolor + ÄO (~10 enheter)", "Exkluderar": "11 förskolor (saknar svinn-%-data)", "Mått": "total_waste_pct", "Status": "✅ Verifierad med avgränsning"},
        {"Analys": "Säsongsmönster (area-graf)", "Inkluderar": "Skolor + ÄO (~10 enheter)", "Exkluderar": "11 förskolor (NaN hoppas över i median)", "Mått": "total_waste_pct", "Status": "✅ Verifierad med avgränsning"},
        {"Analys": "Svinntyper pie-chart", "Inkluderar": "Skolor + ÄO (~10 enheter, komp_diff<20%)", "Exkluderar": "11 förskolor (komponentdata ~44× för hög)", "Mått": "kokssvinn_kg m.fl.", "Status": "✅ Verifierad med avgränsning"},
        {"Analys": "Svinn vs Näring kvadrant", "Inkluderar": "Skolor + ÄO (näringsfil täcker ej förskola)", "Exkluderar": "Förskolor + 3 felmatchningar", "Mått": "svinn_g_p, protein_g, kcal", "Status": "✅ Verifierad med avgränsning"},
        {"Analys": "Beställningsprecision", "Inkluderar": "Alla 21 enheter", "Exkluderar": "–", "Mått": "ordered_portions, served_portions", "Status": "⚠️ 70% kopia — indikativ"},
        {"Analys": "Inköp & ekonomi", "Inkluderar": "Alla enheter (inköpsdata)", "Exkluderar": "–", "Mått": "kronor, ekologisk", "Status": "✅ Fullt verifierad"},
        {"Analys": "Avtalstrohet", "Inkluderar": "Alla enheter (inköpsdata)", "Exkluderar": "–", "Mått": "procent_utanfor_avtal, kronor", "Status": "✅ Fullt verifierad"},
    ]
    st.dataframe(pd.DataFrame(matris), use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Flaggor och avvikelser")

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
        # NaN i total_waste_pct — förskolor rapporterar ej svinn-procent
        nan_pct = food_waste["total_waste_pct"].isna().sum()
        if nan_pct:
            nan_units = food_waste[food_waste["total_waste_pct"].isna()]["unit_name"].nunique()
            issues.append({"Typ": "Saknade värden", "Tabell": "Matsvinn", "Beskrivning": f"{nan_pct} rader ({nan_units} enheter) saknar svinn-procent — förskolor registrerar ej % i svinnbladet. Svinn-kg finns för dessa enheter.", "Allvarlighet": "Varning"})
        # Felregistreringar: serverade >> beställda (>200%)
        if "served_portions" in food_waste.columns and "ordered_portions" in food_waste.columns:
            suspicious = food_waste[
                food_waste["ordered_portions"] > 0,
            ].copy() if False else food_waste[food_waste["ordered_portions"] > 0].copy()
            ratio = suspicious["served_portions"] / suspicious["ordered_portions"]
            bad_rows = (ratio > 3).sum()
            if bad_rows:
                issues.append({"Typ": "Felregistrering", "Tabell": "Matsvinn", "Beskrivning": f"{bad_rows} veckorader där serverade >3× beställda — troliga datainmatningsfel (t.ex. extra nolla)", "Allvarlighet": "Kritisk"})

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
        kpi("Totalt kontrollerade tabeller", "5", "purchases, food_waste, portions, naring, preschool", "#3B82F6")

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

    # ── Stakeholder-summary ───────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("📋 För beslutsfattare — vad kan dashboarden visa och inte visa?"):
        st.markdown("""
### Vad kan dashboarden visa med säkerhet?

- **Totalt matsvinn i kilogram** för alla 21 enheter i Höganäs kommuns kostverksamhet 2025. Summan är 24 420 kg och har verifierats direkt mot rådatan.
- **Inköpskostnad** på 16,9 Mkr fördelat på tre leverantörer, varugrupper och enheter — fullt spårbar mot inköpsfiler.
- **Avtalstrohet** — andelen inköp utanför upphandlade avtal är 13,0 % totalt. Kullagymnasiet, Vikhaga och Nyhamnsgården sticker ut.
- **Ekologisk andel** — 31,5 % av inköpsvärdet är ekologiskt certifierat.
- **Svinnmönster per rätt** för skolor och äldreomsorg — vilka rätter genererar mest svinn per serverad portion.
- **Svinntypsfördelning** (kök/servering/tallrik) för skolor och äldreomsorg — tallrikssvinn är störst (54 %).

### Vad kan dashboarden inte visa med säkerhet — och varför?

- **Svinn-procent för förskolor** saknas i rådata. Förskolor registrerar inte svinn i procent i svinnbladen. Det är en brist i datainsamlingen, inte i dashboarden. Svinn i kilogram för förskolor finns och ingår i totalsummorna.
- **Komponentsvinn (kök/servering/tallrik) för förskolor** — dessa kolumner innehåller felaktiga värden för förskolor i rådata (summan är 44 gånger för hög). Dashboarden exkluderar dem i komponentanalysen.
- **Beställningsprecision** kan inte fullt ut verifieras — 70 % av beställda portioner är identiska med serverade portioner, vilket tyder på att en kopia används istället för verkliga förhandsbeställningar. Analysen visar ändå mönster i de 26 % av fallen med genuina skillnader.
- **Koppling leverantör → svinn** — det finns ingen länk i data mellan vilken leverantörs råvaror som användes i en specifik rätt. Det går alltså inte att säga att "leverantör X orsakar mer svinn".
- **Näring för förskolor** — näringsfilen täcker enbart skolmenyer och äldreomsorgsmenyer. Förskolemat ingår inte i kvadrantanalysen.

### Hur ska man tolka siffrorna?

- **Verifierat** (märkt ✅): siffran stämmer mot rådatan inom 1 % och kan försvaras för extern granskning.
- **Verifierat med avgränsning** (märkt ✅ med not): siffran är korrekt för den grupp som ingår — men gruppen är inte alla enheter. Läs alltid grafrubriken och captionen för att se vilka enheter som ingår.
- **Indikativt** (märkt ⚠️): data finns men har känd kvalitetsbegränsning. Använd som vägledning, inte som faktaunderlag för beslut utan ytterligare kontroll.
- **Scenariobaserat** (märkt i AI-assistenten): ekonomisk potential beräknad med ett antagande om råvarukostnad — alltid specificerat och inte hämtat från faktiska inköpspriser.

### Rekommendationer för dataförbättring

1. Be förskoleköken börja registrera svinn-procent i svinnbladen — samma format som skolorna.
2. Granska beställningsrutinen för portioner — varför är 70 % av beställda portioner identiska med serverade?
3. Korrigera de 2 kända felregistreringarna (Kullagymnasiet v14, Havets förskola v16) i källsystemet.
        """)

    # ── Exkluderingsöversikt ─────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Exkluderingsöversikt — rader borttagna ur respektive analys")
    if not food_waste_d.empty:
        kg_c = ["kokssvinn_kg", "serveringssvinn_kg", "tallrikssvinn_kg"]
        if all(c in food_waste_d.columns for c in kg_c):
            tmp = food_waste_d.copy()
            tmp["_ks"] = tmp[kg_c].sum(axis=1)
            tmp["_rd"] = (tmp["_ks"] - tmp["totalt_svinn_kg"].fillna(0)).abs() / tmp["totalt_svinn_kg"].replace(0, float("nan"))
            n_excl_pie = (tmp["_rd"] >= 0.2).sum()
            n_incl_pie = (tmp["_rd"] < 0.2).sum()
        else:
            n_excl_pie = n_incl_pie = 0
        n_nan_pct = food_waste_d["total_waste_pct"].isna().sum() if "total_waste_pct" in food_waste_d.columns else 0
        n_tot = len(food_waste_d)
        excl_data = [
            {"Analys": "Svinn % per vecka", "Inkluderade rader": n_tot - n_nan_pct, "Exkluderade rader": n_nan_pct, "Orsak": "NaN i total_waste_pct (förskolor)"},
            {"Analys": "Säsongsmönster svinn %", "Inkluderade rader": n_tot - n_nan_pct, "Exkluderade rader": n_nan_pct, "Orsak": "NaN i total_waste_pct (förskolor)"},
            {"Analys": "Svinntyper pie-chart", "Inkluderade rader": int(n_incl_pie), "Exkluderade rader": int(n_excl_pie), "Orsak": "Komponent-diff ≥ 20% mot totalt_svinn_kg"},
            {"Analys": "Totalt svinn kg (KPI)", "Inkluderade rader": n_tot, "Exkluderade rader": 0, "Orsak": "Inga exkluderingar — alla enheter ingår"},
        ]
        st.dataframe(pd.DataFrame(excl_data), use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# AI-ASSISTENT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🤖 AI-assistent":
    st.title("AI-assistent")
    st.caption("Ställ frågor om Höganäs kommuns kostverksamhet.")

    if not OPENAI_AVAILABLE:
        st.error("OpenAI API-nyckel saknas. Lägg till `OPENAI_API_KEY` i Streamlit Secrets.")
        st.stop()

    # ── Ladda förberäknade grafanalyser (verifierade Cypher-resultat) ─────────
    @st.cache_data
    def load_graph_analysis() -> dict:
        import json
        from pathlib import Path
        analysis = {}
        base = Path("Data/analysis")
        files = {
            "enheter_svinn":        "enheter_svinn_ranking.json",
            "leverantorer":         "leverantorer_kostnad.json",
            "avtalstrohet":         "avtalstrohet_per_enhet.json",
            "ekologisk":            "ekologisk_andel.json",
            "varugrupper":          "varugrupper_kostnad.json",
            "ratter_svinn":         "ratter_svinn_per_portion.json",
            "ratter_lag_svinn":     "ratter_lag_svinn.json",
            "ratter_tallrik":       "ratter_tallrikssvinn.json",
            "svinn_veckodag":       "svinn_per_veckodag.json",
            "svinntyper":           "svinntyper_per_enhet.json",
            "ratter_per_enhet":     "ratter_per_enhet_topp.json",
            "overbestallning":      "overbestallning_per_ratt.json",
            "svinn_naring":         "svinn_naring_per_ratt.json",
            "svinn_naring_kvadrant":"svinn_naring_kvadrant.json",
            "konsumerad_naring":    "konsumerad_naring.json",
        }
        for key, fname in files.items():
            p = base / fname
            if p.exists():
                try:
                    analysis[key] = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    analysis[key] = []
        return analysis

    graph_analysis = load_graph_analysis()

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
- Du får ENDAST svara på frågor som rör Höganäs kommuns kostverksamhet, skolmåltider, matsvinn, inköp, leverantörer, portioner eller avtalstrohet baserat på den data som finns nedan
- Om användaren ställer en fråga som inte är relaterad till denna data, svara artigt: "Jag är specialiserad på Höganäs kostverksamhet och kan tyvärr inte hjälpa med det. Ställ gärna en fråga om matsvinn, inköp eller portionsdata."
- Om användaren frågar vad en rätt "innehåller", "är gjord på" eller efterfrågar ingredienser/recept: svara att systemet inte har tillgång till receptdatabasen eller ingredienslistor — vi har rättnamn, näringsvärden och svinndata men inte vilka råvaror som ingår. Hänvisa till kostchefen eller produktionssystemet för receptdetaljer.
- Ge detaljerade, analytiska svar med konkreta siffror från datan
- Lyft alltid fram 2-3 handlingsbara rekommendationer
- Jämför enheter mot varandra och mot genomsnittet
- Kvantifiera ekonomisk potential där möjligt — märk alltid beräkningar som scenariobaserade med ett antagande om råvarukostnad (t.ex. "vid antagandet 50 kr/kg, vilket inte är verifierat mot faktiska inköpspriser")
- Strukturera längre svar med rubriker och punktlistor
- Om du inte har tillräcklig data för att svara säkert, säg det tydligt
- Orsaker till svinnmönster (t.ex. serveringsmetod, temperatur) finns INTE i datan — formulera alltid som "troliga orsaker baserat på mönster" eller "möjlig förklaring", aldrig som konstaterade fakta
- HÅRT VETO: "Fiskgratäng serveras med potatismos" med protein=2,8g är ett känt matchningsfel och är BORTTAGEN ur kvadrantanalysen. Om du ser den i listan har ett fel uppstått. Inkludera den ALDRIG i dubbel-förlust-listan. Om fiskgratäng nämns i dubbel-förlust-kontexten, svara: "Fiskgratäng exkluderas från dubbel-förlust-analysen — protein 2,8g är ett känt matchningsfel och raden är borttagen ur datan."
- Övriga fiskgratäng-varianter (med curry, gräslök, dill, saffran osv) är separata rätter med korrekta näringsvärden (27–33g protein) och kan rekommenderas om de ligger i lag_svinn_hog_protein-kvadranten — ange alltid det fullständiga rättnamnet
- Rätter med lågt svinn per portion kan vara outliers med få observationer — nämn alltid antal observationer vid rekommendationer

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

        # ── Kalender & väder ─────────────────────────────────────────────────
        if not kalender.empty and not food_waste_d.empty:
            import numpy as np
            fw_kal = food_waste_d.copy()
            fw_kal['datum'] = fw_kal['datum'].astype(str).str[:10]
            fw_kal = fw_kal.merge(kalender[['datum','sasong','lov','rod_dag','skoldag','dagar_till_lov']], on='datum', how='left')
            fw_kal['svinn_g_p'] = fw_kal['totalt_svinn_kg'] * 1000 / fw_kal['serverade_portioner'].replace(0, np.nan)
            sas = fw_kal.groupby('sasong')['svinn_g_p'].mean().round(1).to_dict()
            lov_svinn = fw_kal.groupby('lov')['svinn_g_p'].mean().round(1).dropna().to_dict()
            p += "\n## Kalender — svinn per säsong och lov (beräknat från datum)\n"
            p += f"Svinn g/portion per säsong: {', '.join(f'{k}: {v}g' for k,v in sorted(sas.items(), key=lambda x: -x[1]))}\n"
            if lov_svinn:
                p += f"Svinn g/portion per lov: {', '.join(f'{k}: {v}g' for k,v in sorted(lov_svinn.items(), key=lambda x: -x[1]))}\n"
            p += "OBS: lovperioder har färre enheter öppna vilket påverkar genomsnittet.\n"

        if not weather.empty:
            p += "\n## Väderdata — SMHI Helsingborg A 2025\n"
            p += f"- Temperaturkorrelation mot svinn: r≈−0.29 (kalla dagar ger mer svinn)\n"
            p += f"- Nederbördskorrelation: r≈+0.03 (ingen effekt)\n"
            p += f"- Temperaturspann 2025: {weather['temp_c'].min():.1f}°C till {weather['temp_c'].max():.1f}°C\n"
            p += "- Kalla dagar (<3°C) ger ca 5g mer svinn/portion än varma dagar (>16°C)\n"

        # ── Grafanalys (verifierade Cypher-resultat från Neo4j) ───────────────
        ga = graph_analysis
        if ga.get("enheter_svinn"):
            rows = [r for r in ga["enheter_svinn"] if r.get("snitt_svinn_pct")]
            p += "\n## Svinnranking per enhet (graf-analys, verifierad)\n"
            p += "OBS: gram_per_portion använder SERVERADE portioner som nämnare (inte beställda). Ange alltid 'per serverad portion' i svar.\n"
            for r in rows[:10]:
                p += f"- {r['enhet']}: {r['snitt_svinn_pct']}% snitt, {r['gram_per_portion']}g per serverad portion, {r['total_kg']} kg totalt ({r['dagar']} dagar)\n"

        if ga.get("leverantorer"):
            rows = [r for r in ga["leverantorer"] if r.get("leverantor") != "Okänd" and r.get("total_mkr")]
            p += "\n## Leverantörer — inköpskostnad (graf-analys, verifierad)\n"
            p += ("VIKTIG BEGRÄNSNING: det finns INGEN koppling mellan leverantör och svinn i datan. "
                  "Datan saknar råvara→rätt-länken. Alla enheter köper från flera leverantörer samtidigt, "
                  "så det är omöjligt att fördela svinn per leverantör. "
                  "Om frågan ställs: svara att det inte går att besvara med befintlig data, "
                  "och förklara varför (inköp och svinn är båda på enhetsnivå men inte länkade via rätt).\n")
            for r in rows:
                p += f"- {r['leverantor']}: {r['total_mkr']} Mkr, {r['total_ton']} ton, {r['enheter']} enheter\n"

        if ga.get("avtalstrohet"):
            rows = [r for r in ga["avtalstrohet"] if r.get("pct_utanfor", 0) > 0]
            p += "\n## Avtalstrohet per enhet — andel av inköpsvärde utanför avtal (graf-analys, verifierad)\n"
            p += "OBS: pct_utanfor = tkr_utanfor / total_tkr × 100, dvs andel av faktisk inköpskostnad. Använd aldrig snitt_utanfor_pct — det fältet är borttaget pga beräkningsfel.\n"
            for r in rows[:8]:
                p += f"- {r['enhet']}: {r['pct_utanfor']}% utanför avtal ({r['tkr_utanfor']} tkr av {r['total_tkr']} tkr totalt)\n"

        if ga.get("ekologisk"):
            rows = [r for r in ga["ekologisk"] if r.get("eko_andel_pct", 0) > 0]
            p += "\n## Ekologisk andel per enhet (graf-analys, verifierad)\n"
            for r in rows[:8]:
                p += f"- {r['enhet']}: {r['eko_andel_pct']}% ekologiskt av {r['total_tkr']} tkr\n"

        if ga.get("varugrupper"):
            p += "\n## Varugrupper — top 10 kostnad (graf-analys, verifierad)\n"
            for r in ga["varugrupper"][:10]:
                p += f"- {r['varugrupp']}: {r['total_tkr']} tkr ({r['total_kg']} kg)\n"

        if ga.get("ratter_svinn"):
            p += "\n## Rätter med högst svinn per portion (dag-nivå, verifierad)\n"
            for r in ga["ratter_svinn"][:10]:
                p += f"- {r['ratt']}: {r['gram_per_portion']}g/portion ({r['obs']} observationer, {r['totalt_kg']}kg totalt)\n"

        if ga.get("ratter_lag_svinn"):
            p += "\n## Rätter med lägst svinn per portion — bäst praxis (verifierad)\n"
            for r in ga["ratter_lag_svinn"][:10]:
                p += f"- {r['ratt']}: {r['gram_per_portion']}g/portion ({r['obs']} observationer)\n"

        if ga.get("ratter_tallrik"):
            p += "\n## Rätter med högst tallrikssvinn per portion (verifierad)\n"
            for r in ga["ratter_tallrik"][:8]:
                p += f"- {r['ratt']}: {r['tallrik_gram_per_portion']}g tallrik/portion ({r['obs']} observationer, {r['totalt_tallrik_kg']}kg totalt)\n"

        if ga.get("svinn_veckodag"):
            p += "\n## Svinn per veckodag (genomsnitt alla enheter, verifierad)\n"
            for r in ga["svinn_veckodag"]:
                p += f"- {r['dag']}: {r['gram_per_portion']}g/portion (snitt {r['snitt_kg']}kg, {r['obs']} dagar)\n"

        if ga.get("svinntyper"):
            p += "\n## Svinntyper per enhet — tallrik/servering/kök (verifierad)\n"
            p += "ANALYTISK NYCKEL: detta är det viktigaste fyndet vid enhetsjämförelser. Hög tallrikssvinn → elever/gäster äter inte upp (åtgärd: mindre förstaportion, fri påfyllning). Hög serveringssvinn → personal lägger upp för mycket (åtgärd: utbilda i portionering). Hög kökssvinn → tillagningsfel eller fel kvantitet. Lyft alltid fram svinntyp-skillnader när du jämför enheter.\n"
            for r in ga["svinntyper"][:8]:
                p += (f"- {r['enhet']}: tallrik {r.get('tallrik_g_p','?')}g, "
                      f"servering {r.get('servering_g_p','?')}g, "
                      f"kök {r.get('koks_g_p','?')}g per serverad portion\n")

        if ga.get("overbestallning"):
            p += "\n## Rätter med störst överbeställning (verifierad)\n"
            for r in ga["overbestallning"][:8]:
                p += f"- {r['ratt']}: {r['snitt_over_pct']}% i snitt, {int(r['total_over_portioner'])} portioner totalt\n"

        if ga.get("svinn_naring_kvadrant"):
            dubbel = [r for r in ga["svinn_naring_kvadrant"] if r.get("kvadrant") == "hog_svinn_lag_protein"]
            optimal = [r for r in ga["svinn_naring_kvadrant"] if r.get("kvadrant") == "lag_svinn_hog_protein"]
            p += "\n## Svinn + näring — kvadrantanalys (graf-analys, verifierad)\n"
            p += f"Baserat på {len(ga['svinn_naring_kvadrant'])} rätter matchade mot näringsvärden (orimliga näringsvärden har filtrerats bort — protein<5g eller kcal<150 exkluderas som troliga felmatchningar).\n"
            p += "### Dubbel förlust — högt svinn OCH lågt protein (prioritera att åtgärda):\n"
            for r in dubbel[:8]:
                namn = r.get('komponent') or r.get('ratt', '?')
                p += f"- {namn}: {r['svinn_g_p']}g/portion svinn, {r['protein']}g protein, {r['kcal']} kcal\n"
            p += "### Optimala rätter — lågt svinn OCH högt protein (prioritera i menyn):\n"
            for r in optimal[:8]:
                namn = r.get('komponent') or r.get('ratt', '?')
                p += f"- {namn}: {r['svinn_g_p']}g/portion svinn, {r['protein']}g protein, {r['kcal']} kcal\n"

        if ga.get("konsumerad_naring"):
            p += "\n## Konsumerad näring per rätt (serverat × (1−svinn), verifierad)\n"
            p += ("VIKTIGT: svinn_pct här är procentuellt svinn (av vikt), INTE gram per portion. "
                  "Blanda ALDRIG svinn_pct från den här listan med svinn_g_p från kvadrantanalysen — de är olika mått. "
                  "Vid rekommendationer: använd svinn_g_p (gram/portion) som primärt jämförelsemått. "
                  "svinn_pct från den här listan är kompletterande information, ange den alltid med enheten '%'.\n")
            p += "Visar hur mycket näring som faktiskt äts upp efter svinn:\n"
            for r in ga["konsumerad_naring"][:8]:
                namn = r.get('komponent') or r.get('ratt', '?')
                p += (f"- {namn}: {r.get('protein_konsumerad_g','?')}g protein konsumerat "
                      f"(serverat: {r.get('protein_serverad_g','?')}g, svinn: {r.get('svinn_pct','?')}% av serverad vikt)\n")

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

# ══════════════════════════════════════════════════════════════════════════════
# GRAF-ANALYS — OpenAI + Neo4j-lins
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔗 Graf-analys":
    st.title("Graf-analys")
    st.caption("Ställ frågor som kräver relationer — rätt → svinn → näring → leverantör")
    source_label("Neo4j-graf (förberäknade Cypher-analyser)", extra=f"uppdaterad {_ANALYSIS_DATE}")

    if not OPENAI_AVAILABLE:
        st.warning("OpenAI API-nyckel saknas.")
        st.stop()

    # ── Ladda bara graf-specifika analysfiler ─────────────────────────────────
    @st.cache_data
    def load_graph_context() -> str:
        import json
        base = Path("Data/analysis")
        files = {
            "Svinnranking per enhet":           "enheter_svinn_ranking.json",
            "Rätter med högst svinn/portion":   "ratter_svinn_per_portion.json",
            "Rätter med lägst svinn/portion":   "ratter_lag_svinn.json",
            "Tallrikssvinn per rätt":            "ratter_tallrikssvinn.json",
            "Svinn per veckodag":               "svinn_per_veckodag.json",
            "Svinntyper per enhet":             "svinntyper_per_enhet.json",
            "Topp-rätter per enhet":            "ratter_per_enhet_topp.json",
            "Överbeställning per rätt":         "overbestallning_per_ratt.json",
            "Leverantörskostnader":             "leverantorer_kostnad.json",
            "Avtalstrohet per enhet":           "avtalstrohet_per_enhet.json",
            "Ekologisk andel per enhet":        "ekologisk_andel.json",
            "Varugrupper kostnad":              "varugrupper_kostnad.json",
            "Svinn × näring kvadrant":          "svinn_naring_kvadrant.json",
            "Konsumerad näring per rätt":       "konsumerad_naring.json",
        }
        ctx = "Du har tillgång till följande förberäknade grafanalyser från Neo4j:\n\n"
        for label, fname in files.items():
            p = base / fname
            if not p.exists():
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            ctx += f"### {label} ({len(data)} rader)\n"
            ctx += json.dumps(data[:20], ensure_ascii=False, indent=2)
            ctx += "\n\n"
        return ctx

    GRAPH_SYSTEM = """Du är en grafanalytiker för Höganäs kommuns skolmåltider.
Du svarar ENDAST baserat på Neo4j-grafanalyserna nedan — inga gissningar.
Svara på svenska. Var konkret och hänvisa alltid till vilken analys du använder.
Lyft gärna fram relationer: hur rätten hänger ihop med svinn, näring och leverantör.
Om data saknas för att besvara frågan, säg det explicit.

TILLGÄNGLIGA GRAFANALYSER:
""" + load_graph_context()

    # ── Föreslagna frågor ─────────────────────────────────────────────────────
    if "graph_messages" not in st.session_state:
        st.session_state.graph_messages = []

    if not st.session_state.graph_messages:
        st.markdown("**Föreslagna frågor:**")
        graph_suggestions = [
            "Vilka rätter är dubbel förlust — högt svinn och lågt protein?",
            "Vilken leverantör är kopplad till mest svinn via sina rätter?",
            "Jämför Kullagymnasiet och Lerbergsskolan — vad skiljer dem?",
            "Vilka rätter bör vi prioritera i menyn baserat på näring och svinn?",
            "Var är överbeställningen störst och vilka rätter driver den?",
        ]
        cols = st.columns(2)
        for i, s in enumerate(graph_suggestions):
            if cols[i % 2].button(s, key=f"gs_{i}", use_container_width=True):
                st.session_state.graph_messages.append({"role": "user", "content": s})
                st.rerun()

    # ── Chattgränssnitt ───────────────────────────────────────────────────────
    for msg in st.session_state.graph_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Fråga om relationer i grafen…"):
        st.session_state.graph_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

    if st.session_state.graph_messages and st.session_state.graph_messages[-1]["role"] == "user":
        with st.chat_message("assistant"):
            with st.spinner("Traverserar grafen…"):
                try:
                    import openai
                    client = openai.OpenAI(api_key=OPENAI_KEY)
                    resp = client.chat.completions.create(
                        model="o4-mini",
                        messages=[
                            {"role": "system", "content": GRAPH_SYSTEM},
                            *st.session_state.graph_messages,
                        ],
                    )
                    answer = resp.choices[0].message.content
                except Exception as e:
                    answer = f"⚠️ Fel: {e}"
            st.markdown(answer)
            st.session_state.graph_messages.append({"role": "assistant", "content": answer})

    if st.session_state.graph_messages:
        if st.button("Rensa konversation", key="clear_graph", type="secondary"):
            st.session_state.graph_messages = []
            st.rerun()
