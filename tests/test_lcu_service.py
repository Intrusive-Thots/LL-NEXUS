from nexus.core.events.bus import EventBus
from nexus.core.state.manager import LeagueStateManager
from nexus.core.state.models import LeagueState, StateConfidence
from nexus.services.lcu.events import GAMEFLOW_MAP, LCUEventService
from nexus.services.lcu.adapter import LCUActionPortImpl

def test_gameflow_map_completeness():
    assert GAMEFLOW_MAP["Lobby"] is LeagueState.LOBBY
    assert GAMEFLOW_MAP["ChampSelect"] is LeagueState.CHAMP_SELECT
    assert GAMEFLOW_MAP["ReadyCheck"] is LeagueState.QUEUE
    assert GAMEFLOW_MAP["Play"] is LeagueState.IN_GAME

def test_lcu_event_service_phase_handling():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    service = LCUEventService(client=None, manager=manager, bus=bus)

    # Transition to connected first
    manager.transition(LeagueState.CONNECTED)
    service.apply_gameflow_phase("Lobby")
    assert manager.state is LeagueState.LOBBY
    assert manager.confidence is StateConfidence.CONFIRMED

    # Unknown phase marks stale
    service.apply_gameflow_phase("UnknownSuperPhase")
    assert manager.confidence is StateConfidence.STALE

def test_action_port_impl_disconnected_safeguard():
    port = LCUActionPortImpl(lambda: None)
    assert port.is_connected() is False
    assert port.accept_ready_check() is False
    assert port.select_champion(1) is False
    assert port.lock_in_champion() is False
    assert port.ban_champion(1) is False
