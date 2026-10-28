"""Completed field receipt -> real EOF proof at low HP, with readonly SDK fixtures."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
import test_league_training_batch as h
from laya_pokemon import campaign_route as r


@pytest.fixture
def ready(monkeypatch):
    pb=h.FakePyBoy();pb.frame_count=100
    pb.memory.values[h.sdk.PARTY_MONS_ADDRESS+1]=0
    pb.memory.values[h.sdk.PARTY_MONS_ADDRESS+2]=30
    v=r.league_training_supervisor
    plan=h.plan();plan['steps']=plan['steps'][:1]
    plan.update(training_job=v.JOB,training_supervisor=r.league_training_proof.MARKER)
    def state():
        return dict(frame=pb.frame_count,location=dict(map_id=194,x=28,y=7),
                    progress=h.read_progress(pb),battle_state=h.read_battle_state(pb))
    context=dict(field_move_complete=True,field_move_kind='league-training-batch',
        training_batch_complete=True,training_batch_job=v.JOB,training_batch_owner_step=plan['steps'][0]['id'],
        source_commit=v.SOURCE_COMMIT,training_batch_outcome='complete_single_wild',
        training_batch_displacements=1,training_batch_receipt=dict(closed_frames=[99,100],wild_count=1,total_exp_gain=120))
    stored=v.project_completed_batch(plan,context,state())
    monkeypatch.setattr(r,'_TRAINING_BATCH_PROOFS',{plan['steps'][0]['id']:stored})
    monkeypatch.setattr(r,'_training_peers_clear',lambda:True)
    for name in ('_SESSIONS','_OWNERS','_ERRORS'):
        monkeypatch.setattr(r.league_training_proof,name,{})
    attr=dict(review_reason='party_attrition_requires_center',party_attrition=dict(fainted_party_indices=[]))
    return SimpleNamespace(pb=pb,plan=plan,state=state,stored=stored,attr=attr)


def test_completion_frame_waits_then_two_fresh_worlds_close_real_eof(ready):
    s=ready
    out,key=r._training_batch_eof_attrition_context(s.pb,s.state(),s.plan,'complete',s.attr)
    assert key=='complete' and out['available_actions']==['wait']
    assert out['training_completed_batch_attrition_wait'] and 'field_move_complete' not in out
    s.pb.frame_count+=40
    first,key=r._training_batch_eof_attrition_context(s.pb,s.state(),s.plan,'complete',s.attr)
    assert first['phase']=='league_training_wait' and key=='complete'
    s.pb.frame_count+=40
    final,key=r._training_batch_eof_attrition_context(s.pb,s.state(),s.plan,'complete',s.attr)
    assert final['review_reason']=='route_extension_required' and key=='complete'
    assert final['training_world_proof']['closed_frames']==[140,180]
    assert final['training_batch_proof']==s.stored
    r.league_training_supervisor.validate_closed_proof({**s.state(),**final})


@pytest.mark.parametrize('change',['missing','progress','step','fainted','future','peer'])
def test_missing_changed_fainted_future_or_owned_elsewhere_never_grants_wait(ready,monkeypatch,change):
    s=ready;state=s.state()
    if change=='missing':r._TRAINING_BATCH_PROOFS.clear()
    if change=='progress':state['progress']['money']+=1
    if change=='step':s.plan['steps'][0]['target']=[28,8]
    if change=='fainted':state['progress']['party'][0]['hp']=0
    if change=='future':state['frame']=99
    if change=='peer':monkeypatch.setattr(r,'_training_peers_clear',lambda:False)
    out,key=r._training_batch_eof_attrition_context(s.pb,state,s.plan,'complete',s.attr)
    assert key=='complete' and out['review_reason']=='training_completed_batch_attrition_proof_unverified'


def test_nonterminal_or_fainted_attrition_stays_with_original_gate(ready):
    s=ready
    assert r._training_batch_eof_attrition_context(s.pb,s.state(),s.plan,'training-001',s.attr) is None
    bad=deepcopy(s.attr);bad['party_attrition']['fainted_party_indices']=[0]
    assert r._training_batch_eof_attrition_context(s.pb,s.state(),s.plan,'complete',bad) is None
