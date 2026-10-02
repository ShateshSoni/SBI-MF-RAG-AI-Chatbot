"""Query pipeline. PII is refused before any embedding or model call."""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Literal

from src.config import ConfigurationError, Settings
from src.ingest.store import CollectionModelMismatch, get_store
from src.logging_utils import setup_logging
from src.query.guards import (
    OUT_OF_CORPUS,
    PII_REFUSAL,
    advice_message,
    check_length,
    check_pii,
    check_scope,
    factsheet_message,
    length_message,
    manifest_docs,
    manifest_urls,
)
from src.query.intent import detect_advice, detect_performance, detect_scheme
from src.query.llm import (
    GroqClient,
    LLMAuthError,
    LLMRequestError,
    LLMTruncated,
    LLMUnavailable,
)
from src.query.prompt import assemble_context, build_messages
from src.query.retrieve import RetrievalResult, retrieve
from src.query.validate import (
    VALIDATOR_FALLBACK,
    clean_citation_markup,
    enforce_output,
    extract_urls,
    freshness_date,
    strip_freshness,
)

logger = logging.getLogger(__name__)

Status = Literal["answered", "refused_advice", "refused_pii", "out_of_corpus", "error"]

_LOGGING_READY = False


@dataclass(frozen=True)
class Citation:
    title: str
    url: str
    page_no: int = 0


@dataclass
class Response:
    answer: str
    citations: list[Citation]
    freshness: str | None
    status: Status
    guard: dict = field(default_factory=dict)
    retrieval: dict | None = None
    latency_ms: dict[str, int] = field(default_factory=dict)


def _ensure_logging() -> None:
    global _LOGGING_READY
    if not _LOGGING_READY:
        setup_logging()
        _LOGGING_READY = True


def _log(question: str, status: str, latency: dict[str, int]) -> None:
    _ensure_logging()
    if os.getenv("LOG_QUERY_TEXT") == "1":
        logger.info("query status=%s latency_ms=%s", status, latency)
        return
    digest = hashlib.sha256(question.encode("utf-8")).hexdigest()
    logger.info(
        "query sha256=%s length=%d status=%s latency_ms=%s",
        digest,
        len(question),
        status,
        latency,
    )


def _finish(
    question: str,
    started: float,
    latency: dict[str, int],
    answer: str,
    status: Status,
    guard: dict,
    citations: list[Citation] | None = None,
    freshness: str | None = None,
    retrieval: dict | None = None,
) -> Response:
    latency["total"] = int((time.perf_counter() - started) * 1000)
    _log(question, status, latency)
    return Response(
        answer=answer,
        citations=citations or [],
        freshness=freshness,
        status=status,
        guard=guard,
        retrieval=retrieval,
        latency_ms=latency,
    )


def _citations_for(answer: str, hits: list) -> list[Citation]:
    found: list[Citation] = []
    seen: set[str] = set()
    for url in extract_urls(answer):
        if url in seen:
            continue
        for hit in hits:
            if hit.metadata.get("source_url") != url:
                continue
            found.append(
                Citation(
                    title=str(hit.metadata.get("doc_title") or "Source"),
                    url=url,
                    page_no=int(hit.metadata.get("page_no") or 0),
                )
            )
            seen.add(url)
            break
    return found


def _corpus_newest() -> str:
    dates = [doc.as_of_date for doc in manifest_docs() if doc.ingest and doc.as_of_date]
    return max(dates) if dates else ""


def _retrieval_view(result: RetrievalResult, top_k: int) -> dict:
    return {
        "top_k": top_k,
        "max_similarity": round(result.max_similarity, 4),
        "chunk_ids": [hit.chunk_id for hit in result.hits],
    }


def answer_question(question: str, settings: Settings | None = None) -> Response:
    settings = settings or Settings.from_env()
    started = time.perf_counter()
    latency = {"embed": 0, "retrieve": 0, "generate": 0, "total": 0}
    guard: dict = {"pii": None, "intent": None, "validation": None, "answer_mode": None}

    kind = check_length(question, settings.max_query_chars)
    if kind:
        text, status = length_message(kind)
        guard["intent"] = kind
        return _finish(question or "", started, latency, text, status, guard)  # type: ignore[arg-type]

    pii = check_pii(question)
    if pii:
        guard["pii"] = pii
        return _finish(question, started, latency, PII_REFUSAL, "refused_pii", guard)

    advice = detect_advice(question)
    if advice:
        guard["intent"] = advice.rule
        text, title, url = advice_message(question)
        return _finish(
            question,
            started,
            latency,
            text,
            "refused_advice",
            guard,
            citations=[Citation(title=title, url=url, page_no=0)],
        )

    performance = detect_performance(question)
    if performance:
        guard["intent"] = performance.rule
        guard["answer_mode"] = "FACTSHEET_LINK"
        text, title, url, as_of = factsheet_message()
        return _finish(
            question,
            started,
            latency,
            text,
            "answered",
            guard,
            citations=[Citation(title=title, url=url, page_no=0)],
            freshness=f"Last updated from sources: {as_of}",
        )

    scope = check_scope(question)
    if scope:
        guard["intent"] = scope
        return _finish(question, started, latency, OUT_OF_CORPUS, "out_of_corpus", guard)

    scheme = detect_scheme(question)
    guard["scheme"] = scheme
    try:
        store = get_store(settings)
        if store.count() == 0:
            return _finish(
                question,
                started,
                latency,
                "The corpus is not ready. Run python scripts/run_ingest.py",
                "error",
                guard,
            )
        store.assert_model_match()
    except CollectionModelMismatch as exc:
        return _finish(question, started, latency, str(exc), "error", guard)
    except ConfigurationError as exc:
        return _finish(question, started, latency, str(exc), "error", guard)
    except Exception as exc:
        # A corrupt, locked or unreadable index is an operator problem, not a user
        # one. Report it as an error instead of letting it escape as a crash.
        logger.warning("corpus unavailable: %s", exc, exc_info=True)
        return _finish(
            question,
            started,
            latency,
            "I can't reach the document index right now. Please retry shortly.",
            "error",
            guard,
        )

    result = retrieve(question, settings, store=store, scheme=scheme)
    latency["embed"] = result.embed_ms
    latency["retrieve"] = result.retrieve_ms
    view = _retrieval_view(result, settings.top_k)
    if result.out_of_corpus:
        return _finish(question, started, latency, OUT_OF_CORPUS, "out_of_corpus", guard, retrieval=view)

    context = assemble_context(result.hits)
    try:
        client = GroqClient(settings)
    except ConfigurationError:
        return _finish(
            question,
            started,
            latency,
            "Assistant API not configured",
            "error",
            guard,
            retrieval=view,
        )
    except ImportError as exc:
        logger.error("groq client unavailable: %s", exc, exc_info=True)
        return _finish(
            question,
            started,
            latency,
            "The assistant client is not installed.",
            "error",
            guard,
            retrieval=view,
        )

    def _generate(repair: str | None = None) -> str:
        generated = time.perf_counter()
        text = client.complete(build_messages(context, question, repair=repair))
        latency["generate"] += int((time.perf_counter() - generated) * 1000)
        return text

    repair = (
        "Your previous answer failed validation. Rewrite it now. Use at most 3 short "
        "sentences, write the source_url plain and on its own with no brackets, "
        "markdown or trailing punctuation, and end with the line "
        "Last updated from sources: YYYY-MM-DD using an as_of_date that appears in "
        "the context. Be brief: keep your reasoning short so the answer fits."
    )
    try:
        draft = _generate()
        outcome = enforce_output(
            draft,
            result.hits,
            manifest_urls(),
            _corpus_newest(),
            regenerate=lambda: _generate(repair),
            question=question,
        )
    except LLMAuthError:
        return _finish(
            question,
            started,
            latency,
            "Assistant API not configured",
            "error",
            guard,
            retrieval=view,
        )
    except LLMTruncated:
        return _finish(
            question,
            started,
            latency,
            "That answer was too long to finish. Try asking about one scheme fact at a time.",
            "error",
            guard,
            retrieval=view,
        )
    except (LLMUnavailable, LLMRequestError):
        logger.warning("llm call failed for %d-char question", len(question), exc_info=True)
        return _finish(
            question,
            started,
            latency,
            "Something went wrong — please retry",
            "error",
            guard,
            retrieval=view,
        )

    guard["validation"] = outcome.code
    if outcome.status == "refused_advice":
        text, title, url = advice_message(question)
        return _finish(
            question,
            started,
            latency,
            text,
            "refused_advice",
            guard,
            citations=[Citation(title=title, url=url)],
            retrieval=view,
        )

    body = clean_citation_markup(strip_freshness(outcome.answer))
    if outcome.status == "out_of_corpus" or VALIDATOR_FALLBACK in body:
        return _finish(question, started, latency, VALIDATOR_FALLBACK, "out_of_corpus", guard, retrieval=view)

    date = outcome.freshness or freshness_date(outcome.answer)
    freshness = f"Last updated from sources: {date}" if date else None
    return _finish(
        question,
        started,
        latency,
        body,
        "answered",
        guard,
        citations=_citations_for(outcome.answer, result.hits),
        freshness=freshness,
        retrieval=view,
    )
