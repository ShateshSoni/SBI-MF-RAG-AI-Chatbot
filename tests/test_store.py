"""Chroma upsert idempotency, metadata coercion, scoped delete, and model guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Settings
from src.ingest.chunk import Chunk
from src.ingest.store import CollectionModelMismatch, Store, coerce_metadata


def _chunk(chunk_id: str, doc_id: str = "doc-a", scheme: str = "SBI Bluechip Fund") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
        source_url="https://www.sbimf.com/a.pdf",
        doc_title="Factsheet",
        doc_type="factsheet",
        scheme=scheme,
        scheme_category="Large Cap",
        section="Expense ratio",
        page_no=2,
        as_of_date="2026-06-30",
        text=f"{scheme} | Expense ratio\nTER | 1.50 | 0.86",
        char_len=40,
        token_len=12,
    )


def _settings(tmp_path: Path, model: str = "sentence-transformers/all-MiniLM-L6-v2") -> Settings:
    return Settings(chroma_dir=tmp_path / "chroma", embedding_model=model)


def test_coerce_replaces_none() -> None:
    coerced = coerce_metadata({"scheme": None, "page_no": None, "token_len": 3})
    assert coerced["scheme"] == ""
    assert coerced["page_no"] == 0
    assert coerced["token_len"] == 3
    assert all(value is not None for value in coerced.values())


def test_upsert_is_idempotent_and_delete_is_scoped(tmp_path: Path) -> None:
    store = Store(_settings(tmp_path))
    first = _chunk("a__bluechip__expense-ratio__000", "doc-a")
    second = _chunk("b__flexicap__expense-ratio__000", "doc-b", scheme="SBI Flexicap Fund")
    vector = [[0.1] * 384]
    store.upsert_chunks([first], vector)
    store.upsert_chunks([first], vector)
    store.upsert_chunks([second], vector)
    assert store.count() == 2
    stored = store.collection.get(ids=[first.chunk_id], include=["metadatas"])
    assert stored["metadatas"][0]["page_no"] == 2
    assert stored["metadatas"][0]["scheme"] == "SBI Bluechip Fund"
    store.delete_doc("doc-a")
    assert store.count() == 1
    remaining = store.collection.get(include=["metadatas"])
    assert remaining["metadatas"][0]["doc_id"] == "doc-b"


def test_model_mismatch(tmp_path: Path) -> None:
    Store(_settings(tmp_path))
    drifted = Store(_settings(tmp_path, model="some-other-model"))
    with pytest.raises(CollectionModelMismatch):
        drifted.assert_model_match()
