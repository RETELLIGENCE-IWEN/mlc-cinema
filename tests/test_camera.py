"""Tests for ``mlc_cinema.scene.camera``."""

from __future__ import annotations

import math

import numpy as np
import pytest

from mlc_cinema.scene.bounds import SceneBounds
from mlc_cinema.scene.camera import (
    OrbitCameraState,
    clamp_pitch,
    frame_bounds,
    orbit,
    orbit_camera_position,
    pan,
    zoom,
)


def test_orbit_camera_position_has_expected_distance() -> None:
    state = OrbitCameraState(
        target=np.zeros(3),
        distance=50.0,
        yaw_rad=0.0,
        pitch_rad=0.0,
    )
    pos = orbit_camera_position(state)
    # yaw=0 pitch=0 → camera offset along +X.
    np.testing.assert_allclose(pos, [50.0, 0.0, 0.0])
    assert np.linalg.norm(pos - state.target) == pytest.approx(50.0)


def test_orbit_camera_position_pitched_up_lifts_z() -> None:
    state = OrbitCameraState(
        target=np.zeros(3),
        distance=10.0,
        yaw_rad=0.0,
        pitch_rad=math.radians(45.0),
    )
    pos = orbit_camera_position(state)
    expected = 10.0 * np.array(
        [math.cos(math.pi / 4), 0.0, math.sin(math.pi / 4)]
    )
    np.testing.assert_allclose(pos, expected, atol=1e-12)


def test_orbit_camera_position_offset_target_translates() -> None:
    state = OrbitCameraState(
        target=np.array([100.0, 200.0, 5.0]),
        distance=20.0,
        yaw_rad=0.0,
        pitch_rad=0.0,
    )
    pos = orbit_camera_position(state)
    np.testing.assert_allclose(pos, [120.0, 200.0, 5.0])


def test_orbit_camera_pitch_is_clamped() -> None:
    # Pushing past +π/2 should be clamped strictly inside.
    state = OrbitCameraState(distance=1.0, pitch_rad=math.pi)
    pos = orbit_camera_position(state)
    # If pitch were unclamped, sin(π) = 0 and we'd see no Z. With
    # clamping, pitch is just under π/2 so Z component is nearly equal
    # to the distance.
    assert abs(pos[2]) > 0.99


def test_clamp_pitch_extremes() -> None:
    assert -math.pi / 2 < clamp_pitch(-math.pi) < 0.0
    assert 0.0 < clamp_pitch(math.pi) < math.pi / 2


def test_orbit_applies_deltas() -> None:
    state = OrbitCameraState(distance=10.0, yaw_rad=0.0, pitch_rad=0.0)
    after = orbit(state, math.radians(90), math.radians(30))
    assert after.yaw_rad == pytest.approx(math.radians(90))
    assert after.pitch_rad == pytest.approx(math.radians(30))


def test_zoom_multiplies_distance_with_floor() -> None:
    state = OrbitCameraState(distance=10.0)
    z_in = zoom(state, 0.5)
    assert z_in.distance == pytest.approx(5.0)
    z_zero = zoom(state, 0.0)
    assert z_zero.distance > 0.0  # never goes to zero


def test_pan_translates_target_along_view_plane() -> None:
    state = OrbitCameraState(
        target=np.zeros(3), distance=10.0, yaw_rad=0.0, pitch_rad=0.0
    )
    panned = pan(state, dx_world=1.0, dy_world=2.0)
    # With yaw=pitch=0 the camera sits on +X looking back to origin.
    # forward = (-1, 0, 0), world up = (0, 0, 1) → right = forward × up = (0, 1, 0).
    # up_view = right × forward = (0, 0, 1). So target moves by (0, 1, 2).
    np.testing.assert_allclose(panned.target, [0.0, 1.0, 2.0], atol=1e-12)


def test_frame_bounds_distance_grows_with_radius() -> None:
    small = SceneBounds(np.zeros(3), np.ones(3), radius=5.0)
    big = SceneBounds(np.zeros(3), np.ones(3), radius=500.0)
    s = frame_bounds(small)
    b = frame_bounds(big)
    assert b.distance > s.distance
    np.testing.assert_allclose(s.target, [0.0, 0.0, 0.0])


def test_frame_bounds_centers_target_on_bounds_center() -> None:
    bounds = SceneBounds(
        center=np.array([10.0, 20.0, 30.0]),
        extent=np.ones(3),
        radius=8.0,
    )
    state = frame_bounds(bounds)
    np.testing.assert_allclose(state.target, [10.0, 20.0, 30.0])
