"""Patent-paper pair input normalization and merge logic."""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import PairInputs
from table_io import normalize_patent_id, normalize_work_id, patent_id_us, read_table


def load_pairs(inputs: PairInputs) -> pd.DataFrame:
    primary = read_table(inputs.primary_pairs_path)
    reference = read_table(inputs.reference_pairs_path)

    primary = primary.copy()
    reference = reference.copy()

    if "model_classification" in primary.columns:
        primary = primary[
            primary["model_classification"].isna()
            | (primary["model_classification"] == 1)
        ]

    if "work_id" not in primary.columns and "paper_id" in primary.columns:
        primary["work_id"] = primary["paper_id"].map(normalize_work_id)
    if "paper_id" not in primary.columns:
        primary["paper_id"] = primary["work_id"].map(
            lambda x: normalize_work_id(x, full=False)
        )

    primary["patent_id"] = primary["patent_id"].map(normalize_patent_id)
    primary["patent_id_us"] = primary["patent_id"].map(patent_id_us)
    primary["paper_id"] = primary["paper_id"].map(
        lambda x: normalize_work_id(x, full=False)
    )
    primary["work_id"] = primary["paper_id"].map(normalize_work_id)
    primary["pair_id"] = (
        primary["paper_id"].astype("string")
        + "|"
        + primary["patent_id_us"].astype("string")
    )
    primary["source"] = 0

    if "paperid" in reference.columns:
        reference["paper_id"] = reference["paperid"].map(lambda x: normalize_work_id(x, full=False))
    elif "paper_id" in reference.columns:
        reference["paper_id"] = reference["paper_id"].map(lambda x: normalize_work_id(x, full=False))
    else:
        raise ValueError("Reference pairs must include `paperid` or `paper_id`")

    if "patent" in reference.columns:
        reference["patent_id_us"] = reference["patent"].astype("string").str.strip()
        reference["patent_id"] = reference["patent_id_us"].map(normalize_patent_id)
    elif "patent_id" in reference.columns:
        reference["patent_id"] = reference["patent_id"].map(normalize_patent_id)
        reference["patent_id_us"] = reference["patent_id"].map(patent_id_us)
    else:
        raise ValueError("Reference pairs must include `patent` or `patent_id`")

    reference["work_id"] = reference["paper_id"].map(normalize_work_id)
    reference["pair_id"] = reference["paper_id"].astype("string") + "|" + reference["patent_id_us"].astype("string")
    reference["source"] = 1
    daysdiff_lookup = None
    if "daysdiffcont" in reference.columns:
        daysdiff_lookup = reference[["pair_id", "daysdiffcont"]].drop_duplicates(
            subset=["pair_id"], keep="first"
        )

    overlap = set(primary["pair_id"].dropna()) & set(reference["pair_id"].dropna())
    paired = pd.concat([primary, reference], ignore_index=True, sort=False)
    paired.loc[paired["pair_id"].isin(overlap), "source"] = 2

    paired["pair_source"] = np.select(
        [paired["source"].eq(0), paired["source"].eq(1), paired["source"].eq(2)],
        ["primary_data", "reference_data", "both"],
        default=pd.NA,
    )
    paired = paired.sort_values("patent_date", ascending=False, na_position="last")
    paired = paired.drop_duplicates(subset=["pair_id"], keep="first").reset_index(drop=True)
    if daysdiff_lookup is not None:
        if "daysdiffcont" in paired.columns:
            paired = paired.drop(columns=["daysdiffcont"])
        paired = paired.merge(daysdiff_lookup, on="pair_id", how="left")
    return paired
