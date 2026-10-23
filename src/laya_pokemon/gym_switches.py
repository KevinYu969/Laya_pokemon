"""枯葉道館垃圾桶的可見訊息控制器；只產生子目標，不讀寫遊戲記憶體。

固定來源 pret/pokered a53671100ec22e5394ff26ec028d0812a238dae2：
data/events/hidden_events.asm、engine/events/hidden_events/vermilion_gym_trash.asm。
呼叫者應在一般戰鬥／學招處理後呼叫，並傳入實際已執行的 previous 動作。
同一 instance 可跨主控熱載入保留；程序重啟不可假定知道首鎖所在桶。
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math
import re
import time


MAP_ID = 92
FIRST_EVENT = 'first_lock_opened'   # EVENT_1ST_LOCK_OPENED = 0x161
SECOND_EVENT = 'second_lock_opened'  # EVENT_2ND_LOCK_OPENED = 0x160
CANS = tuple((x, y) for x in (1, 3, 5, 7, 9) for y in (7, 9, 11))
_DIRECTIONS = {'up': (0, -1), 'left': (-1, 0), 'right': (1, 0), 'down': (0, 1)}


def _compact(value):
    return re.sub('[^A-Z0-9]', '', str(value).upper())


def _screen(text):
    cells = text.get('cells', [])
    if len(cells) != 18 or any(len(row) != 20 for row in cells):
        return None
    rows = [''.join(row) for row in cells]
    # 實際下方對話區；不將背景上方偶然解碼的英文字當成機關訊息。
    lower = '\n'.join(rows[12:18])
    return _compact(lower), bool(re.search('[A-Za-z]{2}', lower))


def _verified_cells(grid):
    if not isinstance(grid, dict) or grid.get('screen_cells_verified', 0) < 12:
        return None
    cells = grid.get('walkable')
    if (not isinstance(cells, list) or len(cells) != 18
            or any(not isinstance(row, list) or len(row) != 10 for row in cells)
            or any(value not in (0, 1) for row in cells for value in row)):
        return None
    return cells


def _paths(cells, start, blocked):
    forbidden = set(blocked) | set(CANS)
    parents = {start: None}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in _DIRECTIONS.values():
            point = x + dx, y + dy
            xx, yy = point
            if (0 <= xx < 10 and 0 <= yy < 18 and cells[yy][xx] == 1
                    and point not in parents and point not in forbidden):
                parents[point] = (x, y)
                queue.append(point)
    return parents


def _path(parents, target):
    if target not in parents:
        return None
    result = []
    while target is not None:
        result.append(target)
        target = parents[target]
    return result[::-1]


def second_candidates(first):
    """相鄰桶優先，最後加原版下溢 bug 的桶 0；不讀隱藏答案。"""
    x, y = CANS[first]
    adjacent = [i for i, (xx, yy) in enumerate(CANS)
                if abs(xx - x) + abs(yy - y) == 2]
    if first != 0 and 0 not in adjacent:
        adjacent.append(0)
    # 首鎖本身不是第二鎖（桶0首鎖時，其下溢情況可能仍為0，故也保留bug候選）。
    if first == 0:
        adjacent.append(0)
    return adjacent


@dataclass
class GymSwitchController:
    max_attempts: int = 120
    max_seconds: float = 240.0
    max_resets: int = 24
    max_response_steps: int = 12
    state: str = 'search_first'
    first_can: int | None = None
    current_can: int | None = None
    checked: set = field(default_factory=set)
    second_rotations: dict = field(default_factory=dict)
    attempts: int = 0
    resets: int = 0
    active_seconds: float = 0.0
    history: list = field(default_factory=list)
    _pending: bool = False
    _result: str | None = None
    _response_steps: int = 0
    _first_intro: bool = False
    _completion_text_seen: bool = False
    _issued: tuple | None = None
    _face_verified: tuple | None = None
    _last_now: float | None = None
    _last_paused: bool = True
    _review_reason: str | None = None

    def __post_init__(self):
        if (not isinstance(self.max_attempts, int) or self.max_attempts < 1
                or not isinstance(self.max_resets, int) or self.max_resets < 1
                or not isinstance(self.max_response_steps, int) or self.max_response_steps < 1
                or not isinstance(self.max_seconds, (int, float))
                or not math.isfinite(self.max_seconds) or self.max_seconds <= 0):
            raise ValueError('機關嘗試／時間上限必須為正數')

    def _meta(self):
        return {'gym_switch_state': self.state, 'gym_switch_can': self.current_can,
                'gym_switch_first_can': self.first_can, 'gym_switch_attempts': self.attempts,
                'gym_switch_resets': self.resets, 'gym_switch_active_seconds': self.active_seconds,
                'gym_switch_version_bug': 'second lock may be can0; fixed original Red source'}

    def _review(self, reason):
        self._review_reason = reason
        return {'phase': 'campaign_review', 'review_reason': reason, 'objective': 'Wait.',
                'available_actions': ['wait'], **self._meta()}

    def _command(self, action, **extra):
        objectives = {'a': 'Confirm the current selection.', 'wait': 'Wait.',
                      **{direction: 'Move ' + direction.upper() + '.' for direction in _DIRECTIONS}}
        return {'phase': 'overworld', 'objective': objectives[action],
                'available_actions': [action, 'wait'] if action != 'wait' else ['wait'],
                'goal': 'vermilion-gym-switches', 'controller_menu_verified': True,
                'phase_source': 'visible gym switch dialogue and source-verified adjacent-cell navigation',
                **self._meta(), **extra}

    def _reset(self):
        self.state = 'reset'
        if self.first_can is not None:
            self.second_rotations[self.first_can] = self.second_rotations.get(self.first_can, 0) + 1
        self.resets += 1
        self.checked.clear()
        self.first_can = None
        self._first_intro = False
        self.history.append({'kind': 'reset', 'can': self.current_can, 'attempt': self.attempts})

    def context(self, text, location, progress, grid, *, battle_state=None,
                previous=(), blocked=(), now=None):
        """回傳導航／互動子目標、完成訊號或 review；戰鬥和其他地圖回 None。

        ``progress.story_event_bits`` 需有兩個具 bool 值的 FIRST/SECOND_EVENT。
        ``grid`` 是已與畫面校準的 read_world_grid 結果，尚在對話時可為 None。
        ``previous`` 是真正執行完的動作，不是本函式曾經建議的動作。
        完成回傳 ``gym_switches_complete=True``，呼叫者應推進路線。
        """
        current_time = time.monotonic() if now is None else now
        if (not isinstance(current_time, (int, float)) or not math.isfinite(current_time)
                or self._last_now is not None and current_time < self._last_now):
            return self._review('gym_switch_clock_invalid')
        in_battle = bool(battle_state and (battle_state.get('active')
                         or battle_state.get('kind') not in {None, 'none'}))
        paused = not location or location.get('map_id') != MAP_ID or in_battle
        if self._last_now is not None and not paused and not self._last_paused:
            self.active_seconds += current_time - self._last_now
        self._last_now, self._last_paused = current_time, paused
        if paused:
            self._issued = self._face_verified = None
            if in_battle:
                # 戰鬥不可被選桶／確認訊息攔走；若尚未收到檢查結果，回來重查同桶。
                self._pending = False
                self._response_steps = 0
            return None
        if self._review_reason:
            return self._review(self._review_reason)
        events = progress.get('story_event_bits', {})
        first, second = events.get(FIRST_EVENT), events.get(SECOND_EVENT)
        if not isinstance(first, bool) or not isinstance(second, bool):
            return self._review('gym_switch_events_unavailable')
        if second and not first:
            return self._review('gym_switch_event_inconsistency')
        screen = _screen(text)
        if screen is None:
            return self._review('gym_switch_full_screen_unavailable')
        compact, lower_dialogue = screen
        position = location.get('x'), location.get('y')
        if any(not isinstance(v, int) or isinstance(v, bool) for v in position):
            return self._review('gym_switch_location_invalid')
        if not (0 <= position[0] < 10 and 0 <= position[1] < 18):
            return self._review('gym_switch_location_invalid')
        if self._issued:
            action, can, stand, face = self._issued
            if previous and previous[-1] == action and self.current_can == can and position == stand:
                if action == 'a':
                    self._pending = True
                    self._response_steps = 0
                    self.attempts += 1
                elif action == face:
                    self._face_verified = (stand, face)
            self._issued = None

        first_final = '1STELECTRICLOCKOPENED' in compact
        second_final = ('2NDELECTRICLOCKOPENED' in compact or 'MOTORIZEDDOOROPENED' in compact)
        reset_final = 'LOCKSWERERESET' in compact
        intro = ('SWITCHUNDER' in compact or 'TURNITON' in compact or 'SWITCHUNDERTHE' in compact)
        trash = 'ONLYTRASHHERE' in compact
        own_text = first_final or second_final or reset_final or intro or trash
        if second_final:
            if not first or not second:
                return self._review('gym_switch_second_text_event_mismatch')
            self.state = 'complete'
            self._completion_text_seen = True
            self._pending = False
            self._result = 'complete'
            return self._command('a', gym_switch_dialogue='second_lock_confirmed')
        if self.state == 'complete':
            if not first or not second:
                return self._review('gym_switch_completed_event_changed')
            if own_text:
                return self._command('a', gym_switch_dialogue='close_completed_dialogue')
            door_cells=_verified_cells(grid)
            if not lower_dialogue and door_cells and all(door_cells[y][x]==1 for y in (4,5) for x in (4,5)):
                return self._command('wait', gym_switches_complete=True,gym_switch_door_grid_verified=True)
            self._completion_wait_steps=getattr(self,'_completion_wait_steps',0)+1
            if self._completion_wait_steps<=30:return self._command('wait',gym_switch_waiting_for_door=True)
            return self._review('gym_switch_open_door_unverified')
        cells = _verified_cells(grid)
        if second:
            # 重新接入已解開的道館：事件＋來源門區實際可走，不能再搜尋垃圾桶。
            if cells and all(cells[y][x] == 1 for y in (4, 5) for x in (4, 5)):
                self.state = 'complete'
                return self._command('wait', gym_switches_complete=True, gym_switch_door_grid_verified=True)
            if self._pending and self.current_can is not None:
                self._second_wait_steps=getattr(self,'_second_wait_steps',0)+1
                if self._second_wait_steps<=30:
                    return self._command('wait',gym_switch_waiting_for_second_lock_dialogue=True)
            return self._review('gym_switch_open_door_unverified')
        if self.active_seconds >= self.max_seconds:
            return self._review('gym_switch_budget_exhausted')
        if reset_final:
            if first:
                return self._review('gym_switch_reset_text_event_mismatch')
            if self._result != 'reset':
                if not self._pending and self.state != 'search_second':
                    return self._review('gym_switch_unassociated_reset')
                self._reset()
                self._result = 'reset'
                self._pending = False
            return self._command('a', gym_switch_dialogue='reset_confirmed')
        if first_final:
            if not first:
                return self._review('gym_switch_first_text_event_mismatch')
            if self._result != 'first':
                if not self._pending or self.current_can is None:
                    return self._review('gym_switch_first_origin_unknown')
                self.first_can = self.current_can
                self.state = 'search_second'
                self._result = 'first'
                self._pending = False
                self._first_intro = False
                self.history.append({'kind': 'first_lock', 'can': self.first_can, 'attempt': self.attempts})
            return self._command('a', gym_switch_dialogue='first_lock_confirmed')
        if intro:
            if not self._pending or self.current_can is None or not first:
                return self._review('gym_switch_unassociated_first_intro')
            self._first_intro = True
            return self._command('a', gym_switch_dialogue='first_lock_wrapped_page')
        if trash:
            if self.state == 'search_second' and not first:
                # 第二鎖錯誤第一頁仍是普通垃圾文字；等後面的 reset 頁再確認一次。
                if self._pending:
                    self._reset()
                    self._result = 'reset'
                    self._pending = False
                return self._command('a', gym_switch_dialogue='advance_reset_wrapped_page')
            if self._result in {'trash', 'reset'}:
                return self._command('a', gym_switch_dialogue='close_trash_dialogue')
            if self.state != 'search_first' or first or not self._pending or self.current_can is None:
                return self._review('gym_switch_trash_context_mismatch')
            self.checked.add(self.current_can)
            self.history.append({'kind': 'trash', 'can': self.current_can, 'attempt': self.attempts})
            self._result = 'trash'
            self._pending = False
            return self._command('a', gym_switch_dialogue='trash_confirmed')
        if lower_dialogue:
            return None  # 不代替外層推進訓練家等無關對話。
        if self._first_intro and self._pending and first:
            # 外層可能在完整首鎖結尾出現前先推進對話；已見 switch/Turn it on
            # 與首鎖事件且此次 A/桶來源完整，足以交叉核對，不憑空等消失的末頁。
            self.first_can = self.current_can
            self.state = 'search_second'
            self._pending = False
            self._result = 'first'
            self._first_intro = False
            self.history.append({'kind': 'first_lock', 'can': self.first_can,
                                 'attempt': self.attempts, 'evidence': 'visible_intro_and_event'})
        if self._result:
            self._result = None
            self.current_can = None
            self._face_verified = None
            if self.state == 'reset':
                self.state = 'search_first'
        if self._pending:
            self._response_steps += 1
            if self._response_steps >= self.max_response_steps:
                return self._review('gym_switch_response_not_verified')
            return self._command('wait', gym_switch_waiting_for_result=True)
        if (self.attempts >= self.max_attempts or self.resets >= self.max_resets
                or self.active_seconds >= self.max_seconds):
            return self._review('gym_switch_budget_exhausted')
        if first and self.first_can is None:
            return self._review('gym_switch_first_origin_unknown')
        if not first and self.state == 'search_second':
            return self._review('gym_switch_unexplained_first_lock_reset')
        if cells is None:
            if grid is not None:return self._review('gym_switch_grid_unverified')
            self._grid_wait_steps=getattr(self,'_grid_wait_steps',0)+1
            if self._grid_wait_steps>12:return self._review('gym_switch_grid_unverified')
            return self._command('wait',gym_switch_waiting_for_grid=True)
        self._grid_wait_steps=0
        if self.current_can is None:
            if self.state == 'search_second':
                choices = second_candidates(self.first_can)
                choice = choices[self.second_rotations.get(self.first_can, 0) % len(choices)]
                candidates = [choice]
            else:
                candidates = [i for i in range(len(CANS)) if i not in self.checked]
            if not candidates:
                return self._review('gym_switch_first_search_exhausted')
        else:
            candidates = [self.current_can]
        parents = _paths(cells, position, blocked)
        options = []
        for index in candidates:
            cx, cy = CANS[index]
            for face, (dx, dy) in _DIRECTIONS.items():
                stand = cx - dx, cy - dy
                path = _path(parents, stand)
                if path:
                    options.append((len(path), index, stand, face, path))
        if not options:
            return self._review('gym_switch_adjacent_cell_unreachable')
        _, index, stand, face, path = min(options)
        self.current_can = index
        extra = {'navigation_target': list(stand), 'face': face, 'gym_switch_target': list(CANS[index])}
        if len(path) > 1:
            dx, dy = path[1][0] - position[0], path[1][1] - position[1]
            action = next(d for d, delta in _DIRECTIONS.items() if delta == (dx, dy))
            self._face_verified = None
            return self._command(action, **extra)
        if self._face_verified != (stand, face):
            self._issued = face, index, stand, face
            return self._command(face, controller_interaction=True, **extra)
        self._issued = 'a', index, stand, face
        return self._command('a', controller_interaction=True, **extra)
