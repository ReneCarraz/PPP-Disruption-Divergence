"""USPTO/PatentsView feature extraction."""

from __future__ import annotations

from glob import glob
from pathlib import Path
import re

import pandas as pd

from config import UsptoInputs
from table_io import normalize_patent_id, read_table, require_columns, unique_clean_list


def add_patent_text_and_dates(df: pd.DataFrame, inputs: UsptoInputs) -> pd.DataFrame:
    patents = read_table(inputs.patents_path)
    patents["patent_id"] = patents["patent_id"].map(normalize_patent_id)
    keep = ["patent_id"]
    for col in ["patent_date", "patent_filing_date", "patent_assignee_country"]:
        if col in patents.columns:
            keep.append(col)
    patents = patents[keep].drop_duplicates(subset=["patent_id"], keep="first")
    out = df.merge(patents, on="patent_id", how="left", suffixes=("", "_uspto"))
    for col in ["patent_date", "patent_filing_date", "patent_assignee_country"]:
        alt = f"{col}_uspto"
        if alt in out.columns:
            out[col] = out[col].fillna(out[alt]) if col in out.columns else out[alt]
            out = out.drop(columns=[alt])

    g_patent = read_table(inputs.g_patent_path)
    g_patent["patent_id"] = g_patent["patent_id"].map(normalize_patent_id)
    text_cols = [c for c in ["patent_id", "patent_title", "patent_abstract"] if c in g_patent.columns]
    g_patent = g_patent[text_cols].drop_duplicates(subset=["patent_id"], keep="first")
    out = out.merge(g_patent, on="patent_id", how="left", suffixes=("", "_lookup"))
    for col in ["patent_title", "patent_abstract"]:
        alt = f"{col}_lookup"
        if alt in out.columns:
            out[col] = out[col].fillna(out[alt]) if col in out.columns else out[alt]
            out = out.drop(columns=[alt])
    return out


def add_inventor_team_size(df: pd.DataFrame, inputs: UsptoInputs) -> pd.DataFrame:
    inventors = read_table(inputs.inventors_path)
    require_columns(inventors, ["patent_id"], context="inventors")
    inventors["patent_id"] = inventors["patent_id"].map(normalize_patent_id)
    counts = inventors.groupby("patent_id").size().rename("inventor_team_size").reset_index()
    out = df.drop(columns=["inventor_team_size"], errors="ignore").merge(counts, on="patent_id", how="left")
    out["inventor_team_size"] = out["inventor_team_size"].fillna(0).astype("int64")
    return out


def add_assignees(df: pd.DataFrame, inputs: UsptoInputs) -> pd.DataFrame:
    assignees = read_table(inputs.assignees_path, dtype=str)
    org_col = (
        "disambig_assignee_organization"
        if "disambig_assignee_organization" in assignees.columns
        else "assignee"
    )
    require_columns(assignees, ["patent_id", org_col, "assignee_type", "location_id"], context="assignees")
    assignees["patent_id"] = assignees["patent_id"].map(normalize_patent_id)
    grouped = (
        assignees.dropna(subset=["patent_id"])
        .groupby("patent_id")
        .agg(
            patent_assignee_names=(org_col, unique_clean_list),
            patent_assignee_types=("assignee_type", unique_clean_list),
            patent_assignee_location_ids=("location_id", unique_clean_list),
        )
        .reset_index()
    )
    return df.drop(
        columns=["patent_assignee_names", "patent_assignee_types", "patent_assignee_location_ids"],
        errors="ignore",
    ).merge(grouped, on="patent_id", how="left")


def add_patent_family_size(df: pd.DataFrame, inputs: UsptoInputs) -> pd.DataFrame:
    patents = read_table(inputs.patents_path, columns=["patent_id"])
    patents["patent_id"] = patents["patent_id"].map(normalize_patent_id)
    sizes = patents.groupby("patent_id").size().rename("patent_family_size").reset_index()
    out = df.drop(columns=["patent_family_size"], errors="ignore").merge(sizes, on="patent_id", how="left")
    out["patent_family_size"] = out["patent_family_size"].fillna(0).astype("int64")
    return out


def _normalize_claim_patent_id(s: pd.Series) -> pd.Series:
    return s.astype("string").str.replace("US-", "", regex=False).str.replace(r"\.0$", "", regex=True).str.strip()


def _claim_paths(pattern: str) -> list[Path]:
    paths = [Path(p) for p in glob(pattern)]
    if not paths:
        raise FileNotFoundError(f"No claim TSVs matched: {pattern}")
    return sorted(paths)


def add_claim_features(df: pd.DataFrame, inputs: UsptoInputs, *, chunksize: int = 500_000) -> pd.DataFrame:
    target_ids = set(df["patent_id"].dropna().astype(str))
    counts: dict[str, int] = {}
    first_len: dict[str, int] = {}
    usecols = ["patent_id", "claim_sequence", "claim_text", "dependent"]
    dtypes = {"patent_id": "string", "claim_sequence": "Int64", "claim_text": "string", "dependent": "string"}

    for path in _claim_paths(inputs.claims_tsv_glob):
        for chunk in pd.read_csv(path, sep="\t", usecols=usecols, dtype=dtypes, chunksize=chunksize, na_values=["", "NULL", "\\N"]):
            chunk["patent_id"] = _normalize_claim_patent_id(chunk["patent_id"])
            chunk = chunk[chunk["patent_id"].isin(target_ids)]
            if chunk.empty:
                continue
            for pid, count in chunk.groupby("patent_id").size().items():
                counts[pid] = counts.get(pid, 0) + int(count)
            first = chunk[(chunk["claim_sequence"] == 0) & (chunk["dependent"].isna())].copy()
            if first.empty:
                continue
            first["length"] = first["claim_text"].fillna("").str.strip().str.count(r"\S+")
            for pid, length in first.groupby("patent_id")["length"].max().items():
                first_len.setdefault(pid, int(length))

    features = pd.DataFrame({"patent_id": sorted(target_ids)})
    features["patent_num_claims"] = features["patent_id"].map(counts).fillna(0).astype("int64")
    features["patent_first_claim_length"] = features["patent_id"].map(first_len).astype("Int64")
    return df.drop(columns=["patent_num_claims", "patent_first_claim_length"], errors="ignore").merge(features, on="patent_id", how="left")


def add_uspto_features(df: pd.DataFrame, inputs: UsptoInputs) -> pd.DataFrame:
    out = add_patent_text_and_dates(df, inputs)
    out = add_inventor_team_size(out, inputs)
    out = add_assignees(out, inputs)
    out = add_patent_family_size(out, inputs)
    out = add_claim_features(out, inputs)
    return out
