"""NexusQtBridge — pumps EventBus deliveries into the Qt main loop.

EventBus listeners run on background threads (LCU supervisor, automation
worker, simulator). Qt widgets may only be touched from the GUI thread, so
every bus event is converted into a queued Signal emission here. UI code
connects to ``event`` exactly like any other Qt signal; nothing in the UI
ever polls the LCU (§7).
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from ...core.events.bus import EventBus, NexusEvent


class NexusQtBridge(QObject):
    #: emitted on the GUI thread for every bus event (any kind)
    event = Signal(object)
    #: emitted only for state.changed events, with the new state name
    state_changed = Signal(str)

    def __init__(self, bus: EventBus, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._bus = bus
        self._unsub = bus.subscribe("*", self._on_bus_event)

    def _on_bus_event(self, ev: NexusEvent) -> None:
        # cross-thread queued emit — receiver runs in this object's thread (GUI)
        self.event.emit(ev)
        if ev.kind == "state.changed":
            self.state_changed.emit(str(ev.payload.get("new", "")))

    def shutdown(self) -> None:
        self._unsub()
