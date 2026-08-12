#!/usr/bin/env python3
"""One-time: backfill 'Citation Count' into the existing snapshots from OpenAlex.

The harvester never collected citations, so the only citation figures on record
were a few hand-entered values from Airtable. OpenAlex exposes a per-year
citation history (``counts_by_year``) for every DOI, which lets us reconstruct
each output's *cumulative* citation total as of each snapshot's year and write it
back into that snapshot — exactly the lifetime-count shape build_rollup expects.

For a snapshot taken in year Y, cumulative citations = lifetime total minus every
citation received after Y. Only outputs cited at least once get rows.

Re-runnable: it replaces any existing 'Citation Count' rows in each snapshot.
After running, rebuild the rollup:  python3 scripts/build_rollup.py

Run:  python3 scripts/backfill_citations.py
"""
import csv
import glob
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTPUTS = os.path.join(ROOT, "data", "outputs.csv")
SNAP = os.path.join(ROOT, "snapshots")

OPENALEX_MAIL = "cdh@princeton.edu"
DOI_RE = re.compile(r"(10\.\d{4,9}/\S+)")
METRIC = "Citation Count"
TIMEOUT = 20
SLEEP_BETWEEN = 0.15


def extract_doi(link: str):
    m = DOI_RE.search(link or "")
    return m.group(1).rstrip("/.") if m else None


def openalex_entity(o: dict):
    """Return the OpenAlex lookup path for an output: a DOI, or an explicit
    OpenAlex work id from the alt_id column (e.g. 'openalex:W123' for books
    that have an ISBN but no DOI). None if neither is present."""
    doi = extract_doi(o.get("link", ""))
    if doi:
        return "https://doi.org/" + urllib.parse.quote(doi, safe="")
    alt = (o.get("alt_id") or "").strip()
    if alt.lower().startswith("openalex:"):
        return alt.split(":", 1)[1].strip()
    return None


def fetch_openalex(entity: str):
    """Return (cited_by_count, {year: count}) for an OpenAlex entity, or (None, {})."""
    url = (
        "https://api.openalex.org/works/" + entity
        + "?mailto=" + OPENALEX_MAIL + "&select=cited_by_count,counts_by_year"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "rse-tracking/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            j = json.load(resp)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! OpenAlex {entity}: {exc}", file=sys.stderr)
        return None, {}
    cby = {c["year"]: c["cited_by_count"] for c in j.get("counts_by_year", [])}
    return j.get("cited_by_count"), cby


def cumulative_through(total: int, cby: dict, year: int) -> int:
    """Lifetime citations as of end of `year` = total minus later-year citations."""
    return total - sum(c for y, c in cby.items() if y > year)


def main() -> None:
    snaps = sorted(glob.glob(os.path.join(SNAP, "metrics-*.csv")))
    if not snaps:
        sys.exit("No snapshots found in snapshots/.")

    with open(OUTPUTS, encoding="utf-8", newline="") as f:
        outputs = [o for o in csv.DictReader(f) if openalex_entity(o)]

    # Fetch OpenAlex once per output (by DOI, or by pinned OpenAlex id for books).
    cites = {}  # output_id -> (total, counts_by_year)
    print(f"Fetching citations for {len(outputs)} outputs from OpenAlex …")
    for o in outputs:
        total, cby = fetch_openalex(openalex_entity(o))
        if isinstance(total, int):
            cites[o["output_id"]] = (total, cby)
        time.sleep(SLEEP_BETWEEN)

    cited = {oid: v for oid, v in cites.items() if v[0] and v[0] > 0}
    print(f"  {len(cites)} indexed, {len(cited)} with >=1 citation.")

    out_by_id = {o["output_id"]: o for o in outputs}
    total_rows = 0
    for path in snaps:
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames
            rows = [r for r in reader if (r.get("metric_type") or "").strip() != METRIC]
        # Snapshot's year, from any row's retrieved_date.
        dates = [(r.get("retrieved_date") or "").strip() for r in rows if r.get("retrieved_date")]
        if not dates:
            print(f"  ! {os.path.basename(path)}: no retrieved_date, skipping")
            continue
        snap_date = max(dates)
        snap_year = int(snap_date[:4])

        added = 0
        for oid, (total, cby) in sorted(cited.items()):
            o = out_by_id[oid]
            val = cumulative_through(total, cby, snap_year)
            rows.append({
                "output_id": oid,
                "link": (o.get("link") or "").strip(),
                "output_name": o.get("output_name", ""),
                "project": o.get("project", ""),
                "type": o.get("type", ""),
                "metric_type": METRIC,
                "count": val,
                "retrieved_date": snap_date,
                "status": "openalex",
            })
            added += 1

        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        total_rows += added
        print(f"  {os.path.basename(path)} (year {snap_year}): +{added} citation rows")

    print(f"\nWrote {total_rows} citation rows across {len(snaps)} snapshots.")
    print("Next: python3 scripts/build_rollup.py")


if __name__ == "__main__":
    main()
