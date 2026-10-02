"""Groq retry policy: 429 and timeouts retry, 401 does not, and the key is never logged."""

from __future__ import annotations

import logging

import pytest

from src.config import ConfigurationError, Settings
from src.query.llm import GroqClient, LLMAuthError, LLMTruncated, LLMUnavailable


def _client(monkeypatch: pytest.MonkeyPatch) -> GroqClient:
    monkeypatch.setenv("GROQ_API_KEY", "gsk_testkeyvalue")
    monkeypatch.setattr("src.query.llm.time.sleep", lambda *_args, **_kwargs: None)
    return GroqClient(Settings())


def test_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ConfigurationError):
        GroqClient(Settings())


def test_retries_429_then_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    calls = {"n": 0}

    def fail(_messages):
        calls["n"] += 1
        raise LLMUnavailable("429")

    monkeypatch.setattr(client, "_complete_once", fail)
    with pytest.raises(LLMUnavailable):
        client.complete([{"role": "user", "content": "hello"}])
    assert calls["n"] == 3


def test_401_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    calls = {"n": 0}

    def fail(_messages):
        calls["n"] += 1
        raise LLMAuthError("unauthorized")

    monkeypatch.setattr(client, "_complete_once", fail)
    with pytest.raises(LLMAuthError):
        client.complete([{"role": "user", "content": "hello"}])
    assert calls["n"] == 1


def test_failure_log_omits_the_key(monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    client = _client(monkeypatch)

    def fail(_messages):
        raise LLMUnavailable("429")

    monkeypatch.setattr(client, "_complete_once", fail)
    with caplog.at_level(logging.INFO):
        with pytest.raises(LLMUnavailable):
            client.complete([{"role": "user", "content": "hello"}])
    assert "gsk_testkeyvalue" not in caplog.text


def _message(content: str, finish_reason: str = "stop", reasoning: str = ""):
    class _Msg:
        def __init__(self) -> None:
            self.content = content
            self.reasoning = reasoning

    class _Choice:
        def __init__(self) -> None:
            self.message = _Msg()
            self.finish_reason = finish_reason

    class _Response:
        def __init__(self) -> None:
            self.choices = [_Choice()]

    return _Response()


def test_hit_the_token_cap_is_never_returned_as_an_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    monkeypatch.setattr(
        client._client.chat.completions,
        "create",
        lambda **_kwargs: _message("The exit load is 0.10% if redeemed within", "length", "thinking..."),
    )
    with pytest.raises(LLMTruncated):
        client.complete([{"role": "user", "content": "exit load"}])


def test_empty_body_is_never_returned_as_an_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    monkeypatch.setattr(
        client._client.chat.completions,
        "create",
        lambda **_kwargs: _message("", "stop", "spent the whole budget reasoning"),
    )
    with pytest.raises(LLMTruncated):
        client.complete([{"role": "user", "content": "exit load"}])


def test_each_retry_buys_a_larger_token_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    seen: list[int] = []

    def create(**kwargs):
        seen.append(kwargs["max_tokens"])
        return _message("", "length", "...")

    monkeypatch.setattr(client._client.chat.completions, "create", create)
    monkeypatch.setattr("src.query.llm.time.sleep", lambda *_a, **_k: None)
    with pytest.raises(LLMTruncated):
        client.complete([{"role": "user", "content": "exit load"}])
    assert seen == sorted(seen) and len(set(seen)) == 3
    assert seen[0] == client.settings.llm_max_tokens


def test_a_complete_answer_is_returned_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    text = "Exit load is 0.10% within 30 days. Source: https://x.test/a.pdf"
    monkeypatch.setattr(
        client._client.chat.completions,
        "create",
        lambda **_kwargs: _message(text, "stop", "reasoning"),
    )
    assert client.complete([{"role": "user", "content": "exit load"}]) == text
