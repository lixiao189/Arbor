"""Render the layered icon SVGs into the PNGs Arbor sets as its window icon.

Usage: python packaging/icon/make_pngs.py [output directory]

Writes arbor-<size>.png for each size into src/arbor/icons by default. The
PNGs are checked in, so rerun this after changing the layer SVGs. The Linux
build also installs them into the bundle's hicolor icon theme.
"""

import sys
from pathlib import Path

from PyQt6.QtGui import QGuiApplication

from render import HERE, PLAIN_SHAPE_RADIUS, PLAIN_SHAPE_SIZE, render

# The hicolor theme's usual app icon sizes; Qt picks the closest for a window.
SIZES = [16, 24, 32, 48, 64, 128, 256]
DEFAULT_OUT = HERE.parents[1] / "src" / "arbor" / "icons"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    _app = QGuiApplication([])
    out.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        render(size, PLAIN_SHAPE_SIZE, PLAIN_SHAPE_RADIUS).save(str(out / f"arbor-{size}.png"))


if __name__ == "__main__":
    main()
