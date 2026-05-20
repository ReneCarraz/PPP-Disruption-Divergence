"""Patent technology classification features."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import UsptoInputs
from table_io import normalize_patent_id, read_table


def _ipc_class(value: object) -> str:
    s = str(value).strip().lstrip("0") or "0"
    try:
        return str(int(s)).zfill(2)
    except ValueError:
        return s


def add_wipo_ipc(df: pd.DataFrame, inputs: UsptoInputs) -> pd.DataFrame:
    wipo = read_table(inputs.wipo_technology_path, dtype=str)
    wipo["patent_id"] = wipo["patent_id"].map(normalize_patent_id)
    sector_col = "wipo_sector_title" if "wipo_sector_title" in wipo.columns else "wipo_sector"
    field_col = "wipo_field_title"
    wipo["wipo_key"] = (
        wipo[sector_col].astype(str) + " " + wipo["wipo_field_id"].astype(str) + " " + wipo[field_col].astype(str)
    )
    wipo_grouped = (
        wipo.groupby("patent_id")["wipo_key"]
        .agg(lambda vals: "; ".join(sorted(set(v for v in vals if pd.notna(v)))))
        .rename("wipo_fields")
        .reset_index()
    )

    ipc = read_table(inputs.ipc_at_issue_path, dtype=str)
    ipc["patent_id"] = ipc["patent_id"].map(normalize_patent_id)
    ipc["ipc_code"] = ipc["section"].astype(str) + "_" + ipc["ipc_class"].map(_ipc_class)
    ipc_grouped = (
        ipc.groupby("patent_id")["ipc_code"]
        .agg(lambda vals: sorted(set(v for v in vals if pd.notna(v))))
        .rename("ipc_codes")
        .reset_index()
    )
    return df.drop(columns=["wipo_fields", "ipc_codes"], errors="ignore").merge(
        wipo_grouped, on="patent_id", how="left"
    ).merge(ipc_grouped, on="patent_id", how="left")


def _to_underscore(class_code: str) -> str:
    return f"{class_code[0]}_{class_code[1:]}"


def add_ipc_sectors(df: pd.DataFrame, mapping_path: str | Path) -> pd.DataFrame:
    ipc = pd.read_excel(mapping_path, skiprows=6, dtype={"IPC_code": str})
    ipc = ipc.dropna(subset=["IPC_code", "Sector_en"]).copy()
    ipc["class_code"] = ipc["IPC_code"].str.extract(r"^([A-H]\d{2})", expand=False)
    ipc = ipc.dropna(subset=["class_code"])
    sector_map = {
        _to_underscore(code): " / ".join(sorted(set(values)))
        for code, values in ipc.groupby("class_code")["Sector_en"]
    }

    def map_codes(codes: object) -> list[str | None]:
        if not isinstance(codes, list):
            return []
        return [sector_map.get(str(code)) for code in codes]

    out = df.copy()
    out["ipc_sectors"] = out["ipc_codes"].apply(map_codes)
    return out
