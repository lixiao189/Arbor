"""Converting topics to and from clipboard data."""

from __future__ import annotations

import json

from PyQt6.QtCore import QMimeData

from . import model
from .model import Topic

MIME_TYPE = "application/x-arbor-topic"


def to_mime(topics: list[Topic]) -> QMimeData:
    """Topics as our own format (exact copy) plus an indented text outline for other apps."""
    data = QMimeData()
    data.setData(MIME_TYPE, json.dumps([t.to_dict() for t in topics]).encode())
    data.setText("\n".join(model.outline_text(t) for t in topics))
    return data


def from_mime(data: QMimeData | None) -> list[Topic]:
    """Topics to paste from clipboard data; empty if it holds nothing usable."""
    if data is None:
        return []
    if data.hasFormat(MIME_TYPE):
        payload = json.loads(bytes(data.data(MIME_TYPE)).decode())  # ty: ignore[invalid-argument-type]  # QByteArray supports the buffer protocol
        return [Topic.from_dict(d) for d in (payload if isinstance(payload, list) else [payload])]
    if data.hasText():
        return model.parse_outline(data.text())
    return []
