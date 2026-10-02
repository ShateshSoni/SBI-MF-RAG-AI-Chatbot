"""Mandatory-topic coverage gate over parsed document text."""

from __future__ import annotations

import re
from pathlib import Path

from src.ingest.manifest import Doc

TOPICS: dict[str, tuple[str, ...]] = {
    "expense_ratio": (r"expense ratio", r"\bTER\b", r"total expense ratio", r"base ter"),
    "exit_load": (r"exit load",),
    "minimum_sip": (r"minimum sip", r"\bSIP\b", r"systematic investment"),
    "elss_lockin": (r"lock-?\s*in", r"\bELSS\b", r"equity linked savings"),
    "riskometer": (r"risk-?o-?meter", r"riskometer"),
    "benchmark": (r"benchmark",),
    "statement_download": (
        r"account statement",
        r"capital gain",
        r"consolidated account statement",
        r"\bCAS\b",
        r"download",
    ),
}


def topic_support(docs: list[Doc], raw_text_dir: Path) -> dict[str, list[str]]:
    ingested = [doc for doc in docs if doc.ingest]
    texts = {
        doc.doc_id: (raw_text_dir / f"{doc.doc_id}.txt").read_text(encoding="utf-8", errors="replace")
        for doc in ingested
        if (raw_text_dir / f"{doc.doc_id}.txt").exists()
    }
    support: dict[str, list[str]] = {}
    for topic, patterns in TOPICS.items():
        compiled = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
        hits = [doc_id for doc_id, text in texts.items() if any(pattern.search(text) for pattern in compiled)]
        support[topic] = sorted(hits)
    return support


def coverage_failures(support: dict[str, list[str]], minimum: int = 2) -> list[str]:
    return [topic for topic, doc_ids in support.items() if len(doc_ids) < minimum]
