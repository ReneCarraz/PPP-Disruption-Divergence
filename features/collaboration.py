"""Collaboration and assignee/institution type features."""

from __future__ import annotations

import pandas as pd

from openai_assignees import classify_assignees


COMPANY_CODES = {"2", "2.0", 2, 2.0, "3", "3.0", 3, 3.0}


def _company_list(types: object) -> list[int] | pd._libs.missing.NAType:
    if not isinstance(types, list):
        return pd.NA
    return [1 if t in COMPANY_CODES or str(t) in COMPANY_CODES else 0 for t in types]


def _all_indicator(xs: object) -> int | pd._libs.missing.NAType:
    if not isinstance(xs, list):
        return pd.NA
    return int(all(v == 1 for v in xs)) if xs else pd.NA


def _institution_type(types: object) -> str | None:
    if not isinstance(types, list):
        return None
    vals = set(types)
    if "company" in vals and "education" in vals:
        return "collab"
    if "company" in vals:
        return "company"
    if "education" in vals:
        return "education"
    if "other" in vals:
        return "other"
    return None


def add_collaboration_features(
    df: pd.DataFrame, *, openai_model: str = "gpt-5-mini", openai_batch_size: int = 20
) -> pd.DataFrame:
    out = df.copy()
    out["multiple_assignee"] = out["patent_assignee_names"].apply(
        lambda x: len(set(x)) > 1 if isinstance(x, list) else pd.NA
    )
    out["assignee_type_company_list"] = out["patent_assignee_types"].apply(_company_list)
    out["assignee_type_company"] = out["assignee_type_company_list"].apply(_all_indicator)

    out["multiple_author_institution"] = out["work_institution_names"].apply(
        lambda x: len(set(x)) > 1 if isinstance(x, list) else pd.NA
    )
    normalized_work_types = out["work_institution_types"].apply(
        lambda xs: [
            "company" if x == "company" else "education" if x == "education" else "other"
            for x in xs
        ]
        if isinstance(xs, list)
        else pd.NA
    )
    out["author_type"] = normalized_work_types.apply(_institution_type)

    unique_assignees = sorted(
        {
            str(name)
            for names in out["patent_assignee_names"].dropna()
            if isinstance(names, list)
            for name in names
            if name
        }
    )
    classifications = classify_assignees(
        unique_assignees, model=openai_model, batch_size=openai_batch_size
    )
    sector_map = dict(zip(classifications["patent_assignee"], classifications["sector"]))
    out["patent_assignee_sectors"] = out["patent_assignee_names"].apply(
        lambda xs: [sector_map.get(x) for x in xs] if isinstance(xs, list) else pd.NA
    )
    out["assignee_type_university_list"] = out["patent_assignee_sectors"].apply(
        lambda xs: [1 if x == "education" else 0 for x in xs] if isinstance(xs, list) else pd.NA
    )
    out["assignee_type_university"] = out["assignee_type_university_list"].apply(_all_indicator)
    return out
