import pytest
from PyQt6.QtCore import Qt
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
