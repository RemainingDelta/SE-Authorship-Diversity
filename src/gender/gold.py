"""Aggregate silver authorship rows into yearly gender statistics.

PYTHONPATH=src python -m gender.gold <silver_rows.json> [out.json]
"""

import json
import pathlib
import sys

# TODO: move to shared.config once it holds the gender labels (see docs/SCHEMA.md).
GENDER_LABELS = ["female-presenting", "male-presenting", "unclassified", "unknown"]
# Only these go into percentage denominators.
CLASSIFIED_GENDER_LABELS = ["female-presenting", "male-presenting"]
ROOT = pathlib.Path(__file__).parents[2]
OUTPUT_PATH = ROOT / "data" / "gold" / "gender_yearly.json"
PCT_DECIMALS = 2


def gender_pct(counts):
    """Return female/male percentages, excluding unclassified and unknown."""
    classified_total = sum(counts.get(label, 0) for label in CLASSIFIED_GENDER_LABELS)
    if classified_total == 0:
        return {label: None for label in CLASSIFIED_GENDER_LABELS}
    return {
        label: round(counts.get(label, 0) / classified_total * 100, PCT_DECIMALS)
        for label in CLASSIFIED_GENDER_LABELS
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


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if not 1 <= len(args) <= 2:
        sys.exit("usage: python -m gender.gold <silver_rows.json> [out.json]")
    rows = json.loads(pathlib.Path(args[0]).read_text(encoding="utf-8"))
    output_path = pathlib.Path(args[1]) if len(args) == 2 else OUTPUT_PATH
    write_gender_yearly(rows, output_path)
    print(f"Wrote {output_path} from {len(rows):,} silver rows")


if __name__ == "__main__":
    main()
