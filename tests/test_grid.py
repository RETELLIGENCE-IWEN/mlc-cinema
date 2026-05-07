"""Tests for ``mlc_cinema.scene.grid``."""

from __future__ import annotations

import math

import numpy as np
import pytest

from mlc_cinema.scene.bounds import SceneBounds
from mlc_cinema.scene.grid import (
    GridSpec,
    grid_spec_from_bounds,
    nice_grid_step,
)


def test_nice_grid_step_returns_1_2_5_sequence() -> None:
    assert nice_grid_step(0.3) == pytest.approx(0.5)
    assert nice_grid_step(0.8) == pytest.approx(1.0)
    assert nice_grid_step(1.2) == pytest.approx(2.0)
    assert nice_grid_step(3.0) == pytest.approx(5.0)
    assert nice_grid_step(8.0) == pytest.approx(10.0)
    assert nice_grid_step(12.0) == pytest.approx(20.0)


def test_nice_grid_step_handles_subnormal_inputs() -> None:
    # Zero / negative / NaN should not crash; they fall back to 1.0.
    assert nice_grid_step(0.0) == 1.0
    assert nice_grid_step(-3.0) == 1.0
    assert nice_grid_step(math.nan) == 1.0


def _bounds(radius: float) -> SceneBounds:
    return SceneBounds(
        center=np.zeros(3, dtype=np.float64),
        extent=np.full(3, radius, dtype=np.float64),
        radius=float(radius),
    )


def test_grid_spec_from_bounds_has_positive_size_and_step() -> None:
    spec = grid_spec_from_bounds(_bounds(50.0))
    assert isinstance(spec, GridSpec)
    assert spec.half_size > 0.0
    assert spec.step > 0.0


def test_grid_spec_covers_bounds_radius() -> None:
    bounds = _bounds(50.0)
    spec = grid_spec_from_bounds(bounds)
    # Grid must comfortably cover 1.25× radius.
    assert spec.half_size >= bounds.radius * 1.25 - 1e-9


def test_grid_spec_line_count_reasonable() -> None:
    """For a wide range of bounds radii, the number of grid lines per
    axis should stay in a usable range — not 3 lines, not 500."""

    for radius in [1.0, 25.0, 100.0, 750.0, 12_345.0]:
        spec = grid_spec_from_bounds(_bounds(radius))
        lines_per_axis = (spec.half_size / spec.step) * 2.0 + 1.0
        assert 5.0 <= lines_per_axis <= 100.0, (
            f"radius={radius}: half={spec.half_size}, step={spec.step}, "
            f"lines={lines_per_axis}"
        )


def test_grid_spec_minimum_half_size_for_tiny_bounds() -> None:
    """Even a near-zero scene should get a usable grid."""

    spec = grid_spec_from_bounds(_bounds(0.1))
    assert spec.half_size >= 10.0


def test_grid_spec_step_is_a_nice_number() -> None:
    """The step itself should be a 1/2/5×10ⁿ value."""

    for radius in [3.0, 30.0, 300.0]:
        spec = grid_spec_from_bounds(_bounds(radius))
        # Reduce step to its [1, 10) mantissa.
        exp = math.floor(math.log10(spec.step))
        mantissa = spec.step / (10.0**exp)
        assert mantissa == pytest.approx(1.0) or mantissa == pytest.approx(2.0) \
            or mantissa == pytest.approx(5.0), (
                f"step={spec.step} mantissa={mantissa}"
            )
