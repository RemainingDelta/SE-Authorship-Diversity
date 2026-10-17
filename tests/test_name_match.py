import pytest
from shared.name_match import names_match


@pytest.mark.parametrize("dblp_name,openalex_name", [
    # Initial vs. full first name
    ("Wei Zhang", "W. Zhang"),
    # Middle initial on one side only
    ("Jane A. Doe", "Jane Doe"),
    # Accents
    ("José García", "Jose Garcia"),
    # Hyphenated vs. spaced first name
    ("Anne-Marie Li", "Anne Marie Li"),
])
def test_names_match(dblp_name, openalex_name):
    assert names_match(dblp_name, openalex_name)


@pytest.mark.parametrize("dblp_name,openalex_name", [
    ("John Smith", "Maria Garcia"),
])
def test_names_do_not_match(dblp_name, openalex_name):
    assert not names_match(dblp_name, openalex_name)