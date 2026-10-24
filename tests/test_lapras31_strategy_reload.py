from importlib import reload
from laya_pokemon import campaign_route,battle,team_strategy,levelup_moves

def test_campaign_resume_refreshes_strategy_before_natural_learning_and_retains_session(monkeypatch):
    stale=lambda *a,**k:{'decision':'replace','replace_index':2,'forget':'SING','move':'CONFUSE_RAY'}
    monkeypatch.setattr(team_strategy,'learn_move_plan',stale)
    monkeypatch.setattr(levelup_moves,'learn_move_plan',stale)
    original={'error':'original-error','baseline':('retained',),'waits':7}
    monkeypatch.setattr(levelup_moves,'_SESSION',original)
    assert levelup_moves.candidate_plan(19,31,[57,34,47,54])['replace_index']==2
    reload(campaign_route)
    reload(battle)
    assert levelup_moves.candidate_plan(19,31,[57,34,47,54])['replace_index']==3
    assert levelup_moves._SESSION is original and original['waits']==7 and original['error']=='original-error'
