"""runner窄分派：不以禮物owner繞過真倒下、低血或其他未知原因。"""
from types import SimpleNamespace
import pytest
from laya_pokemon import campaign_route as route


@pytest.mark.parametrize('reason,issue',[
 ('party_attrition_requires_center','party_read_not_verified'),
 ('battle_loss_requires_review','party_read_not_verified'),
 ('party_attrition_state_unverified','party_hp_invalid'),
 ('party_attrition_state_unverified','party_roster_invalid'),
 ('party_attrition_state_unverified','party_count_mismatch'),
 ('party_attrition_state_unverified',None),('unknown','party_read_not_verified')])
def test_other_failures_never_read_ui_or_call_lapras_hook(monkeypatch,reason,issue):
    def forbidden(*a,**kw):raise AssertionError('其他安全原因不可委派命名過渡')
    from laya_pokemon import observation
    monkeypatch.setattr(observation,'read_visible_text',forbidden)
    monkeypatch.setattr(route.lapras_bridge,'pre_attrition_context',forbidden)
    assert route.attrition_transition_context(None,{}, {}, 'gift',
        dict(review_reason=reason,party_attrition=dict(issue=issue))) is None


@pytest.mark.parametrize('result',[None,({'phase':'campaign_review','review_reason':'native_unknown'},'gift'),
                                 ({'phase':'lapras_gift','available_actions':['wait']},'gift')])
def test_exact_unknown_party_reason_passes_original_observation_and_keeps_result(monkeypatch,result):
    from laya_pokemon import observation
    text={'sentinel':'unaltered text'};grid={'sentinel':'same-frame grid'}
    state={'location':dict(map_id=212,x=2,y=5),'progress':{'party':[]}}
    plan={'steps':[]};emulator=object();seen=[]
    monkeypatch.setattr(observation,'read_visible_text',lambda p:text)
    monkeypatch.setattr(route,'read_world_grid',lambda p,loc:grid)
    def hook(*args):
        seen.append(args);return result
    monkeypatch.setattr(route.lapras_bridge,'pre_attrition_context',hook)
    assert route.attrition_transition_context(emulator,state,plan,'gift',
        dict(review_reason='party_attrition_state_unverified',
             party_attrition=dict(issue='party_read_not_verified'))) is result
    assert seen==[(emulator,state,plan,'gift',text,grid)]


def test_normal_field_lapras_owner_uses_same_bridge_and_advances_only_its_receipt(monkeypatch):
    from laya_pokemon import observation
    text={};grid={};state={'location':dict(map_id=212,x=2,y=5)}
    plan={'steps':[dict(id='gift',mechanic='silph_lapras_gift')]}
    expected=({'phase':'lapras_gift_complete','available_actions':['wait']},'after')
    monkeypatch.setattr(observation,'read_visible_text',lambda p:text)
    monkeypatch.setattr(route,'read_world_grid',lambda p,loc:grid)
    monkeypatch.setattr(route.lapras_bridge,'applies',lambda *a:True)
    def context(p,s,pl,sid,t,g):
        assert (s,pl,sid,t,g)==(state,plan,'gift',text,grid)
        return expected
    monkeypatch.setattr(route.lapras_bridge,'context',context)
    assert route.field_context(object(),state,plan,'gift') is expected
