"""Colours, fonts and per-depth topic styles."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPen

from .model import Topic

CANVAS_BG = QColor("#FBFBFC")
SELECTION = QColor("#2F7BF5")
ROOT_FILL = QColor("#22304F")
SUB_TEXT = QColor("#2B2B2B")
PALETTE = [QColor(c) for c in ("#E8594A", "#F29B38", "#E9C33B", "#4DB86C", "#3D9BE0", "#8E6BD8")]
MAX_TEXT_WIDTH = 280
DRAG_DIM = 0.35


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
        return ROOT_FILL
    node = topic
    while node.parent is not None and node.parent.parent is not None:
        node = node.parent
    return PALETTE[node.index % len(PALETTE)]
