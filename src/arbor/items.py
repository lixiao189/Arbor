"""Graphics items for a topic: its label/inline editor, body and fold badge."""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFocusEvent, QFont, QKeyEvent, QPainter, QPen, QTextLayout, QTextOption
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsItem,
    QGraphicsSceneMouseEvent,
    QGraphicsTextItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

from .layout import Side
from .model import Topic
from .style import MAX_TEXT_WIDTH, SELECTION, SUB_TEXT, Z, branch_color, make_pen, style_for

if TYPE_CHECKING:
    from .canvas import MindMapView

# Modifiers for toggling a topic in the selection. On macOS Qt reports Cmd as Control and the
# physical Ctrl key as Meta (and turns Ctrl+click into a right-click), so accept all of them.
TOGGLE_MODIFIERS = (
    Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.ShiftModifier
)
NO_WRAP = -1  # QGraphicsTextItem text width that disables wrapping
UNWRAPPED_WIDTH = 1e6  # QTextLayout line width that effectively disables wrapping
MIN_TEXT_WIDTH = 12  # keeps an empty topic clickable
UNDERLINE_WIDTH = 2  # subtopics are drawn as an underline instead of a box
SELECTION_WIDTH = 2.2
SELECTION_GAP = 3.5  # between the topic body and the selection outline
SELECTION_RADIUS_EXTRA = 3  # outline corners are rounder than the body's
BOUNDS_MARGIN = 5  # must cover SELECTION_GAP plus half of SELECTION_WIDTH


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


@cache
def label_font(size: int, bold: bool) -> QFont:
    font = QFont()
    font.setPointSize(size)
    font.setBold(bold)
    return font


def layout_text(text: str, font: QFont) -> tuple[list[QTextLayout], float, float]:
    """Lay out plain text the way an unwrapped-then-capped ``TopicText`` would.

    Returns the laid-out paragraphs and the text's width and height.
    """
    option = QTextOption()
    option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)

    def run(width: float) -> tuple[list[QTextLayout], float, float]:
        layouts, natural, y = [], 0.0, 0.0
        for paragraph in (text or " ").split("\n"):
            tl = QTextLayout(paragraph, font)
            tl.setTextOption(option)
            tl.beginLayout()
            while (line := tl.createLine()).isValid():
                line.setLineWidth(width)
                line.setPosition(QPointF(0, y))
                y += line.height()
                natural = max(natural, line.naturalTextWidth())
            tl.endLayout()
            layouts.append(tl)
        return layouts, natural, y

    layouts, natural, height = run(UNWRAPPED_WIDTH)
    if natural <= MAX_TEXT_WIDTH:
        return layouts, natural, height
    layouts, _, height = run(MAX_TEXT_WIDTH)
    return layouts, MAX_TEXT_WIDTH, height


class TopicItem(QGraphicsItem):
    """A topic's body. Its text is painted directly; a ``TopicText`` exists only while editing."""

    def __init__(self, topic: Topic, canvas: MindMapView) -> None:
        super().__init__()
        self.topic = topic
        self.canvas = canvas
        self.style = style_for(topic)
        self.color = branch_color(topic)
        self.selected = False
        self.toggling = False  # this press was a Ctrl+click: no drag, no narrowing on release
        self.side = Side.CENTER
        self._w = self._h = 0.0
        self.font = label_font(self.style.font_size, self.style.bold)
        self.text_color = QColor(Qt.GlobalColor.white) if self.style.filled else SUB_TEXT
        self.label: TopicText | None = None  # the inline editor, while editing
        self._layouts: list[QTextLayout] = []
        self._text_rect = QRectF()
        self.set_text(topic.text)
        self.setZValue(Z.TOPIC)

    def is_editing(self) -> bool:
        return self.label is not None

    def set_text(self, text: str) -> None:
        self._layouts, w, h = layout_text(text, self.font)
        self._set_text_size(w, h)

    def open_editor(self) -> TopicText:
        label = self.label = TopicText(self)
        label.setFont(self.font)
        label.setDefaultTextColor(self.text_color)
        label.document().setDocumentMargin(0)
        label.setPlainText(self.topic.text or " ")
        label.document().contentsChanged.connect(self._on_text_changed)
        self._fit_editor()
        self.update()
        return label

    def close_editor(self) -> str:
        """Remove the editor and return its text; the caller sets the text to show."""
        label, self.label = self.label, None
        text = label.toPlainText()
        label.document().contentsChanged.disconnect(self._on_text_changed)
        if label.scene() is not None:
            label.scene().removeItem(label)
        self.update()
        return text

    def _fit_editor(self) -> None:
        label = self.label
        label.setTextWidth(NO_WRAP)
        if label.boundingRect().width() > MAX_TEXT_WIDTH:
            label.setTextWidth(MAX_TEXT_WIDTH)
        r = label.boundingRect()
        self._set_text_size(r.width(), r.height())
        label.setPos(self._text_rect.topLeft())

    def _set_text_size(self, w: float, h: float) -> None:
        self.prepareGeometryChange()
        self._text_rect = QRectF(-w / 2, -h / 2, w, h)
        self._w = max(w, MIN_TEXT_WIDTH) + 2 * self.style.pad_x
        self._h = h + 2 * self.style.pad_y

    def _on_text_changed(self) -> None:
        if self.label is not None and self.label.is_editing():
            self._fit_editor()
            self.canvas.apply_layout()

    def size(self) -> tuple[float, float]:
        return self._w, self._h

    def body_rect(self) -> QRectF:
        return QRectF(-self._w / 2, -self._h / 2, self._w, self._h)

    def boundingRect(self) -> QRectF:
        return self.body_rect().adjusted(-BOUNDS_MARGIN, -BOUNDS_MARGIN, BOUNDS_MARGIN, BOUNDS_MARGIN)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.body_rect()
        if self.style.filled:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.color)
            painter.drawRoundedRect(rect, self.style.radius, self.style.radius)
        else:
            painter.setPen(make_pen(self.color, UNDERLINE_WIDTH))
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        if self.selected:
            painter.setPen(QPen(SELECTION, SELECTION_WIDTH))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            r = self.style.radius + SELECTION_RADIUS_EXTRA
            painter.drawRoundedRect(rect.adjusted(-SELECTION_GAP, -SELECTION_GAP, SELECTION_GAP, SELECTION_GAP), r, r)
        if self.label is None:
            painter.setPen(self.text_color)
            for tl in self._layouts:
                tl.draw(painter, self._text_rect.topLeft())

    def anchor_out(self) -> QPointF:
        """Where edges to this topic's children start."""
        r = self.body_rect()
        x = 0.0 if self.side is Side.CENTER else self.side * r.width() / 2
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
                or self.is_editing()
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
        if not self.is_editing():
            self.canvas.select(self.topic)
            self.canvas.start_edit()
        event.accept()


class FoldBadge(QGraphicsItem):
    """Circle beside a collapsed topic showing how many topics are hidden."""

    RADIUS = 9
    BOUNDS_MARGIN = 1  # room for the outline pen
    PEN_WIDTH = 1.5
    FONT_SIZE = 8
    MAX_COUNT = 99  # larger counts show as "99+"

    def __init__(self, item: TopicItem) -> None:
        super().__init__()
        self.item = item
        self.count = item.topic.descendant_count()
        self.setZValue(Z.FOLD_BADGE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def boundingRect(self) -> QRectF:
        r = self.RADIUS + self.BOUNDS_MARGIN
        return QRectF(-r, -r, 2 * r, 2 * r)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self.item.color, self.PEN_WIDTH))
        painter.setBrush(QColor("white"))
        painter.drawEllipse(QPointF(0, 0), self.RADIUS, self.RADIUS)
        font = QFont()
        font.setPointSize(self.FONT_SIZE)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(self.item.color)
        text = str(self.count) if self.count <= self.MAX_COUNT else f"{self.MAX_COUNT}+"
        painter.drawText(self.boundingRect(), Qt.AlignmentFlag.AlignCenter, text)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self.item.canvas.select(self.item.topic)
        self.item.canvas.toggle_collapse()
        event.accept()

