import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """The one QApplication for the whole session. Holding it in a function-scoped
    fixture freed it after every test, and PyQt then destroys every window and leaves
    stale entries in its wrapper map that crash a later MainWindow() (seen in CI on
    Linux ARM64)."""
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])
