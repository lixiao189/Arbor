"""Graphics view that renders and edits a mind map."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QTextCursor,
    QUndoStack,
    QWheelEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)

from . import clipboard, model
from .drag import DragState, Marquee, indicator_path, make_band, make_indicator
from .items import FoldBadge, TopicItem
from .layout import Placement, drop_target, layout, neighbor
from .model import Topic
from .qtutil import required
from .render import node_for, render
from .style import DRAG_DIM, DRAG_GHOST_OPACITY, Z, make_pen, theme
from .undo import SnapshotCommand

MIN_ZOOM, MAX_ZOOM = 0.2, 4.0
WHEEL_ZOOM_BASE = 1.0015  # zoom factor per unit of wheel angle delta
SCENE_MARGIN_X, SCENE_MARGIN_Y = 2000, 1500  # pannable space around the map
FIT_MARGIN = 40  # around the map in "Fit Map"
SELECT_MARGIN = 60  # kept visible around the selected topic
AUTOSCROLL_MARGIN = 30  # kept visible around the cursor while dragging
FOLD_BADGE_GAP = 3  # between a collapsed topic and its badge
ROOT_EDGE_BEND = (
    0.2  # root edges reach the child's height this fraction of the way across
)
GHOST_OFFSET_X, GHOST_OFFSET_Y = 14, 10  # drag ghost, below-right of the cursor


class MindMapView(QGraphicsView):
    editingChanged = pyqtSignal(bool)
    selectionChanged = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.map_scene = QGraphicsScene(self)
        self.setScene(self.map_scene)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
        )
        self.setBackgroundBrush(QBrush(theme().canvas_bg))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.undo_stack = QUndoStack(self)
        self.root: Topic = model.new_document()
        self.selected: Topic | None = (
            None  # primary selection: keyboard commands act on it
        )
        self.selection: list[
            Topic
        ] = []  # all selected topics, primary first; may be empty
        self.topic_items: dict[Topic, TopicItem] = {}
        self.edges: dict[TopicItem, QGraphicsPathItem] = {}  # keyed by the child's item
        self.badges: dict[TopicItem, FoldBadge] = {}
        self.placements: dict[Topic, Placement] = {}
        self.editing: TopicItem | None = None
        self.drag: DragState | None = None
        self.marquee: Marquee | None = None
        self._pan_from: QPoint | None = (
            None  # last cursor position while right-dragging, in viewport coordinates
        )
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
        return self.root.to_dict(keep_uids=True), self.selected.path() if self.selected else None

    def restore(self, snap: tuple) -> None:
        self.cancel_edit()
        data, path = snap
        self.root = Topic.from_dict(data)
        try:
            self.selected = self.root.at(path) if path is not None else None
        except IndexError:
            self.selected = self.root
        self.rebuild()

    def change(self, label: str, op: Callable[[Topic], Topic | None]) -> bool:
        """Run a model operation on the selected topic as one undoable step; ``op`` returns the new selection."""
        self.commit_edit()
        if self.selected is None:
            return False  # every command acts on the selection
        before = self.snapshot()
        result = op(self.selected)
        if result is None:
            return False
        self.selected = result
        self.undo_stack.push(SnapshotCommand(self, label, before, self.snapshot()))
        self.rebuild()
        return True

    # --- rendering

    def rebuild(self) -> None:
        """Bring the scene in line with the tree, like a virtual DOM diff: ``render()``
        describes every visible topic, items are matched to nodes by ``uid`` (React's keys)
        and patched only where their node differs; the rest are added or removed."""
        self.cancel_drag()
        self.end_marquee()
        scene = self.map_scene
        old = {item.node.uid: item for item in self.topic_items.values()}
        self.topic_items = {}
        for topic, node in render(self.root).items():
            item = old.pop(node.uid, None)
            if item is None:
                item = TopicItem(topic, node, self)
                scene.addItem(item)
            else:
                item.topic = topic  # the same topic, possibly rebuilt by undo
                if item.patch(node) and item in self.badges:
                    self.badges[item].update()  # it draws the node's colour and count
                if item.selected:
                    item.selected = False  # reselected below
                    item.update()
            self.topic_items[topic] = item
        for item in old.values():
            scene.removeItem(item)
            for decorations in (self.edges, self.badges):
                if item in decorations:
                    scene.removeItem(decorations.pop(item))
        self.apply_layout()
        if self.selected is not None:
            self.select(self.selected)
        else:
            self.set_selection([])

    def apply_theme(self) -> None:
        """Repaint in the current light or dark theme."""
        self.setBackgroundBrush(QBrush(theme().canvas_bg))
        if self.editing is not None:
            self.commit_edit()  # rebuilds
        else:
            self.rebuild()
        self.map_scene.update()  # selection outlines and badges read the theme when painted

    def apply_layout(self) -> None:
        self.placements = layout(self.root, lambda t: self.topic_items[t].size())
        for topic, p in self.placements.items():
            item = self.topic_items[topic]
            item.side = p.side
            item.setPos(p.x, p.y)
        for item in self.topic_items.values():
            self._sync_edge(item)
            self._sync_badge(item)
        bounds = self.map_scene.itemsBoundingRect()
        self.map_scene.setSceneRect(
            bounds.adjusted(
                -SCENE_MARGIN_X, -SCENE_MARGIN_Y, SCENE_MARGIN_X, SCENE_MARGIN_Y
            )
        )

    def _sync_edge(self, child: TopicItem) -> None:
        """Create, update or remove the edge from a topic's parent to it."""
        edge, width, parent = (
            self.edges.get(child),
            child.node.edge_width,
            child.topic.parent,
        )
        if width is None or parent is None:
            if edge is not None:
                self.map_scene.removeItem(self.edges.pop(child))
            return
        path = self._edge_path(self.topic_items[parent], child)
        pen = make_pen(child.color, width)
        if edge is None:
            edge = self.edges[child] = QGraphicsPathItem()
            edge.setZValue(Z.EDGE)
            self.map_scene.addItem(edge)
        if edge.path() != path:
            edge.setPath(path)
        if edge.pen() != pen:
            edge.setPen(pen)

    def _sync_badge(self, item: TopicItem) -> None:
        """Create, update or remove the fold badge of a collapsed topic."""
        badge = self.badges.get(item)
        if item.node.hidden_count is None:
            if badge is not None:
                self.map_scene.removeItem(self.badges.pop(item))
            return
        if badge is None:
            badge = self.badges[item] = FoldBadge(item)
            self.map_scene.addItem(badge)
        side = item.side.outward
        badge.setPos(
            item.pos()
            + QPointF(
                side * (item.size()[0] / 2 + FoldBadge.RADIUS + FOLD_BADGE_GAP), 0
            )
        )

    @staticmethod
    def _edge_path(parent: TopicItem, child: TopicItem) -> QPainterPath:
        start, end = parent.anchor_out(), child.anchor_in()
        path = QPainterPath(start)
        mid = (start.x() + end.x()) / 2
        if parent.topic.is_root:
            path.cubicTo(
                QPointF(mid, start.y()),
                QPointF(start.x() + (end.x() - start.x()) * ROOT_EDGE_BEND, end.y()),
                end,
            )
        else:
            path.cubicTo(QPointF(mid, start.y()), QPointF(mid, end.y()), end)
        return path

    def center_root(self) -> None:
        self.centerOn(self.topic_items[self.root])

    # --- selection & navigation

    def select(self, topic: Topic) -> None:
        self.set_selection([topic])
        if self.selected is not None:
            self.ensureVisible(
                self.topic_items[self.selected], SELECT_MARGIN, SELECT_MARGIN
            )

    def set_selection(self, topics: list[Topic]) -> None:
        """Select several topics (or none); the first becomes the primary selection."""
        topics = [t for t in topics if t in self.topic_items]
        for t in self.selection:
            if t in self.topic_items:
                self.topic_items[t].selected = False
                self.topic_items[t].update()
        self.selection, self.selected = topics, topics[0] if topics else None
        for t in topics:
            self.topic_items[t].selected = True
            self.topic_items[t].update()
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
            self.select(
                self.root
            )  # XMind: with nothing selected, arrows start at the central topic
            return
        target = neighbor(self.selected, direction, self.placements)
        if target is not None:
            self.select(target)

    def select_root(self) -> None:
        self.select(self.root)
        self.center_root()

    # --- editing operations (XMind commands)

    def add_child(self) -> None:
        if self.change("Insert Subtopic", model.add_child):
            self.start_edit()

    def add_sibling(self, before: bool = False) -> None:
        if self.change("Insert Topic", lambda t: model.add_sibling(t, before)):
            self.start_edit()

    def insert_parent(self) -> None:
        if self.change("Insert Parent Topic", model.insert_parent):
            self.start_edit()

    def delete(self) -> None:
        label = "Delete Topics" if len(self.selection) > 1 else "Delete Topic"
        self.change(label, lambda _: model.remove_all(self.selection))

    def move_topic(self, delta: int) -> None:
        self.change("Move Topic", lambda t: model.move(t, delta))

    def toggle_collapse(self) -> None:
        def op(topic: Topic) -> Topic | None:
            if not topic.children:
                return None
            topic.collapsed = not topic.collapsed
            return topic

        self.change("Collapse/Expand", op)

    def set_all_collapsed(self, collapsed: bool) -> None:
        def op(topic: Topic) -> Topic | None:
            for t in topic.walk():
                if t is not topic or not collapsed:
                    t.collapsed = collapsed and bool(t.children)
            return topic

        self.change("Collapse All" if collapsed else "Expand All", op)

    def copy(self) -> None:
        if self.selection:
            required(QApplication.clipboard()).setMimeData(
                clipboard.to_mime(model.top_level(self.selection))
            )

    def cut(self) -> None:
        if any(not t.is_root for t in self.selection):
            self.copy()
            self.delete()

    def paste(self) -> None:
        topics = clipboard.from_mime(required(QApplication.clipboard()).mimeData())
        if not topics:
            return

        def op(target: Topic) -> Topic | None:
            last = None
            for t in topics:
                last = model.paste(target, t)
            return last

        self.change("Paste", op)

    # --- inline text editing

    def start_edit(self, initial_text: str | None = None) -> None:
        if self.editing is not None or self.selected is None:
            return
        if len(self.selection) > 1:
            self.set_selection([self.selected])
        item = self.topic_items[self.selected]
        self.editing = item
        self._edit_before = self.snapshot()
        label = item.open_editor()
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        # Queued so the editor is not torn down from inside its own signal handler.
        label.committed.connect(lambda: QTimer.singleShot(0, self.commit_edit))
        label.cancelled.connect(lambda: QTimer.singleShot(0, self.cancel_edit))
        label.tab_pressed.connect(
            lambda: QTimer.singleShot(0, self._commit_and_add_child)
        )
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

    def _end_edit(self) -> tuple[TopicItem, str] | None:
        """Close the editor; returns the edited item and the editor's text."""
        item, self.editing = self.editing, None
        if item is None:
            return None
        label = required(item.label)
        for sig in (label.committed, label.cancelled, label.tab_pressed):
            sig.disconnect()
        label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        label.clearFocus()
        text = item.close_editor()
        self.setFocus()
        self.editingChanged.emit(False)
        return item, text

    def commit_edit(self) -> None:
        ended = self._end_edit()
        if ended is None:
            return
        item, text = ended
        text = text.strip()
        topic = item.topic
        if text and text != topic.text and self._edit_before is not None:
            topic.text = text
            self.undo_stack.push(
                SnapshotCommand(self, "Edit Topic", self._edit_before, self.snapshot())
            )
        self.rebuild()

    def cancel_edit(self) -> None:
        ended = self._end_edit()
        if ended is not None:
            item = ended[0]
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
        ghost = TopicItem(topic, node_for(topic), self)
        if len(topics) > 1:
            ghost.set_text(f"{topic.text}  +{len(topics) - 1}")
        ghost.setOpacity(DRAG_GHOST_OPACITY)
        ghost.setZValue(Z.DRAG_GHOST)
        ghost.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        indicator = make_indicator()
        self.map_scene.addItem(ghost)
        self.map_scene.addItem(indicator)
        for t in topics:
            for d in t.walk_visible():
                self.topic_items[d].setOpacity(DRAG_DIM)
        self.drag = DragState(topic, topics, ghost, indicator)

    def update_drag(self, pos: QPointF) -> None:
        drag = self.drag
        if drag is None:
            return
        w, h = drag.ghost.size()
        drag.ghost.setPos(pos + QPointF(w / 2 + GHOST_OFFSET_X, h / 2 + GHOST_OFFSET_Y))
        drag.target = drop_target(drag.topics, pos.x(), pos.y(), self.placements)
        drag.indicator.setPath(indicator_path(drag.target, self.topic_items))
        self.ensureVisible(
            QRectF(pos, pos).adjusted(
                -AUTOSCROLL_MARGIN,
                -AUTOSCROLL_MARGIN,
                AUTOSCROLL_MARGIN,
                AUTOSCROLL_MARGIN,
            ),
            0,
            0,
        )

    def cancel_drag(self) -> None:
        drag, self.drag = self.drag, None
        if drag is None:
            return
        self.map_scene.removeItem(drag.ghost)
        self.map_scene.removeItem(drag.indicator)
        for t in drag.topics:
            for d in t.walk_visible():
                if d in self.topic_items:
                    self.topic_items[d].setOpacity(1.0)

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
        if self.change(
            label,
            lambda _: model.reparent_all(drag.topics, target.parent, target.index),
        ):
            if len(drag.topics) > 1:
                self.set_selection(
                    selection
                )  # topics keep their identity, so the group stays selected

    # --- marquee (drag on the empty canvas) selection

    def begin_marquee(self, origin: QPointF) -> None:
        if self.drag is not None:
            return
        self.commit_edit()
        band = make_band()
        self.map_scene.addItem(band)
        self.marquee = Marquee(origin, band, list(self.selection))
        required(self.viewport()).setCursor(Qt.CursorShape.CrossCursor)
        self.update_marquee(origin)

    def update_marquee(self, pos: QPointF) -> None:
        m = self.marquee
        if m is None:
            return
        rect = QRectF(m.origin, pos).normalized()
        m.band.setRect(rect)
        hits = [
            t
            for t, item in self.topic_items.items()
            if rect.intersects(item.body_rect().translated(item.pos()))
        ]
        self.set_selection(
            hits
        )  # a box touching nothing (a plain click) clears the selection
        self.ensureVisible(
            QRectF(pos, pos).adjusted(
                -AUTOSCROLL_MARGIN,
                -AUTOSCROLL_MARGIN,
                AUTOSCROLL_MARGIN,
                AUTOSCROLL_MARGIN,
            ),
            0,
            0,
        )

    def end_marquee(self, cancel: bool = False) -> None:
        m, self.marquee = self.marquee, None
        if m is None:
            return
        self.map_scene.removeItem(m.band)
        if cancel:
            self.set_selection(m.before)
        required(self.viewport()).unsetCursor()

    # --- view

    def zoom_by(self, factor: float) -> None:
        current = self.transform().m11()
        factor = max(MIN_ZOOM / current, min(MAX_ZOOM / current, factor))
        self.scale(factor, factor)

    def zoom_reset(self) -> None:
        self.resetTransform()
        self.ensureVisible(
            self.topic_items[self.selected or self.root], SELECT_MARGIN, SELECT_MARGIN
        )

    def fit_map(self) -> None:
        self.resetTransform()
        bounds = QRectF()
        for item in self.topic_items.values():
            bounds = bounds.united(item.sceneBoundingRect())
        self.fitInView(
            bounds.adjusted(-FIT_MARGIN, -FIT_MARGIN, FIT_MARGIN, FIT_MARGIN),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        if self.transform().m11() > 1:
            self.resetTransform()
            self.centerOn(bounds.center())

    # --- Qt events

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        event = required(event)
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
            and not mods
            & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
        ):
            self.start_edit(initial_text=text)
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        event = required(event)
        # XMind: left-drag on the empty canvas draws a selection box, right-drag pans.
        pos = event.position().toPoint()
        if event.button() == Qt.MouseButton.LeftButton and self.drag is None:
            hit = self.itemAt(pos)
            if hit is None or isinstance(hit, QGraphicsPathItem):
                self.begin_marquee(self.mapToScene(pos))
                return
        # On macOS a Ctrl+click arrives as a right-click with Meta: that toggles, it doesn't pan.
        if (
            event.button() == Qt.MouseButton.RightButton
            and not event.modifiers() & Qt.KeyboardModifier.MetaModifier
        ):
            self._pan_from = pos
            required(self.viewport()).setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        event = required(event)
        pos = event.position().toPoint()
        if self.marquee is not None:
            self.update_marquee(self.mapToScene(pos))
            return
        if self._pan_from is not None:
            delta, self._pan_from = pos - self._pan_from, pos
            for bar, d in (
                (self.horizontalScrollBar(), delta.x()),
                (self.verticalScrollBar(), delta.y()),
            ):
                bar = required(bar)
                bar.setValue(bar.value() - d)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        event = required(event)
        if event.button() == Qt.MouseButton.LeftButton and self.marquee is not None:
            self.end_marquee()
            return
        if event.button() == Qt.MouseButton.RightButton and self._pan_from is not None:
            self._pan_from = None
            required(self.viewport()).unsetCursor()
        super().mouseReleaseEvent(event)

    def focusNextPrevChild(self, next: bool) -> bool:
        return False  # Tab belongs to "Insert Subtopic", not focus traversal

    def wheelEvent(self, event: QWheelEvent | None) -> None:
        event = required(event)
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_by(WHEEL_ZOOM_BASE ** event.angleDelta().y())
        else:
            super().wheelEvent(event)
