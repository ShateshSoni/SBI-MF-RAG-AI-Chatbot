"""Stage 2 of ingestion: document-type-aware chunking under the tokenizer cap."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.config import EMBEDDING_MODEL, TOKENIZER_TOKEN_LIMIT
from src.ingest.manifest import Doc
from src.ingest.profiles import DocProfile, profile_for
from src.ingest.types import Block

_TOKENIZER = None

_SCHEMES: tuple[tuple[re.Pattern[str], str, str, str], ...] = (
    (
        re.compile(r"sbi\s+large\s+cap\s+fund|sbi\s+blue\s*chip(?:\s+fund)?", re.IGNORECASE),
        "SBI Bluechip Fund",
        "Large Cap",
        "bluechip",
    ),
    (
        re.compile(r"sbi\s+long\s+term\s+equity|sbi\s+elss|long\s+term\s+equity\s+fund", re.IGNORECASE),
        "SBI Long Term Equity Fund",
        "ELSS",
        "long-term-equity",
    ),
    (
        re.compile(r"sbi\s+flexi\s*cap(?:\s+fund)?", re.IGNORECASE),
        "SBI Flexicap Fund",
        "Flexi Cap",
        "flexicap",
    ),
    (
        re.compile(r"sbi\s+small\s*cap(?:\s+fund)?", re.IGNORECASE),
        "SBI Small Cap Fund",
        "Small Cap",
        "smallcap",
    ),
)

_SECTION_RULES: tuple[tuple[str, str], ...] = (
    (r"expense ratio|\bter\b|total expense|base ter", "expense-ratio"),
    (r"exit load", "exit-load"),
    (r"\bsip\b|systematic investment", "minimum-sip"),
    (r"lock-?\s*in|\belss\b", "lock-in"),
    (r"risk-?o-?meter|riskometer", "riskometer"),
    (r"benchmark", "benchmark"),
    (r"capital gain|account statement|\bcas\b", "statement"),
    (r"investment objective", "objective"),
    (r"\bfees?\b", "fees"),
    (r"\btax\b", "tax"),
)

_FEE = re.compile(
    r"expense ratio|\bter\b|exit load|benchmark|risk-?o-?meter|riskometer|\bsip\b|lock-?\s*in",
    re.IGNORECASE,
)
_OTHER_FUND = re.compile(r"\bSBI\s+[A-Za-z0-9&][^|\n]{0,80}?Fund\b", re.IGNORECASE)
_TER_PAIR = re.compile(r"\bTER\b\s+(\d+\.\d+)\s+(\d+\.\d+)", re.IGNORECASE)
_SCHEME_SLUGS = {
    "SBI Bluechip Fund": "bluechip",
    "SBI Long Term Equity Fund": "long-term-equity",
    "SBI Flexicap Fund": "flexicap",
    "SBI Small Cap Fund": "smallcap",
    "All schemes": "all-schemes",
}


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    source_url: str
    doc_title: str
    doc_type: str
    scheme: str
    scheme_category: str
    section: str
    page_no: int
    as_of_date: str
    text: str
    char_len: int
    token_len: int


@dataclass
class _Unit:
    scheme: str
    scheme_category: str
    scheme_slug: str
    section: str
    page_no: int
    prose: list[str] = field(default_factory=list)
    rows: list[str] = field(default_factory=list)
    row_safe: bool = False


def get_tokenizer():
    global _TOKENIZER
    if _TOKENIZER is None:
        from transformers import AutoTokenizer

        _TOKENIZER = AutoTokenizer.from_pretrained(EMBEDDING_MODEL)
    return _TOKENIZER


def token_len(text: str, tok=None) -> int:
    tokenizer = tok or get_tokenizer()
    return len(tokenizer.encode(text, add_special_tokens=True))


def assert_within_limit(text: str, tok, chunk_id: str) -> int:
    count = len(tok.encode(text, add_special_tokens=True))
    if count > TOKENIZER_TOKEN_LIMIT:
        raise ValueError(f"{chunk_id} has {count} tokens")
    return count


def split_document(
    doc: Doc,
    blocks: list[Block],
    profile: DocProfile | None = None,
) -> tuple[list[Chunk], list[str]]:
    rules = profile or profile_for(doc.doc_type)
    tokenizer = get_tokenizer()
    units = _group(doc, blocks, rules)
    chunks: list[Chunk] = []
    unsplittable: list[str] = []
    counters: dict[tuple[str, str], int] = {}
    for unit in units:
        for text, section in _render(unit, rules):
            pieces, failed = _fit(text, unit, rules, tokenizer)
            slug = section_slug(section)
            if failed:
                unsplittable.append(f"{doc.doc_id} {unit.scheme} {section}")
            for piece in pieces:
                count = token_len(piece, tokenizer)
                if count > TOKENIZER_TOKEN_LIMIT:
                    unsplittable.append(f"{doc.doc_id} {unit.scheme} {section}")
                    continue
                key = (unit.scheme_slug, slug)
                seq = counters.get(key, 0)
                counters[key] = seq + 1
                chunk_id = f"{doc.doc_id}__{unit.scheme_slug}__{slug}__{seq:03d}"
                assert_within_limit(piece, tokenizer, chunk_id)
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        doc_id=doc.doc_id,
                        source_url=doc.source_url,
                        doc_title=doc.title,
                        doc_type=doc.doc_type,
                        scheme=unit.scheme,
                        scheme_category=unit.scheme_category,
                        section=section,
                        page_no=unit.page_no,
                        as_of_date=doc.as_of_date,
                        text=piece,
                        char_len=len(piece),
                        token_len=count,
                    )
                )
    return chunks, unsplittable


def _group(doc: Doc, blocks: list[Block], profile: DocProfile) -> list[_Unit]:
    multi = doc.doc_type == "factsheet" and doc.scheme in {"", "All schemes"}
    current = None if multi else _fixed_scheme(doc)
    page_schemes = _page_schemes(blocks) if multi else {}
    units: list[_Unit] = []
    prose: list[str] = []
    rows: list[str] = []
    section = "Overview"
    page_no = 1
    label = ""

    def active_scheme() -> tuple[str, str, str] | None:
        if current is not None:
            return current
        if multi and doc.doc_type == "factsheet":
            return None
        return ("All schemes", doc.scheme_category, "all-schemes")

    def flush() -> None:
        nonlocal prose, rows
        scheme = active_scheme()
        if scheme and (prose or rows):
            units.append(
                _Unit(
                    scheme=scheme[0],
                    scheme_category=scheme[1],
                    scheme_slug=scheme[2],
                    section=section,
                    page_no=page_no,
                    prose=prose,
                    rows=rows,
                    row_safe=bool(rows),
                )
            )
        prose = []
        rows = []

    for block in blocks:
        text = block.text.strip()
        if not text:
            continue
        detected = _single_scheme(text) if len(text) <= 240 or block.kind == "table_row" else None
        if multi and block.kind in {"heading", "para"} and len(text) <= 180:
            if detected:
                flush()
                current = detected
                section = _clean_title(text)
                page_no = block.page_no
            elif _OTHER_FUND.search(text):
                flush()
                current = None
        page_scheme = page_schemes.get(block.page_no)
        if page_scheme and (detected is None or detected[2] == page_scheme[2]):
            if current != page_scheme:
                flush()
                current = page_scheme
        scheme_for_row = detected if block.kind == "table_row" else None
        if scheme_for_row and current != scheme_for_row:
            flush()
            current_for_row = scheme_for_row
        else:
            current_for_row = active_scheme()
        if current_for_row is None:
            continue
        if profile.split_on == "table_row" and block.kind == "table_row":
            flush()
            body = _enrich_fee(_with_label(label, text))
            units.append(
                _Unit(
                    scheme=current_for_row[0],
                    scheme_category=current_for_row[1],
                    scheme_slug=current_for_row[2],
                    section=_section_name(body),
                    page_no=block.page_no,
                    rows=[body],
                    row_safe=True,
                )
            )
            continue
        if profile.split_on == "scheme_section" and block.kind == "table_row" and _FEE.search(text):
            flush()
            body = _enrich_fee(_with_label(label, text))
            units.append(
                _Unit(
                    scheme=current_for_row[0],
                    scheme_category=current_for_row[1],
                    scheme_slug=current_for_row[2],
                    section=_section_name(body),
                    page_no=block.page_no,
                    rows=[body],
                    row_safe=True,
                )
            )
            continue
        if _new_section(profile, block):
            flush()
            section = _clean_title(text) if block.kind == "heading" else section
            page_no = block.page_no
        if block.kind in {"heading", "para"} and len(text) <= 220 and _FEE.search(text):
            label = text
        if not prose and not rows:
            page_no = block.page_no
        if block.kind == "table_row":
            if prose:
                flush()
                section = _section_name(text)
            rows.append(_enrich_fee(text))
        else:
            if rows:
                flush()
            prose.append(_enrich_fee(text))
    flush()
    return units


def _render(unit: _Unit, profile: DocProfile) -> list[tuple[str, str]]:
    crumb = _breadcrumb(unit.scheme, unit.scheme_category, unit.section)
    pieces: list[tuple[str, str]] = []
    if unit.prose:
        body = "\n".join(unit.prose)
        for part in _window(body, profile.target_chars, profile.overlap_chars):
            pieces.append((f"{crumb}\n{part}", unit.section))
    if unit.rows:
        for group in _pack_rows(unit.rows, profile.target_chars):
            pieces.append((f"{crumb}\n" + "\n".join(group), unit.section))
    return pieces


def _fit(text: str, unit: _Unit, profile: DocProfile, tok) -> tuple[list[str], bool]:
    if token_len(text, tok) <= TOKENIZER_TOKEN_LIMIT:
        return [text], False
    if unit.row_safe:
        rows = text.split("\n")
        crumb = rows[0]
        body_rows = [row for row in rows[1:] if row.strip()]
        if len(body_rows) == 1 and (
            len(body_rows[0]) > 700 or body_rows[0].count("|") > 6
        ) and token_len(text, tok) > TOKENIZER_TOKEN_LIMIT:
            return _split_prose(text, tok), False
        groups = _pack_token_rows(crumb, body_rows, tok)
        failed = len(groups) < len([row for row in body_rows if row.strip()]) and any(
            token_len(f"{crumb}\n{row}", tok) > TOKENIZER_TOKEN_LIMIT for row in body_rows
        )
        kept = [group for group in groups if token_len(group, tok) <= TOKENIZER_TOKEN_LIMIT]
        dropped = len(groups) != len(kept)
        return kept, failed or dropped
    return _split_prose(text, tok), False


def _split_prose(text: str, tok) -> list[str]:
    if token_len(text, tok) <= TOKENIZER_TOKEN_LIMIT:
        return [text] if text.strip() else []
    lines = text.split("\n", 1)
    crumb = lines[0] if len(lines) == 2 else ""
    body = lines[1] if len(lines) == 2 else text
    budget = TOKENIZER_TOKEN_LIMIT - (token_len(crumb + "\n", tok) if crumb else 0)
    budget = max(budget, 32)
    parts = _split_to_budget(body, tok, budget)
    rendered = [f"{crumb}\n{part}".strip() if crumb else part for part in parts if part.strip()]
    checked: list[str] = []
    for part in rendered:
        if token_len(part, tok) <= TOKENIZER_TOKEN_LIMIT:
            checked.append(part)
        else:
            checked.extend(_split_to_budget(part, tok, TOKENIZER_TOKEN_LIMIT))
    return [part for part in checked if part.strip() and token_len(part, tok) <= TOKENIZER_TOKEN_LIMIT]


def _split_to_budget(text: str, tok, budget: int) -> list[str]:
    if not text.strip():
        return []
    if token_len(text, tok) <= budget:
        return [text.strip()]
    cut = _boundary(text)
    if cut <= 0 or cut >= len(text):
        cut = _word_midpoint(text)
    if cut <= 0 or cut >= len(text):
        return [text.strip()]
    left = _split_to_budget(text[:cut].strip(), tok, budget)
    right = _split_to_budget(text[cut:].strip(), tok, budget)
    return left + right


def _boundary(text: str) -> int:
    start = int(len(text) * 0.45)
    end = int(len(text) * 0.85)
    region = text[start:end]
    cut = -1
    for match in re.finditer(r"[.!?]\s+", region):
        cut = start + match.end()
    if cut > 0:
        return cut
    space = text.rfind(" ", start, end)
    return space if space > 0 else -1


def _word_midpoint(text: str) -> int:
    mid = len(text) // 2
    space = text.rfind(" ", 0, mid)
    return space if space > 0 else mid


def _pack_rows(rows: list[str], target: int) -> list[list[str]]:
    groups: list[list[str]] = []
    current: list[str] = []
    size = 0
    for row in rows:
        if current and size + len(row) + 1 > target:
            groups.append(current)
            current = []
            size = 0
        current.append(row)
        size += len(row) + 1
    if current:
        groups.append(current)
    return groups


def _pack_token_rows(crumb: str, rows: list[str], tok) -> list[str]:
    groups: list[str] = []
    current: list[str] = []
    for row in rows:
        trial = "\n".join([crumb, *current, row])
        if current and token_len(trial, tok) > TOKENIZER_TOKEN_LIMIT:
            groups.append("\n".join([crumb, *current]))
            current = [row]
        else:
            current.append(row)
    if current:
        groups.append("\n".join([crumb, *current]))
    return groups


def _window(text: str, target: int, overlap: int) -> list[str]:
    text = text.strip()
    if len(text) <= target or target <= 0:
        return [text] if text else []
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + target, len(text))
        if end < len(text):
            snap_from = start + int(target * 0.85)
            region = text[snap_from:end]
            cut = None
            for match in re.finditer(r"[.!?]\s+", region):
                cut = snap_from + match.end()
            if cut and cut > start:
                end = cut
            else:
                space = text.rfind(" ", snap_from, end)
                if space > start:
                    end = space
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        next_start = max(end - overlap, start + 1) if overlap else end
        if next_start <= start:
            next_start = end
        start = next_start
    return pieces


def _fixed_scheme(doc: Doc) -> tuple[str, str, str]:
    detected = _detect_scheme(doc.scheme) or _detect_scheme(doc.title)
    if detected:
        category = doc.scheme_category or detected[1]
        return detected[0], category, detected[2]
    slug = _SCHEME_SLUGS.get(doc.scheme, section_slug(doc.scheme or "general"))
    return doc.scheme or "All schemes", doc.scheme_category, slug


def _page_schemes(blocks: list[Block]) -> dict[int, tuple[str, str, str]]:
    by_page: dict[int, list[Block]] = {}
    for block in blocks:
        by_page.setdefault(block.page_no, []).append(block)
    assigned: dict[int, tuple[str, str, str]] = {}
    for page_no, page_blocks in by_page.items():
        slugs: set[str] = set()
        chosen: tuple[str, str, str] | None = None
        for block in page_blocks:
            if len(block.text) > 500:
                continue
            matches = _matching_schemes(block.text)
            if len(matches) == 1:
                slugs.add(matches[0][2])
                chosen = matches[0]
        if len(slugs) == 1 and chosen is not None:
            assigned[page_no] = chosen
    return assigned


def _detect_scheme(text: str) -> tuple[str, str, str] | None:
    found = _matching_schemes(text)
    if len(found) == 1:
        return found[0]
    return None


def _single_scheme(text: str) -> tuple[str, str, str] | None:
    return _detect_scheme(text)


def _matching_schemes(text: str) -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for pattern, name, category, slug in _SCHEMES:
        if pattern.search(text) and slug not in seen:
            seen.add(slug)
            found.append((name, category, slug))
    return found


def _enrich_fee(text: str) -> str:
    match = _TER_PAIR.search(text)
    if not match:
        return text
    regular, direct = match.group(1), match.group(2)
    labelled = (
        f"Expense ratio (Regular Plan): {regular}%\n"
        f"Expense ratio (Direct Plan): {direct}%\n"
        f"TER | {regular} | {direct}"
    )
    if "Expense ratio (Regular Plan)" in text:
        return text
    return f"{text}\n{labelled}"


def _new_section(profile: DocProfile, block: Block) -> bool:
    if block.kind != "heading":
        return False
    if profile.split_on in {"heading", "heading_or_list", "scheme_section"}:
        return block.level <= 3 or block.level == 0
    return False


def _breadcrumb(scheme: str, category: str, section: str) -> str:
    if category and category.lower() not in scheme.lower():
        head = f"{scheme} ({category})"
    else:
        head = scheme or "SBI Mutual Fund"
    return f"{head} | {section}"


def _section_name(text: str) -> str:
    slug = section_slug(text)
    titles = {
        "expense-ratio": "Expense ratio",
        "exit-load": "Exit load",
        "minimum-sip": "Minimum SIP",
        "lock-in": "Lock-in",
        "riskometer": "Riskometer",
        "benchmark": "Benchmark",
        "statement": "Statements",
        "objective": "Investment objective",
        "fees": "Fees and expenses",
        "tax": "Tax",
    }
    return titles.get(slug, _clean_title(text))


def section_slug(title: str) -> str:
    for pattern, slug in _SECTION_RULES:
        if re.search(pattern, title, re.IGNORECASE):
            return slug
    cleaned = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return cleaned[:48] or "section"


def _clean_title(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()[:80] or "Section"


def _with_label(label: str, text: str) -> str:
    if label and label not in text:
        return f"{label}\n{text}"
    return text
