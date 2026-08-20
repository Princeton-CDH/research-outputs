#!/usr/bin/env python3
"""One-time: remove graduate-student-led work from the published data.

Before making the tracker public we drop graduate-student projects from the
dataset entirely (not just hidden in the dashboard views). The `community`
field on data/projects.csv carries CDH's Project-Lead classification, and
"Graduate Student" is one value of it (often multi-valued).

Rules:
  - A project whose community is *solely* "Graduate Student" is deleted, and
    any of its outputs in data/outputs.csv are deleted too (outputs link to a
    project by name; they inherit community at load time).
  - A project co-led with someone else (e.g. "Faculty,Graduate Student") is
    KEPT, but the "Graduate Student" token is stripped from its community so the
    label disappears from the interface while the project is retained.

CSV fields contain quoted commas, so this uses csv.DictReader/DictWriter rather
than naive splitting. Idempotent: re-running when nothing grad-tagged remains is
a no-op reporting 0 changes. Kept for provenance alongside the other one-time
data scripts.

Run:  python3 scripts/remove_grad_projects.py
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROJECTS = os.path.join(ROOT, "data", "projects.csv")
OUTPUTS = os.path.join(ROOT, "data", "outputs.csv")

GRAD = "Graduate Student"


def communities(row):
    """Split the multi-valued `community` field into trimmed, non-empty parts."""
    return [c.strip() for c in (row.get("community") or "").split(",") if c.strip()]


def main():
    # --- projects.csv: drop solely-grad rows, detag mixed rows ---
    with open(PROJECTS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        project_rows = list(reader)
        project_fields = list(reader.fieldnames)

    kept_projects, dropped_names, detagged = [], set(), []
    for r in project_rows:
        comms = communities(r)
        if comms == [GRAD]:
            dropped_names.add((r.get("project") or "").strip())
            continue
        if GRAD in comms:
            remaining = [c for c in comms if c != GRAD]
            r["community"] = ",".join(remaining)
            detagged.append((r.get("project") or "").strip())
        kept_projects.append(r)

    with open(PROJECTS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=project_fields)
        w.writeheader()
        w.writerows(kept_projects)

    # --- outputs.csv: drop outputs of the deleted projects ---
    with open(OUTPUTS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        output_rows = list(reader)
        output_fields = list(reader.fieldnames)

    kept_outputs, dropped_outputs = [], []
    for r in output_rows:
        if (r.get("project") or "").strip() in dropped_names:
            dropped_outputs.append(r)
        else:
            kept_outputs.append(r)

    with open(OUTPUTS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=output_fields)
        w.writeheader()
        w.writerows(kept_outputs)

    # --- report ---
    print(f"projects: dropped {len(dropped_names)} solely-grad, "
          f"detagged {len(detagged)} mixed, kept {len(kept_projects)} total")
    for name in sorted(dropped_names):
        print(f"  - dropped   {name[:60]}")
    for name in detagged:
        print(f"  ~ detagged  {name[:60]}")
    print(f"outputs:  dropped {len(dropped_outputs)}, kept {len(kept_outputs)}")
    for r in dropped_outputs:
        print(f"  - {(r.get('output_id') or '').strip()}  {(r.get('output_name') or '')[:55]}")


if __name__ == "__main__":
    main()
