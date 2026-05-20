"""CLI entrypoint for the compact PPP pipeline."""

from __future__ import annotations

import argparse
import numpy as np
import pandas as pd

from config import PipelineConfig
from features.classification import add_ipc_sectors, add_wipo_ipc
from features.collaboration import add_collaboration_features
from features.experience import add_previous_experience
from features.export import add_final_dates, prepare_final_export, write_outputs
from features.geography import add_geography
from features.openalex import fetch_openalex_enrichment
from features.pairs import load_pairs
from features.references import add_reference_features
from features.uspto import add_uspto_features
from openalex_client import OpenAlexClient
from text_scores import semantic_similarity_score, word_overlap_score


def add_text_similarity(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["title_word_overlap_score"] = out.apply(
        lambda row: word_overlap_score(row.get("patent_title"), row.get("work_title")),
        axis=1,
    )
    out["abstract_word_overlap_score"] = out.apply(
        lambda row: word_overlap_score(row.get("patent_abstract"), row.get("work_abstract")),
        axis=1,
    )
    out["word_overlap_score"] = out[
        ["title_word_overlap_score", "abstract_word_overlap_score"]
    ].mean(axis=1)

    out["title_semantic_similarity_score"] = out.apply(
        lambda row: semantic_similarity_score(row.get("patent_title"), row.get("work_title")),
        axis=1,
    )
    out["abstract_semantic_similarity_score"] = out.apply(
        lambda row: semantic_similarity_score(row.get("patent_abstract"), row.get("work_abstract")),
        axis=1,
    )
    out["semantic_similarity_score"] = out[
        ["title_semantic_similarity_score", "abstract_semantic_similarity_score"]
    ].mean(axis=1)
    return out


def add_basic_counts_and_international(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["author_team_size"] = out["work_author_ids"].apply(
        lambda x: len(x) if isinstance(x, list) else np.nan
    )
    out["team_size_difference"] = out["author_team_size"] - out["inventor_team_size"]

    def countries(row) -> list[str]:
        codes = set()
        inst_codes = row.get("institution_country_codes")
        if isinstance(inst_codes, list):
            codes.update(c for c in inst_codes if c)
        country = row.get("patent_assignee_country")
        if isinstance(country, str) and country:
            codes.add(country)
        return sorted(codes)

    out["collab_countries"] = out.apply(countries, axis=1)
    out["international_collab"] = out["collab_countries"].apply(
        lambda xs: int(len(xs) > 1) if xs else pd.NA
    )
    return out


def run_pipeline(config: PipelineConfig | str) -> dict[str, object]:
    if isinstance(config, (str, bytes)):
        config = PipelineConfig.from_toml(config)
    config.validate_paths()

    openalex = OpenAlexClient(
        batch_size=config.openalex_batch_size,
        pause_seconds=config.openalex_pause_seconds,
    )

    df = load_pairs(config.pairs)
    df = add_uspto_features(df, config.uspto)
    df, _works = fetch_openalex_enrichment(df, openalex)
    df = add_basic_counts_and_international(df)
    df = add_text_similarity(df)
    df = add_reference_features(
        df,
        config.references,
        openalex,
        uspto_reference_chunksize=config.uspto_reference_chunksize,
    )
    df = add_collaboration_features(
        df,
        openai_model=config.openai_model,
        openai_batch_size=config.openai_batch_size,
    )
    df = add_wipo_ipc(df, config.uspto)
    df = add_ipc_sectors(df, config.classification.ipc_technology_xlsx)
    df = add_geography(df, config.uspto, openalex)
    df = add_previous_experience(df)
    df = add_final_dates(df)
    final = prepare_final_export(df)
    outputs = write_outputs(
        final,
        csv_path=config.outputs.compact_csv,
        parquet_path=config.outputs.compact_parquet,
    )
    return {"rows": len(final), "columns": len(final.columns), "outputs": outputs}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the compact PPP dataset.")
    parser.add_argument("--config", required=True, help="Path to config.toml")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_pipeline(PipelineConfig.from_toml(args.config))
    print(
        "Wrote compact PPP dataset: "
        f"{result['rows']:,} rows x {result['columns']} columns"
    )
    for label, path in result["outputs"].items():
        print(f"  {label}: {path}")


if __name__ == "__main__":
    main()
