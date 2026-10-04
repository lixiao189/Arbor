"""State and scene decorations for dragging topics and drawing a selection box."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QColor, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsRectItem

from .items import TopicItem
from .layout import DropTarget, Side
from .model import Topic
from .style import SELECTION, Z, make_pen

INDICATOR_WIDTH = 3
INDICATOR_PAD = 4  # outline of a "child" target, outside the topic body
INDICATOR_RADIUS = 8
STUB_W, STUB_H = 34, 14  # placeholder sketched for a parent with no visible children
STUB_RADIUS = 4
STUB_OFFSET = 40  # from the parent's edge to the placeholder's centre
STUB_LINE_GAP = 4  # from the parent's edge to the start of the connecting line
INSERT_LINE_GAP = 6  # between a sibling and the "before"/"after" line
INSERT_DOT_RADIUS = 3
INSERT_DOT_GAP = 4  # dot centre, left of the sibling's edge
BAND_WIDTH = 1
BAND_ALPHA = 40


@dataclass
class DragState:
    topic: Topic  # the topic under the cursor, shown as the ghost
    topics: list[Topic]  # everything being moved
    ghost: TopicItem
    indicator: QGraphicsPathItem
    target: DropTarget | None = None


@dataclass
class Marquee:
    origin: QPointF
    band: QGraphicsRectItem
    before: list[Topic]  # selection to restore on Esc


def make_indicator() -> QGraphicsPathItem:
    indicator = QGraphicsPathItem()
    indicator.setZValue(Z.DROP_INDICATOR)
    indicator.setPen(make_pen(SELECTION, INDICATOR_WIDTH))
    return indicator


def make_band() -> QGraphicsRectItem:
    band = QGraphicsRectItem()
    band.setPen(QPen(SELECTION, BAND_WIDTH))
    fill = QColor(SELECTION)
    fill.setAlpha(BAND_ALPHA)
    band.setBrush(fill)
    band.setZValue(Z.MARQUEE)
    return band


def indicator_path(target: DropTarget | None, items: dict[Topic, TopicItem]) -> QPainterPath:
    """Outline showing where a drop onto ``target`` would put the dragged topics."""
    path = QPainterPath()
    if target is None:
        return path
    item = items[target.anchor]
    rect = item.body_rect().translated(item.pos())
    if target.kind == "child":
        # Outline the new parent; if it has no visible children yet, also sketch
        # a placeholder where the topic will go.
        pad = INDICATOR_PAD
        path.addRoundedRect(rect.adjusted(-pad, -pad, pad, pad), INDICATOR_RADIUS, INDICATOR_RADIUS)
        if target.anchor.children and not target.anchor.collapsed:
            return path
        side = item.side.outward
        x = rect.right() if side is Side.RIGHT else rect.left()
        stub = QRectF(0, 0, STUB_W, STUB_H)
        stub.moveCenter(QPointF(x + side * STUB_OFFSET, rect.center().y()))
        path.moveTo(x + side * STUB_LINE_GAP, rect.center().y())
        path.lineTo(stub.left() if side is Side.RIGHT else stub.right(), stub.center().y())
        path.addRoundedRect(stub, STUB_RADIUS, STUB_RADIUS)
    else:
        y = rect.top() - INSERT_LINE_GAP if target.kind == "before" else rect.bottom() + INSERT_LINE_GAP
        path.addEllipse(QPointF(rect.left() - INSERT_DOT_GAP, y), INSERT_DOT_RADIUS, INSERT_DOT_RADIUS)
        path.moveTo(rect.left(), y)
        path.lineTo(rect.right(), y)
    return path
