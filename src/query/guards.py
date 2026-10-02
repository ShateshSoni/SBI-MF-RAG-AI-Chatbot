"""Length and PII guards, plus the canned refusal copy."""

from __future__ import annotations

import re
from functools import lru_cache

from src.ingest.manifest import Doc, load_manifest

PII_REFUSAL = (
    "For your security I can't accept personal identifiers such as PAN, Aadhaar, "
    "account or OTP details. Please ask only about scheme facts."
)

ADVICE_REFUSAL = "I only share documented facts and don't give investment advice."

OUT_OF_CORPUS = (
    "I can't find that in my official sources. Try asking about expense ratio, "
    "exit load, minimum SIP, lock-in, riskometer, benchmark, or how to download a statement."
)

VALIDATOR_FALLBACK = "I can't answer that from my official sources."

_PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
_AADHAAR = re.compile(r"\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b")
_MOBILE = re.compile(r"(\+91[- ]?)?[6-9]\d{9}\b")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_DIGIT_RUN = re.compile(r"\b\d{9,18}\b")
_DIGIT_KEYWORD = re.compile(
    r"account|folio|bank|ifsc|aadhaar|aadhar|pan|mobile|phone|otp|cvv|demat|card",
    re.IGNORECASE,
)
_KEYWORD = re.compile(
    r"\b(otp|cvv|pan number|aadhaar|aadhar|folio (no|number)|account number|demat)\b",
    re.IGNORECASE,
)
_OTHER_HOUSE = re.compile(
    r"\b(hdfc|icici prudential|icici|axis mutual|nippon|kotak|mirae|parag parikh|"
    r"zerodha|uti mutual|bandhan mutual|quant mutual)\b",
    re.IGNORECASE,
)
_NAV = re.compile(r"\bnav\b", re.IGNORECASE)
_LIVE = re.compile(r"\b(today|current|live|right now)\b", re.IGNORECASE)


@lru_cache(maxsize=1)
def manifest_docs() -> tuple[Doc, ...]:
    return tuple(load_manifest())


def _doc(doc_id: str) -> Doc:
    for doc in manifest_docs():
        if doc.doc_id == doc_id:
            return doc
    raise KeyError(doc_id)


def manifest_urls() -> set[str]:
    return {doc.source_url for doc in manifest_docs()}


def check_length(question: str, limit: int = 500) -> str | None:
    """Return empty, too_long, or non_text. None means the question may continue."""
    if not isinstance(question, str) or not question.strip():
        return "empty"
    if len(question) > limit:
        return "too_long"
    if not re.search(r"[A-Za-z0-9]", question):
        return "non_text"
    return None


def check_pii(question: str) -> str | None:
    """Return the PII class, or None. Bare digit runs need a nearby keyword."""
    text = question or ""
    if _PAN.search(text):
        return "pan"
    if _AADHAAR.search(text):
        return "aadhaar"
    if _EMAIL.search(text):
        return "email"
    keyword = _KEYWORD.search(text)
    if keyword:
        token = keyword.group(1).lower()
        if token.startswith("folio"):
            return "folio"
        if token.startswith("account"):
            return "account"
        if token.startswith("pan"):
            return "pan"
        if token.startswith("aadhar"):
            return "aadhaar"
        return token
    if _MOBILE.search(text):
        return "mobile"
    for match in _DIGIT_RUN.finditer(text):
        window = text[max(0, match.start() - 48) : min(len(text), match.end() + 48)]
        if _DIGIT_KEYWORD.search(window):
            return "account"
    return None


def check_scope(question: str) -> str | None:
    """Live NAV and other fund houses are outside this corpus."""
    text = question or ""
    if _OTHER_HOUSE.search(text):
        return "other_house"
    if _NAV.search(text) and _LIVE.search(text):
        return "live_nav"
    return None


def advice_link(question: str) -> tuple[str, str]:
    """Pick a tier-4 educational page from the manifest."""
    text = question.lower()
    compares = re.search(r"\b(vs|versus|or)\b", text) and re.search(
        r"flexi|large cap|small cap|mid cap|categor", text
    )
    if compares:
        doc = _doc("amfi_categorization")
        return doc.title, doc.source_url
    if re.search(r"\b(which|best|category|elss|type)\b", text):
        doc = _doc("amfi_scheme_types")
        return doc.title, doc.source_url
    doc = _doc("sebi_mf_faq_2024_09")
    return doc.title, doc.source_url


def advice_message(question: str) -> tuple[str, str, str]:
    title, url = advice_link(question)
    text = f"{ADVICE_REFUSAL} For how these fund categories work, see {title}: {url}"
    return text, title, url


def factsheet_message() -> tuple[str, str, str, str]:
    doc = _doc("sbimf_factsheet_2026_06")
    text = (
        "Performance is published in the official factsheet, and I do not compute, "
        f"compare, or estimate returns. Source: {doc.source_url}"
    )
    return text, doc.title, doc.source_url, doc.as_of_date


def length_message(kind: str) -> tuple[str, str]:
    if kind == "empty":
        return "Please ask a factual question about an SBI Mutual Fund scheme.", "out_of_corpus"
    return "Please ask a shorter factual question (500 characters or fewer).", "error"
