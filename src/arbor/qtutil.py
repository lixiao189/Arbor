"""Helpers for working with PyQt6's type stubs."""

from __future__ import annotations


def required[T](value: T | None) -> T:
    """``value`` narrowed to non-``None``.

    For Qt getters such as ``viewport()`` or ``menuBar()`` that the stubs type as
    Optional but that always return an object in this app.
    """
    if value is None:
        raise RuntimeError("Qt returned None where an object was expected")
    return value
