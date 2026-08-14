#!/usr/bin/env python3
"""Data loader: rollups/yearly-metrics.csv -> analysis-ready long-format JSON.

Coerces `year`/`lifetime_count`/`yearly_delta` to numbers (blank -> null) and
left-joins each metric row to its output (by `output_id`) to attach `type`,
`tier`, and `status` so the impact page can facet without a client-side join.
Prints a JSON array to stdout.
"""
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
METRICS_CSV = REPO_ROOT / "rollups" / "yearly-metrics.csv"
OUTPUTS_CSV = REPO_ROOT / "data" / "outputs.csv"
PEOPLE_CSV = REPO_ROOT / "data" / "people.csv"
PROJECTS_CSV = REPO_ROOT / "data" / "projects.csv"

REALIZED_STATUSES = {"Released", "Done"}

# Website analytics vs. published-output (DOI) metrics — different units/scales,
# so the dashboard keeps them in separate sections.
WEB_METRICS = {"Active Users"}


def to_int(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def first_type(value):
    """outputs.type may be multi-valued; use the first for faceting."""
    parts = [p.strip() for p in (value or "").split(",") if p.strip()]
    return parts[0] if parts else None


def pub_year(value):
    """Year of an output's completed_date (M/D/YYYY), or None."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%m/%d/%Y").year
    except ValueError:
        return None


def load_roles():
    roles = {}
    if PEOPLE_CSV.exists():
        with PEOPLE_CSV.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                name = (row.get("name") or "").strip()
                if name:
                    roles[name] = (row.get("role") or "").strip() or "Unknown"
    return roles


def load_project_communities():
    comm = {}
    if PROJECTS_CSV.exists():
        with PROJECTS_CSV.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                p = (row.get("project") or "").strip()
                if p:
                    comm[p] = [c.strip() for c in (row.get("community") or "").split(",") if c.strip()]
    return comm


def load_output_index():
    roles = load_roles()
    communities = load_project_communities()
    index = {}
    with OUTPUTS_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            oid = (row.get("output_id") or "").strip()
            if not oid:
                continue
            status = (row.get("status") or "").strip()
            assignees = [a.strip() for a in (row.get("assignee") or "").split(",") if a.strip()]
            lead = assignees[0] if assignees else None
            index[oid] = {
                "project": (row.get("project") or "").strip(),
                "community": communities.get((row.get("project") or "").strip(), []),
                "type": first_type(row.get("type")),
                "tier": (row.get("tier") or "").strip() or None,
                "status": status,
                "realized": status in REALIZED_STATUSES,
                "link": (row.get("link") or "").strip() or None,
                "pub_year": pub_year(row.get("completed_date")),
                "lead": lead,
                "lead_role": roles.get(lead, "Unknown") if lead else "Unknown",
            }
    return index


def main():
    outputs = load_output_index()
    records = []
    with METRICS_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            oid = (row.get("output_id") or "").strip()
            meta = outputs.get(oid, {})
            metric_type = (row.get("metric_type") or "").strip()
            # Prefer the canonical project name from outputs.csv (via output_id);
            # the rollup's project string can be stale after a project rename.
            project = meta.get("project") or (row.get("project") or "").strip().strip('"')
            records.append(
                {
                    "output_id": oid,
                    "output_name": (row.get("output_name") or "").strip().strip('"'),
                    "project": project,
                    "community": meta.get("community", []),
                    "metric_type": metric_type,
                    "metric_family": "web" if metric_type in WEB_METRICS else "publication",
                    "year": to_int(row.get("year")),
                    "lifetime_count": to_int(row.get("lifetime_count")),
                    "yearly_delta": to_int(row.get("yearly_delta")),
                    "type": meta.get("type"),
                    "tier": meta.get("tier"),
                    "status": meta.get("status"),
                    "link": meta.get("link"),
                    "pub_year": meta.get("pub_year"),
                    "lead": meta.get("lead"),
                    "lead_role": meta.get("lead_role"),
                }
            )
    json.dump(records, sys.stdout, ensure_ascii=False, indent=None)


if __name__ == "__main__":
    main()
