"""專用補藥入口的全peer快照與UI前互斥；不代表實機成功。"""
from types import ModuleType,SimpleNamespace
import pytest
from laya_pokemon import campaign_route as r,observation


def forbidden(*args,**kwargs):raise AssertionError('互斥驗證前不可讀UI或開始別的交易')


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for m in vars(r).values():
        if not isinstance(m,ModuleType):continue
        for key,value in (('_BINDINGS',{}),('_COMPLETED',set()),('_CONTROLLERS',{}),
                          ('_ERRORS',{}),('_OWNERS',{}),('_SESSIONS',{})):
            if hasattr(m,key):monkeypatch.setattr(m,key,value)
        if hasattr(m,'_REGISTRY_ERROR'):monkeypatch.setattr(m,'_REGISTRY_ERROR',None)
    monkeypatch.setattr(r.safari_entry,'_RUN_CONTROLLER',None)
    monkeypatch.setattr(r.league_native_wait,'_WAITS',{})
    monkeypatch.setattr(r,'_FIELD_CONTROLLERS',{})
    monkeypatch.setattr(r,'_GYM_CONTROLLERS',{})


def test_snapshot_has_every_known_peer_and_no_assumed_active_owner():
    inventory=r._field_medicine_peers()
    assert set(inventory)==r.owned_field_medicine.PEER_NAMES
    assert len(inventory)==33 and all(type(v) is set and not v for v in inventory.values())


@pytest.mark.parametrize('name',('battle_medicine_bridge','trainer_medicine_ui_bridge',
    'mansion_secret_key_bridge','mansion_statue_bridge','mansion_transition_ready',
    'mansion_native_landing','route21_water_bridge','pallet_surf_bridge','fly_pallet_bridge',
    'fly_viridian_bridge','safari_entry','hm_teaching_bridge','vending_bridge','saffron_guard_bridge',
    'silph_card_bridge','lapras_bridge','player_pc_bridge','cinnabar_purchase_bridge','campaign_transactions'))
def test_completed_marker_does_not_hide_sticky_legacy_error(name):
    module=getattr(r,name);module._BINDINGS['old']=('retained',);module._COMPLETED.add('old')
    if not hasattr(module,'_ERRORS'):return
    module._ERRORS['old']='retained-error'
    peer_name=dict(mansion_transition_ready='mansion_transition_ready',mansion_native_landing='mansion_native_landing',
                   campaign_transactions='campaign_transactions',safari_entry='safari_entry').get(name,name.removesuffix('_bridge'))
    assert r._field_medicine_peers()[peer_name]=={'old'}


@pytest.mark.parametrize('fault',('capture','safari','native','field','gym','malformed_capture','malformed_legacy'))
def test_nonfield_owner_or_unknown_registry_is_retained(monkeypatch,fault):
    if fault=='capture':r.capture_transaction._SESSIONS['capture']={'done':False}
    if fault=='safari':monkeypatch.setattr(r.safari_entry,'_RUN_CONTROLLER',object())
    if fault=='native':r.league_native_wait._WAITS['native']=SimpleNamespace(waiting=True)
    if fault=='field':r._FIELD_CONTROLLERS['field']=SimpleNamespace(stage='menu')
    if fault=='gym':r._GYM_CONTROLLERS['gym']=SimpleNamespace(state='menu')
    if fault=='malformed_capture':monkeypatch.setattr(r.capture_transaction,'_SESSIONS',None)
    if fault=='malformed_legacy':monkeypatch.setattr(r.player_pc_bridge,'_BINDINGS',None)
    inventory=r._field_medicine_peers()
    assert any(v is None or bool(v) for v in inventory.values())


@pytest.mark.parametrize('entry',('switch','attrition'))
def test_special_preflight_precedes_readers_and_preserves_actual_previous(monkeypatch,entry):
    pb=object();state={'frame':15697};plan={'steps':[]};previous=['a','wait'];calls=[]
    result=({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
             'review_reason':'owned_field_medicine_foreign_or_unknown_owner'},'original')
    monkeypatch.setattr(r.owned_field_medicine,'applies',lambda *_:True)
    def gate(*args,**kwargs):calls.append((args,kwargs));return result
    monkeypatch.setattr(r.owned_field_medicine,'preflight',gate)
    monkeypatch.setattr(r.owned_field_medicine,'context',forbidden)
    monkeypatch.setattr(observation,'read_visible_text',forbidden)
    monkeypatch.setattr(r,'read_world_grid',forbidden)
    attrition={'review_reason':'party_attrition_requires_center'}
    out=(r.switch_context(pb,state,plan,'original',previous) if entry=='switch' else
         r.attrition_transition_context(pb,state,plan,'original',attrition,previous))
    assert out is result and len(calls)==1
    args,kwargs=calls[0];assert args==(pb,state,plan,'original')
    assert kwargs['native_owner'] is pb and kwargs['game_id']=='game28'
    assert set(kwargs['peer_owners'])==r.owned_field_medicine.PEER_NAMES
    assert kwargs['attrition'] is (attrition if entry=='attrition' else None)


def test_active_coordinator_blocks_generic_field_before_readers(monkeypatch):
    monkeypatch.setattr(r.owned_field_medicine,'_active',lambda:{'original'})
    monkeypatch.setattr(observation,'read_visible_text',forbidden)
    monkeypatch.setattr(r,'read_world_grid',forbidden)
    out,_=r._league_field_context(object(),{}, {},'other',{},[])
    assert out['review_reason']=='league_field_other_transaction_active'
    assert r._training_peers_clear() is False


def test_field_entry_defers_to_true_previous_dispatch(monkeypatch):
    monkeypatch.setattr(r.owned_field_medicine,'applies',lambda *_:True)
    monkeypatch.setattr(observation,'read_visible_text',forbidden)
    monkeypatch.setattr(r,'read_world_grid',forbidden)
    assert r.field_context(object(),{}, {'steps':[]},'original') is None


@pytest.mark.parametrize('entry',('switch','attrition'))
def test_full_heal_preflight_precedes_ui_and_receives_independent_evidence(monkeypatch,entry):
    pb=object();s={'frame':5353};p={'steps':[]};previous=['a'];calls=[]
    result=({'phase':'campaign_review','available_actions':['wait'],'review_reason':'blocked'},'original')
    monkeypatch.setattr(r.recovery_field_medicine,'applies',lambda *a,**k:True)
    def gate(*args,**kwargs):calls.append((args,kwargs));return result
    monkeypatch.setattr(r.recovery_field_medicine,'preflight',gate)
    monkeypatch.setattr(r.recovery_field_medicine,'context',forbidden)
    monkeypatch.setattr(r.owned_field_medicine,'preflight',forbidden)
    monkeypatch.setattr(observation,'read_visible_text',forbidden)
    monkeypatch.setattr(r,'read_world_grid',forbidden)
    attrition={'review_reason':'party_attrition_requires_center'}
    out=(r.switch_context(pb,s,p,'original',previous) if entry=='switch' else
        r.attrition_transition_context(pb,s,p,'original',attrition,previous))
    assert out is result and len(calls)==1
    args,kwargs=calls[0];assert args==(pb,s,p,'original')
    assert kwargs['native_owner'] is pb and kwargs['game_id']=='game29'
    assert kwargs['source_evidence'] is r._RECOVERY_FULL_HEAL_EVIDENCE
    assert set(kwargs['peer_owners'])==r.owned_field_medicine.PEER_NAMES
    assert kwargs['attrition'] is (attrition if entry=='attrition' else None)


def test_completed_full_heal_none_never_falls_through_to_old_coordinator(monkeypatch):
    pb=object();s={'location':{'map_id':198,'x':12,'y':13}};p={};previous=['right'];seen=[]
    monkeypatch.setattr(r.recovery_field_medicine,'applies',lambda *a,**k:True)
    monkeypatch.setattr(r.recovery_field_medicine,'preflight',lambda *a,**k:None)
    def done(*args,**kwargs):seen.append(args);return None
    monkeypatch.setattr(r.recovery_field_medicine,'context',done)
    monkeypatch.setattr(r.owned_field_medicine,'applies',forbidden)
    monkeypatch.setattr(observation,'read_visible_text',lambda _: 'actual-text')
    monkeypatch.setattr(r,'read_world_grid',lambda *_:'actual-grid')
    assert r._owned_field_medicine_context(pb,s,p,'original',previous) is None
    assert seen==[(pb,s,p,'original','actual-text','actual-grid',previous)]


def test_unmarked_old_no_cursor_plan_is_not_stolen_by_new_profile():
    assert r.recovery_field_medicine.applies({},None,shared=r.owned_field_medicine) is False
