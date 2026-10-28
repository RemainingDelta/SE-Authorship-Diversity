import json
import logging
import pathlib

import pytest
from geo.affiliation import primary_region
from ingest.openalex_parse import parse_work
from shared.build_silver import build_rows
from shared.name_match import names_match

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def dblp():
    return _load("dblp_records.json")


@pytest.fixture
def works():
    return [
        parse_work(json.loads(p.read_text(encoding="utf-8")))
        for p in sorted((FIXTURES / "openalex_works").glob("*.json"))
    ]


@pytest.fixture
def gender_lookup():
    return _load("gender_lookup_sample.json")


def _build(dblp, works, gender_lookup, **kwargs):
    return build_rows(dblp, works, gender_lookup, names_match, primary_region, **kwargs)


def _paper(key, crossref, authors, doi="10.1/x"):
    return {
        "record_type": "inproceedings",
        "key": key,
        "year": int(crossref.split("/")[2][:4]),
        "title": f"Paper {key}.",
        "authors": authors,
        "crossref": crossref,
        "doi": doi,
    }


def _work(doi, names, countries):
    return {
        "doi": doi.lower(),
        "primary_topic": "Topic",
        "authorships": [
            {
                "author_position": i,
                "openalex_name": name,
                "affiliations": [{"institution": f"Uni {code}", "country_code": code}],
            }
            for i, (name, code) in enumerate(zip(names, countries))
        ],
    }


def test_fixtures_build_the_expected_silver_rows(dblp, works, gender_lookup):
    assert _build(dblp, works, gender_lookup) == _load("silver_rows.json")


def test_position_mismatch_when_openalex_order_differs(dblp, works, gender_lookup):
    # The WICSA 2009 fixture lists the two authors in the opposite order.
    rows = [r for r in _build(dblp, works, gender_lookup) if r["year"] == 2009]

    assert [(r["author_name"], r["position_mismatch"]) for r in rows] == [
        ("Qing Gu", True),
        ("Patricia Lago", True),
    ]


def test_no_matching_name_is_a_mismatch_with_no_affiliations():
    record = _paper("conf/icse/A20", "conf/icse/2020", ["Ada Lovelace", "Alan Turing"])
    work = _work("10.1/x", ["Ada Lovelace", "Grace Hopper"], ["GB", "US"])

    rows = build_rows([record], [work], {}, names_match, primary_region)

    assert rows[0]["position_mismatch"] is False
    assert rows[1]["position_mismatch"] is True
    assert rows[1]["affiliations"] == []
    assert rows[1]["region"] == "unknown"


def test_mismatched_rows_keep_dblp_name_and_position(tmp_path):
    # Never auto-correct: DBLP's name and order stay; only the flag is set.
    record = _paper("conf/icse/A20", "conf/icse/2020", ["Ada Lovelace", "Alan Turing"])
    work = _work("10.1/x", ["Alan Turing", "Ada Lovelace"], ["GB", "US"])

    rows = build_rows([record], [work], {}, names_match, primary_region)

    assert [(r["author_name"], r["author_position"]) for r in rows] == [
        ("Ada Lovelace", 0),
        ("Alan Turing", 1),
    ]
    assert [r["country_code"] for r in rows] == ["US", "GB"]


def test_mismatched_rows_go_to_review_log(dblp, works, gender_lookup, tmp_path):
    log = tmp_path / "review.jsonl"

    rows = _build(dblp, works, gender_lookup, review_log=log)

    entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    flagged = [r for r in rows if r["position_mismatch"]]
    assert [(e["doi"], e["author_position"]) for e in entries] == [
        (r["doi"], r["author_position"]) for r in flagged
    ]
    assert entries[0]["openalex_names"] == ["Patricia Lago", "Qing Gu"]


@pytest.mark.parametrize(
    "crossref,joint",
    [
        ("conf/wicsa/2009", True),
        ("conf/wicsa/2012", True),
        ("conf/wicsa/2011", False),
        ("conf/ecsa/2012", False),
        ("conf/icsa/2017", False),
    ],
)
def test_joint_flag_only_for_wicsa_2009_and_2012(crossref, joint):
    rows = build_rows(
        [_paper("k", crossref, ["Ada Lovelace"], doi=None)],
        [],
        {},
        names_match,
        primary_region,
    )
    assert rows[0]["joint_wicsa_ecsa"] is joint


def test_wicsa_maps_to_icsa():
    rows = build_rows(
        [_paper("k", "conf/wicsa/2011", ["Ada Lovelace"], doi=None)],
        [],
        {},
        names_match,
        primary_region,
    )
    assert rows[0]["venue"] == "ICSA"


def test_non_main_track_records_get_no_rows(dblp, works, gender_lookup):
    titles = {r["title"] for r in _build(dblp, works, gender_lookup)}
    companion = [r["title"] for r in dblp if r["crossref"] == "conf/icse/2020c"]
    assert companion and not titles & set(companion)


def test_no_doi_rows_are_kept_and_logged(dblp, works, gender_lookup, caplog):
    # SCHEMA.md: no-DOI papers keep their rows so their authors still count
    # for gender; they're logged because they can't get affiliations.
    with caplog.at_level(logging.WARNING, logger="shared.build_silver"):
        rows = _build(dblp, works, gender_lookup)

    no_doi = [r for r in rows if r["doi"] is None]
    assert [r["author_name"] for r in no_doi] == ["Colin Paterson", "Radu Calinescu"]
    assert all(r["affiliations"] == [] and r["region"] == "unknown" for r in no_doi)
    assert "conf/icsa/PatersonC17" in caplog.text


def test_matcher_and_region_fn_are_injected():
    record = _paper("conf/icse/A20", "conf/icse/2020", ["Ada Lovelace"])
    work = _work("10.1/x", ["Someone Else"], ["GB"])

    rows = build_rows(
        [record], [work], {}, lambda a, b: True, lambda affs: ("ZZ", "Stand-in")
    )

    assert rows[0]["position_mismatch"] is False
    assert (rows[0]["country_code"], rows[0]["region"]) == ("ZZ", "Stand-in")


def test_gender_is_looked_up_by_cleaned_name():
    record = _paper("conf/icse/A20", "conf/icse/2020", ["Ada Lovelace 0001"])
    lookup = {"Ada Lovelace": {"gender": "female", "probability": 0.95, "count": 3}}

    row = build_rows([record], [], lookup, names_match, primary_region)[0]

    assert row["author_name"] == "Ada Lovelace"
    assert (row["gender_label"], row["gender_confidence"]) == ("female-presenting", 0.95)
