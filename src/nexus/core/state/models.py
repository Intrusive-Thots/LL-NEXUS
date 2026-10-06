"""League state model — the single authoritative view of what the client is doing.

Every subsystem (UI, automation, sessions, recommendations) consumes this state.
Nothing else is allowed to query the LCU directly for state decisions.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class LeagueState(str, Enum):
    """Authoritative high-level League client states."""

    DISCONNECTED = "DISCONNECTED"
    CONNECTED = "CONNECTED"
    LOBBY = "LOBBY"
    QUEUE = "QUEUE"
    SEARCHING = "SEARCHING"
    CHAMP_SELECT = "CHAMP_SELECT"
    PICK_PHASE = "PICK_PHASE"
    BAN_PHASE = "BAN_PHASE"
    LOCKED = "LOCKED"
    LOADING = "LOADING"
    IN_GAME = "IN_GAME"
    POST_GAME = "POST_GAME"
    ERROR = "ERROR"

    @property
    def isChampSelectContext(self) -> bool:
        return self in (LeagueState.CHAMP_SELECT, LeagueState.BAN_PHASE,
                        LeagueState.PICK_PHASE, LeagueState.LOCKED)


class StateConfidence(str, Enum):
    """How much the application trusts its current view of League state.

    Automation must refuse consequential actions unless confidence is CONFIRMED.
    """

    CONFIRMED = "CONFIRMED"   # verified against a live, recent LCU source
    SYNCING = "SYNCING"       # mid-refresh; previous value may lag reality
    STALE = "STALE"           # no recent confirmation; do not act
    UNKNOWN = "UNKNOWN"       # never established
    ERROR = "ERROR"           # last refresh failed


#: Confidence levels at which automation may perform consequential actions.
AUTOMATION_SAFE_CONFIDENCE = frozenset({StateConfidence.CONFIRMED})

#: A snapshot older than this (seconds) is considered stale for automation.
DEFAULT_STALE_AFTER_SECONDS = 8.0


class Role(str, Enum):
    NONE = "NONE"
    TOP = "TOP"
    JUNGLE = "JUNGLE"
    MIDDLE = "MIDDLE"
    ADC = "ADC"
    SUPPORT = "SUPPORT"

    @classmethod
    def from_lcu(cls, raw: Optional[str]) -> "Role":
        if not raw:
            return cls.NONE
        mapping = {
            "TOP": cls.TOP, "JUNGLE": cls.JUNGLE, "MIDDLE": cls.MIDDLE,
            "UTILITY": cls.SUPPORT, "SUPPORT": cls.SUPPORT,
            "BOTTOM": cls.ADC, "ADC": cls.ADC,
        }
        return mapping.get(raw.upper().strip(), cls.NONE)

    @property
    def display(self) -> str:
        return {"MIDDLE": "MID", "ADC": "ADC", "SUPPORT": "SUP"}.get(
            self.value, self.value.title())


@dataclass(frozen=True)
class ChampionSlotInfo:
    """One slot in champ select as understood by Nexus."""

    champion_id: int
    team: str            # "ally" | "enemy"
    slot_index: int      # 0..9 within team
    pick_or_ban: str     # "pick" | "ban"
    completed: bool
    available: bool = True


@dataclass
class LeagueSnapshot:
    """Full authoritative snapshot of the client situation.

    Mutable container owned exclusively by LeagueStateManager.
    """

    state: LeagueState = LeagueState.DISCONNECTED
    confidence: StateConfidence = StateConfidence.UNKNOWN
    role: Role = Role.NONE
    queue_type: Optional[str] = None
    timer_seconds: Optional[float] = None
    timer_total_seconds: Optional[float] = None
    my_team: list[ChampionSlotInfo] = field(default_factory=list)
    enemy_team: list[ChampionSlotInfo] = field(default_factory=list)
    banned_ids: set[int] = field(default_factory=set)
    ally_pick_ids: set[int] = field(default_factory=set)
    enemy_pick_ids: set[int] = field(default_factory=set)
    action_is_pick: bool = True          # current actor is picking (not banning)
    action_champion_id: Optional[int] = None  # champion assigned to my action, if any
    locked_in: bool = False
    last_event_ts: float = field(default_factory=time.monotonic)
    error_detail: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)

    def with_updated_confidence(self, stale_after: float = DEFAULT_STALE_AFTER_SECONDS) -> "LeagueSnapshot":
        age = time.monotonic() - self.last_event_ts
        if self.confidence == StateConfidence.ERROR:
            return self
        if age > stale_after:
            self.confidence = StateConfidence.STALE
        elif self.confidence == StateConfidence.UNKNOWN and self.state != LeagueState.DISCONNECTED:
            self.confidence = StateConfidence.STALE
        return self

    @property
    def age_seconds(self) -> float:
        return max(0.0, time.monotonic() - self.last_event_ts)

    @property
    def automation_safe(self) -> bool:
        return self.confidence in AUTOMATION_SAFE_CONFIDENCE
