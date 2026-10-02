"""PII, advice, and scheme-alias guards. PII never reaches the encoder."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

from src.query.guards import check_pii
from src.query.intent import detect_advice, detect_scheme
from src.query.pipeline import answer_question
from src.config import Settings

ROOT = Path(__file__).resolve().parent


def _rows(name: str) -> list[dict[str, str]]:
    with (ROOT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_pii_table_covers_every_class() -> None:
    rows = _rows("pii_cases.csv")
    assert len(rows) >= 20
    legitimate = [row for row in rows if row["expected_status"] == "pass"]
    assert len(legitimate) >= 5
    classes = {row["pii_type"] for row in rows if row["expected_status"] == "refused_pii"}
    for required in ("pan", "aadhaar", "mobile", "email", "account", "folio", "otp", "cvv", "demat"):
        assert required in classes


@pytest.mark.parametrize("row", _rows("pii_cases.csv"), ids=lambda row: row["qid"])
def test_pii_case(row: dict[str, str]) -> None:
    found = check_pii(row["input"])
    if row["expected_status"] == "refused_pii":
        assert found == row["pii_type"]
    else:
        assert found is None


def test_pii_false_positive_rate_on_eval_set() -> None:
    rows = _rows("eval_set.csv") + [row for row in _rows("pii_cases.csv") if row["expected_status"] == "pass"]
    blocked = [row for row in rows if check_pii(row.get("question") or row.get("input"))]
    assert len(blocked) / len(rows) <= 0.02


def test_adversarial_counts() -> None:
    rows = _rows("adversarial_set.csv")
    assert len(rows) == 20
    assert sum(row["category"] == "advice" for row in rows) == 12
    assert sum(row["category"] == "performance" for row in rows) == 5
    assert sum(row["category"] == "disguised_advice" for row in rows) == 3


@pytest.mark.parametrize("row", _rows("adversarial_set.csv"), ids=lambda row: row["qid"])
def test_adversarial_case(row: dict[str, str]) -> None:
    response = answer_question(row["question"], Settings())
    blob = response.answer + " " + " ".join(item.url for item in response.citations)
    assert re.search(row["expected_link_pattern"], blob)
    if row["expected_status"] == "factsheet_link":
        assert response.guard["answer_mode"] == "FACTSHEET_LINK"
        assert response.status == "answered"
    else:
        assert response.status == row["expected_status"]


def test_pii_does_not_encode_or_call_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("encoder or model was called")

    monkeypatch.setattr("src.query.retrieve.encode", boom)
    monkeypatch.setattr("src.ingest.embed.encode", boom)
    monkeypatch.setattr("src.query.llm.GroqClient.complete", boom)
    response = answer_question("My PAN is ABCDE1234F", Settings())
    assert response.status == "refused_pii"
    assert "ABCDE1234F" not in response.answer


def test_scheme_aliases_share_one_id_and_ignore_categories() -> None:
    assert detect_scheme("SBI Bluechip Fund expense ratio") == "SBI Bluechip Fund"
    assert detect_scheme("SBI Large Cap Fund expense ratio") == "SBI Bluechip Fund"
    assert detect_scheme("bluechip") == "SBI Bluechip Fund"
    assert detect_scheme("What is a large cap fund?") is None
    assert detect_scheme("How does ELSS work?") is None
    assert detect_scheme("What is a flexi-cap?") is None
    assert detect_scheme("Tell me about SBI Mutual Fund") is None
    assert detect_scheme("SBI Flexicap Fund exit load") == "SBI Flexicap Fund"
    assert detect_scheme("SBI Bluechip or SBI Flexicap") is None


def test_nav_today_is_out_of_corpus_without_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("encoder was called")

    monkeypatch.setattr("src.query.retrieve.encode", boom)
    response = answer_question("what is the NAV of SBI Bluechip today?", Settings())
    assert response.status == "out_of_corpus"
