"""Actual normal zero bridge -> projection -> JSON -> EOF -> return proposal."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent


def load(name,path):
    assert path.resolve() in {(ROOT/'src/laya_pokemon/league_training_batch_bridge.py').resolve(),
                             (ROOT/'src/laya_pokemon/league_training_proof.py').resolve()}
    spec=importlib.util.spec_from_file_location('laya_pokemon._zero_receiver_formal_'+name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


import importlib
bridge=load('bridge',ROOT/'src/laya_pokemon/league_training_batch_bridge.py')
proof=load('proof',ROOT/'src/laya_pokemon/league_training_proof.py')
sup=importlib.import_module('laya_pokemon.league_training_supervisor')
h=importlib.import_module('test_league_training_batch')
hs=importlib.import_module('test_league_training_supervisor')
assert Path(sup.__file__).resolve()==(ROOT/'src/laya_pokemon/league_training_supervisor.py').resolve()
assert Path(h.__file__).resolve()==(ROOT/'tests/test_league_training_batch.py').resolve()
assert Path(hs.__file__).resolve()==(ROOT/'tests/test_league_training_supervisor.py').resolve()
b=bridge.batch


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(h,'bridge',bridge);monkeypatch.setattr(h,'b',bridge.batch);monkeypatch.setattr(hs,'s',sup)
    for name,value in (('_CONTROLLERS',{}),('_BINDINGS',{}),('_COMPLETED',set()),('_ERRORS',{}),('_OWNERS',{})):
        monkeypatch.setattr(bridge,name,value)
    for name in ('_SESSIONS','_OWNERS','_ERRORS'):monkeypatch.setattr(proof,name,{})


def outing():
    seed=h.Session();p=h.read_progress(seed.pb,h.sdk)
    snap=hs.snapshot(p=p);sha=sup.digest(snap['raw'][0]);cal=hs.calibration(sha)
    budget=sup.budget_start(2000.,sha,'c'*64,sup.digest(snap['raw'][3]))
    out=sup.propose(snap,budget,cal,2001.)
    s=h.Session();s.plan=out['plan'];s.step_id=s.plan['steps'][-1]['id'];s.pb.frame_count=150
    return s,out,cal


def first_return(s,*,ack=True):
    s.call();p=s.c.pending;s.previous=[p['action']] if ack else ['wait']
    s.call(raw=1,window=True,no_grid=True)
    s.reward();result=s.call()
    return p,result


def completed_zero():
    s,out,cal=outing();p,first=first_return(s)
    assert not first['training_batch_complete'] and s.c.pending is p
    result=s.call();assert result['field_move_complete'] and result['training_batch_displacements']==0
    return s,result,out,cal


def projected(s,result):
    return sup.project_completed_batch(s.plan,result,s.last_state)


def test_real_zero_bridge_receipt_survives_json_eof_and_proposes_only_normal_return():
    s,result,out,cal=completed_zero();c=s.c;origin=c._zero_bridge_origin
    assert origin['controller'] is c and origin['native'] is s.pb
    assert origin['wild']['pending'] is c.wild_walk_evidence['pending']
    assert origin['closed']['pending'] is origin['wild']['pending']
    record=projected(s,result);native=record['batch_receipt']
    assert native['walk_resolution']=='cancelled_before_displacement'
    assert native['cancelled_walk']['kind']=='observed_turn_before_displacement'
    assert record['batch_receipt_sha256']==sup.canonical_sha(native)
    assert isinstance(native['cancelled_walk']['pending']['player'],list)
    wire=json.loads(json.dumps(record));f=s.last_state['frame']+10
    # Actual EOFProofController, with fresh real SDK/world/movement readers.
    from laya_pokemon.rocket_movement import read_rocket_movement
    for frame in (f-1,f):
        s.pb.frame_count=frame;loc=deepcopy(s.last_state['location'])
        progress=h.read_progress(s.pb,h.sdk);text=h.read_visible_text(s.pb);text['observation_frame']=frame
        state=dict(frame=frame,location=loc,progress=progress,battle_state=h.read_battle_state(s.pb),phase='unclassified')
        eof=proof.context(state,out['plan'],text=text,grid=h.read_world_grid(s.pb,loc),
            movement=read_rocket_movement(s.pb,observation_frame=frame),native_owner=s.pb,
            peers_clear=True,full_party_healed=sup.full_party(progress['party']),validation=sup,stored_batch_proof=wire)
        assert eof['phase']==('league_training_wait' if frame==f-1 else 'campaign_review')
    assert eof['review_reason']=='route_extension_required' and eof['training_batch_proof']==wire
    end=hs.snapshot(out['plan'],frame=f,loc=s.last_state['location'],p=s.last_state['progress'],batch=wire)
    values=list(map(sup.decode,end['raw']));values[2]['state']['training_world_proof']=eof['training_world_proof']
    end=sup.snapshot_from_bytes([sup.encode(v) for v in values])
    assert sup.eof_batch_proof(out['plan'],end['review']['state'],wire)==wire
    original=deepcopy(out['budget']);back=sup.propose(end,out['budget'],cal,2100.)
    assert back['status']=='proposal_only' and back['budget']['phase']=='returning'
    assert back['budget']['outings']==original['outings']==1 and back['budget']['appends']==original['appends']+1
    assert back['budget']['started_wall']==original['started_wall'] and back['budget']['deadline_wall']==original['deadline_wall']
    assert out['budget']==original and all(v['recovery_route'] for v in back['plan']['steps'][len(out['plan']['steps']):])
    assert back['plan']['steps'][-1]['kind']=='heal' and back['plan']['steps'][-1]['require_full_pp'] is True


@pytest.mark.parametrize('bad',['native','controller','binding','pending_ref','evidence_ref','ack_ref','ack_frame',
    'first_raw_bool','first_location','first_frame','history_extra','history_counter','receipt_exp',
    'receipt_frames_float','cancel_frames_float','no_closed_witness','closed_frame','closed_resources'])
def test_bridge_rejects_zero_without_original_native_pending_wild_and_two_fresh_witnesses(bad):
    s,out,cal=outing();p,first=first_return(s);c=s.c;o=c._zero_bridge_origin;e=c.wild_walk_evidence
    if bad=='native':o['native']=object()
    if bad=='controller':
        clone=object.__new__(c.__class__);clone.__dict__.update(c.__dict__);bridge._CONTROLLERS[s.step_id]=clone
    if bad=='binding':bridge._BINDINGS[s.step_id]=tuple(list(bridge._BINDINGS[s.step_id]))
    if bad=='pending_ref':e['pending']=deepcopy(p)
    if bad=='evidence_ref':c.wild_walk_evidence=deepcopy(e)
    if bad=='ack_ref':o['ack']['pending']=deepcopy(p)
    if bad=='ack_frame':o['ack']['frame']+=1
    if bad=='first_raw_bool':o['wild']['raw']=True
    if bad=='first_location':o['wild']['location']['y']=8
    if bad=='first_frame':o['wild']['frame']+=1
    if bad=='history_extra':c.cancelled_walk_history.append({'pretend':'prior'})
    if bad=='no_closed_witness':o['closed']=None
    if bad=='closed_frame':o['closed']['frame']-=1
    if bad=='closed_resources':o['closed']['resources']['party'][0]['exp']+=1
    original=c.hint
    if bad in ('history_counter','receipt_exp','receipt_frames_float','cancel_frames_float'):
        def altered(*args,**kwargs):
            if c.complete:
                if bad=='history_counter':c.cancelled_walk_history[-1]['displacements_after']=False
                if bad=='receipt_exp':c.receipt['total_exp_gain']+=1
                if bad=='receipt_frames_float':c.receipt['closed_frames']=[float(f) for f in c.receipt['closed_frames']]
                if bad=='cancel_frames_float':
                    c.cancelled_walk_history[-1]['closed_frames']=[float(f) for f in c.cancelled_walk_history[-1]['closed_frames']]
                    c.receipt['cancelled_walk']=deepcopy(c.cancelled_walk_history[-1])
            return original(*args,**kwargs)
        c.hint=altered
    result=s.call();h.review(result);assert s.step_id not in bridge._COMPLETED


def test_one_real_return_cannot_use_planted_controller_fields_as_a_second_fresh_world():
    s,out,cal=outing();s.call();p=s.c.pending;s.previous=[p['action']]
    s.call(raw=1,window=True,no_grid=True);s.reward();c=s.c
    # Public controller metadata alone is not a true bridge closure witness.
    s.pb.frame_count+=10
    current=h.read_progress(s.pb,h.sdk)
    c.closed_frame=s.pb.frame_count-1;c.closed_player=p['player'];c.closed_resources=b.resources(current)
    c.closed_cancelled_walk=c._cancelled_turn_evidence()
    result=s.call();h.review(result,'zero_cancel_original_provenance')
    assert c._zero_bridge_origin['closed'] is None and s.step_id not in bridge._COMPLETED


@pytest.mark.parametrize('bad',['no_ack','fake_seen_wild','second_wild','wrong_source'])
def test_zero_requires_actual_normal_ack_first_wild_and_source(bad):
    s,out,cal=outing()
    if bad=='fake_seen_wild':
        s.call();p=s.c.pending;s.previous=[p['action']];s.call();s.c.seen_wild=s.c.suspended=True;s.reward()
    elif bad=='wrong_source':
        s.call();s.advance(wild=True);s.place(s.c.pending['player']);s.reward()
    else:
        first_return(s,ack=bad!='no_ack')
    result=s.call(raw=1,window=True,no_grid=True) if bad=='second_wild' else s.call()
    h.review(result);assert not bridge._COMPLETED


@pytest.mark.parametrize('bad',['missing_receipt','missing_sha','sha','exp0','wild_bool','exp_bool','count_bool',
    'historical_kind','source','expected','action','executed','ack','firstwild','pending_frame','counter_bool',
    'cancel_frame_float','outer_frame_float','outcome','fake_noencounter','count_one'])
def test_json_eof_and_propose_revalidate_zero_even_with_recomputed_integrity_hash(bad):
    s,result,out,cal=completed_zero();record=json.loads(json.dumps(projected(s,result)))
    native=record['batch_receipt'];cancel=native['cancelled_walk']
    if bad=='missing_receipt':record.pop('batch_receipt')
    if bad=='missing_sha':record.pop('batch_receipt_sha256')
    if bad=='sha':record['batch_receipt_sha256']='a'*64
    if bad=='exp0':native['total_exp_gain']=0
    if bad=='wild_bool':native['wild_count']=True
    if bad=='exp_bool':native['total_exp_gain']=True
    if bad=='count_bool':record['displacements']=False
    if bad=='historical_kind':cancel['kind']='reviewed_original_turn_before_displacement'
    if bad=='source':cancel['wild_player']=[28,8]
    if bad=='expected':cancel['pending']['expected']=[28,7]
    if bad=='action':cancel['pending']['action']='up'
    if bad=='executed':cancel['pending']['executed']=False
    if bad=='ack':cancel['actual_ack_frame']=cancel['pending']['frame']
    if bad=='firstwild':cancel['wild_frame']=native['closed_frames'][0]
    if bad=='pending_frame':cancel['pending']['frame']=True
    if bad=='counter_bool':cancel['displacements_before']=False
    if bad=='cancel_frame_float':cancel['closed_frames']=[float(f) for f in native['closed_frames']]
    if bad=='outer_frame_float':record['closed_frames'][0]=float(record['closed_frames'][0])
    if bad in ('outcome','fake_noencounter'):record['outcome']='complete_no_encounter'
    if bad=='fake_noencounter':native.update(wild_count=0,total_exp_gain=0)
    if bad=='count_one':record['displacements']=1
    if bad not in ('missing_receipt','missing_sha','sha'):
        record['batch_receipt_sha256']=sup.canonical_sha(native)
    end=hs.snapshot(out['plan'],frame=s.last_state['frame']+10,loc=s.last_state['location'],p=s.last_state['progress'],batch=record)
    with pytest.raises(sup.ReviewRequired):sup.eof_batch_proof(out['plan'],end['review']['state'],record)
    with pytest.raises(sup.ReviewRequired):sup.propose(end,out['budget'],cal,2100.)


@pytest.mark.parametrize('bad',['wild_bool','exp0','exp_bool','count_bool','noencounter','wrong_source','frames_float'])
def test_projection_does_not_admit_bad_zero_context(bad):
    s,result,out,cal=completed_zero();native=result['training_batch_receipt']
    if bad=='wild_bool':native['wild_count']=True
    if bad=='exp0':native['total_exp_gain']=0
    if bad=='exp_bool':native['total_exp_gain']=True
    if bad=='count_bool':result['training_batch_displacements']=False
    if bad=='noencounter':result['training_batch_outcome']='complete_no_encounter'
    if bad=='wrong_source':native['cancelled_walk']['wild_player']=[28,8]
    if bad=='frames_float':native['closed_frames']=[float(f) for f in native['closed_frames']]
    with pytest.raises(sup.ReviewRequired):projected(s,result)


def test_original_positive_and_noencounter_receipts_and_legacy_projections_remain_compatible():
    snap,budget,cal=hs.start();out=sup.propose(snap,budget,cal,2001.)
    for outcome in ('complete_single_wild','complete_no_encounter'):
        end=hs.batch_snapshot(out,outcome=outcome);record=end['review']['state']['training_batch_proof']
        assert 'batch_receipt' in record and 'batch_receipt_sha256' in record
        assert sup.propose(end,out['budget'],cal,2100.)['budget']['phase']=='returning'
        legacy=deepcopy(record);legacy.pop('batch_receipt');legacy.pop('batch_receipt_sha256')
        assert sup.eof_batch_proof(out['plan'],end['review']['state'],legacy)==legacy
