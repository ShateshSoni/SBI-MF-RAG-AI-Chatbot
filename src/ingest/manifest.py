"""Load and validate the corpus manifest, including the host allowlist."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from src.config import SOURCES_CSV

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class Doc:
    doc_id: str
    title: str
    doc_type: str
    scheme: str
    scheme_category: str
    source_url: str
    as_of_date: str
    tier: int
    ingest: bool
    local_filename: str
    fetched_at: str
    notes: str


def load_manifest(path: Path | None = None) -> list[Doc]:
    csv_path = path or SOURCES_CSV
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    docs: list[Doc] = []
    seen: set[str] = set()
    for row in rows:
        doc = _parse_row(row)
        if doc.doc_id in seen:
            raise ValueError(f"duplicate doc_id: {doc.doc_id}")
        seen.add(doc.doc_id)
        docs.append(doc)
    return docs


def allowed_hosts(docs: list[Doc]) -> set[str]:
    hosts: set[str] = set()
    for doc in docs:
        if not doc.ingest:
            continue
        host = urlparse(doc.source_url).hostname
        if host:
            hosts.add(host.lower())
    return hosts


def doc_urls(docs: list[Doc], doc_id: str) -> str:
    for doc in docs:
        if doc.doc_id == doc_id:
            return doc.source_url
    raise KeyError(doc_id)


def _parse_row(row: dict[str, str]) -> Doc:
    doc_id = (row.get("doc_id") or "").strip()
    doc_type = (row.get("doc_type") or "").strip()
    source_url = (row.get("source_url") or "").strip()
    as_of = (row.get("as_of_date") or "").strip()
    tier_raw = (row.get("tier") or "").strip()
    ingest_raw = (row.get("ingest") or "").strip().lower()
    if not doc_id:
        raise ValueError("empty doc_id")
    if not doc_type:
        raise ValueError(f"{doc_id}: empty doc_type")
    if not source_url.startswith("https://"):
        raise ValueError(f"{doc_id}: URL must be https")
    if not tier_raw.isdigit() or not 1 <= int(tier_raw) <= 5:
        raise ValueError(f"{doc_id}: tier outside 1-5")
    if not _DATE.match(as_of):
        raise ValueError(f"{doc_id}: malformed as_of_date")
    date.fromisoformat(as_of)
    if ingest_raw not in {"yes", "no"}:
        raise ValueError(f"{doc_id}: ingest must be yes or no")
    return Doc(
        doc_id=doc_id,
        title=(row.get("title") or "").strip(),
        doc_type=doc_type,
        scheme=(row.get("scheme") or "").strip(),
        scheme_category=(row.get("scheme_category") or "").strip(),
        source_url=source_url,
        as_of_date=as_of,
        tier=int(tier_raw),
        ingest=ingest_raw == "yes",
        local_filename=(row.get("local_filename") or "").strip(),
        fetched_at=(row.get("fetched_at") or "").strip(),
        notes=(row.get("notes") or "").strip(),
    )
