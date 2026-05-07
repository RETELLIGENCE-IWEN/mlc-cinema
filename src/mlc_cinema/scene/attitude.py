"""Attitude / quaternion frame conversion for the cinema viewer.

MLC v1 stores body attitude as ``q_body_to_NED``. Internally cinema
operates in a Z-up viewer frame; downstream renderers receive
``q_body_to_viewer`` and only need to perform backend-specific
ordering conversion (scalar-first ↔ scalar-last).

Frame definitions:

    NED:    +X = north, +Y = east, +Z = down
    Viewer: +X = east,  +Y = north, +Z = up

Therefore::

    R_ned_to_viewer · v_ned = v_viewer

with ``R_ned_to_viewer`` chosen so that

* ``[1, 0, 0]`` (north) → ``[0, 1, 0]`` (viewer +Y)
* ``[0, 1, 0]`` (east)  → ``[1, 0, 0]`` (viewer +X)
* ``[0, 0, 1]`` (down)  → ``[0, 0, -1]`` (viewer -Z)

The composition rule for body attitude is::

    q_body_to_viewer = q_ned_to_viewer ⊗ q_body_to_ned

where ``⊗`` is the Hamilton product (``q_body_to_ned`` applied first,
``q_ned_to_viewer`` applied second).

All quaternions in this module are scalar-first ``[w, x, y, z]``.
This module is renderer-agnostic; it imports ``numpy`` only.
"""

from __future__ import annotations

import numpy as np


# A norm below this is considered too close to zero to safely normalize.
_QUAT_NORM_EPSILON: float = 1e-12


# Basis-change matrix sending NED vectors to viewer-frame vectors.
# Orthonormal with determinant +1 (proper rotation, no reflection).
NED_TO_VIEWER_MATRIX = np.array(
    [
        [0.0, 1.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 0.0, -1.0],
    ],
    dtype=np.float64,
)


# ----- quaternion primitives ------------------------------------------------

def normalize_quaternion_wxyz(q: np.ndarray) -> np.ndarray:
    """Return ``q`` rescaled to unit length.

    Raises ``ValueError`` if ``q`` is not a 4-vector or its norm is too
    close to zero to be normalized meaningfully.
    """

    q_arr = np.asarray(q, dtype=np.float64)
    if q_arr.shape != (4,):
        raise ValueError(
            f"quaternion must be a 4-vector [w, x, y, z]; got shape {q_arr.shape}"
        )
    norm = float(np.linalg.norm(q_arr))
    if norm < _QUAT_NORM_EPSILON:
        raise ValueError(
            "cannot normalize a near-zero quaternion (norm < "
            f"{_QUAT_NORM_EPSILON})"
        )
    return q_arr / norm


def quaternion_multiply_wxyz(q2: np.ndarray, q1: np.ndarray) -> np.ndarray:
    """Hamilton product ``q2 ⊗ q1`` (apply ``q1`` first, then ``q2``).

    Composes rotations: rotating a vector by the result is equivalent
    to rotating it by ``q1`` then by ``q2``.
    """

    a = np.asarray(q2, dtype=np.float64)
    b = np.asarray(q1, dtype=np.float64)
    if a.shape != (4,) or b.shape != (4,):
        raise ValueError(
            f"quaternions must be shape (4,); got {a.shape} and {b.shape}"
        )
    w_a, x_a, y_a, z_a = a
    w_b, x_b, y_b, z_b = b
    return np.array(
        [
            w_a * w_b - x_a * x_b - y_a * y_b - z_a * z_b,
            w_a * x_b + x_a * w_b + y_a * z_b - z_a * y_b,
            w_a * y_b - x_a * z_b + y_a * w_b + z_a * x_b,
            w_a * z_b + x_a * y_b - y_a * x_b + z_a * w_b,
        ],
        dtype=np.float64,
    )


def quaternion_to_rotation_matrix_wxyz(q: np.ndarray) -> np.ndarray:
    """Return the 3x3 rotation matrix corresponding to scalar-first ``q``."""

    qn = normalize_quaternion_wxyz(q)
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


def rotation_matrix_to_quaternion_wxyz(r: np.ndarray) -> np.ndarray:
    """Return a scalar-first quaternion equivalent to the rotation matrix.

    Uses the standard Shepperd / Shoemake branch-by-largest-trace
    algorithm so it stays numerically stable for all rotations,
    including 180° cases.
    """

    R = np.asarray(r, dtype=np.float64)
    if R.shape != (3, 3):
        raise ValueError(f"rotation matrix must be (3, 3); got {R.shape}")

    trace = R[0, 0] + R[1, 1] + R[2, 2]
    if trace > 0.0:
        s = 2.0 * np.sqrt(trace + 1.0)
        w = 0.25 * s
        x = (R[2, 1] - R[1, 2]) / s
        y = (R[0, 2] - R[2, 0]) / s
        z = (R[1, 0] - R[0, 1]) / s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
        w = (R[2, 1] - R[1, 2]) / s
        x = 0.25 * s
        y = (R[0, 1] + R[1, 0]) / s
        z = (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
        w = (R[0, 2] - R[2, 0]) / s
        x = (R[0, 1] + R[1, 0]) / s
        y = 0.25 * s
        z = (R[1, 2] + R[2, 1]) / s
    else:
        s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
        w = (R[1, 0] - R[0, 1]) / s
        x = (R[0, 2] + R[2, 0]) / s
        y = (R[1, 2] + R[2, 1]) / s
        z = 0.25 * s
    return np.array([w, x, y, z], dtype=np.float64)


def rotate_vector_by_quaternion_wxyz(
    q: np.ndarray, v: np.ndarray
) -> np.ndarray:
    """Apply rotation ``q`` to vector ``v``."""

    R = quaternion_to_rotation_matrix_wxyz(q)
    v_arr = np.asarray(v, dtype=np.float64)
    if v_arr.shape != (3,):
        raise ValueError(f"vector must be shape (3,); got {v_arr.shape}")
    return R @ v_arr


# ----- frame conversion -----------------------------------------------------

def ned_to_viewer_quaternion_wxyz() -> np.ndarray:
    """Return the unit quaternion equivalent to ``NED_TO_VIEWER_MATRIX``.

    This is a 180° rotation about the bisector of the NED north & east
    axes. Closed-form: ``[0, 1/√2, 1/√2, 0]``.
    """

    s = 1.0 / np.sqrt(2.0)
    return np.array([0.0, s, s, 0.0], dtype=np.float64)


def body_to_ned_quaternion_to_body_to_viewer_wxyz(
    q_body_to_ned: np.ndarray,
) -> np.ndarray:
    """Convert a ``q_body_to_NED`` quaternion into ``q_body_to_viewer``.

    The composition rule is::

        q_body_to_viewer = q_ned_to_viewer ⊗ q_body_to_ned

    The result is normalized before return.
    """

    q_ned_to_viewer = ned_to_viewer_quaternion_wxyz()
    q_body_to_viewer = quaternion_multiply_wxyz(
        q_ned_to_viewer, q_body_to_ned
    )
    return normalize_quaternion_wxyz(q_body_to_viewer)
