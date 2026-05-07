"""Tests for ``mlc_cinema.scene.bounds``."""

from __future__ import annotations

import numpy as np
import pytest

from mlc_cinema.mlc.records import MLCBody, MLCParseResult, MLCState
from mlc_cinema.mlc.timeline import build_timeline
from mlc_cinema.scene.bounds import (
    SceneBounds,
    compute_bounds_from_points,
    compute_timeline_bounds,
)


def _state(t: float, body_id: int, p: tuple[float, float, float]) -> MLCState:
    return MLCState(
        t=t, body_id=body_id, position=np.asarray(p, dtype=np.float64)
    )


def test_compute_timeline_bounds_single_body() -> None:
    bodies = {0: MLCBody(id=0, name="b0")}
    states = [
        _state(0.0, 0, (0.0, 0.0, 0.0)),
        _state(1.0, 0, (10.0, -4.0, 6.0)),
    ]
    timeline = build_timeline(MLCParseResult(None, bodies, states))
    b = compute_timeline_bounds(timeline)

    np.testing.assert_allclose(b.center, [5.0, -2.0, 3.0])
    np.testing.assert_allclose(b.extent, [5.0, 2.0, 3.0])
    assert b.radius >= float(np.linalg.norm(b.extent))


def test_compute_timeline_bounds_multibody() -> None:
    bodies = {0: MLCBody(id=0, name="b0"), 1: MLCBody(id=1, name="b1")}
    states = [
        _state(0.0, 0, (-5.0, 0.0, 0.0)),
        _state(0.0, 1, (5.0, 0.0, 0.0)),
        _state(1.0, 0, (0.0, 10.0, 0.0)),
        _state(1.0, 1, (0.0, -10.0, 4.0)),
    ]
    timeline = build_timeline(MLCParseResult(None, bodies, states))
    b = compute_timeline_bounds(timeline)

    # Both bodies' positions should be inside the box.
    p_min = b.center - b.extent
    p_max = b.center + b.extent
    for s in states:
        assert (s.position >= p_min - 1e-9).all()
        assert (s.position <= p_max + 1e-9).all()


def test_compute_timeline_bounds_nonzero_radius_for_single_point() -> None:
    bodies = {0: MLCBody(id=0, name="b0")}
    states = [_state(0.0, 0, (3.0, 4.0, 5.0))]
    timeline = build_timeline(MLCParseResult(None, bodies, states))
    b = compute_timeline_bounds(timeline)

    np.testing.assert_allclose(b.center, [3.0, 4.0, 5.0])
    np.testing.assert_allclose(b.extent, [0.0, 0.0, 0.0])
    # Radius must be strictly positive — no camera-at-zero-distance.
    assert b.radius > 0.0


def test_compute_bounds_from_points_rejects_bad_shape() -> None:
    with pytest.raises(ValueError):
        compute_bounds_from_points(np.zeros((4,)))


def test_compute_bounds_from_points_empty_uses_fallback() -> None:
    b = compute_bounds_from_points(np.zeros((0, 3)), fallback_radius=7.5)
    assert isinstance(b, SceneBounds)
    assert b.radius == 7.5
