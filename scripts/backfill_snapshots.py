#!/usr/bin/env python3
"""One-time backfill: curated Airtable Access_Metrics table -> per-year snapshots.

The Airtable export ``Access_Metrics-Grid view (2).csv`` is a curated multi-year
table: each row is one (output x metric type) observation tagged with a ``Year``
(2024/2025/2026), and it already includes hand-entered counts for the
manual-only providers (CulturalAnalytics / MITPress / PubPub). We split it by
year into ``snapshots/metrics-<date>.csv`` files matching the schema that the
live pipeline (fetch_metrics.py) writes going forward.

Counts are lifetime-cumulative as of each year, so build_rollup.py can compute
per-year deltas across them.

Run:  python3 scripts/backfill_snapshots.py
"""

import csv
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SNAP = os.path.join(ROOT, "snapshots")

SOURCE = os.path.join(ROOT, "archive", "airtable-exports", "Access_Metrics-Grid view (2).csv")
OUTPUTS = os.path.join(ROOT, "data", "outputs.csv")

# Representative "as of" date stamped on each backfilled year — the date the
# annual metrics were pulled (mid-year, June 30). 2026 uses its actual export
# date. The live pipeline stamps its own real retrieval date, and build_rollup
# keeps the latest snapshot per year.
YEAR_DATE = {"2024": "2024-06-30", "2025": "2025-06-30", "2026": "2026-08-11"}

SNAPSHOT_COLS = ["output_id", "link", "output_name", "project", "type",
                 "metric_type", "count", "retrieved_date", "status"]


def canon_link(raw: str) -> str:
    s = (raw or "").strip()
    if s.startswith("http://"):
        s = "https://" + s[len("http://"):]
    return s


def load_output_ids() -> dict:
    with open(OUTPUTS, encoding="utf-8", newline="") as f:
        return {canon_link(o["link"]): o["output_id"]
                for o in csv.DictReader(f) if (o["link"] or "").strip()}


def main() -> None:
    os.makedirs(SNAP, exist_ok=True)
    link_to_id = load_output_ids()

    with open(SOURCE, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    by_year = defaultdict(list)
    unmatched = set()
    for r in rows:
        year = (r.get("Year") or "").strip()
        if year not in YEAR_DATE:
            continue
        link = canon_link(r.get("Link (from Outputs)"))
        oid = link_to_id.get(link, "")
        if link and not oid:
            unmatched.add(link)
        count = (r.get("Count") or "").strip()
        by_year[year].append({
            "output_id": oid,
            "link": link,
            "output_name": (r.get("Outputs") or "").strip(),
            "project": (r.get("Project (from Outputs)") or "").strip(),
            "type": (r.get("Type (from Outputs)") or "").strip(),
            "metric_type": (r.get("Metric Type") or "").strip(),
            "count": count,
            "retrieved_date": YEAR_DATE[year],
            "status": "ok" if count else "no-count",
        })

    for year, recs in sorted(by_year.items()):
        path = os.path.join(SNAP, f"metrics-{YEAR_DATE[year]}.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=SNAPSHOT_COLS)
            w.writeheader()
            w.writerows(recs)
        print(f"Wrote {len(recs):>3} rows -> snapshots/{os.path.basename(path)}")

    if unmatched:
        print(f"\n{len(unmatched)} metric link(s) with no matching output_id "
              "(count still recorded, output_id blank):")
        for L in sorted(unmatched):
            print(f"  - {L}")


if __name__ == "__main__":
    main()
