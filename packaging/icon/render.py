"""Draw the app icon from its layer SVGs; shared by the per-platform icon scripts.

The layers (the background, then the Icon Composer layers in Arbor.icon/Assets)
are drawn back to front and clipped to a continuous-corner rounded square
centred in the 1024 canvas. Needs PyQt6 (QtSvg) and a QGuiApplication.
"""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QImage, QPainter, QPainterPath
from PyQt6.QtSvg import QSvgRenderer

HERE = Path(__file__).parent
ICON_ASSETS = HERE / "Arbor.icon" / "Assets"
# Arbor.icon draws the background as its fill (see icon.json), so it is the
# only layer kept outside the bundle.
LAYERS = [
    HERE / "0-background.svg",
    ICON_ASSETS / "1-branches.svg",
    ICON_ASSETS / "2-subtopics.svg",
    ICON_ASSETS / "3-root.svg",
]

CANVAS = 1024

# Windows and Linux don't mask app icons to a shape, so elsewhere the same
# shape fills more of the canvas, keeping a thin margin like their own icons.
PLAIN_SHAPE_SIZE = 896
PLAIN_SHAPE_RADIUS = 201.6  # the macOS 185.4 radius, scaled with the shape

# Apple's continuous corner, as (along-edge, inward) offsets in units of the
# corner radius: three curves (control, control, end) joined by short lines.
CORNER_START = 1.52866483
CORNER_CURVES = [
    ((1.08849323, 0.0), (0.86840689, 0.0), (0.66993427, 0.06549600)),
    ((0.37282392, 0.16905899), (0.16906013, 0.37282401), (0.07491100, 0.63149399)),
    ((0.0, 0.86840689), (0.0, 1.08849323), (0.0, CORNER_START)),
]
CORNER_LINES = [(0.63149399, 0.07491100), (0.06549600, 0.66993427)]


def icon_shape(rect: QRectF, radius: float) -> QPainterPath:
    """The continuous-corner rounded rectangle macOS uses for app icons."""
    # Each corner: its point, and the unit vectors along the incoming edge
    # (towards the corner) and the outgoing edge (away from it).
    corners = [
        (rect.topRight(), QPointF(1, 0), QPointF(0, 1)),
        (rect.bottomRight(), QPointF(0, 1), QPointF(-1, 0)),
        (rect.bottomLeft(), QPointF(-1, 0), QPointF(0, -1)),
        (rect.topLeft(), QPointF(0, -1), QPointF(1, 0)),
    ]
    path = QPainterPath()
    for i, (corner, into, out) in enumerate(corners):

        def at(along: float, inward: float) -> QPointF:
            # `along` is the distance back from the corner on the incoming
            # edge; `inward` the distance along the outgoing edge.
            return corner - into * (along * radius) + out * (inward * radius)

        start = at(CORNER_START, 0)
        if i == 0:
            path.moveTo(start)
        else:
            path.lineTo(start)
        for k, (c1, c2, end) in enumerate(CORNER_CURVES):
            path.cubicTo(at(*c1), at(*c2), at(*end))
            if k < len(CORNER_LINES):
                path.lineTo(at(*CORNER_LINES[k]))
    path.closeSubpath()
    return path


def render(size: int, shape_size: float, shape_radius: float) -> QImage:
    """The icon at `size` px, its shape `shape_size` wide in units of the canvas."""
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    scale = size / CANVAS
    inset = (CANVAS - shape_size) / 2 * scale
    shape = QRectF(inset, inset, shape_size * scale, shape_size * scale)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setClipPath(icon_shape(shape, shape_radius * scale))
    for layer in LAYERS:
        QSvgRenderer(str(layer)).render(painter, shape)
    painter.end()
    return image
