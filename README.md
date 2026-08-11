# RSE Project Tracking

The canonical record of RSE/CDH **projects**, their **outputs** (publications,
datasets, software, etc.), and the **yearly views/downloads** each output earns.

This folder is now the source of truth — you edit two CSVs by hand and run two
scripts once a year. Airtable is no longer in the loop (its exports are kept in
`archive/` for provenance).

## Folder map

```
data/
  projects.csv            # hand-maintained: one row per project
  outputs.csv             # hand-maintained: one row per output (stable output_id)
snapshots/
  metrics-<date>.csv      # lifetime view/download counts as of a date (time series)
rollups/
  yearly-metrics.csv      # GENERATED: per output × metric × year → lifetime + yearly gain
scripts/
  fetch_metrics.py        # harvest lifetime counts → a new dated snapshot
  build_rollup.py         # snapshots/* → rollups/yearly-metrics.csv
  migrate_from_airtable.py  # one-time: built data/ from the Airtable exports (provenance)
  backfill_snapshots.py     # one-time: built 2024–2026 snapshots from the curated export
archive/                  # raw Airtable exports + the retired 2-stage pipeline
requirements.txt          # just `requests`
```

## Maintaining projects & outputs

Edit `data/projects.csv` and `data/outputs.csv` directly (Numbers, Excel, or any
text editor — they're plain CSV and diff cleanly in git).

- **projects.csv** — `project, status, start_date, end_date, faculty_engagement, notes`.
  `project` is the key; it must match the `project` value used in outputs.csv.
- **outputs.csv** — `output_id, output_name, project, type, tier, status, assignee,
  link, doi_service, completed_date, availability, description`.
  - `output_id` is a stable key (`o001`…). When you add an output, give it the next
    unused id and never renumber existing ones — the snapshots and rollup join on it.
  - `link` is the canonical DOI/URL (`https://doi.org/…`). It's what the harvester
    reads and what snapshots join back on, so keep it accurate.
  - `type` is the medium (Publication / Dataset / Software Release / …); `tier` is the
    Tier 1/2/3 classification. They're independent — leave `tier` blank if N/A.
  - `status` is the lifecycle facet — this one table holds an output at every stage,
    and views filter on it rather than splitting the list:
    - **Realized:** `Released`, `Done` — the work exists. This is the impact set; the
      dashboard and metrics only ever look here (and narrow further to rows with a `link`).
    - **Pipeline:** `To do`, `In progress`, `Submitted` — planned deliverables that don't
      exist yet (usually no link, no metrics). They power a "what's coming" view.

    An output moves along the pipeline by editing its `status` in place — when a planned
    paper is released, flip it to `Released` and paste the DOI into `link`. Never move
    rows between files; the status is the single source of truth for where it stands.

## The annual refresh (views & downloads)

Once a year (or whenever you want a fresh reading):

```bash
cd "Projects/RSE Project Tracking"
pip install -r requirements.txt        # first time only
python3 scripts/fetch_metrics.py       # writes snapshots/metrics-<today>.csv
python3 scripts/build_rollup.py        # rebuilds rollups/yearly-metrics.csv
```

`fetch_metrics.py` reads `data/outputs.csv`, and for every output with a link pulls
its **lifetime** views/downloads:

- **Zenodo** (`10.5281/zenodo…`) — fetched automatically via the Zenodo API. Reliable.
- **DataCommons / Cultural Analytics / MIT Press / PubPub** — these hide metrics
  behind JavaScript/Cloudflare, so their rows land with status `manual` and a blank
  `count`. **Fill those counts in by hand** in the new snapshot file (look the number
  up on the site). The run's summary tells you how many need entry.

`build_rollup.py` reads every snapshot and computes, per output × metric × year:

- `lifetime_count` — the cumulative total as of that year.
- `yearly_delta` — `lifetime_count(year) − lifetime_count(previous year)` = what the
  output earned *during* that year. Blank in an output's first year (no baseline).
  A negative delta means a count dropped year-over-year — worth a look.

If you re-harvest twice in one year, the later snapshot wins for that year.

## History already loaded

`snapshots/` is seeded with **2024, 2025, and 2026** from the curated Airtable
Access_Metrics table (including the hand-entered Cultural Analytics / MIT Press
counts), so `yearly-metrics.csv` has real year-over-year deltas today. Next year,
just run the two refresh commands to add 2027.

## Rebuilding the canonical CSVs from scratch (rare)

The two `*_from_airtable` / `backfill_*` scripts are one-time builders kept for
provenance. They read the exports in `archive/airtable-exports/` and regenerate
`data/` and the backfilled snapshots deterministically. You normally never run them
again — edit the CSVs directly instead.

### Known limitation

The DataCommons HTML scrape (`fetch_datacommons`) currently returns nothing because
the site changed its markup / added Cloudflare; those rows fall back to `manual`. If
DataCommons metrics become important to automate, update the scrape in
`scripts/fetch_metrics.py`.
