"""Tests for the pure OpenAlex work parser."""

import json
from pathlib import Path

from ingest.openalex_parse import parse_work

FIXTURES = Path(__file__).parent / "fixtures" / "openalex_works"

NORMAL = "10.1145%2F3377811.3380343.json"
MULTI_AFFILIATION = "10.1145%2F1806799.1806855.json"
NO_INSTITUTION = "10.1007%2F978-3-642-39031-9_31.json"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_normal_paper():
    work = _load(NORMAL)
    parsed = parse_work(work)

    assert parsed["doi"] == "10.1145/3377811.3380343"
    assert parsed["primary_topic"] == work["primary_topic"]["display_name"]
    assert len(parsed["authorships"]) == len(work["authorships"])
    for i, (out, src) in enumerate(zip(parsed["authorships"], work["authorships"])):
        assert out["author_position"] == i
        assert out["openalex_name"] == src["author"]["display_name"]
        assert set(out) == {"author_position", "openalex_name", "affiliations"}
        for aff in out["affiliations"]:
            assert set(aff) == {"institution", "country_code"}


def test_multiple_affiliations_preserve_order():
    work = _load(MULTI_AFFILIATION)
    parsed = parse_work(work)

    src = next(a for a in work["authorships"] if len(a["institutions"]) > 1)
    out = parsed["authorships"][work["authorships"].index(src)]
    assert [a["institution"] for a in out["affiliations"]] == [
        i["display_name"] for i in src["institutions"]
    ]
    assert [a["country_code"] for a in out["affiliations"]] == [
        i["country_code"] for i in src["institutions"]
    ]


def test_author_without_institution_has_empty_list():
    work = _load(NO_INSTITUTION)
    parsed = parse_work(work)

    idx = next(i for i, a in enumerate(work["authorships"]) if not a["institutions"])
    assert parsed["authorships"][idx]["affiliations"] == []


def test_missing_primary_topic_is_none():
    work = _load(NORMAL)
    work["primary_topic"] = None
    parsed = parse_work(work)
    assert parsed["primary_topic"] is None


def test_does_not_mutate_input():
    work = _load(NORMAL)
    before = json.dumps(work, sort_keys=True)
    parse_work(work)
    assert json.dumps(work, sort_keys=True) == before


def test_author_position_is_index_not_openalex_label():
    # OpenAlex labels every middle author "middle"; silver needs the index.
    parsed = parse_work(_load(MULTI_AFFILIATION))
    assert [a["author_position"] for a in parsed["authorships"]] == [0, 1, 2]


def test_doi_is_bare_and_lowercased():
    work = _load(NORMAL)
    work["doi"] = "https://doi.org/10.1109/ICSA.2017.24"
    assert parse_work(work)["doi"] == "10.1109/icsa.2017.24"


def test_missing_doi_is_none():
    work = _load(NORMAL)
    work["doi"] = None
    assert parse_work(work)["doi"] is None
