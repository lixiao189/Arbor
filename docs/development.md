# Development

The project uses `uv` (Python 3.13, PyQt6).

```bash
uv run arbor            # run the app (optionally pass a .mind file)
uv run pytest           # run tests
```

## Source layout

- `src/arbor/model.py`: topic tree, editing operations, JSON (`.mind`) format
- `src/arbor/layout.py`: balanced left/right layout, arrow-key navigation and drop zones (no Qt dependency)
- `src/arbor/style.py`: colours and per-depth topic styles
- `src/arbor/items.py`: graphics items for a topic (label/inline editor, body, fold badge)
- `src/arbor/drag.py`: drag-and-drop and selection-box state and drop indicator
- `src/arbor/clipboard.py`: copying topics to and pasting them from the clipboard
- `src/arbor/undo.py`: snapshot-based undo command
- `src/arbor/canvas.py`: `QGraphicsView` that owns the document, selection, inline editing and dragging
- `src/arbor/app.py`: main window, menus and key bindings
- `src/arbor/shortcuts.py`: keyboard shortcuts help dialog
