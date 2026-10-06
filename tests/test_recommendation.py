from nexus.core.champions.models import ChampionCatalog
from nexus.core.champions.priority import PriorityList
from nexus.core.recommendations.engine import RecommendationEngine
from nexus.core.state.models import LeagueSnapshot,Role
def test_recommendation_is_deterministic():
    catalog=ChampionCatalog.from_dict({"champions":[{"id":1,"key":"Ahri","name":"Ahri","roles":["MIDDLE"]},{"id":2,"key":"Lux","name":"Lux","roles":["MIDDLE"]}]})
    priorities=PriorityList(); priorities.set_priority("Ahri",1); priorities.set_priority("Lux",2)
    e=RecommendationEngine(catalog,priorities); s=LeagueSnapshot(role=Role.MIDDLE)
    a=e.recommend(s); b=e.recommend(s)
    assert a.winner and b.winner and a.winner.champion.key=="Ahri" and a.winner.champion.key==b.winner.champion.key and a.winner.reasons
