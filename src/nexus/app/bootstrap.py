from __future__ import annotations
import os,sys
from PySide6.QtWidgets import QApplication
from .controller import AppController
from nexus.ui.shell.main_window import MainWindow
def main()->int:
    app=QApplication(sys.argv); app.setApplicationName("LeagueLoop Nexus")
    controller=AppController(simulate=os.environ.get("NEXUS_SIMULATE")=="1"); controller.start()
    window=MainWindow(controller); window.show(); app.aboutToQuit.connect(controller.shutdown)
    return app.exec()
if __name__=="__main__": raise SystemExit(main())
