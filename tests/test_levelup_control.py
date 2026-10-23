import copy
import importlib

import pytest

import laya_pokemon.levelup_control as control
from tests.test_battle import text_at


PARTY = [
    {'species': 167, 'level': 23, 'moves': [43, 33, 30, 40], 'hp': 25},
    {'species': 9, 'level': 25, 'moves': [77, 45, 73, 22]},
    {'species': 5, 'level': 19, 'moves': [64, 45, 43, 31]},
]


@pytest.fixture(autouse=True)
def reset_session(monkeypatch):
    monkeypatch.setattr(control, '_SESSION', None)


def intro():
    return control.skip_context(text_at((1, 14, 'NIDORINO is'), (1, 16, 'trying to learn')), PARTY)


def confirm_move():
    intro()
    return control.skip_context(text_at((1, 14, 'FOCUS ENERGY!')), PARTY)


def question(first, second, *, selected='YES'):
    return text_at((15, 7, 'YES'), (15, 9, 'NO'),
                   (14, 7 if selected == 'YES' else 9, '▶'),
                   (1, 14, first), (1, 16, second))


def choose_delete_no():
    confirm_move()
    return control.skip_context(question('Delete an older', 'move?', selected='NO'), PARTY)


def test_complete_skip_sequence_preserves_every_existing_move():
    original = copy.deepcopy(PARTY)
    assert intro()['learning_tactic'] == 'advance_focus_energy_intro'
    assert control.skip_context(text_at((1, 14, 'FOCUS ENERGY!')), PARTY)['learn_move_plan']['decision'] == 'skip'
    result = control.skip_context(question('Delete an older', 'move?', selected='YES'), PARTY)
    assert result['menu_label'] == 'NO' and result['objective'] == 'Move DOWN.'
    result = control.skip_context(question('Delete an older', 'move?', selected='NO'), PARTY)
    assert result['objective'] == 'Confirm the current selection.' and result['menu_label'] == 'NO'
    result = control.skip_context(question('Stop learning', 'FOCUS ENERGY?', selected='NO'), PARTY)
    assert result['menu_label'] == 'YES' and result['objective'] == 'Move UP.'
    result = control.skip_context(question('Stop learning', 'FOCUS ENERGY?', selected='YES'), PARTY)
    assert result['menu_label'] == 'YES' and result['objective'] == 'Confirm the current selection.'
    result = control.skip_context(text_at((1, 14, 'NIDORINO did not'), (1, 16, 'learn FOCUS ENERGY!')), PARTY)
    assert result['learning_tactic'] == 'skip_confirmed' and result['learning_moves_unchanged']
    assert control._SESSION is None and PARTY == original
    assert control.skip_context(text_at(), PARTY) is None


def test_wrapped_questions_remember_no_and_yes_across_pages_and_hot_reload():
    confirm_move()
    result = control.skip_context(text_at((1, 14, 'Delete an older'), (1, 16, 'move to make room▼')), PARTY)
    assert result['learning_tactic'] == 'advance_wrapped_learning_question'
    importlib.reload(control)
    result = control.skip_context(question('move to make room', 'for FOCUS ENERGY?'), PARTY)
    assert result['menu_label'] == 'NO' and result['objective'] == 'Move DOWN.'
    result = control.skip_context(question('move to make room', 'for FOCUS ENERGY?', selected='NO'), PARTY)
    assert result['objective'] == 'Confirm the current selection.'
    result = control.skip_context(text_at((1, 14, 'Stop'), (1, 16, 'learning▼')), PARTY)
    assert result['learning_question'] == 'stop_question'
    importlib.reload(control)
    result = control.skip_context(question('learning', 'FOCUS ENERGY?'), PARTY)
    assert result['menu_label'] == 'YES'


def test_move_name_can_wrap_across_twenty_column_lines():
    intro()
    result = control.skip_context(text_at((1, 14, 'FOCUS'), (1, 16, 'ENERGY!')), PARTY)
    assert result['learning_tactic'] == 'advance_focus_energy_intro'
    assert control._SESSION['confirmed_move']


def test_move_name_can_wrap_across_separate_pages():
    intro()
    control.skip_context(text_at((1, 14, 'FOCUS▼')), PARTY)
    control.skip_context(text_at((1, 14, 'ENERGY!')), PARTY)
    assert control._SESSION['confirmed_move']


def test_yes_no_before_visual_move_confirmation_is_rejected():
    intro()
    result = control.skip_context(question('Delete an older', 'move?'), PARTY)
    assert result['phase'] == 'strategy_review'
    assert result['review_reason'] == 'learning_move_not_visually_confirmed'
    assert result['available_actions'] == ['wait']


@pytest.mark.parametrize('first,second', [('Which move should', 'be forgotten?'),
                                        ('NIDORINO forgot', 'HORN ATTACK!'),
                                        ('1, 2 and... POOF!', '')])
def test_unexpected_forget_screen_cannot_receive_a_confirm(first, second):
    confirm_move()
    result = control.skip_context(text_at((1, 14, first), (1, 16, second)), PARTY)
    assert result['phase'] == 'strategy_review'
    assert result['review_reason'] == 'unexpected_forget_menu_during_skip'


def test_changed_moves_in_any_member_require_review():
    confirm_move()
    changed = copy.deepcopy(PARTY)
    changed[1]['moves'][0] = 33
    result = control.skip_context(question('Delete an older', 'move?'), changed)
    assert result['review_reason'] == 'learning_party_changed_unexpectedly'


@pytest.mark.parametrize('change', ['wrong_level', 'wrong_moves', 'duplicate_learner'])
def test_only_the_bounded_nidorino_case_can_start(change):
    party = copy.deepcopy(PARTY)
    if change == 'wrong_level':
        party[0]['level'] = 24
    elif change == 'wrong_moves':
        party[0]['moves'][0] = 116
    else:
        party.append(copy.deepcopy(party[0]))
    result = control.skip_context(text_at((1, 14, 'NIDORINO is'), (1, 16, 'trying to learn')), party)
    assert result['review_reason'] == 'learning_case_not_verified'


def test_non_skip_strategy_cannot_be_overridden(monkeypatch):
    monkeypatch.setattr(control, 'learn_move_plan', lambda *a, **k: {'decision': 'replace'})
    assert intro()['review_reason'] == 'learning_skip_not_approved_by_strategy'


def test_unknown_move_or_page_stops_without_default_confirm():
    intro()
    result = control.skip_context(text_at((1, 14, 'FURY ATTACK!')), PARTY)
    assert result['review_reason'] == 'learning_page_not_verified'


def test_unreadable_cursor_and_unknown_question_stop():
    confirm_move()
    result = control.skip_context(text_at((15, 7, 'YES'), (15, 9, 'NO'),
                                        (1, 14, 'Delete an older'), (1, 16, 'move?')), PARTY)
    assert result['review_reason'] == 'learning_choices_or_cursor_unreadable'


def test_question_cannot_be_inferred_from_previous_intro_move_name():
    confirm_move()
    result = control.skip_context(question('FOCUS ENERGY?', ''), PARTY)
    assert result['review_reason'] == 'learning_question_not_confirmed'


def test_stop_question_requires_a_prior_requested_no_confirmation():
    confirm_move()
    result = control.skip_context(question('Stop learning', 'FOCUS ENERGY?'), PARTY)
    assert result['review_reason'] == 'learning_stop_before_delete_no'


def test_completion_requires_the_stop_yes_request_and_unchanged_moves():
    choose_delete_no()
    result = control.skip_context(text_at((1, 14, 'NIDORINO did not'), (1, 16, 'learn FOCUS ENERGY!')), PARTY)
    assert result['review_reason'] == 'learning_completion_not_verified'


def test_unrelated_battle_text_is_not_claimed_as_a_learning_session():
    assert control.skip_context(text_at((1, 14, 'NIDORINO used'), (1, 16, 'HORN ATTACK!')), PARTY) is None


@pytest.mark.parametrize('partial', ['D', 'De', 'Del', 'Delete', 'Delete an older'])
def test_typing_delete_question_waits_without_pressing_a(partial):
    confirm_move()
    result = control.skip_context(text_at((1, 14, partial)), PARTY)
    assert result['learning_question'] == 'delete_question'
    assert result['available_actions'] == ['wait'] and result['objective'] == 'Wait.'
    assert result['learning_tactic'] == 'wait_for_learning_question_text'


def test_typing_wrapped_move_name_waits_then_returns_to_verified_choices():
    confirm_move()
    control.skip_context(text_at((1, 14, 'Delete')), PARTY)
    result = control.skip_context(text_at((1, 14, 'Delete an older'), (1, 16, 'move to make room▼')), PARTY)
    assert result['learning_tactic'] == 'advance_wrapped_learning_question'
    for partial in ('for F', 'for FOCUS', 'for FOCUS ENER'):
        result = control.skip_context(text_at((1, 14, 'move to make room'), (1, 16, partial)), PARTY)
        assert result['available_actions'] == ['wait']
    result = control.skip_context(question('move to make room', 'for FOCUS ENERGY?'), PARTY)
    assert result['menu_label'] == 'NO' and result['objective'] == 'Move DOWN.'
    assert control._SESSION['question_wait_steps'] == 0


def test_typing_stop_question_also_waits_until_actual_choices():
    choose_delete_no()
    for partial in ('S', 'St', 'Stop', 'Stop learning'):
        result = control.skip_context(text_at((1, 14, partial)), PARTY)
        assert result['learning_question'] == 'stop_question'
        assert result['available_actions'] == ['wait']
    result = control.skip_context(question('Stop learning', 'FOCUS ENERGY?', selected='NO'), PARTY)
    assert result['menu_label'] == 'YES' and result['objective'] == 'Move UP.'


def test_question_typing_wait_has_a_bounded_failure_instead_of_confirming():
    confirm_move()
    page = text_at((1, 14, 'Delete'))
    for step in range(1, 31):
        result = control.skip_context(page, PARTY)
        assert result['available_actions'] == ['wait']
        assert result['learning_question_wait_steps'] == step
    result = control.skip_context(page, PARTY)
    assert result['review_reason'] == 'learning_question_typing_timeout'
    assert result['available_actions'] == ['wait']


def test_v2_migration_once_clears_only_the_reviewed_legacy_typing_error():
    confirm_move()
    control._SESSION.pop('schema_version')
    control._SESSION.pop('question_wait_steps')
    control._SESSION.update(phase='delete_question', failed_reason='learning_question_choices_not_visible')
    preserved = {key: copy.deepcopy(control._SESSION[key])
                 for key in ('fingerprint', 'history', 'confirmed_move', 'phase')}
    importlib.reload(control)
    assert control._SESSION['schema_version'] == control._SCHEMA_VERSION
    assert control._SESSION['migration_v2_cleared_typing_pause']
    assert 'failed_reason' not in control._SESSION
    for key, value in preserved.items():
        assert control._SESSION[key] == value
    result = control.skip_context(text_at((1, 14, 'Delete')), PARTY)
    assert result['available_actions'] == ['wait']
    control._SESSION['failed_reason'] = 'learning_question_choices_not_visible'
    importlib.reload(control)
    result = control.skip_context(text_at((1, 14, 'Delete')), PARTY)
    assert result['review_reason'] == 'learning_question_choices_not_visible'


@pytest.mark.parametrize('reason', ['unexpected_forget_menu_during_skip',
                                  'learning_party_changed_unexpectedly',
                                  'learning_move_not_visually_confirmed'])
def test_v2_migration_never_clears_other_legacy_errors(reason):
    confirm_move()
    control._SESSION.pop('schema_version')
    control._SESSION.update(phase='delete_question', failed_reason=reason)
    importlib.reload(control)
    result = control.skip_context(text_at((1, 14, 'Delete')), PARTY)
    assert result['review_reason'] == reason


@pytest.mark.parametrize('confirmed,phase', [(False, 'delete_question'), (True, 'intro'),
                                           (True, 'stop_question')])
def test_v2_migration_cannot_bypass_move_confirmation_or_other_phase(confirmed, phase):
    intro()
    control._SESSION.pop('schema_version')
    control._SESSION.update(phase=phase, confirmed_move=confirmed,
                            failed_reason='learning_question_choices_not_visible')
    importlib.reload(control)
    assert control._SESSION['failed_reason'] == 'learning_question_choices_not_visible'
