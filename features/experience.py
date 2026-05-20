"""Author previous-experience features."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _first_last(authors: object, positions: object) -> list:
    if not isinstance(authors, list) or not authors:
        return []
    if isinstance(positions, list) and len(positions) == len(authors):
        selected = [a for a, p in zip(authors, positions) if p in {"first", "last"}]
        if selected:
            return selected
    return [authors[0]] if len(authors) == 1 else [authors[0], authors[-1]]


def add_previous_experience(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    sort_cols = [c for c in ["work_publication_date", "patent_date"] if c in out.columns]
    if not sort_cols:
        raise ValueError("experience: need work_publication_date and/or patent_date")
    ordered = out.sort_values(sort_cols).index

    seen_all: set = set()
    seen_fl: set = set()
    prev_all = {}
    prev_fl = {}

    for idx in ordered:
        authors = out.at[idx, "work_author_ids"]
        authors = authors if isinstance(authors, list) else []
        positions = out.at[idx, "work_author_positions"] if "work_author_positions" in out.columns else None

        prev_all[idx] = any(author in seen_all for author in authors) if authors else False
        seen_all.update(authors)

        first_last = _first_last(authors, positions)
        prev_fl[idx] = any(author in seen_fl for author in first_last) if first_last else False
        seen_fl.update(first_last)

    out["previous_experience"] = pd.Series(prev_all)
    out["previous_experience_first_last"] = pd.Series(prev_fl)
    return out
