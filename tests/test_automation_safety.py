import time
import pytest
from nexus.core.automation.config import AutomationConfig
from nexus.core.automation.controller import AutomationController, AutomationStatus, Decision
from nexus.core.automation.kill_switch import GlobalKillSwitch, KillSwitchTripped
from nexus.core.automation.port import LCUActionPort
from nexus.core.champions.models import Champion, ChampionCatalog
from nexus.core.champions.priority import PriorityList
from nexus.core.events.bus import EventBus
from nexus.core.recommendations.engine import RecommendationEngine
from nexus.core.sessions.recorder import SessionRecorder
from nexus.core.state.manager import LeagueStateManager
from nexus.core.state.models import LeagueState, Role, StateConfidence


class DummyPort(LCUActionPort):
    def __init__(self, connected: bool = True, accept_result: bool = True,
                 verify_result: bool = True):
        self._connected = connected
        self._accept_result = accept_result
        self._verify_result = verify_result
        self.actions_attempted = []

    def accept_ready_check(self) -> bool:
        self.actions_attempted.append("accept_ready_check")
        return self._accept_result

    def select_champion(self, champion_id: int) -> bool:
        self.actions_attempted.append(f"select:{champion_id}")
        return self._accept_result

    def lock_in_champion(self) -> bool:
        self.actions_attempted.append("lock_in")
        return self._accept_result

    def ban_champion(self, champion_id: int) -> bool:
        self.actions_attempted.append(f"ban:{champion_id}")
        return self._accept_result

    def verify_selection(self, champion_id: int) -> bool:
        return self._verify_result

    def verify_locked(self) -> bool:
        return self._verify_result

    def verify_ban(self, champion_id: int) -> bool:
        return self._verify_result

    def available_champion_ids(self):
        return {1, 2}

    def is_connected(self) -> bool:
        return self._connected


def test_kill_switch_blocks_and_resets():
    k = GlobalKillSwitch()
    assert k.armed
    assert not k.tripped

    k.trip("manual test stop")
    assert k.tripped
    assert not k.armed
    assert k.trip_count == 1

    with pytest.raises(KillSwitchTripped) as exc_info:
        k.guard()
    assert "manual test stop" in str(exc_info.value)

    k.reset()
    assert k.armed
    assert not k.tripped
    k.guard()  # Should not raise


def test_fail_closed_on_stale_confidence():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    port = DummyPort()
    catalog = ChampionCatalog([Champion(1, "Ahri", "Ahri", "Ahri", ("MIDDLE",))])
    priorities = PriorityList()
    priorities.set_priority("Ahri", 1)
    engine = RecommendationEngine(catalog, priorities)
    recorder = SessionRecorder(bus)
    cfg = AutomationConfig(master_enabled=True, auto_pick=True)

    controller = AutomationController(
        manager, bus, port, engine, recorder, config=cfg
    )

    manager.transition(LeagueState.CONNECTED, StateConfidence.CONFIRMED)
    manager.transition(LeagueState.LOBBY, StateConfidence.CONFIRMED)
    manager.transition(LeagueState.QUEUE, StateConfidence.CONFIRMED)
    manager.transition(LeagueState.CHAMP_SELECT, StateConfidence.CONFIRMED)

    # State is CONFIRMED -> ARMED
    controller.evaluate_once()
    assert controller.status == AutomationStatus.ARMED

    # Stale confidence -> fails closed to PAUSED
    manager.mark_stale()
    controller.evaluate_once()
    assert controller.status == AutomationStatus.PAUSED_STALE


def test_emergency_stop_blocks_action():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    port = DummyPort()
    catalog = ChampionCatalog([Champion(1, "Ahri", "Ahri", "Ahri", ("MIDDLE",))])
    priorities = PriorityList()
    priorities.set_priority("Ahri", 1)
    engine = RecommendationEngine(catalog, priorities)
    recorder = SessionRecorder(bus)
    cfg = AutomationConfig(master_enabled=True, auto_pick=True, lock_in_delay_seconds=0.0)

    controller = AutomationController(
        manager, bus, port, engine, recorder, config=cfg
    )

    manager.transition(LeagueState.CONNECTED, StateConfidence.CONFIRMED)
    manager.transition(LeagueState.LOBBY, StateConfidence.CONFIRMED)
    manager.transition(LeagueState.QUEUE, StateConfidence.CONFIRMED)
    manager.transition(LeagueState.CHAMP_SELECT, StateConfidence.CONFIRMED)
    manager.transition(LeagueState.PICK_PHASE, StateConfidence.CONFIRMED, action_is_pick=True)

    controller.emergency_stop("user hit stop button")
    assert controller.status == AutomationStatus.STOPPED
    assert controller.kill_switch.tripped

    controller.evaluate_once()
    assert port.actions_attempted == []


def test_verification_mismatch_refuses_blind_repetition():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    # Port accepts call, but verification fails
    port = DummyPort(connected=True, accept_result=True, verify_result=False)
    catalog = ChampionCatalog([Champion(1, "Ahri", "Ahri", "Ahri", ("MIDDLE",))])
    priorities = PriorityList()
    priorities.set_priority("Ahri", 1)
    engine = RecommendationEngine(catalog, priorities)
    recorder = SessionRecorder(bus)
    cfg = AutomationConfig(master_enabled=True, auto_pick=True, lock_in_delay_seconds=0.0)

    controller = AutomationController(
        manager, bus, port, engine, recorder, config=cfg
    )

    d = Decision(kind="auto_pick", action="select Ahri")
    ok = controller._execute(d, lambda: port.select_champion(1), verify=lambda: port.verify_selection(1))

    assert not ok
    assert d.result == "FAILED"
    assert "verification mismatch" in d.detail


def test_recommendation_generated_when_automation_disabled():
    bus = EventBus()
    manager = LeagueStateManager(bus)
    port = DummyPort()
    catalog = ChampionCatalog([Champion(1, "Ahri", "Ahri", "Ahri", ("MIDDLE",))])
    priorities = PriorityList()
    priorities.set_priority("Ahri", 1)
    engine = RecommendationEngine(catalog, priorities)
    recorder = SessionRecorder(bus)
    cfg = AutomationConfig(master_enabled=False)

    controller = AutomationController(
        manager, bus, port, engine, recorder, config=cfg
    )

    manager.transition(LeagueState.CONNECTED, StateConfidence.CONFIRMED)
    manager.transition(LeagueState.LOBBY, StateConfidence.CONFIRMED)
    manager.transition(LeagueState.QUEUE, StateConfidence.CONFIRMED)
    manager.transition(LeagueState.CHAMP_SELECT, StateConfidence.CONFIRMED)
    manager.update_fields(role=Role.MIDDLE)

    controller.evaluate_once()
    assert controller.status == AutomationStatus.STOPPED
    assert controller.pending_recommendation is not None
    assert controller.pending_recommendation.winner.champion.name == "Ahri"
