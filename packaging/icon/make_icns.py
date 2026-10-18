"""Render the layered icon SVGs into a macOS .icns file.

Usage: python packaging/icon/make_icns.py <output .icns>

The layers are clipped to the macOS app icon shape (see render.py), inset in
the 1024 canvas as on Apple's grid, so the result matches what Icon Composer
produces and macOS Tahoe doesn't put it on a plate. Needs macOS's iconutil.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from PyQt6.QtGui import QGuiApplication

from render import render

# macOS app icon grid, in units of the 1024 canvas.
SHAPE_SIZE = 824
SHAPE_RADIUS = 185.4

# iconutil wants these point sizes, each at @1x and @2x.
ICONSET_SIZES = [16, 32, 128, 256, 512]
SCALES = [1, 2]


def main() -> None:
    out = Path(sys.argv[1])
    _app = QGuiApplication([])
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp, "Arbor.iconset")
        iconset.mkdir()
        for points in ICONSET_SIZES:
            for scale in SCALES:
                suffix = "" if scale == 1 else f"@{scale}x"
                image = render(points * scale, SHAPE_SIZE, SHAPE_RADIUS)
                image.save(str(iconset / f"icon_{points}x{points}{suffix}.png"))
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["iconutil", "-c", "icns", "-o", out, iconset], check=True)


if __name__ == "__main__":
    main()
