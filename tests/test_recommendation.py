from nexus.core.champions.models import Champion, ChampionCatalog
from nexus.core.champions.priority import PriorityList
from nexus.core.recommendations.engine import RecommendationEngine
from nexus.core.state.models import LeagueSnapshot, Role


def test_champion_upper_roles():
    c = Champion(1, "Ahri", "Ahri", "Ahri", ("middle", "Mage"))
    assert c.upper_roles == {"MIDDLE", "MAGE"}


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


def test_recommendation_role_override_strict():
    catalog = ChampionCatalog([
        Champion(1, "Jinx", "Jinx", "Jinx", ("ADC",)),
        Champion(2, "Ahri", "Ahri", "Ahri", ("MIDDLE",)),
    ])
    priorities = PriorityList()
    priorities.set_priority("Jinx", 1)
    # Set role override on Jinx to MIDDLE (she is natively ADC)
    pref = priorities.get("Jinx")
    assert pref is not None
    pref.role_override = "MIDDLE"

    engine = RecommendationEngine(catalog, priorities)

    # In ADC role, Jinx has role_override="MIDDLE", so it should NOT match ADC via catalog default roles
    snapshot_adc = LeagueSnapshot(role=Role.ADC)
    rec_adc = engine.recommend(snapshot_adc)
    jinx_score = next(c for c in rec_adc.ranked if c.champion.key == "Jinx")
    assert jinx_score.factors["role"] == -40.0
    assert "Off-role for ADC" in jinx_score.reasons

    # In MIDDLE role, Jinx's role_override="MIDDLE" matches
    snapshot_mid = LeagueSnapshot(role=Role.MIDDLE)
    rec_mid = engine.recommend(snapshot_mid)
    jinx_score_mid = next(c for c in rec_mid.ranked if c.champion.key == "Jinx")
    assert jinx_score_mid.factors["role"] == 40.0
    assert f"{Role.MIDDLE.display} role matched" in jinx_score_mid.reasons


def test_recommendation_role_override():
    catalog = ChampionCatalog([
        Champion(1, "Garen", "Garen", "Garen", ("TOP",)),
        Champion(2, "Ahri", "Ahri", "Ahri", ("MIDDLE",)),
    ])
    priorities = PriorityList()
    priorities.set_priority("Garen", 1)
    priorities.set_priority("Ahri", 2)
    priorities.set_role_override("Garen", "MIDDLE")

    engine = RecommendationEngine(catalog, priorities)
    snapshot = LeagueSnapshot(role=Role.MIDDLE)

    rec = engine.recommend(snapshot)
    assert rec.winner and rec.winner.champion.key == "Garen"
    garen_score = [c for c in rec.ranked if c.champion.key == "Garen"][0]
    assert "MID role matched" in garen_score.reasons


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
