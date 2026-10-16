"""Checks the shared sample data against the silver schema in docs/SCHEMA.md.

silver_rows.json is worked out by hand from the DBLP, OpenAlex and Genderize
fixtures. These tests guard its shape and make sure it stays consistent with
those inputs, so the ingest, gender and geo tickets can all build against it.
"""

import json
import pathlib
import re

import pytest
from ingest.main_track import is_main_track
from shared.config import REGION_MAP, REGIONS, UNMAPPED_REGION, VENUES, YEARS

ROOT = pathlib.Path(__file__).parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
SCHEMA_DOC = ROOT / "docs" / "SCHEMA.md"

SILVER_FIELDS = {
    "doi",
    "title",
    "venue",
    "year",
    "author_name",
    "author_position",
    "joint_wicsa_ecsa",
    "affiliations",
    "primary_affiliation",
    "country_code",
    "region",
    "gender_label",
    "gender_confidence",
    "position_mismatch",
    "primary_topic",
}
AFFILIATION_FIELDS = {"institution", "country_code"}

# TODO(gender-ticket): move GENDER_LABELS and the threshold to shared.config.
GENDER_LABELS = ["female-presenting", "male-presenting", "unclassified", "unknown"]
GENDER_THRESHOLD = 0.70
UNKNOWN = "unknown"
ALLOWED_REGIONS = [*REGIONS, UNKNOWN]

# The joint WICSA/ECSA years are stored under DBLP's wicsa key only.
JOINT_CROSSREFS = {"conf/wicsa/2009", "conf/wicsa/2012"}


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def silver():
    return _load("silver_rows.json")


@pytest.fixture(scope="module")
def dblp():
    return _load("dblp_records.json")


@pytest.fixture(scope="module")
def gender_lookup():
    return _load("gender_lookup_sample.json")


@pytest.fixture(scope="module")
def openalex():
    """OpenAlex works keyed by DOI; file names are the DOI with / as _."""
    works = {}
    for path in sorted((FIXTURES / "openalex_works").glob("*.json")):
        works[path.stem.replace("_", "/", 1)] = json.loads(
            path.read_text(encoding="utf-8")
        )
    return works


@pytest.fixture(scope="module")
def main_track(dblp):
    return [
        r
        for r in dblp
        if r["record_type"] == "inproceedings" and is_main_track(r["crossref"])
    ]


def _papers(rows):
    """Group silver rows by paper (title, since doi can be null)."""
    papers = {}
    for row in rows:
        papers.setdefault(row["title"], []).append(row)
    return papers


def _clean_name(name):
    # Same behaviour as the gender repo's clean_name(); the cache is keyed on it.
    name = name.replace("&apos;", "'")
    return re.sub(r" \d{4}", "", name)


def _expected_label(entry):
    if not entry or entry["gender"] is None:
        return UNKNOWN
    if entry["probability"] >= GENDER_THRESHOLD and entry["gender"] in (
        "female",
        "male",
    ):
        return f"{entry['gender']}-presenting"
    return "unclassified"


def _venue(crossref):
    key = crossref.split("/")[1].upper()
    return "ICSA" if key == "WICSA" else key


# ── Shape ─────────────────────────────────────────────────────────────────────


def test_silver_rows_have_exact_fields(silver):
    assert silver
    for row in silver:
        assert set(row) == SILVER_FIELDS, row
        for aff in row["affiliations"]:
            assert set(aff) == AFFILIATION_FIELDS, row


def _is_opt(value, kind):
    return value is None or isinstance(value, kind)


def test_silver_field_types(silver):
    for row in silver:
        assert _is_opt(row["doi"], str)
        assert isinstance(row["title"], str) and row["title"]
        assert isinstance(row["venue"], str)
        assert type(row["year"]) is int
        assert isinstance(row["author_name"], str) and row["author_name"]
        assert type(row["author_position"]) is int and row["author_position"] >= 0
        assert type(row["joint_wicsa_ecsa"]) is bool
        assert isinstance(row["affiliations"], list)
        for aff in row["affiliations"]:
            assert isinstance(aff["institution"], str) and aff["institution"]
            assert _is_opt(aff["country_code"], str)
        assert _is_opt(row["primary_affiliation"], str)
        assert _is_opt(row["country_code"], str)
        assert isinstance(row["region"], str)
        assert isinstance(row["gender_label"], str)
        assert row["gender_confidence"] is None or type(row["gender_confidence"]) in (
            int,
            float,
        )
        assert type(row["position_mismatch"]) is bool
        assert _is_opt(row["primary_topic"], str)


def test_silver_allowed_values(silver):
    for row in silver:
        assert row["venue"] in VENUES
        assert row["year"] in YEARS
        assert row["gender_label"] in GENDER_LABELS
        assert row["region"] in ALLOWED_REGIONS
        if row["gender_confidence"] is not None:
            assert 0.0 <= row["gender_confidence"] <= 1.0
        for code in [
            row["country_code"],
            *(a["country_code"] for a in row["affiliations"]),
        ]:
            assert code is None or (len(code) == 2 and code.isupper())


# ── Consistency between fields ────────────────────────────────────────────────


def test_primary_affiliation_is_first_affiliation(silver):
    for row in silver:
        first = row["affiliations"][0] if row["affiliations"] else {}
        assert row["primary_affiliation"] == first.get("institution")
        assert row["country_code"] == first.get("country_code")


def test_region_follows_from_country_code(silver):
    for row in silver:
        code = row["country_code"]
        expected = UNKNOWN if code is None else REGION_MAP.get(code, UNMAPPED_REGION)
        assert row["region"] == expected, row


def test_gender_follows_from_lookup(silver, gender_lookup):
    for row in silver:
        entry = gender_lookup.get(row["author_name"])
        assert row["gender_label"] == _expected_label(entry), row
        assert row["gender_confidence"] == (entry["probability"] if entry else None), (
            row
        )


def test_positions_are_contiguous_per_paper(silver):
    for title, rows in _papers(silver).items():
        assert [r["author_position"] for r in rows] == list(range(len(rows))), title
        paper_fields = {
            (r["doi"], r["venue"], r["year"], r["joint_wicsa_ecsa"], r["primary_topic"])
            for r in rows
        }
        assert len(paper_fields) == 1, title


# ── Consistency with the input fixtures ───────────────────────────────────────


def test_silver_papers_are_the_main_track_records(silver, main_track):
    papers = _papers(silver)
    assert set(papers) == {r["title"] for r in main_track}

    for rec in main_track:
        rows = papers[rec["title"]]
        assert [r["author_name"] for r in rows] == [
            _clean_name(a) for a in rec["authors"]
        ]
        for row in rows:
            assert row["doi"] == rec["doi"]
            assert row["year"] == rec["year"]
            assert row["venue"] == _venue(rec["crossref"])
            assert row["joint_wicsa_ecsa"] == (rec["crossref"] in JOINT_CROSSREFS)


def test_silver_matches_openalex(silver, openalex):
    for title, rows in _papers(silver).items():
        work = openalex.get(rows[0]["doi"])
        if work is None:
            # No DOI or no OpenAlex match: nothing to take affiliations from.
            for row in rows:
                assert row["affiliations"] == [] and row["primary_topic"] is None, title
                assert row["position_mismatch"] is False, title
            continue

        assert rows[0]["primary_topic"] == (work["primary_topic"] or {}).get(
            "display_name"
        )
        options = [
            [
                {"institution": i["display_name"], "country_code": i["country_code"]}
                for i in a["institutions"]
            ]
            for a in work["authorships"]
        ]
        for row in rows:
            pos = row["author_position"]
            if not row["position_mismatch"]:
                assert row["affiliations"] == options[pos], row
            else:
                assert row["affiliations"] in [*options, []], row


# ── Coverage of the cases other tickets rely on ───────────────────────────────


def test_dblp_fixture_coverage(dblp):
    crossrefs = {r["crossref"] for r in dblp if r["record_type"] == "inproceedings"}
    assert "conf/icse/2010-1" in crossrefs
    assert crossrefs & JOINT_CROSSREFS
    assert any(c.startswith("conf/ecsa/") for c in crossrefs)
    assert any(not is_main_track(c) for c in crossrefs), "needs a companion paper"
    assert any(r["record_type"] == "proceedings" for r in dblp)
    assert any(
        r["record_type"] == "inproceedings"
        and is_main_track(r["crossref"])
        and r["doi"] is None
        for r in dblp
    )


def test_openalex_fixture_coverage(openalex, dblp):
    assert len(openalex) == 4
    assert set(openalex) <= {r["doi"] for r in dblp}
    authorships = [a for w in openalex.values() for a in w["authorships"]]
    assert any(len(a["institutions"]) > 1 for a in authorships)
    assert any(len(a["institutions"]) == 0 for a in authorships)


def test_silver_fixture_coverage(silver, gender_lookup):
    assert any(r["position_mismatch"] for r in silver)
    assert any(r["joint_wicsa_ecsa"] for r in silver)
    assert any(r["doi"] is None for r in silver)
    assert any(r["region"] == UNKNOWN for r in silver)
    assert any(len(r["affiliations"]) > 1 for r in silver)
    assert {r["gender_label"] for r in silver} == set(GENDER_LABELS)
    # Both ways to get "unknown": not in the cache, and Genderize returned null.
    assert any(r["author_name"] not in gender_lookup for r in silver)
    assert any(
        r["author_name"] in gender_lookup
        and gender_lookup[r["author_name"]]["gender"] is None
        for r in silver
    )


# ── Schema doc ────────────────────────────────────────────────────────────────


def test_schema_doc_lists_every_field_and_value():
    doc = SCHEMA_DOC.read_text(encoding="utf-8")
    for name in [
        *SILVER_FIELDS,
        *AFFILIATION_FIELDS,
        *GENDER_LABELS,
        *ALLOWED_REGIONS,
        *VENUES,
    ]:
        assert f"`{name}`" in doc, name
