"""固定紅蓮→常磐原生Fly橋接候選；只讀觀測，不按鍵或步進遊戲。

純controller的唯一來源路徑是本專案的明確stage/formal檔案；不搜尋fixture。
parent負責全peer mutex。此橋接保存同一owner/controller/error/pending/budget。
"""
import importlib.util
import json
from pathlib import Path
import time


def _load_exact_controller():
    folder = Path(__file__).resolve().parent
    if (folder.name == "staged-fly-viridian-bridge-20261025"
            and folder.parent.name == ".local"):
        root = folder.parent.parent
        source = root / ".local/staged-fly-viridian-20261025/fly_viridian.py"
    elif folder.name == "laya_pokemon" and folder.parent.name == "src":
        root = folder.parent.parent
        source = root / "src/laya_pokemon/fly_viridian.py"
    else:
        raise RuntimeError("Fly bridge requires its exact staged or formal source directory")
    resolved = source.resolve(strict=True)
    if resolved != source.absolute():
        raise RuntimeError("Fly controller source path must not redirect outside its exact location")
    spec = importlib.util.spec_from_file_location("laya_pokemon._fly_viridian_exact_source", resolved)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if Path(module.__file__).resolve() != resolved:
        raise RuntimeError("Fly controller module source mismatch")
    return module


fly_viridian = _load_exact_controller()
MECHANIC = "fly_viridian"
_CONTROLLERS = globals().get("_CONTROLLERS", {})
_BINDINGS = globals().get("_BINDINGS", {})
_COMPLETED = globals().get("_COMPLETED", set())
_FORBIDDEN = {"event", "item", "badge", "next_map", "terminal", "await_script_event"}


def _review(reason):
    return dict(phase="campaign_review", objective="Wait.", available_actions=["wait"],
                review_reason="fly_viridian_" + reason)


def applies(step_id, step):
    return (bool(set(_BINDINGS) - _COMPLETED)
            or isinstance(step_id, str) and step_id in _BINDINGS
            or isinstance(step, dict) and step.get("mechanic") == MECHANIC)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _explicit(step):
    intent = step.get("fly_intent")
    expected = fly_viridian.FLY_VIRIDIAN_INTENT
    return (step.get("kind") == "interact" and step.get("mechanic") == MECHANIC
            and type(step.get("map_id")) is int and step["map_id"] == 8
            and type(step.get("target")) is list and step["target"] == [18, 4]
            and all(type(value) is int for value in step["target"])
            and type(intent) is dict and intent == expected and set(intent) == set(expected)
            and all(type(intent[key]) is type(value) for key, value in expected.items())
            and not _FORBIDDEN.intersection(step))


def context(pyboy, state, plan, step_id, text, grid, previous):
    """保留真previous與同frame封包；只有原controller的完整落地收據能前進。"""
    active = set(_BINDINGS) - _COMPLETED
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
                if step_id in _BINDINGS else None)
    if not _explicit(step):
        return _review("explicit_intent_unverified"), step_id
    try:
        binding = (MECHANIC, _canonical(step), _canonical(plan.get("training_job")))
    except (ValueError, TypeError):
        return _review("owner_unverified"), step_id
    if step_id in _BINDINGS and _BINDINGS[step_id] != binding:
        return _review("intent_or_owner_changed"), step_id
    controller = _CONTROLLERS.get(step_id)
    if step_id in _BINDINGS and controller is None:
        return _review("original_controller_missing"), step_id
    if (controller is not None or step_id in _COMPLETED) and step_id not in _BINDINGS:
        return _review("original_binding_missing"), step_id
    if not isinstance(state, dict) or not isinstance(state.get("location"), dict):
        return _review("state_unverified"), step_id
    loc = state["location"]
    frame = state.get("frame")
    if (type(frame) is not int or frame < 0
            or any(type(loc.get(key)) is not int or not 0 <= loc[key] <= 255
                   for key in ("map_id", "x", "y"))):
        return _review("frame_or_location_unverified"), step_id
    position = {key: loc[key] for key in ("map_id", "x", "y")}
    if controller is None and position != fly_viridian.START:
        return None  # 未綁定前交正常導航；已綁定後絕不因離開起點提前放手。

    from laya_pokemon.campaign_transactions import verified_blank_transaction_world, ui_overworld_ready
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    signal = fly_viridian.read_fly_observation(pyboy, frame, constants)
    if controller is None:
        if not verified_blank_transaction_world(text, grid):
            return _review("initial_closed_world_required"), step_id
        if not isinstance(signal, dict) or signal.get("read_valid") is not True:
            return _review("initial_signal_unverified"), step_id
        controller = fly_viridian.FlyViridianController(step["fly_intent"])
        _CONTROLLERS[step_id] = controller
        _BINDINGS[step_id] = binding
    controller.__class__ = fly_viridian.FlyViridianController
    result = controller.context(text, state.get("progress"), location=loc,
        battle_state=state.get("battle_state"), grid=grid, signal=signal, frame=frame,
        previous=previous, now=time.monotonic(), overworld_ready=ui_overworld_ready(text, grid))
    if not isinstance(result, dict):
        return _review("controller_result_unverified"), step_id
    if result.get("fly_viridian_complete") is True:
        if (position != fly_viridian.LANDING or not isinstance(signal, dict)
                or signal.get("read_valid") is not True or signal.get("location") != position
                or type(signal.get("observation_frame")) is not int
                or signal["observation_frame"] != frame):
            return _review("completion_location_or_signal_unverified"), step_id
        _COMPLETED.add(step_id)
        result = {**result, "field_move_complete": True, "field_move_kind": "fly-viridian"}
        index = plan["steps"].index(step) + 1
        following = plan["steps"][index]["id"] if index < len(plan["steps"]) else "complete"
        return result, following
    return result, step_id
