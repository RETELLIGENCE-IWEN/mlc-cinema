"""Tests for ``mlc_cinema.mlc.reader``."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pytest

from mlc_cinema.mlc.reader import MLCParseError, read_mlc_ndjson


EXAMPLE = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "logs"
    / "minimal_demo.mlc.ndjson"
)


def test_minimal_log_can_be_read() -> None:
    result = read_mlc_ndjson(EXAMPLE)
    assert result is not None


def test_minimal_log_header_is_parsed() -> None:
    result = read_mlc_ndjson(EXAMPLE)
    assert result.header is not None
    assert result.header.format == 1
    assert result.header.label == "minimal_demo"
    assert result.header.producer == "mlc-cinema-example"
    assert result.header.scenario == "single_body_demo"
    assert result.header.seed == 1


def test_minimal_log_body_is_parsed() -> None:
    result = read_mlc_ndjson(EXAMPLE)
    assert 0 in result.bodies
    body = result.bodies[0]
    assert body.id == 0
    assert body.name == "rocket_0"
    assert body.platform == "rocket"
    assert body.model == "generic_vtv_booster"


def test_minimal_log_state_count() -> None:
    result = read_mlc_ndjson(EXAMPLE)
    assert len(result.states) == 5


def test_state_position_is_numpy_array() -> None:
    result = read_mlc_ndjson(EXAMPLE)
    s0 = result.states[0]
    assert isinstance(s0.position, np.ndarray)
    assert s0.position.shape == (3,)
    np.testing.assert_allclose(s0.position, [0.0, 0.0, 100.0])

    assert isinstance(s0.velocity, np.ndarray)
    np.testing.assert_allclose(s0.velocity, [0.0, 0.0, -10.0])

    assert isinstance(s0.quaternion, np.ndarray)
    assert s0.quaternion.shape == (4,)
    np.testing.assert_allclose(s0.quaternion, [1.0, 0.0, 0.0, 0.0])


def test_unknown_record_does_not_crash(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    log_path = tmp_path / "with_unknown.mlc.ndjson"
    lines = [
        {"$": "header", "format": 1},
        {"$": "body", "id": 0, "name": "a"},
        {"$": "state", "t": 0.0, "b": 0, "p": [0.0, 0.0, 0.0]},
        {"$": "totally_unknown_kind", "payload": [1, 2, 3]},
        {"$": "metric", "t": 0.0, "name": "ignored_in_m0", "value": 42.0},
    ]
    log_path.write_text(
        "\n".join(json.dumps(rec) for rec in lines), encoding="utf-8"
    )

    with caplog.at_level(logging.WARNING, logger="mlc_cinema.mlc.reader"):
        result = read_mlc_ndjson(log_path)

    assert len(result.states) == 1
    # Unknown records should be retained for future use; recognised
    # optional types like "metric" are kept but not warned about.
    assert any(
        rec.get("$") == "totally_unknown_kind" for rec in result.unknown_records
    )
    # Exactly one warning for the genuinely-unknown record kind.
    unknown_warnings = [
        r for r in caplog.records if "Unknown MLC record type" in r.getMessage()
    ]
    assert len(unknown_warnings) == 1


def test_skips_blank_lines(tmp_path: Path) -> None:
    log_path = tmp_path / "with_blanks.mlc.ndjson"
    log_path.write_text(
        "\n".join(
            [
                "",
                json.dumps({"$": "header", "format": 1}),
                "",
                json.dumps({"$": "body", "id": 0, "name": "x"}),
                json.dumps({"$": "state", "t": 0.0, "b": 0, "p": [0, 0, 0]}),
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    result = read_mlc_ndjson(log_path)
    assert result.header is not None
    assert len(result.states) == 1


def test_malformed_json_raises(tmp_path: Path) -> None:
    log_path = tmp_path / "bad.mlc.ndjson"
    log_path.write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(MLCParseError):
        read_mlc_ndjson(log_path)


def test_state_missing_required_field_raises(tmp_path: Path) -> None:
    log_path = tmp_path / "missing_p.mlc.ndjson"
    log_path.write_text(
        json.dumps({"$": "state", "t": 0.0, "b": 0}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(MLCParseError):
        read_mlc_ndjson(log_path)


def test_missing_dollar_field_raises(tmp_path: Path) -> None:
    log_path = tmp_path / "no_kind.mlc.ndjson"
    log_path.write_text(json.dumps({"format": 1}) + "\n", encoding="utf-8")
    with pytest.raises(MLCParseError):
        read_mlc_ndjson(log_path)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(MLCParseError):
        read_mlc_ndjson(tmp_path / "does_not_exist.mlc.ndjson")
