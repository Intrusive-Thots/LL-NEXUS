import tempfile
from pathlib import Path
from nexus.core.preferences.settings import Settings, SettingsStore
from nexus.core.champions.priority import PriorityList
from nexus.core.sessions.models import Session
from nexus.services.persistence.store import PersistenceService


def test_settings_store_persistence():
    with tempfile.TemporaryDirectory() as td:
        dir_path = Path(td)
        store = SettingsStore(dir_path)
        store.load()

        assert store.settings.automation.master_enabled is True
        store.settings.automation.master_enabled = False
        store.save()

        # Reload in a new store instance
        store2 = SettingsStore(dir_path)
        store2.load()
        assert store2.settings.automation.master_enabled is False


def test_priority_persistence():
    with tempfile.TemporaryDirectory() as td:
        dir_path = Path(td)
        store = SettingsStore(dir_path)
        store.load()

        store.priorities.set_priority("Ahri", 1)
        store.priorities.set_priority("Lux", 2)
        store.save_priorities()

        store2 = SettingsStore(dir_path)
        store2.load()
        ahri_pref = store2.priorities.get("Ahri")
        lux_pref = store2.priorities.get("Lux")
        assert ahri_pref is not None and ahri_pref.priority == 1
        assert lux_pref is not None and lux_pref.priority == 2


def test_session_sqlite_persistence():
    with tempfile.TemporaryDirectory() as td:
        dir_path = Path(td)
        svc = PersistenceService(dir_path)
        assert svc.diagnostics()["healthy"] is True

        s = Session(number=1, queue_type="Ranked Solo/Duo", role="ADC")
        s.add("state", "Entered Queue")
        s.add("action", "Picked Jinx")
        s.finish("SUCCESS")

        assert svc.save_session(s) is True

        recent = svc.load_recent()
        assert len(recent) == 1
        assert recent[0].number == 1
        assert recent[0].queue_type == "Ranked Solo/Duo"
        assert recent[0].result == "SUCCESS"
        assert len(recent[0].events) == 2

        exported = svc.export_all()
        assert len(exported) == 1
        svc.close()


def test_session_recorder_syncs_queue_and_role():
    from nexus.core.events.bus import EventBus
    from nexus.core.sessions.recorder import SessionRecorder
    from nexus.core.state.manager import LeagueStateManager
    from nexus.core.state.models import LeagueState, Role

    bus = EventBus()
    state_mgr = LeagueStateManager(bus)
    recorder = SessionRecorder(bus)

    # Transition DISCONNECTED -> CONNECTED -> LOBBY -> QUEUE
    state_mgr.transition(LeagueState.CONNECTED)
    state_mgr.transition(LeagueState.LOBBY)
    state_mgr.transition(LeagueState.QUEUE, queue_type="Ranked Solo/Duo", role=Role.ADC)
    session = recorder.active
    assert session is not None
    assert session.queue_type == "Ranked Solo/Duo"
    assert session.role == "ADC"

    # Field updates propagate
    state_mgr.update_fields(queue_type="Flex", role=Role.MIDDLE)
    assert session.queue_type == "Ranked Solo/Duo"  # set_context keeps first non-null queue_type
    assert session.role == "MIDDLE"  # role gets updated if initially set or overridden

    recorder.shutdown()
