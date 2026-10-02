"""Manifest validation, host allowlist, and the locked 24-URL corpus."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ingest.manifest import allowed_hosts, doc_urls, load_manifest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "config" / "sources.csv"


def _write(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def test_real_manifest_shape() -> None:
    docs = load_manifest(SOURCES)
    assert len(docs) == 24
    assert sum(doc.ingest for doc in docs) == 15
    hosts = allowed_hosts(docs)
    assert hosts
    assert not any("caalley.com" in host for host in hosts)
    assert not any("camsonline.com" in host for host in hosts)
    assert all(doc.source_url.startswith("https://") for doc in docs)
    mirror = next(doc for doc in docs if doc.doc_id == "sebi_riskometer_mirror")
    assert mirror.tier == 5
    assert mirror.ingest is False
    assert doc_urls(docs, "sbimf_ter_notice_2025_05_30").startswith("https://www.sbimf.com/")


def test_duplicate_doc_id(tmp_path: Path) -> None:
    path = tmp_path / "sources.csv"
    row = "a,Title,factsheet,All schemes,,https://example.com/a,2026-01-01,1,yes,,,"
    _write(path, "doc_id,title,doc_type,scheme,scheme_category,source_url,as_of_date,tier,ingest,local_filename,fetched_at,notes\n" + row + "\n" + row + "\n")
    with pytest.raises(ValueError, match="duplicate"):
        load_manifest(path)


def test_rejects_bad_rows(tmp_path: Path) -> None:
    header = "doc_id,title,doc_type,scheme,scheme_category,source_url,as_of_date,tier,ingest,local_filename,fetched_at,notes\n"
    cases = [
        "a,Title,factsheet,S,,http://example.com/a,2026-01-01,1,yes,,,\n",
        "a,Title,factsheet,S,,https://example.com/a,2026-01-01,9,yes,,,\n",
        "a,Title,factsheet,S,,https://example.com/a,30-05-2025,1,yes,,,\n",
        "a,Title,,S,,https://example.com/a,2026-01-01,1,yes,,,\n",
    ]
    for body in cases:
        path = tmp_path / "bad.csv"
        _write(path, header + body)
        with pytest.raises(ValueError):
            load_manifest(path)
