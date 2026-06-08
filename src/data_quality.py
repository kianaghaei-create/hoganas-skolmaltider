from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd


@dataclass
class DataQualityFinding:
    table: str
    severity: str
    issue: str
    count: int


def _count_negative(df: pd.DataFrame, cols: list[str]) -> int:
    count = 0
    for c in cols:
        if c in df.columns:
            s = pd.to_numeric(df[c], errors="coerce")
            count += int((s < 0).sum())
    return count


def _count_pct_over_100(df: pd.DataFrame) -> int:
    count = 0
    for c in df.columns:
        if c.endswith("_pct"):
            s = pd.to_numeric(df[c], errors="coerce")
            count += int((s > 100).sum())
    return count


def run_data_quality_checks(tables: Dict[str, pd.DataFrame]) -> List[DataQualityFinding]:
    findings: List[DataQualityFinding] = []

    for name, df in tables.items():
        if df.empty:
            findings.append(DataQualityFinding(name, "high", "empty_table", 1))
            continue

        empty_rows = int(df.isna().all(axis=1).sum())
        if empty_rows:
            findings.append(DataQualityFinding(name, "medium", "fully_empty_rows", empty_rows))

        neg = _count_negative(df, ["served_portions", "ordered_portions", "total_waste_kg", "plate_waste_kg", "serving_waste_kg"])
        if neg:
            findings.append(DataQualityFinding(name, "high", "negative_values", neg))

        pct = _count_pct_over_100(df)
        if pct:
            findings.append(DataQualityFinding(name, "high", "percent_over_100", pct))

        if "date" in df.columns:
            bad_dates = int(pd.to_datetime(df["date"], errors="coerce").isna().sum())
            if bad_dates:
                findings.append(DataQualityFinding(name, "medium", "unparseable_dates", bad_dates))

    return findings


def render_data_quality_report(findings: List[DataQualityFinding]) -> str:
    lines = ["# Data Quality Report", ""]
    if not findings:
        lines.append("No major issues detected.")
        return "\n".join(lines)

    lines.append("| table | severity | issue | count |")
    lines.append("|---|---|---|---:|")
    for f in findings:
        lines.append(f"| {f.table} | {f.severity} | {f.issue} | {f.count} |")
    return "\n".join(lines)
