import json
import pathlib

import pytest

from geo.gold import (
    country_stats,
    main,
    region_stats,
    write_country_yearly,
    write_region_yearly,
)

from shared.config import REGIONS, UNKNOWN_REGION

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def make_row(doi, country_code, region, venue="ICSE", year=2020, joint=False):
    """Build a silver row with only the fields gold.py reads."""
    return {
        "doi": doi,
        "title": f"Title of {doi}",
        "venue": venue,
        "year": year,
        "joint_wicsa_ecsa": joint,
        "country_code": country_code,
        "region": region,
    }


# ── region_stats ──────────────────────────────────────────────────────────────


def test_us_and_de_authors_count_once_in_each_region():
    rows = [
        make_row("10.1/a", "US", "North America"),
        make_row("10.1/a", "DE", "W. Europe"),
    ]
    [group] = region_stats(rows)
    assert group["total_papers"] == 1
    assert group["counts"]["North America"] == 1
    assert group["counts"]["W. Europe"] == 1


def test_two_us_authors_on_one_paper_count_once():
    rows = [
        make_row("10.1/a", "US", "North America"),
        make_row("10.1/a", "US", "North America"),
    ]
    [group] = region_stats(rows)
    assert group["total_papers"] == 1
    assert group["counts"]["North America"] == 1


def test_paper_with_all_authors_unknown_counts_as_unknown():
    rows = [
        make_row("10.1/a", None, UNKNOWN_REGION),
        make_row("10.1/a", None, UNKNOWN_REGION),
    ]
    [group] = region_stats(rows)
    assert group["counts"][UNKNOWN_REGION] == 1


def test_paper_with_some_known_authors_is_not_unknown():
    rows = [
        make_row("10.1/a", "CN", "Asia-Pacific"),
        make_row("10.1/a", None, UNKNOWN_REGION),
    ]
    [group] = region_stats(rows)
    assert group["counts"]["Asia-Pacific"] == 1
    assert group["counts"][UNKNOWN_REGION] == 0


def test_joint_wicsa_ecsa_flag_is_carried_into_output():
    rows = [
        make_row("10.1/a", "NL", "W. Europe", venue="ICSA", year=2009, joint=True),
        make_row("10.1/b", "US", "North America", venue="ICSA", year=2017),
    ]
    joint, regular = region_stats(rows)
    assert (joint["venue"], joint["year"], joint["joint_wicsa_ecsa"]) == (
        "ICSA",
        2009,
        True,
    )
    assert regular["joint_wicsa_ecsa"] is False


def test_counts_follow_regions_order_with_unknown_last_and_zeros_kept():
    [group] = region_stats([make_row("10.1/a", "US", "North America")])
    assert list(group["counts"]) == [*REGIONS, UNKNOWN_REGION]
    assert group["counts"]["Africa"] == 0


def test_papers_without_doi_are_grouped_by_title():
    rows = [
        make_row(None, "GB", "W. Europe"),
        make_row(None, "GB", "W. Europe"),
    ]
    [group] = region_stats(rows)
    assert group["total_papers"] == 1


def test_percentages_use_all_papers_as_denominator():
    rows = [
        make_row("10.1/a", "US", "North America"),
        make_row("10.1/a", "DE", "W. Europe"),
        make_row("10.1/b", "US", "North America"),
    ]
    [group] = region_stats(rows)
    assert group["total_papers"] == 2
    assert group["percentages"]["North America"] == 100.0
    assert group["percentages"]["W. Europe"] == 50.0


def test_unexpected_region_raises():
    with pytest.raises(ValueError):
        region_stats([make_row("10.1/a", None, "Middle East & Africa")])


def test_region_stats_on_shared_fixtures():
    rows = json.loads((FIXTURES / "silver_rows.json").read_text(encoding="utf-8"))
    result = {
        (g["venue"], g["year"], g["joint_wicsa_ecsa"]): g for g in region_stats(rows)
    }
    assert list(result) == [
        ("ECSA", 2013, False),
        ("ICSA", 2009, True),
        ("ICSA", 2017, False),
        ("ICSE", 2010, False),
        ("ICSE", 2020, False),
    ]
    for group in result.values():
        assert group["total_papers"] == 1
    assert result[("ECSA", 2013, False)]["counts"][UNKNOWN_REGION] == 1
    assert result[("ICSA", 2009, True)]["counts"]["W. Europe"] == 1
    # No DOI: the two authors are grouped into one paper by title.
    assert result[("ICSA", 2017, False)]["counts"][UNKNOWN_REGION] == 1
    # Romain Robbes is CH then CL; only the first affiliation counts.
    assert result[("ICSE", 2010, False)]["counts"]["W. Europe"] == 1
    assert result[("ICSE", 2010, False)]["counts"]["Latin America"] == 0
    # Two US authors on one paper count once.
    assert result[("ICSE", 2020, False)]["counts"]["North America"] == 1


# ── country_stats ─────────────────────────────────────────────────────────────


def test_country_stats_counts_each_country_once_per_paper():
    rows = [
        make_row("10.1/a", "US", "North America"),
        make_row("10.1/a", "US", "North America"),
        make_row("10.1/a", "DE", "W. Europe"),
    ]
    [group] = country_stats(rows)
    assert group["total_papers"] == 1
    assert group["counts"] == {"DE": 1, "US": 1, UNKNOWN_REGION: 0}


def test_country_stats_reports_unknown_for_papers_with_no_country():
    rows = [
        make_row("10.1/a", None, UNKNOWN_REGION),
        make_row("10.1/b", "US", "North America"),
        make_row("10.1/b", None, UNKNOWN_REGION),
    ]
    [group] = country_stats(rows)
    assert group["counts"] == {"US": 1, UNKNOWN_REGION: 1}


def test_country_stats_carries_joint_flag():
    rows = [make_row("10.1/a", "NL", "W. Europe", venue="ICSA", year=2009, joint=True)]
    [group] = country_stats(rows)
    assert group["joint_wicsa_ecsa"] is True


# ── writing ───────────────────────────────────────────────────────────────────


def test_write_functions_create_json_files(tmp_path):
    rows = [make_row("10.1/a", "US", "North America")]
    region_path = tmp_path / "gold" / "region_yearly.json"
    country_path = tmp_path / "gold" / "country_yearly.json"

    write_region_yearly(rows, region_path)
    write_country_yearly(rows, country_path)

    assert json.loads(region_path.read_text(encoding="utf-8")) == region_stats(rows)
    assert json.loads(country_path.read_text(encoding="utf-8")) == country_stats(rows)



def test_main_writes_both_gold_files_from_silver_file(tmp_path):
    rows = json.loads((FIXTURES / "silver_rows.json").read_text(encoding="utf-8"))

    main([str(FIXTURES / "silver_rows.json"), str(tmp_path)])

    region = json.loads((tmp_path / "region_yearly.json").read_text(encoding="utf-8"))
    country = json.loads((tmp_path / "country_yearly.json").read_text(encoding="utf-8"))
    assert region == region_stats(rows)
    assert country == country_stats(rows)