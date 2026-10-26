"""Aggregate silver authorship rows by venue, year, and region."""

import json
import pathlib

from gender.gold import GENDER_LABELS, gender_pct

ROOT = pathlib.Path(__file__).parents[2]
OUTPUT_PATH = ROOT / "data" / "gold" / "gender_by_region.json"


def gender_by_region(rows):
    """Count authors and gender percentages per venue, year, and region."""
    groups = {}
    for row in rows:
        label = row["gender_label"]
        if label not in GENDER_LABELS:
            raise ValueError(f"Unexpected gender label: {label!r}")

        key = (row["venue"], row["year"], row["region"])
        group = groups.setdefault(
            key,
            {
                "venue": row["venue"],
                "year": row["year"],
                "region": row["region"],
                "counts": {label: 0 for label in GENDER_LABELS},
            },
        )
        group["counts"][label] += 1

    result = []
    for key in sorted(groups):
        group = groups[key]
        group["percentages"] = gender_pct(group["counts"])
        result.append(group)
    return result


def write_gender_by_region(rows, output_path=OUTPUT_PATH):
    """Write regional gender statistics as JSON."""
    output_path = pathlib.Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(gender_by_region(rows), indent=2) + "\n",
        encoding="utf-8",
    )
