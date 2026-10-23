"""來源座標劇情只等原生腳本，不能用到站冒充戰勝。"""
from copy import deepcopy
import pytest
from laya_pokemon import campaign_route as route

STEP={'id':'test-marowak-wait','kind':'move','map_id':147,'target':[10,16],
      'event':'beat_ghost_marowak','await_script_event':True}
STATE={'location':{'map_id':147,'x':10,'y':16},'phase':'unclassified',
       'battle_state':{'kind':'none','active':False},
       'progress':{'party_read_valid':True,'party':[],
                   'story_event_bits':{'beat_ghost_marowak':False},
                   'inventory':[{'item':72,'quantity':1}]}}

@pytest.fixture(autouse=True)
def clear_waits():
    route._SCRIPT_WAITS.clear()
    yield
    route._SCRIPT_WAITS.clear()

def test_arrival_waits_without_any_button_or_claiming_victory():
    state=deepcopy(STATE)
    context,step=route.waypoint(None,state,{'steps':[STEP]},STEP['id'],[])
    assert step==STEP['id'] and context['available_actions']==['wait']
    assert context['source_coordinate_script_wait'] is True and state==STATE

def test_verified_event_advances_but_unknown_does_not():
    state=deepcopy(STATE);state['progress']['story_event_bits']['beat_ghost_marowak']=True
    context,step=route.waypoint(None,state,{'steps':[STEP]},STEP['id'],[])
    assert step=='complete' and context['review_reason']=='route_extension_required'
    state['progress']['story_event_bits']['beat_ghost_marowak']=None
    assert route.coordinate_script_wait(state,STEP)['review_reason']=='coordinate_script_prerequisites_unverified'

@pytest.mark.parametrize('change',[
    {'kind':'interact'},{'map_id':146},{'target':[9,16]},
    {'event':'got_poke_flute'},{'await_script_event':1},
])
def test_wrong_explicit_intent_never_sends_a(change):
    context=route.coordinate_script_wait(STATE,{**STEP,**change})
    assert context['phase']=='campaign_review' and context['available_actions']==['wait']

@pytest.mark.parametrize('change',[
    lambda s:s['progress'].update(party_read_valid=False),
    lambda s:s['progress'].update(inventory=[]),
    lambda s:s['progress'].update(inventory=[{'item':72,'quantity':True}]),
    lambda s:s['battle_state'].update(active=None),
    lambda s:s['battle_state'].update(kind='wild',active=True),
])
def test_unknown_prerequisite_only_reviews(change):
    state=deepcopy(STATE);change(state)
    context=route.coordinate_script_wait(state,STEP)
    assert context['phase']=='campaign_review' and context['available_actions']==['wait']

def test_call_and_time_budgets_are_bounded(monkeypatch):
    monkeypatch.setattr(route.time,'monotonic',lambda:10.)
    for _ in range(25):assert route.coordinate_script_wait(STATE,STEP)['phase']=='overworld'
    assert route.coordinate_script_wait(STATE,STEP)['review_reason']=='coordinate_script_wait_exhausted'
    route._SCRIPT_WAITS.clear();route.coordinate_script_wait(STATE,STEP)
    monkeypatch.setattr(route.time,'monotonic',lambda:70.001)
    assert route.coordinate_script_wait(STATE,STEP)['review_reason']=='coordinate_script_wait_exhausted'
