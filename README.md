# Mind Demo

A small mind map editor built with PyQt6, using XMind-style key bindings.

```bash
uv run mind-demo            # start with a new map
uv run mind-demo notes.mind # open a file
uv run pytest               # run tests
```

## Key bindings

On macOS, `Ctrl` means `Cmd` and `Alt` means `Option`.

| Key | Action |
| --- | --- |
| `Tab` / `Insert` | Insert subtopic |
| `Enter` | Insert topic after (sibling) |
| `Shift+Enter` | Insert topic before |
| `Ctrl+Enter` | Insert parent topic |
| `Space` / `F2` / double-click | Edit topic (start typing to replace the text) |
| `Enter` / `Esc` / `Shift+Enter` (while editing) | Finish / cancel / new line |
| `Tab` (while editing) | Finish and insert a subtopic |
| `Delete` / `Backspace` | Delete topic |
| Arrow keys | Move selection (left/right go toward or away from the centre) |
| `Alt+Up` / `Alt+Down` | Move topic up / down |
| `Ctrl+/` | Collapse / expand |
| `Ctrl+Alt+/` / `Ctrl+Alt+Shift+/` | Collapse / expand all subtopics |
| `Home` | Select the central topic |
| `Ctrl+X` / `Ctrl+C` / `Ctrl+V` | Cut / copy / paste (paste plain-text outlines too) |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Undo / redo |
| `Ctrl+=` / `Ctrl+-` / `Ctrl+0` / `Ctrl+Shift+0` | Zoom in / out / actual size / fit map |
| `Ctrl+scroll`, drag the canvas | Zoom, pan |
| `Ctrl+N` / `Ctrl+O` / `Ctrl+S` / `Ctrl+Shift+S` | New / open / save / save as |
| `Ctrl+Shift+L` | Show all shortcuts |

## Layout

- `src/mind_demo/model.py`: topic tree, editing operations, JSON (`.mind`) format
- `src/mind_demo/layout.py`: balanced left/right layout and arrow-key navigation (no Qt dependency)
- `src/mind_demo/canvas.py`: `QGraphicsView` rendering, inline editing, snapshot-based undo
- `src/mind_demo/app.py`: main window, menus and key bindings
