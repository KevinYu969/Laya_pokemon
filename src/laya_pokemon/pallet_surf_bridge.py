"""固定真新鎮下水交易橋接；只產生子目標，保留同owner實例跨reload。"""
import importlib
import json
import time

from . import pallet_surf
from .rocket_movement import read_rocket_movement

importlib.reload(pallet_surf)

MECHANIC = 'pallet_surf'
_CONTROLLERS = globals().get('_CONTROLLERS', {})
_BINDINGS = globals().get('_BINDINGS', {})
_COMPLETED = globals().get('_COMPLETED', set())


def _review(reason):
    return dict(phase='campaign_review', objective='Wait.', available_actions=['wait'],
                review_reason=reason)


def applies(step_id, step):
    return (bool(set(_BINDINGS)-_COMPLETED) or step_id in _BINDINGS
            or isinstance(step, dict) and step.get('mechanic') == MECHANIC)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def context(pyboy, state, plan, step_id, text, grid, previous):
    """只有原controller的surf_entry_complete收據可推進；地圖/位置不能代替。"""
    active = set(_BINDINGS)-_COMPLETED
    if active and active != {step_id}:
        return _review('pallet_surf_owner_changed'), step_id
    if not isinstance(plan, dict) or not isinstance(plan.get('steps'), list):
        return _review('pallet_surf_plan_unverified'), step_id
    matches = [s for s in plan['steps'] if isinstance(s, dict) and s.get('id') == step_id]
    if len(matches) != 1:
        return (_review('pallet_surf_step_unverified'), step_id) if active or matches else None
    step = matches[0]
    if step.get('mechanic') != MECHANIC:
        return (_review('pallet_surf_intent_changed'), step_id) if step_id in _BINDINGS else None
    intent = step.get('surf_intent')
    expected = pallet_surf.PALLET_SURF_INTENT
    if (type(intent) is not dict or intent != expected or set(intent) != set(expected)
            or any(type(intent[k]) is not type(v) for k, v in expected.items())
            or step.get('kind') != 'interact' or type(step.get('map_id')) is not int or step['map_id'] != 0
            or type(step.get('target')) is not list or step['target'] != [4, 13]
            or any(type(v) is not int for v in step['target'])
            or 'face' in step and step['face'] != 'down'
            or any(k in step for k in ('next_map', 'terminal', 'event', 'item', 'badge', 'await_script_event'))):
        return _review('pallet_surf_explicit_intent_unverified'), step_id
    try:
        binding = (MECHANIC, 0, (4, 13), _canonical(intent), _canonical(plan.get('training_job')))
    except (ValueError, TypeError):
        return _review('pallet_surf_owner_unverified'), step_id
    if step_id in _BINDINGS and _BINDINGS[step_id] != binding:
        return _review('pallet_surf_intent_or_owner_changed'), step_id
    if not isinstance(state, dict) or not isinstance(state.get('location'), dict):
        return _review('pallet_surf_state_unverified'), step_id
    controller = _CONTROLLERS.get(step_id)
    if step_id in _BINDINGS and controller is None:
        return _review('pallet_surf_original_controller_missing'), step_id
    if controller is not None and step_id not in _BINDINGS:
        return _review('pallet_surf_original_binding_missing'), step_id
    loc = state['location']
    pos = {k: loc.get(k) for k in ('map_id', 'x', 'y')}
    if controller is None and pos != pallet_surf.START:
        return None  # 尚在正常導航；已落水不能冒充新交易已完成。
    from .campaign_transactions import verified_blank_transaction_world, ui_overworld_ready
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    signal = pallet_surf.read_surf_observation(pyboy, state.get('frame'), constants)
    movement = read_rocket_movement(pyboy, observation_frame=state.get('frame'))
    if controller is None:
        if not verified_blank_transaction_world(text, grid):
            return _review('pallet_surf_initial_closed_world_required'), step_id
        if not isinstance(signal, dict) or signal.get('read_valid') is not True:
            return _review('pallet_surf_initial_signal_unverified'), step_id
        if not isinstance(movement, dict) or movement.get('read_valid') is not True:
            return _review('pallet_surf_initial_movement_unverified'), step_id
        controller = pallet_surf.PalletSurfController(intent)
        _CONTROLLERS[step_id] = controller
        _BINDINGS[step_id] = binding
    controller.__class__ = pallet_surf.PalletSurfController
    result = controller.context(text, state.get('progress'), location=loc,
        battle_state=state.get('battle_state'), grid=grid, signal=signal, movement=movement,
        frame=state.get('frame'), previous=previous, now=time.monotonic(),
        overworld_ready=ui_overworld_ready(text, grid))
    if result.get('surf_entry_complete') is True:
        if (pos != pallet_surf.LANDING or signal.get('read_valid') is not True
                or type(signal.get('mode')) is not int or signal['mode'] != 2
                or signal.get('location') != pos):
            return _review('pallet_surf_completion_location_or_mode_unverified'), step_id
        _COMPLETED.add(step_id)
        result = {**result, 'field_move_complete': True, 'field_move_kind': 'pallet-surf'}
        index = plan['steps'].index(step)+1
        return result, (plan['steps'][index]['id'] if index < len(plan['steps']) else 'complete')
    return result, step_id
