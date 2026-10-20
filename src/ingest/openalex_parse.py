"""Parse a cached OpenAlex work into authorships, affiliations and topic."""

from __future__ import annotations


def parse_work(work: dict) -> dict:
    """Return {doi, primary_topic, authorships} for one OpenAlex work.

    Pure function: no network or file access. Affiliation order follows
    OpenAlex's ``institutions`` order. An author with no institutions gets
    an empty affiliations list; a missing primary topic becomes None.
    """
    topic = work.get("primary_topic")

    authorships = []
    for authorship in work.get("authorships") or []:
        author = authorship.get("author") or {}
        authorships.append(
            {
                "author_position": authorship.get("author_position"),
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
        "doi": work.get("doi"),
        "primary_topic": topic.get("display_name") if topic else None,
        "authorships": authorships,
    }
