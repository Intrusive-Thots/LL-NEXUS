from nexus.core.events.bus import EventBus
from nexus.core.state.manager import LeagueStateManager,StateTransitionError
from nexus.core.state.models import LeagueState,StateConfidence
def test_valid_transition():
    m=LeagueStateManager(EventBus()); m.transition(LeagueState.CONNECTED)
    assert m.state is LeagueState.CONNECTED and m.confidence is StateConfidence.CONFIRMED
def test_invalid_transition_rejected():
    m=LeagueStateManager(EventBus())
    try:m.transition(LeagueState.IN_GAME)
    except StateTransitionError:pass
    else:assert False
def test_stale_is_not_safe():
    m=LeagueStateManager(EventBus()); m.transition(LeagueState.CONNECTED); m.mark_stale()
    assert not m.snapshot().automation_safe


def test_dodge_and_requeue_transitions():
    bus = EventBus()
    for draft_state in (LeagueState.CHAMP_SELECT, LeagueState.BAN_PHASE,
                        LeagueState.PICK_PHASE, LeagueState.LOCKED):
        for recovery_target in (LeagueState.LOBBY, LeagueState.SEARCHING, LeagueState.QUEUE):
            m = LeagueStateManager(bus)
            m.transition(LeagueState.CONNECTED)
            m.transition(LeagueState.LOBBY)
            m.transition(LeagueState.QUEUE)
            m.transition(LeagueState.SEARCHING)
            m.transition(LeagueState.CHAMP_SELECT)
            if draft_state is LeagueState.BAN_PHASE:
                m.transition(LeagueState.BAN_PHASE)
            elif draft_state is LeagueState.PICK_PHASE:
                m.transition(LeagueState.PICK_PHASE)
            elif draft_state is LeagueState.LOCKED:
                m.transition(LeagueState.PICK_PHASE)
                m.transition(LeagueState.LOCKED)

            snap = m.transition(recovery_target, reason="dodge recovery")
            assert snap.state is recovery_target

