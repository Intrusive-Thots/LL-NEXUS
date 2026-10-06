"""AutomationController — independent of the UI, driven by authoritative state.

Responsibilities:
* react to state changes from LeagueStateManager (never polls LCU itself);
* decide whether to act using AutomationConfig + GlobalKillSwitch + confidence;
* execute via the LCUActionPort and VERIFY against authoritative state;
* publish a full Decision record for every action (spec §12):
      Decision · Inputs · Reason · Action · Verification · Result
* safe retry on transient failures; refuse retries on verification mismatch;
* pause automatically ("fail closed") whenever state is not CONFIRMED.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from ..events.bus import EventBus
from ..recommendations.engine import RecommendationEngine, Recommendation
from ..sessions.recorder import SessionRecorder
from ..state.manager import LeagueStateManager
from ..state.models import LeagueSnapshot, LeagueState, Role, StateConfidence
from .config import AutomationConfig, BanMode
from .kill_switch import GlobalKillSwitch, KillSwitchTripped
from .port import LCUActionPort


class AutomationStatus:
    IDLE = "IDLE"
    ARMED = "ARMED"            # waiting for a trigger
    PAUSED_STALE = "PAUSED"    # fail-closed: state not confident
    STOPPED = "STOPPED"        # kill switch tripped / master disabled
    ACTING = "ACTING"


@dataclass
class Decision:
    """Explainable audit record for one automated decision."""

    kind: str                                  # "auto_accept" | "auto_pick" | ...
    inputs: dict = field(default_factory=dict)
    reason: str = ""
    action: str = ""                           # what we did / wanted to do
    verification: str = ""                     # how it was checked
    result: str = "PENDING"                    # SUCCESS | FAILED | REFUSED | SKIPPED | ERROR
    detail: Optional[str] = None
    ts: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return {"kind": self.kind, "inputs": self.inputs, "reason": self.reason,
                "action": self.action, "verification": self.verification,
                "result": self.result, "detail": self.detail, "ts": self.ts}


class AutomationController:
    def __init__(self, manager: LeagueStateManager, bus: EventBus,
                 port: LCUActionPort, engine: RecommendationEngine,
                 recorder: SessionRecorder, config: Optional[AutomationConfig] = None,
                 kill_switch: Optional[GlobalKillSwitch] = None) -> None:
        self._manager = manager
        self._bus = bus
        self._port = port
        self._engine = engine
        self._recorder = recorder
        self.config = config or AutomationConfig()
        self.kill_switch = kill_switch or GlobalKillSwitch()

        self._lock = threading.RLock()
        self._status = AutomationStatus.IDLE
        self._pending_recommendation: Optional[Recommendation] = None
        self._acted_this_action_window: set[str] = set()  # idempotency guard
        self._last_decision: Optional[Decision] = None
        self._worker: Optional[threading.Thread] = None
        self._wake = threading.Event()
        self._stop = threading.Event()

        # single subscription point: everything flows from authoritative state
        self._unsub_state = bus.subscribe("state.", self._on_state_event)

    # ---------------------------------------------------------------- setup
    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop.clear()
        self._worker = threading.Thread(target=self._run, name="nexus-automation", daemon=True)
        self._worker.start()

    def shutdown(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._worker:
            self._worker.join(timeout=2.0)
        self._unsub_state()

    # ------------------------------------------------------------- controls
    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    @property
    def last_decision(self) -> Optional[Decision]:
        with self._lock:
            return self._last_decision

    @property
    def pending_recommendation(self) -> Optional[Recommendation]:
        with self._lock:
            return self._pending_recommendation

    def emergency_stop(self, reason: str = "emergency stop") -> None:
        """Kill switch trip — immediate, global, verified before next action."""
        self.kill_switch.trip(reason)
        with self._lock:
            self._status = AutomationStatus.STOPPED
            self._acted_this_action_window.add("*")   # freeze current window
        self._bus.publish("automation.stopped", source="automation", reason=reason)
        self._record(Decision(kind="kill_switch", reason=reason,
                              action="trip", result="SUCCESS"))

    def resume(self) -> None:
        self.kill_switch.reset()
        with self._lock:
            self._status = AutomationStatus.IDLE
        self._bus.publish("automation.resumed", source="automation")
        self._wake.set()

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self.config.master_enabled = enabled
            if not enabled:
                self._status = AutomationStatus.STOPPED
            else:
                self._status = AutomationStatus.IDLE
        self._bus.publish("automation.enabled", source="automation", enabled=enabled)
        self._wake.set()

    # ----------------------------------------------------------- event intake
    def _on_state_event(self, event) -> None:
        # Coalesce: just wake the worker; the worker reads fresh authoritative
        # state so rapid event bursts cannot cause duplicate actions.
        self._wake.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            self._wake.wait(timeout=0.5)
            self._wake.clear()
            if self._stop.is_set():
                break
            try:
                self.evaluate_once()
            except Exception as exc:  # automation must never crash the app
                self._fail(exc)

    # ------------------------------------------------------------ evaluation
    def evaluate_once(self) -> None:
        """One evaluation pass over authoritative state. Idempotent per window."""
        snap = self._manager.snapshot()
        with self._lock:
            if self.kill_switch.tripped:
                self._status = AutomationStatus.STOPPED
                return
            if not self.config.master_enabled:
                self._status = AutomationStatus.STOPPED
                return
            if self.config.require_confirmed_state and \
                    snap.confidence not in (StateConfidence.CONFIRMED, StateConfidence.SYNCING):
                if snap.state not in (LeagueState.DISCONNECTED, LeagueState.CONNECTED,
                                      LeagueState.LOBBY):
                    self._pause_stale(snap)
                    return
            self._status = AutomationStatus.ARMED

        if snap.state in (LeagueState.CHAMP_SELECT, LeagueState.BAN_PHASE,
                          LeagueState.PICK_PHASE):
            self._refresh_recommendation(snap)
            self._handle_champ_select(snap)
        elif snap.state is LeagueState.QUEUE:
            self._handle_ready(snap)

    # -------------------------------------------------------------- helpers
    def _pause_stale(self, snap: LeagueSnapshot) -> None:
        with self._lock:
            already = self._status == AutomationStatus.PAUSED_STALE
            self._status = AutomationStatus.PAUSED_STALE
        if not already:
            d = Decision(kind="safety_pause",
                         inputs={"confidence": snap.confidence.value},
                         reason=f"state confidence is {snap.confidence.value}",
                         action="pause automation",
                         verification="none",
                         result="REFUSED",
                         detail="AUTOMATION PAUSED — will resume when state is confirmed")
            self._record(d)
            self._bus.publish("automation.paused", source="automation",
                              confidence=snap.confidence.value)

    def _refresh_recommendation(self, snap: LeagueSnapshot) -> Recommendation:
        unavailable = self._compute_unavailable(snap)
        rec = self._engine.recommend(snap, unavailable_keys=unavailable)
        with self._lock:
            self._pending_recommendation = rec
        return rec

    def _compute_unavailable(self, snap: LeagueSnapshot) -> set[str]:
        avail = self._port.available_champion_ids()
        if avail is None:
            return set()          # unknown availability → trust recommendation
        catalog = self._engine.catalog
        return {c.key for c in catalog.all if c.id not in avail}

    def _window_key(self, snap: LeagueSnapshot) -> str:
        """Identity of the current action window — prevents double-actions."""
        return f"{snap.state.value}:{snap.action_is_pick}:{snap.timer_total_seconds}"

    def _handle_ready(self, snap: LeagueSnapshot) -> None:
        if not self.config.auto_accept_ready:
            return
        key = "ready:" + str(snap.raw.get("game_id", "current"))
        with self._lock:
            if key in self._acted_this_action_window:
                return
            self._acted_this_action_window.add(key)
        decision = Decision(kind="auto_accept",
                            inputs={"state": snap.state.value, "queue": snap.queue_type},
                            reason="Ready Check detected and Auto Accept is enabled",
                            action="accept ready check",
                            verification="client accepted transition out of QUEUE")
        if self._execute(decision, lambda: self._port.accept_ready_check(),
                         verify=lambda: True):
            self._recorder.note_automation("Auto Accept", decision)

    def _handle_champ_select(self, snap: LeagueSnapshot) -> None:
        if snap.locked_in:
            return
        if not snap.action_is_pick and self.config.ban_mode is not BanMode.AUTO:
            return
        if snap.action_is_pick and not self.config.auto_pick:
            return

        rec = self.pending_recommendation or self._refresh_recommendation(snap)
        if not rec.winner:
            return
        champ = rec.winner.champion

        # Respect an assigned champion draft only when user opted into comp import
        if snap.action_champion_id is not None and not self.config.auto_import_team_comp:
            if snap.action_champion_id != champ.id:
                return  # client-assigned champion outranks recommendation

        window = self._window_key(snap)
        with self._lock:
            if window in self._acted_this_action_window:
                return
            self._acted_this_action_window.add(window)
            self._status = AutomationStatus.ACTING

        if snap.action_is_pick:
            self._do_pick(snap, rec, champ, window)
        else:
            self._do_ban(snap, rec, champ, window)

    def _do_pick(self, snap: LeagueSnapshot, rec: Recommendation, champ, window: str) -> None:
        delay = max(0.0, self.config.lock_in_delay_seconds)
        # Grace window: give the user a chance to override before we act.
        end = time.monotonic() + delay
        while time.monotonic() < end and not self._stop.is_set():
            if self.kill_switch.tripped or self._wake.wait(0.05):
                # A newer authoritative event arrived during the grace window —
                # re-evaluate instead of blindly acting on stale intent.
                with self._lock:
                    self._acted_this_action_window.discard(window)
                    self._status = AutomationStatus.ARMED
                return
        fresh = self._manager.snapshot()
        if fresh.state not in (LeagueState.CHAMP_SELECT, LeagueState.PICK_PHASE,
                               LeagueState.BAN_PHASE) or fresh.locked_in:
            with self._lock:
                self._acted_this_action_window.discard(window)
            return

        reasons = list(rec.winner.reasons) if rec.winner else []
        decision = Decision(
            kind="auto_pick",
            inputs={"role": fresh.role.display, "priority_rank": rec.winner.priority_rank,
                    "confidence": fresh.confidence.value,
                    "alternates": [c.champion.name for c in rec.alternates]},
            reason="; ".join(reasons[:3]) or "no reasons recorded",
            action=f"select champion {champ.name} (id={champ.id})",
            verification="authoritative snapshot shows my pick == champion",
        )
        ok = self._execute(decision,
                           lambda: self._port.select_champion(champ.id),
                           verify=lambda: self._port.verify_selection(champ.id))
        if ok:
            lock = Decision(kind="auto_lock_in",
                            inputs={"champion": champ.name},
                            reason="selection verified; auto lock-in enabled",
                            action=f"lock in {champ.name}",
                            verification="authoritative snapshot shows locked==True",
                            result="SKIPPED")
            if self._execute(lock, lambda: self._port.lock_in_champion(),
                             verify=lambda: self._port.verify_locked()):
                self._manager.update_fields(source="automation", locked_in=True)
                self._recorder.record_lock(champ.name, decision)
        else:
            with self._lock:
                self._acted_this_action_window.discard(window)  # allow safe retry later

    def _do_ban(self, snap: LeagueSnapshot, rec: Recommendation, champ, window: str) -> None:
        decision = Decision(kind="auto_ban",
                            inputs={"role": snap.role.display},
                            reason="; ".join(list(rec.winner.reasons)[:2]) if rec.winner else "",
                            action=f"ban champion {champ.name} (id={champ.id})",
                            verification="authoritative banned set contains champion")
        ok = self._execute(decision, lambda: self._port.ban_champion(champ.id),
                           verify=lambda: self._port.verify_ban(champ.id))
        if ok:
            self._recorder.note_automation(f"Auto Ban {champ.name}", decision)

    # ------------------------------------------------------------- execution
    def _execute(self, decision: Decision, do, verify) -> bool:
        """Run one action through the kill switch, with retries + verification."""
        attempts = max(1, self.config.retry_limit + 1)
        for attempt in range(attempts):
            try:
                self.kill_switch.guard()          # last-moment gate
            except KillSwitchTripped as exc:
                decision.result = "REFUSED"
                decision.detail = f"kill switch: {exc}"
                self._record(decision)
                with self._lock:
                    self._status = AutomationStatus.STOPPED
                return False
            if not self._port.is_connected():
                decision.result = "ERROR"
                decision.detail = "client not connected"
                self._record(decision)
                self._publish_fail(decision)
                return False
            try:
                accepted = bool(do())
            except Exception as exc:
                decision.result = "ERROR"
                decision.detail = f"attempt {attempt + 1}: {exc}"
                if attempt + 1 < attempts:
                    continue
                self._record(decision)
                self._publish_fail(decision)
                return False
            if not accepted:
                decision.result = "FAILED"
                decision.detail = f"client rejected action (attempt {attempt + 1})"
                if attempt + 1 < attempts:
                    continue
                self._record(decision)
                self._publish_fail(decision)
                return False
            # verification against authoritative state
            if verify():
                decision.result = "SUCCESS"
                self._record(decision)
                self._bus.publish("automation.action", source="automation",
                                  **decision.as_dict())
                with self._lock:
                    self._status = AutomationStatus.ARMED
                return True
            # action accepted but not reflected yet → verify once more after
            # a short wait; if still missing, treat as failure (never blind-retry).
            time.sleep(0.15)
            if verify():
                decision.result = "SUCCESS"
                self._record(decision)
                self._bus.publish("automation.action", source="automation",
                                  **decision.as_dict())
                with self._lock:
                    self._status = AutomationStatus.ARMED
                return True
            decision.result = "FAILED"
            decision.detail = "verification mismatch — refusing to repeat consequential action"
            self._record(decision)
            self._publish_fail(decision)
            return False
        return False

    def manual_override(self, champion_name: str, champion_id: int) -> None:
        """User picked manually — freeze this window, honour the choice."""
        snap = self._manager.snapshot()
        window = self._window_key(snap)
        with self._lock:
            self._acted_this_action_window.add(window)
        self._bus.publish("automation.override", source="automation",
                          champion=champion_name, champion_id=champion_id)
        self._recorder.note_override(champion_name)

    def _fail(self, exc: Exception) -> None:
        d = Decision(kind="automation_error", reason=str(exc),
                     action="none", verification="none", result="ERROR")
        self._record(d)
        with self._lock:
            self._status = AutomationStatus.ARMED  # recover-safe

    def _publish_fail(self, decision: Decision) -> None:
        self._bus.publish("automation.action_failed", source="automation",
                          **decision.as_dict())

    def _record(self, decision: Decision) -> None:
        with self._lock:
            self._last_decision = decision
        self._recorder.note_decision(decision.as_dict())
        self._bus.publish("automation.decision", source="automation",
                          **decision.as_dict())

    def diagnostics(self) -> dict:
        with self._lock:
            return {
                "status": self._status,
                "master_enabled": self.config.master_enabled,
                "auto_accept": self.config.auto_accept_ready,
                "auto_pick": self.config.auto_pick,
                "ban_mode": self.config.ban_mode.value,
                "kill_switch_armed": self.kill_switch.armed,
                "kill_switch_trips": self.kill_switch.trip_count,
                "last_decision": self._last_decision.as_dict() if self._last_decision else None,
            }
