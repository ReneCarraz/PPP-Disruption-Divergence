"""I/O and dataframe utility helpers."""

from __future__ import annotations

import ast
from pathlib import Path
import re
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


ILLEGAL_EXCEL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def require_columns(df: pd.DataFrame, columns: Sequence[str], *, context: str) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"{context}: missing required columns: {', '.join(missing)}")


def read_table(path: str | Path, **kwargs) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path, **kwargs)
    if "columns" in kwargs:
        kwargs["usecols"] = kwargs.pop("columns")
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(path, **kwargs)
    if suffix == ".tsv":
        return pd.read_csv(path, sep="\t", **kwargs)
    raise ValueError(f"Unsupported table format for {path}")


def normalize_patent_id(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None
    s = s.removeprefix("US-").removeprefix("us-")
    if "-" in s:
        s = s.split("-", 1)[0]
    if s.endswith(".0"):
        s = s[:-2]
    return s


def patent_id_us(value: object) -> str | None:
    pid = normalize_patent_id(value)
    return f"US-{pid}" if pid else None


def normalize_work_id(value: object, *, full: bool = True) -> str | None:
    if value is None or pd.isna(value):
        return None
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None
    short = s.rsplit("/", 1)[-1] if s.startswith("https://openalex.org/") else s
    return f"https://openalex.org/{short}" if full else short


def normalize_doi(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    doi = str(value).strip().lower()
    doi = re.sub(r"^doi\s*:\s*", "", doi)
    doi = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", doi)
    return doi or None


def decode_list(value: object) -> list | pd._libs.missing.NAType:
    if isinstance(value, list):
        return value
    if isinstance(value, np.ndarray):
        return value.tolist()
    if value is None or value is pd.NA:
        return pd.NA
    if isinstance(value, float) and pd.isna(value):
        return pd.NA
    if not isinstance(value, str):
        return pd.NA
    s = value.strip()
    if not s:
        return pd.NA
    if s.startswith("[") and s.endswith("]"):
        try:
            parsed = ast.literal_eval(s)
            return parsed if isinstance(parsed, list) else pd.NA
        except Exception:
            return pd.NA
    return pd.NA


def list_len(value: object) -> int | pd._libs.missing.NAType:
    return len(value) if isinstance(value, list) else pd.NA


def mean_or_nan(values: object) -> float:
    if not isinstance(values, list) or not values:
        return np.nan
    numeric = [v for v in values if v is not None and not pd.isna(v)]
    return float(np.mean(numeric)) if numeric else np.nan


def strip_illegal_chars(value: object) -> object:
    if isinstance(value, str):
        return ILLEGAL_EXCEL_RE.sub("", value)
    return value


def unique_clean_list(values: Iterable) -> list:
    out = []
    seen = set()
    for value in values:
        if value is None or pd.isna(value):
            continue
        if value not in seen:
            out.append(value)
            seen.add(value)
    return out
