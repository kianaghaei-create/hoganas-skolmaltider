from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
import warnings

import pandas as pd

from .clean_columns import clean_columns
from .config import EXCEL_SUFFIX, MAX_FILES, MAX_SHEETS_PER_FILE, SKIP_PREFIXES, SOURCE_DIRS


@dataclass
class SheetData:
    file_path: Path
    sheet_name: str
    dataframe: pd.DataFrame


def discover_excel_files() -> list[Path]:
    files: list[Path] = []
    for src in SOURCE_DIRS:
        if not src.exists():
            continue
        for p in src.rglob(f"*{EXCEL_SUFFIX}"):
            if p.name.startswith(SKIP_PREFIXES):
                continue
            if any(part.startswith(".") for part in p.parts):
                continue
            files.append(p)
    files = sorted(set(files))
    if MAX_FILES > 0:
        return files[:MAX_FILES]
    return files


def _read_sheet(file_path: Path, sheet_name: str) -> pd.DataFrame:
    # Header autodetect: read without header then infer row with most non-empty cells
    raw = pd.read_excel(file_path, sheet_name=sheet_name, header=None, engine="openpyxl")
    if raw.empty:
        return pd.DataFrame()

    scan = raw.head(40)
    score = scan.notna().sum(axis=1)
    header_idx = int(score.idxmax())

    data = pd.read_excel(file_path, sheet_name=sheet_name, header=header_idx, engine="openpyxl")
    if data.empty:
        return data
    data.columns = clean_columns(data.columns)
    data = data.loc[:, ~data.columns.duplicated()]
    return data


def iter_workbook_sheets(file_path: Path) -> Iterator[SheetData]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            xls = pd.ExcelFile(file_path, engine="openpyxl")
    except Exception:
        return

    for idx, sheet in enumerate(xls.sheet_names):
        if MAX_SHEETS_PER_FILE > 0 and idx >= MAX_SHEETS_PER_FILE:
            break
        if sheet.upper() == "ESRI_MAPINFO_SHEET":
            continue
        try:
            # Parse via already-open workbook object for speed/stability.
            raw = xls.parse(sheet_name=sheet, header=None)
            if raw.empty:
                df = pd.DataFrame()
            else:
                scan = raw.head(40)
                score = scan.notna().sum(axis=1)
                header_idx = int(score.idxmax())
                df = xls.parse(sheet_name=sheet, header=header_idx)
                if not df.empty:
                    df.columns = clean_columns(df.columns)
                    df = df.loc[:, ~df.columns.duplicated()]
        except Exception:
            df = pd.DataFrame()
        yield SheetData(file_path=file_path, sheet_name=sheet, dataframe=df)
