#!/usr/bin/env python3
"""One-time / idempotent schema prep for the CDH-community reframe.

- projects.csv: add `community` (CDH Project-Lead facet, comma-separated),
  `cdh_built` (yes/blank), and `cdh_slug` (CDH project slug) if missing. Values
  are filled by sync_cdh_projects.py; this only ensures the columns exist.
- people.csv: trim stray leading/trailing whitespace on name/role (two roles had
  a leading space, e.g. " Faculty").

Safe to re-run.

Run:  python3 scripts/add_project_columns.py
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROJECTS = os.path.join(ROOT, "data", "projects.csv")
PEOPLE = os.path.join(ROOT, "data", "people.csv")

NEW_COLS = ["community", "cdh_built", "cdh_slug"]


def add_project_columns():
    with open(PROJECTS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames)
    added = [c for c in NEW_COLS if c not in fields]
    for c in NEW_COLS:
        if c not in fields:
            fields.append(c)
    for r in rows:
        for c in NEW_COLS:
            r.setdefault(c, "")
    with open(PROJECTS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return added, fields


def clean_people():
    with open(PEOPLE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames)
    fixed = 0
    for r in rows:
        for k in list(r.keys()):
            v = (r.get(k) or "")
            if v != v.strip():
                r[k] = v.strip()
                fixed += 1
    with open(PEOPLE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return fixed


def main():
    added, fields = add_project_columns()
    fixed = clean_people()
    print(f"projects.csv columns added: {added or '(none — already present)'}")
    print(f"projects.csv columns: {fields}")
    print(f"people.csv whitespace fixes: {fixed}")
    from collections import Counter
    roles = Counter(r["role"] for r in csv.DictReader(open(PEOPLE, encoding="utf-8")))
    print(f"people.csv roles now: {dict(roles)}")


if __name__ == "__main__":
    main()
