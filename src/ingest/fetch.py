"""Allowlist-enforcing downloader with size cap, retries, and sha256 skip."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from src.ingest.errors import FetchError
from src.ingest.manifest import Doc

logger = logging.getLogger(__name__)

MAX_BYTES = 25 * 1024 * 1024
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 SBI-MF-FAQ/0.1"
)
_BACKOFFS = (1, 4, 16)
_RETRY_STATUS = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class FetchResult:
    path: Path
    sha256: str
    changed: bool


def download(
    doc: Doc,
    allowed_hosts: set[str],
    raw_dir: Path,
    cache_path: Path,
    session: requests.Session | None = None,
) -> FetchResult:
    host = (urlparse(doc.source_url).hostname or "").lower()
    if host not in {item.lower() for item in allowed_hosts}:
        raise FetchError(f"host not on allowlist: {host}")
    if not doc.source_url.startswith("https://"):
        raise FetchError(f"refusing non-https URL for {doc.doc_id}")
    raw_dir.mkdir(parents=True, exist_ok=True)
    cache = _read_cache(cache_path)
    cached_hash = cache.get(doc.doc_id, "")
    existing = _existing_file(raw_dir, doc.doc_id)
    if existing is not None and cached_hash:
        digest = _sha256(existing)
        if digest == cached_hash:
            logger.info("download cache hit for %s", doc.doc_id)
            return FetchResult(existing, digest, changed=False)
    content, content_type = _fetch_bytes(doc, session or requests.Session())
    suffix = _suffix(doc.source_url, content_type, content)
    if suffix == ".pdf" and not content.startswith(b"%PDF"):
        raise FetchError(f"{doc.doc_id}: expected a PDF but the body is not a PDF")
    path = raw_dir / f"{doc.doc_id}{suffix}"
    path.write_bytes(content)
    digest = _sha256(path)
    cache[doc.doc_id] = digest
    _write_cache(cache_path, cache)
    changed = digest != cached_hash
    logger.info("downloaded %s bytes=%s changed=%s", doc.doc_id, len(content), changed)
    return FetchResult(path, digest, changed=changed)


def _existing_file(raw_dir: Path, doc_id: str) -> Path | None:
    matches = sorted(raw_dir.glob(f"{doc_id}.*"))
    return matches[0] if matches else None


def _fetch_bytes(doc: Doc, session: requests.Session) -> tuple[bytes, str]:
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    last_error: Exception | None = None
    for attempt in range(4):
        if attempt:
            time.sleep(_BACKOFFS[attempt - 1])
        try:
            response = session.get(doc.source_url, headers=headers, timeout=(15, 180), stream=True)
            if response.status_code in _RETRY_STATUS:
                last_error = FetchError(f"{doc.doc_id}: HTTP {response.status_code}")
                response.close()
                continue
            if response.status_code != 200:
                response.close()
                raise FetchError(f"{doc.doc_id}: HTTP {response.status_code}")
            length = response.headers.get("Content-Length")
            if length and length.isdigit() and int(length) > MAX_BYTES:
                response.close()
                raise FetchError(f"{doc.doc_id}: remote file exceeds 25 MB")
            chunks: list[bytes] = []
            total = 0
            for piece in response.iter_content(chunk_size=1024 * 256):
                if not piece:
                    continue
                total += len(piece)
                if total > MAX_BYTES:
                    response.close()
                    raise FetchError(f"{doc.doc_id}: download exceeded 25 MB")
                chunks.append(piece)
            content_type = response.headers.get("Content-Type", "")
            response.close()
            return b"".join(chunks), content_type
        except FetchError:
            raise
        except (requests.RequestException, TimeoutError) as exc:
            last_error = exc
            logger.warning("download attempt %s failed for %s", attempt + 1, doc.doc_id)
    raise FetchError(f"{doc.doc_id}: download failed after retries") from last_error


def _suffix(url: str, content_type: str, content: bytes) -> str:
    lowered = url.lower().split("?", 1)[0]
    if content.startswith(b"%PDF") or "pdf" in content_type.lower() or lowered.endswith(".pdf"):
        return ".pdf"
    return ".html"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_cache(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(key): str(value) for key, value in data.items()}


def _write_cache(path: Path, cache: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")
