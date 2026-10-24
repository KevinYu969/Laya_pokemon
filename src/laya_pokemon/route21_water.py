"""真新鎮已上水後，沿固定21號水道到紅蓮上岸的純導航候選。

不執行按鍵、不讀寫RAM，不把water加入一般陸地碰撞表。caller須先做
loss／attrition，再以同一物件處理水步與第一個battle觀測，不能丟掉真previous。
state['text']須為同次read_visible_text原封包；原位置與signal須同幀。
每個真新格才重算60秒／30WAIT；整路900秒／1500calls，reload不重建。
只有連續新幀、有效active wild觀測間的時間排除；同幀工程pause不自清。
"""
from copy import deepcopy
import math

from .mart_purchase import _inventory, _party
from .pallet_surf import PROFILE as SURF_PROFILE, _idle, _rows

SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
CONTRACT_SHA256 = 'bc2ea06ef3b4af7848e692826e6c45d13543cb14905e6f09eebd40b02970eda9'
INTENT = {'kind': 'route21_water', 'start': [0, 4, 14], 'goal': [8, 4, 10],
          'path_id': 'pallet-route21-cinnabar-source-v1'}
# (map, x, y, mode, lower-left tile)，只取固定source full_path的水段＋上岸。
PATH = (tuple((0, 4, y, 2, 0x32) for y in range(14, 18))
        + tuple((32, 4, y, 2, 0x32 if y < 14 else 0x14) for y in range(15))
        + tuple((32, 3, y, 2, 0x14) for y in range(14, 90))
        + tuple((8, 3, y, 2, 0x14) for y in range(11))
        + ((8, 4, 10, 0, 0x39),))
MAX_STEP_SECONDS, MAX_STEP_WAITS = 60, 30
MAX_SECONDS, MAX_CALLS = 900, 1500
SOURCES = tuple(f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/{p}' for p in (
    'data/maps/headers/PalletTown.asm', 'data/maps/headers/Route21.asm',
    'data/maps/headers/CinnabarIsland.asm', 'home/overworld.asm#L1164',
    'data/tilesets/collision_tile_ids.asm', 'data/tilesets/pair_collision_tile_ids.asm'))


def _int(v, low=0, high=0x7fffffffffffffff):
    return type(v) is int and low <= v <= high


def _intent(value):
    return (type(value) is dict and value == INTENT
            and all(type(value[k]) is list and all(type(n) is int for n in value[k])
                    for k in ('start', 'goal')))


def _position(value):
    if (not isinstance(value, dict) or any(not _int(value.get(k), 0, 255)
            for k in ('map_id', 'x', 'y'))): return None
    return value['map_id'], value['x'], value['y']


def _direction(a, b):
    if a[0] == b[0]:
        return {(0, -1): 'up', (0, 1): 'down', (-1, 0): 'left', (1, 0): 'right'}.get(
            (b[1] - a[1], b[2] - a[2]))
    return 'down' if (a[:3], b[:3]) in (((0, 4, 17), (32, 4, 0)),
                                      ((32, 3, 89), (8, 3, 0))) else None


def _fingerprint(progress):
    party = _party(progress)
    bag = _inventory(progress.get('inventory')) if isinstance(progress, dict) else None
    if party is None or len(party) != 6 or bag is None or not _int(progress.get('money'), 0, 999999):
        return None
    return deepcopy((party, bag, progress['money']))


def _blank(text):
    return (_rows(text) == (' ' * 20,) * 18 and text['window_visible'] is False)


def _grid(grid, node, frame, next_node=None):
    """驗原grid，不改water walkable=0；同圖下一格須在真visible proof中。"""
    mid, x, y, _, tile = node
    height = {0: 18, 32: 90, 8: 18}[mid]
    if (not isinstance(grid, dict) or type(grid.get('tileset_id')) is not int or grid['tileset_id'] != 0
            or type(grid.get('observation_frame')) is not int or grid['observation_frame'] != frame
            or type(grid.get('verified_location')) is not list
            or any(type(v) is not int for v in grid['verified_location'])
            or grid['verified_location'] != [mid, x, y]): return False
    for key, high in (('tiles', 255), ('walkable', 1)):
        matrix = grid.get(key)
        if (type(matrix) is not list or len(matrix) != height
                or any(type(row) is not list or len(row) != 20
                       or any(not _int(v, 0, high) for v in row) for row in matrix)): return False
    cells = grid.get('visible_verified_cells')
    if (type(cells) is not list or not _int(grid.get('screen_cells_verified'), 12, 90)
            or len(cells) != grid['screen_cells_verified']
            or any(type(c) is not list or len(c) != 2 or not _int(c[0], 0, 19)
                   or not _int(c[1], 0, height - 1) for c in cells)): return False
    visible = {tuple(c) for c in cells}
    if len(visible) != len(cells): return False
    required = [node] + ([next_node] if next_node is not None and next_node[0] == mid else [])
    return all((n[1], n[2]) in visible and grid['tiles'][n[2]][n[1]] == n[4]
               and grid['walkable'][n[2]][n[1]] == (1 if n[3] == 0 else 0) for n in required)


class Route21WaterController:
    """固定單向海路；None僅交給同位置／mode的既有野戰控制。"""
    def __init__(self, intent=INTENT):
        if not _intent(intent): raise ValueError('只允許固定Pallet已上水至Cinnabar上岸路徑')
        self.intent, self.contract = deepcopy(intent), deepcopy(intent)
        self.index = 0; self.pending = None; self.error = None; self.stage = 'initial'
        self.started = self.step_started = self.last_now = None
        self.excluded = self.step_excluded = 0.; self.last_frame = -1; self.last_packet = None
        self.waits = self.calls = 0; self.in_battle = self.last_active = False
        self.fingerprint = None; self.goal_frames = []

    def _hint(self, action, tactic, complete=False):
        return {'phase': 'overworld', 'objective': 'Wait.' if action == 'wait' else f'Move {action.upper()}.',
                'available_actions': ['wait'] if action == 'wait' else [action, 'wait'],
                'controller_menu_verified': action != 'wait', 'route21_water_complete': complete,
                'route21_water_stage': self.stage, 'route21_water_index': self.index,
                'route21_water_tactic': tactic, 'source_commit': SOURCE_COMMIT,
                'source_contract_sha256': CONTRACT_SHA256, 'sources': SOURCES}

    def _fail(self, reason):
        self.error = self.error or 'route21_water_' + reason
        return {**self._hint('wait', 'review'), 'phase': 'campaign_review', 'review_reason': self.error}

    def _wait(self, reason):
        self.waits += 1
        return self._fail('step_wait_budget_exhausted') if self.waits > MAX_STEP_WAITS else self._hint('wait', reason)

    def _advance(self, now):
        self.index += 1; self.pending = None; self.step_started = now
        self.step_excluded = 0.; self.waits = 0; self.goal_frames.clear()

    def _offer(self, frame):
        action = _direction(PATH[self.index], PATH[self.index + 1])
        self.pending = {'frame': frame, 'action': action, 'from': self.index,
                        'to': self.index + 1, 'executed': False}
        self.stage = 'walking'
        return self._hint(action, 'verified_next_source_cell')

    def context(self, state, *, grid, signal, movement, previous, now):
        """只提出一個方向；caller健康閘優先，戰鬥資料不做永久水路基線。"""
        if self.error: return self._fail('sticky')
        if not _intent(self.intent) or self.intent != self.contract: return self._fail('intent_changed')
        frame = state.get('frame') if isinstance(state, dict) else None
        if (not _int(frame) or type(now) not in (int, float) or not math.isfinite(now) or now < 0
                or frame < self.last_frame or self.last_now is not None and now < self.last_now):
            return self._fail('clock_or_frame_unverified')
        self.calls += 1
        if self.calls > MAX_CALLS: return self._fail('whole_call_budget_exhausted')
        pos = _position(state.get('location'))
        battle = state.get('battle_state')
        if (pos is None or not isinstance(battle, dict) or type(battle.get('raw')) is not int
                or type(battle.get('observation_frame')) is not int or battle['observation_frame'] != frame):
            return self._fail('location_or_battle_unverified')
        active = battle['raw'] == 1 and battle.get('active') is True and battle.get('kind') == 'wild'
        none = battle['raw'] == 0 and battle.get('active') is False and battle.get('kind') == 'none'
        if not active and not none: return self._fail('only_normal_wild_or_none_supported')
        if (not isinstance(signal, dict) or signal.get('profile') != SURF_PROFILE
                or signal.get('source_commit') != SOURCE_COMMIT or signal.get('read_valid') is not True
                or signal.get('read_error') is not None or type(signal.get('observation_frame')) is not int
                or signal['observation_frame'] != frame or _position(signal.get('location')) != pos
                or type(signal.get('mode')) is not int or signal['mode'] not in (0, 2)
                or type(signal.get('battle_raw')) is not int or signal['battle_raw'] != battle['raw']):
            return self._fail('surf_signal_unverified')
        mode = signal['mode']
        for packet in (state.get('location'), state.get('progress'), state.get('text'), grid, movement):
            if (isinstance(packet, dict) and 'observation_frame' in packet
                    and (not _int(packet['observation_frame']) or packet['observation_frame'] != frame)):
                return self._fail('packet_frame_disagrees')
        if (type(previous) not in (list, tuple) or any(type(a) is not str
                or a not in ('up', 'down', 'left', 'right', 'a', 'b', 'start', 'wait') for a in previous)):
            return self._fail('actual_previous_unverified')
        packet = deepcopy((state, grid, signal, movement, previous))
        if frame == self.last_frame and packet != self.last_packet: return self._fail('same_frame_conflict')
        if self.started is not None:
            # 只凍結前後都有有效active wild且frame確實前進的間隔；原錯誤不清除。
            if frame > self.last_frame and self.last_active and active:
                delta = now - self.last_now; self.excluded += delta; self.step_excluded += delta
            if now - self.started - self.excluded > MAX_SECONDS: return self._fail('whole_time_budget_exhausted')
            if now - self.step_started - self.step_excluded > MAX_STEP_SECONDS: return self._fail('step_time_budget_exhausted')
        same = frame == self.last_frame
        self.last_now, self.last_active = now, active
        if same: return None if self.in_battle and active else self._wait('same_frame_no_action')
        self.last_frame, self.last_packet = frame, packet
        current = PATH[self.index]
        if self.stage == 'initial':
            if pos != PATH[0][:3] or mode != 2 or active: return self._fail('initial_water_stance_unverified')
            fp = _fingerprint(state.get('progress'))
            if (fp is None or any(m['hp'] <= 0 or m['status'] != 0 for m in fp[0])
                    or fp[0][0]['hp'] * 3 <= fp[0][0]['max_hp'] * 2
                    or not _blank(state.get('text')) or _idle(movement, frame) is not True
                    or not _grid(grid, current, frame, PATH[1])): return self._fail('initial_health_or_world_unverified')
            self.fingerprint = fp; self.started = self.step_started = now
            return self._offer(frame)
        if self.pending:
            offered = self.pending; target = PATH[offered['to']]
            if not offered['executed'] and previous and previous[-1] == offered['action']:
                offered['executed'] = True
            if pos not in (current[:3], target[:3]): return self._fail('unexpected_step_position')
            if active:
                # 首個battle必須消化原水步；缺grid不能把原候選當成已送方向。
                if not offered['executed'] or pos != target[:3] or mode != target[3] or mode != 2:
                    return self._fail('battle_without_verified_water_step_receipt')
                self._advance(now); self.in_battle = True; self.stage = 'battle'
                self.fingerprint = None
                return None
        elif pos != current[:3]: return self._fail('position_changed_without_water_step')
        if active:
            if not self.in_battle or pos != current[:3] or mode != 2:
                return self._fail('battle_location_or_mode_changed')
            return None
        if self.in_battle:
            if pos != current[:3] or mode != current[3]: return self._fail('battle_return_location_or_mode_changed')
            if (not _blank(state.get('text')) or _idle(movement, frame) is not True
                    or not _grid(grid, current, frame, PATH[self.index + 1])):
                return self._wait('await_none_blank_idle_after_battle')
            fp = _fingerprint(state.get('progress'))
            if fp is None: return self._fail('battle_return_progress_unverified')
            self.fingerprint = fp; self.in_battle = False; self.stage = 'walking'
        fp = _fingerprint(state.get('progress'))
        if fp is None or fp != self.fingerprint: return self._fail('water_step_party_bag_or_money_changed')
        if self.pending:
            target = PATH[self.pending['to']]
            # 上岸先設mode0，再完成腳步；只等這一條已真送RIGHT的原水格。
            if (self.pending['executed'] and target == PATH[-1] and pos == current[:3] and mode == 0):
                return self._wait('native_mode0_before_actual_landfall')
            expected_mode = target[3] if pos == target[:3] else current[3]
            if mode != expected_mode: return self._fail('step_mode_disagrees')
            if not self.pending['executed'] and pos != current[:3]: return self._fail('movement_without_actual_direction')
            idle = _idle(movement, frame)
            if not _blank(state.get('text')) or idle is not True:
                return self._wait('await_native_water_step') if self.pending['executed'] else self._fail('unarmed_world_unverified')
            node = target if pos == target[:3] else current
            if not _grid(grid, node, frame, None if node == target else target):
                return self._wait('await_verified_grid_after_step') if self.pending['executed'] else self._fail('unarmed_grid_unverified')
            if not self.pending['executed']: return self._offer(frame)
            if pos == current[:3]: return self._wait('await_actual_next_cell')
            self._advance(now); current = PATH[self.index]
        if mode != current[3] or pos != current[:3]: return self._fail('accepted_position_or_mode_disagrees')
        if self.index == len(PATH) - 1:
            if (not _blank(state.get('text')) or _idle(movement, frame) is not True
                    or not _grid(grid, current, frame)):
                self.goal_frames.clear(); return self._wait('await_closed_idle_landfall')
            self.goal_frames.append(frame)
            if len(self.goal_frames) < 2: return self._wait('verify_second_fresh_landfall')
            self.stage = 'complete'; return self._hint('wait', 'verified_cinnabar_landfall', True)
        if not _grid(grid, current, frame, PATH[self.index + 1]): return self._fail('next_source_cell_not_visible_or_verified')
        return self._offer(frame)
