"""拉普拉斯25級自然學泰山壓頂：合成觀測，不載入遊戲或送鍵。"""
from copy import deepcopy

import pytest

from laya_pokemon import levelup_moves as control
from tests.test_battle import text_at


@pytest.fixture(autouse=True)
def fresh_session(monkeypatch):
    monkeypatch.setattr(control, '_SESSION', None)


def party():
    return {'party_read_valid': True, 'party': [
        {'species': 7, 'level': 36, 'moves': [61, 57, 30, 40]},
        {'species': 19, 'level': 25, 'moves': [55, 45, 47, 54]},
        {'species': 102, 'level': 35, 'moves': [33, 28, 98, 39]},
        {'species': 154, 'level': 35, 'moves': [75, 15, 73, 22]},
        {'species': 35, 'level': 36, 'moves': [64, 65, 43, 31]},
        {'species': 132, 'level': 37, 'moves': [70, 133, 156, 34]},
    ]}


def intro(state):
    return control.context(text_at((1, 14, 'LAPRAS is'), (1, 16, 'trying to learn')), state)


def yes_no(*, selected='YES'):
    return text_at((15, 8, 'YES'), (15, 10, 'NO'), (14, 8 if selected == 'YES' else 10, '▶'),
                   (1, 14, 'for BODY SLAM?'))


def four_moves(row=9):
    return text_at((6, 8, 'WATER GUN'), (6, 9, 'GROWL'), (6, 10, 'SING'), (6, 11, 'MIST'),
                   (5, row, '▶'), (0, 3, '▷'),
                   (1, 14, 'Which move should'), (1, 16, 'be forgotten?'))


def to_question(state):
    intro(state)
    control.context(text_at((1, 14, 'BODY SLAM!')), state)
    return control.context(text_at((1, 14, 'Delete an older'), (1, 16, 'move to make room▼')), state)


def to_selected(state):
    to_question(state)
    control.context(yes_no(), state)
    return control.context(four_moves(), state)


def to_and(state):
    to_selected(state)
    control.context(text_at((1, 14, '1, 2 and... Poof!')), state)
    control.context(text_at((1, 14, 'LAPRAS forgot'), (1, 16, 'GROWL!')), state)
    return control.context(text_at((1, 14, 'And...')), state)


def test_fixed_source_and_team_plan_allow_only_level25_body_slam_for_growl():
    plan = control.candidate_plan(19, 25, [55, 45, 47, 54])
    assert plan['natural_level'] == 25 and plan['new_move_id'] == 34
    assert plan['decision'] == 'replace' and plan['replace_index'] == 1
    assert plan['forget'] == 'GROWL' and plan['move'] == 'BODY_SLAM'
    assert plan['ui_candidate_implemented'] is True
    assert control.reference()['source_commit'] == control.SOURCE_COMMIT
    assert {'level': 25, 'move': 'BODY_SLAM'} in control.reference()['species']['LAPRAS']['level_moves']


def test_level24_does_not_claim_learning_and_wrong_moves_review_without_a():
    state = party(); state['party'][1]['level'] = 24
    assert control.candidate_plan(19, 24, [55, 45, 47, 54]) is None
    assert intro(state) is None and control._SESSION is None
    state = party(); state['party'][1]['moves'][1] = 15
    result = intro(state)
    assert result['phase'] == 'strategy_review' and result['available_actions'] == ['wait']
    assert control._SESSION is None


def test_complete_natural_sequence_only_forgets_growl_and_verifies_whole_party_moves():
    state = party(); original = deepcopy(state)
    assert intro(state)['available_actions'] == ['a', 'wait']
    control.context(text_at((1, 14, 'BODY SLAM!')), state)
    assert control.context(text_at((1, 14, 'But, LAPRAS'), (1, 16, "can't learn more")), state)['available_actions'] == ['wait']
    control.context(text_at((1, 14, 'than 4 moves!')), state)
    control.context(text_at((1, 14, 'Delete an older'), (1, 16, 'move to make room▼')), state)
    assert control.context(yes_no(selected='NO'), state)['objective'] == 'Move UP.'
    assert control.context(yes_no(), state)['menu_label'] == 'YES'
    assert control.context(four_moves(8), state)['objective'] == 'Move DOWN.'
    assert control.context(four_moves(11), state)['objective'] == 'Move UP.'
    selected = control.context(four_moves(9), state)
    assert selected['available_actions'] == ['a', 'wait'] and selected['forgotten_move'] == 45
    assert selected['protected_moves'] == [55, 47, 54]
    assert control.context(text_at((1, 14, '1, 2 and... Poof!')), state)['available_actions'] == ['a', 'wait']
    assert control.context(text_at((1, 14, 'LAPRAS forgot'), (1, 16, 'GROWL!')), state)['available_actions'] == ['a', 'wait']
    assert control.context(text_at((1, 14, 'And...')), state)['available_actions'] == ['a', 'wait']
    assert state == original
    state['party'][1]['moves'][1] = 34  # 合成遊戲結果；控制器本身不修改progress。
    result = control.context(text_at((1, 14, 'LAPRAS learned'), (1, 16, 'BODY SLAM!')), state)
    assert result['learning_complete'] is True and result['moves_verified'] == [55, 34, 47, 54]
    assert result['protected_moves'] == [55, 47, 54]
    assert state['party'][0]['moves'][1] == 57 and state['party'][3]['moves'][1] == 15
    assert state['party'][5]['moves'][0] == 70
    assert control.context(text_at(), state) is None and control._SESSION is None


def test_source_has_no_standalone_slam_page_so_suffix_never_advances():
    state = party(); intro(state)
    result = control.context(text_at((1, 14, 'SLAM!')), state)
    assert result['phase'] == 'strategy_review' and result['available_actions'] == ['wait']
    assert control._SESSION['seen_move'] is False


def test_strategy_must_agree_on_growl_slot_before_binding(monkeypatch):
    monkeypatch.setattr(control, 'learn_move_plan', lambda *a, **kw: {
        'decision': 'replace', 'replace_index': 2, 'forget': 'SING', 'move': 'BODY_SLAM'})
    result = intro(party())
    assert result['review_reason'] == 'natural_learning_replacement_plan_mismatch'
    assert result['available_actions'] == ['wait'] and control._SESSION is None


def test_observe_six_party_learning_precedes_transformed_enemy_battle(monkeypatch):
    from types import SimpleNamespace
    from laya_pokemon import battle, game, navigation, observation, progress

    state = party()
    for mon in state['party']:
        mon.update(hp=100, max_hp=100)
    page = text_at((1, 14, 'LAPRAS is'), (1, 16, 'trying to learn'))
    page.update(profile='synthetic_source_layout', warnings=[])
    monkeypatch.setattr(observation, 'read_visible_text', lambda _: page)
    monkeypatch.setattr(observation, 'opening_context', lambda *a: {})
    monkeypatch.setattr(progress, 'read_progress', lambda _: state)
    monkeypatch.setattr(navigation, 'read_location', lambda _: {'map_id': 26, 'x': 18, 'y': 8})
    monkeypatch.setattr(battle, 'read_battle_state', lambda _: {
        'active': True, 'raw': 1, 'kind': 'wild', 'opponent_species': 'FEAROW'})
    monkeypatch.setattr(battle, 'battle_context', lambda *a, **kw: pytest.fail(
        '一般戰鬥不得先於已接管的自然學招流程'))
    emulator = SimpleNamespace(frame_count=1, screen=SimpleNamespace(
        ndarray=SimpleNamespace(tobytes=lambda: b'synthetic framebuffer')))
    result = game.observe(emulator, 'Wait.', opening_route=True, route_stage='team_training')
    assert result['phase'] == 'learning_menu'
    assert result['learning_controller'] == 'bounded_natural_move_candidate'
    assert control._SESSION['replacement_case'] == (19, 25)


@pytest.mark.parametrize('row,action', [(8, 'down'), (9, 'a'), (10, 'up'), (11, 'up')])
def test_active_cursor_never_confirms_protected_water_gun_sing_or_mist(row, action):
    state = party(); to_question(state); control.context(yes_no(), state)
    assert control.context(four_moves(row), state)['available_actions'] == [action, 'wait']


@pytest.mark.parametrize('bad', ['inactive_only', 'wrong_column', 'two_active', 'wrong_labels'])
def test_wrong_forget_cursor_or_move_labels_never_confirm(bad):
    state = party(); to_question(state); control.context(yes_no(), state)
    page = four_moves()
    if bad == 'inactive_only': page['cells'][9][5] = '▷'
    elif bad == 'wrong_column': page['cells'][9][5], page['cells'][9][4] = ' ', '▶'
    elif bad == 'two_active': page['cells'][8][5] = '▶'
    else: page['cells'][9][6:11] = list('SING ')
    result = control.context(page, state)
    assert result['phase'] == 'strategy_review' and result['available_actions'] == ['wait']


@pytest.mark.parametrize('name,move', [('FEAROW', 'GROWL!'), ('LAPRAS', 'SING!'), ('LAPRAS', 'WATER GUN!'), ('LAPRAS', 'MIST!')])
def test_wrong_name_or_wrong_forgot_move_latches_review(name, move):
    state = party(); to_selected(state)
    result = control.context(text_at((1, 14, name + ' forgot'), (1, 16, move)), state)
    assert result['phase'] == 'strategy_review' and result['available_actions'] == ['wait']
    assert control.context(text_at((1, 14, 'And...')), state)['review_reason'] == result['review_reason']


@pytest.mark.parametrize('member,slot,value', [(1, 0, 34), (1, 2, 34), (1, 3, 34), (0, 1, 33), (3, 1, 33), (5, 0, 29)])
def test_any_extra_move_change_including_other_members_hm_requires_review(member, slot, value):
    state = party(); to_and(state); state['party'][member]['moves'][slot] = value
    result = control.context(text_at((1, 14, 'LAPRAS learned'), (1, 16, 'BODY SLAM!')), state)
    assert result['phase'] == 'strategy_review' and result['available_actions'] == ['wait']


def test_known_partial_delete_forgot_and_learned_wait_without_a():
    state = party(); to_question(state)
    assert control.context(text_at((1, 14, 'for BODY SLA')), state)['available_actions'] == ['wait']
    control.context(yes_no(), state); control.context(four_moves(), state)
    assert control.context(text_at((1, 14, 'LAPRAS forgot')), state)['available_actions'] == ['wait']
    control.context(text_at((1, 14, 'LAPRAS forgot'), (1, 16, 'GROWL!')), state)
    assert control.context(text_at((1, 14, 'An')), state)['available_actions'] == ['wait']
    control.context(text_at((1, 14, 'And...')), state)
    state['party'][1]['moves'][1] = 34
    assert control.context(text_at((1, 14, 'LAPRAS learned')), state)['available_actions'] == ['wait']


def test_unknown_page_and_result_without_real_move_change_never_confirm():
    state = party(); intro(state)
    assert control.context(text_at((1, 14, 'A completely'), (1, 16, 'unknown page!')), state)['phase'] == 'strategy_review'
    control._SESSION = None
    state = party(); to_and(state)
    result = control.context(text_at((1, 14, 'LAPRAS learned'), (1, 16, 'BODY SLAM!')), state)
    assert result['review_reason'] == 'natural_learning_learned_without_expected_moves'
    assert result['available_actions'] == ['wait']
