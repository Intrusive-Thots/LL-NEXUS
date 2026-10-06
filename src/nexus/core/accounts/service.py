"""Account context (spec §20) — deliberately minimal.

Nexus is not a stats dashboard; the account service only fetches what the UI
needs to show *who you are* and to key per-account preferences. All network I/O
runs on a worker thread; the UI never blocks.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class AccountSummary:
    game_name: str = ""
    tag_line: str = ""
    level: Optional[int] = None
    summoner_id: Optional[int] = None
    puuid: Optional[str] = None

    @property
    def display(self) -> str:
        if self.game_name and self.tag_line:
            return f"{self.game_name}#{self.tag_line}"
        return self.game_name or "Unknown summoner"


class AccountService:
    def __init__(self, lcu_client) -> None:
        """`lcu_client` must expose get(path) -> dict|None (LCUClient or simulator)."""
        self._client = lcu_client
        self._lock = threading.Lock()
        self._summary: Optional[AccountSummary] = None
        self._loading = False

    @property
    def summary(self) -> Optional[AccountSummary]:
        with self._lock:
            return self._summary

    def refresh_async(self, on_done: Optional[Callable[[Optional[AccountSummary]], None]] = None) -> None:
        with self._lock:
            if self._loading:
                return
            self._loading = True

        def work() -> None:
            try:
                me = self._client.get("/lol-summoner/v1/current-summoner")
                s = None
                if isinstance(me, dict):
                    s = AccountSummary(
                        game_name=str(me.get("gameName") or me.get("summonerName") or ""),
                        tag_line=str(me.get("gameTag") or ""),
                        level=me.get("summonerLevel"),
                        summoner_id=me.get("summonerId"),
                        puuid=me.get("puuid"),
                    )
                with self._lock:
                    self._summary = s
                    self._loading = False
            except Exception:
                with self._lock:
                    self._loading = False
                    s = None
            if on_done:
                on_done(s)

        threading.Thread(target=work, name="nexus-account", daemon=True).start()
