"""Dialog listing every keyboard shortcut."""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QHeaderView, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from .qtutil import required


class ShortcutsDialog(QDialog):
    def __init__(self, shortcuts: list[tuple[str, str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        table = QTableWidget(len(shortcuts), 3, self)
        table.setHorizontalHeaderLabels(["Menu", "Command", "Shortcut"])
        required(table.verticalHeader()).setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, values in enumerate(shortcuts):
            for col, value in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(value))
        header = required(table.horizontalHeader())
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        layout = QVBoxLayout(self)
        layout.addWidget(table)
        self.resize(560, 600)
