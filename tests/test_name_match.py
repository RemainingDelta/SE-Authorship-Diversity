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
    # DBLP number for people who share a name
    ("Wei Zhang 0001", "Wei Zhang"),
    # The cases below are real DBLP / OpenAlex pairs from the same author slot.
    # OpenAlex often uses the Unicode hyphen (U+2010), not "-"
    ("Jane Cleland-Huang", "Jane Cleland‐Huang"),
    ("Margaret-Anne D. Storey", "Margaret‐Anne Storey"),
    ("Özden Özcan Top", "Özden Özcan‐Top"),
    # Curly apostrophe
    ("Marcelo d'Amorim", "Marcelo d’Amorim"),
    # Stray initial after the surname in OpenAlex
    ("Arie van Deursen", "Arie Van Deursen A"),
    ("Roberta Gori", "Roberta Gori B"),
    # Family name first in OpenAlex
    ("Daniel Doyle", "Doyle Daniel"),
    ("Jun Nomura", "Nomura Jun"),
])
def test_names_match(dblp_name, openalex_name):
    assert names_match(dblp_name, openalex_name)


@pytest.mark.parametrize("dblp_name,openalex_name", [
    ("John Smith", "Maria Garcia"),
    # Same surname, different first name
    ("Lucia Happe", "Jens Happe"),
    # OpenAlex dropped the surname; the remaining "Kil" is not "Cha"
    ("Sang Kil Cha", "Sang Kil"),
    # Swapped order still needs both names to agree
    ("Daniel Doyle", "Doyle David"),
    # Empty names never match
    ("", "Wei Zhang"),
])
def test_names_do_not_match(dblp_name, openalex_name):
    assert not names_match(dblp_name, openalex_name)