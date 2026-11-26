from nexus.core.champions.preferences import ChampionPreference
from nexus.core.champions.priority import PriorityList


def test_priority_list_initialization():
    plist = PriorityList()
    assert plist.all == []
    assert plist.ranked() == []

    p1 = ChampionPreference(champion_key="Ahri", priority=2)
    p2 = ChampionPreference(champion_key="Zed", priority=1)
    plist2 = PriorityList([p1, p2])

    assert len(plist2.all) == 2
    assert plist2.ranked()[0].champion_key == "Zed"
    assert plist2.ranked()[1].champion_key == "Ahri"


def test_set_priority_shifts_and_normalizes():
    plist = PriorityList()
    plist.set_priority("Ahri", 1)
    plist.set_priority("Zed", 2)
    plist.set_priority("Lux", 3)

    assert [p.champion_key for p in plist.ranked()] == ["Ahri", "Zed", "Lux"]
    assert [p.priority for p in plist.ranked()] == [1, 2, 3]

    # Insert Lux at rank 1
    plist.set_priority("Lux", 1)
    assert [p.champion_key for p in plist.ranked()] == ["Lux", "Ahri", "Zed"]
    assert [p.priority for p in plist.ranked()] == [1, 2, 3]

    # Insert new champion at rank 2
    plist.set_priority("Yasuo", 2)
    assert [p.champion_key for p in plist.ranked()] == ["Lux", "Yasuo", "Ahri", "Zed"]
    assert [p.priority for p in plist.ranked()] == [1, 2, 3, 4]


def test_move_and_swap_neighbour():
    plist = PriorityList()
    for i, key in enumerate(["A", "B", "C", "D"], start=1):
        plist.set_priority(key, i)

    # Move C up by 1 position (delta -1)
    plist.move("C", -1)
    assert [p.champion_key for p in plist.ranked()] == ["A", "C", "B", "D"]

    # Swap B with neighbour towards start (up)
    swapped = plist.swap_with_neighbour("B", towards_start=True)
    assert swapped is True
    assert [p.champion_key for p in plist.ranked()] == ["A", "B", "C", "D"]

    # Swap A towards start (invalid boundary)
    swapped_boundary = plist.swap_with_neighbour("A", towards_start=True)
    assert swapped_boundary is False
    assert [p.champion_key for p in plist.ranked()] == ["A", "B", "C", "D"]


def test_toggles_and_removal():
    plist = PriorityList()
    plist.set_priority("A", 1)
    plist.set_priority("B", 2)

    assert plist.toggle_disabled("A") is True
    assert plist.get("A").disabled is True
    assert plist.toggle_disabled("A") is False

    assert plist.toggle_never_pick("B") is True
    assert plist.get("B").never_pick is True

    assert plist.toggle_preferred("A") is True
    assert plist.get("A").preferred is True

    # Remove priority for A
    plist.remove_priority("A")
    assert plist.get("A").priority is None
    assert [p.champion_key for p in plist.ranked()] == ["B"]
    assert plist.get("B").priority == 1


def test_serialization_roundtrip():
    plist = PriorityList()
    plist.set_priority("Ahri", 1)
    plist.toggle_never_pick("Ahri")
    plist.set_priority("Jinx", 2)
    plist.toggle_preferred("Jinx")

    data = plist.to_list()
    restored = PriorityList.from_list(data)

    assert len(restored.all) == 2
    assert restored.get("Ahri").priority == 1
    assert restored.get("Ahri").never_pick is True
    assert restored.get("Jinx").priority == 2
    assert restored.get("Jinx").preferred is True
