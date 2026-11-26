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


def _cells_conflict(local_cell: Any, actor_cell: Any) -> bool:
    """True when both cell ids are known and name different players.

    A missing actor cell still matches. That is main's behavior, and it still
    applies the PR's cellId filter whenever both ids are present.
    """
    return local_cell is not None and actor_cell is not None and actor_cell != local_cell


def _action_is_pick(act: dict) -> bool:
    """Whether an action is a pick.

    An explicit ``type`` wins, case-insensitively, so both ``pick`` (main) and
    ``PICK`` (this PR) count. Otherwise ``isPick`` is used, defaulting to a pick.
    """
    type_val = act.get("type")
    if isinstance(type_val, str) and type_val.strip():
        return type_val.upper() == "PICK"
    return bool(act.get("isPick", True))


def _action_is_ban(act: dict) -> bool:
    type_val = act.get("type")
    if isinstance(type_val, str) and type_val.strip():
        return type_val.upper() == "BAN"
    if act.get("isPick") is not None:
        return not bool(act.get("isPick"))
    return False


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
                            if _cells_conflict(cell_id, act.get("actorCellId")):
                                continue
                            is_pick = _action_is_pick(act)
                            if want_pick is None or is_pick == want_pick:
                                return act

        for member in session.get("myTeam") or []:
            if not isinstance(member, dict):
                continue
            if _cells_conflict(cell_id, member.get("cellId")):
                continue
            for act in member.get("actions") or []:
                if isinstance(act, dict) and not act.get("completed"):
                    is_pick = _action_is_pick(act)
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
        actions_matrix = session.get("actions")
        if isinstance(actions_matrix, list):
            for turn in actions_matrix:
                if isinstance(turn, list):
                    for act in turn:
                        if not isinstance(act, dict):
                            continue
                        if _cells_conflict(cell_id, act.get("actorCellId")):
                            continue
                        cid = act.get("championId")
                        selected = act.get("selectedChampionId")
                        if cid != champion_id and selected != champion_id:
                            continue
                        # selectedChampionId is main's signal. A championId hit
                        # must be a pick so a completed ban is not a selection.
                        if selected == champion_id or _action_is_pick(act):
                            return True
        for member in session.get("myTeam") or []:
            if not isinstance(member, dict):
                continue
            member_is_local = cell_id is None or member.get("cellId") == cell_id
            if member_is_local and member.get("championId") == champion_id:
                return True
            for act in member.get("actions") or []:
                if not isinstance(act, dict):
                    continue
                if act.get("championId") != champion_id and act.get("selectedChampionId") != champion_id:
                    continue
                if cell_id is None or act.get("actorCellId") == cell_id or member.get("cellId") == cell_id:
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
            if _cells_conflict(cell_id, member.get("cellId")):
                continue
            if member.get("completed"):
                return True
            for act in member.get("actions") or []:
                if isinstance(act, dict) and act.get("completed") and _action_is_pick(act):
                    return True
        actions_matrix = session.get("actions")
        if isinstance(actions_matrix, list):
            for turn in actions_matrix:
                if isinstance(turn, list):
                    for act in turn:
                        if isinstance(act, dict) and act.get("completed"):
                            if _cells_conflict(cell_id, act.get("actorCellId")):
                                continue
                            if _action_is_pick(act):
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
                        if isinstance(act, dict) and act.get("completed") and _action_is_ban(act):
                            if act.get("championId") == champion_id:
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
