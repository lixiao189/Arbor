"""Render the layered icon SVGs into a macOS .icns file.

Usage: python packaging/icon/make_icns.py <output .icns>

The layers (the background, then the Icon Composer layers in Arbor.icon/Assets)
are drawn back to front and clipped to the macOS app icon shape (a
continuous-corner rounded square inset in the 1024 canvas), so the result
matches what Icon Composer produces and macOS Tahoe doesn't put it on a plate.
Needs PyQt6 (QtSvg) and macOS's iconutil.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QGuiApplication, QImage, QPainter, QPainterPath
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

# macOS app icon grid, in units of the 1024 canvas.
CANVAS = 1024
SHAPE_SIZE = 824
SHAPE_RADIUS = 185.4

# iconutil wants these point sizes, each at @1x and @2x.
ICONSET_SIZES = [16, 32, 128, 256, 512]
SCALES = [1, 2]

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


def render(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    scale = size / CANVAS
    inset = (CANVAS - SHAPE_SIZE) / 2 * scale
    shape = QRectF(inset, inset, SHAPE_SIZE * scale, SHAPE_SIZE * scale)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setClipPath(icon_shape(shape, SHAPE_RADIUS * scale))
    for layer in LAYERS:
        QSvgRenderer(str(layer)).render(painter, shape)
    painter.end()
    return image


def main() -> None:
    out = Path(sys.argv[1])
    _app = QGuiApplication([])
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp, "Arbor.iconset")
        iconset.mkdir()
        for points in ICONSET_SIZES:
            for scale in SCALES:
                suffix = "" if scale == 1 else f"@{scale}x"
                render(points * scale).save(str(iconset / f"icon_{points}x{points}{suffix}.png"))
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["iconutil", "-c", "icns", "-o", out, iconset], check=True)


if __name__ == "__main__":
    main()
