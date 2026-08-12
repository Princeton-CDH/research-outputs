#!/usr/bin/env python3
"""Sync the Zenodo `princetoncdh` community into the ingest review pipeline.

For every record in the community:
  - if it matches an existing output   -> enrich that row in place (backfill
    zenodo_concept / source / a blank link or date) and report it
  - else if it was already decided      -> skip (the ledger remembers)
  - else                                -> propose it in data/incoming/zenodo-review.csv
                                            pre-marked decision=keep (community
                                            items are in scope by definition)

Idempotent: matched rows and ledgered rows are suppressed, so a re-run with no
merge in between proposes the same set once and nothing new after a merge.

Run:  python3 scripts/sync_zenodo.py
"""
import csv
import json
import time
import urllib.request

import synclib as S

COMMUNITY = "princetoncdh"
REVIEW = f"{S.INCOMING}/zenodo-review.csv"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "rse-tracking/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r, json.load(r)


def fetch_community():
    recs, page = [], 1
    while True:
        _, j = get(f"https://zenodo.org/api/communities/{COMMUNITY}/records?size=10&page={page}&sort=newest")
        hits = j["hits"]["hits"]
        recs += hits
        if len(recs) >= j["hits"]["total"] or not hits:
            break
        page += 1
        time.sleep(0.4)
    return recs


def normalize(rec):
    md = rec.get("metadata", {})
    rt = md.get("resource_type", {})
    concept = str(rec.get("conceptrecid") or "")
    conceptdoi = rec.get("conceptdoi") or rec.get("doi") or ""
    creators = [S.name_first_last(c) for c in md.get("creators", []) if S.name_first_last(c)]
    pubdate = md.get("publication_date", "")
    return {
        "upstream_key": concept,
        "zenodo_concept": concept,
        "zenodo_ids": [str(rec.get("id") or ""), concept],
        "doi": conceptdoi,
        "title": md.get("title", ""),
        "year": S.year_of(pubdate),
        "assignee": ",".join(creators),
        "type": S.map_zenodo_type(rt.get("type"), rt.get("subtype")),
        "status": "Released" if rt.get("type") == "software" else "Done",
        "link": f"https://doi.org/{conceptdoi}" if conceptdoi else "",
        "completed_date": S.iso_to_us(pubdate),
    }


def enrich(row, item):
    """Fill blank provenance/link/date fields on a matched output. Returns changed fields."""
    changed = []
    if not (row.get("zenodo_concept") or "").strip() and item["zenodo_concept"]:
        row["zenodo_concept"] = item["zenodo_concept"]; changed.append("zenodo_concept")
    if (row.get("source") or "").strip() in ("", "manual") and (row.get("source") or "") != "zenodo":
        row["source"] = "zenodo"; changed.append("source")
    if not (row.get("link") or "").strip() and item["link"]:
        row["link"] = item["link"]; changed.append("link")
    if not (row.get("completed_date") or "").strip() and item["completed_date"]:
        row["completed_date"] = item["completed_date"]; changed.append("completed_date")
    return changed


def main():
    print(f"Fetching Zenodo community '{COMMUNITY}' …")
    recs = fetch_community()
    rows, fields = S.load_outputs()
    idx = S.OutputsIndex(rows)
    by_oid = {r["output_id"]: r for r in rows}
    decided = S.load_ledger()

    proposals, enriched, matched, skipped = [], [], 0, 0
    for rec in recs:
        item = normalize(rec)
        oid, how = idx.match(item)
        if oid:
            matched += 1
            ch = enrich(by_oid[oid], item)
            if ch:
                enriched.append((oid, how, ch, item["title"][:40]))
            continue
        if S.already_decided(decided, "zenodo", item["upstream_key"]):
            skipped += 1
            continue
        proposals.append({
            "decision": "keep", "confidence": "high", "why": "zenodo community item",
            "project": "", "output_name": item["title"], "type": item["type"], "tier": "",
            "assignee": item["assignee"], "link": item["link"], "alt_id": "",
            "completed_date": item["completed_date"], "source": "zenodo",
            "upstream_key": item["upstream_key"],
        })

    if enriched:
        with open(S.OUTPUTS, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    S.write_review(REVIEW, proposals)

    print(f"\ncommunity records: {len(recs)}")
    print(f"  matched existing outputs : {matched}  ({len(enriched)} enriched in place)")
    print(f"  already decided (ledger) : {skipped}")
    print(f"  NEW proposals            : {len(proposals)}  -> {REVIEW}")
    if enriched:
        print("\nenriched:")
        for oid, how, ch, title in enriched[:20]:
            print(f"    {oid} (via {how}): {'+'.join(ch)}   {title!r}")
    if proposals:
        print("\nproposed (all pre-marked keep — assign a project):")
        for p in proposals[:20]:
            print(f"    {p['type'][:20]:20} {p['output_name'][:48]!r}")


if __name__ == "__main__":
    main()
