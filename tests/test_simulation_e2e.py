import time
from nexus.core.events.bus import EventBus
from nexus.core.champions.models import default_catalog
from nexus.core.state.manager import LeagueStateManager
from nexus.core.state.models import LeagueState, Role
from nexus.developer.simulation.port import SimActionPort
from nexus.developer.simulation.simulator import Simulator

def test_simulator_scenarios_and_verbs():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    catalog = default_catalog()
    sim = Simulator(manager, bus, catalog)

    assert sim.feed("CONNECT")
    assert manager.state is LeagueState.CONNECTED

    assert sim.feed("LOBBY")
    assert manager.state is LeagueState.LOBBY

    assert sim.feed("SEARCHING")
    assert manager.state is LeagueState.SEARCHING

    assert sim.feed("CHAMP_SELECT", queue_type="Ranked Solo")
    assert manager.state is LeagueState.CHAMP_SELECT

    assert sim.feed("ROLE_DETECTED", role="ADC")
    assert manager.snapshot().role is Role.ADC

    assert sim.feed("PICK_PHASE")
    assert manager.state is LeagueState.PICK_PHASE

    sim.reset()
    assert manager.state is LeagueState.DISCONNECTED

def test_sim_action_port_e2e():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    catalog = default_catalog()
    port = SimActionPort(manager, catalog)

    manager.transition(LeagueState.CONNECTED)
    manager.transition(LeagueState.LOBBY)
    manager.transition(LeagueState.QUEUE)
    manager.transition(LeagueState.SEARCHING)

    assert port.accept_ready_check() is True
    assert manager.state is LeagueState.CHAMP_SELECT

    manager.transition(LeagueState.PICK_PHASE, action_is_pick=True)
    jinx = catalog.by_name("Jinx")
    assert jinx is not None

    assert port.select_champion(jinx.id) is True
    assert port.verify_selection(jinx.id) is True

    assert port.lock_in_champion() is True
    assert port.verify_locked() is True
