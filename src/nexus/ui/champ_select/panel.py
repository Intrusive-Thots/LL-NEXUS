from __future__ import annotations
from PySide6.QtCore import Qt,Signal
from PySide6.QtWidgets import QGridLayout,QHBoxLayout,QLineEdit,QListWidget,QPushButton,QScrollArea,QVBoxLayout,QWidget,QLabel
from ...core.state.models import LeagueState
from ..components.base import NexusCard,NexusChampionTile
class ChampionSelectPanel(QWidget):
    manual_select=Signal(str)
    def __init__(self,controller,parent=None):
        super().__init__(parent); self.controller=controller; self._items=[]
        root=QVBoxLayout(self); root.addWidget(QLabel("Champion Pool"))
        self.search=QLineEdit(); self.search.setPlaceholderText("Search champions…"); self.search.textChanged.connect(self.refresh); root.addWidget(self.search)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); self.host=QWidget(); self.grid=QGridLayout(self.host); self.grid.setSpacing(8); self.scroll.setWidget(self.host); root.addWidget(self.scroll,1)
        self.refresh()
    def refresh(self):
        while self.grid.count(): item=self.grid.takeAt(0); w=item.widget(); w.deleteLater() if w else None
        snap=self.controller.manager.snapshot(); unavailable=set()
        ids=self.controller._port.available_champion_ids()
        if ids is not None: unavailable={c.id for c in self.controller.catalog.all if c.id not in ids}
        champs=[c for c in self.controller.catalog.search(self.search.text()) if c.id not in unavailable]
        for i,c in enumerate(champs):
            tile=NexusChampionTile(c); tile.clicked.connect(lambda _,n=c.name:self.manual_select.emit(n)); self.grid.addWidget(tile,i//6,i%6)
