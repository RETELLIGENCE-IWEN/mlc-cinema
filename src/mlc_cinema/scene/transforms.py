"""Quaternion / rotation utilities.

Quaternions throughout mlc-cinema are scalar-first: ``q = [w, x, y, z]``.
"""

from __future__ import annotations

import numpy as np


class TransformError(ValueError):
    """Raised on degenerate transform inputs (e.g. a near-zero quaternion)."""


_QUAT_NORM_EPSILON: float = 1e-12


def normalize_quaternion(q: np.ndarray) -> np.ndarray:
    """Return the unit quaternion corresponding to ``q``.

    Raises ``TransformError`` if ``q`` is too close to zero to be
    meaningfully normalized.
    """

    q_arr = np.asarray(q, dtype=np.float64)
    if q_arr.shape != (4,):
        raise TransformError(
            f"Quaternion must be a 4-vector [w, x, y, z]; got shape {q_arr.shape}"
        )

    norm = float(np.linalg.norm(q_arr))
    if norm < _QUAT_NORM_EPSILON:
        raise TransformError(
            "Cannot normalize a near-zero quaternion (norm < "
            f"{_QUAT_NORM_EPSILON})"
        )
    return q_arr / norm


def quaternion_wxyz_to_rotation_matrix(q: np.ndarray) -> np.ndarray:
    """Convert a scalar-first quaternion ``[w, x, y, z]`` to a 3x3 rotation matrix."""

    qn = normalize_quaternion(q)
    w, x, y, z = qn

    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z

    return np.array(
        [
            [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz),       2.0 * (xz + wy)],
            [2.0 * (xy + wz),       1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
            [2.0 * (xz - wy),       2.0 * (yz + wx),       1.0 - 2.0 * (xx + yy)],
        ],
        dtype=np.float64,
    )
