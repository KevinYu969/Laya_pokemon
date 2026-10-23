"""卡比獸最後一投後的純收服結尾候選；沒有I/O、模型、getter或按鍵執行。

只支援固定Route12、新圖鑑分支、原四人隊；caller須另取得最後一投前
同一場戰鬥的完整snapshot。本模組不假裝既有battle_state已提供敵HP。
"""
from copy import deepcopy
import math
import re

from .observation import PROFILE as TEXT_PROFILE


SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
INTENT = {'kind': 'complete_route12_snorlax_capture', 'map_id': 23, 'x': 10, 'y': 61,
          'species': 132, 'level': 30, 'party_count_before': 4,
          'nickname': 'NO', 'dex_branch': 'new_entry_required'}
SOURCE_ROOT = f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/'
SOURCES = [SOURCE_ROOT + p for p in (
    'engine/items/item_effects.asm#L510', 'data/text/text_6.asm#L29',
    'engine/pokemon/add_mon.asm#L12', 'engine/menus/naming_screen.asm#L1',
    'engine/menus/text_box.asm#L206', 'data/text/text_2.asm#L1756',
    'engine/menus/pokedex.asm#L449', 'data/pokemon/dex_entries.asm#L963',
    'data/pokemon/dex_text.asm#L1091', 'home/text.asm#L245')]
_PROGRESS_PROFILE = 'gen1-wrapper-ram-progress-v1-unvalidated'
_OLD_NAMES = {7: 'NIDOKING', 9: 'IVYSAUR',154:'VENUSAUR', 35: 'FEAROW', 102: 'EEVEE'}
_ALL_NAMES = {**_OLD_NAMES, 132: 'SNORLAX'}
NEW_MOVES, NEW_PP, NEW_EXP = [29, 133, 156, 0], [15, 20, 10, 0], 33750
_BODY = {
    'caught_start': ((1, 14, 'ALL RIGHT!'), (1, 16, 'SNORLAX WAS')),
    'caught_receipt': ((1, 14, 'SNORLAX WAS'), (1, 16, 'CAUGHT!')),
    'new_dex_start': ((1, 14, 'NEW POKÉDEX DATA'), (1, 16, 'WILL BE ADDED FOR')),
    'new_dex_receipt': ((1, 14, 'WILL BE ADDED FOR'), (1, 16, 'SNORLAX!')),
    'dex_first': ((1, 11, 'VERY LAZY. JUST'), (1, 13, 'EATS AND SLEEPS.'), (1, 15, 'AS ITS ROTUND')),
    'dex_second': ((1, 11, 'BULK BUILDS, IT'), (1, 13, 'BECOMES STEADILY'), (1, 15, 'MORE SLOTHFUL.')),
    'nickname_intro': ((1, 14, 'DO YOU WANT TO'), (1, 16, 'GIVE A NICKNAME')),
    'nickname_menu': ((1, 14, 'GIVE A NICKNAME'), (1, 16, 'TO SNORLAX?')),
}
_NEXT = {'caught_start': 'caught_receipt', 'caught_receipt': 'new_dex_start',
         'new_dex_start': 'new_dex_receipt', 'new_dex_receipt': 'dex_first',
         'dex_first': 'dex_second', 'dex_second': 'nickname_intro',
         'nickname_intro': 'nickname_menu'}
_PROMPT_PAGES = set(_NEXT) - {'dex_second'}


def _int(value, low, high):
    return type(value) is int and low <= value <= high


def _clock(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _rows(text, frame):
    if (not isinstance(text, dict) or text.get('profile') != TEXT_PROFILE
            or text.get('read_valid') is not True or text.get('alignment_verified') is not True
            or type(text.get('window_visible')) is not bool or text.get('read_error') is not None
            or 'observation_frame' in text and (type(text['observation_frame']) is not int
                                                or text['observation_frame'] != frame)):
        return None
    cells = text.get('cells')
    if (not isinstance(cells, (list, tuple)) or len(cells) != 18
            or any(not isinstance(row, (list, tuple, str)) or len(row) != 20
                   or any(not isinstance(c, str) or len(c) != 1 for c in row) for row in cells)):
        return None
    raw = tuple(''.join(row) for row in cells)
    if 'lines' in text or 'line_rows' in text:
        selected = [(i, row.rstrip()) for i, row in enumerate(raw) if re.search(r'[A-Za-z0-9]{2,}', row)][:12]
        if text.get('lines') != [row for _, row in selected] or text.get('line_rows') != [i for i, _ in selected]:
            return None
    return tuple(row.upper() for row in raw)


def _party(progress):
    if (not isinstance(progress, dict) or progress.get('profile') != _PROGRESS_PROFILE
            or progress.get('party_read_valid') is not True
            or progress.get('initialization_candidate') is not True):
        return None
    party, count = progress.get('party'), progress.get('party_count')
    if not isinstance(party, list) or not _int(count, 1, 6) or len(party) != count:
        return None
    for mon in party:
        if (not isinstance(mon, dict) or type(mon.get('species')) is not int
                or mon['species'] not in _ALL_NAMES or mon.get('species_name') != _ALL_NAMES[mon['species']]
                or not _int(mon.get('level'), 1, 100) or not _int(mon.get('exp'), 0, 0xFFFFFF)
                or not _int(mon.get('max_hp'), 1, 999) or not _int(mon.get('hp'), 0, mon['max_hp'])
                or type(mon.get('status')) is not int or mon['status'] not in {*range(8), 8, 16, 32, 64}
                or any(not isinstance(mon.get(k), list) or len(mon[k]) != 4
                       or any(not _int(v, 0, cap) for v in mon[k]) for k, cap in (('moves', 165), ('pp', 255)))):
            return None
    return party


def _inventory(progress):
    items = progress.get('inventory') if isinstance(progress, dict) else None
    if (not isinstance(items, list) or len(items) > 20
            or any(not isinstance(x, dict) or set(x) != {'item', 'quantity'}
                   or not _int(x['item'], 1, 250) or not _int(x['quantity'], 1, 99) for x in items)):
        return None
    pairs = [(x['item'], x['quantity']) for x in items]
    return pairs if len(set(i for i, _ in pairs)) == len(pairs) else None


def _stance(location):
    return (isinstance(location, dict) and all(type(location.get(k)) is int for k in ('map_id', 'x', 'y'))
            and (location['map_id'], location['x'], location['y']) == (23, 10, 61))


def _battle(state):
    if not isinstance(state, dict) or type(state.get('raw')) is not int:
        return None
    if state.get('raw') == 0 and state.get('active') is False and state.get('kind') == 'none':
        return 'none'
    if state.get('raw') != 1 or state.get('active') is not True or state.get('kind') != 'wild':
        return None
    for key in ('opponent_species', 'wild_opponent_species'):
        value = state.get(key)
        if not (type(value) is int and value == 132 or type(value) is str and value == 'SNORLAX'):
            return None
    for key in ('enemy_level', 'opponent_level', 'level'):
        if key in state and (type(state[key]) is not int or state[key] != 30):
            return None
    return 'wild'


def _put(rows, x, y, word):
    rows[y][x:x + len(word)] = list(word)


def _dex_header():
    # 固定SDK decoder沒有№/′/″/<DOT>字碼；這些格子投影成空白，
    # 不是偽造標點。數字／HT／WT／lb仍須完整、位置正確。
    rows = [[' '] * 20 for _ in range(11)]
    for x, y, value in ((9, 2, 'SNORLAX'), (9, 4, 'SLEEPING'), (9, 6, 'HT'),
                        (13, 6, '6'), (15, 6, '11'), (4, 8, '143'),
                        (9, 8, 'WT'), (11, 8, '1014'), (16, 8, '0'), (17, 8, 'LB')):
        _put(rows, x, y, value)
    return tuple(''.join(row) for row in rows)


def _dex_initial_placeholder():
    # DrawDexEntryScreen先印來源問號，播放叫聲後才填owned資料。
    # 此頁不能A；本場checkpoint純WAIT已證會進完整資料頁。
    rows=[[' ']*20 for _ in range(18)]
    for x,y,value in ((9,2,'SNORLAX'),(9,4,'SLEEPING'),(9,6,'HT'),(13,6,'?'),
                      (15,6,'??'),(4,8,'143'),(9,8,'WT'),(14,8,'???'),(17,8,'LB')):
        _put(rows,x,y,value)
    return tuple(''.join(row) for row in rows)


class CaptureCompletionController:
    """最後一投的明確交易；完整逐頁才確認，只有兩幀野外驗收才complete。

    last_throw必含frame/now/ball_item/progress/location/battle_state/enemy，
    及同場最後一投前的battle_text/hud_frame。battle_text是袋未遮HUD時
    的有效decoder原物件；caller須保證其後只有正常開袋／選球，沒有
    敵人回合或隊伍改變。敵HP/maxHP/status由caller另提供真實唯讀snapshot，
    不是本模組替既有battle_state補造getter。
    """

    def __init__(self, intent, *, last_throw, max_calls=240, max_seconds=60, max_waits=120):
        if intent != INTENT or any(type(intent.get(k)) is not int for k in INTENT if type(INTENT[k]) is int):
            raise ValueError('只允許指定Route12 Snorlax30四人隊的新圖鑑收服結尾')
        if (not _int(max_calls, 1, 240) or not _int(max_waits, 1, 240)
                or not _clock(max_seconds) or not 0 < max_seconds <= 60):
            raise ValueError('上限240calls／240waits／60秒，可縮不可擴')
        if not isinstance(last_throw, dict):
            raise ValueError('缺最後一投前snapshot')
        b = deepcopy(last_throw)
        required = {'frame', 'now', 'ball_item', 'progress', 'location', 'battle_state', 'enemy', 'battle_text', 'hud_frame'}
        if (set(b) != required or not _int(b['frame'], 0, 2**63 - 1) or not _clock(b['now'])
                or not _int(b['hud_frame'], 0, b['frame']) or type(b['ball_item']) is not int
                or b['ball_item'] not in {2, 3, 4} or not _stance(b['location'])
                or _battle(b['battle_state']) != 'wild'):
            raise ValueError('最後一投frame／位置／球／野生對手缺證')
        p, items = _party(b['progress']), _inventory(b['progress'])
        if (p is None or len(p) != 4 or {m['species'] for m in p} not in ({7,9,35,102},{7,154,35,102})
                or b['progress'].get('player_name_raw') != 'KEVIN' or items is None
                or items.count((73, 1)) != 1 or b['ball_item'] not in dict(items)):
            raise ValueError('最後一投必須有完整原四人／Flute73／指定球基線')
        enemy = b['enemy']
        if (not isinstance(enemy, dict) or set(enemy) != {'species', 'level', 'hp', 'max_hp', 'status'}
                or type(enemy['species']) is not int or enemy['species'] != 132
                or type(enemy['level']) is not int or enemy['level'] != 30
                or not _int(enemy['max_hp'], 136, 145) or not _int(enemy['hp'], 1, enemy['max_hp'])
                or type(enemy['status']) is not int or enemy['status'] not in {*range(8), 8, 16, 32, 64}):
            raise ValueError('必須提供真實Snorlax30捕獲時HP／maxHP／status')
        hud = _rows(b['battle_text'], b['hud_frame'])
        if hud is None or not self._hud_verified(hud, p, enemy):
            raise ValueError('同場最後一投前battle HUD缺證或污染')
        for packet in (b['progress'], b['location'], b['battle_state']):
            if 'observation_frame' in packet and (type(packet['observation_frame']) is not int
                                                  or packet['observation_frame'] != b['frame']):
                raise ValueError('最後一投snapshot frame矛盾')
        self.intent, self._contract, self.baseline = deepcopy(intent), deepcopy(INTENT), b
        self.before_party, self.before_items, self.battle_upper = deepcopy(p), items, hud[:12]
        self.after_items = [(i, q - (i == b['ball_item'])) for i, q in items if i != b['ball_item'] or q > 1]
        self.max_calls, self.max_waits, self.max_seconds = max_calls, max_waits, max_seconds
        self.calls = self.waits = 0
        self.stage, self.error = 'caught_start', None
        self.last_frame, self.last_packet, self.last_now = b['frame'], None, b['now']
        self.pending_page = None
        self.no_down_pending = self.no_confirmed = False
        self.world_frame = self.completion = None

    @staticmethod
    def _hud_verified(rows, party, enemy):
        # Sprite custom tiles可能被既有decoder讀為#；只許來源圖像區的該字碼，
        # 不接受任意文字在背景，再把它當作可信snapshot。
        clean = [list(row) for row in rows[:12]]
        for y, row in enumerate(clean):
            for x, c in enumerate(row):
                if c == '#' and (x < 8 and 5 <= y < 12 or 12 <= x < 19 and y < 7):
                    row[x] = ' '
        clean = [''.join(row) for row in clean]
        if clean[0].strip() != 'SNORLAX':
            return False
        active = [m for m in party if clean[7].strip() == m['species_name']]
        if len(active) != 1:
            return False
        def status(value, level):
            return 'SLP' if value & 7 else {8: 'PSN', 16: 'BRN', 32: 'FRZ', 64: 'PAR'}.get(value, str(level))
        hp = re.fullmatch(r'\s*(\d+)\s*/\s*(\d+)\s*', clean[10])
        lower = [[' '] * 20 for _ in range(6)]
        for x, y, value in ((10, 2, 'FIGHT'), (10, 4, 'ITEM'), (16, 4, 'RUN')):
            _put(lower, x, y, value)
        cursors = [(x, y) for y, row in enumerate(rows[12:]) for x, c in enumerate(row) if c == '▶']
        if len(cursors) != 1 or cursors[0] not in {(9, 2), (15, 2), (9, 4), (15, 4)}:
            return False
        x, y = cursors[0]; lower[y][x] = '▶'
        return (rows[12:] == tuple(''.join(row) for row in lower)
                and clean[1].strip() == status(enemy['status'], 30)
                and clean[8].strip() == status(active[0]['status'], active[0]['level'])
                and hp is not None and tuple(map(int, hp.groups())) == (active[0]['hp'], active[0]['max_hp'])
                and not any(clean[y].strip() for y in (2, 3, 4, 5, 6, 9, 11))
                and not any(c in ''.join(rows[:12]) for c in '▶▷▼'))

    def _hint(self, action, tactic, **extra):
        meta = {'capture_completion_controller': 'route12_snorlax_candidate', 'capture_stage': self.stage,
                'capture_tactic': tactic, 'source_commit': SOURCE_COMMIT, 'sources': SOURCES,
                'capture_complete': False, 'controller_menu_verified': True, **extra}
        if action == 'wait':
            return {'phase': 'capture_completion_menu', 'objective': 'Wait.', 'available_actions': ['wait'], **meta}
        return {'phase': 'capture_completion_menu', 'objective': 'Move DOWN.' if action == 'down' else 'Confirm the current selection.',
                'available_actions': [action, 'wait'], **meta}

    def _fail(self, reason):
        self.error = reason
        return {**self._hint('wait', 'stop_for_review'), 'phase': 'campaign_review',
                'controller_menu_verified': False, 'review_reason': reason}

    def _wait(self, tactic):
        self.waits += 1
        if self.waits > self.max_waits:
            return self._fail('capture_completion_wait_budget_exhausted')
        return self._hint('wait', tactic)

    def _page(self, rows, name, *, menu=False):
        """完整固定版面／已知prefix／矛盾；未知字元不因partial而放行。"""
        template = [[' '] * 20 for _ in range(18)]
        if name.startswith('dex_'):
            template[:11] = [list(row) for row in _dex_header()]
        elif name.startswith('caught_') or name.startswith('new_dex_'):
            template[:12] = [list(row) for row in self.battle_upper]
        for x, y, value in _BODY[name]:
            _put(template, x, y, value)
        if menu:
            _put(template, 16, 8, 'YES'); _put(template, 16, 10, 'NO')
            cursors = [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == '▶']
            if cursors not in ([], [(15, 8)], [(15, 10)]):
                return 'invalid'
            for x, y in cursors:
                template[y][x] = '▶'
        elif any('▶' in row for row in rows):
            return 'invalid'
        if any('▷' in row for row in rows):
            return 'invalid'
        prompt = [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == '▼']
        if prompt not in ([], [(18, 16)]) or prompt and name not in _PROMPT_PAGES:
            return 'invalid'
        clean = [row.replace('▼', ' ') for row in rows]
        if any(c != ' ' and c != template[y][x] for y, row in enumerate(clean) for x, c in enumerate(row)):
            return 'invalid'
        for x, y, value in _BODY[name]:
            actual = clean[y][x:x + len(value)].rstrip()
            if not value.startswith(actual):
                return 'invalid'
        body_full = all(clean[y][x:x + len(value)] == value for x, y, value in _BODY[name])
        header_full = not name.startswith('dex_') or tuple(clean[:11]) == _dex_header()
        if prompt and not (body_full and header_full):
            return 'invalid'
        if not body_full or not header_full:
            return 'partial'
        if menu:
            return 'full' if clean[8][16:19] == 'YES' and clean[10][16:18] == 'NO' and cursors else 'partial'
        return 'full' if bool(prompt) == (name in _PROMPT_PAGES) else 'partial'

    def _progress(self, progress):
        items = _inventory(progress)
        if items is None or items not in (self.before_items, self.after_items):
            return 'capture_completion_inventory_changed'
        if items == self.after_items and not self.no_confirmed:
            return 'capture_completion_ball_consumed_before_nickname_no'
        if progress.get('player_name_raw') != 'KEVIN':
            return 'capture_completion_player_name_changed'
        if ('money' in self.baseline['progress']
                and progress.get('money') != self.baseline['progress']['money']):
            return 'capture_completion_money_changed'
        party = _party(progress)
        can_initialize = self.stage in {'nickname_intro', 'nickname_menu', 'closing'}
        if party is None:
            if (can_initialize and progress.get('profile') == _PROGRESS_PROFILE
                    and progress.get('party_read_valid') is False
                    and progress.get('initialization_candidate') is False
                    and type(progress.get('party_count')) is int and progress['party_count'] == 5
                    and progress.get('party') == []):
                return None
            return 'capture_completion_party_unverified'
        if party[:4] != self.before_party or len(party) not in (4, 5):
            return 'capture_completion_original_party_changed'
        if len(party) == 5:
            if not can_initialize:
                return 'capture_completion_new_party_before_expected_initialization'
            new, enemy = party[4], self.baseline['enemy']
            expected = {'species': 132, 'species_name': 'SNORLAX', 'level': 30,
                        'exp': NEW_EXP, 'hp': enemy['hp'], 'max_hp': enemy['max_hp'],
                        'status': enemy['status'], 'moves': NEW_MOVES, 'pp': NEW_PP}
            if (any(new.get(k) != v for k, v in expected.items())
                    or set(new) - set(expected) - {'nickname'}
                    or 'nickname' in new and new['nickname'] != 'SNORLAX'):
                return 'capture_completion_new_snorlax_fingerprint_invalid'
        return None

    def context(self, text, progress, *, location, battle_state, frame, now,
                overworld_ready=False, grid=None, intent=None):
        """每次僅回一個子目標；caller提供原觀測，不可替未知資料補True／frame。"""
        if self.completion is not None:
            return deepcopy(self.completion)
        if self.error:
            return self._fail(self.error)
        self.calls += 1
        if self.intent != self._contract or intent is not None and intent != self._contract:
            return self._fail('capture_completion_intent_changed')
        if (not _int(frame, self.last_frame, 2**63 - 1) or not _clock(now) or now < self.last_now):
            return self._fail('capture_completion_clock_or_frame_invalid')
        if self.calls > self.max_calls or now - self.baseline['now'] > self.max_seconds:
            return self._fail('capture_completion_transaction_budget_exhausted')
        self.last_now = now
        rows = _rows(text, frame)
        if rows is None or type(overworld_ready) is not bool:
            return self._fail('capture_completion_decoder_proof_required')
        if not _stance(location):
            return self._fail('capture_completion_location_changed')
        for packet in (progress, location, battle_state):
            if not isinstance(packet, dict) or 'observation_frame' in packet and (
                    type(packet['observation_frame']) is not int or packet['observation_frame'] != frame):
                return self._fail('capture_completion_observation_frame_conflict')
        battle = _battle(battle_state)
        if battle is None or battle == 'none' and not self.no_confirmed:
            return self._fail('capture_completion_battle_signal_invalid')
        error = self._progress(progress)
        if error:
            return self._fail(error)
        packet = (rows, deepcopy(progress), deepcopy(location), deepcopy(battle_state),
                  text['window_visible'], overworld_ready, deepcopy(grid))
        if frame == self.last_frame:
            if self.last_packet != packet:
                return self._fail('capture_completion_same_frame_changed_packet')
            return self._wait('same_frame_no_resend')
        self.last_frame, self.last_packet = frame, packet
        if self.stage == 'closing':
            return self._closing(rows, text, progress, battle, grid, frame, overworld_ready)
        if overworld_ready:
            return self._fail('capture_completion_overworld_before_nickname_no')
        if self.pending_page and self._page(rows, self.pending_page) != 'invalid':
            return self._wait('await_next_page_without_resending_previous_confirm')
        # 完全空白只能是已投球後／已知頁面之間的有界動畫，絕不A。
        if not ''.join(rows).strip():
            return self._wait('await_known_capture_transition')
        if self.stage=='dex_first' and rows==_dex_initial_placeholder():
            return self._wait('await_native_dex_owned_details_after_initial_question_marks')
        if self.stage == 'nickname_menu':
            return self._nickname(rows)
        status = self._page(rows, self.stage)
        if status == 'invalid':
            return self._fail('capture_completion_unrecognized_or_polluted_page')
        if status != 'full':
            return self._wait('await_complete_known_capture_page')
        page = self.stage
        self.pending_page, self.stage = page, _NEXT[page]
        return self._hint('a', 'confirm_complete_' + page + '_once')

    def _nickname(self, rows):
        status = self._page(rows, 'nickname_menu', menu=True)
        if status == 'invalid':
            return self._fail('capture_completion_nickname_layout_or_question_invalid')
        if status != 'full':
            return self._wait('await_complete_nickname_question_and_yes_no')
        y = next(y for y, row in enumerate(rows) if '▶' in row)
        if y == 8:
            if self.no_down_pending:
                return self._wait('await_nickname_no_cursor_without_resending_down')
            self.no_down_pending = True
            return self._hint('down', 'move_verified_nickname_yes_cursor_to_no_once')
        if not self.no_down_pending:
            return self._fail('capture_completion_no_cursor_without_requested_move')
        self.no_confirmed, self.stage, self.pending_page = True, 'closing', None
        return self._hint('a', 'confirm_only_verified_nickname_no_once', menu_label='NO')

    @staticmethod
    def _grid_verified(grid, frame):
        if (not isinstance(grid, dict) or type(grid.get('observation_frame')) is not int
                or grid['observation_frame'] != frame or grid.get('verified_location') != [23, 10, 61]
                or not _int(grid.get('screen_cells_verified'), 12, 90)):
            return False
        cells = grid.get('visible_verified_cells')
        return (isinstance(cells, list) and len(cells) == grid['screen_cells_verified']
                and all(isinstance(c, list) and len(c) == 2 and all(_int(v, 0, 255) for v in c) for c in cells)
                and len(set(map(tuple, cells))) == len(cells) and [10, 61] in cells)

    def _closing(self, rows, text, progress, battle, grid, frame, ready):
        # NO後的舊頁可保留或去掉選單，但絕不再A／DOWN。
        nickname = self._page(rows, 'nickname_menu', menu=True)
        if nickname != 'invalid' and any('▶' in row for row in rows):
            if not (rows[10][15] == '▶' and nickname == 'full'):
                return self._fail('capture_completion_nickname_cursor_changed_after_no')
            if ready or battle == 'none':
                return self._fail('capture_completion_closed_signal_conflicts_with_visible_menu')
            self.world_frame = None
            return self._wait('await_menu_close_without_reconfirming_no')
        if any(c in ''.join(rows) for c in '▶▷▼'):
            return self._fail('capture_completion_unknown_closing_menu')
        if ''.join(rows[12:]).strip():
            if self._page(rows, 'nickname_menu') == 'invalid':
                return self._fail('capture_completion_unknown_closing_dialogue')
            if ready:
                return self._fail('capture_completion_world_conflicts_with_dialogue')
            self.world_frame = None
            return self._wait('await_known_nickname_dialogue_close')
        if ready:
            if text['window_visible'] or battle != 'none' or not self._grid_verified(grid, frame):
                return self._fail('capture_completion_overworld_proof_required')
            if re.search(r'[A-ZÉ0-9]', ''.join(rows)):
                return self._fail('capture_completion_unknown_text_in_overworld')
            if (_party(progress) is None or len(progress['party']) != 5
                    or _inventory(progress) != self.after_items):
                self.world_frame = None
                return self._wait('await_full_new_party_and_final_single_ball_deduction')
            if self.world_frame is None:
                self.world_frame = frame
                return self._wait('verify_capture_on_second_distinct_overworld_frame')
            self.stage = 'complete'
            self.completion = {**self._hint('wait', 'capture_complete_after_two_verified_world_frames'),
                'phase': 'capture_completion_complete', 'capture_complete': True,
                'captured_species': 132, 'captured_level': 30, 'original_party_identity_and_order_preserved': True,
                'last_throw_ball_item': self.baseline['ball_item'], 'last_throw_ball_quantity_used': 1,
                'baseline_scope': 'last throw only; earlier throws are excluded',
                'nickname_evidence': 'verified normal NO flow; species_name is not nickname RAM',
                'completion_observation_frame': frame, 'first_world_observation_frame': self.world_frame}
            return deepcopy(self.completion)
        self.world_frame = None
        if ''.join(rows).strip():
            return self._fail('capture_completion_unverified_closing_content')
        return self._wait('await_bounded_battle_exit_or_party_initialization')
