"""``mlc-cinema-validate`` — command-line MLC v1 validator.

Runs the same parse + timeline build pipeline the GUI uses, then
prints a compact summary. Exit code is ``0`` on success, ``1`` on a
parse/timeline error. Intended for CI smoke tests against external
MLC v1 producers.
"""

from __future__ import annotations

import argparse
import logging
import sys

from mlc_cinema.config import APP_NAME, LOG_NAMESPACE
from mlc_cinema.mlc.reader import MLCParseError, read_mlc_ndjson
from mlc_cinema.mlc.summary import build_summary, format_summary
from mlc_cinema.mlc.timeline import TimelineError, build_timeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"{APP_NAME}-validate",
        description=(
            "Parse a Maneuver Log Contract v1 NDJSON file and print a "
            "summary. Exits with code 0 on success, 1 on parse error."
        ),
    )
    parser.add_argument("path", help="Path to an MLC v1 NDJSON file.")
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress logging output. Print only the summary or error.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Console entry point for ``mlc-cinema-validate``."""

    args = _build_parser().parse_args(argv)

    if not args.quiet:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        logging.getLogger(LOG_NAMESPACE).setLevel(logging.INFO)
    else:
        # Discard everything except the printed report.
        logging.basicConfig(level=logging.CRITICAL)

    try:
        parse_result = read_mlc_ndjson(args.path)
        timeline = build_timeline(parse_result)
    except MLCParseError as exc:
        print(f"MLC file: {args.path}", file=sys.stdout)
        print("Status: ERROR", file=sys.stdout)
        print(str(exc), file=sys.stdout)
        return 1
    except TimelineError as exc:
        print(f"MLC file: {args.path}", file=sys.stdout)
        print("Status: ERROR", file=sys.stdout)
        print(f"Timeline: {exc}", file=sys.stdout)
        return 1
    except OSError as exc:
        print(f"MLC file: {args.path}", file=sys.stdout)
        print("Status: ERROR", file=sys.stdout)
        print(f"OS error: {exc}", file=sys.stdout)
        return 1

    summary = build_summary(args.path, parse_result, timeline)
    sys.stdout.write(format_summary(summary, parse_result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
