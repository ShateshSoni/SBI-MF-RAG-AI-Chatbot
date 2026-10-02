"""Write parse and chunk reports, including the human-review section."""

from __future__ import annotations

import re
import statistics
from pathlib import Path

from src.ingest.chunk import Chunk
from src.ingest.coverage import TOPICS

_VERDICT_HEADING = "## Review verdict"


def write_parse_report(
    rows: list[dict[str, str]],
    support: dict[str, list[str]],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Parse report",
        "",
        "| doc_id | tier | ingest | blocks | chars | pages | parser | flag | error |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {doc_id} | {tier} | {ingest} | {blocks} | {chars} | {pages} | {parser} | {flag} | {error} |".format(
                **{key: _cell(row.get(key, "")) for key in ("doc_id", "tier", "ingest", "blocks", "chars", "pages", "parser", "flag", "error")}
            )
        )
    lines.extend(["", "## Mandatory-topic coverage", "", "| topic | documents | count | gate |", "|---|---|---|---|"])
    for topic in TOPICS:
        doc_ids = support.get(topic, [])
        gate = "pass" if len(doc_ids) >= 2 else "FAIL"
        listed = ", ".join(doc_ids) if doc_ids else "—"
        lines.append(f"| {topic} | {listed} | {len(doc_ids)} | {gate} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_chunk_report(
    chunks: list[Chunk],
    unsplittable: list[str],
    parse_flags: list[str],
    rationale: str,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    verdict = _existing_verdict(path)
    by_doc: dict[str, list[Chunk]] = {}
    for chunk in chunks:
        by_doc.setdefault(chunk.doc_id, []).append(chunk)
    over_limit = sum(1 for chunk in chunks if chunk.token_len > 250)
    lines = [
        "# Chunk report",
        "",
        f"chunks: {len(chunks)}",
        f"over_limit: {over_limit}",
        f"unsplittable: {len(unsplittable)}",
        "",
        "## Per document",
        "",
        "| doc_id | chunks | min | median | max |",
        "|---|---|---|---|---|",
    ]
    for doc_id in sorted(by_doc):
        lengths = sorted(chunk.token_len for chunk in by_doc[doc_id])
        lines.append(
            f"| {doc_id} | {len(lengths)} | {lengths[0]} | {_median(lengths)} | {lengths[-1]} |"
        )
    lines.extend(["", "## Unsplittable", ""])
    if unsplittable:
        lines.extend(f"- {item}" for item in unsplittable)
    else:
        lines.append("None.")
    lines.extend(["", "## Parse flags", ""])
    if parse_flags:
        lines.extend(f"- {item}" for item in parse_flags)
    else:
        lines.append("None.")
    lines.extend(["", "## Chunking rationale", "", rationale.strip(), "", _VERDICT_HEADING, "", verdict, ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _existing_verdict(path: Path) -> str:
    if not path.exists():
        return "Pending review of artifacts/chunks.txt."
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"{re.escape(_VERDICT_HEADING)}\n+([\s\S]+)$", text)
    if not match:
        return "Pending review of artifacts/chunks.txt."
    verdict = match.group(1).strip()
    return verdict or "Pending review of artifacts/chunks.txt."


def _median(values: list[int]) -> float:
    if not values:
        return 0
    return statistics.median(values)


def _cell(value: str) -> str:
    return value.replace("|", "/") if value else "—"
