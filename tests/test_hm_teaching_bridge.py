from copy import deepcopy
import pytest
from tests.test_hm_teaching import progress,packet,start
from laya_pokemon import hm_teaching_bridge as bridge,campaign_route as route

@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(bridge,'_CONTROLLERS',{})
    monkeypatch.setattr(bridge,'_BINDINGS',{})
    monkeypatch.setattr(bridge,'_COMPLETED',set())

def inputs():
    step={'id':'surf','kind':'interact','map_id':155,'target':[4,5],
          'mechanic':'teach_surf_nidoking','hm_intent':deepcopy(bridge.hm_teaching.SURF_INTENT)}
    state={'frame':40,'location':{'map_id':155,'x':4,'y':5},'progress':progress(),
           'battle_state':{'kind':'none','active':False,'raw':0,'observation_frame':40}}
    return state,{'steps':[step,{'id':'next','kind':'move','map_id':155,'target':[4,6]}]}

def test_ordinary_step_is_out_of_scope_and_initial_wrong_location_does_not_start():
    s,p=inputs();assert not bridge.applies('ordinary',{'kind':'move'})
    s['location']['x']=3
    assert bridge.context(s,p,'surf',packet(window=False),object()) is None
    assert not bridge._CONTROLLERS

def test_exact_new_transaction_starts_once_and_binding_change_cannot_rebuild_it(monkeypatch):
    monkeypatch.setattr('laya_pokemon.campaign_transactions.ui_overworld_ready',lambda t,g:True)
    s,p=inputs();out,key=bridge.context(s,p,'surf',packet(window=False),object())
    assert key=='surf' and out['available_actions']==['start','wait']
    c=bridge._CONTROLLERS['surf'];baseline=deepcopy(c.baseline)
    s['frame']=80;s['battle_state']['observation_frame']=80
    p['steps'][0]['hm_intent']['replace_move']=40
    out,_=bridge.context(s,p,'surf',packet(start()),object())
    assert out['phase']=='campaign_review' and bridge._CONTROLLERS['surf'] is c and c.baseline==baseline

def test_active_owner_cannot_change_even_to_another_valid_hm(monkeypatch):
    monkeypatch.setattr('laya_pokemon.campaign_transactions.ui_overworld_ready',lambda t,g:True)
    s,p=inputs();bridge.context(s,p,'surf',packet(window=False),object())
    p['steps'].append({'id':'strength','kind':'interact','map_id':155,'target':[4,5],
       'mechanic':'teach_strength_snorlax','hm_intent':deepcopy(bridge.hm_teaching.STRENGTH_INTENT)})
    out,_=bridge.context(s,p,'strength',packet(window=False),object())
    assert out['review_reason']=='hm_teaching_owner_changed' and 'strength' not in bridge._CONTROLLERS

@pytest.mark.parametrize('change',['raw','frame','active','kind'])
def test_conflicting_battle_signal_cannot_open_start(change,monkeypatch):
    monkeypatch.setattr('laya_pokemon.campaign_transactions.ui_overworld_ready',lambda t,g:True)
    s,p=inputs();s['battle_state'][{'frame':'observation_frame'}.get(change,change)]={
        'raw':True,'frame':39,'active':True,'kind':'wild'}[change]
    out,_=bridge.context(s,p,'surf',packet(window=False),object())
    assert out['review_reason']=='hm_teaching_battle_signal_unverified'
    assert bridge._CONTROLLERS['surf'].baseline is None

@pytest.mark.parametrize('other',['entry','run','ordinary'])
def test_hm_bridge_never_masks_an_existing_unfinished_transaction(other,monkeypatch):
    s,p=inputs()
    monkeypatch.setattr(route.safari_entry,'_BINDINGS',{'entry':object()} if other=='entry' else {})
    monkeypatch.setattr(route.safari_entry,'_COMPLETED',set())
    monkeypatch.setattr(route.safari_entry,'_RUN_CONTROLLER',object() if other=='run' else None)
    monkeypatch.setattr(route.campaign_transactions,'_BINDINGS',{'old':object()} if other=='ordinary' else {})
    monkeypatch.setattr(route.campaign_transactions,'_COMPLETED',set())
    out,_=route.field_context(None,s,p,'surf')
    assert out['review_reason']=='hm_teaching_other_transaction_active' and not bridge._CONTROLLERS
