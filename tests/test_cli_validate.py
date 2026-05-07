"""Tests for ``mlc_cinema.cli_validate``."""

from __future__ import annotations

import json
from pathlib import Path

from mlc_cinema.cli_validate import main


_EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "logs"
MINIMAL = _EXAMPLES / "minimal_demo_v1.mlc.ndjson"
MULTIBODY = _EXAMPLES / "multibody_demo_v1.mlc.ndjson"
ARE = _EXAMPLES / "action_reward_event_demo_v1.mlc.ndjson"


def test_validate_cli_success_for_minimal_log(capsys) -> None:
    rc = main([str(MINIMAL), "--quiet"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Status: OK" in out
    assert "label: minimal_demo_v1" in out
    assert "duration_s: 2.000" in out


def test_validate_cli_success_for_multibody_log(capsys) -> None:
    rc = main([str(MULTIBODY), "--quiet"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "bodies: 2" in out
    assert "frames: 4" in out


def test_validate_cli_success_for_action_reward_event_log(capsys) -> None:
    rc = main([str(ARE), "--quiet"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "action_specs: 1" in out
    assert "reward_specs: 1" in out
    assert "events: 2" in out


def test_validate_cli_failure_for_bad_log(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "bad.mlc.ndjson"
    bad.write_text(
        "\n".join(
            [
                json.dumps({"$": "header", "format": 1}),
                json.dumps({"$": "body", "id": 0, "name": "b"}),
                json.dumps({"$": "step", "s": 0, "t": 0.0}),
                json.dumps({"b": 0, "x": [1.0, 2.0, 3.0]}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rc = main([str(bad), "--quiet"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Status: ERROR" in out
    assert "28 values, got 3" in out


def test_validate_cli_failure_for_missing_file(tmp_path: Path, capsys) -> None:
    rc = main([str(tmp_path / "no_such.mlc.ndjson"), "--quiet"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Status: ERROR" in out
