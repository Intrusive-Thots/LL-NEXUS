import json
from pathlib import Path
from nexus.core.champions.priority import PriorityList
from nexus.core.champions.preferences import ChampionPreference
from nexus.core.preferences.settings import Settings, SettingsStore

def test_settings_store_save_load(tmp_path: Path):
    store = SettingsStore(tmp_path)
    store.settings.appearance.theme = "light"
    store.settings.automation.auto_accept_ready = True
    store.save()

    new_store = SettingsStore(tmp_path)
    assert new_store.settings.appearance.theme == "light"
    assert new_store.settings.automation.auto_accept_ready is True

def test_priority_list_mutations_and_persistence(tmp_path: Path):
    priorities = PriorityList()
    priorities.set_priority("Ahri", 1)
    priorities.set_priority("Lux", 2)
    priorities.set_priority("Jinx", 3)

    assert priorities.ranked()[0].champion_key == "Ahri"
    assert priorities.ranked()[1].champion_key == "Lux"

    # Move Lux up
    priorities.move("Lux", -1)
    assert priorities.ranked()[0].champion_key == "Lux"
    assert priorities.ranked()[1].champion_key == "Ahri"

    # Toggle options
    priorities.toggle_never_pick("Jinx")
    assert priorities.get("Jinx").never_pick is True

    # Persist via store
    store = SettingsStore(tmp_path)
    store.priorities = priorities
    store.save_priorities()

    new_store = SettingsStore(tmp_path)
    p_loaded = new_store.priorities
    assert p_loaded.get("Jinx").never_pick is True
    assert p_loaded.ranked()[0].champion_key == "Lux"
