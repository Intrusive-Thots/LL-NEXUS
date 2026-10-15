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


def test_priority_list_movements_and_toggles():
    pl = PriorityList()
    pl.set_priority("Jinx", 1)
    pl.set_priority("Ashe", 2)
    pl.set_priority("Ezreal", 3)

    assert [p.champion_key for p in pl.ranked()] == ["Jinx", "Ashe", "Ezreal"]

    # Move Ezreal up by 1 position
    pl.move("Ezreal", -1)
    assert [p.champion_key for p in pl.ranked()] == ["Jinx", "Ezreal", "Ashe"]

    # Swap Ashe with neighbor towards start
    assert pl.swap_with_neighbour("Ashe", towards_start=True) is True
    assert [p.champion_key for p in pl.ranked()] == ["Jinx", "Ashe", "Ezreal"]

    # Move unranked champion
    pl.move("Caitlyn", -1)
    assert pl.get("Caitlyn").priority == 1

    # Toggles and removal
    assert pl.toggle_disabled("Jinx") is True
    assert pl.get("Jinx").disabled is True

    assert pl.toggle_never_pick("Jinx") is True
    assert pl.get("Jinx").never_pick is True

    assert pl.toggle_preferred("Jinx") is True
    assert pl.get("Jinx").preferred is True

    pl.remove_priority("Jinx")
    assert pl.get("Jinx").priority is None
