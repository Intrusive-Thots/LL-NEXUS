from nexus.core.events.bus import EventBus
from nexus.core.champions.models import default_catalog
from nexus.core.state.manager import LeagueStateManager
from nexus.developer.simulation.port import SimActionPort
from nexus.developer.simulation.simulator import Simulator
def test_simulator_constructs():
    b=EventBus(); m=LeagueStateManager(b); c=default_catalog(); Simulator(m,b,c)
def test_sim_port_constructs():
    SimActionPort(LeagueStateManager(EventBus()),default_catalog())
