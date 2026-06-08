import re
import unicodedata


def normalize_text(text: str) -> str:
    if text is None:
        return ""
    text = str(text).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text)
    return text


def clean_column_name(name: str) -> str:
    n = normalize_text(name)
    n = n.replace("%", " procent ")
    n = re.sub(r"[^a-z0-9]+", "_", n)
    n = re.sub(r"_+", "_", n).strip("_")
    return n


STANDARD_COLUMN_MAP = {
    "antal_serverade_portioner": "served_portions",
    "bestallda_portioner": "ordered_portions",
    "tallrikssvinn_kg": "plate_waste_kg",
    "tallrikssvinn_procent": "plate_waste_pct",
    "serveringssvinn_kg": "serving_waste_kg",
    "serveringssvinn_procent": "serving_waste_pct",
    "totalt_uppmatt_matsvinn_kg": "total_waste_kg",
    "totalt_uppmatt_matsvinn_procent": "total_waste_pct",
    "datum": "date",
    "ar": "year",
    "manad": "month",
    "vecka": "week",
    "leverantor": "supplier",
    "artikelnamn": "article_name",
    "fardigmangd_kr_kg": "unit_cost_sek_per_kg",
    "mottagningskok": "receiving_kitchen",
    "tillagningskok": "cooking_kitchen",
    "kokets_namn": "unit_name",
    "typ_av_kok": "kitchen_type",
    "lunch": "lunch",
    "antal_barn": "children_count",
}


def clean_columns(columns):
    cleaned = [clean_column_name(c) for c in columns]
    standardized = [STANDARD_COLUMN_MAP.get(c, c) for c in cleaned]
    return standardized
