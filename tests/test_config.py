"""Settings defaults, missing-key failure, and directory creation."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import COLLECTION, ConfigurationError, Settings


def test_defaults() -> None:
    settings = Settings()
    assert settings.top_k == 5
    assert settings.sim_floor == 0.35
    assert settings.tokenizer_token_limit == 250
    assert settings.chunk_target_chars == 900
    assert settings.chunk_overlap_chars == 120
    assert settings.max_query_chars == 500
    assert settings.chroma_collection == COLLECTION
    assert settings.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
    assert settings.llm_temperature == 0.0
    # Must clear a reasoning model's deliberation plus a 3-sentence answer with a
    # long source URL, or the citation is cut off and the answer is discarded.
    assert settings.llm_max_tokens >= 1024


def test_settings_are_frozen() -> None:
    settings = Settings()
    with pytest.raises(Exception):
        settings.top_k = 3  # type: ignore[misc]


def test_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ConfigurationError):
        _ = Settings().api_key


def test_from_env_reads_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_MODEL", "llama-3.1-8b-instant")
    settings = Settings.from_env()
    assert settings.llm_model == "llama-3.1-8b-instant"


def test_ensure_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    Settings().ensure_dirs()
    for relative in ("data", "data/raw", "data/raw_text", "data/cache", "artifacts", "logs"):
        assert (tmp_path / relative).is_dir()
