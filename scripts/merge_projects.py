#!/usr/bin/env python3
"""Apply a reviewed cdh-projects-review.csv into data/projects.csv + ledger.

decision=keep -> append a new project row (community/cdh_built/cdh_slug from CDH,
other columns blank for you to fill). decision=skip -> logged only. Idempotent:
rows already in data/sync_ledger.csv are skipped.

Usage:
  python3 scripts/merge_projects.py data/incoming/cdh-projects-review.csv          # dry run
  python3 scripts/merge_projects.py data/incoming/cdh-projects-review.csv --apply
"""
import csv
import datetime
import os
import sys

import synclib as S

PROJECTS = os.path.join(S.ROOT, "data", "projects.csv")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    if not args:
        sys.exit("usage: merge_projects.py <cdh-projects-review.csv> [--apply]")

    with open(args[0], newline="", encoding="utf-8") as f:
        review = list(csv.DictReader(f))
    with open(PROJECTS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames)
    decided = S.load_ledger()
    today = datetime.date.today().isoformat()

    to_add, ledger, already, blanks = [], [], 0, 0
    for rev in review:
        slug = (rev.get("cdh_slug") or "").strip()
        decision = (rev.get("decision") or "").strip().lower()
        if S.already_decided(decided, "cdh", slug):
            already += 1
            continue
        if decision == "keep":
            new = {c: "" for c in fields}
            new.update({
                "project": rev.get("project", ""),
                "status": rev.get("status", ""),
                "community": rev.get("community", ""),
                "cdh_built": rev.get("cdh_built", ""),
                "cdh_slug": slug,
            })
            to_add.append(new)
            ledger.append({"source": "cdh", "upstream_key": slug, "decision": "keep",
                           "output_id": "", "decided_date": today, "title": rev.get("project", "")})
        elif decision == "skip":
            ledger.append({"source": "cdh", "upstream_key": slug, "decision": "skip",
                           "output_id": "", "decided_date": today, "title": rev.get("project", "")})
        else:
            blanks += 1

    print(f"review file: {args[0]}")
    print(f"  keep  -> add {len(to_add)} project(s)")
    print(f"  skip  -> log {sum(1 for e in ledger if e['decision']=='skip')}")
    print(f"  already decided: {already}" + (f" | ⚠ blank (undecided): {blanks}" if blanks else ""))

    if not apply:
        print("\n(dry run — re-run with --apply to write)")
        return
    if to_add:
        with open(PROJECTS, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows + to_add)
    if ledger:
        S.append_ledger(ledger)
    print(f"\napplied: projects.csv now {len(rows) + len(to_add)} rows; ledger +{len(ledger)}.")


if __name__ == "__main__":
    main()
