"""Tests for ``mlc_cinema.mlc.timeline``."""

from __future__ import annotations

import numpy as np
import pytest

from mlc_cinema.mlc.records import MLCBody, MLCParseResult, MLCState
from mlc_cinema.mlc.timeline import (
    TimelineError,
    build_timeline,
)


def _state(t: float, body_id: int, x: float = 0.0) -> MLCState:
    return MLCState(
        t=t,
        body_id=body_id,
        position=np.array([x, 0.0, 0.0], dtype=np.float64),
    )


def _result_with(states: list[MLCState], bodies: dict[int, MLCBody] | None = None) -> MLCParseResult:
    return MLCParseResult(
        header=None,
        bodies=bodies or {0: MLCBody(id=0, name="b0")},
        states=states,
    )


def test_frames_are_sorted_by_time() -> None:
    out_of_order = [
        _state(2.0, 0),
        _state(0.5, 0),
        _state(1.0, 0),
        _state(0.0, 0),
    ]
    timeline = build_timeline(_result_with(out_of_order))
    times = [f.t for f in timeline.frames]
    assert times == sorted(times)
    assert times == [0.0, 0.5, 1.0, 2.0]


def test_duration_is_correct() -> None:
    states = [_state(0.0, 0), _state(0.5, 0), _state(2.0, 0)]
    timeline = build_timeline(_result_with(states))
    assert timeline.start_time_s == 0.0
    assert timeline.end_time_s == 2.0
    assert timeline.duration_s == pytest.approx(2.0)


def test_nearest_frame_lookup() -> None:
    states = [_state(0.0, 0), _state(1.0, 0), _state(2.0, 0)]
    timeline = build_timeline(_result_with(states))

    # Exact hits.
    assert timeline.nearest_frame(0.0).t == 0.0
    assert timeline.nearest_frame(1.0).t == 1.0
    assert timeline.nearest_frame(2.0).t == 2.0

    # Strictly nearer to a neighbour.
    assert timeline.nearest_frame(0.4).t == 0.0
    assert timeline.nearest_frame(0.6).t == 1.0
    assert timeline.nearest_frame(1.6).t == 2.0

    # Out-of-range times clamp to the endpoints.
    assert timeline.nearest_frame(-5.0).t == 0.0
    assert timeline.nearest_frame(99.0).t == 2.0


def test_states_with_same_timestamp_group_into_one_frame() -> None:
    states = [
        MLCState(
            t=0.0,
            body_id=0,
            position=np.array([1.0, 0.0, 0.0]),
        ),
        MLCState(
            t=0.0,
            body_id=1,
            position=np.array([0.0, 2.0, 0.0]),
        ),
        MLCState(
            t=1.0,
            body_id=0,
            position=np.array([1.0, 0.0, 1.0]),
        ),
    ]
    bodies = {
        0: MLCBody(id=0, name="b0"),
        1: MLCBody(id=1, name="b1"),
    }
    timeline = build_timeline(_result_with(states, bodies))
    assert len(timeline.frames) == 2

    f0 = timeline.frames[0]
    assert f0.t == 0.0
    assert set(f0.states_by_body.keys()) == {0, 1}
    np.testing.assert_allclose(f0.states_by_body[0].position, [1.0, 0.0, 0.0])
    np.testing.assert_allclose(f0.states_by_body[1].position, [0.0, 2.0, 0.0])

    f1 = timeline.frames[1]
    assert f1.t == 1.0
    assert set(f1.states_by_body.keys()) == {0}


def test_empty_states_raise_clear_error() -> None:
    with pytest.raises(TimelineError):
        build_timeline(_result_with([]))


def test_frame_at_index_out_of_range_raises() -> None:
    states = [_state(0.0, 0), _state(1.0, 0)]
    timeline = build_timeline(_result_with(states))
    with pytest.raises(IndexError):
        timeline.frame_at_index(99)
    with pytest.raises(IndexError):
        timeline.frame_at_index(-1)


def test_floating_point_close_timestamps_group_together() -> None:
    # Two timestamps that differ only by floating-point noise should be
    # treated as the same frame.
    t0 = 0.1 + 0.2  # 0.30000000000000004
    t1 = 0.3        # 0.3
    states = [
        MLCState(t=t0, body_id=0, position=np.zeros(3)),
        MLCState(t=t1, body_id=1, position=np.zeros(3)),
    ]
    bodies = {0: MLCBody(id=0, name="a"), 1: MLCBody(id=1, name="b")}
    timeline = build_timeline(_result_with(states, bodies))
    assert len(timeline.frames) == 1
    assert set(timeline.frames[0].states_by_body) == {0, 1}
