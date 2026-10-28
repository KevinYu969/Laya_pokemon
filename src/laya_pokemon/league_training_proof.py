"""訓練EOF雙fresh真world證據候選；來源／合成限定，未實機／未批准。

純封包／registry helper，不讀JSON/ROM/state、不發鍵、不tick。parent提供真reader
封包與已初始化supervisor純validators。時間只從真frame累計；錯誤不拋出game。
"""
from copy import deepcopy
import hashlib
import json
import math

SOURCE_COMMIT="a53671100ec22e5394ff26ec028d0812a238dae2"
PROFILE="red-en-league-training-world-v1"
JOB="league-six-party45-game29-20261028"
MARKER="vr2-east-balanced45-v1"
MAX_FRAMES,MAX_CALLS=3600,120
_SESSIONS=globals().get("_SESSIONS",{})
_OWNERS=globals().get("_OWNERS",{})
_ERRORS=globals().get("_ERRORS",{})


def integer(v,lo=0,hi=2**63-1):return type(v) is int and lo<=v<=hi
def canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)
def progress_sha(progress):return hashlib.sha256(canonical(progress).encode("utf-8")).hexdigest()
def _review(reason):
    return dict(phase="campaign_review",objective="Wait.",available_actions=["wait"],route_step="complete",
        review_reason="league_training_proof_"+reason,suppress_navigation_stall=True)
def _wait(reason):
    return dict(phase="league_training_wait",objective="Wait.",available_actions=["wait"],route_step="complete",
        training_proof_tactic=reason,suppress_navigation_stall=True,suppress_blocked_edge_learning=True)
def _active():
    if type(_SESSIONS) is not dict or type(_OWNERS) is not dict or type(_ERRORS) is not dict:return None
    return ({key for key,c in _SESSIONS.items() if not getattr(c,"complete",False) or getattr(c,"error",None) is not None}
        |{k for k in _OWNERS if k not in _SESSIONS}|set(_ERRORS))
def applies(plan):
    active=_active()
    return active is None or bool(active) or (isinstance(plan,dict)
        and plan.get("training_supervisor")==MARKER and plan.get("training_job")==JOB)
def _fail(key,reason):
    if type(_ERRORS) is dict:
        for owner in (_active() or {key}):_ERRORS.setdefault(owner,reason)
        reason=_ERRORS.get(key,reason)
    return _review(reason)


def _movement(movement,frame):
    if (not isinstance(movement,dict) or movement.get("profile")!="gen1-arrow-movement-source-v1"
            or movement.get("source_commit")!=SOURCE_COMMIT or movement.get("read_valid") is not True
            or movement.get("read_error") is not None or type(movement.get("observation_frame")) is not int
            or movement["observation_frame"]!=frame
            or any(not integer(movement.get(k),0,255) for k in ("simulated_remaining","joy_ignore","walk_counter","movement_flags"))
            or movement["joy_ignore"] not in (0,255) or movement["movement_flags"]&0x38
            or type(movement.get("spinning")) is not bool
            or movement["spinning"]!=bool(movement["movement_flags"]&128)):
        raise ValueError("movement_packet_unknown")
    return bool(movement["simulated_remaining"] or movement["joy_ignore"] or movement["walk_counter"]
                or movement["movement_flags"]&0xFB)


def _current_world(state,text,grid,movement,full_party_healed,validation):
    frame=state["frame"];loc=state["location"]
    validation.validate_party(state.get("progress"))
    if type(full_party_healed) is not bool:raise ValueError("full_heal_flag_unknown")
    if full_party_healed!=validation.full_party(state["progress"]["party"]):raise ValueError("full_heal_flag_disagrees")
    if (not isinstance(text,dict) or text.get("profile")!="gen1-visible-tile-text-candidates-v1-unvalidated"
            or text.get("read_valid") is not True or text.get("alignment_verified") is not True
            or text.get("read_error") is not None or type(text.get("window_visible")) is not bool):
        raise ValueError("text_packet_unknown")
    cells=text.get("cells")
    if (not isinstance(cells,list) or len(cells)!=18 or any(not isinstance(row,list) or len(row)!=20
            or any(type(ch) is not str or len(ch)!=1 for ch in row) for row in cells)):
        raise ValueError("text_cells_unknown")
    if "observation_frame" in text and (type(text["observation_frame"]) is not int or text["observation_frame"]!=frame):
        raise ValueError("text_frame_conflict")
    if text["window_visible"] or cells!=[[" "]*20 for _ in range(18)]:return False
    if (not isinstance(grid,dict) or type(grid.get("observation_frame")) is not int or grid["observation_frame"]!=frame
            or grid.get("verified_location")!=[loc[k] for k in ("map_id","x","y")]
            or not integer(grid.get("screen_cells_verified"),12,28800)):
        raise ValueError("grid_packet_unknown")
    tiles=grid.get("tiles");walk=grid.get("walkable");visible=grid.get("visible_verified_cells")
    if (not isinstance(tiles,list) or not 1<=len(tiles)<=144 or any(not isinstance(row,list)
            or not 1<=len(row)<=200 or any(not integer(v,0,255) for v in row) for row in tiles)
            or any(len(row)!=len(tiles[0]) for row in tiles)
            or not isinstance(walk,list) or len(walk)!=len(tiles)
            or any(not isinstance(row,list) or len(row)!=len(tiles[0])
                   or any(type(v) is not int or v not in (0,1) for v in row) for row in walk)
            or not isinstance(visible,list) or len(visible)!=grid["screen_cells_verified"]
            or any(not isinstance(p,list) or len(p)!=2 or not integer(p[0],0,len(tiles[0])-1)
                   or not integer(p[1],0,len(tiles)-1) for p in visible)
            or len(set(map(tuple,visible)))!=len(visible) or [loc["x"],loc["y"]] not in visible):
        raise ValueError("grid_matrix_or_visible_proof_unknown")
    return True


class EOFProofController:
    def __init__(self,binding):
        self.binding=binding;self.calls=0;self.elapsed_frames=0;self.last_frame=None;self.last_now=None
        self.last_packet=None;self.first_frame=None;self.first_location=None;self.first_progress_sha=None
        self.error=None;self.complete=False
    def fail(self,reason):
        self.error=self.error or reason;return _review(self.error)
    def context(self,state,*,text,grid,movement,full_party_healed,validation,now,plan,stored_batch_proof):
        if self.error:return self.fail("sticky")
        if self.complete:return self.fail("completed_eof_reentered")
        frame=state.get("frame") if isinstance(state,dict) else None
        if (not integer(frame) or type(now) not in (int,float) or not math.isfinite(now)
                or abs(now-frame/60)>1e-6 or self.last_frame is not None and frame<self.last_frame
                or self.last_now is not None and now<self.last_now):
            return self.fail("frame_or_frame_clock_invalid")
        self.calls+=1
        if self.last_frame is not None:self.elapsed_frames+=frame-self.last_frame
        if self.calls>MAX_CALLS or self.elapsed_frames>MAX_FRAMES:return self.fail("true_frame_or_call_budget_exhausted")
        loc=state.get("location");battle=state.get("battle_state")
        if (not isinstance(loc,dict) or any(not integer(loc.get(k),0,255) for k in ("map_id","x","y"))
                or not isinstance(battle,dict) or type(battle.get("raw")) is not int or battle["raw"]!=0
                or battle.get("kind")!="none" or battle.get("active") is not False
                or type(battle.get("observation_frame")) is not int or battle["observation_frame"]!=frame):
            return self.fail("native_world_or_location_unknown")
        packet=deepcopy((state,text,grid,movement,full_party_healed,stored_batch_proof))
        if frame==self.last_frame:
            if packet!=self.last_packet:return self.fail("same_frame_conflict")
            return _wait("same_frame_cannot_be_second_world")
        self.last_frame,self.last_now,self.last_packet=frame,now,packet
        try:
            busy=_movement(movement,frame)
            if busy:
                self.first_frame=self.first_location=self.first_progress_sha=None
                return _wait("source_known_movement_busy")
            closed=_current_world(state,text,grid,movement,full_party_healed,validation)
            if not closed:
                self.first_frame=self.first_location=self.first_progress_sha=None
                return _wait("valid_visible_ui_not_blank")
            current_sha=progress_sha(state["progress"])
            if self.first_frame is None:
                self.first_frame=frame;self.first_location=deepcopy(loc);self.first_progress_sha=current_sha
                return _wait("first_true_closed_world")
            if loc!=self.first_location or current_sha!=self.first_progress_sha:
                return self.fail("closed_pair_location_or_progress_changed")
            proof=dict(profile=PROFILE,source_commit=SOURCE_COMMIT,observation_frame=frame,
                closed_frames=[self.first_frame,frame],location=deepcopy(loc),text=deepcopy(text),grid=deepcopy(grid),
                movement=deepcopy(movement),progress_sha256=current_sha,full_party_healed=full_party_healed)
            candidate={**state,"training_world_proof":proof}
            validation.validate_closed_proof(candidate)
            result={**_review("unused"),"review_reason":"route_extension_required","training_world_proof":proof}
            if plan["steps"][-1].get("mechanic")=="league_training_batch":
                result["training_batch_proof"]=validation.eof_batch_proof(plan,candidate,stored_batch_proof)
            self.complete=True
            return result
        except Exception as exc:
            return self.fail("packet_or_validation_failed:"+type(exc).__name__+":"+str(exc)[:100])


def context(state,plan,*,text,grid,movement,native_owner,peers_clear,full_party_healed,validation,
            stored_batch_proof=None,now=None):
    """只能由parent waypoint EOF接；peers_clear須已包含所有field與legacy owner。"""
    active=_active()
    if active is None:return _review("registries_unknown")
    marked=(isinstance(plan,dict) and plan.get("training_supervisor")==MARKER and plan.get("training_job")==JOB)
    if not marked:return _fail(next(iter(active)),"marker_or_job_removed") if active else None
    try:
        if plan.get("mode")!="league_campaign":return _fail(next(iter(active)) if active else (JOB,"unbound"),"campaign_mode_changed")
        steps=plan.get("steps")
        if (not isinstance(steps,list) or not steps or any(not isinstance(s,dict) or not isinstance(s.get("id"),str) or not s["id"] for s in steps)
                or len({s["id"] for s in steps})!=len(steps)):
            return _fail(next(iter(active)) if active else (JOB,"unbound"),"plan_tail_unknown")
        key=(JOB,steps[-1]["id"])
        if active and active!={key}:return _fail(next(iter(active)),"active_owner_or_tail_changed")
        if key in _ERRORS:return _review(_ERRORS[key])
        if type(peers_clear) is not bool or peers_clear is not True:return _fail(key,"active_field_or_legacy_owner")
        if native_owner is None or type(native_owner) in (str,int,float,bool,list,tuple,dict):return _fail(key,"native_owner_unknown")
        binding=canonical(plan)
        controller=_SESSIONS.get(key)
        if key in _OWNERS and (controller is None or _OWNERS[key] is not native_owner):return _fail(key,"native_owner_changed_or_original_controller_missing")
        if controller is not None and key not in _OWNERS:return _fail(key,"original_native_owner_missing")
        if controller is not None and controller.binding!=binding:return _fail(key,"immutable_plan_binding_changed")
        if any(not callable(getattr(validation,k,None)) for k in ("validate_party","full_party","validate_closed_proof","eof_batch_proof")):
            return _fail(key,"pure_validators_missing")
        if controller is None:
            controller=EOFProofController(binding);_SESSIONS[key]=controller;_OWNERS[key]=native_owner
        controller.__class__=EOFProofController
        frame=state.get("frame") if isinstance(state,dict) else None
        frame_now=frame/60 if integer(frame) else float("nan")
        return controller.context(state,text=text,grid=grid,movement=movement,full_party_healed=full_party_healed,
            validation=validation,now=frame_now if now is None else now,plan=plan,stored_batch_proof=stored_batch_proof)
    except Exception as exc:
        return _fail(locals().get("key",(JOB,"unknown")),"bridge_validation_failed:"+type(exc).__name__+":"+str(exc)[:100])
