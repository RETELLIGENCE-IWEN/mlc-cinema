"""Bottom playback bar: play/pause button, scrubber, time/frame readouts."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QWidget,
)
from PySide6.QtCore import Qt


class TimelineWidget(QWidget):
    """Playback transport. Decoupled from the controller: emits intent signals
    (``play_toggled``, ``frame_requested``) that the main window wires up."""

    play_toggled = Signal()
    frame_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._play_btn = QPushButton("Play")
        self._play_btn.setEnabled(False)
        self._play_btn.setFixedWidth(80)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setEnabled(False)
        self._slider.setMinimum(0)
        self._slider.setMaximum(0)
        self._slider.setSingleStep(1)
        self._slider.setPageStep(1)
        self._slider.setTracking(True)

        self._time_label = QLabel("t = —")
        self._time_label.setMinimumWidth(120)
        self._frame_label = QLabel("frame —/—")
        self._frame_label.setMinimumWidth(120)

        for w in (self._time_label, self._frame_label):
            w.setStyleSheet(
                "font-family: Consolas, 'Courier New', monospace;"
            )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.addWidget(self._play_btn)
        layout.addWidget(self._slider, 1)
        layout.addWidget(self._frame_label)
        layout.addWidget(self._time_label)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._play_btn.clicked.connect(self.play_toggled.emit)
        self._slider.valueChanged.connect(self._on_slider_value_changed)

        self._suppress_slider = False

    # ----- public API -----

    def configure_for_timeline(self, frame_count: int) -> None:
        """Enable controls and set the slider range to ``[0, frame_count - 1]``."""

        if frame_count <= 0:
            self._slider.setEnabled(False)
            self._play_btn.setEnabled(False)
            self._slider.setMaximum(0)
            self._slider.setValue(0)
            self._frame_label.setText("frame —/—")
            self._time_label.setText("t = —")
            return

        self._suppress_slider = True
        try:
            self._slider.setMinimum(0)
            self._slider.setMaximum(max(0, frame_count - 1))
            self._slider.setValue(0)
        finally:
            self._suppress_slider = False
        self._slider.setEnabled(True)
        self._play_btn.setEnabled(True)
        self._frame_label.setText(f"frame 0/{frame_count - 1}")

    def set_frame(self, frame_index: int, frame_time: float) -> None:
        """Reflect an externally-driven frame change on the UI."""

        max_index = self._slider.maximum()
        self._suppress_slider = True
        try:
            self._slider.setValue(frame_index)
        finally:
            self._suppress_slider = False
        self._frame_label.setText(f"frame {frame_index}/{max_index}")
        self._time_label.setText(f"t = {frame_time:.3f} s")

    def set_playing(self, is_playing: bool) -> None:
        self._play_btn.setText("Pause" if is_playing else "Play")

    # ----- internal -----

    def _on_slider_value_changed(self, value: int) -> None:
        if self._suppress_slider:
            return
        self.frame_requested.emit(int(value))
