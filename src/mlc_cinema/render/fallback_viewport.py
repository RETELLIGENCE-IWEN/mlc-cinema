"""Qt-painted 2D fallback viewport.

Used when the pygfx + wgpu real-3D backend is unavailable on the host
(no compatible GPU drivers, missing libraries, etc.). Implements the
same public interface as the pygfx viewport so the rest of the app
doesn't care which backend is active.

Projection convention (orthographic side-view):
    screen_x  =  world_x  (east)
    screen_y  = -world_z  (altitude points up on the screen)
The world Y (north) axis is collapsed in this 2D view.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from mlc_cinema.config import DEFAULT_TRAIL_LENGTH
from mlc_cinema.mlc.timeline import MLCTimeline
from mlc_cinema.scene.entities import SceneEntity
from mlc_cinema.scene.scene_model import SceneFrame
from mlc_cinema.scene.trajectory import (
    TrajectoryCache,
    build_trajectory_cache,
    full_trajectory_points,
    trajectory_points_up_to_frame,
)


# Trail-mode constants mirror those in pygfx_renderer.py so the UI
# can pass the same string values to either backend.
TRAIL_MODE_HIDDEN: str = "hidden"
TRAIL_MODE_TO_CURRENT: str = "to_current"
TRAIL_MODE_FULL: str = "full"
_VALID_TRAIL_MODES: frozenset[str] = frozenset(
    {TRAIL_MODE_HIDDEN, TRAIL_MODE_TO_CURRENT, TRAIL_MODE_FULL}
)

_log = logging.getLogger(__name__)


# A small palette so multiple bodies render in distinct colours.
_BODY_COLORS: tuple[tuple[int, int, int], ...] = (
    (235, 110, 110),
    (110, 200, 235),
    (180, 235, 130),
    (235, 200, 110),
    (200, 130, 235),
    (235, 235, 235),
)


@dataclass
class _BodyVisualState:
    entity: SceneEntity
    color: QColor
    trail: deque[np.ndarray]


class FallbackViewport(QWidget):
    """Qt-painted 2D fallback used when pygfx is unavailable.

    Implements the M1.0 viewport public interface so it can stand in
    for the pygfx-backed widget without UI changes.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAutoFillBackground(False)

        self._entities: dict[int, _BodyVisualState] = {}
        self._current_frame: SceneFrame | None = None
        self._timeline: MLCTimeline | None = None
        self._frame_index: int = 0
        self._selected_body_id: int | None = None
        self._trail_length: int = DEFAULT_TRAIL_LENGTH

        # Trajectory cache + trail display state (mirrors pygfx backend).
        self._trajectory_cache: TrajectoryCache | None = None
        self._trail_mode: str = TRAIL_MODE_TO_CURRENT
        self._trails_visible: bool = True

        # Cached extents for auto-fitting the camera. Updated as new
        # frames arrive so the view follows the scene.
        self._extents_min = np.array([-5.0, -5.0], dtype=np.float64)
        self._extents_max = np.array([5.0, 5.0], dtype=np.float64)

    # ----- public API used by the UI -----

    def set_entities(self, entities: dict[int, SceneEntity]) -> None:
        """Replace the set of known entities; clears trails."""

        self._entities.clear()
        for i, (body_id, ent) in enumerate(entities.items()):
            r, g, b = _BODY_COLORS[i % len(_BODY_COLORS)]
            self._entities[body_id] = _BodyVisualState(
                entity=ent,
                color=QColor(r, g, b),
                trail=deque(maxlen=self._trail_length),
            )
        self._reset_extents()
        self.update()

    def set_scene_frame(
        self, frame: SceneFrame, frame_index: int | None = None
    ) -> None:
        """Render this frame on the next paint event.

        When a timeline is known, ``frame_index`` is used to recompute
        the trail from frames ``[0..frame_index]`` so scrubbing
        backward never paints a "future-trail" artifact. Without a
        timeline, trails accumulate from each call instead.
        """

        self._current_frame = frame
        if frame_index is not None:
            self._frame_index = int(frame_index)

        for body_id, body_state in frame.body_states.items():
            vis = self._entities.get(body_id)
            if vis is None:
                # An unexpected body id appeared in the state stream —
                # add a synthetic entity so it still renders.
                _log.debug(
                    "Viewport received state for undeclared body id %d", body_id
                )
                synthetic = SceneEntity(body_id=body_id, name=f"body_{body_id}")
                idx = len(self._entities)
                r, g, b = _BODY_COLORS[idx % len(_BODY_COLORS)]
                vis = _BodyVisualState(
                    entity=synthetic,
                    color=QColor(r, g, b),
                    trail=deque(maxlen=self._trail_length),
                )
                self._entities[body_id] = vis

            self._update_extents(body_state.position)

        if self._timeline is not None and frame_index is not None:
            self._refresh_trails_from_timeline()
        else:
            for body_id, body_state in frame.body_states.items():
                vis = self._entities.get(body_id)
                if vis is None:
                    continue
                vis.trail.append(
                    np.asarray(body_state.position, dtype=np.float64)
                )

        self.update()

    def reset_trails(self) -> None:
        """Forget the position history (e.g. after scrubbing back to start)."""

        for vis in self._entities.values():
            vis.trail.clear()
        self.update()

    def set_timeline(self, timeline: MLCTimeline | None) -> None:
        self._timeline = timeline
        if timeline is not None and timeline.frames:
            self._trajectory_cache = build_trajectory_cache(timeline)
        else:
            self._trajectory_cache = None
        for vis in self._entities.values():
            vis.trail.clear()

    def set_trail_mode(self, mode: str) -> None:
        if mode not in _VALID_TRAIL_MODES:
            _log.warning("Unknown trail mode %r; ignoring", mode)
            return
        self._trail_mode = mode
        if self._timeline is not None:
            self._refresh_trails_from_timeline()
        self.update()

    def set_trails_visible(self, visible: bool) -> None:
        self._trails_visible = bool(visible)
        if self._timeline is not None:
            self._refresh_trails_from_timeline()
        self.update()

    def save_screenshot(self, path) -> bool:  # path: str | Path
        try:
            pixmap = self.grab()
            if pixmap is None or pixmap.isNull():
                return False
            return bool(pixmap.save(str(path), "PNG"))
        except Exception:  # pragma: no cover
            _log.exception("Fallback screenshot save failed")
            return False

    def set_selected_body(self, body_id: int | None) -> None:
        self._selected_body_id = body_id
        self.update()

    def reset_camera(self) -> None:
        self._reset_extents()
        if self._timeline is not None:
            for frame in self._timeline.frames:
                for state in frame.states_by_body.values():
                    self._update_extents(state.position)
        self.update()

    def frame_all(self) -> None:
        # In the 2D fallback, "frame all" just resets cached extents
        # and lets the next paint auto-fit.
        self.reset_camera()

    def _refresh_trails_from_timeline(self) -> None:
        if self._trajectory_cache is None:
            return
        for vis in self._entities.values():
            vis.trail.clear()
        if not self._trails_visible or self._trail_mode == TRAIL_MODE_HIDDEN:
            return
        for body_id, vis in self._entities.items():
            trajectory = self._trajectory_cache.trajectories.get(body_id)
            if trajectory is None:
                continue
            if self._trail_mode == TRAIL_MODE_FULL:
                pts = full_trajectory_points(trajectory)
            else:
                pts = trajectory_points_up_to_frame(
                    trajectory, self._frame_index
                )
            for i in range(pts.shape[0]):
                vis.trail.append(np.asarray(pts[i], dtype=np.float64))

    # ----- camera extents -----

    def _reset_extents(self) -> None:
        self._extents_min = np.array([-5.0, -5.0], dtype=np.float64)
        self._extents_max = np.array([5.0, 5.0], dtype=np.float64)

    def _update_extents(self, world_pos: np.ndarray) -> None:
        # Project: screen-x = world.x, screen-y = world.z.
        proj = np.array([world_pos[0], world_pos[2]], dtype=np.float64)
        self._extents_min = np.minimum(self._extents_min, proj)
        self._extents_max = np.maximum(self._extents_max, proj)

    # ----- painting -----

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (Qt API)
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            self._paint_background(painter)
            self._paint_grid_and_axes(painter)
            self._paint_bodies(painter)
            self._paint_overlay(painter)
        finally:
            painter.end()

    # --- helpers ---

    def _paint_background(self, p: QPainter) -> None:
        rect = self.rect()
        p.fillRect(rect, QColor(18, 20, 26))

    def _viewport_transform(self) -> tuple[QPointF, float]:
        """Compute (origin_screen, world_to_screen_scale) with isotropic scaling."""

        margin = 40.0
        w = max(1.0, float(self.width()) - 2.0 * margin)
        h = max(1.0, float(self.height()) - 2.0 * margin)

        size_world = self._extents_max - self._extents_min
        # Pad a little to avoid markers sitting flush against the edge.
        pad = 0.10 * np.maximum(size_world, 1.0)
        size_world = size_world + 2.0 * pad
        center_world = 0.5 * (self._extents_max + self._extents_min)

        scale_x = w / max(size_world[0], 1e-6)
        scale_y = h / max(size_world[1], 1e-6)
        scale = min(scale_x, scale_y)

        cx_screen = self.width() / 2.0
        cy_screen = self.height() / 2.0
        # screen_y is flipped so altitude (world z) goes up.
        origin = QPointF(
            cx_screen - center_world[0] * scale,
            cy_screen + center_world[1] * scale,
        )
        return origin, scale

    def _world_to_screen(
        self, origin: QPointF, scale: float, world_pos: np.ndarray
    ) -> QPointF:
        return QPointF(
            origin.x() + world_pos[0] * scale,
            origin.y() - world_pos[2] * scale,
        )

    def _paint_grid_and_axes(self, p: QPainter) -> None:
        origin, scale = self._viewport_transform()

        # Ground line at world z = 0.
        ground_pen = QPen(QColor(70, 110, 80), 1.5)
        p.setPen(ground_pen)
        ground_y = origin.y()
        p.drawLine(QPointF(0.0, ground_y), QPointF(float(self.width()), ground_y))

        # Faint grid every "round" world unit chosen by extent size.
        size_world = self._extents_max - self._extents_min
        target_lines = 10.0
        raw_step = max(size_world.max(), 1.0) / target_lines
        step = _nice_step(raw_step)

        grid_pen = QPen(QColor(40, 50, 65), 1.0)
        p.setPen(grid_pen)

        # Horizontal grid lines (world z planes).
        z_min = self._extents_min[1] - step
        z_max = self._extents_max[1] + step
        z = _floor_to(z_min, step)
        while z <= z_max:
            y = origin.y() - z * scale
            p.drawLine(QPointF(0.0, y), QPointF(float(self.width()), y))
            z += step

        # Vertical grid lines (world x planes).
        x_min = self._extents_min[0] - step
        x_max = self._extents_max[0] + step
        x = _floor_to(x_min, step)
        while x <= x_max:
            xs = origin.x() + x * scale
            p.drawLine(QPointF(xs, 0.0), QPointF(xs, float(self.height())))
            x += step

        # World axes through origin: X (red), Z (green).
        x_axis_pen = QPen(QColor(200, 90, 90), 2.0)
        z_axis_pen = QPen(QColor(110, 200, 110), 2.0)
        cx, cy = origin.x(), origin.y()
        p.setPen(x_axis_pen)
        p.drawLine(QPointF(cx, cy), QPointF(cx + 30.0, cy))
        p.setPen(z_axis_pen)
        p.drawLine(QPointF(cx, cy), QPointF(cx, cy - 30.0))

        p.setPen(QColor(180, 180, 180))
        font = QFont()
        font.setPointSize(8)
        p.setFont(font)
        p.drawText(QPointF(cx + 32.0, cy + 4.0), "+X")
        p.drawText(QPointF(cx + 4.0, cy - 32.0), "+Z")

    def _paint_bodies(self, p: QPainter) -> None:
        if not self._entities:
            return

        origin, scale = self._viewport_transform()

        for vis in self._entities.values():
            color = vis.color

            # Trail.
            if len(vis.trail) >= 2:
                pen = QPen(QColor(color.red(), color.green(), color.blue(), 140))
                pen.setWidthF(1.5)
                p.setPen(pen)
                prev: QPointF | None = None
                for pt in vis.trail:
                    s = self._world_to_screen(origin, scale, pt)
                    if prev is not None:
                        p.drawLine(prev, s)
                    prev = s

            # Body marker (small filled circle).
            if vis.trail:
                pos = vis.trail[-1]
                center = self._world_to_screen(origin, scale, pos)
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(color))
                radius = 6.0
                p.drawEllipse(center, radius, radius)

                # Halo to make the body easy to spot.
                halo = QColor(color.red(), color.green(), color.blue(), 80)
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(halo, 1.5))
                p.drawEllipse(center, radius + 4.0, radius + 4.0)

                # Label.
                p.setPen(QColor(220, 220, 220))
                p.drawText(
                    QPointF(center.x() + 10.0, center.y() - 8.0),
                    vis.entity.name,
                )

    def _paint_overlay(self, p: QPainter) -> None:
        info_lines: list[str] = []
        if self._current_frame is None:
            info_lines.append("No frame loaded.")
        else:
            info_lines.append(f"t = {self._current_frame.t:.3f} s")
            info_lines.append(
                f"bodies tracked: {len(self._entities)}"
            )

        p.setPen(QColor(180, 180, 200))
        font = QFont()
        font.setPointSize(9)
        p.setFont(font)
        rect = QRectF(10.0, 8.0, float(self.width()) - 20.0, 40.0)
        p.drawText(rect, Qt.AlignLeft | Qt.AlignTop, "\n".join(info_lines))


def _nice_step(raw: float) -> float:
    """Round ``raw`` up to a 'nice' grid step (1, 2, 5, 10, ...)."""

    if raw <= 0.0:
        return 1.0
    exp = np.floor(np.log10(raw))
    base = 10.0**exp
    for mult in (1.0, 2.0, 5.0, 10.0):
        candidate = mult * base
        if candidate >= raw:
            return float(candidate)
    return float(10.0 * base)


def _floor_to(value: float, step: float) -> float:
    return float(np.floor(value / step) * step)
