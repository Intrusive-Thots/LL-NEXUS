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


def test_priority_normalization():
    sparse_data = [
        {"champion_key": "Ahri", "priority": 1},
        {"champion_key": "Lux", "priority": 5},
        {"champion_key": "Jinx", "priority": 12},
    ]
    pl = PriorityList.from_list(sparse_data)
    assert pl.get("Ahri").priority == 1
    assert pl.get("Lux").priority == 2
    assert pl.get("Jinx").priority == 3

    # Direct call to normalize
    pl_direct = PriorityList.from_list([])
    pl_direct.ensure("Ahri").priority = 10
    pl_direct.ensure("Lux").priority = 20
    pl_direct.normalize()
    assert pl_direct.get("Ahri").priority == 1
    assert pl_direct.get("Lux").priority == 2


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
