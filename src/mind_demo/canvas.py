"""Graphics view that renders and edits a mind map."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import QMimeData, QPoint, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFocusEvent,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QTextCursor,
    QUndoCommand,
    QUndoStack,
    QWheelEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsTextItem,
    QGraphicsView,
    QStyleOptionGraphicsItem,
    QWidget,
)

from . import model
from .layout import DropTarget, Placement, drop_target, layout, neighbor
from .model import Topic

MIME_TYPE = "application/x-mind-demo-topic"
CANVAS_BG = QColor("#FBFBFC")
SELECTION = QColor("#2F7BF5")
ROOT_FILL = QColor("#22304F")
SUB_TEXT = QColor("#2B2B2B")
PALETTE = [QColor(c) for c in ("#E8594A", "#F29B38", "#E9C33B", "#4DB86C", "#3D9BE0", "#8E6BD8")]
MAX_TEXT_WIDTH = 280
MIN_ZOOM, MAX_ZOOM = 0.2, 4.0
DRAG_DIM = 0.35
# Modifiers for toggling a topic in the selection. On macOS Qt reports Cmd as Control and the
# physical Ctrl key as Meta (and turns Ctrl+click into a right-click), so accept all of them.
TOGGLE_MODIFIERS = (
    Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.ShiftModifier
)


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


class TopicText(QGraphicsTextItem):
    """Text label of a topic; becomes an inline editor while editing."""

    committed = pyqtSignal()
    cancelled = pyqtSignal()
    tab_pressed = pyqtSignal()

    def is_editing(self) -> bool:
        return self.textInteractionFlags() != Qt.TextInteractionFlag.NoTextInteraction

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key, mods = event.key(), event.modifiers()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not mods & Qt.KeyboardModifier.ShiftModifier:
            self.committed.emit()
        elif key == Qt.Key.Key_Escape:
            self.cancelled.emit()
        elif key == Qt.Key.Key_Tab:
            self.tab_pressed.emit()
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        super().focusOutEvent(event)
        # Opening a menu or switching apps should not end the edit.
        if self.is_editing() and event.reason() not in (
            Qt.FocusReason.PopupFocusReason,
            Qt.FocusReason.ActiveWindowFocusReason,
        ):
            self.committed.emit()


class TopicItem(QGraphicsItem):
    def __init__(self, topic: Topic, canvas: MindMapView) -> None:
        super().__init__()
        self.topic = topic
        self.canvas = canvas
        self.style = style_for(topic)
        self.color = branch_color(topic)
        self.selected = False
        self.toggling = False  # this press was a Ctrl+click: no drag, no narrowing on release
        self.side = 0
        self._w = self._h = 0.0

        self.label = TopicText(self)
        font = QFont()
        font.setPointSize(self.style.font_size)
        font.setBold(self.style.bold)
        self.label.setFont(font)
        self.label.setDefaultTextColor(Qt.GlobalColor.white if self.style.filled else SUB_TEXT)
        self.label.document().setDocumentMargin(0)
        self.set_text(topic.text)
        self.label.document().contentsChanged.connect(self._on_text_changed)
        self.setZValue(1)

    def set_text(self, text: str) -> None:
        self.label.setTextWidth(-1)
        self.label.setPlainText(text or " ")
        self._fit()

    def _fit(self) -> None:
        self.label.setTextWidth(-1)
        if self.label.boundingRect().width() > MAX_TEXT_WIDTH:
            self.label.setTextWidth(MAX_TEXT_WIDTH)
        r = self.label.boundingRect()
        self.prepareGeometryChange()
        self._w = max(r.width(), 12) + 2 * self.style.pad_x
        self._h = r.height() + 2 * self.style.pad_y
        self.label.setPos(-r.width() / 2, -r.height() / 2)

    def _on_text_changed(self) -> None:
        if self.label.is_editing():
            self._fit()
            self.canvas.apply_layout()

    def size(self) -> tuple[float, float]:
        return self._w, self._h

    def body_rect(self) -> QRectF:
        return QRectF(-self._w / 2, -self._h / 2, self._w, self._h)

    def boundingRect(self) -> QRectF:
        return self.body_rect().adjusted(-5, -5, 5, 5)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.body_rect()
        if self.style.filled:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.color)
            painter.drawRoundedRect(rect, self.style.radius, self.style.radius)
        else:
            painter.setPen(make_pen(self.color, 2))
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        if self.selected:
            painter.setPen(QPen(SELECTION, 2.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            r = self.style.radius + 3
            painter.drawRoundedRect(rect.adjusted(-3.5, -3.5, 3.5, 3.5), r, r)

    def anchor_out(self) -> QPointF:
        """Where edges to this topic's children start."""
        r = self.body_rect()
        x = 0.0 if self.side == 0 else self.side * r.width() / 2
        y = r.bottom() if not self.style.filled else 0.0
        return self.pos() + QPointF(x, y)

    def anchor_in(self) -> QPointF:
        """Where the edge from the parent ends."""
        r = self.body_rect()
        y = r.bottom() if not self.style.filled else 0.0
        return self.pos() + QPointF(-self.side * r.width() / 2, y)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        # While editing, clicks on the text are taken by the label itself.
        # Pressing a topic of a multi-selection keeps the group so it can be dragged.
        self.toggling = bool(event.modifiers() & TOGGLE_MODIFIERS)
        if self.toggling:
            self.canvas.toggle_selected(self.topic)
        elif self.topic not in self.canvas.selection:
            self.canvas.select(self.topic)
        event.accept()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        canvas = self.canvas
        if canvas.drag is None:
            if (
                not event.buttons() & Qt.MouseButton.LeftButton
                or self.topic.is_root
                or self.toggling
                or self.label.is_editing()
            ):
                return
            moved = event.screenPos() - event.buttonDownScreenPos(Qt.MouseButton.LeftButton)
            if moved.manhattanLength() < QApplication.startDragDistance():
                return
            canvas.begin_drag(self.topic)
        canvas.update_drag(event.scenePos())

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self.canvas.drag is not None:
            # Dropping rebuilds the scene, which deletes this item: leave its handler first.
            pos = event.scenePos()
            QTimer.singleShot(0, lambda canvas=self.canvas: canvas.end_drag(pos))
        elif event.button() == Qt.MouseButton.LeftButton and len(self.canvas.selection) > 1 and not self.toggling:
            self.canvas.select(self.topic)  # a click without dragging selects just this topic

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if not self.label.is_editing():
            self.canvas.select(self.topic)
            self.canvas.start_edit()
        event.accept()


class FoldBadge(QGraphicsItem):
    """Circle beside a collapsed topic showing how many topics are hidden."""

    RADIUS = 9

    def __init__(self, item: TopicItem) -> None:
        super().__init__()
        self.item = item
        self.count = item.topic.descendant_count()
        self.setZValue(2)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def boundingRect(self) -> QRectF:
        r = self.RADIUS + 1
        return QRectF(-r, -r, 2 * r, 2 * r)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self.item.color, 1.5))
        painter.setBrush(QColor("white"))
        painter.drawEllipse(QPointF(0, 0), self.RADIUS, self.RADIUS)
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(self.item.color)
        text = str(self.count) if self.count < 100 else "99+"
        painter.drawText(self.boundingRect(), Qt.AlignmentFlag.AlignCenter, text)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self.item.canvas.select(self.item.topic)
        self.item.canvas.toggle_collapse()
        event.accept()


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


class SnapshotCommand(QUndoCommand):
    """Undo step storing the whole document before and after a change."""

    def __init__(self, canvas: MindMapView, label: str, before: tuple, after: tuple) -> None:
        super().__init__(label)
        self.canvas, self.before, self.after = canvas, before, after
        self._applied = True  # the change is already live when the command is pushed

    def redo(self) -> None:
        if self._applied:
            self._applied = False
            return
        self.canvas.restore(self.after)

    def undo(self) -> None:
        self.canvas.restore(self.before)


class MindMapView(QGraphicsView):
    editingChanged = pyqtSignal(bool)
    selectionChanged = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setBackgroundBrush(QBrush(CANVAS_BG))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.undo_stack = QUndoStack(self)
        self.root: Topic = model.new_document()
        self.selected: Topic | None = None  # primary selection: keyboard commands act on it
        self.selection: list[Topic] = []  # all selected topics, primary first; may be empty
        self.items: dict[Topic, TopicItem] = {}
        self.placements: dict[Topic, Placement] = {}
        self.editing: TopicItem | None = None
        self.drag: DragState | None = None
        self.marquee: Marquee | None = None
        self._pan_from: QPoint | None = None  # last cursor position while right-dragging, in viewport coordinates
        self._edit_before: tuple | None = None
        self.rebuild()

    # --- document

    def set_document(self, root: Topic) -> None:
        self.cancel_edit()
        self.root, self.selected, self.selection = root, None, []
        self.undo_stack.clear()
        self.rebuild()
        self.resetTransform()
        self.center_root()

    def snapshot(self) -> tuple:
        return self.root.to_dict(), self.selected.path() if self.selected else None

    def restore(self, snap: tuple) -> None:
        self.cancel_edit()
        data, path = snap
        self.root = Topic.from_dict(data)
        try:
            self.selected = self.root.at(path) if path is not None else None
        except IndexError:
            self.selected = self.root
        self.rebuild()

    def change(self, label: str, op: Callable[[], Topic | None]) -> bool:
        """Run a model operation as one undoable step; ``op`` returns the new selection."""
        self.commit_edit()
        if self.selected is None:
            return False  # every command acts on the selection
        before = self.snapshot()
        result = op()
        if result is None:
            return False
        self.selected = result
        self.undo_stack.push(SnapshotCommand(self, label, before, self.snapshot()))
        self.rebuild()
        return True

    # --- rendering

    def rebuild(self) -> None:
        self.drag = self.marquee = None
        scene = self.scene()
        scene.clear()
        self.items = {}
        for topic in self.root.walk_visible():
            item = TopicItem(topic, self)
            scene.addItem(item)
            self.items[topic] = item
        self.apply_layout()
        if self.selected is not None:
            self.select(self.selected)
        else:
            self.set_selection([])

    def apply_layout(self) -> None:
        self.placements = layout(self.root, lambda t: self.items[t].size())
        for topic, p in self.placements.items():
            item = self.items[topic]
            item.side = p.side
            item.setPos(p.x, p.y)
        for child in list(self.scene().items()):
            if isinstance(child, (QGraphicsPathItem, FoldBadge)):
                self.scene().removeItem(child)
        for topic, item in self.items.items():
            if topic.parent is not None:
                self._add_edge(self.items[topic.parent], item)
            if topic.collapsed and topic.children:
                badge = FoldBadge(item)
                side = item.side or 1
                badge.setPos(item.pos() + QPointF(side * (item.size()[0] / 2 + FoldBadge.RADIUS + 3), 0))
                self.scene().addItem(badge)
        bounds = self.scene().itemsBoundingRect()
        self.scene().setSceneRect(bounds.adjusted(-2000, -1500, 2000, 1500))

    def _add_edge(self, parent: TopicItem, child: TopicItem) -> None:
        start, end = parent.anchor_out(), child.anchor_in()
        path = QPainterPath(start)
        mid = (start.x() + end.x()) / 2
        if parent.topic.is_root:
            path.cubicTo(QPointF(mid, start.y()), QPointF(start.x() + (end.x() - start.x()) * 0.2, end.y()), end)
        else:
            path.cubicTo(QPointF(mid, start.y()), QPointF(mid, end.y()), end)
        edge = QGraphicsPathItem(path)
        width = 3.0 if parent.topic.is_root else 1.8
        edge.setPen(make_pen(child.color, width))
        edge.setZValue(0)
        self.scene().addItem(edge)

    def center_root(self) -> None:
        self.centerOn(self.items[self.root])

    # --- selection & navigation

    def select(self, topic: Topic) -> None:
        self.set_selection([topic])
        if self.selected is not None:
            self.ensureVisible(self.items[self.selected], 60, 60)

    def set_selection(self, topics: list[Topic]) -> None:
        """Select several topics (or none); the first becomes the primary selection."""
        topics = [t for t in topics if t in self.items]
        for t in self.selection:
            if t in self.items:
                self.items[t].selected = False
                self.items[t].update()
        self.selection, self.selected = topics, topics[0] if topics else None
        for t in topics:
            self.items[t].selected = True
            self.items[t].update()
        self.selectionChanged.emit()

    def toggle_selected(self, topic: Topic) -> None:
        """Ctrl+click: add ``topic`` to the selection, or remove it."""
        self.commit_edit()
        if topic not in self.selection:
            self.set_selection([*self.selection, topic])
        else:
            self.set_selection([t for t in self.selection if t is not topic])

    def navigate(self, direction: str) -> None:
        if self.selected is None:
            self.select(self.root)  # XMind: with nothing selected, arrows start at the central topic
            return
        target = neighbor(self.selected, direction, self.placements)
        if target is not None:
            self.select(target)

    def select_root(self) -> None:
        self.select(self.root)
        self.center_root()

    # --- editing operations (XMind commands)

    def add_child(self) -> None:
        if self.change("Insert Subtopic", lambda: model.add_child(self.selected)):
            self.start_edit()

    def add_sibling(self, before: bool = False) -> None:
        if self.change("Insert Topic", lambda: model.add_sibling(self.selected, before)):
            self.start_edit()

    def insert_parent(self) -> None:
        if self.change("Insert Parent Topic", lambda: model.insert_parent(self.selected)):
            self.start_edit()

    def delete(self) -> None:
        label = "Delete Topics" if len(self.selection) > 1 else "Delete Topic"
        self.change(label, lambda: model.remove_all(self.selection))

    def move(self, delta: int) -> None:
        self.change("Move Topic", lambda: model.move(self.selected, delta))

    def toggle_collapse(self) -> None:
        def op() -> Topic | None:
            if not self.selected.children:
                return None
            self.selected.collapsed = not self.selected.collapsed
            return self.selected

        self.change("Collapse/Expand", op)

    def set_all_collapsed(self, collapsed: bool) -> None:
        def op() -> Topic | None:
            for t in self.selected.walk():
                if t is not self.selected or not collapsed:
                    t.collapsed = collapsed and bool(t.children)
            return self.selected

        self.change("Collapse All" if collapsed else "Expand All", op)

    def copy(self) -> None:
        if not self.selection:
            return
        topics = model.top_level(self.selection)
        data = QMimeData()
        data.setData(MIME_TYPE, json.dumps([t.to_dict() for t in topics]).encode())
        data.setText("\n".join(model.outline_text(t) for t in topics))
        QApplication.clipboard().setMimeData(data)

    def cut(self) -> None:
        if any(not t.is_root for t in self.selection):
            self.copy()
            self.delete()

    def paste(self) -> None:
        data = QApplication.clipboard().mimeData()
        if data is None:
            return
        if data.hasFormat(MIME_TYPE):
            payload = json.loads(bytes(data.data(MIME_TYPE)).decode())
            topics = [Topic.from_dict(d) for d in (payload if isinstance(payload, list) else [payload])]
        elif data.hasText():
            topics = model.parse_outline(data.text())
        else:
            return

        def op() -> Topic | None:
            last = None
            for t in topics:
                last = model.paste(self.selected, t)
            return last

        self.change("Paste", op)

    # --- inline text editing

    def start_edit(self, initial_text: str | None = None) -> None:
        if self.editing is not None or self.selected is None:
            return
        if len(self.selection) > 1:
            self.set_selection([self.selected])
        item = self.items[self.selected]
        self.editing = item
        self._edit_before = self.snapshot()
        label = item.label
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        label.committed.connect(self.commit_edit, Qt.ConnectionType.QueuedConnection)
        label.cancelled.connect(self.cancel_edit, Qt.ConnectionType.QueuedConnection)
        label.tab_pressed.connect(self._commit_and_add_child, Qt.ConnectionType.QueuedConnection)
        label.setFocus(Qt.FocusReason.OtherFocusReason)
        cursor = label.textCursor()
        if initial_text is not None:
            label.setPlainText(initial_text)
            cursor = label.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
        else:
            cursor.select(QTextCursor.SelectionType.Document)
        label.setTextCursor(cursor)
        self.editingChanged.emit(True)

    def _end_edit(self) -> TopicItem | None:
        item, self.editing = self.editing, None
        if item is None:
            return None
        label = item.label
        for sig in (label.committed, label.cancelled, label.tab_pressed):
            sig.disconnect()
        label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        cursor = label.textCursor()
        cursor.clearSelection()
        label.setTextCursor(cursor)
        label.clearFocus()
        self.setFocus()
        self.editingChanged.emit(False)
        return item

    def commit_edit(self) -> None:
        item = self._end_edit()
        if item is None:
            return
        text = item.label.toPlainText().strip()
        topic = item.topic
        if text and text != topic.text:
            topic.text = text
            self.undo_stack.push(SnapshotCommand(self, "Edit Topic", self._edit_before, self.snapshot()))
        self.rebuild()

    def cancel_edit(self) -> None:
        item = self._end_edit()
        if item is not None:
            item.set_text(item.topic.text)
            self.apply_layout()

    def _commit_and_add_child(self) -> None:
        self.commit_edit()
        self.add_child()

    # --- drag and drop

    def begin_drag(self, topic: Topic) -> None:
        self.commit_edit()
        group = model.top_level([t for t in self.selection if not t.is_root])
        topics = group if topic in group else [topic]
        ghost = TopicItem(topic, self)
        if len(topics) > 1:
            ghost.set_text(f"{topic.text}  +{len(topics) - 1}")
        ghost.setOpacity(0.75)
        ghost.setZValue(10)
        ghost.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        indicator = QGraphicsPathItem()
        indicator.setZValue(9)
        indicator.setPen(make_pen(SELECTION, 3))
        self.scene().addItem(ghost)
        self.scene().addItem(indicator)
        for t in topics:
            for d in t.walk_visible():
                self.items[d].setOpacity(DRAG_DIM)
        self.drag = DragState(topic, topics, ghost, indicator)

    def update_drag(self, pos: QPointF) -> None:
        drag = self.drag
        if drag is None:
            return
        w, h = drag.ghost.size()
        drag.ghost.setPos(pos + QPointF(w / 2 + 14, h / 2 + 10))  # below-right of the cursor
        drag.target = drop_target(drag.topics, pos.x(), pos.y(), self.placements)
        drag.indicator.setPath(self._indicator_path(drag.target))
        self.ensureVisible(QRectF(pos, pos).adjusted(-30, -30, 30, 30), 0, 0)

    def _indicator_path(self, target: DropTarget | None) -> QPainterPath:
        path = QPainterPath()
        if target is None:
            return path
        item = self.items[target.anchor]
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

    def cancel_drag(self) -> None:
        drag, self.drag = self.drag, None
        if drag is None:
            return
        self.scene().removeItem(drag.ghost)
        self.scene().removeItem(drag.indicator)
        for t in drag.topics:
            for d in t.walk_visible():
                if d in self.items:
                    self.items[d].setOpacity(1.0)

    def end_drag(self, pos: QPointF) -> None:
        drag = self.drag
        if drag is None:
            return
        self.update_drag(pos)
        target = drag.target
        self.cancel_drag()
        if target is None:
            return
        selection = list(self.selection)
        label = "Move Topics" if len(drag.topics) > 1 else "Move Topic"
        if self.change(label, lambda: model.reparent_all(drag.topics, target.parent, target.index)):
            if len(drag.topics) > 1:
                self.set_selection(selection)  # topics keep their identity, so the group stays selected

    # --- marquee (drag on the empty canvas) selection

    def begin_marquee(self, origin: QPointF) -> None:
        if self.drag is not None:
            return
        self.commit_edit()
        band = QGraphicsRectItem()
        band.setPen(QPen(SELECTION, 1))
        fill = QColor(SELECTION)
        fill.setAlpha(40)
        band.setBrush(fill)
        band.setZValue(20)
        self.scene().addItem(band)
        self.marquee = Marquee(origin, band, list(self.selection))
        self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.update_marquee(origin)

    def update_marquee(self, pos: QPointF) -> None:
        m = self.marquee
        if m is None:
            return
        rect = QRectF(m.origin, pos).normalized()
        m.band.setRect(rect)
        hits = [t for t, item in self.items.items() if rect.intersects(item.body_rect().translated(item.pos()))]
        self.set_selection(hits)  # a box touching nothing (a plain click) clears the selection
        self.ensureVisible(QRectF(pos, pos).adjusted(-30, -30, 30, 30), 0, 0)

    def end_marquee(self, cancel: bool = False) -> None:
        m, self.marquee = self.marquee, None
        if m is None:
            return
        self.scene().removeItem(m.band)
        if cancel:
            self.set_selection(m.before)
        self.viewport().unsetCursor()

    # --- view

    def zoom_by(self, factor: float) -> None:
        current = self.transform().m11()
        factor = max(MIN_ZOOM / current, min(MAX_ZOOM / current, factor))
        self.scale(factor, factor)

    def zoom_reset(self) -> None:
        self.resetTransform()
        self.ensureVisible(self.items[self.selected or self.root], 60, 60)

    def fit_map(self) -> None:
        self.resetTransform()
        bounds = QRectF()
        for item in self.items.values():
            bounds = bounds.united(item.sceneBoundingRect())
        self.fitInView(bounds.adjusted(-40, -40, 40, 40), Qt.AspectRatioMode.KeepAspectRatio)
        if self.transform().m11() > 1:
            self.resetTransform()
            self.centerOn(bounds.center())

    # --- Qt events

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.drag is not None or self.marquee is not None:
            if event.key() == Qt.Key.Key_Escape:
                self.cancel_drag()
                self.end_marquee(cancel=True)
            return
        # XMind: typing on a selected topic starts editing and replaces its text.
        text = event.text()
        mods = event.modifiers()
        if (
            self.editing is None
            and text
            and text.isprintable()
            and not text.isspace()
            and not mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
        ):
            self.start_edit(initial_text=text)
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # XMind: left-drag on the empty canvas draws a selection box, right-drag pans.
        pos = event.position().toPoint()
        if event.button() == Qt.MouseButton.LeftButton and self.drag is None:
            hit = self.itemAt(pos)
            if hit is None or isinstance(hit, QGraphicsPathItem):
                self.begin_marquee(self.mapToScene(pos))
                return
        # On macOS a Ctrl+click arrives as a right-click with Meta: that toggles, it doesn't pan.
        if event.button() == Qt.MouseButton.RightButton and not event.modifiers() & Qt.KeyboardModifier.MetaModifier:
            self._pan_from = pos
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self.marquee is not None:
            self.update_marquee(self.mapToScene(pos))
            return
        if self._pan_from is not None:
            delta, self._pan_from = pos - self._pan_from, pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.marquee is not None:
            self.end_marquee()
            return
        if event.button() == Qt.MouseButton.RightButton and self._pan_from is not None:
            self._pan_from = None
            self.viewport().unsetCursor()
        super().mouseReleaseEvent(event)

    def focusNextPrevChild(self, next: bool) -> bool:
        return False  # Tab belongs to "Insert Subtopic", not focus traversal

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_by(1.0015 ** event.angleDelta().y())
        else:
            super().wheelEvent(event)
