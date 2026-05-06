"""Rendering layer for mlc-cinema.

The renderer consumes ``SceneEntity`` and ``SceneFrame`` only; it does
not import from ``mlc_cinema.mlc`` directly. ``MLCViewport`` is the
public widget — it currently uses a Qt-painted side-view placeholder
and exposes a stable interface so a hardware-accelerated backend
(``pygfx_renderer``) can drop in later without UI changes.
"""

from mlc_cinema.render.viewport import MLCViewport

__all__ = ["MLCViewport"]
