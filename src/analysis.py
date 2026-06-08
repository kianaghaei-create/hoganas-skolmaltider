from __future__ import annotations

from typing import Dict
import pandas as pd


def summarize_tables(tables: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, df in tables.items():
        rows.append({
            "table": name,
            "rows": len(df),
            "columns": len(df.columns),
            "files": df["source_file"].nunique() if not df.empty and "source_file" in df.columns else 0,
            "sheets": df["source_sheet"].nunique() if not df.empty and "source_sheet" in df.columns else 0,
        })
    return pd.DataFrame(rows).sort_values("table").reset_index(drop=True)


def _to_num(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce")


def first_insights(tables: Dict[str, pd.DataFrame]) -> dict:
    out = {}

    # ── FOOD WASTE ────────────────────────────────────────────────────────────
    fw = tables.get("food_waste", pd.DataFrame())
    if not fw.empty:

        # Svinn per serverad portion per enhet (minst 10 portioner för att undvika extremvärden)
        if {"total_waste_kg", "served_portions", "unit_name"}.issubset(fw.columns):
            tmp = fw.copy()
            tmp["served_portions"] = _to_num(tmp, "served_portions")
            tmp["total_waste_kg"]  = _to_num(tmp, "total_waste_kg")
            tmp = tmp[tmp["served_portions"] > 10]
            tmp["waste_per_portion"] = tmp["total_waste_kg"] / tmp["served_portions"]
            tmp = tmp[tmp["waste_per_portion"].notna() & ~tmp["waste_per_portion"].isin([float("inf")])]
            if not tmp.empty:
                unit_waste = (
                    tmp.groupby("unit_name", dropna=False)["waste_per_portion"]
                    .mean()
                    .sort_values(ascending=False)
                )
                out["waste_per_portion_by_unit"] = unit_waste

        # Serveringssvinn vs tallrikssvinn — var försvinner maten?
        if {"serving_waste_kg", "plate_waste_kg", "unit_name"}.issubset(fw.columns):
            tmp = fw.copy()
            tmp["serving_waste_kg"] = _to_num(tmp, "serving_waste_kg")
            tmp["plate_waste_kg"] = _to_num(tmp, "plate_waste_kg")
            agg = tmp.groupby("unit_name")[["serving_waste_kg", "plate_waste_kg"]].sum()
            agg = agg[(agg["serving_waste_kg"] > 0) | (agg["plate_waste_kg"] > 0)]
            out["waste_type_by_unit"] = agg

        # Säsongsmönster: genomsnittligt svinn per vecka
        if {"week", "total_waste_kg", "served_portions"}.issubset(fw.columns):
            tmp = fw.copy()
            tmp["week"] = pd.to_numeric(tmp["week"], errors="coerce")
            tmp["waste_per_portion"] = _to_num(tmp, "total_waste_kg") / _to_num(tmp, "served_portions")
            tmp = tmp[tmp["waste_per_portion"].notna() & ~tmp["waste_per_portion"].isin([float("inf")])]
            if not tmp.empty:
                weekly = tmp.groupby("week")["waste_per_portion"].mean().sort_index()
                out["waste_per_portion_by_week"] = weekly
                out["_fw_week"] = tmp  # keep for cross-table join

    # ── PURCHASES ─────────────────────────────────────────────────────────────
    pur = tables.get("purchases", pd.DataFrame())
    if not pur.empty:

        # Kostnad per kg per varugrupp
        if {"varugrupp", "kronor", "kilo"}.issubset(pur.columns):
            tmp = pur.copy()
            tmp["kronor"] = _to_num(tmp, "kronor")
            tmp["kilo"] = _to_num(tmp, "kilo")
            tmp = tmp[(tmp["kronor"] > 0) & (tmp["kilo"] > 0)]
            if not tmp.empty:
                cost_by_group = (
                    tmp.groupby("varugrupp")[["kronor", "kilo"]]
                    .sum()
                    .assign(kr_kg=lambda d: d["kronor"] / d["kilo"])
                    .sort_values("kronor", ascending=False)
                    .head(20)
                )
                out["top_cost_varugrupp"] = cost_by_group

        # Total inköpskostnad per enhet (droppa okopplade rader utan enhetsnnamn)
        if {"unit_name_std", "kronor"}.issubset(pur.columns):
            tmp = pur.copy()
            tmp["kronor"] = _to_num(tmp, "kronor")
            tmp = tmp[tmp["unit_name_std"].notna()]
            cost_by_unit = (
                tmp.groupby("unit_name_std")["kronor"]
                .sum()
                .sort_values(ascending=False)
            )
            out["total_cost_by_unit"] = cost_by_unit

        # Avtalstrohet: andel inköp utanför avtal per enhet
        if {"unit_name_std", "procent_utanfor_avtal", "kronor"}.issubset(pur.columns):
            tmp = pur.copy()
            tmp["kronor"] = _to_num(tmp, "kronor")
            tmp["utanfor"] = _to_num(tmp, "procent_utanfor_avtal")
            tmp = tmp[tmp["kronor"] > 0]
            if not tmp.empty:
                # Weighted average off-contract % by unit
                def wavg(g):
                    w = g["kronor"]
                    v = g["utanfor"]
                    mask = v.notna() & w.notna()
                    if mask.sum() == 0:
                        return float("nan")
                    return (v[mask] * w[mask]).sum() / w[mask].sum()

                contract = tmp.groupby("unit_name_std").apply(wavg).sort_values(ascending=False)
                out["off_contract_pct_by_unit"] = contract

        # Inköpskostnad per månad (säsong)
        if {"month", "kronor"}.issubset(pur.columns):
            tmp = pur.copy()
            tmp["kronor"] = _to_num(tmp, "kronor")
            monthly = tmp.groupby("month")["kronor"].sum().sort_index()
            out["cost_by_month"] = monthly

    # ── PORTIONS ─────────────────────────────────────────────────────────────
    por = tables.get("portions", pd.DataFrame())
    if not por.empty and "portion_type" in por.columns:

        # Serverade portioner per enhet (lunch_children + lunch_guests = total served)
        if {"unit_name", "count", "portion_type"}.issubset(por.columns):
            lunch = por[por["portion_type"].isin(["lunch_children", "lunch_guests"])].copy()
            lunch["count"] = _to_num(lunch, "count")
            served_by_unit = lunch.groupby("unit_name")["count"].sum().sort_values(ascending=False)
            out["served_portions_by_unit"] = served_by_unit

        # Portioner per månad (säsong)
        if {"month", "count", "portion_type"}.issubset(por.columns):
            lunch = por[por["portion_type"].isin(["lunch_children", "lunch_guests"])].copy()
            lunch["count"] = _to_num(lunch, "count")
            monthly_por = lunch.groupby("month")["count"].sum().sort_index()
            out["portions_by_month"] = monthly_por

    # ── MENU NUTRITION ────────────────────────────────────────────────────────
    mn = tables.get("menu_nutrition", pd.DataFrame())
    if not mn.empty:
        out["menu_dish_count"] = mn["dish_type"].value_counts()

    # ── CROSS-TABLE: meny × svinn ─────────────────────────────────────────────
    if "_fw_week" in out and not mn.empty:
        fw_w = out.pop("_fw_week")
        skola = mn[(mn["menu_type"] == "skola") & (mn["dish_type"] == "dagens_lunch")].copy()
        skola["week"] = pd.to_numeric(skola["week"], errors="coerce")
        skola_week = (
            skola.groupby("week")["dish_name"]
            .apply(lambda x: " | ".join(x.dropna().unique()))
            .reset_index()
        )
        fw_week = fw_w.groupby("week")["waste_per_portion"].mean().reset_index()
        merged = fw_week.merge(skola_week, on="week", how="inner").sort_values(
            "waste_per_portion", ascending=False
        )
        if not merged.empty:
            out["menu_waste_high"] = merged.head(10)   # veckor med högst svinn
            out["menu_waste_low"] = merged.tail(10)    # veckor med lägst svinn
    elif "_fw_week" in out:
        out.pop("_fw_week")

    # ── CROSS-TABLE: kostnad per serverad portion ─────────────────────────────
    if "total_cost_by_unit" in out and "served_portions_by_unit" in out:
        cost = out["total_cost_by_unit"]
        served = out["served_portions_by_unit"]
        combined = pd.DataFrame({"total_cost_sek": cost, "served_portions": served}).dropna()
        if not combined.empty:
            combined["cost_per_portion"] = combined["total_cost_sek"] / combined["served_portions"]
            out["cost_per_portion_by_unit"] = combined.sort_values("cost_per_portion", ascending=False)

    return out
