"""Decide whether a DBLP author name and an OpenAlex author name are the same person.

Used by the silver builder to flag author-position mismatches. Surnames must
be equal, and first names must be equal or one must be the other's initial.
Case, accents, middle initials, and hyphens are ignored.
"""

import re
import unicodedata

_SEPARATORS = re.compile(r"[-.]")


def _tokens(name: str) -> list[str]:
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    return _SEPARATORS.sub(" ", name.lower()).split()


def names_match(dblp_name: str, openalex_name: str) -> bool:
    """True when both names plausibly refer to the same person."""
    a, b = _tokens(dblp_name), _tokens(openalex_name)
    if not a or not b or a[-1] != b[-1]:
        return False
    first_a, first_b = a[0], b[0]
    return (
        first_a == first_b
        or (len(first_a) == 1 and first_b.startswith(first_a))
        or (len(first_b) == 1 and first_a.startswith(first_b))
    )
