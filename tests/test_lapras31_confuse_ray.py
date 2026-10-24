"""拉普拉斯31級奇異之光：只忘白霧，合成可見UI不載入遊戲。"""
from copy import deepcopy

import pytest

from laya_pokemon import levelup_moves as control
from laya_pokemon.team_strategy import choose_damage_move, learn_move_plan
from tests.test_battle import text_at


@pytest.fixture(autouse=True)
def fresh_session(monkeypatch):
    monkeypatch.setattr(control, '_SESSION', None)
    monkeypatch.setattr(control.snorlax_harden_skip, '_SESSION', None)


def party():
    mons = [
        (19, 31, [57, 34, 47, 54], [15, 15, 15, 30]),
        (132, 41, [70, 133, 156, 34], [15, 20, 10, 15]),
        (102, 35, [33, 28, 98, 39], [35, 15, 30, 30]),
        (154, 35, [75, 15, 73, 22], [25, 30, 10, 10]),
        (35, 37, [64, 65, 19, 31], [35, 20, 15, 20]),
        (7, 36, [61, 57, 30, 40], [20, 15, 25, 35]),
    ]
    return {'party_read_valid': True, 'party': [
        dict(species=species, level=level, moves=moves, pp=pp, hp=100, max_hp=120,
             status=0, exp=50000 + i, nickname=f'SOURCE-{i}')
        for i, (species, level, moves, pp) in enumerate(mons)]}


def call(page, state):
    before = deepcopy((page, state))
    result = control.context(page, state)
    assert (page, state) == before  # 所有按鍵均為子目標，不能改觀測／遊戲結果。
    return result


def intro(state):
    return call(text_at((1, 14, 'LAPRAS is'), (1, 16, 'trying to learn')), state)


def choices(selected='YES'):
    return text_at((15, 8, 'YES'), (15, 10, 'NO'), (14, 8 if selected == 'YES' else 10, '▶'),
                   (1, 14, 'for CONFUSE RAY?'))


def four_moves(row=11):
    return text_at((6, 8, 'SURF'), (6, 9, 'BODY SLAM'), (6, 10, 'SING'), (6, 11, 'MIST'),
                   (5, row, '▶'), (0, 3, '▷'),
                   (1, 14, 'Which move should'), (1, 16, 'be forgotten?'))


def to_question(state):
    intro(state)
    call(text_at((1, 14, 'CONFUSE RAY!')), state)
    return call(text_at((1, 14, 'Delete an older'), (1, 16, 'move to make room▼')), state)


def to_selected(state):
    to_question(state); call(choices(), state)
    return call(four_moves(), state)


def to_and(state):
    to_selected(state)
    call(text_at((1, 14, '1, 2 and... Poof!')), state)
    call(text_at((1, 14, 'LAPRAS forgot'), (1, 16, 'MIST!')), state)
    return call(text_at((1, 14, 'And...')), state)


def review(result):
    assert result['phase'] == 'strategy_review' and result['available_actions'] == ['wait']


def test_pinned_reference_and_candidate_require_level31_confuse_ray109_pp10_for_mist():
    ref = control.reference()
    assert ref['source_commit'] == 'a53671100ec22e5394ff26ec028d0812a238dae2'
    assert {'level': 31, 'move': 'CONFUSE_RAY'} in ref['species']['LAPRAS']['level_moves']
    assert (ref['moves']['CONFUSE_RAY']['id'], ref['moves']['CONFUSE_RAY']['pp']) == (109, 10)
    assert ref['moves']['SING']['effect'] == 'SLEEP_EFFECT'
    plan = control.candidate_plan(19, 31, [57, 34, 47, 54])
    assert plan['decision'] == 'replace' and plan['replace_index'] == 3
    assert (plan['forget'], plan['move'], plan['natural_level'], plan['new_move_id']) == ('MIST', 'CONFUSE_RAY', 31, 109)
    assert plan['ui_candidate_implemented'] is True


def test_low_capture_utility_preserves_sing_but_keeps_old_lapras25_and_damage_strategy():
    assert learn_move_plan(19, [57, 34, 47, 54], 109, level=31)['forget'] == 'MIST'
    assert learn_move_plan(19, [55, 45, 47, 54], 34, level=25)['forget'] == 'GROWL'
    assert choose_damage_move(19, [57, 34, 47, 54], [15, 15, 15, 30], 'KOFFING') == 'SURF'


@pytest.mark.parametrize('moves', [[55, 34, 47, 54], [57, 34, 54, 47], [57, 34, 47, 45]])
def test_old_water_gun_or_any_other_order_cannot_bind(moves):
    state = party(); state['party'][0]['moves'] = moves
    assert control.candidate_plan(19, 31, moves)['decision'] == 'review'
    review(intro(state)); assert control._SESSION is None


def test_wrong_level_or_species_does_not_claim_lapras31_learning():
    state = party(); state['party'][0]['level'] = 30
    assert control.candidate_plan(19, 30, [57, 34, 47, 54]) is None
    assert intro(state) is None and control._SESSION is None
    state = party(); state['party'][0]['species'] = 128
    assert intro(state) is None and control._SESSION is None


def test_full_fresh_flow_forgets_only_slot3_then_verifies_expected_whole_party_moves():
    state = party(); original = deepcopy(state)
    assert intro(state)['available_actions'] == ['a', 'wait']
    assert call(text_at((1, 14, 'CONFUSE RA')), state)['available_actions'] == ['wait']
    assert call(text_at((1, 14, 'CONFUSE RAY!')), state)['available_actions'] == ['a', 'wait']
    call(text_at((1, 14, 'But, LAPRAS'), (1, 16, "can't learn more")), state)
    call(text_at((1, 14, 'than 4 moves!')), state)
    call(text_at((1, 14, 'Delete an older'), (1, 16, 'move to make room▼')), state)
    assert call(choices('NO'), state)['available_actions'] == ['up', 'wait']
    assert call(choices(), state)['menu_label'] == 'YES'
    assert call(four_moves(8), state)['available_actions'] == ['down', 'wait']
    selected = call(four_moves(), state)
    assert selected['available_actions'] == ['a', 'wait'] and selected['forgotten_move'] == 54
    assert selected['protected_moves'] == [57, 34, 47]
    assert call(text_at((1, 14, '1, 2 and... Poof!')), state)['available_actions'] == ['a', 'wait']
    assert call(text_at((1, 14, 'LAPRAS forgot'), (1, 16, 'MIST!')), state)['available_actions'] == ['a', 'wait']
    assert call(text_at((1, 14, 'And...')), state)['available_actions'] == ['a', 'wait']
    assert state == original
    state['party'][0]['moves'][3] = 109; state['party'][0]['pp'][3] = 10  # 合成原生學會結果，非控制器寫值。
    result = call(text_at((1, 14, 'LAPRAS learned'), (1, 16, 'CONFUSE RAY!')), state)
    assert result['learning_complete'] is True and result['moves_verified'] == [57, 34, 47, 109]
    assert result['protected_moves'] == [57, 34, 47]
    assert state['party'][1:] == original['party'][1:]
    expected = deepcopy(original); expected['party'][0]['moves'][3] = 109; expected['party'][0]['pp'][3] = 10
    assert state == expected
    assert call(text_at(), state) is None and control._SESSION is None


@pytest.mark.parametrize('row,action', [(8, 'down'), (9, 'down'), (10, 'down'), (11, 'a')])
def test_cursor_at_surf_body_slam_or_sing_never_confirms_that_protected_move(row, action):
    state = party(); to_question(state); call(choices(), state)
    result = call(four_moves(row), state)
    assert result['available_actions'] == [action, 'wait']
    if action == 'a': assert result['forgotten_move'] == 54


@pytest.mark.parametrize('wrong', ['inactive', 'column', 'duplicate', 'labels'])
def test_wrong_forget_cursor_or_labels_review_without_a(wrong):
    state = party(); to_question(state); call(choices(), state); page = four_moves()
    if wrong == 'inactive': page['cells'][11][5] = '▷'
    elif wrong == 'column': page['cells'][11][5], page['cells'][11][4] = ' ', '▶'
    elif wrong == 'duplicate': page['cells'][10][5] = '▶'
    else: page['cells'][11][6:10] = list('SING')
    review(call(page, state))


def test_partial_pages_only_wait_and_unknown_ray_suffix_never_advances():
    state = party(); intro(state)
    review(call(text_at((1, 14, 'RAY!')), state))
    control._SESSION = None; state = party(); to_question(state)
    assert call(text_at((1, 14, 'for CONFUSE RA')), state)['available_actions'] == ['wait']
    call(choices(), state); call(four_moves(), state)
    assert call(text_at((1, 14, 'LAPRAS forgot')), state)['available_actions'] == ['wait']
    call(text_at((1, 14, 'LAPRAS forgot'), (1, 16, 'MIST!')), state)
    assert call(text_at((1, 14, 'An')), state)['available_actions'] == ['wait']
    call(text_at((1, 14, 'And...')), state)
    state['party'][0]['moves'][3] = 109
    assert call(text_at((1, 14, 'LAPRAS learned')), state)['available_actions'] == ['wait']


def test_strategy_disagreement_unknown_page_and_wrong_result_never_confirm(monkeypatch):
    state = party()
    monkeypatch.setattr(control, 'learn_move_plan', lambda *a, **kw:
        dict(decision='replace', replace_index=2, forget='SING', move='CONFUSE_RAY'))
    result = intro(state)
    assert result['review_reason'] == 'natural_learning_replacement_plan_mismatch' and control._SESSION is None
    monkeypatch.undo(); to_and(state)
    result = call(text_at((1, 14, 'LAPRAS learned'), (1, 16, 'CONFUSE RAY!')), state)
    assert result['review_reason'] == 'natural_learning_learned_without_expected_moves'


@pytest.mark.parametrize('change', ['learner_species', 'learner_level', 'duplicate', 'other_hm', 'sing'])
def test_midflow_identity_or_protected_move_change_is_sticky_review(change):
    state = party(); to_selected(state)
    if change == 'learner_species': state['party'][0]['species'] = 132
    elif change == 'learner_level': state['party'][0]['level'] = 32
    elif change == 'duplicate': state['party'][2]['species'] = 19
    elif change == 'other_hm': state['party'][1]['moves'][0] = 29
    else: state['party'][0]['moves'][2] = 109
    result = call(text_at((1, 14, 'LAPRAS forgot'), (1, 16, 'MIST!')), state)
    review(result)
    assert call(text_at((1, 14, 'And...')), state)['review_reason'] == result['review_reason']


def test_known_abandon_question_keeps_moves_and_only_waits_for_wrapped_result():
    state = party(); original = deepcopy(state); to_question(state)
    assert call(text_at((1, 14, 'Abandon learning')), state)['available_actions'] == ['wait']
    question = text_at((15, 8, 'YES'), (15, 10, 'NO'), (14, 8, '▶'),
                       (1, 14, 'Abandon learning'), (1, 16, 'CONFUSE RAY?'))
    assert call(question, state)['menu_label'] == 'YES'
    # 原生兩行先見名字／did not learn；不把三行硬塞成超寬的假完成頁。
    result = call(text_at((1, 14, 'LAPRAS'), (1, 16, 'did not learn▼')), state)
    assert result['available_actions'] == ['wait'] and state == original
