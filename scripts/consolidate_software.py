#!/usr/bin/env python3
"""One-time: one output per software package, not one per release.

The Zotero/Zenodo sweeps added a row per version release (e.g. three
"Princeton-CDH/mep-django: vX" rows) alongside the curated package-level rows,
which carry a Zenodo *concept* DOI — the version-agnostic identifier whose
stats already aggregate across all releases. This folds every release row into
its package row:

  - the package row keeps its name/date/link and absorbs the union of the
    release rows' assignees (contributor credit survives);
  - derrida-django had no package row, so its earliest release (o201) becomes
    one (renamed, repointed at the concept DOI 10.5281/zenodo.1299971);
  - dropped rows' sync-ledger entries flip keep -> skip so no sweep
    resurfaces them;
  - package rows get zenodo_concept filled where missing, so the Zenodo sync's
    concept matching recognizes future releases as already-tracked.

Run build_rollup.py afterwards to prune the dropped rows' metric rows.
Idempotent: a re-run finds nothing to drop. Kept for provenance alongside the
other one-time data scripts.

Run:  python3 scripts/consolidate_software.py
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTPUTS = os.path.join(ROOT, "data", "outputs.csv")
LEDGER = os.path.join(ROOT, "data", "sync_ledger.csv")

# package row -> release rows folded into it
GROUPS = {
    "o016": ["o177", "o179", "o180"],  # mep-django
    "o201": ["o178", "o181"],          # derrida-django (o201 becomes the package row)
    "o011": ["o172"],                  # corppa
    "o035": ["o182"],                  # ppa-django
    "o020": ["o175"],                  # annotorious-tahqiq
    "o018": ["o173"],                  # djiffy
    "o054": ["o176"],                  # piffle
    "o057": ["o174"],                  # django-pucas
}
# field fixes applied to kept package rows
FIXES = {
    "o201": {
        "output_name": "derrida-django",
        "link": "https://doi.org/10.5281/zenodo.1299971",
        "zenodo_concept": "1299971",
    },
    "o035": {"zenodo_concept": "2400704"},
}


def main():
    with open(OUTPUTS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames)
    by_id = {r["output_id"]: r for r in rows}

    drop_ids = set()
    for keep_id, release_ids in GROUPS.items():
        keeper = by_id.get(keep_id)
        if keeper is None:
            continue
        merged = [a.strip() for a in (keeper.get("assignee") or "").split(",") if a.strip()]
        for rid in release_ids:
            r = by_id.get(rid)
            if r is None:
                continue
            drop_ids.add(rid)
            for a in (r.get("assignee") or "").split(","):
                a = a.strip()
                if a and a not in merged:
                    merged.append(a)
        keeper["assignee"] = ",".join(merged)
        keeper.update(FIXES.get(keep_id, {}))

    kept = [r for r in rows if r["output_id"] not in drop_ids]
    with open(OUTPUTS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(kept)

    # ledger: dropped rows must never resurface from a sweep
    with open(LEDGER, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        led = list(reader)
        lfields = list(reader.fieldnames)
    flipped = 0
    for l in led:
        if l.get("output_id") in drop_ids and l.get("decision") == "keep":
            l["decision"] = "skip"
            flipped += 1
    with open(LEDGER, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=lfields)
        w.writeheader()
        w.writerows(led)

    print(f"outputs: {len(rows)} -> {len(kept)} (dropped {sorted(drop_ids)})")
    print(f"ledger entries flipped keep->skip: {flipped}")
    for keep_id in GROUPS:
        r = by_id.get(keep_id)
        if r:
            print(f"  {keep_id}  {r['output_name'][:28]:30s} assignees: {r['assignee'][:70]}")


if __name__ == "__main__":
    main()
