"""Main-track rule for DBLP records, plus a per-venue, per-year count report.

Ported from the standalone validate_main_track.py. Run the report to check
counts against known published numbers:

    PYTHONPATH=src python -m ingest.main_track [filtered.json]
"""

import json
import re
import sys
from collections import Counter

from shared.config import MAIN_TRACK_CROSSREF

_MAIN_TRACK = re.compile(MAIN_TRACK_CROSSREF)

DEFAULT_IN = "data/bronze/dblp/icse_ecsa_icsa_filtered.json"


def is_main_track(crossref: str | None) -> bool:
    """True when the crossref points at a venue's main proceedings volume."""
    return bool(crossref and _MAIN_TRACK.match(crossref))


def report_counts(records) -> Counter:
    """Count main-track papers per (DBLP venue key, year).

    Only inproceedings records are papers; proceedings records describe the
    volume itself. Venue keys are DBLP's (wicsa stays wicsa here); mapping
    WICSA to ICSA happens when silver rows are built.
    """
    counts = Counter()
    for rec in records:
        if rec["record_type"] != "inproceedings":
            continue
        m = _MAIN_TRACK.match(rec.get("crossref") or "")
        if m:
            counts[(m.group(1), int(m.group(2)))] += 1
    return counts


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IN
    with open(path, encoding="utf-8") as fh:
        records = json.load(fh)

    papers = sum(1 for r in records if r["record_type"] == "inproceedings")
    counts = report_counts(records)
    kept = sum(counts.values())

    print(f"Papers (all tracks): {papers:,}")
    print(f"Main track:          {kept:,}")
    print(f"Excluded:            {papers - kept:,}\n")
    for (venue, year), n in sorted(counts.items()):
        print(f"  {venue:6s} {year}  {n:>4}")


if __name__ == "__main__":
    main()
