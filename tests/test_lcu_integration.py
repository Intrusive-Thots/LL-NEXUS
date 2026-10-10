import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from nexus.core.events.bus import EventBus
from nexus.core.state.manager import LeagueStateManager
from nexus.core.state.models import LeagueState, StateConfidence
from nexus.services.client_detection.detector import _parse_lockfile_path, ClientInfo
from nexus.services.lcu.client import LCUClient
from nexus.services.lcu.events import GAMEFLOW_MAP, LCUEventService


def test_lockfile_parsing_colon_format():
    with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
        tf.write("LeagueClient:1234:5678:my_secret_token:https\n")
        tf.flush()
        tf_path = Path(tf.name)

    info = _parse_lockfile_path(tf_path)
    assert info is not None
    assert info.port == 5678
    assert info.pid == 1234
    assert info.auth_token == "my_secret_token"
    assert info.source == "lockfile"
    tf_path.unlink()


def test_lockfile_parsing_json_format():
    with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
        json.dump(["Custom League Client", "", 4321, 8765, "json_token"], tf)
        tf.flush()
        tf_path = Path(tf.name)

    info = _parse_lockfile_path(tf_path)
    assert info is not None
    assert info.port == 8765
    assert info.pid == 4321
    assert info.auth_token == "json_token"
    tf_path.unlink()


def test_invalid_lockfile_returns_none():
    with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
        tf.write("invalid content")
        tf.flush()
        tf_path = Path(tf.name)

    info = _parse_lockfile_path(tf_path)
    assert info is None
    tf_path.unlink()


def test_gameflow_map_known_phases():
    assert GAMEFLOW_MAP["Lobby"] == LeagueState.LOBBY
    assert GAMEFLOW_MAP["ReadyCheck"] == LeagueState.QUEUE
    assert GAMEFLOW_MAP["ChampSelect"] == LeagueState.CHAMP_SELECT
    assert GAMEFLOW_MAP["EndOfGame"] == LeagueState.POST_GAME
    assert GAMEFLOW_MAP["GameStart"] == LeagueState.LOADING
    assert GAMEFLOW_MAP["InProgress"] == LeagueState.IN_GAME


def test_lcu_event_service_apply_gameflow_phase():
    bus = EventBus()
    mgr = LeagueStateManager(bus)
    client = MagicMock()
    service = LCUEventService(client, mgr, bus)

    service.apply_gameflow_phase("Lobby")
    assert mgr.state == LeagueState.LOBBY
    assert mgr.confidence == StateConfidence.CONFIRMED

    service.apply_gameflow_phase("ReadyCheck")
    assert mgr.state == LeagueState.QUEUE

    service.apply_gameflow_phase("ChampSelect")
    assert mgr.state == LeagueState.CHAMP_SELECT

    # Unknown phase marks state as stale
    service.apply_gameflow_phase("SomeUnknownPhase")
    assert mgr.confidence == StateConfidence.STALE


def test_lcu_event_service_apply_champ_select_ban_formats():
    bus = EventBus()
    mgr = LeagueStateManager(bus)
    client = MagicMock()
    service = LCUEventService(client, mgr, bus)

    mgr.transition(LeagueState.CONNECTED, StateConfidence.CONFIRMED, source="test")
    mgr.transition(LeagueState.LOBBY, StateConfidence.CONFIRMED, source="test")
    mgr.transition(LeagueState.QUEUE, StateConfidence.CONFIRMED, source="test")
    mgr.transition(LeagueState.SEARCHING, StateConfidence.CONFIRMED, source="test")
    mgr.transition(LeagueState.CHAMP_SELECT, StateConfidence.CONFIRMED, source="test")

    session_dict_bans = {
        "timer": {"gameDraftTime": 25.0, "totalTime": 30.0},
        "bans": {"myTeamBans": [10, 20], "theirTeamBans": [30, 40]},
        "myTeam": [
            {"championId": 100, "role": "MIDDLE", "actions": [{"completed": False, "isPick": True, "championId": 100}]}
        ],
        "theirTeam": [
            {"championId": 200}
        ],
    }

    service.apply_champ_select(session_dict_bans)
    snap = mgr.snapshot()
    assert snap.banned_ids == {10, 20, 30, 40}
    assert snap.ally_pick_ids == {100}
    assert snap.enemy_pick_ids == {200}
    assert snap.role.value == "MIDDLE"
    assert snap.timer_seconds == 25.0

    session_list_dict_bans = {
        "timer": {"duration": 15.0},
        "bans": [{"championId": 50}, {"championId": 60}],
        "myTeam": [],
        "theirTeam": [],
    }

    service.apply_champ_select(session_list_dict_bans)
    snap = mgr.snapshot()
    assert snap.banned_ids == {50, 60}
    assert snap.timer_seconds == 15.0

    session_list_int_bans = {
        "bans": [70, 80],
        "myTeam": [],
        "theirTeam": [],
    }

    service.apply_champ_select(session_list_int_bans)
    snap = mgr.snapshot()
    assert snap.banned_ids == {70, 80}
