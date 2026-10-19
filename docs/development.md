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
- `src/arbor/icon.py`: window icon on Windows and Linux (macOS uses the app bundle's)
- `src/arbor/shortcuts.py`: keyboard shortcuts help dialog

## App icon

The icon is drawn from the layer SVGs in `packaging/icon` (`render.py`):

- macOS: `make_icns.py` (the `.icns`) and `Arbor.icon` (Icon Composer, compiled into `Assets.car`), both built by `packaging/arbor.spec`
- Windows: `make_ico.py`, built into `Arbor.exe` by the spec
- Windows and Linux window icon: `make_pngs.py` writes the checked-in `src/arbor/icons/arbor-*.png`; rerun it after changing the SVGs. The Flatpak also installs these PNGs as its hicolor icons

```bash
uv run python packaging/icon/make_pngs.py
```

## Flatpak (Linux)

Linux builds ship as a Flatpak, `io.github.lixiao189.Arbor`, from `packaging/flatpak`. The manifest installs the PyQt6 wheels pinned in `uv.lock` (listed with their hashes in the generated `python-deps.json`) on the freedesktop runtime. Regenerate that file after `uv lock` changes the runtime dependencies; `tests/test_flatpak.py` fails while it is stale:

```bash
uv run python packaging/flatpak/make_python_deps.py
```

To build and install it locally (needs `flatpak-builder` and the Flathub remote):

```bash
flatpak-builder --user --install --install-deps-from=flathub --force-clean build-dir packaging/flatpak/io.github.lixiao189.Arbor.yml
```
