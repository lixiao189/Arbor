"""Snapshot-based undo command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtGui import QUndoCommand

if TYPE_CHECKING:
    from .canvas import MindMapView


class SnapshotCommand(QUndoCommand):
    """Undo step storing the whole document before and after a change."""

    def __init__(self, canvas: MindMapView, label: str, before: tuple, after: tuple) -> None:
        super().__init__(label)
        self.canvas, self.before, self.after = canvas, before, after
        self._applied = True  # the change is already live when the command is pushed

    def redo(self) -> None:
        if self._applied:
            self._applied = False
            return
        self.canvas.restore(self.after)

    def undo(self) -> None:
        self.canvas.restore(self.before)
