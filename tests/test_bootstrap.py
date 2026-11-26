import os
import pytest

pytestmark = pytest.mark.ui

try:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from nexus.app.bootstrap import main
    HAS_QT = True
except (ImportError, Exception):
    HAS_QT = False

if not HAS_QT:
    pytest.skip("PySide6 system libraries not available in this environment", allow_module_level=True)


def test_bootstrap_main_launches_and_exits(monkeypatch):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["NEXUS_SIMULATE"] = "1"

    app = QApplication.instance() or QApplication([])

    def quit_timer():
        cur_app = QApplication.instance()
        if cur_app:
            cur_app.quit()

    QTimer.singleShot(50, quit_timer)
    ret = main()
    assert ret == 0
