"""Streaming reader for MLC NDJSON files."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

from mlc_cinema.mlc.records import (
    MLCBody,
    MLCHeader,
    MLCParseResult,
    MLCState,
)

_log = logging.getLogger(__name__)

# Records that we recognize but don't fully model in M0. They are
# accepted silently — no warning, no crash.
_OPTIONAL_KNOWN_TYPES: frozenset[str] = frozenset(
    {"action_spec", "event", "metric", "marker"}
)


class MLCParseError(Exception):
    """Raised when the MLC NDJSON file cannot be parsed."""


def read_mlc_ndjson(path: str | Path) -> MLCParseResult:
    """Read and parse an MLC NDJSON file.

    Each non-empty line must be a JSON object with a ``$`` field naming
    the record type. Header / body / state are decoded into dataclasses.
    Optional known types are kept aside silently. Unknown types are
    accumulated into ``unknown_records`` and warned about.
    """

    p = Path(path)
    if not p.exists():
        raise MLCParseError(f"MLC file not found: {p}")

    header: MLCHeader | None = None
    bodies: dict[int, MLCBody] = {}
    states: list[MLCState] = []
    unknown: list[dict[str, Any]] = []

    with p.open("r", encoding="utf-8") as fh:
        for lineno, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MLCParseError(
                    f"Malformed JSON on line {lineno} of {p}: {exc.msg}"
                ) from exc

            if not isinstance(rec, dict):
                raise MLCParseError(
                    f"Line {lineno} of {p} is not a JSON object"
                )

            kind = rec.get("$")
            if kind is None:
                raise MLCParseError(
                    f"Line {lineno} of {p} is missing the '$' record type field"
                )

            if kind == "header":
                header = _parse_header(rec, lineno, p)
            elif kind == "body":
                body = _parse_body(rec, lineno, p)
                bodies[body.id] = body
            elif kind == "state":
                states.append(_parse_state(rec, lineno, p))
            elif kind in _OPTIONAL_KNOWN_TYPES:
                # Recognized but not modelled in M0 — keep raw for the future.
                unknown.append(rec)
            else:
                _log.warning(
                    "Unknown MLC record type '%s' on line %d of %s; ignoring",
                    kind,
                    lineno,
                    p,
                )
                unknown.append(rec)

    _log.info(
        "Loaded %s: header=%s, bodies=%d, states=%d, unknown=%d",
        p,
        "yes" if header is not None else "no",
        len(bodies),
        len(states),
        len(unknown),
    )

    return MLCParseResult(
        header=header,
        bodies=bodies,
        states=states,
        unknown_records=unknown,
    )


def _parse_header(rec: dict[str, Any], lineno: int, path: Path) -> MLCHeader:
    fmt = rec.get("format")
    if not isinstance(fmt, int):
        raise MLCParseError(
            f"Header on line {lineno} of {path} is missing integer 'format'"
        )
    return MLCHeader(
        format=fmt,
        label=rec.get("label"),
        producer=rec.get("producer"),
        mode=rec.get("mode"),
        scenario=rec.get("scenario"),
        seed=rec.get("seed"),
        raw=dict(rec),
    )


def _parse_body(rec: dict[str, Any], lineno: int, path: Path) -> MLCBody:
    body_id = rec.get("id")
    name = rec.get("name")
    if not isinstance(body_id, int):
        raise MLCParseError(
            f"Body on line {lineno} of {path} is missing integer 'id'"
        )
    if not isinstance(name, str):
        raise MLCParseError(
            f"Body on line {lineno} of {path} is missing string 'name'"
        )
    return MLCBody(
        id=body_id,
        name=name,
        platform=rec.get("platform"),
        model=rec.get("model"),
        raw=dict(rec),
    )


def _parse_state(rec: dict[str, Any], lineno: int, path: Path) -> MLCState:
    t = rec.get("t")
    if not isinstance(t, (int, float)):
        raise MLCParseError(
            f"State on line {lineno} of {path} is missing numeric 't'"
        )

    body_id = rec.get("b")
    if not isinstance(body_id, int):
        raise MLCParseError(
            f"State on line {lineno} of {path} is missing integer 'b' (body id)"
        )

    pos_list = rec.get("p")
    position = _to_vec3(pos_list, "p", lineno, path)

    velocity = _to_optional_vec3(rec.get("v"), "v", lineno, path)
    quaternion = _to_optional_quat(rec.get("q"), lineno, path)
    angular_velocity = _to_optional_vec3(rec.get("w"), "w", lineno, path)

    return MLCState(
        t=float(t),
        body_id=body_id,
        position=position,
        velocity=velocity,
        quaternion=quaternion,
        angular_velocity=angular_velocity,
        raw=dict(rec),
    )


def _to_vec3(value: Any, field_name: str, lineno: int, path: Path) -> np.ndarray:
    if not isinstance(value, list) or len(value) != 3:
        raise MLCParseError(
            f"State on line {lineno} of {path} is missing 3-vector "
            f"'{field_name}'"
        )
    try:
        arr = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise MLCParseError(
            f"State on line {lineno} of {path}: '{field_name}' is not numeric"
        ) from exc
    return arr


def _to_optional_vec3(
    value: Any, field_name: str, lineno: int, path: Path
) -> np.ndarray | None:
    if value is None:
        return None
    return _to_vec3(value, field_name, lineno, path)


def _to_optional_quat(
    value: Any, lineno: int, path: Path
) -> np.ndarray | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 4:
        raise MLCParseError(
            f"State on line {lineno} of {path}: 'q' must be a 4-vector "
            f"[w, x, y, z]"
        )
    try:
        return np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise MLCParseError(
            f"State on line {lineno} of {path}: 'q' is not numeric"
        ) from exc
