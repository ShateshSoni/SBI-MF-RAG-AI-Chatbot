"""The chat module must not run the pipeline on import."""

from __future__ import annotations

import importlib

import pytest

from src.app import DISCLAIMER, EXAMPLES


def test_disclaimer_and_examples() -> None:
    assert DISCLAIMER == "Facts-only. No investment advice."
    assert len(EXAMPLES) == 3


def test_import_does_not_call_the_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("pipeline called at import")

    monkeypatch.setattr("src.query.pipeline.answer_question", boom)
    importlib.reload(importlib.import_module("src.app"))
