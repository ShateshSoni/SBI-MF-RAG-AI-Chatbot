"""Fail-closed checks on model output. V5 discards the answer."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from src.query.guards import VALIDATOR_FALLBACK, advice_message
from src.query.intent import detect_advice

logger = logging.getLogger(__name__)

# Brackets, angle quotes and backticks are never part of a source link, but models
# routinely wrap one in 【…】, [label](link) or `link` before copying it across.
# Excluding them here means a decorated URL still compares equal to the manifest
# entry, instead of failing the citation check on punctuation alone.
_URL = re.compile("https://[^\\s<>\"'`()\\[\\]{}`【】〔〕《》〈〉]+")
_TRAILING_URL_CHARS = ".,;:!?*。，、；：！？"
_FRESHNESS = re.compile(r"Last updated from sources:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
_ABBREVIATIONS = ("e.g.", "i.e.", "Rs.")
_PERFORMANCE = re.compile(
    r"%|₹|\bRs\.?|\bINR\b|\bCAGR\b|\b\d+\s*-?\s*(?:year|month)s?\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class ValidationOutcome:
    answer: str
    status: str
    code: str | None
    freshness: str | None


def extract_urls(text: str) -> list[str]:
    urls = []
    for match in _URL.findall(text or ""):
        cleaned = match.rstrip(_TRAILING_URL_CHARS)
        if cleaned:
            urls.append(cleaned)
    return urls


def split_sentences(text: str) -> list[str]:
    """Split on .?! while keeping e.g., i.e., and Rs. intact."""
    protected = text or ""
    for abbr in _ABBREVIATIONS:
        protected = re.sub(re.escape(abbr), abbr.replace(".", "\0"), protected, flags=re.IGNORECASE)
    parts = re.split(r"(?<=[.!?])\s+", protected.strip())
    sentences = []
    for part in parts:
        cleaned = part.replace("\0", ".").strip()
        if cleaned:
            sentences.append(cleaned)
    return sentences


def freshness_date(text: str) -> str | None:
    match = _FRESHNESS.search(text or "")
    return match.group(1) if match else None


def strip_freshness(text: str) -> str:
    return _FRESHNESS.sub("", text or "").strip()


# Models habitually wrap a copied link in 【…】 or (…) before emitting it. The
# brackets are presentational, so drop them and keep the bare link, leaving a
# space behind so the number and the link do not run together.
_CITATION_WRAPPER = re.compile(r"[【〔（(]\s*(https://\S+?)\s*[】〕）)]")


def clean_citation_markup(text: str) -> str:
    def _unwrap(match: re.Match) -> str:
        start = match.start()
        needs_space = start > 0 and not match.string[start - 1].isspace()
        return f"{' ' if needs_space else ''}{match.group(1)}"

    return _CITATION_WRAPPER.sub(_unwrap, text or "").rstrip()


def _context_blob(hits: list) -> tuple[str, set[str], set[str]]:
    parts: list[str] = []
    urls: set[str] = set()
    dates: set[str] = set()
    for hit in hits:
        meta = hit.metadata
        url = str(meta.get("source_url") or "")
        as_of = str(meta.get("as_of_date") or "")
        parts.append(hit.text or "")
        parts.append(url)
        parts.append(as_of)
        if url:
            urls.add(url)
        if as_of:
            dates.add(as_of)
    return "\n".join(parts), urls, dates


def _cited(answer: str, manifest_urls: set[str], context_urls: set[str]) -> bool:
    for url in extract_urls(answer):
        if url in manifest_urls and url in context_urls:
            return True
    return False


def _uncited_performance(answer: str, context: str) -> bool:
    body = strip_freshness(answer)
    for sentence in split_sentences(body):
        if not _PERFORMANCE.search(sentence):
            continue
        if extract_urls(sentence):
            continue
        for number in _NUMBER.findall(sentence):
            if number not in context:
                return True
    return False


def _issues(answer: str, hits: list, manifest_urls: set[str]) -> set[str]:
    context, context_urls, dates = _context_blob(hits)
    found: set[str] = set()
    if detect_advice(answer):
        found.add("v5")
    if not _cited(answer, manifest_urls, context_urls):
        found.add("v1")
    if len(split_sentences(strip_freshness(answer))) > 3:
        found.add("v2")
    date = freshness_date(answer)
    if date is None or date not in dates:
        found.add("v3")
    if _uncited_performance(answer, context):
        found.add("v4")
    return found


def _truncate(answer: str) -> str:
    date_line = ""
    match = _FRESHNESS.search(answer or "")
    if match:
        date_line = match.group(0)
    sentences = split_sentences(strip_freshness(answer))
    kept = " ".join(sentences[:3])
    if date_line:
        return f"{kept}\n{date_line}"
    return kept


def _append_freshness(answer: str, hits: list) -> str:
    dates = [str(hit.metadata.get("as_of_date") or "") for hit in hits]
    dates = [item for item in dates if item]
    chosen = max(dates) if dates else ""
    line = f"Last updated from sources: {chosen}"
    body = strip_freshness(answer)
    return f"{body}\n{line}".strip()


def _warn_if_stale(answer: str, newest_corpus: str) -> None:
    date = freshness_date(answer)
    if date and newest_corpus and date < newest_corpus:
        logger.warning("STALE_SOURCE date=%s newest=%s", date, newest_corpus)


def enforce_output(
    answer: str,
    hits: list,
    manifest_urls: set[str],
    newest_corpus: str,
    regenerate,
    question: str = "",
) -> ValidationOutcome:
    """Apply V1–V6. Regenerate at most once, then fall closed."""
    current = answer
    regenerated = False
    while True:
        issues = _issues(current, hits, manifest_urls)
        if "v5" in issues:
            text, _title, _url = advice_message(question or current)
            return ValidationOutcome(text, "refused_advice", "v5", None)

        if "v2" in issues:
            shortened = _truncate(current)
            shortened_issues = _issues(shortened, hits, manifest_urls)
            if "v1" not in shortened_issues and "v4" not in shortened_issues:
                current = shortened
                issues = shortened_issues
            else:
                issues.add("v2")

        blocking = issues & {"v1", "v2", "v4"}
        if not blocking and "v3" not in issues:
            _warn_if_stale(current, newest_corpus)
            return ValidationOutcome(current, "answered", None, freshness_date(current))

        if regenerated:
            if not blocking and "v3" in issues:
                current = _append_freshness(current, hits)
                _warn_if_stale(current, newest_corpus)
                return ValidationOutcome(current, "answered", "v3", freshness_date(current))
            code = "v1" if "v1" in issues else "v4" if "v4" in issues else "v2"
            return ValidationOutcome(VALIDATOR_FALLBACK, "out_of_corpus", code, None)

        if not blocking and "v3" in issues:
            current = regenerate()
            regenerated = True
            continue

        current = regenerate()
        regenerated = True
