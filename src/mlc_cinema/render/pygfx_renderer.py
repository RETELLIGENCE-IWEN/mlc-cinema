"""Real 3D viewport backed by pygfx + wgpu.

Implements the M1.0 viewport public interface. Receives MLC-decoded
``SceneFrame`` objects only — never raw NDJSON or MLC v1 row indices.

If pygfx / wgpu cannot be imported on the host (e.g. a missing
GPU adapter, headless Linux without a Vulkan driver), :func:`is_available`
returns ``False`` and ``render.viewport`` falls back to the Qt-painted
:class:`FallbackViewport`.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

# Heavy imports are wrapped so the module still imports on hosts where
# pygfx or wgpu is broken — ``is_available()`` reports the situation
# and the dispatcher in viewport.py handles the fallback.
try:  # pragma: no cover — environment dependent
    import pygfx as gfx
except Exception:  # pragma: no cover
    gfx = None  # type: ignore[assignment]

# Canvas integration. Newer wgpu (>=0.20) split the Qt embedding out
# into the ``rendercanvas`` package; older wgpu still ships ``wgpu.gui``.
# Try the new path first, fall back to the old one.
WgpuCanvas = None  # type: ignore[assignment]
try:  # pragma: no cover — environment dependent
    from rendercanvas.qt import QRenderWidget as WgpuCanvas  # type: ignore
except Exception:  # pragma: no cover
    try:
        from wgpu.gui.qt import WgpuCanvas  # type: ignore
    except Exception:
        try:
            from wgpu.gui.auto import WgpuCanvas  # type: ignore
        except Exception:
            WgpuCanvas = None  # type: ignore[assignment]

from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from mlc_cinema.mlc.timeline import MLCTimeline
from mlc_cinema.scene.bounds import SceneBounds, compute_timeline_bounds
from mlc_cinema.scene.camera import frame_bounds, orbit_camera_position
from mlc_cinema.scene.entities import SceneEntity
from mlc_cinema.scene.scene_model import SceneFrame

_log = logging.getLogger(__name__)


# Per-platform RGB body colors (0-1 floats).
_PLATFORM_COLORS: dict[str, tuple[float, float, float]] = {
    "rocket": (0.92, 0.43, 0.43),
    "quadcopter": (0.43, 0.78, 0.92),
    "fixed_wing": (0.71, 0.92, 0.51),
}

# Fallback palette when no platform color is registered.
_FALLBACK_PALETTE: tuple[tuple[float, float, float], ...] = (
    (0.92, 0.43, 0.43),
    (0.43, 0.78, 0.92),
    (0.71, 0.92, 0.51),
    (0.92, 0.78, 0.43),
    (0.78, 0.51, 0.92),
)

# Trail buffer length per body. 8192 covers the bundled rocketsim
# 30-second / 100 Hz log; longer logs will see trails truncated to the
# most recent 8192 samples.
_TRAIL_BUFFER_LEN: int = 8192


def is_available() -> bool:
    """True if pygfx + a Qt-friendly wgpu canvas can be used."""

    return gfx is not None and WgpuCanvas is not None


class PygfxViewport(QWidget):
    """Pygfx-backed 3D viewport widget.

    Public API:

    * ``set_entities(entities)``       — once per loaded log
    * ``set_timeline(timeline)``       — once per loaded log
    * ``set_scene_frame(frame, idx)``  — every frame change
    * ``set_selected_body(body_id)``   — on selection change
    * ``reset_camera()``               — back to default orbit
    * ``frame_all()``                  — fit camera to scene bounds
    * ``reset_trails()``               — clear position history
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if not is_available():  # pragma: no cover — guard for fallback
            raise RuntimeError(
                "PygfxViewport requires pygfx and a Qt-capable wgpu backend; "
                "neither is available."
            )

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(320, 240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._canvas = WgpuCanvas(parent=self)
        layout.addWidget(self._canvas)

        self._renderer = gfx.WgpuRenderer(self._canvas)
        self._scene = gfx.Scene()

        # Background.
        bg_material = gfx.BackgroundMaterial((0.06, 0.07, 0.09))
        self._scene.add(gfx.Background(None, bg_material))

        # Lights.
        self._scene.add(gfx.AmbientLight("#ffffff", 0.55))
        sun = gfx.DirectionalLight("#ffffff", 0.85)
        try:
            sun.local.position = (60.0, 40.0, 120.0)
        except Exception:  # pragma: no cover
            pass
        self._scene.add(sun)

        # Camera (Z-up viewer frame).
        self._camera = gfx.PerspectiveCamera(
            fov=45, aspect=1.0, depth_range=(0.1, 1.0e6)
        )
        try:
            self._camera.local.up = (0.0, 0.0, 1.0)
        except Exception:  # pragma: no cover
            pass
        try:
            self._camera.local.position = (60.0, 60.0, 60.0)
            self._camera.show_pos((0.0, 0.0, 0.0))
        except Exception:  # pragma: no cover
            pass

        # Orbit controller.
        self._controller = gfx.OrbitController(
            self._camera, register_events=self._renderer
        )

        # Helper objects: ground grid + world axes.
        self._helpers_group = gfx.Group()
        self._helpers_group.add(_build_axes(length=10.0))
        for line in _build_grid_lines(half_size=100.0, step=10.0):
            self._helpers_group.add(line)
        self._scene.add(self._helpers_group)

        # Per-body state.
        self._entities: dict[int, SceneEntity] = {}
        self._body_meshes: dict[int, Any] = {}
        self._trails: dict[int, Any] = {}
        self._timeline: MLCTimeline | None = None
        self._frame_index: int = 0
        self._selected_body_id: int | None = None
        self._bounds: SceneBounds | None = None

        self._canvas.request_draw(self._draw)

    # ----- public API ----------------------------------------------------

    def set_entities(self, entities: dict[int, SceneEntity]) -> None:
        for mesh in self._body_meshes.values():
            self._safe_remove(mesh)
        for trail in self._trails.values():
            self._safe_remove(trail)
        self._body_meshes.clear()
        self._trails.clear()

        self._entities = dict(entities)
        for i, (body_id, ent) in enumerate(entities.items()):
            color = _color_for(ent.platform, i)
            mesh = _build_body_mesh(ent.platform, color)
            self._scene.add(mesh)
            self._body_meshes[body_id] = mesh

            trail = _build_empty_trail(color)
            self._scene.add(trail)
            self._trails[body_id] = trail

        self._update_selection_visuals()
        self._request_redraw()

    def set_timeline(self, timeline: MLCTimeline | None) -> None:
        self._timeline = timeline
        if timeline is not None and timeline.frames:
            self._bounds = compute_timeline_bounds(timeline)
        else:
            self._bounds = None
        self._request_redraw()

    def set_scene_frame(
        self, frame: SceneFrame, frame_index: int | None = None
    ) -> None:
        if frame_index is not None:
            self._frame_index = int(frame_index)
        for body_id, body_state in frame.body_states.items():
            mesh = self._body_meshes.get(body_id)
            if mesh is None:
                continue
            p = body_state.position
            try:
                mesh.local.position = (float(p[0]), float(p[1]), float(p[2]))
            except Exception:  # pragma: no cover
                pass
            q = body_state.quaternion
            if q is not None and len(q) == 4:
                # MLC v1 quaternion is scalar-first (w, x, y, z); pygfx
                # / pylinalg uses (x, y, z, w).
                try:
                    mesh.local.rotation = (
                        float(q[1]), float(q[2]), float(q[3]), float(q[0])
                    )
                except Exception:  # pragma: no cover
                    pass
        self._refresh_trails()
        self._request_redraw()

    def set_selected_body(self, body_id: int | None) -> None:
        self._selected_body_id = body_id
        self._update_selection_visuals()
        self._request_redraw()

    def reset_camera(self) -> None:
        self.frame_all()

    def frame_all(self) -> None:
        bounds = self._bounds
        if bounds is None and self._timeline is not None and self._timeline.frames:
            bounds = compute_timeline_bounds(self._timeline)
        if bounds is None:
            return
        state = frame_bounds(bounds)
        cam_pos = orbit_camera_position(state)
        try:
            self._camera.local.position = (
                float(cam_pos[0]), float(cam_pos[1]), float(cam_pos[2])
            )
            self._camera.show_pos(
                (float(state.target[0]), float(state.target[1]), float(state.target[2]))
            )
        except Exception:  # pragma: no cover
            _log.debug("Camera reframing failed")
        self._request_redraw()

    def reset_trails(self) -> None:
        for trail in self._trails.values():
            _zero_trail(trail)
        self._request_redraw()

    # ----- internals -----------------------------------------------------

    def _draw(self) -> None:
        try:
            self._renderer.render(self._scene, self._camera)
        except Exception:  # pragma: no cover
            _log.exception("pygfx render failed")

    def _request_redraw(self) -> None:
        try:
            self._canvas.request_draw()
        except Exception:  # pragma: no cover
            pass

    def _safe_remove(self, obj: Any) -> None:
        try:
            self._scene.remove(obj)
        except Exception:
            pass

    def _refresh_trails(self) -> None:
        if self._timeline is None:
            return
        end = max(0, min(self._frame_index + 1, len(self._timeline.frames)))
        for body_id, trail in self._trails.items():
            pts: list[np.ndarray] = []
            for i in range(end):
                state = self._timeline.frames[i].states_by_body.get(body_id)
                if state is not None:
                    pts.append(state.position)
            _write_trail(trail, pts)

    def _update_selection_visuals(self) -> None:
        for bid, mesh in self._body_meshes.items():
            scale = 1.4 if bid == self._selected_body_id else 1.0
            try:
                mesh.local.scale = (scale, scale, scale)
            except Exception:  # pragma: no cover
                pass


# ----- module-level helpers (no Qt / pygfx state retained) -------------------

def _color_for(
    platform: str | None, idx: int
) -> tuple[float, float, float]:
    norm = (platform or "").lower()
    if norm in _PLATFORM_COLORS:
        return _PLATFORM_COLORS[norm]
    return _FALLBACK_PALETTE[idx % len(_FALLBACK_PALETTE)]


def _build_body_mesh(
    platform: str | None, color: tuple[float, float, float]
) -> Any:
    material = gfx.MeshPhongMaterial(color=(*color, 1.0))
    norm = (platform or "").lower()
    if norm == "rocket":
        # Tall thin box stands along Z by default in our Z-up frame.
        geom = gfx.box_geometry(0.8, 0.8, 2.5)
    elif norm == "quadcopter":
        geom = gfx.box_geometry(1.5, 1.5, 0.3)
    elif norm == "fixed_wing":
        geom = gfx.box_geometry(2.0, 0.6, 0.25)
    else:
        geom = gfx.sphere_geometry(0.5, width_segments=16, height_segments=12)
    return gfx.Mesh(geom, material)


def _build_empty_trail(color: tuple[float, float, float]) -> Any:
    positions = np.zeros((_TRAIL_BUFFER_LEN, 3), dtype=np.float32)
    geometry = gfx.Geometry(positions=positions)
    material = gfx.LineMaterial(color=(*color, 0.85), thickness=2.0)
    return gfx.Line(geometry, material)


def _build_axes(length: float) -> Any:
    # Try the built-in helper if available; otherwise a manual three-segment line.
    try:
        return gfx.AxesHelper(size=float(length), thickness=2.0)
    except Exception:  # pragma: no cover — older pygfx
        positions = np.array(
            [
                [0, 0, 0], [length, 0, 0],
                [0, 0, 0], [0, length, 0],
                [0, 0, 0], [0, 0, length],
            ],
            dtype=np.float32,
        )
        colors = np.array(
            [
                [1.0, 0.30, 0.30, 1.0], [1.0, 0.30, 0.30, 1.0],
                [0.30, 1.0, 0.40, 1.0], [0.30, 1.0, 0.40, 1.0],
                [0.40, 0.60, 1.0, 1.0], [0.40, 0.60, 1.0, 1.0],
            ],
            dtype=np.float32,
        )
        geometry = gfx.Geometry(positions=positions, colors=colors)
        try:
            material = gfx.LineMaterial(thickness=2.0, color_mode="vertex")
        except Exception:
            material = gfx.LineMaterial(thickness=2.0)
        return gfx.Line(geometry, material)


def _build_grid_lines(half_size: float, step: float) -> list[Any]:
    """Build the ground grid as one Line object per grid line."""

    lines: list[Any] = []
    n = int(math.floor(half_size / step))
    color = (0.30, 0.32, 0.36, 1.0)
    material = gfx.LineMaterial(color=color, thickness=1.0)
    for i in range(-n, n + 1):
        v = i * step
        # Line parallel to Y at x=v.
        ax = np.array(
            [[v, -half_size, 0.0], [v,  half_size, 0.0]], dtype=np.float32
        )
        lines.append(gfx.Line(gfx.Geometry(positions=ax), material))
        # Line parallel to X at y=v.
        ay = np.array(
            [[-half_size, v, 0.0], [ half_size, v, 0.0]], dtype=np.float32
        )
        lines.append(gfx.Line(gfx.Geometry(positions=ay), material))
    return lines


def _write_trail(trail: Any, pts: list[np.ndarray]) -> None:
    """Write a list of viewer-frame points into a pre-allocated trail buffer."""

    try:
        buf = trail.geometry.positions
        data = buf.data
        capacity = len(data)
        if not pts:
            data[:] = 0.0
            buf.update_range(0, capacity)
            return
        arr = np.asarray(pts, dtype=np.float32)
        # If we have more points than buffer slots, keep the most recent.
        if len(arr) > capacity:
            arr = arr[-capacity:]
        n = len(arr)
        data[:n] = arr
        # Pad the unused tail with the last point so the line doesn't
        # snap back to the origin.
        if n < capacity:
            data[n:] = arr[-1]
        buf.update_range(0, capacity)
    except Exception:  # pragma: no cover
        _log.debug("Trail buffer update failed")


def _zero_trail(trail: Any) -> None:
    try:
        buf = trail.geometry.positions
        buf.data[:] = 0.0
        buf.update_range(0, len(buf.data))
    except Exception:  # pragma: no cover
        pass
