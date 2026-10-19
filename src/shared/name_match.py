"""Decide whether a DBLP author name and an OpenAlex author name are the same person.

Used by the silver builder to flag author-position mismatches. Surnames must
be equal, and first names must be equal or one must be the other's initial.
Case, accents, middle initials, hyphens, and apostrophes are ignored, as is
the number DBLP adds to tell apart people with the same name ("Wei Zhang 0001").

Two OpenAlex quirks are also tolerated: a stray initial after the surname
("Arie Van Deursen A") and family name first ("Nomura Jun").
"""

import re
import unicodedata

# ASCII hyphen plus the Unicode dashes OpenAlex uses (U+2010 to U+2015).
_SEPARATORS = re.compile(r"[-.‐-―]")

# Straight and curly apostrophes: "d'Amorim" and "d’Amorim" are the same name.
_APOSTROPHES = re.compile(r"['‘’ʼ]")

# DBLP numbers people who share a name: "Wei Zhang 0001". OpenAlex does not.
_DBLP_SUFFIX = re.compile(r"\s+\d{4}$")


def _tokens(name: str) -> list[str]:
    name = _DBLP_SUFFIX.sub("", name.strip())
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = _APOSTROPHES.sub("", name)
    tokens = _SEPARATORS.sub(" ", name.lower()).split()
    # Drop stray initials after the surname, but always keep a first and last name.
    while len(tokens) > 2 and len(tokens[-1]) == 1:
        tokens.pop()
    return tokens


def _first_names_agree(x: str, y: str) -> bool:
    return (
        x == y or (len(x) == 1 and y.startswith(x)) or (len(y) == 1 and x.startswith(y))
    )


def names_match(dblp_name: str, openalex_name: str) -> bool:
    """True when both names plausibly refer to the same person."""
    a, b = _tokens(dblp_name), _tokens(openalex_name)
    if not a or not b:
        return False
    if a[-1] == b[-1] and _first_names_agree(a[0], b[0]):
        return True
    # Family name first on one side: "Jun Nomura" / "Nomura Jun".
    return a[-1] == b[0] and _first_names_agree(a[0], b[-1])
