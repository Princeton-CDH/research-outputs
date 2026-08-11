#!/usr/bin/env python3
"""Build the yearly metrics rollup from all snapshots.

Reads every ``snapshots/metrics-*.csv`` and produces
``rollups/yearly-metrics.csv`` with one row per (output x metric type x year):

  lifetime_count  the cumulative total as of that year (what the provider reports)
  yearly_delta    lifetime_count(year) - lifetime_count(previous year present)

Snapshot counts are lifetime-cumulative, so the delta is the views/downloads an
output actually earned during that calendar year. The first year an output
appears has no prior baseline, so its delta is blank. A negative delta (a count
that dropped year-over-year) is left as-is — it flags a data issue worth a look.

If two snapshots cover the same year (e.g. a mid-year backfill plus a year-end
re-harvest), the one with the later ``retrieved_date`` wins.

Run:  python3 scripts/build_rollup.py
"""

import csv
import glob
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SNAP = os.path.join(ROOT, "snapshots")
ROLLUP = os.path.join(ROOT, "rollups", "yearly-metrics.csv")

OUT_COLS = ["output_id", "output_name", "project", "metric_type", "year",
            "lifetime_count", "yearly_delta"]


def to_int(s):
    s = (s or "").strip()
    try:
        return int(float(s))
    except ValueError:
        return None


def main() -> None:
    files = sorted(glob.glob(os.path.join(SNAP, "metrics-*.csv")))
    if not files:
        raise SystemExit("No snapshots found in snapshots/ — run fetch or backfill first.")

    # (output_key, metric_type, year) -> chosen row, keeping latest retrieved_date.
    chosen: dict = {}
    for path in files:
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                okey = (r.get("output_id") or "").strip() or (r.get("link") or "").strip()
                mt = (r.get("metric_type") or "").strip()
                year = (r.get("retrieved_date") or "").strip()[:4]
                if not (okey and mt and year):
                    continue
                k = (okey, mt, year)
                prev = chosen.get(k)
                if prev is None or r.get("retrieved_date", "") > prev.get("retrieved_date", ""):
                    chosen[k] = r

    # Group by output+metric, walk years in order to compute deltas.
    series = defaultdict(dict)  # (okey, mt) -> {year: row}
    for (okey, mt, year), row in chosen.items():
        series[(okey, mt)][year] = row

    out_rows = []
    for (okey, mt), years in series.items():
        prev_val = None
        for year in sorted(years):
            row = years[year]
            val = to_int(row.get("count"))
            delta = "" if (val is None or prev_val is None) else val - prev_val
            out_rows.append({
                "output_id": (row.get("output_id") or "").strip(),
                "output_name": (row.get("output_name") or "").strip(),
                "project": (row.get("project") or "").strip(),
                "metric_type": mt,
                "year": year,
                "lifetime_count": "" if val is None else val,
                "yearly_delta": delta,
            })
            if val is not None:
                prev_val = val

    out_rows.sort(key=lambda r: (r["project"], r["output_name"], r["metric_type"], r["year"]))

    os.makedirs(os.path.dirname(ROLLUP), exist_ok=True)
    with open(ROLLUP, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLS)
        w.writeheader()
        w.writerows(out_rows)

    years = sorted({r["year"] for r in out_rows})
    print(f"Wrote {len(out_rows)} rows -> rollups/yearly-metrics.csv")
    print(f"Years: {', '.join(years)} | from {len(files)} snapshot(s)")


if __name__ == "__main__":
    main()
