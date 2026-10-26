import json
import pathlib
from collections import defaultdict

from gender.gold import gender_counts
from shared.gold_combined import gender_by_region, write_gender_by_region

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _silver_rows():
    return json.loads((FIXTURES / "silver_rows.json").read_text(encoding="utf-8"))


def test_gender_by_region_counts_authors_by_region():
    result = gender_by_region(_silver_rows())
    icse_2010 = next(
        row for row in result
        if row["venue"] == "ICSE"
        and row["year"] == 2010
        and row["region"] == "W. Europe"
    )

    assert icse_2010["counts"] == {
        "female-presenting": 0,
        "male-presenting": 2,
        "unclassified": 1,
        "unknown": 0,
    }
    assert icse_2010["percentages"] == {
        "female-presenting": 0.0,
        "male-presenting": 100.0,
    }


def test_region_counts_sum_to_gender_counts_by_venue_and_year():
    rows = _silver_rows()
    regional_totals = defaultdict(lambda: defaultdict(int))
    for row in gender_by_region(rows):
        totals = regional_totals[(row["venue"], row["year"])]
        for label, count in row["counts"].items():
            totals[label] += count

    yearly_totals = defaultdict(lambda: defaultdict(int))
    for row in gender_counts(rows):
        totals = yearly_totals[(row["venue"], row["year"])]
        for label, count in row["all_authors"]["counts"].items():
            totals[label] += count

    assert dict(regional_totals) == dict(yearly_totals)


def test_regional_percentages_exclude_unclassified_and_unknown():
    rows = [
        {
            "venue": "ICSE",
            "year": 2020,
            "region": "North America",
            "gender_label": "female-presenting",
        },
        {
            "venue": "ICSE",
            "year": 2020,
            "region": "North America",
            "gender_label": "male-presenting",
        },
        {
            "venue": "ICSE",
            "year": 2020,
            "region": "North America",
            "gender_label": "unclassified",
        },
        {
            "venue": "ICSE",
            "year": 2020,
            "region": "North America",
            "gender_label": "unknown",
        },
    ]

    result = gender_by_region(rows)

    assert result[0]["percentages"] == {
        "female-presenting": 50.0,
        "male-presenting": 50.0,
    }


def test_write_gender_by_region_serializes_aggregated_rows(tmp_path):
    output_path = tmp_path / "gender_by_region.json"

    write_gender_by_region(_silver_rows(), output_path)

    assert json.loads(output_path.read_text(encoding="utf-8")) == gender_by_region(
        _silver_rows()
    )
