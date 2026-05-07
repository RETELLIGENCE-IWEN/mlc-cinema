"""Renderer-agnostic orbit camera state.

This module knows nothing about pygfx, Qt, or any specific graphics
backend. It computes a camera position from an orbit-state dataclass
and provides helpers for orbiting, panning, zooming, and framing a
:class:`SceneBounds` — pure NumPy math, fully unit-testable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np

from mlc_cinema.scene.bounds import SceneBounds


# Pitch is clamped to a near-vertical range to avoid the gimbal-lock
# singularity at ±π/2.
_PITCH_LIMIT_RAD: float = math.pi / 2.0 - 1e-2
_MIN_DISTANCE: float = 1e-3
# Default vertical FOV used when framing bounds.
_DEFAULT_FOV_RAD: float = math.radians(45.0)
_FRAME_PADDING: float = 1.4  # 40% padding around the bounding sphere


@dataclass
class OrbitCameraState:
    """Mutable orbit-camera state.

    The camera looks at ``target`` from a position offset by
    ``distance`` along the direction defined by ``yaw_rad`` (around the
    world Z axis) and ``pitch_rad`` (above the X-Y plane).
    """

    target: np.ndarray = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )
    distance: float = 100.0
    yaw_rad: float = math.radians(-60.0)
    pitch_rad: float = math.radians(25.0)
    up: np.ndarray = field(
        default_factory=lambda: np.array([0.0, 0.0, 1.0], dtype=np.float64)
    )


def clamp_pitch(pitch_rad: float) -> float:
    """Clamp pitch to the camera's safe range."""

    return max(-_PITCH_LIMIT_RAD, min(_PITCH_LIMIT_RAD, float(pitch_rad)))


def normalized_state(state: OrbitCameraState) -> OrbitCameraState:
    """Return a copy of ``state`` with pitch clamped and distance positive."""

    return replace(
        state,
        pitch_rad=clamp_pitch(state.pitch_rad),
        distance=max(_MIN_DISTANCE, float(state.distance)),
    )


def orbit_camera_position(state: OrbitCameraState) -> np.ndarray:
    """Compute the camera's world-space position from its orbit state."""

    s = normalized_state(state)
    cos_p = math.cos(s.pitch_rad)
    sin_p = math.sin(s.pitch_rad)
    cos_y = math.cos(s.yaw_rad)
    sin_y = math.sin(s.yaw_rad)

    # yaw spins around world Z; pitch lifts toward +Z.
    offset = np.array(
        [
            s.distance * cos_p * cos_y,
            s.distance * cos_p * sin_y,
            s.distance * sin_p,
        ],
        dtype=np.float64,
    )
    return s.target + offset


def orbit(
    state: OrbitCameraState, d_yaw_rad: float, d_pitch_rad: float
) -> OrbitCameraState:
    """Apply incremental yaw / pitch deltas (in radians)."""

    return replace(
        state,
        yaw_rad=float(state.yaw_rad + d_yaw_rad),
        pitch_rad=clamp_pitch(state.pitch_rad + d_pitch_rad),
    )


def zoom(state: OrbitCameraState, factor: float) -> OrbitCameraState:
    """Multiply the camera distance by ``factor`` (clamped to a positive minimum)."""

    return replace(
        state, distance=max(_MIN_DISTANCE, float(state.distance * factor))
    )


def pan(
    state: OrbitCameraState, dx_world: float, dy_world: float
) -> OrbitCameraState:
    """Translate the look-at target along the camera's view-plane axes.

    ``dx_world`` moves along the camera's right vector; ``dy_world``
    moves along the camera's up vector.
    """

    s = normalized_state(state)
    forward = (s.target - orbit_camera_position(s)).astype(np.float64)
    forward_n = _safe_normalize(forward)
    right = _safe_normalize(np.cross(forward_n, s.up))
    up_view = _safe_normalize(np.cross(right, forward_n))
    new_target = s.target + dx_world * right + dy_world * up_view
    return replace(s, target=new_target)


def frame_bounds(
    bounds: SceneBounds,
    *,
    fov_rad: float = _DEFAULT_FOV_RAD,
    padding: float = _FRAME_PADDING,
    yaw_rad: float | None = None,
    pitch_rad: float | None = None,
) -> OrbitCameraState:
    """Build an :class:`OrbitCameraState` that frames ``bounds``.

    The distance is chosen so a sphere of radius ``bounds.radius * padding``
    is fully visible at vertical field of view ``fov_rad``.
    """

    radius = max(float(bounds.radius), _MIN_DISTANCE) * float(padding)
    distance = radius / math.sin(0.5 * float(fov_rad))
    return OrbitCameraState(
        target=np.asarray(bounds.center, dtype=np.float64).copy(),
        distance=max(_MIN_DISTANCE, distance),
        yaw_rad=math.radians(-60.0) if yaw_rad is None else float(yaw_rad),
        pitch_rad=clamp_pitch(
            math.radians(25.0) if pitch_rad is None else float(pitch_rad)
        ),
    )


def _safe_normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n < 1e-12:
        return np.zeros_like(v)
    return v / n
