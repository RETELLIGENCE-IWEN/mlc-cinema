"""Tests for ``mlc_cinema.mlc.reader`` against canonical MLC v1."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pytest

from mlc_cinema.mlc.mlc_v1 import MLC_V1_STATE_LEN
from mlc_cinema.mlc.reader import read_mlc_ndjson
from mlc_cinema.mlc.records import MLCParseError


_EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "logs"
EXAMPLE_V1 = _EXAMPLES / "minimal_demo_v1.mlc.ndjson"
EXAMPLE_MULTIBODY = _EXAMPLES / "multibody_demo_v1.mlc.ndjson"
EXAMPLE_ARE = _EXAMPLES / "action_reward_event_demo_v1.mlc.ndjson"


def _zeros28() -> list[float]:
    return [0.0] * MLC_V1_STATE_LEN


def _write_log(tmp_path: Path, name: str, records: list[dict]) -> Path:
    p = tmp_path / name
    p.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )
    return p


# --- example file ----------------------------------------------------------

def test_example_v1_log_can_be_read() -> None:
    result = read_mlc_ndjson(EXAMPLE_V1)
    assert result is not None


def test_example_v1_header_is_parsed() -> None:
    result = read_mlc_ndjson(EXAMPLE_V1)
    assert result.header is not None
    assert result.header.format == 1
    assert result.header.label == "minimal_demo_v1"
    assert result.header.scenario == "single_body_mlc_v1_demo"


def test_example_v1_body_is_parsed() -> None:
    result = read_mlc_ndjson(EXAMPLE_V1)
    body = result.bodies[0]
    assert body.id == 0
    assert body.name == "rocket_0"
    assert body.platform == "rocket"
    assert body.model == "generic_vtv_booster"


def test_example_v1_step_count() -> None:
    result = read_mlc_ndjson(EXAMPLE_V1)
    assert len(result.steps) == 5
    assert [s.t for s in result.steps] == [0.0, 0.5, 1.0, 1.5, 2.0]
    assert [s.index for s in result.steps] == [0, 1, 2, 3, 4]


def test_example_v1_state_count() -> None:
    result = read_mlc_ndjson(EXAMPLE_V1)
    assert len(result.states) == 5


def test_example_v1_action_samples_collected() -> None:
    result = read_mlc_ndjson(EXAMPLE_V1)
    assert len(result.action_samples) == 5
    a0 = result.action_samples[0]
    assert a0.spec_id == 0
    assert a0.step_index == 0
    assert a0.values.shape == (6,)
    np.testing.assert_allclose(
        a0.values, [0.0, 0.0, 1.0, 0.70, 0.0, 0.0]
    )


def test_example_v1_action_spec_collected() -> None:
    result = read_mlc_ndjson(EXAMPLE_V1)
    assert 0 in result.action_specs
    spec = result.action_specs[0]
    assert spec.body_id == 0
    assert spec.fields[0] == "raw_action_0"
    assert spec.fields[3] == "throttle_cmd"


def test_example_v1_event_collected() -> None:
    result = read_mlc_ndjson(EXAMPLE_V1)
    assert len(result.events) == 1
    ev = result.events[0]
    assert ev.topic == "demo_end"
    assert ev.body_id == 0
    assert ev.data == {"reason": "minimal_mlc_v1_demo_complete"}


# --- v1 body state decoding -----------------------------------------------

def test_reader_parses_mlc_v1_step_scoped_body_states() -> None:
    """Times and step indices are inherited from the most recent step."""

    result = read_mlc_ndjson(EXAMPLE_V1)
    assert len(result.states) == 5
    s0 = result.states[0]

    # Time inherited from step s=0, t=0.0.
    assert s0.t == 0.0
    assert s0.step_index == 0

    # Position decoded as [pe, pn, -pd] from x[4], x[3], -x[5].
    np.testing.assert_allclose(s0.position, [0.0, 0.0, 100.0])

    # Velocity decoded as [ve, vn, -vd] from x[7], x[6], -x[8].
    np.testing.assert_allclose(s0.velocity, [0.0, 0.0, -10.0])

    # Quaternion taken verbatim from x[12:16].
    np.testing.assert_allclose(s0.quaternion, [1.0, 0.0, 0.0, 0.0])

    # Altitude_m taken verbatim from x[2].
    assert s0.altitude_m == 220.0

    # Source format tagged.
    assert s0.source_format == "mlc_v1"

    # Subsequent state inherits its later step's time.
    s1 = result.states[1]
    assert s1.t == 0.5
    assert s1.step_index == 1
    np.testing.assert_allclose(s1.position, [0.0, 0.0, 95.25])
    assert s1.altitude_m == 215.25


def test_v1_explicit_t_overrides_step(tmp_path: Path) -> None:
    log = tmp_path / "explicit_t.mlc.ndjson"
    log.write_text(
        "\n".join(
            [
                json.dumps({"$": "header", "format": 1}),
                json.dumps({"$": "body", "id": 0, "name": "b"}),
                json.dumps({"$": "step", "s": 0, "t": 0.0}),
                json.dumps(
                    {"b": 0, "t": 7.5, "s": 99, "x": _zeros28()}
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    result = read_mlc_ndjson(log)
    assert len(result.states) == 1
    s = result.states[0]
    assert s.t == 7.5
    assert s.step_index == 99


# --- error paths ----------------------------------------------------------

def test_mlc_v1_body_state_without_step_or_explicit_time_raises(
    tmp_path: Path,
) -> None:
    log = tmp_path / "no_step.mlc.ndjson"
    log.write_text(
        "\n".join(
            [
                json.dumps({"$": "header", "format": 1, "label": "bad"}),
                json.dumps({"$": "body", "id": 0, "name": "body_0"}),
                json.dumps({"b": 0, "x": _zeros28()}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(MLCParseError, match="active step or explicit"):
        read_mlc_ndjson(log)


def test_mlc_v1_body_state_requires_28_values(tmp_path: Path) -> None:
    log = tmp_path / "short_x.mlc.ndjson"
    log.write_text(
        "\n".join(
            [
                json.dumps({"$": "header", "format": 1}),
                json.dumps({"$": "step", "s": 0, "t": 0.0}),
                json.dumps({"b": 0, "x": [1.0, 2.0, 3.0]}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(MLCParseError, match="28 values, got 3"):
        read_mlc_ndjson(log)


def test_untyped_row_without_known_compact_pattern_raises(
    tmp_path: Path,
) -> None:
    log = tmp_path / "weird_untyped.mlc.ndjson"
    # No "$"; not b/x, a/x, or r/x — should be a parse error.
    log.write_text(json.dumps({"format": 1}) + "\n", encoding="utf-8")
    with pytest.raises(MLCParseError, match="not a known compact row"):
        read_mlc_ndjson(log)


def test_malformed_json_raises(tmp_path: Path) -> None:
    log = tmp_path / "bad.mlc.ndjson"
    log.write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(MLCParseError, match="Malformed JSON"):
        read_mlc_ndjson(log)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(MLCParseError, match="not found"):
        read_mlc_ndjson(tmp_path / "does_not_exist.mlc.ndjson")


# --- robustness -----------------------------------------------------------

def test_unknown_typed_record_does_not_crash(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    log = tmp_path / "with_unknown_typed.mlc.ndjson"
    log.write_text(
        "\n".join(
            [
                json.dumps({"$": "header", "format": 1}),
                json.dumps({"$": "body", "id": 0, "name": "x"}),
                json.dumps({"$": "step", "s": 0, "t": 0.0}),
                json.dumps({"b": 0, "x": _zeros28()}),
                json.dumps({"$": "totally_unknown_kind", "payload": [1, 2, 3]}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="mlc_cinema.mlc.reader"):
        result = read_mlc_ndjson(log)

    assert len(result.states) == 1
    assert any(
        rec.get("$") == "totally_unknown_kind"
        for rec in result.unknown_records
    )
    unknown_warnings = [
        r for r in caplog.records if "Unknown MLC record type" in r.getMessage()
    ]
    assert len(unknown_warnings) == 1


def test_skips_blank_lines(tmp_path: Path) -> None:
    log = tmp_path / "with_blanks.mlc.ndjson"
    log.write_text(
        "\n".join(
            [
                "",
                json.dumps({"$": "header", "format": 1}),
                "",
                json.dumps({"$": "body", "id": 0, "name": "x"}),
                json.dumps({"$": "step", "s": 0, "t": 0.0}),
                "",
                json.dumps({"b": 0, "x": _zeros28()}),
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    result = read_mlc_ndjson(log)
    assert result.header is not None
    assert len(result.states) == 1


# --- M0.6 hardening -------------------------------------------------------

def test_reader_parses_multibody_mlc_v1() -> None:
    result = read_mlc_ndjson(EXAMPLE_MULTIBODY)
    assert set(result.bodies.keys()) == {0, 1}
    assert result.bodies[0].platform == "rocket"
    assert result.bodies[1].platform == "quadcopter"
    assert len(result.steps) == 4
    assert len(result.states) == 8  # 2 bodies * 4 steps
    # Both bodies are present at the first step.
    s0_states = [s for s in result.states if s.t == 0.0]
    assert {s.body_id for s in s0_states} == {0, 1}


def test_reader_parses_action_reward_event_demo() -> None:
    result = read_mlc_ndjson(EXAMPLE_ARE)
    assert len(result.action_specs) == 1
    assert len(result.reward_specs) == 1
    assert len(result.action_samples) == 4
    assert len(result.reward_samples) == 4
    assert len(result.events) == 2
    topics = sorted(e.topic for e in result.events)
    assert topics == ["engine_ignite", "max_q"]


def test_reader_validates_action_sample_length(tmp_path: Path) -> None:
    log = _write_log(
        tmp_path,
        "bad_action_len.mlc.ndjson",
        [
            {"$": "header", "format": 1, "label": "bad"},
            {"$": "body", "id": 0, "name": "body_0"},
            {"$": "action_spec", "id": 0, "b": 0, "fields": ["a0", "a1"]},
            {"$": "step", "s": 0, "t": 0.0},
            {"a": 0, "x": [1.0]},
        ],
    )
    with pytest.raises(MLCParseError, match="action sample x length"):
        read_mlc_ndjson(log)


def test_reader_validates_reward_sample_length(tmp_path: Path) -> None:
    log = _write_log(
        tmp_path,
        "bad_reward_len.mlc.ndjson",
        [
            {"$": "header", "format": 1},
            {"$": "body", "id": 0, "name": "b"},
            {
                "$": "reward_spec",
                "id": 0,
                "b": 0,
                "fields": ["step_reward", "fuel"],
            },
            {"$": "step", "s": 0, "t": 0.0},
            {"r": 0, "x": [0.5]},
        ],
    )
    with pytest.raises(MLCParseError, match="reward sample x length"):
        read_mlc_ndjson(log)


def test_reader_rejects_unknown_action_spec_id(tmp_path: Path) -> None:
    log = _write_log(
        tmp_path,
        "unknown_action_spec.mlc.ndjson",
        [
            {"$": "header", "format": 1},
            {"$": "body", "id": 0, "name": "b"},
            {"$": "step", "s": 0, "t": 0.0},
            {"a": 99, "x": [1.0, 2.0]},
        ],
    )
    with pytest.raises(MLCParseError, match="unknown action_spec id"):
        read_mlc_ndjson(log)


def test_reader_rejects_unknown_reward_spec_id(tmp_path: Path) -> None:
    log = _write_log(
        tmp_path,
        "unknown_reward_spec.mlc.ndjson",
        [
            {"$": "header", "format": 1},
            {"$": "body", "id": 0, "name": "b"},
            {"$": "step", "s": 0, "t": 0.0},
            {"r": 7, "x": [0.5]},
        ],
    )
    with pytest.raises(MLCParseError, match="unknown reward_spec id"):
        read_mlc_ndjson(log)


def test_reader_rejects_duplicate_body_id(tmp_path: Path) -> None:
    log = _write_log(
        tmp_path,
        "dup_body.mlc.ndjson",
        [
            {"$": "header", "format": 1},
            {"$": "body", "id": 0, "name": "first"},
            {"$": "body", "id": 0, "name": "second"},
        ],
    )
    with pytest.raises(MLCParseError, match="duplicate body id"):
        read_mlc_ndjson(log)


def test_reader_rejects_duplicate_step_index(tmp_path: Path) -> None:
    log = _write_log(
        tmp_path,
        "dup_step.mlc.ndjson",
        [
            {"$": "header", "format": 1},
            {"$": "body", "id": 0, "name": "b"},
            {"$": "step", "s": 0, "t": 0.0},
            {"b": 0, "x": _zeros28()},
            {"$": "step", "s": 0, "t": 0.5},
        ],
    )
    with pytest.raises(MLCParseError, match="duplicate step index"):
        read_mlc_ndjson(log)


def test_reader_rejects_step_index_going_backwards(tmp_path: Path) -> None:
    log = _write_log(
        tmp_path,
        "back_step.mlc.ndjson",
        [
            {"$": "header", "format": 1},
            {"$": "body", "id": 0, "name": "b"},
            {"$": "step", "s": 5, "t": 0.0},
            {"$": "step", "s": 3, "t": 0.5},
        ],
    )
    with pytest.raises(MLCParseError, match="step index went backwards"):
        read_mlc_ndjson(log)


def test_reader_rejects_step_time_going_backwards(tmp_path: Path) -> None:
    log = _write_log(
        tmp_path,
        "back_time.mlc.ndjson",
        [
            {"$": "header", "format": 1},
            {"$": "body", "id": 0, "name": "b"},
            {"$": "step", "s": 0, "t": 1.0},
            {"$": "step", "s": 1, "t": 0.5},
        ],
    )
    with pytest.raises(MLCParseError, match="step time went backwards"):
        read_mlc_ndjson(log)


def test_reader_rejects_state_for_unknown_body_id(tmp_path: Path) -> None:
    log = _write_log(
        tmp_path,
        "state_unknown_body.mlc.ndjson",
        [
            {"$": "header", "format": 1},
            {"$": "step", "s": 0, "t": 0.0},
            {"b": 0, "x": _zeros28()},
        ],
    )
    with pytest.raises(MLCParseError, match="undeclared body id 0"):
        read_mlc_ndjson(log)


def test_reader_rejects_duplicate_header(tmp_path: Path) -> None:
    log = _write_log(
        tmp_path,
        "dup_header.mlc.ndjson",
        [
            {"$": "header", "format": 1},
            {"$": "header", "format": 1},
        ],
    )
    with pytest.raises(MLCParseError, match="duplicate header"):
        read_mlc_ndjson(log)


def test_reader_rejects_non_v1_format(tmp_path: Path) -> None:
    log = _write_log(
        tmp_path,
        "format2.mlc.ndjson",
        [{"$": "header", "format": 2}],
    )
    with pytest.raises(MLCParseError, match="'format' must be 1"):
        read_mlc_ndjson(log)


def test_reader_warns_on_non_step_reward_first_field(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    log = _write_log(
        tmp_path,
        "weird_reward.mlc.ndjson",
        [
            {"$": "header", "format": 1},
            {"$": "body", "id": 0, "name": "b"},
            {
                "$": "reward_spec",
                "id": 0,
                "b": 0,
                "fields": ["something_else", "fuel"],
            },
        ],
    )
    with caplog.at_level(logging.WARNING, logger="mlc_cinema.mlc.reader"):
        read_mlc_ndjson(log)
    assert any(
        "fields[0] should be 'step_reward'" in r.getMessage()
        for r in caplog.records
    )
