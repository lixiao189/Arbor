import sys

import pytest
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from arbor import icon

ICON_SIZES = [16, 24, 32, 48, 64, 128, 256]


@pytest.fixture
def app(qapp):
    yield qapp
    QApplication.setWindowIcon(QIcon())
    QApplication.setDesktopFileName("")


def test_app_icon_has_every_size(app):
    sizes = sorted(size.width() for size in icon.app_icon().availableSizes())
    assert sizes == ICON_SIZES


def test_install_sets_window_icon_on_linux(app, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    icon.install(app)
    assert not QApplication.windowIcon().isNull()
    assert QApplication.desktopFileName() == icon.DESKTOP_FILE_NAME


def test_install_keeps_bundle_icon_on_macos(app, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    icon.install(app)
    assert QApplication.windowIcon().isNull()
