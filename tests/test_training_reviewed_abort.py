"""Self-contained native readers/pure failure -> reviewed abort; no local evidence."""
from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/'src/laya_pokemon/league_training_batch_bridge.py'
spec=importlib.util.spec_from_file_location('laya_pokemon._reviewed_abort_test_bridge',SOURCE)
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
assert Path(bridge.__file__).resolve()==SOURCE.resolve()
h=importlib.import_module('test_league_training_batch')
assert Path(h.__file__).resolve()==(ROOT/'tests/test_league_training_batch.py').resolve()


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(h,'bridge',bridge);monkeypatch.setattr(h,'b',bridge.batch)
    for k,v in (('_CONTROLLERS',{}),('_BINDINGS',{}),('_OWNERS',{}),('_ERRORS',{}),
                ('_COMPLETED',set()),('_REVIEWED_ABORTS',{})):
        monkeypatch.setattr(bridge,k,v)


def failed_retreat():
    s=h.Session();address=h.sdk.PARTY_MONS_ADDRESS
    s.pb.memory.values[address+2]=90;s.pb.memory.values[address+0x23]=90
    s.call()
    for _ in range(3):s.advance()
    p=s.c.pending;s.previous=[p['action']]
    s.call(raw=1,window=True,no_grid=True)
    s.pb.memory.values[address+2]=25;s.pb.memory.values[address+31]-=3
    s.pb.frame_count=160496;s.previous=['a'];out=s.call()
    assert s.c.error==bridge._ABORT_ERROR and not s.c.complete and not bridge._COMPLETED
    assert out['phase']=='campaign_review' and s.c.pending is p
    c=s.c;cap=dict(kind='reviewed_training_escape160497_v1',game_id='game29',source_frame=160497,
        source_location=deepcopy(s.last_state['location']),step_id=s.step_id,job=s.plan['training_job'],
        original_error=c.error,original_plan=deepcopy(s.plan),plan_bytes_sha256='b'*64,
        plan_sha256=bridge._digest(s.plan),binding_sha256=bridge._digest(bridge._BINDINGS[s.step_id]),
        baseline_sha256=bridge._digest(c.baseline),progress_sha256=bridge._digest(s.last_state['progress']),
        packet_sha256=bridge._digest(c.last_packet),pending=deepcopy(c.pending),pending_sha256=bridge._digest(c.pending),
        counters={k:getattr(c,k) for k in ('started','last_now','calls','waits','requests','displacements','last_frame')},
        baseline=deepcopy(c.baseline),controller_identity=id(c),native_identity=id(s.pb),
        source_escape=dict(file='synthetic-steps.jsonl',line_number=29,line_sha256='a'*64,
            record=dict(state=dict(frame=160369,location=deepcopy(s.last_state['location']),
                battle_state=dict(raw=1,kind='wild',active=True),
                visible_text_candidates=[' Got away safely!']),action='a')),
        original_review_sha256='c'*64,source_state_sha256='d'*64,
        root_review=dict(reason='Synthetic actual retreat review',reward_exp=0,pp_spent=3,hp_lost=65,
            original_counter_refund=False,original_error_cleared=False,source_frame_wait_limit=80))
    cap['counters_sha256']=bridge._digest(cap['counters'])
    args=dict(expected_capsule_sha256=bridge._digest(cap),original_controller=c,
        original_binding=bridge._BINDINGS[s.step_id],original_pending=c.pending,original_last_packet=c.last_packet)
    return s,cap,args


def fresh(s,frame=160537):
    s.pb.frame_count=frame
    text=h.read_visible_text(s.pb);text['observation_frame']=frame
    loc=dict(map_id=194,x=s.player[0],y=s.player[1]);grid=h.read_world_grid(s.pb,loc)
    state=dict(frame=frame,location=loc,progress=h.read_progress(s.pb,h.sdk),battle_state=h.read_battle_state(s.pb),phase='overworld')
    return state,text,grid


def abort(s,cap,args,current=None):
    state,text,grid=current or (s.last_state,s.last_text,s.last_grid)
    return bridge.reviewed_abort(s.pb,state,s.plan,s.step_id,text,grid,cap,**args)


def test_true_failed_retreat_stays_failure_two_fresh_abort_is_not_completed_and_recovery_is_unowned():
    s,cap,args=failed_retreat();c=s.c;preserved=bridge._abort_snapshot(c);packet=c.last_packet;p=c.pending;base=c.baseline
    out,_=abort(s,cap,args)
    assert not out['training_batch_aborted'] and bridge._active()=={s.step_id}
    assert out['phase']=='training_batch_owned' and out['available_actions']==['wait'] and 'review_reason' not in out
    abort(s,cap,args);assert bridge._REVIEWED_ABORTS[s.step_id]['closed_frames']==[160497]
    current=fresh(s);out,_=abort(s,cap,args,current)
    assert out['review_reason']=='training_batch_reviewed_abort_ready_for_recovery'
    assert out['training_batch_aborted'] and not out['training_batch_complete']
    assert 'field_move_complete' not in out and 'training_batch_receipt' not in out
    assert bridge._active()==set() and not bridge._COMPLETED and c.error==bridge._ABORT_ERROR
    assert bridge._abort_snapshot(c)==preserved and c.pending is p and c.last_packet is packet and c.baseline is base
    assert bridge._REVIEWED_ABORTS[s.step_id]['closed_frames']==[160497,160537]
    assert not bridge.applies('recovery-026-000',dict(kind='move',map_id=194,target=[28,7]))
    assert bridge.reviewed_abort(s.pb,current[0],s.plan,'recovery-026-000',current[1],current[2],cap,**args) is None
    old=bridge.context(s.pb,current[0],s.plan,s.step_id,current[1],current[2],['wait'])
    assert old[0]['review_reason']=='training_batch_reviewed_abort_ready_for_recovery' and c.last_packet is packet


def test_pending_abort_and_done_abort_survive_exact_source_reload_without_refunding():
    s,cap,args=failed_retreat();c=s.c;abort(s,cap,args);registry=bridge._REVIEWED_ABORTS
    spec.loader.exec_module(bridge)
    assert bridge._REVIEWED_ABORTS is registry and bridge._active()=={s.step_id} and bridge._CONTROLLERS[s.step_id] is c
    abort(s,cap,args,fresh(s));spec.loader.exec_module(bridge)
    assert bridge._REVIEWED_ABORTS is registry and bridge._active()==set() and c.error==bridge._ABORT_ERROR


@pytest.mark.parametrize('bad',['pin','plan','native','controller','binding','pending','packet','cap_identity','escape','exp','nonblank','battle','late'])
def test_abort_rejects_missing_authority_changed_identity_or_nonclosed_native_world(bad):
    s,cap,args=failed_retreat();c=s.c;current=None
    if bad=='pin':args['expected_capsule_sha256']='e'*64
    if bad=='plan':s.plan['lead_species']=154
    if bad=='native':args['original_controller']=object()
    if bad=='controller':bridge._CONTROLLERS[s.step_id]=deepcopy(c)
    if bad=='binding':bridge._BINDINGS[s.step_id]=tuple(list(bridge._BINDINGS[s.step_id]))
    if bad=='pending':args['original_pending']=deepcopy(c.pending)
    if bad=='packet':args['original_last_packet']=deepcopy(c.last_packet)
    if bad=='cap_identity':cap['native_identity']+=1;args['expected_capsule_sha256']=bridge._digest(cap)
    if bad=='escape':cap['source_escape']['record']['state']['visible_text_candidates']=['Can\'t escape!'];args['expected_capsule_sha256']=bridge._digest(cap)
    if bad=='exp':s.pb.experience(0,cap['baseline']['party'][0]['exp']+1)
    if bad=='nonblank':current=(s.last_state,dict(s.last_text,window_visible=True),s.last_grid)
    if bad=='battle':s.pb.memory.values[0xD057]=1
    if bad=='late':abort(s,cap,args);current=fresh(s,160578)
    out,_=abort(s,cap,args,current)
    assert out['phase']=='campaign_review' and not out.get('training_batch_aborted')
    assert not bridge._COMPLETED and not any(r['done'] for r in bridge._REVIEWED_ABORTS.values())
    assert c.error==bridge._ABORT_ERROR


@pytest.mark.parametrize('bad',['pending_ref','binding_ref','native_ref','packet_ref','counter','error','capsule','done_forged','registry'])
def test_done_record_cannot_hide_changed_original_objects_or_forged_registry(bad):
    s,cap,args=failed_retreat();c=s.c;abort(s,cap,args);abort(s,cap,args,fresh(s));r=bridge._REVIEWED_ABORTS[s.step_id]
    if bad=='pending_ref':c.pending=deepcopy(c.pending)
    if bad=='binding_ref':bridge._BINDINGS[s.step_id]=tuple(list(bridge._BINDINGS[s.step_id]))
    if bad=='native_ref':bridge._OWNERS[s.step_id]=object()
    if bad=='packet_ref':c.last_packet=deepcopy(c.last_packet)
    if bad=='counter':c.calls=0
    if bad=='error':c.error=None
    if bad=='capsule':r['capsule']['original_error']='none'
    if bad=='done_forged':r['closed_frames']=[160497]
    if bad=='registry':bridge._REVIEWED_ABORTS=123
    assert bridge._active() is None and bridge.applies('recovery-026-000',dict(kind='move'))


def test_default_escape_still_fails_and_has_no_implicit_abort_or_completion():
    s,cap,args=failed_retreat()
    assert bridge._active()=={s.step_id} and not bridge._REVIEWED_ABORTS and not bridge._COMPLETED
    assert s.c.receipt is None and s.c.error==bridge._ABORT_ERROR


def test_existing_peer_prevents_reviewed_abort():
    s,cap,args=failed_retreat();bridge._CONTROLLERS['peer']=object()
    out,_=abort(s,cap,args)
    assert out['phase']=='campaign_review' and not bridge._REVIEWED_ABORTS
