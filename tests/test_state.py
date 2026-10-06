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
