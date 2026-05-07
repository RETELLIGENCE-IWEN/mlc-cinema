"""Tests for ``mlc_cinema.scene.attitude``.

All tests are deterministic and free of GUI / pygfx dependencies.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from mlc_cinema.scene.attitude import (
    NED_TO_VIEWER_MATRIX,
    body_to_ned_quaternion_to_body_to_viewer_wxyz,
    ned_to_viewer_quaternion_wxyz,
    normalize_quaternion_wxyz,
    quaternion_multiply_wxyz,
    quaternion_to_rotation_matrix_wxyz,
    rotate_vector_by_quaternion_wxyz,
    rotation_matrix_to_quaternion_wxyz,
)


# --- 10.1 -----------------------------------------------------------------

def test_ned_to_viewer_matrix_maps_basis_vectors() -> None:
    R = NED_TO_VIEWER_MATRIX
    np.testing.assert_allclose(R @ [1.0, 0.0, 0.0], [0.0, 1.0, 0.0])  # north → +Y_view
    np.testing.assert_allclose(R @ [0.0, 1.0, 0.0], [1.0, 0.0, 0.0])  # east  → +X_view
    np.testing.assert_allclose(R @ [0.0, 0.0, 1.0], [0.0, 0.0, -1.0])  # down  → -Z_view


# --- 10.2 -----------------------------------------------------------------

def test_ned_to_viewer_matrix_is_proper_rotation() -> None:
    R = NED_TO_VIEWER_MATRIX
    np.testing.assert_allclose(R.T @ R, np.eye(3), atol=1e-12)
    assert np.linalg.det(R) == pytest.approx(1.0, abs=1e-12)


# --- 10.3 -----------------------------------------------------------------

def test_ned_to_viewer_quaternion_matches_matrix() -> None:
    q = ned_to_viewer_quaternion_wxyz()
    R = NED_TO_VIEWER_MATRIX
    sample_vectors = [
        np.array([1.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([0.0, 0.0, 1.0]),
        np.array([1.0, 2.0, 3.0]),
        np.array([-3.5, 0.7, 12.0]),
    ]
    for v in sample_vectors:
        via_matrix = R @ v
        via_quat = rotate_vector_by_quaternion_wxyz(q, v)
        np.testing.assert_allclose(via_quat, via_matrix, atol=1e-12)


# --- 10.4 -----------------------------------------------------------------

def test_body_to_viewer_identity_body_attitude_equals_ned_to_viewer() -> None:
    q_body_to_ned_identity = np.array([1.0, 0.0, 0.0, 0.0])
    q_body_to_viewer = body_to_ned_quaternion_to_body_to_viewer_wxyz(
        q_body_to_ned_identity
    )
    np.testing.assert_allclose(
        q_body_to_viewer, ned_to_viewer_quaternion_wxyz(), atol=1e-12
    )


# --- 10.5 -----------------------------------------------------------------

def test_yaw_90_body_forward_points_viewer_x() -> None:
    """+90° yaw about NED-down should put body-forward at viewer +X.

    Aerospace convention:
      * body forward axis in body frame = ``[1, 0, 0]``
      * identity attitude → body forward points north in NED
      * positive yaw about NED-down is a clockwise rotation viewed from
        above, taking north → east

    So with ``q_body_to_ned`` = +90° yaw about NED-down, body forward
    should point east in NED. After NED→viewer that becomes +X_view.
    """

    half = math.pi / 4.0
    # Quaternion for rotation by +π/2 about NED-down axis (Z_ned = [0, 0, 1]).
    q_body_to_ned = np.array(
        [math.cos(half), 0.0, 0.0, math.sin(half)],
        dtype=np.float64,
    )
    q_body_to_viewer = body_to_ned_quaternion_to_body_to_viewer_wxyz(
        q_body_to_ned
    )
    body_forward = np.array([1.0, 0.0, 0.0])
    rotated = rotate_vector_by_quaternion_wxyz(q_body_to_viewer, body_forward)
    np.testing.assert_allclose(rotated, [1.0, 0.0, 0.0], atol=1e-12)


def test_pitch_up_90_body_forward_points_viewer_z() -> None:
    """+90° pitch (nose up) about NED-east should put body-forward at viewer +Z.

    Identity → body forward = north (NED). Rotating +90° about NED-east
    (Y_ned = [0, 1, 0], aerospace pitch axis) takes the forward vector
    from north to up — i.e. -Z_ned. After NED→viewer mapping that's
    +Z_view.
    """

    half = math.pi / 4.0
    q_body_to_ned = np.array(
        [math.cos(half), 0.0, math.sin(half), 0.0],
        dtype=np.float64,
    )
    q_body_to_viewer = body_to_ned_quaternion_to_body_to_viewer_wxyz(
        q_body_to_ned
    )
    body_forward = np.array([1.0, 0.0, 0.0])
    rotated = rotate_vector_by_quaternion_wxyz(q_body_to_viewer, body_forward)
    np.testing.assert_allclose(rotated, [0.0, 0.0, 1.0], atol=1e-12)


# --- 10.6 -----------------------------------------------------------------

def test_attitude_conversion_normalizes_quaternion() -> None:
    q_body_to_ned_unnormalized = 2.0 * np.array([1.0, 0.0, 0.0, 0.0])
    q_body_to_viewer = body_to_ned_quaternion_to_body_to_viewer_wxyz(
        q_body_to_ned_unnormalized
    )
    assert np.linalg.norm(q_body_to_viewer) == pytest.approx(1.0, abs=1e-12)


# --- 10.7 -----------------------------------------------------------------

def test_zero_quaternion_raises() -> None:
    with pytest.raises(ValueError):
        body_to_ned_quaternion_to_body_to_viewer_wxyz(np.zeros(4))
    with pytest.raises(ValueError):
        normalize_quaternion_wxyz(np.zeros(4))


# --- additional sanity checks --------------------------------------------

def test_quaternion_multiply_identity() -> None:
    q = np.array([math.cos(math.pi / 6), math.sin(math.pi / 6), 0.0, 0.0])
    identity = np.array([1.0, 0.0, 0.0, 0.0])
    np.testing.assert_allclose(quaternion_multiply_wxyz(identity, q), q)
    np.testing.assert_allclose(quaternion_multiply_wxyz(q, identity), q)


def test_rotation_matrix_to_quaternion_round_trips() -> None:
    R = NED_TO_VIEWER_MATRIX
    q = rotation_matrix_to_quaternion_wxyz(R)
    np.testing.assert_allclose(
        quaternion_to_rotation_matrix_wxyz(q), R, atol=1e-12
    )


def test_rotation_matrix_to_quaternion_for_ned_to_viewer() -> None:
    q = rotation_matrix_to_quaternion_wxyz(NED_TO_VIEWER_MATRIX)
    expected = ned_to_viewer_quaternion_wxyz()
    # Quaternion sign is ambiguous; allow either q or -q.
    if np.dot(q, expected) < 0.0:
        q = -q
    np.testing.assert_allclose(q, expected, atol=1e-12)


def test_rotate_vector_matches_matrix() -> None:
    # Random-ish quaternion, normalized.
    q = normalize_quaternion_wxyz(np.array([0.6, 0.2, -0.3, 0.5]))
    v = np.array([1.0, 2.0, -1.0])
    R = quaternion_to_rotation_matrix_wxyz(q)
    np.testing.assert_allclose(
        rotate_vector_by_quaternion_wxyz(q, v), R @ v, atol=1e-12
    )
