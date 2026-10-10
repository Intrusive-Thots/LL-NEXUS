from nexus.core.champions.models import Champion, ChampionCatalog
from nexus.core.champions.priority import PriorityList
from nexus.core.recommendations.engine import RecommendationEngine
from nexus.core.state.models import LeagueSnapshot, Role


def test_recommendation_is_deterministic():
    catalog = ChampionCatalog([
        Champion(1, "Ahri", "Ahri", "Ahri", ("MIDDLE",)),
        Champion(2, "Lux", "Lux", "Lux", ("MIDDLE",)),
    ])
    priorities = PriorityList()
    priorities.set_priority("Ahri", 1)
    priorities.set_priority("Lux", 2)
    e = RecommendationEngine(catalog, priorities)
    s = LeagueSnapshot(role=Role.MIDDLE)
    a = e.recommend(s)
    b = e.recommend(s)
    assert a.winner and b.winner
    assert a.winner.champion.key == "Ahri"
    assert a.winner.champion.key == b.winner.champion.key
    assert a.winner.reasons


def test_recommendation_exclusions_and_off_role():
    catalog = ChampionCatalog([
        Champion(1, "Ahri", "Ahri", "Ahri", ("MIDDLE",)),
        Champion(2, "Lux", "Lux", "Lux", ("MIDDLE",)),
        Champion(3, "Garen", "Garen", "Garen", ("TOP",)),
    ])
    priorities = PriorityList()
    priorities.set_priority("Ahri", 1)
    priorities.set_priority("Lux", 2)
    priorities.set_priority("Garen", 3)

    pref_ahri = priorities.get("Ahri")
    assert pref_ahri is not None
    pref_ahri.never_pick = True

    e = RecommendationEngine(catalog, priorities)
    s = LeagueSnapshot(role=Role.MIDDLE, banned_ids=(2,))  # Lux banned

    rec = e.recommend(s)
    assert rec.winner is not None
    assert rec.winner.champion.key == "Garen"
    assert "Off-role for MID" in rec.winner.reasons

    explanation = rec.explanation()
    assert any("Recommendation: Garen" in line for line in explanation)
    assert len(rec.context_summary) >= 2
