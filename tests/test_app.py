import sys

import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from arbor.app import MainWindow
from arbor.layout import Side

K = Qt.Key
M = Qt.KeyboardModifier


@pytest.fixture
def win():
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    w.show()
    w.activateWindow()
    w.view.setFocus()
    app.processEvents()
    yield w
    w.view.cancel_edit()
    w.view.undo_stack.setClean()
    w.close()


def key(w, k, mods=M.NoModifier):
    QTest.keyClick(w.view, k, mods)  # ty: ignore[no-matching-overload]
    QApplication.processEvents()


def type_text(w, s):
    QTest.keyClicks(w.view, s)  # ty: ignore[missing-argument]
    QApplication.processEvents()


def test_xmind_flow(win):
    v = win.view
    root = v.root
    assert v.selected is None and v.selection == []  # nothing is selected at first
    key(win, K.Key_Tab)  # commands need a selection
    assert v.root.descendant_count() == 4 and v.editing is None
    key(win, K.Key_Right)  # the first arrow key selects the central topic
    assert v.selected is root
    key(win, K.Key_Right)
    main1 = v.selected
    assert main1.parent is root

    key(win, K.Key_Tab)  # new subtopic, in edit mode
    assert v.editing is not None and v.selected.parent is main1
    type_text(win, "Idea")
    key(win, K.Key_Return)  # commit
    assert v.editing is None and v.selected.text == "Idea"

    key(win, K.Key_Return)  # sibling after
    assert v.editing is not None
    key(win, K.Key_Escape)
    assert v.editing is None
    sib = v.selected
    assert sib.parent is main1 and sib.index == 1

    key(win, K.Key_Up)
    assert v.selected.text == "Idea"
    key(win, K.Key_Return, M.ControlModifier)  # insert parent
    key(win, K.Key_Escape)
    assert v.selected.children[0].text == "Idea"
    key(win, K.Key_Z, M.ControlModifier)
    assert v.root.at([0, 0]).text == "Idea"


def test_typing_replaces_text_and_undo(win):
    v = win.view
    key(win, K.Key_Home)
    key(win, K.Key_Right)
    QTest.keyClicks(v, "X")  # ty: ignore[missing-argument, invalid-argument-type]
    QApplication.processEvents()
    assert v.editing is not None
    type_text(win, "yz")
    key(win, K.Key_Return)
    assert v.selected.text == "Xyz"
    key(win, K.Key_Z, M.ControlModifier)
    assert v.selected.text == "Main Topic 1"
    key(win, K.Key_Z, M.ControlModifier | M.ShiftModifier)
    assert v.selected.text == "Xyz"


def test_delete_move_collapse(win):
    v = win.view
    key(win, K.Key_Home)
    key(win, K.Key_Right)
    first = v.selected
    key(win, K.Key_Down, M.AltModifier)
    assert v.root.children[1] is first
    key(win, K.Key_Tab)
    key(win, K.Key_Escape)
    key(win, K.Key_Left)
    assert v.selected is v.root.children[1]
    key(win, K.Key_Slash, M.ControlModifier)
    assert v.selected.collapsed
    key(win, K.Key_Backspace)
    assert len(v.root.children) == 3
    key(win, K.Key_Delete)
    assert len(v.root.children) == 2


def test_copy_paste(win):
    v = win.view
    key(win, K.Key_Home)
    key(win, K.Key_Right)
    key(win, K.Key_C, M.ControlModifier)
    key(win, K.Key_Down)
    key(win, K.Key_V, M.ControlModifier)
    assert v.selected.text == "Main Topic 1"
    assert v.selected.parent is v.root.children[1]


def test_destroying_dirty_window_does_not_touch_deleted_window():
    from PyQt6.QtCore import QCoreApplication, QEvent

    app = QApplication.instance() or QApplication([])
    errors = []
    old_hook = sys.excepthook
    sys.excepthook = lambda *exc: errors.append(exc)
    try:
        w = MainWindow()
        w.view.add_child()
        w.view.cancel_edit()
        w.deleteLater()
        del w
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        app.processEvents()
    finally:
        sys.excepthook = old_hook
    assert not errors


def drag(w, src, dst, release=True):
    """Press on topic ``src``, drag to scene point ``dst`` and (optionally) release."""
    v = w.view
    vp = v.viewport()

    def send(kind, scene_pt, buttons):
        local = QPointF(v.mapFromScene(scene_pt))
        btn = Qt.MouseButton.NoButton if kind == QMouseEvent.Type.MouseMove else Qt.MouseButton.LeftButton
        ev = QMouseEvent(kind, local, QPointF(vp.mapToGlobal(local.toPoint())), btn, buttons, M.NoModifier)
        QApplication.sendEvent(vp, ev)
        QApplication.processEvents()

    start = v.topic_items[src].pos()
    L = Qt.MouseButton.LeftButton
    send(QMouseEvent.Type.MouseButtonPress, start, L)
    for t in (0.1, 0.5, 1.0):
        send(QMouseEvent.Type.MouseMove, start + (dst - start) * t, L)
    if release:
        send(QMouseEvent.Type.MouseButtonRelease, dst, Qt.MouseButton.NoButton)
        QApplication.processEvents()


def test_drag_topic_onto_another_makes_it_a_child(win):
    v = win.view
    m1, m2 = v.root.children[:2]
    drag(win, m1, v.topic_items[m2].pos())
    assert m1.parent is m2 and v.drag is None and v.selected is m1
    assert v.root.children[0] is m2
    key(win, K.Key_Z, M.ControlModifier)
    assert [c.text for c in v.root.children] == [f"Main Topic {i}" for i in range(1, 5)]


def test_drag_to_edge_reorders_and_esc_cancels(win):
    v = win.view
    m1, m2 = v.root.children[:2]
    item = v.topic_items[m2]
    below = item.pos() + QPointF(0, item.size()[1] / 2 - 2)
    drag(win, m1, below)
    assert [c.text for c in v.root.children][:2] == ["Main Topic 2", "Main Topic 1"]

    m3 = v.root.children[2]
    drag(win, m3, v.topic_items[v.root.children[0]].pos(), release=False)
    assert v.drag is not None and v.drag.target is not None
    key(win, K.Key_Escape)
    assert v.drag is None and m3.parent is v.root


def mouse(w, kind, scene_pt, button=Qt.MouseButton.LeftButton, mods=M.NoModifier):
    v = w.view
    vp = v.viewport()
    local = QPointF(v.mapFromScene(scene_pt))
    btn = Qt.MouseButton.NoButton if kind == QMouseEvent.Type.MouseMove else button
    held = Qt.MouseButton.NoButton if kind == QMouseEvent.Type.MouseButtonRelease else button
    ev = QMouseEvent(kind, local, QPointF(vp.mapToGlobal(local.toPoint())), btn, held, mods)
    QApplication.sendEvent(vp, ev)
    QApplication.processEvents()


def canvas_drag(w, start, end, button=Qt.MouseButton.LeftButton, release=True):
    mouse(w, QMouseEvent.Type.MouseButtonPress, start, button)
    mouse(w, QMouseEvent.Type.MouseMove, (start + end) / 2, button)
    mouse(w, QMouseEvent.Type.MouseMove, end, button)
    if release:
        mouse(w, QMouseEvent.Type.MouseButtonRelease, end, button)


def box_around_right_topics(v):
    right = [t for t in v.root.children if v.placements[t].side is Side.RIGHT]
    rects = [v.topic_items[t].sceneBoundingRect() for t in right]
    start = QPointF(max(r.right() for r in rects) + 20, min(r.top() for r in rects) - 20)
    end = QPointF(v.topic_items[right[0]].pos().x(), max(r.bottom() for r in rects) + 5)
    return right, start, end


def test_left_drag_on_canvas_selects_multiple_and_deletes(win):
    v = win.view
    right, start, end = box_around_right_topics(v)
    canvas_drag(win, start, end, release=False)
    assert v.marquee is not None
    assert set(v.selection) == set(right) and v.root not in v.selection
    mouse(win, QMouseEvent.Type.MouseButtonRelease, end)
    assert v.marquee is None and set(v.selection) == set(right)

    key(win, K.Key_Delete)
    assert len(v.root.children) == 4 - len(right) and v.selection == [v.selected]
    key(win, K.Key_Z, M.ControlModifier)
    assert len(v.root.children) == 4


def test_esc_cancels_selection_box(win):
    v = win.view
    _, start, end = box_around_right_topics(v)
    canvas_drag(win, start, end, release=False)
    key(win, K.Key_Escape)
    assert v.marquee is None and v.selection == []
    mouse(win, QMouseEvent.Type.MouseButtonRelease, end)


def test_click_on_blank_canvas_clears_selection(win):
    v = win.view
    m1, m2 = v.root.children[:2]
    v.set_selection([m1, m2])
    _, start, _ = box_around_right_topics(v)
    mouse(win, QMouseEvent.Type.MouseButtonPress, start)
    mouse(win, QMouseEvent.Type.MouseButtonRelease, start)
    assert v.selection == [] and v.selected is None and v.marquee is None
    key(win, K.Key_Delete)  # nothing to delete
    assert len(v.root.children) == 4


def test_right_drag_pans_instead_of_selecting(win):
    v = win.view
    _, start, end = box_around_right_topics(v)
    h, vert = v.horizontalScrollBar().value(), v.verticalScrollBar().value()
    canvas_drag(win, start, end, Qt.MouseButton.RightButton)
    assert v.marquee is None and v.selection == []
    assert (v.horizontalScrollBar().value(), v.verticalScrollBar().value()) != (h, vert)


def test_copy_paste_multiple_topics(win):
    v = win.view
    m1, m2 = v.root.children[:2]
    v.set_selection([m1, m2])
    key(win, K.Key_C, M.ControlModifier)
    v.select(v.root.children[3])
    key(win, K.Key_V, M.ControlModifier)
    assert [c.text for c in v.root.children[3].children] == ["Main Topic 1", "Main Topic 2"]


def test_drag_moves_all_selected_topics(win):
    v = win.view
    m1, m2, m3, m4 = v.root.children
    v.set_selection([m1, m3])
    drag(win, m3, v.topic_items[m4].pos())
    assert m1.parent is m4 and m3.parent is m4 and m4.children[-2:] == [m1, m3]
    assert v.selection == [m1, m3] and v.drag is None
    key(win, K.Key_Z, M.ControlModifier)
    assert [c.text for c in v.root.children] == [f"Main Topic {i}" for i in range(1, 5)]


def test_click_in_group_without_dragging_selects_one(win):
    v = win.view
    m1, m2 = v.root.children[:2]
    v.set_selection([m1, m2])
    drag(win, m2, v.topic_items[m2].pos())  # press and release in place
    assert v.selection == [m2] and m1.parent is v.root


def ctrl_click(w, topic, mods=M.ControlModifier, button=Qt.MouseButton.LeftButton):
    v = w.view
    local = v.mapFromScene(v.topic_items[topic].pos())
    QTest.mouseClick(v.viewport(), button, mods, local)  # ty: ignore[no-matching-overload]
    QApplication.processEvents()


def test_ctrl_click_toggles_topics(win):
    v = win.view
    m1, m2, m3, _ = v.root.children
    v.select(m1)
    ctrl_click(win, m3)
    ctrl_click(win, m2)
    assert v.selection == [m1, m3, m2] and v.selected is m1
    ctrl_click(win, m1)  # removing the primary promotes the next topic
    assert v.selection == [m3, m2] and v.selected is m3
    ctrl_click(win, m3)
    ctrl_click(win, m2)  # the selection can become empty
    assert v.selection == [] and v.selected is None


def test_shift_and_mac_ctrl_click_also_toggle(win):
    v = win.view
    m1, m2, m3, _ = v.root.children
    v.select(m1)
    ctrl_click(win, m2, M.ShiftModifier)
    # On macOS the physical Ctrl key arrives as Meta, and Ctrl+click as a right-click.
    ctrl_click(win, m3, M.MetaModifier, Qt.MouseButton.RightButton)
    assert v.selection == [m1, m2, m3]
