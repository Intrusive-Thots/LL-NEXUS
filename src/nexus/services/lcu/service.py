"""LCUService — orchestrates detection, connection lifecycle and ingestion.

Runs a single background supervisor thread:

    detect client → connect (LCUClient) → start LCUEventService
        │                                        │
        └────── client vanished / HTTP dead ◄────┘  → teardown + DISCONNECTED

The UI only sees bus events ("lcu.status") and the state manager; it never
touches HTTP itself. Reconnect is automatic; manual reconnect is exposed via
`reconnect_now()` for the status bar's [RECONNECT] button.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from ...core.events.bus import EventBus
from ...core.state.manager import LeagueStateManager
from ...core.state.models import LeagueState, StateConfidence
from ..client_detection.detector import ClientInfo, detect_client
from .adapter import LCUActionPortImpl
from .client import LCUClient
from .events import LCUEventService


class LCUService:
    def __init__(self, manager: LeagueStateManager, bus: EventBus,
                 detector: Callable[[], Optional[ClientInfo]] = detect_client) -> None:
        self._manager = manager
        self._bus = bus
        self._detect = detector
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._client: Optional[LCUClient] = None
        self._events: Optional[LCUEventService] = None
        self._info: Optional[ClientInfo] = None
        self._reconnect_requested = threading.Event()
        self.action_port = LCUActionPortImpl(lambda: self._client)

    # ------------------------------------------------------------- lifecycle
    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._supervisor, name="nexus-lcu", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._reconnect_requested.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        self._teardown(reason="shutdown")

    def reconnect_now(self) -> None:
        self._reconnect_requested.set()

    @property
    def connected(self) -> bool:
        return self._client is not None

    @property
    def client_info(self) -> Optional[ClientInfo]:
        return self._info

    def diagnostics(self) -> dict:
        return {
            "connected": self.connected,
            "port": self._info.port if self._info else None,
            "source": self._info.source if self._info else None,
            "token_present": bool(self._info and self._info.auth_token),  # never the token itself
            "sse_connected": self._events.sse_connected if self._events else False,
            "last_raw_event_uri": (self._events.last_raw_event or {}).get("uri")
            if self._events else None,
        }

    # ------------------------------------------------------------ supervisor
    def _supervisor(self) -> None:
        was_connected = False
        while not self._stop.is_set():
            try:
                if self._client is None:
                    info = self._detect()
                    if info and info.auth_token:
                        self._connect(info)
                    elif info:
                        self._publish("no_token", port=info.port)
                    else:
                        self._publish("not_found")
                else:
                    alive = self._client.ping()
                    if not alive:
                        self._teardown(reason="client unreachable")
                cur_state = self._manager.state
                if self._client is not None and cur_state is LeagueState.DISCONNECTED:
                    self._manager.transition(LeagueState.CONNECTED, StateConfidence.CONFIRMED,
                                             source="lcu", reason="connected")
                    self._publish("connected", port=self._info.port if self._info else None)
                elif self._client is None and was_connected:
                    self._manager.reset_to_disconnected(source="lcu", reason="connection lost")
                    self._publish("disconnected")
                was_connected = self._client is not None
            except Exception as exc:
                self._publish("error", detail=str(exc))
            wait_for = 2.0 if self._client is None else 5.0
            self._reconnect_requested.wait(wait_for)
            self._reconnect_requested.clear()
        self._teardown(reason="stopped")

    def _connect(self, info: ClientInfo) -> None:
        client = LCUClient(info.port, info.auth_token)
        if not client.ping():
            client.close()
            self._publish("handshake_failed", port=info.port)
            return
        self._client = client
        self._info = info
        self._events = LCUEventService(client, self._manager, self._bus)
        self._events.start()
        # prime current phase immediately so the UI lands in the right place
        try:
            phase = client.get("/lol-gameflow/v1/gameflow-phase")
            if isinstance(phase, str):
                self._events.apply_gameflow_phase(phase)
        except Exception:
            pass

    def _teardown(self, reason: str) -> None:
        if self._events:
            self._events.stop()
            self._events = None
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        if reason != "shutdown" and self._manager.state is not LeagueState.DISCONNECTED:
            self._manager.reset_to_disconnected(source="lcu", reason=reason)
            self._publish("disconnected", reason=reason)

    def _publish(self, status: str, **extra) -> None:
        self._bus.publish("lcu.status", source="lcu", status=status, **extra)
