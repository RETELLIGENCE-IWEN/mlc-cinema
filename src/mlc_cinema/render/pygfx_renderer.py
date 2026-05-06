"""Stub for a future hardware-accelerated pygfx renderer.

M0 ships a Qt-painted placeholder in ``viewport.py``. This module is a
deliberate skeleton: it documents the contract the eventual pygfx
backend must honour and provides a single ``is_available()`` helper so
the UI can query support without paying the import cost up front.

A future commit can flesh out ``PygfxRenderer`` and have ``MLCViewport``
delegate to it when ``is_available()`` returns ``True``.
"""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)


def is_available() -> bool:
    """Return True if pygfx + wgpu can be imported and initialized."""

    try:
        import pygfx  # noqa: F401
        import wgpu  # noqa: F401
    except Exception as exc:  # pragma: no cover — environment-dependent
        _log.debug("pygfx/wgpu unavailable: %s", exc)
        return False
    return True


class PygfxRenderer:  # pragma: no cover — not implemented in M0
    """Reserved class name for the future hardware-accelerated backend.

    The M1 implementation is expected to expose the same ``set_entities``,
    ``set_scene_frame``, and ``reset_trails`` methods as
    ``MLCViewport`` so it can be substituted without UI churn.
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "PygfxRenderer is not implemented in M0; the Qt-painted "
            "MLCViewport is used instead."
        )
