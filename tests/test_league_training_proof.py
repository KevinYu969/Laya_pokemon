"""純JSON合成驗證真EOF controller與既有supervisor validator；不開遊戲。"""
from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest

HERE=Path(__file__).resolve().parent
if HERE.name=="staged-training-proof-20261028" and HERE.parent.name==".local":
    ROOT=HERE.parent.parent;SOURCE=HERE/"league_training_proof.py"
    V_SOURCE=ROOT/".local/staged-league-training-supervisor-20261028/league_training_supervisor.py"
    spec=importlib.util.spec_from_file_location("_exact_proof_supervisor_validation",V_SOURCE)
    validation=importlib.util.module_from_spec(spec);spec.loader.exec_module(validation)
elif HERE.name=="tests":
    ROOT=HERE.parent;SOURCE=ROOT/"src/laya_pokemon/league_training_proof.py"
    validation=importlib.import_module("laya_pokemon.league_training_supervisor")
    assert Path(validation.__file__).resolve()==ROOT/"src/laya_pokemon/league_training_supervisor.py"
else:raise RuntimeError("只接受精確stage或formal tests路徑")
spec=importlib.util.spec_from_file_location("laya_pokemon._exact_training_eof_proof_tests",SOURCE)
proof=importlib.util.module_from_spec(spec);spec.loader.exec_module(proof)
assert Path(proof.__file__).resolve()==SOURCE.resolve()


def progress():
    return dict(profile="gen1-wrapper-ram-progress-v1-unvalidated",party_read_valid=True,
        initialization_candidate=True,party_count=6,player_name_raw="KEVIN",badges_raw=255,
        money=12345,inventory=[],party=[dict(species=species,species_name=validation.NAMES[species],
        level=level,exp=level**3,hp=120,max_hp=120,status=0,moves=[33,0,0,0],pp=[35,0,0,0])
        for species,level in [(19,41),(132,41),(102,35),(154,35),(35,37),(7,36)]])


def plan(batch=False):
    step=(dict(id="training-tail",kind="interact",mechanic="league_training_batch",map_id=194,
        target=[28,7],training_intent=deepcopy(validation.BATCH_INTENT)) if batch
        else dict(id="normal-nurse-tail",kind="heal",map_id=174,target=[7,7],face="up",require_full_pp=True))
    return dict(mode="league_campaign",training_job=proof.JOB,training_supervisor=proof.MARKER,steps=[step])


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for key in ("_SESSIONS","_OWNERS","_ERRORS"):monkeypatch.setattr(proof,key,{})


class Session:
    def __init__(self,*,batch=False):
        self.plan=plan(batch);self.owner=object();self.frame=100;self.p=progress();self.stored=None
        self.loc=dict(map_id=194,x=28,y=8) if batch else dict(map_id=174,x=7,y=7)
        if batch:
            context=dict(field_move_complete=True,field_move_kind="league-training-batch",training_batch_complete=True,
                training_batch_job=proof.JOB,training_batch_owner_step="training-tail",source_commit=proof.SOURCE_COMMIT,
                training_batch_outcome="complete_single_wild",training_batch_displacements=1,
                training_batch_receipt=dict(closed_frames=[90,91],wild_count=1,total_exp_gain=120))
            self.stored=validation.project_completed_batch(self.plan,context,dict(frame=91,location=self.loc,progress=self.p))
    @property
    def c(self):return proof._SESSIONS[(proof.JOB,self.plan["steps"][-1]["id"])]
    def call(self,*,same=False,advance=1,peers_clear=True,now=None,busy=False,window=False,
             state_change=None,text_change=None,grid_change=None,movement_change=None,validation_override=None):
        if not same:self.frame+=advance
        f=self.frame;state=dict(frame=f,location=deepcopy(self.loc),progress=deepcopy(self.p),
            battle_state=dict(raw=0,kind="none",active=False,observation_frame=f),phase="unclassified")
        text=dict(profile="gen1-visible-tile-text-candidates-v1-unvalidated",read_valid=True,
            alignment_verified=True,read_error=None,window_visible=window,cells=[[" "]*20 for _ in range(18)])
        visible=[[x,0] for x in range(11)]+[[self.loc["x"],self.loc["y"]]]
        grid=dict(observation_frame=f,verified_location=[self.loc[k] for k in ("map_id","x","y")],
            screen_cells_verified=12,visible_verified_cells=visible,
            tiles=[[32]*30 for _ in range(18)],walkable=[[1]*30 for _ in range(18)])
        movement=dict(profile="gen1-arrow-movement-source-v1",source_commit=proof.SOURCE_COMMIT,
            read_valid=True,observation_frame=f,spinning=False,simulated_remaining=0,joy_ignore=0,
            walk_counter=int(busy),movement_flags=0)
        if state_change:state_change(state)
        if text_change:text_change(text)
        if grid_change:grid_change(grid)
        if movement_change:movement_change(movement)
        self.last=deepcopy((state,text,grid,movement))
        return proof.context(state,self.plan,text=text,grid=grid,movement=movement,native_owner=self.owner,
            peers_clear=peers_clear,full_party_healed=validation.full_party(state["progress"]["party"]),
            validation=validation if validation_override is None else validation_override,stored_batch_proof=self.stored,now=now)


def review(out,fragment=None):
    assert out["phase"]=="campaign_review" and out["available_actions"]==["wait"]
    if fragment:assert fragment in out["review_reason"],out


def reload_proof():
    spec=importlib.util.spec_from_file_location(proof.__name__,SOURCE);spec.loader.exec_module(proof)


def test_two_actual_fresh_world_packets_produce_supervisor_accepted_exact_proof():
    s=Session();first=s.call();assert first["phase"]=="league_training_wait"
    frame=s.c.first_frame;assert "training_world_proof" not in first
    final=s.call();review(final,"route_extension_required")
    state,text,grid,movement=s.last;published={**state,**final}
    validation.validate_closed_proof(published)
    payload=final["training_world_proof"]
    assert payload["closed_frames"]==[frame,s.frame] and payload["text"]==text and payload["grid"]==grid
    assert payload["movement"]==movement and payload["progress_sha256"]==validation.canonical_sha(state["progress"])
    assert payload["full_party_healed"] is True


def test_same_frame_never_counts_second_world_and_modified_same_frame_is_sticky():
    s=Session();s.call();first=s.c.first_frame
    assert s.call(same=True)["phase"]=="league_training_wait" and s.c.first_frame==first
    review(s.call(same=True,state_change=lambda st:st["progress"].update(money=999)),"same_frame_conflict")
    reason=s.c.error;review(s.call());assert s.c.error==reason


def test_true_frame_budget_survives_busy_samples_and_cannot_be_refunded():
    s=Session();s.call();c=s.c
    assert s.call(busy=True,advance=1800)["phase"]=="league_training_wait"
    assert c.first_frame is None and c.elapsed_frames==1800
    reload_proof();assert s.c is c
    review(s.call(busy=True,advance=1801),"true_frame_or_call_budget")
    assert c.elapsed_frames==3601


def test_120_calls_bound_even_without_frame_progress():
    s=Session();s.call()
    for _ in range(proof.MAX_CALLS):out=s.call(same=True)
    review(out,"call_budget");assert s.c.elapsed_frames==0


def test_known_busy_and_valid_ui_clear_only_pair_candidate_not_total_budget():
    s=Session();s.call();assert s.c.first_frame
    out=s.call(busy=True);assert out["phase"]=="league_training_wait" and s.c.first_frame is None
    s.call();out=s.call(window=True);assert out["phase"]=="league_training_wait" and s.c.first_frame is None
    s.call();out=s.call();review(out,"route_extension_required")
    assert s.c.elapsed_frames==5


@pytest.mark.parametrize("mutate,fragment",[
    (lambda s:s.p["party"][0].update(hp=119),"progress_changed"),
    (lambda s:s.loc.update(x=8),"location_or_progress_changed"),
])
def test_closed_pair_position_or_progress_drift_requires_review(mutate,fragment):
    s=Session();s.call();mutate(s);review(s.call(),fragment)


@pytest.mark.parametrize("kind,mutate",[
    ("state",lambda st:st.update(frame=True)),
    ("state",lambda st:st["battle_state"].update(raw=255,kind="lost_transition",active=True)),
    ("state",lambda st:st["battle_state"].update(observation_frame=1)),
    ("state",lambda st:st["progress"]["party"][0].update(hp=0)),
    ("text",lambda t:t.update(read_valid=False)),
    ("text",lambda t:t.update(profile="foreign")),
    ("grid",lambda g:g.update(observation_frame=True)),
    ("grid",lambda g:g["visible_verified_cells"].pop()),
    ("movement",lambda m:m.update(read_valid=False)),
    ("movement",lambda m:m.update(joy_ignore=1)),
    ("movement",lambda m:m.update(movement_flags=128,spinning=False)),
])
def test_unknown_packets_stop_sticky_instead_of_making_blank_proof(kind,mutate):
    s=Session();kwargs={kind+"_change":mutate};out=s.call(**kwargs)
    review(out);assert "training_world_proof" not in out
    reason=s.c.error;review(s.call());assert s.c.error==reason


@pytest.mark.parametrize("bad_now",[False,float("nan"),float("inf"),-1.,9999.])
def test_wallclock_or_unknown_clock_cannot_replace_true_frame_clock(bad_now):
    s=Session();review(s.call(now=bad_now),"frame_clock_invalid")


def test_frame_rollback_is_sticky():
    s=Session();s.call();s.frame=1;review(s.call(),"frame_clock_invalid")


def test_marker_mismatch_yields_none_without_registry_or_validator_work():
    s=Session();s.plan.pop("training_supervisor")
    assert not proof.applies(s.plan)
    assert s.call(validation_override=object()) is None and not proof._SESSIONS and not proof._OWNERS


def test_active_owner_cannot_remove_marker_change_tail_or_native_session():
    s=Session();s.call();c=s.c;s.plan.pop("training_supervisor")
    assert proof.applies(s.plan)
    review(s.call(),"marker_or_job_removed");assert s.c is c


def test_peer_mutex_fails_before_any_eof_world_capture():
    s=Session();review(s.call(peers_clear=False),"active_field_or_legacy_owner")
    assert not proof._SESSIONS
    review(s.call(peers_clear=True),"active_field_or_legacy_owner")


def test_native_owner_and_full_plan_binding_are_immutable():
    s=Session();s.call();c=s.c;s.owner=object()
    review(s.call(),"native_owner_changed");assert s.c is c


@pytest.mark.parametrize("owner",[None,True,"same-job"])
def test_native_owner_must_be_actual_session_object(owner):
    s=Session();s.owner=owner;review(s.call(),"native_owner_unknown")


def test_modified_plan_and_foreign_tail_are_sticky():
    s=Session();s.call();s.plan["label"]="changed"
    review(s.call(),"immutable_plan_binding")


def test_mode_error_cannot_be_cleared_by_restoring_plan_mode():
    s=Session();s.call();s.plan["mode"]="battle_recovery"
    review(s.call(),"campaign_mode_changed");s.plan["mode"]="league_campaign"
    review(s.call(),"campaign_mode_changed")


def test_peer_error_before_capture_cannot_be_bypassed_with_new_tail_id():
    s=Session();review(s.call(peers_clear=False),"active_field_or_legacy_owner")
    s.plan["steps"][-1]["id"]="foreign-tail"
    review(s.call(),"active_field_or_legacy_owner")


def test_reload_preserves_original_sample_identity_call_frame_budget_and_error():
    s=Session();s.call();c=s.c;sample=c.first_progress_sha;spent=(c.calls,c.elapsed_frames,c.first_frame)
    reload_proof();assert s.c is c and c.first_progress_sha==sample and (c.calls,c.elapsed_frames,c.first_frame)==spent
    out=s.call();review(out,"route_extension_required")
    reload_proof();review(s.call(),"completed_eof_reentered")


def test_real_batch_projection_is_attached_unchanged_not_inferred_at_eof():
    s=Session(batch=True);original=deepcopy(s.stored);s.call();final=s.call()
    review(final,"route_extension_required");assert final["training_batch_proof"]==original
    assert s.stored==original


def test_batch_eof_without_prior_true_completion_projection_never_infers_success():
    s=Session(batch=True);s.stored=None;s.call();review(s.call(),"stored_batch_proof")


def test_batch_projection_progress_mismatch_is_caught_without_raising_into_game():
    s=Session(batch=True);s.p["party"][0]["hp"]-=1;s.call();out=s.call()
    review(out,"stored_batch_proof")


def test_validator_exception_is_translated_to_sticky_review():
    s=Session();bad=SimpleNamespace(**{k:getattr(validation,k) for k in ("validate_party","full_party","validate_closed_proof","eof_batch_proof")})
    def throws(state):raise RuntimeError("synthetic_validation_exception")
    bad.validate_closed_proof=throws;s.call(validation_override=bad)
    review(s.call(validation_override=bad),"synthetic_validation_exception")


def test_pure_context_has_no_file_tick_or_input_operations(monkeypatch):
    s=Session();s.call()
    def forbidden(*args,**kwargs):raise AssertionError("context不允許I/O")
    monkeypatch.setattr("builtins.open",forbidden)
    out=s.call();review(out,"route_extension_required")
