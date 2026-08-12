#!/usr/bin/env python3
"""Sync the CDH Zotero group collection into the ingest review pipeline.

Zotero is the noisier source: ~179 items, mostly presentations, many without
DOIs, and some not tied to a CDH project. For every item:
  - if it matches an existing output  -> enrich in place (backfill zotero_key /
    a blank link or date) and report — this captures Zenodo↔Zotero overlap
  - else if already decided            -> skip (ledger)
  - else                               -> propose it in data/incoming/zotero-review.csv
      * roster author (tightened)  -> decision=keep  (auto-classified in scope)
      * otherwise                  -> decision=<blank> (needs your triage)

Run:  python3 scripts/sync_zotero.py
"""
import csv
import json
import time
import urllib.request

import synclib as S

GROUP = "1657550"
COLLECTION = "BUG8AC3A"
REVIEW = f"{S.INCOMING}/zotero-review.csv"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "rse-tracking/1.0"})
    r = urllib.request.urlopen(url=req, timeout=30)
    return r, json.load(r)


def fetch_collection():
    base = f"https://api.zotero.org/groups/{GROUP}/collections/{COLLECTION}/items/top?format=json&limit=100"
    items, start = [], 0
    while True:
        r, batch = get(base + f"&start={start}")
        items += batch
        if len(items) >= int(r.headers.get("Total-Results", "0")) or not batch:
            break
        start += 100
        time.sleep(0.3)
    return items


def normalize(it):
    d = it["data"]
    key = d.get("key", "")
    doi = (d.get("DOI") or "").strip()
    isbn = (d.get("ISBN") or "").strip()
    url = (d.get("url") or "").strip()
    creators = [S.name_first_last(c) for c in d.get("creators", []) if S.name_first_last(c)]
    date = d.get("date", "")
    link = f"https://doi.org/{doi}" if doi else url
    alt = f"isbn:{S.normalize_isbn(isbn)}" if (isbn and not doi) else ""
    return {
        "upstream_key": key,
        "zotero_key": key,
        "doi": doi,
        "isbn": isbn,
        "zenodo_ids": [S.zenodo_id(url), S.zenodo_id(doi)],
        "title": d.get("title", ""),
        "year": S.year_of(date),
        "assignee": ",".join(creators),
        "creators": d.get("creators", []),
        "type": S.map_zotero_type(d.get("itemType", "")),
        "itemType": d.get("itemType", ""),
        "link": link,
        "alt_id": alt,
        "completed_date": S.iso_to_us(date),
    }


def enrich(row, item):
    changed = []
    if not (row.get("zotero_key") or "").strip() and item["zotero_key"]:
        row["zotero_key"] = item["zotero_key"]; changed.append("zotero_key")
    if not (row.get("link") or "").strip() and item["link"]:
        row["link"] = item["link"]; changed.append("link")
    if not (row.get("completed_date") or "").strip() and item["completed_date"]:
        row["completed_date"] = item["completed_date"]; changed.append("completed_date")
    return changed


def main():
    print(f"Fetching Zotero collection {COLLECTION} …")
    items = fetch_collection()
    rows, fields = S.load_outputs()
    idx = S.OutputsIndex(rows)
    by_oid = {r["output_id"]: r for r in rows}
    decided = S.load_ledger()
    roster = S.roster_names()

    proposals, enriched, matched, skipped = [], [], 0, 0
    keep_n = ambiguous_n = 0
    for it in items:
        item = normalize(it)
        oid, how = idx.match(item)
        if oid:
            matched += 1
            ch = enrich(by_oid[oid], item)
            if ch:
                enriched.append((oid, how, ch, item["title"][:38]))
            continue
        if S.already_decided(decided, "zotero", item["upstream_key"]):
            skipped += 1
            continue
        roster_match = S.roster_author_name(item["creators"], roster)
        if roster_match:
            decision, conf = "keep", "high"
            why = f"roster author ({roster_match}); {item['itemType']}"
            keep_n += 1
        else:
            decision, conf = "", "low"
            why = f"{item['itemType']}; {'external DOI' if item['doi'] else 'no DOI'}, no roster author"
            ambiguous_n += 1
        proposals.append({
            "decision": decision, "confidence": conf, "why": why,
            "project": "", "output_name": item["title"], "type": item["type"], "tier": "",
            "assignee": item["assignee"], "link": item["link"], "alt_id": item["alt_id"],
            "completed_date": item["completed_date"], "source": "zotero",
            "upstream_key": item["upstream_key"],
        })

    if enriched:
        with open(S.OUTPUTS, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    S.write_review(REVIEW, proposals)

    print(f"\ncollection items: {len(items)}")
    print(f"  matched existing outputs : {matched}  ({len(enriched)} enriched — Zotero↔outputs overlap)")
    print(f"  already decided (ledger) : {skipped}")
    print(f"  NEW proposals            : {len(proposals)}  -> {REVIEW}")
    print(f"       ├─ pre-marked keep (roster author): {keep_n}")
    print(f"       └─ blank (needs your triage)      : {ambiguous_n}")
    if enriched:
        print("\nenriched (overlap captured):")
        for oid, how, ch, title in enriched[:15]:
            print(f"    {oid} (via {how}): {'+'.join(ch)}   {title!r}")
    print("\nsample proposals:")
    for p in proposals[:12]:
        mark = p["decision"] or "·"
        print(f"    [{mark:4}] {p['output_name'][:46]!r:48} — {p['why']}")


if __name__ == "__main__":
    main()
