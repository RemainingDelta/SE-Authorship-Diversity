from geo.affiliation import primary_region
from shared.config import REGION_MAP, UNKNOWN_REGION, UNMAPPED_REGION


def test_first_affiliation_wins_when_there_are_several():
    affiliations = [
        {"institution": "TU Munich", "country_code": "DE"},
        {"institution": "MIT", "country_code": "US"},
    ]
    assert primary_region(affiliations) == ("DE", "W. Europe")


def test_single_mapped_affiliation():
    affiliations = [{"institution": "MIT", "country_code": "US"}]
    assert primary_region(affiliations) == ("US", "North America")


def test_empty_list_is_unknown():
    assert primary_region([]) == (None, UNKNOWN_REGION)


def test_none_is_unknown():
    assert primary_region(None) == (None, UNKNOWN_REGION)


def test_affiliation_with_no_country_code_is_unknown():
    affiliations = [{"institution": "Independent Researcher", "country_code": None}]
    assert primary_region(affiliations) == (None, UNKNOWN_REGION)


def test_affiliation_missing_country_code_key_is_unknown():
    affiliations = [{"institution": "Independent Researcher"}]
    assert primary_region(affiliations) == (None, UNKNOWN_REGION)


def test_no_fallback_to_later_affiliation_when_first_has_no_country():
    affiliations = [
        {"institution": "Independent Researcher", "country_code": None},
        {"institution": "MIT", "country_code": "US"},
    ]
    assert primary_region(affiliations) == (None, UNKNOWN_REGION)


def test_country_not_in_region_map_is_other():
    assert "KE" not in REGION_MAP  # guard: pick a real code that stays unmapped
    affiliations = [{"institution": "University of Nairobi", "country_code": "KE"}]
    assert primary_region(affiliations) == ("KE", UNMAPPED_REGION)


def test_unknown_and_other_are_distinct():
    assert UNKNOWN_REGION == "unknown"
    assert UNMAPPED_REGION == "Other"
    assert UNKNOWN_REGION != UNMAPPED_REGION