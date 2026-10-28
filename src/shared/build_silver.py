"""Join DBLP records to parsed OpenAlex works and build silver rows.

One row per main-track authorship, following docs/SCHEMA.md. Names and author
order come from DBLP; affiliations and topic come from OpenAlex.

    PYTHONPATH=src python -m shared.build_silver
"""

import json
import logging
import pathlib

from gender.classify import classify_gender
from gender.names import clean_name
from ingest.main_track import is_main_track
from shared.config import ICSA_LINEAGE

logger = logging.getLogger(__name__)

ROOT = pathlib.Path(__file__).parents[2]
DEFAULT_DBLP = ROOT / "data" / "bronze" / "dblp" / "icse_ecsa_icsa_filtered.json"
DEFAULT_OPENALEX = ROOT / "data" / "bronze" / "openalex"
DEFAULT_GENDER = ROOT / "data" / "bronze" / "genderize" / "gender_lookup.json"
DEFAULT_OUT = ROOT / "data" / "silver" / "silver_rows.json"
DEFAULT_REVIEW_LOG = ROOT / "data" / "silver" / "position_mismatches.jsonl"

# WICSA and ECSA were held jointly in 2009 and 2012. No deduplication is needed:
# DBLP stores those papers only under conf/wicsa/, never also under conf/ecsa/,
# so each joint paper appears once and is flagged here.
JOINT_WICSA_ECSA_CROSSREFS = {"conf/wicsa/2009", "conf/wicsa/2012"}


def _venue(crossref):
    """DBLP venue key to a VENUES name; WICSA is ICSA's name before 2017."""
    key = crossref.split("/")[1].upper()
    return "ICSA" if key in ICSA_LINEAGE else key


def _match(dblp_name, position, authorships, matcher, used):
    """Index of the OpenAlex authorship for this DBLP author, or None.

    The same position is preferred; otherwise the first unused name match.
    """
    if position < len(authorships) and position not in used:
        if matcher(dblp_name, authorships[position]["openalex_name"]):
            return position
    for i, authorship in enumerate(authorships):
        if i not in used and matcher(dblp_name, authorship["openalex_name"]):
            return i
    return None


def _gender(name, gender_lookup):
    entry = gender_lookup.get(name)
    if entry is None:
        return "unknown", None
    return classify_gender(entry["gender"], entry["probability"]), entry["probability"]


def build_rows(
    dblp_records, parsed_works, gender_lookup, matcher, region_fn, *, review_log=None
) -> list[dict]:
    """Build silver rows for every main-track paper in dblp_records.

    parsed_works are ingest.openalex_parse.parse_work() outputs. matcher(dblp,
    openalex) decides whether two names are the same person, and region_fn
    (affiliations) returns (country_code, region); both are passed in so tests
    can use stand-ins. Rows whose author can't be matched at the same position
    are flagged with position_mismatch and, if review_log is a path, written
    there for review. They are never auto-corrected: name and position stay
    DBLP's, and affiliations come from the name-matched OpenAlex author.
    """
    works = {w["doi"]: w for w in parsed_works if w.get("doi")}
    rows, review = [], []

    for rec in dblp_records:
        if rec["record_type"] != "inproceedings" or not is_main_track(rec["crossref"]):
            continue

        doi = rec.get("doi")
        work = works.get(doi.lower()) if doi else None
        if not doi:
            # Kept, so its authors still count for gender (docs/SCHEMA.md).
            logger.warning("No DOI for %s; rows kept without affiliations", rec["key"])
        authorships = work["authorships"] if work else []
        used = set()

        for position, dblp_name in enumerate(rec["authors"]):
            matched = (
                _match(dblp_name, position, authorships, matcher, used)
                if work
                else None
            )
            if matched is not None:
                used.add(matched)
            affiliations = (
                authorships[matched]["affiliations"] if matched is not None else []
            )
            mismatch = work is not None and matched != position
            country_code, region = region_fn(affiliations)
            name = clean_name(dblp_name)
            gender_label, gender_confidence = _gender(name, gender_lookup)

            row = {
                "doi": doi,
                "title": rec["title"],
                "venue": _venue(rec["crossref"]),
                "year": rec["year"],
                "author_name": name,
                "author_position": position,
                "joint_wicsa_ecsa": rec["crossref"] in JOINT_WICSA_ECSA_CROSSREFS,
                "affiliations": affiliations,
                "primary_affiliation": affiliations[0]["institution"]
                if affiliations
                else None,
                "country_code": country_code,
                "region": region,
                "gender_label": gender_label,
                "gender_confidence": gender_confidence,
                "position_mismatch": mismatch,
                "primary_topic": work["primary_topic"] if work else None,
            }
            rows.append(row)
            if mismatch:
                review.append(
                    {
                        "doi": doi,
                        "title": rec["title"],
                        "author_name": name,
                        "author_position": position,
                        "openalex_position": matched,
                        "openalex_names": [a["openalex_name"] for a in authorships],
                    }
                )

    def order(r):
        return (r["doi"] is None, r["doi"] or "", r["title"], r["author_position"])

    rows.sort(key=order)
    review.sort(key=order)
    if review:
        logger.warning("%d authorships flagged position_mismatch", len(review))
    if review_log is not None:
        path = pathlib.Path(review_log)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in review),
            encoding="utf-8",
        )
    return rows


def main():
    from geo.affiliation import primary_region
    from ingest.openalex_parse import parse_work
    from shared.name_match import names_match

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    dblp = json.loads(DEFAULT_DBLP.read_text(encoding="utf-8"))
    works = [
        parse_work(json.loads(p.read_text(encoding="utf-8")))
        for p in sorted(DEFAULT_OPENALEX.glob("*.json"))
    ]
    gender_lookup = json.loads(DEFAULT_GENDER.read_text(encoding="utf-8"))

    rows = build_rows(
        dblp,
        works,
        gender_lookup,
        names_match,
        primary_region,
        review_log=DEFAULT_REVIEW_LOG,
    )
    DEFAULT_OUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUT.write_text(
        json.dumps(rows, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(rows):,} rows to {DEFAULT_OUT} ({len(works):,} OpenAlex works)")


if __name__ == "__main__":
    main()
