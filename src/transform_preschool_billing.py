from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

MONTH_MAP = {
    "januari": 1, "februari": 2, "mars": 3, "april": 4,
    "maj": 5, "juni": 6, "juli": 7, "augusti": 8,
    "september": 9, "oktober": 10, "november": 11, "december": 12,
}


def _normalize(s: str) -> str:
    import unicodedata
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _month_num(label: str) -> int | None:
    n = _normalize(label)
    for swe, num in MONTH_MAP.items():
        if swe in n:
            return num
    return None


def transform_preschool_billing(df: pd.DataFrame, file_path: Path, sheet_name: str) -> pd.DataFrame:
    """
    Preschool billing: sheet name = unit name.
    Rows: month name | ordered_portions | paid_portions | diff | swish_note
    We extract these into a clean long-format table.
    """
    if df.empty:
        return pd.DataFrame()

    unit_name = sheet_name.strip()

    # Try to find year from file
    year = None
    m = re.search(r"(20\d{2})", file_path.stem + " " + str(df.iloc[0].tolist()))
    if m:
        year = int(m.group(1))

    rows = []
    for _, row in df.iterrows():
        vals = [v for v in row.values if pd.notna(v)]
        if len(vals) < 3:
            continue

        # First value should be month name
        month_label = str(vals[0]).strip()
        month_num = _month_num(month_label)
        if month_num is None:
            continue

        # Second = ordered, third = paid
        try:
            ordered = float(vals[1])
            paid = float(vals[2])
        except (ValueError, TypeError):
            continue

        diff = ordered - paid
        swish = str(vals[4]).strip() if len(vals) > 4 else None

        rows.append({
            "unit_name": unit_name,
            "year": year,
            "month": month_num,
            "month_name": month_label,
            "ordered_portions": ordered,
            "paid_portions": paid,
            "diff_portions": diff,
            "swish_note": swish,
            "source_file": str(file_path),
            "source_sheet": sheet_name,
            "detected_category": "preschool_billing",
        })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)
