from __future__ import annotations
import os
import sys
from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from nexus.app.controller import AppController
from nexus.core.champions.models import ASSET_CATALOG
from nexus.ui.shell.main_window import MainWindow


def main() -> int:
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("IntrusiveThots.LeagueLoopNexus.App")
        except Exception:
            pass

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("LeagueLoop Nexus")

    icon_path = ASSET_CATALOG.parent / "app.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    controller = AppController(simulate=os.environ.get("NEXUS_SIMULATE") == "1")
    controller.start()
    window = MainWindow(controller)
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    app.aboutToQuit.connect(controller.shutdown)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
