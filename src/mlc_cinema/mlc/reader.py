"""Streaming reader for Maneuver Log Contract v1 NDJSON files.

A v1 file mixes two record kinds:

* **Typed records** carry a ``$`` field naming the type (``header``,
  ``body``, ``step``, ``action_spec``, ``reward_spec``, ``event``).
* **Compact step-scoped rows** have *no* ``$`` field. They inherit
  ``t`` and ``s`` from the most recent ``$=step`` record:
    - ``{"b":<body_id>, "x":[...28 values...]}`` — body state sample
    - ``{"a":<spec_id>, "x":[...]}``               — action sample
    - ``{"r":<spec_id>, "x":[...]}``               — reward sample

The reader produces an ``MLCParseResult`` whose ``states`` field
contains decoded ``MLCState`` objects in viewer-frame coordinates,
ready for ``build_timeline``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

from mlc_cinema.mlc.mlc_v1 import decode_mlc_v1_body_state
from mlc_cinema.mlc.records import (
    MLCActionSample,
    MLCActionSpec,
    MLCBody,
    MLCEvent,
    MLCHeader,
    MLCParseError,
    MLCParseResult,
    MLCRewardSample,
    MLCRewardSpec,
    MLCState,
    MLCStep,
)

_log = logging.getLogger(__name__)


__all__ = ["MLCParseError", "read_mlc_ndjson"]


def read_mlc_ndjson(path: str | Path) -> MLCParseResult:
    """Parse an MLC v1 NDJSON file at ``path``.

    Raises :class:`MLCParseError` on malformed input. Unknown typed
    records (``$=foo`` for any unrecognized ``foo``) are accepted with
    a warning and stashed in ``unknown_records``. Untyped rows that
    don't match any known compact pattern are treated as parse errors.
    """

    p = Path(path)
    if not p.exists():
        raise MLCParseError(f"MLC file not found: {p}")

    header: MLCHeader | None = None
    bodies: dict[int, MLCBody] = {}
    states: list[MLCState] = []
    steps: list[MLCStep] = []
    action_specs: dict[int, MLCActionSpec] = {}
    reward_specs: dict[int, MLCRewardSpec] = {}
    action_samples: list[MLCActionSample] = []
    reward_samples: list[MLCRewardSample] = []
    events: list[MLCEvent] = []
    unknown: list[dict[str, Any]] = []

    current_step: MLCStep | None = None
    saw_compact_v1 = False

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
                # --- compact, step-scoped row ---
                location = f"Line {lineno} of {p}: "
                if "b" in rec and "x" in rec:
                    state = decode_mlc_v1_body_state(
                        rec, current_step, location=location
                    )
                    states.append(state)
                    saw_compact_v1 = True
                elif "a" in rec and "x" in rec:
                    action_samples.append(
                        _decode_action_sample(rec, current_step, location)
                    )
                elif "r" in rec and "x" in rec:
                    reward_samples.append(
                        _decode_reward_sample(rec, current_step, location)
                    )
                else:
                    raise MLCParseError(
                        f"{location}record without '$' is not a known compact "
                        f"row type: expected b/x, a/x, or r/x"
                    )
                continue

            # --- typed record ---
            if kind == "header":
                header = _parse_header(rec, lineno, p)
            elif kind == "body":
                body = _parse_body(rec, lineno, p)
                bodies[body.id] = body
            elif kind == "step":
                step = _parse_step(rec, lineno, p)
                steps.append(step)
                current_step = step
            elif kind == "action_spec":
                spec = _parse_action_spec(rec, lineno, p)
                action_specs[spec.id] = spec
            elif kind == "reward_spec":
                spec = _parse_reward_spec(rec, lineno, p)
                reward_specs[spec.id] = spec
            elif kind == "event":
                events.append(_parse_event(rec, current_step, lineno, p))
            else:
                _log.warning(
                    "Unknown MLC record type '%s' on line %d of %s; ignoring",
                    kind,
                    lineno,
                    p,
                )
                unknown.append(rec)

    if saw_compact_v1:
        _log.info("Detected MLC v1 step-scoped state rows in %s", p)

    _log.info(
        "Loaded %s: header=%s, bodies=%d, steps=%d, states=%d, "
        "action_samples=%d, reward_samples=%d, events=%d, unknown=%d",
        p,
        "yes" if header is not None else "no",
        len(bodies),
        len(steps),
        len(states),
        len(action_samples),
        len(reward_samples),
        len(events),
        len(unknown),
    )

    return MLCParseResult(
        header=header,
        bodies=bodies,
        states=states,
        steps=steps,
        action_specs=action_specs,
        reward_specs=reward_specs,
        action_samples=action_samples,
        reward_samples=reward_samples,
        events=events,
        unknown_records=unknown,
    )


# --- typed-record parsers ---------------------------------------------------

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


def _parse_step(rec: dict[str, Any], lineno: int, path: Path) -> MLCStep:
    s = rec.get("s")
    t = rec.get("t")
    if not isinstance(s, int):
        raise MLCParseError(
            f"Step on line {lineno} of {path} is missing integer 's'"
        )
    if not isinstance(t, (int, float)):
        raise MLCParseError(
            f"Step on line {lineno} of {path} is missing numeric 't'"
        )
    return MLCStep(index=s, t=float(t), raw=dict(rec))


def _parse_action_spec(
    rec: dict[str, Any], lineno: int, path: Path
) -> MLCActionSpec:
    return _parse_field_spec(rec, lineno, path, kind="action_spec", cls=MLCActionSpec)


def _parse_reward_spec(
    rec: dict[str, Any], lineno: int, path: Path
) -> MLCRewardSpec:
    return _parse_field_spec(rec, lineno, path, kind="reward_spec", cls=MLCRewardSpec)


def _parse_field_spec(
    rec: dict[str, Any],
    lineno: int,
    path: Path,
    *,
    kind: str,
    cls: type,
) -> Any:
    spec_id = rec.get("id")
    if not isinstance(spec_id, int):
        raise MLCParseError(
            f"{kind} on line {lineno} of {path} is missing integer 'id'"
        )
    body_id = rec.get("b") if isinstance(rec.get("b"), int) else None
    fields = rec.get("fields", [])
    if not isinstance(fields, list) or not all(isinstance(f, str) for f in fields):
        raise MLCParseError(
            f"{kind} on line {lineno} of {path}: 'fields' must be a list of strings"
        )
    return cls(id=spec_id, body_id=body_id, fields=list(fields), raw=dict(rec))


def _parse_event(
    rec: dict[str, Any],
    current_step: MLCStep | None,
    lineno: int,
    path: Path,
) -> MLCEvent:
    topic = rec.get("topic")
    if not isinstance(topic, str):
        raise MLCParseError(
            f"Event on line {lineno} of {path} is missing string 'topic'"
        )

    explicit_t = rec.get("t")
    if explicit_t is None:
        t: float | None = current_step.t if current_step is not None else None
    elif isinstance(explicit_t, (int, float)):
        t = float(explicit_t)
    else:
        raise MLCParseError(
            f"Event on line {lineno} of {path}: 't' must be numeric"
        )

    body_id_raw = rec.get("b")
    if body_id_raw is not None and not isinstance(body_id_raw, int):
        raise MLCParseError(
            f"Event on line {lineno} of {path}: 'b' must be an integer"
        )

    data_raw = rec.get("data", {})
    if not isinstance(data_raw, dict):
        raise MLCParseError(
            f"Event on line {lineno} of {path}: 'data' must be an object"
        )

    return MLCEvent(
        t=t,
        topic=topic,
        body_id=body_id_raw,
        data=dict(data_raw),
        step_index=current_step.index if current_step is not None else None,
        raw=dict(rec),
    )


# --- compact-row decoders ---------------------------------------------------

def _decode_action_sample(
    rec: dict[str, Any], current_step: MLCStep | None, location: str
) -> MLCActionSample:
    return _decode_packed_sample(
        rec,
        current_step,
        location,
        spec_key="a",
        cls=MLCActionSample,
        kind="action sample",
    )


def _decode_reward_sample(
    rec: dict[str, Any], current_step: MLCStep | None, location: str
) -> MLCRewardSample:
    return _decode_packed_sample(
        rec,
        current_step,
        location,
        spec_key="r",
        cls=MLCRewardSample,
        kind="reward sample",
    )


def _decode_packed_sample(
    rec: dict[str, Any],
    current_step: MLCStep | None,
    location: str,
    *,
    spec_key: str,
    cls: type,
    kind: str,
) -> Any:
    spec_id = rec.get(spec_key)
    if not isinstance(spec_id, int):
        raise MLCParseError(
            f"{location}{kind} requires integer '{spec_key}'"
        )
    x_raw = rec.get("x")
    if not isinstance(x_raw, list):
        raise MLCParseError(f"{location}{kind} requires list 'x'")
    try:
        values = np.asarray(x_raw, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise MLCParseError(f"{location}{kind} 'x' is not numeric") from exc

    explicit_t = rec.get("t")
    if explicit_t is None:
        if current_step is None:
            raise MLCParseError(
                f"{location}{kind} requires an active step or explicit 't'"
            )
        t = current_step.t
    elif isinstance(explicit_t, (int, float)):
        t = float(explicit_t)
    else:
        raise MLCParseError(f"{location}{kind} 't' must be numeric")

    explicit_s = rec.get("s")
    if explicit_s is None:
        step_index = current_step.index if current_step is not None else None
    elif isinstance(explicit_s, int):
        step_index = explicit_s
    else:
        raise MLCParseError(f"{location}{kind} 's' must be an integer")

    return cls(
        t=float(t),
        spec_id=spec_id,
        values=values,
        step_index=step_index,
        raw=dict(rec),
    )
