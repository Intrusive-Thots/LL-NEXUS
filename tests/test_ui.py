import os
import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from nexus.app.controller import AppController
from nexus.ui.shell.main_window import MainWindow

@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

@pytest.mark.ui
def test_ui_main_window_lifecycle_and_navigation(qt_app, tmp_path):
    controller = AppController(data_dir=tmp_path, simulate=True)
    controller.start()

    window = MainWindow(controller)
    window.show()

    # Test page switches
    for page in ("Champ Select", "Automation", "Profile", "Settings", "Developer"):
        window._show(page)
        assert window.stack.currentWidget() == window.pages[page]

    # Test compact mode toggle
    window._toggle_compact()
    assert window.compact.isVisible()
    window._toggle_compact()
    assert not window.compact.isVisible()

    window.close()
    controller.shutdown()
