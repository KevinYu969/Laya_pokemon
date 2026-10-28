"""Replay native pages to a lost final-A acknowledgement, then reviewed restore."""
from copy import deepcopy
import pytest
from tests import test_route22_checkpoint_resume as cold


def replay(remember_a=False,empty_intro_window=False):
    e=cold.env.__wrapped__();s=e.s;cold.adopted(e)
    def call(frame,previous):
        s.game.frame_count=frame;s.now=e.c.last_now+(frame-e.c.last_frame)/60
        return e.call(previous=previous)
    for page,frame in [(4,209),(5,337),(6,465),(7,593),(8,761)]:
        s.text=cold.fx.dialogue_text(*cold.fx.BEFORE[page]);assert call(frame,['a'])['available_actions']==['a','wait']
    s.text=cold.fx.dialogue_text(*cold.fx.BEFORE[9],arrow=False)
    assert call(889,['a'])['available_actions']==['wait']
    assert call(929,['wait'])['available_actions']==['a','wait']
    s.values.update(script=5,current=242);s.text=cold.fx.native_text()
    assert call(1057,['a'] if remember_a else ['wait'])['available_actions']==['wait']
    s.values['raw']=2
    if empty_intro_window:s.text=cold.fx.native_text(window=True)
    result=call(1177,['wait'])
    return e,result


@pytest.fixture
def paused():
    e,r=replay()
    assert r['review_reason']=='league_native_wait_native_dialogue_advanced_without_actual_a'
    return e


def marker(e):
    return dict(kind='route22_before_final_a_receipt_v1',source_frame=1177,offer_frame=929,ack_frame=1057,
        step_id=e.s.step['id'],source_steps_sha256='c'*64,source_review_sha256='d'*64)


def test_final_a_is_remembered_during_raw0_intro_before_raw2_starts():
    e,r=replay(remember_a=True)
    assert e.c.error is None and e.c.route22_dialogues['before']['pending']['executed']
    assert r['native_wait_reason']=='blank_trainer_intro'


def test_empty_trainer_window_waits_without_premature_battle_handoff():
    e,r=replay(remember_a=True,empty_intro_window=True)
    assert r['native_wait_reason']=='empty_trainer_intro_window'
    assert r['available_actions']==['wait'] and not e.c.intro_handoff


def test_reviewed_actual_ledger_receipt_preserves_counters_instance_and_error_history(paused):
    e=paused;c=e.c;before=(c.calls,c.elapsed,c.started,c.last_now,c.owner,c.packet)
    cap=marker(e);signal=c.packet[4]
    assert e.m.restore_reviewed_final_a(c,e.s.state,e.s.step,signal,cap) is None
    assert c.error is None and c.route22_dialogues['before']['pending']['executed']
    assert (c.calls,c.elapsed,c.started,c.last_now,c.owner,c.packet)==before
    assert c.reviewed_error_history[0]['error']=='native_dialogue_advanced_without_actual_a'
    assert c.reviewed_error_history[0]['calls']==before[0]
    c._review('new_unknown_error')
    assert e.m.restore_reviewed_final_a(c,e.s.state,e.s.step,signal,cap) is None
    assert c.error=='new_unknown_error' and len(c.reviewed_error_history)==1


@pytest.mark.parametrize('fault',['frame','offer','ack','hash','step','name','flag','script','pending','rows','progress'])
def test_foreign_or_unproved_receipts_never_unlock_review(paused,fault):
    e=paused;c=e.c;cap=marker(e);state=deepcopy(e.s.state);signal=deepcopy(c.packet[4])
    if fault=='frame':cap['source_frame']+=1
    elif fault=='offer':cap['offer_frame']-=1
    elif fault=='ack':cap['ack_frame']+=1
    elif fault=='hash':cap['source_steps_sha256']='unknown'
    elif fault=='step':cap['step_id']='other'
    elif fault=='name':signal['names']['rival']='OTHER'
    elif fault=='flag':signal['values']['event_164']=0
    elif fault=='script':signal['values']['script']=0
    elif fault=='pending':c.route22_dialogues['before']['pending']['final']=False
    elif fault=='rows':c.route22_dialogues['before']['pending']['rows']=('other',)
    else:state['progress']['money']+=1
    out=e.m.restore_reviewed_final_a(c,state,e.s.step,signal,cap)
    assert out['phase']=='campaign_review' and c.error=='native_dialogue_advanced_without_actual_a'
    assert not getattr(c,'reviewed_error_history',[]) and not c.route22_dialogues['before']['pending']['executed']
