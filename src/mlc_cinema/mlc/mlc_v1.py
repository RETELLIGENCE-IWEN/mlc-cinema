"""Maneuver Log Contract v1 — fundamental maneuver state vector.

The 28-element ``x`` vector that follows a ``$=step`` record in MLC v1
has a fixed layout. This module defines the layout as named indices
(no magic numbers in the reader) and provides ``decode_mlc_v1_body_state``
to turn one compact ``{"b":..., "x":[...]}`` row into an ``MLCState``.

Coordinate conversion:
    MLC v1 uses a local NED frame.
    Cinema's internal viewer frame is right-handed with Z up:
        x_view =  pe_m
        y_view =  pn_m
        z_view = -pd_m
    Velocities convert the same way.
    Attitudes are converted from ``q_body_to_NED`` to
    ``q_body_to_viewer`` (see ``mlc_cinema.scene.attitude``); downstream
    consumers receive a viewer-frame body quaternion only.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from mlc_cinema.mlc.records import MLCParseError, MLCState, MLCStep
from mlc_cinema.scene.attitude import (
    body_to_ned_quaternion_to_body_to_viewer_wxyz,
)


SOURCE_FORMAT: str = "mlc_v1"
MLC_V1_STATE_LEN: int = 28

# --- field indices into the 28-vector x ---
IDX_LAT_RAD = 0
IDX_LON_RAD = 1
IDX_ALT_M = 2
IDX_PN_M = 3
IDX_PE_M = 4
IDX_PD_M = 5
IDX_VN_MPS = 6
IDX_VE_MPS = 7
IDX_VD_MPS = 8
IDX_U_MPS = 9
IDX_V_MPS = 10
IDX_W_MPS = 11
IDX_QW = 12
IDX_QX = 13
IDX_QY = 14
IDX_QZ = 15
IDX_ROLL_RAD = 16
IDX_PITCH_RAD = 17
IDX_YAW_RAD = 18
IDX_P_RADPS = 19
IDX_Q_RADPS = 20
IDX_R_RADPS = 21
IDX_AN_MPS2 = 22
IDX_AE_MPS2 = 23
IDX_AD_MPS2 = 24
IDX_AX_BODY_MPS2 = 25
IDX_AY_BODY_MPS2 = 26
IDX_AZ_BODY_MPS2 = 27


def decode_mlc_v1_body_state(
    record: dict[str, Any],
    current_step: MLCStep | None,
    *,
    location: str = "",
) -> MLCState:
    """Decode one compact MLC v1 body state row into an ``MLCState``.

    ``location`` is prepended to error messages (e.g. ``"Line 12 of foo: "``)
    so callers can report file context without this module knowing about it.
    """

    body_id = record.get("b")
    if not isinstance(body_id, int):
        raise MLCParseError(
            f"{location}MLC v1 body state row requires integer 'b'"
        )

    x_raw = record.get("x")
    if not isinstance(x_raw, list):
        raise MLCParseError(
            f"{location}MLC v1 body state row requires list 'x'"
        )
    if len(x_raw) != MLC_V1_STATE_LEN:
        raise MLCParseError(
            f"{location}MLC v1 body state vector x must contain exactly "
            f"{MLC_V1_STATE_LEN} values, got {len(x_raw)}"
        )

    try:
        x = np.asarray(x_raw, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise MLCParseError(
            f"{location}MLC v1 body state vector x is not numeric"
        ) from exc

    # --- timestamp: explicit 't' wins; otherwise inherit from step ---
    explicit_t = record.get("t")
    if explicit_t is None:
        if current_step is None:
            raise MLCParseError(
                f"{location}MLC v1 body state row requires an active step "
                f"or explicit 't'"
            )
        t = current_step.t
    elif isinstance(explicit_t, (int, float)):
        t = float(explicit_t)
    else:
        raise MLCParseError(
            f"{location}MLC v1 body state row 't' must be numeric"
        )

    # --- step index: explicit 's' wins; otherwise inherit from step ---
    explicit_s = record.get("s")
    if explicit_s is None:
        step_index = current_step.index if current_step is not None else None
    elif isinstance(explicit_s, int):
        step_index = explicit_s
    else:
        raise MLCParseError(
            f"{location}MLC v1 body state row 's' must be an integer"
        )

    # NED -> viewer-frame conversion. Position and velocity components
    # are reordered to (east, north, up).
    position = np.array(
        [x[IDX_PE_M], x[IDX_PN_M], -x[IDX_PD_M]],
        dtype=np.float64,
    )
    velocity = np.array(
        [x[IDX_VE_MPS], x[IDX_VN_MPS], -x[IDX_VD_MPS]],
        dtype=np.float64,
    )
    # MLC v1 stores q_body_to_ned. Cinema state stores q_body_to_viewer.
    q_body_to_ned = np.array(
        [x[IDX_QW], x[IDX_QX], x[IDX_QY], x[IDX_QZ]],
        dtype=np.float64,
    )
    try:
        quaternion = body_to_ned_quaternion_to_body_to_viewer_wxyz(
            q_body_to_ned
        )
    except ValueError as exc:
        raise MLCParseError(
            f"{location}body state has invalid quaternion: {exc}"
        ) from exc
    angular_velocity = np.array(
        [x[IDX_P_RADPS], x[IDX_Q_RADPS], x[IDX_R_RADPS]],
        dtype=np.float64,
    )
    altitude_m = float(x[IDX_ALT_M])

    return MLCState(
        t=float(t),
        body_id=body_id,
        position=position,
        velocity=velocity,
        quaternion=quaternion,
        angular_velocity=angular_velocity,
        step_index=step_index,
        altitude_m=altitude_m,
        source_format=SOURCE_FORMAT,
        raw=dict(record),
    )
