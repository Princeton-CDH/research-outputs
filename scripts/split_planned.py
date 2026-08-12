#!/usr/bin/env python3
"""One-time: split planned/forecast work out of data/outputs.csv.

`outputs.csv` is becoming a *generated* artifact reconciled from the canonical
sources (Zenodo + Zotero), so it should hold only **realized** outputs
(status Released/Done). Planned and hypothetical works — which don't exist in
those sources yet — move to a new hand-maintained `data/planned.csv` with a
lean, Zenhub-oriented schema.

This script:
  - reads data/outputs.csv,
  - writes the non-realized rows to data/planned.csv (mapped to the planned
    schema, assigned p001… ids), and
  - rewrites data/outputs.csv with only the realized rows (columns unchanged).

Idempotent-ish: re-running when nothing is left to move is a no-op that just
reports 0 moved. Kept for provenance alongside the other one-time builders.

Run:  python3 scripts/split_planned.py
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTPUTS = os.path.join(ROOT, "data", "outputs.csv")
PLANNED = os.path.join(ROOT, "data", "planned.csv")

REALIZED_STATUSES = {"Released", "Done"}

PLANNED_COLS = [
    "planned_id", "name", "project", "type", "tier", "status",
    "owner", "milestone", "target_date", "priority", "notes",
]


def to_planned(row, i):
    """Map an outputs.csv row to the planned schema. milestone/priority are
    left blank for manual fill; target_date seeds from completed_date if set."""
    return {
        "planned_id": f"p{i:03d}",
        "name": (row.get("output_name") or "").strip(),
        "project": (row.get("project") or "").strip(),
        "type": (row.get("type") or "").strip(),
        "tier": (row.get("tier") or "").strip(),
        "status": (row.get("status") or "").strip(),
        "owner": (row.get("assignee") or "").strip(),
        "milestone": "",
        "target_date": (row.get("completed_date") or "").strip(),
        "priority": "",
        "notes": (row.get("description") or "").strip(),
    }


def main():
    with open(OUTPUTS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames)

    realized, planned_src = [], []
    for r in rows:
        (realized if (r.get("status") or "").strip() in REALIZED_STATUSES
         else planned_src).append(r)

    planned_rows = [to_planned(r, i) for i, r in enumerate(planned_src, start=1)]

    with open(PLANNED, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=PLANNED_COLS)
        w.writeheader()
        w.writerows(planned_rows)

    with open(OUTPUTS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(realized)

    print(f"moved {len(planned_rows)} planned row(s) -> data/planned.csv")
    print(f"kept  {len(realized)} realized row(s) in data/outputs.csv")
    for p in planned_rows:
        print(f"  {p['planned_id']}  [{p['status']}]  {p['name'][:55]}")


if __name__ == "__main__":
    main()
