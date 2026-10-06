from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
class EventType(StrEnum):
    CONNECT="connect"; DISCONNECT="disconnect"; LOBBY="lobby"; QUEUE="queue"; SEARCHING="searching"; CHAMP_SELECT="champ_select"; ROLE_DETECTED="role_detected"; PICK_PHASE="pick_phase"; BAN_PHASE="ban_phase"; CHAMPION_AVAILABLE="champion_available"; CHAMPION_UNAVAILABLE="champion_unavailable"; TIMER_CHANGE="timer_change"; LOCKED="locked"; ERROR="error"; RECONNECT="reconnect"; POST_GAME="post_game"
@dataclass(frozen=True)
class NexusEvent:
    type:EventType
    payload:dict[str,object]|None=None
