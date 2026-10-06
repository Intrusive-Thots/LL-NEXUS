"""Event Inspector (Developer Mode §30) — raw LCU/event stream, off by default.

Shows the real NexusEvent stream (kind, source, payload, timestamp) plus a
filter box. Only mounted when Developer Mode is enabled in Settings.
"""
from __future__ import annotations

import time
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHeaderView, QLineEdit, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget, QLabel,
)

from ...core.events.bus import EventBus


class EventInspector(QWidget):
    MAX_ROWS = 400

    def __init__(self, bus: EventBus, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._bus = bus
        self._filter = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("RAW EVENT STREAM")
        title.setObjectName("eyebrow")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter by event kind (e.g. automation.)…")
        self.search.textChanged.connect(self._set_filter)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Time", "Kind", "Source", "Payload"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(title)
        layout.addWidget(self.search)
        layout.addWidget(self.table, 1)

        # poll the ring buffer; cheap and avoids cross-thread table mutation
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(500)
        self._seen = 0

    def _set_filter(self, text: str) -> None:
        self._filter = text.strip()
        self._seen = 0
        self._refresh()

    def _refresh(self) -> None:
        events = self._bus.history()
        if len(events) == self._seen and not self._filter:
            return
        new = events[self._seen:] if len(events) >= self._seen else events
        self._seen = len(events)
        for ev in new:
            if self._filter and self._filter not in ev.kind:
                continue
            row = self.table.rowCount()
            if row >= self.MAX_ROWS:
                self.table.removeRow(0)
                row = self.table.rowCount() - 1
                self._reindex()
            self.table.insertRow(row)
            ts = time.strftime("%H:%M:%S", time.localtime(ev.ts))
            payload = ", ".join(f"{k}={_short(v)}" for k, v in ev.payload.items())
            for col, value in enumerate((ts, ev.kind, ev.source, payload)):
                item = QTableWidgetItem(str(value))
                if col == 1:
                    item.setData(Qt.UserRole, ev.kind)
                self.table.setItem(row, col, item)
            self.table.scrollToBottom()

    def _reindex(self) -> None:
        self._seen = max(0, self._seen - 1)

    def stop(self) -> None:
        self._timer.stop()


def _short(value: object, width: int = 80) -> str:
    text = repr(value)
    return text if len(text) <= width else text[: width - 1] + "…"
