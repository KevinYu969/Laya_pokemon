"""固定來源卡比獸41級略過變硬；純合成觀測，沒有遊戲／模型呼叫。"""
from copy import deepcopy
import importlib
from types import SimpleNamespace

import pytest

from laya_pokemon import levelup_moves, snorlax_harden_skip as control
from tests.test_battle import text_at as synthetic_cells


def text_at(*entries):
    """本檔fixture明示真decoder契約；不修改共用text_at。"""
    text = synthetic_cells(*entries)
    text.update(profile=control.TEXT_PROFILE, read_valid=True, alignment_verified=True,
                read_error=None, window_visible=True)
    return text


def closed_text():
    text = text_at()
    text['window_visible'] = False
    return text


@pytest.fixture(autouse=True)
def fresh_sessions(monkeypatch):
    monkeypatch.setattr(control, '_SESSION', None)
    monkeypatch.setattr(levelup_moves, '_SESSION', None)


def progress():
    mons = [(7, 'NIDOKING', [61, 57, 30, 40], [20, 15, 25, 35]),
            (19, 'LAPRAS', [55, 34, 47, 54], [25, 15, 15, 30]),
            (102, 'EEVEE', [33, 28, 98, 39], [35, 15, 30, 30]),
            (154, 'VENUSAUR', [75, 15, 73, 22], [25, 30, 10, 10]),
            (35, 'FEAROW', [64, 65, 43, 31], [35, 20, 30, 20]),
            (132, 'SNORLAX', [70, 133, 156, 34], [15, 20, 10, 7])]
    return {'profile': 'gen1-wrapper-ram-progress-v1-unvalidated', 'initialization_candidate': True,
            'party_read_valid': True, 'party_count': 6, 'party': [
                {'species': s, 'species_name': name, 'level': 41 if s == 132 else 35,
                 'exp': 87285 if s == 132 else 50000, 'hp': 187 if s == 132 else 100,
                 'max_hp': 198 if s == 132 else 100, 'status': 0, 'moves': moves, 'pp': pp}
                for s, name, moves, pp in mons]}


def intro():
    return text_at((1, 14, 'SNORLAX is'), (1, 16, 'trying to learn'))


def question(kind, selected='YES'):
    words = [(1, 14, 'for HARDEN?')] if kind == 'delete' else [
        (1, 14, 'Abandon learning'), (1, 16, 'HARDEN?')]
    return text_at((16, 8, 'YES'), (16, 10, 'NO'),
                   (15, 8 if selected == 'YES' else 10, '▶'), *words)


def prefix(arrow=True):
    return text_at((1, 14, 'SNORLAX'), (1, 16, 'did not learn'),
                   *((18, 16, '▼'),) if arrow else ())


def to_delete(p):
    control.context(intro(), p)
    control.context(text_at((1, 14, 'trying to learn'), (1, 16, 'HARDEN!')), p)
    return control.context(text_at((1, 14, 'Delete an older'),
                                   (1, 16, 'move to make room'), (18, 16, '▼')), p)


def to_abandon(p):
    to_delete(p)
    return control.context(question('delete', 'NO'), p)


def to_result(p):
    to_abandon(p)
    return control.context(question('abandon', 'YES'), p)


def review(result):
    assert result['phase'] == 'strategy_review' and result['available_actions'] == ['wait']


def test_reference_and_strategy_are_exact_level41_harden_skip():
    ref = control.reference()
    assert ref['source_commit'] == control.SOURCE_COMMIT
    assert {'level': 41, 'move': 'HARDEN'} in ref['species']['SNORLAX']['level_moves']
    assert ref['moves']['HARDEN']['id'] == 106
    plan = control.learn_move_plan(132, [70, 133, 156, 34], 106, level=41)
    assert plan == {'decision': 'skip', 'reason': 'preserve_higher_priority_moves', 'move': 'HARDEN'}


def test_complete_native_skip_preserves_whole_party_and_hm_without_any_forget_menu():
    p = progress(); original = deepcopy(p)
    assert control.context(intro(), p)['available_actions'] == ['wait']
    assert control.context(text_at((1, 14, 'SNORLAX is'), (1, 16, 'trying to learn'),
                                   (18, 16, '▼')), p)['available_actions'] == ['a', 'wait']
    assert control.context(text_at((1, 14, 'trying to learn'), (1, 16, 'HARDEN!')), p)['available_actions'] == ['a', 'wait']
    assert control.context(text_at((1, 14, 'But, SNORLAX'), (1, 16, "can't learn more"),
                                   (18, 16, '▼')), p)['available_actions'] == ['a', 'wait']
    assert control.context(text_at((1, 14, "can't learn more"), (1, 16, 'than 4 moves!')), p)['available_actions'] == ['a', 'wait']
    assert control.context(text_at((1, 14, 'Delete an older'), (1, 16, 'move to make room'),
                                   (18, 16, '▼')), p)['available_actions'] == ['a', 'wait']
    assert control.context(question('delete', 'YES'), p)['objective'] == 'Move DOWN.'
    result = control.context(question('delete', 'NO'), p)
    assert result['menu_label'] == 'NO' and result['available_actions'] == ['a', 'wait']
    assert control.context(question('abandon', 'NO'), p)['objective'] == 'Move UP.'
    assert control.context(question('abandon', 'YES'), p)['available_actions'] == ['a', 'wait']
    assert control.context(prefix(False), p)['available_actions'] == ['wait']
    result = control.context(prefix(), p)
    assert result['available_actions'] == ['a', 'wait'] and not result.get('learning_complete')
    assert control.context(text_at((1, 14, 'did not learn'), (1, 16, 'HARD')), p)['available_actions'] == ['wait']
    result = control.context(text_at((1, 14, 'did not learn'), (1, 16, 'HARDEN!')), p)
    assert result['learning_complete'] is True and result['learning_result'] == 'skipped_unchanged'
    assert result['moves_verified'] == result['protected_moves'] == [70, 133, 156, 34]
    assert p == original
    assert control.context(closed_text(), p) is None and control._SESSION is None


@pytest.mark.parametrize('bad', ['level40', 'moves', 'duplicate', 'not_readable', 'five'])
def test_initial_wrong_party_level_or_moves_never_take_irreversible_action(bad):
    p = progress()
    if bad == 'level40': p['party'][5]['level'] = 40
    elif bad == 'moves': p['party'][5]['moves'][0] = 29
    elif bad == 'duplicate': p['party'][0] = deepcopy(p['party'][5])
    elif bad == 'not_readable': p['party_read_valid'] = False
    else: p['party'].pop(0); p['party_count'] = 5
    result = control.context(intro(), p)
    review(result)
    importlib.reload(levelup_moves)
    assert control.context(intro(), progress())['review_reason'] == result['review_reason']


def test_different_learner_does_not_intercept_existing_cases():
    assert control.context(text_at((1, 14, 'LAPRAS is'), (1, 16, 'trying to learn')), progress()) is None


def test_strategy_or_source_disagreement_never_binds(monkeypatch):
    monkeypatch.setattr(control, 'learn_move_plan', lambda *a, **kw: {'decision': 'replace', 'move': 'HARDEN'})
    review(control.context(intro(), progress()))
    assert control._SESSION['error'] == 'strategy_skip_unverified'


@pytest.mark.parametrize('kind', ['delete', 'abandon'])
@pytest.mark.parametrize('bad', ['inactive', 'wrong_x', 'double', 'missing_no', 'duplicate_yes', 'partial'])
def test_only_full_source_yes_no_with_one_active_cursor_can_confirm(kind, bad):
    p = progress()
    to_delete(p) if kind == 'delete' else to_abandon(p)
    page = question(kind, 'NO' if kind == 'delete' else 'YES')
    row = 10 if kind == 'delete' else 8
    if bad == 'inactive': page['cells'][row][15] = '▷'
    elif bad == 'wrong_x': page['cells'][row][15] = ' '; page['cells'][row][14] = '▶'
    elif bad == 'double': page['cells'][8 if row == 10 else 10][15] = '▶'
    elif bad == 'missing_no': page['cells'][10][16:18] = list('  ')
    elif bad == 'duplicate_yes': page['cells'][0][0:3] = list('YES')
    else: page['cells'][8][18] = ' '
    result = control.context(page, p)
    assert result['available_actions'] == ['wait']
    assert not control._SESSION['delete_no'] if kind == 'delete' else not control._SESSION['abandon_yes']


def test_fake_laya_wait_allows_retrying_same_safe_direction_and_no_confirmation():
    p = progress(); to_delete(p)
    original = deepcopy(p)
    assert control.context(question('delete', 'YES'), p)['objective'] == 'Move DOWN.'
    chosen_by_fake_laya = 'wait'
    assert chosen_by_fake_laya == 'wait' and p == original
    assert control.context(text_at(), p)['available_actions'] == ['wait']
    assert control.context(deepcopy(question('delete', 'YES')), p)['objective'] == 'Move DOWN.'
    assert control.context(question('delete', 'NO'), p)['available_actions'] == ['a', 'wait']
    assert control.context(text_at(), p)['available_actions'] == ['wait']
    assert control.context(deepcopy(question('delete', 'NO')), p)['available_actions'] == ['a', 'wait']
    assert p == original


def test_fake_laya_wait_can_retry_verified_abandon_yes_after_blank_or_reload():
    p = progress(); to_result(p)
    control.context(text_at(), p)
    importlib.reload(levelup_moves)
    assert control.context(deepcopy(question('abandon', 'YES')), p)['available_actions'] == ['a', 'wait']


@pytest.mark.parametrize('first,second', [('FEAROW', 'did not learn'), ('SNORLAX forgot', 'STRENGTH!'),
    ('SNORLAX learned', 'HARDEN!'), ('Which move should', 'be forgotten?'), ('1, 2 and... Poof!', ''),
    ('Abandon learning', 'BODY SLAM?'), ('for MIST?', ''), ('EN!', '')])
def test_wrong_name_move_unknown_tail_or_forget_screen_latches_review(first, second):
    p = progress(); to_result(p)
    result = control.context(text_at((1, 14, first), (1, 16, second)), p)
    review(result)
    importlib.reload(levelup_moves)
    assert control.context(prefix(), p)['review_reason'] == result['review_reason']


@pytest.mark.parametrize('member,key,value', [(0, 'hp', 99), (1, 'exp', 50001),
    (5, 'moves', [106, 133, 156, 34]), (5, 'pp', [15, 20, 10, 6]), (5, 'level', 42)])
def test_any_party_field_change_stops_before_result_confirmation(member, key, value):
    p = progress(); to_result(p); p['party'][member][key] = value
    result = control.context(prefix(), p)
    assert result['review_reason'] == 'snorlax_harden_skip_party_changed'
    review(result)


def test_did_not_learn_prefix_arrow_is_required_before_harden_tail():
    p = progress(); to_result(p)
    assert control.context(text_at((1, 14, 'SNORLAX'), (1, 16, 'did not lear')), p)['available_actions'] == ['wait']
    review(control.context(text_at((1, 14, 'HARDEN!')), p))


def test_result_prefix_and_tail_partials_wait_without_a_and_cannot_fake_success():
    p = progress(); to_result(p)
    control.context(prefix(), p)
    for text in ('H', 'HARD', 'HARDEN'):
        result = control.context(text_at((1, 14, text)), p)
        assert result['available_actions'] == ['wait'] and not result.get('learning_complete')
    result = control.context(text_at((1, 14, 'HARDEN!')), p)
    assert result['learning_complete'] is True
    assert control.context(text_at((1, 14, 'HARDEN!')), p)['available_actions'] == ['a', 'wait']


def test_fake_laya_wait_can_retry_source_cont_and_final_prompt_but_not_partial():
    p = progress(); to_result(p)
    original = deepcopy(p)
    for _ in range(2):
        assert control.context(deepcopy(prefix()), p)['available_actions'] == ['a', 'wait']
    assert control.context(text_at((1, 14, 'HARDEN')), p)['available_actions'] == ['wait']
    for _ in range(2):
        result = control.context(text_at((1, 14, 'HARDEN!')), p)
        assert result['available_actions'] == ['a', 'wait'] and result['learning_complete'] is True
    assert control.context(text_at((1, 14, 'HARDEN')), p)['available_actions'] == ['wait']
    assert p == original


def test_old_complete_result_with_unexpected_active_cursor_never_reconfirms():
    p = progress(); to_result(p)
    control.context(prefix(), p)
    control.context(text_at((1, 14, 'HARDEN!')), p)
    review(control.context(text_at((1, 14, 'HARDEN!'), (0, 0, '▶')), p))


def test_thirty_total_safe_waits_and_sticky_error_survive_reload():
    p = progress()
    for _ in range(15): assert control.context(intro(), p)['available_actions'] == ['wait']
    importlib.reload(levelup_moves)
    for _ in range(15): assert control.context(intro(), p)['available_actions'] == ['wait']
    result = control.context(intro(), p)
    assert result['review_reason'] == 'snorlax_harden_skip_safe_wait_exhausted'
    importlib.reload(levelup_moves)
    review(control.context(text_at((1, 14, 'HARDEN!')), p))


def test_observe_dispatches_snorlax_skip_before_general_battle(monkeypatch):
    from laya_pokemon import battle, game, navigation, observation, progress as progress_module
    p = progress(); page = intro(); page.update(warnings=[])
    monkeypatch.setattr(observation, 'read_visible_text', lambda _: page)
    monkeypatch.setattr(observation, 'opening_context', lambda *a: {})
    monkeypatch.setattr(progress_module, 'read_progress', lambda _: p)
    monkeypatch.setattr(navigation, 'read_location', lambda _: {'map_id': 235, 'x': 6, 'y': 13})
    monkeypatch.setattr(battle, 'read_battle_state', lambda _: {'active': True, 'raw': 2, 'kind': 'trainer'})
    monkeypatch.setattr(battle, 'battle_context', lambda *a, **kw: pytest.fail('學招應先接管'))
    emulator = SimpleNamespace(frame_count=1, screen=SimpleNamespace(ndarray=SimpleNamespace(tobytes=lambda: b'fake')))
    result = game.observe(emulator, 'Wait.', opening_route=True, route_stage='first_gym')
    assert result['learning_controller'] == 'snorlax41_harden_skip'
    assert result['available_actions'] == ['wait']


def native_but(tail='lear', arrow=False):
    page = text_at((1, 14, 'But, SNORLAX'))
    tokens = ['c', 'a', 'n', "'t", ' ', *tail]
    page['cells'][16][1:1 + len(tokens)] = tokens
    if arrow: page['cells'][16][18] = '▼'
    page.update(profile='gen1-visible-tile-text-candidates-v1-unvalidated', read_valid=True,
                alignment_verified=True, window_visible=True, read_error=None)
    return page


def legacy_token_error(p):
    control.context(intro(), p)
    control.context(text_at((1, 14, 'HARDEN!')), p)
    control._SESSION['error'] = 'text_unreadable'


def test_native_single_tile_t_partial_only_waits_without_changing_physical_columns():
    p = progress(); control.context(intro(), p)
    control.context(text_at((1, 14, 'HARDEN!')), p)
    page = native_but(); original = deepcopy(page)
    assert len(page['cells'][16]) == 20 and len(control._rows(page)[16]) == 21
    result = control.context(page, p)
    assert result['available_actions'] == ['wait'] and page == original
    # 真▼仍在實體第18格，不能因't展開而誤判成第19格。
    result = control.context(native_but('learn more', arrow=True), p)
    assert result['available_actions'] == ['a', 'wait']


@pytest.mark.parametrize('y,token', [(16, "'s"), (16, 'XX'), (8, "'t"), (10, "'t")])
def test_unknown_multi_character_or_upper_menu_tile_stays_unreadable(y, token):
    p = progress(); to_delete(p)
    page = question('delete', 'NO')
    page['cells'][y][16 if y in (8, 10) else 4] = token
    result = control.context(page, p)
    review(result)
    assert result['review_reason'] == 'snorlax_harden_skip_text_unreadable'


def test_reviewed_exact_old_intro_error_migrates_once_without_resetting_wait_budget():
    p = progress(); legacy_token_error(p)
    old_party, waits = deepcopy(control._SESSION['party']), control._SESSION['waits']
    importlib.reload(levelup_moves)
    result = control.context(native_but(), p)
    assert result['available_actions'] == ['wait'] and control._SESSION['error'] is None
    assert control._SESSION['waits'] == waits + 1 and control._SESSION['party'] == old_party
    assert control._SESSION['reviewed_token_migration']['sdk_byte'] == 0xBE
    assert control._SESSION['reviewed_token_migration']['recovery_action'] == 'wait_only'
    control._SESSION['error'] = 'text_unreadable'
    importlib.reload(levelup_moves)
    assert control.context(native_but(), p)['review_reason'] == 'snorlax_harden_skip_text_unreadable'


@pytest.mark.parametrize('bad', ['party', 'stage', 'seen', 'delete', 'abandon', 'other_error',
                                 'read_invalid', 'no_token', 'other_page'])
def test_migration_does_not_clear_other_errors_or_mismatching_old_transaction(bad):
    p = progress(); legacy_token_error(p); page = native_but()
    if bad == 'party': p['party'][0]['hp'] -= 1
    elif bad == 'stage': control._SESSION['stage'] = 'delete_question'
    elif bad == 'seen': control._SESSION['seen_move'] = False
    elif bad == 'delete': control._SESSION['delete_no'] = True
    elif bad == 'abandon': control._SESSION['abandon_yes'] = True
    elif bad == 'other_error': control._SESSION['error'] = 'party_changed'
    elif bad == 'read_invalid': page['read_valid'] = False
    elif bad == 'no_token': page['cells'][16][4] = 't'
    else: page['cells'][14] = [' '] * 20
    expected = 'snorlax_harden_skip_' + control._SESSION['error']
    assert control.context(page, p)['review_reason'] == expected
    assert 'reviewed_token_migration' not in control._SESSION


def test_unknown_multitile_cannot_reclassify_other_sticky_error_into_migratable_error():
    p = progress(); legacy_token_error(p)
    control._SESSION['error'] = 'party_changed'
    page = native_but(); page['cells'][16][4] = 'XX'
    assert control.context(page, p)['review_reason'] == 'snorlax_harden_skip_party_changed'
    assert control.context(native_but(), p)['review_reason'] == 'snorlax_harden_skip_party_changed'
    assert 'reviewed_token_migration' not in control._SESSION


@pytest.mark.parametrize('kind', ['delete', 'abandon'])
@pytest.mark.parametrize('key,value', [('window_visible', False), ('profile', 'wrong'),
    ('read_error', 'visible_display_disabled'), ('read_valid', 1), ('alignment_verified', 1)])
def test_complete_question_with_contradictory_or_untyped_decoder_metadata_never_confirms(kind, key, value):
    p = progress()
    to_delete(p) if kind == 'delete' else to_abandon(p)
    page = question(kind, 'NO' if kind == 'delete' else 'YES')
    page[key] = value
    result = control.context(page, p)
    review(result)
    assert result['review_reason'] == 'snorlax_harden_skip_decoder_unverified'


@pytest.mark.parametrize('missing', ['profile', 'read_valid', 'alignment_verified', 'window_visible'])
def test_missing_decoder_metadata_cannot_advance_partial_or_full_intro(missing):
    p = progress(); page = intro(); page.pop(missing)
    result = control.context(page, p)
    review(result)
    assert result['review_reason'] == 'snorlax_harden_skip_decoder_unverified'


def test_read_error_may_be_absent_but_all_other_decoder_evidence_still_required():
    p = progress(); to_delete(p)
    page = question('delete', 'NO'); page.pop('read_error')
    assert control.context(page, p)['available_actions'] == ['a', 'wait']


def test_complete_receipt_cannot_close_on_stale_open_window_or_fake_closed_metadata():
    p = progress(); to_result(p); control.context(prefix(), p)
    control.context(text_at((1, 14, 'HARDEN!')), p)
    assert control.context(text_at(), p)['available_actions'] == ['wait']
    page = closed_text(); page['profile'] = 'wrong'
    review(control.context(page, p))
    assert control._SESSION is not None


def test_old_result_with_window_false_neither_confirms_nor_clears_session():
    p = progress(); to_result(p); control.context(prefix(), p)
    control.context(text_at((1, 14, 'HARDEN!')), p)
    page = text_at((1, 14, 'HARDEN!')); page['window_visible'] = False
    review(control.context(page, p))
    assert control._SESSION is not None


@pytest.mark.parametrize('key,value', [('profile', 'wrong'), ('read_error', 'visible_display_disabled'),
                                     ('window_visible', False)])
def test_reviewed_t_migration_cannot_bypass_required_decoder_metadata(key, value):
    p = progress(); legacy_token_error(p); page = native_but(); page[key] = value
    result = control.context(page, p)
    assert result['review_reason'] == 'snorlax_harden_skip_text_unreadable'
    assert 'reviewed_token_migration' not in control._SESSION


@pytest.mark.parametrize('kind', ['delete', 'abandon'])
def test_foreign_inactive_cursor_cannot_confirm_or_reset_existing_transaction(kind):
    p = progress()
    to_delete(p) if kind == 'delete' else to_abandon(p)
    before = deepcopy(control._SESSION)
    page = question(kind, 'NO' if kind == 'delete' else 'YES')
    page['cells'][0][0] = '▷'
    result = control.context(page, p)
    review(result)
    assert result['review_reason'] == 'snorlax_harden_skip_unexpected_inactive_cursor'
    assert control._SESSION == {**before, 'error': 'unexpected_inactive_cursor'}
    assert control.context(question(kind), p)['review_reason'] == result['review_reason']


def post_skip_ready():
    p = progress()
    p['story_event_bits'] = {'beat_silph_co_rival': True, 'silph_co_11_unlocked_door': True,
                             'beat_silph_co_giovanni': False}
    to_result(p); control.context(prefix(), p)
    control.context(text_at((1, 14, 'did not learn'), (1, 16, 'HARDEN!')), p)
    return p


def next_giovanni(first='GIOVANNI sent', second='out RHYHORN!'):
    return text_at((1, 14, first), (1, 16, second))


def test_source_giovanni_rhyhorn_prefixes_wait_then_only_complete_sentence_hands_off():
    p = post_skip_ready(); baseline = deepcopy(p)
    for first, second in [('GIOVA', ''), ('GIOVAN', ''), ('GIOVANNI sent', ''),
                          ('GIOVANNI sent', 'out RHYHORN')]:
        result = control.context(next_giovanni(first, second), p)
        assert result['available_actions'] == ['wait'] and not result.get('learning_complete')
        assert result['learning_tactic'] == 'await_complete_giovanni_rhyhorn_sendout'
    assert control.context(next_giovanni(), p) is None
    assert control._SESSION is None and p == baseline


def test_exact_old_handoff_error_migrates_once_and_preserves_original_wait_budget():
    p = post_skip_ready()
    control._SESSION.update(error='closed_after_skip_unverified', waits=10,
                            reviewed_token_migration={'existing_audit': True})
    baseline = deepcopy(control._SESSION['party'])
    importlib.reload(levelup_moves)
    result = control.context(next_giovanni('GIOVA', ''), p)
    assert result['available_actions'] == ['wait'] and control._SESSION['waits'] == 11
    assert control._SESSION['error'] is None and control._SESSION['party'] == baseline
    assert control._SESSION['reviewed_token_migration'] == {'existing_audit': True}
    assert result['reviewed_post_skip_migration']['full_action'] == 'handoff_no_button'
    control._SESSION['error'] = 'closed_after_skip_unverified'
    review(control.context(next_giovanni('GIOVA', ''), p))


@pytest.mark.parametrize('bad', ['party', 'stage', 'delete', 'abandon', 'prefix', 'other_error',
    'wrong_trainer', 'wrong_mon', 'partial_metadata', 'foreign_cursor', 'foreign_inactive',
    'unknown_flag', 'already_won'])
def test_post_skip_migration_never_clears_nonmatching_session_or_unknown_message(bad):
    p = post_skip_ready(); page = next_giovanni()
    control._SESSION['error'] = 'closed_after_skip_unverified'
    if bad == 'party': p['party'][0]['hp'] -= 1
    elif bad == 'stage': control._SESSION['stage'] = 'intro'
    elif bad == 'delete': control._SESSION['delete_no'] = False
    elif bad == 'abandon': control._SESSION['abandon_yes'] = False
    elif bad == 'prefix': control._SESSION['result_prefix'] = False
    elif bad == 'other_error': control._SESSION['error'] = 'party_changed'
    elif bad == 'wrong_trainer': page = next_giovanni('ROCKET sent')
    elif bad == 'wrong_mon': page = next_giovanni(second='out NIDOQUEEN!')
    elif bad == 'partial_metadata': page.pop('read_valid')
    elif bad == 'foreign_cursor': page['cells'][0][0] = '▶'
    elif bad == 'foreign_inactive': page['cells'][0][0] = '▷'
    elif bad == 'unknown_flag': p['story_event_bits']['beat_silph_co_rival'] = 1
    else: p['story_event_bits']['beat_silph_co_giovanni'] = True
    expected = 'snorlax_harden_skip_' + control._SESSION['error']
    assert control.context(page, p)['review_reason'] == expected
    assert 'reviewed_post_skip_migration' not in control._SESSION


def test_unknown_next_battle_text_is_reviewed_instead_of_generic_handoff():
    p = post_skip_ready()
    review(control.context(text_at((1, 14, 'Wild RHYHORN'), (1, 16, 'appeared!')), p))


def test_post_skip_partial_wait_limit_is_not_reset_by_reload_or_migration():
    p = post_skip_ready()
    control._SESSION.update(error='closed_after_skip_unverified', waits=29)
    assert control.context(next_giovanni('GIOVA', ''), p)['available_actions'] == ['wait']
    importlib.reload(levelup_moves)
    result = control.context(next_giovanni('GIOVAN', ''), p)
    assert result['review_reason'] == 'snorlax_harden_skip_safe_wait_exhausted'


def about_giovanni(second='about to use', arrow=False):
    page = text_at((1, 14, 'GIOVANNI is'), (1, 16, second))
    if arrow: page['cells'][16][18] = '▼'
    return page


def test_source_about_to_use_partial_and_arrow_blink_wait_then_full_cont_hands_off():
    p = post_skip_ready(); original = deepcopy(p)
    for second in ('about to', 'about to us', 'about to use'):
        result = control.context(about_giovanni(second), p)
        assert result['available_actions'] == ['wait']
        assert result['learning_tactic'] == 'await_complete_giovanni_about_to_use'
    assert control.context(about_giovanni(arrow=True), p) is None
    assert control._SESSION is None and p == original


def test_second_named_migration_preserves_first_history_and_original_wait_count():
    p = post_skip_ready()
    first_history = {'next_source_message': 'GIOVANNI sent / out RHYHORN!', 'wait_budget_preserved': True}
    control._SESSION.update(error='closed_after_skip_unverified', waits=12,
                            reviewed_post_skip_migration=deepcopy(first_history),
                            reviewed_token_migration={'prior_token_audit': True})
    importlib.reload(levelup_moves)
    result = control.context(about_giovanni('about to'), p)
    assert result['available_actions'] == ['wait'] and control._SESSION['waits'] == 13
    assert control._SESSION['reviewed_post_skip_migration'] == first_history
    assert control._SESSION['reviewed_token_migration'] == {'prior_token_audit': True}
    assert result['reviewed_about_to_use_migration']['handoff_means_learning_finished_only'] is True
    control._SESSION['error'] = 'closed_after_skip_unverified'
    review(control.context(about_giovanni('about to'), p))


@pytest.mark.parametrize('bad', ['early_arrow', 'exclamation_instead_of_cont', 'wrong_trainer', 'missing_first_history'])
def test_about_migration_rejects_incomplete_wrong_source_or_unreviewed_history(bad):
    p = post_skip_ready(); page = about_giovanni('about to')
    control._SESSION.update(error='closed_after_skip_unverified',
                            reviewed_post_skip_migration={'first_history': True})
    if bad == 'early_arrow': page['cells'][16][18] = '▼'
    elif bad == 'exclamation_instead_of_cont': page = about_giovanni('about to use!')
    elif bad == 'wrong_trainer': page['cells'][14][1:9] = list('ROCKET  ')
    else: control._SESSION.pop('reviewed_post_skip_migration')
    review(control.context(page, p))
    assert control._SESSION['error'] == 'closed_after_skip_unverified'
    assert 'reviewed_about_to_use_migration' not in control._SESSION
