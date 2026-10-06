"""Global kill switch — the single gate every automated action must pass.

Architecture (spec §14):

    UI → AutomationController → GlobalKillSwitch → Automation Actions → LCU

Tripping the switch immediately prevents any further automated action, even
one already queued on the worker thread, because actions re-check the gate at
execution time (not merely when they are scheduled).
"""
from __future__ import annotations

import threading
from typing import Optional


class KillSwitchTripped(RuntimeError):
    """Raised internally when an action loses the race against the switch."""


class GlobalKillSwitch:
    def __init__(self) -> None:
        self._event = threading.Event()   # set == automation allowed
        self._event.set()
        self._reason: Optional[str] = None
        self._trip_count = 0

    # ------------------------------------------------------------- control
    def trip(self, reason: str = "user emergency stop") -> None:
        self._reason = reason
        self._trip_count += 1
        self._event.clear()               # atomic for waiters

    def reset(self) -> None:
        self._reason = None
        self._event.set()

    # --------------------------------------------------------------- query
    @property
    def armed(self) -> bool:
        """True while automation is permitted to act."""
        return self._event.is_set()

    @property
    def tripped(self) -> bool:
        return not self._event.is_set()

    @property
    def reason(self) -> Optional[str]:
        return self._reason

    @property
    def trip_count(self) -> int:
        return self._trip_count

    def guard(self) -> None:
        """Raise unless the switch is armed. Call at the last moment."""
        if self.tripped:
            raise KillSwitchTripped(self._reason or "kill switch tripped")
