"""保護runtime所有權與輸入；門本體另測完整交易。"""
from copy import deepcopy
from types import SimpleNamespace
import importlib
import pytest
from laya_pokemon import silph_card_bridge as bridge


@pytest.fixture
def env(monkeypatch):
    for name, value in (('_CONTROLLERS', {}), ('_BINDINGS', {}), ('_COMPLETED', set())):
        monkeypatch.setattr(bridge, name, value)
    from laya_pokemon import campaign_transactions as tx
    monkeypatch.setattr(tx, 'ui_overworld_ready', lambda text, grid: text.get('ready') is True)
    monkeypatch.setattr(tx, 'verified_blank_transaction_world', lambda text, grid: text.get('ready') is True)
    monkeypatch.setattr(bridge.silph_card_door, 'read_silph_card_door', lambda *a, **k: {'sentinel': 'source'})
    class Controller:
        def __init__(self, intent):
            self.intent = deepcopy(intent); self.baseline = {'kept':True}
            self.final_ack = True; self.error = None; self.calls = 19; self.done = False
        def context(self, text, progress, **kwargs):
            self.args = kwargs
            return {'phase':'silph_card_door','available_actions':['wait'],
                    'objective':'Wait.','silph_card_door_complete':self.done}
    monkeypatch.setattr(bridge.silph_card_door, 'SilphCardDoorController', Controller)
    intent = deepcopy(bridge.silph_card_door.THREE_F_INTENT)
    plan = {'steps':[dict(id='door', kind='interact', map_id=208,target=[18,8],
                         mechanic='silph_card_door', card_door_intent=intent),
                      dict(id='after',kind='move',map_id=208,target=[18,9])]}
    state = dict(frame=50,location=dict(map_id=208,x=18,y=8),progress={},
                 battle_state=dict(kind='none',raw=0,active=False,observation_frame=50))
    return SimpleNamespace(plan=plan,state=state,emulator=SimpleNamespace(memory={0xC109:8},frame_count=50))


def call(env, step='door', ready=True):
    return bridge.context(env.emulator,env.state,env.plan,step,{'ready':ready},{})


def test_same_frame_reader_and_exact_facing_feed_one_original_controller(env):
    call(env); c=bridge._CONTROLLERS['door']; base=c.baseline
    call(env)
    assert bridge._CONTROLLERS['door'] is c and c.baseline is base and c.final_ack
    assert c.calls == 19
    assert c.args['door_signal']=={'sentinel':'source'}
    assert c.args['location']==dict(map_id=208,x=18,y=8,facing='left',facing_raw=8)
    assert c.args['frame']==50


def test_unbound_movement_passes_but_bound_location_change_reviews(env):
    env.state['location']['x']=19; assert call(env) is None
    env.state['location']['x']=18;call(env)
    env.state['location']['x']=19
    assert call(env)[0]['review_reason']=='silph_card_bridge_location_changed'


def test_wrong_initial_facing_and_open_ui_never_create_or_turn(env):
    env.emulator.memory[0xC109]=12
    assert call(env,ready=False)[0]['review_reason']=='silph_card_bridge_initial_closed_world_required'
    assert call(env)[0]['review_reason']=='silph_card_bridge_initial_facing_required'
    assert not bridge._BINDINGS and not bridge._CONTROLLERS


@pytest.mark.parametrize('change',[('observation_frame',49),('observation_frame',False),
                                  ('raw',False),('raw',1),('active',True),('kind','trainer')])
def test_invalid_battle_never_binds(env,change):
    env.state['battle_state'][change[0]]=change[1]
    assert call(env)[0]['review_reason']=='silph_card_bridge_battle_signal_unverified'
    assert not bridge._CONTROLLERS


@pytest.mark.parametrize('key,value',[('map_id',True),('target',[18,True]),('target',[19,8]),('kind','move')])
def test_bad_route_contract_never_binds(env,key,value):
    env.plan['steps'][0][key]=value
    assert call(env)[0]['review_reason']=='silph_card_bridge_explicit_intent_unverified'


@pytest.mark.parametrize('value',[True,9,None])
def test_wrong_facing_raw_never_binds(env,value):
    env.emulator.memory[0xC109]=value
    assert call(env)[0]['review_reason']=='silph_card_bridge_facing_or_frame_unverified'
    assert not bridge._CONTROLLERS


def test_frame_advanced_during_facing_read_never_binds(env):
    env.emulator.frame_count=51
    assert call(env)[0]['review_reason']=='silph_card_bridge_facing_or_frame_unverified'


@pytest.mark.parametrize('second',[8.0,True,None,12])
def test_second_facing_read_requires_real_int_and_same_value(env,second):
    class Memory:
        values=iter([8,second])
        def __getitem__(self,address):
            assert address==0xC109
            return next(self.values)
    env.emulator.memory=Memory()
    assert call(env)[0]['review_reason']=='silph_card_bridge_facing_or_frame_unverified'
    assert not bridge._BINDINGS and not bridge._CONTROLLERS


@pytest.mark.parametrize('second',[50.0,True,None,51])
def test_second_frame_read_requires_real_int_and_same_frame(env,second):
    class Emulator:
        memory={0xC109:8}
        values=iter([50,second])
        @property
        def frame_count(self):return next(self.values)
    env.emulator=Emulator()
    assert call(env)[0]['review_reason']=='silph_card_bridge_facing_or_frame_unverified'
    assert not bridge._BINDINGS and not bridge._CONTROLLERS


def test_foreign_owner_or_different_intent_cannot_rebuild_a_transaction(env):
    call(env);c=bridge._CONTROLLERS['door']
    assert call(env,step='after')[0]['review_reason']=='silph_card_bridge_owner_changed'
    env.plan['steps'][0].update(map_id=235,target=[6,14],card_door_intent=deepcopy(bridge.silph_card_door.ELEVEN_F_INTENT))
    assert call(env)[0]['review_reason']=='silph_card_bridge_intent_changed'
    assert bridge._CONTROLLERS['door'] is c


def test_only_controller_closed_receipt_advances_route(env):
    assert call(env)[1]=='door'
    bridge._CONTROLLERS['door'].done=True
    assert call(env)[1]=='after' and 'door' in bridge._COMPLETED


def test_active_budget_and_baseline_survive_bridge_reload(env,monkeypatch):
    call(env); controllers=bridge._CONTROLLERS; bindings=bridge._BINDINGS
    c=controllers['door'];base=c.baseline;c.error='retained';c.calls=203
    importlib.reload(bridge)
    assert bridge._CONTROLLERS is controllers and bridge._BINDINGS is bindings
    assert bridge._CONTROLLERS['door'] is c and c.error=='retained' and c.calls==203 and c.baseline is base


def test_runtime_cannot_mask_active_capture_transaction(env,monkeypatch):
    from laya_pokemon import campaign_route as route
    monkeypatch.setattr(route.silph_card_bridge,'applies',lambda *a:True)
    monkeypatch.setattr(route.capture_transaction,'_SESSIONS',{'catch':{'done':False}})
    result,_=route.field_context(env.emulator,env.state,env.plan,'door')
    assert result['review_reason']=='silph_card_bridge_other_transaction_active'
