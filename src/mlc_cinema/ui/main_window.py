"""Top-level QMainWindow: docks, menu, and pipeline wiring.

The main window owns the playback controller and dispatches frame
updates from the controller to the viewport and telemetry panel. It
is the only place that is allowed to call into ``mlc.reader``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QWidget,
)

from mlc_cinema.config import APP_DISPLAY_NAME, DEFAULT_PLAYBACK_FPS
from mlc_cinema.mlc.reader import MLCParseError, read_mlc_ndjson
from mlc_cinema.mlc.timeline import (
    MLCTimeline,
    TimelineError,
    build_timeline,
)
from mlc_cinema.mlc.validate import warn_on_suspicious_content
from mlc_cinema.playback.controller import PlaybackController
from mlc_cinema.render.viewport import MLCViewport
from mlc_cinema.scene.entities import SceneEntity
from mlc_cinema.scene.scene_model import (
    SceneBodyState,
    scene_entities_from_bodies,
    scene_frame_from_timeline_frame,
)
from mlc_cinema.ui.entity_tree import EntityTree
from mlc_cinema.ui.telemetry_panel import TelemetryPanel
from mlc_cinema.ui.timeline_widget import TimelineWidget

_log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """The application's main window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.resize(1200, 760)

        # --- viewport (central) ---
        self._viewport = MLCViewport(self)
        self.setCentralWidget(self._viewport)

        # --- entity tree (left dock) ---
        self._entity_tree = EntityTree(self)
        self._entity_dock = self._make_dock(
            "Entities", self._entity_tree, Qt.LeftDockWidgetArea
        )

        # --- telemetry (right dock) ---
        self._telemetry = TelemetryPanel(self)
        self._telemetry_dock = self._make_dock(
            "Telemetry", self._telemetry, Qt.RightDockWidgetArea
        )

        # --- timeline / transport (bottom dock) ---
        self._timeline_widget = TimelineWidget(self)
        self._timeline_dock = self._make_dock(
            "Playback", self._timeline_widget, Qt.BottomDockWidgetArea
        )

        # --- status bar ---
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Ready.")

        # --- menu ---
        self._build_menu()

        # --- runtime state ---
        self._timeline: MLCTimeline | None = None
        self._entities: dict[int, SceneEntity] = {}
        self._controller: PlaybackController | None = None
        self._selected_body_id: int | None = None

        # --- signal wiring (UI side) ---
        self._entity_tree.body_selected.connect(self._on_body_selected)
        self._timeline_widget.play_toggled.connect(self._on_play_toggled)
        self._timeline_widget.frame_requested.connect(self._on_frame_requested)

    # ----- public API -----

    def open_file_path(self, path: str | Path) -> None:
        """Open an MLC NDJSON file from a command-line path."""

        self._load_file(Path(path))

    # ----- menu / actions -----

    def _build_menu(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("&File")

        open_act = QAction("&Open MLC Log...", self)
        open_act.setShortcut(QKeySequence.Open)
        open_act.triggered.connect(self._on_open_dialog)
        file_menu.addAction(open_act)

        file_menu.addSeparator()
        quit_act = QAction("E&xit", self)
        quit_act.setShortcut(QKeySequence.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        view_menu = bar.addMenu("&View")
        view_menu.addAction(self._entity_dock.toggleViewAction())
        view_menu.addAction(self._telemetry_dock.toggleViewAction())
        view_menu.addAction(self._timeline_dock.toggleViewAction())

        playback_menu = bar.addMenu("&Playback")
        play_act = QAction("&Play / Pause", self)
        play_act.setShortcut(Qt.Key_Space)
        play_act.triggered.connect(self._on_play_toggled)
        playback_menu.addAction(play_act)

        step_back_act = QAction("Step &Backward", self)
        step_back_act.setShortcut(Qt.Key_Left)
        step_back_act.triggered.connect(self._on_step_back)
        playback_menu.addAction(step_back_act)

        step_fwd_act = QAction("Step &Forward", self)
        step_fwd_act.setShortcut(Qt.Key_Right)
        step_fwd_act.triggered.connect(self._on_step_forward)
        playback_menu.addAction(step_fwd_act)

    def _make_dock(
        self, title: str, widget: QWidget, area: Qt.DockWidgetArea
    ) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.addDockWidget(area, dock)
        return dock

    # ----- file loading -----

    def _on_open_dialog(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open MLC Log",
            "",
            "MLC NDJSON (*.mlc.ndjson *.ndjson *.json);;All files (*)",
        )
        if path_str:
            self._load_file(Path(path_str))

    def _load_file(self, path: Path) -> None:
        try:
            parse_result = read_mlc_ndjson(path)
            timeline = build_timeline(parse_result)
        except (MLCParseError, TimelineError) as exc:
            _log.exception("Failed to load %s", path)
            QMessageBox.critical(
                self, "Failed to load MLC log", f"{exc}"
            )
            return
        except OSError as exc:
            _log.exception("OS error loading %s", path)
            QMessageBox.critical(
                self, "Failed to load MLC log", f"{exc}"
            )
            return

        warn_on_suspicious_content(parse_result)

        # Tear down any previous controller before adopting the new one.
        if self._controller is not None:
            try:
                self._controller.pause()
            except Exception:  # pragma: no cover — defensive
                pass
            self._controller.frame_changed.disconnect()
            self._controller.playing_changed.disconnect()
            self._controller.deleteLater()
            self._controller = None

        self._timeline = timeline
        self._entities = scene_entities_from_bodies(timeline.bodies)

        # Bodies that appear only in state records (and not in body
        # records) still need a renderable entity.
        state_only_ids = {
            bid for f in timeline.frames for bid in f.states_by_body
        } - set(self._entities.keys())
        for bid in state_only_ids:
            self._entities[bid] = SceneEntity(
                body_id=bid, name=f"body_{bid}"
            )

        self._entity_tree.populate(self._entities)
        self._viewport.set_entities(self._entities)
        self._viewport.reset_trails()

        self._controller = PlaybackController(
            timeline, parent=self, fps=DEFAULT_PLAYBACK_FPS
        )
        self._controller.frame_changed.connect(self._on_frame_changed)
        self._controller.playing_changed.connect(self._on_playing_changed)

        self._timeline_widget.configure_for_timeline(len(timeline.frames))
        self._timeline_widget.set_playing(False)

        # Render the first frame immediately so the user sees something.
        self._controller.set_frame_index(0)
        self._controller.emit_current()

        self.statusBar().showMessage(
            f"Loaded {path.name}: {len(self._entities)} bodies, "
            f"{len(timeline.frames)} frames, {timeline.duration_s:.3f}s"
        )

    # ----- controller events -----

    def _on_frame_changed(self, index: int, t: float) -> None:
        if self._timeline is None or self._controller is None:
            return

        timeline_frame = self._controller.current_frame()
        scene_frame = scene_frame_from_timeline_frame(timeline_frame)

        self._viewport.set_scene_frame(scene_frame)
        self._timeline_widget.set_frame(index, t)
        self._update_telemetry_for_frame(scene_frame)

    def _on_playing_changed(self, playing: bool) -> None:
        self._timeline_widget.set_playing(playing)

    # ----- ui events -----

    def _on_body_selected(self, body_id: int) -> None:
        self._selected_body_id = body_id
        ent = self._entities.get(body_id)
        self._telemetry.set_entity(ent)
        if self._controller is not None:
            timeline_frame = self._controller.current_frame()
            scene_frame = scene_frame_from_timeline_frame(timeline_frame)
            self._update_telemetry_for_frame(scene_frame)

    def _on_play_toggled(self) -> None:
        if self._controller is None:
            return
        self._controller.toggle_play()

    def _on_frame_requested(self, index: int) -> None:
        if self._controller is None:
            return
        # Scrubbing while playing pauses; consistent with most replay tools.
        if self._controller.is_playing:
            self._controller.pause()
        # Scrubbing back to (or past) the start should clear stale trails
        # rather than painting an arc through "history that hasn't happened".
        if index < self._controller.frame_index:
            self._viewport.reset_trails()
            self._controller.set_frame_index(index)
            # After reset we need to repaint trails forward; replay frames 0..index.
            self._replay_to_index(index)
        else:
            self._controller.set_frame_index(index)

    def _on_step_back(self) -> None:
        if self._controller is None:
            return
        self._on_frame_requested(self._controller.frame_index - 1)

    def _on_step_forward(self) -> None:
        if self._controller is None:
            return
        self._on_frame_requested(self._controller.frame_index + 1)

    # ----- helpers -----

    def _update_telemetry_for_frame(self, scene_frame) -> None:
        if self._selected_body_id is None:
            self._telemetry.update_state(scene_frame.t, None)
            return
        body_state: SceneBodyState | None = scene_frame.body_states.get(
            self._selected_body_id
        )
        self._telemetry.update_state(scene_frame.t, body_state)

    def _replay_to_index(self, target_index: int) -> None:
        """Re-feed the viewport every frame from 0..target_index after a backward scrub.

        This rebuilds the trail so it matches the new history rather
        than leaving the old (now-future) trail visible.
        """

        if self._timeline is None:
            return
        target_index = max(0, min(target_index, len(self._timeline.frames) - 1))
        for i in range(0, target_index + 1):
            tf = self._timeline.frame_at_index(i)
            self._viewport.set_scene_frame(scene_frame_from_timeline_frame(tf))
