#!/usr/bin/env python3
"""Data loader: clean data/projects.csv into analysis-ready JSON.

Splits the multi-valued `status` field into an array, normalizes dates to ISO,
and splits `faculty_engagement` (a comma-separated list of meetings) into an
array with a count. Prints a JSON array to stdout.
"""
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECTS_CSV = REPO_ROOT / "data" / "projects.csv"


def parse_date(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def split_multi(value):
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def main():
    records = []
    with PROJECTS_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            engagements = split_multi(row.get("faculty_engagement"))
            records.append(
                {
                    "project": (row.get("project") or "").strip(),
                    "status": split_multi(row.get("status")),
                    "start_date": parse_date(row.get("start_date")),
                    "end_date": parse_date(row.get("end_date")),
                    "faculty_engagement": engagements,
                    "engagement_count": len(engagements),
                    "notes": (row.get("notes") or "").strip() or None,
                    "community": split_multi(row.get("community")),
                    "cdh_built": (row.get("cdh_built") or "").strip().lower() == "yes",
                    "cdh_slug": (row.get("cdh_slug") or "").strip() or None,
                }
            )
    json.dump(records, sys.stdout, ensure_ascii=False, indent=None)


if __name__ == "__main__":
    main()
