"""Read-only bridge for exactly VR1 slot5 first switch. No game input or ticks.

Frozen pure/getter only; owner/pending/clock/baseline/error survive hot reload.
Root integrates the full peer mutex and real battle dispatcher.
"""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import time

PURE_SHA256="78870aa893c3461b320b7c5abf19d20ff31768202a8599f872591fa85e1a718f"
PURE_CRLF_SHA256="61c8290018078352ed1cd91d8b892e786c97dc75f25ce82e722efe74def12da9"
PURE_SHA256S=(PURE_SHA256,PURE_CRLF_SHA256)


def _load_exact_controller():
    folder=Path(__file__).resolve().parent
    if folder.name=="staged-victory-first-boulder-postreview-20261025" and folder.parent.name==".local":
        source=folder.parent.parent/".local/staged-victory-first-boulder-postreview-20261025/victory_first_boulder.py"
    elif folder.name=="laya_pokemon" and folder.parent.name=="src":
        source=folder.parent.parent/"src/laya_pokemon/victory_first_boulder.py"
    else:raise RuntimeError("First-boulder bridge requires its exact stage or formal directory")
    resolved=source.resolve(strict=True)
    if resolved!=source.absolute() or sha256(resolved.read_bytes()).hexdigest() not in PURE_SHA256S:
        raise RuntimeError("First-boulder pure source path/hash mismatch")
    spec=importlib.util.spec_from_file_location("laya_pokemon._victory_first_boulder_exact_source",resolved)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if Path(module.__file__).resolve()!=resolved:raise RuntimeError("First-boulder pure module source mismatch")
    return module


boulder=_load_exact_controller()
MECHANIC="victory_first_boulder"
START=dict(map_id=108,x=8,y=16)
_CONTROLLERS=globals().get("_CONTROLLERS",{})
_BINDINGS=globals().get("_BINDINGS",{})
_COMPLETED=globals().get("_COMPLETED",set())
_FORBIDDEN={"event","item","badge","next_map","terminal","await_script_event"}
_BATTLE_PHASES={"battle_menu","battle_bag","battle_animation","battle_dialogue",
                "learning_menu","dialogue","strategy_review","campaign_review"}
_ACTIONS={"up","down","left","right","a","b","start","wait"}


def _review(reason):
    return dict(phase="campaign_review",objective="Wait.",available_actions=["wait"],
                review_reason="victory_first_boulder_"+reason)


def _active():
    if type(_BINDINGS) is not dict or type(_CONTROLLERS) is not dict or type(_COMPLETED) is not set:
        return None
    return (set(_BINDINGS)|set(_CONTROLLERS))-_COMPLETED


def applies(step_id,step):
    active=_active()
    return (active is None or bool(active) or isinstance(step_id,str) and step_id in _BINDINGS
            or isinstance(step,dict) and step.get("mechanic")==MECHANIC)


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)


def _explicit(step):
    intent=step.get("boulder_intent");expected=boulder.INTENT
    return (step.get("kind")=="interact" and step.get("mechanic")==MECHANIC
            and type(step.get("map_id")) is int and step["map_id"]==108
            and type(step.get("target")) is list and step["target"]==[8,16]
            and all(type(n) is int for n in step["target"])
            and type(intent) is dict and intent==expected and set(intent)==set(expected)
            and all(type(intent[k]) is type(v) for k,v in expected.items())
            and all(type(n) is int for k in ("start_player","start_boulder","goal_boulder") for n in intent[k])
            and not _FORBIDDEN.intersection(step))


def _handoff(state,result,step_id):
    """Keep a truthy owned field result while preserving actual battle UI choices.

    Returning None would allow main's lead reorder or waypoint fallback to run.
    Never turn an unclassified return transition into a new battle command.
    """
    phase=state.get("phase");choices=state.get("available_actions");objective=state.get("objective")
    valid=(type(phase) is str and phase in _BATTLE_PHASES and isinstance(objective,str) and bool(objective)
           and type(choices) is list and bool(choices) and all(type(a) is str and a in _ACTIONS for a in choices)
           and len(choices)==len(set(choices)) and (choices==["wait"] or len(choices)>=2))
    if not valid:
        return {**result,"first_boulder_owner_step":step_id,
                "first_boulder_battle_delegate":"await_existing_battle_context"}
    # The other battle fields remain in the original state; copy only existing
    # decision keys to avoid pure's WAIT hint overwriting real battle decisions.
    out={k:v for k,v in result.items() if k not in ("phase","objective","available_actions","controller_menu_verified")}
    out.update(phase=phase,objective=objective,available_actions=list(choices),
               first_boulder_owner_step=step_id,first_boulder_battle_delegate="existing_battle")
    if "controller_menu_verified" in state:out["controller_menu_verified"]=state["controller_menu_verified"]
    if "review_reason" in state:out["review_reason"]=state["review_reason"]
    return out


def context(pyboy,state,plan,step_id,text,grid,previous):
    """Use unchanged native packets and true previous; only real closure advances."""
    active=_active()
    if active is None:return _review("registries_unverified"),step_id
    if not isinstance(step_id,str) or not step_id:return _review("step_id_unverified"),step_id
    if active and active!={step_id}:return _review("owner_changed"),step_id
    if not isinstance(plan,dict) or not isinstance(plan.get("steps"),list):return _review("plan_unverified"),step_id
    ids=[s.get("id") if isinstance(s,dict) else None for s in plan["steps"]]
    if any(not isinstance(i,str) or not i for i in ids) or len(ids)!=len(set(ids)):
        return _review("plan_unverified"),step_id
    matches=[s for s in plan["steps"] if s["id"]==step_id]
    if len(matches)!=1:
        return (_review("step_unverified"),step_id) if active or step_id in _BINDINGS else None
    step=matches[0]
    if step.get("mechanic")!=MECHANIC:
        return (_review("intent_changed"),step_id) if step_id in _BINDINGS or active else None
    if not _explicit(step):return _review("explicit_intent_unverified"),step_id
    try:
        if "training_job" not in plan or plan["training_job"] is None:raise ValueError("missing job")
        binding=(MECHANIC,_canonical(step),_canonical(plan["training_job"]))
    except (TypeError,ValueError):return _review("owner_unverified"),step_id
    if step_id in _BINDINGS and _BINDINGS[step_id]!=binding:return _review("intent_or_owner_changed"),step_id
    controller=_CONTROLLERS.get(step_id)
    if step_id in _BINDINGS and controller is None:return _review("original_controller_missing"),step_id
    if (controller is not None or step_id in _COMPLETED) and step_id not in _BINDINGS:
        return _review("original_binding_missing"),step_id
    if step_id in _COMPLETED:return _review("completed_step_reentered"),step_id
    if not isinstance(state,dict) or not isinstance(state.get("location"),dict):return _review("state_unverified"),step_id
    loc=state["location"];frame=state.get("frame")
    if (type(frame) is not int or frame<0 or any(type(loc.get(k)) is not int or not 0<=loc[k]<=255
                                               for k in ("map_id","x","y"))):
        return _review("frame_or_location_unverified"),step_id
    position={k:loc[k] for k in ("map_id","x","y")}
    if controller is None and position!=START:return None

    from laya_pokemon.campaign_transactions import verified_blank_transaction_world,ui_overworld_ready
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
    signal=boulder.read_first_boulder_observation(pyboy,frame,sdk)
    if controller is None:
        if not verified_blank_transaction_world(text,grid):return _review("initial_closed_world_required"),step_id
        if not isinstance(signal,dict) or signal.get("read_valid") is not True:
            return _review("initial_signal_unverified"),step_id
        controller=boulder.VictoryFirstBoulderController(step["boulder_intent"])
        _CONTROLLERS[step_id]=controller;_BINDINGS[step_id]=binding
    controller.__class__=boulder.VictoryFirstBoulderController
    result=controller.context(state,text=text,grid=grid,signal=signal,previous=previous,
                              now=time.monotonic(),owner=step_id,overworld_ready=ui_overworld_ready(text,grid))
    if not isinstance(result,dict):return _review("controller_result_unverified"),step_id
    if result.get("first_boulder_battle_handoff") is True:
        return _handoff(state,result,step_id),step_id
    if result.get("first_boulder_complete") is True:
        raw=signal.get("raw");stone=signal.get("stone")
        if (signal.get("read_valid") is not True or signal.get("profile")!=boulder.PROFILE
                or signal.get("source_commit")!=boulder.SOURCE_COMMIT
                or type(signal.get("observation_frame")) is not int or signal["observation_frame"]!=frame
                or signal.get("location")!=position or position["map_id"]!=108
                or tuple(position[k] for k in ("x","y"))!=controller.final_player
                or controller.push_index!=18 or controller.closed_frame is None or controller.closed_frame>=frame
                or controller.pending is not None or controller.suspended or controller.error is not None
                or not isinstance(raw,dict) or any(type(raw.get(k)) is not int for k in ("flags1","event_raw","gate_block","mode","battle_raw"))
                or not raw["flags1"]&1 or not raw["event_raw"]&128 or raw["gate_block"]!=0x1D
                or raw["mode"]!=0 or raw["battle_raw"]!=0 or signal.get("event") is not True
                or signal.get("idle") is not True or signal.get("native_push_busy") is not False
                or not isinstance(stone,dict) or (stone.get("slot"),stone.get("x"),stone.get("y"),stone.get("movement_byte2"))!=(5,17,13,16)
                or not verified_blank_transaction_world(text,grid) or not boulder._grid(grid,controller.final_player,frame)
                or grid["tiles"][12][9]!=5):
            return _review("completion_native_receipt_unverified"),step_id
        _COMPLETED.add(step_id)
        result={**result,"field_move_complete":True,"field_move_kind":"victory-first-boulder",
                "first_boulder_owner_step":step_id}
        index=ids.index(step_id)+1
        return result,ids[index] if index<len(ids) else "complete"
    return {**result,"first_boulder_owner_step":step_id},step_id
