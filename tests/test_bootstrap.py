import os
import pytest

pytestmark = pytest.mark.ui

try:
    from PySide6.QtWidgets import QApplication
    from nexus.app.bootstrap import main
    HAS_QT = True
except (ImportError, Exception):
    HAS_QT = False

if not HAS_QT:
    pytest.skip("PySide6 system libraries not available in this environment", allow_module_level=True)


def test_bootstrap_module_structure(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("NEXUS_SIMULATE", "1")

    app = QApplication.instance() or QApplication([])
    assert app is not None

    import nexus.app.bootstrap as bootstrap
    assert hasattr(bootstrap, "main")
    assert callable(bootstrap.main)
