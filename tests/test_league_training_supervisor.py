"""純JSON合成測試；不初始化模擬器、不讀ROM/state、不執行真supervisor。"""
from copy import deepcopy
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import pytest

HERE=Path(__file__).resolve().parent
if HERE.name=="staged-league-training-supervisor-20261028" and HERE.parent.name==".local":
    SOURCE=HERE/"league_training_supervisor.py"
elif HERE.name=="tests":
    SOURCE=HERE.parent/"src/laya_pokemon/league_training_supervisor.py"
else:raise RuntimeError("只接受精確staged或formal tests目錄")
spec=importlib.util.spec_from_file_location("_staged_training_supervisor",SOURCE)
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)


def progress():
    rows=[(19,41),(132,41),(102,35),(154,35),(35,37),(7,36)]
    return dict(profile="gen1-wrapper-ram-progress-v1-unvalidated",party_read_valid=True,
        initialization_candidate=True,party_count=6,player_name_raw="KEVIN",badges_raw=255,
        money=12345,inventory=[],party=[dict(species=species,species_name=s.NAMES[species],level=level,
        exp=level**3,hp=120,max_hp=120,status=0,moves=[33,0,0,0],pp=[35,0,0,0]) for species,level in rows])


def initial_plan():
    return dict(mode="league_campaign",source_commit=s.SOURCE_COMMIT,resume_revision=1,
        training_supervisor="vr2-east-balanced45-v1",training_job=s.JOB,
        blocked={"194":[[27,7],[29,8]]},steps=[dict(id="root-calibrated-center",kind="move",map_id=174,target=[7,7])])


def proof(state):
    frame=state["frame"];loc=state["location"]
    visible=[[x,loc["y"]] for x in range(11)]+[[loc["x"],loc["y"]]]
    if len(set(map(tuple,visible)))<12:visible=[list(p) for p in [(x,0) for x in range(11)]+[(loc["x"],loc["y"])]]
    return dict(profile=s.PROOF_PROFILE,source_commit=s.SOURCE_COMMIT,observation_frame=frame,
        closed_frames=[frame-1,frame],location=deepcopy(loc),
        text=dict(profile="gen1-visible-tile-text-candidates-v1-unvalidated",read_valid=True,
            alignment_verified=True,window_visible=False,read_error=None,cells=[[" "]*20 for _ in range(18)]),
        movement=dict(profile="gen1-arrow-movement-source-v1",source_commit=s.SOURCE_COMMIT,
            read_valid=True,observation_frame=frame,spinning=False,simulated_remaining=0,
            joy_ignore=0,walk_counter=0,movement_flags=0),
        grid=dict(verified_location=[loc[k] for k in ("map_id","x","y")],observation_frame=frame,
            screen_cells_verified=12,visible_verified_cells=visible,
            tiles=[[32]*30 for _ in range(18)],walkable=[[1]*30 for _ in range(18)]),
        progress_sha256=s.digest(json.dumps(state["progress"],sort_keys=True,separators=(",",":"),
            ensure_ascii=False,allow_nan=False).encode()),full_party_healed=s.full_party(state["progress"]["party"]))


def snapshot(plan=None,*,frame=100,loc=None,p=None,batch=None):
    plan=initial_plan() if plan is None else deepcopy(plan);p=progress() if p is None else deepcopy(p)
    loc=dict(map_id=174,x=7,y=7) if loc is None else loc
    state=dict(phase="campaign_review",review_reason="route_extension_required",frame=frame,
        observation_profile="gen1-visible-tile-text-candidates-v1-unvalidated",
        visible_text_candidates=[],location=deepcopy(loc),progress=p,
        battle_state=dict(raw=0,kind="none",active=False,observation_frame=frame))
    state["training_world_proof"]=proof(state)
    if batch is not None:state["training_batch_proof"]=batch
    rawplan=s.encode(plan)
    review=dict(at=datetime.fromtimestamp(1000+frame,timezone.utc).isoformat(),reason="route_extension_required",
        route_step="complete",plan_sha256=s.digest(rawplan),state=state)
    summary=dict(status="paused_for_review",review_reason=review["reason"],route_step="complete",source_state_sha256="a"*64)
    active=dict(game=s.GAME_REL,plan=s.PLAN_REL,source_sha256="a"*64)
    return s.snapshot_from_bytes([rawplan,s.encode(summary),s.encode(review),s.encode(active)])


def calibration(plan_sha):
    return dict(profile="league-training-calibration-v1",approved_by="root",game=s.GAME_REL,
        source_commit=s.SOURCE_COMMIT,route_audit_sha256=s.ROUTE_SHA,batch_receipt_sha256=s.BATCH_RECEIPT_SHA,
        batch_pure_sha256=s.BATCH_PURE_SHA,batch_bridge_sha256=s.BATCH_BRIDGE_SHA,
        round_trip_verified=True,single_wild_verified=True,normal_nurse_verified=True,
        proof_profile=s.PROOF_PROFILE,single_plan_writer="root-supervisor-exclusive",initial_plan_sha256=plan_sha)


def start():
    snap=snapshot();sha=s.digest(snap["raw"][0]);c=calibration(sha)
    return snap,s.budget_start(2000.,sha,"c"*64,s.digest(snap["raw"][3])),c


def rejected(fn,fragment):
    with pytest.raises(s.ReviewRequired,match=fragment):fn()


def batch_snapshot(out,*,frame=200,p=None,outcome="complete_single_wild",location=None):
    p=progress() if p is None else deepcopy(p);location=location or dict(map_id=194,x=28,y=8)
    completed=dict(field_move_complete=True,field_move_kind="league-training-batch",training_batch_complete=True,
        training_batch_job=s.JOB,training_batch_owner_step=out["plan"]["steps"][-1]["id"],source_commit=s.SOURCE_COMMIT,
        training_batch_outcome=outcome,training_batch_displacements=32 if outcome=="complete_no_encounter" else 1,
        training_batch_receipt=dict(closed_frames=[frame-5,frame-4],wild_count=0 if outcome=="complete_no_encounter" else 1,
            total_exp_gain=0 if outcome=="complete_no_encounter" else 120))
    receipt=s.project_completed_batch(out["plan"],completed,dict(frame=frame-4,location=location,progress=p))
    return snapshot(out["plan"],frame=frame,loc=location,p=p,batch=receipt)


def test_default_and_explicit_dry_run_never_touch_live_files_or_lock(monkeypatch,capsys):
    def forbidden(*args,**kwargs):raise AssertionError("dry-run不可讀寫live檔")
    monkeypatch.setattr(s,"read_snapshot",forbidden)
    monkeypatch.setattr(Path,"open",forbidden)
    assert s.main([])==s.main(["--dry-run"])==0
    assert '"enabled": false' in capsys.readouterr().out


def test_enable_without_exact_hashes_stops_before_live_snapshot(monkeypatch):
    monkeypatch.setattr(s,"read_snapshot",lambda:pytest.fail("不可讀真game"))
    rejected(lambda:s.main(["--enable"]),"exact_enable_hashes_required")


def test_frozen_source_route_and_fixed_game_job_target_are_new():
    assert s.TARGET==45 and s.MAX_SECONDS==14400 and s.MAX_OUTINGS==1000
    assert s.GAME_REL=="outputs/league-campaign-20261028-29/game"
    assert "35" not in s.JOB and "20261024" not in s.JOB
    assert s.ROUTE["training_map_id"]==194


def test_source_assets_allow_only_independently_verified_lf_and_crlf_identical_json():
    paths=[(s.ROUTE_PATH,s.ROUTE_SHA256S),(s.ROOT/"src/laya_pokemon/data/gen1_reference.json",s.REFERENCE_SHA256S)]
    for path,allowed in paths:
        raw=path.read_bytes();lf=raw.replace(b"\r\n",b"\n");crlf=lf.replace(b"\n",b"\r\n")
        assert s.digest(lf) in allowed and s.digest(crlf) in allowed
        assert s.decode(lf)==s.decode(crlf)==s.decode(raw)
    assert s.SOURCE_PATH.resolve()==SOURCE.resolve()


def test_initial_full_center_builds_lowest_lead_move_then_one_owned_batch():
    snap,budget,c=start();out=s.propose(snap,budget,c,2001.)
    steps=out["plan"]["steps"][len(snap["plan"]["steps"]):]
    assert out["plan"]["lead_species"]==102
    assert steps[0]["kind"]=="move" and steps[0]["target"]==[7,7] and steps[0]["map_id"]==174
    assert steps[-2]["kind"]=="move" and steps[-2]["target"]==[28,7]
    assert steps[-1]["mechanic"]=="league_training_batch" and steps[-1]["training_intent"]==s.BATCH_INTENT
    assert out["budget"]["outings"]==1 and out["budget"]["phase"]=="outbound_batch"
    assert out["budget"]["started_wall"]==2000 and out["budget"]["deadline_wall"]==2000+s.MAX_SECONDS
    assert snap["plan"]["steps"]==initial_plan()["steps"] and budget["appends"]==0
    assert out["plan"]["blocked"]==snap["plan"]["blocked"]


def test_complete_single_wild_builds_normal_marked_recovery_then_full_pp_nurse():
    snap,budget,c=start();out=s.propose(snap,budget,c,2001)
    p=progress();p["party"][2]["exp"]+=120;p["party"][2]["hp"]-=4;p["party"][2]["pp"][0]-=1
    end=batch_snapshot(out,p=p);back=s.propose(end,out["budget"],c,2100)
    steps=back["plan"]["steps"][len(out["plan"]["steps"]):]
    assert steps[0]["target"]==[28,7] and all(x["recovery_route"] is True for x in steps)
    assert steps[-1]["kind"]=="heal" and steps[-1]["map_id"]==174 and steps[-1]["target"]==[7,7]
    assert steps[-1]["face"]=="up" and steps[-1]["require_full_pp"] is True
    assert back["budget"]["outings"]==1 and back["budget"]["deadline_wall"]==2000+s.MAX_SECONDS
    assert back["budget"]["phase"]=="returning"
    assert not {x["id"] for x in steps}&{x["id"] for x in out["plan"]["steps"]}


def test_center_full_heal_closure_starts_next_outing_with_fresh_lowest_lead():
    snap,budget,c=start();out=s.propose(snap,budget,c,2001)
    p=progress();p["party"][2]["exp"]+=120
    back=s.propose(batch_snapshot(out,p=p),out["budget"],c,2100)
    center=snapshot(back["plan"],frame=300,p=p)
    next_out=s.propose(center,back["budget"],c,2200)
    assert next_out["plan"]["lead_species"]==154
    assert next_out["budget"]["outings"]==2 and next_out["budget"]["deadline_wall"]==2000+s.MAX_SECONDS


def test_no_encounter_batch_still_returns_instead_of_adding_extra_laps():
    snap,budget,c=start();out=s.propose(snap,budget,c,2001)
    end=batch_snapshot(out,outcome="complete_no_encounter")
    end["review"]["state"]["training_batch_proof"]["displacements"]=32
    end["raw"][2]=s.encode(end["review"])
    back=s.propose(end,out["budget"],c,2100)
    assert back["budget"]["phase"]=="returning"
    assert back["plan"]["steps"][-1]["kind"]=="heal"


@pytest.mark.parametrize("name",["round_trip_verified","single_wild_verified","normal_nurse_verified"])
def test_missing_real_calibration_never_builds_plan(name):
    snap,budget,c=start();c[name]=False
    rejected(lambda:s.propose(snap,budget,c,2001),"root_real_calibration")


@pytest.mark.parametrize("mutate,fragment",[
    (lambda v:v[3].update(game="outputs/other/game"),"active_game"),
    (lambda v:v[3].update(plan=".local/other.json"),"active_game"),
    (lambda v:v[1].update(status="running"),"complete_paused"),
    (lambda v:v[2].update(plan_sha256="0"*64),"review_plan_hash"),
    (lambda v:v[2].update(reason="party_attrition_requires_center"),"only_closed_route_extension"),
    (lambda v:v[1].update(review_reason="operator_review"),"only_closed_route_extension"),
    (lambda v:v[2]["state"].pop("training_world_proof"),"complete_world_proof"),
    (lambda v:v[2]["state"]["training_world_proof"]["text"].update(window_visible=True),"visible_blank_world"),
    (lambda v:v[2]["state"]["training_world_proof"]["movement"].update(joy_ignore=255),"native_idle"),
    (lambda v:v[2]["state"]["training_world_proof"].update(closed_frames=[100,100]),"two_fresh"),
    (lambda v:v[2]["state"]["training_world_proof"].update(progress_sha256="0"*64),"progress_proof_hash"),
    (lambda v:v[2]["state"]["progress"]["party"][0].update(hp=0),"fainted"),
    (lambda v:v[2]["state"]["progress"]["party"][0].pop("pp"),"moves_or_pp"),
])
def test_inconsistent_or_incomplete_paused_json_stops(mutate,fragment):
    snap=snapshot();values=list(map(s.decode,snap["raw"]));mutate(values)
    rejected(lambda:s.snapshot_from_bytes([s.encode(v) for v in values]),fragment)


@pytest.mark.parametrize("now",[1999.,2000.+s.MAX_SECONDS,2001.+s.MAX_SECONDS,float("nan"),False])
def test_budget_proof_never_refunds_or_extends_same_job(now):
    snap,budget,c=start();rejected(lambda:s.propose(snap,budget,c,now),"job_budget")


def test_preseed_cap_change_does_not_migrate_or_refund_historical_budget():
    snap,budget,c=start()
    budget.update(max_seconds=900,max_outings=40,deadline_wall=2900)
    original=deepcopy(budget)
    rejected(lambda:s.propose(snap,budget,c,2001),"job_budget")
    assert budget==original


def test_initial_outing_ceiling_or_sticky_error_stop_without_reset():
    snap,budget,c=start();budget.update(outings=s.MAX_OUTINGS,appends=2*s.MAX_OUTINGS,phase="returning")
    snap["plan"][s.BUDGET_KEY]=s.plan_budget(budget);snap["raw"][0]=s.encode(snap["plan"])
    snap["review"]["plan_sha256"]=s.digest(snap["raw"][0]);snap["raw"][2]=s.encode(snap["review"])
    budget["expected_plan_sha256"]=s.digest(snap["raw"][0])
    # 出行數滿額即使budget格式完整，仍不得開第1001趟；其owned tail由root生成。
    snap["plan"]["steps"][-1]["id"]=s.JOB+f"-{2*s.MAX_OUTINGS:03}-000"
    snap["raw"][0]=s.encode(snap["plan"]);snap["review"]["plan_sha256"]=s.digest(snap["raw"][0]);snap["raw"][2]=s.encode(snap["review"])
    budget["expected_plan_sha256"]=s.digest(snap["raw"][0])
    rejected(lambda:s.propose(snap,budget,c,2001),"outings_budget")
    snap,budget,c=start();budget["error"]="previous_failure"
    rejected(lambda:s.propose(snap,budget,c,2001),"sticky_error")


def test_all_six_45_stops_as_checkpoint_without_claiming_league_finished():
    p=progress()
    for mon in p["party"]:mon["level"]=45;mon["exp"]=45**3
    snap=snapshot(p=p);sha=s.digest(snap["raw"][0]);budget=s.budget_start(2000,sha,"c"*64,s.digest(snap["raw"][3]))
    out=s.propose(snap,budget,calibration(sha),2001)
    assert out["plan"] is None and out["status"]=="all_six_45_checkpoint_review" and out["target"]==45


def test_xp_regression_or_move_change_never_silently_becomes_new_baseline():
    snap,budget,c=start();out=s.propose(snap,budget,c,2001)
    p=progress();p["party"][2]["exp"]-=1
    rejected(lambda:s.propose(batch_snapshot(out,p=p),out["budget"],c,2100),"xp_regressed")


def test_missing_wrong_job_or_future_batch_receipt_stops():
    snap,budget,c=start();out=s.propose(snap,budget,c,2001);end=batch_snapshot(out)
    end["review"]["state"]["training_batch_proof"]["owner_step"]="foreign"
    end["raw"][2]=s.encode(end["review"])
    rejected(lambda:s.propose(end,out["budget"],c,2100),"stored_batch_proof")


def test_batch_projection_requires_real_complete_context_and_preserves_exact_progress():
    snap,budget,c=start();out=s.propose(snap,budget,c,2001);end=batch_snapshot(out)
    state=end["review"]["state"];stored=state["training_batch_proof"]
    assert s.eof_batch_proof(out["plan"],state,stored)==stored
    state=deepcopy(state);state["progress"]["party"][0]["hp"]-=1
    rejected(lambda:s.eof_batch_proof(out["plan"],state,stored),"stored_batch_proof")
    rejected(lambda:s.project_completed_batch(out["plan"],{},state),"real_completed_bridge")


def test_poison_low_hp_never_queues_long_recovery_even_without_fainting():
    snap,budget,c=start();out=s.propose(snap,budget,c,2001)
    p=progress();p["party"][0].update(hp=1,status=8)
    rejected(lambda:s.propose(batch_snapshot(out,p=p),out["budget"],c,2100),"poison_recovery_margin")


def test_old_batch_and_world_closed_frames_cannot_be_relabeled_for_a_fresh_owner():
    snap,budget,c=start();out=s.propose(snap,budget,c,2001);end=batch_snapshot(out)
    end["review"]["state"]["training_batch_proof"]["closed_frames"]=[1,2];end["raw"][2]=s.encode(end["review"])
    rejected(lambda:s.propose(end,out["budget"],c,2100),"owned_batch_closed")
    end=batch_snapshot(out);end["review"]["state"]["training_world_proof"]["closed_frames"]=[1,200]
    end["raw"][2]=s.encode(end["review"])
    rejected(lambda:s.propose(end,out["budget"],c,2100),"review_replayed")


def test_external_plan_change_cannot_reuse_owned_budget():
    snap,budget,c=start();snap["raw"][0]+=b" "
    rejected(lambda:s.propose(snap,budget,c,2001),"review_plan_hash_mismatch")


def test_wall_clock_cannot_move_back_after_commit_even_with_original_deadline():
    snap,budget,c=start();out=s.propose(snap,budget,c,2200)
    rejected(lambda:s.propose(batch_snapshot(out),out["budget"],c,2100),"job_budget")


def test_append_only_seed_reserve_commit_proves_persistent_budget_and_crash_stops():
    snap,budget,c=start();out=s.propose(snap,budget,c,2001)
    seed=dict(kind="seed",job=s.JOB,budget=budget)
    reserve=dict(kind="reserve",job=s.JOB,plan_sha256=out["budget"]["expected_plan_sha256"])
    commit=dict(kind="commit",job=s.JOB,budget=out["budget"])
    restored=s.history_budget([seed,reserve,commit],2100)
    assert restored["deadline_wall"]==2000+s.MAX_SECONDS and restored["outings"]==1
    rejected(lambda:s.history_budget([seed,reserve],2100),"uncommitted_reserve")
    rejected(lambda:s.history_budget([seed,reserve,commit,dict(kind="error",job=s.JOB)],2100),"sticky_job_error")
    altered=deepcopy(commit);altered["budget"]["started_wall"]+=100;altered["budget"]["deadline_wall"]+=100
    rejected(lambda:s.history_budget([seed,reserve,altered],2100),"ledger_budget_was_reset")


@pytest.mark.parametrize("value",[None,"","x"*64,"A"*64,True])
def test_missing_or_malformed_reserve_hash_never_hides_uncommitted_plan(value):
    snap,budget,c=start();seed=dict(kind="seed",job=s.JOB,budget=budget)
    rejected(lambda:s.history_budget([seed,dict(kind="reserve",job=s.JOB,plan_sha256=value)],2100),"reserve_or_hash_invalid")


def test_replay_same_review_and_same_job_missing_ledger_proof_are_rejected():
    snap,budget,c=start();out=s.propose(snap,budget,c,2001)
    same=deepcopy(budget);same["last_review_sha256"]=s.digest(snap["raw"][2])
    rejected(lambda:s.propose(snap,same,c,2002),"review_replayed")
    missing=s.budget_start(2100,s.digest(s.encode(out["plan"])),"c"*64,s.digest(snap["raw"][3]))
    end=batch_snapshot(out)
    rejected(lambda:s.propose(end,missing,c,2101),"same_job_budget_cannot_restart")


def test_same_named_game_with_changed_active_session_cannot_reuse_original_budget():
    snap,budget,c=start();values=list(map(s.decode,snap["raw"]))
    values[3]["source_sha256"]="b"*64;values[1]["source_state_sha256"]="b"*64
    replaced=s.snapshot_from_bytes([s.encode(v) for v in values])
    rejected(lambda:s.propose(replaced,budget,c,2001),"active_session_changed")
