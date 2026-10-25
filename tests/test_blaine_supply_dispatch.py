"""Real formal dispatch + real policy; stub getter packets and bridge only."""
from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import laya_pokemon
import pytest

ROOT=Path(laya_pokemon.__file__).resolve().parents[2]
STAGE=ROOT/'.local/staged-blaine-dispatch-tests-20261025'


def source_for_test(path):
    p=Path(path).resolve()
    if p in (STAGE/'test_blaine_supply_dispatch.py',ROOT/'tests/test_blaine_supply_dispatch.py'):
        return ROOT/'src/laya_pokemon/blaine_supply_dispatch.py'
    raise RuntimeError('Only exact staged or formal test locations are supported')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


fx=load('dispatch_policy_fixture',ROOT/'tests/test_blaine_supply_policy.py')


def finisher_inputs(env,hp=77,enemy_hp=5,approved=True):
    e=env;e.kw=fx.inputs(hp,0,164)
    raw=e.kw['enemy_proof']['raw_record'];raw[1:3]=[0,enemy_hp];raw[14]=42;raw[15:17]=[0,113]
    raw[8:12]=[39,23,45,83];raw[17:19]=[0,96];raw[23:25]=[0,78]
    e.kw['enemy_proof']['enemy']=e.d.bm.decode_enemy_mon(raw)['enemy']
    e.kw['player_snapshot']['player']['defense']=88
    p=e.kw['player_snapshot']['player'];enemy=e.kw['enemy_proof']['enemy']
    e.kw['text']=fx.native_text(e.d.bm._command_view(p,enemy,(9,14)))
    e.state['progress']=e.kw['progress'];e.state['battle_state']['opponent_species']='RAPIDASH'
    e.plan['steps'][0]['reviewed_rapidash_finisher']=approved


@pytest.mark.parametrize('hp,enemy_hp,approved,allowed',[(77,5,True,True),(78,1,True,True),
    (76,5,True,False),(79,5,True,False),(77,6,True,False),(77,5,False,False),(77,5,1,False)])
def test_reviewed_rapidash_finish_is_narrow_and_keeps_risk_explicit(env,hp,enemy_hp,approved,allowed):
    e=env;finisher_inputs(e,hp,enemy_hp,approved);result=e.call()
    if allowed:
        assert result[0]['battle_tactic']=='reviewed_rapidash_5hp_finisher'
        assert result[0]['survival_approved'] is False and result[0]['finisher_source_enemy_hp']==enemy_hp
        assert not e.bridge_calls
    else:assert result is None and not e.bridge_calls


@pytest.fixture
def env(monkeypatch):
    d=load('laya_pokemon._formal_supply_dispatch_under_test',source_for_test(__file__))
    for name,value in (('_CONTROLLERS',{}),('_BINDINGS',{}),('_COMPLETED',set())):
        monkeypatch.setattr(d.bridge,name,value)
    e=SimpleNamespace(d=d,reads=[],decisions=[],bridge_calls=[],getter_hook=None)
    e.kw=fx.inputs(65)
    e.game=SimpleNamespace(frame_count=e.kw['frame'])
    e.state=dict(frame=e.kw['frame'],location=deepcopy(fx.LOC),progress=e.kw['progress'],
        battle_state=dict(raw=2,active=True,kind='trainer',observation_frame=e.kw['frame'],opponent_species='ARCANINE'))
    step=dict(id='blaine',kind='interact',map_id=166,target=[3,4],face='up',event='beat_blaine',battle_supply=d.bridge.SUPPLY)
    e.plan=dict(steps=[step]);e.previous=['down','a'];e.constants=object()
    monkeypatch.setattr(d.bridge,'_sdk_constants',lambda:e.constants)
    def getter(name):
        def read(game,**kwargs):
            assert game is e.game and kwargs['constants'] is e.constants
            assert kwargs['observation_frame']==e.state['frame']
            assert kwargs['expected_location']==fx.LOC
            e.reads.append(name)
            if e.getter_hook:e.getter_hook(name)
            return deepcopy(e.kw['player_snapshot' if name=='player' else 'enemy_proof'])
        return read
    monkeypatch.setattr(d.player_battle,'read_player_battle',getter('player'))
    monkeypatch.setattr(d.trainer_opponent,'read_trainer_opponent',getter('enemy'))
    real_decide=d.policy.decide
    def decide(*args):
        result=real_decide(*args);e.decisions.append(deepcopy(result));return result
    monkeypatch.setattr(d.policy,'decide',decide)
    def bridge(game,state,plan,step_id,text,previous,**kwargs):
        assert previous is e.previous and state is e.state and plan is e.plan
        e.bridge_calls.append(dict(kwargs=deepcopy(kwargs),previous=list(previous)))
        return dict(phase='battle_medicine_wait',available_actions=['wait'],bridge_sentinel=True),step_id
    monkeypatch.setattr(d.bridge,'context',bridge)
    def call(step_id='blaine'):
        before=deepcopy((e.state,e.plan,e.kw,e.previous))
        result=d.context(e.game,e.state,e.plan,step_id,e.kw['text'],e.previous)
        assert (e.state,e.plan,e.kw,e.previous)==before
        return result
    e.call=call
    return e


def reset_inputs(e,hp=65,status=0,enemy_species=20):
    e.kw=fx.inputs(hp,status,enemy_species)
    e.state['progress']=e.kw['progress']
    e.state['battle_state']['opponent_species']=e.kw['enemy_proof']['enemy']['species_name']


@pytest.mark.parametrize('hp,enemy_hp,status,approved,allowed',[
    (125,4,16,True,True),(156,1,0,True,True),(124,4,16,True,False),
    (125,5,16,True,False),(125,4,16,False,False),(125,4,16,1,False),(125,4,8,True,False)])
def test_arcanine_finisher_precedes_item_policy_only_in_reviewed_narrow_case(env,hp,enemy_hp,status,approved,allowed):
    e=env;reset_inputs(e,hp,status);raw=e.kw['enemy_proof']['raw_record']
    raw[1:3]=[0,enemy_hp]
    for index,value in ((17,116),(19,87),(21,101),(23,87)):raw[index:index+2]=[0,value]
    e.kw['enemy_proof']['enemy']=e.d.bm.decode_enemy_mon(raw)['enemy']
    e.kw['text']=fx.native_text(e.d.bm._command_view(e.kw['player_snapshot']['player'],e.kw['enemy_proof']['enemy'],(9,16)))
    e.plan['steps'][0]['reviewed_arcanine_finisher']=approved
    result=e.call()
    assert (result[0].get('battle_tactic')=='reviewed_arcanine_4hp_finisher') is allowed
    if allowed:
        assert not e.bridge_calls and not e.decisions
        assert result[0]['survival_approved'] is False and result[0]['finisher_source_enemy_hp']==enemy_hp


@pytest.mark.parametrize('hp,status,species,item',[(156,0,20,None),(65,0,20,18),(147,16,20,52),(65,0,83,None)])
def test_complete_command_runs_true_policy_and_only_selected_medicine_claims_bridge(env,hp,status,species,item):
    e=env;reset_inputs(e,hp,status,species);r=e.call()
    assert e.reads==['player','enemy'] and len(e.decisions)==1
    if item is None:assert r is None and e.bridge_calls==[]
    else:
        assert r[0]['bridge_sentinel'] and r[1]=='blaine'
        assert e.bridge_calls[0]['kwargs']['intent']['item']==item
        assert r[0]['blaine_supply_decision']==e.decisions[0]
        if item==52:assert e.d.policy.FULL_HEAL_RISK in e.decisions[0]['risks']


def test_nonbattle_does_not_read_or_decide(env):
    e=env;e.state['battle_state']=dict(raw=0,active=False,kind='none')
    assert e.call() is None and not e.reads and not e.decisions and not e.bridge_calls


@pytest.mark.parametrize('ui',['partial_label','dialog','unknown_decoder'])
def test_noncommand_does_not_read_or_decide(env,ui):
    e=env
    if ui=='unknown_decoder':e.kw['text']['read_valid']=False
    else:
        player=e.kw['player_snapshot']['player'];enemy=e.kw['enemy_proof']['enemy']
        rows=e.d.bm._dialog(player,enemy,'ENEMY ARCANINE','USED TAKE DOWN!') if ui=='dialog' else e.d.bm._command_view(player,enemy,(9,16))
        if ui=='partial_label':
            rows=[list(r) for r in rows];rows[14][10]=' ';rows=[''.join(r) for r in rows]
        e.kw['text']=fx.native_text(rows)
    assert e.call() is None and not e.reads and not e.decisions and not e.bridge_calls


def test_active_owner_passes_actual_previous_to_bridge_without_new_reads_or_decision(env):
    e=env;e.d.bridge._CONTROLLERS['active']=object();e.d.bridge._BINDINGS['active']={}
    r=e.call()
    assert r[0]['bridge_sentinel'] and not e.reads and not e.decisions
    assert e.bridge_calls==[dict(kwargs={},previous=['down','a'])]


def test_completed_frame_medicine_waits_then_fresh_frame_can_request_next_owner(env):
    e=env;e.d.bridge._CONTROLLERS['old']=object()
    e.d.bridge._BINDINGS['old']=dict(completed_frame=e.state['frame']);e.d.bridge._COMPLETED.add('old')
    r=e.call();assert r[0]['phase']=='battle_medicine_wait'
    assert r[0]['battle_tactic']=='fresh_command_before_next_medicine' and not e.bridge_calls
    frame=e.state['frame']+40;e.state['frame']=frame;e.game.frame_count=frame
    e.state['battle_state']['observation_frame']=frame;e.kw['frame']=frame
    e.kw['player_snapshot']['observation_frame']=frame
    for k in ('observation_frame','frame_before','frame_after'):e.kw['enemy_proof'][k]=frame
    assert e.call()[0]['bridge_sentinel'] and len(e.bridge_calls)==1


def test_unknown_reader_proof_reviews_without_bridge_claim(env):
    e=env;e.kw['enemy_proof']['read_valid']=False;r=e.call()
    assert r[0]['phase']=='campaign_review' and not e.bridge_calls


def test_native_command_labels_with_wrong_hud_require_calibration_review(env):
    e=env;rows=[list(r) for r in e.d.bm._command_view(e.kw['player_snapshot']['player'],e.kw['enemy_proof']['enemy'],(9,16))]
    rows[0][1]='X';e.kw['text']=fx.native_text([''.join(r) for r in rows]);r=e.call()
    assert r[0]['review_reason']=='blaine_supply_command_hud_requires_calibration'
    assert e.reads==['player','enemy'] and not e.bridge_calls


@pytest.mark.parametrize('bad',['missing','signature'])
def test_wrong_step_refuses_reading_or_bridge(env,bad):
    e=env
    if bad=='signature':e.plan['steps'][0]['target']=[4,4]
    r=e.call('foreign' if bad=='missing' else 'blaine')
    assert r[0]['review_reason']=='blaine_supply_fixed_step_unverified'
    assert not e.reads and not e.decisions and not e.bridge_calls


@pytest.mark.parametrize('bad',['packet_frame','frame_during_read'])
def test_foreign_frame_refuses_medicine(env,bad):
    e=env
    if bad=='packet_frame':e.state['battle_state']['observation_frame']+=1
    else:e.getter_hook=lambda name:setattr(e.game,'frame_count',e.game.frame_count+1) if name=='enemy' else None
    r=e.call();assert r[0]['phase']=='campaign_review' and not e.bridge_calls
    assert not e.decisions


def test_exact_source_resolution_has_no_fallback():
    assert source_for_test(__file__)==ROOT/'src/laya_pokemon/blaine_supply_dispatch.py'
    assert source_for_test(ROOT/'tests/test_blaine_supply_dispatch.py')==source_for_test(__file__)
    with pytest.raises(RuntimeError):source_for_test(ROOT/'tests/copy/test_blaine_supply_dispatch.py')
