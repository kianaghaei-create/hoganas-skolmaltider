from __future__ import annotations

from pathlib import Path
import pandas as pd

MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Maj", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Dec",
}


def _fmt(val, decimals=1) -> str:
    try:
        return f"{float(val):,.{decimals}f}"
    except Exception:
        return str(val)


def render_analysis_report(summary: pd.DataFrame, insights: dict, unreadable: list[dict]) -> str:
    lines = [
        "# Skolmåltidsanalys — Rapport",
        "",
        "> Analyserar var resurser faktiskt försvinner: planering, menyacceptans, inköpskostnad eller konsumtion.",
        "",
    ]

    # ── Datamängder ──────────────────────────────────────────────────────────
    lines += [
        "## Datamängder",
        "",
        "| Tabell | Rader | Kolumner | Filer | Blad |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, r in summary.iterrows():
        lines.append(f"| {r['table']} | {r['rows']:,} | {r['columns']} | {r['files']} | {r['sheets']} |")

    # ── Svinn per enhet ───────────────────────────────────────────────────────
    wpu = insights.get("waste_per_portion_by_unit")
    if isinstance(wpu, pd.Series) and not wpu.empty:
        lines += [
            "",
            "## Svinn per serverad portion — per enhet",
            "",
            "| Enhet | kg svinn/portion |",
            "|---|---:|",
        ]
        for unit, val in wpu.items():
            lines.append(f"| {unit} | {_fmt(val, 4)} |")

    # ── Serveringssvinn vs tallrikssvinn ──────────────────────────────────────
    wtbu = insights.get("waste_type_by_unit")
    if isinstance(wtbu, pd.DataFrame) and not wtbu.empty:
        lines += [
            "",
            "## Var försvinner maten? Serveringssvinn vs tallrikssvinn",
            "",
            "| Enhet | Serveringssvinn (kg) | Tallrikssvinn (kg) |",
            "|---|---:|---:|",
        ]
        for unit, row in wtbu.iterrows():
            sv = _fmt(row.get("serving_waste_kg", 0), 1)
            pv = _fmt(row.get("plate_waste_kg", 0), 1)
            lines.append(f"| {unit} | {sv} | {pv} |")

    # ── Svinn per vecka ───────────────────────────────────────────────────────
    wpw = insights.get("waste_per_portion_by_week")
    if isinstance(wpw, pd.Series) and not wpw.empty:
        lines += [
            "",
            "## Säsongsmönster: svinn per vecka (medel kg/portion)",
            "",
            "| Vecka | kg svinn/portion |",
            "|---|---:|",
        ]
        for week, val in wpw.items():
            lines.append(f"| v.{week} | {_fmt(val, 4)} |")

    # ── Inköpskostnad per enhet ───────────────────────────────────────────────
    cbu = insights.get("total_cost_by_unit")
    if isinstance(cbu, pd.Series) and not cbu.empty:
        lines += [
            "",
            "## Inköpskostnad per enhet (kr, helår)",
            "",
            "| Enhet | Total inköp (kr) |",
            "|---|---:|",
        ]
        for unit, val in cbu.items():
            lines.append(f"| {unit} | {_fmt(val, 0)} |")

    # ── Top varugrupper ───────────────────────────────────────────────────────
    tcv = insights.get("top_cost_varugrupp")
    if isinstance(tcv, pd.DataFrame) and not tcv.empty:
        lines += [
            "",
            "## Topp 20 varugrupper efter inköpskostnad",
            "",
            "| Varugrupp | Total (kr) | Volym (kg) | kr/kg |",
            "|---|---:|---:|---:|",
        ]
        for grp, row in tcv.iterrows():
            lines.append(
                f"| {grp} | {_fmt(row['kronor'], 0)} | {_fmt(row['kilo'], 0)} | {_fmt(row['kr_kg'], 2)} |"
            )

    # ── Avtalstrohet ──────────────────────────────────────────────────────────
    ocp = insights.get("off_contract_pct_by_unit")
    if isinstance(ocp, pd.Series) and not ocp.empty:
        lines += [
            "",
            "## Avtalstrohet — andel inköp utanför avtal per enhet (viktad %)",
            "",
            "| Enhet | Utanför avtal (%) |",
            "|---|---:|",
        ]
        for unit, val in ocp.items():
            lines.append(f"| {unit} | {_fmt(val, 1)} |")

    # ── Kostnad per serverad portion ──────────────────────────────────────────
    cpp = insights.get("cost_per_portion_by_unit")
    if isinstance(cpp, pd.DataFrame) and not cpp.empty:
        lines += [
            "",
            "## Kostnad per serverad portion (inköp / portioner)",
            "",
            "| Enhet | Inköp (kr) | Portioner | kr/portion |",
            "|---|---:|---:|---:|",
        ]
        for unit, row in cpp.iterrows():
            lines.append(
                f"| {unit} | {_fmt(row['total_cost_sek'], 0)} | {_fmt(row['served_portions'], 0)} | {_fmt(row['cost_per_portion'], 2)} |"
            )

    # ── Portioner per månad ───────────────────────────────────────────────────
    pbm = insights.get("portions_by_month")
    cbm = insights.get("cost_by_month")
    if isinstance(pbm, pd.Series) and not pbm.empty:
        lines += [
            "",
            "## Säsongsmönster: portioner och kostnad per månad",
            "",
            "| Månad | Serverade portioner | Inköpskostnad (kr) |",
            "|---|---:|---:|",
        ]
        months = sorted(set(list(pbm.index) + (list(cbm.index) if isinstance(cbm, pd.Series) else [])))
        for m in months:
            p = _fmt(pbm.get(m, 0), 0)
            c = _fmt(cbm.get(m, 0), 0) if isinstance(cbm, pd.Series) else "—"
            lines.append(f"| {MONTH_NAMES.get(m, m)} | {p} | {c} |")

    # ── Meny × svinn ─────────────────────────────────────────────────────────
    mwh = insights.get("menu_waste_high")
    mwl = insights.get("menu_waste_low")
    if isinstance(mwh, pd.DataFrame) and not mwh.empty:
        lines += [
            "",
            "## Menyacceptans — veckor med HÖGST svinn",
            "",
            "| Vecka | kg svinn/portion | Veckans rätter |",
            "|---|---:|---|",
        ]
        for _, row in mwh.iterrows():
            lines.append(f"| v.{int(row['week'])} | {_fmt(row['waste_per_portion'], 4)} | {row['dish_name']} |")

    if isinstance(mwl, pd.DataFrame) and not mwl.empty:
        lines += [
            "",
            "## Menyacceptans — veckor med LÄGST svinn",
            "",
            "| Vecka | kg svinn/portion | Veckans rätter |",
            "|---|---:|---|",
        ]
        for _, row in mwl.sort_values("waste_per_portion").iterrows():
            lines.append(f"| v.{int(row['week'])} | {_fmt(row['waste_per_portion'], 4)} | {row['dish_name']} |")

    # ── Förskoledebitering ────────────────────────────────────────────────────
    # (preschool_billing shown in summary only for now)

    # ── Filer som inte kunde tolkas ───────────────────────────────────────────
    if unreadable:
        lines += ["", "## Filer/blad som inte kunde tolkas", ""]
        for item in unreadable[:50]:
            lines.append(f"- `{Path(item.get('file', '')).name}` / `{item.get('sheet')}`: {item.get('error')}")

    # ── Öppna osäkerheter ────────────────────────────────────────────────────
    lines += [
        "",
        "## Osäkerheter och begränsningar",
        "",
        "- **Kostnad per portion** är approximativ: inköp matchas på enhetsnamn utan strikt datum-nyckel.",
        "- **Portions-data** extraherar enhetsnnamn ur katalogstruktur — kan avvika vid oregelbunden filorganisation.",
        "- **Menyacceptans** är analyserad på veckobasis (meny × svinn). Rätt-för-rätt-analys kräver daglig svinnregistrering kopplad till specifik maträtt.",
        "- **Lov/studiedagar** saknas — låga portionsveckor kan vara lov, inte verkliga avvikelser.",
    ]

    return "\n".join(lines)


def write_report(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
