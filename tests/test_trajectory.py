"""Tests for ``mlc_cinema.scene.trajectory``."""

from __future__ import annotations

import numpy as np

from mlc_cinema.mlc.records import MLCBody, MLCParseResult, MLCState
from mlc_cinema.mlc.timeline import build_timeline
from mlc_cinema.scene.trajectory import (
    build_trajectory_cache,
    full_trajectory_points,
    trajectory_points_up_to_frame,
)


def _state(t: float, body_id: int, p: tuple[float, float, float]) -> MLCState:
    return MLCState(
        t=t, body_id=body_id, position=np.asarray(p, dtype=np.float64)
    )


def _timeline(states, bodies):
    return build_timeline(MLCParseResult(None, bodies, states))


def test_build_trajectory_cache_single_body() -> None:
    bodies = {0: MLCBody(id=0, name="b0")}
    states = [
        _state(0.0, 0, (1.0, 0.0, 0.0)),
        _state(0.5, 0, (2.0, 0.0, 0.0)),
        _state(1.0, 0, (3.0, 0.0, 0.0)),
    ]
    timeline = _timeline(states, bodies)
    cache = build_trajectory_cache(timeline)

    assert cache.frame_count == 3
    assert set(cache.trajectories.keys()) == {0}

    traj = cache.trajectories[0]
    assert traj.body_id == 0
    np.testing.assert_array_equal(traj.frame_indices, [0, 1, 2])
    np.testing.assert_allclose(traj.times, [0.0, 0.5, 1.0])
    assert traj.positions.shape == (3, 3)
    np.testing.assert_allclose(
        traj.positions,
        [[1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [3.0, 0.0, 0.0]],
    )


def test_build_trajectory_cache_multibody_with_missing_states() -> None:
    bodies = {0: MLCBody(id=0, name="b0"), 1: MLCBody(id=1, name="b1")}
    states = [
        # Frame 0: both bodies.
        _state(0.0, 0, (1.0, 0.0, 0.0)),
        _state(0.0, 1, (0.0, 1.0, 0.0)),
        # Frame 1: only body 0.
        _state(0.5, 0, (2.0, 0.0, 0.0)),
        # Frame 2: only body 1.
        _state(1.0, 1, (0.0, 2.0, 0.0)),
    ]
    timeline = _timeline(states, bodies)
    cache = build_trajectory_cache(timeline)

    assert cache.frame_count == 3
    traj0 = cache.trajectories[0]
    traj1 = cache.trajectories[1]

    np.testing.assert_array_equal(traj0.frame_indices, [0, 1])
    np.testing.assert_array_equal(traj1.frame_indices, [0, 2])

    assert traj0.positions.shape == (2, 3)
    assert traj1.positions.shape == (2, 3)


def test_trajectory_points_up_to_frame_basic() -> None:
    bodies = {0: MLCBody(id=0, name="b0")}
    states = [
        _state(0.0, 0, (1.0, 0.0, 0.0)),
        _state(0.5, 0, (2.0, 0.0, 0.0)),
        _state(1.0, 0, (3.0, 0.0, 0.0)),
    ]
    cache = build_trajectory_cache(_timeline(states, bodies))
    traj = cache.trajectories[0]

    # Before first frame → empty.
    assert trajectory_points_up_to_frame(traj, -1).shape == (0, 3)

    # First frame only.
    pts = trajectory_points_up_to_frame(traj, 0)
    assert pts.shape == (1, 3)
    np.testing.assert_allclose(pts[0], [1.0, 0.0, 0.0])

    # Through frame 1.
    pts = trajectory_points_up_to_frame(traj, 1)
    assert pts.shape == (2, 3)

    # All frames.
    pts = trajectory_points_up_to_frame(traj, 2)
    assert pts.shape == (3, 3)

    # Beyond last frame → still all frames.
    pts = trajectory_points_up_to_frame(traj, 999)
    assert pts.shape == (3, 3)


def test_trajectory_points_up_to_frame_with_sparse_indices() -> None:
    """Body that only has states at frames 0 and 2; intermediate frame
    index 1 should still return only the points from frame ≤ 1."""

    bodies = {0: MLCBody(id=0, name="b0"), 1: MLCBody(id=1, name="b1")}
    states = [
        _state(0.0, 0, (1.0, 0.0, 0.0)),
        _state(0.0, 1, (0.0, 1.0, 0.0)),
        _state(0.5, 0, (2.0, 0.0, 0.0)),
        _state(1.0, 1, (0.0, 2.0, 0.0)),
    ]
    cache = build_trajectory_cache(_timeline(states, bodies))
    traj1 = cache.trajectories[1]
    # body 1 has frame_indices = [0, 2].

    pts = trajectory_points_up_to_frame(traj1, 0)
    assert pts.shape == (1, 3)

    pts = trajectory_points_up_to_frame(traj1, 1)
    assert pts.shape == (1, 3)  # frame 1 has no body 1 state

    pts = trajectory_points_up_to_frame(traj1, 2)
    assert pts.shape == (2, 3)


def test_full_trajectory_points_returns_all_positions() -> None:
    bodies = {0: MLCBody(id=0, name="b0")}
    states = [
        _state(0.0, 0, (1.0, 0.0, 0.0)),
        _state(0.5, 0, (2.0, 0.0, 0.0)),
    ]
    cache = build_trajectory_cache(_timeline(states, bodies))
    traj = cache.trajectories[0]
    pts = full_trajectory_points(traj)
    assert pts.shape == (2, 3)
    np.testing.assert_allclose(pts, [[1.0, 0.0, 0.0], [2.0, 0.0, 0.0]])


def test_trajectory_points_returns_view_not_copy() -> None:
    """Slicing should not allocate a new buffer."""

    bodies = {0: MLCBody(id=0, name="b0")}
    states = [_state(0.0, 0, (1.0, 0.0, 0.0))]
    cache = build_trajectory_cache(_timeline(states, bodies))
    traj = cache.trajectories[0]
    pts = trajectory_points_up_to_frame(traj, 0)
    # Mutating the slice should write through to the cache buffer
    # (i.e. pts is a view, not a copy).
    pts[0, 0] = 42.0
    assert traj.positions[0, 0] == 42.0
