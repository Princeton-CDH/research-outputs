# RSE Project Tracking

The canonical record of RSE/CDH **projects**, their **outputs** (publications,
datasets, software, presentations, …), and the **yearly views / downloads /
citations** each output earns — plus an **Observable dashboard** for viewing it all.

You maintain a few hand-edited CSVs and run a small set of scripts on a regular
(quarterly) cadence. Airtable is no longer in the loop (its exports are kept in
`archive/` for provenance).

## Folder map

```
data/
  projects.csv            # hand-maintained: one row per project
  outputs.csv             # hand-maintained: one row per output (stable output_id)
  people.csv              # hand-maintained: name → role (Faculty / CDH / Post Doc)
snapshots/
  metrics-<date>.csv      # lifetime view/download/citation counts as of a date (time series)
rollups/
  yearly-metrics.csv      # GENERATED: per output × metric × year → lifetime + yearly gain
scripts/
  fetch_metrics.py        # harvest lifetime counts (Zenodo + OpenAlex citations) → dated snapshot
  build_rollup.py         # snapshots/* → rollups/yearly-metrics.csv
  backfill_citations.py   # (re-runnable) reconstruct historical citations from OpenAlex
  migrate_from_airtable.py  # one-time: built data/ from the Airtable exports (provenance)
  backfill_snapshots.py     # one-time: built 2024–2026 snapshots from the curated export
dashboard/                # Observable Framework app (Impact / Pipeline / Portfolio)
archive/                  # raw Airtable exports + the retired 2-stage pipeline
requirements.txt          # just `requests`
```

## Maintaining projects, outputs & people

Edit the CSVs directly (Numbers, Excel, or any text editor — they're plain CSV and
diff cleanly in git).

- **projects.csv** — `project, status, start_date, end_date, faculty_engagement, notes`.
  `project` is the key; it must match the `project` value used in outputs.csv. `status`
  may be multi-valued (comma-separated).
- **outputs.csv** — `output_id, output_name, project, type, tier, status, assignee,
  link, doi_service, completed_date, availability, description, alt_id`.
  - `output_id` is a stable key (`o001`…). Give a new output the next unused id and
    never renumber — snapshots and the rollup join on it.
  - `link` is the canonical DOI/URL. For Zenodo, prefer the **concept DOI** (the
    version-agnostic "always latest" one) over a specific version DOI.
  - `alt_id` is an optional secondary identifier for items with no usable DOI — e.g.
    `openalex:W4408262440` for a book that has only an ISBN. The citation harvester
    uses it to fetch citations (see below).
  - `assignee` is a comma-separated author list; the **first** name is treated as the
    lead. `type`/`tier` are independent facets.
  - `status` is the lifecycle: **Realized** (`Released`, `Done`) = the work exists;
    **Pipeline** (`To do`, `In progress`, `Submitted`) = planned. Move an output along
    by editing `status` in place — never move rows between files.
- **people.csv** — `name, role`. `role` is `Faculty`, `CDH`, or `Post Doc`, and drives
  the lead-author coloring on the dashboard. A lead not listed here shows as "Unknown".

## The metrics refresh (views, downloads, citations)

On your regular cadence (quarterly), or whenever you want a fresh reading:

```bash
pip install -r requirements.txt        # first time only
python3 scripts/fetch_metrics.py       # writes snapshots/metrics-<today>.csv
python3 scripts/build_rollup.py        # rebuilds rollups/yearly-metrics.csv
```

`fetch_metrics.py` reads `data/outputs.csv` and, for every output with a link, pulls:

- **Views / Downloads** — from **Zenodo** (concept-DOI aware, all-versions totals;
  handles both `…/zenodo.NNN` DOIs and `zenodo.org/records/NNN` links). Other providers
  (**DataCommons / Cultural Analytics / MIT Press / PubPub**) hide metrics behind
  JavaScript/Cloudflare, so their rows land as `manual` with a blank `count` — **fill
  those in by hand** in the new snapshot. The run's summary says how many need entry.
- **Citations** — from **OpenAlex** (free, no key), keyed by DOI or by `alt_id`
  (`openalex:…`). A `Citation Count` row is written for any output that's been cited.

`build_rollup.py` turns every snapshot into per output × metric × year rows with a
`lifetime_count` and a `yearly_delta` (what it earned that year; blank in the first
year). On same-key ties it **prefers a real value over a blank**, so hand-entered
press counts survive a later automated harvest that re-emits them blank. Website
**Active Users** are hand-maintained (no automated source).

`backfill_citations.py` is re-runnable: it uses OpenAlex `counts_by_year` to
reconstruct each output's cumulative citations *as of* each existing snapshot's year
and writes them back — useful after adding new DOI'd outputs. Rebuild the rollup after.

## The dashboard

```bash
cd dashboard
npm install            # first time only
npm run dev            # http://127.0.0.1:3000
npm run build          # static site → dashboard/dist/
```

Python **data loaders** (`dashboard/src/data/*.py`, standard-library only) read the
CSVs and rollup and emit JSON; the pages (`src/index.md` = Impact, `pipeline.md`,
`portfolio.md`) render it with Observable Plot. `node_modules/`, `dist/`, and the
`.observablehq` cache are git-ignored — `npm install && npm run build` regenerates them.

A **dormant** GitHub Pages workflow lives at `.github/workflows/deploy.yml`; activate
it per the comments in that file once the repo is on GitHub.

## Sources of published works

Zenodo (the `princetoncdh` community) is one canonical source. A second — a **Zotero**
group library — is planned, to capture books and externally-published work Zenodo
doesn't. A quarterly two-source sweep with a review/filter step is the intended
workflow (not yet built).

## History already loaded

`snapshots/` is seeded with **2024, 2025, and 2026** from the curated Airtable
Access_Metrics table (including hand-entered Cultural Analytics / MIT Press / Active
Users counts) and OpenAlex citation backfill, so `yearly-metrics.csv` has real
year-over-year deltas today.

## Rebuilding the canonical CSVs from scratch (rare)

The `*_from_airtable` / `backfill_*` scripts are one-time builders kept for provenance;
they read `archive/airtable-exports/` and regenerate `data/` and the backfilled
snapshots deterministically. You normally never run them again — edit the CSVs directly.

### Known limitation

The DataCommons HTML scrape returns nothing when the site changes its markup / fronts
it with Cloudflare; those rows fall back to `manual`. Cultural Analytics, MIT Press,
and PubPub are likewise manual-entry. If automating any of these becomes important,
update the relevant fetcher in `scripts/fetch_metrics.py`.
