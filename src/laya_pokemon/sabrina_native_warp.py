"""娜姿道館固定正向／返程原生傳送的純觀測候選；不按鍵、不讀寫遊戲。

previous必須是caller實際已送出的動作序列；新frame及匹配方向才是動作回執。
只有到指定目的墊的兩個新鮮靜止觀測、再正常離墊，才完成這一個step。
"""
from copy import deepcopy
import math
import re
import time

from .mart_purchase import _inventory, _party
from .observation import PROFILE as TEXT_PROFILE
from .rocket_movement import MOVEMENT_PROFILE
from .team_strategy import effective_power

SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
SOURCE = f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/data/maps/objects/SaffronGym.asm'
PAIRS = {(11, 15): ((19, 17), (18, 17)), (15, 15): ((19, 3), (18, 3)),
         (15, 5): ((1, 3), (1, 4)), (1, 5): ((11, 11), (10, 11))}
# 固定公開來源的互逆墊；只供明示 recovery_route=True 的正常返程。
RECOVERY_PAIRS = {(11, 11): ((1, 5), (1, 4)), (1, 3): ((15, 5), (16, 5)),
                  (19, 3): ((15, 15), (15, 16)), (19, 17): ((11, 15), (11, 16))}
MAX_WAITS, MAX_SECONDS = 30, 60
_SESSIONS = globals().get('_SESSIONS', {})
_OWNER = globals().get('_OWNER')


def _int(value, lo=0, hi=0x7FFFFFFFFFFFFFFF):
    return type(value) is int and lo <= value <= hi


def _xy(value):
    return (type(value) is list and len(value) == 2
            and _int(value[0], 0, 19) and _int(value[1], 0, 17))


def _intent(step):
    if (not isinstance(step, dict) or not isinstance(step.get('id'), str)
            or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', step['id']) is None
            or step.get('kind') != 'move' or step.get('mechanic') != 'sabrina_native_warp'
            or type(step.get('map_id')) is not int or step['map_id'] != 178
            or any(not _xy(step.get(k)) for k in ('target', 'landing', 'offpad'))
            or 'next_map' in step or 'terminal' in step):
        return False
    source = tuple(step['target'])
    if source in PAIRS:
        return ('recovery_route' not in step
                and PAIRS[source] == (tuple(step['landing']), tuple(step['offpad'])))
    return (step.get('recovery_route') is True
            and RECOVERY_PAIRS.get(source) == (tuple(step['landing']), tuple(step['offpad'])))


def _baseline(progress, *, recovery=False):
    party = _party(progress)
    inventory = _inventory(progress.get('inventory')) if isinstance(progress, dict) else None
    money = progress.get('money') if isinstance(progress, dict) else None
    if (party is None or len(party) != 6
            or any(m['status'] not in (*range(8), 8, 16, 32, 64) for m in party)
            or inventory is None or not _int(money, 0, 999999)):
        return None
    if recovery:
        # raw PP 高二位是 PP Up 次數，不能當剩餘 PP；不把候選當作補血／復活。
        if not any(m['status'] == 0 and m['hp'] * 3 > m['max_hp'] * 2
                   and any((pp & 63) >= 3 and effective_power(move, m['species']) > 0
                           for move, pp in zip(m['moves'], m['pp'])) for m in party):
            return None
    elif any(m['hp'] <= 0 for m in party):
        return None
    return deepcopy((party, inventory, money))


def _closed(text):
    cells = text.get('cells') if isinstance(text, dict) else None
    return (isinstance(text, dict) and text.get('profile') == TEXT_PROFILE
            and text.get('read_valid') is True and text.get('alignment_verified') is True
            and text.get('read_error') is None and text.get('window_visible') is False
            and type(cells) is list and len(cells) == 18
            and all(type(row) is list and len(row) == 20
                    and all(type(c) is str and c == ' ' for c in row) for row in cells)
            and text.get('lines') == [] and text.get('line_rows', []) == [])


def _idle(movement):
    if (not isinstance(movement, dict) or movement.get('profile') != MOVEMENT_PROFILE
            or movement.get('source_commit') != SOURCE_COMMIT or movement.get('read_valid') is not True
            or movement.get('read_error') is not None
            or any(not _int(movement.get(k), 0, 255) for k in
                   ('simulated_remaining', 'joy_ignore', 'walk_counter', 'movement_flags'))
            or movement['joy_ignore'] not in (0, 255) or movement['movement_flags'] & 0x38
            or type(movement.get('spinning')) is not bool
            or movement['spinning'] != bool(movement['movement_flags'] & 0x80)):
        return False
    return (movement['simulated_remaining'] == movement['joy_ignore'] == movement['walk_counter'] == 0
            and movement['spinning'] is False)


def _grid(grid, frame, pos, required):
    if (not isinstance(grid, dict) or type(grid.get('tileset_id')) is not int or grid['tileset_id'] != 22
            or grid.get('observation_frame') != frame or type(grid.get('observation_frame')) is not int
            or type(grid.get('verified_location')) is not list or len(grid['verified_location']) != 3
            or any(type(v) is not int for v in grid['verified_location'])
            or grid['verified_location'] != [178, *pos]):
        return False
    tiles, walk = grid.get('tiles'), grid.get('walkable')
    if any(type(a) is not list or len(a) != 18
           or any(type(row) is not list or len(row) != 20
                  or any(not _int(x, 0, high) for x in row) for row in a)
           for a, high in ((tiles, 255), (walk, 1))):
        return False
    cells = grid.get('visible_verified_cells')
    if (type(cells) is not list or not _int(grid.get('screen_cells_verified'), 12, 90)
            or len(cells) != grid['screen_cells_verified'] or any(not _xy(c) for c in cells)):
        return False
    visible = {tuple(c) for c in cells}
    return len(visible) == len(cells) and all(tuple(c) in visible for c in (pos, *required))


def _direction(origin, target):
    return {(0, -1): 'up', (0, 1): 'down', (-1, 0): 'left', (1, 0): 'right'}.get(
        (target[0] - origin[0], target[1] - origin[1]))


def context(state, step, text, grid, movement, previous, now=None):
    """回None交導航，或唯一direction+wait／有界WAIT／review；不自行執行。

    state/progress/location/battle與getter封包須來自同一次observe。完成標記
    native_warp_complete只代表本傳送與離墊，不代表抵達娜姿或獲勝。
    """
    global _OWNER
    sid = step.get('id') if isinstance(step, dict) else None
    record = _SESSIONS.get(_OWNER) if _OWNER is not None else _SESSIONS.get(sid) if isinstance(sid, str) else None

    def review(reason):
        if record is not None:
            record['error'] = record.get('error') or reason
            reason = record['error']
        return {'phase': 'campaign_review', 'objective': 'Wait.', 'available_actions': ['wait'],
                'review_reason': 'sabrina_native_warp_' + reason, 'route_step': sid,
                'source_commit': SOURCE_COMMIT}

    def hint(action, tactic, complete=False):
        extra = {'route_step': sid, 'goal': sid, 'sabrina_native_warp_stage': record['stage'],
                 'native_warp_complete': complete, 'source_commit': SOURCE_COMMIT, 'source': SOURCE,
                 'native_warp_tactic': tactic, 'safe_wait_count': record['waits']}
        if action == 'wait':
            result = {'phase': 'overworld', 'objective': 'Wait.', 'available_actions': ['wait'], **extra}
        else:
            result = {'phase': 'overworld', 'objective': f'Move {action.upper()}.',
                      'available_actions': [action, 'wait'], 'controller_menu_verified': True,
                      'phase_source': 'fixed Sabrina native warp; verified one-step floor/pad observation', **extra}
        record['result'] = deepcopy(result)
        return result

    def wait(tactic):
        record['waits'] += 1
        if record['waits'] > MAX_WAITS:
            return review('wait_budget_exhausted')
        return hint('wait', tactic)

    def offer(stage, origin, target):
        direction = _direction(origin, target)
        record['stage'] = stage
        record['offer'] = {'frame': frame, 'origin': pos, 'direction': direction}
        return hint(direction, 'step_onto_source' if stage == 'entry' else 'step_off_landing')

    if record is not None and record.get('error'):
        return review(record['error'])
    if not _intent(step):
        return review('intent_unverified')
    if record is not None and (record['step'] != step or _OWNER not in (None, sid)):
        return review('owner_or_intent_changed')
    if not isinstance(state, dict) or not _int(state.get('frame')):
        return review('state_frame_unverified')
    frame, loc = state['frame'], state.get('location')
    if (not isinstance(loc, dict) or type(loc.get('map_id')) is not int or loc['map_id'] != 178
            or not _int(loc.get('x'), 0, 19) or not _int(loc.get('y'), 0, 17)):
        return review('location_unverified')
    pos = (loc['x'], loc['y'])
    source, landing, offpad = (tuple(step[k]) for k in ('target', 'landing', 'offpad'))
    if record is None and abs(pos[0] - source[0]) + abs(pos[1] - source[1]) > 1:
        return None
    now = time.monotonic() if now is None else now
    if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
        return review('clock_unverified')
    if record is not None and (frame < record['last_frame'] or now < record['last_now']):
        return review('frame_or_clock_regressed')
    for packet in (loc, state.get('progress'), text, grid, movement):
        if (isinstance(packet, dict) and 'observation_frame' in packet
                and (not _int(packet['observation_frame']) or packet['observation_frame'] != frame)):
            return review('packet_frame_disagrees')
    battle = state.get('battle_state')
    if (not isinstance(battle, dict) or battle.get('active') is not False or battle.get('kind') != 'none'
            or type(battle.get('raw')) is not int or battle['raw'] != 0
            or type(battle.get('observation_frame')) is not int or battle['observation_frame'] != frame):
        return review('battle_not_verified_none')
    baseline = _baseline(state.get('progress'), recovery=step.get('recovery_route') is True)
    if baseline is None:
        return review('party_inventory_money_unverified')
    if (not isinstance(previous, (list, tuple))
            or any(type(a) is not str or a not in ('up', 'down', 'left', 'right', 'a', 'b', 'start', 'select', 'wait')
                   for a in previous)):
        return review('actual_action_history_unverified')
    if record is None:
        if pos == source:
            return review('source_without_action_receipt')
        record = {'step': deepcopy(step), 'baseline': baseline, 'stage': 'initial', 'started': now,
                  'last_now': now, 'last_frame': -1, 'packet': None, 'waits': 0,
                  'landing_frames': [], 'error': None, 'offer': None, 'result': None}
        _SESSIONS[sid] = record; _OWNER = sid
    if baseline != record['baseline']:
        return review('baseline_changed')
    packet = deepcopy((state, text, grid, movement, previous))
    if frame == record['last_frame']:
        if packet != record['packet']:
            return review('same_frame_packet_conflict')
        if now - record['started'] > MAX_SECONDS:
            return review('time_budget_exhausted')
        record['last_now'] = now
        return deepcopy(record['result'])
    record['last_frame'], record['last_now'], record['packet'] = frame, now, packet
    if now - record['started'] > MAX_SECONDS:
        return review('time_budget_exhausted')
    stage = record['stage']
    if stage in ('entry', 'offpad') and frame > record['offer']['frame']:
        offered = record['offer']
        if previous and previous[-1] == offered['direction']:
            record['stage'] = stage = 'transition' if stage == 'entry' else 'offpad_transition'
            record['actual_action_frame'] = frame
        elif pos != offered['origin']:
            return review('movement_without_matching_action_receipt')
    allowed = ({record['offer']['origin'], source, landing} if stage == 'transition'
               else {landing, offpad} if stage == 'offpad_transition' else None)
    if allowed is not None and pos not in allowed:
        return review('unexpected_transition_position')
    required = (source,) if stage in ('initial', 'entry') else (offpad,) if pos == landing else ()
    ready = (_closed(text) and _idle(movement)
             and isinstance(movement, dict) and type(movement.get('observation_frame')) is int
             and movement['observation_frame'] == frame and _grid(grid, frame, pos, required))
    if not ready:
        record['landing_frames'] = []
        return wait('await_native_transition') if stage in ('transition', 'offpad_transition') else review('closed_idle_world_unverified')
    tile, walkable = grid['tiles'][pos[1]][pos[0]], grid['walkable'][pos[1]][pos[0]]
    expected_tile = 0x20 if pos in (source, landing) else 0x01
    if tile != expected_tile or walkable != 1:
        return review('actual_tile_or_collision_unverified')
    if stage == 'complete':
        return hint('wait', 'already_verified_offpad', complete=True) if pos == offpad else review('completed_step_reused')
    if stage in ('initial', 'entry'):
        if pos != source and (grid['tiles'][source[1]][source[0]] != 0x20
                              or grid['walkable'][source[1]][source[0]] != 1):
            return review('source_pad_unverified')
        return offer('entry', pos, source)
    if stage == 'transition':
        if pos != landing:
            record['landing_frames'] = []
            return wait('await_exact_landing')
        record['landing_frames'].append(frame)
        if len(record['landing_frames']) < 2:
            return wait('verify_second_fresh_landing')
        if grid['tiles'][offpad[1]][offpad[0]] != 0x01 or grid['walkable'][offpad[1]][offpad[0]] != 1:
            return review('offpad_floor_unverified')
        return offer('offpad', landing, offpad)
    if stage == 'offpad':
        if pos != landing:
            return review('offpad_without_action_receipt')
        return offer('offpad', landing, offpad)
    if stage == 'offpad_transition':
        if pos != offpad:
            return wait('await_actual_offpad')
        record['stage'] = 'complete'
        _OWNER = None
        return hint('wait', 'verified_actual_offpad', complete=True)
    return review('stage_unverified')
