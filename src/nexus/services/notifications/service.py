"""In-app notification service (toasts).

Publishes "notify." events on the bus; the UI shell renders them as NexusToast.
Sound is optional and best-effort (QApplication.beep via UI adapter — no hard
dependency here so core stays headless-testable).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ...core.events.bus import EventBus


class NotifyLevel(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Notification:
    title: str
    body: str = ""
    level: NotifyLevel = NotifyLevel.INFO
    duration_ms: int = 4000
    action_label: Optional[str] = None


class NotificationService:
    def __init__(self, bus: EventBus, enabled: bool = True) -> None:
        self._bus = bus
        self.enabled = enabled

    def notify(self, n: Notification) -> None:
        if not self.enabled:
            return
        self._bus.publish("notify", source="ui", title=n.title, body=n.body,
                          level=n.level.value, duration_ms=n.duration_ms,
                          action_label=n.action_label)

    def info(self, title: str, body: str = "") -> None:
        self.notify(Notification(title, body, NotifyLevel.INFO))

    def success(self, title: str, body: str = "") -> None:
        self.notify(Notification(title, body, NotifyLevel.SUCCESS))

    def warning(self, title: str, body: str = "") -> None:
        self.notify(Notification(title, body, NotifyLevel.WARNING, duration_ms=6000))

    def critical(self, title: str, body: str = "") -> None:
        self.notify(Notification(title, body, NotifyLevel.CRITICAL, duration_ms=8000))
