"""PC橋接的owner／精確意圖及真previous整合，交易本體另測。"""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from laya_pokemon import player_pc_bridge as bridge
from laya_pokemon import campaign_route as route


@pytest.fixture
def env(monkeypatch):
    for key,value in (('_CONTROLLERS',{}),('_BINDINGS',{}),('_COMPLETED',set())):
        monkeypatch.setattr(bridge,key,value)
    from laya_pokemon import campaign_transactions as tx
    monkeypatch.setattr(tx,'ui_overworld_ready',lambda t,g:t.get('ready') is True)
    monkeypatch.setattr(tx,'verified_blank_transaction_world',lambda t,g:t.get('ready') is True)
    class Controller:
        def __init__(self,intent):
            self.intent=deepcopy(intent);self.baseline={'original':True};self.done=False;self.args=None
        def context(self,text,progress,**kwargs):
            self.args=kwargs
            return dict(phase='player_pc_deposit',objective='Wait.',available_actions=['wait'],
                        pc_deposit_complete=self.done)
    monkeypatch.setattr(bridge.player_pc_deposit,'PlayerPCDepositController',Controller)
    signal=dict(read_valid=True,read_error=None,facing_raw=4,facing='up',count=1,
                items=[dict(item=20,quantity=1)],observation_frame=10)
    monkeypatch.setattr(bridge.player_pc_deposit,'read_player_pc',lambda *a,**kw:deepcopy(signal))
    step=dict(id='pc-tm34',kind='interact',mechanic='player_pc_deposit',map_id=182,
              target=[13,4],face='up',pc_intent={**bridge.player_pc_deposit.INTENT_BASE,'item':234})
    state=dict(frame=10,location=dict(map_id=182,x=13,y=4),progress={},
               battle_state=dict(kind='none',active=False,raw=0,observation_frame=10))
    return SimpleNamespace(step=step,plan=dict(steps=[step,dict(id='after',kind='move',map_id=182,target=[12,4])]),
                           state=state,signal=signal,emulator=SimpleNamespace())


def call(e,step='pc-tm34',ready=True,previous=('up',)):
    return bridge.context(e.emulator,e.state,e.plan,step,dict(ready=ready),{},previous)


def test_only_exact_pc_stance_and_true_previous_are_forwarded(env):
    call(env,previous=('right','up'))
    c=bridge._CONTROLLERS['pc-tm34'];original=c.baseline
    assert c.args['frame']==10 and c.args['previous']==('right','up')
    assert c.args['location']==dict(map_id=182,x=13,y=4)
    call(env);assert bridge._CONTROLLERS['pc-tm34'] is c and c.baseline is original


@pytest.mark.parametrize('field,value',[('map_id',True),('map_id',181),('target',[13,3]),('kind','move'),('face','down'),
                                      ('next_map',182),('terminal',True),('event','got_hm02'),('item',234),
                                      ('badge',64),('await_script_event',True)])
def test_generic_completion_keys_or_wrong_stance_cannot_bypass_deposit(env,field,value):
    env.step[field]=value
    assert call(env)[0]['review_reason']=='player_pc_explicit_intent_unverified'
    assert not bridge._CONTROLLERS


@pytest.mark.parametrize('item',[True,1,196,197,246,None])
def test_only_two_explicit_nonkey_tm_intents_are_allowed(env,item):
    env.step['pc_intent']['item']=item
    assert call(env)[0]['review_reason']=='player_pc_explicit_intent_unverified'
    assert not bridge._BINDINGS


def test_unbound_wrong_location_defers_navigation_bound_wrong_location_stops(env):
    env.state['location']['y']=5;assert call(env) is None
    env.state['location']['y']=4;call(env)
    env.state['location']['y']=5
    assert call(env)[0]['review_reason']=='player_pc_location_changed'


def test_owner_cannot_be_changed_or_satisfied_by_generic_target(env):
    call(env)
    assert call(env,step='after')[0]['review_reason']=='player_pc_owner_changed'
    env.step['pc_intent']['item']=221
    assert call(env)[0]['review_reason']=='player_pc_intent_changed'


def test_initial_menu_or_unknown_facing_never_binds_controller(env):
    assert call(env,ready=False)[0]['review_reason']=='player_pc_initial_closed_world_required'
    env.signal['facing_raw']=12
    assert call(env)[0]['review_reason']=='player_pc_initial_read_or_facing_unverified'
    assert not bridge._CONTROLLERS


def test_completion_requires_controller_receipt_and_produces_existing_capture_marker(env):
    assert call(env)[1]=='pc-tm34'
    bridge._CONTROLLERS['pc-tm34'].done=True
    context,next_id=call(env)
    assert next_id=='after' and context['pc_deposit_complete']
    assert context['field_move_complete'] and context['field_move_kind']=='player-pc-deposit'
    assert 'pc-tm34' in bridge._COMPLETED


def test_runtime_defer_then_real_previous_dispatch_precedes_generic_pc_menu(env,monkeypatch):
    from laya_pokemon import campaign_route as route
    monkeypatch.setattr(route,'player_pc_bridge',bridge)
    for mod in (route.safari_entry,route.hm_teaching_bridge,route.vending_bridge,route.saffron_guard_bridge,
                route.silph_card_bridge,route.lapras_bridge,route.campaign_transactions):
        monkeypatch.setattr(mod,'_BINDINGS',{});monkeypatch.setattr(mod,'_COMPLETED',set())
    monkeypatch.setattr(route.safari_entry,'_RUN_CONTROLLER',None)
    monkeypatch.setattr(route.capture_transaction,'_SESSIONS',{})
    from laya_pokemon import observation
    monkeypatch.setattr(observation,'read_visible_text',lambda p:dict(ready=True))
    monkeypatch.setattr(route,'read_world_grid',lambda *a:{})
    assert route.field_context(env.emulator,env.state,env.plan,'pc-tm34') is None
    result,_=route.switch_context(env.emulator,env.state,env.plan,'pc-tm34',['down','up'])
    assert result['phase']=='player_pc_deposit'
    assert bridge._CONTROLLERS['pc-tm34'].args['previous']==['down','up']
    monkeypatch.setattr(route.capture_transaction,'_SESSIONS',{'capture':{'done':False}})
    result,_=route.switch_context(env.emulator,env.state,env.plan,'pc-tm34',['a'])
    assert result['review_reason']=='player_pc_other_transaction_active'


def reviewed_redraw(env,monkeypatch):
    call(env);c=bridge._CONTROLLERS['pc-tm34']
    c.error='player_pc_deposit_bag_viewport_or_quantity_unverified'
    c.stage='after_receipt';c.transferred=True;c.receipt_seen=True;c.pending=None
    c.last_frame=1427457;c.last_now=10.;c.started=5.;c.calls=19;c.waits=7;c.actions=12
    c.baseline=dict(party=[],money=55372,bag_after=[dict(item=221,quantity=1)],
                    pc_after=[dict(item=20,quantity=1),dict(item=234,quantity=1)])
    env.state.update(frame=1427457,progress=dict(party=[],money=55372,inventory=deepcopy(c.baseline['bag_after'])))
    env.signal['items']=deepcopy(c.baseline['pc_after'])
    env.step['reviewed_pc_ui_revision']=1
    monkeypatch.setattr(bridge.time,'monotonic',lambda:100.)
    return c


def test_named_redraw_review_preserves_transaction_and_used_budget_once(env,monkeypatch):
    c=reviewed_redraw(env,monkeypatch);base=c.baseline
    call(env,ready=False)
    assert c.error is None and c.baseline is base and c.started==95.
    assert (c.calls,c.waits,c.actions)==(19,7,12)
    assert c.transferred and c.receipt_seen
    call(env,ready=False)
    assert c.started==95. and len(c.review_pause_adjustments)==1


@pytest.mark.parametrize('field,value',[('error','other_error'),('stage','receipt'),('transferred',False),
                                      ('receipt_seen',False),('last_frame',1427417),('pending',{'action':'a'})])
def test_named_redraw_review_cannot_clear_other_failures_or_stages(env,monkeypatch,field,value):
    c=reviewed_redraw(env,monkeypatch);setattr(c,field,value)
    assert call(env,ready=False)[0]['review_reason']=='player_pc_named_redraw_review_unverified'
    assert c.started==5.


def test_second_named_review_requires_first_review_and_exact_later_frame(env,monkeypatch):
    c=reviewed_redraw(env,monkeypatch)
    env.step['reviewed_pc_ui_revision']=2
    env.state['frame']=c.last_frame=1427537
    assert call(env,ready=False)[0]['review_reason']=='player_pc_named_redraw_review_unverified'
    assert c.started==5.
    c._reviewed_pc_ui_revision=1
    call(env,ready=False)
    assert c.started==95. and c._reviewed_pc_ui_revision==2
    call(env,ready=False)
    assert c.started==95. and len(c.review_pause_adjustments)==1


def test_third_named_review_only_allows_real_exit_player_error_after_second_review(env,monkeypatch):
    c=reviewed_redraw(env,monkeypatch)
    env.step['reviewed_pc_ui_revision']=3;env.state['frame']=c.last_frame=1427617
    c._reviewed_pc_ui_revision=2
    assert call(env,ready=False)[0]['review_reason']=='player_pc_named_redraw_review_unverified'
    c.stage='exit_player';c.error='player_pc_deposit_player_menu_or_deposit_label_unverified'
    call(env,ready=False)
    assert c.error is None and c.started==95. and c._reviewed_pc_ui_revision==3
