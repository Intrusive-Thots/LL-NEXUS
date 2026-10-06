"""LeagueStateManager — the ONE authoritative state model.

Everything flows through here:

    League Client ── LCU/Event Service ─┐
                                        ├──► LeagueStateManager ──► Application State
    Simulator ───── exact same feed ────┘          │
                                                   ▼
                                       UI · Automation · Sessions · Recommendations

Rules enforced by this module:
* Only valid transitions are accepted (invalid ones are logged + rejected).
* Confidence is tracked on every snapshot; staleness degrades it automatically.
* Consumers receive snapshots via the event bus; nobody polls the LCU itself.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from ..events.bus import EventBus
from .models import (
    DEFAULT_STALE_AFTER_SECONDS,
    LeagueSnapshot,
    LeagueState,
    Role,
    StateConfidence,
)
from .transitions import can_transition


class StateTransitionError(RuntimeError):
    pass


class LeagueStateManager:
    def __init__(self, bus: EventBus, stale_after: float = DEFAULT_STALE_AFTER_SECONDS) -> None:
        self._bus = bus
        self._lock = threading.RLock()
        self._snapshot = LeagueSnapshot()
        self._stale_after = stale_after
        self._last_error: Optional[str] = None
        self._watchdog_stop = threading.Event()

    # ------------------------------------------------------------------ read
    @property
    def bus(self) -> EventBus:
        return self._bus

    def snapshot(self) -> LeagueSnapshot:
        """Copy-on-read snapshot (cheap; consumers must not mutate the original)."""
        with self._lock:
            return self._snapshot

    @property
    def state(self) -> LeagueState:
        with self._lock:
            return self._snapshot.state

    @property
    def confidence(self) -> StateConfidence:
        with self._lock:
            return self._snapshot.confidence

    @property
    def last_error(self) -> Optional[str]:
        with self._lock:
            return self._last_error

    # --------------------------------------------------------------- writing
    def transition(
        self,
        target: LeagueState,
        confidence: StateConfidence = StateConfidence.CONFIRMED,
        *,
        source: str = "core",
        reason: str = "",
        **updates: object,
    ) -> LeagueSnapshot:
        """Attempt an authoritative state transition.

        Raises StateTransitionError when the graph forbids the move — callers
        (LCU adapter, simulator) should treat that as a bug or feed ERROR.
        """
        with self._lock:
            current = self._snapshot.state
            if not can_transition(current, target):
                self._last_error = f"rejected transition {current.value} -> {target.value} ({reason})"
                self._bus.publish("state.rejected", source=source,
                                  current=current.value, target=target.value, reason=reason)
                raise StateTransitionError(self._last_error)

            old = current
            self._snapshot.state = target
            self._snapshot.confidence = confidence
            self._snapshot.last_event_ts = time.monotonic()
            for key, value in updates.items():
                if hasattr(self._snapshot, key):
                    setattr(self._snapshot, key, value)
            if target is LeagueState.ERROR:
                self._last_error = str(updates.get("error_detail") or reason or "unknown error")
            elif old is LeagueState.ERROR:
                self._last_error = None
            snap = self._snapshot
        self._bus.publish("state.changed", source=source,
                          old=old.value, new=target.value,
                          confidence=confidence.value, reason=reason)
        return snap

    def update_fields(self, *, confidence: Optional[StateConfidence] = None,
                      source: str = "core", **updates: object) -> LeagueSnapshot:
        """Update contextual fields (timer, role, teams…) without changing state."""
        with self._lock:
            for key, value in updates.items():
                if hasattr(self._snapshot, key):
                    setattr(self._snapshot, key, value)
            if confidence is not None:
                self._snapshot.confidence = confidence
            self._snapshot.last_event_ts = time.monotonic()
            snap = self._snapshot
        self._bus.publish("state.fields_updated", source=source, keys=sorted(updates))
        return snap

    def set_confidence(self, confidence: StateConfidence, *, source: str = "core") -> None:
        with self._lock:
            self._snapshot.confidence = confidence
        self._bus.publish("state.confidence", source=source, confidence=confidence.value)

    def mark_syncing(self) -> None:
        self.set_confidence(StateConfidence.SYNCING)

    def mark_stale(self) -> None:
        self.set_confidence(StateConfidence.STALE)

    def fail(self, detail: str, *, source: str = "core") -> None:
        """Move to ERROR with an explanation; automation will pause."""
        with self._lock:
            current = self._snapshot.state
            if can_transition(current, LeagueState.ERROR):
                pass
            self._snapshot.state = LeagueState.ERROR
            self._snapshot.confidence = StateConfidence.ERROR
            self._snapshot.error_detail = detail
            self._last_error = detail
        self._bus.publish("state.changed", source=source, old=current.value,
                          new=LeagueState.ERROR.value,
                          confidence=StateConfidence.ERROR.value, reason=detail)

    def reset_to_disconnected(self, *, source: str = "core", reason: str = "") -> None:
        """Hard reset used on disconnect; bypasses the graph by design."""
        with self._lock:
            old = self._snapshot.state
            fresh = LeagueSnapshot(state=LeagueState.DISCONNECTED,
                                   confidence=StateConfidence.UNKNOWN)
            self._snapshot = fresh
        self._bus.publish("state.changed", source=source, old=old.value,
                          new=LeagueState.DISCONNECTED.value,
                          confidence=StateConfidence.UNKNOWN.value, reason=reason)

    # ------------------------------------------------------------- watchdog
    def start_watchdog(self, interval: float = 1.0) -> None:
        """Background freshness check: silently degrades CONFIRMED→STALE."""
        def _loop() -> None:
            while not self._watchdog_stop.wait(interval):
                with self._lock:
                    snap = self._snapshot
                    was = snap.confidence
                    if snap.state is LeagueState.DISCONNECTED:
                        continue
                    if was in (StateConfidence.CONFIRMED, StateConfidence.SYNCING) \
                            and snap.age_seconds > self._stale_after:
                        snap.confidence = StateConfidence.STALE
                        degrade = True
                    else:
                        degrade = False
                if degrade:
                    self._bus.publish("state.confidence", source="core",
                                      confidence=StateConfidence.STALE.value,
                                      reason=f"no events for {snap.age_seconds:.1f}s")
        self._watchdog_stop.clear()
        t = threading.Thread(target=_loop, name="nexus-state-watchdog", daemon=True)
        t.start()

    def stop_watchdog(self) -> None:
        self._watchdog_stop.set()

    # ------------------------------------------------------------ helpers
    def diagnostics(self) -> dict[str, object]:
        with self._lock:
            s = self._snapshot
            return {
                "state": s.state.value,
                "confidence": s.confidence.value,
                "role": s.role.value,
                "queue_type": s.queue_type,
                "age_seconds": round(s.age_seconds, 2),
                "locked_in": s.locked_in,
                "last_error": self._last_error,
            }
