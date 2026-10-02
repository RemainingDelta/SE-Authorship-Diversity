import json
import pathlib

import pytest
from ingest.main_track import is_main_track, report_counts

FILTERED = (
    pathlib.Path(__file__).parent.parent
    / "data"
    / "bronze"
    / "dblp"
    / "icse_ecsa_icsa_filtered.json"
)


@pytest.mark.parametrize("crossref", [
    # Plain proceedings key for each venue
    "conf/icse/2020",
    "conf/ecsa/2013",
    "conf/icsa/2017",
    # Joint WICSA/ECSA year is stored under wicsa only
    "conf/wicsa/2009",
    # Volume-split years: only volume 1 is the research track
    "conf/icse/2010-1",
    "conf/icse/2015-1",
])
def test_main_track_kept(crossref):
    assert is_main_track(crossref)


@pytest.mark.parametrize("crossref", [
    # Volume 2 is mostly companion material (workshop summaries, short papers)
    "conf/icse/2010-2",
    "conf/icse/2015-2",
    # Satellite suffixes after the year
    "conf/icse/2020c",
    "conf/icse/2020w",
    "conf/icse/2020seip",
    "conf/icse/2020nier",
    "conf/icse/2020ast",
    # Not a target venue
    "conf/sigsoft/2020",
    # No crossref at all
    None,
    "",
])
def test_main_track_excluded(crossref):
    assert not is_main_track(crossref)


def _paper(crossref, record_type="inproceedings"):
    return {"record_type": record_type, "crossref": crossref}


def test_report_counts_by_venue_and_year():
    records = [
        _paper("conf/icse/2020"),
        _paper("conf/icse/2020"),
        _paper("conf/icse/2020c"),
        _paper("conf/wicsa/2009"),
        _paper(None),
        # Proceedings records describe the volume itself, not a paper
        _paper(None, record_type="proceedings"),
    ]

    assert report_counts(records) == {("icse", 2020): 2, ("wicsa", 2009): 1}


def test_icse_counts_on_committed_data():
    # Guards the committed filtered JSON. If DBLP data is regenerated and
    # these move, check the change before updating the numbers.
    records = json.loads(FILTERED.read_text(encoding="utf-8"))
    counts = report_counts(records)

    assert {y: counts[("icse", y)] for y in (2010, 2015, 2016, 2018, 2020, 2023, 2024, 2025)} == {
        2010: 65,
        2015: 86,
        2016: 101,
        2018: 153,
        2020: 129,
        2023: 211,
        2024: 237,
        2025: 245,
    }
