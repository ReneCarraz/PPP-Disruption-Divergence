# Disruption Is Not Intrinsic: Evidence from Patent–Paper Pairs

Carraz, René and Nguyen, Van-Thien (Dorothie) and Pelletier, Pierre and Yang, Alex Jie and Higham, Kyle, Disruption Is Not Intrinsic: Evidence from Patent–Paper Pairs. 
Available at SSRN: https://ssrn.com/abstract=6811561 or http://dx.doi.org/10.2139/ssrn.6811561

This project builds a compact patent-paper-pair feature dataset for studying
how scientific research and patented technology diverge.

(*) This research was supported by JSPS KAKENHI Grant Number 24K05092.

## Run

```bash
uv run python -m run_pipeline --config config.toml
```

Required environment variables:

```bash
export OPENALEX_API_KEY="..."
export OPENALEX_EMAIL="you@example.org"
export OPENAI_API_KEY="..."
```

The run writes:

- compact CSV
- compact Parquet

## Config

Example `config.toml`:

```toml
[pairs]
primary_pairs_path = "data/pairs/primary_pairs.parquet"
reference_pairs_path = "data/pairs/reference_pairs.csv"

[uspto]
inventors_path = "data/uspto/inventors.parquet"
patents_path = "data/uspto/patents.parquet"
g_patent_path = "data/uspto/g_patent.tsv"
assignees_path = "data/uspto/g_assignee_disambiguated.tsv"
locations_path = "data/uspto/g_location_disambiguated.tsv"
wipo_technology_path = "data/uspto/g_wipo_technology.tsv"
ipc_at_issue_path = "data/uspto/g_ipc_at_issue.tsv"
claims_tsv_glob = "data/uspto/claims/g_claims_*.tsv"

[references]
patent_references_path = "data/patent_references.parquet"
other_reference_path = "data/uspto/g_other_reference.tsv"
us_patent_citation_path = "data/uspto/g_us_patent_citation.tsv"
foreign_citation_path = "data/uspto/g_foreign_citation.tsv"

[classification]
ipc_technology_xlsx = "data/ipc_technology.xlsx"

[outputs]
compact_csv = "outputs/compact_result.csv"
compact_parquet = "outputs/compact_result.parquet"

[runtime]
openai_model = "gpt-5-mini"
openalex_batch_size = 50
openalex_pause_seconds = 0.2
openai_batch_size = 20
uspto_reference_chunksize = 2000000
```

## Expected Inputs

PPP inputs:

- Primary pair table: `patent_id`, `work_id` or `paper_id`; optional
  `model_classification`, patent/work text, dates, and `daysdiffcont`.
- Reference pair table: `paperid` or `paper_id`, plus `patent` or
  `patent_id`; optional `daysdiffcont`.

USPTO/PatentsView-style inputs:

- Inventors: `patent_id`, one row per inventor.
- Patents: `patent_id`, `patent_date`, `patent_filing_date`,
  `patent_assignee_country`.
- Patent text: `patent_id`, `patent_title`, `patent_abstract`.
- Assignees: `patent_id`, `disambig_assignee_organization` or `assignee`,
  `assignee_type`, `location_id`.
- Locations: `location_id`, `latitude`, `longitude`.
- WIPO: `patent_id`, `wipo_field_id`, `wipo_sector_title` or `wipo_sector`,
  `wipo_field_title`.
- IPC: `patent_id`, `section`, `ipc_class`.
- Claims: `patent_id`, `claim_sequence`, `claim_text`, `dependent`.
- Patent references: `patent` or `patent_id`, plus DOI and/or OpenAlex
  reference ID columns.
- USPTO non-patent references: `patent_id`, one row per referenced item.
- USPTO US patent citations: `patent_id`, one row per cited patent.
- USPTO foreign patent citations: `patent_id`, one row per cited patent.

OpenAlex data is fetched from the REST API for works, sources, institutions,
reference works, topics, authorships, and source impact.

## Output Schema

The compact output contains 45 columns in the order defined in `schema.py`.
Use `author_team_size` and `inventor_team_size` for paper and patent team size.
