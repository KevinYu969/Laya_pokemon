"""六人補練在下一次走草前檢查全隊，正常回城步驟仍可執行。"""
from test_shared_experience_training import Harness
from laya_pokemon.campaign_safety import attrition_context


def setup(monkeypatch):
    env=Harness(monkeypatch)
    env.state['phase']='unclassified'
    env.state['battle_state'].update(kind='none',raw=0,active=False)
    env.plan['steps']=[{'id':'grass','kind':'move'}]
    return env


def test_poisoned_support_stops_before_next_encounter(monkeypatch):
    env=setup(monkeypatch);env.party[-1]['status']=8
    out=attrition_context(env.state,env.plan,'grass')
    assert out['review_reason']=='party_attrition_requires_center'
    assert out['party_attrition']['training_team_needs_center'] is True


def test_support_low_hp_or_no_attack_pp_also_returns_center(monkeypatch):
    env=setup(monkeypatch);env.party[-1]['hp']=1
    assert attrition_context(env.state,env.plan,'grass')['review_reason']=='party_attrition_requires_center'
    env.party[-1]['hp']=env.party[-1]['max_hp'];env.party[-1]['pp']=[0]*4
    assert attrition_context(env.state,env.plan,'grass')['review_reason']=='party_attrition_requires_center'


def test_marked_recovery_allows_normal_healing_and_other_plans_keep_prior_policy(monkeypatch):
    env=setup(monkeypatch);env.party[-1]['status']=8
    env.plan['steps'][0]['recovery_route']=True
    assert attrition_context(env.state,env.plan,'grass') is None
    env.plan['steps'][0]['recovery_route']=False
    env.plan['training_shared_experience']=False
    assert attrition_context(env.state,env.plan,'grass') is None
