"""Lightweight parse-summary used by the validation CLI.

The summary is a frozen snapshot of "did the file parse, and what's
in it?" — counts, identifiers, durations. It contains no MLC-internal
record references, only scalar fields and lists, so it can be cheaply
formatted, serialized, or compared.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mlc_cinema.mlc.records import MLCParseResult
from mlc_cinema.mlc.timeline import MLCTimeline


@dataclass(frozen=True)
class MLCSummary:
    """Compact summary of one parsed MLC file."""

    path: str
    label: str | None
    producer: str | None
    scenario: str | None
    format: int | None

    body_count: int
    step_count: int
    state_count: int
    frame_count: int
    action_spec_count: int
    action_sample_count: int
    reward_spec_count: int
    reward_sample_count: int
    event_count: int
    unknown_record_count: int

    start_time_s: float | None
    end_time_s: float | None
    duration_s: float | None


def build_summary(
    path: str | Path,
    parse_result: MLCParseResult,
    timeline: MLCTimeline,
) -> MLCSummary:
    """Assemble an :class:`MLCSummary` from a parsed file + built timeline."""

    header = parse_result.header
    if timeline.frames:
        start = timeline.start_time_s
        end = timeline.end_time_s
        duration = timeline.duration_s
    else:
        start = end = duration = None

    return MLCSummary(
        path=str(path),
        label=header.label if header is not None else None,
        producer=header.producer if header is not None else None,
        scenario=header.scenario if header is not None else None,
        format=header.format if header is not None else None,
        body_count=len(parse_result.bodies),
        step_count=len(parse_result.steps),
        state_count=len(parse_result.states),
        frame_count=len(timeline.frames),
        action_spec_count=len(parse_result.action_specs),
        action_sample_count=len(parse_result.action_samples),
        reward_spec_count=len(parse_result.reward_specs),
        reward_sample_count=len(parse_result.reward_samples),
        event_count=len(parse_result.events),
        unknown_record_count=len(parse_result.unknown_records),
        start_time_s=start,
        end_time_s=end,
        duration_s=duration,
    )


def format_summary(
    summary: MLCSummary, parse_result: MLCParseResult
) -> str:
    """Render the summary as the CLI's textual report."""

    lines: list[str] = []
    lines.append(f"MLC file: {summary.path}")
    lines.append("Status: OK")
    lines.append("")

    lines.append("Header:")
    lines.append(f"  label: {_or_dash(summary.label)}")
    lines.append(f"  producer: {_or_dash(summary.producer)}")
    lines.append(f"  scenario: {_or_dash(summary.scenario)}")
    lines.append(f"  format: {_or_dash(summary.format)}")
    lines.append("")

    lines.append("Counts:")
    lines.append(f"  bodies: {summary.body_count}")
    lines.append(f"  steps: {summary.step_count}")
    lines.append(f"  states: {summary.state_count}")
    lines.append(f"  frames: {summary.frame_count}")
    lines.append(f"  action_specs: {summary.action_spec_count}")
    lines.append(f"  action_samples: {summary.action_sample_count}")
    lines.append(f"  reward_specs: {summary.reward_spec_count}")
    lines.append(f"  reward_samples: {summary.reward_sample_count}")
    lines.append(f"  events: {summary.event_count}")
    lines.append(f"  unknown_records: {summary.unknown_record_count}")
    lines.append("")

    lines.append("Timeline:")
    lines.append(f"  start_time_s: {_fmt_t(summary.start_time_s)}")
    lines.append(f"  end_time_s: {_fmt_t(summary.end_time_s)}")
    lines.append(f"  duration_s: {_fmt_t(summary.duration_s)}")

    if parse_result.bodies:
        lines.append("")
        lines.append("Bodies:")
        for body_id in sorted(parse_result.bodies.keys()):
            body = parse_result.bodies[body_id]
            platform = _or_none_label(body.platform)
            model = _or_none_label(body.model)
            lines.append(
                f"  {body.id} {body.name} platform={platform} model={model}"
            )

    return "\n".join(lines) + "\n"


def _or_dash(v: object) -> str:
    return "—" if v is None else str(v)


def _or_none_label(v: object) -> str:
    return "—" if v is None else str(v)


def _fmt_t(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:.3f}"
