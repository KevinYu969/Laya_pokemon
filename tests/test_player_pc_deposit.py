"""固定來源物理 cell／fake memory；不建立模擬器、不送鍵或載存檔。"""
from copy import deepcopy
import importlib
import re
from types import SimpleNamespace

import pytest

from laya_pokemon import player_pc_deposit as pc


def progress(item=234):
    names = {7: 'NIDOKING', 19: 'LAPRAS', 102: 'EEVEE', 154: 'VENUSAUR',
             35: 'FEAROW', 132: 'SNORLAX'}
    return {'profile': 'gen1-wrapper-ram-progress-v1-unvalidated', 'initialization_candidate': True,
            'party_read_valid': True, 'party_count': 6, 'money': 55372,
            'inventory': [{'item': i, 'quantity': q} for i, q in
                          [(4, 6), (234, 1), (42, 1), (221, 1), (48, 1), (196, 1), (198, 1), (199, 1)]],
            'party': [dict(species=s, species_name=n, level=35, exp=50000, hp=100,
                           max_hp=100, status=0, moves=[33, 0, 0, 0], pp=[35, 0, 0, 0])
                      for s, n in names.items()]}


def blank(): return [[' '] * 20 for _ in range(18)]


def put(c, x, y, word):
    # SDK 的 's 是單一 tile，測試不把它展開成兩欄。
    chunks = re.findall("'s|.", word)
    c[y][x:x + len(chunks)] = [v if v == "'s" else v.upper() for v in chunks]
    return c


def text(c=None, window=True):
    c = deepcopy(blank() if c is None else c)
    visible = [(''.join(row).rstrip(), i) for i, row in enumerate(c)
               if re.search(r'[A-Za-z0-9]{2,}', ''.join(row))][:12]
    return dict(profile=pc.TEXT_PROFILE, read_valid=True, alignment_verified=True,
                read_error=None, window_visible=window, cells=c,
                lines=[r for r, _ in visible], line_rows=[i for _, i in visible])


def dialogue(first, second='', *, upper=None, arrow=True):
    c = deepcopy(blank() if upper is None else upper)
    for y in range(12, 18): c[y] = [' '] * 20
    put(c, 1, 14, first); put(c, 1, 16, second)
    if arrow: c[16][18] = '▼'
    return c


def main(row=2):
    c = blank()
    for y, word in [(2, "BILL's PC"), (4, "KEVIN's PC"), (6, "PROF.OAK's PC"), (8, 'LOG OFF')]:
        put(c, 2, y, word)
    c[row][1] = '▶'
    return c


def player(row=2):
    c = blank()
    for y, word in [(2, 'WITHDRAW ITEM'), (4, 'DEPOSIT ITEM'), (6, 'TOSS ITEM'), (8, 'LOG OFF')]:
        put(c, 2, y, word)
    c[row][1] = '▶'
    return dialogue('What do you want', 'to do?', upper=c, arrow=False)


NAMES = {4: 'POKé BALL', 234: 'TM34', 221: 'TM21', 42: 'HELIX FOSSIL', 49: 'NUGGET', 63: 'S.S.TICKET',
         48: 'CARD KEY', 196: 'HM01', 198: 'HM03', 199: 'HM04'}


def bag(p, offset=0, cursor=0, marker='▶'):
    c = blank()
    for y, word in [(2, 'WI'), (4, 'DE'), (6, 'TO'), (8, 'LO')]: put(c, 2, y, word)
    c[4][1] = '▷'
    printed = 0
    for n in range(4):
        index, y = offset+n, 4+n*2
        if index == len(p['inventory']):
            put(c, 6, y, 'CANCEL'); break
        if index > len(p['inventory']): break
        entry = p['inventory'][index]
        put(c, 6, y, NAMES[entry['item']])
        if entry['item'] in (4, 234, 221, 49): put(c, 14, y+1, f"×{entry['quantity']:2}")
        printed += 1
    if printed == 4: c[11][18] = '▼'
    c[4+cursor*2][5] = marker
    return dialogue('What do you want', 'to deposit?', upper=c, arrow=False)


def quantity(p, offset, cursor):
    c = bag(p, offset, cursor, '▷')
    for y in range(9, 12):
        for x in range(15, 20): c[y][x] = ' '
    put(c, 16, 10, '×01')
    return dialogue('How many?', upper=c, arrow=False)


class Session:
    def __init__(self, item=234, pc_items=None):
        self.p = progress(item); self.items = deepcopy(pc_items or [{'item': 20, 'quantity': 1}])
        self.controller = pc.PlayerPCDepositController({**pc.INTENT_BASE, 'item': item})
        self.frame = 0; self.now = 0.

    def call(self, cells=None, previous=('wait',), *, ready=False, window=True,
             same=False, t=None, p=None, signal=None, **kwargs):
        if not same: self.frame += 1; self.now += .05
        sig = dict(profile=pc.PROFILE, source_commit=pc.SOURCE_COMMIT, read_valid=True,
                   read_error=None, observation_frame=self.frame, location=deepcopy(pc.LOCATION),
                   facing='up', facing_raw=4, count=len(self.items), items=deepcopy(self.items))
        args = dict(location=deepcopy(pc.LOCATION), battle_state=dict(raw=0, active=False, kind='none',
                    observation_frame=self.frame), pc_signal=sig if signal is None else signal,
                    frame=self.frame, previous=previous, now=self.now, overworld_ready=ready)
        args.update(kwargs)
        value = text(cells, window) if t is None else t
        actual_p = self.p if p is None else p
        before = deepcopy((value, actual_p, args))
        result = self.controller.context(value, actual_p, **args)
        assert (value, actual_p, args) == before
        return result

    def expect(self, cells, key, previous, **kwargs):
        result = self.call(cells, (previous,), **kwargs)
        assert result['available_actions'] == ([key, 'wait'] if key != 'wait' else ['wait']), result
        assert result['phase'] != 'campaign_review', result
        return result

    def to_bag(self):
        self.expect(blank(), 'a', 'wait', ready=True, window=False)
        self.expect(dialogue('KEVIN turned on', 'the PC.'), 'a', 'a')
        self.expect(main(2), 'down', 'a')
        self.expect(main(4), 'a', 'down')
        self.expect(dialogue('Accessed my PC.', upper=main(4)), 'a', 'a')
        self.expect(dialogue('Accessed Item', 'Storage System.', upper=main(4)), 'a', 'a')
        self.expect(player(2), 'down', 'a')
        self.expect(player(4), 'a', 'down')

    def to_quantity(self):
        self.to_bag()
        target = next(i for i, v in enumerate(self.p['inventory']) if v['item'] == self.controller.intent['item'])
        previous = 'a'
        for index in range(target+1):
            offset, cursor = max(0, index-2), min(index, 2)
            self.expect(bag(self.p, offset, cursor), 'a' if index == target else 'down', previous)
            previous = 'down'
        self.offset, self.cursor = offset, cursor
        return quantity(self.p, offset, cursor)

    def transfer(self):
        item = self.controller.intent['item']
        self.p['inventory'] = [v for v in self.p['inventory'] if v['item'] != item]
        entry = next((v for v in self.items if v['item'] == item), None)
        if entry: entry['quantity'] += 1
        else: self.items.append({'item': item, 'quantity': 1})


def review(result):
    assert result['phase'] == 'campaign_review' and result['available_actions'] == ['wait'], result
    assert result.get('pc_deposit_complete') is False


@pytest.mark.parametrize('item', [234, 221])
def test_full_normal_transfer_uses_quantity_and_receipt_then_exits_with_two_fresh_closed_frames(item):
    s = Session(item); original_party = deepcopy(s.p['party']); original_money = s.p['money']
    qty = s.to_quantity(); s.expect(qty, 'a', 'a')
    s.transfer()
    receipt = dialogue(f'TM{item-200:02d} was', 'stored via PC.', upper=qty)
    s.expect(receipt, 'a', 'a')
    s.expect(bag(s.p), 'b', 'a')
    s.expect(player(4), 'b', 'b')
    s.expect(main(2), 'b', 'b')
    first = s.expect(blank(), 'wait', 'b', ready=True, window=False)
    assert not first['pc_deposit_complete']
    assert not s.call(blank(), ('b',), ready=True, window=False, same=True)['pc_deposit_complete']
    assert s.expect(blank(), 'wait', 'wait', ready=True, window=False)['pc_deposit_complete']
    assert s.p['party'] == original_party and s.p['money'] == original_money
    assert sum(v['quantity'] for v in s.items if v['item'] == item) == 1


def test_two_independent_controllers_can_deposit_in_order_without_reusing_old_bag_slot():
    first = Session(234); qty = first.to_quantity(); first.expect(qty, 'a', 'a'); first.transfer()
    first.expect(dialogue('TM34 was', 'stored via PC.', upper=qty), 'a', 'a')
    first.expect(bag(first.p), 'b', 'a'); first.expect(player(4), 'b', 'b'); first.expect(main(), 'b', 'b')
    first.expect(blank(), 'wait', 'b', ready=True, window=False)
    assert first.expect(blank(), 'wait', 'wait', ready=True, window=False)['pc_deposit_complete']
    second = Session(221, first.items); second.p = deepcopy(first.p)
    qty2 = second.to_quantity()
    assert second.controller.baseline['bag'][2]['item'] == 221
    second.expect(qty2, 'a', 'a'); second.transfer()
    assert [v['item'] for v in second.p['inventory']] == [4, 42, 48, 196, 198, 199]
    assert second.items[-2:] == [{'item':234, 'quantity':1}, {'item':221, 'quantity':1}]


def test_existing_pc_stack_gains_one_without_replacing_other_entries():
    s = Session(pc_items=[{'item': 234, 'quantity': 4}, {'item': 20, 'quantity': 1}])
    qty = s.to_quantity(); s.expect(qty, 'a', 'a'); s.transfer()
    s.expect(dialogue('TM34 was', 'stored via PC.', upper=qty), 'a', 'a')
    assert s.items == [{'item':234, 'quantity':5}, {'item':20, 'quantity':1}]


def test_laya_wait_is_not_execution_and_same_frame_never_repeats_confirmation():
    s = Session(); c = blank()
    s.expect(c, 'a', 'wait', ready=True, window=False)
    assert s.call(c, ready=True, window=False, same=True)['available_actions'] == ['wait']
    s.expect(c, 'a', 'wait', ready=True, window=False)
    assert s.controller.stage == 'initial'
    s.expect(dialogue('KEVIN turned on', 'the PC.'), 'a', 'a')
    # A 已真的送過但文字頁尚未消失，只等待，不能重複 A。
    assert s.call(dialogue('KEVIN turned on', 'the PC.'), ('a',))['available_actions'] == ['wait']
    assert s.controller.stage == 'main'


def test_page_change_without_actual_previous_is_not_confirmation_evidence():
    s = Session(); s.expect(blank(), 'a', 'wait', ready=True, window=False)
    review(s.call(dialogue('KEVIN turned on', 'the PC.'), ('wait',)))


@pytest.mark.parametrize('bad', ['withdraw', 'toss', 'wrong_name', 'foreign', 'duplicate_cursor'])
def test_wrong_pc_or_deposit_menu_never_confirms(bad):
    s = Session(); s.to_bag()
    # 已選 DEPOSIT 後尚未得到清單，任意別的選單都不能 A。
    c = player(2 if bad == 'withdraw' else 6)
    if bad == 'wrong_name': c = main(4); put(c, 2, 4, "RED's PC  ")
    elif bad == 'foreign': c = bag(s.p); c[0][0] = '☃'
    elif bad == 'duplicate_cursor': c = bag(s.p); c[0][0] = '▶'
    review(s.call(c, ('a',)))


@pytest.mark.parametrize('bad', ['quantity', 'wrong_item', 'inactive', 'unknown_prompt'])
def test_quantity_page_requires_exact_selected_item_and_01(bad):
    s = Session(); c = s.to_quantity()
    if bad == 'quantity': put(c, 17, 10, '02')
    elif bad == 'wrong_item': put(c, 6, 6, 'TM21')
    elif bad == 'inactive': c[4][0] = '▷'
    else: c = dialogue('Use this item?', upper=c, arrow=False)
    review(s.call(c, ('a',)))


def test_known_partial_and_prompt_blink_only_wait_without_early_a():
    s = Session(); s.expect(blank(), 'a', 'wait', ready=True, window=False)
    s.expect(dialogue('KEVIN tur', '', arrow=False), 'wait', 'a')
    s.expect(dialogue('KEVIN turned on', 'the PC.', arrow=False), 'wait', 'wait')
    s.expect(dialogue('KEVIN turned on', 'the PC.'), 'a', 'wait')


@pytest.mark.parametrize('bad', ['no_pc_add', 'bag_not_removed', 'other_bag', 'other_pc', 'party', 'money'])
def test_stored_receipt_never_substitutes_for_exact_conservation(bad):
    s = Session(); qty = s.to_quantity(); s.expect(qty, 'a', 'a')
    old = deepcopy(s.p); old_pc = deepcopy(s.items); s.transfer()
    if bad == 'no_pc_add': s.items = old_pc
    elif bad == 'bag_not_removed': s.p['inventory'] = old['inventory']
    elif bad == 'other_bag': s.p['inventory'][0]['quantity'] -= 1
    elif bad == 'other_pc': s.items[0]['quantity'] += 1
    elif bad == 'party': s.p['party'][2]['hp'] -= 1
    else: s.p['money'] -= 1
    review(s.call(dialogue('TM34 was', 'stored via PC.', upper=qty), ('a',)))


def test_missing_or_partial_receipt_cannot_exit_or_complete_even_with_transfer():
    s = Session(); qty = s.to_quantity(); s.expect(qty, 'a', 'a'); s.transfer()
    s.expect(dialogue('TM34 was', 'stored via', upper=qty, arrow=False), 'wait', 'a')
    assert not s.controller.receipt_seen
    review(s.call(bag(s.p), ('wait',)))


def test_inventory_change_while_laya_waits_cannot_retry_an_old_a():
    s = Session(); s.expect(blank(), 'a', 'wait', ready=True, window=False)
    s.p['inventory'][0]['quantity'] -= 1
    review(s.call(blank(), ('wait',), ready=True, window=False))


@pytest.mark.parametrize('bad', ['profile', 'window', 'alignment', 'read_error', 'lines', 'line_rows', 'multicell'])
def test_decoder_metadata_and_physical_rows_must_agree(bad):
    s = Session(); s.to_bag(); t = text(bag(s.p))
    if bad == 'profile': t['profile'] = 'wrong'
    elif bad == 'window': t['window_visible'] = False
    elif bad == 'alignment': t['alignment_verified'] = False
    elif bad == 'read_error': t['read_error'] = 'visible_display_disabled'
    elif bad == 'lines': t['lines'] = ['FAKE']
    elif bad == 'line_rows': t['line_rows'] = [0]
    else: t['cells'][0][0] = "'t"
    review(s.call(previous=('a',), t=t))


def test_single_tile_possessive_is_required_at_its_source_position():
    s = Session(); s.expect(blank(), 'a', 'wait', ready=True, window=False)
    s.expect(dialogue('KEVIN turned on', 'the PC.'), 'a', 'a')
    assert main()[2][6] == "'s"
    s.expect(main(), 'down', 'a')


@pytest.mark.parametrize('bad', ['empty_qty', 'wrong_item', 'full_stack', 'full_pc', 'faint', 'party_count'])
def test_initial_baseline_reserves_capacity_and_rejects_wrong_party_or_stack(bad):
    s = Session()
    if bad == 'empty_qty': s.p['inventory'][1]['quantity'] = 2
    elif bad == 'wrong_item': s.p['inventory'][1]['item'] = 246
    elif bad == 'full_stack': s.items = [{'item':234, 'quantity':99}]
    elif bad == 'full_pc': s.items = [{'item':i, 'quantity':1} for i in range(1, 51) if i not in (7, 44)] + [{'item':51,'quantity':1}, {'item':52,'quantity':1}]
    elif bad == 'faint': s.p['party'][0]['hp'] = 0
    else: s.p['party_count'] = 5
    review(s.call(blank(), ready=True, window=False))


def test_budget_and_sticky_intent_are_not_reset_by_class_reload():
    s = Session(); s.expect(blank(), 'a', 'wait', ready=True, window=False)
    record = s.controller; importlib.reload(pc); record.__class__ = pc.PlayerPCDepositController
    review(s.call(blank(), ('a',), ready=True, window=False, now=61))
    assert s.controller.started == .05
    s.controller.intent['item'] = 221
    review(s.call(blank(), ready=True, window=False, now=62))


def test_same_frame_conflict_and_false_typed_intent_fail_closed():
    s = Session(); s.expect(blank(), 'a', 'wait', ready=True, window=False)
    changed = deepcopy(s.p); changed['money'] -= 1
    review(s.call(blank(), ready=True, window=False, same=True, p=changed))
    s2 = Session(); s2.controller.intent['quantity'] = True
    review(s2.call(blank(), ready=True, window=False))


def sdk():
    return SimpleNamespace(**pc.SDK_ANCHORS, MAPS={'saffron_pokecenter':182})


class Memory:
    def __init__(self, items=None):
        self.values = {0xD35E:182, 0xD361:4, 0xD362:13, 0xC109:4}
        for address in range(pc.PC_COUNT, pc.PC_ITEMS+101): self.values[address] = 0
        items = [{'item':20, 'quantity':1}] if items is None else items
        self.values[pc.PC_COUNT] = len(items)
        for i, v in enumerate(items):
            self.values[pc.PC_ITEMS+i*2] = v['item']; self.values[pc.PC_ITEMS+i*2+1] = v['quantity']
        self.values[pc.PC_ITEMS+len(items)*2] = 255
        self.reads = 0
    def __getitem__(self, address):
        self.reads += 1
        return self.values[address]
    def __setitem__(self, *args): raise AssertionError('不得寫入記憶體')


def read(mem=None, constants=None, game=None):
    obj = game or SimpleNamespace(frame_count=10, memory=mem or Memory())
    return pc.read_player_pc(obj, observation_frame=10, expected_location=deepcopy(pc.LOCATION), constants=constants or sdk())


def test_reader_reads_full_table_twice_without_writes_and_unknown_is_not_empty():
    m = Memory(); result = read(m)
    assert result['read_valid'] is True and result['items'] == [{'item':20,'quantity':1}]
    assert m.reads == 212 and result['live_calibrated'] is False
    empty = read(Memory([])); assert empty['read_valid'] is True and empty['items'] == []
    bad = sdk(); bad.BAG_ITEMS_ADDRESS += 1
    assert read(constants=bad)['items'] is None


@pytest.mark.parametrize('bad', ['count', 'terminator', 'duplicate', 'quantity', 'bool', 'stance', 'unknown_item'])
def test_reader_rejects_invalid_or_unknown_full_table(bad):
    m = Memory()
    if bad == 'count': m.values[pc.PC_COUNT] = 51
    elif bad == 'terminator': m.values[pc.PC_ITEMS+2] = 0
    elif bad == 'duplicate': m = Memory([{'item':20,'quantity':1},{'item':20,'quantity':2}])
    elif bad == 'quantity': m.values[pc.PC_ITEMS+1] = 0
    elif bad == 'bool': m.values[pc.PC_COUNT] = True
    elif bad == 'stance': m.values[0xD361] = 3
    else: m.values[pc.PC_ITEMS] = 190
    result = read(m); assert result['read_valid'] is False and result['items'] is None


def test_reader_rejects_torn_table_or_frame_change():
    class Torn(Memory):
        def __getitem__(self, address):
            value = super().__getitem__(address)
            return value + 1 if address == pc.PC_ITEMS+1 and self.reads > 106 else value
    assert read(Torn())['read_valid'] is False
    class Changed:
        memory = Memory()
        n = 0
        @property
        def frame_count(self):
            self.n += 1
            return 10 if self.n == 1 else 11
    assert read(game=Changed())['read_valid'] is False


def test_reader_oserror_returns_unknown_without_claiming_an_empty_pc():
    class Unreadable(Memory):
        def __getitem__(self, address):
            if address == pc.PC_COUNT: raise OSError('read unavailable')
            return super().__getitem__(address)
    result = read(Unreadable())
    assert result['read_valid'] is False and result['items'] is None
    assert result['read_error'] == 'pc_getter_failed'


def post_receipt_session():
    s = Session()
    s.p['inventory'][3] = {'item':49, 'quantity':1}
    s.p['inventory'][4] = {'item':63, 'quantity':1}
    qty = s.to_quantity(); s.expect(qty, 'a', 'a'); s.transfer()
    s.expect(dialogue('TM34 was', 'stored via PC.', upper=qty), 'a', 'a')
    return s, qty


def test_real_post_receipt_footer_redraw_keeps_old_quantity_until_fresh_bag():
    # 固定 no-input clone frame1 的原物理文字；來源 campaign frame1427457。
    # outputs/research/player-pc-tm34-first-pause-20261024.json，非另造新讀值。
    observed = [' '*20, ' '*20, '  WI                ', ' '*20,
                ' ▷DE  POKé BALL     ', '              × 6   ',
                '  TO ▷TM34          ', '              × 1   ',
                '  LO  HELIX FOSSIL  ', ' '*20, '      NUGGET    ×01 ',
                '              ×     ', ' '*20, ' '*20,
                ' What do you want   ', ' '*20, ' '*20, ' '*20]
    assert all(len(row) == 20 for row in observed)
    rows = [list(row) for row in observed]
    s, qty = post_receipt_session()
    assert [[c.upper() for c in row] for row in rows] == dialogue('What do you want', upper=qty, arrow=False)
    result = s.expect(rows, 'wait', 'a')
    assert result['player_pc_tactic'] == 'stored_receipt_acknowledged_await_fresh_bag'
    assert s.controller.stage == 'after_receipt' and s.controller.transferred and s.controller.receipt_seen
    s.expect(dialogue('What do you want', 'to dep', upper=qty, arrow=False), 'wait', 'wait')
    s.expect(dialogue('What do you want', 'to deposit?', upper=qty, arrow=False), 'wait', 'wait')
    s.expect(bag(s.p), 'b', 'wait')  # 真新清單及 ▶ 才能退出。


@pytest.mark.parametrize('bad', ['upper', 'footer', 'arrow'])
def test_post_receipt_redraw_does_not_allow_unknown_background_or_prompt(bad):
    s, qty = post_receipt_session()
    rows = dialogue('What do you want', upper=qty, arrow=False)
    if bad == 'upper': rows[0][0] = 'X'
    elif bad == 'footer': put(rows, 1, 16, 'Use this item?')
    else: rows[16][18] = '▼'
    review(s.call(rows, ('a',)))


def test_real_refreshed_bag_scroll_arrow_blink_is_the_only_optional_cell():
    # 固定 second-pause clone frame1 的原18列；campaign frame1427537。
    observed = [' '*20, ' '*20, '  WI                ', ' '*20,
                ' ▷DE ▶POKé BALL     ', '              × 6   ',
                '  TO  HELIX FOSSIL  ', ' '*20, '  LO  NUGGET        ',
                '              × 1   ', '      S.S.TICKET    ', ' '*20,
                ' '*20, ' '*20, ' What do you want   ', ' '*20,
                ' to deposit?        ', ' '*20]
    s, qty = post_receipt_session()
    rows = [list(row) for row in observed]
    expected = bag(s.p)
    diff = [(x, y) for y in range(18) for x in range(20)
            if rows[y][x].upper() != expected[y][x]]
    assert diff == [(18, 11)] and expected[11][18] == '▼' and rows[11][18] == ' '
    s.expect(rows, 'b', 'a')


def test_scroll_arrow_blink_also_applies_to_normal_deposit_bag_before_selection():
    s = Session(); s.to_bag()
    rows = bag(s.p); rows[11][18] = ' '
    s.expect(rows, 'down', 'a')


@pytest.mark.parametrize('bad', ['foreign_scroll_glyph', 'different_arrow_cell', 'missing_active_cursor'])
def test_scroll_blink_does_not_relax_other_glyphs_or_cursor(bad):
    s, _ = post_receipt_session(); rows = bag(s.p)
    if bad == 'foreign_scroll_glyph': rows[11][18] = '▶'
    elif bad == 'different_arrow_cell': rows[11][18] = ' '; rows[11][17] = '▼'
    else: rows[4][5] = ' '
    review(s.call(rows, ('a',)))


def leaving_list_session():
    s, _ = post_receipt_session()
    s.expect(bag(s.p), 'b', 'a')
    return s


def test_real_player_menu_redraw_without_cursor_only_waits_until_full_active_menu():
    # third-pause no-input clone frame1，campaign frame1427617；真尾字是 wan。
    observed = [' '*20, ' '*20, '  WITHDRAW ITEM     ', ' '*20,
                '  DEPOSIT ITEM      ', ' '*20, '  TOSS ITEM         ', ' '*20,
                '  LOG OFF           ', ' '*20, ' '*20, ' '*20, ' '*20, ' '*20,
                ' What do you wan    ', ' '*20, ' '*20, ' '*20]
    s = leaving_list_session(); rows = [list(row) for row in observed]
    assert all(len(row) == 20 for row in rows)
    result = s.expect(rows, 'wait', 'b')
    assert result['player_pc_tactic'] == 'player_menu_footer_before_active_cursor'
    assert s.controller.stage == 'exit_player'
    completed_text = player(4); completed_text[4][1] = ' '
    s.expect(completed_text, 'wait', 'wait')  # 無游標，全文也不可按 B。
    s.expect(player(4), 'b', 'wait')


@pytest.mark.parametrize('bad', ['unknown_label', 'inactive', 'unknown_footer'])
def test_exit_player_wait_does_not_accept_foreign_label_cursor_or_body(bad):
    s = leaving_list_session()
    rows = player(4); rows[4][1] = ' '
    rows = dialogue('What do you wan', upper=rows, arrow=False)
    if bad == 'unknown_label': put(rows, 2, 6, 'USE ITEM ')
    elif bad == 'inactive': rows[4][1] = '▷'
    else: put(rows, 1, 16, 'Toss this item?')
    review(s.call(rows, ('b',)))
