"""Print guard results for the PII and adversarial fixtures. Inputs are not logged."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from src.query.guards import check_pii
from src.query.intent import detect_advice, detect_performance


def _read(name: str) -> list[dict[str, str]]:
    path = Path(__file__).resolve().parents[1] / "tests" / name
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _pii() -> int:
    failed = 0
    for row in _read("pii_cases.csv"):
        found = check_pii(row["input"])
        if row["expected_status"] == "refused_pii":
            ok = found == row["pii_type"]
        else:
            ok = found is None
        print(f"{'PASS' if ok else 'FAIL'} {row['qid']}")
        failed += int(not ok)
    return failed


def _adversarial() -> int:
    failed = 0
    for row in _read("adversarial_set.csv"):
        advice = detect_advice(row["question"])
        performance = detect_performance(row["question"])
        if row["expected_status"] == "refused_advice":
            ok = advice is not None
        elif row["expected_status"] == "factsheet_link":
            ok = advice is None and performance is not None
        else:
            ok = False
        print(f"{'PASS' if ok else 'FAIL'} {row['qid']}")
        failed += int(not ok)
    return failed


def main() -> int:
    failed = _pii() + _adversarial()
    print(f"failures={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
