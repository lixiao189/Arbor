# Using Arbor

```bash
uv run arbor            # start with a new map
uv run arbor notes.mind # open a file
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
| Arrow keys | Move selection (left/right go toward or away from the centre); with nothing selected, select the central topic |
| `Alt+Up` / `Alt+Down` | Move topic up / down |
| `Ctrl+/` | Collapse / expand |
| `Ctrl+Alt+/` / `Ctrl+Alt+Shift+/` | Collapse / expand all subtopics |
| `Home` | Select the central topic |
| `Ctrl+X` / `Ctrl+C` / `Ctrl+V` | Cut / copy / paste (paste plain-text outlines too) |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Undo / redo |
| `Ctrl+=` / `Ctrl+-` / `Ctrl+0` / `Ctrl+Shift+0` | Zoom in / out / actual size / fit map |
| `Ctrl+scroll` / right-drag the canvas or scroll | Zoom / pan |
| `Ctrl+N` / `Ctrl+O` / `Ctrl+S` / `Ctrl+Shift+S` | New / open / save / save as |
| `Ctrl+Shift+L` | Show all shortcuts |

## Drag and drop

Drag a topic to move it, together with its subtopics. Drop it on the middle of
another topic to make it a subtopic there, or on that topic's top or bottom edge
to insert it before or after as a sibling. Press `Esc` while dragging to cancel.
Moves can be undone.

## Selecting multiple topics

As in XMind, drag on an empty part of the canvas with the left mouse button to
draw a selection box: every topic it touches is selected. Press `Esc` while
drawing the box to cancel. Click an empty spot to clear the selection (nothing
is selected when a map opens). (Pan with the right mouse button, or by scrolling.)

Dragging one of the selected topics moves them all, keeping their order; clicking
one without dragging selects just that topic. `Delete`, `Ctrl+X` and `Ctrl+C`
apply to all selected topics; other commands act on the first one.

`Shift`+click or `Ctrl`+click a topic to add it to the selection, or to remove
it (on macOS `Cmd`+click; the physical `Ctrl` key works too).
