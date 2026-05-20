"""Configuration loading for the compact PPP pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class PairInputs:
    primary_pairs_path: Path
    reference_pairs_path: Path


@dataclass(frozen=True)
class UsptoInputs:
    inventors_path: Path
    patents_path: Path
    g_patent_path: Path
    assignees_path: Path
    locations_path: Path
    wipo_technology_path: Path
    ipc_at_issue_path: Path
    claims_tsv_glob: str


@dataclass(frozen=True)
class ReferenceInputs:
    patent_references_path: Path
    other_reference_path: Path
    us_patent_citation_path: Path
    foreign_citation_path: Path


@dataclass(frozen=True)
class ClassificationInputs:
    ipc_technology_xlsx: Path


@dataclass(frozen=True)
class OutputPaths:
    compact_csv: Path
    compact_parquet: Path


@dataclass(frozen=True)
class PipelineConfig:
    pairs: PairInputs
    uspto: UsptoInputs
    references: ReferenceInputs
    classification: ClassificationInputs
    outputs: OutputPaths
    openai_model: str = "gpt-5-mini"
    openalex_batch_size: int = 50
    openalex_pause_seconds: float = 0.2
    openai_batch_size: int = 20
    uspto_reference_chunksize: int = 2_000_000

    @classmethod
    def from_toml(cls, path: str | Path) -> "PipelineConfig":
        config_path = Path(path)
        with config_path.open("rb") as fh:
            raw = tomllib.load(fh)

        def section(name: str) -> dict:
            value = raw.get(name)
            if not isinstance(value, dict):
                raise ValueError(f"Missing [{name}] section in {config_path}")
            return value

        pairs = section("pairs")
        uspto = section("uspto")
        references = section("references")
        classification = section("classification")
        outputs = section("outputs")
        runtime = raw.get("runtime", {})

        return cls(
            pairs=PairInputs(
                primary_pairs_path=Path(pairs["primary_pairs_path"]),
                reference_pairs_path=Path(pairs["reference_pairs_path"]),
            ),
            uspto=UsptoInputs(
                inventors_path=Path(uspto["inventors_path"]),
                patents_path=Path(uspto["patents_path"]),
                g_patent_path=Path(uspto["g_patent_path"]),
                assignees_path=Path(uspto["assignees_path"]),
                locations_path=Path(uspto["locations_path"]),
                wipo_technology_path=Path(uspto["wipo_technology_path"]),
                ipc_at_issue_path=Path(uspto["ipc_at_issue_path"]),
                claims_tsv_glob=str(uspto["claims_tsv_glob"]),
            ),
            references=ReferenceInputs(
                patent_references_path=Path(references["patent_references_path"]),
                other_reference_path=Path(references["other_reference_path"]),
                us_patent_citation_path=Path(references["us_patent_citation_path"]),
                foreign_citation_path=Path(references["foreign_citation_path"]),
            ),
            classification=ClassificationInputs(
                ipc_technology_xlsx=Path(classification["ipc_technology_xlsx"]),
            ),
            outputs=OutputPaths(
                compact_csv=Path(outputs["compact_csv"]),
                compact_parquet=Path(outputs["compact_parquet"]),
            ),
            openai_model=str(runtime.get("openai_model", "gpt-5-mini")),
            openalex_batch_size=int(runtime.get("openalex_batch_size", 50)),
            openalex_pause_seconds=float(runtime.get("openalex_pause_seconds", 0.2)),
            openai_batch_size=int(runtime.get("openai_batch_size", 20)),
            uspto_reference_chunksize=int(
                runtime.get("uspto_reference_chunksize", 2_000_000)
            ),
        )

    def input_paths(self) -> list[Path]:
        return [
            self.pairs.primary_pairs_path,
            self.pairs.reference_pairs_path,
            self.uspto.inventors_path,
            self.uspto.patents_path,
            self.uspto.g_patent_path,
            self.uspto.assignees_path,
            self.uspto.locations_path,
            self.uspto.wipo_technology_path,
            self.uspto.ipc_at_issue_path,
            self.references.patent_references_path,
            self.references.other_reference_path,
            self.references.us_patent_citation_path,
            self.references.foreign_citation_path,
            self.classification.ipc_technology_xlsx,
        ]

    def validate_paths(self) -> None:
        missing = [str(path) for path in self.input_paths() if not path.exists()]
        if missing:
            raise FileNotFoundError("Missing configured input files: " + ", ".join(missing))
