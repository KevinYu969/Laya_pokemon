"""固定Silph 3F/11F卡片門交易橋接；只把核對後子目標交回Laya。"""
import importlib
import json
import time
from . import silph_card_door
importlib.reload(silph_card_door)

_CONTROLLERS = globals().get('_CONTROLLERS', {})
_BINDINGS = globals().get('_BINDINGS', {})
_COMPLETED = globals().get('_COMPLETED', set())
MECHANIC = 'silph_card_door'


def _review(reason):
    return {'phase': 'campaign_review', 'objective': 'Wait.', 'available_actions': ['wait'],
            'review_reason': reason}


def applies(step_id, step):
    return bool(set(_BINDINGS) - _COMPLETED) or step_id in _BINDINGS or bool(
        step and step.get('mechanic') == MECHANIC)


def context(pyboy, state, plan, step_id, text, grid):
    active = set(_BINDINGS) - _COMPLETED
    if active and active != {step_id}:
        return _review('silph_card_bridge_owner_changed'), step_id
    step = next((s for s in plan['steps'] if s['id'] == step_id), None)
    if not step or step.get('mechanic') != MECHANIC:
        return (_review('silph_card_bridge_intent_changed'), step_id) if step_id in _BINDINGS else None
    intent = step.get('card_door_intent')
    if (not silph_card_door._intent(intent) or step.get('kind') != 'interact'
            or type(step.get('map_id')) is not int or step['map_id'] != intent['map_id']
            or step.get('target') != [intent['player_x'], intent['player_y']]
            or any(type(v) is not int for v in step.get('target', []))):
        return _review('silph_card_bridge_explicit_intent_unverified'), step_id
    binding = (MECHANIC, json.dumps(intent, sort_keys=True, separators=(',', ':')))
    if step_id in _BINDINGS and _BINDINGS[step_id] != binding:
        return _review('silph_card_bridge_intent_changed'), step_id
    loc = dict(map_id=intent['map_id'], x=intent['player_x'], y=intent['player_y'])
    if (state.get('location') != loc or any(type(v) is not int for v in state['location'].values())):
        return (_review('silph_card_bridge_location_changed'), step_id) if step_id in _BINDINGS else None
    frame, battle = state.get('frame'), state.get('battle_state', {})
    if (type(frame) is not int or type(battle.get('observation_frame')) is not int
            or battle['observation_frame'] != frame or battle.get('kind') != 'none'
            or battle.get('active') is not False or type(battle.get('raw')) is not int or battle['raw'] != 0):
        return _review('silph_card_bridge_battle_signal_unverified'), step_id
    try:
        before_frame = pyboy.frame_count
        facing = pyboy.memory[0xC109]
        after_facing = pyboy.memory[0xC109]
        after_frame = pyboy.frame_count
        if (type(facing) is not int or facing not in {0, 4, 8, 12}
                or type(after_facing) is not int or after_facing != facing
                or type(before_frame) is not int or type(after_frame) is not int
                or before_frame != frame or after_frame != frame):
            return _review('silph_card_bridge_facing_or_frame_unverified'), step_id
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, RuntimeError):
        return _review('silph_card_bridge_facing_or_frame_unverified'), step_id
    from .campaign_transactions import ui_overworld_ready, verified_blank_transaction_world
    controller = _CONTROLLERS.get(step_id)
    if controller is None:
        if not verified_blank_transaction_world(text, grid):
            return _review('silph_card_bridge_initial_closed_world_required'), step_id
        if facing != (8 if intent['facing'] == 'left' else 4):
            # 先由正常步行抵達正確朝向，沒有繞過基線的轉向按鍵。
            return _review('silph_card_bridge_initial_facing_required'), step_id
        _BINDINGS[step_id] = binding
        controller = silph_card_door.SilphCardDoorController(intent)
        _CONTROLLERS[step_id] = controller
    controller.__class__ = silph_card_door.SilphCardDoorController
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    signal = silph_card_door.read_silph_card_door(pyboy, intent=intent,
        observation_frame=frame, expected_location=state['location'], constants=constants)
    result = controller.context(text, state['progress'],
        location={**loc, 'facing': {0:'down',4:'up',8:'left',12:'right'}[facing], 'facing_raw':facing},
        battle_state=battle, door_signal=signal, world_grid=grid, frame=frame,
        now=time.monotonic(), overworld_ready=ui_overworld_ready(text, grid))
    if result.get('silph_card_door_complete'):
        _COMPLETED.add(step_id)
        index = plan['steps'].index(step) + 1
        return result, (plan['steps'][index]['id'] if index < len(plan['steps']) else 'complete')
    return result, step_id
