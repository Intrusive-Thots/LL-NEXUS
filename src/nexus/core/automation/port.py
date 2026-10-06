"""Port (interface) between automation and the League Client.

The real implementation is `nexus.services.lcu.adapter.LCUActionPort` (HTTP to
the live client).  The simulator implements the same port, which is how UI /
automation logic is exercised end-to-end without a running game.

Contract rules that both implementations honour:
* every mutating call returns True only when the client *accepted* the action;
* `verify_*` calls read authoritative state — never cached intent;
* actions are idempotency-safe: re-issuing select on an already-selected
  champion is a no-op returning True.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class LCUActionPort(ABC):
    # ------------------------------------------------------------- ready
    @abstractmethod
    def accept_ready_check(self) -> bool: ...

    # ------------------------------------------------------------ champ select
    @abstractmethod
    def select_champion(self, champion_id: int) -> bool: ...

    @abstractmethod
    def lock_in_champion(self) -> bool: ...

    @abstractmethod
    def ban_champion(self, champion_id: int) -> bool: ...

    # ----------------------------------------------------------- verification
    @abstractmethod
    def verify_selection(self, champion_id: int) -> bool:
        """True iff authoritative client state shows champion selected by me."""

    @abstractmethod
    def verify_locked(self) -> bool:
        """True iff authoritative client state shows my pick locked in."""

    @abstractmethod
    def verify_ban(self, champion_id: int) -> bool: ...

    # ------------------------------------------------------------------ info
    @abstractmethod
    def available_champion_ids(self) -> Optional[set[int]]:
        """Champion ids the client currently offers me; None = unknown."""

    @abstractmethod
    def is_connected(self) -> bool: ...
