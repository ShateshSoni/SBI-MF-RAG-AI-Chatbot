"""Offline ingestion entry point: load, parse, chunk, and optionally embed."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import (  # noqa: E402
    ARTIFACTS_DIR,
    EMBED_CACHE,
    HASH_CACHE,
    RAW_DIR,
    RAW_TEXT_DIR,
    SOURCES_CSV,
    Settings,
)
from src.ingest.chunk import split_document  # noqa: E402
from src.ingest.coverage import coverage_failures, topic_support  # noqa: E402
from src.ingest.dump import write_chunks  # noqa: E402
from src.ingest.errors import FetchError, ParseError  # noqa: E402
from src.ingest.fetch import download  # noqa: E402
from src.ingest.manifest import allowed_hosts, load_manifest  # noqa: E402
from src.ingest.parse_html import parse_html  # noqa: E402
from src.ingest.parse_pdf import parse_pdf  # noqa: E402
from src.ingest.profiles import profile_for  # noqa: E402
from src.ingest.report import write_chunk_report, write_parse_report  # noqa: E402
from src.ingest.types import Block  # noqa: E402
from src.logging_utils import setup_logging  # noqa: E402

import logging  # noqa: E402

logger = logging.getLogger(__name__)

_RATIONALE = """
Factsheets are grouped by scheme section, and fee rows (TER, exit load, SIP, benchmark, riskometer, lock-in) stay one chunk per row so a label is not separated from its value. SID, KIM, and the tax reckoner split on headings, then window prose at 900 characters with 120 characters of overlap, snapping the cut to a sentence boundary in the final 15% of the window. Guides and regulator pages keep a heading together with the list items that follow it. Table rows are never split mid-row. Every chunk is measured with the MiniLM tokenizer and re-split, or withheld, if it would exceed 250 tokens. Multi-scheme factsheets keep only the four in-scope schemes, and each chunk carries that scheme rather than the document-level label.
""".strip()

_PROBES = (
    "SBI Bluechip Fund",
    "SBI Long Term Equity Fund",
    "SBI Flexicap Fund",
    "SBI Small Cap Fund",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load, parse, chunk, and store the SBI MF corpus.")
    parser.add_argument("--report", action="store_true", help="Write parse and chunk reports.")
    parser.add_argument("--force", action="store_true", help="Embed after the chunk review gate.")
    parser.add_argument("--probe", action="store_true", help="Run one expense-ratio probe per scheme.")
    parser.add_argument("--only", default="", help="Process a single doc_id.")
    parser.add_argument("--refresh", action="store_true", help="Re-chunk and re-embed from local files.")
    args = parser.parse_args(argv)
    probe_only = args.probe and not (args.force or args.report or args.refresh or args.only)
    if not probe_only:
        code = ingest(args)
        if code != 0:
            return code
    if args.probe:
        return probe()
    return 0


def ingest(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    settings.ensure_dirs()
    setup_logging()
    docs = load_manifest(SOURCES_CSV)
    hosts = allowed_hosts(docs)
    selected = [doc for doc in docs if doc.ingest and (not args.only or doc.doc_id == args.only)]
    if args.only and not selected:
        print(f"unknown or non-ingested doc_id: {args.only}")
        return 1
    embed_cache = _read_json(EMBED_CACHE)
    rows: list[dict[str, str]] = []
    parsed: list[tuple] = []
    flags: list[str] = []
    failures = 0
    for doc in docs:
        if not doc.ingest:
            rows.append(_row(doc, blocks="—", chars="—", pages="—", parser="—", flag="NOT_INGESTED", error="—"))
    for doc in selected:
        try:
            fetched = download(doc, hosts, RAW_DIR, HASH_CACHE)
            cached = (not args.refresh) and embed_cache.get(doc.doc_id) == fetched.sha256 and args.force
            if cached:
                logger.info("cached, skipping")
                print(f"{doc.doc_id}: cached, skipping")
                rows.append(_row(doc, blocks="cached", chars="—", pages="—", parser="cache", flag="—", error="—"))
                continue
            profile = profile_for(doc.doc_type)
            parser_name = _parser_name(profile.parser, fetched.path)
            if parser_name == "html_sections":
                blocks, meta = parse_html(fetched.path, doc)
            else:
                blocks, meta = parse_pdf(fetched.path, doc, parser=parser_name)
            text = _render_text(blocks)
            if not text.strip():
                raise ParseError(f"{doc.doc_id}: empty text")
            (RAW_TEXT_DIR / f"{doc.doc_id}.txt").write_text(text, encoding="utf-8")
            flag = meta.flag or "-"
            if meta.flag:
                flags.append(f"{doc.doc_id}: {meta.flag}")
            rows.append(
                _row(
                    doc,
                    blocks=str(len(blocks)),
                    chars=str(len(text)),
                    pages=str(meta.pages),
                    parser=meta.parser,
                    flag=flag,
                    error="—",
                )
            )
            print(
                f"{doc.doc_id}  blocks={len(blocks)} chars={len(text)} pages={meta.pages} "
                f"flag={flag} error=-"
            )
            parsed.append((doc, blocks, fetched.sha256))
        except (FetchError, ParseError, OSError, ValueError) as exc:
            failures += 1
            logger.error("ingest failed for %s", doc.doc_id)
            rows.append(_row(doc, blocks="0", chars="0", pages="0", parser="—", flag="—", error=str(exc)))
            print(f"{doc.doc_id}  blocks=0 chars=0 pages=0 flag=- error={exc}")
            stale = RAW_TEXT_DIR / f"{doc.doc_id}.txt"
            if stale.exists():
                stale.unlink()
    if not args.only:
        _prune_raw_text({doc.doc_id for doc in docs if doc.ingest})
    support = topic_support(docs, RAW_TEXT_DIR) if not args.only else {}
    if args.report or True:
        write_parse_report(rows, support, ARTIFACTS_DIR / "parse_report.md")
    if support:
        _print_coverage(support)
        gaps = coverage_failures(support)
        if gaps and not args.only:
            print("coverage gate failed: " + ", ".join(gaps))
            failures += 1
    chunks = []
    unsplittable: list[str] = []
    for doc, blocks, _sha in parsed:
        doc_chunks, bad = split_document(doc, blocks)
        chunks.extend(doc_chunks)
        unsplittable.extend(bad)
        print(f"chunked {doc.doc_id}: {len(doc_chunks)} chunks, unsplittable={len(bad)}")
    if chunks or not args.force:
        write_chunks(chunks, ARTIFACTS_DIR / "chunks.txt")
        write_chunk_report(chunks, unsplittable, flags, _RATIONALE, ARTIFACTS_DIR / "chunk_report.md")
    if failures:
        return 1
    if unsplittable:
        print("unsplittable chunks present; not embedding")
        return 1
    if not args.force:
        print("review artifacts/chunks.txt, then re-run with --force")
        return 0
    return _embed(settings, parsed, embed_cache, docs)


def _embed(settings: Settings, parsed: list[tuple], embed_cache: dict[str, str], docs) -> int:
    from src.ingest.embed import encode
    from src.ingest.store import get_store

    store = get_store(settings)
    store.assert_model_match()
    for doc, blocks, sha in parsed:
        doc_chunks, bad = split_document(doc, blocks)
        if bad:
            print(f"{doc.doc_id}: unsplittable chunks, not embedded")
            return 1
        if not doc_chunks:
            logger.info("no chunks for %s", doc.doc_id)
            continue
        vectors = encode([chunk.text for chunk in doc_chunks])
        store.delete_doc(doc.doc_id)
        store.upsert_chunks(doc_chunks, vectors)
        embed_cache[doc.doc_id] = sha
        _write_json(EMBED_CACHE, embed_cache)
        logger.info("embedded %s chunks=%s", doc.doc_id, len(doc_chunks))
        print(f"embedded {doc.doc_id}: {len(doc_chunks)}")
    version = max((doc.as_of_date for doc in docs if doc.ingest), default="")
    print(f"collection={settings.chroma_collection} count={store.count()} corpus_version={version}")
    print(store.collection.metadata)
    return 0


def probe() -> int:
    from src.ingest.embed import encode
    from src.ingest.store import get_store

    settings = Settings()
    store = get_store(settings)
    store.assert_model_match()
    print(store.collection.metadata)
    failed = False
    for scheme in _PROBES:
        question = f"expense ratio of {scheme}"
        vector = encode([question])[0]
        result = store.query(vector, top_k=3, where={"scheme": scheme})
        print(f"scheme={scheme}")
        metadatas = result["metadatas"]
        distances = result["distances"]
        if not metadatas:
            print("  NONE")
            failed = True
            continue
        for metadata, distance in zip(metadatas, distances):
            similarity = 1 - float(distance)
            chunk_id = metadata.get("chunk_id", "")
            found = metadata.get("scheme", "")
            print(f"  {similarity:.3f}  {chunk_id}  scheme={found}")
            if found != scheme:
                failed = True
    return 1 if failed else 0


def _parser_name(profile_parser: str, path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf_table" if profile_parser == "pdf_table" else "pdf_text"
    if suffix in {".html", ".htm"}:
        return "html_sections"
    return profile_parser


def _render_text(blocks: list[Block]) -> str:
    lines: list[str] = []
    page = None
    for block in blocks:
        if block.page_no != page:
            page = block.page_no
            lines.append(f"--- page {page} ---")
        lines.append(block.text)
    return "\n".join(lines).strip() + "\n"


def _row(doc, **fields: str) -> dict[str, str]:
    return {
        "doc_id": doc.doc_id,
        "tier": str(doc.tier),
        "ingest": "yes" if doc.ingest else "no",
        **fields,
    }


def _print_coverage(support: dict[str, list[str]]) -> None:
    for topic, doc_ids in support.items():
        print(f"coverage {topic}: {len(doc_ids)}")


def _prune_raw_text(valid_ids: set[str]) -> None:
    if not RAW_TEXT_DIR.exists():
        return
    for path in RAW_TEXT_DIR.glob("*.txt"):
        if path.stem not in valid_ids:
            path.unlink()


def _read_json(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {str(key): str(value) for key, value in json.loads(path.read_text(encoding="utf-8")).items()}


def _write_json(path: Path, payload: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _ = datetime.now(timezone.utc)


if __name__ == "__main__":
    sys.exit(main())
