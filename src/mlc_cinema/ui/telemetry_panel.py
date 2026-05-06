"""Telemetry panel.

Shows the latest scalar values for the currently selected body. The
panel never reads MLC records directly — the main window pushes the
relevant ``SceneBodyState`` into ``update_state``.
"""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from mlc_cinema.scene.entities import SceneEntity
from mlc_cinema.scene.scene_model import SceneBodyState


_NA = "—"


class TelemetryPanel(QWidget):
    """Compact key/value readout for one body at the current frame."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self._title = QLabel("No body selected")
        self._title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        font = self._title.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        self._title.setFont(font)

        self._subtitle = QLabel("")
        self._subtitle.setStyleSheet("color: #aab; ")

        # Identity + frame context
        self._time = self._make_value()
        self._step_index = self._make_value()
        self._body_id = self._make_value()
        self._source_format = self._make_value()
        # Position
        self._pos_x = self._make_value()
        self._pos_y = self._make_value()
        self._pos_z = self._make_value()
        self._altitude_m = self._make_value()
        # Velocity
        self._vel_x = self._make_value()
        self._vel_y = self._make_value()
        self._vel_z = self._make_value()
        self._speed = self._make_value()
        # Quaternion
        self._q_w = self._make_value()
        self._q_x = self._make_value()
        self._q_y = self._make_value()
        self._q_z = self._make_value()

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFormAlignment(Qt.AlignTop | Qt.AlignLeft)
        form.addRow("time (s)", self._time)
        form.addRow("step index", self._step_index)
        form.addRow("body id", self._body_id)
        form.addRow("source format", self._source_format)
        form.addRow(_separator(), QLabel(""))
        form.addRow("position x", self._pos_x)
        form.addRow("position y", self._pos_y)
        form.addRow("position z", self._pos_z)
        form.addRow("altitude (m)", self._altitude_m)
        form.addRow(_separator(), QLabel(""))
        form.addRow("velocity x", self._vel_x)
        form.addRow("velocity y", self._vel_y)
        form.addRow("velocity z", self._vel_z)
        form.addRow("speed", self._speed)
        form.addRow(_separator(), QLabel(""))
        form.addRow("quat w", self._q_w)
        form.addRow("quat x", self._q_x)
        form.addRow("quat y", self._q_y)
        form.addRow("quat z", self._q_z)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self._title)
        layout.addWidget(self._subtitle)
        layout.addLayout(form)
        layout.addStretch(1)

        self._current_entity: SceneEntity | None = None

    # ----- public API -----

    def set_entity(self, entity: SceneEntity | None) -> None:
        self._current_entity = entity
        if entity is None:
            self._title.setText("No body selected")
            self._subtitle.setText("")
            self.clear()
            return
        self._title.setText(entity.name)
        meta_parts = []
        if entity.platform:
            meta_parts.append(entity.platform)
        if entity.model:
            meta_parts.append(entity.model)
        self._subtitle.setText(" / ".join(meta_parts) if meta_parts else "")
        self._body_id.setText(str(entity.body_id))

    def update_state(self, t: float, state: SceneBodyState | None) -> None:
        self._time.setText(f"{t:.3f}")
        if state is None:
            self._clear_state_only()
            return

        self._body_id.setText(str(state.body_id))
        self._step_index.setText(
            str(state.step_index) if state.step_index is not None else _NA
        )
        self._source_format.setText(state.source_format or _NA)

        self._pos_x.setText(_fmt(state.position[0]))
        self._pos_y.setText(_fmt(state.position[1]))
        self._pos_z.setText(_fmt(state.position[2]))
        self._altitude_m.setText(
            _fmt(state.altitude_m) if state.altitude_m is not None else _NA
        )

        if state.velocity is not None:
            self._vel_x.setText(_fmt(state.velocity[0]))
            self._vel_y.setText(_fmt(state.velocity[1]))
            self._vel_z.setText(_fmt(state.velocity[2]))
            speed = float(np.linalg.norm(state.velocity))
            self._speed.setText(_fmt(speed))
        else:
            for w in (self._vel_x, self._vel_y, self._vel_z, self._speed):
                w.setText(_NA)

        if state.quaternion is not None and len(state.quaternion) == 4:
            self._q_w.setText(_fmt(state.quaternion[0]))
            self._q_x.setText(_fmt(state.quaternion[1]))
            self._q_y.setText(_fmt(state.quaternion[2]))
            self._q_z.setText(_fmt(state.quaternion[3]))
        else:
            for w in (self._q_w, self._q_x, self._q_y, self._q_z):
                w.setText(_NA)

    def clear(self) -> None:
        self._time.setText(_NA)
        self._body_id.setText(_NA)
        self._step_index.setText(_NA)
        self._source_format.setText(_NA)
        self._clear_state_only()

    # ----- helpers -----

    def _clear_state_only(self) -> None:
        for w in (
            self._pos_x, self._pos_y, self._pos_z, self._altitude_m,
            self._vel_x, self._vel_y, self._vel_z, self._speed,
            self._q_w, self._q_x, self._q_y, self._q_z,
        ):
            w.setText(_NA)

    @staticmethod
    def _make_value() -> QLabel:
        lbl = QLabel(_NA)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lbl.setStyleSheet("font-family: Consolas, 'Courier New', monospace;")
        return lbl


def _fmt(v: float) -> str:
    if v is None:
        return _NA
    if not math.isfinite(float(v)):
        return _NA
    return f"{float(v):.3f}"


def _separator() -> QFrame:
    sep = QFrame()
    sep.setFrameShape(QFrame.HLine)
    sep.setFrameShadow(QFrame.Sunken)
    return sep
