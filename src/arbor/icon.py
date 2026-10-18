"""The app icon on Windows and Linux, where a window shows its own icon.

The PNGs in icons/ are rendered by packaging/icon/make_pngs.py. On macOS the
icon comes from the app bundle (with its Liquid Glass variants), and setting a
window icon would replace it in the Dock, so it is left alone there.
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

ICON_DIR = Path(__file__).parent / "icons"
ICON_GLOB = "arbor-*.png"
# Matches arbor.desktop, which the Linux build ships; Wayland compositors take
# the window's icon from it.
DESKTOP_FILE_NAME = "arbor"
# Groups Arbor's windows on the Windows taskbar under its own icon, rather than
# under python.exe's when run from source.
APP_USER_MODEL_ID = "Arbor.Arbor"


def app_icon() -> QIcon:
    icon = QIcon()
    for path in sorted(ICON_DIR.glob(ICON_GLOB)):
        icon.addFile(str(path))
    return icon


def install(app: QApplication) -> None:
    """Give the app's windows the Arbor icon, except on macOS."""
    if sys.platform == "darwin":
        return
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    app.setDesktopFileName(DESKTOP_FILE_NAME)
    app.setWindowIcon(app_icon())
