"""Geographic distance features."""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import UsptoInputs
from features.openalex import institution_geo
from table_io import read_table
from openalex_client import OpenAlexClient


def _latlon_array(values: object) -> np.ndarray | None:
    if not isinstance(values, list):
        return None
    coords = []
    for value in values:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            continue
        lat, lon = value
        if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
            continue
        coords.append((float(lat), float(lon)))
    return np.array(coords, dtype=float) if coords else None


def _pairwise_haversine_km(a_values: object, b_values: object) -> np.ndarray | None:
    a = _latlon_array(a_values)
    b = _latlon_array(b_values)
    if a is None or b is None:
        return None
    lat1 = np.radians(a[:, 0])[:, None]
    lon1 = np.radians(a[:, 1])[:, None]
    lat2 = np.radians(b[:, 0])[None, :]
    lon2 = np.radians(b[:, 1])[None, :]
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 6371.0 * (2 * np.arcsin(np.sqrt(h)))


def add_geography(df: pd.DataFrame, inputs: UsptoInputs, client: OpenAlexClient) -> pd.DataFrame:
    out = df.copy()
    locations = read_table(inputs.locations_path, dtype=str)
    locations = locations.dropna(subset=["location_id"]).set_index("location_id")
    loc_map = locations.to_dict("index")

    def patent_latlons(ids: object) -> list[tuple[float, float]]:
        if not isinstance(ids, list):
            return []
        coords = []
        for loc_id in ids:
            rec = loc_map.get(str(loc_id))
            if not rec:
                continue
            lat = rec.get("latitude")
            lon = rec.get("longitude")
            if lat is not None and lon is not None and not pd.isna(lat) and not pd.isna(lon):
                coords.append((float(lat), float(lon)))
        return list(dict.fromkeys(coords))

    out["patent_assignee_latlon_list"] = out["patent_assignee_location_ids"].apply(patent_latlons)

    institution_ids = sorted(
        {
            str(inst_id)
            for ids in out["work_institution_ids"].dropna()
            if isinstance(ids, list)
            for inst_id in ids
            if inst_id
        }
    )
    geo_map = institution_geo(institution_ids, client)

    def work_latlons(ids: object) -> list[tuple[float, float]]:
        if not isinstance(ids, list):
            return []
        return list(dict.fromkeys(geo_map[inst_id] for inst_id in ids if inst_id in geo_map))

    out["work_latlon_list"] = out["work_institution_ids"].apply(work_latlons)
    out["geographical_distance"] = out.apply(
        lambda row: (
            float(np.mean(km))
            if (km := _pairwise_haversine_km(row["patent_assignee_latlon_list"], row["work_latlon_list"])) is not None
            else np.nan
        ),
        axis=1,
    )
    return out
