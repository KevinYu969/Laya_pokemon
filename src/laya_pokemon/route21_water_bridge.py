"""固定21號水路橋接；保留原水步實例，野戰交還既有戰鬥控制。"""
import importlib
import json
import time

from . import pallet_surf, route21_water
from .rocket_movement import read_rocket_movement

importlib.reload(route21_water)

MECHANIC = 'route21_water'
_CONTROLLERS = globals().get('_CONTROLLERS', {})
_BINDINGS = globals().get('_BINDINGS', {})
_COMPLETED = globals().get('_COMPLETED', set())


def _review(reason):
    return dict(phase='campaign_review', objective='Wait.', available_actions=['wait'],
                review_reason='route21_water_bridge_' + reason)


def applies(step_id, step):
    return (bool(set(_BINDINGS) - _COMPLETED) or step_id in _BINDINGS
            or isinstance(step, dict) and step.get('mechanic') == MECHANIC)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _position(value):
    if (not isinstance(value, dict) or any(type(value.get(k)) is not int
            or not 0 <= value[k] <= 255 for k in ('map_id', 'x', 'y'))):
        return None
    return tuple(value[k] for k in ('map_id', 'x', 'y'))


def _signal(signal, state, mode):
    frame = state.get('frame')
    battle = state.get('battle_state')
    return (isinstance(signal, dict) and signal.get('profile') == pallet_surf.PROFILE
            and signal.get('source_commit') == route21_water.SOURCE_COMMIT
            and signal.get('read_valid') is True and signal.get('read_error') is None
            and type(signal.get('observation_frame')) is int
            and signal['observation_frame'] == frame
            and type(signal.get('mode')) is int and signal['mode'] == mode
            and _position(signal.get('location')) == _position(state.get('location'))
            and isinstance(battle, dict) and type(battle.get('observation_frame')) is int
            and battle['observation_frame'] == frame and battle.get('kind') == 'none'
            and battle.get('active') is False and type(battle.get('raw')) is int
            and battle['raw'] == 0 and type(signal.get('battle_raw')) is int
            and signal['battle_raw'] == 0)


def _closed(text, grid, frame):
    from .campaign_transactions import verified_blank_transaction_world
    return (isinstance(text, dict) and isinstance(grid, dict)
            and all('observation_frame' not in packet or
                    (type(packet['observation_frame']) is int and packet['observation_frame'] == frame)
                    for packet in (text, grid))
            and verified_blank_transaction_world(text, grid))


def context(pyboy, state, plan, step_id, text, grid, previous):
    """只在已上水的初始格綁定；完整水路收據與真上岸閉合才推進。"""
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
    intent = step.get('water_intent')
    if (not route21_water._intent(intent) or step.get('kind') != 'interact'
            or type(step.get('map_id')) is not int or step['map_id'] != 0
            or type(step.get('target')) is not list or step['target'] != [4, 14]
            or any(type(v) is not int for v in step['target'])
            or any(k in step for k in ('next_map', 'terminal', 'event', 'item', 'badge',
                                      'await_script_event'))):
        return _review('explicit_intent_unverified'), step_id
    try:
        binding = (MECHANIC, 0, (4, 14), _canonical(intent), _canonical(plan.get('training_job')))
    except (ValueError, TypeError):
        return _review('owner_unverified'), step_id
    if step_id in _BINDINGS and _BINDINGS[step_id] != binding:
        return _review('intent_or_owner_changed'), step_id
    controller = _CONTROLLERS.get(step_id)
    if step_id in _BINDINGS and controller is None:
        return _review('original_controller_missing'), step_id
    if controller is not None and step_id not in _BINDINGS:
        return _review('original_binding_missing'), step_id
    if (not isinstance(state, dict) or type(state.get('frame')) is not int
            or state['frame'] < 0 or _position(state.get('location')) is None):
        return _review('state_unverified'), step_id
    pos = _position(state['location'])
    if controller is None and pos != (0, 4, 14):
        return None  # 既有正常導航；不可在遠方或終點憑空建立完成交易。
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    frame = state['frame']
    signal = pallet_surf.read_surf_observation(pyboy, frame, constants)
    movement = read_rocket_movement(pyboy, observation_frame=frame)
    if controller is None:
        if not _closed(text, grid, frame):
            return _review('initial_closed_world_required'), step_id
        if not _signal(signal, state, 2) or pallet_surf._idle(movement, frame) is not True:
            return _review('initial_water_signal_or_idle_unverified'), step_id
        controller = route21_water.Route21WaterController(intent)
        _CONTROLLERS[step_id] = controller
        _BINDINGS[step_id] = binding
    controller.__class__ = route21_water.Route21WaterController
    # 不改原state；完整decoder封包及真previous由同一controller自行核對。
    observed = {**state, 'text': text}
    result = controller.context(observed, grid=grid, signal=signal, movement=movement,
                                previous=previous, now=time.monotonic())
    if result is None:
        return None  # 必須讓既有battle處理；不能包成(None, step_id)。
    if not isinstance(result, dict):
        return _review('controller_result_unverified'), step_id
    if result.get('route21_water_complete') is True:
        if (pos != (8, 4, 10) or not _signal(signal, state, 0)
                or not _closed(text, grid, frame) or pallet_surf._idle(movement, frame) is not True):
            return _review('completion_landfall_or_closed_world_unverified'), step_id
        _COMPLETED.add(step_id)
        result = {**result, 'field_move_complete': True, 'field_move_kind': 'route21-water'}
        index = plan['steps'].index(step) + 1
        return result, (plan['steps'][index]['id'] if index < len(plan['steps']) else 'complete')
    return result, step_id
