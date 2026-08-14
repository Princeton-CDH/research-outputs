#!/usr/bin/env python3
"""Import the CDH project catalog and classify each project by its CDH
Project-Lead facet (the `community` dimension).

Fetches cdh.princeton.edu/projects: the full listing (slug + name), each
`role=<id>` facet (1=Graduate Student, 2=Faculty, 3=Staff, 4=Postdoc,
5=External Collaborator), and `cdh_built=on`. Then, against projects.csv:
  - exact/alias name match -> enrich in place (community, cdh_built, cdh_slug)
  - fuzzy name match       -> propose, flagged as a possible duplicate (blank decision)
  - no match               -> propose as a new project (decision=keep)
Proposals land in data/incoming/cdh-projects-review.csv; merge_projects.py applies
them. Idempotent (decisions remembered in the shared ledger).

Run:  python3 scripts/sync_cdh_projects.py
"""
import csv
import os
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict

import synclib as S

BASE = "https://cdh.princeton.edu/projects/"
PROJECTS = os.path.join(S.ROOT, "data", "projects.csv")
REVIEW = f"{S.INCOMING}/cdh-projects-review.csv"

ROLE_LABEL = {"1": "Graduate Student", "2": "Faculty", "3": "Staff",
              "4": "Postdoc", "5": "External Collaborator"}
ORDER = ["Faculty", "Postdoc", "Graduate Student", "Staff", "External Collaborator"]
CARD_RE = re.compile(r'class="tile__link"\s+href="/projects/([a-z0-9-]+)/"\s*>\s*<h3>\s*(.*?)\s*</h3>', re.S)
REVIEW_COLS = ["decision", "confidence", "why", "project", "status", "community", "cdh_built", "cdh_slug"]

# CDH slug -> our existing project name, where names differ.
ALIAS = {
    "citing-marx": "Marxism’s Marx",
    "shakespeare-and-company-project": "Shakespeare and Company",
    "princeton-geniza-project": "Geniza",
    "bringing-htr-to-the-hpc": "Open HTR",
    "simulating-risk": "Simulating Risks",
    "princeton-ethiopian-miracles-mary-project": "Princeton Ethiopian, Eritrean, and Egyptian Miracles of Mary (PEMM) Project",
}


def fetch(params):
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "rse-tracking/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def parse_cards(html):
    return {slug: re.sub(r"\s+", " ", name).strip() for slug, name in CARD_RE.findall(html)}


def token_set(s):
    return set(S.normalize_title(s).split())


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def main():
    print("Fetching CDH project catalog …")
    listing = parse_cards(fetch({"current": "false"}))
    built = set(parse_cards(fetch({"cdh_built": "on", "current": "false"})))
    role_of = defaultdict(list)
    for rid, label in ROLE_LABEL.items():
        for slug in parse_cards(fetch({"role": rid, "current": "false"})):
            role_of[slug].append(label)
        time.sleep(0.3)
    print(f"  catalog: {len(listing)} projects | built-by-CDH: {len(built)}")

    with open(PROJECTS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        prows = list(reader)
        pfields = list(reader.fieldnames)
    by_norm = {S.normalize_title(r["project"]): r for r in prows}
    tokens = {r["project"]: token_set(r["project"]) for r in prows}
    decided = S.load_ledger()

    proposals, enriched, matched, skipped = [], [], 0, 0

    def community_str(slug):
        labels = sorted(set(role_of.get(slug, [])), key=lambda x: ORDER.index(x) if x in ORDER else 9)
        return ",".join(labels)

    def enrich(row, slug):
        ch = []
        comm = community_str(slug)
        if comm and not (row.get("community") or "").strip():
            row["community"] = comm; ch.append("community")
        if slug in built and not (row.get("cdh_built") or "").strip():
            row["cdh_built"] = "yes"; ch.append("cdh_built")
        if not (row.get("cdh_slug") or "").strip():
            row["cdh_slug"] = slug; ch.append("cdh_slug")
        return ch

    for slug, name in sorted(listing.items()):
        # exact / alias match
        target = by_norm.get(S.normalize_title(name)) or by_norm.get(
            S.normalize_title(ALIAS.get(slug, "")))
        if target:
            matched += 1
            ch = enrich(target, slug)
            if ch:
                enriched.append((target["project"][:32], "+".join(ch)))
            continue
        if S.already_decided(decided, "cdh", slug):
            skipped += 1
            continue
        # fuzzy — flag a likely duplicate for review
        best, score = None, 0.0
        for pname, tks in tokens.items():
            j = jaccard(token_set(name), tks)
            if j > score:
                best, score = pname, j
        if score >= 0.6:
            decision, conf, why = "", "review", f"possible duplicate of {best!r} (sim {score:.2f})"
        else:
            decision, conf, why = "keep", "new", "CDH catalog project"
        proposals.append({
            "decision": decision, "confidence": conf, "why": why,
            "project": name, "status": "", "community": community_str(slug),
            "cdh_built": "yes" if slug in built else "", "cdh_slug": slug,
        })

    if enriched:
        with open(PROJECTS, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=pfields)
            w.writeheader()
            w.writerows(prows)
    os.makedirs(S.INCOMING, exist_ok=True)
    with open(REVIEW, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REVIEW_COLS)
        w.writeheader()
        for p in proposals:
            w.writerow(p)

    keep_n = sum(1 for p in proposals if p["decision"] == "keep")
    rev_n = len(proposals) - keep_n
    print(f"\ncatalog projects: {len(listing)}")
    print(f"  matched existing        : {matched}  ({len(enriched)} enriched)")
    print(f"  already decided (ledger): {skipped}")
    print(f"  NEW proposals           : {len(proposals)}  -> {REVIEW}")
    print(f"       ├─ pre-marked keep (new project) : {keep_n}")
    print(f"       └─ needs review (possible dup)   : {rev_n}")
    if enriched:
        print("\nenriched:")
        for name, ch in enriched:
            print(f"    {name:34} {ch}")
    from collections import Counter
    cc = Counter(c for p in proposals for c in (p["community"].split(",") if p["community"] else ["(none)"]))
    print("\nnew projects by community (Project Lead):", dict(cc))


if __name__ == "__main__":
    main()
