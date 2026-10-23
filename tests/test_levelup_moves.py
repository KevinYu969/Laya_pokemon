"""純合成自然學招候選驗證；不載入 ROM、不執行模型／按鍵。"""
import copy
import importlib

import pytest

import laya_pokemon.levelup_moves as control
from tests.test_battle import text_at


def progress():
    return {'party_read_valid': True, 'party': [
        {'species': 9, 'level': 30, 'moves': [77, 15, 73, 22]},
        {'species': 167, 'level': 24, 'moves': [43, 33, 30, 40]},
        {'species': 35, 'level': 20, 'moves': [64, 45, 43, 31]},
    ]}


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    monkeypatch.setattr(control, '_SESSION', None)


def question(first, second, selected='YES'):
    return text_at((15, 8, 'YES'), (15, 10, 'NO'),
                   (14, 8 if selected == 'YES' else 10, '▶'),
                   (1, 14, first), (1, 16, second))


def forget(*, selected=8, inactive=False):
    return text_at((6, 8, 'POISONPOWDER'), (6, 9, 'CUT'), (6, 10, 'LEECH SEED'), (6, 11, 'VINE WHIP'),
                   (5, selected, '▶'), (0, 3, '▷' if inactive else ' '),
                   (1, 14, 'Which move should'), (1, 16, 'be forgotten?'))


def start(state):
    return control.context(text_at((1, 14, 'IVYSAUR is'), (1, 16, 'trying to learn')), state)


def to_delete(state):
    start(state)
    control.context(text_at((1, 14, 'RAZOR LEAF!')), state)
    return control.context(text_at((1, 14, 'Delete an older'), (1, 16, 'move to make room▼')), state)


def to_forget(state):
    to_delete(state)
    result = control.context(question('for RAZOR LEAF?', ''), state)
    assert result['menu_label'] == 'YES'
    return control.context(forget(), state)


def to_and(state):
    to_forget(state)
    control.context(text_at((1, 14, '1, 2 and... Poof!')), state)
    control.context(text_at((1, 14, 'IVYSAUR forgot'), (1, 16, 'POISONPOWDER!')), state)
    return control.context(text_at((0, 3, '▷'), (1, 14, 'And...')), state)


def test_fixed_source_and_strategy_replace_only_poisonpowder():
    plan = control.candidate_plan(9, 30, [77, 15, 73, 22])
    assert plan['decision'] == 'replace' and plan['replace_index'] == 0
    assert plan['forget'] == 'POISONPOWDER' and plan['new_move_id'] == 75


def test_source_corrects_nidorino_fury_attack_to_32_and_verifies_fearow_skip():
    assert control.candidate_plan(167, 30, [43, 33, 30, 40])['reason'] == 'source_fury_attack_level_is_32_not_30'
    plan = control.candidate_plan(167, 32, [43, 33, 30, 40])
    assert plan['decision'] == 'replace' and plan['new_move_id'] == 31 and not plan['ui_candidate_implemented']
    plan = control.candidate_plan(35, 25, [64, 45, 43, 31])
    assert plan['decision'] == 'skip' and plan['new_move_id'] == 119 and plan['ui_candidate_implemented']


@pytest.mark.parametrize('species,level,name,moves', [
    (167, 32, 'NIDORINO', [43, 33, 30, 40])])
def test_unimplemented_cases_return_plan_and_no_button(species, level, name, moves):
    state = {'party_read_valid': True, 'party': [{'species': species, 'level': level, 'moves': moves}]}
    result = control.context(text_at((1, 14, name + ' is'), (1, 16, 'trying to learn')), state)
    assert result['review_reason'] == 'natural_learning_ui_requires_review'
    assert result['available_actions'] == ['wait'] and not result['learning_move_visually_confirmed']
    assert control._SESSION is None


def test_complete_natural_replacement_requires_forgot_and_and_expected_fingerprint():
    state = progress()
    original = copy.deepcopy(state)
    assert start(state)['available_actions'] == ['a', 'wait']
    control.context(text_at((1, 14, 'RAZOR LEAF!')), state)
    assert control.context(text_at((1, 14, 'But, IVYSAUR'), (1, 16, "can't learn more")), state)['available_actions'] == ['wait']
    assert control.context(text_at((1, 14, 'than 4 moves!')), state)['available_actions'] == ['a', 'wait']
    to_delete(state)
    assert control.context(question('for RAZOR LEAF?', '', selected='NO'), state)['objective'] == 'Move UP.'
    assert control.context(question('for RAZOR LEAF?', ''), state)['menu_label'] == 'YES'
    assert control.context(forget(), state)['forgotten_move'] == 77
    assert control.context(text_at((1, 14, '1, 2 and... Poof!')), state)['available_actions'] == ['a', 'wait']
    result = control.context(text_at((1, 14, 'IVYSAUR forgot'), (1, 16, 'POISONPOWDER!')), state)
    assert result['learning_tactic'] == 'advance_verified_poisonpowder_forgot'
    assert control.context(text_at((1, 14, 'And...')), state)['learning_tactic'] == 'advance_verified_learning_and'
    assert state == original  # 控制器完全沒有寫入進度；以下由合成遊戲結果更新。
    state['party'][0]['moves'] = [75, 15, 73, 22]
    result = control.context(text_at((1, 14, 'IVYSAUR learned'), (1, 16, 'RAZOR LEAF!')), state)
    assert result['learning_complete'] and result['moves_verified'] == [75, 15, 73, 22]
    assert result['protected_moves'] == [15, 73, 22]
    assert control.context(text_at(), state) is None and control._SESSION is None


def test_typing_delete_and_wrapped_continuation_wait_until_actual_choices():
    state = progress()
    start(state)
    control.context(text_at((1, 14, 'RAZOR LEAF!')), state)
    for partial in ('D', 'Delete', 'Delete an older'):
        assert control.context(text_at((1, 14, partial)), state)['available_actions'] == ['wait']
    assert control.context(text_at((1, 14, 'Delete an older'), (1, 16, 'move to make room▼')), state)['available_actions'] == ['a', 'wait']
    importlib.reload(control)
    for partial in ('for R', 'for RAZOR', 'for RAZOR LEA'):
        assert control.context(text_at((1, 14, partial)), state)['available_actions'] == ['wait']
    assert control.context(question('for RAZOR LEAF?', '', selected='NO'), state)['menu_label'] == 'YES'


def test_capacity_typing_b_is_not_mistaken_for_be_forgotten_question():
    state = progress()
    start(state)
    control.context(text_at((1, 14, 'RAZOR LEAF!')), state)
    for partial in ('B', 'Bu', 'But', 'But, IVYSAUR'):
        result = control.context(text_at((1, 14, partial)), state)
        assert result['available_actions'] == ['wait'] and result['phase'] == 'learning_menu'


def test_known_transition_blank_only_waits_without_using_an_inactive_marker():
    state = progress()
    start(state)
    result = control.context(text_at((0, 3, '▷')), state)
    assert result['available_actions'] == ['wait']
    assert result['learning_tactic'] == 'await_known_natural_learning_transition'


def test_typing_forgot_and_and_and_learned_only_waits():
    state = progress()
    to_forget(state)
    for partial in ('I', 'IVYSAUR f', 'IVYSAUR forgot'):
        assert control.context(text_at((1, 14, partial)), state)['available_actions'] == ['wait']
    control.context(text_at((1, 14, 'IVYSAUR forgot'), (1, 16, 'POISONPOWDER!')), state)
    for partial in ('A', 'An', 'And'):
        assert control.context(text_at((1, 14, partial)), state)['available_actions'] == ['wait']
    control.context(text_at((1, 14, 'And...')), state)
    state['party'][0]['moves'][0] = 75
    for partial in ('I', 'IVYSAUR learned', 'IVYSAUR learnedRA'):
        assert control.context(text_at((1, 14, partial)), state)['available_actions'] == ['wait']


def test_inactive_marker_is_ignored_and_active_four_move_cursor_is_used():
    state = progress()
    to_delete(state)
    control.context(question('for RAZOR LEAF?', ''), state)
    menu = forget(selected=10, inactive=True)
    menu['cells'][8][5] = '▷'
    assert control.context(menu, state)['objective'] == 'Move UP.'
    assert control.context(forget(selected=8, inactive=True), state)['available_actions'] == ['a', 'wait']


@pytest.mark.parametrize('mutation', ['wrong_move', 'wrong_order', 'wrong_cursor_column', 'double_active', 'inactive_only'])
def test_forget_menu_rejects_any_unverified_four_move_layout_or_active_cursor(mutation):
    state = progress()
    to_delete(state)
    control.context(question('for RAZOR LEAF?', ''), state)
    menu = forget()
    if mutation == 'wrong_move':
        menu['cells'][9][6:] = list('GROWL         ')
    elif mutation == 'wrong_order':
        menu['cells'][8][6:], menu['cells'][9][6:] = menu['cells'][9][6:], menu['cells'][8][6:]
    elif mutation == 'wrong_cursor_column':
        menu['cells'][8][5], menu['cells'][8][4] = ' ', '▶'
    elif mutation == 'double_active':
        menu['cells'][9][5] = '▶'
    else:
        menu['cells'][8][5] = '▷'
    result = control.context(menu, state)
    assert result['phase'] == 'strategy_review' and result['available_actions'] == ['wait']


def test_four_move_menu_cannot_be_entered_without_a_verified_delete_yes():
    state = progress()
    start(state)
    control.context(text_at((1, 14, 'RAZOR LEAF!')), state)
    assert control.context(forget(), state)['review_reason'] == 'natural_learning_unexpected_forget_menu'


def test_partial_forget_question_preserves_battle_hud_then_waits_for_real_move_frame():
    state = progress()
    to_delete(state)
    control.context(question('for RAZOR LEAF?', ''), state)
    for partial in ('Which m', 'Which move should', 'Which move should b'):
        page = text_at((10, 7, 'IVYSAUR'), (14, 8, '30'), (10, 10, '80/80'), (1, 14, partial))
        result = control.context(page, state)
        assert result['available_actions'] == ['wait'] and result['phase'] == 'learning_menu'
        assert result['learning_tactic'] == 'await_source_ordered_four_move_menu'
    result = control.context(forget(), state)
    assert result['forgotten_move'] == 77 and result['available_actions'] == ['a', 'wait']


def test_complete_forget_question_with_old_hud_still_waits_bounded_without_confirming():
    state = progress()
    to_delete(state)
    control.context(question('for RAZOR LEAF?', ''), state)
    page = text_at((10, 7, 'IVYSAUR'), (14, 8, '30'), (10, 10, '80/80'),
                   (1, 14, 'Which move should'), (1, 16, 'be forgotten?'))
    for _ in range(30):
        assert control.context(page, state)['available_actions'] == ['wait']
    assert control.context(page, state)['review_reason'] == 'natural_learning_known_transition_wait_exhausted'


def test_question_without_visual_new_move_name_cannot_be_confirmed():
    state = progress()
    start(state)
    result = control.context(question('Delete an older', 'move?'), state)
    assert result['review_reason'] == 'natural_learning_delete_without_confirmed_move'


def test_abandon_question_selects_yes_and_verifies_no_moves_changed_then_reviews():
    state = progress()
    to_delete(state)
    assert control.context(text_at((1, 14, 'Abandon')), state)['available_actions'] == ['wait']
    result = control.context(question('Abandon learning', 'RAZOR LEAF?', selected='NO'), state)
    assert result['menu_label'] == 'YES' and result['objective'] == 'Move UP.'
    control.context(question('Abandon learning', 'RAZOR LEAF?'), state)
    result = control.context(text_at((1, 14, 'IVYSAUR did not'), (1, 16, 'learn RAZOR LEAF!')), state)
    assert result['review_reason'] == 'natural_learning_abandoned_safely'
    assert result['learning_moves_unchanged'] and result['learning_result'] == 'did_not_learn'


def test_abandon_after_forget_selection_is_never_accepted():
    state = progress()
    to_forget(state)
    result = control.context(question('Abandon learning', 'RAZOR LEAF?'), state)
    assert result['phase'] == 'strategy_review' and result['available_actions'] == ['wait']


@pytest.mark.parametrize('member,slot,value', [(0, 1, 75), (0, 3, 75), (1, 0, 31)])
def test_any_difference_outside_expected_one_move_change_requires_review(member, slot, value):
    state = progress()
    to_and(state)
    state['party'][member]['moves'][slot] = value
    result = control.context(text_at((1, 14, 'IVYSAUR learned'), (1, 16, 'RAZOR LEAF!')), state)
    assert result['review_reason'] == 'natural_learning_unexpected_move_change'


def test_expected_move_change_is_rejected_before_confirmed_forgot_and_and():
    state = progress()
    to_forget(state)
    state['party'][0]['moves'][0] = 75
    result = control.context(text_at((1, 14, 'IVYSAUR learned'), (1, 16, 'RAZOR LEAF!')), state)
    assert result['review_reason'] == 'natural_learning_move_changed_before_verified_selection'


def test_learned_text_alone_does_not_prove_moves_changed():
    state = progress()
    to_and(state)
    result = control.context(text_at((1, 14, 'IVYSAUR learned'), (1, 16, 'RAZOR LEAF!')), state)
    assert result['review_reason'] == 'natural_learning_learned_without_expected_moves'


def test_forgot_wrong_move_or_and_without_forgot_latches_review():
    state = progress()
    to_forget(state)
    result = control.context(text_at((1, 14, 'IVYSAUR forgot'), (1, 16, 'CUT!')), state)
    assert result['phase'] == 'strategy_review'
    assert control.context(text_at((1, 14, 'And...')), state)['review_reason'] == result['review_reason']


def test_and_cannot_skip_the_actual_forgot_poisonpowder_confirmation():
    state = progress()
    to_forget(state)
    assert control.context(text_at((1, 14, 'And...')), state)['review_reason'] == 'natural_learning_and_without_verified_forgot'


def test_question_wait_is_bounded_without_auto_accept():
    state = progress()
    to_delete(state)
    for _ in range(30):
        assert control.context(text_at((1, 14, 'for R')), state)['available_actions'] == ['wait']
    assert control.context(text_at((1, 14, 'for R')), state)['review_reason'] == 'natural_learning_known_transition_wait_exhausted'


def test_hot_reload_preserves_selection_and_fingerprint_before_irreversible_result():
    state = progress()
    to_and(state)
    snapshot = copy.deepcopy(control._SESSION)
    importlib.reload(control)
    assert control._SESSION == snapshot
    state['party'][0]['moves'][0] = 75
    assert control.context(text_at((1, 14, 'IVYSAUR learned'), (1, 16, 'RAZOR LEAF!')), state)['learning_complete']


@pytest.mark.parametrize('change', ['wrong_level', 'unknown_learner'])
def test_unknown_case_does_not_claim_the_learning_flow(change):
    state = progress()
    if change == 'wrong_level':
        state['party'][0]['level'] = 29
    else:
        state['party'][0]['species'] = 154
    assert start(state) is None


def test_invalid_initial_moves_or_unsafe_strategy_never_enter_the_menu(monkeypatch):
    state = progress()
    state['party'][0]['moves'][1] = 45
    assert start(state)['review_reason'] == 'natural_learning_candidate_not_verified'
    state = progress()
    monkeypatch.setattr(control, 'learn_move_plan', lambda *a, **kw: {'decision': 'replace', 'replace_index': 1,
                                                                  'forget': 'CUT', 'move': 'RAZOR_LEAF'})
    assert start(state)['review_reason'] == 'natural_learning_replacement_plan_mismatch'


def test_other_dialogue_or_unreadable_text_is_not_automatically_a_case():
    assert control.context(text_at((1, 14, 'IVYSAUR used'), (1, 16, 'VINE WHIP!')), progress()) is None
    assert control.context({'cells': []}, progress()) is None
    state = progress()
    start(state)
    assert control.context({'cells': []}, state)['review_reason'] == 'natural_learning_text_unreadable'


def fearow_progress():
    state = progress()
    state['party'][0]['level'] = 29
    state['party'][2]['level'] = 25
    return state


def start_mirror(state):
    return control.context(text_at((1, 14, 'FEAROW is'), (1, 16, 'trying to learn')), state)


def mirror_to_delete_no(state):
    start_mirror(state)
    control.context(text_at((1, 14, 'MIRROR MOVE!')), state)
    return control.context(question('Delete an older', 'move?', selected='NO'), state)


def mirror_to_abandon_yes(state):
    mirror_to_delete_no(state)
    return control.context(question('Abandon learning', 'MIRROR MOVE?'), state)


def test_fearow25_full_skip_preserves_all_four_moves_and_confirms_did_not_learn():
    state = fearow_progress()
    original = copy.deepcopy(state)
    assert start_mirror(state)['learning_tactic'] == 'advance_verified_mirror_move_intro'
    control.context(text_at((1, 14, 'MIRROR MOVE!')), state)
    result = control.context(question('Delete an older', 'move?'), state)
    assert result['menu_label'] == 'NO' and result['objective'] == 'Move DOWN.'
    result = control.context(question('Delete an older', 'move?', selected='NO'), state)
    assert result['menu_label'] == 'NO' and result['available_actions'] == ['a', 'wait']
    result = control.context(question('Abandon learning', 'MIRROR MOVE?', selected='NO'), state)
    assert result['menu_label'] == 'YES' and result['objective'] == 'Move UP.'
    result = control.context(question('Abandon learning', 'MIRROR MOVE?'), state)
    assert result['available_actions'] == ['a', 'wait']
    result = control.context(text_at((1, 14, 'FEAROW did not'), (1, 16, 'learn MIRROR MOVE!')), state)
    assert result['learning_complete'] and result['learning_moves_unchanged']
    assert result['moves_verified'] == [64, 45, 43, 31] and result['learning_result'] == 'skipped_unchanged'
    assert state == original
    assert control.context(text_at(), state) is None and control._SESSION is None


def test_fearow_wrapped_questions_and_active_cursor_survive_reload():
    state = fearow_progress()
    start_mirror(state)
    control.context(text_at((1, 14, 'MIRROR MOVE!')), state)
    assert control.context(text_at((1, 14, 'Delete')), state)['available_actions'] == ['wait']
    assert control.context(text_at((1, 14, 'Delete an older'), (1, 16, 'move to make room▼')), state)['available_actions'] == ['a', 'wait']
    importlib.reload(control)
    assert control.context(text_at((1, 14, 'for MIRROR')), state)['available_actions'] == ['wait']
    page = question('for MIRROR MOVE?', '', selected='NO')
    page['cells'][3][0] = '▷'
    assert control.context(page, state)['menu_label'] == 'NO'
    assert control.context(text_at((1, 14, 'Abandon')), state)['available_actions'] == ['wait']
    control.context(text_at((1, 14, 'Abandon learning▼')), state)
    importlib.reload(control)
    result = control.context(question('MIRROR MOVE?', '', selected='NO'), state)
    assert result['menu_label'] == 'YES' and result['objective'] == 'Move UP.'


def test_fearow_name_and_final_result_can_wrap_across_separate_pages():
    state = fearow_progress()
    start_mirror(state)
    control.context(text_at((1, 14, 'MIRROR▼')), state)
    control.context(text_at((1, 14, 'MOVE!')), state)
    control.context(question('Delete an older', 'move?', selected='NO'), state)
    control.context(question('Abandon learning', 'MIRROR MOVE?'), state)
    assert control.context(text_at((1, 14, 'FEAROW did not'), (1, 16, 'learn▼')), state)['available_actions'] == ['a', 'wait']
    result = control.context(text_at((1, 14, 'MIRROR MOVE!')), state)
    assert result['learning_complete'] and result['learning_moves_unchanged']


def test_fearow_never_answers_choices_before_visually_confirming_mirror_move():
    state = fearow_progress()
    start_mirror(state)
    result = control.context(question('Delete an older', 'move?'), state)
    assert result['review_reason'] == 'fearow_skip_delete_without_confirmed_move'
    assert result['available_actions'] == ['wait']


@pytest.mark.parametrize('which,slot,value', [(2, 0, 119), (2, 3, 119), (0, 1, 45)])
def test_fearow_skip_rejects_changes_to_any_party_move(which, slot, value):
    state = fearow_progress()
    mirror_to_abandon_yes(state)
    state['party'][which]['moves'][slot] = value
    result = control.context(text_at((1, 14, 'FEAROW did not'), (1, 16, 'learn MIRROR MOVE!')), state)
    assert result['review_reason'] == 'fearow_skip_party_changed_unexpectedly'


@pytest.mark.parametrize('first,second', [('Which move should', 'be forgotten?'),
                                        ('FEAROW forgot', 'PECK!'), ('1, 2 and... Poof!', ''),
                                        ('FEAROW learned', 'MIRROR MOVE!')])
def test_fearow_forget_or_learned_screens_always_stop(first, second):
    state = fearow_progress()
    mirror_to_delete_no(state)
    result = control.context(text_at((1, 14, first), (1, 16, second)), state)
    assert result['review_reason'] == 'fearow_skip_unexpected_forget_or_learned_screen'
    assert result['available_actions'] == ['wait']


def test_fearow_requires_strategy_skip_and_does_not_override_replacement(monkeypatch):
    state = fearow_progress()
    monkeypatch.setattr(control, 'learn_move_plan', lambda *args, **kw: {'decision': 'replace', 'move': 'MIRROR_MOVE'})
    assert start_mirror(state)['review_reason'] == 'fearow_skip_strategy_not_verified'
    assert control._SESSION is None


def test_fearow_abandon_cannot_precede_delete_no_or_fake_completion():
    state = fearow_progress()
    start_mirror(state)
    control.context(text_at((1, 14, 'MIRROR MOVE!')), state)
    assert control.context(question('Abandon learning', 'MIRROR MOVE?'), state)['review_reason'] == 'fearow_skip_abandon_before_delete_no'


def test_fearow_did_not_learn_without_abandon_yes_is_not_proof_of_success():
    state = fearow_progress()
    mirror_to_delete_no(state)
    result = control.context(text_at((1, 14, 'FEAROW did not'), (1, 16, 'learn MIRROR MOVE!')), state)
    assert result['review_reason'] == 'fearow_skip_completion_not_verified'


def test_fearow_question_typing_wait_is_bounded_without_pressing_a():
    state = fearow_progress()
    start_mirror(state)
    control.context(text_at((1, 14, 'MIRROR MOVE!')), state)
    for _ in range(30):
        assert control.context(text_at((1, 14, 'Delete')), state)['available_actions'] == ['wait']
    assert control.context(text_at((1, 14, 'Delete')), state)['review_reason'] == 'natural_learning_known_transition_wait_exhausted'


def test_fearow_inactive_only_yes_no_cursor_cannot_confirm_any_option():
    state = fearow_progress()
    start_mirror(state)
    control.context(text_at((1, 14, 'MIRROR MOVE!')), state)
    page = question('Delete an older', 'move?', selected='NO')
    page['cells'][10][14] = '▷'
    assert control.context(page, state)['review_reason'] == 'fearow_skip_yes_no_cursor_unreadable'


def mirror_result_prefix():
    return text_at((1, 14, 'FEAROW'), (1, 16, 'did not learn'), (18, 16, '▼'))


def test_live_mirror_did_not_learn_page_advances_only_then_waits_for_full_move_name():
    state = fearow_progress()
    mirror_to_abandon_yes(state)
    result = control.context(mirror_result_prefix(), state)
    assert result['learning_tactic'] == 'advance_verified_mirror_did_not_learn_page'
    assert result['available_actions'] == ['a', 'wait'] and not result.get('learning_complete')
    for partial in ('M', 'MIRROR', 'MIRROR MOV'):
        result = control.context(text_at((1, 14, partial)), state)
        assert result['available_actions'] == ['wait'] and not result.get('learning_complete')
    result = control.context(text_at((1, 14, 'MIRROR MOVE!')), state)
    assert result['learning_complete'] and result['learning_moves_unchanged']


def legacy_result_timeout_session(state):
    mirror_to_abandon_yes(state)
    control._SESSION.update(schema_version=2, waits=31, last_page='FEAROWDIDNOTLEARN',
                            error='natural_learning_known_transition_wait_exhausted')
    control._SESSION['history'] += 'FEAROWDIDNOTLEARN'


def test_reviewed_v2_result_timeout_migrates_exact_case_once_without_changing_proofs():
    state = fearow_progress()
    legacy_result_timeout_session(state)
    preserved = {name: copy.deepcopy(control._SESSION[name])
                 for name in ('baseline', 'history', 'stage', 'seen_move', 'abandon_yes_requested')}
    importlib.reload(control)
    result = control.context(mirror_result_prefix(), state)
    assert result['available_actions'] == ['a', 'wait'] and not result.get('learning_complete')
    assert control._SESSION['schema_version'] == 3 and control._SESSION['waits'] == 0
    assert not control._SESSION['migration_v3_reviewed_result_page']['completion_verified']
    for name, value in preserved.items():
        assert control._SESSION[name] == value
    control._SESSION['error'] = 'natural_learning_known_transition_wait_exhausted'
    importlib.reload(control)
    assert control.context(mirror_result_prefix(), state)['review_reason'] == 'natural_learning_known_transition_wait_exhausted'


@pytest.mark.parametrize('error', ['fearow_skip_party_changed_unexpectedly',
                                 'fearow_skip_unexpected_forget_or_learned_screen', 'fearow_skip_page_unknown'])
def test_result_page_migration_does_not_clear_other_errors(error):
    state = fearow_progress()
    legacy_result_timeout_session(state)
    control._SESSION['error'] = error
    assert control.context(mirror_result_prefix(), state)['review_reason'] == error


@pytest.mark.parametrize('change', ['wrong_phase', 'without_yes', 'changed_moves'])
def test_reviewed_timeout_requires_exact_page_phase_yes_and_unchanged_fingerprint(change):
    state = fearow_progress()
    legacy_result_timeout_session(state)
    page = mirror_result_prefix()
    if change == 'wrong_phase':
        control._SESSION['stage'] = 'delete_question'
    elif change == 'without_yes':
        control._SESSION['abandon_yes_requested'] = False
    else:
        state['party'][0]['moves'][0] = 75
    result = control.context(page, state)
    assert result['review_reason'] == 'natural_learning_known_transition_wait_exhausted'
    assert control._SESSION['schema_version'] == 2


def test_reviewed_mirror_timeout_without_flashing_arrow_clears_but_only_waits_until_arrow():
    state = fearow_progress()
    legacy_result_timeout_session(state)
    page = mirror_result_prefix()
    page['cells'][16][18] = ' '
    result = control.context(page, state)
    assert result['available_actions'] == ['wait'] and not result.get('learning_complete')
    assert 'error' not in control._SESSION and control._SESSION['schema_version'] == 3
    assert control._SESSION['migration_v3_reviewed_result_page']['advance_requires_visible_marker']
    assert not control._SESSION.get('result_prefix_observed')
    result = control.context(mirror_result_prefix(), state)
    assert result['available_actions'] == ['a', 'wait'] and not result.get('learning_complete')
    assert control._SESSION['result_prefix_observed']


@pytest.mark.parametrize('ending', ['!', '▼'])
def test_mirror_wrapped_did_not_learn_tail_requires_observed_prefix_and_terminal_marker(ending):
    state = fearow_progress()
    mirror_to_abandon_yes(state)
    control.context(mirror_result_prefix(), state)
    page = text_at((1, 14, 'did not learn'), (1, 16, 'MIRROR MOVE' + ending))
    result = control.context(page, state)
    assert result['learning_complete'] and result['learning_moves_unchanged']


@pytest.mark.parametrize('prefix,ending', [(False, '!'), (True, '')])
def test_mirror_wrapped_tail_without_prefix_or_terminal_marker_is_not_complete(prefix, ending):
    state = fearow_progress()
    mirror_to_abandon_yes(state)
    if prefix:
        control.context(mirror_result_prefix(), state)
    result = control.context(text_at((1, 14, 'did not learn'), (1, 16, 'MIRROR MOVE' + ending)), state)
    assert result['available_actions'] == ['wait'] and not result.get('learning_complete')
    assert control._SESSION['stage'] != 'complete'


def poof_page(ending='!'):
    return text_at((10, 7, 'IVYSAUR'), (14, 8, '30'), (10, 10, '73/84'),
                   (1, 14, '1, 2 and... Poof' + ending))


@pytest.mark.parametrize('ending', ['!', '▼'])
def test_live_complete_poof_advances_without_claiming_forgot_or_learned(ending):
    state = progress()
    original = copy.deepcopy(state)
    to_forget(state)
    result = control.context(poof_page(ending), state)
    assert result['available_actions'] == ['a', 'wait']
    assert result['learning_tactic'] == 'advance_verified_poisonpowder_poof'
    assert not result.get('learning_complete') and state == original
    assert control._SESSION['stage'] == 'forget_selected'
    assert not control._SESSION['seen_forgot'] and not control._SESSION['and_requested']


@pytest.mark.parametrize('partial', ['1', '1, 2 and...', '1, 2 and... P', '1, 2 and... Poof', 'Poof!'])
def test_poof_partial_or_unverified_tail_only_waits(partial):
    state = progress()
    to_forget(state)
    result = control.context(text_at((1, 14, partial)), state)
    assert result['available_actions'] == ['wait'] and not result.get('learning_complete')
    assert not control._SESSION['seen_forgot'] and not control._SESSION['and_requested']


@pytest.mark.parametrize('flag', ['seen_move', 'delete_yes_requested'])
def test_complete_poof_requires_both_prior_confirmations(flag):
    state = progress()
    to_forget(state)
    control._SESSION[flag] = False
    # seen_move must remain false rather than be reconstructed from prior history.
    if flag == 'seen_move':
        control._SESSION['history'] = '12ANDPOOF'
    result = control.context(poof_page(), state)
    assert result['review_reason'] == 'natural_learning_poof_without_verified_selection'
    assert result['available_actions'] == ['wait']


def legacy_poof_timeout_session(state):
    to_forget(state)
    control._SESSION.update(schema_version=1, waits=31, last_page='12ANDPOOF',
                            error='natural_learning_known_transition_wait_exhausted')
    control._SESSION['history'] += '12ANDPOOF'


def test_reviewed_poof_timeout_migrates_exact_case_once_and_still_requires_all_result_pages():
    state = progress()
    original = copy.deepcopy(state)
    legacy_poof_timeout_session(state)
    preserved = {name: copy.deepcopy(control._SESSION[name]) for name in
                 ('baseline', 'expected', 'history', 'stage', 'seen_move', 'delete_yes_requested')}
    importlib.reload(control)
    result = control.context(poof_page(), state)
    assert result['available_actions'] == ['a', 'wait'] and not result.get('learning_complete')
    assert control._SESSION['schema_version'] == 2 and control._SESSION['waits'] == 0
    assert 'error' not in control._SESSION
    assert control._SESSION['migration_v2_reviewed_poof_page']['moves_unchanged']
    assert not control._SESSION['migration_v2_reviewed_poof_page']['completion_verified']
    for name, value in preserved.items():
        assert control._SESSION[name] == value
    assert state == original
    # _ForgotAndText有para與And... prompt，不能繼續當自動動畫等待。
    result = control.context(text_at((1, 14, 'IVYSAUR forgot'), (1, 16, 'POISONPOWDER!')), state)
    assert result['available_actions'] == ['a', 'wait'] and not result.get('learning_complete')
    result = control.context(text_at((1, 14, 'And...')), state)
    assert result['available_actions'] == ['a', 'wait'] and not result.get('learning_complete')
    state['party'][0]['moves'][0] = 75
    result = control.context(text_at((1, 14, 'IVYSAUR learned'), (1, 16, 'RAZOR LEAF!')), state)
    assert result['learning_complete'] and result['moves_verified'] == [75, 15, 73, 22]


@pytest.mark.parametrize('change', ['other_error', 'wrong_phase', 'unseen_move', 'without_delete_yes',
                                  'wrong_page', 'partial_page', 'without_terminal', 'changed_moves',
                                  'invalid_party', 'already_migrated'])
def test_poof_timeout_migration_never_clears_other_or_unverified_cases(change):
    state = progress()
    legacy_poof_timeout_session(state)
    page = poof_page()
    error = 'natural_learning_known_transition_wait_exhausted'
    if change == 'other_error':
        error = control._SESSION['error'] = 'natural_learning_unexpected_move_change'
    elif change == 'wrong_phase':
        control._SESSION['stage'] = 'await_forget'
    elif change == 'unseen_move':
        control._SESSION['seen_move'] = False
    elif change == 'without_delete_yes':
        control._SESSION['delete_yes_requested'] = False
    elif change == 'wrong_page':
        control._SESSION['last_page'] = '12AND'
    elif change == 'partial_page':
        page = text_at((1, 14, '1, 2 and... P'))
    elif change == 'without_terminal':
        page = poof_page('')
    elif change == 'changed_moves':
        state['party'][1]['moves'][0] = 31
    elif change == 'invalid_party':
        state['party_read_valid'] = False
    else:
        control._SESSION['schema_version'] = 2
    result = control.context(page, state)
    assert result['review_reason'] == error and result['available_actions'] == ['wait']
    assert 'migration_v2_reviewed_poof_page' not in control._SESSION


def test_poof_timeout_migration_cannot_be_repeated_after_hot_reload():
    state = progress()
    legacy_poof_timeout_session(state)
    control.context(poof_page(), state)
    control._SESSION['error'] = 'natural_learning_known_transition_wait_exhausted'
    importlib.reload(control)
    result = control.context(poof_page(), state)
    assert result['review_reason'] == 'natural_learning_known_transition_wait_exhausted'
    assert control._SESSION['schema_version'] == 2
