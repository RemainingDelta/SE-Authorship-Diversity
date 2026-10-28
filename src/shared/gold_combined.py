"""Aggregate silver authorship rows by venue, year, and region.

PYTHONPATH=src python -m shared.gold_combined <silver_rows.json> [out.json]
"""

import json
import pathlib
import sys

from gender.gold import GENDER_LABELS, gender_pct

ROOT = pathlib.Path(__file__).parents[2]
OUTPUT_PATH = ROOT / "data" / "gold" / "gender_by_region.json"


def gender_by_region(rows):
    """Count authors and gender percentages per venue, year, and region.

    Grouped by the joint WICSA/ECSA flag too, like gender.gold, so charts can
    leave the joint years out of per-venue trends.
    """
    groups = {}
    for row in rows:
        label = row["gender_label"]
        if label not in GENDER_LABELS:
            raise ValueError(f"Unexpected gender label: {label!r}")

        key = (row["venue"], row["year"], row["joint_wicsa_ecsa"], row["region"])
        group = groups.setdefault(
            key,
            {
                "venue": row["venue"],
                "year": row["year"],
                "joint_wicsa_ecsa": row["joint_wicsa_ecsa"],
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


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if not 1 <= len(args) <= 2:
        sys.exit("usage: python -m shared.gold_combined <silver_rows.json> [out.json]")
    rows = json.loads(pathlib.Path(args[0]).read_text(encoding="utf-8"))
    output_path = pathlib.Path(args[1]) if len(args) == 2 else OUTPUT_PATH
    write_gender_by_region(rows, output_path)
    print(f"Wrote {output_path} from {len(rows):,} silver rows")


if __name__ == "__main__":
    main()
