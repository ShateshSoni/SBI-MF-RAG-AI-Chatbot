"""Downloader refuses hosts that are not on the manifest allowlist."""

from __future__ import annotations

from pathlib import Path

import pytest
import requests

from src.ingest.errors import FetchError
from src.ingest.fetch import download
from src.ingest.manifest import Doc


def _doc(url: str) -> Doc:
    return Doc(
        doc_id="evil",
        title="Evil",
        doc_type="guide",
        scheme="All schemes",
        scheme_category="",
        source_url=url,
        as_of_date="2026-01-01",
        tier=5,
        ingest=False,
        local_filename="",
        fetched_at="",
        notes="",
    )


def test_non_manifest_host_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("HTTP request issued")

    monkeypatch.setattr(requests.Session, "get", boom)
    monkeypatch.setattr(requests, "get", boom)
    with pytest.raises(FetchError, match="allowlist"):
        download(
            _doc("https://www.caalley.com/sebi24/1730809272616.pdf"),
            {"www.sbimf.com", "www.sebi.gov.in"},
            tmp_path,
            tmp_path / "hashes.json",
        )
