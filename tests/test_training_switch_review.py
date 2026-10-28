"""Root binding and field-clock lifecycle; no private capsule, ROM or real input."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from laya_pokemon import training_switch_review as r,battle


@pytest.fixture
def case(monkeypatch):
    monkeypatch.setattr(r,'_CLOCKS',{})
    step=dict(id=r.STEP,mechanic='league_training_batch')
    plan=dict(training_job=r.JOB,steps=[step]);native=SimpleNamespace(frame_count=770673)
    state=dict(frame=770673,phase='strategy_review',review_reason='wild_retreat_pending_observation_or_owner_changed',
        progress=dict(party=[dict(species=7),dict(species=19)]),location=dict(map_id=194,x=28,y=7),battle_state={})
    text=dict(cells=[['source text']]);pending=dict(error='pending_observation_or_owner_changed')
    c=SimpleNamespace(started=100.,last_now=105.,last_frame=770673,calls=47,waits=0,requests=18,
        displacements=17,error=None,pending=dict(action='up'),last_packet=('original',),baseline=object(),complete=False)
    bridge=SimpleNamespace(MECHANIC='league_training_batch',_canonical=lambda x:r._canonical(x),
        _CONTROLLERS={r.STEP:c},_OWNERS={r.STEP:native},_BINDINGS={},_COMPLETED=set(),
        batch=SimpleNamespace(MAX_CALLS=1800,MAX_SECONDS=600),_active=lambda:{r.STEP})
    binding=(bridge.MECHANIC,bridge._canonical(step),r.JOB);bridge._BINDINGS[r.STEP]=binding
    fields=('started','last_now','last_frame','calls','waits','requests','displacements','error','pending','last_packet')
    cap=dict(original_field={k:deepcopy(getattr(c,k)) for k in fields},original_step_id=r.STEP,
        controller_identity=id(c),switch_identity=id(pending),source_location=state['location'],
        progress_sha256=r._canonical(state['progress']),text_sha256=r._canonical(text),
        original_switch_sha256=r._canonical(pending),original_deadline=10**12)
    peers={k:({r.STEP} if k=='league_training_batch' else set()) for k in r.shared.PEER_NAMES}
    monkeypatch.setattr(r,'_read_capsule',lambda:(cap,deepcopy(plan)))
    monkeypatch.setattr(battle,'_wild_retreat_switch',pending)
    calls=[]
    def migrate(*args,**kwargs):
        calls.append((args,kwargs));return dict(phase='battle_animation',available_actions=['wait'])
    monkeypatch.setattr(battle,'review_wild_switch770673',migrate,raising=False)
    def invoke():return r.context(native,state,plan,r.STEP,text,bridge=bridge,peers=peers)
    return SimpleNamespace(**locals())


def test_first_same_frame_handoff_preserves_all_original_field_spent_and_references(case):
    s=case;before={k:deepcopy(getattr(s.c,k)) for k in s.fields};baseline=s.c.baseline;pending=s.c.pending;packet=s.c.last_packet
    hint,clock=s.invoke();assert hint['available_actions']==['wait'] and clock is None
    assert len(s.calls)==1 and s.calls[0][1]['original_pending'] is s.pending
    assert all(getattr(s.c,k)==v for k,v in before.items())
    assert s.c.baseline is baseline and s.c.pending is pending and s.c.last_packet is packet


def test_field_clock_survives_child_switch_clear_until_real_batch_completion(case,monkeypatch):
    s=case;s.invoke();monkeypatch.setattr(battle,'_wild_retreat_switch',None)
    s.native.frame_count+=40;s.state['frame']+=40
    hint,clock=s.invoke();assert hint is None and clock==pytest.approx(105+40/60)
    assert s.c.last_now==105 and s.c.calls==47 and len(s.calls)==1
    assert r.applies(s.state,r.STEP)
    s.c.complete=True;s.bridge._COMPLETED.add(r.STEP)
    assert r.finish(s.native,r.STEP,s.state['frame'],bridge=s.bridge)
    assert not r.applies(s.state,r.STEP) and r._CLOCKS[r.STEP]['done'] is True


def test_rejected_child_migration_cannot_open_a_clock(case,monkeypatch):
    s=case;monkeypatch.setattr(battle,'review_wild_switch770673',lambda *a,**k:None)
    assert s.invoke()[0]['phase']=='campaign_review' and r._CLOCKS=={}
    assert s.c.calls==47 and s.c.last_now==105


def test_foreign_peer_owner_or_changed_spent_stops_before_child_mutation(case):
    s=case;s.peers['native_wait']={'foreign'}
    assert s.invoke()[0]['phase']=='campaign_review' and not s.calls
    s.peers['native_wait']=set();s.c.calls+=1
    assert s.invoke()[0]['phase']=='campaign_review' and not s.calls


def test_existing_clock_rejects_replaced_native_plan_or_baseline(case):
    s=case;s.invoke();s.native.frame_count+=40;s.state['frame']+=40
    baseline=s.c.baseline;s.c.baseline=object()
    assert s.invoke()[0]['phase']=='campaign_review'
    s.c.baseline=baseline;s.plan['changed']=True
    assert s.invoke()[0]['phase']=='campaign_review'


def test_unrelated_normal_frame_has_no_capsule_io_or_child_call(case,monkeypatch):
    s=case;s.state['frame']=770674
    monkeypatch.setattr(r,'_read_capsule',lambda:pytest.fail('normal frame read private capsule'))
    assert s.invoke()==(None,None) and not s.calls
