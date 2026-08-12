#!/usr/bin/env python3
"""Apply a reviewed *-review.csv into data/outputs.csv and record decisions.

For each reviewed row:
  decision=keep  -> append a new realized output (next output_id) carrying the
                    user-assigned project/type/tier plus source/zenodo_concept/
                    zotero_key; log the decision.
  decision=skip  -> log the decision only (so it never re-surfaces).
  decision blank -> left undecided (warned, not logged) so it comes back.

Idempotent: rows already in data/sync_ledger.csv are skipped, so re-running a
merge (or merging an already-merged file) is a no-op.

Usage:
  python3 scripts/merge_incoming.py data/incoming/zenodo-review.csv          # dry run
  python3 scripts/merge_incoming.py data/incoming/zenodo-review.csv --apply  # write
"""
import csv
import datetime
import sys

import synclib as S


def infer_status(rtype):
    return "Released" if rtype == "Software Release" else "Done"


def infer_doi_service(link):
    return "Zenodo" if "zenodo" in (link or "").lower() else ""


def to_output_row(rev, output_id):
    src = (rev.get("source") or "").strip()
    key = (rev.get("upstream_key") or "").strip()
    return {
        "output_id": output_id,
        "output_name": rev.get("output_name", ""),
        "project": rev.get("project", ""),
        "type": rev.get("type", ""),
        "tier": rev.get("tier", ""),
        "status": infer_status((rev.get("type") or "").strip()),
        "assignee": rev.get("assignee", ""),
        "link": rev.get("link", ""),
        "doi_service": infer_doi_service(rev.get("link", "")),
        "completed_date": rev.get("completed_date", ""),
        "availability": "",
        "description": "",
        "alt_id": rev.get("alt_id", ""),
        "source": src,
        "zenodo_concept": key if src == "zenodo" else "",
        "zotero_key": key if src == "zotero" else "",
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    if not args:
        sys.exit("usage: merge_incoming.py <review.csv> [--apply]")
    review_path = args[0]

    with open(review_path, newline="", encoding="utf-8") as f:
        review = list(csv.DictReader(f))
    rows, fields = S.load_outputs()
    decided = S.load_ledger()
    mk_id = S.next_output_id(rows)
    today = datetime.date.today().isoformat()

    to_add, ledger_entries, blanks, already = [], [], [], 0
    i = 0
    for rev in review:
        src = (rev.get("source") or "").strip()
        key = (rev.get("upstream_key") or "").strip()
        decision = (rev.get("decision") or "").strip().lower()
        if S.already_decided(decided, src, key):
            already += 1
            continue
        if decision == "keep":
            i += 1
            oid = mk_id(i)
            new_row = to_output_row(rev, oid)
            to_add.append(new_row)
            ledger_entries.append({"source": src, "upstream_key": key, "decision": "keep",
                                   "output_id": oid, "decided_date": today,
                                   "title": rev.get("output_name", "")})
        elif decision == "skip":
            ledger_entries.append({"source": src, "upstream_key": key, "decision": "skip",
                                   "output_id": "", "decided_date": today,
                                   "title": rev.get("output_name", "")})
        else:
            blanks.append(rev.get("output_name", ""))

    # New projects not yet in projects.csv (informational).
    known_projects = {r["project"] for r in rows}
    new_projects = sorted({r["project"] for r in to_add if r["project"] and r["project"] not in known_projects})

    print(f"review file: {review_path}")
    print(f"  keep  -> add {len(to_add)} new output(s): {to_add[0]['output_id'] if to_add else '-'}"
          f"…{to_add[-1]['output_id'] if to_add else ''}")
    print(f"  skip  -> log {sum(1 for e in ledger_entries if e['decision']=='skip')}")
    print(f"  already decided (skipped): {already}")
    if blanks:
        print(f"  ⚠ blank decision (left undecided, will re-surface): {len(blanks)}")
        for b in blanks[:10]:
            print(f"      {b[:52]!r}")
    if new_projects:
        print(f"  ⚠ new projects to add to data/projects.csv: {new_projects}")

    if not apply:
        print("\n(dry run — re-run with --apply to write)")
        return

    if to_add:
        with open(S.OUTPUTS, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows + to_add)
    if ledger_entries:
        S.append_ledger(ledger_entries)
    print(f"\napplied: outputs.csv now {len(rows) + len(to_add)} rows; "
          f"ledger +{len(ledger_entries)} decisions.")


if __name__ == "__main__":
    main()
