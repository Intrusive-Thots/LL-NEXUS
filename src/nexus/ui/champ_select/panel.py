from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...core.champions.models import Champion
from ..champion.grid import NexusChampionGrid
from ..components.base import NexusSearch
from ..theme import tokens as T


class ChampionSelectPanel(QWidget):
    manual_select = Signal(str)

    def __init__(self, controller, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._last_sig: Optional[tuple] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(T.SP_2)

        header_row = QHBoxLayout()
        header_row.setSpacing(T.SP_2)
        title = QLabel("CHAMPION POOL")
        title.setObjectName("Headline")
        header_row.addWidget(title)

        self.count_label = QLabel("")
        self.count_label.setObjectName("Secondary")
        header_row.addWidget(self.count_label)
        header_row.addStretch(1)

        self.search = NexusSearch("Search champions (name or role)…")
        self.search.textChanged.connect(self._on_search_changed)
        header_row.addWidget(self.search, 1)
        root.addLayout(header_row)

        self.grid = NexusChampionGrid(self, base_tile=88)
        self.grid.tile_clicked.connect(self._on_tile_clicked)
        root.addWidget(self.grid, 1)

        self.refresh()

    def _on_search_changed(self, _text: str) -> None:
        self.refresh(force=True)

    def _on_tile_clicked(self, champion: Champion) -> None:
        self.manual_select.emit(champion.name)

    def refresh(self, force: bool = False) -> None:
        if not self.controller.catalog:
            return

        q = self.search.text().strip().lower()
        ids = self.controller._port.available_champion_ids()
        avail_frozen = frozenset(ids) if ids is not None else None
        snap = self.controller.manager.snapshot()
        taken = frozenset(set(snap.banned_ids) | set(snap.ally_pick_ids) | set(snap.enemy_pick_ids))
        priorities_rev = tuple((p.champion_key, p.priority) for p in self.controller.priorities.all)

        sig = (q, avail_frozen, taken, priorities_rev)
        if not force and sig == self._last_sig:
            return
        self._last_sig = sig

        unavailable_ids = set() if ids is None else {c.id for c in self.controller.catalog.all if c.id not in ids}

        all_champs = self.controller.catalog.all
        if q:
            filtered = [
                c for c in all_champs
                if q in c.name.lower() or any(q in r.lower() for r in c.roles)
            ]
        else:
            filtered = list(all_champs)

        ranks: dict[str, int] = {}
        flags: dict[str, str] = {}
        for c in filtered:
            pref = self.controller.priorities.get(c.key)
            if pref and pref.priority is not None:
                ranks[c.key] = pref.priority
            if c.id in snap.banned_ids:
                flags[c.key] = "BANNED"
            elif c.id in snap.ally_pick_ids:
                flags[c.key] = "ALLY"
            elif c.id in snap.enemy_pick_ids:
                flags[c.key] = "ENEMY"
            elif c.id in unavailable_ids:
                flags[c.key] = "UNAVAIL"

        self.count_label.setText(f"{len(filtered)} champions")
        self.grid.populate(filtered, ranks=ranks, flags=flags, keep_selection=True)
