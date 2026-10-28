"""Self-contained prompt/review closure; no private evidence, live data or input."""
from copy import deepcopy
import importlib
from pathlib import Path

import pytest

h=importlib.import_module('test_eevee37_learning_ui');p=h.p
ROOT=Path(__file__).resolve().parent.parent
assert Path(h.__file__).resolve()==(ROOT/'tests/test_eevee37_learning_ui.py').resolve()
assert Path(p.__file__).resolve()==(ROOT/'src/laya_pokemon/eevee37_learning_proof.py').resolve()


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(p,'_ACTIVE',None);monkeypatch.setattr(p,'_DONE',{})
    monkeypatch.setattr(h.c,'_SESSION',None);monkeypatch.setattr(h.c.snorlax_harden_skip,'_SESSION',None)


def page(frame,arrow=True):
    entries=[(1,14,'EEVEE learned'),(1,16,'BITE!')]
    if arrow:entries.append((18,16,'▼'))
    return h.text(frame,*entries)


def changed(r):r.prog['party'][0]['moves'][0]=44;r.prog['party'][0]['pp'][0]=25


def failed_original():
    r=h.Run();r.frame=617241;r.to_and();assert r.ack();changed(r);r.frame=618081
    assert not r.call(page).get('learning_request_id')
    assert r.call(page)['learning_request_id'];assert r.ack(executed_frame=618201)
    r.frame=618201;r.call(page,advance=False)
    for _ in range(30):r.call(page)
    original=p._ACTIVE
    assert r.frame==619401 and original.error=='source_wait_budget_exhausted'
    assert original.learned_frames==[618121,618161] and original.pending['frame']==618161
    cap=dict(kind='reviewed_early_dismiss_ignored_619401_v1',job=p.JOB,source_frame=619401,
        original_step_id=r.fixed['owner_step'],original_error=original.error,
        closure_max_waits=8,closure_max_requests=2,source_progress=deepcopy(r.prog),
        source_evidence_sha256={k:'a'*64 for k in ('plan','review','state','summary')},
        plan_sha256='b'*64,original_deadline=123456789.)
    return r,original,cap


def migrate(r,proof,cap,**extra):
    return p.review_ignored_early_dismiss(r.binding(),cap,expected_capsule_sha256=p.sha(cap),
        original_proof=proof,original_core_session=proof.core_session,text=page(r.frame),progress=r.prog,**extra)


def test_future_complete_text_without_native_prompt_never_offers_dismiss_and_arrow_blink_only_waits():
    r=h.Run();r.to_and();assert r.ack();changed(r)
    for _ in range(2):assert r.call(lambda f:page(f,False))['learning_tactic']=='await_native_learned_prompt'
    assert p._ACTIVE.learned_frames==[]
    assert r.call(page)['learning_tactic']=='first_fresh_complete_learned_resources'
    request=r.call(page);assert request['learning_request_id']
    assert r.call(lambda f:page(f,False))['available_actions']==['wait']
    assert p._ACTIVE.error is None and r.call(page)['learning_request_id']==request['learning_request_id']


def test_named_migration_keeps_original_objects_cost_and_acks_then_produces_new_true_receipt_pair():
    r,proof,cap=failed_original();core=proof.core_session;acks=proof.acks;oldack=proof.dismiss_ack;pending=proof.pending
    cost=(proof.calls,proof.waits,proof.started);oldpair=list(proof.learned_frames)
    assert migrate(r,proof,cap)['available_actions']==['wait']
    assert p._ACTIVE is proof and proof.core_session is core and proof.acks is acks
    assert (proof.calls,proof.waits,proof.started)==cost and proof.error is None
    history=proof.dismiss_review_history[0]
    assert history['original_error']=='source_wait_budget_exhausted' and history['old_dismiss_ack']==oldack
    assert history['old_pending']==pending and history['old_learned_frames']==oldpair
    assert proof.dismiss_review['source_pending'] is pending and proof.dismiss_review['source_dismiss_ack'] is oldack
    assert r.call(page)['learning_tactic']=='first_fresh_complete_learned_resources'
    assert r.call(page)['learning_request_id'];assert r.ack()
    receipt=r.call(raw=0)['learning_receipt']
    assert receipt['observed_learned_frames']==[619441,619481]
    assert receipt['dismiss_ack']['requested_frame']==619481 and oldack in receipt['actual_dispatch_acks']
    assert receipt['reviewed_dismiss_history'][0]==history and proof.waits>=cost[1]
    from laya_pokemon import league_training_learning_receiver as receiver,league_training_batch as batch
    receiver.proof_semantics(receipt,batch.resources)


def test_invalid_capsule_or_original_core_or_progress_changes_nothing():
    r,proof,cap=failed_original();before=(proof.error,proof.calls,proof.waits,proof.started,proof.pending,proof.dismiss_ack)
    bad=deepcopy(cap);bad['source_frame']=619400
    assert migrate(r,proof,bad) is None
    assert p.review_ignored_early_dismiss(r.binding(),cap,expected_capsule_sha256=p.sha(cap),
        original_proof=proof,original_core_session={},text=page(r.frame),progress=r.prog) is None
    changed_progress=deepcopy(r.prog);changed_progress['money']+=1
    assert p.review_ignored_early_dismiss(r.binding(),cap,expected_capsule_sha256=p.sha(cap),
        original_proof=proof,original_core_session=proof.core_session,text=page(r.frame),progress=changed_progress) is None
    assert (proof.error,proof.calls,proof.waits,proof.started,proof.pending,proof.dismiss_ack)==before
    assert getattr(proof,'dismiss_review',None) is None and getattr(proof,'dismiss_review_history',[])==[]


def test_reviewed_unexecuted_request_stops_at_eight_closure_waits_without_refunding_old_waits():
    r,proof,cap=failed_original();spent=proof.waits;assert migrate(r,proof,cap)
    r.call(page);assert r.call(page)['learning_request_id']
    result=None
    for _ in range(9):
        result=r.call(page)
        if proof.error:break
    assert result['phase']=='strategy_review' and proof.error=='reviewed_dismiss_wait_budget_exhausted'
    assert proof.waits>spent and proof.dismiss_review['requests']==1 and proof.dismiss_review['waits']==9


def test_reviewed_native_ignored_again_allows_at_most_two_new_dismiss_requests():
    r,proof,cap=failed_original();original_acks=len(proof.acks);assert migrate(r,proof,cap)
    r.call(page);r.call(page);assert r.ack()
    assert r.call(page)['learning_tactic']=='reviewed_dismiss_retry_fresh_prompt_required'
    r.call(page);assert r.call(page)['learning_request_id'];assert r.ack()
    for _ in range(3):assert not r.call(page).get('learning_request_id')
    assert proof.dismiss_review['requests']==2 and len(proof.acks)==original_acks+2


def test_original_call_and_frame_limits_still_override_review_closure_allowance():
    r,proof,cap=failed_original();calls=proof.calls;proof.calls=p.MAX_CALLS
    assert migrate(r,proof,cap) is None and proof.error=='source_wait_budget_exhausted'
    proof.calls=calls;assert migrate(r,proof,cap)
    proof.calls=p.MAX_CALLS
    assert r.call(page)['phase']=='strategy_review' and proof.error=='frame_or_call_budget_exhausted'
    assert proof.calls>p.MAX_CALLS and proof.dismiss_review_history[0]['spent']['calls']==calls
