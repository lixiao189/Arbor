"""Main window: menus, XMind-style key bindings and file handling."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from PyQt6.QtCore import QLoggingCategory, Qt
from PyQt6.QtGui import QAction, QCloseEvent, QKeySequence
from PyQt6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox

from . import model
from .canvas import MindMapView
from .qtutil import required
from .shortcuts import ShortcutsDialog

FILE_FILTER = "Mind Map (*.mind);;All Files (*)"

Keys = str | Sequence[str]


class MainWindow(QMainWindow):
    def __init__(self, path: Path | None = None) -> None:
        super().__init__()
        self.path: Path | None = None
        self.view = MindMapView(self)
        self.setCentralWidget(self.view)
        self.resize(1200, 800)

        # Actions that must not fire while a topic's text is being edited (the
        # keys belong to the text editor then: Enter, Tab, arrows, Backspace, ...).
        self.map_actions: list[QAction] = []
        self.shortcuts: list[tuple[str, str, str]] = []  # (menu, label, keys) for the help dialog
        self._build_menus()

        self.view.editingChanged.connect(self._on_editing_changed)
        # Bound methods (not lambdas) so PyQt disconnects them when the window is
        # destroyed; the undo stack still emits while it is being torn down.
        self.view.undo_stack.cleanChanged.connect(self._update_title)
        self.view.selectionChanged.connect(self._update_status)

        if path is not None:
            self.open_path(path)
        self._update_title()
        self._update_status()

    # --- actions

    def _action(self, menu, label: str, slot: Callable[[], object], keys: Keys = (), map_only: bool = True) -> QAction:
        action = QAction(label, self)
        seqs = [keys] if isinstance(keys, str) else list(keys)
        if seqs:
            action.setShortcuts([QKeySequence(k) for k in seqs])
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            native = ", ".join(QKeySequence(k).toString(QKeySequence.SequenceFormat.NativeText) for k in seqs)
            self.shortcuts.append((menu.title().replace("&", "") if menu else "Navigate", label, native))
        action.triggered.connect(lambda _checked=False: slot())
        (menu or self).addAction(action)
        if map_only:
            self.map_actions.append(action)
        return action

    def _build_menus(self) -> None:
        v = self.view
        bar = required(self.menuBar())
        a = self._action

        m = required(bar.addMenu("&File"))
        a(m, "New", self.new_file, "Ctrl+N", map_only=False)
        a(m, "Open…", self.open_file, "Ctrl+O", map_only=False)
        m.addSeparator()
        a(m, "Save", self.save, "Ctrl+S", map_only=False)
        a(m, "Save As…", self.save_as, "Ctrl+Shift+S", map_only=False)
        m.addSeparator()
        a(m, "Quit", self.close, "Ctrl+Q", map_only=False)

        m = required(bar.addMenu("&Edit"))
        undo = a(m, "Undo", v.undo_stack.undo, "Ctrl+Z")
        redo = a(m, "Redo", v.undo_stack.redo, ["Ctrl+Shift+Z", "Ctrl+Y"])
        self._undo, self._redo = undo, redo
        v.undo_stack.canUndoChanged.connect(self._sync_undo_actions)
        v.undo_stack.canRedoChanged.connect(self._sync_undo_actions)
        self._sync_undo_actions()
        m.addSeparator()
        a(m, "Cut", v.cut, "Ctrl+X")
        a(m, "Copy", v.copy, "Ctrl+C")
        a(m, "Paste", v.paste, "Ctrl+V")
        a(m, "Delete", v.delete, ["Delete", "Backspace"])
        m.addSeparator()
        a(m, "Edit Topic", v.start_edit, ["Space", "F2"])

        m = required(bar.addMenu("&Insert"))
        a(m, "Subtopic", v.add_child, ["Tab", "Insert"])
        a(m, "Topic (After)", lambda: v.add_sibling(before=False), ["Return", "Enter"])
        a(m, "Topic (Before)", lambda: v.add_sibling(before=True), ["Shift+Return", "Shift+Enter"])
        a(m, "Parent Topic", v.insert_parent, ["Ctrl+Return", "Ctrl+Enter"])

        m = required(bar.addMenu("&Topic"))
        a(m, "Collapse / Expand", v.toggle_collapse, "Ctrl+/")
        a(m, "Collapse All Subtopics", lambda: v.set_all_collapsed(True), "Ctrl+Alt+/")
        a(m, "Expand All Subtopics", lambda: v.set_all_collapsed(False), "Ctrl+Alt+Shift+/")
        m.addSeparator()
        a(m, "Move Up", lambda: v.move_topic(-1), "Alt+Up")
        a(m, "Move Down", lambda: v.move_topic(+1), "Alt+Down")
        m.addSeparator()
        a(m, "Select Central Topic", v.select_root, "Home")

        m = required(bar.addMenu("&View"))
        a(m, "Zoom In", lambda: v.zoom_by(1.25), ["Ctrl+=", "Ctrl++"], map_only=False)
        a(m, "Zoom Out", lambda: v.zoom_by(0.8), "Ctrl+-", map_only=False)
        a(m, "Actual Size", v.zoom_reset, "Ctrl+0", map_only=False)
        a(m, "Fit Map", v.fit_map, "Ctrl+Shift+0", map_only=False)

        # Arrow-key navigation: window-level actions, not shown in a menu.
        for direction, key in (("up", "Up"), ("down", "Down"), ("left", "Left"), ("right", "Right")):
            a(None, f"Select {direction.title()}", lambda d=direction: v.navigate(d), key)

        m = required(bar.addMenu("&Help"))
        a(m, "Keyboard Shortcuts", self.show_shortcuts, "Ctrl+Shift+L", map_only=False)

    def _on_editing_changed(self, editing: bool) -> None:
        for action in self.map_actions:
            action.setEnabled(not editing)
        self._sync_undo_actions()
        self._update_status()

    def _sync_undo_actions(self) -> None:
        editing = self.view.editing is not None
        self._undo.setEnabled(self.view.undo_stack.canUndo() and not editing)
        self._redo.setEnabled(self.view.undo_stack.canRedo() and not editing)

    def _update_title(self, *_args: object) -> None:
        name = self.path.name if self.path else "Untitled"
        self.setWindowFilePath(str(self.path) if self.path else "")
        self.setWindowModified(not self.view.undo_stack.isClean())
        self.setWindowTitle(f"{name}[*] — Arbor")

    def _update_status(self) -> None:
        if self.view.editing is not None:
            msg = "Editing — Enter to finish, Shift+Enter for a new line, Esc to cancel, Tab to add a subtopic"
        elif len(self.view.selection) > 1:
            msg = f"{len(self.view.selection)} topics selected — Del, Cut and Copy apply to all of them"
        else:
            msg = "Tab: subtopic · Enter: sibling · Ctrl+Enter: parent · Space/F2: edit · Del: delete · Arrows: move"
        required(self.statusBar()).showMessage(msg)

    # --- files

    def maybe_save(self) -> bool:
        self.view.commit_edit()
        if self.view.undo_stack.isClean():
            return True
        answer = QMessageBox.question(
            self,
            "Unsaved Changes",
            "Save changes to this mind map?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        return answer == QMessageBox.StandardButton.Discard

    def new_file(self) -> None:
        if self.maybe_save():
            self.path = None
            self.view.set_document(model.new_document())
            self._update_title()

    def open_file(self) -> None:
        if not self.maybe_save():
            return
        name, _ = QFileDialog.getOpenFileName(self, "Open Mind Map", "", FILE_FILTER)
        if name:
            self.open_path(Path(name))

    def open_path(self, path: Path) -> None:
        try:
            root = model.document_from_json(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Open Failed", f"Could not open {path}:\n{exc}")
            return
        self.path = path
        self.view.set_document(root)
        self._update_title()

    def save(self) -> bool:
        if self.path is None:
            return self.save_as()
        self.view.commit_edit()
        try:
            data = json.dumps(model.document_to_json(self.view.root), ensure_ascii=False, indent=2)
            self.path.write_text(data + "\n", encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Save Failed", f"Could not save {self.path}:\n{exc}")
            return False
        self.view.undo_stack.setClean()
        self._update_title()
        return True

    def save_as(self) -> bool:
        name, _ = QFileDialog.getSaveFileName(self, "Save Mind Map", "untitled.mind", FILE_FILTER)
        if not name:
            return False
        self.path = Path(name)
        return self.save()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.maybe_save():
            event.accept()
        else:
            event.ignore()

    # --- help

    def show_shortcuts(self) -> None:
        ShortcutsDialog(self.shortcuts, self).exec()


def main() -> None:
    # Qt 6 on macOS logs a "Mismatch between Cocoa and Carbon" warning for every
    # Return/Tab shortcut; it is harmless noise.
    QLoggingCategory.setFilterRules("qt.qpa.keymapper.warning=false")
    app = QApplication(sys.argv)
    app.setApplicationName("Arbor")
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    window = MainWindow(path)
    window.show()
    window.view.center_root()
    window.view.setFocus()
    sys.exit(app.exec())
