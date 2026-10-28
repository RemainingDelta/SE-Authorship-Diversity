import json
from unittest.mock import MagicMock, patch

import pytest

from gender import genderize as mod

KNOWN = "Known Person"
KNOWN_ENTRY = {"gender": "female", "probability": 0.98, "count": 120}


def _new_names(n):
    return [f"New Person{i:02d}" for i in range(n)]


def _fake_get(url, params, timeout):
    """Answer like Genderize: one result per name[], in the order sent."""
    sent = [value for key, value in params if key == "name[]"]
    resp = MagicMock()
    resp.json.return_value = [
        {"name": name.split()[0], "gender": "male", "probability": 0.9, "count": 7}
        for name in sent
    ]
    return resp


def _sent_batches(get):
    return [
        [value for key, value in call.kwargs["params"] if key == "name[]"]
        for call in get.call_args_list
    ]


@pytest.fixture
def cache_path(tmp_path):
    path = tmp_path / "gender_lookup.json"
    path.write_text(json.dumps({KNOWN: KNOWN_ENTRY}), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch.object(mod.time, "sleep"):
        yield


def _cache(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_cached_names_are_never_sent(cache_path):
    with patch.object(mod.requests, "get", side_effect=_fake_get) as get:
        mod.lookup_new([KNOWN, "Ada Lovelace"], cache_path, "key", confirm=False)

    assert _sent_batches(get) == [["Ada Lovelace"]]
    assert _cache(cache_path)[KNOWN] == KNOWN_ENTRY


def test_names_are_sent_in_batches_of_10(cache_path):
    with patch.object(mod.requests, "get", side_effect=_fake_get) as get:
        result = mod.lookup_new(_new_names(25), cache_path, "key", confirm=False)

    assert [len(b) for b in _sent_batches(get)] == [10, 10, 5]
    assert result == {"new_names": 25, "looked_up": 25}


def test_cache_is_saved_after_each_batch(cache_path):
    # The second batch fails: the first batch must already be on disk,
    # so a re-run resumes instead of paying for those names again.
    calls = [_fake_get, RuntimeError("API down")]

    def get(url, params, timeout):
        step = calls.pop(0)
        if isinstance(step, Exception):
            raise step
        return step(url, params, timeout)

    with patch.object(mod.requests, "get", side_effect=get):
        with pytest.raises(RuntimeError):
            mod.lookup_new(_new_names(15), cache_path, "key", confirm=False)

    cache = _cache(cache_path)
    assert set(_new_names(10)) <= set(cache)
    assert not set(_new_names(15)[10:]) & set(cache)


def test_nothing_is_sent_if_confirmation_is_declined(cache_path):
    with (
        patch.object(mod.requests, "get") as get,
        patch("builtins.input", return_value="n") as ask,
    ):
        result = mod.lookup_new(_new_names(3), cache_path, "key")

    ask.assert_called_once()
    get.assert_not_called()
    assert result == {"new_names": 3, "looked_up": 0}
    assert _cache(cache_path) == {KNOWN: KNOWN_ENTRY}


def test_confirmed_run_sends_names(cache_path):
    with (
        patch.object(mod.requests, "get", side_effect=_fake_get) as get,
        patch("builtins.input", return_value="yes"),
    ):
        mod.lookup_new(_new_names(3), cache_path, "key")

    assert get.call_count == 1


def test_dry_run_returns_new_count_without_calling_api(cache_path):
    with (
        patch.object(mod.requests, "get") as get,
        patch("builtins.input") as ask,
    ):
        result = mod.lookup_new([KNOWN, *_new_names(4)], cache_path, None, dry_run=True)

    assert result == {"new_names": 4, "looked_up": 0}
    get.assert_not_called()
    ask.assert_not_called()


def test_names_are_cleaned_and_deduplicated(cache_path):
    # DBLP's same-name numbers are stripped by clean_name(), which is how
    # the cache is keyed; "Known Person 0001" is already paid for.
    names = [f"{KNOWN} 0001", "Ada Lovelace", "Ada Lovelace 0002", "O&apos;Brien Smith"]
    with patch.object(mod.requests, "get", side_effect=_fake_get) as get:
        mod.lookup_new(names, cache_path, "key", confirm=False)

    assert _sent_batches(get) == [["Ada Lovelace", "O'Brien Smith"]]


def test_results_are_keyed_by_the_name_sent(cache_path):
    # Genderize echoes back only the first name; the cache key must stay
    # the full cleaned name, or the same person is paid for on every run.
    with patch.object(mod.requests, "get", side_effect=_fake_get):
        mod.lookup_new(["Ada Lovelace"], cache_path, "key", confirm=False)

    assert _cache(cache_path)["Ada Lovelace"] == {
        "gender": "male",
        "probability": 0.9,
        "count": 7,
    }


def test_missing_cache_file_is_an_error(tmp_path):
    # Never start from an empty cache: that would re-buy every name.
    with patch.object(mod.requests, "get") as get:
        with pytest.raises(FileNotFoundError):
            mod.lookup_new(["Ada Lovelace"], tmp_path / "missing.json", "key", confirm=False)
    get.assert_not_called()


def test_missing_api_key_is_an_error_before_any_request(cache_path):
    with patch.object(mod.requests, "get") as get:
        with pytest.raises(ValueError):
            mod.lookup_new(["Ada Lovelace"], cache_path, None, confirm=False)
    get.assert_not_called()


def test_no_new_names_sends_nothing_and_does_not_ask(cache_path):
    with (
        patch.object(mod.requests, "get") as get,
        patch("builtins.input") as ask,
    ):
        result = mod.lookup_new([KNOWN], cache_path, "key")

    assert result == {"new_names": 0, "looked_up": 0}
    get.assert_not_called()
    ask.assert_not_called()


def test_committed_cache_is_the_gender_repo_cache():
    # Guards the paid-for cache from being regenerated or trimmed.
    cache = _cache(mod.DEFAULT_CACHE)
    assert len(cache) >= 10_822
    assert cache["A. T. M. Aerts"] == {"gender": "male", "probability": 0.59, "count": 94346}


def test_dblp_author_names_default_to_main_track(tmp_path):
    dblp = tmp_path / "dblp.json"
    dblp.write_text(
        json.dumps(
            [
                {"record_type": "inproceedings", "crossref": "conf/icse/2020", "authors": ["Main Author"]},
                {"record_type": "inproceedings", "crossref": "conf/icse/2020c", "authors": ["Companion Author"]},
                {"record_type": "proceedings", "crossref": None, "authors": []},
            ]
        ),
        encoding="utf-8",
    )

    assert mod.dblp_author_names(dblp) == ["Main Author"]
    assert mod.dblp_author_names(dblp, all_tracks=True) == ["Main Author", "Companion Author"]

