"""Dataclasses representing parsed MLC records.

Quaternions use scalar-first convention: ``q = [w, x, y, z]``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


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
class MLCState:
    """A ``$=state`` record for a body at one timestamp.

    Quaternions, when present, follow the scalar-first convention
    ``[w, x, y, z]``.
    """

    t: float
    body_id: int
    position: np.ndarray
    velocity: np.ndarray | None = None
    quaternion: np.ndarray | None = None
    angular_velocity: np.ndarray | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class MLCParseResult:
    """Result of parsing one MLC NDJSON file."""

    header: MLCHeader | None
    bodies: dict[int, MLCBody]
    states: list[MLCState]
    unknown_records: list[dict[str, Any]] = field(default_factory=list)
