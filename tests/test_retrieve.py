"""Retrieval scoring, scheme filter, and the similarity floor."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Settings
from src.query.retrieve import retrieve


class _Store:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.wheres: list[dict | None] = []
        self.top_ks: list[int] = []

    def query(self, vector, top_k: int, where: dict | None = None) -> dict:
        self.wheres.append(where)
        self.top_ks.append(top_k)
        return self.responses.pop(0)


def _encode(_texts):
    return [[0.1] * 384]


def _row(distance: float, scheme: str = "SBI Bluechip Fund") -> dict:
    return {
        "documents": ["Expense ratio 1.50"],
        "metadatas": [
            {
                "chunk_id": "doc__bluechip__fees__000",
                "source_url": "https://www.sbimf.com/ways-to-invest",
                "scheme": scheme,
                "as_of_date": "2026-06-30",
                "doc_title": "Factsheet",
                "page_no": 2,
                "section": "fees",
            }
        ],
        "distances": [distance],
    }


def test_filtered_empty_result_retries_once_unfiltered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.query.retrieve.encode", _encode)
    store = _Store([{"documents": [], "metadatas": [], "distances": []}, _row(0.2)])
    result = retrieve("expense ratio of SBI Bluechip", Settings(), store=store)
    assert store.wheres == [{"scheme": "SBI Bluechip Fund"}, None]
    assert store.top_ks == [5, 5]
    assert result.retried_unfiltered
    assert result.max_similarity == pytest.approx(0.8)
    assert not result.out_of_corpus


def test_similarity_floor_marks_out_of_corpus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.query.retrieve.encode", _encode)
    store = _Store([_row(0.8)])
    result = retrieve("something vague about markets", Settings(), store=store, scheme=None)
    assert store.wheres == [None]
    assert result.max_similarity == pytest.approx(0.2)
    assert result.out_of_corpus


@pytest.mark.skipif(not Path("chroma_db").exists(), reason="local corpus is not built")
def test_live_bluechip_retrieval_stays_on_scheme() -> None:
    result = retrieve("expense ratio of SBI Bluechip Fund", Settings())
    assert not result.out_of_corpus
    assert result.hits
    assert all(hit.metadata.get("scheme") == "SBI Bluechip Fund" for hit in result.hits)
    assert result.max_similarity >= 0.35
