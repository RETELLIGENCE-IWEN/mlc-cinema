"""Axis-aligned scene bounds, used for camera auto-fit.

The bounds are computed from every body's position across every frame
of a timeline. Output is in cinema viewer-frame coordinates (right-
handed, Z up). Single-point timelines fall back to a small default
radius so the camera doesn't end up at zero distance.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from mlc_cinema.mlc.timeline import MLCTimeline


# Used when a timeline has only one (or all-equal) positions.
_DEFAULT_FALLBACK_RADIUS: float = 10.0


@dataclass(frozen=True)
class SceneBounds:
    """Axis-aligned bounds of a scene in viewer-frame coordinates."""

    center: np.ndarray   # shape (3,)
    extent: np.ndarray   # shape (3,) — half-size per axis
    radius: float        # bounding-sphere radius, always > 0


def compute_timeline_bounds(
    timeline: MLCTimeline,
    *,
    fallback_radius: float = _DEFAULT_FALLBACK_RADIUS,
) -> SceneBounds:
    """Compute :class:`SceneBounds` covering every body across every frame."""

    points = _collect_points(timeline)
    if points.size == 0:
        # No states at all — center at origin with a generic radius.
        return _default_bounds(fallback_radius)

    return compute_bounds_from_points(points, fallback_radius=fallback_radius)


def compute_bounds_from_points(
    points: np.ndarray,
    *,
    fallback_radius: float = _DEFAULT_FALLBACK_RADIUS,
) -> SceneBounds:
    """Compute bounds for an arbitrary ``(N, 3)`` array of viewer-frame points."""

    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError(
            f"points must have shape (N, 3); got {points.shape}"
        )

    if points.shape[0] == 0:
        return _default_bounds(fallback_radius)

    p_min = points.min(axis=0)
    p_max = points.max(axis=0)
    center = 0.5 * (p_min + p_max)
    extent = 0.5 * (p_max - p_min)

    # Radius is the max corner-distance from the center; clamp to a
    # nonzero floor so a degenerate (all-same-point) scene still has
    # a usable camera distance.
    diag = float(np.linalg.norm(extent))
    radius = max(diag, fallback_radius)

    return SceneBounds(
        center=center.astype(np.float64, copy=False),
        extent=extent.astype(np.float64, copy=False),
        radius=radius,
    )


def _collect_points(timeline: MLCTimeline) -> np.ndarray:
    out: list[np.ndarray] = []
    for frame in timeline.frames:
        for state in frame.states_by_body.values():
            out.append(np.asarray(state.position, dtype=np.float64))
    if not out:
        return np.zeros((0, 3), dtype=np.float64)
    return np.vstack(out)


def _default_bounds(fallback_radius: float) -> SceneBounds:
    return SceneBounds(
        center=np.zeros(3, dtype=np.float64),
        extent=np.full(3, fallback_radius, dtype=np.float64),
        radius=float(fallback_radius),
    )
