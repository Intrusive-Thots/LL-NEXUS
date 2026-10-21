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


def test_recommendation_role_override_strict_evaluation():
    catalog = ChampionCatalog([
        Champion(111, "111", "Nautilus", "Nautilus", ("SUPPORT", "MIDDLE")),
    ])
    priorities = PriorityList()
    pref = priorities.ensure("111")
    pref.role_override = "SUPPORT"

    engine = RecommendationEngine(catalog, priorities)

    # When assigned role is MID, even though Nautilus has "MIDDLE" in catalog,
    # role_override "SUPPORT" strictly overrides and causes off-role evaluation.
    snapshot_mid = LeagueSnapshot(role=Role.MIDDLE)
    rec_mid = engine.recommend(snapshot_mid)
    assert rec_mid.winner is not None
    assert any("Off-role for MID" in r for r in rec_mid.winner.reasons)

    # When assigned role is SUPPORT, role_override "SUPPORT" matches.
    snapshot_supp = LeagueSnapshot(role=Role.SUPPORT)
    rec_supp = engine.recommend(snapshot_supp)
    assert rec_supp.winner is not None
    assert any("SUP role matched" in r for r in rec_supp.winner.reasons)
