"""固定單件 TM34／TM21／TM46 正常存入玩家 PC 的純候選；不執行按鍵或寫 RAM。

地址由固定公開 WRAM 的 PC 表與既有 D5A6 toggle 表差 108 bytes 推導；
SDK 沒有直接 PC item 常數。reader 的 SDK 指紋／雙讀不能冒充 ROM 身分或
實機校準。caller 必須序列化觀測，提供真 previous，並保留同一 controller。
"""
from copy import deepcopy
import math
import re

from .mart_purchase import _inventory, _party
from .observation import PROFILE as TEXT_PROFILE

SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
SOURCE_ROOT = f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/'
SOURCES = tuple(SOURCE_ROOT + p for p in ('engine/menus/players_pc.asm#L90',
    'engine/menus/pc.asm', 'engine/pokemon/bills_pc.asm#L1', 'home/list_menu.asm#L338',
    'engine/items/inventory.asm', 'data/text/text_2.asm#L1443', 'ram/wram.asm#L1893',
    'engine/overworld/hidden_events.asm#L89', 'data/items/names.asm', 'home/window.asm#L33'))
PROFILE = 'red-en-player-pc-items-source-v1-unvalidated'
INTENT_BASE = {'kind': 'player_pc_deposit', 'map_id': 182, 'player_x': 13,
               'player_y': 4, 'facing': 'up', 'quantity': 1}
LOCATION = {'map_id': 182, 'x': 13, 'y': 4}
# a536711 hidden_events.asm327–330:PC front13,3/UP → 玩家13,4；
# map_constants.asm275 $AB=171。舊金黃意圖與位置常數保留相容。
CINNABAR_TM46_INTENT = {**INTENT_BASE, 'map_id': 171, 'item': 246}
INTENTS = {(182,234): {**INTENT_BASE, 'item':234},
           (182,221): {**INTENT_BASE, 'item':221},
           (171,246): CINNABAR_TM46_INTENT,
           (171,228): {**INTENT_BASE, 'map_id':171, 'item':228},
           (171,206): {**INTENT_BASE, 'map_id':171, 'item':206}}
LOCATIONS = {182: LOCATION, 171: {'map_id':171,'x':13,'y':4}}
MAP_NAMES = {182:'saffron_pokecenter',171:'cinnabar_pokecenter'}


def _intent(intent):
    return (type(intent) is dict and any(intent == fixed and set(intent) == set(fixed)
            and all(type(intent.get(k)) is type(v) for k,v in fixed.items())
            for fixed in INTENTS.values()))

SDK_ANCHORS = {'BAG_ITEM_COUNT_ADDRESS': 0xD31D, 'BAG_ITEMS_ADDRESS': 0xD31E,
               'BAG_ITEM_CAPACITY': 20, 'STATUS_FLAGS3_ADDRESS': 0xD72D,
               'OBTAINED_BADGES_ADDRESS': 0xD356, 'EVENT_FLAGS_ADDRESS': 0xD747}
PC_COUNT, PC_ITEMS = 0xD53A, 0xD53B
_ITEM_NAMES = ('MASTER BALL|ULTRA BALL|GREAT BALL|POKé BALL|TOWN MAP|BICYCLE|?????|'
    'SAFARI BALL|POKéDEX|MOON STONE|ANTIDOTE|BURN HEAL|ICE HEAL|AWAKENING|PARLYZ HEAL|'
    'FULL RESTORE|MAX POTION|HYPER POTION|SUPER POTION|POTION|BOULDERBADGE|CASCADEBADGE|'
    'THUNDERBADGE|RAINBOWBADGE|SOULBADGE|MARSHBADGE|VOLCANOBADGE|EARTHBADGE|ESCAPE ROPE|'
    'REPEL|OLD AMBER|FIRE STONE|THUNDERSTONE|WATER STONE|HP UP|PROTEIN|IRON|CARBOS|'
    'CALCIUM|RARE CANDY|DOME FOSSIL|HELIX FOSSIL|SECRET KEY|?????|BIKE VOUCHER|'
    'X ACCURACY|LEAF STONE|CARD KEY|NUGGET|PP UP|POKé DOLL|FULL HEAL|REVIVE|MAX REVIVE|'
    'GUARD SPEC.|SUPER REPEL|MAX REPEL|DIRE HIT|COIN|FRESH WATER|SODA POP|LEMONADE|'
    "S.S.TICKET|GOLD TEETH|X ATTACK|X DEFEND|X SPEED|X SPECIAL|COIN CASE|OAK's PARCEL|"
    'ITEMFINDER|SILPH SCOPE|POKé FLUTE|LIFT KEY|EXP.ALL|OLD ROD|GOOD ROD|SUPER ROD|'
    'PP UP|ETHER|MAX ETHER|ELIXER|MAX ELIXER').split('|')
_KEY_ITEMS = {5, 6, 7, 8, 9, *range(21, 29), 31, 41, 42, 43, 44, 45, 48,
              63, 64, *range(69, 75), 76, 77, 78, *range(196, 201)}
_MAIN = ("BILL's PC", "KEVIN's PC", "PROF.OAK's PC", 'LOG OFF')
_PLAYER = ('WITHDRAW ITEM', 'DEPOSIT ITEM', 'TOSS ITEM', 'LOG OFF')


def _int(v, low=0, high=0x7fffffffffffffff):
    return type(v) is int and low <= v <= high


def _items(items, capacity):
    return (type(items) is list and len(items) <= capacity
            and all(type(i) is dict and set(i) == {'item', 'quantity'}
                    and _int(i['item'], 1, 250) and _name(i['item']) not in (None, '?????')
                    and _int(i['quantity'], 1, 99) for i in items)
            and len({i['item'] for i in items}) == len(items))


def read_player_pc(pyboy, *, observation_frame, expected_location, constants, profile=PROFILE):
    """只 getter：完整 50-slot 表、位置／朝向同幀雙讀；未知不當空 PC。"""
    result = {'profile': profile, 'source_commit': SOURCE_COMMIT, 'read_valid': False,
              'read_error': 'pc_source_anchor_or_observation_unverified', 'items': None,
              'count': None, 'live_calibrated': False}
    if (profile != PROFILE or not _int(observation_frame)
            or type(expected_location) is not dict or expected_location not in LOCATIONS.values()
            or any(type(v) is not int for v in expected_location.values())
            or any(type(getattr(constants, k, None)) is not int or getattr(constants, k) != v
                   for k, v in SDK_ANCHORS.items())
            or not isinstance(getattr(constants, 'MAPS', None), dict)
            or type(constants.MAPS.get(MAP_NAMES[expected_location['map_id']])) is not int
            or constants.MAPS[MAP_NAMES[expected_location['map_id']]] != expected_location['map_id']):
        return result
    addresses = (0xD35E, 0xD361, 0xD362, 0xC109, *range(PC_COUNT, PC_ITEMS + 101))
    try:
        before = pyboy.frame_count
        first = tuple(pyboy.memory[a] for a in addresses)
        second = tuple(pyboy.memory[a] for a in addresses)
        after = pyboy.frame_count
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, RuntimeError, OSError):
        return {**result, 'read_error': 'pc_getter_failed'}
    if (not _int(before) or not _int(after) or before != observation_frame or after != before
            or first != second or any(not _int(v, 0, 255) for v in first + second)):
        return {**result, 'read_error': 'pc_read_torn_or_frame_changed'}
    mid, y, x, facing, count, *table = first
    if {'map_id': mid, 'x': x, 'y': y} != expected_location or facing != 4:
        return {**result, 'read_error': 'pc_stance_disagrees'}
    if count > 50 or table[count * 2] != 255:
        return {**result, 'read_error': 'pc_table_count_or_terminator_invalid'}
    items = [{'item': table[i * 2], 'quantity': table[i * 2 + 1]} for i in range(count)]
    if not _items(items, 50):
        return {**result, 'read_error': 'pc_table_items_invalid'}
    return {**result, 'read_valid': True, 'read_error': None, 'items': items, 'count': count,
            'observation_frame': observation_frame, 'location': deepcopy(expected_location),
            'facing': 'up', 'facing_raw': 4}


def _canvas():
    return [[' '] * 20 for _ in range(18)]


def _tokens(value):
    # Gen1 原生 's 是一個 tile；不把物理座標因多字縮寫展開。
    return value.upper().replace("'S", '\ue000')


def _put(cells, x, y, value):
    chars = list(_tokens(value))
    cells[y][x:x + len(chars)] = chars


def _rows(text, frame):
    if (not isinstance(text, dict) or text.get('profile') != TEXT_PROFILE
            or text.get('read_valid') is not True or text.get('alignment_verified') is not True
            or text.get('read_error') is not None or type(text.get('window_visible')) is not bool
            or type(text.get('cells')) is not list or len(text['cells']) != 18):
        return None
    projected = [(''.join(row).rstrip(), y) for y, row in enumerate(text['cells'])
                 if type(row) is list and all(type(c) is str for c in row)]
    visible = [(line, y) for line, y in projected if re.search(r'[A-Za-z0-9]{2,}', line)][:12]
    if (text.get('lines') != [line for line, _ in visible]
            or text.get('line_rows') != [y for _, y in visible]):
        return None
    rows = []
    for row in text['cells']:
        if type(row) is not list or len(row) != 20:
            return None
        out = []
        for c in row:
            if type(c) is not str or c == '\ue000' or (len(c) != 1 and c != "'s"):
                return None
            out.append(_tokens(c))
        rows.append(out)
    return rows


def _body(cells, first, second='', arrow=False):
    result = deepcopy(cells)
    for y in range(12, 18): result[y] = [' '] * 20
    _put(result, 1, 14, first); _put(result, 1, 16, second)
    if arrow: result[16][18] = '▼'
    return result


def _menu(labels, cursor):
    result = _canvas()
    for i, label in enumerate(labels): _put(result, 2, 2 + i * 2, label)
    result[cursor][1] = '▶'
    return result


def _name(item):
    if 1 <= item <= len(_ITEM_NAMES): return _ITEM_NAMES[item - 1]
    if 196 <= item <= 200: return f'HM{item - 195:02d}'
    if 201 <= item <= 250: return f'TM{item - 200:02d}'
    return None


def _bag(bag, offset, cursor, marker='▶'):
    """來源玩家 PC 殘留左欄＋四列名稱（末列只預覽）＋固定捲動箭頭。"""
    result = _canvas()
    for i, label in enumerate(_PLAYER): _put(result, 2, 2 + i * 2, label[:2])
    result[4][1] = '▷'
    printed = 0
    for n in range(4):
        index, y = offset + n, 4 + n * 2
        if index == len(bag):
            _put(result, 6, y, 'CANCEL'); break
        if index > len(bag): break
        item = bag[index]; name = _name(item['item'])
        if name is None: return None
        _put(result, 6, y, name)
        if item['item'] not in _KEY_ITEMS: _put(result, 14, y + 1, f"×{item['quantity']:2}")
        printed += 1
    if printed == 4: result[11][18] = '▼'
    result[4 + cursor * 2][5] = marker
    return _body(result, 'What do you want', 'to deposit?')


def _quantity(selected):
    result = deepcopy(selected)
    for y in range(9, 12):
        for x in range(15, 20): result[y][x] = ' '
    _put(result, 16, 10, '×01')
    return _body(result, 'How many?')


def _bag_matches(rows, expected):
    # HandleMenuInput 在固定 (18,11) 呼叫 HandleDownArrowBlinkTiming；
    # 只容許來源已放置的捲動提示 ▼ 暫時變空白，絕不省略活游標或其他格。
    return (expected is not None and all(
        rows[y][x] == expected[y][x]
        or (x == 18 and y == 11 and expected[y][x] == '▼' and rows[y][x] == ' ')
        for y in range(18) for x in range(20)))


class PlayerPCDepositController:
    """固定 TM 單件存物；所有候選須真 previous／新幀回執才轉階。"""
    def __init__(self, intent):
        if not _intent(intent):
            raise ValueError('僅金黃中心TM34/TM21或紅蓮中心TM46，13,4朝UP單件存物')
        self.intent = deepcopy(intent); self.contract = deepcopy(intent)
        self.stage = 'initial'; self.error = None; self.baseline = None
        self.started = None; self.last_now = None; self.last_frame = -1; self.last_packet = None
        self.pending = None; self.expected_selection = None; self.selected_bag = None
        self.calls = self.waits = self.actions = self.scrolls = 0
        self.transferred = self.receipt_seen = False; self.closed_frames = []

    def _hint(self, action, reason, complete=False):
        return {'phase': 'player_pc_deposit', 'objective': {'wait': 'Wait.', 'a': 'Press A.',
                'b': 'Press B.', 'up': 'Move UP.', 'down': 'Move DOWN.'}[action],
                'available_actions': ['wait'] if action == 'wait' else [action, 'wait'],
                'controller_menu_verified': action != 'wait', 'pc_deposit_complete': complete,
                'player_pc_stage': self.stage, 'player_pc_tactic': reason, 'item': self.contract['item'],
                'source_commit': SOURCE_COMMIT, 'sources': SOURCES}

    def _fail(self, reason):
        self.error = self.error or 'player_pc_deposit_' + reason
        return {**self._hint('wait', 'review'), 'phase': 'campaign_review', 'review_reason': self.error}

    def _wait(self, reason):
        self.waits += 1
        return self._fail('wait_budget_exhausted') if self.waits > 120 else self._hint('wait', reason)

    def _offer(self, action, next_stage, rows, selection=None):
        self.actions += 1
        if self.actions > 80: return self._fail('action_budget_exhausted')
        self.pending = {'action': action, 'next': next_stage, 'rows': deepcopy(rows),
                        'frame': self.last_frame, 'executed': False, 'selection': selection}
        return self._hint(action, next_stage)

    def _selection(self, kind, index):
        if self.expected_selection is not None and self.expected_selection != (kind, index):
            return False
        self.expected_selection = None
        return True

    def _printing(self, rows, upper, first, second=''):
        a, b = ''.join(rows[14][1:19]).rstrip(), ''.join(rows[16][1:19]).rstrip()
        clean = deepcopy(rows)
        for y in range(12, 18): clean[y] = [' '] * 20
        if (clean == _body(upper, '', '') and not any(c in '▶▷▼' for row in rows[12:] for c in row)
                and _tokens(first).startswith(a) and (not b or a == _tokens(first) and _tokens(second).startswith(b))):
            return True
        return False

    def _prompt(self, rows, upper, first, second, next_stage):
        full = _body(upper, first, second, True)
        if rows == full: return self._offer('a', next_stage, rows)
        if self._printing(rows, upper, first, second):
            return self._wait('known_text_printing_or_prompt_blink')
        return self._fail('unknown_or_polluted_prompt')

    def context(self, text, progress, *, location, battle_state, pc_signal, frame, previous,
                now, overworld_ready=False):
        """same-frame 同包只 WAIT；初次須 closed，兩件存物應分別重新建構。"""
        if self.error: return self._fail('sticky')
        if (self.intent != self.contract or any(type(self.intent.get(k)) is not int
                for k in ('map_id', 'player_x', 'player_y', 'quantity', 'item'))):
            return self._fail('intent_changed')
        if (not _int(frame) or type(now) not in (int, float) or not math.isfinite(now) or now < 0
                or frame < self.last_frame or self.last_now is not None and now < self.last_now):
            return self._fail('clock_or_frame_unverified')
        if self.started is None: self.started = now
        self.last_now = now; self.calls += 1
        if self.calls > 240 or now - self.started > 60: return self._fail('budget_exhausted')
        if (type(overworld_ready) is not bool or type(location) is not dict or location != LOCATIONS.get(self.contract['map_id'])
                or any(type(v) is not int for v in location.values())
                or type(previous) not in (list, tuple) or any(a not in ('a', 'b', 'up', 'down', 'left', 'right', 'start', 'wait')
                                                           or type(a) is not str for a in previous)):
            return self._fail('stance_or_actual_history_unverified')
        if (not isinstance(battle_state, dict) or battle_state.get('active') is not False
                or battle_state.get('kind') != 'none' or type(battle_state.get('raw')) is not int
                or battle_state['raw'] != 0 or type(battle_state.get('observation_frame')) is not int
                or battle_state['observation_frame'] != frame): return self._fail('battle_not_none')
        for p in (text, progress, pc_signal):
            if isinstance(p, dict) and 'observation_frame' in p and (not _int(p['observation_frame']) or p['observation_frame'] != frame):
                return self._fail('observation_frame_disagrees')
        signal = pc_signal
        if (not isinstance(signal, dict) or signal.get('profile') != PROFILE or signal.get('read_valid') is not True
                or signal.get('source_commit') != SOURCE_COMMIT or signal.get('read_error') is not None
                or type(signal.get('observation_frame')) is not int or signal['observation_frame'] != frame
                or signal.get('location') != location or signal.get('facing') != 'up'
                or type(signal.get('facing_raw')) is not int or signal['facing_raw'] != 4
                or not _items(signal.get('items'), 50) or not _int(signal.get('count'), 0, 50)
                or signal['count'] != len(signal['items'])): return self._fail('pc_snapshot_unverified')
        party = _party(progress); bag = _inventory(progress.get('inventory')) if isinstance(progress, dict) else None
        if (party is None or len(party) != 6 or any(m['hp'] <= 0 or m['status'] not in (*range(8), 8, 16, 32, 64) for m in party)
                or bag is None or not _items(bag, 20)
                or not _int(progress.get('money'), 0, 999999)): return self._fail('progress_unverified')
        rows = _rows(text, frame)
        if rows is None: return self._fail('decoder_unverified')
        packet = deepcopy((text, progress, location, battle_state, pc_signal, previous, overworld_ready))
        if frame == self.last_frame:
            return self._fail('same_frame_conflict') if packet != self.last_packet else self._wait('same_frame_no_resend')
        self.last_frame, self.last_packet = frame, packet
        item = self.contract['item']
        if self.baseline is None:
            if (not overworld_ready or text['window_visible'] is not False or rows != _canvas()
                    or [i for i in bag if i['item'] == item] != [{'item': item, 'quantity': 1}]):
                return self._fail('initial_closed_or_item_unverified')
            pc_after = deepcopy(signal['items']); match = next((i for i in pc_after if i['item'] == item), None)
            if match:
                if match['quantity'] >= 99: return self._fail('pc_stack_has_no_reserved_capacity')
                match['quantity'] += 1
            elif len(pc_after) >= 50: return self._fail('pc_has_no_reserved_slot')
            else: pc_after.append({'item': item, 'quantity': 1})
            self.baseline = deepcopy({'party': party, 'bag': bag, 'pc': signal['items'], 'money': progress['money'],
                'bag_after': [i for i in bag if i['item'] != item], 'pc_after': pc_after})
            return self._offer('a', 'opening', rows)
        base = self.baseline
        if party != base['party'] or progress['money'] != base['money']: return self._fail('party_or_money_changed')
        retry = None
        if self.pending and not self.pending['executed']:
            if previous and previous[-1] == self.pending['action']:
                self.pending['executed'] = True; self.stage = self.pending['next']
                self.expected_selection = self.pending['selection']
            elif rows == self.pending['rows']:
                retry = self.pending
            else: return self._fail('changed_page_without_actual_action')
        allow_transfer = self.stage in ('receipt', 'after_receipt', 'exit_player', 'exit_main', 'closing', 'complete')
        ledger = (bag, signal['items'])
        allowed = [(base['bag'], base['pc'])]
        if allow_transfer: allowed += [(base['bag'], base['pc_after']), (base['bag_after'], base['pc_after'])]
        if ledger not in allowed or self.transferred and ledger != (base['bag_after'], base['pc_after']):
            return self._fail('inventory_conservation_failed')
        if ledger == (base['bag_after'], base['pc_after']): self.transferred = True
        if retry:
            return self._offer(retry['action'], retry['next'], rows, retry['selection'])
        if self.pending:
            if rows == self.pending['rows']: return self._wait('await_actual_action_effect')
            self.pending = None
        if self.stage in ('closing', 'complete'):
            if (rows != _canvas() or text['window_visible'] is not False or not overworld_ready):
                self.closed_frames.clear(); return self._fail('closed_world_unverified')
            if not self.transferred or not self.receipt_seen: return self._fail('missing_transfer_or_receipt')
            self.closed_frames.append(frame)
            if len(self.closed_frames) < 2: return self._wait('verify_second_closed_frame')
            self.stage = 'complete'; return self._hint('wait', 'verified_single_item_deposit', True)
        if text['window_visible'] is not True: return self._fail('open_pc_window_unverified')
        if self.stage == 'opening': return self._prompt(rows, _canvas(), 'KEVIN turned on', 'the PC.', 'main')
        if self.stage in ('main', 'exit_main'):
            for row in (2, 4, 6, 8):
                if rows == _menu(_MAIN, row):
                    if not self._selection('main', row): return self._fail('main_cursor_jump')
                    if self.stage == 'exit_main': return self._offer('b', 'closing', rows)
                    if row == 4: return self._offer('a', 'access_first', rows)
                    key = 'down' if row < 4 else 'up'
                    return self._offer(key, 'main', rows, ('main', row + (2 if key == 'down' else -2)))
            return self._fail('main_pc_menu_unverified')
        if self.stage == 'access_first': return self._prompt(rows, _menu(_MAIN, 4), 'Accessed my PC.', '', 'access_second')
        if self.stage == 'access_second': return self._prompt(rows, _menu(_MAIN, 4), 'Accessed Item', 'Storage System.', 'player')
        if self.stage in ('player', 'exit_player'):
            if self.stage == 'exit_player' and self.transferred and self.receipt_seen:
                drawing = _menu(_PLAYER, 2)
                drawing[2][1] = ' '
                if self._printing(rows, drawing, 'What do you want', 'to do?'):
                    return self._wait('player_menu_footer_before_active_cursor')
            for row in (2, 4, 6, 8):
                expected = _body(_menu(_PLAYER, row), 'What do you want', 'to do?')
                if rows == expected:
                    if not self._selection('player', row): return self._fail('player_cursor_jump')
                    if self.stage == 'exit_player': return self._offer('b', 'exit_main', rows)
                    if row == 4: return self._offer('a', 'bag', rows)
                    key = 'down' if row < 4 else 'up'
                    return self._offer(key, 'player', rows, ('player', row + (2 if key == 'down' else -2)))
            return self._fail('player_menu_or_deposit_label_unverified')
        if self.stage in ('bag', 'after_receipt'):
            # 原生 .loop 先重印 footer，後重畫清單；此時仍留已驗舊 ▷/×01。
            # 只能等待，不以已移除的舊道具列作新的確認或提早 B。
            if (self.stage == 'after_receipt' and self.transferred and self.receipt_seen
                    and self.selected_bag is not None
                    and self._printing(rows, _quantity(self.selected_bag),
                                       'What do you want', 'to deposit?')):
                return self._wait('stored_receipt_acknowledged_await_fresh_bag')
            current_bag = base['bag_after'] if self.stage == 'after_receipt' else base['bag']
            for offset in range(max(1, len(current_bag) - 1)):
                for cursor in range(3):
                    if offset + cursor > len(current_bag): continue
                    if not _bag_matches(rows, _bag(current_bag, offset, cursor)): continue
                    index = offset + cursor
                    if not self._selection('bag', index): return self._fail('bag_cursor_or_scroll_jump')
                    if self.stage == 'after_receipt': return self._offer('b', 'exit_player', rows)
                    target = next(i for i, v in enumerate(current_bag) if v['item'] == item)
                    if index == target:
                        self.selected_bag = _bag(current_bag, offset, cursor, '▷')
                        return self._offer('a', 'quantity', rows)
                    self.scrolls += 1
                    if self.scrolls > 20: return self._fail('bag_navigation_budget_exhausted')
                    key = 'down' if index < target else 'up'
                    return self._offer(key, 'bag', rows, ('bag', index + (1 if key == 'down' else -1)))
            return self._fail('bag_viewport_or_quantity_unverified')
        if self.stage == 'quantity':
            if rows == _quantity(self.selected_bag): return self._offer('a', 'receipt', rows)
            if self._printing(rows, self.selected_bag, 'How many?'):
                return self._wait('quantity_prompt_printing_without_confirm')
            return self._fail('quantity_01_or_selected_item_unverified')
        if self.stage == 'receipt':
            upper = _quantity(self.selected_bag)
            full = _body(upper, f'{_name(item)} was', 'stored via PC.', True)
            if rows == full:
                if not self.transferred: return self._fail('stored_receipt_without_actual_transfer')
                self.receipt_seen = True
                return self._offer('a', 'after_receipt', rows)
            return self._prompt(rows, upper, f'{_name(item)} was', 'stored via PC.', 'after_receipt')
        return self._fail('unknown_stage')
