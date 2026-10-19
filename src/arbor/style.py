"""Colours, fonts and per-depth topic styles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QGuiApplication, QPen

from .model import Topic
from .qtutil import required

# Main topics and their branches; bright enough to read on either canvas.
PALETTE = [
    QColor(c)
    for c in ("#E8594A", "#F29B38", "#E9C33B", "#4DB86C", "#3D9BE0", "#8E6BD8")
]
FILLED_TEXT = QColor(Qt.GlobalColor.white)  # text on filled (root and main) topics
STATUS_FONT_SIZE = 12
MAX_TEXT_WIDTH = 280
DRAG_DIM = 0.35
DRAG_GHOST_OPACITY = 0.75


@dataclass(frozen=True)
class Theme:
    """Colours that follow the system's light or dark appearance."""

    canvas_bg: QColor
    selection: QColor
    root_fill: QColor
    sub_text: QColor
    badge_fill: QColor  # inside the fold badge
    # Status bar hints: keys stand out, their descriptions recede.
    status_key: QColor
    status_text: QColor
    status_border: QColor


LIGHT = Theme(
    canvas_bg=QColor("#FBFBFC"),
    selection=QColor("#2F7BF5"),
    root_fill=QColor("#22304F"),
    sub_text=QColor("#2B2B2B"),
    badge_fill=QColor("#FFFFFF"),
    status_key=QColor("#4A4A52"),
    status_text=QColor("#9A9AA2"),
    status_border=QColor("#E4E4E8"),
)
DARK = Theme(
    canvas_bg=QColor("#1E1F23"),
    selection=QColor("#4C8DF6"),
    root_fill=QColor("#3C5080"),
    sub_text=QColor("#E4E4E8"),
    badge_fill=QColor("#2A2B30"),
    status_key=QColor("#D2D2D8"),
    status_text=QColor("#85858E"),
    status_border=QColor("#33343A"),
)


def theme_for(scheme: Qt.ColorScheme) -> Theme:
    return DARK if scheme == Qt.ColorScheme.Dark else LIGHT


def theme() -> Theme:
    """The theme for the system's current appearance (light when it is unknown)."""
    return theme_for(required(QGuiApplication.styleHints()).colorScheme())


class Z(IntEnum):
    """Stacking order of scene items, back to front."""

    EDGE = 0
    TOPIC = 1
    FOLD_BADGE = 2
    DROP_INDICATOR = 9
    DRAG_GHOST = 10
    MARQUEE = 20


@dataclass(frozen=True)
class Style:
    font_size: int
    bold: bool
    pad_x: float
    pad_y: float
    radius: float
    filled: bool


ROOT_STYLE = Style(20, True, 26, 15, 10, True)
MAIN_STYLE = Style(15, False, 16, 9, 7, True)
SUB_STYLE = Style(13, False, 6, 4, 0, False)


def make_pen(color: QColor, width: float) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pen


def style_for(topic: Topic) -> Style:
    return (ROOT_STYLE, MAIN_STYLE)[topic.depth] if topic.depth < 2 else SUB_STYLE


def branch_color(topic: Topic) -> QColor:
    if topic.parent is None:
        return theme().root_fill
    node = topic
    while node.parent is not None and node.parent.parent is not None:
        node = node.parent
    return PALETTE[node.index % len(PALETTE)]
