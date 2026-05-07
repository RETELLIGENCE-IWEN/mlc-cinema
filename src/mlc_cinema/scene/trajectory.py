"""Per-body trajectory cache for cheap trail recomputation.

The pygfx viewport rebuilt trail point lists by walking
``timeline.frames[0..frame_index]`` on every frame change. For long
high-rate logs (3000+ frames) that's O(N²) over the whole replay.

This module preallocates ``(N, 3)`` numpy arrays per body once when
the timeline is loaded, so trail updates during playback or scrubbing
become O(1) array slices.

The cache is renderer-agnostic: it imports only numpy.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from mlc_cinema.mlc.timeline import MLCTimeline


@dataclass(frozen=True)
class BodyTrajectory:
    """Compact, per-body trajectory in viewer-frame coordinates.

    ``frame_indices`` are the indices into ``timeline.frames`` at which
    this body actually had a state record (so multi-body logs with
    sparse coverage are handled cleanly).
    """

    body_id: int
    frame_indices: np.ndarray   # shape (N,), dtype int64
    times: np.ndarray           # shape (N,), dtype float64
    positions: np.ndarray       # shape (N, 3), dtype float64


@dataclass(frozen=True)
class TrajectoryCache:
    """All per-body trajectories for one timeline."""

    trajectories: dict[int, BodyTrajectory]
    frame_count: int


def build_trajectory_cache(timeline: MLCTimeline) -> TrajectoryCache:
    """Walk ``timeline.frames`` once and pack per-body arrays.

    Empty trajectories are kept (zero-length arrays) so the renderer
    can still look up a body id; missing per-frame states are simply
    skipped.
    """

    body_indices: dict[int, list[int]] = {}
    body_times: dict[int, list[float]] = {}
    body_positions: dict[int, list[np.ndarray]] = {}

    for frame_idx, frame in enumerate(timeline.frames):
        for body_id, state in frame.states_by_body.items():
            body_indices.setdefault(body_id, []).append(frame_idx)
            body_times.setdefault(body_id, []).append(float(state.t))
            body_positions.setdefault(body_id, []).append(
                np.asarray(state.position, dtype=np.float64)
            )

    trajectories: dict[int, BodyTrajectory] = {}
    for body_id in body_indices:
        idxs = np.asarray(body_indices[body_id], dtype=np.int64)
        times = np.asarray(body_times[body_id], dtype=np.float64)
        positions = (
            np.vstack(body_positions[body_id]).astype(np.float64, copy=False)
            if body_positions[body_id]
            else np.zeros((0, 3), dtype=np.float64)
        )
        trajectories[body_id] = BodyTrajectory(
            body_id=body_id,
            frame_indices=idxs,
            times=times,
            positions=positions,
        )

    return TrajectoryCache(
        trajectories=trajectories,
        frame_count=len(timeline.frames),
    )


def trajectory_points_up_to_frame(
    trajectory: BodyTrajectory, frame_index: int
) -> np.ndarray:
    """Return positions whose ``frame_indices <= frame_index``.

    * ``frame_index < first frame``: empty ``(0, 3)`` array.
    * ``frame_index >= last frame``: every point.

    Uses ``np.searchsorted`` for an O(log N) cut and returns a slice
    (a view, not a copy).
    """

    if trajectory.positions.shape[0] == 0:
        return trajectory.positions

    cut = int(
        np.searchsorted(trajectory.frame_indices, int(frame_index), side="right")
    )
    if cut <= 0:
        return trajectory.positions[:0]
    return trajectory.positions[:cut]


def full_trajectory_points(trajectory: BodyTrajectory) -> np.ndarray:
    """Return every cached position for this body."""

    return trajectory.positions
