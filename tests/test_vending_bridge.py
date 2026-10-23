"""單瓶購買bridge的所有權與同幀保護；純UI交易另有獨立測試。"""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from laya_pokemon import vending_bridge as bridge


@pytest.fixture
def env(monkeypatch):
    for name,value in (('_CONTROLLERS',{}),('_BINDINGS',{}),('_COMPLETED',set())):
        monkeypatch.setattr(bridge,name,value)
    from laya_pokemon import campaign_transactions as tx
    monkeypatch.setattr(tx,'ui_overworld_ready',lambda text,grid:text.get('ready') is True)
    monkeypatch.setattr(tx,'verified_blank_transaction_world',lambda text,grid:text.get('ready') is True)
    class Controller:
        def __init__(self,intent):
            self.intent=deepcopy(intent);self.error=None;self.started=3.;self.calls=2;self.waits=1
            self.baseline={'keep':'original'};self.purchase_issued=True;self.args=None;self.done=False
        def context(self,text,progress,**kwargs):
            self.args=kwargs
            return {'phase':'vending_water','available_actions':['wait'],
                    'vending_water_complete':self.done,'objective':'Wait.'}
    monkeypatch.setattr(bridge.vending_water,'VendingWaterController',Controller)
    p={'steps':[{'id':'water','kind':'interact','map_id':126,'target':[11,2],
                 'mechanic':'buy_fresh_water','water_intent':deepcopy(bridge.vending_water.INTENT)},
                {'id':'after','kind':'move','map_id':126,'target':[11,3]}]}
    state={'frame':5,'location':{'map_id':126,'x':11,'y':2},'progress':{},
           'battle_state':{'kind':'none','active':False,'raw':0,'observation_frame':5}}
    return SimpleNamespace(plan=p,state=state,emulator=SimpleNamespace(memory={0xC109:4}))


def call(env,step='water',ready=True):
    return bridge.context(env.emulator,env.state,env.plan,step,{'ready':ready},{})


def test_exact_stance_passes_source_facing_and_same_frame_to_original_controller(env):
    call(env);controller=bridge._CONTROLLERS['water'];original=controller.baseline
    env.plan['steps'][0]['reviewed_vending_revision']=4
    env.plan['steps'][0]['reviewed_vending_error']='calibrated-error';controller.error='calibrated-error'
    call(env)
    assert bridge._CONTROLLERS['water'] is controller and controller.baseline is original
    assert controller.purchase_issued and controller.error is None and controller.calls==controller.waits==0
    assert controller.args['frame']==5
    assert controller.args['location']==dict(map_id=126,x=11,y=2,facing='up',facing_raw=4)


def test_unbound_other_position_does_not_intercept_movement_but_bound_move_reviews(env):
    env.state['location']['x']=10;assert call(env) is None
    env.state['location']['x']=11;call(env)
    env.state['location']['x']=10;assert call(env)[0]['review_reason']=='vending_location_changed'


def test_bridge_never_turns_before_the_controller_has_a_valid_baseline(env):
    env.emulator.memory[0xC109]=12
    assert call(env,ready=False)[0]['review_reason']=='vending_initial_closed_world_required'
    for _ in range(3):assert call(env)[0]['review_reason']=='vending_initial_up_facing_required'
    assert not bridge._CONTROLLERS
    assert not bridge._BINDINGS


@pytest.mark.parametrize('change',[('raw',False),('active',True),('kind','wild'),('observation_frame',4)])
def test_conflicting_battle_or_observation_frame_never_creates_controller(env,change):
    env.state['battle_state'][change[0]]=change[1]
    assert call(env)[0]['review_reason']=='vending_battle_signal_unverified'
    assert not bridge._CONTROLLERS


@pytest.mark.parametrize('field,value',[('map_id',125),('target',[12,2]),('kind','move')])
def test_different_explicit_stance_or_operation_is_rejected(env,field,value):
    env.plan['steps'][0][field]=value
    assert call(env)[0]['review_reason']=='vending_explicit_intent_unverified'


def test_intent_changed_after_binding_or_owner_changed_cannot_escape_transaction(env):
    call(env)
    assert call(env,step='after')[0]['review_reason']=='vending_owner_changed'
    env.plan['steps'][0]['water_intent']['quantity']=2
    assert call(env)[0]['review_reason']=='vending_explicit_intent_unverified'


def test_matching_review_only_clears_error_without_rebuying_or_rebuilding_baseline(env):
    call(env);c=bridge._CONTROLLERS['water'];base=c.baseline;c.error='old'
    env.plan['steps'][0].update(reviewed_vending_revision=1,reviewed_vending_error='wrong')
    call(env);assert c.error=='old' and c.baseline is base
    env.plan['steps'][0]['reviewed_vending_error']='old';call(env)
    assert c.error is None and c.baseline is base and c.purchase_issued


def test_only_controller_closed_receipt_advances_exact_next_step(env):
    assert call(env)[1]=='water'
    bridge._CONTROLLERS['water'].done=True
    result,next_id=call(env)
    assert result['vending_water_complete'] and next_id=='after' and 'water' in bridge._COMPLETED


def test_runtime_cannot_mask_other_active_transactions(env,monkeypatch):
    from laya_pokemon import campaign_route as route
    monkeypatch.setattr(route.vending_bridge,'applies',lambda *a:True)
    monkeypatch.setattr(route.safari_entry,'_BINDINGS',{})
    monkeypatch.setattr(route.safari_entry,'_RUN_CONTROLLER',None)
    monkeypatch.setattr(route.hm_teaching_bridge,'_BINDINGS',{})
    monkeypatch.setattr(route.campaign_transactions,'_BINDINGS',{})
    monkeypatch.setattr(route.capture_transaction,'_SESSIONS',{'capture':{'done':False}})
    result,_=route.field_context(env.emulator,env.state,env.plan,'water')
    assert result['review_reason']=='vending_other_transaction_active'
