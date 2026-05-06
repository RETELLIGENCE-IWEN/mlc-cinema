"""Dataclasses representing parsed MLC v1 records.

Quaternions use scalar-first convention: ``q = [w, x, y, z]``.

Internal positions/velocities on ``MLCState`` are already in
**viewer-frame** coordinates (right-handed, Z up). The decoder is
responsible for converting from MLC v1 NED into this frame; downstream
consumers (timeline, scene, render) do not re-interpret the values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


class MLCParseError(ValueError):
    """Raised when an MLC NDJSON file cannot be parsed."""


@dataclass(frozen=True)
class MLCHeader:
    """The single ``$=header`` record, if present."""

    format: int
    label: str | None = None
    producer: str | None = None
    mode: str | None = None
    scenario: str | None = None
    seed: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MLCBody:
    """A ``$=body`` record declaring an entity in the scene."""

    id: int
    name: str
    platform: str | None = None
    model: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MLCStep:
    """A ``$=step`` record. Subsequent untyped rows inherit ``t`` and ``index``."""

    index: int
    t: float
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MLCActionSpec:
    """A ``$=action_spec`` record declaring the layout of action samples."""

    id: int
    body_id: int | None
    fields: list[str]
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MLCRewardSpec:
    """A ``$=reward_spec`` record declaring the layout of reward samples."""

    id: int
    body_id: int | None
    fields: list[str]
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MLCState:
    """Decoded body state at one timestamp, in viewer-frame coordinates.

    Position/velocity are already converted from NED to the cinema
    viewer frame (``x = pe, y = pn, z = -pd``). ``altitude_m`` carries
    the geodetic altitude from MLC v1 ``x[2]``; the renderer's vertical
    axis still uses ``position[2]`` (= ``-pd_m``).
    """

    t: float
    body_id: int
    position: np.ndarray
    velocity: np.ndarray | None = None
    quaternion: np.ndarray | None = None
    angular_velocity: np.ndarray | None = None
    step_index: int | None = None
    altitude_m: float | None = None
    source_format: str = "unknown"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MLCActionSample:
    """One action vector at a step (compact ``{"a":..., "x":[...]}`` row)."""

    t: float
    spec_id: int
    values: np.ndarray
    step_index: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MLCRewardSample:
    """One reward vector at a step (compact ``{"r":..., "x":[...]}`` row)."""

    t: float
    spec_id: int
    values: np.ndarray
    step_index: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MLCEvent:
    """An ``$=event`` record (touchdown, stage separation, etc.)."""

    t: float | None
    topic: str
    body_id: int | None = None
    data: dict[str, Any] = field(default_factory=dict)
    step_index: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class MLCParseResult:
    """Result of parsing one MLC NDJSON file."""

    header: MLCHeader | None
    bodies: dict[int, MLCBody]
    states: list[MLCState]
    steps: list[MLCStep] = field(default_factory=list)
    action_specs: dict[int, MLCActionSpec] = field(default_factory=dict)
    reward_specs: dict[int, MLCRewardSpec] = field(default_factory=dict)
    action_samples: list[MLCActionSample] = field(default_factory=list)
    reward_samples: list[MLCRewardSample] = field(default_factory=list)
    events: list[MLCEvent] = field(default_factory=list)
    unknown_records: list[dict[str, Any]] = field(default_factory=list)
