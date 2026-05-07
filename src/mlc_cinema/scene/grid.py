"""Ground grid sizing helpers.

Picks a "nice" grid step (1, 2, 5 × 10ⁿ) and a ``half_size`` that
covers the scene comfortably. Used to rebuild the pygfx ground grid
each time a new timeline is loaded.

Backend-agnostic: pure NumPy / math.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from mlc_cinema.scene.bounds import SceneBounds


# Tunables for ``grid_spec_from_bounds``.
_TARGET_LINES_PER_HALF_AXIS: int = 10
_BOUNDS_PADDING: float = 1.25
_MIN_HALF_SIZE: float = 10.0
_MAX_HALF_SIZE: float = 1.0e6  # avoid runaway grids on degenerate input


@dataclass(frozen=True)
class GridSpec:
    """Grid extent and tick spacing, both in viewer-frame metres."""

    half_size: float
    step: float


def nice_grid_step(x: float) -> float:
    """Round ``x`` *up* to the next 1, 2, or 5 × 10ⁿ.

    Examples::

        0.3  → 0.5
        0.8  → 1.0
        1.2  → 2.0
        3.0  → 5.0
        8.0  → 10.0
        12.0 → 20.0
    """

    xv = float(x)
    if not math.isfinite(xv) or xv <= 0.0:
        return 1.0

    exp = math.floor(math.log10(xv))
    base = 10.0**exp
    fraction = xv / base  # in [1, 10)
    if fraction <= 1.0 + 1e-12:
        nice = 1.0
    elif fraction <= 2.0 + 1e-12:
        nice = 2.0
    elif fraction <= 5.0 + 1e-12:
        nice = 5.0
    else:
        nice = 10.0
    return nice * base


def grid_spec_from_bounds(bounds: SceneBounds) -> GridSpec:
    """Return a :class:`GridSpec` that comfortably covers ``bounds``.

    * ``half_size`` is at least ``_MIN_HALF_SIZE`` and at least
      ``bounds.radius * _BOUNDS_PADDING``.
    * ``step`` is a 1/2/5×10ⁿ value targeting ~10 lines per half-axis,
      so total lines per axis stays in a usable range (≈ 20–40).
    * ``half_size`` is rounded up to a multiple of ``step`` so
      grid lines land on whole-step coordinates.
    """

    desired_half = max(_MIN_HALF_SIZE, float(bounds.radius) * _BOUNDS_PADDING)
    desired_half = min(desired_half, _MAX_HALF_SIZE)

    raw_step = desired_half / float(_TARGET_LINES_PER_HALF_AXIS)
    step = nice_grid_step(raw_step)

    # Round half_size up to a multiple of the step.
    half_size = math.ceil(desired_half / step) * step
    return GridSpec(half_size=float(half_size), step=float(step))
