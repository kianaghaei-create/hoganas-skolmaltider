from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

MONTH_MAP = {
    "januari": 1, "februari": 2, "mars": 3, "april": 4,
    "maj": 5, "juni": 6, "juli": 7, "augusti": 8,
    "september": 9, "oktober": 10, "november": 11, "december": 12,
}

# Day columns: 1–31 (as int or str)
DAY_COLS = [str(i) for i in range(1, 32)]

# Row labels that represent portion types we care about
PORTION_TYPE_PATTERNS = [
    (r"lunch.*barn|barn.*lunch|antal barn", "lunch_children"),
    (r"ovriga.*gaster|gaster.*ovriga|ovriga gaster", "lunch_guests"),
    (r"summa|totalt", "total"),
    (r"frukost", "breakfast"),
    (r"mellanmal|mellansmal", "snack"),
    (r"kvallsmat|kvall", "dinner"),
]


def _normalize(s: str) -> str:
    import unicodedata
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s


def _detect_portion_type(label: str) -> str | None:
    n = _normalize(label)
    for pattern, ptype in PORTION_TYPE_PATTERNS:
        if re.search(pattern, n):
            return ptype
    return None


def _extract_unit_from_path(file_path: Path) -> str:
    """Best-effort: take the parent folder name or stem as unit name."""
    # Structure: Data/2025/<UnitFolder>/<file>.xlsx
    # Try parent folder first
    parent = file_path.parent.name
    # If parent is a year or generic name, fall back to stem
    if re.match(r"^\d{4}$", parent) or parent.lower() in ("data", "2025", "processed"):
        return file_path.stem
    return parent


def _extract_year(file_path: Path, sheet_name: str) -> int | None:
    # Try sheet name or file name
    for s in [sheet_name, file_path.stem]:
        m = re.search(r"(20\d{2})", str(s))
        if m:
            return int(m.group(1))
    return None


def transform_portions(df: pd.DataFrame, file_path: Path, sheet_name: str) -> pd.DataFrame:
    """
    Portions files are wide: columns are day numbers (1–31), rows are portion types.
    We melt to long format: unit_name | year | month | day | portion_type | count.
    """
    if df.empty:
        return df

    # --- Identify which columns are day columns ---
    present_day_cols = [c for c in df.columns if str(c).strip() in DAY_COLS]
    if not present_day_cols:
        # Not a recognizable portions sheet — skip
        return pd.DataFrame()

    # --- Find the label column (first non-day column, usually index 0) ---
    non_day_cols = [c for c in df.columns if str(c).strip() not in DAY_COLS
                    and c not in ("sa", "summa", "source_file", "source_sheet", "detected_category")]
    label_col = non_day_cols[0] if non_day_cols else None

    # --- Detect month from sheet name ---
    month_num = None
    sheet_lower = _normalize(sheet_name)
    for swe, num in MONTH_MAP.items():
        if swe in sheet_lower:
            month_num = num
            break

    unit_name = _extract_unit_from_path(file_path)
    year = _extract_year(file_path, sheet_name)

    rows = []
    for _, row in df.iterrows():
        # Determine portion type from label column
        label = str(row[label_col]).strip() if label_col and pd.notna(row.get(label_col)) else ""
        portion_type = _detect_portion_type(label)
        if portion_type is None:
            continue  # skip unrecognized rows (headers, empty rows, formulas)

        for day_col in present_day_cols:
            val = row.get(day_col)
            if pd.isna(val):
                continue
            try:
                count = float(val)
            except (ValueError, TypeError):
                continue
            if count == 0:
                continue

            rows.append({
                "unit_name": unit_name,
                "year": year,
                "month": month_num,
                "day": int(str(day_col).strip()),
                "portion_type": portion_type,
                "count": count,
                "source_file": str(file_path),
                "source_sheet": sheet_name,
                "detected_category": "portions",
            })

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)

    # Build date where possible
    if {"year", "month", "day"}.issubset(out.columns):
        out["date"] = pd.to_datetime(
            out[["year", "month", "day"]].rename(columns={"day": "day"}),
            errors="coerce",
        )
        out["week"] = out["date"].dt.isocalendar().week.astype("Int64")

    return out
