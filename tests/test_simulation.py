from nexus.core.events.bus import EventBus
from nexus.core.champions.models import default_catalog
from nexus.core.state.manager import LeagueStateManager
from nexus.core.state.models import LeagueState, StateConfidence
from nexus.developer.simulation.port import SimActionPort
from nexus.developer.simulation.simulator import Simulator, SCENARIOS


def test_simulator_constructs():
    b = EventBus()
    m = LeagueStateManager(b)
    c = default_catalog()
    s = Simulator(m, b, c)
    assert s.current_scenario is None
    assert not s.playing


def test_sim_port_constructs_and_acts():
    b = EventBus()
    m = LeagueStateManager(b)
    c = default_catalog()
    avail = {c.all[0].id}
    port = SimActionPort(m, c, available_ids=avail)
    assert port.is_connected()

    m.transition(LeagueState.CONNECTED)
    m.transition(LeagueState.LOBBY)
    m.transition(LeagueState.QUEUE)
    assert port.accept_ready_check()
    assert m.state == LeagueState.CHAMP_SELECT
    assert port.available_champion_ids() is not None

    champ = c.all[0]
    m.transition(LeagueState.PICK_PHASE, action_is_pick=True)
    assert port.select_champion(champ.id)
    assert port.verify_selection(champ.id)
    assert port.lock_in_champion()
    assert port.verify_locked()


def test_all_scenarios_feed_cleanly():
    b = EventBus()
    m = LeagueStateManager(b)
    c = default_catalog()
    sim = Simulator(m, b, c)

    for sc in SCENARIOS:
        sim.reset()
        for step in sc.steps:
            sim.feed(step.verb, **step.params)


def test_simulation_reset():
    b = EventBus()
    m = LeagueStateManager(b)
    c = default_catalog()
    sim = Simulator(m, b, c)

    sim.feed("CONNECT")
    sim.feed("LOBBY")
    assert m.state == LeagueState.LOBBY

    sim.reset()
    assert m.state == LeagueState.DISCONNECTED
