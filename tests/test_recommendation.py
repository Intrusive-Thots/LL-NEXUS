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


def test_recommendation_role_override():
    # Ahri is catalog MIDDLE, but overridden to TOP
    catalog = ChampionCatalog([
        Champion(1, "Ahri", "Ahri", "Ahri", ("MIDDLE",)),
        Champion(2, "Garen", "Garen", "Garen", ("TOP",)),
    ])
    priorities = PriorityList()
    priorities.set_priority("Ahri", 1)
    priorities.set_priority("Garen", 2)

    p_ahri = priorities.ensure("Ahri")
    p_ahri.role_override = "TOP"

    engine = RecommendationEngine(catalog, priorities)

    # When role is TOP, Ahri matches role_override TOP
    rec_top = engine.recommend(LeagueSnapshot(role=Role.TOP))
    ahri_score = next(c for c in rec_top.ranked if c.champion.key == "Ahri")
    assert "Top role matched" in ahri_score.reasons

    # When role is MIDDLE, Ahri does NOT match because role_override TOP overrides catalog MIDDLE
    rec_mid = engine.recommend(LeagueSnapshot(role=Role.MIDDLE))
    ahri_score_mid = next(c for c in rec_mid.ranked if c.champion.key == "Ahri")
    assert "Off-role for MID" in ahri_score_mid.reasons
