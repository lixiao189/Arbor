import sys

import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from mind_demo.app import MainWindow

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
    QTest.keyClick(w.view, k, mods)
    QApplication.processEvents()


def type_text(w, s):
    QTest.keyClicks(w.view, s)
    QApplication.processEvents()


def test_xmind_flow(win):
    v = win.view
    root = v.root
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
    key(win, K.Key_Right)
    QTest.keyClicks(v, "X")
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

    start = v.items[src].pos()
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
    drag(win, m1, v.items[m2].pos())
    assert m1.parent is m2 and v.drag is None and v.selected is m1
    assert v.root.children[0] is m2
    key(win, K.Key_Z, M.ControlModifier)
    assert [c.text for c in v.root.children] == [f"Main Topic {i}" for i in range(1, 5)]


def test_drag_to_edge_reorders_and_esc_cancels(win):
    v = win.view
    m1, m2 = v.root.children[:2]
    item = v.items[m2]
    below = item.pos() + QPointF(0, item.size()[1] / 2 - 2)
    drag(win, m1, below)
    assert [c.text for c in v.root.children][:2] == ["Main Topic 2", "Main Topic 1"]

    m3 = v.root.children[2]
    drag(win, m3, v.items[v.root.children[0]].pos(), release=False)
    assert v.drag is not None and v.drag.target is not None
    key(win, K.Key_Escape)
    assert v.drag is None and m3.parent is v.root
