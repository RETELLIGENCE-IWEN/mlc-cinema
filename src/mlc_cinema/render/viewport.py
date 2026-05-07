"""Viewport dispatcher.

Returns a real-3D :class:`PygfxViewport` when pygfx + a Qt-capable
wgpu canvas are available; otherwise returns the Qt-painted
:class:`FallbackViewport`. The two backends share the same M1.0
public interface so the rest of the app doesn't care which one
is in use.

The dispatcher always logs at ``INFO`` which backend it chose and
*why* — important for diagnosing "why am I seeing the 2D fallback?"
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QWidget

_log = logging.getLogger(__name__)


def create_viewport(parent: QWidget | None = None) -> QWidget:
    """Construct the best-available viewport for ``parent``.

    Falls back to the Qt-painted backend if pygfx isn't importable,
    its ``is_available()`` check fails, or its constructor raises
    (e.g. no compatible GPU adapter).
    """

    reason: str | None = None
    try:
        from mlc_cinema.render import pygfx_renderer
    except Exception as exc:
        reason = f"pygfx_renderer import failed: {exc!r}"
    else:
        # Determine why is_available() said no, if it did.
        try:
            import pygfx  # noqa: F401
        except Exception as exc:
            reason = reason or f"pygfx import failed: {exc!r}"

        try:
            from rendercanvas.qt import QRenderWidget  # noqa: F401
        except Exception:
            try:
                from wgpu.gui.qt import WgpuCanvas  # noqa: F401
            except Exception:
                try:
                    from wgpu.gui.auto import WgpuCanvas  # noqa: F401
                except Exception as exc:
                    reason = reason or (
                        f"Qt-capable canvas not found: tried "
                        f"rendercanvas.qt and wgpu.gui — {exc!r}"
                    )

        if pygfx_renderer.is_available():
            try:
                viewport = pygfx_renderer.PygfxViewport(parent=parent)
            except Exception as exc:
                _log.warning(
                    "Pygfx viewport instantiation failed: %r — "
                    "falling back to the Qt-painted viewport",
                    exc,
                )
            else:
                _log.info(
                    "Using pygfx 3D viewport (backend: %s)",
                    pygfx_renderer.WgpuCanvas.__module__
                    if pygfx_renderer.WgpuCanvas is not None
                    else "?",
                )
                return viewport

    from mlc_cinema.render.fallback_viewport import FallbackViewport

    _log.warning(
        "Using Qt-painted FALLBACK viewport (no real 3D). Reason: %s",
        reason or "pygfx_renderer.is_available() returned False",
    )
    return FallbackViewport(parent=parent)


# Backwards-compatible alias. Existing imports of ``MLCViewport``
# resolve to the dispatcher result; instantiate via ``create_viewport``.
MLCViewport = create_viewport


__all__ = ["MLCViewport", "create_viewport"]
