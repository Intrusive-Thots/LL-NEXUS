from nexus.core.champions.models import Champion, ChampionCatalog
from nexus.core.champions.priority import PriorityList
from nexus.core.recommendations.engine import RecommendationEngine
from nexus.core.state.models import LeagueSnapshot, Role

def test_recommendation_never_pick_and_unavailable():
    catalog = ChampionCatalog([
        Champion(1, "Ahri", "Ahri", "Ahri", ("MIDDLE",)),
        Champion(2, "Lux", "Lux", "Lux", ("MIDDLE",)),
        Champion(3, "Syndra", "Syndra", "Syndra", ("MIDDLE",)),
    ])
    priorities = PriorityList()
    priorities.set_priority("Ahri", 1)
    priorities.set_priority("Lux", 2)
    priorities.set_priority("Syndra", 3)

    # Hard exclude Ahri via never_pick
    priorities.toggle_never_pick("Ahri")

    engine = RecommendationEngine(catalog, priorities)
    snap = LeagueSnapshot(role=Role.MIDDLE)

    # Ahri is excluded via never_pick, Lux should be winner
    rec1 = engine.recommend(snap)
    assert rec1.winner is not None
    assert rec1.winner.champion.key == "Lux"

    # Lux is unavailable, Syndra should win
    rec2 = engine.recommend(snap, unavailable_keys={"Lux"})
    assert rec2.winner is not None
    assert rec2.winner.champion.key == "Syndra"
