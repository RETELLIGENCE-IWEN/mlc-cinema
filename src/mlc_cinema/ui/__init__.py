"""PySide6 widgets for mlc-cinema.

UI widgets consume only the scene-layer dataclasses; they never reach
back into ``mlc_cinema.mlc.*`` to interpret raw records.
"""

from mlc_cinema.ui.entity_tree import EntityTree
from mlc_cinema.ui.main_window import MainWindow
from mlc_cinema.ui.telemetry_panel import TelemetryPanel
from mlc_cinema.ui.timeline_widget import TimelineWidget

__all__ = [
    "EntityTree",
    "MainWindow",
    "TelemetryPanel",
    "TimelineWidget",
]
