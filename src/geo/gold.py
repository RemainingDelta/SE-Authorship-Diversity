"""Aggregate silver authorship rows into yearly regional and country stats.

Counts papers, not authors (geo_data's method): a paper counts once in every
region (or country) its authors come from, so shares can add up to more than
100%. The denominator is all papers in the group.

Each author's region and country come from their first affiliation, already
set on the silver row by geo.affiliation.primary_region. A paper counts as
unknown only when none of its authors has a country.

PYTHONPATH=src python -m geo.gold <silver_rows.json> [out_dir]
"""

import json
import pathlib
import sys

from shared.config import REGIONS, UNKNOWN_REGION

ROOT = pathlib.Path(__file__).parents[2]
OUTPUT_DIR = ROOT / "data" / "gold"
REGION_FILENAME = "region_yearly.json"
COUNTRY_FILENAME = "country_yearly.json"
REGION_LABELS = [*REGIONS, UNKNOWN_REGION]
PCT_DECIMALS = 2


def _paper_key(row):
    """Identify a paper by DOI, or by title when it has no DOI."""
    if row["doi"] is not None:
        return ("doi", row["doi"])
    return ("title", row["title"])


def _paper_buckets(values):
    """Return the buckets a paper counts in: its known values, else unknown."""
    known = values - {UNKNOWN_REGION}
    return known if known else {UNKNOWN_REGION}


def _aggregate(rows, field, order_counts):
    """Count papers per (venue, year, joint flag) for each value of `field`."""
    groups = {}
    for row in rows:
        key = (row["venue"], row["year"], row["joint_wicsa_ecsa"])
        papers = groups.setdefault(key, {})
        value = row[field] if row[field] is not None else UNKNOWN_REGION
        papers.setdefault(_paper_key(row), set()).add(value)

    result = []
    for key in sorted(groups):
        venue, year, joint = key
        papers = groups[key]
        counts = {}
        for values in papers.values():
            for bucket in _paper_buckets(values):
                counts[bucket] = counts.get(bucket, 0) + 1

        counts = order_counts(counts)
        total = len(papers)
        result.append(
            {
                "venue": venue,
                "year": year,
                "joint_wicsa_ecsa": joint,
                "total_papers": total,
                "counts": counts,
                "percentages": {
                    label: round(n / total * 100, PCT_DECIMALS)
                    for label, n in counts.items()
                },
            }
        )
    return result


def _region_order(counts):
    """Every region in REGIONS order, then unknown; regions with no papers are 0."""
    return {label: counts.get(label, 0) for label in REGION_LABELS}


def _country_order(counts):
    """Countries present, sorted by code, then unknown."""
    codes = sorted(code for code in counts if code != UNKNOWN_REGION)
    ordered = {code: counts[code] for code in codes}
    ordered[UNKNOWN_REGION] = counts.get(UNKNOWN_REGION, 0)
    return ordered


def region_stats(rows):
    """Count papers per venue, year, and region."""
    for row in rows:
        if row["region"] not in REGION_LABELS:
            raise ValueError(f"Unexpected region: {row['region']!r}")
    return _aggregate(rows, "region", _region_order)


def country_stats(rows):
    """Count papers per venue, year, and country code."""
    return _aggregate(rows, "country_code", _country_order)


def _write_json(data, output_path):
    output_path = pathlib.Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_region_yearly(rows, output_path=OUTPUT_DIR / REGION_FILENAME):
    """Write yearly regional paper counts as JSON."""
    _write_json(region_stats(rows), output_path)


def write_country_yearly(rows, output_path=OUTPUT_DIR / COUNTRY_FILENAME):
    """Write yearly country paper counts as JSON."""
    _write_json(country_stats(rows), output_path)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if not 1 <= len(args) <= 2:
        sys.exit("usage: python -m geo.gold <silver_rows.json> [out_dir]")
    rows = json.loads(pathlib.Path(args[0]).read_text(encoding="utf-8"))
    output_dir = pathlib.Path(args[1]) if len(args) == 2 else OUTPUT_DIR
    write_region_yearly(rows, output_dir / REGION_FILENAME)
    write_country_yearly(rows, output_dir / COUNTRY_FILENAME)
    print(f"Wrote {REGION_FILENAME} and {COUNTRY_FILENAME} to {output_dir}")
    print(f"from {len(rows):,} silver rows")


if __name__ == "__main__":
    main()
