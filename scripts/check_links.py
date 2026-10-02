"""Entry point for corpus URL liveness checks (implemented in a later phase)."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check that ingested corpus URLs return HTTP 200.")
    parser.parse_args(argv)
    print("check_links is not implemented until phase 7.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
