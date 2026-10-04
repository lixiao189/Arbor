"""State and scene decorations for dragging topics and drawing a selection box."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QColor, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsRectItem

from .items import TopicItem
from .layout import DropTarget
from .model import Topic
from .style import SELECTION, make_pen


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
    indicator.setZValue(9)
    indicator.setPen(make_pen(SELECTION, 3))
    return indicator


def make_band() -> QGraphicsRectItem:
    band = QGraphicsRectItem()
    band.setPen(QPen(SELECTION, 1))
    fill = QColor(SELECTION)
    fill.setAlpha(40)
    band.setBrush(fill)
    band.setZValue(20)
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
        path.addRoundedRect(rect.adjusted(-4, -4, 4, 4), 8, 8)
        if target.anchor.children and not target.anchor.collapsed:
            return path
        side = item.side or 1
        x = rect.right() if side > 0 else rect.left()
        stub = QRectF(0, 0, 34, 14)
        stub.moveCenter(QPointF(x + side * 40, rect.center().y()))
        path.moveTo(x + side * 4, rect.center().y())
        path.lineTo(stub.left() if side > 0 else stub.right(), stub.center().y())
        path.addRoundedRect(stub, 4, 4)
    else:
        y = rect.top() - 6 if target.kind == "before" else rect.bottom() + 6
        path.addEllipse(QPointF(rect.left() - 4, y), 3, 3)
        path.moveTo(rect.left(), y)
        path.lineTo(rect.right(), y)
    return path
