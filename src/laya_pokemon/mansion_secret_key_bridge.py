"""固定洋館秘密鑰匙拾取橋接；保留原controller及預算，不直接送鍵。"""
import importlib
import json
import time

from . import mansion_secret_key

importlib.reload(mansion_secret_key)

MECHANIC = 'mansion_secret_key'
_CONTROLLERS = globals().get('_CONTROLLERS', {})
_BINDINGS = globals().get('_BINDINGS', {})
_COMPLETED = globals().get('_COMPLETED', set())


def _review(reason):
    return dict(phase='campaign_review', objective='Wait.', available_actions=['wait'],
                review_reason='mansion_secret_key_bridge_' + reason)


def applies(step_id, step):
    return (bool(set(_BINDINGS) - _COMPLETED) or step_id in _BINDINGS
            or isinstance(step, dict) and step.get('mechanic') == MECHANIC)


def _position(loc):
    return (isinstance(loc, dict) and all(type(loc.get(k)) is int and loc[k] == v
            for k, v in mansion_secret_key.LOCATION.items()))


def _signal(signal, frame):
    return (isinstance(signal, dict) and signal.get('read_valid') is True
            and signal.get('read_error') is None and signal.get('profile') == mansion_secret_key.PROFILE
            and signal.get('source_commit') == mansion_secret_key.SOURCE_COMMIT
            and type(signal.get('observation_frame')) is int and signal['observation_frame'] == frame
            and _position(signal.get('location')))


def _closed(text, grid, frame):
    from .campaign_transactions import verified_blank_transaction_world
    return (isinstance(text, dict) and isinstance(grid, dict)
            and all('observation_frame' not in p or
                    (type(p['observation_frame']) is int and p['observation_frame'] == frame)
                    for p in (text, grid)) and verified_blank_transaction_world(text, grid))


def context(pyboy, state, plan, step_id, text, grid, previous):
    """只在固定站位綁基線；真controller的完整拾取收據才推進。"""
    if type(step_id) is not str or not step_id:
        return _review('step_id_unverified'), step_id
    active = set(_BINDINGS) - _COMPLETED
    if active and active != {step_id}:
        return _review('owner_changed'), step_id
    if not isinstance(plan, dict) or type(plan.get('steps')) is not list:
        return _review('plan_unverified'), step_id
    matches = [s for s in plan['steps'] if isinstance(s, dict) and s.get('id') == step_id]
    if len(matches) != 1:
        return (_review('step_unverified'), step_id) if active or matches else None
    step = matches[0]
    if step.get('mechanic') != MECHANIC:
        return (_review('intent_changed'), step_id) if step_id in _BINDINGS else None
    intent = step.get('key_intent')
    if (not mansion_secret_key._intent(intent) or step.get('kind') != 'interact'
            or type(step.get('map_id')) is not int or step['map_id'] != 216
            or type(step.get('target')) is not list or step['target'] != [5, 12]
            or any(type(v) is not int for v in step['target'])
            or any(k in step for k in ('next_map', 'terminal', 'event', 'item', 'badge', 'await_script_event'))):
        return _review('explicit_intent_unverified'), step_id
    try:
        binding = json.dumps([MECHANIC, intent, plan.get('training_job')], sort_keys=True,
                             ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return _review('owner_unverified'), step_id
    if step_id in _BINDINGS and _BINDINGS[step_id] != binding:
        return _review('intent_or_owner_changed'), step_id
    controller = _CONTROLLERS.get(step_id)
    if step_id in _BINDINGS and controller is None:
        return _review('original_controller_missing'), step_id
    if controller is not None and step_id not in _BINDINGS:
        return _review('original_binding_missing'), step_id
    if (not isinstance(state, dict) or type(state.get('frame')) is not int or state['frame'] < 0
            or not isinstance(state.get('location'), dict)):
        return _review('state_unverified'), step_id
    loc, frame = state['location'], state['frame']
    if controller is None and not _position(loc):
        return None
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    signal = mansion_secret_key.read_mansion_secret_key(pyboy, frame, constants)
    if controller is None:
        if not _closed(text, grid, frame):
            return _review('initial_closed_world_required'), step_id
        if not _signal(signal, frame) or signal.get('item_hidden') is not False:
            return _review('initial_source_unknown'), step_id
        controller = mansion_secret_key.MansionSecretKeyController(intent)
        _CONTROLLERS[step_id] = controller
        _BINDINGS[step_id] = binding
    controller.__class__ = mansion_secret_key.MansionSecretKeyController
    from .campaign_transactions import ui_overworld_ready
    result = controller.context(text, state.get('progress'), location=loc,
        battle_state=state.get('battle_state'), grid=grid, signal=signal, frame=frame,
        previous=previous, now=time.monotonic(), overworld_ready=ui_overworld_ready(text, grid))
    if not isinstance(result, dict):
        return _review('controller_result_unverified'), step_id
    if result.get('mansion_secret_key_complete') is True:
        if (not _position(loc) or not _signal(signal, frame) or signal.get('item_hidden') is not True
                or not _closed(text, grid, frame)):
            return _review('completion_source_or_closed_world_unverified'), step_id
        _COMPLETED.add(step_id)
        result = {**result, 'field_move_complete': True, 'field_move_kind': 'mansion-secret-key'}
        index = plan['steps'].index(step) + 1
        return result, (plan['steps'][index]['id'] if index < len(plan['steps']) else 'complete')
    return result, step_id
