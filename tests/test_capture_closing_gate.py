from copy import deepcopy
import pytest
from laya_pokemon import capture_closing_gate as gate
from laya_pokemon.campaign_safety import attrition_context
from tests.test_capture_completion import Session,last_throw,battle_text,LOCATION,NONE


@pytest.fixture(autouse=True)
def clean():
    gate.tx._SESSIONS.clear();yield;gate.tx._SESSIONS.clear()


def setup():
    b=last_throw();b['progress']['party'][0]['hp']=56;b['battle_text']=battle_text(b['progress'])
    s=Session(b);s.decline();s.finalize_data()
    step={'id':'capture','kind':'interact','map_id':23,'target':[10,61],
          'mechanic':gate.tx.MECHANIC,'capture_intent':deepcopy(gate.tx.snorlax_capture.INTENT)}
    plan={'mode':'league_campaign','steps':[step]}
    gate.tx._SESSIONS['capture']={'done':False,'completion':s.c,'switch':None,
      'binding':(23,(10,61),tuple(sorted(step['capture_intent'].items())))}
    state={'phase':'unclassified','progress':s.p,'location':deepcopy(LOCATION),'battle_state':deepcopy(NONE)}
    return s,state,plan


def test_low_lead_can_only_finish_real_no_declined_transaction_then_center_guard_returns():
    s,state,plan=setup()
    assert gate.eligible(state,plan,'capture') and attrition_context(state,plan,'capture') is None
    first=s.call(world=True);assert first['available_actions']==['wait'] and not first.get('capture_complete')
    last=s.call(world=True);assert last['available_actions']==['wait'] and last['capture_complete']
    assert not gate.eligible(state,plan,'capture')
    assert attrition_context(state,plan,'capture')['review_reason']=='party_attrition_requires_center'


@pytest.mark.parametrize('change',['faint','unverified','wrong_location','wild','wrong_step','done','switch',
 'error','not_no','not_closing','binding','intent','second_owner'])
def test_unknown_or_other_owner_cannot_bypass_attrition(change):
    s,state,plan=setup();record=gate.tx._SESSIONS['capture']
    if change=='faint':state['progress']['party'][2]['hp']=0
    elif change=='unverified':state['progress']['party_read_valid']=False
    elif change=='wrong_location':state['location']['x']=11
    elif change=='wild':state['battle_state'].update(raw=1,kind='wild',active=True)
    elif change=='wrong_step':plan['steps'][0]['mechanic']='other'
    elif change=='done':record['done']=True
    elif change=='switch':record['switch']=object()
    elif change=='error':s.c.error='unknown'
    elif change=='not_no':s.c.no_confirmed=False
    elif change=='not_closing':s.c.stage='nickname_menu'
    elif change=='binding':record['binding']=None
    elif change=='intent':plan['steps'][0]['capture_intent']['no_run']=1
    else:gate.tx._SESSIONS['other']={'done':False}
    assert not gate.eligible(state,plan,'capture')


@pytest.mark.parametrize('actions',[['a','wait'],['down','wait'],None,[]])
def test_closing_gate_rejects_every_non_wait_result(actions):
    r,step=gate.restrict(({'available_actions':actions},'capture'))
    assert r['phase']=='campaign_review' and r['available_actions']==['wait']


def test_closing_gate_does_not_erase_verified_completion_receipt():
    r={'available_actions':['wait'],'capture_complete':True,'field_move_complete':True}
    assert gate.restrict((r,'after'))==(r,'after')
