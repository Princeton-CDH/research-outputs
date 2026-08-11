#!/usr/bin/env python3
"""One-time migration: Airtable grid-view exports -> canonical repo CSVs.

Reads the three raw Airtable exports in the parent folder and writes cleaned,
normalized ``data/projects.csv`` and ``data/outputs.csv`` that become the
hand-maintained source of truth. After this runs once, Airtable is no longer
read — you edit the two data CSVs directly.

Deterministic: outputs get stable ``output_id``s (o001…) assigned by the
Airtable ``Order`` sort key, so re-running produces identical IDs. Safe to
delete this script afterward; kept in scripts/ for provenance.

Run:  python3 scripts/migrate_from_airtable.py
"""

import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

EXPORTS = os.path.join(ROOT, "archive", "airtable-exports")
PROJECTS_SRC = os.path.join(EXPORTS, "Projects-Grid view (1).csv")
OUTPUTS_SRC = os.path.join(EXPORTS, "Outputs-Grid view (1).csv")

PROJECTS_OUT = os.path.join(DATA, "projects.csv")
OUTPUTS_OUT = os.path.join(DATA, "outputs.csv")


def dedupe_list(cell: str) -> str:
    """Collapse a comma-joined Airtable cell to unique, order-preserved items."""
    seen, keep = set(), []
    for item in (cell or "").split(","):
        item = item.strip()
        if item and item not in seen:
            seen.add(item)
            keep.append(item)
    return ", ".join(keep)


def canon_link(raw: str) -> str:
    """Normalize a link: http->https, strip. Already-canonical doi.org URLs pass through."""
    s = (raw or "").strip()
    if s.startswith("http://"):
        s = "https://" + s[len("http://"):]
    return s


def migrate_projects() -> int:
    with open(PROJECTS_SRC, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    fieldnames = ["project", "status", "start_date", "end_date",
                  "faculty_engagement", "notes"]
    with open(PROJECTS_OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            name = (r.get("Project") or "").strip()
            if not name:
                continue
            w.writerow({
                "project": name,
                "status": (r.get("Project Status") or "").strip(),
                "start_date": (r.get("Start date") or "").strip(),
                "end_date": (r.get("End date") or "").strip(),
                "faculty_engagement": dedupe_list(r.get("Faculty Engagement", "")),
                "notes": "",
            })
    return sum(1 for r in rows if (r.get("Project") or "").strip())


def is_stub(r: dict) -> bool:
    """True for broken fragment rows: a Task/Order but no real content."""
    keys = ["Project", "Link", "DOI", "Type", "Status", "Completed", "Assignee"]
    return not any((r.get(k) or "").strip() for k in keys)


def migrate_outputs() -> tuple[int, list[str]]:
    with open(OUTPUTS_SRC, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    kept = [r for r in rows if not is_stub(r)]
    stubs = [(r.get("Task") or "").strip() for r in rows if is_stub(r)]

    # Stable ID order: Airtable's base-36 Order key, blanks last.
    kept.sort(key=lambda r: ((r.get("Order") or "~~~"), (r.get("Task") or "")))

    fieldnames = ["output_id", "output_name", "project", "type", "tier",
                  "status", "assignee", "link", "doi_service",
                  "completed_date", "availability", "description"]
    with open(OUTPUTS_OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for i, r in enumerate(kept, start=1):
            w.writerow({
                "output_id": f"o{i:03d}",
                "output_name": (r.get("Task") or "").strip(),
                "project": (r.get("Project") or "").strip(),
                "type": (r.get("Type") or "").strip(),           # medium
                "tier": (r.get("Output Type") or "").strip(),    # Tier 1/2/3
                "status": (r.get("Status") or "").strip(),
                "assignee": (r.get("Assignee") or "").strip(),
                "link": canon_link(r.get("Link", "")),
                "doi_service": (r.get("DOI Service") or "").strip(),
                "completed_date": (r.get("Completed") or "").strip(),
                "availability": (r.get("Availability") or "").strip(),
                "description": (r.get("Description") or "").strip(),
            })
    return len(kept), stubs


def main() -> None:
    os.makedirs(DATA, exist_ok=True)
    nproj = migrate_projects()
    nout, stubs = migrate_outputs()
    print(f"Wrote {nproj} projects -> data/projects.csv")
    print(f"Wrote {nout} outputs  -> data/outputs.csv")
    if stubs:
        print(f"\nExcluded {len(stubs)} stub/fragment rows (no project, link, or type) "
              "— review and re-add by hand if any are real:")
        for s in stubs:
            print(f"  - {s!r}")


if __name__ == "__main__":
    main()
