# CDH Research Tracking

A record of the Center for Digital Humanities' **projects**, their
**outputs** (publications, datasets, software, presentations, …), and the **yearly
views / downloads / citations** each output earns — plus an **Observable dashboard**
for viewing it all, across every CDH community.

You maintain a few hand-edited CSVs and run a small set of scripts on a regular
(quarterly) cadence. Airtable is no longer in the loop (its exports are kept in
`archive/` for provenance).

## Folder map

```
data/
  projects.csv            # projects + CDH community (Project-Lead) classification
  outputs.csv             # REALIZED outputs (Released/Done); increasingly generated from Zenodo/Zotero
  planned.csv             # hand-maintained: planned/forecast outputs (stable planned_id)
  people.csv              # hand-maintained: name → role (Faculty / CDH / Post Doc)
  sync_ledger.csv         # GENERATED: durable record of every ingest keep/skip decision
  incoming/               # transient review files from the syncs (git-ignored)
snapshots/
  metrics-<date>.csv      # lifetime view/download/citation counts as of a date (time series)
rollups/
  yearly-metrics.csv      # GENERATED: per output × metric × year → lifetime + yearly gain
scripts/
  sync_zenodo.py          # sweep the Zenodo princetoncdh community → review file
  sync_zotero.py          # sweep the 4 Zotero collections (DOI/link items) → review file
  merge_incoming.py       # apply a reviewed review file into outputs.csv + ledger
  synclib.py              # shared: matching/dedup, ledger, name & type helpers
  add_provenance_columns.py # one-time/idempotent: add source/zenodo_concept/zotero_key
  sync_cdh_projects.py    # sweep the CDH projects catalog → project community classification
  merge_projects.py       # apply a reviewed cdh-projects-review file into projects.csv
  add_project_columns.py  # one-time/idempotent: add community/cdh_built/cdh_slug
  fetch_metrics.py        # harvest lifetime counts (Zenodo + OpenAlex citations) → dated snapshot
  build_rollup.py         # snapshots/* → rollups/yearly-metrics.csv
  backfill_citations.py   # (re-runnable) reconstruct historical citations from OpenAlex
  migrate_from_airtable.py  # one-time: built data/ from the Airtable exports (provenance)
  backfill_snapshots.py     # one-time: built 2024–2026 snapshots from the curated export
dashboard/                # Observable Framework app (Impact / Portfolio)
archive/                  # raw Airtable exports + the retired 2-stage pipeline
requirements.txt          # just `requests`
```

## Maintaining projects, outputs & people

Edit the CSVs directly (Numbers, Excel, or any text editor — they're plain CSV and
diff cleanly in git).

- **projects.csv** — `project, status, start_date, end_date, faculty_engagement, notes,
  community, cdh_built, cdh_slug`. `project` is the key; it must match the `project` value
  used in outputs.csv. `status` may be multi-valued (comma-separated). `community` is the
  CDH **Project-Lead** classification (`Faculty` / `Postdoc` / `Staff` /
  `External Collaborator`, multi-valued) used to classify/curate the catalog — kept as data
  but not currently rendered on the dashboard. (Graduate-student-led projects are excluded
  from the published data.) `cdh_built`/`cdh_slug` come from the CDH catalog.
- **outputs.csv** — `output_id, output_name, project, type, status, assignee,
  link, doi_service, completed_date, availability, description, alt_id, source, zenodo_concept, zotero_key`. The last
  three are provenance: `source` (`zenodo`/`zotero`/`manual`) plus the stable
  upstream keys the syncs match on.
    - `output_id` is a stable key (`o001`…). Give a new output the next unused id and
      never renumber — snapshots and the rollup join on it.
    - `link` is the canonical DOI/URL. For Zenodo, prefer the **concept DOI** (the
      version-agnostic "always latest" one) over a specific version DOI.
    - `alt_id` is an optional secondary identifier for items with no usable DOI — e.g.
      `openalex:W4408262440` for a book that has only an ISBN. The citation harvester
      uses it to fetch citations (see below).
    - `assignee` is a comma-separated author list; the **first** name is treated as the
      lead. `type` may be multi-valued (comma-separated).
    - `status` here is **realized-only** (`Released`, `Done`) — outputs.csv is the record
      of work that *exists*, and is increasingly **generated** from the canonical sources
      (Zenodo + Zotero). Planned/forecast work lives in `planned.csv` (below), not here.
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
CSVs and rollup and emit JSON; the pages (`src/index.md` = the **Impact** landing page,
and `portfolio.md`) render it with Observable Plot, all reading the realized `outputs.csv`.
`node_modules/`, `dist/`, and the `.observablehq` cache are git-ignored —
`npm install && npm run build` regenerates them.

The GitHub Pages workflow at `.github/workflows/deploy.yml` builds and deploys
`dashboard/dist` on every push to `main`. First-time setup: on GitHub, set
**Settings → Pages → Source: "GitHub Actions"**. Served at
`https://princeton-cdh.github.io/research-outputs/` (the `base` path in
`observablehq.config.js` must match the repo name).

## Sources of published works — the quarterly ingest sweep

Realized outputs are reconciled from **two canonical sources** into `outputs.csv`:
the **Zenodo `princetoncdh` community** (clean, all-DOI'd) and the **Zotero** group's
four collections — Publications, Datasets, Documentation, Software (books + externally-
published work Zenodo lacks, but noisier). Each sync dedups against `outputs.csv` and the
ledger, then writes a **review file** you edit; `merge_incoming.py` applies your
decisions. Run quarterly:

```bash
python3 scripts/sync_zenodo.py        # → data/incoming/zenodo-review.csv
python3 scripts/sync_zotero.py        # → data/incoming/zotero-review.csv
#  edit each review file: set `decision` (keep / drop / review) and assign `project` to keeps
python3 scripts/merge_incoming.py data/incoming/zenodo-review.csv --apply
python3 scripts/merge_incoming.py data/incoming/zotero-review.csv --apply
#  add any new project names the merge flagged to data/projects.csv
python3 scripts/fetch_metrics.py      # metrics + citations for the now-larger list
python3 scripts/build_rollup.py
cd dashboard && npm run build
```

How the sweep decides:

- **Matches** an existing output (DOI → Zenodo-id → ISBN → concept → zotero_key →
  title+year) → **enriched in place** (backfills provenance keys), never duplicated.
- **New Zenodo** items → proposed pre-marked `keep` (community = in scope).
- **New Zotero** items with a DOI/link → pre-marked `keep` if a `people.csv` author is on
  them, otherwise left blank for you to triage. Zotero items with **no DOI/link are
  skipped** (not proposed).
- `merge_incoming.py` reads your `decision`: `keep` adds the output, `skip`/`drop`
  discards it (logged so it won't resurface), and `review`/blank leaves it undecided to
  come back next sweep.
- Every keep/drop is written to **`data/sync_ledger.csv`**, so re-running a sweep only
  ever surfaces genuinely new items (idempotent). The `incoming/` review files are
  transient (git-ignored); the ledger is the durable record.

Graduation from `planned.csv`: when a planned item ships and appears via a sweep,
delete its row from `planned.csv` (manual — there's no automatic dedup across the two).

## CDH project catalog & communities

Projects and their **community** (CDH Project-Lead classification) are imported from the
CDH projects site to build and classify the project catalog. Idempotent and review-gated,
like the output syncs:

```bash
python3 scripts/sync_cdh_projects.py                              # → data/incoming/cdh-projects-review.csv
#  review: keep/skip proposed projects, fix any name-mismatch flags
python3 scripts/merge_projects.py data/incoming/cdh-projects-review.csv --apply
```

`sync_cdh_projects.py` reads `cdh.princeton.edu/projects` (the `role=<id>` facet gives each
project's lead; `cdh_built=on` flags Built-by-CDH), matches to `projects.csv` (enriching
existing rows in place, with a small alias map for renamed projects), and proposes new
catalog projects. Projects not in the CDH catalog (internal R&D / tooling) get their
`community` set by hand; graduate-student-led catalog projects are skipped (excluded from
the published data). The dashboard colors outputs by **lead_role** — an output's
first-author role, from `people.csv`.

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