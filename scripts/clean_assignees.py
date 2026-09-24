#!/usr/bin/env python3
"""One-time: normalize assignee names in data/outputs.csv.

The Zotero/Zenodo ingests carried author names through verbatim, which left the
assignee column with GitHub handles, typos, all-caps names, a truncated org
name, and one non-person entry. This maps each bad token to its canonical form
(matching data/people.csv where the person is on the roster) and drops tokens
that aren't people. External co-authors are deliberately kept as-is — the
dashboard renders their outputs' lead_role as "External".

Resolution provenance (2026-09-24):
  - meg-codes / older name variants -> Meg Hicks, the roster name in
    data/people.csv (the GitHub login's commits resolve to this person).
  - The Princeton: Zenodo record 14888965 (o175) lists "The Center for Digital
    Humanities at Princeton" — the name was truncated at a comma on import.
  - Rebecca Koeser -> Rebecca Sutton Koeser: canonical form per people.csv.
  - yorukoglu: no recoverable real name (GitHub profile and commits are
    nameless) — left as-is on purpose.

Idempotent: re-running when nothing matches is a no-op reporting 0 changes.
Kept for provenance alongside the other one-time data scripts.

Run:  python3 scripts/clean_assignees.py
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTPUTS = os.path.join(ROOT, "data", "outputs.csv")

# bad token -> canonical name
ALIASES = {
    "Rebecca Koeser": "Rebecca Sutton Koeser",
    "gissoo": "Gissoo Doroudian",
    "xinyil": "Xinyi Li",
    "meg-codes": "Meg Hicks",
    "Benjamin Hicks": "Meg Hicks",
    "Nicholas Budak": "Nick Budak",
    "Natalia Ermoalev": "Natalia Ermolaev",
    "Abdellatif Mohamed": "Mohamed Abdellatif",
    "BEN GLASER": "Ben Glaser",
    "JONATHAN CULLER": "Jonathan Culler",
    "J. Porter": "J.D. Porter",
    "The Princeton": "The Center for Digital Humanities at Princeton",
}

# tokens that aren't people at all
DROP = {"Automated code reviews"}


def main():
    with open(OUTPUTS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames)

    changed = []
    for r in rows:
        tokens = [t.strip() for t in (r.get("assignee") or "").split(",") if t.strip()]
        new_tokens = [ALIASES.get(t, t) for t in tokens if t not in DROP]
        # a rename can collide with a name already in the list; keep first occurrence
        seen, deduped = set(), []
        for t in new_tokens:
            if t not in seen:
                seen.add(t)
                deduped.append(t)
        new_val = ",".join(deduped)
        if new_val != (r.get("assignee") or ""):
            changed.append((r["output_id"], r.get("assignee") or "", new_val))
            r["assignee"] = new_val

    with open(OUTPUTS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f"assignees: changed {len(changed)} of {len(rows)} rows")
    for oid, old, new in changed:
        print(f"  {oid}  {old[:70]!r}\n        -> {new[:70]!r}")


if __name__ == "__main__":
    main()
