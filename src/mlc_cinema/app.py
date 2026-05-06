"""Application entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from mlc_cinema.config import APP_DISPLAY_NAME, APP_NAME, LOG_NAMESPACE


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger(LOG_NAMESPACE).setLevel(logging.INFO)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="MLC-native 3D replay viewer (M0 skeleton).",
    )
    parser.add_argument(
        "log_file",
        type=str,
        nargs="?",
        default=None,
        help="Path to an MLC NDJSON file to open on startup.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the Qt exit code."""

    _configure_logging()
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))

    # Imports are deferred so that ``--help`` does not require Qt to load.
    from PySide6.QtWidgets import QApplication

    from mlc_cinema.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_DISPLAY_NAME)

    window = MainWindow()
    window.show()

    if args.log_file:
        path = Path(args.log_file)
        if not path.exists():
            logging.getLogger(LOG_NAMESPACE).error(
                "MLC log not found: %s", path
            )
        else:
            window.open_file_path(path)

    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
