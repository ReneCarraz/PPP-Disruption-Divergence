"""Final cleanup and export."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from table_io import require_columns, strip_illegal_chars
from schema import FINAL_COLUMNS, RENAME_MAP


def add_final_dates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["work_publication_date"] = pd.to_datetime(out["work_publication_date"], errors="coerce")
    out["patent_filing_date"] = pd.to_datetime(out["patent_filing_date"], errors="coerce")
    out["publication_year"] = out["work_publication_date"].dt.year.astype("Int64")
    out["patent_priority_year"] = out["patent_filing_date"].dt.year.astype("Int64")
    out["lag_days"] = (out["work_publication_date"] - out["patent_filing_date"]).dt.days
    if "daysdiffcont" in out.columns:
        days = pd.to_numeric(out["daysdiffcont"], errors="coerce")
        out["earliest_patent_year"] = (
            out["work_publication_date"] + pd.to_timedelta(days, unit="D")
        ).dt.year.astype("Int64")
    else:
        out["earliest_patent_year"] = pd.NA
    out["team_size_difference"] = out["author_team_size"] - out["inventor_team_size"]
    return out


def prepare_final_export(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for old, new in RENAME_MAP.items():
        if old in out.columns and new not in out.columns:
            out = out.rename(columns={old: new})
        elif old in out.columns and new in out.columns:
            out = out.drop(columns=[old])

    for col in ["mean_age_of_work_references", "mean_age_of_patent_references"]:
        if col in out.columns:
            out.loc[out[col] < 0, col] = np.nan

    require_columns(out, FINAL_COLUMNS, context="final export")
    final = out[FINAL_COLUMNS].copy()
    object_cols = final.select_dtypes(include=["object", "string"]).columns
    if len(object_cols):
        final.loc[:, object_cols] = final[object_cols].apply(lambda col: col.map(strip_illegal_chars))
    return final


def write_outputs(df: pd.DataFrame, *, csv_path: str | Path, parquet_path: str | Path) -> dict[str, Path]:
    csv_path = Path(csv_path)
    parquet_path = Path(parquet_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    df.to_parquet(parquet_path, index=False)
    return {"csv": csv_path, "parquet": parquet_path}
