"""Valid transitions for the central League state machine.

The graph is intentionally permissive about *recovery* paths (any state can go
to ERROR/DISCONNECTED) but strict about progression paths, so bugs in event
handling surface as rejected transitions instead of silent nonsense states.
"""
from __future__ import annotations

from .models import LeagueState as S

_TRANSITIONS: dict[S, set[S]] = {
    S.DISCONNECTED: {S.CONNECTED, S.ERROR},
    S.CONNECTED:    {S.LOBBY, S.DISCONNECTED, S.ERROR, S.CHAMP_SELECT, S.SEARCHING},
    S.LOBBY:        {S.QUEUE, S.SEARCHING, S.CONNECTED, S.DISCONNECTED, S.ERROR,
                     S.CHAMP_SELECT},
    S.QUEUE:        {S.SEARCHING, S.LOBBY, S.DISCONNECTED, S.ERROR, S.CHAMP_SELECT},
    S.SEARCHING:    {S.CHAMP_SELECT, S.LOBBY, S.QUEUE, S.DISCONNECTED, S.ERROR},
    S.CHAMP_SELECT: {S.BAN_PHASE, S.PICK_PHASE, S.LOCKED, S.LOADING,
                     S.DISCONNECTED, S.ERROR, S.LOBBY},
    S.BAN_PHASE:    {S.PICK_PHASE, S.CHAMP_SELECT, S.LOADING,
                     S.DISCONNECTED, S.ERROR},
    S.PICK_PHASE:   {S.BAN_PHASE, S.PICK_PHASE, S.LOCKED, S.CHAMP_SELECT,
                     S.LOADING, S.DISCONNECTED, S.ERROR},
    S.LOCKED:       {S.LOADING, S.PICK_PHASE, S.CHAMP_SELECT,
                     S.DISCONNECTED, S.ERROR},
    S.LOADING:      {S.IN_GAME, S.LOBBY, S.CHAMP_SELECT, S.DISCONNECTED, S.ERROR},
    S.IN_GAME:      {S.POST_GAME, S.LOBBY, S.DISCONNECTED, S.ERROR},
    S.POST_GAME:    {S.LOBBY, S.CONNECTED, S.DISCONNECTED, S.ERROR},
    S.ERROR:        {S.CONNECTED, S.LOBBY, S.DISCONNECTED, S.CHAMP_SELECT,
                     S.LOADING, S.POST_GAME},
}


def can_transition(current: S, target: S) -> bool:
    if current is target:
        return True  # idempotent updates are always allowed
    return target in _TRANSITIONS.get(current, set())


def allowed_targets(current: S) -> set[S]:
    return set(_TRANSITIONS.get(current, set())) | {current}
