"""Tests for ``mlc_cinema.mlc.summary``."""

from __future__ import annotations

from pathlib import Path

import pytest

from mlc_cinema.mlc.reader import read_mlc_ndjson
from mlc_cinema.mlc.summary import build_summary, format_summary
from mlc_cinema.mlc.timeline import build_timeline


_EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "logs"
MINIMAL = _EXAMPLES / "minimal_demo_v1.mlc.ndjson"
MULTIBODY = _EXAMPLES / "multibody_demo_v1.mlc.ndjson"
ARE = _EXAMPLES / "action_reward_event_demo_v1.mlc.ndjson"


def _summary(path: Path):
    parse = read_mlc_ndjson(path)
    timeline = build_timeline(parse)
    return build_summary(path, parse, timeline), parse


def test_summary_counts_minimal_log() -> None:
    s, _ = _summary(MINIMAL)
    assert s.label == "minimal_demo_v1"
    assert s.format == 1
    assert s.body_count == 1
    assert s.step_count == 5
    assert s.state_count == 5
    assert s.frame_count == 5
    assert s.action_spec_count == 1
    assert s.action_sample_count == 5
    assert s.event_count == 1
    assert s.start_time_s == 0.0
    assert s.end_time_s == 2.0
    assert s.duration_s == pytest.approx(2.0)


def test_summary_counts_multibody_log() -> None:
    s, _ = _summary(MULTIBODY)
    assert s.body_count == 2
    assert s.step_count == 4
    assert s.state_count == 8
    assert s.frame_count == 4
    assert s.event_count == 1
    assert s.duration_s == pytest.approx(1.5)


def test_summary_counts_action_reward_event_log() -> None:
    s, _ = _summary(ARE)
    assert s.action_spec_count == 1
    assert s.reward_spec_count == 1
    assert s.action_sample_count == 4
    assert s.reward_sample_count == 4
    assert s.event_count == 2


def test_format_summary_includes_expected_sections() -> None:
    s, parse = _summary(MINIMAL)
    text = format_summary(s, parse)
    assert "Status: OK" in text
    assert "Header:" in text
    assert "Counts:" in text
    assert "Timeline:" in text
    assert "Bodies:" in text
    assert "rocket_0" in text
    assert "platform=rocket" in text
    assert "duration_s: 2.000" in text
