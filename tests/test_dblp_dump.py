import gzip
import json
import pathlib

import pytest
from ingest.dblp_dump import TARGET_PREFIXES, filter_dump, write_records

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "dblp"


@pytest.fixture
def records(tmp_path):
    # The real dump is gzipped; keep the fixture readable and gzip it here.
    gz_path = tmp_path / "mini.xml.gz"
    gz_path.write_bytes(gzip.compress((FIXTURES / "mini.xml").read_bytes()))
    return filter_dump(gz_path, FIXTURES / "mini.dtd")


@pytest.fixture
def by_key(records):
    return {r["key"]: r for r in records}


def test_target_prefixes_come_from_config():
    # ICSE, ECSA, ICSA from VENUES, plus WICSA from ICSA_LINEAGE
    assert set(TARGET_PREFIXES) == {
        "conf/icse/",
        "conf/ecsa/",
        "conf/icsa/",
        "conf/wicsa/",
    }


def test_keeps_only_target_venues_within_year_range(by_key):
    assert set(by_key) == {
        "conf/icse/OCinneide20",
        "conf/icse/Smith20c",
        "conf/icse/2020",
        "conf/wicsa/Muller09",
        "conf/ecsa/Rossi13",
        "conf/icsa/Kim17",
    }


def test_main_track_decision_is_left_to_later_stage(by_key):
    # Companion papers are kept here; #4 filters main track by crossref.
    assert by_key["conf/icse/Smith20c"]["crossref"] == "conf/icse/2020c"


def test_proceedings_records_are_kept_with_type(by_key):
    assert by_key["conf/icse/2020"]["record_type"] == "proceedings"
    assert by_key["conf/icse/OCinneide20"]["record_type"] == "inproceedings"


@pytest.mark.parametrize("key,expected", [
    # Named entities resolve through the local DTD, even though the XML's
    # DOCTYPE points at a path that does not exist
    ("conf/icse/OCinneide20", ["Mel Ó Cinnéide", "José García", "Wei Zhang 0001"]),
    ("conf/wicsa/Muller09", ["Hans Müller"]),
    # Multi-author order preserved
    ("conf/ecsa/Rossi13", ["Maria Rossi", "Luca Bianchi"]),
    # Single author is still a list
    ("conf/icsa/Kim17", ["Ji-woo Kim"]),
])
def test_authors(by_key, key, expected):
    assert by_key[key]["authors"] == expected


def test_title_with_inline_markup_is_kept_whole(by_key):
    assert by_key["conf/icse/OCinneide20"]["title"] == "Testing quickly at scale."


@pytest.mark.parametrize("key,doi", [
    # DOI listed as the second <ee> is still found
    ("conf/icse/OCinneide20", "10.1145/3377811.3380001"),
    # Old dx.doi.org form
    ("conf/ecsa/Rossi13", "10.1007/978-3-642-39031-9_1"),
    ("conf/icsa/Kim17", "10.1109/ICSA.2017.24"),
    # No <ee> at all
    ("conf/wicsa/Muller09", None),
])
def test_doi_extracted_from_ee(by_key, key, doi):
    assert by_key[key]["doi"] == doi


def test_ee_keeps_first_link(by_key):
    assert by_key["conf/icse/OCinneide20"]["ee"] == "https://ieeexplore.ieee.org/document/123"


def test_fields(by_key):
    rec = by_key["conf/icse/OCinneide20"]
    assert set(rec) == {
        "record_type",
        "key",
        "year",
        "title",
        "authors",
        "doi",
        "ee",
        "crossref",
        "booktitle",
    }
    assert rec["year"] == 2020
    assert rec["booktitle"] == "ICSE"


def test_write_records_round_trips_one_record_per_line(records, tmp_path):
    out = tmp_path / "out.json"
    write_records(records, out)

    assert json.loads(out.read_text(encoding="utf-8")) == records
    # [ + one line per record + ]
    assert len(out.read_text(encoding="utf-8").splitlines()) == len(records) + 2
