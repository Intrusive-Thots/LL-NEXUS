"""SessionRecorder — subscribes to the bus and maintains the active session.

Sessions are also persisted through the persistence service; this class owns
the *in-memory* current session plus numbering so ordering is deterministic.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

from ..events.bus import EventBus, NexusEvent
from ..state.models import LeagueState
from .models import Session


class SessionRecorder:
    def __init__(self, bus: EventBus, on_session_closed: Optional[Callable[[Session], None]] = None) -> None:
        self._bus = bus
        self._lock = threading.RLock()
        self._active: Optional[Session] = None
        self._counter = 0
        self._on_closed = on_session_closed
        self._unsubs = [
            bus.subscribe("state.", self._on_event),
            bus.subscribe("automation.", self._on_event),
            bus.subscribe("recommendation.", self._on_event),
        ]

    # ------------------------------------------------------------ lifecycle
    def _next_number(self) -> int:
        self._counter += 1
        return self._counter

    @property
    def active(self) -> Optional[Session]:
        with self._lock:
            return self._active

    def close_active(self, result: str = "ABANDONED") -> Optional[Session]:
        with self._lock:
            s = self._active
            self._active = None
        if s:
            s.finish(result)
            if self._on_closed:
                self._on_closed(s)
        return s

    def shutdown(self) -> None:
        for u in self._unsubs:
            u()

    # ---------------------------------------------------------------- intake
    def _on_event(self, event: NexusEvent) -> None:
        kind = event.kind
        p = event.payload
        if kind in ("state.fields_updated", "state.confidence", "state.rejected"):
            return
        if kind == "state.changed":
            new = p.get("new")
            old = p.get("old")
            if new == LeagueState.QUEUE.value and old != LeagueState.SEARCHING.value:
                self._start_session(p)
            elif new == LeagueState.CHAMP_SELECT.value:
                self._ensure_session(p)
                self._add("state", "Champ Select started")
            elif new == LeagueState.BAN_PHASE.value:
                self._ensure_session(p)
                self._add("state", "Ban phase")
            elif new == LeagueState.PICK_PHASE.value:
                self._ensure_session(p)
                self._add("state", "Pick phase")
            elif new == LeagueState.LOCKED.value:
                self._ensure_session(p)
                self._add("state", "Selection locked")
            elif new == LeagueState.LOADING.value:
                self._ensure_session(p)
                self._add("state", "Loading into game")
            elif new == LeagueState.IN_GAME.value:
                self._ensure_session(p)
                self._add("state", "In game")
            elif new == LeagueState.POST_GAME.value:
                self._ensure_session(p)
                self._add("outcome", "Post-game reached — session complete")
                self.close_active("SUCCESS")
            elif new == LeagueState.LOBBY.value and self.active is not None:
                self._add("state", "Returned to lobby")
                self.close_active("SUCCESS")
            elif new == LeagueState.DISCONNECTED.value:
                if self.active:
                    self._add("failure", "Client disconnected mid-session")
                    self.close_active("FAILED")
            elif new == LeagueState.ERROR.value:
                self._ensure_session(p)
                self._add("failure", f"Error: {p.get('reason', 'unknown')}")

        elif kind == "recommendation.made":
            self._ensure_session(p)
            name = p.get("champion", "?")
            reasons = list(p.get("reasons", []))
            s = self.active
            if s:
                with self._lock:
                    s.recommendation = name
                    s.recommendation_reasons = reasons
                self._add("recommendation", f"{name} — {reasons[0]}" if reasons else name)

        elif kind == "automation.action":
            self._ensure_session(p)
            res = p.get("result")
            text = f"{p.get('kind','action')}: {p.get('action','')}"
            if res == "SUCCESS":
                self._add("action", f"{text} ✓ verified")
                s = self.active
                if s and p.get("kind") in ("auto_pick",):
                    with self._lock:
                        s.action_taken = "Auto-selected"
            elif res == "REFUSED":
                self._add("failure", f"{text} refused ({p.get('detail')})")
            else:
                self._add("failure", f"{text} — {res}")

        elif kind == "automation.override":
            self._ensure_session(p)
            self._add("override", f"Manual pick: {p.get('champion')}")
            s = self.active
            if s:
                with self._lock:
                    s.action_taken = "Manual override"

        elif kind == "automation.stopped":
            self._ensure_session(p)
            self._add("failure", f"Emergency stop — {p.get('reason')}")

        elif kind == "automation.paused":
            self._ensure_session(p)
            self._add("failure", "Automation paused: state not confirmed")

    # -------------------------------------------------------------- helpers
    def _start_session(self, p: dict) -> None:
        with self._lock:
            if self._active is not None:
                return
            self._counter += 1
            self._active = Session(number=self._counter)
            s = self._active
        s.add("state", f"Queue started ({p.get('reason') or p.get('new')})")

    def _ensure_session(self, p: dict) -> Session:
        with self._lock:
            if self._active is None:
                self._counter += 1
                self._active = Session(number=self._counter)
            return self._active

    def _add(self, kind: str, text: str, **detail) -> None:
        s = self._ensure_session({})
        s.add(kind, text, **detail)

    # public hooks used by other subsystems -------------------------------
    def note_automation(self, label: str, decision) -> None:
        s = self._ensure_session({})
        s.add("action", f"{label} ✓ verified")

    def note_decision(self, decision_dict: dict) -> None:
        kind = decision_dict.get("kind")
        if kind in ("kill_switch", "safety_pause"):
            s = self._ensure_session({})
            s.add("failure" if kind == "safety_pause" else "action",
                  "AUTOMATION PAUSED" if kind == "safety_pause"
                  else f"Kill switch tripped: {decision_dict.get('reason')}")

    def note_override(self, champion_name: str) -> None:
        s = self._ensure_session({})
        s.add("override", f"Manual pick: {champion_name}")
        with self._lock:
            s.action_taken = "Manual override"

    def record_lock(self, champion_name: str, decision) -> None:
        s = self._ensure_session({})
        s.add("action", f"Locked in {champion_name} ✓ League confirmed")
        with self._lock:
            if s.action_taken in (None, ""):
                s.action_taken = "Auto-selected"
