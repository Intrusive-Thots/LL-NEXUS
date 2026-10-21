from nexus.core.champions.models import Champion,ChampionCatalog
from nexus.core.champions.priority import PriorityList
from nexus.core.recommendations.engine import RecommendationEngine
from nexus.core.state.models import LeagueSnapshot,Role
def test_recommendation_is_deterministic():
    catalog=ChampionCatalog([Champion(1,"Ahri","Ahri","Ahri",("MIDDLE",)),Champion(2,"Lux","Lux","Lux",("MIDDLE",))])
    priorities=PriorityList(); priorities.set_priority("Ahri",1); priorities.set_priority("Lux",2)
    e=RecommendationEngine(catalog,priorities); s=LeagueSnapshot(role=Role.MIDDLE)
    a=e.recommend(s); b=e.recommend(s)
    assert a.winner and b.winner and a.winner.champion.key=="Ahri" and a.winner.champion.key==b.winner.champion.key and a.winner.reasons


def test_recommendation_exclusions():
    catalog = ChampionCatalog([
        Champion(1, "Ahri", "Ahri", "Ahri", ("MIDDLE",)),
        Champion(2, "Lux", "Lux", "Lux", ("MIDDLE",)),
        Champion(3, "Zed", "Zed", "Zed", ("MIDDLE",)),
    ])
    priorities = PriorityList()
    priorities.set_priority("Ahri", 1)
    priorities.set_priority("Lux", 2)
    priorities.set_priority("Zed", 3)

    priorities.toggle_never_pick("Ahri")
    priorities.toggle_disabled("Lux")

    engine = RecommendationEngine(catalog, priorities)
    snapshot = LeagueSnapshot(role=Role.MIDDLE, banned_ids={3})

    rec = engine.recommend(snapshot)
    assert rec.winner is None
    assert rec.explanation() == ["No eligible champion available."]


def test_recommendation_role_matching_and_adjustments():
    catalog = ChampionCatalog([
        Champion(1, "Jinx", "Jinx", "Jinx", ("ADC",)),
        Champion(2, "Ahri", "Ahri", "Ahri", ("MIDDLE",)),
    ])
    priorities = PriorityList()
    priorities.set_priority("Jinx", 1)
    priorities.set_priority("Ahri", 2)
    priorities.toggle_preferred("Jinx")

    adjustments = {"Jinx": 2.0}
    engine = RecommendationEngine(catalog, priorities, match_adjustments=adjustments)

    snapshot_adc = LeagueSnapshot(role=Role.ADC)
    rec_adc = engine.recommend(snapshot_adc)
    assert rec_adc.winner and rec_adc.winner.champion.key == "Jinx"
    assert "Recommendation: Jinx" in rec_adc.explanation()[0]


def test_recommendation_role_override_evaluated_strictly():
    catalog = ChampionCatalog([
        Champion(1, "Lulu", "Lulu", "Lulu", ("SUPPORT",)),
    ])
    priorities = PriorityList()
    priorities.set_priority("Lulu", 1)

    engine = RecommendationEngine(catalog, priorities)

    # By default, Lulu matches SUPPORT role
    rec_supp = engine.recommend(LeagueSnapshot(role=Role.SUPPORT))
    assert rec_supp.winner and rec_supp.winner.factors["role"] > 0

    # Setting role_override to TOP means Lulu is evaluated strictly as TOP
    pref = priorities.get("Lulu")
    assert pref is not None
    pref.role_override = "TOP"

    rec_supp_override = engine.recommend(LeagueSnapshot(role=Role.SUPPORT))
    assert rec_supp_override.winner and rec_supp_override.winner.factors["role"] < 0
    assert f"Off-role for {Role.SUPPORT.display}" in rec_supp_override.winner.reasons

    rec_top_override = engine.recommend(LeagueSnapshot(role=Role.TOP))
    assert rec_top_override.winner and rec_top_override.winner.factors["role"] > 0
    assert f"{Role.TOP.display} role matched" in rec_top_override.winner.reasons
