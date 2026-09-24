#!/usr/bin/env python3
"""One-time: backfill missing completed_date in data/outputs.csv from sources.

The Zotero merge brought in rows whose date field was blank upstream or wasn't
carried through; a few manual rows never had one. Rows without a
completed_date are invisible on every time-based dashboard chart, so this
resolves each blank from the row's own provenance, in order:

  1. zotero_key   -> Zotero group item (meta.parsedDate, else data.date)
  2. zenodo DOI   -> Zenodo record metadata.publication_date
  3. any other DOI-> OpenAlex work publication_date (no API key, same source
                     as backfill_citations.py)

Dates are written in the file's existing M/D/YYYY convention. A bare year
resolves to 1/1/YYYY, a year-month to M/1/YYYY (better on a timeline than
staying invisible). Anything unresolved is printed as a hand-fill checklist.

Idempotent: only rows with a blank completed_date are touched.
Kept for provenance alongside the other one-time data scripts.

Run:  python3 scripts/backfill_dates.py
"""
import csv
import json
import os
import re
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTPUTS = os.path.join(ROOT, "data", "outputs.csv")

ZOTERO_GROUP = "1657550"  # cdh_princeton (public)


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "cdh-research-outputs/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def to_mdy(iso_ish):
    """'2021-04-29' -> '4/29/2021'; '2021-04' -> '4/1/2021'; '2021' -> '1/1/2021'."""
    m = re.match(r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", (iso_ish or "").strip())
    if not m:
        return None
    y, mo, d = m.group(1), m.group(2) or "1", m.group(3) or "1"
    return f"{int(mo)}/{int(d)}/{y}"


def from_zotero(key):
    it = get_json(f"https://api.zotero.org/groups/{ZOTERO_GROUP}/items/{key}?format=json")
    parsed = (it.get("meta") or {}).get("parsedDate")
    if parsed:
        return to_mdy(parsed)
    raw = (it.get("data") or {}).get("date") or ""
    m = re.search(r"(\d{4})", raw)
    return to_mdy(m.group(1)) if m else None


def from_zenodo(recid):
    rec = get_json(f"https://zenodo.org/api/records/{recid}")
    return to_mdy((rec.get("metadata") or {}).get("publication_date"))


def from_openalex(doi):
    work = get_json(f"https://api.openalex.org/works/doi:{doi}")
    return to_mdy(work.get("publication_date"))


def doi_of(row):
    m = re.search(r"doi\.org/(.+)$", (row.get("link") or "").strip(), re.I)
    return m.group(1).rstrip("/") if m else None


def resolve(row):
    """Return (date, source_used) or (None, None). Tries all sources in order."""
    zk = (row.get("zotero_key") or "").strip()
    if zk:
        try:
            d = from_zotero(zk)
            if d:
                return d, f"zotero:{zk}"
        except Exception:
            pass
    doi = doi_of(row)
    if doi:
        m = re.match(r"10\.5281/zenodo\.(\d+)", doi, re.I)
        if m:
            try:
                d = from_zenodo(m.group(1))
                if d:
                    return d, f"zenodo:{m.group(1)}"
            except Exception:
                pass
        try:
            d = from_openalex(doi)
            if d:
                return d, f"openalex:{doi}"
        except Exception:
            pass
    return None, None


def main():
    with open(OUTPUTS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames)

    blank = [r for r in rows if not (r.get("completed_date") or "").strip()]
    print(f"{len(blank)} rows missing completed_date")

    filled, unresolved = [], []
    for r in blank:
        date, src = resolve(r)
        if date:
            r["completed_date"] = date
            filled.append((r["output_id"], date, src))
        else:
            unresolved.append(r)
        time.sleep(0.3)  # be polite to the APIs

    with open(OUTPUTS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f"filled {len(filled)}:")
    for oid, date, src in filled:
        print(f"  {oid}  {date:>10}  ({src})")
    if unresolved:
        print(f"\nhand-fill checklist ({len(unresolved)} unresolved):")
        for r in unresolved:
            print(f"  {r['output_id']}  {r['output_name'][:55]!r}  link={r.get('link') or '-'}")


if __name__ == "__main__":
    main()
