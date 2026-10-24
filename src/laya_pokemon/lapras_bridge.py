"""固定Lapras贈送橋接與窄命名過渡候選；未接runner／實況。

pre_attrition_context只續接已綁owner的來源過渡，不建立或補造party資料。
呼叫端仍須只在party_read_not_verified類安全閘使用；其他失敗不得旁路。
"""
from copy import deepcopy
import importlib
import json
import time

from . import lapras_gift

importlib.reload(lapras_gift)

MECHANIC = 'silph_lapras_gift'
GRID_SOURCE = 'wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM'
_CONTROLLERS = globals().get('_CONTROLLERS', {})
_BINDINGS = globals().get('_BINDINGS', {})
_COMPLETED = globals().get('_COMPLETED', set())


def _review(reason):
    return dict(phase='campaign_review', objective='Wait.', available_actions=['wait'],
                review_reason='lapras_bridge_' + reason.removeprefix('lapras_bridge_'))


def applies(step_id, step):
    return bool(set(_BINDINGS) - _COMPLETED) or step_id in _BINDINGS or (
        isinstance(step, dict) and step.get('mechanic') == MECHANIC)


def _foreign_owner_active():
    """只查既有交易registry，不讀遊戲；不讓prehook蓋過別人的owner。"""
    from . import (campaign_transactions, capture_transaction, safari_entry,
                   hm_teaching_bridge, vending_bridge, saffron_guard_bridge, silph_card_bridge)
    for module in (campaign_transactions, safari_entry, hm_teaching_bridge, vending_bridge,
                   saffron_guard_bridge, silph_card_bridge):
        if (not isinstance(module._BINDINGS, dict) or not isinstance(module._COMPLETED, set)
                or set(module._BINDINGS) - module._COMPLETED):
            return True
    sessions = capture_transaction._SESSIONS
    return (safari_entry._RUN_CONTROLLER is not None or not isinstance(sessions, dict)
            or any(not isinstance(s, dict) or s.get('done') is not True for s in sessions.values()))


def _request(state, plan, step_id):
    """回傳精確意圖；None留原路徑，review結果仍保持原step。"""
    active = set(_BINDINGS) - _COMPLETED
    if active and active != {step_id}:
        return _review('owner_changed')
    if not isinstance(plan, dict) or not isinstance(plan.get('steps'), list):
        return _review('plan_unverified')
    step = next((s for s in plan['steps'] if isinstance(s, dict) and s.get('id') == step_id), None)
    if not step or step.get('mechanic') != MECHANIC:
        return _review('intent_changed') if step_id in _BINDINGS else None
    intent = step.get('lapras_gift_intent')
    if (not lapras_gift._valid_intent(intent) or step.get('kind') != 'interact'
            or type(step.get('map_id')) is not int or step['map_id'] != intent['map_id']
            or step.get('target') != [intent['player_x'], intent['player_y']]
            or any(type(v) is not int for v in step.get('target', []))):
        return _review('explicit_intent_unverified')
    binding = (MECHANIC, json.dumps(intent, sort_keys=True, separators=(',', ':')))
    if step_id in _BINDINGS and _BINDINGS[step_id] != binding:
        return _review('intent_changed')
    if step_id in _CONTROLLERS and step_id not in _BINDINGS:
        return _review('controller_without_binding')
    if step_id in _BINDINGS and step_id not in _CONTROLLERS:
        return _review('bound_controller_missing')
    loc = dict(map_id=intent['map_id'], x=intent['player_x'], y=intent['player_y'])
    if (not isinstance(state, dict) or state.get('location') != loc
            or any(type(v) is not int for v in state.get('location', {}).values())):
        return _review('location_changed') if step_id in _BINDINGS else None
    if _foreign_owner_active():
        return _review('other_transaction_active')
    return dict(step=step, intent=intent, binding=binding, location=loc)


def _observation(pyboy, state, text):
    """朝向前後真int與frame包住讀取，再用既有SDK雙讀raw getter。"""
    frame, battle = state.get('frame'), state.get('battle_state')
    if (type(frame) is not int or frame < 0 or not isinstance(battle, dict)
            or type(battle.get('observation_frame')) is not int
            or battle['observation_frame'] != frame or battle.get('kind') != 'none'
            or battle.get('active') is not False or type(battle.get('raw')) is not int
            or battle['raw'] != 0):
        return _review('battle_or_frame_unverified')
    for packet in (text, state.get('progress'), state['location'], battle):
        if not isinstance(packet, dict) or ('observation_frame' in packet and (
                type(packet['observation_frame']) is not int or packet['observation_frame'] != frame)):
            return _review('packet_frame_disagrees')
    try:
        before = pyboy.frame_count
        facing = pyboy.memory[0xC109]
        after_facing = pyboy.memory[0xC109]
        after = pyboy.frame_count
        if (type(before) is not int or type(after) is not int or before != frame or after != frame
                or type(facing) is not int or type(after_facing) is not int
                or facing != after_facing or facing != 8):
            return _review('facing_or_frame_unverified')
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, RuntimeError):
        return _review('facing_or_frame_unverified')
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    signal = lapras_gift.read_lapras_gift(pyboy, observation_frame=frame,
        expected_location=state['location'], constants=constants)
    return dict(signal=signal, facing=facing, frame=frame)


def _closed_grid(grid, state):
    """不以任意非None網格當野外證據；至少12個同幀可見背景錨。"""
    if (not isinstance(grid, dict) or grid.get('source') != GRID_SOURCE
            or type(grid.get('observation_frame')) is not int
            or grid['observation_frame'] != state['frame']
            or grid.get('verified_location') != [212, 2, 5]
            or any(type(v) is not int for v in grid['verified_location'])):
        return False
    tiles, walk = grid.get('tiles'), grid.get('walkable')
    if (not isinstance(walk, (list, tuple)) or not walk or not isinstance(walk[0], (list, tuple))
            or not walk[0] or not isinstance(tiles, (list, tuple)) or len(tiles) != len(walk)):
        return False
    height, width = len(walk), len(walk[0])
    if width > 100 or height > 72 or not (2 < width and 5 < height):
        return False
    for matrix, high in ((walk, 1), (tiles, 255)):
        if any(not isinstance(row, (list, tuple)) or len(row) != width
               or any(type(v) is not int or not 0 <= v <= high for v in row) for row in matrix):
            return False
    visible = grid.get('visible_verified_cells')
    return (isinstance(visible, list) and type(grid.get('screen_cells_verified')) is int
            and grid['screen_cells_verified'] == len(visible) and len(visible) >= 12
            and all(isinstance(v, list) and len(v) == 2 and type(v[0]) is int and type(v[1]) is int
                    and 0 <= v[0] < width and 0 <= v[1] < height for v in visible)
            and len({tuple(v) for v in visible}) == len(visible)
            and [2, 5] in visible and [1, 5] in visible and walk[5][2] == 1)


def _ready(text, grid, state):
    from .campaign_transactions import ui_overworld_ready
    return _closed_grid(grid, state) and ui_overworld_ready(text, grid)


def _deliver(controller, observed, state, request, text, grid, step_id, *, prehook=False):
    controller.__class__ = lapras_gift.LaprasGiftController
    result = controller.context(text, state['progress'],
        location={**request['location'], 'facing': 'left', 'facing_raw': observed['facing']},
        battle_state=state['battle_state'], gift_signal=observed['signal'],
        frame=observed['frame'], now=time.monotonic(), overworld_ready=_ready(text, grid, state))
    result = {**result, 'lapras_bridge_owner_step': step_id}
    if prehook:
        if result.get('lapras_gift_complete'):
            return _review('pre_attrition_cannot_complete')
        result['lapras_pre_attrition_transition'] = True
    return result


def context(pyboy, state, plan, step_id, text, grid):
    """正常field交易；完整第6與兩closed只有purecontroller能宣告。"""
    request = _request(state, plan, step_id)
    if request is None:
        return None
    if 'review_reason' in request:
        return request, step_id
    observed = _observation(pyboy, state, text)
    if 'review_reason' in observed:
        return observed, step_id
    if grid is not None and not _closed_grid(grid, state):
        return _review('provided_grid_unverified'), step_id
    controller = _CONTROLLERS.get(step_id)
    if controller is None:
        from .campaign_transactions import verified_blank_transaction_world
        if not _closed_grid(grid, state) or not verified_blank_transaction_world(text, grid):
            return _review('initial_closed_world_required'), step_id
        party = lapras_gift._party(state['progress'])
        if (party is None or len(party) != 5 or any(mon['hp'] <= 0 for mon in party)
                or party[0]['hp'] * 3 <= party[0]['max_hp'] * 2):
            return _review('initial_health_unverified'), step_id
        _BINDINGS[step_id] = request['binding']
        controller = lapras_gift.LaprasGiftController(request['intent'])
        controller.initial_health_verified = True
        controller.initial_health_party = deepcopy(party)
        _CONTROLLERS[step_id] = controller
    result = _deliver(controller, observed, state, request, text, grid, step_id)
    if result.get('lapras_gift_complete'):
        if (result['lapras_gift_complete'] is not True or controller.stage != 'complete'
                or result.get('phase') != 'lapras_gift_complete' or result.get('available_actions') != ['wait']):
            return _review('completion_contract_unverified'), step_id
        _COMPLETED.add(step_id)
        index = plan['steps'].index(request['step']) + 1
        return result, plan['steps'][index]['id'] if index < len(plan['steps']) else 'complete'
    return result, step_id


def _sixth_fully_initialized(signal):
    """只看真raw，不造progress；完整來源第6出現時不得用未知party接口旁路。"""
    raw = signal['new_mon_raw']
    mon = lapras_gift._raw_mon(raw)
    if mon is None:
        return False
    dv1, dv2 = raw[27:29]
    hp_dv = ((dv1 >> 4 & 1) << 3) | ((dv1 & 1) << 2) | ((dv2 >> 4 & 1) << 1) | (dv2 & 1)
    hp = 2 * (130 + hp_dv) * 15 // 100 + 25
    return (mon == dict(species=19, level=15, hp=hp, max_hp=hp, status=0, exp=4218,
                        moves=[55, 45, 0, 0], pp=[25, 40, 0, 0])
            and not any(raw[17:27]) and raw[3] == 0)


def _native_transition(controller, text):
    rows = lapras_gift._rows(text)
    if rows is None or not controller.receipt_seen:
        return False
    stage = controller.stage
    if stage == 'gift':
        allowed = [lapras_gift._screen(('KEVIN got', 'LAPRAS!')),
                   lapras_gift._screen(lapras_gift.QUESTION, arrow=True)]
    elif stage == 'nickname' and controller.question_ack and controller.append_seen:
        allowed = [lapras_gift._screen(lapras_gift.QUESTION, arrow=True),
                   lapras_gift._screen(lapras_gift.QUESTION, scroll=True)]
        allowed += [lapras_gift._screen(lapras_gift.NICKNAME, cursor=cursor) for cursor in (None, 8, 10)]
    elif stage == 'post_no' and controller.no_issued and controller.append_seen:
        allowed = [lapras_gift._screen(lapras_gift.NICKNAME, cursor=cursor) for cursor in (None, 8, 10)]
    else:
        return False
    return any(lapras_gift._subset(rows, target) for target in allowed)


def pre_attrition_context(pyboy, state, plan, step_id, text, grid):
    """僅原五raw不變的AskName未初始化過渡；其餘None保留原安全閘。

    呼叫端只能在party_attrition_state_unverified/party_read_not_verified使用。
    未綁owner不建立；完整六人回None；這個入口永不前進route。
    """
    request = _request(state, plan, step_id)
    if request is None:
        return None
    if 'review_reason' in request:
        return request, step_id
    controller = _CONTROLLERS.get(step_id)
    if controller is None or controller.baseline is None or step_id in _COMPLETED:
        return None
    p = state.get('progress')
    if (not isinstance(p, dict) or p.get('party_read_valid') is not False
            or p.get('initialization_candidate') is not False or p.get('party') != []
            or type(p.get('party_count')) is not int or p['party_count'] != 6
            or p.get('profile') != 'gen1-wrapper-ram-progress-v1-unvalidated'):
        return None
    observed = _observation(pyboy, state, text)
    if 'review_reason' in observed:
        return observed, step_id
    if grid is not None and not _closed_grid(grid, state):
        return None
    s, baseline = observed['signal'], controller.baseline
    if not controller._signal(s, observed['frame']):
        return None
    prefix = dict(mons=s['prefix_mons_raw'], ot=s['prefix_ot_raw'],
                  nicks=s['prefix_nicks_raw'], species=s['party_species'][:5])
    if (s['party_count'] != 6 or s['got_lapras'] or s['raw_flags'] != baseline['flags']
            or prefix != baseline['prefix'] or _sixth_fully_initialized(s)
            or lapras_gift._raw_name(s['new_ot_raw']) != 'KEVIN'
            or lapras_gift._inventory(p.get('inventory')) != baseline['bag']
            or type(p.get('money')) is not int or p['money'] != baseline['money']
            or p.get('player_name_raw') != baseline['name']
            or type(p.get('badges_raw')) is not int or p['badges_raw'] != baseline['badges']
            or getattr(controller, 'initial_health_verified', None) is not True
            or getattr(controller, 'initial_health_party', None) != baseline['party']
            or any(mon['hp'] <= 0 for mon in baseline['party'])
            or baseline['party'][0]['hp'] * 3 <= baseline['party'][0]['max_hp'] * 2
            or not _native_transition(controller, text)):
        return None
    result = _deliver(controller, observed, state, request, text, grid, step_id, prehook=True)
    return result, step_id
