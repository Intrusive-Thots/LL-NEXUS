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
        cell_id = session.get("localPlayerCellId")
        actions_matrix = session.get("actions")
        if isinstance(actions_matrix, list):
            for turn in actions_matrix:
                if isinstance(turn, list):
                    for act in turn:
                        if isinstance(act, dict) and not act.get("completed"):
                            if cell_id is not None and act.get("actorCellId") is not None and act.get("actorCellId") != cell_id:
                                continue
                            is_pick = (act.get("type") == "pick") if "type" in act else bool(act.get("isPick", True))
                            if want_pick is None or is_pick == want_pick:
                                return act

        for member in session.get("myTeam") or []:
            if not isinstance(member, dict):
                continue
            if cell_id is not None and member.get("cellId") is not None and member.get("cellId") != cell_id:
                continue
            for act in member.get("actions") or []:
                if isinstance(act, dict) and not act.get("completed"):
                    is_pick = (act.get("type") == "pick") if "type" in act else bool(act.get("isPick", True))
                    if want_pick is None or is_pick == want_pick:
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
        cell_id = session.get("localPlayerCellId")
        for member in session.get("myTeam") or []:
            if not isinstance(member, dict):
                continue
            if cell_id is None or member.get("cellId") == cell_id:
                if member.get("championId") == champion_id:
                    return True
            for act in member.get("actions") or []:
                if isinstance(act, dict) and act.get("championId") == champion_id:
                    if cell_id is None or act.get("actorCellId") == cell_id or member.get("cellId") == cell_id:
                        return True
        actions_matrix = session.get("actions")
        if isinstance(actions_matrix, list):
            for turn in actions_matrix:
                if isinstance(turn, list):
                    for act in turn:
                        if isinstance(act, dict):
                            if cell_id is not None and act.get("actorCellId") is not None and act.get("actorCellId") != cell_id:
                                continue
                            if act.get("championId") == champion_id or act.get("selectedChampionId") == champion_id:
                                return True
        return False

    def verify_locked(self) -> bool:
        session = self._session()
        if not session:
            return False
        cell_id = session.get("localPlayerCellId")
        for member in session.get("myTeam") or []:
            if not isinstance(member, dict):
                continue
            if cell_id is None or member.get("cellId") == cell_id:
                for act in member.get("actions") or []:
                    if isinstance(act, dict) and act.get("completed"):
                        is_pick = (act.get("type") == "pick") if "type" in act else bool(act.get("isPick", True))
                        if is_pick:
                            return True
        actions_matrix = session.get("actions")
        if isinstance(actions_matrix, list):
            for turn in actions_matrix:
                if isinstance(turn, list):
                    for act in turn:
                        if isinstance(act, dict) and act.get("completed"):
                            if cell_id is not None and act.get("actorCellId") is not None and act.get("actorCellId") != cell_id:
                                continue
                            is_pick = (act.get("type") == "pick") if "type" in act else bool(act.get("isPick", True))
                            if is_pick:
                                return True
        return False

    def verify_ban(self, champion_id: int) -> bool:
        session = self._session()
        if not session:
            return False
        from .events import _extract_banned_ids
        banned = _extract_banned_ids(session.get("bans"))
        if champion_id in banned:
            return True
        actions_matrix = session.get("actions")
        if isinstance(actions_matrix, list):
            for turn in actions_matrix:
                if isinstance(turn, list):
                    for act in turn:
                        if isinstance(act, dict) and act.get("completed"):
                            is_ban = (act.get("type") == "ban") if "type" in act else not bool(act.get("isPick", True))
                            if is_ban and act.get("championId") == champion_id:
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
