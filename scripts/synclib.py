#!/usr/bin/env python3
"""Shared helpers for the two-source ingest pipeline (sync_zenodo, sync_zotero,
merge_incoming).

Provides: identifier normalization, an OutputsIndex for cross-source dedup
(match precedence DOI -> ISBN -> zenodo_concept -> zotero_key -> title+year),
creator-name formatting, roster-author detection, item-type maps, the review-CSV
schema, and read/append helpers for the decision ledger.
"""
import csv
import datetime
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTPUTS = os.path.join(ROOT, "data", "outputs.csv")
PEOPLE = os.path.join(ROOT, "data", "people.csv")
LEDGER = os.path.join(ROOT, "data", "sync_ledger.csv")
INCOMING = os.path.join(ROOT, "data", "incoming")

DOI_RE = re.compile(r"(10\.\d{4,9}/\S+)")
ZENODO_ID_RE = re.compile(r"zenodo(?:\.org/records?/|\.)(\d+)", re.I)

# Columns in a *-review.csv (what sync_* writes and the user edits).
REVIEW_COLS = [
    "decision", "confidence", "why", "project", "output_name", "type", "tier",
    "assignee", "link", "alt_id", "completed_date", "source", "upstream_key",
]
LEDGER_COLS = ["source", "upstream_key", "decision", "output_id", "decided_date", "title"]


# ---------------------------------------------------------------- identifiers
def normalize_doi(s):
    if not s:
        return ""
    s = s.strip().lower()
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s)
    m = DOI_RE.search(s)
    return (m.group(1) if m else s).rstrip("/.")


def extract_doi(link):
    m = DOI_RE.search(link or "")
    return normalize_doi(m.group(1)) if m else ""


def zenodo_id(link):
    m = ZENODO_ID_RE.search(link or "")
    return m.group(1) if m else ""


def normalize_isbn(s):
    return re.sub(r"[^0-9Xx]", "", s or "").upper()


def normalize_title(s):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", (s or "").lower())).strip()


def year_of(date_str):
    """Year from an ISO (YYYY-…) or US (M/D/YYYY) date string, or ''."""
    date_str = (date_str or "").strip()
    m = re.search(r"(\d{4})", date_str)
    return m.group(1) if m else ""


def iso_to_us(s):
    """'YYYY-MM-DD' -> 'M/D/YYYY' (outputs.csv convention), else ''."""
    try:
        d = datetime.date.fromisoformat((s or "")[:10])
        return f"{d.month}/{d.day}/{d.year}"
    except ValueError:
        return ""


# ------------------------------------------------------------------ names
def name_first_last(creator):
    """Normalize a Zenodo/Zotero creator to 'Given Family' (matches people.csv).

    Accepts either a Zotero creator dict ({firstName, lastName} or {name}) or a
    Zenodo creator dict ({person_or_org:{name:'Family, Given'}} or {name:...}) or
    a raw string.
    """
    if isinstance(creator, str):
        raw = creator
    elif "firstName" in creator or "lastName" in creator:
        given = (creator.get("firstName") or "").strip()
        family = (creator.get("lastName") or "").strip()
        return f"{given.split()[0]} {family}".strip() if given else family
    else:
        raw = (creator.get("person_or_org", {}) or {}).get("name") or creator.get("name", "")
    raw = (raw or "").strip()
    if "," in raw:  # 'Family, Given Middle' -> 'Given Family'
        family, given = [p.strip() for p in raw.split(",", 1)]
        return f"{given.split()[0]} {family}".strip() if given else family
    return raw


def roster_names():
    names = set()
    if os.path.exists(PEOPLE):
        with open(PEOPLE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                n = (row.get("name") or "").strip().lower()
                if n:
                    names.add(n)
    return names


def roster_author_name(creators, roster=None):
    """The first creator whose normalized 'Given Family' matches the roster, or ''."""
    roster = roster_names() if roster is None else roster
    for c in creators or []:
        n = name_first_last(c)
        if n.strip().lower() in roster:
            return n
    return ""


def is_roster_author(creators, roster=None):
    """True if any creator's normalized 'Given Family' exactly matches the roster."""
    return bool(roster_author_name(creators, roster))


# ------------------------------------------------------------------ type maps
def map_zenodo_type(rtype, subtype=""):
    rtype = (rtype or "").lower()
    subtype = (subtype or "").lower()
    if rtype == "software":
        return "Software Release"
    if rtype == "dataset":
        return "Dataset"
    if rtype in ("poster", "presentation"):
        return "Presentation / Poster"
    if rtype == "publication":
        if subtype in ("report", "other", "technicalnote", "workingpaper", "deliverable"):
            return "Grey Literature"
        return "Publication"
    return ""  # 'other', image, video, lesson … -> leave for manual


ZOTERO_TYPE_MAP = {
    "journalArticle": "Publication",
    "conferencePaper": "Publication",
    "bookSection": "Publication",
    "book": "Publication",
    "thesis": "Publication",
    "preprint": "Publication",
    "magazineArticle": "Publication",
    "newspaperArticle": "Publication",
    "presentation": "Presentation / Poster",
    "report": "Grey Literature",
    "blogPost": "Grey Literature",
    "webpage": "Grey Literature",
    "document": "Grey Literature",
    "computerProgram": "Software Release",
}


def map_zotero_type(item_type):
    return ZOTERO_TYPE_MAP.get(item_type, "")


# ------------------------------------------------------------- outputs index
class OutputsIndex:
    """Lookups over data/outputs.csv for cross-source dedup."""

    def __init__(self, rows):
        self.rows = rows
        self.by_doi = {}
        self.by_isbn = {}
        self.by_concept = {}
        self.by_zotero = {}
        self.by_zenodo_id = {}  # any Zenodo numeric id (version or concept) -> oid
        self.by_title_year = {}
        for r in rows:
            oid = r["output_id"]
            doi = extract_doi(r.get("link", ""))
            if doi:
                self.by_doi.setdefault(doi, oid)
            alt = (r.get("alt_id") or "").strip().lower()
            if alt.startswith("isbn:"):
                self.by_isbn.setdefault(normalize_isbn(alt.split(":", 1)[1]), oid)
            concept = (r.get("zenodo_concept") or "").strip()
            if concept:
                self.by_concept.setdefault(concept, oid)
                self.by_zenodo_id.setdefault(concept, oid)
            zid = zenodo_id(r.get("link", ""))
            if zid:
                self.by_zenodo_id.setdefault(zid, oid)
            zk = (r.get("zotero_key") or "").strip()
            if zk:
                self.by_zotero.setdefault(zk, oid)
            ty = (normalize_title(r.get("output_name", "")), year_of(r.get("completed_date", "")))
            if ty[0]:
                self.by_title_year.setdefault(ty, oid)

    def match(self, item):
        """item: dict with any of doi, isbn, zenodo_concept, zotero_key, title, year.
        Returns (output_id, matched_by) or (None, None)."""
        doi = normalize_doi(item.get("doi", ""))
        if doi and doi in self.by_doi:
            return self.by_doi[doi], "doi"
        # Any Zenodo numeric id (version or concept) the item carries.
        for zid in item.get("zenodo_ids", []) or []:
            if zid and zid in self.by_zenodo_id:
                return self.by_zenodo_id[zid], "zenodo_id"
        isbn = normalize_isbn(item.get("isbn", ""))
        if isbn and isbn in self.by_isbn:
            return self.by_isbn[isbn], "isbn"
        concept = (item.get("zenodo_concept") or "").strip()
        if concept and concept in self.by_concept:
            return self.by_concept[concept], "zenodo_concept"
        zk = (item.get("zotero_key") or "").strip()
        if zk and zk in self.by_zotero:
            return self.by_zotero[zk], "zotero_key"
        ty = (normalize_title(item.get("title", "")), str(item.get("year", "")))
        if ty[0] and ty in self.by_title_year:
            return self.by_title_year[ty], "title+year"
        return None, None


def load_outputs():
    with open(OUTPUTS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames)


def load_outputs_index():
    rows, _ = load_outputs()
    return OutputsIndex(rows)


def next_output_id(rows):
    n = max((int(r["output_id"][1:]) for r in rows if r["output_id"].startswith("o")), default=0)
    return lambda i: f"o{n + i:03d}"


# ---------------------------------------------------------------- ledger
def load_ledger():
    decided = set()
    if os.path.exists(LEDGER):
        with open(LEDGER, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                decided.add((row.get("source", ""), row.get("upstream_key", "")))
    return decided


def already_decided(decided, source, key):
    return (source, key) in decided


def append_ledger(entries):
    """entries: list of dicts with LEDGER_COLS keys."""
    exists = os.path.exists(LEDGER)
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_COLS)
        if not exists:
            w.writeheader()
        for e in entries:
            w.writerow({c: e.get(c, "") for c in LEDGER_COLS})


def write_review(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REVIEW_COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in REVIEW_COLS})
