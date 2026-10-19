import json
import pathlib

from gender.gold import gender_counts, gender_pct, write_gender_yearly

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _silver_rows():
    return json.loads((FIXTURES / "silver_rows.json").read_text(encoding="utf-8"))


def test_unclassified_and_unknown_do_not_change_female_percentage():
    baseline = {
        "female-presenting": 1,
        "male-presenting": 1,
        "unclassified": 0,
        "unknown": 0,
    }
    with_unclassified_and_unknown = {
        **baseline,
        "unclassified": 7,
        "unknown": 4,
    }

    assert gender_pct(baseline) == gender_pct(with_unclassified_and_unknown)
    assert gender_pct(with_unclassified_and_unknown) == {
        "female-presenting": 50.0,
        "male-presenting": 50.0,
    }


def test_gender_counts_include_all_and_first_author_breakdowns():
    result = gender_counts(_silver_rows())
    icse_2010 = next(
        row for row in result
        if row["venue"] == "ICSE" and row["year"] == 2010
    )

    assert icse_2010["all_authors"]["counts"] == {
        "female-presenting": 0,
        "male-presenting": 2,
        "unclassified": 1,
        "unknown": 0,
    }
    assert icse_2010["first_authors"]["counts"] == {
        "female-presenting": 0,
        "male-presenting": 1,
        "unclassified": 0,
        "unknown": 0,
    }
    assert icse_2010["all_authors"]["percentages"] == {
        "female-presenting": 0.0,
        "male-presenting": 100.0,
    }


def test_gender_counts_preserve_joint_wicsa_ecsa_flag():
    joint = next(
        row for row in gender_counts(_silver_rows())
        if row["venue"] == "ICSA" and row["year"] == 2009
    )

    assert joint["joint_wicsa_ecsa"] is True


def test_gender_pct_returns_none_when_no_classified_genders():
    assert gender_pct({"female-presenting": 0, "male-presenting": 0}) == {
        "female-presenting": None,
        "male-presenting": None,
    }


def test_write_gender_yearly_serializes_aggregated_rows(tmp_path):
    output_path = tmp_path / "gender_yearly.json"

    write_gender_yearly(_silver_rows(), output_path)

    assert json.loads(output_path.read_text(encoding="utf-8")) == gender_counts(
        _silver_rows()
    )
