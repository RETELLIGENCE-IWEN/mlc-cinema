"""Rendering layer for mlc-cinema.

The renderer consumes ``SceneEntity`` and ``SceneFrame`` only; it does
not import from ``mlc_cinema.mlc`` directly. The viewport widget is
backend-pluggable: ``pygfx_renderer.PygfxViewport`` for the real 3D
backend, ``fallback_viewport.FallbackViewport`` for hosts where
pygfx + wgpu are unavailable. Use :func:`create_viewport` to get the
best one.
"""

from mlc_cinema.render.viewport import MLCViewport, create_viewport

__all__ = ["MLCViewport", "create_viewport"]
