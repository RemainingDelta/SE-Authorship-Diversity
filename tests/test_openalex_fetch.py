import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from ingest import openalex_fetch as mod

DOI = "10.1109/ICSA.2023.001"


def _resp(status, payload=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload or {}
    return r


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch.object(mod.time, "sleep") as s:
        yield s


@pytest.fixture(autouse=True)
def _mailto(monkeypatch):
    monkeypatch.setenv("OPENALEX_MAILTO", "test@example.com")


def test_cached_dois_are_never_requested(tmp_path):
    path = mod._cache_path(tmp_path, DOI)
    path.write_text(json.dumps({"id": "W1"}))
    with patch.object(mod.requests, "get") as get:
        mod.fetch_works([DOI], cache_dir=tmp_path)
    get.assert_not_called()


def test_success_is_cached_with_mailto(tmp_path):
    with patch.object(mod.requests, "get", return_value=_resp(200, {"id": "W1"})) as get:
        mod.fetch_works([DOI], cache_dir=tmp_path)
    assert json.loads(mod._cache_path(tmp_path, DOI).read_text()) == {"id": "W1"}
    assert get.call_args.kwargs["params"]["mailto"] == "test@example.com"


@pytest.mark.parametrize("bad_status", [429, 500, 503])
def test_retryable_statuses_are_retried_with_backoff(tmp_path, _no_sleep, bad_status):
    responses = [_resp(bad_status), _resp(bad_status), _resp(200, {"id": "W1"})]
    with patch.object(mod.requests, "get", side_effect=responses) as get:
        mod.fetch_works([DOI], cache_dir=tmp_path)
    assert get.call_count == 3
    assert mod._cache_path(tmp_path, DOI).exists()
    waits = [c.args[0] for c in _no_sleep.call_args_list]
    assert waits[0] < waits[1]  # backoff grows


def test_retries_exhausted_is_logged_missing(tmp_path):
    with patch.object(mod.requests, "get", return_value=_resp(503)) as get:
        mod.fetch_works([DOI], cache_dir=tmp_path)
    assert get.call_count == mod.MAX_RETRIES + 1
    assert mod._normalize_doi(DOI) in (tmp_path / mod.MISSING_FILENAME).read_text()
    assert not mod._cache_path(tmp_path, DOI).exists()


def test_network_error_is_retried(tmp_path):
    side = [requests.ConnectionError("boom"), _resp(200, {"id": "W1"})]
    with patch.object(mod.requests, "get", side_effect=side):
        mod.fetch_works([DOI], cache_dir=tmp_path)
    assert mod._cache_path(tmp_path, DOI).exists()


def test_404_is_logged_to_missing_file(tmp_path):
    with patch.object(mod.requests, "get", return_value=_resp(404)) as get:
        mod.fetch_works([DOI], cache_dir=tmp_path)
    assert get.call_count == 1  # 404 is not retried
    assert mod._normalize_doi(DOI) in (tmp_path / mod.MISSING_FILENAME).read_text()
    assert not mod._cache_path(tmp_path, DOI).exists()


def test_cache_filename_is_safe_for_slashes(tmp_path):
    path = mod._cache_path(tmp_path, DOI)
    assert "/" not in path.name
    assert path.parent == tmp_path
    assert path.suffix == ".json"


def test_doi_url_prefix_is_normalized(tmp_path):
    assert mod._cache_path(tmp_path, f"https://doi.org/{DOI}") == mod._cache_path(tmp_path, DOI)


def test_missing_log_has_no_duplicates_across_runs(tmp_path):
    with patch.object(mod.requests, "get", return_value=_resp(404)):
        mod.fetch_works([DOI], cache_dir=tmp_path)
        mod.fetch_works([DOI], cache_dir=tmp_path)
    lines = (tmp_path / mod.MISSING_FILENAME).read_text().splitlines()
    assert len(lines) == 1


def test_waits_between_requests(tmp_path, _no_sleep):
    with patch.object(mod.requests, "get", return_value=_resp(200, {"id": "W"})):
        mod.fetch_works([DOI, "10.1109/ICSA.2023.002"], cache_dir=tmp_path)
    assert _no_sleep.call_count >= 2

def test_invalid_json_is_retried_then_logged(tmp_path):
    bad = _resp(200)
    bad.json.side_effect = ValueError("not json")
    with patch.object(mod.requests, "get", return_value=bad):
        mod.fetch_works([DOI], cache_dir=tmp_path)
    assert mod._normalize_doi(DOI) in (tmp_path / mod.MISSING_FILENAME).read_text()