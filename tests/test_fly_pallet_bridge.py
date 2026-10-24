"""飛行不能以目的地map前置跳判；必須保留原controller及真previous。"""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from laya_pokemon import fly_pallet_bridge as bridge
from laya_pokemon import campaign_route as route


@pytest.fixture
def env(monkeypatch):
    for name,value in (('_CONTROLLERS',{}),('_BINDINGS',{}),('_COMPLETED',set())):
        monkeypatch.setattr(bridge,name,value)
    from laya_pokemon import campaign_transactions as tx
    monkeypatch.setattr(tx,'verified_blank_transaction_world',lambda t,g:t.get('ready') is True)
    monkeypatch.setattr(tx,'ui_overworld_ready',lambda t,g:t.get('ready') is True)
    class Controller:
        def __init__(self,intent):self.intent=deepcopy(intent);self.baseline={'original':True};self.done=False;self.args=None
        def context(self,text,progress,**kwargs):
            self.args=kwargs
            return dict(phase='fly_pallet',objective='Wait.',available_actions=['wait'],fly_pallet_complete=self.done)
    monkeypatch.setattr(bridge.fly_pallet,'FlyPalletController',Controller)
    signal=dict(read_valid=True)
    monkeypatch.setattr(bridge.fly_pallet,'read_fly_observation',lambda *a:deepcopy(signal))
    step=dict(id='fly-pallet',kind='interact',mechanic='fly_pallet',map_id=27,target=[7,6],
              fly_intent=deepcopy(bridge.fly_pallet.FLY_PALLET_INTENT))
    return SimpleNamespace(plan=dict(steps=[step]),step=step,emulator=SimpleNamespace(),signal=signal,
        state=dict(frame=10,location=dict(map_id=27,x=7,y=6),progress={},battle_state=dict(kind='none')))


def call(e,step='fly-pallet',ready=True,previous=('a','wait')):
    return bridge.context(e.emulator,e.state,e.plan,step,dict(ready=ready),{},previous)


def test_controller_is_retained_through_source_and_destination_until_it_verifies_closed_landing(env):
    call(env,previous=('a','wait'))
    c=bridge._CONTROLLERS['fly-pallet'];base=c.baseline
    assert c.args['previous']==('a','wait') and c.args['frame']==10
    env.state.update(frame=50,location=dict(map_id=0,x=5,y=6))
    assert call(env,ready=False)[1]=='fly-pallet'
    assert bridge._CONTROLLERS['fly-pallet'] is c and c.baseline is base
    assert not bridge._COMPLETED
    c.done=True;context,next_id=call(env)
    assert next_id=='complete' and context['field_move_complete'] and context['field_move_kind']=='fly-pallet'


@pytest.mark.parametrize('key,value',[('next_map',0),('terminal',True),('event','got_hm02'),('item',197),
                                    ('badge',32),('await_script_event',True),('kind','move'),
                                    ('map_id',0),('target',[7,5])])
def test_generic_completion_or_changed_explicit_source_is_rejected_before_binding(env,key,value):
    env.step[key]=value
    assert call(env)[0]['review_reason']=='fly_pallet_explicit_intent_unverified'
    assert not bridge._CONTROLLERS


def test_no_generic_menu_or_unknown_signal_can_bind_initial_flight(env):
    assert call(env,ready=False)[0]['review_reason']=='fly_pallet_initial_closed_world_required'
    env.signal['read_valid']=False
    assert call(env)[0]['review_reason']=='fly_pallet_initial_signal_unverified'
    assert not bridge._BINDINGS


def test_active_flight_cannot_be_abandoned_for_other_step(env):
    call(env)
    assert call(env,step='other')[0]['review_reason']=='fly_pallet_owner_changed'
    env.step.pop('mechanic')
    assert call(env)[0]['review_reason']=='fly_pallet_intent_changed'


def test_runtime_calls_flight_with_real_previous_before_any_generic_party_menu(env,monkeypatch):
    monkeypatch.setattr(route,'fly_pallet_bridge',bridge)
    for mod in (route.safari_entry,route.hm_teaching_bridge,route.vending_bridge,route.saffron_guard_bridge,
                route.silph_card_bridge,route.lapras_bridge,route.player_pc_bridge,route.campaign_transactions):
        monkeypatch.setattr(mod,'_BINDINGS',{});monkeypatch.setattr(mod,'_COMPLETED',set())
    monkeypatch.setattr(route.safari_entry,'_RUN_CONTROLLER',None)
    monkeypatch.setattr(route.capture_transaction,'_SESSIONS',{})
    from laya_pokemon import observation
    monkeypatch.setattr(observation,'read_visible_text',lambda p:dict(ready=True))
    monkeypatch.setattr(route,'read_world_grid',lambda *a:{})
    assert route.field_context(env.emulator,env.state,env.plan,'fly-pallet') is None
    context,_=route.switch_context(env.emulator,env.state,env.plan,'fly-pallet',['down','a'])
    assert context['phase']=='fly_pallet' and bridge._CONTROLLERS['fly-pallet'].args['previous']==['down','a']
    monkeypatch.setattr(route.player_pc_bridge,'_BINDINGS',{'pending-pc':('unchanged',)})
    context,_=route.switch_context(env.emulator,env.state,env.plan,'fly-pallet',['a'])
    assert context['review_reason']=='fly_pallet_other_transaction_active'
