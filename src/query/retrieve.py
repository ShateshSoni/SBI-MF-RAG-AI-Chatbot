"""Embed a question and query Chroma with an optional scheme filter."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from src.config import Settings
from src.ingest.embed import encode
from src.ingest.store import Store, get_store
from src.query.intent import detect_scheme, rewrite_for_embedding


@dataclass
class Hit:
    chunk_id: str
    text: str
    score: float
    metadata: dict


@dataclass
class RetrievalResult:
    hits: list[Hit] = field(default_factory=list)
    max_similarity: float = 0.0
    out_of_corpus: bool = True
    retried_unfiltered: bool = False
    scheme: str | None = None
    embed_ms: int = 0
    retrieve_ms: int = 0


def _hits_from(raw: dict) -> list[Hit]:
    documents = raw.get("documents") or []
    metadatas = raw.get("metadatas") or []
    distances = raw.get("distances") or []
    hits: list[Hit] = []
    for text, meta, distance in zip(documents, metadatas, distances):
        metadata = dict(meta or {})
        score = 1.0 - float(distance)
        hits.append(
            Hit(
                chunk_id=str(metadata.get("chunk_id") or ""),
                text=text or "",
                score=score,
                metadata=metadata,
            )
        )
    hits.sort(key=lambda hit: hit.score, reverse=True)
    return hits


def retrieve(
    question: str,
    settings: Settings,
    store: Store | None = None,
    scheme: str | None = None,
) -> RetrievalResult:
    """Top-k cosine search. One unfiltered retry when a scheme filter is empty."""
    detected = detect_scheme(question) if scheme is None else scheme
    started = time.perf_counter()
    vector = encode([rewrite_for_embedding(question, detected)])[0]
    embed_ms = int((time.perf_counter() - started) * 1000)

    client = store or get_store(settings)
    queried = time.perf_counter()
    where = {"scheme": detected} if detected else None
    raw = client.query(vector, settings.top_k, where=where)
    retried = False
    if detected and not raw.get("documents"):
        raw = client.query(vector, settings.top_k, where=None)
        retried = True
    hits = _hits_from(raw)
    max_similarity = hits[0].score if hits else 0.0
    return RetrievalResult(
        hits=hits,
        max_similarity=max_similarity,
        out_of_corpus=not hits or max_similarity < settings.sim_floor,
        retried_unfiltered=retried,
        scheme=detected,
        embed_ms=embed_ms,
        retrieve_ms=int((time.perf_counter() - queried) * 1000),
    )
