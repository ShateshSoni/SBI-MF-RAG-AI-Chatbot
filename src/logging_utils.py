"""Structured JSON logging with secret and PII redaction."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

_REDACTIONS = (
    re.compile(r"gsk_[A-Za-z0-9]+"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    re.compile(r"\b\d{10}\b"),
)


def redact(text: str) -> str:
    cleaned = text
    for pattern in _REDACTIONS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(log_path: Path | None = None) -> Path:
    path = log_path or Path("logs/app.log")
    path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [handler for handler in root.handlers if not getattr(handler, "mf_faq", False)]
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.mf_faq = True  # type: ignore[attr-defined]
    handler.addFilter(RedactionFilter())
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    return path
