"""Chunker invariants: token cap, stable ids, and intact table rows."""

from __future__ import annotations

from src.config import TOKENIZER_TOKEN_LIMIT
from src.ingest.chunk import split_document
from src.ingest.manifest import Doc
from src.ingest.types import Block


def _doc(**overrides) -> Doc:
    payload = dict(
        doc_id="sample_factsheet",
        title="Sample factsheet",
        doc_type="factsheet",
        scheme="All schemes",
        scheme_category="",
        source_url="https://www.sbimf.com/factsheet.pdf",
        as_of_date="2026-06-30",
        tier=1,
        ingest=True,
        local_filename="",
        fetched_at="",
        notes="",
    )
    payload.update(overrides)
    return Doc(**payload)


def _blocks() -> list[Block]:
    return [
        Block(kind="heading", text="SBI Bluechip Fund", level=2, page_no=1),
        Block(kind="para", text="Expense ratio", page_no=1),
        Block(kind="table_row", text="TER | 1.50 | 0.86", page_no=1, table_id="p1"),
        Block(kind="table_row", text="Exit load | 1% if redeemed within 12 months", page_no=1, table_id="p1"),
        Block(kind="heading", text="SBI Flexicap Fund", level=2, page_no=2),
        Block(kind="para", text="Expense ratio", page_no=2),
        Block(kind="table_row", text="TER | 1.60 | 0.70", page_no=2, table_id="p2"),
    ]


def test_token_cap_unique_stable_ids_and_ter_rows() -> None:
    doc = _doc()
    first, bad = split_document(doc, _blocks())
    second, _again = split_document(doc, _blocks())
    assert bad == []
    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert len({chunk.chunk_id for chunk in first}) == len(first)
    assert all(chunk.token_len <= TOKENIZER_TOKEN_LIMIT for chunk in first)
    assert all(chunk.scheme and chunk.source_url and chunk.as_of_date for chunk in first)
    ter = [chunk for chunk in first if "TER |" in chunk.text]
    assert len(ter) == 2
    assert ter[0].scheme == "SBI Bluechip Fund"
    assert "1.50" in ter[0].text and "0.86" in ter[0].text
    assert ter[1].scheme == "SBI Flexicap Fund"
    exit_row = "Exit load | 1% if redeemed within 12 months"
    assert sum(exit_row in chunk.text for chunk in first) == 1


def test_long_prose_is_resplit_not_truncated() -> None:
    sentence = "The exit load is one percent if units are redeemed within twelve months. "
    doc = _doc(doc_id="sample_sid", doc_type="sid", scheme="SBI Small Cap Fund", scheme_category="Small Cap", title="SID")
    blocks = [Block(kind="para", text=sentence * 80, page_no=3)]
    chunks, bad = split_document(doc, blocks)
    assert bad == []
    assert len(chunks) > 1
    assert all(chunk.token_len <= TOKENIZER_TOKEN_LIMIT for chunk in chunks)
    assert all(chunk.scheme == "SBI Small Cap Fund" for chunk in chunks)
    assert "one percent" in "".join(chunk.text for chunk in chunks)


def test_ter_page_one_chunk_per_row() -> None:
    doc = _doc(doc_id="ter_page", doc_type="ter_page", scheme="All schemes")
    blocks = [
        Block(kind="table_row", text="SBI Bluechip Fund | TER | 1.50 | 0.86", page_no=1, table_id="t"),
        Block(kind="table_row", text="SBI Small Cap Fund | TER | 1.70 | 0.90", page_no=1, table_id="t"),
    ]
    chunks, bad = split_document(doc, blocks)
    assert bad == []
    assert len(chunks) == 2
    assert {chunk.scheme for chunk in chunks} == {"SBI Bluechip Fund", "SBI Small Cap Fund"}
