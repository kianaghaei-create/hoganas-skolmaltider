from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .clean_columns import clean_column_name

CATEGORIES = [
    "purchases",
    "food_waste",
    "portions",
    "menu_nutrition",
    "preschool_billing",
    "unknown",
]


def detect_from_name(path: Path) -> str:
    name = path.name.lower()
    parent = str(path.parent).lower()
    if "ink" in name or "hantera livs" in name:
        return "purchases"
    if "matsvinn" in name or "matsvinn" in parent:
        return "food_waste"
    if "portion" in name and "debiter" in name:
        return "preschool_billing"
    if "portion" in name:
        return "portions"
    if "meny" in name or "naring" in name or "näring" in name:
        return "menu_nutrition"
    return "unknown"


def detect_from_sheet_and_columns(sheet_name: str, columns: Iterable[str]) -> str:
    s = clean_column_name(sheet_name)
    cols = set(clean_column_name(c) for c in columns if c is not None)
    if s.startswith("v_") or "tallrikssvinn" in " ".join(cols):
        return "food_waste"
    if "hantera_livs" in s or {"supplier", "article_name"}.intersection(cols):
        return "purchases"
    if "dagens_lunch" in " ".join(cols) or "vegetarisk_lunch" in " ".join(cols):
        return "menu_nutrition"
    if "antal_betalda_portioner" in cols:
        return "preschool_billing"
    if {"lunch", "antal_barn", "date"}.intersection(cols):
        return "portions"
    return "unknown"


def detect_category(path: Path, sheet_name: str = "", columns=()) -> str:
    by_name = detect_from_name(path)
    if by_name != "unknown":
        return by_name
    by_structure = detect_from_sheet_and_columns(sheet_name, columns)
    return by_structure
