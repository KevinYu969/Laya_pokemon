"""Synthetic wiring only: actual parent functions, no native/game execution."""
from copy import deepcopy
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from laya_pokemon import campaign_route as r,eevee37_dispatch_adapter as a,observation

ROOT=Path(__file__).resolve().parent.parent
assert Path(r.__file__).resolve()==(ROOT/'src/laya_pokemon/campaign_route.py').resolve()
h=importlib.import_module('test_training_parent_wiring')
assert Path(h.__file__).resolve()==(ROOT/'tests/test_training_parent_wiring.py').resolve()


@pytest.fixture
def ready(monkeypatch):
    h.clean.__wrapped__(monkeypatch)
    for name in ('_CONTEXT','_REQUEST','_ERROR','_HOOK'):monkeypatch.setattr(a,name,None)
    p=h.plan(batch=True);key=p['steps'][-1]['id'];state=h.state(frame=617241,batch=True)
    state.update(phase='strategy_review',review_reason='eevee37_trusted_dispatch_binding_missing')
    native=SimpleNamespace(frame_count=617241);baseline=object();pending={};packet=('original old review',)
    c=SimpleNamespace(error=None,calls=7,started=100.,last_now=104.,last_frame=617241,
        baseline=baseline,pending=pending,last_packet=packet)
    b=r.league_training_batch_bridge;binding=('original binding',)
    monkeypatch.setattr(b,'_CONTROLLERS',{key:c});monkeypatch.setattr(b,'_OWNERS',{key:native})
    monkeypatch.setattr(b,'_BINDINGS',{key:binding});monkeypatch.setattr(b,'_active',lambda:{key})
    monkeypatch.setattr(b,'applies',lambda sid,step:sid==key);monkeypatch.setattr(r,'_LEAGUE_FIELDS',(b,))
    monkeypatch.setattr(r.owned_field_medicine,'_active',lambda:set())
    peers={k:({key} if k=='league_training_batch' else set()) for k in r.owned_field_medicine.PEER_NAMES}
    monkeypatch.setattr(r,'_field_medicine_peers',lambda:peers)
    h.Readers(monkeypatch,state)
    return SimpleNamespace(p=p,key=key,s=state,native=native,c=c,b=b,binding=binding,peers=peers)


def existing_context(s,monkeypatch,complete=False):
    binding={'native_owner':s.native,'frame':s.s['frame']};proof=SimpleNamespace(complete=complete)
    owned=dict(native=s.native,controller=s.c,step_id=s.key,plan_sha=a._sha(s.p),binding=s.binding,
        observation={'binding':binding},proof=SimpleNamespace(original_controller=lambda _:proof))
    monkeypatch.setattr(a,'_CONTEXT',owned);monkeypatch.setattr(a,'_validate_context',lambda:owned)
    return owned,binding,proof


def test_ordinary_batch_fastpath_never_registers_reads_provider_or_changes_original_cost(ready,monkeypatch):
    s=ready;s.s['phase']='battle_menu';s.s.pop('review_reason')
    monkeypatch.setattr(a,'register_trusted_context',lambda *x,**k:pytest.fail('ordinary registration'))
    monkeypatch.setattr(a,'current_binding',lambda *x:pytest.fail('ordinary provider getter'))
    before=vars(s.c).copy()
    assert r._eevee37_owned_learning_context(s.native,s.s,s.p,s.key,{})==(None,None)
    assert vars(s.c)==before and a._CONTEXT is None


def test_same_frame_takeover_returns_direct_hint_without_reentering_or_replacing_original_batch(ready,monkeypatch):
    s=ready;hint={'phase':'learning_menu','available_actions':['a','wait'],'learning_request_id':'synthetic-request'}
    monkeypatch.setattr(a,'register_trusted_context',lambda *x,**k:True)
    monkeypatch.setattr(a,'install_actual_dispatch_hook',lambda *x:True)
    monkeypatch.setattr(a,'first_missing_binding_takeover',lambda *x:hint)
    monkeypatch.setattr(s.b,'context',lambda *x,**k:pytest.fail('same-frame batch reentry'))
    before=vars(s.c).copy()
    out,key=r._league_field_context(s.native,s.s,s.p,s.key,s.p['steps'][-1],['a'])
    assert out is hint and key==s.key and vars(s.c)==before


def test_fresh_clock_preserves_spent_and_only_original_completed_proof_is_consumed(ready,monkeypatch):
    s=ready;s.s['frame']=s.native.frame_count=617281;owned,binding,proof=existing_context(s,monkeypatch)
    calls=[]
    def consume(*args,**kw):calls.append((args,kw));return object()
    monkeypatch.setattr(s.b,'consume_owned_eevee37_learning',consume)
    before=vars(s.c).copy()
    hint,clock=r._eevee37_owned_learning_context(s.native,s.s,s.p,s.key,{})
    assert hint is None and clock==pytest.approx(104.+40/60) and not calls
    proof.complete=True
    hint,clock=r._eevee37_owned_learning_context(s.native,s.s,s.p,s.key,{})
    assert hint is None and len(calls)==1 and calls[0][1]['learning_binding'] is binding
    assert calls[0][1]['original_controller'] is s.c and calls[0][1]['original_binding'] is s.binding
    assert calls[0][1]['original_proof'] is proof and vars(s.c)==before


def test_attrition_uses_same_learning_clock_and_keeps_true_previous(ready,monkeypatch):
    s=ready;s.s['frame']=s.native.frame_count=617281;existing_context(s,monkeypatch)
    seen=[];previous=['a','wait']
    def close(*args,**kw):seen.append((args,kw));return {'phase':'training_batch_owned','available_actions':['wait']},s.key
    monkeypatch.setattr(s.b,'pre_attrition_closure_context',close)
    result=r.attrition_transition_context(s.native,s.s,s.p,s.key,
        {'review_reason':'party_attrition_requires_center'},previous=previous)
    assert result[1]==s.key and len(seen)==1 and seen[0][0][-1] is previous
    assert seen[0][1]['now']==pytest.approx(104.+40/60)


def test_true_completion_passes_actual_opaque_authority_then_unregisters_and_abort_cleans_same_frame(ready,monkeypatch):
    s=ready;events=[];authority=object();context=h.completed_context(s.s,s.p)
    monkeypatch.setattr(s.b,'completed_learning_authority',lambda native,key:authority if native is s.native else None)
    def project(plan,ctx,state,*,learning_authority):
        assert learning_authority is authority;events.append('project');return {'stored':'synthetic wiring'}
    def unregister(native):assert native is s.native;events.append('unregister');a._CONTEXT=None;return True
    monkeypatch.setattr(r.league_training_supervisor,'project_completed_batch',project)
    monkeypatch.setattr(a,'unregister_closed_context',unregister);a._CONTEXT={'synthetic':'original'}
    assert r._retain_training_batch_proof(s.s,s.p,(context,'complete'),native_owner=s.native)==(context,'complete')
    assert events==['project','unregister'] and a._CONTEXT is None
    a._CONTEXT={'synthetic':'original'};monkeypatch.setattr(s.b,'_active',lambda:set())
    aborted=({'phase':'campaign_review','training_batch_aborted':True},s.key)
    assert r._eevee37_closed_abort_cleanup(s.native,aborted) is aborted and a._CONTEXT is None


def test_attrition_foreign_peer_is_rejected_before_any_ui_or_closure(ready,monkeypatch):
    s=ready;existing_context(s,monkeypatch);s.peers['tm24_teaching']={'foreign'}
    monkeypatch.setattr(observation,'read_visible_text',lambda *x:pytest.fail('UI before complete mutex'))
    monkeypatch.setattr(s.b,'pre_attrition_closure_context',lambda *x,**k:pytest.fail('closure before complete mutex'))
    out,key=r.attrition_transition_context(s.native,s.s,s.p,s.key,
        {'review_reason':'party_attrition_requires_center'},previous=['wait'])
    assert key==s.key and out['phase']=='campaign_review' and out['available_actions']==['wait']
