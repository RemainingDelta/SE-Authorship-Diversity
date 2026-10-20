import pytest
from gender.names import clean_name


@pytest.mark.parametrize("input_name,expected", [
    # No-op: plain name passes through unchanged
    ("John Smith", "John Smith"),
    # DBLP HTML entity fix
    ("O&apos;Brien", "O'Brien"),
    # 4-digit year disambiguation suffix stripped
    ("Wei Zhang 2019", "Wei Zhang"),
    # 4-digit DBLP numeric disambiguator stripped
    ("First Last 0023", "First Last"),
    # Both transformations applied
    ("A&apos;B 2021", "A'B"),
    # No leading space before digits — not stripped
    ("Smith2019", "Smith2019"),
    # Multiple suffixes — both stripped
    ("Jane Doe 2020 2021", "Jane Doe"),
])
def test_clean_name(input_name, expected):
    assert clean_name(input_name) == expected
