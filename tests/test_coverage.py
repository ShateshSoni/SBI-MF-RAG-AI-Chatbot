"""Mandatory topics must each be supported by at least two ingested documents."""

from __future__ import annotations

from pathlib import Path

from src.config import RAW_TEXT_DIR
from src.ingest.coverage import TOPICS, coverage_failures, topic_support
from src.ingest.manifest import load_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_real_corpus_covers_every_topic() -> None:
    docs = load_manifest(ROOT / "config" / "sources.csv")
    ingested = {doc.doc_id for doc in docs if doc.ingest}
    files = {path.stem for path in RAW_TEXT_DIR.glob("*.txt")}
    assert files == ingested
    for path in RAW_TEXT_DIR.glob("*.txt"):
        assert path.stat().st_size > 0
    support = topic_support(docs, RAW_TEXT_DIR)
    assert coverage_failures(support) == []
    assert set(support) == set(TOPICS)
    for topic, doc_ids in support.items():
        assert len(doc_ids) >= 2, topic
