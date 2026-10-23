"""火箭隊基地單段箭頭候選：只建議入口一步，遊戲自己滑行，其餘只等待。

純輸入／狀態機，不讀檔、ROM、RAM、時鐘或模擬器，不執行按鍵。
觀測時鐘、movement與逐格可見核對必須由呼叫端真實提供；目前未接runner。
"""
import math


SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
SOURCE_ROOT = f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/'
SOURCES = [SOURCE_ROOT + path for path in (
    'scripts/RocketHideoutB2F.asm', 'scripts/RocketHideoutB3F.asm',
    'engine/overworld/spinners.asm', 'constants/ram_constants.asm',
    'constants/map_constants.asm', 'constants/tileset_constants.asm', 'ram/wram.asm',
    'maps/RocketHideoutB2F.blk', 'maps/RocketHideoutB3F.blk', 'gfx/blocksets/facility.bst')]
FACILITY, STOP_TILE, WIDTH, HEIGHT = 22, 0x5E, 30, 28
MOVEMENT_PROFILE = 'gen1-arrow-movement-source-v1'
_DELTAS = {'up': (0, -1), 'down': (0, 1), 'left': (-1, 0), 'right': (1, 0)}
# map,正常站位,入口,唯一入口方向,stop,入口tile,RLE label編號,實際執行順序。
# 所有座標皆固定公開來源；RLE只驗證觀測範圍，絕不轉成外部按鍵／中途目標。
_HOPS = (
    (200, (18, 11), (17, 11), 'left', (2, 9), 0x20, 36, (('left', 5), ('up', 2), ('left', 10))),
    (200, (3, 11), (4, 11), 'right', (8, 11), 0x30, 2, (('right', 4),)),
    (200, (10, 14), (11, 14), 'right', (15, 18), 0x20, 18, (('down', 2), ('right', 4), ('down', 2))),
    (200, (14, 18), (13, 18), 'left', (11, 20), 0x20, 27, (('left', 2), ('down', 2))),
    (200, (14, 22), (13, 22), 'left', (9, 24), 0x20, 29, (('left', 4), ('down', 2))),
    (200, (10, 24), (10, 25), 'down', (14, 25), 0x30, 2, (('right', 4),)),
    (200, (4, 14), (5, 14), 'right', (9, 16), 0x30, 6, (('right', 4), ('down', 2))),
    (200, (10, 16), (11, 16), 'right', (15, 18), 0x30, 19, (('right', 4), ('down', 2))),
    (201, (13, 11), (12, 11), 'left', (10, 11), 0x20, 3, (('left', 2),)),
    (201, (10, 12), (10, 13), 'down', (14, 13), 0x30, 6, (('right', 4),)),
    (201, (10, 18), (11, 18), 'right', (15, 22), 0x30, 2, (('right', 4), ('down', 4))),
    (201, (18, 17), (18, 16), 'up', (18, 15), 0x21, 12, (('up', 1),)),
    (201, (16, 14), (16, 13), 'up', (16, 11), 0x21, 11, (('up', 2),)),
)


def source_hop(map_id, trigger):
    """只回來源白名單的副本，不接受外部自訂落點或RLE。"""
    if (type(map_id) is not int or not isinstance(trigger, (list, tuple)) or len(trigger) != 2
            or any(type(value) is not int for value in trigger)):
        raise ValueError('箭頭必須是固定來源map／入口座標')
    for mid, start, entry, action, stop, tile, label, rle in _HOPS:
        if (map_id, tuple(trigger)) == (mid, entry):
            return {'map_id': mid, 'from': start, 'trigger': entry, 'entry_action': action,
                    'expected_landing': stop, 'trigger_tile': tile, 'rle': rle,
                    'source_label': f'RocketHideout{mid - 198}ArrowMovement{label}',
                    'source_commit': SOURCE_COMMIT}
    raise ValueError('尚未支援或未經來源驗證的箭頭入口')


def _grid_error(grid, frame, position):
    if not isinstance(grid, dict) or grid.get('tileset_id') != FACILITY:
        return 'arrow_grid_tileset_not_verified'
    if (type(grid.get('observation_frame')) is not int or grid['observation_frame'] != frame
            or not isinstance(grid.get('verified_location'), list)
            or any(type(value) is not int for value in grid['verified_location'])
            or grid['verified_location'] != list(position)):
        return 'arrow_grid_observation_not_current'
    for key, maximum in (('tiles', 255), ('walkable', 1)):
        cells = grid.get(key)
        if (not isinstance(cells, (list, tuple)) or len(cells) != HEIGHT
                or any(not isinstance(row, (list, tuple)) or len(row) != WIDTH
                       or any(type(value) is not int or not 0 <= value <= maximum for value in row)
                       for row in cells)):
            return 'arrow_grid_shape_or_values_invalid'
    verified = grid.get('visible_verified_cells')
    if (not isinstance(verified, (list, tuple)) or not 12 <= len(verified) <= 90
            or any(not isinstance(cell, (list, tuple)) or len(cell) != 2
                   or type(cell[0]) is not int or type(cell[1]) is not int
                   or not 0 <= cell[0] < WIDTH or not 0 <= cell[1] < HEIGHT for cell in verified)
            or len({tuple(cell) for cell in verified}) != len(verified)
            or type(grid.get('screen_cells_verified')) is not int
            or grid['screen_cells_verified'] != len(verified)):
        return 'arrow_visible_cell_proof_missing'
    return None


class ArrowFloorController:
    """單一來源入口交易；完成後回wait，呼叫端才能另走下一段正常路線。

    movement必須含read_valid=True、profile、source_commit、spinning(bool)、
    simulated_remaining／joy_ignore／walk_counter(byte)。不猜任何RAM地址。
    grid必須是同frame、同location與畫面逐格比對的唯讀結果，附可見核對座標。
    battle／loss優先交既有控制器；若本候選仍收到戰鬥，鎖review等待重新規劃。
    """

    def __init__(self, map_id, trigger, *, max_calls=90, max_waits=60, max_seconds=60.0):
        for value in (max_calls, max_waits):
            if type(value) is not int or not 1 <= value <= 1000:
                raise ValueError('箭頭操作與等待上限必須為1..1000')
        if (type(max_seconds) not in (int, float) or not math.isfinite(max_seconds)
                or not 0 < max_seconds <= 60):
            raise ValueError('箭頭時間上限必須為0..60秒')
        self.hop = source_hop(map_id, trigger)
        self.max_calls, self.max_waits, self.max_seconds = max_calls, max_waits, max_seconds
        self.calls, self.waits, self.stable_samples = 0, 0, 0
        self.stage, self.error = 'ready', None
        self.started_at = self.last_time = self.last_frame = self.last_stable_frame = None
        self.stable_signature = None
        self._last_position_movement = None
        point = self.hop['trigger']
        self._allowed = {self.hop['from'], point}
        for direction, count in self.hop['rle']:
            dx, dy = _DELTAS[direction]
            for _ in range(count):
                point = point[0] + dx, point[1] + dy
                self._allowed.add(point)
        if point != self.hop['expected_landing']:
            raise ValueError('固定來源RLE與落點不一致')

    def _metadata(self):
        return {'arrow_floor_controller': 'source_single_hop_candidate', 'arrow_floor_stage': self.stage,
                'source_commit': SOURCE_COMMIT, 'sources': SOURCES,
                'arrow_map_id': self.hop['map_id'], 'arrow_trigger': list(self.hop['trigger']),
                'arrow_expected_landing': list(self.hop['expected_landing']),
                'suppress_navigation_stall': True, 'suppress_blocked_edge_learning': True}

    def _result(self, action, tactic, **extra):
        return {'phase': 'arrow_floor', 'objective': 'Wait.' if action == 'wait' else f'Move {action.upper()}.',
                'available_actions': ['wait'] if action == 'wait' else [action, 'wait'],
                'controller_menu_verified': True, 'arrow_floor_tactic': tactic,
                **self._metadata(), **extra}

    def _review(self, reason):
        self.error = reason
        return {**self._result('wait', 'operator_review_required'),
                'phase': 'campaign_review', 'review_reason': reason}

    def _wait(self, tactic):
        self.waits += 1
        if self.waits > self.max_waits:
            return self._review('arrow_wait_budget_exhausted')
        return self._result('wait', tactic, safe_wait_count=self.waits, safe_wait_limit=self.max_waits)

    def context(self, location, grid, movement, *, frame, now, overworld_ready, battle_active=False):
        """只回一個Laya子目標；now須呼叫端單調時鐘，不自行讀取時鐘／遊戲。"""
        if self.error:
            return self._review(self.error)
        self.calls += 1
        if (type(now) not in (int, float) or not math.isfinite(now) or now < 0
                or type(frame) is not int or frame < 0
                or self.last_time is not None and now < self.last_time
                or self.last_frame is not None and frame < self.last_frame):
            return self._review('arrow_clock_or_frame_invalid')
        if self.started_at is None:
            self.started_at = now
        if self.calls > self.max_calls or now - self.started_at > self.max_seconds:
            return self._review('arrow_operation_budget_exhausted')
        prior_frame = self.last_frame
        self.last_time, self.last_frame = now, frame
        if battle_active is not False or type(overworld_ready) is not bool:
            return self._review('arrow_requires_verified_nonbattle')
        if (not isinstance(location, dict) or type(location.get('map_id')) is not int
                or location['map_id'] != self.hop['map_id']
                or type(location.get('x')) is not int or type(location.get('y')) is not int
                or not 0 <= location['x'] < WIDTH or not 0 <= location['y'] < HEIGHT):
            return self._review('arrow_location_unverified_or_wrong_map')
        position = (location['x'], location['y'])
        if (not isinstance(movement, dict) or movement.get('read_valid') is not True
                or movement.get('profile') != MOVEMENT_PROFILE or movement.get('source_commit') != SOURCE_COMMIT
                or type(movement.get('observation_frame')) is not int or movement['observation_frame'] != frame
                or type(movement.get('spinning')) is not bool
                or any(type(movement.get(key)) is not int or not 0 <= movement[key] <= 255
                       for key in ('simulated_remaining', 'joy_ignore', 'walk_counter'))):
            return self._review('arrow_movement_read_not_verified')
        if movement['joy_ignore'] not in (0, 255):
            return self._review('arrow_input_ignore_mask_unknown')
        sample=(position,movement['spinning'],movement['simulated_remaining'],movement['joy_ignore'],movement['walk_counter'])
        if prior_frame==frame and self._last_position_movement is not None and self._last_position_movement!=sample:
            return self._review('arrow_same_frame_observation_conflict')
        self._last_position_movement=sample
        idle = not movement['spinning'] and all(movement[key] == 0 for key in
                                               ('simulated_remaining', 'joy_ignore', 'walk_counter'))
        if position not in self._allowed:
            return self._review('arrow_observed_outside_source_route')
        if grid is not None:
            error = _grid_error(grid, frame, (location['map_id'], *position))
            if error:
                return self._review(error)
        if self.stage == 'ready':
            if position != self.hop['from'] or not idle or not overworld_ready:
                return self._review('arrow_entry_stance_or_idle_not_verified')
            if grid is None:
                return self._review('arrow_entry_grid_required')
            verified = {tuple(cell) for cell in grid['visible_verified_cells']}
            if not {position, self.hop['trigger']} <= verified:
                return self._review('arrow_entry_cells_not_visibly_verified')
            x, y = position
            tx, ty = self.hop['trigger']
            if (grid['tiles'][y][x] != 0x01 or grid['walkable'][y][x] != 1
                    or grid['tiles'][ty][tx] != self.hop['trigger_tile'] or grid['walkable'][ty][tx] != 1):
                return self._review('arrow_entry_tiles_do_not_match_source')
            self.stage = 'entry_requested'
            return self._result(self.hop['entry_action'], 'enter_only_verified_arrow_once')
        # 一旦提出入口按鍵，絕不重送方向；沒移動也只有限等，避免滑行中盲送鍵。
        if not idle:
            self.stable_samples, self.stable_signature, self.last_stable_frame = 0, None, None
            return self._wait('wait_game_owned_forced_movement')
        if position != self.hop['expected_landing']:
            self.stable_samples, self.stable_signature, self.last_stable_frame = 0, None, None
            if position in (self.hop['from'], self.hop['trigger']):
                return self._wait('await_entry_or_script_start_without_resending')
            return self._review('arrow_stopped_before_expected_stop')
        if not overworld_ready or grid is None:
            self.stable_samples, self.stable_signature, self.last_stable_frame = 0, None, None
            return self._wait('await_stable_landing_screen')
        x, y = position
        if position not in {tuple(cell) for cell in grid['visible_verified_cells']}:
            return self._review('arrow_stop_cell_not_visibly_verified')
        if grid['tiles'][y][x] != STOP_TILE or grid['walkable'][y][x] != 1:
            return self._review('arrow_landing_is_not_source_stop_tile')
        signature = tuple((grid['tiles'][yy][xx], grid['walkable'][yy][xx])
                          for yy in range(max(0, y - 1), min(HEIGHT, y + 2))
                          for xx in range(max(0, x - 1), min(WIDTH, x + 2)))
        if signature != self.stable_signature:
            self.stable_signature, self.stable_samples, self.last_stable_frame = signature, 1, frame
        elif self.last_stable_frame != frame:
            self.stable_samples += 1
            self.last_stable_frame = frame
        if self.stable_samples < 2:
            return self._wait('verify_stop_on_two_distinct_observation_frames')
        self.stage = 'complete'
        return self._result('wait', 'source_stop_verified_complete', arrow_floor_complete=True,
                            arrow_observed_landing=list(position), stable_observations=self.stable_samples)
