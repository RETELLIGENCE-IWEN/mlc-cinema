"""Timeline construction from a parsed MLC file.

A timeline is a chronologically sorted list of frames, where each frame
groups together every body's state at one timestamp. Lookups by index
or by time use simple O(log n) bisection — interpolation between
frames is intentionally **not** implemented in M0; we round to the
nearest frame instead.
"""

from __future__ import annotations

import bisect
import logging
import math
from dataclasses import dataclass, field

from mlc_cinema.mlc.records import (
    MLCBody,
    MLCHeader,
    MLCParseResult,
    MLCState,
)

_log = logging.getLogger(__name__)


# Two timestamps within this tolerance (seconds) are considered to belong
# to the same frame. Keeps grouping robust against floating-point noise.
_FRAME_TIME_EPSILON: float = 1e-9


class TimelineError(Exception):
    """Raised when a timeline cannot be constructed or queried."""


@dataclass(frozen=True)
class TimelineFrame:
    """All body states sharing a single timestamp."""

    t: float
    states_by_body: dict[int, MLCState]


@dataclass
class MLCTimeline:
    """Sorted, frame-grouped representation of an MLC parse result."""

    header: MLCHeader | None
    bodies: dict[int, MLCBody]
    frames: list[TimelineFrame] = field(default_factory=list)

    @property
    def duration_s(self) -> float:
        if not self.frames:
            return 0.0
        return self.end_time_s - self.start_time_s

    @property
    def start_time_s(self) -> float:
        if not self.frames:
            raise TimelineError("Timeline is empty; no start time.")
        return self.frames[0].t

    @property
    def end_time_s(self) -> float:
        if not self.frames:
            raise TimelineError("Timeline is empty; no end time.")
        return self.frames[-1].t

    def __len__(self) -> int:
        return len(self.frames)

    def frame_at_index(self, index: int) -> TimelineFrame:
        if not self.frames:
            raise TimelineError("Timeline is empty; cannot index a frame.")
        n = len(self.frames)
        if index < 0 or index >= n:
            raise IndexError(
                f"Frame index {index} out of range [0, {n - 1}]"
            )
        return self.frames[index]

    def nearest_frame(self, t: float) -> TimelineFrame:
        idx = self.nearest_frame_index(t)
        return self.frames[idx]

    def nearest_frame_index(self, t: float) -> int:
        if not self.frames:
            raise TimelineError("Timeline is empty; cannot search by time.")

        times = [f.t for f in self.frames]
        # bisect finds the insertion point; we then compare neighbours.
        pos = bisect.bisect_left(times, t)
        if pos <= 0:
            return 0
        if pos >= len(times):
            return len(times) - 1

        before = times[pos - 1]
        after = times[pos]
        # Prefer the closer of the two; break ties to the earlier frame.
        if (t - before) <= (after - t):
            return pos - 1
        return pos


def build_timeline(parse_result: MLCParseResult) -> MLCTimeline:
    """Group ``parse_result.states`` into chronologically sorted frames."""

    if not parse_result.states:
        raise TimelineError(
            "Cannot build a timeline from a parse result with no state records."
        )

    sorted_states = sorted(parse_result.states, key=lambda s: s.t)

    frames: list[TimelineFrame] = []
    current_t: float | None = None
    current_states: dict[int, MLCState] = {}

    for s in sorted_states:
        if current_t is None or not _times_equal(current_t, s.t):
            if current_states:
                frames.append(
                    TimelineFrame(
                        t=current_t if current_t is not None else s.t,
                        states_by_body=current_states,
                    )
                )
            current_t = s.t
            current_states = {}

        if s.body_id in current_states:
            _log.warning(
                "Multiple states for body %d at t=%.6f; keeping the last one",
                s.body_id,
                s.t,
            )
        current_states[s.body_id] = s

    if current_states and current_t is not None:
        frames.append(
            TimelineFrame(t=current_t, states_by_body=current_states)
        )

    _log.info(
        "Built timeline: %d frame(s), %d body(ies), duration=%.3fs",
        len(frames),
        len(parse_result.bodies),
        (frames[-1].t - frames[0].t) if frames else 0.0,
    )

    return MLCTimeline(
        header=parse_result.header,
        bodies=dict(parse_result.bodies),
        frames=frames,
    )


def _times_equal(a: float, b: float) -> bool:
    return math.isclose(a, b, abs_tol=_FRAME_TIME_EPSILON, rel_tol=0.0)
