"""正式route入口互斥與真previous轉交；交易內頁另由各來源測試驗證。"""
from types import ModuleType
from tm24_parent_fixture import seed_tm24_peer
import pytest
from laya_pokemon import campaign_route as r,observation

def forbidden(*args,**kwargs):raise AssertionError('互斥失敗前不得讀UI或呼叫交易')

@pytest.fixture
def env(monkeypatch):
    peers={name:m for name,m in vars(r).items() if isinstance(m,ModuleType) and hasattr(m,'_BINDINGS')}
    for m in peers.values():
        for key,value in (('_BINDINGS',{}),('_COMPLETED',set()),('_CONTROLLERS',{}),('_ERRORS',{}),('_OWNERS',{})):
            if hasattr(m,key):monkeypatch.setattr(m,key,value)
        if hasattr(m,'_REGISTRY_ERROR'):monkeypatch.setattr(m,'_REGISTRY_ERROR',None)
    monkeypatch.setattr(r.safari_entry,'_RUN_CONTROLLER',None)
    monkeypatch.setattr(r.capture_transaction,'_SESSIONS',{})
    monkeypatch.setattr(r.league_native_wait,'_WAITS',{})
    return peers

def state():return dict(frame=88,location=dict(map_id=34,x=10,y=104),progress={'actual':'untouched'})

def plan(bridge):
    mechanic='route23_surf' if bridge is r.route23_bridge else bridge.MECHANIC
    return dict(training_job='bounded-job',steps=[dict(id='field',kind='interact',mechanic=mechanic)])

@pytest.mark.parametrize('bridge',r._LEAGUE_FIELDS)
def test_each_formal_field_receives_same_state_plan_and_true_previous(env,monkeypatch,bridge):
    s=state();p=plan(bridge);pb=object();text=object();grid=object();previous=['left','wait'];calls=[]
    monkeypatch.setattr(observation,'read_visible_text',lambda obj:text if obj is pb else forbidden())
    monkeypatch.setattr(r,'read_world_grid',lambda obj,loc:grid if obj is pb and loc is s['location'] else forbidden())
    result=({'phase':'battle_menu','objective':'Fight.','available_actions':['a','b'],'kept_battle':True},'field')
    def delegate(*args,**kwargs):calls.append((args,kwargs));return result
    monkeypatch.setattr(bridge,'context',delegate)
    assert r.field_context(pb,s,p,'field') is None
    assert r.switch_context(pb,s,p,'field',previous) is result
    expected_kw={'peer_owners':()} if bridge is r.tm24_teaching_bridge else {}
    assert calls==[((pb,s,p,'field',text,grid,previous),expected_kw)]
    assert s['progress']=={'actual':'untouched'}

@pytest.mark.parametrize('bridge',r._LEAGUE_FIELDS)
def test_active_field_blocks_unrelated_purchase_before_any_read(env,monkeypatch,bridge):
    if bridge is r.tm24_teaching_bridge:
        seed_tm24_peer(bridge,'original')
    elif bridge is r.overworld_hyper_bridge:
        bridge._BINDINGS['original']={'step':{},'training_job':'job','job_canonical':'"job"','error':None}
        bridge._CONTROLLERS['original']=object();bridge._OWNERS['original']=object()
    else:bridge._BINDINGS['original']=('job','fixed-intent')
    before=dict(bridge._BINDINGS)
    monkeypatch.setattr(observation,'read_visible_text',forbidden)
    monkeypatch.setattr(r,'read_world_grid',forbidden)
    p=dict(steps=[dict(id='purchase',mechanic='cinnabar_purchase')])
    out,owner=r.switch_context(object(),state(),p,'purchase',['a'])
    assert owner=='purchase' and out['review_reason']=='league_field_owner_changed'
    assert bridge._BINDINGS==before

@pytest.mark.parametrize('name',('battle_medicine_bridge','trainer_medicine_ui_bridge','campaign_transactions','lapras_bridge','fly_viridian_bridge','player_pc_bridge'))
def test_legacy_owner_blocks_new_field_bidirectionally_before_ui(env,monkeypatch,name):
    env[name]._BINDINGS['original']=('retained',)
    monkeypatch.setattr(observation,'read_visible_text',forbidden)
    monkeypatch.setattr(r,'read_world_grid',forbidden)
    p=plan(r.route23_bridge)
    out,_=r.switch_context(object(),state(),p,'field',['a'])
    assert out['review_reason']=='league_field_other_transaction_active'

@pytest.mark.parametrize('fault',('capture','safari','native','multiple','orphan','registry'))
def test_nontransaction_owners_and_orphans_fail_before_ui(env,monkeypatch,fault):
    if fault=='capture':r.capture_transaction._SESSIONS['capture']={'done':False}
    if fault=='safari':monkeypatch.setattr(r.safari_entry,'_RUN_CONTROLLER',object())
    if fault=='native':r.league_native_wait._WAITS['native']=type('Wait',(),{'waiting':True})()
    if fault=='multiple':
        r.route23_bridge._BINDINGS['field']=('owner',)
        r.victory_strength_bridge._BINDINGS['field']=('owner',)
    if fault=='orphan':r.victory_strength_bridge._CONTROLLERS['old']=object()
    if fault=='registry':monkeypatch.setattr(r.route23_bridge,'_BINDINGS',None)
    monkeypatch.setattr(observation,'read_visible_text',forbidden)
    monkeypatch.setattr(r,'read_world_grid',forbidden)
    out,_=r.switch_context(object(),state(),plan(r.route23_bridge),'field',[])
    assert out['phase']=='campaign_review' and out['available_actions']==['wait']

def test_unbound_before_fixed_location_can_return_to_ordinary_navigation(env,monkeypatch):
    p=plan(r.route23_bridge)
    monkeypatch.setattr(observation,'read_visible_text',lambda _:object())
    monkeypatch.setattr(r,'read_world_grid',lambda *_:object())
    monkeypatch.setattr(r.route23_bridge,'context',lambda *_:None)
    assert r._league_field_context(object(),state(),p,'field',p['steps'][0],['right']) is None

def test_unknown_ordinary_step_does_not_read_ui(env,monkeypatch):
    monkeypatch.setattr(observation,'read_visible_text',forbidden)
    monkeypatch.setattr(r,'read_world_grid',forbidden)
    p=dict(steps=[dict(id='walk',kind='move')])
    assert r._league_field_context(object(),state(),p,'walk',p['steps'][0],[]) is None

def test_completed_field_proof_reaches_main_unchanged(env,monkeypatch):
    p=plan(r.victory_strength_bridge);s=state()
    result=({'phase':'overworld','objective':'Wait.','available_actions':['wait'],
             'field_move_complete':True,'field_move_kind':'source-strength'},'after')
    monkeypatch.setattr(observation,'read_visible_text',lambda _:object())
    monkeypatch.setattr(r,'read_world_grid',lambda *_:object())
    monkeypatch.setattr(r.victory_strength_bridge,'context',lambda *_:result)
    assert r.switch_context(object(),s,p,'field',['a']) is result


@pytest.mark.parametrize('registry',('_BINDINGS','_CONTROLLERS','_OWNERS','_ERRORS'))
@pytest.mark.parametrize('completed',(False,True))
def test_tm24_orphan_or_error_reserves_owner_before_unrelated_ui(env,monkeypatch,registry,completed):
    bridge=r.tm24_teaching_bridge
    if registry=='_BINDINGS':getattr(bridge,registry)['original']={'bad':'orphan'}
    elif registry=='_OWNERS':getattr(bridge,registry)['original']={'pyboy':object(),'controller':object()}
    elif registry=='_ERRORS':getattr(bridge,registry)['original']='tm24_existing_error'
    else:getattr(bridge,registry)['original']=bridge.tm24_teaching.TM24TeachingController(bridge.tm24_teaching.INTENT)
    if completed:bridge._COMPLETED.add('original')
    monkeypatch.setattr(observation,'read_visible_text',forbidden)
    monkeypatch.setattr(r,'read_world_grid',forbidden)
    p=dict(steps=[dict(id='purchase',mechanic='cinnabar_purchase')])
    out,owner=r.switch_context(object(),state(),p,'purchase',[])
    assert out['phase']=='campaign_review' and out['available_actions']==['wait']
    assert bridge._active()=={'original'}


@pytest.mark.parametrize('peer_name',('victory_strength_bridge','overworld_hyper_bridge','player_pc_bridge','cinnabar_purchase_bridge'))
def test_tm24_new_intent_blocks_against_peer_before_read(env,monkeypatch,peer_name):
    peer=getattr(r,peer_name)
    if peer_name=='overworld_hyper_bridge':
        peer._BINDINGS['other']={'step':{},'training_job':'job','job_canonical':'"job"','error':None}
        peer._CONTROLLERS['other']=object();peer._OWNERS['other']=object()
    else:peer._BINDINGS['other']=('still-active',)
    monkeypatch.setattr(observation,'read_visible_text',forbidden)
    monkeypatch.setattr(r,'read_world_grid',forbidden)
    monkeypatch.setattr(r.tm24_teaching_bridge,'context',forbidden)
    out,owner=r.switch_context(object(),state(),plan(r.tm24_teaching_bridge),'field',[])
    assert out['phase']=='campaign_review' and out['available_actions']==['wait']
