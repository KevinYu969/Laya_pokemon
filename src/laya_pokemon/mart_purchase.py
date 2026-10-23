"""紫苑商店正常買20顆超級球的純候選；不讀遊戲檔／RAM或呼叫遊戲／模型。

只接受固定stance與完整同幀decoder/progress。來源版面來自固定pret/pokered，
尚未實機校準。每次只回Laya子目標；呼叫端必須重新觀測，不可批次發按鍵。
"""
from copy import deepcopy
import math
import re

from .observation import PROFILE as TEXT_PROFILE
from .party_control import command
from .team_strategy import normalize, species_key

SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
SOURCE_ROOT = f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/'
SOURCES = [SOURCE_ROOT + p for p in ('data/items/marts.asm', 'data/items/prices.asm',
    'data/maps/objects/LavenderMart.asm', 'home/list_menu.asm', 'engine/events/pokemart.asm',
    'engine/menus/text_box.asm', 'data/text/text_4.asm', 'engine/items/inventory.asm')]
INTENT = {'kind': 'buy_lavender_great_balls', 'map_id': 150, 'player_x': 2, 'player_y': 5,
          'facing': 'left', 'item': 3, 'quantity': 20, 'unit_price': 600,
          'total_price': 12000, 'minimum_remaining_money': 5000}
_PROGRESS = 'gen1-wrapper-ram-progress-v1-unvalidated'
_MAIN = {'BUY': (2, 1), 'SELL': (2, 3), 'QUIT': (2, 5)}
_GOODS = {'GREAT BALL': (6, 4), 'SUPER POTION': (6, 6),
          'REVIVE': (6, 8), 'ESCAPE ROPE': (6, 10)}
_YESNO = {'YES': (16, 8), 'NO': (16, 10)}
_SELECTED = {(1, 1, '▷'), (5, 4, '▷')}
_GREETING, _BUYING = 'HITHERE!MAYIHELPYOU?', 'TAKEYOURTIME.'
_PREFIX, _TAIL = 'GREATBALL?THATWILLBE', 'THATWILLBE¥12000.OK?'
_BOUGHT, _ELSE, _THANKS = 'HEREYOUARE!THANKYOU!', 'ISTHEREANYTHINGELSEICANDO?', 'THANKYOU!'


def _compact(value):
    return re.sub(r'\s+', '', value.upper().replace('É', 'E'))


def _rows(text):
    cells = text.get('cells') if isinstance(text, dict) else None
    if (not isinstance(cells, (list, tuple)) or len(cells) != 18
            or any(not isinstance(r, (list, tuple)) or len(r) != 20
                   or any(not isinstance(c, str) or len(c) != 1 for c in r) for r in cells)):
        return None
    rows = tuple(''.join(r).upper() for r in cells)
    return rows if all(len(row) == 20 for row in rows) else None


def _positions(rows, word):
    return [(m.start(), y) for y, row in enumerate(rows)
            for m in re.finditer(r'(?<![A-ZÉ0-9])' + re.escape(word) + r'(?![A-ZÉ0-9])', row)]


def _labels(rows, expected):
    return all(_positions(rows, word) == [position] for word, position in expected.items())


def _partial_labels(rows, expected):
    return all(_positions(rows, word) in ([], [position])
               and word.startswith(rows[position[1]][position[0]:19].strip())
               for word, position in expected.items())


def _marks(rows):
    return {(x, y, c) for y, row in enumerate(rows) for x, c in enumerate(row) if c in '▶▷▼'}


def _lower(rows):
    # Letters on border/in-between rows are not silently discarded as dialogue.
    if any(re.search(r'[A-ZÉ0-9¥!?]', rows[y]) for y in (12, 13, 15, 17)):
        return None
    if any(re.search(r'[A-ZÉ0-9¥!?]', rows[y][x]) for y in (14, 16) for x in (0, 19)):
        return None
    return _compact(rows[14][1:19].replace('▼', '') + rows[16][1:19].replace('▼', ''))


def _inventory(value):
    if (not isinstance(value, list) or len(value) > 20
            or any(not isinstance(i, dict) or set(i) != {'item', 'quantity'}
                   or type(i['item']) is not int or not 1 <= i['item'] <= 250
                   or type(i['quantity']) is not int or not 1 <= i['quantity'] <= 99 for i in value)):
        return None
    return value if len({i['item'] for i in value}) == len(value) else None


def _party(progress):
    if (not isinstance(progress, dict) or progress.get('profile') != _PROGRESS
            or progress.get('initialization_candidate') is not True
            or progress.get('party_read_valid') is not True):
        return None
    party = progress.get('party')
    if (not isinstance(party, list) or type(progress.get('party_count')) is not int
            or not 1 <= len(party) <= 6 or progress['party_count'] != len(party)):
        return None
    for mon in party:
        if (not isinstance(mon, dict) or type(mon.get('species')) is not int
                or species_key(mon['species']) is None
                or not isinstance(mon.get('species_name'), str)
                or normalize(mon['species_name']) != normalize(species_key(mon['species']))
                or any(type(mon.get(k)) is not int for k in ('level', 'exp', 'hp', 'max_hp', 'status'))
                or not 1 <= mon['level'] <= 100 or not 0 <= mon['exp'] <= 0xFFFFFF
                or not 1 <= mon['max_hp'] <= 999 or not 0 <= mon['hp'] <= mon['max_hp']
                or not 0 <= mon['status'] <= 255
                or any(not isinstance(mon.get(k), list) or len(mon[k]) != 4
                       or any(type(n) is not int or not 0 <= n <= high for n in mon[k])
                       for k, high in (('moves', 165), ('pp', 255)))):
            return None
    return party


def purchase_expectation(progress):
    """純預期差異；不能用這個計算結果冒充真的購買完成。"""
    if _party(progress) is None or _inventory(progress.get('inventory')) is None:
        return None
    money = progress.get('money')
    if type(money) is not int or not 17000 <= money <= 999999:
        return None
    items = deepcopy(progress['inventory'])
    existing = next((i for i in items if i['item'] == 3), None)
    if existing is None:
        if len(items) >= 20:
            return None
        items.append({'item': 3, 'quantity': 20})
    elif existing['quantity'] > 79:
        return None
    else:
        existing['quantity'] += 20
    return {'inventory': items, 'money': money - 12000, 'party': deepcopy(progress['party'])}


def _money_field(value):
    return f'¥{value}'.rjust(7)


def _money(rows, value):
    return _positions(rows, 'MONEY') == [(13, 0)] and rows[1][12:19] == _money_field(value)


def _main(rows, value, *, active=True):
    mark = '▶' if active else '▷'
    return (_labels(rows, _MAIN) and _money(rows, value)
            and all(rows[y][x:10].strip() == word for word, (x, y) in _MAIN.items())
            and _marks(rows) == {(1, 1, mark)})


def _shop(rows, value):
    return (_underlay(rows) and _labels(rows[:12], _GOODS) and _money(rows, value)
            and all(rows[y][11:18] == _money_field(price)
                    for y, price in ((5, 600), (7, 700), (9, 1500), (11, 550)))
            and _marks(rows) in ({(1, 1, '▷'), (5, 4, '▶')},
                                 {(1, 1, '▷'), (5, 4, '▶'), (18, 11, '▼')}))


def _underlay(rows):
    # ListMenu clears only x4..19,y2..12: BUY and its unfilled main cursor remain.
    return (_positions(rows[:12], 'BUY') == [(2, 1)] and rows[1][2:10].strip() == 'BUY'
            and rows[3][2:4] == 'SE' and rows[5][2:4] == 'QU')


def _selected_good(rows, value):
    return (_underlay(rows) and _positions(rows[:12], 'GREAT BALL') == [(6, 4)] and rows[4][6:16] == 'GREAT BALL'
            and rows[5][11:18] == _money_field(600) and _money(rows, value))


def _view(layout, value, *, quantity=20, price=None, dialogue='buying'):
    """Source-derived font mask, including remnants of each overwritten rectangle.

    Border/control tiles are filtered to spaces by the existing decoder. A mask
    permits only an expected character or blank (typing); full parsers still
    require complete labels/amounts/cursors before any button recommendation.
    """
    cells = [[' '] * 20 for _ in range(18)]
    def put(x, y, word):
        cells[y][x:x + len(word)] = list(word)
    def clear(x1, y1, x2, y2):
        for y in range(y1, y2 + 1):
            cells[y][x1:x2 + 1] = [' '] * (x2 - x1 + 1)
    for label, (x, y) in _MAIN.items():
        put(x, y, label)
    put(13, 0, 'MONEY'); put(12, 1, _money_field(value))
    allowed = {(1, 1, '▶'), (1, 1, '▷')}
    if layout != 'main':
        clear(4, 2, 19, 12)
        for label, (x, y) in _GOODS.items():
            put(x, y, label)
        for y, cost in ((5, 600), (7, 700), (9, 1500), (11, 550)):
            put(11, y, _money_field(cost))
        allowed = {(1, 1, '▷'), (5, 4, '▶'), (5, 4, '▷'), (18, 11, '▼')}
    if layout in ('quantity', 'yesno'):
        clear(7, 9, 19, 11)
        put(8, 10, f'×{quantity:02}')
        put(12, 10, _money_field(quantity * 600 if price is None else price))
        allowed = set(_SELECTED)
    if layout == 'yesno':
        clear(14, 7, 19, 11)
        for label, (x, y) in _YESNO.items():
            put(x, y, label)
        allowed |= {(15, 8, '▶'), (15, 10, '▶')}
    first, second = {'greeting': ('HI THERE!', 'MAY I HELP YOU?'),
                     'buying': ('TAKE YOUR TIME.', ''),
                     'prefix': ('GREAT BALL?', 'THAT WILL BE'),
                     'tail': ('THAT WILL BE', '¥12000. OK?'),
                     'bought': ('HERE YOU ARE!', 'THANK YOU!'),
                     'else': ('IS THERE ANYTHING', 'ELSE I CAN DO?'),
                     'thanks': ('THANK YOU!', '')}[dialogue]
    clear(0, 12, 19, 17); put(1, 14, first); put(1, 16, second)
    if dialogue in ('prefix', 'bought'):
        allowed.add((18, 16, '▼'))
    return tuple(''.join(row) for row in cells), allowed


def _matches_view(rows, template, *, partial=True):
    expected, allowed = template
    return all((x, y, c) in allowed if c in '▶▷▼' else
               c == expected[y][x] or partial and c == ' '
               for y, row in enumerate(rows) for x, c in enumerate(row))


class MartPurchaseController:
    """唯一意圖20球；未知鎖review，完成也鎖存。沒有遊戲IO或直接按鍵。

    物種核對沿用species_key及其快取的公開封裝reference JSON；不讀ROM或存檔。

    context(text, progress, *, location, battle_state, frame, now,
            overworld_ready=False, intent=None) -> Laya subgoal.
    frame/now必須由呼叫端同次觀測提供；可選observation_frame若存在必須相同。
    預設上限60秒／240calls／120waits，可縮小不可放大。
    """

    def __init__(self, intent, *, max_calls=240, max_seconds=60, max_waits=120):
        if (not isinstance(intent, dict) or intent != INTENT
                or any(type(intent[k]) is not int for k in INTENT if type(INTENT[k]) is int)):
            raise ValueError('只允許紫苑150(2,5)left正常買20顆Great Ball3，每顆600並保留5000')
        if (type(max_calls) is not int or not 1 <= max_calls <= 240
                or type(max_waits) is not int or not 1 <= max_waits <= 240
                or type(max_seconds) not in (int, float) or not math.isfinite(max_seconds)
                or not 0 < max_seconds <= 60):
            raise ValueError('上限240calls／240waits／60秒，可縮小不可擴大')
        self.intent, self._contract = deepcopy(intent), deepcopy(INTENT)
        self.max_calls, self.max_seconds, self.max_waits = max_calls, max_seconds, max_waits
        self.calls = self.waits = 0
        self.stage, self.error, self.complete = 'initial', None, False
        self.started_at = self.last_time = self.last_frame = self.last_packet = None
        self.pending_rows = self.initial_world_rows = None
        self.party_before = self.inventory_before = self.money_before = self.expected = None
        self.quantity_last = 0
        self.quantity_confirmed = self.prefix_seen = self.prefix_advanced = self.yes_confirmed = False
        self.purchase_observed = self.bought_receipt_seen = self.exit_text_seen = False
        self.world_stable_frame = None

    def _hint(self, action, tactic):
        extra = {'mart_purchase_controller': 'lavender_great_ball20_candidate',
                 'mart_purchase_stage': self.stage, 'mart_purchase_tactic': tactic,
                 'source_commit': SOURCE_COMMIT, 'sources': SOURCES}
        if action == 'wait':
            return {'phase': 'mart_menu', 'objective': 'Wait.', 'available_actions': ['wait'],
                    'controller_menu_verified': True, **extra}
        return command(action, 'mart_menu', extra)

    def _fail(self, reason):
        self.error = reason
        return {**self._hint('wait', 'stop_for_review'), 'phase': 'campaign_review',
                'controller_menu_verified': False, 'review_reason': reason}

    def _wait(self, reason):
        self.waits += 1
        return (self._fail('mart_wait_budget_exhausted') if self.waits > self.max_waits
                else self._hint('wait', reason))

    def _send(self, action, rows, stage, tactic, *, flags=()):
        if not self._action_guard(rows, tactic):
            return self._fail('mart_action_requires_complete_source_ui')
        self.pending_rows, self.stage = rows, stage
        for flag in flags:
            setattr(self, flag, True)
        return self._hint(action, tactic)

    def _done(self):
        self.complete, self.stage = True, 'complete'
        return {**self._hint('wait', 'purchase_complete_observed'), 'phase': 'mart_complete',
                'mart_purchase_complete': True, 'item': 3, 'quantity_purchased': 20,
                'money_spent': 12000, 'money_after': self.expected['money'],
                'party_and_other_inventory_unchanged': True, 'receipt_observation_frame': self.last_frame,
                'evidence_scope': 'latched completed transaction; later calls do not revalidate new packets'}

    def _action_guard(self, rows, tactic):
        if self.stage == 'initial':
            return all(c == ' ' for row in rows for c in row)
        value = self.money_before if self.stage in ('opening', 'buy_open', 'quantity', 'price_text') else self.expected['money']
        layout, dialogue, number = {
            'opening': ('main', 'greeting', 20),
            'buy_open': ('shop', 'buying', 20),
            'quantity': ('quantity', 'buying', self.quantity_last),
            'price_text': ('quantity' if tactic == 'advance_verified_item_and_price_prefix' else 'yesno',
                           'prefix' if tactic == 'advance_verified_item_and_price_prefix' else 'tail', 20),
            'purchase_ack': ('quantity', 'bought', 20),
            'post_receipt': ('shop', 'buying', 20),
            'return_main': ('main', 'else', 20),
            'closing_text': ('main', 'thanks', 20),
        }[self.stage]
        return _matches_view(rows, _view(layout, value, quantity=number, dialogue=dialogue), partial=False)

    def _ui_guard(self, rows, money):
        if self.stage == 'initial':
            return all(c == ' ' for row in rows for c in row)
        if self.stage == 'exit_wait':
            return rows == self.initial_world_rows or _matches_view(rows, _view('main', money, dialogue='thanks'))
        choices = []
        def add(layout, *, dialogue='buying', quantity=20, price=None, value=money):
            choices.append(_view(layout, value, dialogue=dialogue, quantity=quantity, price=price))
        if self.stage == 'opening':
            add('main', dialogue='greeting')
        elif self.stage == 'buy_open':
            add('main', dialogue='greeting'); add('main'); add('shop')
        elif self.stage == 'quantity':
            old, target = self.quantity_last, self.quantity_last + 1 if self.quantity_last else 1
            for number in ({old, target} - {0}):
                for price in ({old * 600, target * 600} - {0}):
                    add('quantity', quantity=number, price=price)
        elif self.stage == 'price_text':
            add('quantity')
            add('quantity', dialogue='prefix'); add('quantity', dialogue='tail')
            add('yesno', dialogue='tail')
        elif self.stage == 'purchase_ack':
            # Source can update inventory, then money, then redraw the box before
            # printing the receipt. Old confirmation/old money may only WAIT.
            for value in {self.money_before, self.expected['money']}:
                add('yesno', dialogue='tail', value=value)
                add('quantity', dialogue='bought', value=value)
        elif self.stage == 'post_receipt':
            add('quantity', dialogue='bought'); add('main'); add('shop')
        elif self.stage == 'return_main':
            add('shop'); add('main'); add('main', dialogue='else')
        elif self.stage == 'closing_text':
            add('main', dialogue='else'); add('main', dialogue='thanks')
        return any(_matches_view(rows, view) for view in choices)

    def context(self, text, progress, *, location, battle_state, frame, now,
                overworld_ready=False, intent=None):
        if self.error:
            return self._fail(self.error)
        if self.complete:
            return self._done()
        self.calls += 1
        if self.intent != self._contract or intent is not None and intent != self._contract:
            return self._fail('mart_intent_changed')
        if (type(frame) is not int or frame < 0 or type(now) not in (int, float)
                or not math.isfinite(now) or now < 0
                or self.last_frame is not None and frame < self.last_frame
                or self.last_time is not None and now < self.last_time):
            return self._fail('mart_clock_or_frame_invalid')
        if self.started_at is None:
            self.started_at = now
        if self.calls > self.max_calls or now - self.started_at > self.max_seconds:
            return self._fail('mart_time_or_call_budget_exhausted')
        rows = _rows(text)
        if (rows is None or text.get('profile') != TEXT_PROFILE or text.get('read_valid') is not True
                or text.get('alignment_verified') is not True or type(text.get('window_visible')) is not bool
                or text.get('read_error') is not None):
            return self._fail('mart_decoder_proof_required')
        if any(not isinstance(packet, dict) or 'observation_frame' in packet
               and (type(packet['observation_frame']) is not int or packet['observation_frame'] != frame)
               for packet in (text, progress, location, battle_state)):
            return self._fail('mart_same_frame_proof_required')
        if (type(overworld_ready) is not bool
                or any(type(location.get(k)) is not int or location[k] != v
                       for k, v in (('map_id', 150), ('x', 2), ('y', 5)))
                or location.get('facing') != 'left'
                or 'facing_raw' in location and (type(location['facing_raw']) is not int or location['facing_raw'] != 8)):
            return self._fail('mart_stance_changed_or_unknown')
        if (battle_state.get('active') is not False or battle_state.get('kind') != 'none'
                or type(battle_state.get('raw')) is not int or battle_state['raw'] != 0):
            return self._fail('mart_requires_known_nonbattle')
        party, inventory = _party(progress), _inventory(progress.get('inventory'))
        money = progress.get('money')
        if party is None or inventory is None or type(money) is not int or not 0 <= money <= 999999:
            return self._fail('mart_progress_invalid')
        packet = deepcopy((rows, text['window_visible'], progress, location, battle_state, overworld_ready))
        if self.last_frame == frame:
            if packet != self.last_packet:
                return self._fail('mart_same_frame_conflicting_packet')
            self.last_time = now
            return self._wait('duplicate_frame_no_repeat')
        self.last_frame, self.last_time, self.last_packet = frame, now, packet
        if self.expected is None:
            self.expected = purchase_expectation(progress)
            if self.expected is None:
                return self._fail('mart_money_or_bag_preflight_failed')
            self.party_before, self.inventory_before, self.money_before = deepcopy(party), deepcopy(inventory), money
        if party != self.party_before:
            return self._fail('mart_party_changed')
        before = inventory == self.inventory_before and money == self.money_before
        after = inventory == self.expected['inventory'] and money == self.expected['money']
        # Source adds items before subtracting money; the reverse is not a valid intermediate packet.
        intermediate = inventory == self.expected['inventory'] and money == self.money_before
        if not self.yes_confirmed and not before:
            return self._fail('mart_transaction_changed_before_yes')
        if self.yes_confirmed:
            if not (after or not self.purchase_observed and (before or intermediate)):
                return self._fail('mart_transaction_difference_unexpected')
            if after:
                self.purchase_observed = True
        lower = _lower(rows)
        if lower is None or any(word in _compact(''.join(rows)) for word in
                                ('TOSS', 'WHATWOULDYOULIKETOSELL', 'ICANPAYYOU', 'ANYTHINGTOSELL')):
            return self._fail('mart_unknown_or_selling_page')
        if not self._ui_guard(rows, money):
            return self._fail('mart_visible_ui_outside_source_mask')
        if self.stage == 'initial':
            if (text['window_visible'] or not overworld_ready or lower or _marks(rows)
                    or any(_positions(rows, word) for word in ('BUY', 'SELL', 'QUIT', 'MONEY', 'YES', 'NO', 'ITEM', 'SAVE'))):
                return self._fail('mart_initial_overworld_required')
            self.initial_world_rows = rows
            return self._send('a', rows, 'opening', 'talk_to_verified_clerk')
        if self.pending_rows == rows:
            return self._wait('unchanged_page_no_repeat')
        if self.stage == 'exit_wait':
            if lower == _THANKS or _marks(rows) or text['window_visible'] or not overworld_ready:
                self.world_stable_frame = None
                return self._wait('normal_exit_dialogue_or_world_not_ready')
            if (rows != self.initial_world_rows or _marks(rows) or lower or not after
                    or not self.bought_receipt_seen or not self.exit_text_seen):
                return self._fail('mart_exit_fingerprint_or_receipt_missing')
            if self.world_stable_frame is None:
                self.world_stable_frame = frame
                return self._wait('verify_second_fresh_world_frame')
            return self._done() if frame - self.world_stable_frame >= 3 else self._wait('world_frames_too_close')
        # Hardware Window visibility is not a semantic menu detector: these
        # menus may be drawn in the BG tilemap. Both bool values are proven
        # measurements; full visible source layouts decide the menu actions.
        if all(c == ' ' for row in rows for c in row):
            return (self._wait('known_blank_render_transition') if not overworld_ready
                    else self._fail('mart_unexpected_overworld'))
        if self.stage in ('opening', 'return_main'):
            expected_text = _GREETING if self.stage == 'opening' else _ELSE
            if _main(rows,money,active=False) and expected_text.startswith(lower):
                return self._wait('await_active_main_cursor_after_known_dialogue')
            if _main(rows, money):
                if lower != expected_text:
                    return self._wait('known_main_dialogue_typing') if expected_text.startswith(lower) else self._fail('mart_main_dialogue_unknown')
                if self.stage == 'opening':
                    return self._send('a', rows, 'buy_open', 'choose_verified_buy')
                if not after or not self.bought_receipt_seen:
                    return self._fail('mart_quit_requires_observed_purchase')
                return self._send('b', rows, 'closing_text', 'normal_b_quit_verified_main_menu')
            if self.stage == 'return_main' and _shop(rows, money) and lower == _BUYING:
                return self._wait('stale_buy_list_after_b_no_repeat')
            if any(_positions(rows, w) for w in _MAIN) or any(c == '▶' for _, _, c in _marks(rows)):
                return self._fail('mart_main_menu_labels_or_cursor_invalid')
            if expected_text.startswith(lower) and _marks(rows) <= {(1, 1, '▷')}:
                return self._wait('known_main_dialogue_or_menu_typing')
            return self._fail('mart_unknown_main_page')
        if self.stage in ('buy_open', 'post_receipt'):
            if _shop(rows, money) and lower == _BUYING:
                if self.stage == 'post_receipt':
                    if not after:
                        return self._fail('mart_receipt_without_transaction')
                    return self._send('b', rows, 'return_main', 'leave_verified_buy_list')
                return self._send('a', rows, 'quantity', 'choose_great_ball_first_item')
            if self.stage == 'post_receipt' and lower == _BOUGHT and _SELECTED <= _marks(rows) <= _SELECTED | {(18, 16, '▼')}:
                return self._wait('stale_bought_receipt_no_repeat')
            if self.stage == 'buy_open' and lower in (_GREETING, _BUYING) and _main(rows, money, active=False):
                return self._wait('buy_menu_opening_no_repeat')
            if (_BUYING.startswith(lower) and not any(c == '▶' for _, _, c in _marks(rows))
                    and _marks(rows) <= {(1, 1, '▷'), (18, 11, '▼')}):
                return self._wait('known_buy_menu_typing')
            return self._fail('mart_goods_or_buy_page_invalid')
        if self.stage == 'quantity':
            if (not _selected_good(rows, money) or _marks(rows) != _SELECTED
                    or not _labels(rows[:9], {k: v for k, v in _GOODS.items() if v[1] < 10})
                    or rows[7][11:18] != _money_field(700) or lower != _BUYING):
                return self._fail('mart_quantity_selected_item_or_cursor_invalid')
            qraw, praw = rows[10][8:11], rows[10][12:19]
            target = self.quantity_last + 1 if self.quantity_last else 1
            quantity = int(qraw[1:]) if re.fullmatch('×[0-9]{2}', qraw) else None
            prices = {self.quantity_last * 600, target * 600}
            amount = next((v for v in prices if praw == _money_field(v)), None)
            if quantity == target and amount == target * 600:
                self.quantity_last = target
                if target == 20:
                    return self._send('a', rows, 'price_text', 'confirm_exact_twenty_and_12000', flags=('quantity_confirmed',))
                return self._send('up', rows, 'quantity', 'increment_quantity_once')
            if (self.quantity_last and quantity in (self.quantity_last, target)
                    and (amount in prices or not praw.strip() or praw.strip() == '0')):
                return self._wait('quantity_and_total_price_redrawing')
            if self.quantity_last and quantity is None and (qraw.strip() in ('', '×') or f'×{target:02}'.startswith(qraw.rstrip())):
                return self._wait('quantity_digits_typing')
            if not self.quantity_last and qraw.strip() in ('', '×', '×0') and set(praw) <= set(' ¥0123456789'):
                return self._wait('initial_quantity_drawing')
            return self._fail('mart_quantity_or_price_unexpected')
        if self.stage == 'price_text':
            if not self.quantity_confirmed or not _selected_good(rows, money):
                return self._fail('mart_price_without_verified_twenty')
            marks = _marks(rows)
            if lower == _PREFIX and _SELECTED <= marks <= _SELECTED | {(18, 16, '▼')}:
                self.prefix_seen = True
                if self.prefix_advanced or (18, 16, '▼') not in marks:
                    return self._wait('price_prefix_wait_for_scroll_or_tail')
                return self._send('a', rows, 'price_text', 'advance_verified_item_and_price_prefix', flags=('prefix_advanced',))
            if lower == _TAIL and self.prefix_seen and self.prefix_advanced:
                if (marks == _SELECTED and rows[10][8:11] == '×20'
                        and rows[10][12:19] == _money_field(12000)
                        and not any(_positions(rows, label) for label in _YESNO)):
                    return self._wait('price_text_done_before_yes_no_box')
                if (marks == _SELECTED and _partial_labels(rows, _YESNO)):
                    return self._wait('verified_price_yes_no_menu_drawing')
                if (not _labels(rows, _YESNO)
                        or any(rows[y][x:19].strip() != label for label, (x, y) in _YESNO.items())
                        or rows[10][8:11] != '×20'):
                    return self._fail('mart_price_yes_no_labels_invalid')
                if marks == _SELECTED | {(15, 10, '▶')}:
                    return self._send('up', rows, 'price_text', 'select_verified_price_yes')
                if marks != _SELECTED | {(15, 8, '▶')}:
                    return self._fail('mart_price_yes_cursor_invalid')
                return self._send('a', rows, 'purchase_ack', 'buy_twenty_once_at_verified_total', flags=('yes_confirmed',))
            if (_SELECTED <= marks <= _SELECTED | {(18, 16, '▼')}
                    and (_PREFIX.startswith(lower) or self.prefix_advanced and _TAIL.startswith(lower))):
                return self._wait('known_price_question_typing')
            return self._fail('mart_unknown_price_question_or_total')
        if self.stage == 'purchase_ack':
            if lower == _TAIL and _labels(rows, _YESNO):
                if _marks(rows) not in (_SELECTED | {(15, 8, '▶')}, _SELECTED | {(15, 10, '▶')}):
                    return self._fail('mart_stale_confirmation_cursor_invalid')
                return self._wait('stale_yes_confirmation_no_repeat')
            if _SELECTED <= _marks(rows) <= _SELECTED | {(18, 16, '▼')} and _BOUGHT.startswith(lower):
                if not _money(rows, money):
                    return self._fail('mart_receipt_visible_money_mismatch')
                if lower != _BOUGHT or (18, 16, '▼') not in _marks(rows) or not after:
                    return self._wait('purchase_receipt_or_transaction_pending')
                return self._send('a', rows, 'post_receipt', 'acknowledge_verified_bought_receipt', flags=('bought_receipt_seen',))
            return self._fail('mart_unknown_purchase_result')
        if self.stage == 'closing_text':
            if _main(rows, money, active=False) and lower == _ELSE:
                return self._wait('quit_menu_closing_no_repeat')
            if _marks(rows) == {(1, 1, '▷')} and _THANKS.startswith(lower):
                if not _money(rows, money):
                    return self._fail('mart_exit_visible_money_mismatch')
                if lower != _THANKS or not after or not self.bought_receipt_seen:
                    return self._wait('normal_exit_thank_you_typing')
                return self._send('a', rows, 'exit_wait', 'close_source_after_displaying_text_id', flags=('exit_text_seen',))
            return self._fail('mart_unknown_quit_page')
        return self._fail('mart_unknown_stage')
