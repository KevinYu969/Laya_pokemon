"""預設dry-run的純JSON單次排程候選；來源／合成限定，未實機／未批准。

不初始化模擬器、不讀ROM/state、不發鍵。每次最多追加一段plan；所有鍵仍由
主runner本機Laya。跨次job固定900秒／40次出行，錯誤與未完成reserve永不自修。
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import time
import uuid

SOURCE_PATH=Path(__file__).resolve()
ROOT=SOURCE_PATH.parents[2]
if SOURCE_PATH.parent.name=="staged-league-training-supervisor-20261028" and SOURCE_PATH.parent.parent.name==".local":
    ROUTE_PATH=SOURCE_PATH.parent/"route-audit.json"
elif SOURCE_PATH.parent.name=="laya_pokemon" and SOURCE_PATH.parent.parent.name=="src":
    ROUTE_PATH=ROOT/"src/laya_pokemon/data/league_training_route.json"
else:raise RuntimeError("只接受精確staged或formal supervisor來源路徑")
STAGE=ROOT/".local/staged-league-training-supervisor-20261028"
GAME_REL="outputs/league-campaign-20261028-29/game"
PLAN_REL=".local/league-plan.json"
GAME=ROOT/GAME_REL
PLAN=ROOT/PLAN_REL
ACTIVE=ROOT/".local/active-campaign.json"
LOCK=STAGE/"supervisor.lock"
LEDGER=STAGE/"job-ledger.jsonl"
STARTED=STAGE/"job-started.json"
JOB="league-six-party45-game29-20261028"
SOURCE_COMMIT="a53671100ec22e5394ff26ec028d0812a238dae2"
ROUTE_SHA="a8255f3c4ce4d07ac89f9fd655b244565dd786ddf3f628a83b64615c0fe5aef8"
ROUTE_SHA256S=(ROUTE_SHA,"be91b93aead4d1229d326d38595f756d726d4667e821dc3970071ad117e0c22d")
BATCH_RECEIPT_SHA="567793ed75c10f9f60d572eb77a7437877296ad7645b4deedf36e87e3001cba5"
BATCH_PURE_SHA="f8d4a1c2be865974b15615c3377b63a21927fb291ceca4ca0a3247d8657b2309"
BATCH_BRIDGE_SHA="78bf4bf1e9a974fc971469a34ffa8656000dd8baa882b68f6a8a55fc8ea6a84c"
REFERENCE_SHA="248c70e24eda08e57e818e8ace37877d3452dda417d0c04dbb21e0dc64b1941b"
REFERENCE_SHA256S=(REFERENCE_SHA,"d427fd277d23235bc25ef4da6fd68a20e5b1f4412f807815a496ef58d9e8b330")
PROOF_PROFILE="red-en-league-training-world-v1"
MAX_SECONDS,MAX_OUTINGS,TARGET=900,40,45
BUDGET_KEY="league_training_supervisor_budget"
ROSTER={19,132,102,154,35,7}
NAMES={19:"LAPRAS",132:"SNORLAX",102:"EEVEE",154:"VENUSAUR",35:"FEAROW",7:"NIDOKING"}
BATCH_INTENT=dict(kind="vr2_east_single_wild",map_id=194,tiles=[[28,7],[28,8]],
                  max_displacements=32,target_level=45)


class ReviewRequired(RuntimeError):pass
def require(ok,reason):
    if not ok:raise ReviewRequired(reason)
def integer(v,lo=0,hi=2**63-1):return type(v) is int and lo<=v<=hi
def clock(v):return type(v) in (int,float) and math.isfinite(v) and v>=0
def hexsha(v):return type(v) is str and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def digest(data):return hashlib.sha256(data).hexdigest()
def canonical_sha(value):return digest(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8"))
def encode(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+"\n").encode("utf-8")
def decode(data):
    try:value=json.loads(data.decode("utf-8-sig"))
    except (ValueError,UnicodeError) as exc:raise ReviewRequired("json_invalid") from exc
    require(isinstance(value,dict),"json_object_required");return value
def _fixed(path,expected):
    data=path.read_bytes();require(digest(data) in expected,"frozen_source_hash_changed");return decode(data)


# 固定package/source只於初始化讀取；後續pure核心不讀檔。
ROUTE=_fixed(ROUTE_PATH,ROUTE_SHA256S)
REF=_fixed(ROOT/"src/laya_pokemon/data/gen1_reference.json",REFERENCE_SHA256S)
require(REF.get("source_commit")==SOURCE_COMMIT,"reference_commit_changed")
MOVES={m["id"]:(m["pp"],m["power"]) for m in REF["moves"].values()}
del REF


def validate_party(progress):
    require(isinstance(progress,dict) and progress.get("profile")=="gen1-wrapper-ram-progress-v1-unvalidated"
        and progress.get("party_read_valid") is True and progress.get("initialization_candidate") is True
        and type(progress.get("party_count")) is int and progress["party_count"]==6,"party_proof_missing")
    party=progress.get("party")
    require(isinstance(party,list) and len(party)==6 and all(isinstance(m,dict)
        and type(m.get("species")) is int for m in party)
        and {m["species"] for m in party}==ROSTER,"fixed_six_roster_required")
    for mon in party:
        require(mon.get("species_name")==NAMES[mon["species"]]
            and integer(mon.get("level"),1,100) and integer(mon.get("exp"),0,0xFFFFFF)
            and integer(mon.get("max_hp"),1,999) and integer(mon.get("hp"),1,mon["max_hp"])
            and integer(mon.get("status"),0,255)
            and mon["status"] in set(range(8))|{8,16,32,64},"party_hp_status_or_identity_unknown_or_fainted")
        require(all(isinstance(mon.get(k),list) and len(mon[k])==4 and all(integer(v,0,hi)
            for v in mon[k]) for k,hi in (("moves",165),("pp",255))),"moves_or_pp_unknown")
        occupied=[m for m in mon["moves"] if m]
        require(bool(occupied) and len(occupied)==len(set(occupied)),"moves_empty_or_duplicate")
        for move,pp in zip(mon["moves"],mon["pp"]):
            require((move==0 and pp==0) or (move in MOVES and (pp&63)<=MOVES[move][0]*(5+(pp>>6))//5),"pp_bound_unknown")
    require(progress.get("player_name_raw")=="KEVIN" and type(progress.get("badges_raw")) is int
        and progress["badges_raw"]==255 and integer(progress.get("money"),0,999999),"campaign_identity_unknown")
    bag=progress.get("inventory")
    require(isinstance(bag,list) and len(bag)<=20 and all(isinstance(i,dict)
        and set(i)=={"item","quantity"} and integer(i["item"],1,250)
        and integer(i["quantity"],1,99) for i in bag)
        and len({i["item"] for i in bag})==len(bag),"inventory_unknown")
    return party


def full_party(party):
    return all(m["hp"]==m["max_hp"] and m["status"]==0 and all(
        pp==MOVES[move][0] if move else pp==0
        for move,pp in zip(m["moves"],m["pp"])) for m in party)


def minimum_lead(party):return min(party,key=lambda m:(m["level"],m["exp"]))["species"]


def validate_closed_proof(state):
    """只驗root EOF兩fresh真證據；不把空文字候選當完整空白world。"""
    proof=state.get("training_world_proof");frame=state.get("frame");loc=state.get("location")
    require(isinstance(proof,dict) and proof.get("profile")==PROOF_PROFILE
        and proof.get("source_commit")==SOURCE_COMMIT and type(proof.get("observation_frame")) is int
        and proof["observation_frame"]==frame and proof.get("location")==loc,"complete_world_proof_required")
    frames=proof.get("closed_frames")
    require(isinstance(frames,list) and len(frames)==2 and all(integer(f) for f in frames)
        and frames[0]<frames[1]==frame,"two_fresh_world_frames_required")
    require(isinstance(loc,dict) and all(type(loc.get(k)) is int for k in ("map_id","x","y")),"proof_location_invalid")
    text=proof.get("text");grid=proof.get("grid");movement=proof.get("movement")
    require(isinstance(text,dict) and text.get("profile")=="gen1-visible-tile-text-candidates-v1-unvalidated"
        and text.get("read_valid") is True and text.get("alignment_verified") is True
        and text.get("read_error") is None and text.get("window_visible") is False
        and text.get("cells")==[[" "]*20 for _ in range(18)],"visible_blank_world_not_verified")
    if "observation_frame" in text:
        require(type(text["observation_frame"]) is int and text["observation_frame"]==frame,"text_frame_conflict")
    require(isinstance(movement,dict) and movement.get("profile")=="gen1-arrow-movement-source-v1"
        and movement.get("source_commit")==SOURCE_COMMIT and movement.get("read_valid") is True
        and type(movement.get("observation_frame")) is int and movement["observation_frame"]==frame
        and movement.get("spinning") is False and all(type(movement.get(k)) is int and movement[k]==0
        for k in ("simulated_remaining","joy_ignore","walk_counter"))
        and type(movement.get("movement_flags")) is int and movement["movement_flags"] in (0,4),"native_idle_proof_unknown")
    require(isinstance(grid,dict) and grid.get("verified_location")==[loc[k] for k in ("map_id","x","y")]
        and type(grid.get("observation_frame")) is int and grid["observation_frame"]==frame
        and integer(grid.get("screen_cells_verified"),12,28800),"grid_frame_or_location_unknown")
    tiles=grid.get("tiles");walk=grid.get("walkable");visible=grid.get("visible_verified_cells")
    require(isinstance(tiles,list) and 1<=len(tiles)<=144 and all(isinstance(r,list)
        and 1<=len(r)<=200 and all(integer(v,0,255) for v in r) for r in tiles)
        and all(len(r)==len(tiles[0]) for r in tiles),"grid_matrix_unknown")
    require(isinstance(walk,list) and len(walk)==len(tiles) and all(isinstance(r,list)
        and len(r)==len(tiles[0]) and all(type(v) is int and v in (0,1) for v in r) for r in walk),"walk_matrix_unknown")
    require(isinstance(visible,list) and len(visible)==grid["screen_cells_verified"]
        and all(isinstance(p,list) and len(p)==2 and all(type(n) is int for n in p)
        and 0<=p[0]<len(tiles[0]) and 0<=p[1]<len(tiles) for p in visible)
        and len(set(map(tuple,visible)))==len(visible) and [loc["x"],loc["y"]] in visible,"visible_map_proof_incomplete")
    canonical=json.dumps(state["progress"],sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")
    require(proof.get("progress_sha256")==digest(canonical),"progress_proof_hash_mismatch")
    require(type(proof.get("full_party_healed")) is bool
        and proof["full_party_healed"]==full_party(validate_party(state["progress"])),"full_heal_proof_disagrees")
    return proof


def snapshot_from_bytes(raw):
    require(isinstance(raw,(list,tuple)) and len(raw)==4 and all(type(v) is bytes for v in raw),"snapshot_bytes_required")
    plan,summary,review,active=map(decode,raw)
    require(active.get("game")==GAME_REL and active.get("plan")==PLAN_REL,"active_game_or_plan_changed")
    require(hexsha(active.get("source_sha256")) and summary.get("source_state_sha256")==active["source_sha256"],"active_source_identity_disagrees")
    require(summary.get("status")=="paused_for_review","complete_paused_review_required")
    require(summary.get("review_reason")==review.get("reason")=="route_extension_required"
        and summary.get("route_step")==review.get("route_step")=="complete","only_closed_route_extension_may_schedule")
    require(review.get("plan_sha256")==digest(raw[0]),"review_plan_hash_mismatch")
    require(plan.get("mode")=="league_campaign" and plan.get("source_commit")==SOURCE_COMMIT
        and plan.get("training_supervisor")=="vr2-east-balanced45-v1" and plan.get("training_job")==JOB
        and integer(plan.get("resume_revision"),0,2**31-2),"plan_identity_unknown")
    steps=plan.get("steps")
    require(isinstance(steps,list) and steps and all(isinstance(s,dict) and isinstance(s.get("id"),str)
        and s["id"] for s in steps) and len({s["id"] for s in steps})==len(steps),"plan_step_ids_invalid")
    state=review.get("state")
    require(isinstance(state,dict) and state.get("phase")=="campaign_review"
        and state.get("observation_profile")=="gen1-visible-tile-text-candidates-v1-unvalidated"
        and state.get("review_reason")=="route_extension_required" and state.get("visible_text_candidates")==[],"review_state_not_closed")
    battle=state.get("battle_state")
    require(isinstance(battle,dict) and type(battle.get("raw")) is int and battle["raw"]==0
        and battle.get("kind")=="none" and battle.get("active") is False
        and type(battle.get("observation_frame")) is int and battle["observation_frame"]==state.get("frame"),"battle_not_closed")
    try:stamp=datetime.fromisoformat(review["at"].replace("Z","+00:00"));require(stamp.tzinfo is not None,"review_time_timezone_missing")
    except (KeyError,ValueError,TypeError) as exc:raise ReviewRequired("review_timestamp_invalid") from exc
    validate_party(state.get("progress"));validate_closed_proof(state)
    return dict(plan=plan,summary=summary,review=review,active=active,raw=list(raw),stamp=stamp.timestamp())


def validate_calibration(calibration):
    require(isinstance(calibration,dict) and calibration.get("profile")=="league-training-calibration-v1"
        and calibration.get("approved_by")=="root" and calibration.get("game")==GAME_REL
        and calibration.get("source_commit")==SOURCE_COMMIT and calibration.get("route_audit_sha256")==ROUTE_SHA
        and calibration.get("batch_receipt_sha256")==BATCH_RECEIPT_SHA
        and calibration.get("batch_pure_sha256")==BATCH_PURE_SHA
        and calibration.get("batch_bridge_sha256")==BATCH_BRIDGE_SHA
        and all(calibration.get(k) is True for k in ("round_trip_verified","single_wild_verified","normal_nurse_verified"))
        and calibration.get("proof_profile")==PROOF_PROFILE
        and calibration.get("single_plan_writer")=="root-supervisor-exclusive","root_real_calibration_required")


def budget_start(now,plan_sha,calibration_sha,active_sha):
    require(clock(now),"wall_clock_invalid")
    return dict(job=JOB,target=TARGET,started_wall=now,deadline_wall=now+MAX_SECONDS,
        max_seconds=MAX_SECONDS,max_outings=MAX_OUTINGS,outings=0,appends=0,phase="center",
        expected_plan_sha256=plan_sha,calibration_sha256=calibration_sha,error=None,
        active_sha256=active_sha,last_frame=-1,last_review_stamp=-1,last_review_sha256=None,last_progress=None,last_wall=now)


def validate_budget(budget,now):
    require(isinstance(budget,dict) and budget.get("job")==JOB and budget.get("target")==TARGET
        and budget.get("max_seconds")==MAX_SECONDS and budget.get("max_outings")==MAX_OUTINGS
        and clock(budget.get("started_wall")) and clock(budget.get("deadline_wall"))
        and budget["deadline_wall"]-budget["started_wall"]==MAX_SECONDS
        and clock(now) and budget["started_wall"]<=now<budget["deadline_wall"]
        and clock(budget.get("last_wall")) and now>=budget["last_wall"]
        and integer(budget.get("outings"),0,MAX_OUTINGS) and integer(budget.get("appends"),0,2*MAX_OUTINGS)
        and budget.get("phase") in ("center","outbound_batch","returning")
        and budget.get("error") is None,"job_budget_expired_invalid_or_sticky_error")
    require(hexsha(budget.get("expected_plan_sha256")) and hexsha(budget.get("calibration_sha256")) and hexsha(budget.get("active_sha256"))
        and type(budget.get("last_frame")) is int and budget["last_frame"]>=-1
        and budget["appends"]==(2*budget["outings"]-1 if budget["phase"]=="outbound_batch" else 2*budget["outings"])
        and (budget["phase"]!="center" or budget["appends"]==budget["outings"]==0),"job_budget_hash_or_phase_invalid")


def plan_budget(budget):return {k:budget[k] for k in ("job","target","started_wall","deadline_wall","max_seconds","max_outings","outings","appends","phase")}


def move(mid,point,**extra):return dict(kind="move",map_id=mid,target=list(point),**extra)
def segment(name,mid):return [move(mid,p) for p in ROUTE["segments"][name]["coordinates"][1:]]


def outbound():
    return ([move(174,(7,7))]+segment("lobby_nurse_to_left_exit",174)[:-1]
        +[move(174,(7,11),next_map=9,terminal=True),move(9,(9,6))]
        +segment("city_landing_to_south_edge",9)
        +[move(9,(9,18),next_map=34,terminal=True)]
        +segment("route_north_edge_to_east_cave_door",34)[:-1]
        +[move(34,(14,31),next_map=194,terminal=True),move(194,(29,7)),move(194,(28,7)),move(194,(28,7)),
          dict(kind="interact",mechanic="league_training_batch",map_id=194,target=[28,7],training_intent=deepcopy(BATCH_INTENT))])


def recovery(player):
    require(player in ({"map_id":194,"x":28,"y":7},{"map_id":194,"x":28,"y":8}),"batch_endpoint_unknown")
    prefix=[move(194,(28,7))] if player["y"]==8 else []
    steps=(prefix+[move(194,(29,7),next_map=34,terminal=True),move(34,(14,32))]
        +segment("route_closed_cave_exit_to_north_edge",34)
        +[move(34,(9,-1),next_map=9,terminal=True)]
        +segment("city_south_edge_to_center_left_door",9)[:-1]
        +[move(9,(9,5),next_map=174,terminal=True)]
        +segment("lobby_raw_left_entry_to_nurse",174)
        +[dict(kind="heal",map_id=174,target=[7,7],face="up",require_full_pp=True)])
    return [dict(s,recovery_route=True) for s in steps]


def continuity(before,after):
    if before is None:return
    require(before["inventory"]==after["inventory"] and before["money"]==after["money"]
        and before["badges_raw"]==after["badges_raw"],"resources_changed_without_review")
    old={m["species"]:m for m in before["party"]}
    for mon in after["party"]:
        prior=old[mon["species"]]
        require(mon["level"]>=prior["level"] and mon["exp"]>=prior["exp"]
            and mon["max_hp"]>=prior["max_hp"] and mon["moves"]==prior["moves"],"xp_regressed_or_move_change_requires_review")


def project_completed_batch(plan,context,completion_state):
    """root須在真bridge完成當輪呼叫；只投影已驗controller輸出，不從EOF猜成功。"""
    step=plan["steps"][-1];receipt=context.get("training_batch_receipt")
    require(step.get("mechanic")=="league_training_batch" and plan.get("training_job")==JOB
        and context.get("field_move_complete") is True and context.get("field_move_kind")=="league-training-batch"
        and context.get("training_batch_complete") is True and context.get("training_batch_job")==JOB
        and context.get("training_batch_owner_step")==step["id"] and context.get("source_commit")==SOURCE_COMMIT
        and isinstance(receipt,dict),"real_completed_bridge_context_required")
    outcome=context.get("training_batch_outcome");count=context.get("training_batch_displacements");frames=receipt.get("closed_frames")
    require(outcome in ("complete_single_wild","complete_no_encounter") and integer(count,1,32)
        and isinstance(frames,list) and len(frames)==2 and all(integer(f) for f in frames)
        and frames[0]<frames[1]==completion_state.get("frame")
        and ((outcome=="complete_single_wild" and receipt.get("wild_count")==1
              and integer(receipt.get("total_exp_gain"),1,8192))
             or (outcome=="complete_no_encounter" and count==32 and receipt.get("wild_count")==0
                 and type(receipt.get("total_exp_gain")) is int and receipt["total_exp_gain"]==0)),"completed_batch_receipt_invalid")
    validate_party(completion_state.get("progress"));loc=completion_state.get("location")
    require(loc in ({"map_id":194,"x":28,"y":7},{"map_id":194,"x":28,"y":8}),"completion_location_invalid")
    return dict(job=JOB,owner_step=step["id"],outcome=outcome,displacements=count,source_commit=SOURCE_COMMIT,
        closed_frames=list(frames),location=deepcopy(loc),progress_sha256=canonical_sha(completion_state["progress"]),
        step_sha256=canonical_sha(step))


def eof_batch_proof(plan,state,stored):
    """root EOF從跨reload registry取同step投影；資源／位置變動不能改造舊收據。"""
    step=plan["steps"][-1]
    require(isinstance(stored,dict) and stored.get("job")==JOB and stored.get("owner_step")==step["id"]
        and stored.get("step_sha256")==canonical_sha(step) and stored.get("location")==state.get("location")
        and stored.get("progress_sha256")==canonical_sha(state["progress"])
        and isinstance(stored.get("closed_frames"),list) and len(stored["closed_frames"])==2
        and integer(stored["closed_frames"][1]) and state["frame"]>stored["closed_frames"][1],"stored_batch_proof_changed_or_missing")
    return deepcopy(stored)


def propose(snapshot,budget,calibration,now):
    """純plan-building；不寫檔，不替校準／護士／batch造成功證據。"""
    snapshot=snapshot_from_bytes(snapshot["raw"])
    validate_calibration(calibration);validate_budget(budget,now)
    plan=snapshot["plan"];review=snapshot["review"];state=review["state"];progress=state["progress"]
    require(digest(snapshot["raw"][0])==budget["expected_plan_sha256"],"plan_changed_outside_job")
    require(digest(snapshot["raw"][3])==budget["active_sha256"],"active_session_changed_inside_job")
    require(digest(snapshot["raw"][2])!=budget["last_review_sha256"] and state["frame"]>budget["last_frame"]
        and state["training_world_proof"]["closed_frames"][0]>budget["last_frame"]
        and snapshot["stamp"]>budget["last_review_stamp"],"review_replayed_or_clock_regressed")
    if budget["appends"]:
        require(plan.get("training_job")==JOB and plan.get(BUDGET_KEY)==plan_budget(budget),"job_plan_budget_disagrees")
        owned=[s for s in plan["steps"] if s["id"].startswith(JOB+"-")]
        require(bool(owned) and plan["steps"][-1] is owned[-1],"owned_tail_missing")
    else:
        require(BUDGET_KEY not in plan and calibration.get("initial_plan_sha256")==budget["expected_plan_sha256"]
            and not any(s["id"].startswith(JOB+"-") for s in plan["steps"]),"same_job_budget_cannot_restart")
    party=validate_party(progress);continuity(budget["last_progress"],progress)
    if all(m["level"]>=TARGET for m in party):
        return dict(status="all_six_45_checkpoint_review",plan=None,budget=deepcopy(budget),target=TARGET)
    updated=deepcopy(budget);loc=state["location"]
    if budget["phase"] in ("center","returning"):
        require(loc=={"map_id":174,"x":7,"y":7} and full_party(party),"full_nurse_center_required")
        require(state["training_world_proof"]["full_party_healed"] is True,"normal_nurse_closed_receipt_required")
        require(budget["outings"]<MAX_OUTINGS,"outings_budget_exhausted")
        updated["outings"]+=1;updated["phase"]="outbound_batch";steps=outbound()
    else:
        require(plan["steps"][-1].get("mechanic")=="league_training_batch","batch_tail_required")
        receipt=state.get("training_batch_proof")
        eof_batch_proof(plan,state,receipt)
        require(isinstance(receipt,dict) and receipt.get("job")==JOB
            and receipt.get("owner_step")==plan["steps"][-1]["id"]
            and receipt.get("outcome") in ("complete_single_wild","complete_no_encounter")
            and integer(receipt.get("displacements"),1,32)
            and (receipt["outcome"]!="complete_no_encounter" or receipt["displacements"]==32)
            and receipt.get("source_commit")==SOURCE_COMMIT
            and isinstance(receipt.get("closed_frames"),list) and len(receipt["closed_frames"])==2
            and all(integer(f) for f in receipt["closed_frames"])
            and receipt["closed_frames"][0]>budget["last_frame"]
            and receipt["closed_frames"][0]<receipt["closed_frames"][1]<=state["training_world_proof"]["closed_frames"][0],"owned_batch_closed_receipt_required")
        steps=recovery(loc);updated["phase"]="returning"
        require(len(steps)+8<=128 and all(not (m["status"]&8) or m["hp"]>40 for m in party),"poison_recovery_margin_requires_root_review")
    updated["appends"]+=1;updated["last_frame"]=state["frame"];updated["last_review_stamp"]=snapshot["stamp"]
    updated["last_wall"]=now
    updated["last_review_sha256"]=digest(snapshot["raw"][2]);updated["last_progress"]=deepcopy(progress)
    for index,step in enumerate(steps):step["id"]=f"{JOB}-{updated['appends']:03d}-{index:03d}"
    require(not {s["id"] for s in steps}&{s["id"] for s in plan["steps"]},"new_step_id_collision")
    newplan=deepcopy(plan);newplan["steps"]+=steps
    newplan.update(training_job=JOB,training_supervisor="vr2-east-balanced45-v1",lead_species=minimum_lead(party),resume_step=steps[0]["id"],
                   resume_revision=plan["resume_revision"]+1)
    newplan[BUDGET_KEY]=plan_budget(updated)
    updated["expected_plan_sha256"]=digest(encode(newplan))
    return dict(status="proposal_only",plan=newplan,budget=updated)


def read_snapshot():
    paths=(PLAN,GAME/"summary.json",GAME/"review-request.json",ACTIVE)
    first=[p.read_bytes() for p in paths];second=[p.read_bytes() for p in paths]
    require(first==second,"snapshot_changed_during_read")
    return snapshot_from_bytes(first)


def history_budget(rows,now):
    require(isinstance(rows,list) and bool(rows) and isinstance(rows[0],dict)
        and rows[0].get("kind")=="seed" and rows[0].get("job")==JOB,"original_job_seed_missing")
    seed=rows[0].get("budget");validate_budget(seed,now)
    require(seed["appends"]==seed["outings"]==0 and seed["phase"]=="center" and seed["last_frame"]==-1,"original_seed_schema_invalid")
    budget=deepcopy(seed);pending=None
    for row in rows[1:]:
        require(isinstance(row,dict) and row.get("job")==JOB,"ledger_owner_changed")
        require(row.get("kind")!="error","sticky_job_error")
        require(row.get("kind")!="terminal","terminal_job_requires_new_job")
        if row.get("kind")=="reserve":
            require(pending is None and hexsha(row.get("plan_sha256")),"uncommitted_reserve_or_hash_invalid")
            pending=row["plan_sha256"]
        elif row.get("kind")=="commit":
            candidate=row.get("budget");validate_budget(candidate,now)
            require(isinstance(pending,str) and pending==candidate.get("expected_plan_sha256")
                and candidate["appends"]==budget["appends"]+1
                and candidate["started_wall"]==seed["started_wall"] and candidate["deadline_wall"]==seed["deadline_wall"]
                and candidate["calibration_sha256"]==seed["calibration_sha256"]
                and candidate["active_sha256"]==seed["active_sha256"]
                and candidate["last_wall"]>=budget["last_wall"] and candidate["last_frame"]>budget["last_frame"]
                and budget["outings"]<=candidate["outings"]<=budget["outings"]+1,"ledger_budget_was_reset")
            budget=deepcopy(candidate);pending=None
        else:raise ReviewRequired("ledger_kind_unknown")
    require(pending is None,"uncommitted_reserve_requires_root_review")
    return budget


def _append(row):
    with LEDGER.open("a",encoding="utf-8") as stream:
        stream.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+"\n");stream.flush();os.fsync(stream.fileno())


def parser():
    p=argparse.ArgumentParser(description="預設dry-run；單次純JSON有界排程候選")
    mode=p.add_mutually_exclusive_group();mode.add_argument("--dry-run",action="store_true",default=True)
    mode.add_argument("--enable",action="store_true")
    for name in ("calibration","calibration-sha256","supervisor-sha256","initial-plan-sha256","initial-review-sha256"):
        p.add_argument("--"+name)
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    # dry-run 永不取得lock／寫ledger／改plan；不會因看見校準檔自行啟用。
    if not args.enable:
        print(json.dumps(dict(enabled=False,mode="dry-run",auto_executable=False,
            status="root_live_round_trip_and_single_wild_calibration_required",job=JOB),ensure_ascii=False))
        return 0
    require(all(isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
        for v in (args.calibration_sha256,args.supervisor_sha256,args.initial_plan_sha256,args.initial_review_sha256)),"exact_enable_hashes_required")
    require(digest(Path(__file__).read_bytes())==args.supervisor_sha256,"supervisor_source_hash_mismatch")
    calibration_raw=Path(args.calibration).read_bytes()
    require(digest(calibration_raw)==args.calibration_sha256,"calibration_receipt_hash_mismatch")
    calibration=decode(calibration_raw);validate_calibration(calibration)
    token=json.dumps(dict(job=JOB,pid=os.getpid(),nonce=uuid.uuid4().hex),sort_keys=True)
    with LOCK.open("x",encoding="utf-8") as stream:stream.write(token);stream.flush();os.fsync(stream.fileno())
    started=LEDGER.exists();temporary=None
    try:
        snapshot=read_snapshot()
        require(digest(snapshot["raw"][0])==args.initial_plan_sha256
            and digest(snapshot["raw"][2])==args.initial_review_sha256,"explicit_snapshot_hash_mismatch")
        now=time.time()
        if LEDGER.exists():
            require(STARTED.exists(),"original_job_started_receipt_missing")
            rows=[json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines()]
            require(bool(rows) and decode(STARTED.read_bytes())==rows[0].get("budget"),"original_seed_receipt_changed")
            budget=history_budget(rows,now)
        else:
            budget=budget_start(now,args.initial_plan_sha256,args.calibration_sha256,digest(snapshot["raw"][3]))
            require(not STARTED.exists() and BUDGET_KEY not in snapshot["plan"],"same_job_seed_missing")
            with STARTED.open("xb") as stream:stream.write(encode(budget));stream.flush();os.fsync(stream.fileno())
            _append(dict(kind="seed",job=JOB,budget=budget))
        started=True
        require(budget["calibration_sha256"]==args.calibration_sha256,"job_calibration_changed")
        result=propose(snapshot,budget,calibration,now)
        if result["plan"] is None:
            _append(dict(kind="terminal",job=JOB,reason=result["status"]))
            print(json.dumps(dict(status=result["status"],target=TARGET),ensure_ascii=False));return 0
        def final_check():
            require(LOCK.read_text(encoding="utf-8")==token,"exclusive_lock_owner_changed")
            require([PLAN.read_bytes(),(GAME/"summary.json").read_bytes(),(GAME/"review-request.json").read_bytes(),ACTIVE.read_bytes()]==snapshot["raw"],"snapshot_changed_before_commit")
            final_wall=time.time()
            require(clock(final_wall) and now<=final_wall<budget["deadline_wall"]
                and final_wall>=budget["last_wall"],"job_deadline_or_clock_regressed_before_commit")
            require(not any((GAME/name).exists() for name in ("RESUME","REVIEW","STOP")),"operator_control_present")
        final_check()
        _append(dict(kind="reserve",job=JOB,plan_sha256=result["budget"]["expected_plan_sha256"]))
        temporary=PLAN.with_name(".league-training-"+json.loads(token)["nonce"]+".tmp")
        with temporary.open("xb") as stream:stream.write(encode(result["plan"]));stream.flush();os.fsync(stream.fileno())
        final_check();os.replace(temporary,PLAN);temporary=None
        _append(dict(kind="commit",job=JOB,budget=result["budget"]))
        print(json.dumps(dict(status="one_bounded_plan_segment_queued",job=JOB,
            deadline_wall=budget["deadline_wall"],outings=result["budget"]["outings"]),ensure_ascii=False));return 0
    except Exception as exc:
        if started:_append(dict(kind="error",job=JOB,reason=str(exc)))
        raise
    finally:
        # 只移除本次自己建立且token仍相等的lock，不刪既有lock/user檔；殘留temp留root檢討。
        if LOCK.exists() and LOCK.read_text(encoding="utf-8")==token:LOCK.unlink()


if __name__=="__main__":
    try:raise SystemExit(main())
    except (ReviewRequired,OSError,ValueError) as error:
        print(json.dumps(dict(status="stopped_for_review",reason=str(error)),ensure_ascii=False));raise SystemExit(2)
