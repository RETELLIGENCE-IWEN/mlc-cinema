"""Playback controller for an ``MLCTimeline``.

This is a thin Qt object that owns:

  * the current frame index;
  * a fixed-rate ``QTimer`` (``PLAYBACK_TICK_HZ``);
  * a wall-clock-aligned playback position in *timeline seconds*;
  * a speed multiplier in ``[MIN_PLAYBACK_SPEED, MAX_PLAYBACK_SPEED]``.

At ``speed == 1.0`` a ``T``-second timeline plays in ``T`` real
seconds. Each timer tick advances the playback position by
``dt_real * speed`` and snaps to the nearest frame. End-of-timeline
behaviour is **pause-at-end** for M0/M0.5.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from mlc_cinema.config import (
    DEFAULT_PLAYBACK_SPEED,
    MAX_PLAYBACK_SPEED,
    MIN_PLAYBACK_SPEED,
    PLAYBACK_TICK_HZ,
)
from mlc_cinema.mlc.timeline import MLCTimeline, TimelineError, TimelineFrame

_log = logging.getLogger(__name__)


class PlaybackController(QObject):
    """Drives playback over a single ``MLCTimeline``."""

    # (frame_index, frame_time_seconds)
    frame_changed = Signal(int, float)
    playing_changed = Signal(bool)
    speed_changed = Signal(float)

    def __init__(
        self,
        timeline: MLCTimeline,
        parent: QObject | None = None,
        speed: float = DEFAULT_PLAYBACK_SPEED,
    ) -> None:
        super().__init__(parent)
        if not timeline.frames:
            raise TimelineError(
                "PlaybackController cannot drive an empty timeline."
            )

        self._timeline = timeline
        self._frame_index: int = 0
        # Free-running playback position in timeline seconds. Kept
        # separate from the frame index so we can advance smoothly
        # between frames at low speeds and skip cleanly at high speeds.
        self._timeline_t: float = timeline.start_time_s
        self._speed: float = self._clamp_speed(speed)

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.setInterval(max(1, int(round(1000.0 / PLAYBACK_TICK_HZ))))
        self._timer.timeout.connect(self._on_tick)

    # ----- public API -----

    @property
    def timeline(self) -> MLCTimeline:
        return self._timeline

    @property
    def frame_count(self) -> int:
        return len(self._timeline.frames)

    @property
    def frame_index(self) -> int:
        return self._frame_index

    @property
    def is_playing(self) -> bool:
        return self._timer.isActive()

    @property
    def speed(self) -> float:
        return self._speed

    def set_speed(self, speed: float) -> None:
        new_speed = self._clamp_speed(speed)
        if new_speed == self._speed:
            return
        self._speed = new_speed
        _log.debug("Playback speed set to %.4fx", self._speed)
        self.speed_changed.emit(self._speed)

    def play(self) -> None:
        if self.is_playing:
            return
        # If we're sitting at the end of the timeline, pressing play
        # should rewind so the user doesn't need to scrub manually.
        if self._frame_index >= self.frame_count - 1:
            self.set_frame_index(0)
        self._timer.start()
        self.playing_changed.emit(True)

    def pause(self) -> None:
        if not self.is_playing:
            return
        self._timer.stop()
        self.playing_changed.emit(False)

    def toggle_play(self) -> None:
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def set_frame_index(self, index: int) -> None:
        index = max(0, min(self.frame_count - 1, int(index)))
        if index == self._frame_index:
            # Even on a no-op, keep the playback position in sync so
            # subsequent ticks advance from the visible frame.
            self._timeline_t = self.current_frame().t
            return
        self._frame_index = index
        self._timeline_t = self.current_frame().t
        self.frame_changed.emit(self._frame_index, self.current_frame().t)

    def step_forward(self) -> None:
        self.set_frame_index(self._frame_index + 1)

    def step_backward(self) -> None:
        self.set_frame_index(self._frame_index - 1)

    def current_frame(self) -> TimelineFrame:
        return self._timeline.frame_at_index(self._frame_index)

    def emit_current(self) -> None:
        """Emit ``frame_changed`` for the current frame.

        Useful right after construction so subscribers receive an
        initial state to render.
        """

        self.frame_changed.emit(self._frame_index, self.current_frame().t)

    # ----- internal -----

    @staticmethod
    def _clamp_speed(speed: float) -> float:
        try:
            s = float(speed)
        except (TypeError, ValueError):
            s = DEFAULT_PLAYBACK_SPEED
        if s != s:  # NaN guard
            s = DEFAULT_PLAYBACK_SPEED
        return max(MIN_PLAYBACK_SPEED, min(MAX_PLAYBACK_SPEED, s))

    def _on_tick(self) -> None:
        dt_real = self._timer.interval() / 1000.0
        self._timeline_t += dt_real * self._speed

        end_t = self._timeline.end_time_s
        if self._timeline_t >= end_t:
            self._timeline_t = end_t
            last_index = self.frame_count - 1
            if last_index != self._frame_index:
                self._frame_index = last_index
                self.frame_changed.emit(
                    self._frame_index, self.current_frame().t
                )
            # Pause-at-end semantics for M0.5.
            self.pause()
            return

        new_index = self._timeline.nearest_frame_index(self._timeline_t)
        if new_index != self._frame_index:
            self._frame_index = new_index
            self.frame_changed.emit(self._frame_index, self.current_frame().t)
