"""OpenAI-backed assignee classification."""

from __future__ import annotations

import os
from typing import Literal

import pandas as pd
from openai import OpenAI
from pydantic import BaseModel


class AssigneeClassification(BaseModel):
    assignee_name: str
    ownership: Literal["public", "private"]
    sector: Literal["education", "company", "other"]


class AssigneeClassificationBatch(BaseModel):
    classifications: list[AssigneeClassification]


SYSTEM_PROMPT = """Classify each institution/company on two dimensions:

1. Ownership ("public" or "private"):
- public: government agencies, public universities, national research institutes, publicly funded organizations
- private: corporations, private universities, private foundations, commercial enterprises

2. Sector ("education", "company", or "other"):
- education: universities, colleges, academic institutions
- company: corporations, businesses, commercial enterprises
- other: government agencies, research institutes, hospitals, foundations, non-profits

Return both classifications for each assignee."""


def classify_assignees(
    assignee_names: list[str], *, model: str = "gpt-5-mini", batch_size: int = 20
) -> pd.DataFrame:
    if not os.environ.get("OPENAI_API_KEY"):
        raise EnvironmentError("OPENAI_API_KEY is required for assignee classification")
    client = OpenAI()
    rows: list[dict] = []
    names = [str(name).strip() for name in assignee_names if str(name).strip()]

    for start in range(0, len(names), batch_size):
        batch = names[start : start + batch_size]
        completion = client.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "\n".join(f"- {name}" for name in batch)},
            ],
            response_format=AssigneeClassificationBatch,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("OpenAI returned no parsed assignee classifications")
        rows.extend(
            {
                "patent_assignee": item.assignee_name,
                "ownership": item.ownership,
                "sector": item.sector,
            }
            for item in parsed.classifications
        )

    return pd.DataFrame(rows).drop_duplicates(subset=["patent_assignee"], keep="last")
