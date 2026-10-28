"""Map an author's primary affiliation to a country code and region.

The primary affiliation is the first one listed for the author on a paper.
Later affiliations are ignored, even when the first has no country code.
"""

from shared.config import REGION_MAP, UNKNOWN_REGION, UNMAPPED_REGION


def primary_region(affiliations: list[dict] | None) -> tuple[str | None, str]:
    """Return (country_code, region) for an author's first affiliation."""
    if not affiliations:
        return None, UNKNOWN_REGION

    code = affiliations[0].get("country_code")
    if not code:
        return None, UNKNOWN_REGION

    return code, REGION_MAP.get(code, UNMAPPED_REGION)
