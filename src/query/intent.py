"""Advice, performance, and scheme-alias detection. Regex only; no LLM fallback."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Stored scheme strings. Both "SBI Large Cap Fund" and "SBI Bluechip Fund" share one id.
_BLUECHIP = "SBI Bluechip Fund"
_LTE = "SBI Long Term Equity Fund"
_FLEXI = "SBI Flexicap Fund"
_SMALL = "SBI Small Cap Fund"

# Category words ("ELSS", "large cap", "flexi-cap") are intentionally absent.
_SCHEME_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\bsbi\s+large\s+cap\s+fund\b|\b(?:sbi\s+)?blue\s*chip(?:\s+fund)?\b",
            re.IGNORECASE,
        ),
        _BLUECHIP,
    ),
    (
        re.compile(
            r"\bsbi\s+lte\b|\blong\s+term\s+equity(?:\s+fund)?\b|\bsbi\s+elss\b|"
            r"\belss\s+tax\s+saver\b|\btax\s+saver\b",
            re.IGNORECASE,
        ),
        _LTE,
    ),
    (
        re.compile(
            r"\bsbi\s+flexi\s*cap(?:\s+fund)?\b|\bflexi\s*cap\s+fund\b",
            re.IGNORECASE,
        ),
        _FLEXI,
    ),
    (
        re.compile(
            r"\bsbi\s+small\s*cap(?:\s+fund)?\b|\bsmallcap\s+fund\b",
            re.IGNORECASE,
        ),
        _SMALL,
    ),
)

_ADVICE_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("should_i", re.compile(r"\bshould i (buy|sell|invest|switch|exit)\b", re.IGNORECASE)),
    ("which_better", re.compile(r"\bwhich (fund|scheme|elss|one)\b.{0,48}\b(better|best)\b", re.IGNORECASE)),
    ("which_is_better", re.compile(r"\bwhich (fund|scheme) is better\b", re.IGNORECASE)),
    ("best_fund", re.compile(r"\bbest (fund|scheme|returns)\b", re.IGNORECASE)),
    ("recommend", re.compile(r"\brecommend", re.IGNORECASE)),
    ("good_time", re.compile(r"\bis (it|now) a good time\b", re.IGNORECASE)),
    ("worth_it", re.compile(r"\bworth it\b", re.IGNORECASE)),
    ("allocate", re.compile(r"\ballocate\b", re.IGNORECASE)),
    ("portfolio", re.compile(r"\bportfolio\b", re.IGNORECASE)),
    ("suitable", re.compile(r"\bsuitable for me\b", re.IGNORECASE)),
    ("can_i_exit", re.compile(r"\bcan i exit\b", re.IGNORECASE)),
    ("would_you", re.compile(r"\bwould you (buy|sell|invest|recommend)\b", re.IGNORECASE)),
    ("as_a_friend", re.compile(r"\bas a friend\b", re.IGNORECASE)),
)

_PERFORMANCE_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("return", re.compile(r"\breturns?\b", re.IGNORECASE)),
    ("cagr", re.compile(r"\bcagr\b", re.IGNORECASE)),
    ("pct_gain", re.compile(r"%\s*gain", re.IGNORECASE)),
    ("performance", re.compile(r"\bperformance\b", re.IGNORECASE)),
    ("how_much_earned", re.compile(r"\bhow much did (it|the scheme) (earn|gain)\b", re.IGNORECASE)),
    ("vs_other", re.compile(r"\bvs other funds\b", re.IGNORECASE)),
    ("earn", re.compile(r"\bearn(?:ed|s)?\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class Match:
    intent: str
    rule: str


def detect_advice(text: str) -> Match | None:
    for name, pattern in _ADVICE_RULES:
        if pattern.search(text or ""):
            return Match("advice", name)
    return None


def detect_performance(text: str) -> Match | None:
    for name, pattern in _PERFORMANCE_RULES:
        if pattern.search(text or ""):
            return Match("performance", name)
    return None


def detect_scheme(text: str) -> str | None:
    """Return the canonical stored scheme, or None for categories and mixed mentions."""
    found: list[str] = []
    for pattern, name in _SCHEME_RULES:
        if pattern.search(text or "") and name not in found:
            found.append(name)
    if len(found) == 1:
        return found[0]
    return None


def rewrite_for_embedding(question: str, scheme: str | None) -> str:
    """Append the canonical scheme name so the encoder sees the stored label."""
    if scheme and scheme.lower() not in question.lower():
        return f"{question} {scheme}"
    return question
