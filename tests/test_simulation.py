from nexus.core.events.bus import EventBus
from nexus.core.champions.models import default_catalog
from nexus.core.state.manager import LeagueStateManager
from nexus.developer.simulation.port import SimActionPort
from nexus.developer.simulation.simulator import Simulator
def test_simulator_constructs():
    b=EventBus(); m=LeagueStateManager(b); c=default_catalog(); Simulator(m,b,c)
def test_sim_port_constructs():
    SimActionPort(LeagueStateManager(EventBus()),default_catalog())

def test_simulation_app_controller_lifecycle(tmp_path):
    from nexus.app.controller import AppController
    from nexus.core.state.models import LeagueState
    controller = AppController(data_dir=tmp_path, simulate=True)
    controller.start()
    try:
        controller.simulator.feed("CONNECT")
        controller.simulator.feed("LOBBY")
        controller.simulator.feed("QUEUE")
        controller.simulator.feed("CHAMP_SELECT", queue_type="Ranked Solo/Duo")
        controller.simulator.feed("ROLE_DETECTED", role="ADC")
        controller.simulator.feed("PICK_PHASE", timer_seconds=30.0, timer_total_seconds=30.0, action_is_pick=True)
        assert controller.manager.state is LeagueState.PICK_PHASE
        rec = controller.automation.pending_recommendation or controller.automation._refresh_recommendation(controller.manager.snapshot())
        assert rec is not None
        assert rec.winner is not None
        assert rec.winner.champion.name == "Aphelios"
    finally:
        controller.shutdown()
