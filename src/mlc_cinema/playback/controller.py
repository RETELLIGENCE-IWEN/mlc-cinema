"""Playback controller for an ``MLCTimeline``.

This is a thin Qt object that owns:

  * the current frame index;
  * a ``QTimer`` that advances the frame index at a configurable rate;
  * signals so the UI can react without polling.

Behaviour at the end of the timeline is **pause-at-end**, as specified
for M0. Looping can be added later.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from mlc_cinema.config import DEFAULT_PLAYBACK_FPS
from mlc_cinema.mlc.timeline import MLCTimeline, TimelineError, TimelineFrame

_log = logging.getLogger(__name__)


class PlaybackController(QObject):
    """Drives playback over a single ``MLCTimeline``."""

    # (frame_index, frame_time_seconds)
    frame_changed = Signal(int, float)
    playing_changed = Signal(bool)

    def __init__(
        self,
        timeline: MLCTimeline,
        parent: QObject | None = None,
        fps: float = DEFAULT_PLAYBACK_FPS,
    ) -> None:
        super().__init__(parent)
        if not timeline.frames:
            raise TimelineError(
                "PlaybackController cannot drive an empty timeline."
            )

        self._timeline = timeline
        self._frame_index: int = 0
        self._fps: float = max(0.1, float(fps))

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._on_tick)
        self._apply_fps()

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
    def fps(self) -> float:
        return self._fps

    def set_fps(self, fps: float) -> None:
        self._fps = max(0.1, float(fps))
        self._apply_fps()

    def play(self) -> None:
        if self.is_playing:
            return
        if self._frame_index >= self.frame_count - 1:
            # Pressing play at the end rewinds to the start so the user
            # doesn't have to scrub back manually.
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
            return
        self._frame_index = index
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

    def _apply_fps(self) -> None:
        interval_ms = max(1, int(round(1000.0 / self._fps)))
        self._timer.setInterval(interval_ms)

    def _on_tick(self) -> None:
        next_index = self._frame_index + 1
        if next_index >= self.frame_count:
            # Pause-at-end semantics for M0.
            self.pause()
            return
        self._frame_index = next_index
        self.frame_changed.emit(self._frame_index, self.current_frame().t)
