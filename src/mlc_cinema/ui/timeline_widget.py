"""Bottom playback bar: play/pause, speed multiplier, scrubber, time/frame readouts."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QWidget,
)

from mlc_cinema.config import (
    DEFAULT_PLAYBACK_SPEED,
    MAX_PLAYBACK_SPEED,
    MIN_PLAYBACK_SPEED,
)


class _SpeedSpinBox(QDoubleSpinBox):
    """``QDoubleSpinBox`` with adaptive precision so 0.001 and 1000 both look right."""

    def textFromValue(self, value: float) -> str:  # noqa: N802 (Qt API)
        v = float(value)
        if v >= 100.0:
            return f"{v:.0f}"
        if v >= 10.0:
            return f"{v:.1f}"
        if v >= 1.0:
            return f"{v:.2f}"
        return f"{v:.3f}"


class TimelineWidget(QWidget):
    """Playback transport. Decoupled from the controller: emits intent signals
    (``play_toggled``, ``frame_requested``, ``speed_changed``) that the main
    window wires up."""

    play_toggled = Signal()
    frame_requested = Signal(int)
    speed_changed = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._play_btn = QPushButton("Play")
        self._play_btn.setEnabled(False)
        self._play_btn.setFixedWidth(80)

        self._speed_label = QLabel("Speed:")
        self._speed_spin = _SpeedSpinBox()
        self._speed_spin.setRange(MIN_PLAYBACK_SPEED, MAX_PLAYBACK_SPEED)
        self._speed_spin.setDecimals(3)
        self._speed_spin.setValue(DEFAULT_PLAYBACK_SPEED)
        self._speed_spin.setSuffix(" ×")  # ' ×'
        self._speed_spin.setKeyboardTracking(False)
        self._speed_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self._speed_spin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._speed_spin.setFixedWidth(96)
        self._speed_spin.setToolTip(
            "Playback speed multiplier (0.001 – 1000).\n"
            "1× = wall-clock matches recorded timeline duration.\n"
            "Type a value and press Enter."
        )

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
        layout.addWidget(self._speed_label)
        layout.addWidget(self._speed_spin)
        layout.addWidget(self._slider, 1)
        layout.addWidget(self._frame_label)
        layout.addWidget(self._time_label)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._play_btn.clicked.connect(self.play_toggled.emit)
        self._slider.valueChanged.connect(self._on_slider_value_changed)
        self._speed_spin.valueChanged.connect(self._on_speed_value_changed)

        self._suppress_slider = False
        self._suppress_speed = False

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

    def set_speed(self, speed: float) -> None:
        """Reflect a controller-side speed change without re-emitting."""

        self._suppress_speed = True
        try:
            self._speed_spin.setValue(float(speed))
        finally:
            self._suppress_speed = False

    def current_speed(self) -> float:
        return float(self._speed_spin.value())

    # ----- internal -----

    def _on_slider_value_changed(self, value: int) -> None:
        if self._suppress_slider:
            return
        self.frame_requested.emit(int(value))

    def _on_speed_value_changed(self, value: float) -> None:
        if self._suppress_speed:
            return
        self.speed_changed.emit(float(value))
