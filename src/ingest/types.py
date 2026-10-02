"""Shared block contract produced by the PDF and HTML parsers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Block:
    kind: str
    text: str
    level: int = 0
    page_no: int = 1
    table_id: str | None = None
    row_span: int | None = None


@dataclass
class ParseMeta:
    pages: int
    parser: str
    flag: str = ""
    notes: str = ""
