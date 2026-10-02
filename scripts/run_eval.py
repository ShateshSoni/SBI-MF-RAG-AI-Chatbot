"""Entry point for the evaluation harness (implemented in a later phase)."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the SBI MF FAQ assistant.")
    parser.add_argument("--adversarial", action="store_true")
    parser.add_argument("--latency", action="store_true")
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--diff", action="store_true")
    parser.add_argument("--accept", action="store_true")
    parser.parse_args(argv)
    print("run_eval is not implemented until phase 7.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
