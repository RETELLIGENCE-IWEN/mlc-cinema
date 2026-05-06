"""Allow ``python -m mlc_cinema`` to launch the app."""

from __future__ import annotations

import sys

from mlc_cinema.app import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
