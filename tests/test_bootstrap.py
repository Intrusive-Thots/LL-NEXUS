import os
import pytest
from PySide6.QtWidgets import QApplication

pytestmark = pytest.mark.ui

def test_bootstrap_main_launches_and_exits(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("NEXUS_SIMULATE", "1")

    from nexus.app import bootstrap

    monkeypatch.setattr(QApplication, "exec", lambda self: 0)

    res = bootstrap.main()
    assert res == 0
