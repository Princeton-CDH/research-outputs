#!/usr/bin/env python3
"""Data loader: clean data/outputs.csv into analysis-ready JSON.

Emits one record per output with multi-valued `type`/`assignee` split into
arrays, `completed_date` normalized to ISO (YYYY-MM-DD), and derived
`realized` / `has_link` flags. Prints a JSON array to stdout.
"""
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUTS_CSV = REPO_ROOT / "data" / "outputs.csv"
PEOPLE_CSV = REPO_ROOT / "data" / "people.csv"
PROJECTS_CSV = REPO_ROOT / "data" / "projects.csv"

REALIZED_STATUSES = {"Released", "Done"}


def load_roles():
    """name -> list of (role, start, end) periods from data/people.csv.

    Roles are time-aware: a person may hold different roles over time (e.g.
    Post Doc -> CDH staff), one row per period. Blank role_start/role_end
    means open-ended on that side; a single blank-blank row is a constant role.
    """
    roles = {}
    if PEOPLE_CSV.exists():
        with PEOPLE_CSV.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                name = (row.get("name") or "").strip()
                if name:
                    roles.setdefault(name, []).append(
                        (
                            (row.get("role") or "").strip() or "Unknown",
                            parse_mdy(row.get("role_start")),
                            parse_mdy(row.get("role_end")),
                        )
                    )
    return roles


def role_for(roles, name, on_date):
    """Role held by `name` on `on_date` (a date or None).

    Undated outputs and dates outside every period fall back to the person's
    current (open-ended) role, else their last listed one. Names not in
    people.csv are external collaborators.
    """
    periods = roles.get(name)
    if not periods:
        return "External"
    if on_date:
        for role, start, end in periods:
            if (start is None or start <= on_date) and (end is None or on_date <= end):
                return role
    for role, start, end in periods:
        if end is None:
            return role
    return periods[-1][0]


def load_project_communities():
    """project name -> list of CDH communities, from data/projects.csv."""
    comm = {}
    if PROJECTS_CSV.exists():
        with PROJECTS_CSV.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                p = (row.get("project") or "").strip()
                if p:
                    comm[p] = [c.strip() for c in (row.get("community") or "").split(",") if c.strip()]
    return comm


def parse_mdy(value):
    """M/D/YYYY -> datetime.date, or None if blank/unparseable."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%m/%d/%Y").date()
    except ValueError:
        return None


def split_multi(value):
    """Comma-separated field -> list of trimmed, non-empty strings."""
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def main():
    roles = load_roles()
    communities = load_project_communities()
    records = []
    with OUTPUTS_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            status = (row.get("status") or "").strip()
            link = (row.get("link") or "").strip()
            assignees = split_multi(row.get("assignee"))
            lead = assignees[0] if assignees else None
            completed = parse_mdy(row.get("completed_date"))
            records.append(
                {
                    "output_id": (row.get("output_id") or "").strip(),
                    "output_name": (row.get("output_name") or "").strip(),
                    "project": (row.get("project") or "").strip(),
                    "community": communities.get((row.get("project") or "").strip(), []),
                    "type": split_multi(row.get("type")),
                    "tier": (row.get("tier") or "").strip() or None,
                    "status": status,
                    "realized": status in REALIZED_STATUSES,
                    "assignee": assignees,
                    "lead": lead,
                    "lead_role": role_for(roles, lead, completed) if lead else "Unknown",
                    "link": link or None,
                    "has_link": bool(link),
                    "doi_service": (row.get("doi_service") or "").strip() or None,
                    "completed_date": completed.isoformat() if completed else None,
                    "availability": (row.get("availability") or "").strip() or None,
                    "description": (row.get("description") or "").strip() or None,
                }
            )
    json.dump(records, sys.stdout, ensure_ascii=False, indent=None)


if __name__ == "__main__":
    main()
