"""Download raw OpenAlex work records into the bronze layer.

Network and caching only; parsing lives in a separate step.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

API_URL = "https://api.openalex.org/works/doi:{doi}"
MISSING_FILENAME = "missing_dois.txt"
REQUEST_DELAY = 0.2  # seconds between requests
MAX_RETRIES = 5
BACKOFF_BASE = 1.0  # seconds; doubles each retry
TIMEOUT = 30


def _normalize_doi(doi: str) -> str:
    doi = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        doi = doi.removeprefix(prefix)
    return doi


def _cache_path(cache_dir: str | Path, doi: str) -> Path:
    """Percent-encode the DOI so '/' never creates subdirectories."""
    return Path(cache_dir) / f"{quote(_normalize_doi(doi), safe='')}.json"


def _load_missing(missing_file: Path) -> set[str]:
    if not missing_file.exists():
        return set()
    return {
        line.split("\t")[0] for line in missing_file.read_text().splitlines() if line
    }


def _log_missing(missing_file: Path, known: set[str], doi: str, reason: str) -> None:
    logger.warning("DOI %s not cached: %s", doi, reason)
    if doi in known:
        return
    with missing_file.open("a", encoding="utf-8") as f:
        f.write(f"{doi}\t{reason}\n")
    known.add(doi)


def _fetch_one(doi: str, params: dict[str, str]) -> tuple[dict | None, str]:
    """Return (record, "") on success or (None, reason) on failure."""
    url = API_URL.format(doi=doi)
    reason = ""
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
            if resp.status_code == 200:
                return resp.json(), ""
        except (requests.RequestException, ValueError) as exc:
            reason = type(exc).__name__
        else:
            reason = str(resp.status_code)
            if resp.status_code != 429 and resp.status_code < 500:
                return None, reason  # 404 and other non-retryable codes
        if attempt < MAX_RETRIES:
            time.sleep(BACKOFF_BASE * 2**attempt)
    return None, f"{reason} (retries exhausted)"


def fetch_works(
    dois: list[str], cache_dir: str | Path = "data/bronze/openalex"
) -> None:
    """Cache the raw OpenAlex record for each DOI; log DOIs that can't be fetched."""
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    missing_file = cache / MISSING_FILENAME
    known_missing = _load_missing(missing_file)

    mailto = os.getenv("OPENALEX_MAILTO")
    params = {"mailto": mailto} if mailto else {}
    if not mailto:
        logger.warning("OPENALEX_MAILTO is not set; requests use the common pool")

    for raw in dois:
        doi = _normalize_doi(raw)
        path = _cache_path(cache, doi)
        if path.exists():
            continue

        record, reason = _fetch_one(doi, params)
        if record is None:
            _log_missing(missing_file, known_missing, doi, reason)
        else:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(record), encoding="utf-8")
            tmp.replace(path)  # atomic: no half-written cache files
        time.sleep(REQUEST_DELAY)
