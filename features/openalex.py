"""OpenAlex enrichment features."""

from __future__ import annotations

import pandas as pd

from table_io import normalize_work_id
from openalex_client import OpenAlexClient


WORK_SELECT = [
    "id",
    "doi",
    "title",
    "display_name",
    "publication_date",
    "primary_location",
    "authorships",
    "abstract_inverted_index",
    "referenced_works",
    "primary_topic",
]


def reconstruct_abstract(index: object) -> str | None:
    if not isinstance(index, dict) or not index:
        return None
    words = []
    for word, positions in index.items():
        for pos in positions or []:
            words.append((pos, word))
    return " ".join(word for _, word in sorted(words)) if words else None


def _short_id(value: object) -> str | None:
    return str(value).rsplit("/", 1)[-1] if value else None


def fetch_openalex_enrichment(df: pd.DataFrame, client: OpenAlexClient) -> tuple[pd.DataFrame, dict[str, dict]]:
    work_ids = sorted({normalize_work_id(x, full=False) for x in df["work_id"].dropna()})
    works = client.works(work_ids, select=WORK_SELECT)
    rows = []
    source_ids = []
    for short_id, work in works.items():
        source = ((work.get("primary_location") or {}).get("source") or {})
        source_id = _short_id(source.get("id"))
        if source_id:
            source_ids.append(source_id)
        topic = work.get("primary_topic") or {}
        subfield = topic.get("subfield") or {}
        field = topic.get("field") or {}
        domain = topic.get("domain") or {}
        authorships = work.get("authorships") or []
        institution_ids = []
        institution_names = []
        institution_types = []
        institution_country_codes = []
        author_ids = []
        author_positions = []
        for authorship in authorships:
            author = authorship.get("author") or {}
            author_id = _short_id(author.get("id"))
            if author_id:
                author_ids.append(author_id)
                author_positions.append(authorship.get("author_position"))
            for inst in authorship.get("institutions") or []:
                if inst.get("id"):
                    institution_ids.append(_short_id(inst.get("id")))
                if inst.get("display_name"):
                    institution_names.append(inst.get("display_name"))
                if inst.get("type"):
                    institution_types.append(inst.get("type"))
                if inst.get("country_code"):
                    institution_country_codes.append(inst.get("country_code"))
        rows.append(
            {
                "work_id": f"https://openalex.org/{short_id}",
                "paper_id": short_id,
                "work_doi": work.get("doi"),
                "work_title": work.get("title") or work.get("display_name"),
                "work_abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
                "work_publication_date": work.get("publication_date"),
                "work_referenced_works": [_short_id(x) for x in work.get("referenced_works") or [] if x],
                "work_author_ids": author_ids,
                "work_author_positions": author_positions,
                "work_institution_ids": list(dict.fromkeys(institution_ids)),
                "work_institution_names": list(dict.fromkeys(institution_names)),
                "work_institution_types": list(dict.fromkeys(institution_types)),
                "institution_country_codes": sorted(set(institution_country_codes)),
                "primary_topic_display_name": topic.get("display_name"),
                "primary_subfield_display_name": subfield.get("display_name"),
                "primary_field_display_name": field.get("display_name"),
                "primary_domain_display_name": domain.get("display_name"),
                "_source_id": source_id,
            }
        )

    works_df = pd.DataFrame(rows)
    if works_df.empty:
        return df, works

    sources = client.sources(sorted(set(source_ids)), select=["id", "summary_stats"])
    impact = {
        sid: (src.get("summary_stats") or {}).get("2yr_mean_citedness")
        for sid, src in sources.items()
    }
    works_df["journal_impact"] = works_df["_source_id"].map(impact)
    works_df = works_df.drop(columns=["_source_id"])

    drop_cols = [c for c in works_df.columns if c in df.columns and c not in {"work_id", "paper_id"}]
    out = df.drop(columns=drop_cols, errors="ignore").merge(works_df, on=["work_id", "paper_id"], how="left")
    out["work_publication_date"] = pd.to_datetime(out["work_publication_date"], errors="coerce")
    return out, works


def institution_geo(
    institution_ids: list[str], client: OpenAlexClient
) -> dict[str, tuple[float, float]]:
    institutions = client.institutions(institution_ids, select=["id", "geo"])
    out: dict[str, tuple[float, float]] = {}
    for inst_id, inst in institutions.items():
        geo = inst.get("geo") or {}
        lat = geo.get("latitude")
        lon = geo.get("longitude")
        if lat is not None and lon is not None:
            out[inst_id] = (float(lat), float(lon))
    return out
