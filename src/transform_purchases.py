from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

MONTH_MAP = {
    "januari": 1, "februari": 2, "mars": 3, "april": 4,
    "maj": 5, "juni": 6, "juli": 7, "augusti": 8,
    "september": 9, "oktober": 10, "november": 11, "december": 12,
}

# Columns that carry analytical value — drop everything else
CORE_COLUMNS = [
    "organisation",
    "ansvarsomrade",
    "enhetstyp",
    "enhet",
    "varuomrade",
    "huvudgrupp",
    "varugrupp",
    "supplier",
    "lev_artnr",
    "article_name",
    "producent",
    "marke",
    "innehall",
    "fsgenhet",
    "kronor",
    "kilo",
    "kr_kg",
    "unit_cost_sek_per_kg",
    "procent_utanfor_avtal",
    "ekologisk",
    "msc",
    "kravmarkt",
    "etisk",
    "fairtrade",
    "produktens_tillverkningsland",
    "ravarans_ursprungsland",
]

# Canonical unit name mapping: purchases (uppercase) → standard (titlecase)
UNIT_NAME_MAP = {
    "ÄVENTYRETS FÖRSKOLA": "Äventyrets förskola",
    "LERBERGSSKOLAN": "Lerbergsskolan",
    "NYHAMNSSKOLAN": "Nyhamnsskolan",
    "VIKENSKOLAN": "Vikenskolan",
    "KULLAGYMNASIET": "Kullagymnasiet",
    "VIKHAGA KÖK": "Vikhaga",
    "TORNLYCKESKOLAN": "Tornlyckeskolan",
    "SOLGLÄNTANS FÖRSKOLA": "Solgläntans förskola",
    "ELEHULTS FÖRSKOLA": "Eleshults förskola",   # stavningskorrigering
    "HAVETS FÖRSKOLA": "Havets förskola",
    "REVETS FÖRSKOLA / 942131": "Revets förskola",
    "SVANEBÄCKS FÖRSKOLA": "Svanebäcks förskola",
    "BRUKSSKOLAN": "Bruksskolan",
    "JONSSTORPSSKOLAN": "Jonstorpsskolan",        # stavningskorrigering
    "NYHAMNSGÅRDEN": "Nyhamnsgården",
    "VÄSBYHEMMET KÖK": "Väsbyhemmet",
    "VIKENS RY FÖRSKOLA": "Vikens Ry förskola",
    "LÄRLYCKAN FÖRSKOLA": "Lärlyckans förskola",
    "KLÖVERÄNGENS FSK": "Klöverängens förskola",
    "PETER LUNDS FSK": "Peter Lundhs förskola",  # stavningskorrigering
}


def _extract_month(file_path: Path) -> int | None:
    """Extract month number from filename, e.g. 'Inköp April 2025.xlsx' → 4."""
    name = file_path.stem.lower()
    for swe, num in MONTH_MAP.items():
        if swe in name:
            return num
    return None


def _extract_year(file_path: Path) -> int | None:
    m = re.search(r"(20\d{2})", file_path.stem)
    return int(m.group(1)) if m else None


def transform_purchases(df: pd.DataFrame, file_path: Path, sheet_name: str) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    # Keep only known analytical columns — drop timestamp garbage columns
    keep = [c for c in CORE_COLUMNS if c in out.columns]
    out = out[keep].copy()

    # Drop rows with no enhet (header echoes, subtotals etc.)
    if "enhet" in out.columns:
        out = out[out["enhet"].notna() & (out["enhet"].astype(str).str.strip() != "")]

    # Normalize unit name
    if "enhet" in out.columns:
        out["unit_name_std"] = out["enhet"].astype(str).str.strip().map(UNIT_NAME_MAP)

    # Month and year from filename
    out["month"] = _extract_month(file_path)
    out["year"] = _extract_year(file_path)

    # Cast mixed-type object columns to string to avoid parquet serialisation errors
    for col in out.select_dtypes(include="object").columns:
        out[col] = out[col].where(out[col].isna(), out[col].astype(str))

    # Ensure numeric types for key financial columns
    for col in ["kronor", "kilo", "kr_kg", "unit_cost_sek_per_kg", "procent_utanfor_avtal"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    # Metadata
    out["source_file"] = str(file_path)
    out["source_sheet"] = sheet_name
    out["detected_category"] = "purchases"

    return out
