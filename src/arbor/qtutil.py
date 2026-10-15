"""Helpers for working with PyQt6's type stubs."""

from __future__ import annotations

from typing import Protocol, cast

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QWindow
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QWidget


class _KeyClick(Protocol):
    def __call__(
        self,
        widget: QWidget | QWindow,
        key: Qt.Key,
        modifier: Qt.KeyboardModifier = ...,
        delay: int = ...,
    ) -> None: ...


class _KeyClicks(Protocol):
    def __call__(
        self,
        widget: QWidget | QWindow,
        sequence: str,
        modifier: Qt.KeyboardModifier = ...,
        delay: int = ...,
    ) -> None: ...


class _MouseClick(Protocol):
    def __call__(
        self,
        widget: QWidget | QWindow,
        button: Qt.MouseButton,
        modifier: Qt.KeyboardModifier = ...,
        pos: QPoint = ...,
        delay: int = ...,
    ) -> None: ...


def required[T](value: T | None) -> T:
    """``value`` narrowed to non-``None``.

    For Qt getters such as ``viewport()`` or ``menuBar()`` that the stubs type as
    Optional but that always return an object in this app. Also used at the start
    of event handlers, whose stubs type the event as optional.
    """
    if value is None:
        raise RuntimeError("Qt returned None where an object was expected")
    return value


def key_click(
    widget: QWidget | QWindow,
    key: Qt.Key,
    modifier: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> None:
    """``QTest.keyClick`` typed as the static method it is.

    The PyQt6 stubs declare it as an instance method, so calling ``QTest.keyClick``
    does not match any overload.
    """
    cast(_KeyClick, QTest.keyClick)(widget, key, modifier)


def key_clicks(
    widget: QWidget | QWindow,
    sequence: str,
    modifier: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> None:
    """``QTest.keyClicks`` typed as the static method it is. See ``key_click``.

    The stubs also require a ``sequence`` argument that the runtime treats as optional.
    """
    cast(_KeyClicks, QTest.keyClicks)(widget, sequence, modifier)


def mouse_click(
    widget: QWidget | QWindow,
    button: Qt.MouseButton,
    modifier: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    pos: QPoint | None = None,
) -> None:
    """``QTest.mouseClick`` typed as the static method it is. See ``key_click``."""
    click = cast(_MouseClick, QTest.mouseClick)
    if pos is None:
        click(widget, button, modifier)
    else:
        click(widget, button, modifier, pos)
