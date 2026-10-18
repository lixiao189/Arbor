"""Render the layered icon SVGs into a Windows .ico file.

Usage: python packaging/icon/make_ico.py <output .ico>

Each size is stored as a PNG, which Windows reads since Vista. Qt's ICO writer
only writes one image per file, so the container is written here.
"""

import struct
import sys
from pathlib import Path

from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtGui import QGuiApplication

from render import PLAIN_SHAPE_RADIUS, PLAIN_SHAPE_SIZE, render

# The sizes Windows asks for at 100-250% scaling (title bar, taskbar, Explorer).
SIZES = [16, 20, 24, 32, 40, 48, 64, 256]

ICO_TYPE_ICON = 1
HEADER = struct.Struct("<HHH")  # reserved, type, image count
ENTRY = struct.Struct("<BBBBHHII")  # width, height, colours, reserved, planes, bpp, size, offset
COLOUR_PLANES = 1
BITS_PER_PIXEL = 32
MAX_BYTE_SIZE = 255  # larger widths and heights are stored as 0, meaning 256


def png_bytes(size: int) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    render(size, PLAIN_SHAPE_SIZE, PLAIN_SHAPE_RADIUS).save(buffer, "PNG")
    return bytes(buffer.data().data())


def main() -> None:
    out = Path(sys.argv[1])
    _app = QGuiApplication([])
    images = [png_bytes(size) for size in SIZES]
    offset = HEADER.size + ENTRY.size * len(images)
    data = [HEADER.pack(0, ICO_TYPE_ICON, len(images))]
    for size, image in zip(SIZES, images):
        side = size if size <= MAX_BYTE_SIZE else 0
        data.append(ENTRY.pack(side, side, 0, 0, COLOUR_PLANES, BITS_PER_PIXEL, len(image), offset))
        offset += len(image)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"".join(data + images))


if __name__ == "__main__":
    main()
