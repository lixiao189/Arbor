# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

The project uses `uv` (Python 3.13, PyQt6).

```bash
uv run arbor                 # run the app (optionally pass a .mind file)
uv run pytest                    # all tests
uv run pytest tests/test_app.py::test_xmind_flow   # a single test
```

Tests run headless: `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen`. There is no linter or formatter configured.

## Architecture

The app is an XMind-style mind map editor. `README.md` is the source of truth for user-facing key bindings and drag-and-drop behaviour; keep it in sync when changing either.

Layers, from pure to Qt-heavy:

- **`model.py`** – `Topic` tree (dataclass with `eq=False`, so equality/hashing is by identity and topics are used as dict keys everywhere). Editing operations are module-level functions that mutate the tree and **return the topic to select next, or `None` if the operation doesn't apply**. `.mind` files are JSON: `{"version": 1, "root": {...}}`.
- **`layout.py`** – no Qt imports. Computes a balanced left/right layout (`layout()` → `dict[Topic, Placement]`, centres in scene coordinates), arrow-key navigation (`neighbor()`), and drag-drop hit testing (`drop_target()`). Topic sizes are injected via a `measure` callback, so it is unit-tested without Qt.
- **`style.py`** – colours and the per-depth `Style` (root / main / subtopic), `branch_color()`.
- **`items.py`** – `TopicItem` (a topic's body; forwards mouse events to the view), its `TopicText` label that doubles as the inline editor, and `FoldBadge`.
- **`drag.py`** – `DragState` / `Marquee` dataclasses and the drop-indicator path; **`clipboard.py`** – topics ↔ `QMimeData` (own JSON format plus a text outline); **`undo.py`** – `SnapshotCommand`.
- **`canvas.py`** – `MindMapView` (`QGraphicsView`) owns the document (`root`, `selected`, plus `selection` for multi-select via a left-drag box on the empty canvas or Ctrl+click; right-drag pans; `selected` is `selection[0]`, or `None` when nothing is selected, which is the initial state; `change()` is a no-op then), the undo stack, inline editing and dragging.
- **`app.py`** – `MainWindow`: menus, `QAction` shortcuts, file I/O. **`shortcuts.py`** – the shortcuts help dialog.

Key mechanics that span files:

- **Undo is snapshot-based.** Every edit goes through `MindMapView.change(label, op)`, where `op` is typically a `model` function. It snapshots `(root.to_dict(), selected.path())` before and after and pushes a `SnapshotCommand`. Undo/redo **rebuilds the whole tree from the dict**, so `Topic` object identities do not survive undo; never hold onto `Topic` references across an undoable change. Text edits are pushed separately by `commit_edit()`.
- **Rendering is rebuild-everything.** `rebuild()` clears the scene and recreates a `TopicItem` for each visible topic, then calls `apply_layout()`. There is no incremental update.
- **Key bindings are window-level `QAction`s** registered via `MainWindow._action()`. Actions created with `map_only=True` (the default) are disabled while a topic is being edited (`editingChanged` signal), because keys like Enter, Tab, arrows and Backspace belong to the text editor then. `_action()` also records each shortcut for the help dialog (`Ctrl+Shift+L`).
- `MindMapView.keyPressEvent` starts editing when a printable key is typed on a selected topic (replacing its text), and `focusNextPrevChild` returns `False` so Tab reaches the "Insert Subtopic" action instead of moving focus.
- Connect signals that outlive the window (for example the undo stack's) to **bound methods, not lambdas**. PyQt doesn't disconnect lambdas when the window is destroyed, which caused a crash on quit.

## Tests

- `test_model.py` and `test_layout.py` are pure-Python.
- `test_app.py` drives a real `MainWindow` with `QTest.keyClick` against `win.view`, then asserts on `view.selected`, `view.editing` and the model. Use the `key()`/`type_text()` helpers, which call `processEvents()`.
