"""Stage 1 PDF parser: pdfplumber blocks with a pypdf fallback."""

from __future__ import annotations

import logging
import re
import statistics
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

from src.ingest.errors import ParseError
from src.ingest.manifest import Doc
from src.ingest.types import Block, ParseMeta

logger = logging.getLogger(__name__)

_FURNITURE = re.compile(
    r"(mutual fund investments are subject to market risks|"
    r"sbimf\.com|^page\s+\d+(\s+of\s+\d+)?$|^--\s*\d+\s*of\s*\d+\s*--$)",
    re.IGNORECASE,
)
_HEADING = re.compile(
    r"^((\d+(\.\d+)*)[\.\)]\s+|[IVXLC]{1,6}\.\s+|[A-Z]\.\s+).{3,120}$"
)


def parse_pdf(path: Path, doc: Doc, parser: str = "pdf_table") -> tuple[list[Block], ParseMeta]:
    raw = path.read_bytes()[:8]
    if not raw.startswith(b"%PDF"):
        raise ParseError(f"{doc.doc_id}: file is not a PDF")
    started = _now()
    blocks: list[Block] = []
    notes: list[str] = []
    artefacts = 0
    real_tables = 0
    fallback_pages = 0
    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)
        reader = None
        for index, page in enumerate(pdf.pages, start=1):
            if index == 1 or index % 10 == 0:
                logger.info("parsing %s page %s/%s", doc.doc_id, index, page_count)
            try:
                page_blocks, page_artefacts, page_tables = _page_blocks(page, index, parser)
                artefacts += page_artefacts
                real_tables += page_tables
            except Exception:
                logger.warning("pdfplumber failed on %s page %s", doc.doc_id, index)
                page_blocks = []
            if not page_blocks:
                if reader is None:
                    reader = PdfReader(str(path))
                page_blocks = _pypdf_blocks(reader, index - 1, index)
                if page_blocks:
                    fallback_pages += 1
            blocks.extend(page_blocks)
    if artefacts:
        notes.append(f"{artefacts} page-wide ruled tables treated as layout artefacts")
    if fallback_pages:
        notes.append(f"pypdf fallback on {fallback_pages} pages")
    flag = ""
    if parser == "pdf_table" and real_tables == 0:
        flag = "PDF_NO_RULED_TABLES"
        notes.append("no ruled tables; text recovered from word positions")
    if not blocks:
        raise ParseError(f"{doc.doc_id}: parser produced zero blocks")
    logger.info(
        "parsed %s blocks=%s pages=%s seconds=%.1f",
        doc.doc_id,
        len(blocks),
        page_count,
        _now() - started,
    )
    return blocks, ParseMeta(pages=page_count, parser=parser, flag=flag, notes="; ".join(notes))


def _page_blocks(page, page_no: int, parser: str) -> tuple[list[Block], int, int]:
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False) or []
    artefacts = 0
    real_tables = 0
    table_rects: list[tuple[float, float, float, float]] = []
    table_blocks: list[Block] = []
    if parser == "pdf_table":
        found = page.find_tables() or []
        for ordinal, table in enumerate(found, start=1):
            bbox = table.bbox
            if _reject_table(bbox, float(page.width), float(page.height)):
                artefacts += 1
                continue
            rows = table.extract() or []
            if not rows:
                continue
            real_tables += 1
            table_rects.append(bbox)
            table_blocks.extend(_table_blocks(rows, page_no, f"p{page_no}-t{ordinal}"))
    prose_words = [word for word in words if not _inside_any(word, table_rects)]
    if parser == "pdf_table":
        prose = _column_flow(prose_words, page_no, float(page.width), float(page.height))
    else:
        prose = _words_to_blocks(prose_words, page_no, float(page.height))
    return prose + table_blocks, artefacts, real_tables


def _table_blocks(rows: list[list[str | None]], page_no: int, table_id: str) -> list[Block]:
    cleaned = [[_collapse(cell or "") for cell in row] for row in rows]
    cleaned = [row for row in cleaned if any(row)]
    if not cleaned:
        return []
    header: list[str] | None = None
    if len(cleaned) >= 2 and _looks_like_header(cleaned[0]):
        header = cleaned[0]
        body = cleaned[1:]
    else:
        body = cleaned
    blocks: list[Block] = []
    if header:
        blocks.append(
            Block(
                kind="table_row",
                text=" | ".join(cell for cell in header if cell),
                page_no=page_no,
                table_id=table_id,
                row_span=1,
                level=0,
            )
        )
    for row in body:
        pipe = " | ".join(cell for cell in row if cell)
        labelled = _label_row(header, row)
        text = f"{labelled}\n{pipe}" if labelled else pipe
        if text:
            blocks.append(
                Block(kind="table_row", text=text, page_no=page_no, table_id=table_id, row_span=1)
            )
    return blocks


def _label_row(header: list[str] | None, row: list[str]) -> str:
    if not header:
        return ""
    lines: list[str] = []
    for name, value in zip(header, row):
        if name and value:
            lines.append(f"{name}: {value}")
    return "\n".join(lines)


def _looks_like_header(row: list[str]) -> bool:
    filled = [cell for cell in row if cell]
    if len(filled) < 2:
        return False
    digits = sum(1 for cell in filled if re.search(r"\d", cell))
    return digits <= len(filled) / 2


def _column_flow(words: list[dict], page_no: int, page_width: float, page_height: float) -> list[Block]:
    if not words:
        return []
    edges = _column_edges(words, page_width)
    if len(edges) < 3:
        return _words_to_blocks(words, page_no, page_height)
    blocks: list[Block] = []
    for left, right in zip(edges, edges[1:]):
        selected = [
            word
            for word in words
            if left <= (float(word["x0"]) + float(word["x1"])) / 2 < right + 0.01
        ]
        blocks.extend(_words_to_blocks(selected, page_no, page_height))
    return blocks


def _column_edges(words: list[dict], page_width: float, min_gap: float = 22.0) -> list[float]:
    step = 3.0
    buckets = int(page_width / step) + 2
    occupancy = [0] * buckets
    for word in words:
        start = max(0, int(float(word["x0"]) / step))
        end = min(buckets - 1, int(float(word["x1"]) / step))
        for index in range(start, end + 1):
            occupancy[index] += 1
    gaps: list[tuple[float, float]] = []
    index = 0
    while index < buckets:
        if occupancy[index] == 0:
            start = index
            while index < buckets and occupancy[index] == 0:
                index += 1
            if (index - start) * step >= min_gap and start > 2 and index < buckets - 2:
                gaps.append((start * step, index * step))
        else:
            index += 1
    edges = [0.0]
    for gap_start, gap_end in gaps:
        edges.append((gap_start + gap_end) / 2)
    edges.append(page_width)
    merged = [edges[0]]
    for edge in edges[1:]:
        if edge - merged[-1] < 36:
            continue
        merged.append(edge)
    if merged[-1] < page_width:
        merged.append(page_width)
    return merged


def _words_to_blocks(words: list[dict], page_no: int, page_height: float) -> list[Block]:
    if not words:
        return []
    heights = [float(word.get("height") or 0) for word in words if word.get("height")]
    median_height = statistics.median(heights) if heights else 10.0
    lines = _group_lines(words)
    blocks: list[Block] = []
    paragraph: list[str] = []
    for line in lines:
        text = _normalize_line(_collapse(_join_line(line["words"])))
        if not text:
            continue
        top = float(line["top"])
        bottom = float(line["bottom"])
        if _is_furniture(text, top, bottom, page_height):
            continue
        kind = _classify(text, line["words"], median_height)
        if kind == "heading":
            _flush_paragraph(paragraph, blocks, page_no)
            blocks.append(Block(kind="heading", text=text, level=2, page_no=page_no))
        elif kind == "table_row":
            _flush_paragraph(paragraph, blocks, page_no)
            blocks.append(Block(kind="table_row", text=text, page_no=page_no, table_id=f"p{page_no}-flow", row_span=1))
        else:
            if paragraph and paragraph[-1].endswith("-") and text[:1].islower():
                paragraph[-1] = paragraph[-1][:-1] + text
            else:
                paragraph.append(text)
    _flush_paragraph(paragraph, blocks, page_no)
    return blocks


def _flush_paragraph(paragraph: list[str], blocks: list[Block], page_no: int) -> None:
    if not paragraph:
        return
    text = _collapse(" ".join(paragraph))
    paragraph.clear()
    if text:
        blocks.append(Block(kind="para", text=text, page_no=page_no))


def _group_lines(words: list[dict]) -> list[dict]:
    ordered = sorted(words, key=lambda word: (round(float(word["top"]), 1), float(word["x0"])))
    lines: list[dict] = []
    for word in ordered:
        top = float(word["top"])
        if lines and abs(top - lines[-1]["top"]) <= 3:
            lines[-1]["words"].append(word)
            lines[-1]["bottom"] = max(lines[-1]["bottom"], float(word["bottom"]))
        else:
            lines.append({"top": top, "bottom": float(word["bottom"]), "words": [word]})
    for line in lines:
        line["words"].sort(key=lambda word: float(word["x0"]))
    return lines


def _join_line(words: list[dict]) -> str:
    if not words:
        return ""
    gaps = [float(right["x0"]) - float(left["x1"]) for left, right in zip(words, words[1:])]
    positive = [gap for gap in gaps if gap > 0.4]
    threshold = max(12.0, (statistics.median(positive) * 3) if positive else 12.0)
    parts = [str(words[0].get("text") or "")]
    for gap, word in zip(gaps, words[1:]):
        parts.append(" | " if gap >= threshold else " ")
        parts.append(str(word.get("text") or ""))
    return "".join(parts)


_SECTION_TITLES = re.compile(
    r"^(investment objective|exit load|entry load|asset allocation|riskometer|"
    r"benchmark|fees and expenses|load structure|minimum application|plans and options|"
    r"fund details|highlights|product label|scheme riskometer)$",
    re.IGNORECASE,
)


def _classify(text: str, words: list[dict], median_height: float) -> str:
    del words, median_height
    if " | " in text and (re.search(r"\d", text) or text.count(" | ") >= 2):
        return "table_row"
    letters = sum(character.isalpha() for character in text)
    caps = text.isupper() and 8 <= len(text) <= 80 and letters >= 6 and not re.search(r"\d{3,}", text)
    if len(text) <= 140 and letters >= 3 and (_HEADING.match(text) or _SECTION_TITLES.match(text) or caps):
        return "heading"
    return "para"


def _is_furniture(text: str, top: float, bottom: float, page_height: float) -> bool:
    in_margin = top <= page_height * 0.055 or bottom >= page_height * 0.945
    if _FURNITURE.search(text) and (in_margin or len(text) < 140):
        return True
    if in_margin and len(text) < 40:
        return True
    return False


def _reject_table(bbox: tuple[float, float, float, float], width: float, height: float) -> bool:
    x0, _y0, x1, _y1 = bbox
    if width > 0 and (x1 - x0) >= width * 0.75:
        return True
    return _page_wide(bbox, width, height)


def _page_wide(bbox: tuple[float, float, float, float], width: float, height: float) -> bool:
    x0, y0, x1, y1 = bbox
    if width <= 0 or height <= 0:
        return False
    return (x1 - x0) >= width * 0.85 and (y1 - y0) >= height * 0.85


def _inside_any(word: dict, rects: list[tuple[float, float, float, float]]) -> bool:
    x = (float(word["x0"]) + float(word["x1"])) / 2
    y = (float(word["top"]) + float(word["bottom"])) / 2
    for x0, y0, x1, y1 in rects:
        if x0 <= x <= x1 and min(y0, y1) <= y <= max(y0, y1):
            return True
    return False


def _pypdf_blocks(reader: PdfReader, index: int, page_no: int) -> list[Block]:
    if index >= len(reader.pages):
        return []
    text = reader.pages[index].extract_text() or ""
    paragraphs = [_collapse(part) for part in re.split(r"\n\s*\n", text)]
    return [Block(kind="para", text=part, page_no=page_no) for part in paragraphs if part]


def _normalize_line(text: str) -> str:
    if not text:
        return text
    text = re.sub(r"\.{4,}", " ", text)
    text = _collapse(text)
    forward = len(re.findall(r"\b(SBI|Fund|Plan|Direct|Regular|Expense|Exit)\b", text))
    backward = len(re.findall(r"\b(IBS|dnuF|nalP|tceriD|ralugeR|esnepxE|tixE)\b", text))
    if backward > forward:
        text = _collapse(text[::-1])
    tokens = text.split(" ")
    singles = sum(1 for token in tokens if len(token) == 1)
    if tokens and singles / len(tokens) >= 0.45:
        text = _collapse(_join_single_characters(tokens))
    return text


def _join_single_characters(tokens: list[str]) -> str:
    pieces: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            pieces.append("".join(buffer))
            buffer.clear()

    for token in tokens:
        if len(token) == 1:
            buffer.append(token)
        else:
            flush()
            pieces.append(token)
    flush()
    return " ".join(pieces)


def _collapse(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip()


def _now() -> float:
    import time

    return time.perf_counter()
