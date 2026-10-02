"""Stage 1 HTML parser: boilerplate-stripped blocks with a JS-render guard."""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from src.ingest.errors import ParseError
from src.ingest.manifest import Doc
from src.ingest.types import Block, ParseMeta

_DROP_TAGS = ("script", "style", "nav", "header", "footer", "aside")
_CONTROL_TAGS = ("input", "button", "select", "option", "textarea", "label")
_PLACEHOLDERS = ("Loading...", "No Records Found", "Enable JavaScript")
_HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4}


def parse_html(path: Path, doc: Doc) -> tuple[list[Block], ParseMeta]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "lxml")
    for tag_name in _DROP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()
    for tag in soup.select(".cookie, .cookies, .popup, .modal, .banner"):
        tag.decompose()
    for tag_name in _CONTROL_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    blocks = _walk(root)
    full_text = _collapse(root.get_text("\n", strip=True))
    structured = sum(len(block.text) for block in blocks)
    if structured < 500 and len(full_text) > structured + 80:
        blocks = _lines_to_blocks(full_text)
    stripped = " ".join(block.text for block in blocks)
    flag = ""
    placeholder = any(token.lower() in raw.lower() for token in _PLACEHOLDERS)
    table_shell = "<table" in raw.lower()
    if len(stripped) < 500 and (table_shell or placeholder):
        flag = "POSSIBLY_JS_RENDERED"
    if not blocks and not flag:
        raise ParseError(f"{doc.doc_id}: parser produced zero blocks")
    return blocks, ParseMeta(pages=1, parser="html_sections", flag=flag, notes="")


def _walk(root: Tag) -> list[Block]:
    blocks: list[Block] = []

    def visit(node: Tag) -> None:
        name = node.name
        if name in _HEADING_TAGS:
            text = _collapse(node.get_text(" ", strip=True))
            if text:
                blocks.append(Block(kind="heading", text=text, level=_HEADING_TAGS[name], page_no=1))
            return
        if name == "li":
            text = _collapse(node.get_text(" ", strip=True))
            if text:
                blocks.append(Block(kind="list_item", text=text, page_no=1))
            return
        if name == "table":
            for row_index, row in enumerate(node.find_all("tr"), start=1):
                cells = [_collapse(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
                cells = [cell for cell in cells if cell]
                if cells:
                    blocks.append(
                        Block(
                            kind="table_row",
                            text=" | ".join(cells),
                            page_no=1,
                            table_id="html-table",
                            row_span=1,
                            level=row_index,
                        )
                    )
            return
        if name == "p":
            text = _collapse(node.get_text(" ", strip=True))
            if text:
                blocks.append(Block(kind="para", text=text, page_no=1))
            return
        for child in node.children:
            if isinstance(child, Tag):
                visit(child)

    if isinstance(root, Tag):
        visit(root)
    return blocks


def _lines_to_blocks(text: str) -> list[Block]:
    blocks: list[Block] = []
    for line in text.split("\n"):
        cleaned = _collapse(line)
        if not cleaned:
            continue
        kind = "heading" if len(cleaned) <= 80 and cleaned.isupper() else "para"
        level = 2 if kind == "heading" else 0
        blocks.append(Block(kind=kind, text=cleaned, level=level, page_no=1))
    return blocks


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u00ad", "")).strip()
