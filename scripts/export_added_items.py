#!/usr/bin/env python3
"""One-off export: every item ADDED to the CDH Zenodo community and Zotero
collections within a fiscal-year window (default 2025-07-01 .. 2026-06-30).

Separate from the dashboard pipeline. Unlike sync_zenodo/sync_zotero — which keep
only the *publication* date — this fetches fresh and captures the date each item
was ADDED to its source (Zenodo record `created`, Zotero `dateAdded`), filters on
that added date, and carries both the added and published dates side by side.

Zotero coverage spans all four top-level collections, and each item keeps its
collection as a preserved `category`:
  Publications (BUG8AC3A), Datasets (HEZPCSWC), Documentation (2CQ3L4FX),
  Software (AFINDJ6D).

Items are deduped across sources (a row present in both reads `source=zenodo,zotero`)
using the same match precedence as the ingest pipeline.

Run:  python3 scripts/export_added_items.py
Output: exports/added-items-<start>_<end>.csv
"""
import csv
import datetime
import json
import os
import sys
import time
import urllib.request

import synclib as S

# --- window (added-date filter), inclusive -----------------------------------
WINDOW_START = datetime.date(2025, 7, 1)
WINDOW_END = datetime.date(2026, 6, 30)

# --- sources -----------------------------------------------------------------
ZENODO_COMMUNITY = "princetoncdh"
ZOTERO_GROUP = "1657550"
ZOTERO_COLLECTIONS = [  # (collection key, preserved category label)
    ("BUG8AC3A", "Publications"),
    ("HEZPCSWC", "Datasets"),
    ("2CQ3L4FX", "Documentation"),
    ("AFINDJ6D", "Software"),
]

OUT_DIR = os.path.join(S.ROOT, "exports")
OUT_CSV = os.path.join(OUT_DIR, f"added-items-{WINDOW_START}_{WINDOW_END}.csv")

COLS = [
    "source", "category", "title", "type", "creators",
    "doi", "link", "date_added", "date_published", "year",
]


# ------------------------------------------------------------------ fetching
def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "rse-tracking/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r, json.load(r)


def fetch_zenodo():
    recs, page = [], 1
    while True:
        _, j = get(f"https://zenodo.org/api/communities/{ZENODO_COMMUNITY}/records?size=25&page={page}&sort=newest")
        hits = j["hits"]["hits"]
        recs += hits
        if len(recs) >= j["hits"]["total"] or not hits:
            break
        page += 1
        time.sleep(0.4)
    return recs


def fetch_zotero_collection(key):
    base = f"https://api.zotero.org/groups/{ZOTERO_GROUP}/collections/{key}/items/top?format=json&limit=100"
    items, start = [], 0
    while True:
        r, batch = get(base + f"&start={start}", headers={"User-Agent": "rse-tracking/1.0"})
        items += batch
        if len(items) >= int(r.headers.get("Total-Results", "0")) or not batch:
            break
        start += 100
        time.sleep(0.3)
    return items


# ------------------------------------------------------------- normalization
def iso_date(s):
    """First 10 chars of an ISO datetime -> 'YYYY-MM-DD', or '' if unparseable."""
    try:
        return datetime.date.fromisoformat((s or "")[:10]).isoformat()
    except ValueError:
        return ""


def norm_zenodo(rec):
    md = rec.get("metadata", {})
    rt = md.get("resource_type", {})
    concept = str(rec.get("conceptrecid") or "")
    doi = S.normalize_doi(rec.get("conceptdoi") or rec.get("doi") or "")
    creators = [S.name_first_last(c) for c in md.get("creators", []) if S.name_first_last(c)]
    pubdate = md.get("publication_date", "")
    return {
        "source": "zenodo",
        "category": "",
        "title": md.get("title", ""),
        "type": S.map_zenodo_type(rt.get("type"), rt.get("subtype")),
        "creators": ", ".join(creators),
        "doi": doi,
        "link": f"https://doi.org/{doi}" if doi else "",
        "date_added": iso_date(rec.get("created", "")),
        "date_published": iso_date(pubdate) or (pubdate or ""),
        "year": S.year_of(pubdate),
        # dedup keys (internal)
        "_doi": doi,
        "_zenodo_ids": [str(rec.get("id") or ""), concept],
        "_zenodo_concept": concept,
        "_isbn": "",
        "_title": md.get("title", ""),
    }


def norm_zotero(it, category):
    d = it["data"]
    doi = S.normalize_doi(d.get("DOI") or "")
    isbn = (d.get("ISBN") or "").strip()
    url = (d.get("url") or "").strip()
    creators = [S.name_first_last(c) for c in d.get("creators", []) if S.name_first_last(c)]
    date = d.get("date", "")
    return {
        "source": "zotero",
        "category": category,
        "title": d.get("title", ""),
        "type": S.map_zotero_type(d.get("itemType", "")),
        "creators": ", ".join(creators),
        "doi": doi,
        "link": f"https://doi.org/{doi}" if doi else url,
        "date_added": iso_date(d.get("dateAdded", "")),
        "date_published": iso_date(date) or (date or ""),
        "year": S.year_of(date),
        # dedup keys (internal)
        "_key": d.get("key", ""),
        "_doi": doi,
        "_zenodo_ids": [S.zenodo_id(url), S.zenodo_id(d.get("DOI") or "")],
        "_zenodo_concept": "",
        "_isbn": isbn,
        "_title": d.get("title", ""),
    }


# ------------------------------------------------------------------ matching
def match_keys(item):
    """The set of identifier tokens an item can be matched on (mirrors
    synclib.OutputsIndex precedence: DOI, zenodo numeric id, ISBN, title+year)."""
    keys = set()
    if item.get("_doi"):
        keys.add(("doi", item["_doi"]))
    for zid in item.get("_zenodo_ids", []) or []:
        if zid:
            keys.add(("zid", zid))
    if item.get("_zenodo_concept"):
        keys.add(("zid", item["_zenodo_concept"]))
    if item.get("_isbn"):
        keys.add(("isbn", S.normalize_isbn(item["_isbn"])))
    t = S.normalize_title(item.get("_title", ""))
    if t:
        keys.add(("ty", t, str(item.get("year", ""))))
    return keys


def merge_categories(a, b):
    cats = [c.strip() for c in (a or "").split(",") if c.strip()]
    for c in [c.strip() for c in (b or "").split(",") if c.strip()]:
        if c not in cats:
            cats.append(c)
    return ", ".join(cats)


def in_window(iso):
    try:
        d = datetime.date.fromisoformat(iso)
    except ValueError:
        return None  # unparseable / missing
    return WINDOW_START <= d <= WINDOW_END


# ------------------------------------------------------------------ main
def main():
    print(f"Window (by date added): {WINDOW_START} .. {WINDOW_END}\n")

    print(f"Fetching Zenodo community '{ZENODO_COMMUNITY}' …")
    zenodo_recs = fetch_zenodo()
    zenodo = [norm_zenodo(r) for r in zenodo_recs]
    print(f"  {len(zenodo)} records")

    print("Fetching Zotero collections …")
    zotero_by_key = {}  # item key -> normalized row (categories merged)
    per_cat = {}
    for key, category in ZOTERO_COLLECTIONS:
        items = fetch_zotero_collection(key)
        per_cat[category] = len(items)
        print(f"  {category:14} ({key}): {len(items)}")
        for it in items:
            row = norm_zotero(it, category)
            k = row["_key"]
            if k in zotero_by_key:
                zotero_by_key[k]["category"] = merge_categories(zotero_by_key[k]["category"], category)
            else:
                zotero_by_key[k] = row
    zotero = list(zotero_by_key.values())
    print(f"  {len(zotero)} unique Zotero items across {len(ZOTERO_COLLECTIONS)} collections")

    # Cross-source dedup: index Zenodo by every match key, merge Zotero into it.
    index = {}
    for z in zenodo:
        for mk in match_keys(z):
            index.setdefault(mk, z)

    merged_count = 0
    rows = list(zenodo)
    for zt in zotero:
        hit = None
        for mk in match_keys(zt):
            if mk in index:
                hit = index[mk]
                break
        if hit is not None:
            merged_count += 1
            hit["source"] = "zenodo,zotero"
            hit["category"] = merge_categories(hit["category"], zt["category"])
            # prefer Zenodo's added date; fall back to Zotero's if Zenodo's is blank
            if not hit["date_added"]:
                hit["date_added"] = zt["date_added"]
            hit["_zt_date_added"] = zt["date_added"]
            for f in ("doi", "link", "date_published", "creators", "type"):
                if not (hit.get(f) or "").strip() and zt.get(f):
                    hit[f] = zt[f]
        else:
            rows.append(zt)

    # Window filter on the added date (either contributing source in window).
    # For a merged row, `date_added` may hold Zenodo's date while it was Zotero's
    # add that fell in-window (or vice versa); surface the in-window date so the
    # column always explains why the row is included.
    kept, excluded = [], 0
    for r in rows:
        added_dates = [d for d in (r.get("date_added", ""), r.get("_zt_date_added", "")) if d]
        in_win = [d for d in added_dates if in_window(d) is True]
        if in_win:
            if in_window(r.get("date_added", "")) is not True:
                r["date_added"] = min(in_win)
            kept.append(r)
        else:
            excluded += 1

    kept.sort(key=lambda r: (r.get("category", ""), r.get("date_added", "")))

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(kept)

    # summary
    by_source = {}
    by_cat = {}
    for r in kept:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
        for c in [c.strip() for c in (r["category"] or "").split(",") if c.strip()]:
            by_cat[c] = by_cat.get(c, 0) + 1

    print("\n--- summary -------------------------------------------------")
    print(f"fetched: {len(zenodo)} Zenodo + {len(zotero)} Zotero (unique)")
    print(f"merged across sources (in both): {merged_count}")
    print(f"excluded (added date missing or outside window): {excluded}")
    print(f"\nkept in window: {len(kept)}")
    for s in sorted(by_source):
        print(f"  source {s:14}: {by_source[s]}")
    print("  by category (rows may carry >1):")
    for c in ["Publications", "Datasets", "Documentation", "Software"]:
        print(f"    {c:14}: {by_cat.get(c, 0)}")
    print(f"\nwrote {len(kept)} rows -> {os.path.relpath(OUT_CSV, S.ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
