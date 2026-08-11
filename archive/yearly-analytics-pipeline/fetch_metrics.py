#!/usr/bin/env python3
"""Stage 2 of the access-metrics pipeline.

Reads ``Access_Metrics-with-provider.csv`` (produced by add_provider_column.py),
visits each row's DOI, and records the metric named in that row's ``Metric Type``
plus the date it was retrieved. Writes a dated snapshot; the source files are
never modified.

Handlers this round:
  Zenodo       -> JSON API (views + downloads)
  DataCommons  -> HTML scrape (#pageviews / #downloads spans)
  CulturalAnalytics / MITPress / PubPub -> passed over (manual entry), because
      they hide metrics behind Cloudflare / JavaScript.

Re-runnable: run again on another date to build a time series of snapshots.
"""

import csv
import datetime
import os
import re
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "Access_Metrics-with-provider.csv")

LINK_COL = "Link (from Outputs)"
METRIC_COL = "Metric Type"
PROVIDER_COL = "DOI Provider"
COUNT_COL = "Count"
RETRIEVED_COL = "Retrieved Date"
STATUS_COL = "Status"

# Providers we pass over this round -> manual entry.
MANUAL_PROVIDERS = {"CulturalAnalytics", "MITPress", "PubPub"}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TIMEOUT = 20
SLEEP_BETWEEN = 1.0  # politeness delay between distinct network calls

TODAY = datetime.date.today().isoformat()


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
        except requests.RequestException as exc:  # network / HTTP error
            last_exc = exc
            if attempt == 0:
                time.sleep(2)
    raise last_exc  # type: ignore[misc]


def fetch_zenodo(link: str) -> dict:
    """Return {'views': int, 'downloads': int} for a Zenodo DOI link."""
    m = re.search(r"zenodo\.(\d+)", link)
    if not m:
        raise ValueError("no zenodo record id in link")
    record_id = m.group(1)
    resp = _get(
        f"https://zenodo.org/api/records/{record_id}",
        headers={"Accept": "application/json"},
    )
    stats = resp.json().get("stats", {})
    return {
        "views": stats.get("views"),
        "downloads": stats.get("downloads"),
    }


def fetch_datacommons(link: str) -> dict:
    """Return {'views': int, 'downloads': int} scraped from a DataCommons page."""
    resp = _get(link)
    html = resp.text

    def grab(span_id: str):
        m = re.search(rf'id="{span_id}"[^>]*>\s*([\d,]+)', html)
        return int(m.group(1).replace(",", "")) if m else None

    return {
        "views": grab("pageviews"),
        "downloads": grab("downloads"),
    }


FETCHERS = {
    "Zenodo": fetch_zenodo,
    "DataCommons": fetch_datacommons,
}


def metric_key(metric_type: str) -> str | None:
    """Map a Metric Type cell to a stats key. None if not a fetchable metric."""
    mt = (metric_type or "").strip().lower()
    if mt == "views":
        return "views"
    if mt == "downloads":
        return "downloads"
    return None  # e.g. "Citation Count"


def main() -> None:
    if not os.path.exists(SOURCE):
        sys.exit(f"Missing {os.path.basename(SOURCE)} — run add_provider_column.py first.")

    with open(SOURCE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    for col in (RETRIEVED_COL, STATUS_COL):
        if col not in fieldnames:
            fieldnames.append(col)

    # Cache fetched stats per DOI so repeated links hit the network once.
    cache: dict[str, dict] = {}
    status_counts: dict[str, int] = {}

    def bump(status: str) -> None:
        status_counts[status] = status_counts.get(status, 0) + 1

    for row in rows:
        link = (row.get(LINK_COL) or "").strip()
        provider = (row.get(PROVIDER_COL) or "").strip()
        row[RETRIEVED_COL] = TODAY

        if not link:
            row[STATUS_COL] = "no-link"
            bump("no-link")
            continue

        if provider in MANUAL_PROVIDERS or provider not in FETCHERS:
            row[STATUS_COL] = "manual"
            bump("manual")
            continue

        # Fetch (with cache), then pick the metric this row asks for.
        try:
            if link not in cache:
                cache[link] = FETCHERS[provider](link)
                time.sleep(SLEEP_BETWEEN)
            stats = cache[link]
        except Exception as exc:  # noqa: BLE001 — one row must not abort the run
            row[STATUS_COL] = f"error:{type(exc).__name__}"
            bump("error")
            print(f"  ! {provider} {link}: {exc}", file=sys.stderr)
            continue

        key = metric_key(row.get(METRIC_COL, ""))
        if key is None:
            row[STATUS_COL] = "no-metric"
            bump("no-metric")
            continue

        value = stats.get(key)
        if value is None:
            row[STATUS_COL] = "error:missing-metric"
            bump("error")
            continue

        row[COUNT_COL] = value
        row[STATUS_COL] = "ok"
        bump("ok")

    out_path = os.path.join(HERE, f"Access_Metrics-{TODAY}.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} rows -> {os.path.basename(out_path)}")
    print("Status breakdown:")
    for status, n in sorted(status_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {status:<20} {n}")
    manual = status_counts.get("manual", 0)
    if manual:
        print(f"\n{manual} rows flagged 'manual' need hand entry "
              "(CulturalAnalytics / MITPress / PubPub).")


if __name__ == "__main__":
    main()
