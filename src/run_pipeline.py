"""Run the whole pipeline in order, or a single stage.

    dblp → main-track → openalex → genderize → silver → gold

Every stage reads its input from disk and writes its output to disk, so any
stage can be rerun on its own:

    PYTHONPATH=src python -m run_pipeline                  # everything but dblp
    PYTHONPATH=src python -m run_pipeline --stage gold     # one stage
    PYTHONPATH=src python -m run_pipeline --refresh-dblp   # also re-filter the dump

The dblp stage is skipped in a full run unless --refresh-dblp is given: the
filtered DBLP JSON is committed, and re-filtering a newer dump would silently
change it. Genderize is paid, so it keeps its yes/no prompt; with no API key,
a "no", no terminal to answer, or a quota error, new names stay unknown and
the run goes on.
"""

import argparse
import json
import logging
import os
import pathlib
from dataclasses import dataclass

from dotenv import load_dotenv

from gender.genderize import GenderizeError, dblp_author_names, lookup_new
from gender.gold import write_gender_yearly
from geo.affiliation import primary_region
from geo.gold import (
    COUNTRY_FILENAME,
    REGION_FILENAME,
    write_country_yearly,
    write_region_yearly,
)
from ingest.dblp_dump import filter_dump, write_records
from ingest.main_track import is_main_track, report_counts
from ingest.openalex_fetch import fetch_works
from ingest.openalex_parse import parse_work
from shared.build_silver import build_rows
from shared.gold_combined import write_gender_by_region
from shared.name_match import names_match

ROOT = pathlib.Path(__file__).parents[1]
STAGES = ("dblp", "main-track", "openalex", "genderize", "silver", "gold")


@dataclass(frozen=True)
class Paths:
    dump: pathlib.Path
    dtd: pathlib.Path
    dblp: pathlib.Path
    openalex: pathlib.Path
    gender_cache: pathlib.Path
    silver: pathlib.Path
    review_log: pathlib.Path
    gold_dir: pathlib.Path

    @classmethod
    def under(cls, root):
        root = pathlib.Path(root)
        data = root / "data"
        return cls(
            dump=root / "dblp.xml.gz",
            dtd=root / "dblp.dtd",
            dblp=data / "bronze" / "dblp" / "icse_ecsa_icsa_filtered.json",
            openalex=data / "bronze" / "openalex",
            gender_cache=data / "bronze" / "genderize" / "gender_lookup.json",
            silver=data / "silver" / "silver_rows.json",
            review_log=data / "silver" / "position_mismatches.jsonl",
            gold_dir=data / "gold",
        )


def _read_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _main_track_papers(records):
    return [
        r
        for r in records
        if r["record_type"] == "inproceedings" and is_main_track(r["crossref"])
    ]


def stage_dblp(paths):
    records = filter_dump(paths.dump, paths.dtd)
    paths.dblp.parent.mkdir(parents=True, exist_ok=True)
    write_records(records, paths.dblp)
    print(f"Wrote {len(records):,} DBLP records to {paths.dblp}")


def stage_main_track(paths):
    counts = report_counts(_read_json(paths.dblp))
    print(f"{sum(counts.values()):,} main-track papers")
    for (venue, year), n in sorted(counts.items()):
        print(f"  {venue:6s} {year}  {n:>4}")


def stage_openalex(paths):
    seen, dois = set(), []
    for rec in _main_track_papers(_read_json(paths.dblp)):
        doi = rec.get("doi")
        if doi and doi.lower() not in seen:
            seen.add(doi.lower())
            dois.append(doi)
    print(f"Fetching OpenAlex works for {len(dois):,} DOIs (cached ones are skipped)")
    fetch_works(dois, paths.openalex)


def stage_genderize(paths):
    load_dotenv()
    api_key = os.getenv("GENDERIZE_API_KEY")
    names = dblp_author_names(paths.dblp)

    if not api_key:
        result = lookup_new(names, paths.gender_cache, None, dry_run=True)
        if result["new_names"]:
            print(
                f"GENDERIZE_API_KEY is not set: {result['new_names']:,} new names "
                "will be labeled unknown"
            )
        return

    try:
        lookup_new(names, paths.gender_cache, api_key, confirm=True)
    except EOFError:
        print("No answer to the Genderize prompt; nothing sent, new names stay unknown")
    except GenderizeError as e:
        # The cache is saved after every batch, so finished lookups are kept
        # and the next run picks up where this one stopped.
        reason = "quota reached" if e.status == 429 else "request failed"
        print(f"Genderize {reason} ({e}); lookups so far are saved")
        lookup_new(names, paths.gender_cache, None, dry_run=True)
        print("Remaining new names stay unknown until the next genderize run")


def stage_silver(paths):
    works = [parse_work(_read_json(p)) for p in sorted(paths.openalex.glob("*.json"))]
    if not works:
        print(f"No OpenAlex works in {paths.openalex}; rows will have no affiliations")
    rows = build_rows(
        _read_json(paths.dblp),
        works,
        _read_json(paths.gender_cache),
        names_match,
        primary_region,
        review_log=paths.review_log,
    )
    paths.silver.parent.mkdir(parents=True, exist_ok=True)
    paths.silver.write_text(
        json.dumps(rows, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(rows):,} silver rows to {paths.silver}")


def stage_gold(paths):
    rows = _read_json(paths.silver)
    gold = paths.gold_dir
    write_gender_yearly(rows, gold / "gender_yearly.json")
    write_region_yearly(rows, gold / REGION_FILENAME)
    write_country_yearly(rows, gold / COUNTRY_FILENAME)
    write_gender_by_region(rows, gold / "gender_by_region.json")
    print(f"Wrote gold files to {gold} from {len(rows):,} silver rows")


STAGE_FUNCTIONS = {
    "dblp": stage_dblp,
    "main-track": stage_main_track,
    "openalex": stage_openalex,
    "genderize": stage_genderize,
    "silver": stage_silver,
    "gold": stage_gold,
}


def run(stages=None, *, paths=None, refresh_dblp=False):
    """Run the given stages (all by default) in pipeline order."""
    paths = paths or Paths.under(ROOT)
    if stages is None:
        stages = [s for s in STAGES if s != "dblp" or refresh_dblp]
        if not refresh_dblp:
            print("Skipping dblp: using the committed filtered JSON (--refresh-dblp)")

    for stage in STAGES:
        if stage in stages:
            print(f"\n== {stage} ==")
            STAGE_FUNCTIONS[stage](paths)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--stage", choices=["all", *STAGES], default="all")
    parser.add_argument(
        "--refresh-dblp",
        action="store_true",
        help="re-filter dblp.xml.gz in a full run",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    stages = None if args.stage == "all" else [args.stage]
    run(stages, refresh_dblp=args.refresh_dblp)


if __name__ == "__main__":
    main()
