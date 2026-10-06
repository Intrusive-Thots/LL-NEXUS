"""Diagnostics (§31) — one snapshot of everything, safe to share.

Never exposes secrets: the LCU lockfile token/password are deliberately not
reachable from here (the client keeps them private), and export() runs a
redaction pass over any string that looks like a credential just in case.
"""
from __future__ import annotations

import platform
import re
import sys
import time
from typing import Any, Optional

from ...core.events.bus import EventBus
from ...core.state.manager import LeagueStateManager

_SECRET_RE = re.compile(r"(token|password|sessionid|key)\s*[:=]\s*\S+", re.I)


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return _SECRET_RE.sub(lambda m: f"{m.group(1)}=[REDACTED]", value)
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if re.search(r"token|password|session", k, re.I)
                    else _redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(v) for v in value]
    return value


class DiagnosticsService:
    def __init__(self, manager: LeagueStateManager, bus: EventBus) -> None:
        self._manager = manager
        self._bus = bus
        self._components: dict[str, Any] = {}
        self.started_at = time.time()

    def register(self, name: str, provider) -> None:
        """Register anything exposing ``diagnostics() -> dict`` or a plain value."""
        self._components[name] = provider

    def snapshot(self) -> dict[str, Any]:
        snap = self._manager.snapshot()
        last = self._bus.history()[-1:] if self._bus.history() else []
        data: dict[str, Any] = {
            "application": {
                "name": "LeagueLoop Nexus",
                "version": "0.1.0",
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "uptime_seconds": round(time.time() - self.started_at, 1),
            },
            "qt": self._qt_version(),
            "state": self._manager.diagnostics(),
            "current_state": snap.state.value,
            "state_confidence": snap.confidence.value,
            "state_age_seconds": round(snap.age_seconds, 2),
            "last_event": last[0].kind if last else None,
            "last_error": self._manager.last_error,
        }
        for name, provider in self._components.items():
            try:
                data[name] = provider.diagnostics() if hasattr(provider, "diagnostics") \
                    else provider() if callable(provider) else provider
            except Exception as exc:  # diagnostics must never crash the app
                data[name] = {"error": str(exc)}
        return _redact(data)

    @staticmethod
    def _qt_version() -> str:
        try:
            from PySide6 import __version__ as qt
            return f"PySide6 {qt}"
        except Exception:
            return "PySide6 not loaded"

    def export_text(self) -> str:
        d = self.snapshot()
        lines = ["LEAGUELOOP NEXUS — DIAGNOSTICS",
                 f"exported: {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
        for section, payload in d.items():
            lines.append(f"[{section}]")
            if isinstance(payload, dict):
                for k, v in payload.items():
                    lines.append(f"  {k}: {v}")
            else:
                lines.append(f"  {payload}")
            lines.append("")
        return "\n".join(lines)
