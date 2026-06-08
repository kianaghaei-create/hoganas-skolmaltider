from __future__ import annotations

from pathlib import Path
import warnings
import pandas as pd

from src.analysis import first_insights, summarize_tables
from src.config import OUTPUT_FORMAT, PROCESSED_DIR, REPORTS_DIR
from src.data_quality import render_data_quality_report, run_data_quality_checks
from src.detect_file_type import detect_category
from src.load_excel import discover_excel_files, iter_workbook_sheets
from src.report import render_analysis_report, write_report
from src.transform_food_waste import transform_food_waste, parse_food_waste_file
from src.transform_menu_nutrition import transform_menu_nutrition, parse_menu_file
from src.transform_portions import transform_portions
from src.transform_preschool_billing import transform_preschool_billing
from src.transform_purchases import transform_purchases

TRANSFORMERS = {
    "purchases": transform_purchases,
    "food_waste": transform_food_waste,
    "portions": transform_portions,
    "menu_nutrition": transform_menu_nutrition,
    "preschool_billing": transform_preschool_billing,
}

TABLE_KEYS = ["purchases", "food_waste", "portions", "menu_nutrition", "preschool_billing"]


def ensure_dirs():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _coerce_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure object columns are consistently typed for parquet serialisation."""
    out = df.copy()
    for col in out.select_dtypes(include="object").columns:
        out[col] = out[col].where(out[col].isna(), out[col].astype(str))
    return out


def export_table(df: pd.DataFrame, name: str):
    df.to_csv(PROCESSED_DIR / f"{name}.csv", index=False)
    try:
        _coerce_for_parquet(df).to_parquet(PROCESSED_DIR / f"{name}.parquet", index=False)
    except Exception as e:
        print(f"  [warn] parquet write failed for {name}: {e}")


def run_pipeline():
    warnings.filterwarnings("ignore", message="Workbook contains no default style")
    ensure_dirs()

    files = discover_excel_files()
    bucket = {k: [] for k in TABLE_KEYS}
    unreadable = []

    for f in files:
        for sheet in iter_workbook_sheets(f):
            df = sheet.dataframe
            if df.empty:
                unreadable.append({"file": str(f), "sheet": sheet.sheet_name, "error": "empty_or_unreadable_sheet"})
                continue

            category = detect_category(f, sheet.sheet_name, df.columns)
            if category not in TRANSFORMERS:
                continue

            transformed = TRANSFORMERS[category](df, f, sheet.sheet_name)
            if transformed.empty:
                continue

            if "detected_category" not in transformed.columns:
                transformed["detected_category"] = category
            bucket[category].append(transformed)

    # Food waste: parse Sammanställning sheet directly (has week + portions + kg)
    fw_dfs = []
    for f in files:
        cat = detect_category(f)
        if cat == "food_waste":
            fdf = parse_food_waste_file(f)
            if not fdf.empty:
                fw_dfs.append(fdf)
    if fw_dfs:
        bucket["food_waste"] = fw_dfs

    # Menu nutrition: parse full workbooks directly (one sheet per week structure)
    menu_dfs = []
    for f in files:
        fname_lower = f.name.lower()
        fname_ascii = fname_lower.encode("ascii", "ignore").decode()
        is_menu = "meny" in fname_lower
        is_skola = "skola" in fname_lower
        is_ao = "ao" in fname_ascii or "\xe4o" in fname_lower or "äo" in fname_lower
        if is_menu and (is_skola or is_ao):
            menu_type = "skola" if is_skola else "ao"
            mdf = parse_menu_file(f, menu_type)
            if not mdf.empty:
                menu_dfs.append(mdf)
    if menu_dfs:
        bucket["menu_nutrition"] = menu_dfs

    tables = {}
    for key in TABLE_KEYS:
        if bucket[key]:
            tables[key] = pd.concat(bucket[key], ignore_index=True)
        else:
            tables[key] = pd.DataFrame()
        export_table(tables[key], key)

    dq_findings = run_data_quality_checks(tables)
    dq_md = render_data_quality_report(dq_findings)
    write_report(REPORTS_DIR / "data_quality_report.md", dq_md)

    summary = summarize_tables(tables)
    insights = first_insights(tables)
    analysis_md = render_analysis_report(summary, insights, unreadable)
    write_report(REPORTS_DIR / "analysis_report.md", analysis_md)

    summary.to_csv(PROCESSED_DIR / "table_summary.csv", index=False)
    print("Pipeline completed.")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    run_pipeline()
