"""League state and automation safety model."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
class LeagueState(str, Enum):
    DISCONNECTED="disconnected"; CONNECTED="connected"; LOBBY="lobby"; QUEUE="queue"; SEARCHING="searching"; CHAMP_SELECT="champ_select"; PICK_PHASE="pick_phase"; BAN_PHASE="ban_phase"; LOCKED="locked"; LOADING="loading"; IN_GAME="in_game"; POST_GAME="post_game"; ERROR="error"
class StateConfidence(str, Enum):
    CONFIRMED="confirmed"; SYNCING="syncing"; STALE="stale"; UNKNOWN="unknown"; ERROR="error"
@dataclass(frozen=True)
class LeagueSnapshot:
    state:LeagueState
    confidence:StateConfidence
    role:str|None=None
    timer_seconds:float|None=None
    session_id:str|None=None
    @property
    def automation_safe(self)->bool:
        return self.confidence is StateConfidence.CONFIRMED and self.state in {LeagueState.PICK_PHASE,LeagueState.BAN_PHASE}
class StateMachine:
    def __init__(self)->None:self.snapshot=LeagueSnapshot(LeagueState.DISCONNECTED,StateConfidence.UNKNOWN)
    def transition(self,state:LeagueState,confidence:StateConfidence=StateConfidence.CONFIRMED,**kwargs)->LeagueSnapshot:
        self.snapshot=LeagueSnapshot(state,confidence,**kwargs); return self.snapshot
