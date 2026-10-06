"""LCU event + state ingestion.

Two cooperating threads (never the GUI thread):
* SSE listener on /sse — publishes raw "lcu." events to the bus and, when the
  payload contains gameflow/champ-select data, feeds LeagueStateManager.
* A slow polling fallback for /lol-gameflow/v1/gameflow-phase in case the SSE
  stream drops (clients restart it during patching).

The mapping from LCU gameflow phases to Nexus states is intentionally explicit
and total: an unknown phase produces STALE confidence rather than a guess.
"""
from __future__ import annotations

import json
import threading
import time
from typing import Optional

from ...core.events.bus import EventBus
from ...core.state.manager import LeagueStateManager
from ...core.state.models import LeagueState, Role, StateConfidence
from .client import LCUClient

#: LCU gameflow phase → Nexus authoritative state.
GAMEFLOW_MAP: dict[str, LeagueState] = {
    "None": LeagueState.CONNECTED,
    "Lobby": LeagueState.LOBBY,
    "Matchmaking": LeagueState.SEARCHING,
    "ReadyCheck": LeagueState.QUEUE,
    "ChampSelect": LeagueState.CHAMP_SELECT,
    "BanBuddy": LeagueState.BAN_PHASE,
    "PickScreen": LeagueState.PICK_PHASE,
    "Preload": LeagueState.LOADING,
    "Play": LeagueState.IN_GAME,
    "PostGame": LeagueState.POST_GAME,
}


class LCUEventService:
    def __init__(self, client: LCUClient, manager: LeagueStateManager, bus: EventBus) -> None:
        self._client = client
        self._manager = manager
        self._bus = bus
        self._stop = threading.Event()
        self._sse_thread: Optional[threading.Thread] = None
        self._poll_thread: Optional[threading.Thread] = None
        self.last_raw_event: Optional[dict] = None
        self.sse_connected = False

    # ------------------------------------------------------------- lifecycle
    def start(self) -> None:
        self._stop.clear()
        self._sse_thread = threading.Thread(target=self._sse_loop, name="nexus-lcu-sse", daemon=True)
        self._poll_thread = threading.Thread(target=self._poll_loop, name="nexus-lcu-poll", daemon=True)
        self._sse_thread.start()
        self._poll_thread.start()

    def stop(self) -> None:
        self._stop.set()

    # ------------------------------------------------------------ sse intake
    def _sse_loop(self) -> None:
        import httpx
        while not self._stop.is_set():
            try:
                with httpx.stream("GET", f"{self._client.base_url}/sse",
                                  auth=self._client.auth, verify=self._client.ssl_context,
                                  timeout=None) as resp:
                    self.sse_connected = True
                    self._bus.publish("lcu.connected", source="lcu", via="sse")
                    event_type = ""
                    for line in resp.iter_lines():
                        if self._stop.is_set():
                            break
                        if line.startswith("event:"):
                            event_type = line.split(":", 1)[1].strip()
                        elif line.startswith("data:") and event_type == "patch":
                            try:
                                payload = json.loads(line.split(":", 1)[1].strip())
                            except Exception:
                                continue
                            self._on_patch(payload)
                self.sse_connected = False
            except Exception as exc:
                self.sse_connected = False
                self._bus.publish("lcu.error", source="lcu", detail=str(exc))
            self._stop.wait(2.0)   # backoff before reconnect

    def _on_patch(self, payload: list) -> None:
        """SSE patch frames look like [{name, uri, data}, ...]."""
        if not isinstance(payload, list):
            return
        for item in payload:
            if not isinstance(item, dict):
                continue
            uri = str(item.get("uri", ""))
            data = item.get("data")
            self.last_raw_event = {"uri": uri, "data": data}
            self._bus.publish("lcu.event", source="lcu", uri=uri)
            if uri.endswith("/lol-gameflow/v1/gameflow-phase"):
                self.apply_gameflow_phase(str(data) if data else "None")
            elif uri.endswith("/lol-champ-select/v1/session"):
                if isinstance(data, dict):
                    self.apply_champ_select(data)

    # ------------------------------------------------------- explicit feeds
    def apply_gameflow_phase(self, phase: str) -> None:
        target = GAMEFLOW_MAP.get(phase)
        if target is None:
            self._manager.mark_stale()
            self._bus.publish("lcu.unknown_phase", source="lcu", phase=phase)
            return
        cur = self._manager.state
        if cur is target:
            self._manager.set_confidence(StateConfidence.CONFIRMED, source="lcu")
            return
        try:
            self._manager.transition(target, StateConfidence.CONFIRMED,
                                     source="lcu", reason=f"gameflow:{phase}")
        except Exception:
            # unexpected jump (e.g. client restarted mid-draft): resync hard
            self._manager.reset_to_disconnected(source="lcu", reason="resync")
            try:
                self._manager.transition(LeagueState.CONNECTED, StateConfidence.SYNCING,
                                         source="lcu", reason="resync")
                self._manager.transition(target, StateConfidence.CONFIRMED,
                                         source="lcu", reason=f"resync:{phase}")
            except Exception as exc:
                self._manager.fail(f"resync failed: {exc}", source="lcu")

    def apply_champ_select(self, session: dict) -> None:
        timer = session.get("timer") or {}
        remaining = timer.get("gameDraftTime") or timer.get("duration")
        total = timer.get("totalTime") or timer.get("adjustedTime") or remaining
        my_team = session.get("myTeam") or []
        their_team = session.get("theirTeam") or []
        banned_ids = {int(b.get("championId", 0)) for b in (session.get("bans") or [])
                      if isinstance(b, dict) and b.get("championId")}
        ally_picks = {int(s.get("championId")) for s in my_team
                      if isinstance(s, dict) and s.get("championId")}
        enemy_picks = {int(s.get("championId")) for s in their_team
                       if isinstance(s, dict) and s.get("championId")}
        role = Role.NONE
        locked = False
        action_is_pick = True
        action_champ: Optional[int] = None
        for s in my_team:
            if not isinstance(s, dict):
                continue
            if s.get("role") and role is Role.NONE:
                role = Role.from_lcu(str(s["role"]))
            if s.get("completed"):
                locked = True
            for act in s.get("actions") or []:
                if isinstance(act, dict) and not act.get("completed"):
                    action_is_pick = bool(act.get("isPick", True))
                    cid = act.get("championId")
                    action_champ = int(cid) if cid else None
        updates = dict(role=role, timer_seconds=float(remaining) if remaining else None,
                       timer_total_seconds=float(total) if total else None,
                       banned_ids=banned_ids, ally_pick_ids=ally_picks,
                       enemy_pick_ids=enemy_picks, locked_in=locked,
                       action_is_pick=action_is_pick, action_champion_id=action_champ,
                       raw=session)
        if self._manager.state.isChampSelectContext:
            self._manager.update_fields(source="lcu", confidence=StateConfidence.CONFIRMED,
                                        **updates)
            if locked:
                self._manager.transition(LeagueState.LOCKED, StateConfidence.CONFIRMED,
                                         source="lcu", reason="all actions complete")
            else:
                phase = session.get("tapout") is not None
                sub = LeagueState.BAN_PHASE if not action_is_pick else LeagueState.PICK_PHASE
                cur = self._manager.state
                if cur is not sub:
                    try:
                        self._manager.transition(sub, StateConfidence.CONFIRMED,
                                                 source="lcu", reason="champselect action")
                    except Exception:
                        pass
        else:
            self._manager.update_fields(source="lcu", **updates)

    # ------------------------------------------------------------ poll loop
    def _poll_loop(self) -> None:
        """Fallback liveness + phase poll; only meaningful when SSE is down."""
        while not self._stop.is_set():
            interval = 5.0 if self.sse_connected else 2.0
            self._stop.wait(interval)
            if self._stop.is_set():
                break
            try:
                phase = self._client.get("/lol-gameflow/v1/gameflow-phase")
                if isinstance(phase, str):
                    if not self.sse_connected:
                        self.apply_gameflow_phase(phase)
                    self._bus.publish("lcu.poll", source="lcu", phase=phase)
                if self._manager.state.isChampSelectContext and not self.sse_connected:
                    cs = self._client.get("/lol-champ-select/v1/session")
                    if isinstance(cs, dict):
                        self.apply_champ_select(cs)
            except Exception as exc:
                self._bus.publish("lcu.poll_error", source="lcu", detail=str(exc))
                if self._manager.state is not LeagueState.DISCONNECTED:
                    self._manager.mark_stale()
