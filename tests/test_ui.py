import os
import pytest

pytestmark = pytest.mark.ui

try:
    from PySide6.QtWidgets import QApplication
    from nexus.app.controller import AppController
    from nexus.ui.compact.overlay import CompactOverlay
    from nexus.ui.shell.main_window import MainWindow
    HAS_QT = True
except (ImportError, Exception):
    HAS_QT = False

if not HAS_QT:
    pytest.skip("PySide6 system libraries not available in this environment", allow_module_level=True)


@pytest.fixture(scope="session")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["NEXUS_SIMULATE"] = "1"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_main_window_pages_and_navigation(qapp):
    controller = AppController(simulate=True)
    controller.start()

    window = MainWindow(controller)
    assert len(window.pages) == 5

    for name in ("Champ Select", "Automation", "Profile", "Settings", "Developer"):
        window._show(name)
        assert window.stack.currentWidget() == window.pages[name]

    assert hasattr(window, "scenario_box")
    assert window.scenario_box.count() > 0
    window._sim_feed("CONNECT")
    window._sim_feed("LOBBY")
    window._sim_reset()

    window._refresh()
    controller.shutdown()
    window.close()


def test_compact_overlay(qapp):
    controller = AppController(simulate=True)
    controller.start()

    overlay = CompactOverlay(controller)
    overlay.refresh()
    assert overlay.status.text() != ""

    controller.shutdown()
    overlay.close()
