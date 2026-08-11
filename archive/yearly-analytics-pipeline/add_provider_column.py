#!/usr/bin/env python3
"""Stage 1 of the access-metrics pipeline.

Reads the Airtable export and adds a single ``DOI Provider`` column, classifying
each row by the prefix of its DOI ``Link (from Outputs)``. Writes a new derived
CSV and never touches the source export.

Provider is what Stage 2 (fetch_metrics.py) dispatches on to decide how to read
views/downloads for each row.
"""

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "Access_Metrics-Grid view.csv")
OUTPUT = os.path.join(HERE, "Access_Metrics-with-provider.csv")

LINK_COL = "Link (from Outputs)"
PROVIDER_COL = "DOI Provider"

# Matched in order against the DOI/URL. First hit wins.
PREFIX_MAP = [
    ("10.5281/zenodo", "Zenodo"),
    ("10.34770", "DataCommons"),
    ("10.22148", "CulturalAnalytics"),
    ("10.1162", "MITPress"),
    ("10.21428", "PubPub"),
]


def classify(link: str) -> str:
    """Return a provider label for a DOI link, or "" / "Unknown"."""
    link = (link or "").strip()
    if not link:
        return ""
    for prefix, label in PREFIX_MAP:
        if prefix in link:
            return label
    return "Unknown"


def main() -> None:
    with open(SOURCE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if PROVIDER_COL not in fieldnames:
        fieldnames.append(PROVIDER_COL)

    counts: dict[str, int] = {}
    for row in rows:
        provider = classify(row.get(LINK_COL, ""))
        row[PROVIDER_COL] = provider
        counts[provider or "(blank)"] = counts.get(provider or "(blank)", 0) + 1

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows -> {os.path.basename(OUTPUT)}")
    print("Provider breakdown:")
    for provider, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {provider:<18} {n}")


if __name__ == "__main__":
    main()
