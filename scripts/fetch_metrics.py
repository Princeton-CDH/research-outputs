#!/usr/bin/env python3
"""Harvest lifetime views/downloads for every output with a DOI, in one pass.

Reads the canonical ``data/outputs.csv``, classifies each output's link by DOI
prefix, and fetches its lifetime view/download counts:

  Zenodo       -> JSON API (views + downloads)
  DataCommons  -> HTML scrape (#pageviews / #downloads spans)
  CulturalAnalytics / MITPress / PubPub -> emitted as ``manual`` (metrics sit
      behind Cloudflare / JavaScript) for hand entry into the snapshot.

Writes a dated snapshot ``snapshots/metrics-<today>.csv`` (one Views row and one
Downloads row per output with a link). Re-runnable: run again on a later date to
extend the time series; build_rollup.py turns the snapshots into per-year deltas.
The source data files are never modified.

Run:  python3 scripts/fetch_metrics.py
"""

import csv
import datetime
import os
import re
import sys
import time
import urllib.parse

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTPUTS = os.path.join(ROOT, "data", "outputs.csv")
SNAP = os.path.join(ROOT, "snapshots")

SNAPSHOT_COLS = ["output_id", "link", "output_name", "project", "type",
                 "metric_type", "count", "retrieved_date", "status"]

# DOI/URL prefix -> provider. First hit wins. (Stage-1 of the old pipeline,
# folded in here so there is no intermediate CSV.)
PREFIX_MAP = [
    ("10.5281/zenodo", "Zenodo"),
    ("10.34770", "DataCommons"),
    ("10.22148", "CulturalAnalytics"),
    ("10.63744", "CulturalAnalytics"),  # newer Journal of Cultural Analytics DOI prefix
    ("10.1162", "MITPress"),
    ("10.21428", "PubPub"),
]
MANUAL_PROVIDERS = {"CulturalAnalytics", "MITPress", "PubPub"}

# Citations come from OpenAlex (free, no key), keyed by DOI — independent of the
# view/download provider. The mailto joins OpenAlex's faster "polite pool".
OPENALEX_MAIL = "cdh@princeton.edu"
DOI_RE = re.compile(r"(10\.\d{4,9}/\S+)")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TIMEOUT = 20
SLEEP_BETWEEN = 1.0  # politeness delay between distinct network calls
TODAY = datetime.date.today().isoformat()


def classify(link: str) -> str:
    link = (link or "").strip()
    if not link:
        return ""
    # Zenodo records are sometimes linked by record URL rather than DOI.
    if re.search(r"zenodo\.org/records?/\d+", link):
        return "Zenodo"
    for prefix, label in PREFIX_MAP:
        if prefix in link:
            return label
    return "Unknown"


def _get(url: str, headers: dict | None = None) -> requests.Response:
    """GET with one retry."""
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    last_exc = None
    for attempt in range(2):
        try:
            resp = requests.get(url, headers=hdrs, timeout=TIMEOUT, allow_redirects=True)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            if attempt == 0:
                time.sleep(2)
    raise last_exc  # type: ignore[misc]


def fetch_zenodo(link: str) -> dict:
    # Handle both the DOI form (…/zenodo.NNN) and the record-URL form
    # (zenodo.org/records/NNN).
    m = re.search(r"zenodo(?:\.org/records?/|\.)(\d+)", link)
    if not m:
        raise ValueError("no zenodo record id in link")
    resp = _get(f"https://zenodo.org/api/records/{m.group(1)}",
                headers={"Accept": "application/json"})
    stats = resp.json().get("stats", {})
    # Prefer all-versions totals (version_*) so a concept DOI reflects the whole
    # record's reach across versions; fall back to this-version counts.
    return {
        "Views": stats.get("version_views", stats.get("views")),
        "Downloads": stats.get("version_downloads", stats.get("downloads")),
    }


def extract_doi(link: str) -> str | None:
    m = DOI_RE.search(link or "")
    return m.group(1).rstrip("/.") if m else None


def openalex_entity(o: dict) -> str | None:
    """OpenAlex lookup path for an output: its DOI, or a pinned OpenAlex work id
    from the alt_id column ('openalex:W123', for books with an ISBN but no DOI)."""
    doi = extract_doi(o.get("link", ""))
    if doi:
        return "https://doi.org/" + urllib.parse.quote(doi, safe="")
    alt = (o.get("alt_id") or "").strip()
    if alt.lower().startswith("openalex:"):
        return alt.split(":", 1)[1].strip()
    return None


def fetch_openalex_citation(entity: str):
    """Lifetime citation count for an OpenAlex entity (DOI or work id), or None."""
    url = (
        "https://api.openalex.org/works/" + entity
        + "?mailto=" + OPENALEX_MAIL + "&select=cited_by_count"
    )
    resp = _get(url, headers={"Accept": "application/json"})
    return resp.json().get("cited_by_count")


def fetch_datacommons(link: str) -> dict:
    html = _get(link).text

    def grab(span_id: str):
        m = re.search(rf'id="{span_id}"[^>]*>\s*([\d,]+)', html)
        return int(m.group(1).replace(",", "")) if m else None

    return {"Views": grab("pageviews"), "Downloads": grab("downloads")}


FETCHERS = {"Zenodo": fetch_zenodo, "DataCommons": fetch_datacommons}


def main() -> None:
    if not os.path.exists(OUTPUTS):
        sys.exit("Missing data/outputs.csv — run migrate_from_airtable.py first.")

    with open(OUTPUTS, encoding="utf-8", newline="") as f:
        outputs = [o for o in csv.DictReader(f) if (o.get("link") or "").strip()]

    cache: dict[str, dict] = {}
    cite_cache: dict[str, object] = {}
    status_counts: dict[str, int] = {}
    rows = []

    def bump(s: str) -> None:
        status_counts[s] = status_counts.get(s, 0) + 1

    def emit(o: dict, metric: str, count, status: str) -> None:
        rows.append({
            "output_id": o.get("output_id", ""),
            "link": (o.get("link") or "").strip(),
            "output_name": o.get("output_name", ""),
            "project": o.get("project", ""),
            "type": o.get("type", ""),
            "metric_type": metric,
            "count": "" if count is None else count,
            "retrieved_date": TODAY,
            "status": status,
        })

    for o in outputs:
        link = (o.get("link") or "").strip()
        provider = classify(link)

        # Citations (OpenAlex) — for any DOI or pinned OpenAlex id, regardless of
        # the view/download provider. Only emit once an output has been cited.
        entity = openalex_entity(o)
        if entity:
            try:
                if entity not in cite_cache:
                    cite_cache[entity] = fetch_openalex_citation(entity)
                    time.sleep(SLEEP_BETWEEN)
                cites = cite_cache[entity]
            except Exception as exc:  # noqa: BLE001
                cites = None
                print(f"  ! OpenAlex {entity}: {exc}", file=sys.stderr)
            if isinstance(cites, int) and cites > 0:
                emit(o, "Citation Count", cites, "ok")
                bump("ok")

        # Citation-only outputs (a pinned OpenAlex id but no DOI, e.g. a book with
        # only an ISBN) have no view/download source — don't emit empty manual rows.
        if not extract_doi(link) and (o.get("alt_id") or "").strip():
            continue

        if provider in MANUAL_PROVIDERS or provider not in FETCHERS:
            for metric in ("Views", "Downloads"):
                emit(o, metric, None, "manual")
                bump("manual")
            continue

        try:
            if link not in cache:
                cache[link] = FETCHERS[provider](link)
                time.sleep(SLEEP_BETWEEN)
            stats = cache[link]
        except Exception as exc:  # noqa: BLE001 — one row must not abort the run
            for metric in ("Views", "Downloads"):
                emit(o, metric, None, f"error:{type(exc).__name__}")
                bump("error")
            print(f"  ! {provider} {link}: {exc}", file=sys.stderr)
            continue

        for metric in ("Views", "Downloads"):
            value = stats.get(metric)
            if value is not None:
                status = "ok"
            elif provider == "DataCommons":
                # The DataCommons scrape reads nothing when the site changes its
                # markup or fronts it with Cloudflare — fall back to hand entry.
                status = "manual"
            else:
                status = "error:missing-metric"
            emit(o, metric, value, status)
            bump("ok" if value is not None else ("manual" if status == "manual" else "error"))

    os.makedirs(SNAP, exist_ok=True)
    out_path = os.path.join(SNAP, f"metrics-{TODAY}.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SNAPSHOT_COLS)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows -> snapshots/{os.path.basename(out_path)}")
    print("Status breakdown:")
    for status, n in sorted(status_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {status:<20} {n}")
    manual = status_counts.get("manual", 0)
    if manual:
        print(f"\n{manual} 'manual' rows need hand entry "
              "(CulturalAnalytics / MITPress / PubPub) — fill the count column in the snapshot.")


if __name__ == "__main__":
    main()
