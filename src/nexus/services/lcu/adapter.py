"""Live-client implementation of the automation action port.

All calls are synchronous HTTP against the local LCU; AutomationController runs
them on its own worker thread, so the GUI never blocks. Verification helpers
re-read authoritative endpoints rather than trusting the POST response code.

Documented limitation: champ-select action ids and the "completed" flag shape
come from /lol-champ-select/v1/session; if the client changes this schema the
port fails closed (returns False → controller records FAILED, never blind-retries).
"""
from __future__ import annotations

import threading
from typing import Any, Optional

from ...core.automation.port import LCUActionPort
from .client import LCUClient


class LCUActionPortImpl(LCUActionPort):
    def __init__(self, client_provider) -> None:
        """client_provider: callable returning LCUClient|None (LCUService owns it)."""
        self._provider = client_provider
        self._lock = threading.Lock()

    @property
    def _client(self) -> Optional[LCUClient]:
        return self._provider()

    # ---------------------------------------------------------------- ready
    def accept_ready_check(self) -> bool:
        c = self._client
        if not c:
            return False
        try:
            c.post("/lol-ready-check/v1/accept")
            return True
        except Exception:
            return False

    # ----------------------------------------------------------- champ select
    def _session(self) -> Optional[dict]:
        c = self._client
        if not c:
            return None
        try:
            data = c.get("/lol-champ-select/v1/session")
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _my_action(self, session: dict, want_pick: Optional[bool] = None) -> Optional[dict]:
        local_cell = session.get("localPlayerCellId")

        # 1. Standard Riot LCU 2D actions matrix at session level
        actions_matrix = session.get("actions")
        if isinstance(actions_matrix, list):
            for group in actions_matrix:
                if isinstance(group, list):
                    for act in group:
                        if isinstance(act, dict) and not act.get("completed"):
                            if local_cell is not None and act.get("actorCellId") != local_cell:
                                continue
                            is_pick_act = act.get("isPick")
                            if is_pick_act is None:
                                is_pick_act = (str(act.get("type", "")).upper() != "BAN")
                            if want_pick is None or bool(is_pick_act) == want_pick:
                                return act

        # 2. Fallback: nested member actions in myTeam
        for member in session.get("myTeam") or []:
            if not isinstance(member, dict):
                continue
            if local_cell is not None and member.get("cellId") is not None and member.get("cellId") != local_cell:
                continue
            for act in member.get("actions") or []:
                if isinstance(act, dict) and not act.get("completed"):
                    is_pick_act = act.get("isPick")
                    if is_pick_act is None:
                        is_pick_act = (str(act.get("type", "")).upper() != "BAN")
                    if want_pick is None or bool(is_pick_act) == want_pick:
                        return act
        return None

    def select_champion(self, champion_id: int) -> bool:
        c = self._client
        if not c:
            return False
        session = self._session()
        if not session:
            return False
        act = self._my_action(session, want_pick=True)
        if not act or "id" not in act:
            return False
        already = act.get("championId")
        if already == champion_id:
            return True                       # idempotent no-op
        try:
            c.post(f"/lol-champ-select/v1/session/actions/{act['id']}",
                   {"selectedChampionId": int(champion_id)})
            return True
        except Exception:
            return False

    def lock_in_champion(self) -> bool:
        c = self._client
        if not c:
            return False
        session = self._session()
        if not session:
            return False
        act = self._my_action(session, want_pick=True)
        if not act or "id" not in act:
            return False
        if not act.get("championId"):
            return False                      # never lock an empty slot
        try:
            c.post(f"/lol-champ-select/v1/session/actions/{act['id']}/complete")
            return True
        except Exception:
            return False

    def ban_champion(self, champion_id: int) -> bool:
        c = self._client
        if not c:
            return False
        session = self._session()
        if not session:
            return False
        act = self._my_action(session, want_pick=False)
        if not act or "id" not in act:
            return False
        try:
            c.post(f"/lol-champ-select/v1/session/actions/{act['id']}",
                   {"championId": int(champion_id), "isPick": False})
            return True
        except Exception:
            return False

    # ------------------------------------------------------------ verification
    def verify_selection(self, champion_id: int) -> bool:
        session = self._session()
        if not session:
            return False
        local_cell = session.get("localPlayerCellId")
        actions_matrix = session.get("actions")
        if isinstance(actions_matrix, list):
            for group in actions_matrix:
                if isinstance(group, list):
                    for act in group:
                        if isinstance(act, dict):
                            if local_cell is not None and act.get("actorCellId") != local_cell:
                                continue
                            is_pick_act = act.get("isPick")
                            if is_pick_act is None:
                                is_pick_act = (str(act.get("type", "")).upper() != "BAN")
                            if is_pick_act and act.get("championId") == champion_id:
                                return True
        for member in session.get("myTeam") or []:
            if not isinstance(member, dict):
                continue
            if local_cell is not None and member.get("cellId") is not None and member.get("cellId") != local_cell:
                continue
            if member.get("championId") == champion_id:
                return True
            for act in member.get("actions") or []:
                if isinstance(act, dict):
                    is_pick_act = act.get("isPick")
                    if is_pick_act is None:
                        is_pick_act = (str(act.get("type", "")).upper() != "BAN")
                    if is_pick_act and act.get("championId") == champion_id:
                        return True
        return False

    def verify_locked(self) -> bool:
        session = self._session()
        if not session:
            return False
        local_cell = session.get("localPlayerCellId")
        actions_matrix = session.get("actions")
        if isinstance(actions_matrix, list):
            for group in actions_matrix:
                if isinstance(group, list):
                    for act in group:
                        if isinstance(act, dict):
                            if local_cell is not None and act.get("actorCellId") != local_cell:
                                continue
                            is_pick_act = act.get("isPick")
                            if is_pick_act is None:
                                is_pick_act = (str(act.get("type", "")).upper() != "BAN")
                            if is_pick_act and act.get("completed"):
                                return True
        for member in session.get("myTeam") or []:
            if not isinstance(member, dict):
                continue
            if local_cell is not None and member.get("cellId") is not None and member.get("cellId") != local_cell:
                continue
            if member.get("completed"):
                return True
            for act in member.get("actions") or []:
                if isinstance(act, dict):
                    is_pick_act = act.get("isPick")
                    if is_pick_act is None:
                        is_pick_act = (str(act.get("type", "")).upper() != "BAN")
                    if is_pick_act and act.get("completed"):
                        return True
        return False

    def verify_ban(self, champion_id: int) -> bool:
        session = self._session()
        if not session:
            return False
        bans = session.get("bans") or []
        if isinstance(bans, dict):
            bans = list(bans.values())
        for b in bans:
            if isinstance(b, dict) and b.get("championId") == champion_id:
                return True
            if isinstance(b, (int, str)) and str(b).isdigit() and int(b) == champion_id:
                return True
            if isinstance(b, list):
                for item in b:
                    if isinstance(item, dict) and item.get("championId") == champion_id:
                        return True
                    if isinstance(item, (int, str)) and str(item).isdigit() and int(item) == champion_id:
                        return True
        actions_matrix = session.get("actions")
        if isinstance(actions_matrix, list):
            for group in actions_matrix:
                if isinstance(group, list):
                    for act in group:
                        if isinstance(act, dict) and act.get("completed"):
                            is_ban_act = not act.get("isPick") if act.get("isPick") is not None else (str(act.get("type", "")).upper() == "BAN")
                            if is_ban_act and act.get("championId") == champion_id:
                                return True
        return False

    # ------------------------------------------------------------------- info
    def available_champion_ids(self) -> Optional[set[int]]:
        """Unknown for the live client in this build.

        The LCU does not expose a single authoritative "my champion pool"
        endpoint; availability is implicit (selecting an unavailable champion
        fails). Returning None makes the recommendation engine trust user
        priority, and a rejected select surfaces as a verified FAILED decision
        rather than a guessed exclusion list.
        """
        return None

    def is_connected(self) -> bool:
        c = self._client
        return bool(c and c.ping())
