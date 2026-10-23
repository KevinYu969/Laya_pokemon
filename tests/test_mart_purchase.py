"""只用合成文字／progress；不讀模擬器、存檔、ignored輸出或網路。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from laya_pokemon.mart_purchase import INTENT, SOURCE_COMMIT, MartPurchaseController, purchase_expectation
from laya_pokemon.observation import PROFILE

STANCE = {'map_id': 150, 'x': 2, 'y': 5, 'facing': 'left', 'facing_raw': 8}
NONE = {'raw': 0, 'active': False, 'kind': 'none'}
GREETING, BUYING, ELSE = ('Hi there!', 'May I help you?'), ('Take your time.', ''), ('Is there anything', 'else I can do?')


def text_at(*entries, window=True):
    cells = [[' '] * 20 for _ in range(18)]
    for x, y, word in entries:
        for dx, c in enumerate(word):
            cells[y][x + dx] = c
    return {'profile': PROFILE, 'read_valid': True, 'alignment_verified': True,
            'window_visible': window, 'read_error': None, 'cells': cells,
            'warnings': ['尚未完全校準，原有warning不等於decoder無效。']}


def put(text, x, y, word):
    text['cells'][y][x:x + len(word)] = list(word)
    return text


def remove_marks(text):
    for row in text['cells']:
        for x, c in enumerate(row):
            if c in '▶▷▼':
                row[x] = ' '
    return text


def progress(money=32000, inventory=None):
    return {'profile': 'gen1-wrapper-ram-progress-v1-unvalidated', 'initialization_candidate': True,
            'party_read_valid': True, 'party_count': 2, 'money': money,
            'inventory': deepcopy(inventory if inventory is not None else [{'item': 4, 'quantity': 6}, {'item': 49, 'quantity': 1}]),
            'party': [{'species': 7, 'species_name': 'NIDOKING', 'level': 30, 'exp': 22000, 'hp': 102,
                       'max_hp': 102, 'status': 0, 'moves': [61, 33, 30, 40], 'pp': [20, 35, 25, 35]},
                      {'species': 35, 'species_name': 'FEAROW', 'level': 31, 'exp': 30000, 'hp': 96,
                       'max_hp': 96, 'status': 0, 'moves': [64, 45, 43, 31], 'pp': [30, 40, 30, 20]}]}


def money(t, value):
    put(t, 13, 0, 'MONEY')
    return put(t, 12, 1, f'¥{value}'.rjust(7))


def dialogue(t, first, second='', prompt=False):
    for y in range(12, 18):
        t['cells'][y] = [' '] * 20
    put(t, 1, 14, first)
    put(t, 1, 16, second)
    if prompt:
        put(t, 18, 16, '▼')
    return t


def main(value=32000, *, cursor=1, inactive=False, words=GREETING):
    t = money(text_at((2, 1, 'BUY'), (2, 3, 'SELL'), (2, 5, 'QUIT'),
                      (1, cursor, '▷' if inactive else '▶')), value)
    return dialogue(t, *words)


def shop(value=32000, *, inactive=False):
    entries = [(6, y, label) for y, label in ((4, 'GREAT BALL'), (6, 'SUPER POTION'), (8, 'REVIVE'), (10, 'ESCAPE ROPE'))]
    entries += [(11, y, f'¥{price}'.rjust(7)) for y, price in ((5, 600), (7, 700), (9, 1500), (11, 550))]
    entries += [(5, 4, '▷' if inactive else '▶'), (18, 11, '▼')]
    t = main(value, inactive=True, words=BUYING)
    for y in range(2, 13):
        t['cells'][y][4:20] = [' '] * 16
    for x, y, word in entries:
        put(t, x, y, word)
    return dialogue(t, *BUYING)


def quantity(number, value=32000, *, price=None):
    t = shop(value, inactive=True)
    for y in range(9, 12):
        t['cells'][y][7:20] = [' '] * 13
    put(t, 8, 10, f'×{number:02}')
    return put(t, 12, 10, f'¥{number * 600 if price is None else price}'.rjust(7))


def prefix(value=32000, *, prompt=True, partial=None):
    return dialogue(quantity(20, value), 'GREAT BALL?' if partial is None else partial,
                    'That will be' if partial is None else '', prompt)


def confirmation(value=32000, *, total=12000, cursor=8, complete=True):
    t = quantity(20, value)
    for y in range(7, 12):
        t['cells'][y][14:20] = [' '] * 6
    dialogue(t, 'That will be', f'¥{total}. OK?')
    if complete:
        put(t, 16, 8, 'YES'); put(t, 16, 10, 'NO'); put(t, 15, cursor, '▶')
    return t


def bought(value=20000, *, prompt=True, partial=None):
    return dialogue(quantity(20, value), 'Here you are!' if partial is None else partial,
                    'Thank you!' if partial is None else '', prompt)


def thanks(value=20000, *, partial=None):
    return dialogue(main(value, inactive=True, words=ELSE), 'Thank you!' if partial is None else partial)


class Session:
    def __init__(self, p=None, **limits):
        self.p = progress() if p is None else p
        self.c = MartPurchaseController(deepcopy(INTENT), **limits)
        self.frame = 0; self.now = 0

    def call(self, t=None, **kw):
        self.frame += 40; self.now += .1
        return self.c.context(text_at(window=False) if t is None else t, self.p,
                              location=kw.pop('location', deepcopy(STANCE)), battle_state=kw.pop('battle_state', deepcopy(NONE)),
                              frame=kw.pop('frame', self.frame), now=kw.pop('now', self.now), **kw)

    def to_quantity(self):
        assert self.call(overworld_ready=True)['available_actions'] == ['a', 'wait']
        assert self.call(main(self.p['money']))['available_actions'] == ['a', 'wait']
        assert self.call(shop(self.p['money']))['available_actions'] == ['a', 'wait']

    def to_price(self):
        self.to_quantity()
        for n in range(1, 21):
            assert self.call(quantity(n, self.p['money']))['available_actions'] == ['up' if n < 20 else 'a', 'wait']

    def to_yes(self):
        self.to_price()
        assert self.call(prefix(self.p['money']))['available_actions'] == ['a', 'wait']
        assert self.call(confirmation(self.p['money']))['available_actions'] == ['a', 'wait']

    def apply_transaction(self):
        expected = self.c.expected
        self.p['inventory'] = deepcopy(expected['inventory']); self.p['money'] = expected['money']


def review(hint):
    assert hint['phase'] == 'campaign_review' and hint['available_actions'] == ['wait']
    assert hint['controller_menu_verified'] is False
    return hint['review_reason']


def test_complete_normal_source_flow_append_twenty_and_close():
    s = Session(); before = deepcopy(s.p)
    s.to_yes(); s.apply_transaction()
    assert s.call(bought())['available_actions'] == ['a', 'wait']
    assert s.call(shop(20000))['available_actions'] == ['b', 'wait']
    assert s.call(main(20000, words=ELSE))['available_actions'] == ['b', 'wait']
    assert s.call(thanks())['available_actions'] == ['a', 'wait']
    assert s.call(overworld_ready=True)['available_actions'] == ['wait']
    done = s.call(overworld_ready=True)
    assert done['mart_purchase_complete'] and done['quantity_purchased'] == 20 and done['money_spent'] == 12000
    assert s.p['inventory'] == before['inventory'] + [{'item': 3, 'quantity': 20}]
    assert s.p['party'] == before['party'] and s.p['money'] == 20000
    assert s.c.quantity_last == 20 and s.c.prefix_advanced and s.c.yes_confirmed
    assert s.call(text_at((1, 14, 'TOSS')))['mart_purchase_complete']


def test_complete_goods_page_without_scroll_decoration_still_selects_only_first_great_ball():
    s=Session();s.call(overworld_ready=True);s.call(main())
    t=shop();put(t,18,11,' ')
    assert s.call(t)['available_actions']==['a','wait']
    assert s.call(t)['available_actions']==['wait']


def test_post_purchase_complete_goods_without_scroll_decoration_exits_normally():
    s=Session();s.to_yes();s.apply_transaction();s.call(bought())
    t=shop(20000);put(t,18,11,' ')
    assert s.call(t)['available_actions']==['b','wait']


def test_missing_scroll_decoration_does_not_allow_missing_goods_text():
    s=Session();s.call(overworld_ready=True);s.call(main())
    t=shop();put(t,18,11,' ');put(t,6,8,'      ')
    review(s.call(t))


def test_inactive_return_main_cursor_while_known_else_text_types_waits_without_quitting():
    s=Session();s.to_yes();s.apply_transaction();s.call(bought());s.call(shop(20000))
    for words in [('Is there anythin',''),ELSE]:
        assert s.call(main(20000,inactive=True,words=words))['available_actions']==['wait']
    assert s.call(main(20000,words=ELSE))['available_actions']==['b','wait']


def test_inactive_opening_main_with_known_partial_greeting_waits():
    s=Session();s.call(overworld_ready=True)
    assert s.call(main(inactive=True,words=('Hi there!','May I')))['available_actions']==['wait']
    assert s.call(main())['available_actions']==['a','wait']


@pytest.mark.parametrize('count', [1, 5, 79])
def test_existing_stack_increases_in_place(count):
    p = progress(inventory=[{'item': 4, 'quantity': 6}, {'item': 3, 'quantity': count}, {'item': 49, 'quantity': 1}])
    old = deepcopy(p); expected = purchase_expectation(p)
    assert expected['inventory'] == [old['inventory'][0], {'item': 3, 'quantity': count + 20}, old['inventory'][2]]
    assert p == old


@pytest.mark.parametrize('amount', [17000, 999999])
def test_money_boundary_valid(amount):
    assert purchase_expectation(progress(amount))['money'] == amount - 12000


@pytest.mark.parametrize('amount', [None, True, 16999, 12000, 0, -1, 1000000, 17000.0])
def test_money_preflight_invalid(amount):
    s = Session(progress(amount)); assert 'preflight' in review(s.call(overworld_ready=True)) or s.c.error == 'mart_progress_invalid'


@pytest.mark.parametrize('items', [[{'item': 3, 'quantity': 80}], [{'item': 3, 'quantity': 99}],
    [{'item': 3, 'quantity': 0}], [{'item': 4, 'quantity': 1}, {'item': 4, 'quantity': 2}],
    [{'item': i, 'quantity': 1} for i in range(4, 24)], [{'item': True, 'quantity': 1}], None])
def test_invalid_or_full_bag_never_sends_key(items):
    p = progress(); p['inventory'] = items
    s = Session(p); review(s.call(overworld_ready=True))


def test_full_twenty_slots_with_existing_stack_is_valid():
    items = [{'item': i, 'quantity': 1} for i in range(3, 23)]
    assert purchase_expectation(progress(inventory=items))['inventory'][0] == {'item': 3, 'quantity': 21}


@pytest.mark.parametrize('change', [lambda p: p.update(party_read_valid=False), lambda p: p.update(party=[]),
    lambda p: p.update(party_count=3), lambda p: p['party'][0].update(pp=[20, None, 25, 35]),
    lambda p: p['party'][0].update(exp=None), lambda p: p['party'][0].update(species_name='FEAROW'),
    lambda p: p.update(profile='unknown'), lambda p: p.update(initialization_candidate=False)])
def test_unknown_party_or_profile_stops(change):
    p = progress(); change(p); review(Session(p).call(overworld_ready=True))


@pytest.mark.parametrize('key,value', [('profile', 'wrong'), ('read_valid', False), ('alignment_verified', False),
    ('window_visible', None), ('read_error', 'failed'), ('cells', [[' '] * 19] * 18), ('observation_frame', 99)])
def test_decoder_proof_and_alignment_required(key, value):
    t = text_at(window=False); t[key] = value
    review(Session().call(t, overworld_ready=True))


@pytest.mark.parametrize('field,value', [('map_id', 149), ('x', 3), ('y', 4), ('facing', 'right'),
    ('facing_raw', 12), ('x', True)])
def test_wrong_stance_stops(field, value):
    loc = deepcopy(STANCE); loc[field] = value
    review(Session().call(overworld_ready=True, location=loc))


@pytest.mark.parametrize('battle', [{'raw': 1, 'active': True, 'kind': 'wild'}, {'raw': 2, 'active': True, 'kind': 'trainer'},
    {'raw': 0, 'active': False, 'kind': 'unknown'}, {'raw': None, 'active': False, 'kind': 'none'}])
def test_battle_or_unknown_never_handled(battle):
    review(Session().call(overworld_ready=True, battle_state=battle))


@pytest.mark.parametrize('cursor', [3, 5, 2])
def test_never_confirms_sell_quit_or_unknown_initial_cursor(cursor):
    s = Session(); s.call(overworld_ready=True); review(s.call(main(cursor=cursor)))


@pytest.mark.parametrize('mutate', [lambda t: put(t, 2, 3, 'NOT '), lambda t: put(t, 2, 7, 'SELL'),
    lambda t: put(t, 1, 3, '▷'), lambda t: put(t, 1, 3, '▶'), lambda t: put(t, 12, 1, ' ¥31999')])
def test_main_labels_duplicates_cursor_and_money_rejected(mutate):
    s = Session(); s.call(overworld_ready=True); t = main(); mutate(t); review(s.call(t))


@pytest.mark.parametrize('mutate', [lambda t: put(t, 5, 4, '▷'), lambda t: put(t, 5, 6, '▶'),
    lambda t: put(t, 6, 4, 'ULTRA BALL'), lambda t: put(t, 11, 5, '   ¥599'),
    lambda t: put(t, 6, 8, 'GREAT BALL')])
def test_goods_must_be_unique_first_great_ball_at_600(mutate):
    s = Session(); s.call(overworld_ready=True); s.call(main()); t = shop(); mutate(t); review(s.call(t))


def test_quantity_same_page_same_frame_or_stale_new_frame_only_wait():
    s = Session(); s.to_quantity(); t = quantity(1)
    assert s.call(t)['available_actions'] == ['up', 'wait']; frame = s.c.last_frame
    assert s.call(deepcopy(t), frame=frame)['available_actions'] == ['wait']
    assert s.call(deepcopy(t))['available_actions'] == ['wait']
    assert s.call(quantity(2))['available_actions'] == ['up', 'wait']


def test_same_frame_conflicting_quantity_is_locked_review():
    s = Session(); s.to_quantity(); s.call(quantity(1)); frame = s.c.last_frame
    assert 'same_frame' in review(s.call(quantity(2), frame=frame))
    assert review(s.call(quantity(2))) == s.c.error


def test_quantity_and_price_redraw_waits_then_increments_once():
    s = Session(); s.to_quantity(); s.call(quantity(1))
    assert s.call(quantity(2, price=600))['available_actions'] == ['wait']
    assert s.call(quantity(1, price=1200))['available_actions'] == ['wait']
    assert s.call(quantity(2))['available_actions'] == ['up', 'wait']


@pytest.mark.parametrize('amount', [599, 1500, 6000, 12000])
def test_wrong_complete_price_after_up_is_review_not_typing(amount):
    s = Session(); s.to_quantity(); s.call(quantity(1)); review(s.call(quantity(2, price=amount)))


def test_partial_quantity_digits_wait_then_one_up():
    s = Session(); s.to_quantity(); q = quantity(1); put(q, 8, 10, '×0 ')
    assert s.call(q)['available_actions'] == ['wait']
    assert s.call(quantity(1))['available_actions'] == ['up', 'wait']


def test_retained_main_and_selected_item_arrows_are_required():
    s = Session(); s.to_quantity(); q = quantity(1); put(q, 1, 1, ' ')
    review(s.call(q))
    w = Session(); w.to_price(); w.call(prefix()); t = confirmation(); put(t, 1, 1, ' ')
    review(w.call(t))


@pytest.mark.parametrize('n,total', [(1, 599), (20, 12000), (0, 0), (99, 59400), (2, 1500)])
def test_unexpected_quantity_or_cost_stops(n, total):
    s = Session(); s.to_quantity(); review(s.call(quantity(n, price=total)))


@pytest.mark.parametrize('mutate', [lambda t: put(t, 5, 4, '▶'), lambda t: put(t, 15, 10, '▶'),
    lambda t: put(t, 8, 10, '×99'), lambda t: put(t, 6, 4, 'POKé BALL ')])
def test_quantity_wrong_cursor_or_item_never_a(mutate):
    s = Session(); s.to_quantity(); t = quantity(1); mutate(t); review(s.call(t))


def test_price_partial_prefix_and_blinking_arrow_wait_then_single_advance():
    s = Session(); s.to_price()
    assert s.call(prefix(partial='GREAT'))['available_actions'] == ['wait']
    assert s.call(prefix(prompt=False))['available_actions'] == ['wait']
    assert s.call(prefix())['available_actions'] == ['a', 'wait']
    assert s.call(prefix(prompt=False))['available_actions'] == ['wait']
    assert s.call(prefix())['available_actions'] == ['wait']
    assert s.call(confirmation())['available_actions'] == ['a', 'wait']


def test_confirmation_tail_without_observed_item_question_rejected():
    s = Session(); s.to_price(); review(s.call(confirmation()))


def test_price_yes_no_can_draw_without_a_and_no_can_move_up_only():
    s = Session(); s.to_price(); s.call(prefix())
    t = confirmation(complete=False); assert s.call(t)['available_actions'] == ['wait']
    put(t, 16, 8, 'Y'); assert s.call(t)['available_actions'] == ['wait']
    assert s.call(confirmation(cursor=10))['available_actions'] == ['up', 'wait']
    assert s.call(confirmation())['available_actions'] == ['a', 'wait']


@pytest.mark.parametrize('mutate', [lambda t: put(t, 16, 10, 'NOT'), lambda t: put(t, 1, 6, 'NO'),
    lambda t: put(t, 15, 9, '▶'), lambda t: put(t, 15, 8, '▷'),
    lambda t: put(t, 16, 8, 'YE '), lambda t: put(t, 1, 16, '¥11999. OK?')])
def test_confirmation_wrong_label_cursor_duplicate_or_total_never_a(mutate):
    s = Session(); s.to_price(); s.call(prefix()); t = confirmation(); mutate(t); review(s.call(t))


def test_purchase_intermediate_add_before_money_is_wait_only():
    s = Session(); s.to_yes(); s.p['inventory'] = deepcopy(s.c.expected['inventory'])
    assert s.call(bought(value=32000))['available_actions'] == ['wait']
    s.p['money'] = 20000
    assert s.call(bought())['available_actions'] == ['a', 'wait']


@pytest.mark.parametrize('change', [lambda s: s.p.update(money=20000),
    lambda s: s.p.update(money=19999), lambda s: s.p['inventory'].append({'item': 3, 'quantity': 19}),
    lambda s: s.p['inventory'].reverse(), lambda s: s.p['party'][0].update(hp=101)])
def test_wrong_transaction_differences_never_acknowledged(change):
    s = Session(); s.to_yes(); change(s); review(s.call(bought()))


def test_visible_receipt_money_mismatch_is_review_even_if_progress_correct():
    s = Session(); s.to_yes(); s.apply_transaction(); review(s.call(bought(value=19999)))


@pytest.mark.parametrize('target', ['money', 'inventory', 'party'])
def test_no_financial_or_party_change_is_allowed_before_yes(target):
    s = Session(); s.to_price()
    if target == 'money': s.p['money'] -= 12000
    elif target == 'inventory': s.p['inventory'].append({'item': 3, 'quantity': 20})
    else: s.p['party'][1]['pp'][0] -= 1
    review(s.call(prefix()))


def test_partial_bought_and_missing_arrow_wait_not_repeat_a():
    s = Session(); s.to_yes(); s.apply_transaction()
    assert s.call(bought(partial='Here you'))['available_actions'] == ['wait']
    assert s.call(bought(prompt=False))['available_actions'] == ['wait']
    assert not s.c.bought_receipt_seen
    assert s.call(bought())['available_actions'] == ['a', 'wait']
    assert s.call(bought(prompt=False))['available_actions'] == ['wait']
    assert s.call(bought())['available_actions'] == ['wait']


@pytest.mark.parametrize('word', ['TOSS', 'What would you', 'I can pay you', 'You can\'t carry', 'Unknown prompt!'])
def test_unknown_or_selling_page_never_pressed(word):
    s = Session(); s.to_yes(); t = bought(partial=word); review(s.call(t))


def test_early_overworld_without_purchase_receipt_does_not_complete():
    s = Session(); s.to_yes(); s.apply_transaction(); review(s.call(overworld_ready=True))


def exit_session():
    s = Session(); s.to_yes(); s.apply_transaction(); s.call(bought()); s.call(shop(20000))
    s.call(main(20000, words=ELSE)); return s


def test_missing_exit_thanks_cannot_fake_complete():
    s = exit_session(); review(s.call(overworld_ready=True))


def test_exit_partial_thanks_then_one_a_then_two_fresh_world_frames():
    s = exit_session()
    assert s.call(thanks(partial='Thank'))['available_actions'] == ['wait']
    assert not s.c.exit_text_seen
    assert s.call(thanks())['available_actions'] == ['a', 'wait']
    assert s.call(thanks())['available_actions'] == ['wait']
    assert s.call(overworld_ready=False)['available_actions'] == ['wait']
    assert s.call(overworld_ready=True)['available_actions'] == ['wait']; old = s.c.last_frame
    assert s.call(frame=old, overworld_ready=True)['available_actions'] == ['wait']
    assert s.call(frame=old + 1, overworld_ready=True)['available_actions'] == ['wait']
    assert s.call(frame=old + 3, overworld_ready=True)['mart_purchase_complete']


def test_different_world_grid_does_not_complete():
    s = exit_session(); s.call(thanks()); t = text_at((1, 1, 'UNKNOWN'), window=False)
    review(s.call(t, overworld_ready=True))


def test_exit_with_wrong_visible_money_does_not_press_a():
    s = exit_session(); review(s.call(thanks(value=19999)))


@pytest.mark.parametrize('field', ['text', 'progress', 'location', 'battle_state'])
def test_explicit_observation_frame_must_match(field):
    s = Session(); t = text_at(window=False); loc = deepcopy(STANCE); battle = deepcopy(NONE)
    packet = {'text': t, 'progress': s.p, 'location': loc, 'battle_state': battle}[field]
    packet['observation_frame'] = 999
    review(s.call(t, location=loc, battle_state=battle, overworld_ready=True))


@pytest.mark.parametrize('x,y', [(0, 14), (19, 14), (1, 15), (1, 13)])
def test_unknown_text_on_border_or_between_lines_is_not_ignored(x, y):
    s = Session(); s.to_price(); t = prefix(); put(t, x, y, 'X'); review(s.call(t))


def test_initial_false_window_with_menu_labels_never_talks_again():
    t = text_at((2, 1, 'BUY'), window=False)
    review(Session().call(t, overworld_ready=True))


@pytest.mark.parametrize('word', ['Delete', 'YES', 'NO', 'TOSS', 'UNKNOWN', '!', '×20'])
def test_initial_background_cannot_be_poisoned_with_any_printed_ui(word):
    s = Session(); t = text_at((0, 0, word), window=False)
    review(s.call(t, overworld_ready=True)); assert s.c.initial_world_rows is None


@pytest.mark.parametrize('word', ['YES', 'Delete', 'RELEASE', 'X', '!'])
def test_unknown_font_outside_main_source_mask_never_selects_buy(word):
    s = Session(); s.call(overworld_ready=True); t = main(); put(t, 0, 0, word)
    review(s.call(t)); assert s.c.stage == 'opening'


@pytest.mark.parametrize('word', ['Delete', 'YES', 'RELEASE', '×20'])
def test_unknown_font_outside_shop_source_mask_never_selects_item(word):
    s = Session(); s.call(overworld_ready=True); s.call(main()); t = shop(); put(t, 0, 0, word)
    review(s.call(t)); assert s.c.stage == 'buy_open'


@pytest.mark.parametrize('mutation', [lambda t: put(t, 0, 0, 'Delete'), lambda t: put(t, 8, 10, '×19'),
    lambda t: put(t, 10, 8, 'X'), lambda t: put(t, 0, 0, 'YES'),
    lambda t: put(t, 6, 8, '      '), lambda t: put(t, 2, 3, '  ')])
def test_independent_review_confirmation_counterexamples_are_closed(mutation):
    s = Session(); s.to_price(); s.call(prefix()); t = confirmation(); mutation(t)
    review(s.call(t)); assert not s.c.yes_confirmed


def test_source_tail_can_exist_before_yes_no_box_is_drawn_only_wait():
    s = Session(); s.to_price(); s.call(prefix())
    t = dialogue(quantity(20), 'That will be', '¥12000. OK?')
    assert s.call(t)['available_actions'] == ['wait']; assert not s.c.yes_confirmed
    assert s.call(confirmation())['available_actions'] == ['a', 'wait']


def test_blank_then_stale_quantity_page_never_repeats_up():
    s = Session(); s.to_quantity(); s.call(quantity(1))
    assert s.call(text_at())['available_actions'] == ['wait']
    assert s.call(quantity(1))['available_actions'] == ['wait']
    assert s.call(quantity(2))['available_actions'] == ['up', 'wait']


def test_blank_then_stale_confirmation_never_repeats_buy():
    s = Session(); s.to_yes()
    assert s.call(text_at())['available_actions'] == ['wait']
    assert s.call(confirmation())['available_actions'] == ['wait']
    assert s.c.yes_confirmed and not s.c.bought_receipt_seen


def test_blank_then_older_main_page_is_not_reconfirmed():
    s = Session(); s.call(overworld_ready=True); s.call(main())
    assert s.call(text_at())['available_actions'] == ['wait']
    assert s.call(main())['available_actions'] == ['wait']


def test_hardware_window_false_is_valid_for_full_bg_drawn_menu():
    s = Session(); original = s.call
    s.call = lambda t=None, **kw: original({**t, 'window_visible': False} if t is not None else t, **kw)
    s.to_yes(); s.apply_transaction()
    assert s.call(bought())['available_actions'] == ['a', 'wait']
    assert s.call(shop(20000))['available_actions'] == ['b', 'wait']
    assert s.call(main(20000, words=ELSE))['available_actions'] == ['b', 'wait']
    assert s.call(thanks())['available_actions'] == ['a', 'wait']
    assert s.call(overworld_ready=True)['available_actions'] == ['wait']
    assert s.call(overworld_ready=True)['mart_purchase_complete']


def test_still_visible_hardware_window_never_marks_world_complete():
    s = exit_session(); s.call(thanks())
    assert s.call(text_at(), overworld_ready=True)['available_actions'] == ['wait']
    assert not s.c.complete
    assert s.call(overworld_ready=True)['available_actions'] == ['wait']
    assert s.call(overworld_ready=True)['mart_purchase_complete']


def test_complete_action_requires_remaining_non_selected_source_letters():
    s = Session(); s.to_quantity(); t = quantity(1); put(t, 6, 10, ' ')
    review(s.call(t))


def test_unknown_receipt_overlay_cannot_be_acknowledged():
    s = Session(); s.to_yes(); s.apply_transaction(); t = bought(); put(t, 0, 0, 'YES')
    review(s.call(t)); assert not s.c.bought_receipt_seen


def test_unknown_quit_overlay_does_not_set_exit_receipt():
    s = exit_session(); t = thanks(); put(t, 0, 0, 'YES')
    review(s.call(t)); assert not s.c.exit_text_seen


def test_mutating_four_member_party_or_one_pp_stops():
    p = progress(); p['party'] += [deepcopy(p['party'][0]), deepcopy(p['party'][1])]; p['party_count'] = 4
    s = Session(p); s.call(overworld_ready=True); s.p['party'][3]['pp'][0] -= 1
    review(s.call(main()))


def test_no_direct_runtime_io_or_game_model_memory_dependencies():
    import ast
    import laya_pokemon.mart_purchase as candidate
    source = Path(candidate.__file__).read_text(encoding='utf-8'); tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(name.name in {'math', 're'} for name in node.names)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {'open', 'eval', 'exec', '__import__'}


def test_party_and_inventory_are_not_mutated_by_context():
    s = Session(); before = deepcopy(s.p); t = text_at(window=False); original = deepcopy(t)
    s.call(t, overworld_ready=True); assert s.p == before and t == original
    s.call(main()); assert s.p == before


def test_rollback_after_observed_purchase_is_review():
    s = Session(); original = deepcopy(s.p); s.to_yes(); s.apply_transaction(); s.call(bought(prompt=False))
    s.p = original; review(s.call(bought(value=32000)))


@pytest.mark.parametrize('time', [60.1001, float('inf'), float('nan'), -1])
def test_seconds_budget_and_invalid_clock(time):
    s = Session(); s.call(overworld_ready=True); review(s.call(main(), now=time))


def test_call_wait_budgets_are_bounded_and_locked():
    s = Session(max_calls=2); s.call(overworld_ready=True); s.call(main()); review(s.call(shop()))
    w = Session(max_waits=1); w.call(overworld_ready=True); w.call(text_at())
    assert 'wait_budget' in review(w.call(text_at()))


@pytest.mark.parametrize('kwargs', [{'max_calls': 241}, {'max_seconds': 61}, {'max_waits': 241}, {'max_calls': True}, {'max_seconds': True}])
def test_limits_cannot_expand(kwargs):
    with pytest.raises(ValueError): MartPurchaseController(deepcopy(INTENT), **kwargs)


def test_intent_cannot_be_repurposed_or_changed():
    wrong = deepcopy(INTENT); wrong['quantity'] = 99
    with pytest.raises(ValueError): MartPurchaseController(wrong)
    s = Session(); s.call(overworld_ready=True); s.c.intent['item'] = 4
    assert 'intent' in review(s.call(main()))


def test_fixed_public_source_fixture_proves_stock_price_stance_and_ui():
    path = Path(__file__).parent / 'data/lavender-mart-source-fixture.json'
    data = json.loads(path.read_text(encoding='utf-8')); files = data['files']
    assert data['commit'] == SOURCE_COMMIT
    for name, source in files.items():
        assert source['url'] == f'https://raw.githubusercontent.com/pret/pokered/{SOURCE_COMMIT}/{name}'
        if 'text' in source:
            assert hashlib.sha256(source['text'].encode()).hexdigest() == source['sha256']
        if 'hex' in source:
            assert hashlib.sha256(bytes.fromhex(source['hex'])).hexdigest() == source['sha256']
    assert 'LavenderMartClerkText::\n\tscript_mart GREAT_BALL, SUPER_POTION, REVIVE, ESCAPE_ROPE' in files['data/items/marts.asm']['text']
    assert 'bcd3 600   ; GREAT_BALL' in files['data/items/prices.asm']['text']
    assert 'object_event  0,  5, SPRITE_CLERK, STAY, RIGHT' in files['data/maps/objects/LavenderMart.asm']['text']
    assert data['map']['bottom_left_collision_tile_grid'][5][2] == 0x1A
    assert data['map']['bottom_left_collision_tile_grid'][5][1] == 0x1E
    assert 'tileset Mart,        $18,$19,$1E' in files['data/tilesets/tileset_headers.asm']['text']
    assert 'hlcoord 8, 10' in files['home/list_menu.asm']['text']
    assert 'hlcoord 12, 10' in files['home/list_menu.asm']['text']
    assert 'hlcoord 14, 7\n\tlb bc, 8, 15' in files['engine/events/pokemart.asm']['text']
    assert 'ld [hli], a ; store item ID' in files['engine/items/inventory.asm']['text']
