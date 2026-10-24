"""38級冰凍光束的隔離候選；畫面皆為合成來源版面，未操作遊戲。"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

import laya_pokemon
from laya_pokemon.team_strategy import learn_move_plan
from tests.test_battle import text_at


_PROJECT_ROOT = Path(laya_pokemon.__file__).resolve().parents[2]


def _candidate_source(test_file):
    """只接受本專案兩個已約定的安裝位置，禁止任意同名鄰檔。"""
    parent = Path(test_file).resolve().parent
    staged = _PROJECT_ROOT / '.local' / 'staged-lapras38-learning-20261024'
    if parent == staged:
        return staged / 'levelup_moves.py'
    if parent == _PROJECT_ROOT / 'tests':
        return _PROJECT_ROOT / 'src' / 'laya_pokemon' / 'levelup_moves.py'
    raise RuntimeError('lapras38 test installation path is not an approved project location')


_SPEC = importlib.util.spec_from_file_location(
    'laya_pokemon._staged_lapras38_learning', _candidate_source(__file__))
control = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(control)


@pytest.fixture(autouse=True)
def fresh_session(monkeypatch):
    monkeypatch.setattr(control, '_SESSION', None)
    monkeypatch.setattr(control.snorlax_harden_skip, '_SESSION', None)


def party():
    mons = [
        (19, 38, [57, 34, 47, 109], [13, 15, 15, 10]),
        (132, 41, [70, 133, 156, 34], [15, 20, 10, 15]),
        (102, 35, [33, 28, 98, 39], [35, 15, 30, 30]),
        (154, 35, [75, 15, 73, 22], [25, 30, 10, 10]),
        (35, 37, [64, 65, 19, 31], [35, 20, 15, 20]),
        (7, 36, [61, 57, 30, 40], [20, 15, 25, 35]),
    ]
    return {'party_read_valid': True, 'money': 60000,
            'inventory': [{'id': 196, 'quantity': 1}, {'id': 198, 'quantity': 1}],
            'party': [dict(species=s, level=l, moves=m, pp=p, hp=156 if i == 0 else 100,
                           max_hp=156 if i == 0 else 120, status=0,
                           exp=68711 if i == 0 else 60000 + i, nickname=f'SYNTHETIC-{i}')
                      for i, (s, l, m, p) in enumerate(mons)]}


def call(page, state):
    original = deepcopy((page, state))
    result = control.context(page, state)
    assert (page, state) == original
    return result


def intro(state):
    return call(text_at((1, 14, 'LAPRAS is'), (1, 16, 'trying to learn')), state)


def choices(selected='YES'):
    return text_at((15, 8, 'YES'), (15, 10, 'NO'),
                   (14, 8 if selected == 'YES' else 10, '▶'), (1, 14, 'for ICE BEAM?'))


def four_moves(row=10):
    return text_at((6, 8, 'SURF'), (6, 9, 'BODY SLAM'), (6, 10, 'SING'),
                   (6, 11, 'CONFUSE RAY'), (5, row, '▶'), (0, 3, '▷'),
                   (1, 14, 'Which move should'), (1, 16, 'be forgotten?'))


def to_question(state):
    intro(state)
    call(text_at((1, 14, 'LAPRAS is'), (1, 16, 'trying to learn  ▼')), state)
    call(text_at((1, 14, 'ICE BEAM!')), state)
    return call(text_at((1, 14, 'Delete an older'), (1, 16, 'move to make room▼')), state)


def to_selected(state):
    to_question(state)
    call(choices(), state)
    return call(four_moves(), state)


def to_and(state):
    to_selected(state)
    call(text_at((1, 14, '1, 2 and... Poof!')), state)
    call(text_at((1, 14, 'LAPRAS forgot'), (1, 16, 'SING!')), state)
    return call(text_at((1, 14, 'And...')), state)


def review(result):
    assert result['phase'] == 'strategy_review'
    assert result['available_actions'] == ['wait']


def test_fixed_source_level_move_pp_and_existing_strategy_agree_on_slot2():
    ref = control.reference()
    assert ref['source_commit'] == 'a53671100ec22e5394ff26ec028d0812a238dae2'
    assert {'level': 38, 'move': 'ICE_BEAM'} in ref['species']['LAPRAS']['level_moves']
    assert (ref['moves']['ICE_BEAM']['id'], ref['moves']['ICE_BEAM']['pp']) == (58, 10)
    result = control.candidate_plan(19, 38, [57, 34, 47, 109])
    assert (result['decision'], result['replace_index'], result['forget'], result['move']) == (
        'replace', 2, 'SING', 'ICE_BEAM')
    assert result['natural_level'] == 38 and result['new_move_id'] == 58
    assert result['ui_candidate_implemented'] is True
    assert learn_move_plan(19, [57, 34, 47, 109], 58, level=38)['replace_index'] == 2


def test_installation_uses_exact_staged_or_official_source_and_rejects_unknown_directory():
    name = 'test_lapras38_ice_beam.py'
    staged = _PROJECT_ROOT / '.local' / 'staged-lapras38-learning-20261024'
    assert _candidate_source(staged / name) == staged / 'levelup_moves.py'
    assert _candidate_source(_PROJECT_ROOT / 'tests' / name) == (
        _PROJECT_ROOT / 'src' / 'laya_pokemon' / 'levelup_moves.py')
    with pytest.raises(RuntimeError, match='not an approved project location'):
        _candidate_source(_PROJECT_ROOT / 'unknown' / name)


@pytest.mark.parametrize('species,level,moves', [
    (19.0, 38, [57, 34, 47, 109]), (19, 38.0, [57, 34, 47, 109]),
    (19, 38, [57, 34, 47.0, 109]), (19, 38, [57, True, 47, 109]),
    (19, 38, None),
])
def test_new_case_requires_typed_source_integers(species, level, moves):
    assert control.candidate_plan(species, level, moves)['decision'] == 'review'


@pytest.mark.parametrize('moves', [[55, 34, 47, 109], [57, 34, 109, 47], [57, 34, 47, 54]])
def test_old_or_reordered_moves_do_not_bind(moves):
    state = party(); state['party'][0]['moves'] = moves
    assert control.candidate_plan(19, 38, moves)['decision'] == 'review'
    review(intro(state)); assert control._SESSION is None


def test_wrong_level_species_and_unverified_source_do_not_claim_case(monkeypatch):
    assert control.candidate_plan(19, 37, [57, 34, 47, 109]) is None
    assert control.candidate_plan(35, 38, [57, 34, 47, 109]) is None
    state = party(); state['party'][0]['level'] = 37
    assert intro(state) is None
    ref = deepcopy(control.reference()); ref['source_commit'] = 'unknown'
    monkeypatch.setattr(control, 'reference', lambda: ref)
    assert control.candidate_plan(19, 38, [57, 34, 47, 109])['decision'] == 'review'


def test_incomplete_initial_intro_never_a_and_wait_is_bounded():
    state = party()
    for _ in range(control.MAX_SAFE_WAITS):
        assert intro(state)['available_actions'] == ['wait']
    assert intro(state)['review_reason'] == 'natural_learning_known_transition_wait_exhausted'


def test_full_flow_changes_only_sing_and_preserves_other_five_bag_money_and_raw_pp():
    state = party(); original = deepcopy(state)
    assert intro(state)['available_actions'] == ['wait']
    assert call(text_at((1, 14, 'ICE BEA')), state)['available_actions'] == ['wait']
    assert call(text_at((1, 14, 'ICE BEAM!')), state)['available_actions'] == ['a', 'wait']
    call(text_at((1, 14, 'But, LAPRAS'), (1, 16, "can't learn more")), state)
    call(text_at((1, 14, 'than 4 moves!')), state)
    call(text_at((1, 14, 'Delete an older'), (1, 16, 'move to make room▼')), state)
    assert call(choices('NO'), state)['available_actions'] == ['up', 'wait']
    assert call(choices(), state)['menu_label'] == 'YES'
    result = call(four_moves(), state)
    assert result['available_actions'] == ['a', 'wait'] and result['forgotten_move'] == 47
    assert result['protected_moves'] == [57, 34, 109]
    assert call(text_at((1, 14, '1, 2 and... Poof!')), state)['available_actions'] == ['a', 'wait']
    assert call(text_at((1, 14, 'LAPRAS forgot'), (1, 16, 'SING!')), state)['available_actions'] == ['a', 'wait']
    assert call(text_at((1, 14, 'And...')), state)['available_actions'] == ['a', 'wait']
    assert state == original
    # 這是測試提供的原生結果，控制器沒有寫入任何觀測或PP。
    state['party'][0]['moves'][2] = 58; state['party'][0]['pp'][2] = 10
    result = call(text_at((1, 14, 'LAPRAS learned'), (1, 16, 'ICE BEAM!')), state)
    assert result['learning_complete'] is True and result['moves_verified'] == [57, 34, 58, 109]
    assert result['protected_moves'] == [57, 34, 109]
    expected = deepcopy(original)
    expected['party'][0]['moves'][2] = 58; expected['party'][0]['pp'][2] = 10
    assert state == expected
    assert call(text_at(), state) is None and control._SESSION is None


@pytest.mark.parametrize('row,action', [(8, 'down'), (9, 'down'), (10, 'a'), (11, 'up')])
def test_only_sing_cursor_can_confirm_and_protects_surf_hm(row, action):
    state = party(); to_question(state); call(choices(), state)
    result = call(four_moves(row), state)
    assert result['available_actions'] == [action, 'wait']
    if action == 'a': assert result['forgotten_move'] == 47


@pytest.mark.parametrize('bad', ['inactive', 'column', 'duplicate', 'labels'])
def test_wrong_forget_cursor_or_labels_never_a(bad):
    state = party(); to_question(state); call(choices(), state); page = four_moves()
    if bad == 'inactive': page['cells'][10][5] = '▷'
    elif bad == 'column': page['cells'][10][5], page['cells'][10][4] = ' ', '▶'
    elif bad == 'duplicate': page['cells'][9][5] = '▶'
    else: page['cells'][10][6:10] = list('MIST')
    review(call(page, state))


@pytest.mark.parametrize('name,move', [('FEAROW', 'SING!'), ('LAPRAS', 'SURF!'), ('LAPRAS', 'CONFUSE RAY!')])
def test_wrong_forgot_name_or_protected_move_latches_review(name, move):
    state = party(); to_selected(state)
    result = call(text_at((1, 14, name + ' forgot'), (1, 16, move)), state)
    review(result)
    assert call(text_at((1, 14, 'And...')), state)['review_reason'] == result['review_reason']


def test_partial_result_and_unknown_beam_suffix_never_a():
    state = party(); intro(state)
    review(call(text_at((1, 14, 'BEAM!')), state))
    control._SESSION = None; state = party(); to_selected(state)
    assert call(text_at((1, 14, 'LAPRAS forgot')), state)['available_actions'] == ['wait']
    call(text_at((1, 14, 'LAPRAS forgot'), (1, 16, 'SING!')), state)
    assert call(text_at((1, 14, 'An')), state)['available_actions'] == ['wait']
    call(text_at((1, 14, 'And...')), state)
    state['party'][0]['moves'][2] = 58
    assert call(text_at((1, 14, 'LAPRAS learned')), state)['available_actions'] == ['wait']


@pytest.mark.parametrize('change', ['learner_level', 'other_species', 'surf', 'duplicate'])
def test_midflow_identity_or_move_drift_stops(change):
    state = party(); to_selected(state)
    if change == 'learner_level': state['party'][0]['level'] = 39
    elif change == 'other_species': state['party'][1]['species'] = 19
    elif change == 'surf': state['party'][0]['moves'][0] = 55
    else: state['party'].append(deepcopy(state['party'][0]))
    review(call(text_at((1, 14, 'LAPRAS forgot'), (1, 16, 'SING!')), state))


def test_early_move_change_and_learned_without_expected_result_review():
    state = party(); to_selected(state); state['party'][0]['moves'][2] = 58
    assert call(text_at((1, 14, 'And...')), state)['review_reason'] == 'natural_learning_move_changed_before_verified_selection'
    control._SESSION = None; state = party(); to_and(state)
    assert call(text_at((1, 14, 'LAPRAS learned'), (1, 16, 'ICE BEAM!')), state)['review_reason'] == 'natural_learning_learned_without_expected_moves'


def test_existing_lapras31_and_hot_reload_keep_same_session_error_and_wait_budget():
    result = control.candidate_plan(19, 31, [57, 34, 47, 54])
    assert result['replace_index'] == 3 and result['forget'] == 'MIST'
    state = party(); state['party'][0].update(level=31, moves=[57, 34, 47, 54])
    assert intro(state)['available_actions'] == ['a', 'wait']
    previous = control._SESSION
    previous['waits'] = 17; previous['error'] = 'existing_review_must_not_be_cleared'
    original = deepcopy(previous)
    _SPEC.loader.exec_module(control)  # 同module globals重載，與原模組的保留方式相同。
    assert control._SESSION is previous and previous == original
    review(intro(state))
    assert previous['waits'] == 17 and previous['error'] == 'existing_review_must_not_be_cleared'


# 父層無按鍵clone的原文字封包；clone_frame不是main campaign frame。
_NATIVE_PROBE_JSON = r'''{"source_frame":1721585,"source_sha256":"6380ee05113e19133c0a362f368868cc2536f488d4fe4f3731a9bab3fc5421d6","no_input":true,"samples":[{"clone_frame":1,"text":{"lines":["          LAPRAS","               38","           156/156"," LAPRAS is"," trying to learn"],"line_rows":[7,8,10,14,16],"cells":[[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," ","L","A","P","R","A","S"," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," ","3","8"," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," ","1","5","6","/","1","5","6"," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" ","L","A","P","R","A","S"," ","i","s"," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" ","t","r","y","i","n","g"," ","t","o"," ","l","e","a","r","n"," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "]],"warnings":["文字候選依 tilemap 字碼推測，尚未完全校準；未核對字型外觀或 sprite 遮罩。"],"profile":"gen1-visible-tile-text-candidates-v1-unvalidated","read_valid":true,"alignment_verified":true,"window_visible":true,"read_error":null}},{"clone_frame":41,"text":{"lines":["          LAPRAS","               38","           156/156"," LAPRAS is"," trying to learn  ▼"],"line_rows":[7,8,10,14,16],"cells":[[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," ","L","A","P","R","A","S"," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," ","3","8"," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," ","1","5","6","/","1","5","6"," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" ","L","A","P","R","A","S"," ","i","s"," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" ","t","r","y","i","n","g"," ","t","o"," ","l","e","a","r","n"," "," ","▼"," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "]],"warnings":["文字候選依 tilemap 字碼推測，尚未完全校準；未核對字型外觀或 sprite 遮罩。"],"profile":"gen1-visible-tile-text-candidates-v1-unvalidated","read_valid":true,"alignment_verified":true,"window_visible":true,"read_error":null}},{"clone_frame":161,"text":{"lines":["          LAPRAS","               38","           156/156"," LAPRAS is"," trying to learn  ▼"],"line_rows":[7,8,10,14,16],"cells":[[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," ","L","A","P","R","A","S"," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," ","3","8"," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," ","1","5","6","/","1","5","6"," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" ","L","A","P","R","A","S"," ","i","s"," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" ","t","r","y","i","n","g"," ","t","o"," ","l","e","a","r","n"," "," ","▼"," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "]],"warnings":["文字候選依 tilemap 字碼推測，尚未完全校準；未核對字型外觀或 sprite 遮罩。"],"profile":"gen1-visible-tile-text-candidates-v1-unvalidated","read_valid":true,"alignment_verified":true,"window_visible":true,"read_error":null}},{"clone_frame":761,"text":{"lines":["          LAPRAS","               38","           156/156"," LAPRAS is"," trying to learn"],"line_rows":[7,8,10,14,16],"cells":[[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," ","L","A","P","R","A","S"," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," ","3","8"," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," ","1","5","6","/","1","5","6"," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" ","L","A","P","R","A","S"," ","i","s"," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" ","t","r","y","i","n","g"," ","t","o"," ","l","e","a","r","n"," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "]],"warnings":["文字候選依 tilemap 字碼推測，尚未完全校準；未核對字型外觀或 sprite 遮罩。"],"profile":"gen1-visible-tile-text-candidates-v1-unvalidated","read_valid":true,"alignment_verified":true,"window_visible":true,"read_error":null}},{"clone_frame":1961,"text":{"lines":["          LAPRAS","               38","           156/156"," LAPRAS is"," trying to learn"],"line_rows":[7,8,10,14,16],"cells":[[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," ","L","A","P","R","A","S"," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," ","3","8"," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," ","1","5","6","/","1","5","6"," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" ","L","A","P","R","A","S"," ","i","s"," "," "," "," "," "," "," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "],[" ","t","r","y","i","n","g"," ","t","o"," ","l","e","a","r","n"," "," "," "," "],[" "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "," "]],"warnings":["文字候選依 tilemap 字碼推測，尚未完全校準；未核對字型外觀或 sprite 遮罩。"],"profile":"gen1-visible-tile-text-candidates-v1-unvalidated","read_valid":true,"alignment_verified":true,"window_visible":true,"read_error":null}}]}'''


def test_fixed_no_input_probe_waits_without_arrow_and_advances_exact_native_first_prompt():
    probe = json.loads(_NATIVE_PROBE_JSON)
    assert probe['no_input'] is True and probe['source_frame'] == 1721585
    assert [sample['clone_frame'] for sample in probe['samples']] == [1, 41, 161, 761, 1961]
    state = party()
    for sample in probe['samples']:
        page = sample['text']
        result = call(page, state)
        lower = ''.join(''.join(row) for row in page['cells'][12:])
        expected = ['a', 'wait'] if '▼' in lower else ['wait']
        assert result['available_actions'] == expected
        assert control._SESSION['seen_move'] is False
        assert control._SESSION['delete_yes_requested'] is False


@pytest.mark.parametrize('line', ['trying to lea  ▼', 'ICE BEA▼'])
def test_arrow_on_other_known_intro_prefix_does_not_authorize_a(line):
    state = party(); intro(state)
    page = (text_at((1, 14, 'LAPRAS is'), (1, 16, line))
            if line.startswith('trying') else text_at((1, 14, line)))
    assert call(page, state)['available_actions'] == ['wait']


@pytest.mark.parametrize('move', ['ICE PUNCH!', 'HYDRO PUMP!'])
def test_other_move_after_initial_prompt_is_still_review(move):
    state = party(); intro(state)
    prompt = text_at((1, 14, 'LAPRAS is'), (1, 16, 'trying to learn  ▼'))
    assert call(prompt, state)['available_actions'] == ['a', 'wait']
    review(call(text_at((1, 14, move)), state))
    assert control._SESSION['delete_yes_requested'] is False
