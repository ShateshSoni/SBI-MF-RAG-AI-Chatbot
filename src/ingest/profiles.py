"""Document-type profiles that select the parser and the split rule."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocProfile:
    doc_type: str
    parser: str
    split_on: str
    target_chars: int
    overlap_chars: int
    never_split_inside: str


def _profile(
    doc_type: str,
    parser: str,
    split_on: str,
    never_split_inside: str = "table_row",
    target_chars: int = 900,
    overlap_chars: int = 120,
) -> DocProfile:
    return DocProfile(doc_type, parser, split_on, target_chars, overlap_chars, never_split_inside)


PROFILES: dict[str, DocProfile] = {
    "factsheet": _profile("factsheet", "pdf_table", "scheme_section"),
    "sid": _profile("sid", "pdf_text", "heading"),
    "kim": _profile("kim", "pdf_text", "heading"),
    "ter_page": _profile("ter_page", "html_sections", "table_row", overlap_chars=0),
    "ter_notice": _profile("ter_notice", "pdf_text", "heading"),
    "guide": _profile("guide", "html_sections", "heading_or_list"),
    "regulator_faq": _profile("regulator_faq", "html_sections", "heading_or_list"),
    "campaign": _profile("campaign", "html_sections", "heading"),
    "disclosure_hub": _profile("disclosure_hub", "html_sections", "heading"),
    "tax_reckoner": _profile("tax_reckoner", "pdf_text", "heading"),
}


def profile_for(doc_type: str) -> DocProfile:
    try:
        return PROFILES[doc_type]
    except KeyError as exc:
        raise KeyError(f"no profile for doc_type {doc_type}") from exc
