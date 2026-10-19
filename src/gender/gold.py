"""Aggregate silver authorship rows into yearly gender statistics."""

import json
import pathlib

GENDER_LABELS = (
    "female-presenting",
    "male-presenting",
    "unclassified",
    "unknown",
)
CLASSIFIED_LABELS = ("female-presenting", "male-presenting")
ROOT = pathlib.Path(__file__).parents[2]
OUTPUT_PATH = ROOT / "data" / "gold" / "gender_yearly.json"


def gender_pct(counts):
    """Return female/male percentages, excluding unclassified and unknown."""
    classified_total = sum(counts.get(label, 0) for label in CLASSIFIED_LABELS)
    if classified_total == 0:
        return {label: None for label in CLASSIFIED_LABELS}
    return {
        label: counts.get(label, 0) / classified_total * 100
        for label in CLASSIFIED_LABELS
    }


def gender_counts(rows):
    """Aggregate author-slot counts and gender percentages by venue and year."""
    groups = {}
    for row in rows:
        label = row["gender_label"]
        if label not in GENDER_LABELS:
            raise ValueError(f"Unexpected gender label: {label!r}")

        key = (row["venue"], row["year"], row["joint_wicsa_ecsa"])
        group = groups.setdefault(
            key,
            {
                "venue": row["venue"],
                "year": row["year"],
                "joint_wicsa_ecsa": row["joint_wicsa_ecsa"],
                "all_authors": {label: 0 for label in GENDER_LABELS},
                "first_authors": {label: 0 for label in GENDER_LABELS},
            },
        )
        group["all_authors"][label] += 1
        if row["author_position"] == 0:
            group["first_authors"][label] += 1

    result = []
    for key in sorted(groups):
        group = groups[key]
        for author_group in ("all_authors", "first_authors"):
            counts = group[author_group]
            group[author_group] = {
                "counts": counts,
                "percentages": gender_pct(counts),
            }
        result.append(group)
    return result


def write_gender_yearly(rows, output_path=OUTPUT_PATH):
    """Write aggregated yearly gender statistics as JSON."""
    output_path = pathlib.Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(gender_counts(rows), indent=2) + "\n",
        encoding="utf-8",
    )
