from nexus.core.champions.models import Champion,ChampionCatalog
from nexus.core.champions.priority import PriorityList
from nexus.core.recommendations.engine import RecommendationEngine
from nexus.core.state.models import LeagueSnapshot,Role
def test_champion_upper_roles():
    c = Champion(1, "Ahri", "Ahri", "Ahri", ("middle", "Mage"))
    assert c.upper_roles == {"MIDDLE", "MAGE"}


def test_recommendation_is_deterministic():
    catalog=ChampionCatalog([Champion(1,"Ahri","Ahri","Ahri",("MIDDLE",)),Champion(2,"Lux","Lux","Lux",("MIDDLE",))])
    priorities=PriorityList(); priorities.set_priority("Ahri",1); priorities.set_priority("Lux",2)
    e=RecommendationEngine(catalog,priorities); s=LeagueSnapshot(role=Role.MIDDLE)
    a=e.recommend(s); b=e.recommend(s)
    assert a.winner and b.winner and a.winner.champion.key=="Ahri" and a.winner.champion.key==b.winner.champion.key and a.winner.reasons
