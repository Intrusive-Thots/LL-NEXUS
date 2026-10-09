"""Profile page — champion priorities and session context (spec §10/§27).

Wraps NexusPriorityList with an "add champion" search so users can rank any
catalog champion, plus a small session summary card. All edits flow through
core PriorityList and are persisted via controller.save_priorities().
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from ...core.champions.priority import PriorityList
from ..champion.priority_list import NexusPriorityList
from ..components.base import (
    NexusButton, NexusCard, NexusHeader, NexusSearch,
)
from ..theme import tokens as T


class ProfilePage(QWidget):
    def __init__(self, controller, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.priorities: PriorityList = controller.priorities
        self.catalog = controller.catalog

        root = QVBoxLayout(self)
        root.setContentsMargins(T.SP_4, T.SP_4, T.SP_4, T.SP_4)
        root.setSpacing(T.SP_3)
        root.addWidget(NexusHeader(
            "Profile", "Champion priorities and session context"))

        row = QHBoxLayout()
        row.setSpacing(T.SP_3)

        # -- priority list card -------------------------------------------
        list_card = NexusCard(raised=True)
        list_card.body.setSpacing(T.SP_2)
        head = QHBoxLayout()
        title = QLabel("PRIORITY LIST"); title.setObjectName("Headline")
        head.addWidget(title, 1)
        self.count_badge = QLabel(""); self.count_badge.setObjectName("Secondary")
        head.addWidget(self.count_badge)
        list_card.body.addLayout(head)

        add_row = QHBoxLayout(); add_row.setSpacing(T.SP_2)
        self.search = NexusSearch("Add champion to priorities…")
        self.search.setAccessibleName("Add champion search")
        add_row.addWidget(self.search, 1)
        add_btn = NexusButton("ADD", variant="primary")
        add_btn.clicked.connect(self._add_from_search)
        self.search.returnPressed.connect(self._add_from_search)
        add_row.addWidget(add_btn)
        list_card.body.addLayout(add_row)

        self.list = NexusPriorityList(self.priorities, self.catalog)
        self.list.changed.connect(self._on_changed)
        list_card.body.addWidget(self.list, 1)
        row.addWidget(list_card, 2)

        # -- session summary ----------------------------------------------
        side = QVBoxLayout(); side.setSpacing(T.SP_3)
        info = NexusCard()
        info.body.addWidget(QLabel("SESSION"));
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setObjectName("Secondary")
        info.body.addWidget(self.summary)
        side.addWidget(info)
        side.addStretch(1)
        row.addLayout(side, 1)

        root.addLayout(row, 1)
        self.refresh()

    # ------------------------------------------------------------------ slots
    def _matches(self) -> list[str]:
        q = self.search.text().strip().lower()
        if not q or self.catalog is None:
            return []
        ranked = {p.champion_key for p in self.priorities.all}
        out = [c.name for c in self.catalog.all
               if q in c.name.lower() and c.key not in ranked]
        return out[:8]

    def _add_from_search(self) -> None:
        m = self._matches()
        if not m:
            return
        name = m[0]
        champ = self.catalog.by_name(name)
        if champ is None:
            return
        self.priorities.ensure(champ.key)          # append at end of ranking
        self.list.reload()
        self.search.clear()
        self._on_changed()

    def _on_changed(self) -> None:
        self.controller.save_priorities()
        self.refresh()

    # ---------------------------------------------------------------- refresh
    def refresh(self) -> None:
        rows = self.priorities.to_list()
        self.count_badge.setText(f"{len(rows)} ranked")
        snap = self.controller.manager.snapshot()
        self.summary.setText(
            f"State: {snap.state.value.replace('_', ' ').title()}\n"
            f"Confidence: {snap.confidence.value}\n"
            f"Catalog: {len(self.catalog.all) if self.catalog else 0} champions")
