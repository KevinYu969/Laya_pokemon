"""獨立測formal parent真函式；合成reader/完成結果只驗接線，不稱實機交易。"""
from copy import deepcopy
import importlib
from pathlib import Path
from types import SimpleNamespace
import pytest
from laya_pokemon import campaign_route as route,observation,rocket_movement

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent if HERE.name=="staged-training-parent-audit-20261028" else HERE.parent
assert HERE.name in ("staged-training-parent-audit-20261028","tests")
assert Path(route.__file__).resolve()==ROOT/"src/laya_pokemon/campaign_route.py"
proof=route.league_training_proof
supervisor=route.league_training_supervisor

LEGACY_NAMES=("battle_medicine_bridge","trainer_medicine_ui_bridge","mansion_secret_key_bridge",
    "mansion_statue_bridge","mansion_transition_ready","mansion_native_landing","route21_water_bridge",
    "pallet_surf_bridge","fly_pallet_bridge","fly_viridian_bridge","safari_entry","hm_teaching_bridge",
    "vending_bridge","saffron_guard_bridge","silph_card_bridge","lapras_bridge","player_pc_bridge",
    "cinnabar_purchase_bridge","campaign_transactions")


def progress():
    return dict(profile="gen1-wrapper-ram-progress-v1-unvalidated",party_read_valid=True,
        initialization_candidate=True,party_count=6,player_name_raw="KEVIN",badges_raw=255,
        money=12345,inventory=[],party=[dict(species=species,species_name=supervisor.NAMES[species],
        level=level,exp=level**3,hp=120,max_hp=120,status=0,moves=[33,0,0,0],pp=[35,0,0,0])
        for species,level in [(19,41),(132,41),(102,35),(154,35),(35,37),(7,36)]])


def plan(batch=False):
    step=(dict(id="batch-tail",kind="interact",mechanic="league_training_batch",map_id=194,target=[28,7],
        training_intent=deepcopy(supervisor.BATCH_INTENT)) if batch
        else dict(id="center-tail",kind="heal",map_id=174,target=[7,7],face="up",require_full_pp=True))
    return dict(mode="league_campaign",source_commit=proof.SOURCE_COMMIT,training_job=proof.JOB,
        training_supervisor=proof.MARKER,resume_revision=1,steps=[step])


def state(frame=100,batch=False):
    return dict(frame=frame,phase="unclassified",location=dict(map_id=194 if batch else 174,x=28 if batch else 7,y=8 if batch else 7),
        progress=progress(),battle_state=dict(raw=0,kind="none",active=False,observation_frame=frame),
        observation_profile="gen1-visible-tile-text-candidates-v1-unvalidated",visible_text_candidates=[])


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for module in [getattr(route,n) for n in LEGACY_NAMES]+list(route._LEAGUE_FIELDS):
        for key,value in (("_BINDINGS",{}),("_CONTROLLERS",{}),("_COMPLETED",set()),("_ERRORS",{}),("_OWNERS",{})):
            if hasattr(module,key):monkeypatch.setattr(module,key,value)
    for key in ("_SESSIONS","_OWNERS","_ERRORS"):monkeypatch.setattr(proof,key,{})
    for key in ("_FIELD_CONTROLLERS","_GYM_CONTROLLERS","_TRAINING_BATCH_PROOFS"):
        monkeypatch.setattr(route,key,{})
    monkeypatch.setattr(route,"_LAST_ATTEMPT",None)
    monkeypatch.setattr(route.capture_transaction,"_SESSIONS",{})
    monkeypatch.setattr(route.league_native_wait,"_WAITS",{})
    monkeypatch.setattr(route.safari_entry,"_RUN_CONTROLLER",None)


class Readers:
    def __init__(self,monkeypatch,current):
        self.current=current;self.calls=[]
        monkeypatch.setattr(observation,"read_visible_text",self.text)
        monkeypatch.setattr(route,"read_world_grid",self.grid)
        monkeypatch.setattr(rocket_movement,"read_rocket_movement",self.movement)
    def text(self,pb):
        self.calls.append(("text",pb));return dict(profile="gen1-visible-tile-text-candidates-v1-unvalidated",
            read_valid=True,alignment_verified=True,read_error=None,window_visible=False,cells=[[" "]*20 for _ in range(18)])
    def grid(self,pb,loc):
        self.calls.append(("grid",pb,loc));return dict(observation_frame=self.current["frame"],
            verified_location=[loc[k] for k in ("map_id","x","y")],screen_cells_verified=12,
            visible_verified_cells=[[x,0] for x in range(11)]+[[loc["x"],loc["y"]]],
            tiles=[[32]*30 for _ in range(18)],walkable=[[1]*30 for _ in range(18)])
    def movement(self,pb,*,observation_frame):
        self.calls.append(("movement",pb,observation_frame));return dict(profile="gen1-arrow-movement-source-v1",
            source_commit=proof.SOURCE_COMMIT,read_valid=True,observation_frame=observation_frame,
            spinning=False,simulated_remaining=0,joy_ignore=0,walk_counter=0,movement_flags=0)


def review(result):
    context,next_id=result
    assert context["phase"]=="campaign_review" and context["available_actions"]==["wait"]
    return context,next_id


def completed_context(s,p):
    return dict(phase="training_batch_complete",objective="Wait.",available_actions=["wait"],
        field_move_complete=True,field_move_kind="league-training-batch",training_batch_complete=True,
        training_batch_job=proof.JOB,training_batch_owner_step=p["steps"][-1]["id"],source_commit=proof.SOURCE_COMMIT,
        training_batch_outcome="complete_single_wild",training_batch_displacements=1,
        training_batch_receipt=dict(closed_frames=[s["frame"]-1,s["frame"]],wild_count=1,total_exp_gain=120))


@pytest.mark.parametrize("branch",["normal_switch","pre_attrition"])
def test_both_true_complete_branches_retain_exact_projection_and_true_previous(monkeypatch,branch):
    pb=object();s=state(batch=True);p=plan(batch=True);readers=Readers(monkeypatch,s)
    ctx=completed_context(s,p);prior=["down","a","wait"];seen=[];batch=route.league_training_batch_bridge
    monkeypatch.setattr(batch,"_active",lambda:{"batch-tail"})
    def completion(*args):
        seen.append(args);assert args[-1] is prior
        return ctx,"complete"
    if branch=="normal_switch":
        monkeypatch.setattr(batch,"context",completion)
        result=route.switch_context(pb,s,p,"batch-tail",prior)
    else:
        monkeypatch.setattr(batch,"pre_attrition_closure_context",completion)
        result=route.attrition_transition_context(pb,s,p,"batch-tail",dict(review_reason="party_attrition_requires_center"),previous=prior)
    assert result==(ctx,"complete") and len(seen)==1
    expected=supervisor.project_completed_batch(p,ctx,s)
    assert route._TRAINING_BATCH_PROOFS=={"batch-tail":expected}
    assert all(call[1] is pb for call in readers.calls)


def test_projection_exception_is_review_and_never_claims_complete(monkeypatch):
    s=state(batch=True);p=plan(batch=True);ctx=completed_context(s,p)
    def broken(*args):raise ValueError("synthetic projection validation failed")
    monkeypatch.setattr(supervisor,"project_completed_batch",broken)
    out,next_id=review(route._retain_training_batch_proof(s,p,(ctx,"complete")))
    assert not out.get("field_move_complete") and next_id=="complete" and route._TRAINING_BATCH_PROOFS=={}


def test_existing_projection_cannot_be_replaced_by_changed_completion(monkeypatch):
    s=state(batch=True);p=plan(batch=True);ctx=completed_context(s,p)
    route._retain_training_batch_proof(s,p,(ctx,"complete"));original=deepcopy(route._TRAINING_BATCH_PROOFS)
    s["progress"]["money"]+=1
    review(route._retain_training_batch_proof(s,p,(ctx,"complete")))
    assert route._TRAINING_BATCH_PROOFS==original


def test_waypoint_eof_produces_two_fresh_exact_supervisor_accepted_packets(monkeypatch):
    pb=object();p=plan();s=state();readers=Readers(monkeypatch,s)
    first,next_id=route.waypoint(pb,s,p,"complete",["wait"])
    assert first["phase"]=="league_training_wait" and first["available_actions"]==["wait"] and next_id=="complete"
    s["frame"]+=1;s["battle_state"]["observation_frame"]=s["frame"]
    final,next_id=route.waypoint(pb,s,p,"complete",["wait"])
    assert next_id=="complete" and final["review_reason"]=="route_extension_required"
    supervisor.validate_closed_proof({**s,**final})
    assert final["training_world_proof"]["closed_frames"]==[100,101]
    assert [c[0] for c in readers.calls]==["text","grid","movement"]*2


def test_unmarked_eof_preserves_original_route_review_without_reading_ui(monkeypatch):
    s=state();p=plan();p.pop("training_supervisor")
    def trap(*args,**kwargs):pytest.fail("unmarked EOF不得讀UI")
    monkeypatch.setattr(observation,"read_visible_text",trap)
    context,next_id=route.waypoint(object(),s,p,"complete",[])
    assert context["review_reason"]=="route_extension_required" and next_id=="complete"
    assert "training_world_proof" not in context and proof._SESSIONS=={}


@pytest.mark.parametrize("entry",["field","switch"])
@pytest.mark.parametrize("change",["marker","job","tail","plan","session"])
def test_active_eof_changed_owner_or_plan_refused_before_ui(monkeypatch,entry,change):
    pb=object();s=state();p=plan();Readers(monkeypatch,s)
    route._training_eof_context(pb,s,p)
    if change=="marker":p.pop("training_supervisor")
    if change=="job":p["training_job"]="foreign"
    if change=="tail":p["steps"][-1]["id"]="foreign"
    if change=="plan":p["label"]="changed"
    if change=="session":pb=object()
    def trap(*args,**kwargs):pytest.fail("active EOF衝突必須先於UI")
    monkeypatch.setattr(observation,"read_visible_text",trap);monkeypatch.setattr(route,"read_world_grid",trap)
    result=(route.field_context(pb,s,p,"complete") if entry=="field" else route.switch_context(pb,s,p,"complete",[]))
    _,next_id=review(result);assert next_id=="complete"


@pytest.mark.parametrize("group",["legacy","new","capture","safari","native","gym","field","unknown_capture","unknown_legacy"])
def test_all_peer_groups_block_eof_world_capture(monkeypatch,group):
    if group=="legacy":monkeypatch.setattr(route.player_pc_bridge,"_BINDINGS",{"peer":{}})
    if group=="new":monkeypatch.setattr(route.victory_strength_bridge,"_BINDINGS",{"peer":{}})
    if group=="capture":monkeypatch.setattr(route.capture_transaction,"_SESSIONS",{"peer":{"done":False}})
    if group=="safari":monkeypatch.setattr(route.safari_entry,"_RUN_CONTROLLER",object())
    if group=="native":monkeypatch.setattr(route.league_native_wait,"_WAITS",{"peer":SimpleNamespace(waiting=True)})
    if group=="gym":monkeypatch.setattr(route,"_GYM_CONTROLLERS",{"peer":SimpleNamespace(state="active")})
    if group=="field":monkeypatch.setattr(route,"_FIELD_CONTROLLERS",{"peer":SimpleNamespace(stage="active")})
    if group=="unknown_capture":monkeypatch.setattr(route.capture_transaction,"_SESSIONS",None)
    if group=="unknown_legacy":monkeypatch.setattr(route.player_pc_bridge,"_BINDINGS",None)
    assert route._training_peers_clear() is False
    s=state();p=plan();Readers(monkeypatch,s)
    out=route._training_eof_context(object(),s,p)
    assert out["phase"]=="campaign_review" and "training_world_proof" not in out
    assert proof._SESSIONS=={}


def test_completed_peer_records_are_not_mistaken_for_active_owners(monkeypatch):
    monkeypatch.setattr(route.player_pc_bridge,"_BINDINGS",{"done":{}})
    monkeypatch.setattr(route.player_pc_bridge,"_COMPLETED",{"done"})
    monkeypatch.setattr(route.capture_transaction,"_SESSIONS",{"done":{"done":True}})
    monkeypatch.setattr(route,"_FIELD_CONTROLLERS",{"done":SimpleNamespace(stage="complete")})
    monkeypatch.setattr(route,"_GYM_CONTROLLERS",{"done":SimpleNamespace(state="complete")})
    assert route._training_peers_clear() is True


def test_eof_peer_check_precedes_reader_calls(monkeypatch):
    monkeypatch.setattr(route.player_pc_bridge,"_BINDINGS",{"peer":{}})
    def trap(*args,**kwargs):pytest.fail("peer active時不得先讀EOF UI")
    monkeypatch.setattr(observation,"read_visible_text",trap)
    out=route._training_eof_context(object(),state(),plan())
    assert out["phase"]=="campaign_review" and out["available_actions"]==["wait"]


@pytest.mark.parametrize("entry",["field","switch"])
def test_new_legacy_owner_during_active_eof_is_refused_at_entry_before_ui(monkeypatch,entry):
    pb=object();s=state();p=plan();Readers(monkeypatch,s);route._training_eof_context(pb,s,p)
    monkeypatch.setattr(route.mansion_transition_ready,"_BINDINGS",{"foreign":{}})
    def trap(*args,**kwargs):pytest.fail("active EOF與new legacy owner衝突必須先拒")
    monkeypatch.setattr(observation,"read_visible_text",trap);monkeypatch.setattr(route,"read_world_grid",trap)
    result=(route.field_context(pb,s,p,"complete") if entry=="field" else route.switch_context(pb,s,p,"complete",[]))
    review(result)


def test_pre_attrition_fallback_checks_active_eof_owner_before_ui(monkeypatch):
    pb=object();s=state();p=plan();Readers(monkeypatch,s);route._training_eof_context(pb,s,p)
    p.pop("training_supervisor")
    def trap(*args,**kwargs):pytest.fail("pre-attrition不得在active EOF改plan後讀UI")
    monkeypatch.setattr(observation,"read_visible_text",trap)
    result=route.attrition_transition_context(pb,s,p,"complete",dict(review_reason="party_attrition_state_unverified",
        party_attrition=dict(issue="party_read_not_verified")),previous=["wait"])
    review(result)


@pytest.mark.parametrize("which",["text","grid","movement","healthy"])
def test_eof_reader_or_health_exception_becomes_review_instead_of_exiting_game(monkeypatch,which):
    s=state();p=plan();Readers(monkeypatch,s)
    def broken(*args,**kwargs):raise OSError("synthetic_"+which+"_read_failed")
    target,key={"text":(observation,"read_visible_text"),"grid":(route,"read_world_grid"),
        "movement":(rocket_movement,"read_rocket_movement"),"healthy":(route,"healthy")}[which]
    monkeypatch.setattr(target,key,broken)
    out,next_id=review(route.waypoint(object(),s,p,"complete",[]))
    assert next_id=="complete" and not out.get("training_world_proof")


def test_inner_pure_validator_exception_already_becomes_sticky_review(monkeypatch):
    pb=object();s=state();p=plan();Readers(monkeypatch,s);route._training_eof_context(pb,s,p)
    s["frame"]+=1;s["battle_state"]["observation_frame"]=s["frame"]
    def broken(*args):raise ValueError("synthetic_inner_validator")
    monkeypatch.setattr(supervisor,"validate_closed_proof",broken)
    out=route._training_eof_context(pb,s,p)
    assert out["phase"]=="campaign_review" and "synthetic_inner_validator" in out["review_reason"]
