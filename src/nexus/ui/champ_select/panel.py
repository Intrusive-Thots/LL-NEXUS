from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout,QLineEdit,QPushButton,QScrollArea,QVBoxLayout,QWidget,QLabel
class ChampionSelectPanel(QWidget):
    manual_select=Signal(str)
    def __init__(self,controller,parent=None):
        super().__init__(parent); self.controller=controller
        root=QVBoxLayout(self); root.addWidget(QLabel("Champion Pool"))
        self.search=QLineEdit(); self.search.setPlaceholderText("Search champions…"); self.search.textChanged.connect(self.refresh); root.addWidget(self.search)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); self.host=QWidget(); self.grid=QGridLayout(self.host); self.grid.setSpacing(8); self.scroll.setWidget(self.host); root.addWidget(self.scroll,1)
        self.refresh()
    def refresh(self):
        while self.grid.count():
            item=self.grid.takeAt(0); w=item.widget()
            if w: w.deleteLater()
        ids=self.controller._port.available_champion_ids()
        unavailable=set() if ids is None else {c.id for c in self.controller.catalog.all if c.id not in ids}
        champs=[c for c in self.controller.catalog.search(self.search.text()) if c.id not in unavailable]
        for i,c in enumerate(champs):
            b=QPushButton(c.name); b.setMinimumHeight(42); b.setToolTip(f"{c.name} · {', '.join(c.roles)}")
            b.clicked.connect(lambda _,n=c.name:self.manual_select.emit(n))
            self.grid.addWidget(b,i//6,i%6)
