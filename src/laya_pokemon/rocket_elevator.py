"""火箭基地 B4F／明確 B1F 返程：純狀態機，只提出 Laya 子目標，不執行按鍵。

唯一 I/O helper 是 read_elevator_animation 的三個唯讀 getter；呼叫端先
核對紅版版本，且在同一模擬器執行緒觀測。read_valid 不代表 ROM 身分。
此候選沒有接入 runner，也不改 warp、樓層、ROM、RAM 或存檔。
"""
import math
import re


SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
SOURCE_ROOT = f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/'
SOURCE_SHA256 = {
    'scripts/RocketHideoutElevator.asm': '2c8bb7f33df5faf6693524a36b7616b1dbd1c705605a07cd0f65bf962b219412',
    'engine/events/elevator.asm': '7665819f6a4f7667d4cf268a45e28a2142d83b70ff14ddbdb52fe99e8b04af6f',
    'home/list_menu.asm': '43f046e47dfa086a753dc9843d00e8fa69c07da226baa3b4cd7ed80476f187ac',
    'home/window.asm': 'f5429ef5610ad9cd3e8d03a38f577eb7acf87f56883120468580973d4e12faed',
    'data/text/text_2.asm': 'ba97e54e9feafb22816b449841181b64234537bac9ccdef6aa3d79f4153e23b9',
    'engine/overworld/elevator.asm': '349abfc08a678c266c34d69b3fe3c3eea2610cd8904a285c458461104c942a51',
    'ram/wram.asm': '00683cd430a9ef30794d2aeaee51f3a5440e4bb14dca13e9f9cb5fa88f130e34',
    'ram/hram.asm': '33b28e183c30dc27d3caa8255dec62110c46f8df35b0599ab11016a4037ca91b',
    'layout.link': '70c20fcaa2fb04b007589c8fc512fdf3e9141d90b05bab955f39582f12ac9bf9',
    'constants/hardware.inc': '0fdc838feed0911844610ba229912e08f3ddec4a93b1a0a7ae320bd80bc1f4f9',
    'constants/audio_constants.asm': 'bc106d2b0ac6c014aeaf3af059243db945a877a6db99a06900d95062852566db',
    'engine/gfx/oam_dma.asm': 'e98d6c7d1d9c969876760f62d1601254614f29273264cf15aa9fa9946d87d65a',
    'maps/RocketHideoutElevator.blk': '9788b9d5d4c4f30d04402a517d77aa76a1967c01c82eb716802181558cdcbd02',
    'gfx/blocksets/lobby.bst': '9b87dd981f486f7a2685e6c90ad87e5c920affea9d03daefdeef0c7298a56849',
    'data/maps/objects/RocketHideoutB4F.asm': '34686b605baadcce32230e920e4054656b41d129c4fe3ac2836cdb4b413a96b3',
    'maps/RocketHideoutB4F.blk': '3bccce60d718cc2a688bb96c6571b7a577ef9ba3f1c5690b2883143873b2a73d',
    'data/maps/objects/RocketHideoutB1F.asm': 'c64e6cebf7a00f896713c4e344058bf15f661f5a09db392545be87ef9e3dc67a',
    'data/maps/headers/RocketHideoutB1F.asm': '2c11acecdd30f6dbcb2acbfb0d44e1458a2093553345f403551dd3bf96279ec4',
    'maps/RocketHideoutB1F.blk': '1262073853fc01aa16c71fdc9338b3eb3023cf4556c491f1e4bf5122687cd0d9',
    'constants/map_constants.asm': '4129ef4e6908267e554c0308254f2269f1fb8f75b5c529faad6fd14c92119271',
    'gfx/blocksets/facility.bst': 'fe0f7cfa2a00ca75fff6bb38f83c229eb9c6d079ef2d45252955290a72baaa08',
}
SOURCES = [SOURCE_ROOT + path for path in SOURCE_SHA256]
ANIMATION_PROFILE = 'gen1-elevator-animation-source-v1'
MOVEMENT_PROFILE = 'gen1-arrow-movement-source-v1'
# 固定源 layout.link 首段 Audio RAM=C000；6 bytes + 2*8 + 2*8 + CHAN5(4)。
CHANNEL5_SOUND_ID_ADDRESS = 0xC02A
# layout.link先配置10-byte OAM DMA於FF80，HRAM段從FF8A開始；
# 含巢狀UNION最大分支後hSCX=FFAE、hSCY=FFAF；非硬體rSCY。
SHADOW_SCY_ADDRESS, HARDWARE_SCY_ADDRESS = 0xFFAF, 0xFF42
MAP_ID, DESTINATION_MAP, LIFT_KEY = 203, 202, 74
PANEL_STANCE, PANEL_FACE, EXIT = (1, 2), 'up', (2, 1)
INTENT = {'kind': 'rocket_elevator', 'target_floor': 'B4F'}
B1F_INTENT = {'kind': 'rocket_elevator', 'target_floor': 'B1F'}
# 只開放兩筆固定來源契約，並非泛用選任意樓層。保留舊B4F常數相容性。
_DESTINATIONS = {
    'B4F': (202, 2, ((25, 15), (25, 14))),
    'B1F': (199, 0, ((25, 19), (25, 18))),
}
MIN_ANIMATION_FRAMES = 200  # 必要下限，絕不是單獨的完成判斷。
_FLOORS = (('B1F', 4), ('B2F', 6), ('B4F', 8), ('CANCEL', 10))
_QUESTION = ((1, 14, 'WHICH FLOOR DO'), (1, 16, 'YOU WANT?'))
_ELEVATOR_TILES = (
    (93, 93, 93, 93, 93, 93), (75, 33, 56, 56, 33, 75),
    (75, 69, 20, 20, 69, 75), (75, 69, 69, 69, 69, 75),
    (75, 69, 69, 69, 69, 75), (75, 69, 69, 69, 69, 75),
    (75, 69, 69, 69, 69, 75), (93, 93, 93, 93, 93, 93),
)
_LOBBY_COLLISION = {0x14, 0x17, 0x1A, 0x1C, 0x20, 0x38, 0x45}


def _byte(value):
    return type(value) is int and 0 <= value <= 255


def read_elevator_animation(pyboy, *, observation_frame):
    """僅三個固定 byte getter；前後實際 frame 必須與呼叫端相等，否則未知。

    呼叫端不可同時從其他執行緒 tick。沒有 setitem、tick、按鍵或ROM讀取。
    """
    result = {'read_valid': False, 'profile': ANIMATION_PROFILE,
              'source_commit': SOURCE_COMMIT, 'observation_frame': observation_frame,
              'shadow_scroll_y': None, 'hardware_scroll_y': None, 'channel5_sound_id': None}
    if type(observation_frame) is not int or observation_frame < 0:
        return {**result, 'read_error': 'elevator_animation_frame_invalid'}
    try:
        before = pyboy.frame_count
        if type(before) is not int or before != observation_frame:
            return {**result, 'read_error': 'elevator_animation_frame_not_current'}
        memory = pyboy.memory
        shadow = memory[SHADOW_SCY_ADDRESS]
        hardware = memory[HARDWARE_SCY_ADDRESS]
        sound = memory[CHANNEL5_SOUND_ID_ADDRESS]
        after = pyboy.frame_count
    except Exception:
        return {**result, 'read_error': 'elevator_animation_getter_failed'}
    if type(after) is not int or after != before:
        return {**result, 'read_error': 'elevator_animation_frame_changed_during_read'}
    if not all(_byte(value) for value in (shadow, hardware, sound)):
        return {**result, 'read_error': 'elevator_animation_byte_invalid'}
    return {**result, 'read_valid': True, 'shadow_scroll_y': shadow,
            'hardware_scroll_y': hardware, 'channel5_sound_id': sound}


def _rows(text):
    cells = text.get('cells') if isinstance(text, dict) else None
    if (not isinstance(cells, (list, tuple)) or len(cells) != 18
            or any(not isinstance(row, (str, list, tuple)) or len(row) != 20
                   or any(not isinstance(c, str) or len(c) != 1 for c in row) for row in cells)):
        return None
    return tuple(''.join(row).upper() for row in cells)


def floor_menu(text):
    """純20×18來源版面驗證。沒有有效active游標就永遠不回可確認索引。

    部分既知提示／標籤且沒有游標只可等待；重複、錯位、NOT或未知字即invalid。
    ▷只代表A後inactive收尾，不當成仍可選取的游標。
    """
    rows = _rows(text)
    if rows is None:
        return {'status': 'invalid', 'reason': 'elevator_visible_cells_invalid'}
    flat = ''.join(rows)
    present = any(label in flat for label, _ in _FLOORS) or 'WHICH' in flat
    present = present or any(rows[y][x:19].strip() for x, y, _ in _QUESTION)
    markers = [(c, x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c in '▶▷▼']
    if not present:
        return {'status': 'invalid' if markers else 'absent',
                'reason': 'elevator_unknown_menu_marker' if markers else None}
    complete = True
    for label, y in _FLOORS:
        positions = [(m.start(), yy) for yy, row in enumerate(rows)
                     for m in re.finditer(r'(?<![A-Z0-9])' + label + r'(?![A-Z0-9])', row)]
        slot = rows[y][6:19].strip()
        if positions not in ([], [(6, y)]) or not label.startswith(slot):
            return {'status': 'invalid', 'reason': 'elevator_floor_labels_not_unique_source_layout'}
        if slot == label and positions != [(6, y)]:
            return {'status': 'invalid', 'reason': 'elevator_floor_labels_not_unique_source_layout'}
        complete = complete and slot == label
    expected = [[' '] * 20 for _ in range(18)]
    for label, y in _FLOORS:
        expected[y][6:6+len(label)] = label
    for x, y, label in _QUESTION:
        slot = rows[y][x:19].strip()
        if not label.startswith(slot):
            return {'status': 'invalid', 'reason': 'elevator_question_not_source_text'}
        complete = complete and slot == label
        expected[y][x:x+len(label)] = label
    # 菜單內與下方對話只能出現已知文字；背景圖塊不參與字母辨識。
    for y in range(3, 12):
        for x in range(5, 19):
            if rows[y][x] not in (' ', expected[y][x]) and not (x == 5 and y in (4, 6, 8) and rows[y][x] in '▶▷'):
                return {'status': 'invalid', 'reason': 'elevator_unknown_menu_content'}
    for y in range(12, 18):
        for x in range(20):
            if rows[y][x] not in (' ', expected[y][x]):
                return {'status': 'invalid', 'reason': 'elevator_question_not_source_text'}
    if not markers:
        return {'status': 'partial'}
    if len(markers) != 1 or markers[0][1] != 5 or markers[0][2] not in (4, 6, 8) or not complete:
        return {'status': 'invalid', 'reason': 'elevator_cursor_not_unique_source_layout'}
    marker, _, y = markers[0]
    return {'status': 'active' if marker == '▶' else 'inactive', 'index': (y - 4) // 2}


def _inventory(progress):
    values = progress.get('inventory') if isinstance(progress, dict) else None
    if (not isinstance(values, list) or not 1 <= len(values) <= 20
            or any(not isinstance(v, dict) or set(v) != {'item', 'quantity'}
                   or type(v['item']) is not int or not 1 <= v['item'] <= 255
                   or type(v['quantity']) is not int or not 1 <= v['quantity'] <= 99 for v in values)):
        return None
    pairs = tuple((v['item'], v['quantity']) for v in values)
    return pairs if len({item for item, _ in pairs}) == len(pairs) else None


def _plain_overworld(rows):
    # 固定兩個tileset的地圖圖塊不是字型；明顯文字／任何游標不是野外證據。
    # 不把呼叫端的ready旗標當成跳過可見選單檢查的授權。
    return not re.search(r'[A-Z0-9▶▷▼]', ''.join(rows)) and not ''.join(rows[12:]).strip()


def _grid_error(grid, frame, location, *, require_source=False):
    if not isinstance(grid, dict):
        return 'elevator_visible_grid_required'
    mid, x, y = location
    width, height, tileset = (6, 8, 18) if mid == MAP_ID else (30, 28 if mid == 199 else 24, 22)
    if (grid.get('tileset_id') != tileset or type(grid.get('tileset_id')) is not int
            or type(grid.get('observation_frame')) is not int or grid['observation_frame'] != frame
            or grid.get('verified_location') != list(location)
            or any(type(value) is not int for value in grid.get('verified_location', []))):
        return 'elevator_grid_observation_not_current'
    for key, limit in (('tiles', 255), ('walkable', 1)):
        cells = grid.get(key)
        if (not isinstance(cells, (list, tuple)) or len(cells) != height
                or any(not isinstance(row, (list, tuple)) or len(row) != width
                       or any(type(v) is not int or not 0 <= v <= limit for v in row) for row in cells)):
            return 'elevator_grid_shape_or_values_invalid'
    visible = grid.get('visible_verified_cells')
    if (not isinstance(visible, (list, tuple)) or not 12 <= len(visible) <= 90
            or any(not isinstance(p, (list, tuple)) or len(p) != 2
                   or any(type(v) is not int for v in p)
                   or not 0 <= p[0] < width or not 0 <= p[1] < height for p in visible)
            or len({tuple(p) for p in visible}) != len(visible)
            or type(grid.get('screen_cells_verified')) is not int
            or grid['screen_cells_verified'] != len(visible)
            or (x, y) not in {tuple(p) for p in visible}):
        return 'elevator_grid_visible_proof_missing'
    if require_source and (tuple(map(tuple, grid['tiles'])) != _ELEVATOR_TILES
                           or any(grid['walkable'][yy][xx] != int(tile in _LOBBY_COLLISION)
                                  for yy, row in enumerate(_ELEVATOR_TILES) for xx, tile in enumerate(row))):
        return 'elevator_grid_does_not_match_fixed_source'
    if mid in (199, DESTINATION_MAP) and (grid['tiles'][y][x] != (0x52 if y == (19 if mid == 199 else 15) else 1)
                                         or grid['walkable'][y][x] != 1):
        return 'elevator_destination_tile_not_source_exit'
    return None


class RocketElevatorController:
    """預設B4F；返B1F必須明確B1F_INTENT，初始必須已正常到(1,2)。

    context(text,progress,location,grid,movement,animation,*,frame,now,
            overworld_ready,battle_active=False,cancel=False)
    now為呼叫端單調時鐘。完整游標回饋後才發下一鍵；同frame不重送。
    cancel僅在已驗證active樓層選單按B，最後不冒稱到達目標樓層。
    """
    def __init__(self, intent=None, *, max_calls=160, max_waits=100, max_seconds=60):
        if intent is not None and intent not in (INTENT, B1F_INTENT):
            raise ValueError('電梯只支援固定Rocket B4F或明確B1F返程意圖')
        if any(type(v) is not int or not 1 <= v <= 1000 for v in (max_calls, max_waits)):
            raise ValueError('操作／等待上限必須為1..1000')
        if type(max_seconds) not in (int, float) or not math.isfinite(max_seconds) or not 0 < max_seconds <= 60:
            raise ValueError('時間上限必須為0..60秒')
        self.max_calls, self.max_waits, self.max_seconds = max_calls, max_waits, max_seconds
        self.stage, self.error = 'initial', None
        self.calls = self.waits = self.turns = self.stable_count = 0
        self.started_at = self.last_time = self.last_frame = self.last_sample = None
        self.baseline_inventory = self.baseline_scy = self.selection_frame = None
        self.expected_cursor = self.previous_cursor = None
        self.stable_signature = self.stable_frame = None
        self.cancel_requested = False
        self.target_floor = (INTENT if intent is None else intent)['target_floor']

    @property
    def destination_spec(self):
        # 已實測舊B4F實例可能由父層保留後熱載入；缺新欄位只沿用原B4F契約。
        return _DESTINATIONS[getattr(self, 'target_floor', 'B4F')]

    def _result(self, action, tactic, **extra):
        objective = ('Wait.' if action == 'wait' else 'Confirm the current selection.' if action == 'a'
                     else 'Cancel the current menu.' if action == 'b' else f'Move {action.upper()}.')
        return {'phase': 'rocket_elevator', 'objective': objective,
                'available_actions': ['wait'] if action == 'wait' else [action, 'wait'],
                'controller_menu_verified': True, 'rocket_elevator_tactic': tactic,
                'rocket_elevator_stage': self.stage, 'source_commit': SOURCE_COMMIT, 'sources': SOURCES,
                'rocket_elevator_target_floor': getattr(self, 'target_floor', 'B4F'),
                'rocket_elevator_destination_map': self.destination_spec[0],
                'suppress_navigation_stall': True, 'suppress_blocked_edge_learning': True, **extra}

    def _review(self, reason):
        self.error = reason
        return {**self._result('wait', 'operator_review_required'),
                'phase': 'campaign_review', 'review_reason': reason}

    def _wait(self, tactic):
        self.waits += 1
        if self.waits > self.max_waits:
            return self._review('elevator_wait_budget_exhausted')
        return self._result('wait', tactic, safe_wait_count=self.waits, safe_wait_limit=self.max_waits)

    def context(self, text, progress, location, grid, movement, animation, *, frame, now,
                overworld_ready, battle_active=False, cancel=False, visible_text_verified=True):
        if self.error:
            return self._review(self.error)
        self.calls += 1
        if (type(frame) is not int or frame < 0 or type(now) not in (int, float)
                or not math.isfinite(now) or now < 0 or self.last_frame is not None and frame < self.last_frame
                or self.last_time is not None and now < self.last_time):
            return self._review('elevator_clock_or_frame_invalid')
        if self.started_at is None:
            self.started_at = now
        if self.calls > self.max_calls or now - self.started_at > self.max_seconds:
            return self._review('elevator_operation_budget_exhausted')
        if (battle_active is not False or type(overworld_ready) is not bool or type(cancel) is not bool
                or type(visible_text_verified) is not bool or not visible_text_verified and overworld_ready):
            return self._review('elevator_requires_verified_nonbattle_and_ui')
        if (not isinstance(location, dict) or any(type(location.get(k)) is not int for k in ('map_id', 'x', 'y'))
                or location.get('facing') not in ('up', 'down', 'left', 'right')):
            return self._review('elevator_location_invalid')
        point = (location['x'], location['y'])
        mid = location['map_id']
        destination_map, target_index, destination_cells = self.destination_spec
        target_floor = getattr(self, 'target_floor', 'B4F').lower()
        transitional_exit=(self.stage=='exit_up_requested' and mid==destination_map and point==EXIT)
        if (mid == MAP_ID and point not in (PANEL_STANCE, (2, 2), EXIT)
                or mid == destination_map and point not in destination_cells and not transitional_exit
                or mid not in (MAP_ID, destination_map)):
            return self._review('elevator_location_outside_source_route')
        rows = _rows(text)
        if rows is None and visible_text_verified:
            return self._review('elevator_visible_cells_invalid')
        inv = _inventory(progress)
        if inv is None or not any(item == LIFT_KEY for item, _ in inv):
            return self._review('elevator_lift_key_inventory_not_verified')
        if self.baseline_inventory is not None and inv != self.baseline_inventory:
            return self._review('elevator_inventory_changed')
        if (not isinstance(movement, dict) or movement.get('read_valid') is not True
                or movement.get('profile') != MOVEMENT_PROFILE or movement.get('source_commit') != SOURCE_COMMIT
                or type(movement.get('observation_frame')) is not int or movement['observation_frame'] != frame
                or type(movement.get('spinning')) is not bool
                or any(not _byte(movement.get(k)) for k in ('simulated_remaining', 'joy_ignore', 'walk_counter'))
                or movement['joy_ignore'] not in (0, 255)):
            return self._review('elevator_movement_not_verified')
        if (not isinstance(animation, dict) or animation.get('read_valid') is not True
                or animation.get('profile') != ANIMATION_PROFILE or animation.get('source_commit') != SOURCE_COMMIT
                or type(animation.get('observation_frame')) is not int or animation['observation_frame'] != frame
                or any(not _byte(animation.get(k)) for k in ('shadow_scroll_y', 'hardware_scroll_y', 'channel5_sound_id'))):
            return self._review('elevator_animation_not_verified')
        if transitional_exit:
            # 實戰正常warp先更新map ID、稍後才更新座標／地圖；僅等待，不當抵達證據。
            self.stable_count,self.stable_signature,self.stable_frame=0,None,None
            self.last_time=now
            return self._wait('await_destination_coordinates_after_normal_exit_warp')
        if not visible_text_verified:
            if self.stage not in {'settling','exit_right_requested','exit_up_requested'}:
                return self._review('elevator_visible_text_not_verified')
            self.stable_count,self.stable_signature,self.stable_frame=0,None,None
            self.last_time=now
            return self._wait('await_complete_visible_text_during_game_owned_transition')
        idle = not movement['spinning'] and not any(movement[k] for k in ('simulated_remaining', 'joy_ignore', 'walk_counter'))
        if grid is not None:
            error = _grid_error(grid, frame, (mid, *point), require_source=mid == MAP_ID)
            if error:
                return self._review(error)
        sample = (mid, point, location['facing'], rows, inv,
                  tuple(movement[k] for k in ('spinning', 'simulated_remaining', 'joy_ignore', 'walk_counter')),
                  tuple(animation[k] for k in ('shadow_scroll_y', 'hardware_scroll_y', 'channel5_sound_id')),
                  None if grid is None else (tuple(map(tuple, grid['tiles'])), tuple(map(tuple, grid['walkable'])),
                                             tuple(map(tuple, grid['visible_verified_cells']))), overworld_ready)
        if self.last_frame == frame:
            if sample != self.last_sample:
                return self._review('elevator_same_frame_observation_conflict')
            self.last_time = now
            return self._wait('await_new_observation_frame_without_resending')
        self.last_frame, self.last_time, self.last_sample = frame, now, sample
        menu = floor_menu(text)
        if self.stage == 'initial':
            if (mid != MAP_ID or point != PANEL_STANCE or not overworld_ready or not idle
                    or grid is None or menu['status'] != 'absent' or not _plain_overworld(rows)
                    or animation['shadow_scroll_y'] != animation['hardware_scroll_y']
                    or animation['channel5_sound_id'] != 0):
                return self._review('elevator_initial_stance_screen_or_idle_not_verified')
            self.baseline_inventory, self.baseline_scy = inv, animation['shadow_scroll_y']
            if cancel:
                return self._review('elevator_cancel_requires_verified_floor_menu')
            if not {(1, 1), PANEL_STANCE} <= {tuple(p) for p in grid['visible_verified_cells']}:
                return self._review('elevator_panel_cells_not_visibly_verified')
            if location['facing'] != PANEL_FACE:
                self.turns += 1
                if self.turns > 2:
                    return self._review('elevator_panel_turn_budget_exhausted')
                return self._result('up', 'face_only_verified_panel_wall')
            self.stage = 'panel_requested'
            return self._result('a', 'interact_only_verified_lift_key_panel')
        if self.stage in ('panel_requested', 'floor_menu'):
            if mid != MAP_ID or point != PANEL_STANCE or location['facing'] != PANEL_FACE:
                return self._review('elevator_panel_location_changed')
            if menu['status'] == 'invalid':
                return self._review(menu['reason'])
            if menu['status'] in ('absent', 'partial'):
                if overworld_ready:
                    return self._review('elevator_menu_absent_after_panel_request')
                return self._wait('wait_known_floor_question_or_labels_without_a')
            if menu['status'] != 'active' or overworld_ready:
                return self._review('elevator_active_floor_menu_not_verified')
            index = menu['index']
            if self.stage == 'panel_requested' and index != 0:
                return self._review('elevator_initial_cursor_not_source_first_floor')
            self.stage = 'floor_menu'
            if self.expected_cursor is not None:
                if index == self.previous_cursor:
                    return self._wait('await_observed_cursor_change_without_resending')
                if index != self.expected_cursor:
                    return self._review('elevator_cursor_moved_unexpectedly')
                self.expected_cursor = self.previous_cursor = None
            if cancel:
                self.stage, self.cancel_requested = 'cancelling', True
                return self._result('b', 'cancel_only_verified_floor_menu')
            if index < target_index:
                self.previous_cursor, self.expected_cursor = index, index + 1
                return self._result('down', f'move_one_verified_floor_row_toward_{target_floor}', observed_cursor_index=index)
            if index != target_index:
                return self._review('elevator_cursor_not_explicit_target_floor')
            self.stage, self.selection_frame = 'settling', frame
            return self._result('a', f'confirm_only_visible_{target_floor}_at_source_cursor', observed_cursor_index=index)
        if self.stage == 'cancelling':
            if mid != MAP_ID or point != PANEL_STANCE:
                return self._review('elevator_cancel_location_changed')
            if menu['status'] in ('active', 'inactive'):
                return self._wait('await_verified_cancel_without_resending_b')
            if menu['status'] != 'absent':
                return self._review('elevator_cancel_unknown_screen')
            if not overworld_ready or grid is None or not idle or not _plain_overworld(rows):
                return self._wait('await_cancelled_overworld')
            self.stage = 'cancelled'
            return self._result('wait', 'floor_menu_cancelled', rocket_elevator_cancelled=True)
        if self.stage == 'cancelled':
            return self._result('wait', 'floor_menu_cancelled', rocket_elevator_cancelled=True)
        if self.stage == 'settling':
            if mid != MAP_ID or point != PANEL_STANCE:
                return self._review('elevator_location_changed_before_verified_exit')
            if menu['status'] in ('active', 'inactive'):
                if menu.get('index') != target_index or overworld_ready:
                    return self._review('elevator_selected_floor_cursor_conflict')
                self.stable_count, self.stable_signature, self.stable_frame = 0, None, None
                return self._wait(f'await_{target_floor}_menu_close_without_second_a')
            if menu['status'] != 'absent':
                return self._review('elevator_unknown_post_selection_screen')
            animation_idle = (frame - self.selection_frame >= MIN_ANIMATION_FRAMES
                              and animation['shadow_scroll_y'] == self.baseline_scy
                              and animation['hardware_scroll_y'] == self.baseline_scy
                              and animation['channel5_sound_id'] == 0)
            if not animation_idle or not overworld_ready or not idle or grid is None or not _plain_overworld(rows):
                self.stable_count, self.stable_signature, self.stable_frame = 0, None, None
                return self._wait('wait_game_owned_animation_sound_and_visible_overworld')
            signature = tuple(map(tuple, grid['tiles']))
            if signature != self.stable_signature:
                self.stable_count, self.stable_signature, self.stable_frame = 1, signature, frame
            elif frame - self.stable_frame >= 3:
                self.stable_count += 1
                self.stable_frame = frame
            if self.stable_count < 2:
                return self._wait('verify_animation_finished_on_distinct_stable_frames')
            if not {(1, 2), (2, 2), EXIT} <= {tuple(p) for p in grid['visible_verified_cells']}:
                return self._review('elevator_exit_route_not_visibly_verified')
            self.stage = 'exit_right_requested'
            return self._result('right', 'walk_one_source_cell_toward_normal_exit')
        if self.stage in ('exit_right_requested', 'exit_up_requested', 'complete'):
            if menu['status'] != 'absent':
                return self._review('elevator_unknown_ui_during_exit')
            if mid == destination_map:
                if self.stage not in ('exit_up_requested', 'complete'):
                    return self._review('elevator_destination_without_normal_exit_request')
                if not overworld_ready or grid is None or not idle or not _plain_overworld(rows):
                    return self._wait(f'await_actual_{target_floor}_source_exit_screen')
                self.stage = 'complete'
                return self._result('wait', f'{target_floor}_actual_map_and_source_exit_verified',
                                    rocket_elevator_complete=True, observed_destination=[mid, *point])
            if self.stage == 'complete':
                return self._review('elevator_completed_destination_changed')
            if not overworld_ready or grid is None or not idle or not _plain_overworld(rows):
                return self._wait('await_normal_exit_movement_without_resending')
            if self.stage == 'exit_right_requested':
                if point == PANEL_STANCE:
                    return self._wait('await_observed_right_step_without_resending')
                if point != (2, 2):
                    return self._review('elevator_right_step_not_source_cell')
                self.stage = 'exit_up_requested'
                return self._result('up', 'walk_normally_into_source_exit_warp')
            if point not in ((2, 2), EXIT):
                return self._review('elevator_exit_step_not_source_cell')
            return self._wait(f'await_actual_{target_floor}_warp_without_resending')
        return self._review('elevator_controller_stage_unknown')
