"""Simulator — drives the REAL LeagueStateManager through scripted scenarios.

This is a core development feature (§29), not a throwaway mock:

* every verb (CONNECT … POST_GAME) maps onto genuine ``transition()`` /
  ``update_fields()`` calls on the same manager the production app uses;
* invalid verbs for the current state are rejected exactly like invalid LCU
  events would be (StateTransitionError surfaces in the event log);
* scenarios are deterministic scripts replayable from any starting point, so
  tests and the Developer→Simulation UI exercise identical code paths.

The companion ``SimActionPort`` (port.py) completes the loop: automation acts
through the same port interface against simulator-owned state.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from ...core.events.bus import EventBus
from ...core.state.manager import LeagueStateManager, StateTransitionError
from ...core.state.models import LeagueState, Role, StateConfidence

#: Verbs accepted by ``Simulator.feed`` (§29).
VERBS = [
    "CONNECT", "DISCONNECT", "LOBBY", "QUEUE", "SEARCHING", "CHAMP_SELECT",
    "ROLE_DETECTED", "PICK_PHASE", "BAN_PHASE", "CHAMPION_AVAILABLE",
    "CHAMPION_UNAVAILABLE", "TIMER_CHANGE", "LOCKED", "ERROR", "RECONNECT",
    "POST_GAME", "LOADING", "IN_GAME",
]


@dataclass
class SimStep:
    verb: str
    params: dict = field(default_factory=dict)
    delay: float = 0.0            # seconds to wait BEFORE applying this step
    note: str = ""


@dataclass
class Scenario:
    id: str
    name: str
    description: str
    steps: list[SimStep]


def _s(verb: str, delay: float = 0.0, note: str = "", **params: object) -> SimStep:
    return SimStep(verb=verb, params=dict(params), delay=delay, note=note)


# --------------------------------------------------------------------- §29
SCENARIOS: list[Scenario] = [
    Scenario("idle", "Idle", "Connected client sitting in lobby.", [
        _s("CONNECT", note="client detected"),
        _s("LOBBY", 0.3),
    ]),
    Scenario("searching", "Queue Search", "Entering ranked queue and finding a game.", [
        _s("CONNECT"), _s("LOBBY", 0.2),
        _s("QUEUE", 0.4, queue_type="Ranked Solo/Duo"),
        _s("SEARCHING", 0.3),
        _s("CHAMP_SELECT", 2.0, queue_type="Ranked Solo/Duo"),
    ]),
    Scenario("adc_champ_select", "Champ Select — ADC",
             "Full champ-select entry with ADC role assigned.", [
        _s("CONNECT"), _s("LOBBY", 0.2), _s("SEARCHING", 0.3),
        _s("CHAMP_SELECT", 0.5, queue_type="Ranked Solo/Duo"),
        _s("ROLE_DETECTED", 0.6, role="ADC"),
        _s("BAN_PHASE", 0.4, timer_total_seconds=30.0),
        _s("TIMER_CHANGE", 1.0, timer_seconds=20.0),
        _s("PICK_PHASE", 1.0, timer_seconds=30.0, timer_total_seconds=30.0,
           action_is_pick=True),
        _s("TIMER_CHANGE", 3.0, timer_seconds=14.0),
    ]),
    Scenario("support_champ_select", "Champ Select — Support",
             "Same flow with SUPPORT role to verify role-aware recommendations.", [
        _s("CONNECT"), _s("LOBBY", 0.2), _s("SEARCHING", 0.3),
        _s("CHAMP_SELECT", 0.5, queue_type="Flex"),
        _s("ROLE_DETECTED", 0.6, role="SUPPORT"),
        _s("PICK_PHASE", 0.8, timer_seconds=30.0, timer_total_seconds=30.0,
           action_is_pick=True),
    ]),
    Scenario("auto_pick_success", "Auto Pick — Success",
             "Timer runs down while automation picks Jinx and League confirms.", [
        _s("CONNECT"), _s("LOBBY", 0.2), _s("SEARCHING", 0.3),
        _s("CHAMP_SELECT", 0.5, queue_type="Ranked Solo/Duo"),
        _s("ROLE_DETECTED", 0.4, role="ADC"),
        _s("PICK_PHASE", 0.4, timer_seconds=30.0, timer_total_seconds=30.0,
           action_is_pick=True),
        _s("TIMER_CHANGE", 2.0, timer_seconds=20.0),
        _s("TIMER_CHANGE", 2.0, timer_seconds=10.0),
        _s("LOCKED", 2.0, locked_in=True, note="automation selects + verifies"),
        _s("LOADING", 1.5), _s("IN_GAME", 2.0), _s("POST_GAME", 2.0),
    ]),
    Scenario("manual_override", "Manual Override",
             "User picks before automation; Nexus records the override.", [
        _s("CONNECT"), _s("LOBBY", 0.2), _s("CHAMP_SELECT", 0.4),
        _s("ROLE_DETECTED", 0.3, role="ADC"),
        _s("PICK_PHASE", 0.4, timer_seconds=25.0, timer_total_seconds=30.0,
           action_is_pick=True),
        _s("CHAMPION_AVAILABLE", 1.5, champion_key="kaisa",
           note="user selects Kai'Sa manually"),
        _s("LOCKED", 0.5, locked_in=True),
    ]),
    Scenario("champion_unavailable", "Champion Unavailable",
             "Top-priority champion gets taken; recommendation falls to #2.", [
        _s("CONNECT"), _s("LOBBY", 0.2), _s("CHAMP_SELECT", 0.4),
        _s("ROLE_DETECTED", 0.3, role="ADC"),
        _s("PICK_PHASE", 0.4, timer_seconds=30.0, timer_total_seconds=30.0,
           action_is_pick=True),
        _s("CHAMPION_UNAVAILABLE", 1.5, champion_key="jinx",
           note="enemy ally-first pick takes Jinx"),
    ]),
    Scenario("automation_error", "Automation Error",
             "A pick action fails verification → controller pauses safely.", [
        _s("CONNECT"), _s("LOBBY", 0.2), _s("CHAMP_SELECT", 0.4),
        _s("ROLE_DETECTED", 0.3, role="MIDDLE"),
        _s("PICK_PHASE", 0.4, timer_seconds=20.0, timer_total_seconds=30.0,
           action_is_pick=True),
    ]),
    Scenario("disconnect", "Disconnect",
             "Client dies mid-champ-select; automation must fail closed.", [
        _s("CONNECT"), _s("LOBBY", 0.2), _s("CHAMP_SELECT", 0.4),
        _s("ROLE_DETECTED", 0.3, role="TOP"),
        _s("PICK_PHASE", 0.4, timer_seconds=15.0, timer_total_seconds=30.0),
        _s("DISCONNECT", 2.0, note="client process vanished"),
    ]),
    Scenario("reconnect", "Reconnect",
             "Disconnect then recovery back to lobby.", [
        _s("CONNECT"), _s("LOBBY", 0.2), _s("DISCONNECT", 1.0),
        _s("RECONNECT", 2.0), _s("LOBBY", 0.5),
    ]),
    Scenario("timer_expiry", "Timer Expiry",
             "Countdown reaches zero during your pick window.", [
        _s("CONNECT"), _s("LOBBY", 0.2), _s("CHAMP_SELECT", 0.4),
        _s("ROLE_DETECTED", 0.3, role="JUNGLE"),
        _s("PICK_PHASE", 0.4, timer_seconds=5.0, timer_total_seconds=30.0,
           action_is_pick=True),
        _s("TIMER_CHANGE", 1.0, timer_seconds=3.0),
        _s("TIMER_CHANGE", 1.0, timer_seconds=1.0),
        _s("TIMER_CHANGE", 1.0, timer_seconds=0.0),
    ]),
]

SCENARIO_INDEX: dict[str, Scenario] = {s.id: s for s in SCENARIOS}


class Simulator:
    """Scripted feed into the authoritative state manager."""

    def __init__(self, manager: LeagueStateManager, bus: EventBus,
                 catalog=None) -> None:
        self._manager = manager
        self._bus = bus
        self._catalog = catalog
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.playing = False
        self.current_scenario: Optional[str] = None
        self.log: list[str] = []
        self._log_lock = threading.Lock()
        #: hook used by the app controller (e.g. SimActionPort availability sets)
        self.on_availability: Optional[Callable[[str, bool], None]] = None

    # ------------------------------------------------------------- verbs
    def feed(self, verb: str, confidence: StateConfidence = StateConfidence.CONFIRMED,
             **params: object) -> bool:
        """Apply one simulation verb to the real state machine.

        Returns True if applied, False if rejected (invalid for current state)
        — rejection is surfaced exactly like a bad LCU event would be.
        """
        m = self._manager
        try:
            if verb == "CONNECT":
                m.transition(LeagueState.CONNECTED, confidence, source="sim")
            elif verb == "DISCONNECT":
                m.reset_to_disconnected(source="sim", reason=str(params.get("reason", "sim disconnect")))
            elif verb == "RECONNECT":
                if m.state is LeagueState.DISCONNECTED:
                    m.transition(LeagueState.CONNECTED, confidence, source="sim")
                else:
                    m.transition(LeagueState.CONNECTED, confidence, source="sim")
            elif verb == "LOBBY":
                if m.state is LeagueState.DISCONNECTED:
                    m.transition(LeagueState.CONNECTED, confidence, source="sim")
                m.transition(LeagueState.LOBBY, confidence, source="sim")
            elif verb == "QUEUE":
                if m.state in (LeagueState.CONNECTED, LeagueState.DISCONNECTED):
                    m.transition(LeagueState.LOBBY, confidence, source="sim")
                m.transition(LeagueState.QUEUE, confidence, source="sim",
                             queue_type=params.get("queue_type", "Ranked Solo/Duo"))
            elif verb == "SEARCHING":
                m.transition(LeagueState.SEARCHING, confidence, source="sim")
            elif verb == "CHAMP_SELECT":
                cur = m.state
                if cur in (LeagueState.CONNECTED, LeagueState.DISCONNECTED):
                    m.transition(LeagueState.LOBBY, confidence, source="sim")
                if cur in (LeagueState.LOBBY, LeagueState.CONNECTED):
                    m.transition(LeagueState.QUEUE, confidence, source="sim")
                if m.state is LeagueState.QUEUE:
                    m.transition(LeagueState.SEARCHING, confidence, source="sim")
                m.transition(LeagueState.CHAMP_SELECT, confidence, source="sim",
                             queue_type=params.get("queue_type", "Ranked Solo/Duo"))
            elif verb == "ROLE_DETECTED":
                m.update_fields(role=Role.from_lcu(str(params.get("role", ""))),
                                source="sim")
            elif verb == "BAN_PHASE":
                m.transition(LeagueState.BAN_PHASE, confidence, source="sim",
                             action_is_pick=False,
                             timer_seconds=float(params.get("timer_seconds", 30.0)),
                             timer_total_seconds=float(params.get("timer_total_seconds", 30.0)))
            elif verb == "PICK_PHASE":
                m.transition(LeagueState.PICK_PHASE, confidence, source="sim",
                             action_is_pick=bool(params.get("action_is_pick", True)),
                             timer_seconds=float(params.get("timer_seconds", 30.0)),
                             timer_total_seconds=float(params.get("timer_total_seconds", 30.0)))
            elif verb == "CHAMPION_AVAILABLE":
                self._apply_team_change(str(params.get("champion_key", "")), picked=True)
            elif verb == "CHAMPION_UNAVAILABLE":
                self._apply_team_change(str(params.get("champion_key", "")), picked=False)
            elif verb == "TIMER_CHANGE":
                m.update_fields(timer_seconds=float(params.get("timer_seconds", 0.0)),
                                source="sim")
            elif verb == "LOCKED":
                m.transition(LeagueState.LOCKED, confidence, source="sim",
                             locked_in=bool(params.get("locked_in", True)))
            elif verb == "LOADING":
                m.transition(LeagueState.LOADING, confidence, source="sim")
            elif verb == "IN_GAME":
                m.transition(LeagueState.IN_GAME, confidence, source="sim")
            elif verb == "POST_GAME":
                if m.state is LeagueState.LOCKED:
                    m.transition(LeagueState.LOADING, confidence, source="sim")
                if m.state is LeagueState.LOADING:
                    m.transition(LeagueState.IN_GAME, confidence, source="sim")
                m.transition(LeagueState.POST_GAME, confidence, source="sim")
            elif verb == "ERROR":
                m.fail(str(params.get("detail", "simulated error")), source="sim")
            else:
                raise ValueError(f"unknown simulation verb: {verb}")
        except StateTransitionError as exc:
            self._note(f"✗ {verb} rejected — {exc}")
            return False
        self._note(f"• {verb}" + (f" {params}" if params else ""))
        return True

    def _apply_team_change(self, key: str, picked: bool) -> None:
        champ = self._catalog.by_key(key) if self._catalog else None
        snap = self._manager.snapshot()
        if champ is None:
            self._note(f"⚠ unknown champion key '{key}'")
            return
        ids = set(snap.ally_pick_ids)
        if picked:
            ids.add(champ.id)
        else:
            ids.discard(champ.id)
        self._manager.update_fields(ally_pick_ids=ids, source="sim")
        if self.on_availability:
            self.on_availability(key, picked)

    # -------------------------------------------------------- scenarios
    def play(self, scenario_id: str, repeat: bool = False) -> bool:
        scenario = SCENARIO_INDEX.get(scenario_id)
        if scenario is None:
            self._note(f"✗ unknown scenario '{scenario_id}'")
            return False
        self.stop_playback()
        self.current_scenario = scenario_id
        self._stop.clear()

        def _run() -> None:
            self.playing = True
            loops = 0
            while not self._stop.is_set():
                loops += 1
                for step in scenario.steps:
                    if self._stop.wait(step.delay):
                        self.playing = False
                        return
                    if self._stop.is_set():
                        break
                    self.feed(step.verb, **step.params)
                if not repeat:
                    break
            self.playing = False

        self._thread = threading.Thread(target=_run, name="nexus-sim", daemon=True)
        self._thread.start()
        return True

    def stop_playback(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.playing = False

    def reset(self) -> None:
        """Return the machine to DISCONNECTED so scenarios can replay cleanly."""
        self.stop_playback()
        try:
            self._manager.reset_to_disconnected(source="sim", reason="simulator reset")
        except Exception:
            pass
        self._note("⟲ simulator reset")

    def _note(self, text: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        with self._log_lock:
            self.log.append(f"{stamp}  {text}")
            del self.log[:-200]
        self._bus.publish("simulation.event", source="sim", text=text)

    def diagnostics(self) -> dict:
        with self._log_lock:
            tail = list(self.log[-50:])
        return {"playing": self.playing, "scenario": self.current_scenario,
                "verbs": VERBS, "log": tail}
