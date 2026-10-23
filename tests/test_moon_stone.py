"""正常石進化的來源／實測選單合成契約；不讀ROM或存檔、不按鍵。"""
from copy import deepcopy

import pytest

from laya_pokemon.moon_stone import MoonStoneController, INTENT
from tests.test_battle import text_at


START = text_at((12, 2, 'POKéDEX'), (12, 4, 'POKéMON'), (11, 6, '▶ITEM'))
LABELS = {4: 'POKé BALL', 234: 'TM34', 10: 'MOON STONE', 42: 'HELIX FOSSIL',
          196: 'HM01', 49: 'NUGGET'}


def progress(*, stone_quantity=1, target_index=1, party_size=3, level=26):
    others = [(35, 'FEAROW'), (9, 'IVYSAUR'), (102, 'EEVEE'),
              (154, 'VENUSAUR'), (5, 'SPEAROW')]
    party = [{'species': s, 'species_name': name, 'level': 25, 'exp': 15625,
              'hp': 70, 'max_hp': 70, 'status': 0,
              'moves': [33, 45, 43, 31], 'pp': [35, 40, 30, 20]}
             for s, name in others[:party_size - 1]]
    party.insert(target_index, {'species': 167, 'species_name': 'NIDORINO', 'level': level,
                               'exp': 17481, 'hp': 63, 'max_hp': 79, 'status': 0,
                               'moves': [61, 33, 30, 40], 'pp': [18, 35, 25, 35]})
    return {'party_read_valid': True, 'party_count': len(party), 'party': party,
            'inventory': [{'item': i, 'quantity': q}
                          for i, q in [(4, 6), (234, 1), (10, stone_quantity), (42, 1), (196, 1)]]}


def bag(p, *, offset=0, cursor=0):
    entries = [(12, 14, 'EXIT'), (5, 4 + 2 * cursor, '▶')]
    for row in range(4):
        index, y = offset + row, 4 + 2 * row
        if index == len(p['inventory']):
            entries.append((6, y, 'CANCEL')); break
        if index > len(p['inventory']):
            break
        item = p['inventory'][index]
        entries.append((6, y, LABELS[item['item']]))
        if item['item'] not in {42, 196}:
            entries.append((14, y + 1, f'×{item["quantity"]:2d}'))
    return text_at(*entries)


def use_screen(p, *, cursor=11, background=True):
    t = bag(p, cursor=2) if background else text_at()
    if background:
        t['cells'][8][5] = '▷'
    for x, y, label in [(15, 11, 'USE'), (15, 13, 'TOSS'), (14, cursor, '▶')]:
        for i, char in enumerate(label):
            t['cells'][y][x + i] = char
    return t


def party_screen(p, *, cursor=0, inactive=False):
    entries = [(1, 14, 'Use item on which'), (1, 16, 'POKéMON?')]
    for i, mon in enumerate(p['party']):
        entries += [(3, 2 * i, mon['species_name']), (13, 2 * i, f'{mon["level"]:3d}'),
                    (12, 2 * i + 1, 'ABLE' if mon['species'] in {4, 100, 167, 168} else 'NOT ABLE')]
    entries.append((0, 2 * cursor + 1, '▷' if inactive else '▶'))
    return text_at(*entries)


def intro(p=None, *, target=1, background=False):
    t = text_at((1, 14, 'What? NIDORINO'), (1, 16, 'is evolving!'))
    if background:
        t['cells'][:12] = deepcopy(party_screen(p, cursor=target, inactive=True)['cells'][:12])
    return t


EVOLVED = text_at((1, 14, 'NIDORINO evolved'), (1, 16, 'into NIDOKING!'))


class Session:
    def __init__(self, p=None, **limits):
        self.p = p if p is not None else progress()
        self.c = MoonStoneController(deepcopy(INTENT), **limits)
        self.now = 0

    def call(self, text=None, **kwargs):
        self.now += 0.1
        return self.c.context(text if text is not None else text_at(), self.p,
                              now=kwargs.pop('now', self.now), **kwargs)

    def to_party(self):
        assert self.call(overworld_ready=True)['available_actions'] == ['start', 'wait']
        assert self.call(START)['menu_label'] == 'ITEM'
        for cursor in (0, 1):
            assert self.call(bag(self.p, cursor=cursor))['available_actions'] == ['down', 'wait']
        assert self.call(bag(self.p, cursor=2))['menu_label'] == 'MOON STONE'
        assert self.call(use_screen(self.p))['menu_label'] == 'USE'

    def to_evolving(self):
        self.to_party()
        for index in range(self.c.target_index):
            assert self.call(party_screen(self.p, cursor=index))['available_actions'] == ['down', 'wait']
        assert self.call(party_screen(self.p, cursor=self.c.target_index))['available_actions'] == ['a', 'wait']

    def observe_texts(self):
        assert self.call(intro(self.p, target=self.c.target_index, background=True))['available_actions'] == ['wait']
        assert self.call(EVOLVED)['available_actions'] == ['wait']

    def evolve(self, *, delta=12):
        mon = self.p['party'][self.c.target_index]
        mon.update(species=7, species_name='NIDOKING', hp=mon['hp'] + delta, max_hp=mon['max_hp'] + delta)

    def consume(self):
        stone = next(x for x in self.p['inventory'] if x['item'] == 10)
        stone['quantity'] -= 1
        if stone['quantity'] == 0:
            self.p['inventory'].remove(stone)

    def finish(self):
        assert self.call(bag(self.p))['available_actions'] == ['b', 'wait']
        assert self.call(START)['available_actions'] == ['b', 'wait']
        return self.call(overworld_ready=True)


@pytest.mark.parametrize('target', range(6))
@pytest.mark.parametrize('quantity', [1, 2])
def test_full_normal_sequence_all_six_slots_preserves_moves_and_consumes_one(target, quantity):
    s = Session(progress(stone_quantity=quantity, target_index=target, party_size=6))
    before = deepcopy(s.p)
    s.to_evolving()
    assert s.p == before  # 純控制器沒有改輸入或執行按鍵。
    s.observe_texts()
    s.evolve(delta=20)  # 合法累積stat-exp重算不受單純base差10／11的錯誤上界限制。
    s.consume()
    result = s.finish()
    assert result['moon_stone_complete'] and result['stone_consumed'] == 10
    assert result['stone_quantity_used'] == 1 and result['evolved_to'] == 7
    assert s.p['party'][target]['moves'] == [61, 33, 30, 40]  # 沒有補Thrash37。
    assert s.p['party'][target]['pp'] == before['party'][target]['pp']
    assert all(s.p['party'][i] == before['party'][i] for i in range(6) if i != target)
    assert s.call(overworld_ready=True)['moon_stone_complete']


@pytest.mark.parametrize('mutate', [
    lambda i: i.update(item=211), lambda i: i.update(species=7),
    lambda i: i.update(evolves_to=16), lambda i: i.update(kind='teach_thrash'),
    lambda i: i.update(item=True), lambda i: i.update(extra=True),
])
def test_exact_intent_is_required(mutate):
    intent = deepcopy(INTENT); mutate(intent)
    with pytest.raises(ValueError):
        MoonStoneController(intent)


@pytest.mark.parametrize('kwargs', [{'max_calls': True}, {'max_waits': 0}, {'max_calls': 1001},
                                    {'max_seconds': 61}, {'max_seconds': float('nan')}])
def test_budget_constructor_rejects_invalid_values(kwargs):
    with pytest.raises(ValueError):
        MoonStoneController(INTENT, **kwargs)


@pytest.mark.parametrize('level', [8, 14, 23])
def test_levels_with_exact_nidoking_learnset_entry_stop_before_stone_use(level):
    result = Session(progress(level=level)).call(overworld_ready=True)
    assert result['review_reason'] == 'moon_stone_current_level_would_enter_move_learning'


@pytest.mark.parametrize('mutation,reason', [
    (lambda p: p.update(party_read_valid=False), 'moon_stone_party_not_verified'),
    (lambda p: p.update(party_count=True), 'moon_stone_party_count_invalid'),
    (lambda p: p['party'][1].update(species=7, species_name='NIDOKING'), 'moon_stone_unique_initial_nidorino_required'),
    (lambda p: p['party'][0].update(species=167, species_name='NIDORINO'), 'moon_stone_unique_initial_nidorino_required'),
    (lambda p: p['party'][1].update(species=True), 'moon_stone_party_fingerprint_invalid'),
    (lambda p: p['party'][1].pop('exp'), 'moon_stone_party_fingerprint_invalid'),
    (lambda p: p['party'][1].update(pp=[True, 35, 25, 35]), 'moon_stone_party_fingerprint_invalid'),
    (lambda p: p.update(inventory=[x for x in p['inventory'] if x['item'] != 10]), 'moon_stone_item10_missing'),
    (lambda p: p['inventory'].append({'item': 10, 'quantity': 1}), 'moon_stone_inventory_invalid'),
    (lambda p: p['inventory'][2].update(quantity=0), 'moon_stone_inventory_invalid'),
])
def test_initial_preconditions_stop_without_action(mutation, reason):
    p = progress(); mutation(p)
    result = Session(p).call(overworld_ready=True)
    assert result['review_reason'] == reason and result['available_actions'] == ['wait']


@pytest.mark.parametrize('text', [START, text_at((0, 0, '▶')), text_at((1, 14, 'Unknown dialogue'))])
def test_initial_menu_markers_or_text_cannot_be_treated_as_overworld(text):
    assert Session().call(text, overworld_ready=True)['phase'] == 'campaign_review'


def test_nonbattle_and_ready_must_be_explicit_bools():
    assert Session().call()['review_reason'] == 'moon_stone_initial_overworld_required'
    assert Session().call(overworld_ready=True, battle_active=0)['review_reason'] == 'moon_stone_requires_verified_nonbattle'


def test_start_uses_source_label12_cursor11_and_rejects_old_shifted_fixture():
    s = Session(); s.call(overworld_ready=True)
    old = text_at((13, 2, 'POKéDEX'), (13, 4, 'POKéMON'), (12, 6, '▶ITEM'))
    assert s.call(old)['phase'] == 'campaign_review'


def test_duplicate_start_label_cannot_confirm_item():
    s = Session(); s.call(overworld_ready=True)
    t = deepcopy(START); t['cells'][0][0:4] = list('ITEM')
    assert s.call(t)['review_reason'] == 'moon_stone_start_label_not_unique'


def test_use_toss_real_two_rows_respects_background_and_never_tosses():
    s = Session(); s.to_party()
    # to_party已送一次USE，仍是同畫面時只wait，不重按A。
    assert s.call(use_screen(s.p))['available_actions'] == ['wait']
    s = Session(); s.call(overworld_ready=True); s.call(START)
    for cursor in (0, 1, 2):
        s.call(bag(s.p, cursor=cursor))
    assert s.call(use_screen(s.p, cursor=13))['available_actions'] == ['up', 'wait']
    assert s.call(use_screen(s.p))['available_actions'] == ['a', 'wait']


@pytest.mark.parametrize('change', ['old_use_y10', 'suffix', 'duplicate', 'wrong_active', 'extra_active', 'wrong_inactive'])
def test_use_toss_wrong_fixture_or_ambiguous_labels_never_confirms(change):
    s = Session(); s.call(overworld_ready=True); s.call(START)
    for cursor in (0, 1, 2): s.call(bag(s.p, cursor=cursor))
    t = use_screen(s.p)
    if change == 'old_use_y10':
        t['cells'][11][14:] = list('      '); t['cells'][10][14:18] = list('▶USE')
    elif change == 'suffix': t['cells'][11][18] = 'D'
    elif change == 'duplicate': t['cells'][0][0:3] = list('USE')
    elif change == 'wrong_active': t['cells'][11][14] = ' '; t['cells'][10][14] = '▶'
    elif change == 'extra_active': t['cells'][0][0] = '▶'
    else: t['cells'][8][5] = ' '; t['cells'][6][5] = '▷'
    assert s.call(t)['phase'] == 'campaign_review'


@pytest.mark.parametrize('change', ['name_level_mixed', 'wrong_level', 'wrong_able', 'wrong_target_name', 'extra_name', 'extra_active'])
def test_party_exact_name_level_ability_and_cursor_are_required(change):
    s = Session(); s.to_party(); t = party_screen(s.p, cursor=1)
    if change == 'name_level_mixed': t['cells'][2][12] = '2'
    elif change == 'wrong_level': t['cells'][2][13:16] = list(' 99')
    elif change == 'wrong_able': t['cells'][3][12:] = list('NOT ABLE')
    elif change == 'wrong_target_name': t['cells'][2][3:11] = list('NIDORINA')
    elif change == 'extra_name': t['cells'][6][3:9] = list('FEAROW')
    else: t['cells'][0][0] = '▶'
    assert s.call(t)['phase'] == 'campaign_review'


def test_inactive_party_arrow_waits_and_correct_target_a_is_sent_only_once():
    s = Session(); s.to_party()
    assert s.call(party_screen(s.p, cursor=1, inactive=True))['available_actions'] == ['wait']
    assert not s.c.selected
    assert s.call(party_screen(s.p, cursor=1))['available_actions'] == ['a', 'wait']
    assert s.call(party_screen(s.p, cursor=1, inactive=True))['available_actions'] == ['wait']
    assert s.call(intro(s.p, background=True))['available_actions'] == ['wait']


@pytest.mark.parametrize('inactive', [False, True])
def test_different_party_cursor_after_target_request_is_not_hidden_by_wait(inactive):
    s = Session(); s.to_evolving()
    assert s.call(party_screen(s.p, cursor=0, inactive=inactive))['review_reason'] == 'moon_stone_party_cursor_changed_after_target_request'


def test_changed_use_cursor_after_a_is_not_treated_as_old_background():
    s = Session(); s.to_party()
    assert s.call(use_screen(s.p, cursor=13))['review_reason'] == 'moon_stone_use_cursor_changed_after_request'


def test_known_partials_wait_and_named_complete_auto_pages_never_press_a_or_b():
    s = Session(); s.to_evolving()
    for t in [text_at((1, 14, 'What? NIDO')), intro(s.p, background=True), text_at(),
              text_at((1, 14, 'NIDORINO evolved')), text_at((1, 14, 'NIDORINO evolved'), (1, 16, 'into NIDOKING')),
              EVOLVED]:
        assert s.call(t)['available_actions'] == ['wait']
    assert s.c.seen_intro and s.c.seen_evolved


@pytest.mark.parametrize('text', [text_at((1, 14, 'NIDORINA evolved'), (1, 16, 'into NIDOQUEEN!')),
                                 text_at((1, 14, 'Huh? NIDORINO'), (1, 16, 'stopped evolving!')),
                                 text_at((1, 14, 'NIDOKING learned'), (1, 16, 'THRASH!')),
                                 text_at((1, 14, 'NIDORINO evolved'), (1, 16, 'into NIDOKING!!'))])
def test_unknown_cancel_wrong_species_or_learning_text_requires_review(text):
    s = Session(); s.to_evolving(); s.call(intro())
    # 最後案例是完整字母但錯誤終止標點；不能視為仍在逐字印刷。
    result = s.call(text)
    assert result['phase'] == 'campaign_review'


@pytest.mark.parametrize('marker', ['▶', '▼', '▷'])
def test_evolution_text_rejects_active_prompt_or_wrong_inactive_marker(marker):
    s = Session(); s.to_evolving(); t = intro(); t['cells'][0][0] = marker
    assert s.call(t)['review_reason'] == 'moon_stone_evolution_unverified_menu_marker'


def test_visible_success_must_follow_visible_intro_and_keep_exact_punctuation():
    s = Session(); s.to_evolving()
    assert s.call(EVOLVED)['review_reason'] == 'moon_stone_success_without_visible_intro'
    s = Session(); s.to_evolving(); t = intro(); t['cells'][16][12] = ' '
    assert s.call(t)['available_actions'] == ['wait'] and not s.c.seen_intro
    assert s.call(EVOLVED)['phase'] == 'campaign_review'


def test_species_change_and_stone_loss_without_receipt_cannot_complete():
    s = Session(); s.to_evolving(); s.call(intro()); s.evolve(); s.consume()
    assert s.call(overworld_ready=True)['review_reason'] == 'moon_stone_new_species_without_visible_success'


@pytest.mark.parametrize('key,value', [('level', 27), ('exp', 17482), ('status', 8),
                                     ('moves', [37, 33, 30, 40]), ('pp', [20, 35, 25, 35])])
def test_evolution_never_allows_level_exp_status_move_or_pp_changes(key, value):
    s = Session(); s.to_evolving(); s.observe_texts(); s.evolve(); s.consume()
    s.p['party'][1][key] = value
    assert s.call()['review_reason'] == 'moon_stone_target_protected_data_changed'


@pytest.mark.parametrize('change', ['other_hp', 'other_exp', 'reorder', 'count', 'wrong_species', 'hp_delta', 'max_decrease', 'extra_stone', 'other_item'])
def test_any_nontransaction_change_blocks_completion(change):
    s = Session(progress(stone_quantity=2)); s.to_evolving(); s.observe_texts(); s.evolve(); s.consume()
    if change == 'other_hp': s.p['party'][0]['hp'] -= 1
    elif change == 'other_exp': s.p['party'][0]['exp'] += 1
    elif change == 'reorder': s.p['party'][0], s.p['party'][1] = s.p['party'][1], s.p['party'][0]
    elif change == 'count': s.p['party_count'] -= 1
    elif change == 'wrong_species': s.p['party'][1].update(species=16, species_name='NIDOQUEEN')
    elif change == 'hp_delta': s.p['party'][1]['hp'] += 1
    elif change == 'max_decrease': s.p['party'][1].update(max_hp=78, hp=62)
    elif change == 'extra_stone': s.p['inventory'] = [x for x in s.p['inventory'] if x['item'] != 10]
    else: s.p['inventory'][0]['quantity'] -= 1
    assert s.call()['phase'] == 'campaign_review'


def test_consumption_before_evolution_and_preselection_changes_fail_immediately():
    s = Session(); s.to_evolving(); s.consume()
    assert s.call(intro())['review_reason'] == 'moon_stone_consumed_before_target_evolution'
    s = Session(); s.call(overworld_ready=True); s.p['party'][1].update(species=7, species_name='NIDOKING')
    assert s.call()['review_reason'] == 'moon_stone_target_changed_before_selection_or_wrong_species'


def test_full_receipt_before_ram_update_waits_and_consumption_is_required():
    s = Session(); s.to_evolving(); s.observe_texts()
    assert s.call()['available_actions'] == ['wait']
    s.evolve()
    assert s.call()['available_actions'] == ['wait']
    assert s.call(overworld_ready=True)['phase'] == 'campaign_review'


def test_empty_post_consumption_bag_can_close_after_exact_last_item_used():
    s = Session(); s.p['inventory'] = [{'item': 10, 'quantity': 1}]
    s.call(overworld_ready=True); s.call(START)
    assert s.call(bag(s.p))['menu_label'] == 'MOON STONE'
    assert s.call(use_screen(s.p, background=False))['menu_label'] == 'USE'
    s.call(party_screen(s.p, cursor=1)); s.observe_texts(); s.evolve(); s.consume()
    assert s.finish()['moon_stone_complete']


def test_post_receipt_menu_cannot_be_misreported_as_overworld():
    s = Session(); s.to_evolving(); s.observe_texts(); s.evolve(); s.consume()
    assert s.call(START, overworld_ready=True)['review_reason'] == 'moon_stone_overworld_conflicts_with_visible_menu'


def test_real_return_start_redraw_never_presses_or_completes_early():
    s = Session(); s.to_evolving(); s.observe_texts(); s.evolve(); s.consume()
    partial=text_at((12,2,'POKéDEX'),(12,4,'POKéMON'))
    result=s.call(partial)
    assert result['available_actions']==['wait'] and not result.get('moon_stone_complete')
    inactive=deepcopy(START);inactive['cells'][6][11]='▷'
    result=s.call(inactive)
    assert result['available_actions']==['wait'] and not result.get('moon_stone_complete')
    assert s.call(START)['available_actions']==['b','wait']
    assert s.call(overworld_ready=True)['moon_stone_complete']


def test_return_redraw_is_bounded_and_unknown_cursor_still_refused():
    s=Session();s.to_evolving();s.observe_texts();s.evolve();s.consume()
    bad=deepcopy(START);bad['cells'][6][11]='▷';bad['cells'][0][0]='▶'
    assert s.call(bad)['phase']=='campaign_review'
    s=Session();s.to_evolving();s.observe_texts();s.evolve();s.consume()
    s.c.max_waits=s.c.waits
    assert s.call(text_at((12,2,'POKéDEX'),(12,4,'POKéMON')))['review_reason']=='moon_stone_wait_budget_exhausted'


def test_bag_preview_is_not_selectable_and_reverse_scroll_uses_verified_order():
    s = Session(); s.p['inventory'][2], s.p['inventory'][3] = s.p['inventory'][3], s.p['inventory'][2]
    s.call(overworld_ready=True); s.call(START)
    assert s.call(bag(s.p, cursor=2))['available_actions'] == ['down', 'wait']
    assert s.call(bag(s.p, offset=1, cursor=2))['menu_label'] == 'MOON STONE'
    s = Session(); s.call(overworld_ready=True); s.call(START)
    assert s.call(bag(s.p, offset=2, cursor=1))['available_actions'] == ['up', 'wait']


@pytest.mark.parametrize('change', ['quantity', 'order', 'unknown', 'extra_cursor'])
def test_unverified_bag_does_not_scroll_or_select(change):
    s = Session(); s.call(overworld_ready=True); s.call(START); t = bag(s.p)
    if change == 'quantity': t['cells'][5][14:18] = list('× 7 ')
    elif change == 'order': t['cells'][6][6:10] = list('HM01')
    elif change == 'unknown': t['cells'][4][6:16] = list('ULTRA BALL')
    else: t['cells'][0][0] = '▶'
    assert s.call(t)['phase'] == 'campaign_review'


def test_stall_wait_clock_and_total_call_limits_are_latched_reviews():
    s = Session(); s.call(overworld_ready=True); s.call(START)
    for _ in range(3): assert s.call(bag(s.p))['available_actions'] == ['down', 'wait']
    assert s.call(bag(s.p))['review_reason'] == 'moon_stone_bag_scroll_budget_exhausted'
    s = Session(max_waits=1); s.to_evolving()
    assert s.call(intro())['available_actions'] == ['wait']
    failed = s.call()
    assert failed['review_reason'] == 'moon_stone_wait_budget_exhausted'
    assert s.call(EVOLVED) == failed
    s = Session(max_calls=1); s.call(overworld_ready=True)
    assert s.call(START)['review_reason'] == 'moon_stone_transaction_budget_exhausted'
    s = Session(); s.call(overworld_ready=True)
    assert s.call(START, now=61)['review_reason'] == 'moon_stone_transaction_budget_exhausted'
    s = Session(); s.call(overworld_ready=True)
    assert s.call(START, now=0)['review_reason'] == 'moon_stone_clock_invalid'


def test_invalid_party_during_partial_animation_is_not_hidden_by_wait():
    s = Session(); s.to_evolving(); s.p['party_read_valid'] = False
    assert s.call(text_at((1, 14, 'What? NID')))['review_reason'] == 'moon_stone_party_not_verified'


def test_battle_interruption_and_wrong_cells_fail_without_any_action():
    s = Session(); s.to_evolving()
    assert s.call(intro(), battle_active=True)['available_actions'] == ['wait']
    s = Session(); t = text_at(); t['cells'][10][0] = "'t"
    assert s.call(t, overworld_ready=True)['review_reason'] == 'moon_stone_full_cells_required'
