#!/usr/bin/env python3
"""Data loader: clean data/projects.csv into analysis-ready JSON.

Splits the multi-valued `status` field into an array and normalizes dates to
ISO. Prints a JSON array to stdout.
"""
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECTS_CSV = REPO_ROOT / "data" / "projects.csv"


def parse_date(value):
    """M/D/YYYY or bare YYYY -> ISO date string, or None."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
    except ValueError:
        pass
    if value.isdigit() and len(value) == 4:
        return f"{value}-01-01"
    return None


def split_multi(value):
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def main():
    records = []
    with PROJECTS_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            # Only include projects flagged for display (display == 'y',
            # case-insensitive); blank or 'n' is excluded from all stats/charts.
            if (row.get("display") or "").strip().lower() != "y":
                continue
            records.append(
                {
                    "project": (row.get("project") or "").strip(),
                    "status": split_multi(row.get("status")),
                    "start_date": parse_date(row.get("start_date")),
                    "end_date": parse_date(row.get("end_date")),
                    "notes": (row.get("notes") or "").strip() or None,
                    "community": split_multi(row.get("community")),
                    "cdh_built": (row.get("cdh_built") or "").strip().lower() == "yes",
                    "cdh_slug": (row.get("cdh_slug") or "").strip() or None,
                }
            )
    json.dump(records, sys.stdout, ensure_ascii=False, indent=None)


if __name__ == "__main__":
    main()
