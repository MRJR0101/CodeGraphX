"""
Parse a CodeGraphX dry run relocation report (.txt) and emit a CSV summary.

Run directly to convert ``dry_run_relocation_report.txt`` next to this file to
``dry_run_relocation_report.csv``. The core parsing logic is exposed as
``parse_txt_content`` so it can be imported and unit-tested without hitting disk.
"""

from __future__ import annotations

import csv
from pathlib import Path

TXT_REPORT = Path(__file__).resolve().parent / "dry_run_relocation_report.txt"
CSV_REPORT = Path(__file__).resolve().parent / "dry_run_relocation_report.csv"


def parse_txt_content(content: str) -> list[list[str]]:
    """Parse a dry run report string into ``[action, source, target]`` rows.

    The report is a sequence of ``EVALUATING: <path>`` blocks followed by
    ``TARGET:`` and an action tag. Blocks without all three pieces are dropped.
    Pure function so it can be unit-tested without touching the filesystem.
    """
    parsed: list[list[str]] = []

    for block in content.split("EVALUATING: ")[1:]:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if len(lines) < 2:
            continue

        src_path = lines[0]
        target_path = ""
        action = ""

        for line in lines[1:]:
            if line.startswith("└─ TARGET:"):
                target_path = line.replace("└─ TARGET:", "").strip()
            elif line.startswith("└─ [REJECTED]:"):
                action = "REJECTED"
            elif line.startswith("└─ [DRY RUN PURGE"):
                action = "PURGE (Duplicate)"
            elif line.startswith("└─ [DRY RUN RELOCATE"):
                action = "RELOCATE"

        if src_path and target_path and action:
            parsed.append([action, src_path, target_path])

    return parsed


def convert_txt_to_csv(
    txt_report: Path = TXT_REPORT,
    csv_report: Path = CSV_REPORT,
) -> int:
    """Read ``txt_report``, write ``csv_report``, return number of rows written."""
    print(f"Reading {txt_report}...")

    if not txt_report.exists():
        print(f"TXT Report not found: {txt_report}")
        return 0

    content = txt_report.read_text(encoding="utf-8", errors="ignore")
    rows = parse_txt_content(content)

    print(f"Parsed {len(rows)} valid mappings. Exporting to CSV...")

    with open(csv_report, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["Action", "Source Path", "Recommended Target"])
        writer.writerows(rows)

    print(f"Successfully created: {csv_report}")
    return len(rows)


if __name__ == "__main__":
    convert_txt_to_csv()
