"""Streamlit BI dashboard for Höganäs skolmåltidsanalys with OpenAI chatbot."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Höganäs Skolmåltider",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── OpenAI key ─────────────────────────────────────────────────────────────────
try:
    import openai as _openai_module
    OPENAI_KEY = (
        st.secrets.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ""
    )
    _openai_module.api_key = OPENAI_KEY
    OPENAI_AVAILABLE = bool(OPENAI_KEY)
except Exception:
    OPENAI_AVAILABLE = False

# ── Data loading ───────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "Data" / "processed"


@st.cache_data
def load_data():
    dfs = {}
    for name in ["purchases", "food_waste", "portions", "menu_nutrition", "preschool_billing"]:
        p = DATA_DIR / f"{name}.csv"
        if p.exists():
            dfs[name] = pd.read_csv(p, low_memory=False)
    return dfs


data = load_data()
purchases = data.get("purchases", pd.DataFrame())
food_waste = data.get("food_waste", pd.DataFrame())
portions = data.get("portions", pd.DataFrame())
menu_nutrition = data.get("menu_nutrition", pd.DataFrame())
preschool_billing = data.get("preschool_billing", pd.DataFrame())

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🍽️ Höganäs Skolmåltider")
    st.caption("Kostanalys 2025 — Höganäs kommun")
    st.divider()
    page = st.radio(
        "Navigera",
        ["📊 Översikt", "🗑️ Matsvinn", "🛒 Inköp", "🍽️ Portioner", "🤖 AI-assistent"],
        label_visibility="collapsed",
    )

# ── KPI helpers ─────────────────────────────────────────────────────────────────
def fmt_sek(v):
    if v >= 1_000_000:
        return f"{v/1_000_000:.1f} Mkr"
    return f"{v/1_000:.0f} tkr"


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Översikt
# ══════════════════════════════════════════════════════════════════════════════
if page == "📊 Översikt":
    st.title("📊 Översikt")
    st.caption("Nyckeltal för kostverksamheten i Höganäs kommun 2025")

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_sek = purchases["kronor"].sum() if not purchases.empty else 0
        st.metric("Totala inköp", fmt_sek(total_sek))
    with col2:
        total_portions = portions["count"].sum() if not portions.empty else 0
        st.metric("Totalt portioner", f"{int(total_portions):,}".replace(",", " "))
    with col3:
        if not food_waste.empty:
            avg_waste = food_waste["total_waste_pct"].mean() * 100
            st.metric("Snitt matsvinn", f"{avg_waste:.1f} %")
        else:
            st.metric("Snitt matsvinn", "–")
    with col4:
        units = food_waste["unit_name"].nunique() if not food_waste.empty else 0
        st.metric("Antal enheter (svinn)", f"{units}")

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Inköp per månad (SEK)")
        if not purchases.empty:
            monthly = purchases.groupby(["year", "month"])["kronor"].sum().reset_index()
            monthly["period"] = monthly["year"].astype(str) + "-" + monthly["month"].astype(str).str.zfill(2)
            monthly = monthly.sort_values("period")
            fig = px.bar(monthly, x="period", y="kronor", labels={"period": "", "kronor": "SEK"}, color_discrete_sequence=["#0068C9"])
            fig.update_layout(margin=dict(t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Ingen data")

    with col_b:
        st.subheader("Matsvinn per enhet (kg/portion)")
        if not food_waste.empty and "ordered_portions" in food_waste.columns:
            waste_unit = food_waste.groupby("unit_name").apply(
                lambda g: g["total_waste_kg"].sum() / g["ordered_portions"].sum()
                if g["ordered_portions"].sum() > 0 else 0
            ).reset_index(name="kg_per_portion").sort_values("kg_per_portion", ascending=False).head(15)
            fig2 = px.bar(waste_unit, x="kg_per_portion", y="unit_name", orientation="h",
                          labels={"kg_per_portion": "kg/portion", "unit_name": ""},
                          color="kg_per_portion", color_continuous_scale="Reds")
            fig2.update_layout(margin=dict(t=10, b=10), showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Matsvinn
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🗑️ Matsvinn":
    st.title("🗑️ Matsvinn")

    if food_waste.empty:
        st.warning("Ingen matsvinndata hittades.")
    else:
        units_list = sorted(food_waste["unit_name"].dropna().unique())
        selected_units = st.multiselect("Filtrera enheter", units_list, default=units_list[:6])
        df_fw = food_waste[food_waste["unit_name"].isin(selected_units)] if selected_units else food_waste

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Svinn % per vecka")
            fig = px.line(
                df_fw.sort_values("week"),
                x="week", y="total_waste_pct", color="unit_name",
                labels={"week": "Vecka", "total_waste_pct": "Svinn %", "unit_name": "Enhet"},
            )
            fig.update_layout(margin=dict(t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Svinntyper (medelvärde)")
            waste_cols = [c for c in ["kitchen_waste_pct", "serving_waste_pct", "plate_waste_pct"] if c in df_fw.columns]
            if waste_cols:
                means = df_fw[waste_cols].mean().rename({
                    "kitchen_waste_pct": "Kök",
                    "serving_waste_pct": "Servering",
                    "plate_waste_pct": "Tallrik",
                })
                fig2 = px.pie(values=means.values, names=means.index, hole=0.4,
                              color_discrete_sequence=px.colors.sequential.RdBu)
                fig2.update_layout(margin=dict(t=10, b=10))
                st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Säsongsmönster — medel svinn per vecka")
        seasonal = food_waste.groupby("week")["total_waste_pct"].mean().reset_index()
        fig3 = px.area(seasonal, x="week", y="total_waste_pct",
                       labels={"week": "Vecka", "total_waste_pct": "Svinn %"},
                       color_discrete_sequence=["#FF4B4B"])
        st.plotly_chart(fig3, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Inköp
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🛒 Inköp":
    st.title("🛒 Inköp")

    if purchases.empty:
        st.warning("Ingen inköpsdata hittades.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Topp 10 varugrupper (SEK)")
            top_groups = purchases.groupby("varugrupp")["kronor"].sum().nlargest(10).reset_index()
            fig = px.bar(top_groups, x="kronor", y="varugrupp", orientation="h",
                         labels={"kronor": "SEK", "varugrupp": ""},
                         color="kronor", color_continuous_scale="Blues")
            fig.update_layout(margin=dict(t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Topp 10 leverantörer (SEK)")
            top_suppliers = purchases.groupby("supplier")["kronor"].sum().nlargest(10).reset_index()
            fig2 = px.bar(top_suppliers, x="kronor", y="supplier", orientation="h",
                          labels={"kronor": "SEK", "supplier": ""},
                          color="kronor", color_continuous_scale="Greens")
            fig2.update_layout(margin=dict(t=10, b=10))
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Ekologiskt vs konventionellt (andel SEK)")
        if "ekologisk" in purchases.columns:
            eco = purchases.groupby("ekologisk")["kronor"].sum().reset_index()
            eco["ekologisk"] = eco["ekologisk"].map({"Ja": "Ekologisk", "Nej": "Konventionell"}).fillna("Okänd")
            fig3 = px.pie(eco, values="kronor", names="ekologisk", hole=0.4,
                          color_discrete_sequence=["#21C354", "#636EFA", "#EF553B"])
            st.plotly_chart(fig3, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Portioner
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🍽️ Portioner":
    st.title("🍽️ Portioner")

    if portions.empty:
        st.warning("Ingen portionsdata hittades.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Portioner per månad")
            monthly = portions.groupby(["year", "month"])["count"].sum().reset_index()
            monthly["period"] = monthly["year"].astype(str) + "-" + monthly["month"].astype(str).str.zfill(2)
            monthly = monthly.sort_values("period")
            fig = px.bar(monthly, x="period", y="count",
                         labels={"period": "", "count": "Portioner"},
                         color_discrete_sequence=["#0068C9"])
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Portioner per typ")
            if "portion_type" in portions.columns:
                by_type = portions.groupby("portion_type")["count"].sum().reset_index()
                fig2 = px.pie(by_type, values="count", names="portion_type", hole=0.4)
                st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Topp enheter (antal portioner)")
        top_units = portions.groupby("unit_name")["count"].sum().nlargest(15).reset_index()
        fig3 = px.bar(top_units, x="count", y="unit_name", orientation="h",
                      labels={"count": "Portioner", "unit_name": ""},
                      color="count", color_continuous_scale="Blues")
        st.plotly_chart(fig3, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: AI-assistent
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🤖 AI-assistent":
    st.title("🤖 AI-assistent")
    st.caption("Ställ frågor om skolmåltidsdata för Höganäs kommun. Drivs av OpenAI.")

    if not OPENAI_AVAILABLE:
        st.error(
            "OpenAI API-nyckel saknas. Lägg till `OPENAI_API_KEY` i Streamlit Secrets "
            "eller som miljövariabel `OPENAI_API_KEY`."
        )
        st.stop()

    # Build a compact data summary to inject as context
    @st.cache_data
    def build_context_summary() -> str:
        lines = [
            "Du är en dataanalytiker för Höganäs kommuns kostverksamhet.",
            "Nedan följer en sammanfattning av tillgänglig data för 2025:\n",
        ]
        if not food_waste.empty:
            avg_w = food_waste["total_waste_pct"].mean() * 100
            worst = food_waste.groupby("unit_name")["total_waste_pct"].mean().idxmax()
            lines.append(f"- Matsvinn: {len(food_waste)} rader, {food_waste['unit_name'].nunique()} enheter. Snittsvinn {avg_w:.1f}%. Högst svinn: {worst}.")
        if not purchases.empty:
            tot = purchases["kronor"].sum()
            top_s = purchases.groupby("supplier")["kronor"].sum().idxmax()
            lines.append(f"- Inköp: {len(purchases):,} rader, total {tot/1e6:.1f} Mkr. Störst leverantör: {top_s}.")
        if not portions.empty:
            tot_p = int(portions["count"].sum())
            lines.append(f"- Portioner: {len(portions):,} rader, totalt {tot_p:,} portioner.")
        if not menu_nutrition.empty:
            lines.append(f"- Menynäring: {len(menu_nutrition):,} rätter registrerade.")
        if not preschool_billing.empty:
            lines.append(f"- Förskoledebitering: {len(preschool_billing)} rader.")
        lines.append("\nSvara alltid på svenska om inte användaren skriver på annat språk.")
        return "\n".join(lines)

    SYSTEM_PROMPT = build_context_summary()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Render history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input
    if prompt := st.chat_input("Skriv din fråga här…"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Tänker…"):
                try:
                    import openai
                    client = openai.OpenAI(api_key=OPENAI_KEY)
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            *st.session_state.messages,
                        ],
                        temperature=0.3,
                    )
                    answer = response.choices[0].message.content
                except Exception as e:
                    answer = f"⚠️ Fel vid anrop till OpenAI: {e}"

            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})

    if st.session_state.messages:
        if st.button("Rensa konversation", type="secondary"):
            st.session_state.messages = []
            st.rerun()
