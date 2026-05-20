"""Citation overlap, reference age/impact, and USPTO reference-count features."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from config import ReferenceInputs
from table_io import normalize_doi, normalize_patent_id, read_table
from openalex_client import OpenAlexClient
from text_scores import citation_overlap_score


def _short(value: object) -> str | None:
    return str(value).rsplit("/", 1)[-1] if value else None


def _valid_date(value: object) -> bool:
    if value is None or pd.isna(value):
        return False
    ts = pd.Timestamp(value)
    return pd.Timestamp("1800-01-01") <= ts <= pd.Timestamp.today().normalize()


def _age_days(main_date: object, ref_dates: list[pd.Timestamp]) -> list[int]:
    if not _valid_date(main_date):
        return []
    main = pd.Timestamp(main_date)
    return [(main - date).days for date in ref_dates if _valid_date(date)]


def _mean(values: list) -> float:
    return float(np.mean(values)) if values else np.nan


def _normalize_uspto_reference_patent_id(value: object) -> str | None:
    patent_id = normalize_patent_id(value)
    if patent_id is None:
        return None
    digits = "".join(ch for ch in patent_id if ch.isdigit())
    return digits or None


def _load_patent_references(path) -> pd.DataFrame:
    refs = read_table(path)
    if "patent" in refs.columns:
        refs["patent_id_us"] = refs["patent"].astype("string").str.strip()
        refs["patent_id"] = refs["patent_id_us"].map(normalize_patent_id)
    elif "patent_id" in refs.columns:
        refs["patent_id"] = refs["patent_id"].map(normalize_patent_id)
        refs["patent_id_us"] = "US-" + refs["patent_id"].astype("string")
    else:
        raise ValueError("Patent references need `patent` or `patent_id`")

    if "reftype" in refs.columns:
        refs = refs[refs["reftype"].eq("app")]

    doi_col = "doi" if "doi" in refs.columns else None
    oaid_col = "openalex_id" if "openalex_id" in refs.columns else "oaid" if "oaid" in refs.columns else None

    grouped = refs.groupby("patent_id").agg(
        patent_doi_references=(doi_col, lambda s: [d for d in s.dropna().map(normalize_doi) if d]) if doi_col else ("patent_id", lambda s: []),
        patent_referenced_works_oaids=(oaid_col, lambda s: [_short(x) if str(x).startswith("http") else f"W{x}" if str(x).isdigit() else str(x) for x in s.dropna()]) if oaid_col else ("patent_id", lambda s: []),
    ).reset_index()
    return grouped


def _count_uspto_reference_rows(
    path: Path,
    target_ids: set[str],
    *,
    chunksize: int,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for chunk in pd.read_csv(
        path,
        sep="\t",
        usecols=["patent_id"],
        dtype=str,
        chunksize=max(1, chunksize),
    ):
        normalized = chunk["patent_id"].map(_normalize_uspto_reference_patent_id)
        matches = normalized[normalized.isin(target_ids)]
        counts.update(matches.value_counts().to_dict())
    return counts


def add_uspto_reference_counts(
    df: pd.DataFrame,
    inputs: ReferenceInputs,
    *,
    chunksize: int,
) -> pd.DataFrame:
    out = df.copy()
    patent_ids = out["patent_id"].map(_normalize_uspto_reference_patent_id)
    target_ids = set(patent_ids.dropna())

    other_counts = _count_uspto_reference_rows(
        inputs.other_reference_path,
        target_ids,
        chunksize=chunksize,
    )
    us_counts = _count_uspto_reference_rows(
        inputs.us_patent_citation_path,
        target_ids,
        chunksize=chunksize,
    )
    foreign_counts = _count_uspto_reference_rows(
        inputs.foreign_citation_path,
        target_ids,
        chunksize=chunksize,
    )
    patent_citation_counts = Counter(us_counts)
    patent_citation_counts.update(foreign_counts)

    valid_patent = patent_ids.notna()
    out["uspto_non_patent_ref"] = patent_ids.map(other_counts).where(valid_patent)
    out["uspto_patent_citation"] = (
        patent_ids.map(patent_citation_counts).where(valid_patent)
    )
    out.loc[valid_patent, "uspto_non_patent_ref"] = out.loc[
        valid_patent, "uspto_non_patent_ref"
    ].fillna(0)
    out.loc[valid_patent, "uspto_patent_citation"] = out.loc[
        valid_patent, "uspto_patent_citation"
    ].fillna(0)
    out["uspto_non_patent_ref"] = out["uspto_non_patent_ref"].astype("Int64")
    out["uspto_patent_citation"] = out["uspto_patent_citation"].astype("Int64")
    return out


def add_reference_features(
    df: pd.DataFrame,
    inputs: ReferenceInputs,
    client: OpenAlexClient,
    *,
    uspto_reference_chunksize: int,
) -> pd.DataFrame:
    out = df.copy()
    patent_refs = _load_patent_references(inputs.patent_references_path)
    out = out.drop(columns=["patent_doi_references", "patent_referenced_works_oaids"], errors="ignore").merge(
        patent_refs, on="patent_id", how="left"
    )
    out = add_uspto_reference_counts(
        out,
        inputs,
        chunksize=uspto_reference_chunksize,
    )

    out["work_reference_list_length"] = out["work_referenced_works"].apply(
        lambda x: len(x) if isinstance(x, list) else np.nan
    )
    out["patent_reference_list_length"] = out["patent_doi_references"].apply(
        lambda x: len(x) if isinstance(x, list) else np.nan
    )
    out["citation_overlap_score"] = out.apply(
        lambda row: citation_overlap_score(
            row.get("patent_referenced_works_oaids"), row.get("work_referenced_works")
        ),
        axis=1,
    )

    work_ref_ids = sorted(
        {
            str(ref_id)
            for refs in out["work_referenced_works"].dropna()
            if isinstance(refs, list)
            for ref_id in refs
            if ref_id
        }
    )
    ref_works = client.works(work_ref_ids, select=["id", "publication_date", "cited_by_count"])
    ref_date = {key: pd.to_datetime(work.get("publication_date"), errors="coerce") for key, work in ref_works.items()}
    ref_count = {key: work.get("cited_by_count") for key, work in ref_works.items()}

    patent_dois = sorted(
        {
            doi
            for refs in out["patent_doi_references"].dropna()
            if isinstance(refs, list)
            for doi in refs
            if doi
        }
    )
    doi_works = client.works_by_dois(patent_dois, select=["id", "doi", "publication_date", "cited_by_count"])
    doi_date = {doi: pd.to_datetime(work.get("publication_date"), errors="coerce") for doi, work in doi_works.items()}
    doi_count = {doi: work.get("cited_by_count") for doi, work in doi_works.items()}

    def work_dates(refs: object) -> list[pd.Timestamp]:
        return [ref_date[x] for x in refs if x in ref_date and _valid_date(ref_date[x])] if isinstance(refs, list) else []

    def work_counts(refs: object) -> list[int]:
        return [int(ref_count[x]) for x in refs if x in ref_count and ref_count[x] is not None and not pd.isna(ref_count[x])] if isinstance(refs, list) else []

    def doi_dates(refs: object) -> list[pd.Timestamp]:
        return [doi_date[x] for x in refs if x in doi_date and _valid_date(doi_date[x])] if isinstance(refs, list) else []

    def doi_counts(refs: object) -> list[int]:
        return [int(doi_count[x]) for x in refs if x in doi_count and doi_count[x] is not None and not pd.isna(doi_count[x])] if isinstance(refs, list) else []

    out["work_reference_dates"] = out["work_referenced_works"].apply(work_dates)
    out["work_reference_age_days"] = out.apply(lambda r: _age_days(r["work_publication_date"], r["work_reference_dates"]), axis=1)
    out["mean_age_of_work_references"] = out["work_reference_age_days"].apply(_mean)
    out["work_reference_cited_by_counts"] = out["work_referenced_works"].apply(work_counts)
    out["work_reference_cited_by_counts_mean"] = out["work_reference_cited_by_counts"].apply(_mean)

    out["patent_reference_dates"] = out["patent_doi_references"].apply(doi_dates)
    out["patent_reference_age_days"] = out.apply(lambda r: _age_days(r["patent_filing_date"], r["patent_reference_dates"]), axis=1)
    out["mean_age_of_patent_references"] = out["patent_reference_age_days"].apply(_mean)
    out["patent_reference_cited_by_counts"] = out["patent_doi_references"].apply(doi_counts)
    out["patent_reference_cited_by_counts_mean"] = out["patent_reference_cited_by_counts"].apply(_mean)
    return out
