"""單場訓練候選橋接；只讀，不送鍵／tick／寫plan；未實機驗證或批准。"""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import time

PURE_SHA256S = ("f8d4a1c2be865974b15615c3377b63a21927fb291ceca4ca0a3247d8657b2309",
               "1257a965b7ce5f72def561e357a104cfa8f70f6d16014dc5e813416b3000a96c")


def _load_exact():
    folder=Path(__file__).resolve().parent
    if not ((folder.name=="staged-league-training-runtime-20261028" and folder.parent.name==".local")
            or (folder.name=="laya_pokemon" and folder.parent.name=="src")):
        raise RuntimeError("只能使用精確stage或formal目錄")
    source=folder/"league_training_batch.py";resolved=source.resolve(strict=True)
    if resolved!=source.absolute() or sha256(resolved.read_bytes()).hexdigest() not in PURE_SHA256S:
        raise RuntimeError("訓練pure來源path/hash不符")
    spec=importlib.util.spec_from_file_location("laya_pokemon._league_training_batch_exact",resolved)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


batch=_load_exact()
MECHANIC="league_training_batch"
START=dict(map_id=194,x=28,y=7)
_CONTROLLERS=globals().get("_CONTROLLERS",{})
_BINDINGS=globals().get("_BINDINGS",{})
_COMPLETED=globals().get("_COMPLETED",set())
_ERRORS=globals().get("_ERRORS",{})
_OWNERS=globals().get("_OWNERS",{})
_FORBIDDEN={"event","item","badge","terminal","next_map","await_script_event","recovery_route"}
_BATTLE_PHASES={"battle_menu","battle_bag","battle_animation","battle_dialogue",
                "learning_menu","dialogue","strategy_review","campaign_review"}
_ACTIONS={"up","down","left","right","a","b","start","wait"}


def _active():
    if (type(_CONTROLLERS) is not dict or type(_BINDINGS) is not dict
            or type(_COMPLETED) is not set or type(_ERRORS) is not dict or type(_OWNERS) is not dict):return None
    return (set(_CONTROLLERS)|set(_BINDINGS)|set(_OWNERS))-_COMPLETED


def _review(reason,step_id):
    active=_active()
    if active:
        for owner in active:_ERRORS.setdefault(owner,"league_training_batch_"+reason)
    key=next(iter(active)) if active and len(active)==1 else step_id
    return dict(phase="campaign_review",objective="Wait.",available_actions=["wait"],
                review_reason=(_ERRORS if type(_ERRORS) is dict else {}).get(key,"league_training_batch_"+reason)),step_id


def applies(step_id,step):
    active=_active()
    return (active is None or bool(active) or isinstance(step_id,str) and step_id in _BINDINGS
            or isinstance(step,dict) and step.get("mechanic")==MECHANIC)


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)


def _explicit(step):
    intent=step.get("training_intent")
    return (step.get("kind")=="interact" and step.get("mechanic")==MECHANIC
        and type(step.get("map_id")) is int and step["map_id"]==194
        and type(step.get("target")) is list and step["target"]==[28,7]
        and all(type(n) is int for n in step["target"])
        and type(intent) is dict and intent==batch.INTENT and set(intent)==set(batch.INTENT)
        and all(type(intent[k]) is type(v) for k,v in batch.INTENT.items())
        and all(type(p) is list and len(p)==2 and all(type(n) is int for n in p) for p in intent["tiles"])
        and not _FORBIDDEN.intersection(step))


def _handoff(state,result,step_id):
    phase=state.get("phase");objective=state.get("objective");actions=state.get("available_actions")
    valid=(type(phase) is str and phase in _BATTLE_PHASES
        and isinstance(objective,str) and bool(objective) and type(actions) is list and bool(actions)
        and all(type(a) is str and a in _ACTIONS for a in actions)
        and len(actions)==len(set(actions)) and (actions==["wait"] or len(actions)>=2))
    if not valid:
        return {**result,"training_batch_owner_step":step_id,
                "training_batch_battle_delegate":"await_existing_battle_context"}
    out={k:v for k,v in result.items() if k not in ("phase","objective","available_actions","controller_menu_verified")}
    out.update(phase=phase,objective=objective,available_actions=list(actions),
               training_batch_owner_step=step_id,training_batch_battle_delegate="existing_battle")
    for key in ("controller_menu_verified","review_reason"):
        if key in state:out[key]=state[key]
    return out


def context(pyboy,state,plan,step_id,text,grid,previous):
    """真getter＋原生決策包；同owner/pending/baseline/clock/error跨reload保留。"""
    active=_active()
    if active is None:return _review("registries_unverified",step_id)
    if not isinstance(step_id,str) or not step_id:return _review("step_id_unverified",step_id)
    if active and active!={step_id}:return _review("owner_changed",step_id)
    if step_id in _ERRORS:return _review("sticky_bridge_error",step_id)
    if (not isinstance(plan,dict) or plan.get("mode")!="league_campaign"
            or not isinstance(plan.get("steps"),list)):
        return _review("plan_unverified",step_id)
    ids=[s.get("id") if isinstance(s,dict) else None for s in plan["steps"]]
    if any(not isinstance(i,str) or not i for i in ids) or len(ids)!=len(set(ids)):
        return _review("plan_step_ids_unverified",step_id)
    matches=[s for s in plan["steps"] if s["id"]==step_id]
    if len(matches)!=1:return _review("step_missing",step_id) if active else None
    step=matches[0]
    if step.get("mechanic")!=MECHANIC:
        return _review("intent_changed",step_id) if active or step_id in _BINDINGS else None
    if not _explicit(step):return _review("explicit_intent_unverified",step_id)
    job=plan.get("training_job")
    if not isinstance(job,str) or not job.strip():return _review("job_unverified",step_id)
    try:binding=(MECHANIC,_canonical(step),job)
    except (TypeError,ValueError):return _review("binding_unverified",step_id)
    if step_id in _BINDINGS and _BINDINGS[step_id]!=binding:return _review("job_or_intent_changed",step_id)
    controller=_CONTROLLERS.get(step_id)
    if step_id in _BINDINGS and controller is None:return _review("original_controller_missing",step_id)
    if (controller is not None or step_id in _COMPLETED) and step_id not in _BINDINGS:
        return _review("original_binding_missing",step_id)
    if step_id in _BINDINGS and step_id not in _OWNERS:return _review("original_session_owner_missing",step_id)
    if step_id in _OWNERS and _OWNERS[step_id] is not pyboy:return _review("native_session_owner_changed",step_id)
    if step_id in _COMPLETED:return _review("completed_step_reentered",step_id)
    if not isinstance(state,dict) or not isinstance(state.get("location"),dict):
        return _review("state_unverified",step_id)
    loc=state["location"];frame=state.get("frame")
    if (not batch.integer(frame,0,2**63-1)
            or any(not batch.integer(loc.get(k)) for k in ("map_id","x","y"))):
        return _review("frame_or_location_unverified",step_id)
    position={k:loc[k] for k in ("map_id","x","y")}
    if controller is None and position!=START:return None
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
    signal=batch.read_training_observation(pyboy,frame,sdk)
    if controller is None:
        current=batch.resources(signal.get("progress"))
        if (signal.get("read_valid") is not True or current is None
                or not batch.closed_world(text,grid,(28,7),frame) or signal.get("idle") is not True):
            return _review("initial_source_world_unverified",step_id)
        weakest=min(current["party"],key=lambda m:(m["level"],m["exp"]))
        if (type(plan.get("lead_species")) is not int or plan["lead_species"]!=weakest["species"]
                or current["party"][0]["species"]!=weakest["species"]):
            return _review("true_lowest_lead_not_ready",step_id)
        if min(m["level"] for m in current["party"])>=45:return _review("all_six_45_checkpoint_review",step_id)
        controller=batch.TrainingBatch(step["training_intent"])
        _CONTROLLERS[step_id]=controller;_BINDINGS[step_id]=binding;_OWNERS[step_id]=pyboy
    controller.__class__=batch.TrainingBatch
    result=controller.context(state,text=text,grid=grid,signal=signal,previous=previous,
                              now=time.monotonic(),owner=step_id)
    if not isinstance(result,dict):return _review("controller_result_unverified",step_id)
    if result.get("training_batch_battle_handoff") is True:return _handoff(state,result,step_id),step_id
    if result.get("training_batch_complete") is True:
        if (controller.error or controller.pending is not None or controller.suspended
                or controller.closed_frame is None or controller.closed_frame>=frame
                or not batch.closed_world(text,grid,(loc["x"],loc["y"]),frame)
                or signal.get("idle") is not True or controller.receipt is None
                or result.get("training_batch_outcome") not in ("complete_single_wild","complete_no_encounter")):
            return _review("completion_receipt_unverified",step_id)
        _COMPLETED.add(step_id)
        result={**result,"field_move_complete":True,"field_move_kind":"league-training-batch",
                "training_batch_owner_step":step_id,"training_batch_job":job}
        index=ids.index(step_id)+1
        return result,ids[index] if index<len(ids) else "complete"
    return {**result,"training_batch_owner_step":step_id},step_id


def pre_attrition_closure_context(pyboy,state,plan,step_id,attrition,text,grid,previous):
    """只讓已綁wild owner做WAIT驗收；其他損耗、FNT、未知仍由原閘停。"""
    if (not isinstance(attrition,dict) or attrition.get("review_reason")!="party_attrition_requires_center"
            or _active()!={step_id}):return None
    controller=_CONTROLLERS.get(step_id)
    current=batch.resources(state.get("progress")) if isinstance(state,dict) else None
    if (controller is None or controller.error or not controller.seen_wild or not controller.suspended
            or current is None or any(m["hp"]<=0 for m in current["party"])):
        return None
    frame=state.get("frame");loc=state.get("location",{})
    if not batch.closed_world(text,grid,(loc.get("x"),loc.get("y")),frame):return None
    owned=context(pyboy,state,plan,step_id,text,grid,previous)
    if owned is None:return None
    out,next_id=owned
    if out.get("available_actions")!=["wait"]:
        return _review("attrition_closure_must_only_wait",step_id)
    return out,next_id
