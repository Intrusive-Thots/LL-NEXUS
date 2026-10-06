"""Lightweight, thread-safe application event bus.

Design goals:
* No Qt dependency in the core layer (core must be testable headless).
* The LCU/ingest thread publishes; the UI thread subscribes via an adapter
  (see nexus.ui.shell.qt_bridge) that marshals callbacks onto the Qt loop.
* Bounded history so Developer Mode can replay recent events without a log file.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Optional


@dataclass(frozen=True)
class NexusEvent:
    """An immutable application event."""

    kind: str                       # e.g. "state.changed", "automation.action"
    payload: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    source: str = "core"            # "lcu" | "simulation" | "automation" | "core" | "ui"

    def human(self) -> str:
        return f"{self.kind} {self.payload}"


Listener = Callable[[NexusEvent], None]


class EventBus:
    def __init__(self, history_size: int = 500) -> None:
        self._lock = threading.RLock()
        self._listeners: dict[str, list[Listener]] = {}
        self._wildcard: list[Listener] = []
        self._history: Deque[NexusEvent] = deque(maxlen=history_size)

    def subscribe(self, kind_prefix: str, listener: Listener) -> Callable[[], None]:
        """Subscribe to events whose kind starts with ``kind_prefix``.

        Use "*" for all events. Returns an unsubscribe callable.
        """
        with self._lock:
            if kind_prefix == "*":
                self._wildcard.append(listener)
                remove = lambda: self._remove_wildcard(listener)  # noqa: E731
            else:
                self._listeners.setdefault(kind_prefix, []).append(listener)
                remove = lambda: self._remove(kind_prefix, listener)  # noqa: E731
        return remove

    def _remove(self, prefix: str, listener: Listener) -> None:
        with self._lock:
            try:
                self._listeners.get(prefix, []).remove(listener)
            except ValueError:
                pass

    def _remove_wildcard(self, listener: Listener) -> None:
        with self._lock:
            try:
                self._wildcard.remove(listener)
            except ValueError:
                pass

    def publish(self, kind: str, /, source: str = "core", **payload: Any) -> NexusEvent:
        event = NexusEvent(kind=kind, payload=payload, source=source)
        with self._lock:
            self._history.append(event)
            targets: list[Listener] = list(self._wildcard)
            for prefix, listeners in self._listeners.items():
                if kind.startswith(prefix):
                    targets.extend(listeners)
        for fn in targets:
            try:
                fn(event)
            except Exception:  # a listener must never break the bus
                import traceback
                traceback.print_exc()
        return event

    def history(self, since_ts: Optional[float] = None, kinds: Optional[tuple[str, ...]] = None) -> list[NexusEvent]:
        with self._lock:
            items = list(self._history)
        if since_ts is not None:
            items = [e for e in items if e.ts >= since_ts]
        if kinds:
            items = [e for e in items if any(e.kind.startswith(k) for k in kinds)]
        return items
