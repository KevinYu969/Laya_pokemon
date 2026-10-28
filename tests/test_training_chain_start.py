"""Portable exact-source chain-start checks; no runtime/private evidence."""
from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/'src/laya_pokemon/league_training_batch_bridge.py'
spec=importlib.util.spec_from_file_location('laya_pokemon._chain_start_test_bridge',SOURCE)
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
assert Path(bridge.__file__).resolve()==SOURCE.resolve()
h=importlib.import_module('test_league_training_batch')
assert Path(h.__file__).resolve()==(ROOT/'tests/test_league_training_batch.py').resolve()
b=bridge.batch

@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(h,'bridge',bridge);monkeypatch.setattr(h,'b',b)
    for k,v in (('_CONTROLLERS',{}),('_BINDINGS',{}),('_OWNERS',{}),('_COMPLETED',set()),('_ERRORS',{}),('_REVIEWED_ABORTS',{}),('_LEARNING',{})):
        monkeypatch.setattr(bridge,k,v)

def lower():
    s=h.Session();s.place((28,8));s.plan['steps'][0]['target']=[28,8]
    return s

def test_default_start_retains_original_intent_contract_and_down_action():
    c=b.TrainingBatch();assert c.start==c.start_contract==(28,7)
    assert c.intent==c.contract==b.INTENT
    s=h.Session();out=s.call()
    assert out['available_actions']==['down','wait'] and s.c.start==(28,7)

def test_lower_start_first_up_true_reward_and_needs_center_remain_exact():
    s=lower();out=s.call();c=s.c;baseline=c.baseline
    assert out['available_actions']==['up','wait'] and c.start==c.start_contract==(28,8)
    assert c.pending['player']==(28,8) and c.pending['expected']==(28,7)
    s.advance(wild=True);s.reward();assert not s.call()['training_batch_complete']
    out=s.call();r=out['training_batch_receipt']
    assert out['field_move_complete'] and c.displacements==1 and c.baseline is baseline
    assert r['total_exp_gain']==120 and r['total_pp_spent']==1
    assert type(r['needs_center']) is bool and r['needs_center'] is b.needs_center(b.resources(s.last_state['progress']))

def test_only_exact_typed_two_tile_tuple_is_a_valid_start():
    for invalid in ((27,7),(28,9),(28,True),(28,8.0),[28,8],None,(28,8,0)):
        with pytest.raises(ValueError):b.TrainingBatch(start=invalid)
    s=lower();s.plan['steps'][0]['target']=[28,9]
    h.review(s.call(),'explicit_intent');assert not bridge._CONTROLLERS

def test_current_tile_must_match_explicit_start_and_pure_default_is_fixed():
    s=lower();s.plan['steps'][0]['target']=[28,7]
    assert s.call() is None and not bridge._CONTROLLERS
    s=lower();s.call();c=b.TrainingBatch()
    signal=b.read_training_observation(s.pb,s.pb.frame_count,h.sdk)
    out=c.context(s.last_state,text=s.last_text,grid=s.last_grid,signal=signal,previous=[],now=s.now,owner='default')
    h.review(out,'initial_start_tile');assert c.baseline is None and c.pending is None

def test_active_start_tampering_or_retarget_never_rebuilds_or_refunds():
    s=lower();s.call();c=s.c;pending=c.pending;baseline=c.baseline
    spent=(c.started,c.calls,c.waits,c.requests,c.displacements)
    c.start=(28,7);h.review(s.call(),'original_start_contract')
    assert s.c is c and c.pending is pending and c.baseline is baseline
    assert spent==(c.started,c.calls,c.waits,c.requests,c.displacements)
    bridge._ERRORS.clear();c.start=(28,8);s.plan['steps'][0]['target']=[28,7]
    h.review(s.call(),'job_or_intent');assert s.c is c and c.pending is pending

def test_lower_zero_displacement_requires_true_ack_and_original_start_witness():
    s=lower();s.call();c=s.c;p=c.pending;baseline=c.baseline
    s.previous=['up'];s.call(raw=1,window=True,no_grid=True)
    assert p['executed'] and c.wild_walk_evidence['pending'] is p
    s.reward();assert not s.call()['training_batch_complete'];out=s.call()
    assert out['field_move_complete'] and c.displacements==0 and c.baseline is baseline
    receipt=out['training_batch_receipt'];assert receipt['walk_resolution']=='cancelled_before_displacement'
    assert receipt['cancelled_walk']['pending']['player']==(28,8)
    assert receipt['cancelled_walk']['wild_player']==[28,8]
    assert receipt['cancelled_walk']['displacements_before']==receipt['cancelled_walk']['displacements_after']==0

def test_lower_zero_without_actual_ack_never_closes_or_claims_displacement():
    s=lower();s.call();p=s.c.pending;s.previous=['wait'];s.call(raw=1,window=True,no_grid=True)
    s.reward();h.review(s.call(),'wild_walk_execution')
    assert not p['executed'] and s.c.displacements==0 and not bridge._COMPLETED

def test_legacy_warm_controller_without_start_fields_survives_without_rewrite():
    s=h.Session();s.call();c=s.c;p=c.pending;base=c.baseline;started=c.started
    del c.start;del c.start_contract
    s.advance(wild=True);s.reward();s.call();out=s.call()
    assert out['field_move_complete'] and s.c is c and c.baseline is base and c.started==started
    assert not hasattr(c,'start') and not hasattr(c,'start_contract')
    assert p['executed'] and c.displacements==1
