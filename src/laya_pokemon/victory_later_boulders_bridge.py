"""Read-only bridge for exactly four fixed later-floor cases. No game input or ticks.

Frozen pure/getter only; owner/pending/clock/baseline/error survive hot reload.
Root integrates the full peer mutex and real battle dispatcher.
"""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import time

PURE_SHA256="d61b5b4d3aafc02ce926f3151784ab711242027cfdabdfb9fc2956bcd7c31ee5"
PURE_CRLF_SHA256="d2615d336750f3b8944f8ce964b4af2cd0678d5c1f0182c52c10489b5de535b2"
PURE_SHA256S=(PURE_SHA256,PURE_CRLF_SHA256)


def _load_exact_controller():
    folder=Path(__file__).resolve().parent
    if folder.name=="staged-victory-later-boulders-bridge-20261025" and folder.parent.name==".local":
        source=folder.parent.parent/".local/staged-victory-later-boulders-20261025/victory_later_boulders.py"
    elif folder.name=="laya_pokemon" and folder.parent.name=="src":
        source=folder.parent.parent/"src/laya_pokemon/victory_later_boulders.py"
    else:raise RuntimeError("Later-boulder bridge requires its exact stage or formal directory")
    resolved=source.resolve(strict=True)
    if resolved!=source.absolute() or sha256(resolved.read_bytes()).hexdigest() not in PURE_SHA256S:
        raise RuntimeError("Later-boulder pure source path/hash mismatch")
    spec=importlib.util.spec_from_file_location("laya_pokemon._victory_later_boulders_exact_source",resolved)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if Path(module.__file__).resolve()!=resolved:raise RuntimeError("Later-boulder pure module source mismatch")
    return module


boulder=_load_exact_controller()
MECHANIC="victory_later_boulder"
_CONTROLLERS=globals().get("_CONTROLLERS",{})
_BINDINGS=globals().get("_BINDINGS",{})
_COMPLETED=globals().get("_COMPLETED",set())
_FORBIDDEN={"event","item","badge","next_map","terminal","await_script_event"}
_BATTLE_PHASES={"battle_menu","battle_bag","battle_animation","battle_dialogue",
                "learning_menu","dialogue","strategy_review","campaign_review"}
_ACTIONS={"up","down","left","right","a","b","start","wait"}


def _review(reason):
    return dict(phase="campaign_review",objective="Wait.",available_actions=["wait"],
                review_reason="victory_later_boulder_"+reason)


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
        return {**result,"later_boulder_owner_step":step_id,
                "later_boulder_battle_delegate":"await_existing_battle_context"}
    # The other battle fields remain in the original state; copy only existing
    # decision keys to avoid pure's WAIT hint overwriting real battle decisions.
    out={k:v for k,v in result.items() if k not in ("phase","objective","available_actions","controller_menu_verified")}
    out.update(phase=phase,objective=objective,available_actions=list(choices),
               later_boulder_owner_step=step_id,later_boulder_battle_delegate="existing_battle")
    if "controller_menu_verified" in state:out["controller_menu_verified"]=state["controller_menu_verified"]
    if "review_reason" in state:out["review_reason"]=state["review_reason"]
    return out


def _explicit(step):
    key=step.get("boulder_case")
    if type(key) is not str or key not in boulder.CASES:return False
    c=boulder.CASES[key]
    return (step.get("kind")=="interact" and step.get("mechanic")==MECHANIC
            and type(step.get("map_id")) is int and step["map_id"]==c["map_id"]
            and type(step.get("target")) is list and step["target"]==c["start_player"]
            and all(type(v) is int for v in step["target"])
            and not (_FORBIDDEN|{"boulder_intent","slot","event_id","ram_address"}).intersection(step))


def _completion(key,c,controller,position,signal,text,grid,frame):
    if (not isinstance(signal,dict) or signal.get("read_valid") is not True or signal.get("read_error") is not None
            or signal.get("profile")!=boulder.PROFILE or signal.get("source_commit")!=boulder.SOURCE_COMMIT
            or signal.get("case_key")!=key or type(signal.get("observation_frame")) is not int
            or signal["observation_frame"]!=frame or signal.get("location")!=position
            or position["map_id"]!=c["map_id"] or (position["x"],position["y"])!=controller.final_player
            or controller.case_key!=key or controller.case!=c or controller.contract!=c
            or controller.push_index!=len(c["pushes"]) or controller.closed_frame is None or controller.closed_frame>=frame
            or controller.pending is not None or controller.suspended or controller.error is not None):return False
    raw,stone,flags=signal.get("raw"),signal.get("stone"),signal.get("toggle_flags")
    if (not isinstance(raw,dict) or any(not boulder._int(raw.get(k)) for k in boulder._addresses(key))
            or not isinstance(stone,dict) or type(flags) is not list or len(flags)!=32 or any(not boulder._int(v) for v in flags)
            or any(type(stone.get(k)) is not int for k in ("slot","x","y","movement_byte2"))
            or (stone["slot"],stone["x"],stone["y"],stone["movement_byte2"])!=(c["slot"],*c["goal_stone"],16)
            or signal.get("event") is not True or not boulder._event(c,raw)
            or not raw["flags1"]&1 or raw["mode"]!=0 or raw["battle_raw"]!=0
            or signal.get("idle") is not True or signal.get("native_push_busy") is not False
            or boulder._native_state(raw,stone)!=(False,True)):return False
    for other_key,other in boulder.CASES.items():
        if other_key!=key and boulder._event(other,raw)!=(other_key in c["required_true"]):return False
    target_pair=key in ("3f_hole","2f_switch2")
    if boulder._hidden(flags,0x7A)!=target_pair or boulder._hidden(flags,0x60)==target_pair:return False
    own_gate=("gate2" if key=="2f_switch2" else "gate1") if c["gate"] else None
    if any(raw[k]!=v for k,v in c["gate_binding"].items() if k!=own_gate):return False
    from laya_pokemon.campaign_transactions import verified_blank_transaction_world
    if not verified_blank_transaction_world(text,grid) or not boulder._grid(grid,c,controller.final_player,frame):return False
    if c["gate"]:
        return (raw[own_gate]==c["gate"]["after"]
                and all(grid["tiles"][y][x]==new for x,y,old,new in c["gate"]["cells"]))
    return grid["tiles"][15][23]==0x22 and raw["gate1"]==0x1D


def context(pyboy,state,plan,step_id,text,grid,previous,*,now=None,reviewed_fainted_bench=()):
    """Bind one exact case/step/job; do not infer Strength or floor transitions."""
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
    if not _explicit(step):return _review("explicit_case_unverified"),step_id
    key=step["boulder_case"];c=boulder.CASES[key]
    try:
        if "training_job" not in plan or plan["training_job"] is None:raise ValueError("missing job")
        binding=(MECHANIC,_canonical(step),_canonical(plan["training_job"]))
    except (TypeError,ValueError):return _review("owner_unverified"),step_id
    if step_id in _BINDINGS and _BINDINGS[step_id]!=binding:return _review("case_or_owner_changed"),step_id
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
    start=dict(map_id=c["map_id"],x=c["start_player"][0],y=c["start_player"][1])
    if controller is None and position!=start:return None
    from laya_pokemon.campaign_transactions import verified_blank_transaction_world,ui_overworld_ready
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
    signal=boulder.read_later_boulder_observation(pyboy,frame,sdk,case_key=key)
    if controller is None:
        if not verified_blank_transaction_world(text,grid):return _review("initial_closed_world_required"),step_id
        if not isinstance(signal,dict) or signal.get("read_valid") is not True:
            return _review("initial_signal_unverified"),step_id
        controller=boulder.VictoryLaterBoulderController(key,reviewed_fainted_bench=reviewed_fainted_bench)
        _CONTROLLERS[step_id]=controller;_BINDINGS[step_id]=binding
    if getattr(controller,'reviewed_fainted_bench',())!=reviewed_fainted_bench:return _review('bound_recovery_allowance_changed'),step_id
    controller.__class__=boulder.VictoryLaterBoulderController
    result=controller.context(state,text=text,grid=grid,signal=signal,previous=previous,
        now=time.monotonic() if now is None else now,owner=step_id,overworld_ready=ui_overworld_ready(text,grid))
    if not isinstance(result,dict):return _review("controller_result_unverified"),step_id
    if result.get("later_boulder_battle_handoff") is True:
        return _handoff(state,result,step_id),step_id
    if result.get("later_boulder_complete") is True:
        if result.get("later_boulder_case")!=key or not _completion(key,c,controller,position,signal,text,grid,frame):
            return _review("completion_native_receipt_unverified"),step_id
        _COMPLETED.add(step_id)
        result={**result,"field_move_complete":True,"field_move_kind":"victory-later-boulder",
                "later_boulder_owner_step":step_id,"later_boulder_case":key}
        index=ids.index(step_id)+1
        return result,ids[index] if index<len(ids) else "complete"
    return {**result,"later_boulder_owner_step":step_id},step_id


