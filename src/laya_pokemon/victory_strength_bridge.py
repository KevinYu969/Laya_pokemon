"""固定VictoryRoad1F原生Strength啟用橋接候選；只讀觀測，不按鍵或步進遊戲。

純controller的唯一來源路徑是本專案的明確stage/formal檔案；不搜尋fixture。
parent負責全peer mutex。此橋接保存同一owner/controller/error/pending/budget。
"""
import importlib.util
from hashlib import sha256
import json
from pathlib import Path
import time


PURE_SHA256="6c3df8932f7f37d32bf29a75ab4b579f40fec7f2ea3e47683603b2b2008a03bb"
PURE_CRLF_SHA256="ffe1cf5c5e59061435c1387310631bc077530ffc47a3804ad994412664e1f06c"
PURE_SHA256S=(PURE_SHA256,PURE_CRLF_SHA256)


def _load_exact_controller():
    folder = Path(__file__).resolve().parent
    if (folder.name == "staged-victory-strength-floors-20261025"
            and folder.parent.name == ".local"):
        root = folder.parent.parent
        source = root / ".local/staged-victory-strength-floors-20261025/victory_strength.py"
    elif folder.name == "laya_pokemon" and folder.parent.name == "src":
        root = folder.parent.parent
        source = root / "src/laya_pokemon/victory_strength.py"
    else:
        raise RuntimeError("Strength bridge requires its exact staged or formal source directory")
    resolved = source.resolve(strict=True)
    if resolved != source.absolute() or sha256(resolved.read_bytes()).hexdigest() not in PURE_SHA256S:
        raise RuntimeError("Strength controller source path must not redirect outside its exact location")
    spec = importlib.util.spec_from_file_location("laya_pokemon._victory_strength_exact_source", resolved)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if Path(module.__file__).resolve() != resolved:
        raise RuntimeError("Strength controller module source mismatch")
    return module


victory_strength = _load_exact_controller()
MECHANIC = "victory_strength"
_CONTROLLERS = globals().get("_CONTROLLERS", {})
_BINDINGS = globals().get("_BINDINGS", {})
_COMPLETED = globals().get("_COMPLETED", set())
_FORBIDDEN = {"event", "item", "badge", "next_map", "terminal", "await_script_event"}


def _review(reason):
    return dict(phase="campaign_review", objective="Wait.", available_actions=["wait"],
                review_reason="victory_strength_" + reason)


def _active():
    if type(_CONTROLLERS) is not dict or type(_BINDINGS) is not dict or type(_COMPLETED) is not set:return None
    return (set(_BINDINGS)|set(_CONTROLLERS))-_COMPLETED


def applies(step_id, step):
    active=_active()
    return (active is None or bool(active)
            or isinstance(step_id, str) and step_id in _BINDINGS
            or isinstance(step, dict) and step.get("mechanic") == MECHANIC)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _explicit(step):
    intent=step.get("strength_intent");key=victory_strength._intent_key(intent)
    if key is None:return False
    c=victory_strength.STANCES[key];start=c["start"]
    return (step.get("kind")=="interact" and step.get("mechanic")==MECHANIC
        and type(step.get("map_id")) is int and step["map_id"]==start["map_id"]
        and type(step.get("target")) is list and step["target"]==[start["x"],start["y"]]
        and all(type(v) is int for v in step["target"]) and not _FORBIDDEN.intersection(step))


def context(pyboy, state, plan, step_id, text, grid, previous):
    """保留真previous與同frame封包；只有原controller的完整原生閉合收據能前進。"""
    active = _active()
    if active is None:return _review("registries_unverified"),step_id
    if not isinstance(step_id, str) or not step_id:
        return _review("step_id_unverified"), step_id
    if active and active != {step_id}:
        return _review("owner_changed"), step_id
    if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list):
        return _review("plan_unverified"), step_id
    ids = [step.get("id") if isinstance(step, dict) else None for step in plan["steps"]]
    if (any(not isinstance(value, str) or not value for value in ids)
            or len(ids) != len(set(ids))):
        return _review("plan_unverified"), step_id
    matches = [step for step in plan["steps"]
               if isinstance(step, dict) and step.get("id") == step_id]
    if len(matches) != 1:
        return ((_review("step_unverified"), step_id)
                if active or matches or step_id in _BINDINGS else None)
    step = matches[0]
    if step.get("mechanic") != MECHANIC:
        return ((_review("intent_changed"), step_id)
                if step_id in _BINDINGS or active else None)
    if not _explicit(step):
        return _review("explicit_intent_unverified"), step_id
    try:
        if "training_job" not in plan or plan["training_job"] is None:raise ValueError("missing job")
        binding = (MECHANIC, _canonical(step), _canonical(plan["training_job"]))
    except (ValueError, TypeError):
        return _review("owner_unverified"), step_id
    if step_id in _BINDINGS and _BINDINGS[step_id] != binding:
        return _review("intent_or_owner_changed"), step_id
    controller = _CONTROLLERS.get(step_id)
    if step_id in _BINDINGS and controller is None:
        return _review("original_controller_missing"), step_id
    if (controller is not None or step_id in _COMPLETED) and step_id not in _BINDINGS:
        return _review("original_binding_missing"), step_id
    if step_id in _COMPLETED:
        return _review("completed_step_reentered"),step_id
    if not isinstance(state, dict) or not isinstance(state.get("location"), dict):
        return _review("state_unverified"), step_id
    loc = state["location"]
    frame = state.get("frame")
    if (type(frame) is not int or frame < 0
            or any(type(loc.get(key)) is not int or not 0 <= loc[key] <= 255
                   for key in ("map_id", "x", "y"))):
        return _review("frame_or_location_unverified"), step_id
    position = {key: loc[key] for key in ("map_id", "x", "y")}
    if controller is None and position != victory_strength.STANCES[victory_strength._intent_key(step["strength_intent"])]["start"]:
        return None  # 未綁定前交正常導航；已綁定後留在原owner，由pure核同一站位。

    from laya_pokemon.campaign_transactions import verified_blank_transaction_world, ui_overworld_ready
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    signal = victory_strength.read_strength_observation(pyboy, frame, constants)
    if controller is None:
        if not verified_blank_transaction_world(text, grid):
            return _review("initial_closed_world_required"), step_id
        if not isinstance(signal, dict) or signal.get("read_valid") is not True:
            return _review("initial_signal_unverified"), step_id
        controller = victory_strength.VictoryStrengthController(step["strength_intent"])
        _CONTROLLERS[step_id] = controller
        _BINDINGS[step_id] = binding
    controller.__class__ = victory_strength.VictoryStrengthController
    result = controller.context(text, state.get("progress"), location=loc,
        battle_state=state.get("battle_state"), grid=grid, signal=signal, frame=frame,
        previous=previous, now=time.monotonic(), overworld_ready=ui_overworld_ready(text, grid))
    if not isinstance(result, dict):
        return _review("controller_result_unverified"), step_id
    if result.get("victory_strength_complete") is True:
        if (position != controller.start or not isinstance(signal, dict)
                or signal.get("read_valid") is not True or signal.get("location") != position
                or type(signal.get("observation_frame")) is not int
                or signal["observation_frame"] != frame
                or signal.get("profile") != victory_strength.PROFILE
                or signal.get("source_commit") != victory_strength.SOURCE_COMMIT
                or signal.get("strength_active") is not True or signal.get("idle") is not True
                or type(signal.get("raw_flags")) is not int or not 0 <= signal["raw_flags"] <= 255
                or not signal["raw_flags"] & victory_strength.FLAG_MASK
                or type(signal.get("mode")) is not int or signal["mode"] != 0
                or type(signal.get("battle_raw")) is not int or signal["battle_raw"] != 0
                or not victory_strength._source_signal_valid(signal,controller.intent)
                or not victory_strength._world(grid,frame,controller.intent)
                or not controller.strength_selected or not controller.prompt_ack
                or controller.closed_frame is None or controller.closed_frame>=frame
                or controller.pending is not None or controller.error is not None):
            return _review("completion_activation_or_signal_unverified"), step_id
        _COMPLETED.add(step_id)
        result = {**result, "field_move_complete": True, "field_move_kind": "victory-strength", "victory_strength_case": victory_strength._intent_key(controller.intent)}
        index = plan["steps"].index(step) + 1
        following = plan["steps"][index]["id"] if index < len(plan["steps"]) else "complete"
        return result, following
    return result, step_id
