"""Write the human-readable chunk dump used as the embedding gate."""

from __future__ import annotations

from pathlib import Path

from src.ingest.chunk import Chunk

_DIVIDER = "=" * 80


def write_chunks(chunks: list[Chunk], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []
    for chunk in chunks:
        parts.append(
            "\n".join(
                [
                    f"chunk_id: {chunk.chunk_id}",
                    f"doc_id: {chunk.doc_id}",
                    f"source_url: {chunk.source_url}",
                    f"doc_title: {chunk.doc_title}",
                    f"doc_type: {chunk.doc_type}",
                    f"scheme: {chunk.scheme}",
                    f"scheme_category: {chunk.scheme_category}",
                    f"section: {chunk.section}",
                    f"page_no: {chunk.page_no}",
                    f"as_of_date: {chunk.as_of_date}",
                    f"char_len: {chunk.char_len}",
                    f"token_len: {chunk.token_len}",
                    "",
                    chunk.text,
                    "",
                    _DIVIDER,
                    "",
                ]
            )
        )
    path.write_text("".join(parts), encoding="utf-8")
