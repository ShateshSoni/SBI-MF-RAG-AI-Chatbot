"""Redaction filter drops keys, PAN, and 10-digit runs before logs are written."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from src.logging_utils import setup_logging


def test_redaction_filter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    setup_logging()
    logging.getLogger("mf.test").info(
        "leak gsk_abcDEF123 sk-abcdefghijklmnopqrstuvwxyz PAN ABCDE1234F phone 9876543210"
    )
    for handler in logging.getLogger().handlers:
        handler.flush()
    text = (tmp_path / "logs" / "app.log").read_text(encoding="utf-8")
    assert "gsk_abcDEF123" not in text
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in text
    assert "ABCDE1234F" not in text
    assert "9876543210" not in text
    assert text.count("[REDACTED]") >= 4
