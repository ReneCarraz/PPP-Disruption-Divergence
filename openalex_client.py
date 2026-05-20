"""Small OpenAlex REST client used by the public pipeline."""

from __future__ import annotations

import json
import os
import time
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class OpenAlexClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        email: str | None = None,
        batch_size: int = 50,
        pause_seconds: float = 0.2,
        max_retries: int = 4,
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENALEX_API_KEY")
        self.email = email or os.environ.get("OPENALEX_EMAIL")
        if not self.api_key:
            raise EnvironmentError("OPENALEX_API_KEY is required")
        self.batch_size = min(batch_size, 100)
        self.pause_seconds = pause_seconds
        self.max_retries = max_retries
        self.timeout = timeout
        self.base_url = "https://api.openalex.org"

    def _get(self, endpoint: str, params: dict[str, object]) -> dict:
        payload = dict(params)
        payload["api_key"] = self.api_key
        if self.email:
            payload["mailto"] = self.email
        url = f"{self.base_url}/{endpoint.lstrip('/')}?{urlencode(payload)}"
        headers = {"User-Agent": f"mailto:{self.email}"} if self.email else {}

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                req = Request(url, headers=headers)
                with urlopen(req, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except Exception as exc:
                last_error = exc
                time.sleep(min(self.pause_seconds * (2**attempt), 10.0))
        raise RuntimeError(f"OpenAlex request failed after retries: {endpoint}") from last_error

    def list_by_openalex_ids(
        self, endpoint: str, ids: Iterable[str], *, select: list[str] | None = None
    ) -> dict[str, dict]:
        out: dict[str, dict] = {}
        cleaned = [str(x).rsplit("/", 1)[-1] for x in ids if x]
        for start in range(0, len(cleaned), self.batch_size):
            batch = cleaned[start : start + self.batch_size]
            if not batch:
                continue
            params: dict[str, object] = {
                "filter": "ids.openalex:" + "|".join(batch),
                "per-page": len(batch),
            }
            if select:
                params["select"] = ",".join(select)
            data = self._get(endpoint, params)
            for item in data.get("results", []):
                item_id = str(item.get("id", "")).rsplit("/", 1)[-1]
                if item_id:
                    out[item_id] = item
            time.sleep(self.pause_seconds)
        return out

    def works(self, work_ids: Iterable[str], *, select: list[str] | None = None) -> dict[str, dict]:
        return self.list_by_openalex_ids("works", work_ids, select=select)

    def sources(self, source_ids: Iterable[str], *, select: list[str] | None = None) -> dict[str, dict]:
        return self.list_by_openalex_ids("sources", source_ids, select=select)

    def institutions(
        self, institution_ids: Iterable[str], *, select: list[str] | None = None
    ) -> dict[str, dict]:
        return self.list_by_openalex_ids("institutions", institution_ids, select=select)

    def works_by_dois(self, dois: Iterable[str], *, select: list[str] | None = None) -> dict[str, dict]:
        out: dict[str, dict] = {}
        cleaned = [d for d in dois if d]
        for start in range(0, len(cleaned), self.batch_size):
            batch = cleaned[start : start + self.batch_size]
            params: dict[str, object] = {
                "filter": "doi:" + "|".join(batch),
                "per-page": len(batch),
            }
            if select:
                params["select"] = ",".join(select)
            data = self._get("works", params)
            for item in data.get("results", []):
                doi = item.get("doi")
                if doi:
                    out[str(doi).lower().removeprefix("https://doi.org/")] = item
            time.sleep(self.pause_seconds)
        return out
