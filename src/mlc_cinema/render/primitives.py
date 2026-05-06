"""Renderer-agnostic primitive descriptions.

These small dataclasses describe the visual primitives used by the
placeholder viewport. They are deliberately backend-neutral so a future
pygfx (or any other) renderer can consume the same data structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class BodyMarker:
    """A single body's drawable representation at the current frame."""

    body_id: int
    position: np.ndarray
    quaternion: np.ndarray | None = None
    color: tuple[int, int, int] = (220, 220, 240)
    label: str = ""


@dataclass
class TrailLine:
    """An ordered polyline showing a body's recent positions."""

    body_id: int
    points: list[np.ndarray] = field(default_factory=list)
    color: tuple[int, int, int] = (110, 170, 220)
