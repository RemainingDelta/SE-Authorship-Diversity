"""Look up gender for names not yet in the Genderize cache.

The Genderize API is paid, and the cache in data/bronze/genderize/ holds the
gender repo's 10,822 paid-for lookups. Never regenerate it: only names missing
from it are sent, after a yes/no confirmation, and the cache is saved after
every batch so an interrupted run resumes where it stopped.

    PYTHONPATH=src python -m gender.genderize --dry-run   # count new names only
    PYTHONPATH=src python -m gender.genderize             # look them up (paid)

By default only main-track authors are looked up, since silver only uses
main-track papers; --all-tracks includes companion and workshop authors too.
"""

import argparse
import json
import os
import pathlib
import time

import requests
from dotenv import load_dotenv

from gender.names import clean_name
from ingest.main_track import is_main_track

ROOT = pathlib.Path(__file__).parents[2]
DEFAULT_CACHE = ROOT / "data" / "bronze" / "genderize" / "gender_lookup.json"
DEFAULT_DBLP = ROOT / "data" / "bronze" / "dblp" / "icse_ecsa_icsa_filtered.json"

API_URL = "https://api.genderize.io"
BATCH_SIZE = 10  # Genderize's limit on names per request
REQUEST_DELAY = 0.5  # seconds between batches
TIMEOUT = 30


def _load_cache(cache_path):
    # Raises FileNotFoundError on purpose: starting from an empty cache
    # would re-buy every name.
    return json.loads(pathlib.Path(cache_path).read_text(encoding="utf-8"))


def _save_cache(cache, cache_path):
    """Write atomically, in the same format as the gender repo's cache."""
    path = pathlib.Path(cache_path)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _fetch_batch(names, api_key):
    params = [("name[]", name) for name in names]
    params.append(("apikey", api_key))
    resp = requests.get(API_URL, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    results = resp.json()
    if len(results) != len(names):
        raise ValueError(f"Sent {len(names)} names, got {len(results)} results")
    return results


def _confirmed(n_new):
    answer = input(f"Send {n_new:,} new names to Genderize (paid)? [y/N] ")
    return answer.strip().lower() in ("y", "yes")


def lookup_new(names, cache_path, api_key, confirm=True, dry_run=False) -> dict:
    """Look up names missing from the cache and add them to it.

    Names go through clean_name() first, since that is how the cache is keyed.
    Returns {"new_names": count not in the cache, "looked_up": count sent}.
    """
    cache = _load_cache(cache_path)
    new = list(dict.fromkeys(n for n in map(clean_name, names) if n not in cache))
    print(f"{len(cache):,} names cached, {len(new):,} new")

    if dry_run or not new:
        return {"new_names": len(new), "looked_up": 0}
    if not api_key:
        raise ValueError("GENDERIZE_API_KEY is not set")
    if confirm and not _confirmed(len(new)):
        print("Cancelled; nothing sent")
        return {"new_names": len(new), "looked_up": 0}

    batches = [new[i : i + BATCH_SIZE] for i in range(0, len(new), BATCH_SIZE)]
    for i, batch in enumerate(batches, 1):
        results = _fetch_batch(batch, api_key)
        # Key by the name we sent: Genderize echoes back only the first name.
        for name, result in zip(batch, results):
            cache[name] = {
                "gender": result.get("gender"),
                "probability": result.get("probability"),
                "count": result.get("count"),
            }
        _save_cache(cache, cache_path)
        print(f"  batch {i}/{len(batches)}: {len(cache):,} cached")
        time.sleep(REQUEST_DELAY)

    return {"new_names": len(new), "looked_up": len(new)}


def dblp_author_names(dblp_path=DEFAULT_DBLP, all_tracks=False):
    """Author names on paper records in the filtered DBLP data.

    Main-track papers only unless all_tracks is set.
    """
    records = json.loads(pathlib.Path(dblp_path).read_text(encoding="utf-8"))
    return [
        a
        for r in records
        if r["record_type"] == "inproceedings"
        and (all_tracks or is_main_track(r["crossref"]))
        for a in r["authors"]
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="only count new names")
    parser.add_argument(
        "--all-tracks", action="store_true", help="include non-main-track authors"
    )
    parser.add_argument("--dblp", default=DEFAULT_DBLP)
    parser.add_argument("--cache", default=DEFAULT_CACHE)
    args = parser.parse_args(argv)

    load_dotenv()
    result = lookup_new(
        dblp_author_names(args.dblp, args.all_tracks),
        args.cache,
        os.getenv("GENDERIZE_API_KEY"),
        dry_run=args.dry_run,
    )
    print(result)


if __name__ == "__main__":
    main()
