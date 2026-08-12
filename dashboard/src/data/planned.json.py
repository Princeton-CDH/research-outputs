#!/usr/bin/env python3
"""Data loader: clean data/planned.csv into analysis-ready JSON.

`planned.csv` is the hand-maintained sheet of forecast/hypothetical outputs
(the counterpart to the increasingly-generated outputs.csv). Emits one record
per planned output with multi-valued `type`/`owner` split into arrays, a derived
`lead` + `lead_role`, and a `target_sort` key (ISO when target_date parses as
M/D/YYYY, else the raw string) for stable sorting. Prints a JSON array to stdout.
"""
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLANNED_CSV = REPO_ROOT / "data" / "planned.csv"
PEOPLE_CSV = REPO_ROOT / "data" / "people.csv"


def load_roles():
    """name -> role (Faculty / CDH / Post Doc) from data/people.csv, if present."""
    roles = {}
    if PEOPLE_CSV.exists():
        with PEOPLE_CSV.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                name = (row.get("name") or "").strip()
                if name:
                    roles[name] = (row.get("role") or "").strip() or "Unknown"
    return roles


def target_sort(value):
    """Sort key for target_date: ISO if it parses as M/D/YYYY, else raw string.
    Blank sorts last."""
    value = (value or "").strip()
    if not value:
        return "9999"
    try:
        return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return value


def split_multi(value):
    """Comma-separated field -> list of trimmed, non-empty strings."""
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def main():
    roles = load_roles()
    records = []
    if PLANNED_CSV.exists():
        with PLANNED_CSV.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                owners = split_multi(row.get("owner"))
                lead = owners[0] if owners else None
                target = (row.get("target_date") or "").strip() or None
                records.append(
                    {
                        "planned_id": (row.get("planned_id") or "").strip(),
                        "name": (row.get("name") or "").strip(),
                        "project": (row.get("project") or "").strip(),
                        "type": split_multi(row.get("type")),
                        "tier": (row.get("tier") or "").strip() or None,
                        "status": (row.get("status") or "").strip(),
                        "owner": owners,
                        "lead": lead,
                        "lead_role": roles.get(lead, "Unknown") if lead else "Unknown",
                        "milestone": (row.get("milestone") or "").strip() or None,
                        "target_date": target,
                        "target_sort": target_sort(row.get("target_date")),
                        "priority": (row.get("priority") or "").strip() or None,
                        "notes": (row.get("notes") or "").strip() or None,
                    }
                )
    json.dump(records, sys.stdout, ensure_ascii=False, indent=None)


if __name__ == "__main__":
    main()
