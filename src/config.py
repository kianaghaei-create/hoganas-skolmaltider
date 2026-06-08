from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"
SOURCE_DIRS = [
    PROJECT_ROOT / "Data",
]
SKIP_PREFIXES = ("~$",)
EXCEL_SUFFIX = ".xlsx"
OUTPUT_FORMAT = "parquet"  # parquet or csv
MAX_FILES = int(os.getenv("MAX_FILES", "0"))
MAX_SHEETS_PER_FILE = int(os.getenv("MAX_SHEETS_PER_FILE", "0"))
