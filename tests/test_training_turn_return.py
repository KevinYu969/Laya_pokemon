"""Real SDK/getters and same original controller; synthetic source RAM only."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent


def load_bridge():
    path=(ROOT/'src/laya_pokemon/league_training_batch_bridge.py').resolve(strict=True)
    spec=importlib.util.spec_from_file_location('laya_pokemon._training_turn_formal_bridge',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert Path(module.__file__).resolve()==path
    return module


bridge=load_bridge()
b=bridge.batch
import importlib
h=importlib.import_module('test_league_training_batch')
assert Path(h.__file__).resolve()==(ROOT/'tests/test_league_training_batch.py').resolve()


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    global b
    b=bridge.batch
    monkeypatch.setattr(h,'bridge',bridge);monkeypatch.setattr(h,'b',b)
    for name,value in (('_CONTROLLERS',{}),('_BINDINGS',{}),('_COMPLETED',set()),('_ERRORS',{}),('_OWNERS',{})):
        monkeypatch.setattr(bridge,name,value)


def turn_wild(s,*,ack=True):
    s.call();p=s.c.pending
    s.previous=[p['action']] if ack else ['wait']
    out=s.call(raw=1,window=True,no_grid=True)
    assert s.c.pending is p and s.player==p['player'] and s.c.seen_wild and s.c.suspended
    return p,out


def test_true_turn_encounter_closes_at_source_without_counting_a_displacement():
    s=h.Session();pending,out=turn_wild(s);c=s.c;baseline=c.baseline
    assert pending['executed'] is True and c.displacements==0
    assert c.wild_walk_evidence['pending'] is pending and c.wild_walk_evidence['player']==pending['player']
    s.reward();before=c.calls;requests=c.requests
    first=s.call();assert first['available_actions']==['wait'] and not first['training_batch_complete']
    assert c.pending is pending and c.baseline is baseline and c.closed_frame and c.returned_world_seen
    final=s.call();assert final['training_batch_complete'] and c.displacements==0 and c.pending is None
    assert c is s.c and c.baseline is baseline and c.calls==before+2 and c.requests==requests
    receipt=final['training_batch_receipt']
    assert receipt['total_exp_gain']==120 and receipt['walk_resolution']=='cancelled_before_displacement'
    assert receipt['displacement_occurred'] is False and receipt['cancelled_walk']['pending']==pending
    assert receipt['cancelled_walk']['displacements_before']==receipt['cancelled_walk']['displacements_after']==0
    assert s.next_id=='after-001' and bridge._COMPLETED=={s.step_id}


def test_previous_true_displacements_stay_exactly_two_when_the_next_turn_encounters_wild():
    s=h.Session();s.call();s.advance();s.advance();assert s.c.displacements==2
    pending=s.c.pending;s.previous=[pending['action']]
    s.call(raw=1,window=True,no_grid=True);s.reward();s.call();out=s.call()
    assert out['training_batch_complete'] and s.c.displacements==2
    assert out['training_batch_receipt']['cancelled_walk']['displacements_after']==2


def test_existing_real_walk_to_expected_then_wild_still_counts_one_true_displacement():
    s=h.Session();out=s.finish_wild()
    assert out['training_batch_complete'] and s.c.displacements==1
    assert 'cancelled_walk' not in out['training_batch_receipt']


@pytest.mark.parametrize('bad',['no_ack','fake_wild_flags','first_wild_at_expected','evidence_pending',
    'evidence_snapshot','evidence_frame','evidence_ack','evidence_location','delta_money','delta_exp',
    'delta_pp','delta_other','extra_fnt','unknown_signal'])
def test_source_stay_never_fakes_displacement_ack_wild_or_reward(bad):
    s=h.Session()
    if bad=='fake_wild_flags':
        s.call();p=s.c.pending;s.previous=[p['action']];s.call()
        s.c.seen_wild=s.c.suspended=True
    elif bad=='first_wild_at_expected':
        s.call();s.advance(wild=True);p=s.c.pending;s.place(p['player'])
    else:p,_=turn_wild(s,ack=bad!='no_ack')
    s.reward();c=s.c
    e=c.wild_walk_evidence
    if bad=='evidence_pending':e['pending']=deepcopy(p)
    if bad=='evidence_snapshot':e['snapshot']['executed']=False
    if bad=='evidence_frame':e['frame']=p['frame']
    if bad=='evidence_ack':e['ack_frame']=None
    if bad=='evidence_location':e['player']=p['expected']
    if bad=='delta_money':s.pb.memory.values[h.sdk.PLAYER_MONEY_ADDRESS+2]=0x46
    if bad=='delta_exp':s.pb.experience(0,c.baseline['party'][0]['exp'])
    if bad=='delta_pp':s.pb.memory.values[h.sdk.PARTY_MONS_ADDRESS+29]+=2
    if bad=='delta_other':s.pb.memory.values[h.sdk.PARTY_MONS_ADDRESS+8]=85
    if bad=='extra_fnt':s.pb.memory.values[h.sdk.PARTY_MONS_ADDRESS+2]=0
    kwargs=dict(state_change=lambda state:state['battle_state'].update(raw=2,kind='trainer',active=True)) if bad=='unknown_signal' else {}
    out=s.call(**kwargs);h.review(out)
    assert c.pending is p and c.displacements==0 and not bridge._COMPLETED


def test_second_wild_after_first_true_source_return_is_never_counted_as_one_battle():
    s=h.Session();turn_wild(s);s.reward();s.call()
    assert s.c.returned_world_seen and s.c.closed_frame
    h.review(s.call(raw=1,window=True,no_grid=True),'second_wild_after_verified_return')


def test_two_closed_source_frames_must_keep_exact_resources_and_position():
    s=h.Session();turn_wild(s);s.reward();s.call();s.pb.experience(0,s.c.closed_resources['party'][0]['exp']+1)
    h.review(s.call(),'closed_world_resources_changed')


def test_normal_budget_is_not_reset_or_extended_by_cancelled_walk_candidate():
    s=h.Session();p,_=turn_wild(s);s.reward();c=s.c;c.waits=b.MAX_WAITS
    oldcalls=c.calls;started=c.started
    h.review(s.call(),'wait_budget_exhausted')
    assert c.waits==b.MAX_WAITS+1 and c.calls==oldcalls+1 and c.started==started and c.pending is p


def test_reload_keeps_original_pending_baseline_and_actual_wild_source_evidence():
    s=h.Session();p,_=turn_wild(s);c=s.c;baseline=c.baseline;evidence=c.wild_walk_evidence
    bridge.__spec__.loader.exec_module(bridge)
    s.reward();s.call();out=s.call()
    assert out['training_batch_complete'] and s.c is c and c.baseline is baseline
    assert c.wild_walk_evidence is evidence and evidence['pending'] is p


REAL_CAPSULE=deepcopy(b.TURN_RETURN_REVIEW)


def legacy_owner(monkeypatch):
    s=h.Session();s.pb.frame_count=23670
    s.call();s.advance();s.advance();p=s.c.pending
    assert s.c.displacements==2 and p['frame']==23673
    s.pb.frame_count=23712;s.previous=[p['action']]
    s.call(raw=1,window=True,no_grid=True)
    for _ in range(16):s.call(raw=1,window=True,no_grid=True,previous=['a'])
    s.reward()
    for _ in range(128):s.call(window=True,no_grid=True)
    s.pb.frame_count=30832
    h.review(s.call(),'wait_budget_exhausted')
    c=s.c
    assert (c.last_frame,c.calls,c.waits,c.requests,c.displacements)==(30833,149,129,3,2)
    # Compatibility fixture: old code returned before setting closure history.
    # The real source ACK/pending/observed wild, resource delta and spent counters
    # above are retained. No successful controller or receipt is fabricated.
    c.closed_frame=c.closed_resources=c.closed_player=None;c.returned_world_seen=False
    for name in ('pending_ack_frame','wild_walk_evidence','closed_cancelled_walk',
                 'cancelled_walk_history','cancelled_walk_review_history','cancelled_walk_closure_review'):
        delattr(c,name)
    cap=deepcopy(REAL_CAPSULE)
    cap.update(original_step_id=s.step_id,baseline_sha256=b._review_sha(c.baseline),
        source_packet_sha256=b._review_sha(c.last_packet),source_progress_sha256=b._review_sha(c.last_packet[0]['progress']))
    monkeypatch.setattr(b,'TURN_RETURN_REVIEW',cap)
    return s,deepcopy(cap)


def review_owner(s,cap):
    return s.c.review_cancelled_turn_return(review_capsule=cap,source_evidence=deepcopy(cap['evidence']))


def fresh_closure(s,frames=40,**kwargs):
    # Reuse the helper's true SDK packets, but the bridge must receive the real
    # additive frame clock rather than retrocharging the old emulated interval.
    c=s.c;s.pb.frame_count+=frames-1
    s.now=c.last_now+frames/60-.05
    return s.call(**kwargs)


def test_named_review_preserves_all_original_fields_then_only_closes_with_budget_monotone(monkeypatch):
    s,cap=legacy_owner(monkeypatch);c=s.c;old=dict(c.__dict__);pending=c.pending;packet=c.last_packet
    out=review_owner(s,cap)
    assert out['available_actions']==['wait'] and c.error is None
    assert all(getattr(c,k) is v for k,v in old.items() if k!='error')
    assert c.pending is pending and c.last_packet is packet and c.waits==129 and c.calls==149
    assert c.cancelled_walk_review_history[0]['old_error']=='league_training_batch_wait_budget_exhausted'
    first=fresh_closure(s);assert not first['training_batch_complete'] and c.waits==130 and c.calls==150
    assert c.pending is pending and c.displacements==2 and c.requests==3
    final=fresh_closure(s)
    assert final['training_batch_complete'] and c.waits==130 and c.calls==151 and c.displacements==2
    assert c.started is old['started'] and c.last_now==pytest.approx(old['last_now']+80/60)
    assert c.cancelled_walk_closure_review['calls']==2 and c.cancelled_walk_closure_review['done'] is True
    assert final['training_batch_receipt']['cancelled_walk']['kind']=='reviewed_original_turn_before_displacement'


@pytest.mark.parametrize('bad',['capsule','evidence','owner','error','pending','executed','calls','waits',
    'requests','displacements','frame','packet','baseline','seen','suspended','returned','closed','clock',
    'history','active_allowance'])
def test_named_review_never_rebinds_unknown_or_changed_legacy_owner(bad,monkeypatch):
    s,cap=legacy_owner(monkeypatch);c=s.c;ev=deepcopy(cap['evidence'])
    if bad=='capsule':cap['historical_wild_sha256']='a'*64
    if bad=='evidence':ev['preflight_sha256']='b'*64
    if bad=='owner':c.owner='other'
    if bad=='error':c.error='league_training_batch_other_error'
    if bad=='pending':c.pending['player']=(28,8)
    if bad=='executed':c.pending['executed']=False
    if bad in ('calls','waits','requests','displacements'):setattr(c,bad,getattr(c,bad)+1)
    if bad=='frame':c.last_frame+=1
    if bad=='packet':c.last_packet[0]['progress']['money']-=1
    if bad=='baseline':c.baseline['party'][0]['exp']+=1
    if bad=='seen':c.seen_wild=False
    if bad=='suspended':c.suspended=False
    if bad=='returned':c.returned_world_seen=True
    if bad=='closed':c.closed_frame=30833
    if bad=='clock':c.last_now=c.started+601
    if bad=='history':c.cancelled_walk_review_history=[{'old_error':'used'}]
    if bad=='active_allowance':c.cancelled_walk_closure_review={}
    old=dict(c.__dict__)
    out=c.review_cancelled_turn_return(review_capsule=cap,source_evidence=ev)
    h.review(out);assert c.__dict__==old and c.error==old['error']


@pytest.mark.parametrize('bad',['position','resource','new_battle','unknown_ui','frames','calls','offer',
    'capsule','history','pending_identity'])
def test_review_allowance_is_finite_closure_only_and_never_offers_another_direction(bad,monkeypatch):
    s,cap=legacy_owner(monkeypatch);review_owner(s,cap);c=s.c
    if bad=='position':s.place(c.pending['expected'])
    if bad=='resource':s.pb.experience(0,c.last_packet[0]['progress']['party'][0]['exp']+1)
    if bad=='new_battle':out=fresh_closure(s,raw=1,window=True,no_grid=True)
    elif bad=='unknown_ui':out=fresh_closure(s,window=True,no_grid=True)
    elif bad=='frames':out=fresh_closure(s,frames=241)
    elif bad=='calls':c.cancelled_walk_closure_review['calls']=4;out=fresh_closure(s)
    elif bad=='offer':out=c.offer((28,7),30873)
    else:
        if bad=='capsule':c.cancelled_walk_closure_review['capsule']['first_wild_frame']+=1
        if bad=='history':c.cancelled_walk_review_history[0]['old_error']='changed'
        if bad=='pending_identity':c.pending=deepcopy(c.pending)
        out=fresh_closure(s)
    h.review(out);assert c.displacements==2 and c.requests==3 and c.pending is not None
    assert not bridge._COMPLETED


def test_real_review_authority_is_pinned_separately_from_artificial_progress():
    assert REAL_CAPSULE['original_step_id']=='root-calibration-game29-20261028-out-067'
    assert REAL_CAPSULE['source_packet_sha256']=='757bd2f50d6e129a47e7fedc7cddc903a34fada3f094f6df51306cd72573a2bf'
    assert REAL_CAPSULE['evidence']['preflight_sha256']=='e7f633c1021dc393419c18bc8c2ba31c1329fdbd85df48e0a432b524fb775123'
