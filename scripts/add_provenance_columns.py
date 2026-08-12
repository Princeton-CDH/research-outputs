#!/usr/bin/env python3
"""One-time / idempotent: add provenance columns to data/outputs.csv.

Adds three trailing columns used by the two-source ingest pipeline:

  source          zenodo | zotero | manual  — where the row originated
  zenodo_concept  Zenodo concept recid (version-agnostic key), filled by sync_zenodo
  zotero_key      Zotero item key,            filled by sync_zotero

Safe to re-run: columns are only added if missing, and `source` is only set on
rows where it is blank (so manual corrections are preserved). The sync scripts
backfill zenodo_concept / zotero_key as they match items to existing rows.

Run:  python3 scripts/add_provenance_columns.py
"""
import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTPUTS = os.path.join(ROOT, "data", "outputs.csv")

NEW_COLS = ["source", "zenodo_concept", "zotero_key"]
ZENODO_RE = re.compile(r"zenodo(?:\.org/records?/|\.)\d+", re.I)


def infer_source(row):
    link = (row.get("link") or "").strip()
    return "zenodo" if ZENODO_RE.search(link) else "manual"


def main():
    with open(OUTPUTS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames)

    added = [c for c in NEW_COLS if c not in fields]
    for c in NEW_COLS:
        if c not in fields:
            fields.append(c)

    filled = 0
    for r in rows:
        for c in NEW_COLS:
            r.setdefault(c, "")
        if not (r.get("source") or "").strip():
            r["source"] = infer_source(r)
            filled += 1

    with open(OUTPUTS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    from collections import Counter
    counts = Counter(r["source"] for r in rows)
    print(f"columns added: {added or '(none — already present)'}")
    print(f"source set on {filled} row(s); distribution: {dict(counts)}")
    print(f"outputs.csv columns: {fields}")


if __name__ == "__main__":
    main()
