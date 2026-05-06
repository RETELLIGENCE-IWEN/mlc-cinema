"""Entity list panel.

Lists every body declared in the loaded MLC file. Selecting a row
emits ``body_selected`` so the telemetry panel can follow the choice.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTreeWidget,
    QTreeWidgetItem,
)

from mlc_cinema.scene.entities import SceneEntity

_BODY_ID_ROLE = int(Qt.UserRole)


class EntityTree(QTreeWidget):
    """Read-only list of bodies in the current scene."""

    body_selected = Signal(int)  # body_id

    _COLUMNS: tuple[str, ...] = ("ID", "Name", "Platform", "Model")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setColumnCount(len(self._COLUMNS))
        self.setHeaderLabels(list(self._COLUMNS))
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

        header = self.header()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)

        self.itemSelectionChanged.connect(self._on_selection_changed)

    def populate(self, entities: dict[int, SceneEntity]) -> None:
        """Replace the tree contents and select the first row, if any."""

        self.blockSignals(True)
        try:
            self.clear()
            for body_id in sorted(entities.keys()):
                ent = entities[body_id]
                item = QTreeWidgetItem(
                    [
                        str(ent.body_id),
                        ent.name,
                        ent.platform or "",
                        ent.model or "",
                    ]
                )
                item.setData(0, _BODY_ID_ROLE, ent.body_id)
                self.addTopLevelItem(item)
            for col in range(self.columnCount() - 1):
                self.resizeColumnToContents(col)
            if self.topLevelItemCount() > 0:
                first = self.topLevelItem(0)
                first.setSelected(True)
                self.setCurrentItem(first)
        finally:
            self.blockSignals(False)

        if self.topLevelItemCount() > 0:
            first_id = self.topLevelItem(0).data(0, _BODY_ID_ROLE)
            self.body_selected.emit(int(first_id))

    def selected_body_id(self) -> int | None:
        item = self.currentItem()
        if item is None:
            return None
        v = item.data(0, _BODY_ID_ROLE)
        return int(v) if v is not None else None

    def _on_selection_changed(self) -> None:
        body_id = self.selected_body_id()
        if body_id is not None:
            self.body_selected.emit(body_id)
