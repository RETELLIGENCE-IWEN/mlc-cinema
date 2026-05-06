"""Tests for ``mlc_cinema.scene.transforms``."""

from __future__ import annotations

import math

import numpy as np
import pytest

from mlc_cinema.scene.transforms import (
    TransformError,
    normalize_quaternion,
    quaternion_wxyz_to_rotation_matrix,
)


def test_identity_quaternion_returns_identity_matrix() -> None:
    q = np.array([1.0, 0.0, 0.0, 0.0])
    R = quaternion_wxyz_to_rotation_matrix(q)
    np.testing.assert_allclose(R, np.eye(3), atol=1e-12)


def test_quaternion_normalization() -> None:
    q = np.array([2.0, 0.0, 0.0, 0.0])
    qn = normalize_quaternion(q)
    np.testing.assert_allclose(qn, [1.0, 0.0, 0.0, 0.0], atol=1e-12)
    assert np.linalg.norm(qn) == pytest.approx(1.0)


def test_normalize_unnormalized_quaternion() -> None:
    q = np.array([1.0, 1.0, 1.0, 1.0])
    qn = normalize_quaternion(q)
    assert np.linalg.norm(qn) == pytest.approx(1.0, rel=1e-12)


def test_near_zero_quaternion_raises() -> None:
    q = np.array([0.0, 0.0, 0.0, 0.0])
    with pytest.raises(TransformError):
        normalize_quaternion(q)
    with pytest.raises(TransformError):
        quaternion_wxyz_to_rotation_matrix(q)


def test_wrong_shape_quaternion_raises() -> None:
    with pytest.raises(TransformError):
        normalize_quaternion(np.array([1.0, 0.0, 0.0]))


def test_quaternion_180_about_z_flips_x_and_y() -> None:
    # Rotation by pi about +Z, scalar-first: q = [cos(pi/2), 0, 0, sin(pi/2)] = [0, 0, 0, 1]
    q = np.array([0.0, 0.0, 0.0, 1.0])
    R = quaternion_wxyz_to_rotation_matrix(q)
    expected = np.array(
        [
            [-1.0, 0.0, 0.0],
            [0.0, -1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    np.testing.assert_allclose(R, expected, atol=1e-12)


def test_quaternion_90_about_x_rotates_y_to_z() -> None:
    # Rotation by pi/2 about +X: q = [cos(pi/4), sin(pi/4), 0, 0]
    c = math.cos(math.pi / 4)
    s = math.sin(math.pi / 4)
    q = np.array([c, s, 0.0, 0.0])
    R = quaternion_wxyz_to_rotation_matrix(q)

    # Y axis (0,1,0) should map to Z axis (0,0,1).
    y = np.array([0.0, 1.0, 0.0])
    np.testing.assert_allclose(R @ y, np.array([0.0, 0.0, 1.0]), atol=1e-12)

    # Z axis (0,0,1) should map to -Y (0,-1,0).
    z = np.array([0.0, 0.0, 1.0])
    np.testing.assert_allclose(R @ z, np.array([0.0, -1.0, 0.0]), atol=1e-12)


def test_rotation_matrix_is_orthogonal() -> None:
    # A non-trivial quaternion.
    q = np.array([0.7071, 0.5, 0.5, 0.0])
    R = quaternion_wxyz_to_rotation_matrix(q)
    np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-9)
    assert np.linalg.det(R) == pytest.approx(1.0, abs=1e-9)
