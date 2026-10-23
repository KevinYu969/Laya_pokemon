"""固定來源與實測CUT版面的合成TM11測試；不載入ROM、模型或模擬器。"""
from copy import deepcopy

import pytest

from laya_pokemon.teach_bubblebeam import (
    BubbleBeamController, INTENT, BEFORE_MOVES, AFTER_MOVES, SOURCE_COMMIT,
    MAX_TEXT_WAITS, MAX_BAG_REQUESTS, MAX_CONTEXTS,
)
from laya_pokemon.team_strategy import reference
from tests.test_battle import text_at


def progress():
    """比照13段恢復後progress；背包TM11第四項，尼多力諾第二位。"""
    return {'party_read_valid': True,
            'inventory': [{'item': item, 'quantity': qty} for item, qty in
                          [(4, 6), (234, 1), (42, 1), (211, 1), (49, 1), (63, 1), (228, 1), (196, 1), (224, 1)]],
            'party': [
                {'species': 35, 'species_name': 'FEAROW', 'level': 22, 'hp': 70, 'max_hp': 70,
                 'exp': 11599, 'status': 0, 'moves': [64, 45, 43, 31], 'pp': [35, 40, 30, 20]},
                {'species': 167, 'species_name': 'NIDORINO', 'level': 25, 'hp': 76, 'max_hp': 76,
                 'exp': 12478, 'status': 0, 'moves': list(BEFORE_MOVES), 'pp': [30, 35, 25, 35]},
                {'species': 9, 'species_name': 'IVYSAUR', 'level': 28, 'hp': 79, 'max_hp': 79,
                 'exp': 19331, 'status': 0, 'moves': [77, 15, 73, 22], 'pp': [35, 30, 10, 10]}]}


START = text_at((13, 2, 'POKéDEX'), (13, 4, 'POKéMON'), (12, 6, '▶ITEM'))
USE = text_at((14, 11, '▶USE'), (15, 13, 'TOSS'))
TEACH = text_at((1, 14, 'Teach BUBBLEBEAM'), (1, 16, 'to a POKéMON?'),
                (15, 8, '▶YES'), (16, 10, 'NO'))
PARTY = text_at((3, 0, 'FEAROW'), (0, 1, '▶'), (12, 1, 'NOT ABLE'),
                (3, 2, 'NIDORINO'), (12, 3, 'ABLE'),
                (3, 4, 'IVYSAUR'), (12, 5, 'NOT ABLE'),
                (14,0,'22'), (14,2,'25'), (14,4,'28'),
                (1, 14, 'Use TM on which'), (1, 16, 'POKéMON?'))
DELETE = text_at((1, 13, 'Delete an older'), (1, 14, 'move to make room'),
                 (1, 16, 'for BUBBLEBEAM?'), (15, 8, '▶YES'), (16, 10, 'NO'))
FORGET = text_at((6, 8, 'LEER'), (5, 8, '▶'), (6, 9, 'TACKLE'),
                 (6, 10, 'HORN ATTACK'), (6, 11, 'POISON STING'),
                 (1, 14, 'Which move should'), (1, 16, 'be forgotten?'))
LEARNED = text_at((1, 14, 'NIDORINO learned'), (1, 16, 'BUBBLEBEAM!'))
LABELS = {4: 'POKé BALL', 234: 'TM34', 42: 'HELIX FOSSIL', 211: 'TM11', 49: 'NUGGET',
          63: 'S.S.TICKET', 228: 'TM28', 196: 'HM01', 224: 'TM24'}


def bag(state, offset=0, cursor=0):
    """實測背包名字x6/y4,6,8,10；最後一列預覽，游標只能前三列。"""
    entries = [(12, 14, 'EXIT'), (5, 4 + cursor * 2, '▶')]
    for i in range(4):
        if offset + i == len(state['inventory']):
            entries.append((6, 4 + i * 2, 'CANCEL'))
            break
        item = state['inventory'][offset + i]
        y = 4 + i * 2
        entries.append((6, y, LABELS[item['item']]))
        if item['item'] not in {42, 63, 196}:
            entries.append((14, y + 1, f'×{item["quantity"]:2d}'))
    return text_at(*entries)


def controller():
    return BubbleBeamController(deepcopy(INTENT))


def to_dialogue(c, p):
    assert c.context(text_at(), p, overworld_ready=True)['available_actions'] == ['start', 'wait']
    assert c.context(START, p)['menu_label'] == 'ITEM'
    for offset, cursor in [(0, 0), (0, 1), (0, 2)]:
        result = c.context(bag(p, offset, cursor), p)
        assert result['available_actions'] == ['down', 'wait'], result
    result = c.context(bag(p, 1, 2), p)
    assert result['menu_label'] == 'TM11' and result['available_actions'] == ['a', 'wait']
    assert c.context(USE, p)['menu_label'] == 'USE'


def to_learning(c, p):
    to_dialogue(c, p)
    for text in [text_at((1, 14, 'Booted up a TM!')),
                 text_at((1, 14, 'It contained'), (1, 16, 'BUBBLEBEAM!')), TEACH]:
        result = c.context(text, p)
        assert result['available_actions'] == ['a', 'wait'], result
    assert c.context(PARTY, p)['objective'] == 'Move DOWN.'
    chosen = deepcopy(PARTY)
    chosen['cells'][1][0], chosen['cells'][3][0] = ' ', '▶'
    assert c.context(chosen, p)['available_actions'] == ['a', 'wait']
    for text in [text_at((1, 14, 'NIDORINO is'), (1, 16, 'trying to learn'), (18, 17, '▼')),
                 text_at((1, 14, 'BUBBLEBEAM!'), (18, 16, '▼')),
                 text_at((1, 14, 'But, NIDORINO'), (1, 16, "can't learn more"), (18, 17, '▼')),
                 text_at((1, 14, 'than 4 moves!'))]:
        result = c.context(text, p)
        assert result['available_actions'] == ['a', 'wait'], result


def to_selected(c, p):
    to_learning(c, p)
    assert c.context(DELETE, p)['menu_label'] == 'YES'
    result = c.context(FORGET, p)
    assert result['available_actions'] == ['a', 'wait'] and result['forgotten_move'] == 43


def install_move(p):
    p['party'][1]['moves'] = list(AFTER_MOVES)
    p['party'][1]['pp'][0] = 20


def consume(p):
    index = next(i for i, x in enumerate(p['inventory']) if x['item'] == 211)
    p['inventory'][index]['quantity'] -= 1
    if p['inventory'][index]['quantity'] == 0:
        p['inventory'].pop(index)


def test_real_teach_yes_no_over_bag_background_keeps_unique_menu_contract():
    c,p=controller(),progress()
    to_dialogue(c,p)
    c.context(text_at((1,14,'Booted up a TM!')),p)
    c.context(text_at((1,14,'It contained'),(1,16,'BUBBLEBEAM!')),p)
    real=deepcopy(TEACH)
    for x,y,label in [(6,4,'TM34'),(6,6,'HELIX FOSSIL'),(5,8,'▷TM11'),(6,10,'NUGGET')]:
        for i,char in enumerate(label):real['cells'][y][x+i]=char
    result=c.context(real,p)
    assert result['available_actions']==['a','wait']
    assert result['menu_label']=='YES'


def test_tm_party_requires_level_as_well_as_name_slot():
    c,p=controller(),progress()
    to_dialogue(c,p)
    for t in [text_at((1,14,'Booted up a TM!')),text_at((1,14,'It contained'),(1,16,'BUBBLEBEAM!')),TEACH]:
        c.context(t,p)
    wrong=deepcopy(PARTY)
    wrong['cells'][2][14:16]=list('99')
    assert c.context(wrong,p)['review_reason']=='bubblebeam_tm_party_name_or_layout_not_verified'


def test_actual_single_tile_cant_contraction_is_bounded_partial_text():
    c,p=controller(),progress()
    to_learning(c,p)
    real=text_at((1,14,'But, NIDORINO'),(1,16,'can'))
    real['cells'][16][4]="'t"
    real['cells'][16][5:8]=list(' le')
    result=c.context(real,p)
    assert result['available_actions']==['wait']
    assert result['phase']!='campaign_review'


@pytest.mark.parametrize('row,cell',[(10,"'t"),(16,'XX'),(16,"'z")])
def test_unverified_compound_tiles_remain_invalid(row,cell):
    c,p=controller(),progress()
    text=text_at();text['cells'][row][4]=cell
    assert c.context(text,p,overworld_ready=True)['review_reason']=='bubblebeam_visible_cells_invalid'


def test_fourth_member_not_able_clipped_by_delete_box_is_verified_background(monkeypatch):
    import sys
    c,p=controller(),progress()
    p['party'].append({'species':102,'species_name':'EEVEE','level':25,'hp':63,'max_hp':63,
                       'status':0,'exp':15625,'moves':[33,28,0,0],'pp':[35,15,0,0]})
    layout=deepcopy(PARTY)
    for x,y,label in [(3,6,'EEVEE'),(14,6,'25'),(12,7,'NOT ABLE')]:
        for i,char in enumerate(label):layout['cells'][y][x+i]=char
    monkeypatch.setattr(sys.modules[__name__],'PARTY',layout)
    to_learning(c,p)
    page=deepcopy(DELETE)
    page['cells'][7][12:14]=list('NO')
    assert c.context(page,p)['menu_label']=='YES'


def test_duplicate_no_outside_verified_party_residue_still_stops():
    c,p=controller(),progress();to_learning(c,p)
    wrong=deepcopy(DELETE);wrong['cells'][0][0:2]=list('NO')
    assert c.context(wrong,p)['review_reason']=='bubblebeam_yes_no_layout_not_verified'


def test_fixed_source_move_id_tm_compatibility_and_power_pp():
    r = reference()
    assert r['source_commit'] == SOURCE_COMMIT
    assert 'BUBBLEBEAM' in r['species']['NIDORINO']['tmhm']
    assert 'DIG' not in r['species']['NIDORINO']['tmhm']
    assert (r['moves']['BUBBLEBEAM']['id'], r['moves']['BUBBLEBEAM']['power'],
            r['moves']['BUBBLEBEAM']['type'], r['moves']['BUBBLEBEAM']['pp']) == (61, 65, 'WATER', 20)


@pytest.mark.parametrize('key,value', [('kind', 'teach_dig'), ('species', 7), ('item', 228),
                                      ('move', 91), ('replace_move', 30), ('item', True)])
def test_explicit_intent_is_bounded_and_not_generic(key, value):
    intent = deepcopy(INTENT)
    intent[key] = value
    with pytest.raises(ValueError):
        BubbleBeamController(intent)


def test_full_sequence_protects_three_moves_and_consumes_only_tm11():
    c, p = controller(), progress()
    before = deepcopy(p)
    to_selected(c, p)
    assert p == before  # 控制器從未改傳入資料。
    for text in [text_at((1, 14, '1, 2 and... Poof!')),
                 text_at((1, 14, 'NIDORINO forgot'), (1, 16, 'LEER!')),
                 text_at((0, 3, '▷'), (1, 14, 'And...'))]:
        assert c.context(text, p)['available_actions'] == ['a', 'wait']
    install_move(p)
    assert c.context(LEARNED, p)['available_actions'] == ['a', 'wait']
    consume(p)
    assert c.context(bag(p), p)['available_actions'] == ['b', 'wait']
    assert c.context(START, p)['available_actions'] == ['b', 'wait']
    result = c.context(text_at(), p, overworld_ready=True)
    assert result['tm_teaching_complete'] and result['moves_verified'] == AFTER_MOVES
    assert result['tm_consumed'] == 211 and result['tm_quantity_used'] == 1
    assert p['party'][0] == before['party'][0] and p['party'][2] == before['party'][2]
    assert p['party'][1]['moves'][1:] == before['party'][1]['moves'][1:]


def test_tm11_fourth_bag_row_is_preview_and_never_confirmed_early():
    c, p = controller(), progress()
    c.context(text_at(), p, overworld_ready=True)
    c.context(START, p)
    result = c.context(bag(p, 0, 2), p)
    assert result['bag_tm11_inventory_index'] == 3 and result['bag_cursor_inventory_index'] == 2
    assert result['available_actions'] == ['down', 'wait']
    assert c.context(bag(p, 1, 2), p)['menu_label'] == 'TM11'


@pytest.mark.parametrize('mutate,reason', [
    (lambda p: p.update(party_read_valid=False), 'bubblebeam_party_not_verified'),
    (lambda p: p['party'][1].update(species=7), 'bubblebeam_unique_target_not_verified'),
    (lambda p: p['party'][1].update(moves=AFTER_MOVES), 'bubblebeam_initial_four_moves_not_supported'),
    (lambda p: p['party'][1].update(moves=[43, 33, 0, 40]), 'bubblebeam_initial_four_moves_not_supported'),
    (lambda p: p.update(inventory=[x for x in p['inventory'] if x['item'] != 211]), 'bubblebeam_tm11_missing'),
    (lambda p: p['inventory'][3].update(quantity=0), 'bubblebeam_inventory_not_verified'),
    (lambda p: p['inventory'].append(deepcopy(p['inventory'][3])), 'bubblebeam_inventory_not_verified'),
])
def test_initial_preconditions_fail_before_any_button(mutate, reason):
    p = progress()
    mutate(p)
    result = controller().context(text_at(), p, overworld_ready=True)
    assert result['review_reason'] == reason and result['available_actions'] == ['wait']


def test_nonbattle_and_explicit_overworld_are_required():
    p = progress()
    assert controller().context(text_at(), p)['review_reason'] == 'bubblebeam_initial_overworld_not_verified'
    assert controller().context(text_at(), p, overworld_ready=True, battle_active=True)['review_reason'] == 'bubblebeam_requires_verified_nonbattle'


@pytest.mark.parametrize('bad,reason', [
    (lambda t: t['cells'][4].__setitem__(slice(6, 19), list('ULTRA BALL   ')), 'bubblebeam_bag_label_not_verified'),
    (lambda t: t['cells'][5].__setitem__(slice(14, 18), list('× 5 ')), 'bubblebeam_bag_quantity_not_verified'),
    (lambda t: t['cells'][6].__setitem__(slice(6, 19), list('TM11         ')), 'bubblebeam_bag_order_not_verified'),
    (lambda t: t['cells'][6].__setitem__(5, '▷'), 'bubblebeam_bag_cursor_not_verified'),
])
def test_unverified_bag_cannot_scroll_or_select(bad, reason):
    c, p = controller(), progress()
    c.context(text_at(), p, overworld_ready=True)
    c.context(START, p)
    text = bag(p)
    bad(text)
    result = c.context(text, p)
    assert result['review_reason'] == reason and result['available_actions'] == ['wait']


def test_scroll_stall_and_total_down_limits_are_bounded():
    c, p = controller(), progress()
    c.context(text_at(), p, overworld_ready=True)
    c.context(START, p)
    for _ in range(3):
        assert c.context(bag(p), p)['available_actions'] == ['down', 'wait']
    assert c.context(bag(p), p)['review_reason'] == 'bubblebeam_bag_scroll_limit'
    c = controller()
    c.context(text_at(), p, overworld_ready=True)
    c.context(START, p)
    c.bag_requests = MAX_BAG_REQUESTS
    assert c.context(bag(p), p)['review_reason'] == 'bubblebeam_bag_scroll_limit'


@pytest.mark.parametrize('phrase', ['Booted', 'Booted up a TM', 'It contained', 'It contained BUB'])
def test_known_tm_printing_prefix_waits_without_confirm(phrase):
    c, p = controller(), progress()
    to_dialogue(c, p)
    result = c.context(text_at((0, 3, '▷'), (1, 14, phrase)), p)
    assert result['available_actions'] == ['wait']
    assert c.context(text_at((1, 14, 'It contained'), (1, 16, 'BUBBLEBEAM!')), p)['available_actions'] == ['a', 'wait']


def test_partial_delete_lock_waits_until_correct_named_choices():
    c, p = controller(), progress()
    to_learning(c, p)
    for word in ['D', 'Delete', 'Delete an older', 'move to make room', 'for BUBBLEBEAM?']:
        assert c.context(text_at((0, 3, '▷'), (1, 14, word)), p)['available_actions'] == ['wait']
    final = text_at((1, 14, 'for BUBBLEBEAM?'), (15, 8, '▶YES'), (16, 10, 'NO'))
    assert c.context(final, p)['menu_label'] == 'YES'


def test_wrapped_delete_full_first_page_needs_a_then_suffix_yes():
    c, p = controller(), progress()
    to_learning(c, p)
    first = text_at((1, 14, 'Delete an older'), (1, 16, 'move to make room'), (18, 17, '▼'))
    assert c.context(first, p)['available_actions'] == ['a', 'wait']
    final = text_at((1, 14, 'for BUBBLEBEAM?'), (15, 8, '▶YES'), (16, 10, 'NO'))
    assert c.context(final, p)['menu_label'] == 'YES'


def test_partial_budget_does_not_reset_as_letters_progress():
    c, p = controller(), progress()
    to_learning(c, p)
    for i in range(MAX_TEXT_WAITS):
        assert c.context(text_at((1, 14, 'Delete' if i < 2 else 'Delete an older')), p)['safe_wait_count'] == i + 1
    assert c.context(text_at((1, 14, 'Delete')), p)['review_reason'] == 'bubblebeam_known_text_wait_exhausted'


def test_forget_question_printing_with_stale_hud_waits_instead_of_reading_false_move_rows():
    c, p = controller(), progress()
    to_learning(c, p)
    c.context(DELETE, p)
    partial = text_at((10, 7, 'NIDORINO'), (14, 8, '25'), (10, 10, '76/76'), (1, 14, 'Which m'))
    assert c.context(partial, p)['available_actions'] == ['wait']
    assert c.context(FORGET, p)['forgotten_move'] == 43


def test_forget_fixed_single_spaced_four_rows_moves_up_to_leer_only():
    c, p = controller(), progress()
    to_learning(c, p)
    c.context(DELETE, p)
    wrong_cursor = deepcopy(FORGET)
    wrong_cursor['cells'][8][5], wrong_cursor['cells'][10][5] = ' ', '▶'
    assert c.context(wrong_cursor, p)['available_actions'] == ['up', 'wait']
    assert c.context(FORGET, p)['available_actions'] == ['a', 'wait']


@pytest.mark.parametrize('mutate', [
    lambda t: t['cells'][9].__setitem__(slice(6, 20), list('HORN ATTACK   ')),
    lambda t: t['cells'][8].__setitem__(5, ' '),
    lambda t: t['cells'][9].__setitem__(5, '▶'),
])
def test_forget_missing_wrong_or_duplicate_cursor_never_confirms(mutate):
    c, p = controller(), progress()
    to_learning(c, p)
    c.context(DELETE, p)
    t = deepcopy(FORGET)
    mutate(t)
    result = c.context(t, p)
    assert result['phase'] == 'campaign_review' and result['available_actions'] == ['wait']


@pytest.mark.parametrize('phrase', ['1, 2 and... Poof!', 'NIDORINO forgot LEER!', 'And...'])
def test_full_poof_forgot_and_pages_require_a_and_do_not_wait_forever(phrase):
    c, p = controller(), progress()
    to_selected(c, p)
    t = text_at((1, 14, phrase)) if len(phrase) <= 19 else text_at((1, 14, 'NIDORINO forgot'), (1, 16, 'LEER!'))
    result = c.context(t, p)
    assert result['available_actions'] == ['a', 'wait']


def test_partial_forgot_waits_but_wrong_forgot_move_is_rejected_first():
    c, p = controller(), progress()
    to_selected(c, p)
    for word in ['NIDORINO for', 'NIDORINO forgot', 'NIDORINO forgot L']:
        assert c.context(text_at((1, 14, word)), p)['available_actions'] == ['wait']
    result = c.context(text_at((1, 14, 'NIDORINO forgot'), (1, 16, 'HORN ATTACK!')), p)
    assert result['review_reason'] == 'bubblebeam_forgot_wrong_move_or_learner'


@pytest.mark.parametrize('phrase', ['A mysterious error', 'It contained DIG!', 'Abandon learning',
                                   'NIDORINO did not', 'IVYSAUR learned CUT!'])
def test_unknown_and_wrong_machine_pages_latch_review(phrase):
    c, p = controller(), progress()
    to_dialogue(c, p)
    t = text_at((1, 14, phrase)) if len(phrase) <= 19 else text_at((1, 14, phrase[:19]), (1, 16, phrase[19:]))
    result = c.context(t, p)
    assert result['phase'] == 'campaign_review' and result['available_actions'] == ['wait']
    assert c.context(text_at((1, 14, 'Booted')), p) == result


@pytest.mark.parametrize('mutate,reason', [
    (lambda p: p['party'][0].update(hp=69), 'bubblebeam_other_party_changed_unexpectedly'),
    (lambda p: p['party'][2]['moves'].__setitem__(0, 61), 'bubblebeam_other_party_changed_unexpectedly'),
    (lambda p: p['party'][1]['moves'].__setitem__(2, 61), 'bubblebeam_unexpected_move_replacement'),
    (lambda p: p['party'][1].update(exp=12479), 'bubblebeam_target_nonmove_data_changed'),
    (lambda p: p['inventory'][0].update(quantity=5), 'bubblebeam_inventory_change_not_only_one_tm11'),
    (lambda p: consume(p), 'bubblebeam_tm11_consumed_before_verified_learning'),
])
def test_fingerprint_errors_precede_known_partial_wait(mutate, reason):
    c, p = controller(), progress()
    to_learning(c, p)
    mutate(p)
    result = c.context(text_at((1, 14, 'Delete')), p)
    assert result['review_reason'] == reason and result['available_actions'] == ['wait']


def test_tm_requires_consumption_and_correct_new_pp_before_complete():
    c, p = controller(), progress()
    to_selected(c, p)
    install_move(p)
    assert c.context(LEARNED, p)['available_actions'] == ['a', 'wait']
    result = c.context(bag(p), p)
    assert result['review_reason'] == 'bubblebeam_tm11_not_consumed_after_learning'
    c, p = controller(), progress()
    to_selected(c, p)
    p['party'][1]['moves'] = list(AFTER_MOVES)
    assert c.context(text_at((1, 14, 'And...')), p)['review_reason'] == 'bubblebeam_pp_change_not_verified'


def test_exact_one_tm_consumption_supports_quantity_two_and_rejects_extra_loss():
    c, p = controller(), progress()
    p['inventory'][3]['quantity'] = 2
    to_selected(c, p)
    install_move(p)
    c.context(LEARNED, p)
    consume(p)
    assert c.context(text_at(), p, overworld_ready=True)['tm_teaching_complete']
    c, p = controller(), progress()
    p['inventory'][3]['quantity'] = 2
    to_selected(c, p)
    install_move(p)
    c.context(LEARNED, p)
    consume(p)
    consume(p)
    assert c.context(text_at(), p, overworld_ready=True)['review_reason'] == 'bubblebeam_inventory_change_not_only_one_tm11'


def test_unverified_learner_ability_and_wrong_name_stop():
    for mutate in [lambda t: t['cells'][3].__setitem__(slice(12, 20), list('NOT ABLE')),
                   lambda t: t['cells'][2].__setitem__(slice(3, 20), list('NIDOKING         '))]:
        c, p = controller(), progress()
        to_dialogue(c, p)
        c.context(text_at((1, 14, 'It contained'), (1, 16, 'BUBBLEBEAM!')), p)
        c.context(TEACH, p)
        t = deepcopy(PARTY)
        mutate(t)
        assert c.context(t, p)['phase'] == 'campaign_review'


def test_confirmed_question_uses_only_real_active_cursor_not_static_triangle():
    c, p = controller(), progress()
    to_learning(c, p)
    t = deepcopy(DELETE)
    t['cells'][0][0] = '▷'
    assert c.context(t, p)['menu_label'] == 'YES'


def test_bare_unknown_yes_no_and_forget_before_delete_are_rejected():
    c, p = controller(), progress()
    to_dialogue(c, p)
    t = text_at((15, 8, '▶YES'), (16, 10, 'NO'))
    assert c.context(t, p)['review_reason'] == 'bubblebeam_unknown_yes_no_question'
    c, p = controller(), progress()
    to_learning(c, p)
    assert c.context(FORGET, p)['phase'] == 'campaign_review'


def test_total_context_limit_and_unknown_initial_blank_do_not_spin():
    c, p = controller(), progress()
    c.calls = MAX_CONTEXTS
    assert c.context(text_at(), p, overworld_ready=True)['review_reason'] == 'bubblebeam_transaction_context_limit'
    c = controller()
    c.context(text_at(), p, overworld_ready=True)
    assert c.context(text_at(), p)['phase'] == 'campaign_review'


def test_delete_partial_never_authorizes_forget_before_yes_was_actually_selected():
    c, p = controller(), progress()
    to_learning(c, p)
    assert c.context(text_at((1, 14, 'Delete')), p)['available_actions'] == ['wait']
    assert c.context(FORGET, p)['review_reason'] == 'bubblebeam_forget_without_verified_delete_yes'


@pytest.mark.parametrize('wrong', ['for DIG?', 'for CUT?', 'Purchase item?', 'Release NIDORINO?'])
def test_prior_delete_page_does_not_authorize_wrong_named_or_unknown_yes_no(wrong):
    c, p = controller(), progress()
    to_learning(c, p)
    first = text_at((1, 14, 'Delete an older'), (1, 16, 'move to make room'), (18, 17, '▼'))
    assert c.context(first, p)['available_actions'] == ['a', 'wait']
    final = text_at((1, 14, wrong), (15, 8, '▶YES'), (16, 10, 'NO'))
    result = c.context(final, p)
    assert result['review_reason'] == 'bubblebeam_question_content_not_verified'


def test_full_wrong_move_delete_with_yes_no_cannot_pass_prefix_check():
    c, p = controller(), progress()
    to_learning(c, p)
    wrong = text_at((1, 13, 'Delete an older'), (1, 14, 'move to make room'),
                    (1, 16, 'for DIG?'), (15, 8, '▶YES'), (16, 10, 'NO'))
    result = c.context(wrong, p)
    assert result['phase'] == 'campaign_review' and result['available_actions'] == ['wait']


def test_complete_requires_named_learned_receipt_and_no_unknown_dialogue():
    c, p = controller(), progress()
    to_selected(c, p)
    install_move(p)
    consume(p)
    assert c.context(text_at(), p, overworld_ready=True)['phase'] == 'campaign_review'
    c, p = controller(), progress()
    to_selected(c, p)
    install_move(p)
    c.context(LEARNED, p)
    consume(p)
    result = c.context(text_at((1, 14, 'A mysterious error')), p, overworld_ready=True)
    assert result['review_reason'] == 'bubblebeam_overworld_completion_conflicts_with_menu'


def test_expected_new_move_arriving_before_forget_confirmation_is_rejected():
    c, p = controller(), progress()
    to_learning(c, p)
    install_move(p)
    assert c.context(text_at((1, 14, 'Delete')), p)['review_reason'] == 'bubblebeam_move_changed_before_verified_forget'


def test_partial_learned_waits_but_actual_expected_move_and_pp_are_still_checked():
    c, p = controller(), progress()
    to_selected(c, p)
    install_move(p)
    assert c.context(text_at((1, 14, 'NIDORINO learned')), p)['available_actions'] == ['wait']
    p['party'][1]['pp'][2] -= 1
    assert c.context(text_at((1, 14, 'NIDORINO learned')), p)['review_reason'] == 'bubblebeam_pp_change_not_verified'


@pytest.mark.parametrize('no_position', [(1, 0), (16, 6), (16, 8), (15, 10)])
def test_yes_no_source_geometry_is_required_before_irreversible_delete(no_position):
    c, p = controller(), progress()
    to_learning(c, p)
    t = text_at((1, 13, 'Delete an older'), (1, 14, 'move to make room'),
                (1, 16, 'for BUBBLEBEAM?'), (15, 8, '▶YES'), (*no_position, 'NO'))
    result = c.context(t, p)
    assert result['phase'] == 'campaign_review' and not c.delete_confirmed


def test_yes_no_duplicate_no_is_rejected_and_no_cursor_moves_up_before_yes():
    c, p = controller(), progress()
    to_learning(c, p)
    t = deepcopy(DELETE)
    t['cells'][0][1:3] = list('NO')
    assert c.context(t, p)['review_reason'] == 'bubblebeam_yes_no_layout_not_verified'
    c, p = controller(), progress()
    to_learning(c, p)
    t = deepcopy(DELETE)
    t['cells'][8][15], t['cells'][10][15] = ' ', '▶'
    assert c.context(t, p)['available_actions'] == ['up', 'wait']
    assert not c.delete_confirmed
    assert c.context(DELETE, p)['available_actions'] == ['a', 'wait'] and c.delete_confirmed


@pytest.mark.parametrize('punctuation,cursor', [('', True), ('!', True), ('', False)])
def test_learned_receipt_needs_complete_punctuation_without_active_menu_cursor(punctuation, cursor):
    c, p = controller(), progress()
    to_selected(c, p)
    install_move(p)
    entries = [(1, 14, 'NIDORINO learned'), (1, 16, 'BUBBLEBEAM' + punctuation)]
    if cursor:
        entries.append((0, 0, '▶'))
    result = c.context(text_at(*entries), p)
    assert result['available_actions'] == ['wait'] and not c.seen_learned
    consume(p)
    assert not c.context(text_at(), p, overworld_ready=True).get('tm_teaching_complete')


@pytest.mark.parametrize('phrase', ['1, 2 and... Poof!', 'And...'])
def test_complete_known_forget_dialogue_with_unrelated_active_cursor_is_rejected(phrase):
    c, p = controller(), progress()
    to_selected(c, p)
    result = c.context(text_at((0, 0, '▶'), (1, 14, phrase)), p)
    assert result['review_reason'] == 'bubblebeam_dialogue_has_active_cursor'


def test_verified_normal_up_scrolling_can_return_from_previous_hm01_bag_position():
    c, p = controller(), progress()
    c.context(text_at(), p, overworld_ready=True)
    c.context(START, p)
    # 背包上方被捲走，但每頁的連續ID、數量及offset仍與唯讀inventory完全吻合。
    for offset, cursor in [(5, 2), (5, 1), (5, 0), (4, 0)]:
        result = c.context(bag(p, offset, cursor), p)
        assert result['available_actions'] == ['up', 'wait'] and 'a' not in result['available_actions']
    result = c.context(bag(p, 3, 0), p)
    assert result['menu_label'] == 'TM11' and result['available_actions'] == ['a', 'wait']


def test_up_scroll_stall_is_bounded_and_opposite_movement_is_rejected():
    c, p = controller(), progress()
    c.context(text_at(), p, overworld_ready=True)
    c.context(START, p)
    for _ in range(3):
        assert c.context(bag(p, 5, 2), p)['available_actions'] == ['up', 'wait']
    assert c.context(bag(p, 5, 2), p)['review_reason'] == 'bubblebeam_bag_scroll_limit'
    c, p = controller(), progress()
    c.context(text_at(), p, overworld_ready=True)
    c.context(START, p)
    assert c.context(bag(p, 5, 1), p)['available_actions'] == ['up', 'wait']
    assert c.context(bag(p, 5, 2), p)['review_reason'] == 'bubblebeam_bag_cursor_moved_opposite_to_verified_request'
