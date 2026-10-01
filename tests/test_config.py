import pytest
from shared.config import (
    ICSA_LINEAGE,
    REGION_MAP,
    REGION_ROLLUPS,
    REGIONS,
    UNMAPPED_REGION,
    VENUES,
    YEAR_END,
    YEAR_START,
    YEARS,
)


@pytest.mark.parametrize("code,expected", [
    # One representative per region
    ("US", "North America"),
    ("DE", "W. Europe"),
    ("PL", "E. Europe"),
    ("CN", "Asia-Pacific"),
    ("BR", "Latin America"),
    # Middle East and Africa are separate regions, not merged
    ("IL", "Middle East"),
    ("TR", "Middle East"),
    ("EG", "Africa"),
    ("ZA", "Africa"),
])
def test_region_map(code, expected):
    assert REGION_MAP[code] == expected


def test_region_map_keys_are_iso_alpha2():
    assert all(len(code) == 2 and code.isupper() for code in REGION_MAP)


def test_every_mapped_region_is_canonical():
    assert set(REGION_MAP.values()) | {UNMAPPED_REGION} == set(REGIONS)


def test_rollups_only_reference_canonical_regions():
    for members in REGION_ROLLUPS.values():
        assert set(members) <= set(REGIONS)


def test_year_range_inclusive():
    assert YEARS[0] == YEAR_START
    assert YEARS[-1] == YEAR_END


def test_icsa_lineage_covers_years_without_overlap():
    years = [y for era in ICSA_LINEAGE.values() for y in era]
    assert len(years) == len(set(years))
    assert sorted(years) == list(YEARS)


def test_icsa_is_a_venue():
    assert "ICSA" in VENUES
