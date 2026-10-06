"""Simulated LCU action port — implements the SAME port as the real client.

The automation controller cannot tell the difference between this and
``nexus.services.lcu.adapter.LCUActionPortImpl``: it drives the identical
LeagueStateManager through the identical verification path.  That is the whole
point of simulation mode (§29): every scenario exercises production logic.

Behaviour mirrors League champ-select rules closely enough to be useful:

* actions only succeed when the authoritative snapshot actually shows your
  action window (pick/ban) — acting out of turn fails, like a real 404;
* selections move the champion into ``ally_pick_ids`` and set ``locked_in``
  when the timer expires or ``lock_in_champion()`` is called;
* scripted failures (``fail_next``, ``flaky_mode``) let tests exercise the
  retry / verification-failure paths deterministically.
"""
from __future__ import annotations

import threading
from typing import Optional

from ...core.automation.port import LCUActionPort
from ...core.state.manager import LeagueStateManager
from ...core.state.models import LeagueState


class SimActionPort(LCUActionPort):
    def __init__(self, manager: LeagueStateManager, catalog,
                 available_ids: Optional[set[int]] = None) -> None:
        self._manager = manager
        self._catalog = catalog
        self._available_ids: Optional[set[int]] = available_ids
        self.action_log: list[str] = []
        self._lock = threading.Lock()
        # scripted failure controls (tests / "automation_error" scenario)
        self.fail_next: Optional[str] = None      # verb -> force failure once
        self.flaky_mode: bool = False             # every action raises
        self.connected = True

    # ------------------------------------------------------------- helpers
    def _consume(self, verb: str) -> bool:
        """Returns True if this scripted call should fail."""
        with self._lock:
            if self.flaky_mode:
                return True
            if self.fail_next == verb:
                self.fail_next = None
                return True
            return False

    def _key_of(self, champion_id: int) -> Optional[str]:
        champ = self._catalog.by_id(champion_id)
        return champ.key if champ else None

    # --------------------------------------------------------------- port
    def accept_ready_check(self) -> bool:
        snap = self._manager.snapshot()
        if snap.state not in (LeagueState.QUEUE, LeagueState.SEARCHING,
                              LeagueState.CONNECTED, LeagueState.LOBBY):
            return False
        if self._consume("accept"):
            return False
        self._manager.transition(LeagueState.CHAMP_SELECT, reason="sim ready accepted",
                                 queue_type=snap.queue_type or "Ranked Solo")
        with self._lock:
            self.action_log.append("accept_ready_check")
        return True

    def select_champion(self, champion_id: int) -> bool:
        snap = self._manager.snapshot()
        if snap.state not in (LeagueState.PICK_PHASE, LeagueState.CHAMP_SELECT,
                              LeagueState.BAN_PHASE):
            return False
        if not snap.action_is_pick:
            return False                      # not a pick window → refuse
        if self._consume("select"):
            return False
        key = self._key_of(champion_id)
        self._manager.update_fields(action_champion_id=champion_id,
                                    ally_pick_ids=set(snap.ally_pick_ids) | {champion_id},
                                    locked_in=False)
        self._manager.transition(LeagueState.LOCKED, reason=f"sim selected {key}")
        with self._lock:
            self.action_log.append(f"select:{key}")
        return True

    def lock_in_champion(self) -> bool:
        snap = self._manager.snapshot()
        if snap.action_champion_id is None:
            return False
        if self._consume("lock"):
            return False
        self._manager.update_fields(locked_in=True)
        with self._lock:
            self.action_log.append("lock_in")
        return True

    def ban_champion(self, champion_id: int) -> bool:
        snap = self._manager.snapshot()
        if snap.state not in (LeagueState.BAN_PHASE, LeagueState.CHAMP_SELECT):
            return False
        if snap.action_is_pick:
            return False
        if self._consume("ban"):
            return False
        key = self._key_of(champion_id)
        self._manager.update_fields(banned_ids=set(snap.banned_ids) | {champion_id})
        with self._lock:
            self.action_log.append(f"ban:{key}")
        return True

    def verify_selection(self, champion_id: int) -> bool:
        snap = self._manager.snapshot()
        return snap.action_champion_id == champion_id and \
            champion_id in snap.ally_pick_ids

    def verify_locked(self) -> bool:
        return self._manager.snapshot().locked_in

    def verify_ban(self, champion_id: int) -> bool:
        return champion_id in self._manager.snapshot().banned_ids

    def available_champion_ids(self) -> Optional[set[int]]:
        return self._available_ids

    def is_connected(self) -> bool:
        return self.connected
