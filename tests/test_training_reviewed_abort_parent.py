"""Parent preflight only; synthetic references, no private evidence or emulator."""
from types import SimpleNamespace

import pytest
from laya_pokemon import campaign_route as r, observation


@pytest.fixture
def ready(monkeypatch):
    b=r.league_training_batch_bridge;key=r._TRAINING_ESCAPE_STEP
    native=SimpleNamespace(frame_count=160497)
    c=SimpleNamespace(error='league_training_batch_single_wild_reward_or_pp_bound_unverified',
                      pending={},last_packet=())
    plan={'test':'original plan'};binding=('original',)
    cap=dict(plan_sha256=r.owned_field_medicine.canonical_sha256(plan),
             controller_identity=id(c),native_identity=id(native))
    peers={k:({key} if k=='league_training_batch' else set()) for k in r.owned_field_medicine.PEER_NAMES}
    for name,value in [('_CONTROLLERS',{key:c}),('_OWNERS',{key:native}),('_BINDINGS',{key:binding}),('_REVIEWED_ABORTS',{})]:
        monkeypatch.setattr(b,name,value)
    monkeypatch.setattr(b,'_active',lambda:{key})
    monkeypatch.setattr(r,'_field_medicine_peers',lambda:peers)
    monkeypatch.setattr(r.owned_field_medicine,'_active',lambda:set())
    monkeypatch.setattr(r,'_LEAGUE_FIELDS',(b,))
    monkeypatch.setattr(r,'_read_training_escape_review_capsule',lambda:cap)
    monkeypatch.setattr(observation,'read_visible_text',lambda _: {'fresh':'text'})
    monkeypatch.setattr(r,'read_world_grid',lambda *_: {'fresh':'grid'})
    received=[]
    def delegate(*args,**kwargs):
        received.append((args,kwargs));return {'phase':'training_batch_owned','available_actions':['wait']},key
    monkeypatch.setattr(b,'reviewed_abort',delegate)
    state=dict(frame=160497,location=dict(map_id=194,x=28,y=8))
    return SimpleNamespace(b=b,key=key,native=native,c=c,plan=plan,cap=cap,peers=peers,
                           binding=binding,state=state,received=received)


def test_parent_passes_the_original_objects_to_the_review_api(ready):
    s=ready;out,key=r._training_escape_abort_review_context(s.native,s.state,s.plan,s.key)
    assert key==s.key and out['phase']=='training_batch_owned'
    args,kw=s.received[0]
    assert args[0] is s.native and args[1] is s.state and args[2] is s.plan and args[6] is s.cap
    assert kw['original_controller'] is s.c and kw['original_binding'] is s.binding
    assert kw['original_pending'] is s.c.pending and kw['original_last_packet'] is s.c.last_packet


def test_foreign_peer_is_rejected_before_evidence_or_native_reads(ready,monkeypatch):
    s=ready;s.peers[next(k for k in s.peers if k!='league_training_batch')]={'foreign'}
    monkeypatch.setattr(r,'_read_training_escape_review_capsule',lambda:pytest.fail('read before peers cleared'))
    out,_=r._training_escape_abort_review_context(s.native,s.state,s.plan,s.key)
    assert out['review_reason'].endswith('owner_or_peers_unverified') and not s.received


@pytest.mark.parametrize('change',['plan','native','frame','state'])
def test_unbound_plan_native_frame_or_opaque_state_never_reaches_review_api(ready,change):
    s=ready;state=s.state;plan=s.plan
    if change=='plan':plan={'test':'changed'}
    if change=='native':s.cap['native_identity']+=1
    if change=='frame':s.native.frame_count+=1
    if change=='state':state=object()
    out,_=r._training_escape_abort_review_context(s.native,state,plan,s.key)
    assert out['phase']=='campaign_review' and not s.received


def test_inactive_case_does_not_require_any_private_files(ready,monkeypatch):
    s=ready;s.b._CONTROLLERS.clear()
    monkeypatch.setattr(r,'_read_training_escape_review_capsule',lambda:pytest.fail('inactive private read'))
    assert r._training_escape_abort_review_context(s.native,object(),{},'unrelated') is None
