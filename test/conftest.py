import os

# Run Qt without a display server (CI has no X11/Wayland, no GPU).
# Must be set before QApplication is created.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """A single offscreen QApplication for the whole test session.

    QObject subclasses (Model, Pacer, View) require a running QApplication,
    but the offscreen platform plugin means no real window is ever shown.
    """
    app = QApplication.instance() or QApplication([])
    yield app
