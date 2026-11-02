import builtins
import gzip
import json
import pathlib
import shutil

import pytest
import requests

import run_pipeline
from gender.gold import gender_counts
from geo.gold import country_stats, region_stats
from run_pipeline import STAGES, Paths, main, run
from shared.gold_combined import gender_by_region

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
GOLD_FILES = {
    "gender_yearly.json": gender_counts,
    "region_yearly.json": region_stats,
    "country_yearly.json": country_stats,
    "gender_by_region.json": gender_by_region,
}
FIXTURE_MAIN_TRACK_DOIS = {
    "10.1145/3377811.3380343",
    "10.1145/1806799.1806855",
    "10.1109/WICSA.2009.5290822",
    "10.1007/978-3-642-39031-9_31",
}


def _load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _as_json(data):
    # Gold functions may return tuples; compare the shape they're written in.
    return json.loads(json.dumps(data))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("network call in a test")

    monkeypatch.setattr(requests, "get", blocked)
    monkeypatch.setattr(requests.Session, "request", blocked)
    # Never pick up a developer's real .env
    monkeypatch.setattr(run_pipeline, "load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("GENDERIZE_API_KEY", raising=False)


@pytest.fixture
def paths(tmp_path):
    p = Paths.under(tmp_path)
    p.dblp.parent.mkdir(parents=True)
    shutil.copy(FIXTURES / "dblp_records.json", p.dblp)
    p.gender_cache.parent.mkdir(parents=True)
    shutil.copy(FIXTURES / "gender_lookup_sample.json", p.gender_cache)
    return p


@pytest.fixture
def fetched(monkeypatch):
    """Stub the OpenAlex fetch: copy fixture works into the cache instead."""
    calls = []

    def fake_fetch_works(dois, cache_dir):
        calls.append(list(dois))
        cache = pathlib.Path(cache_dir)
        cache.mkdir(parents=True, exist_ok=True)
        for f in (FIXTURES / "openalex_works").glob("*.json"):
            shutil.copy(f, cache / f.name)

    monkeypatch.setattr(run_pipeline, "fetch_works", fake_fetch_works)
    return calls


# ── end to end ────────────────────────────────────────────────────────────────


def test_full_run_on_fixtures_writes_expected_silver_and_gold(paths, fetched):
    run(paths=paths)

    expected_silver = _load(FIXTURES / "silver_rows.json")
    assert _load(paths.silver) == expected_silver
    assert paths.review_log.exists()
    for name, fn in GOLD_FILES.items():
        assert _load(paths.gold_dir / name) == _as_json(fn(expected_silver)), name


def test_stages_run_in_pipeline_order():
    assert STAGES == ("dblp", "main-track", "openalex", "genderize", "silver", "gold")


# ── single stages ─────────────────────────────────────────────────────────────


def test_gold_stage_alone_reads_silver_and_writes_only_gold(paths, fetched):
    paths.silver.parent.mkdir(parents=True)
    shutil.copy(FIXTURES / "silver_rows.json", paths.silver)

    run(["gold"], paths=paths)

    assert fetched == []
    assert sorted(p.name for p in paths.gold_dir.iterdir()) == sorted(GOLD_FILES)


def test_openalex_stage_fetches_only_main_track_dois_once(paths, fetched):
    run(["openalex"], paths=paths)

    [dois] = fetched
    assert len(dois) == len(set(dois))
    assert set(dois) == FIXTURE_MAIN_TRACK_DOIS


def test_main_track_stage_prints_counts(paths, capsys):
    run(["main-track"], paths=paths)

    out = capsys.readouterr().out
    assert "icse" in out and "2020" in out


# ── DBLP dump stage ───────────────────────────────────────────────────────────


@pytest.fixture
def dump(paths):
    paths.dump.write_bytes(gzip.compress((FIXTURES / "dblp" / "mini.xml").read_bytes()))
    shutil.copy(FIXTURES / "dblp" / "mini.dtd", paths.dtd)


def test_full_run_keeps_committed_dblp_data_by_default(paths, fetched, dump):
    before = paths.dblp.read_bytes()

    run(paths=paths)

    assert paths.dblp.read_bytes() == before


def test_refresh_dblp_refilters_the_dump(paths, dump):
    run(["dblp"], paths=paths)

    keys = {r["key"] for r in _load(paths.dblp)}
    assert "conf/icse/OCinneide20" in keys  # from mini.xml, not the fixture


def test_full_run_with_refresh_dblp_uses_the_dump(paths, fetched, dump):
    run(paths=paths, refresh_dblp=True)

    assert "conf/icse/OCinneide20" in {r["key"] for r in _load(paths.dblp)}


# ── Genderize: paid, so never sent without a yes ─────────────────────────────


@pytest.fixture
def new_author(paths):
    """Add a main-track author who is not in the Genderize cache."""
    records = _load(paths.dblp)
    records.append(
        {
            "record_type": "inproceedings",
            "key": "conf/icse/New20",
            "year": 2020,
            "title": "A paper by someone new.",
            "authors": ["Brand New Person"],
            "doi": "10.1145/3377811.9999999",
            "ee": None,
            "crossref": "conf/icse/2020",
            "booktitle": "ICSE",
        }
    )
    paths.dblp.write_text(json.dumps(records), encoding="utf-8")


def test_genderize_without_api_key_sends_nothing_and_continues(paths, new_author, capsys):
    before = _load(paths.gender_cache)

    run(["genderize"], paths=paths)

    assert _load(paths.gender_cache) == before
    assert "unknown" in capsys.readouterr().out


@pytest.mark.parametrize("answer", ["n", EOFError])
def test_genderize_keeps_confirmation_prompt(paths, new_author, monkeypatch, answer):
    monkeypatch.setenv("GENDERIZE_API_KEY", "test-key")
    prompts = []

    def fake_input(prompt=""):
        prompts.append(prompt)
        if answer is EOFError:
            raise EOFError
        return answer

    monkeypatch.setattr(builtins, "input", fake_input)
    before = _load(paths.gender_cache)

    run(["genderize"], paths=paths)

    assert len(prompts) == 1
    assert _load(paths.gender_cache) == before


# ── CLI ───────────────────────────────────────────────────────────────────────


def test_main_runs_a_single_stage(paths, monkeypatch):
    seen = []
    monkeypatch.setattr(run_pipeline, "run", lambda stages, **kw: seen.append(stages))

    main(["--stage", "gold"])

    assert seen == [["gold"]]


def test_main_rejects_unknown_stage(capsys):
    with pytest.raises(SystemExit):
        main(["--stage", "nope"])
    assert "invalid choice" in capsys.readouterr().err


def test_genderize_error_is_reported_and_run_continues(paths, new_author, fetched, monkeypatch, capsys):
    monkeypatch.setenv("GENDERIZE_API_KEY", "test-key")
    monkeypatch.setattr(builtins, "input", lambda prompt="": "y")

    def quota_reached(names, api_key):
        raise run_pipeline.GenderizeError("Genderize returned HTTP 429", status=429)

    monkeypatch.setattr("gender.genderize._fetch_batch", quota_reached)

    run(["genderize", "silver"], paths=paths)

    out = capsys.readouterr().out
    assert "quota" in out.lower()
    # Pending count is reported again after the error, for the next run
    assert out.count("names cached") == 2
    assert paths.silver.exists()
