"""Parse a cached OpenAlex work into authorships, affiliations and topic."""

from __future__ import annotations

# Same DOI form as the bronze cache filenames: bare and lowercased.
from ingest.openalex_fetch import _normalize_doi


def parse_work(work: dict) -> dict:
    """Return {doi, primary_topic, authorships} for one OpenAlex work.

    Pure function: no network or file access. ``doi`` is bare and lowercased
    (no https://doi.org/ prefix). ``author_position`` is the 0-based index in
    OpenAlex's author list, the same meaning as in silver. Affiliation order
    follows OpenAlex's ``institutions`` order. An author with no institutions
    gets an empty affiliations list; a missing primary topic becomes None.
    """
    topic = work.get("primary_topic")

    authorships = []
    for position, authorship in enumerate(work.get("authorships") or []):
        author = authorship.get("author") or {}
        authorships.append(
            {
                "author_position": position,
                "openalex_name": author.get("display_name"),
                "affiliations": [
                    {
                        "institution": inst.get("display_name"),
                        "country_code": inst.get("country_code"),
                    }
                    for inst in authorship.get("institutions") or []
                ],
            }
        )

    return {
        "doi": _normalize_doi(work["doi"]) if work.get("doi") else None,
        "primary_topic": topic.get("display_name") if topic else None,
        "authorships": authorships,
    }
