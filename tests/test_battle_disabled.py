"""封招唯讀來源／策略副本及自然學招接點；不啟動遊戲或模型。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

import laya_pokemon.battle as battle
from tests.test_battle import text_at


FEAROW = {'species': 35, 'level': 21, 'hp': 60, 'max_hp': 60,
          'moves': [64, 45, 43, 31], 'pp': [35, 40, 30, 20]}
IVYSAUR = {'species': 9, 'level': 27, 'hp': 75, 'max_hp': 75,
           'moves': [77, 15, 73, 22], 'pp': [35, 30, 10, 10]}


@pytest.fixture(autouse=True)
def reset_globals(monkeypatch):
    monkeypatch.setattr(battle, '_no_pp_switch', None)
    monkeypatch.setattr(battle, '_skip_poison_session', None)
    monkeypatch.setattr(battle.levelup_control, '_SESSION', None)
    monkeypatch.setattr(battle.levelup_moves, '_SESSION', None)


def memory(packed=0x12, *, species=35, moves=(64, 45, 43, 31), index=0):
    return {0xD057: 2, 0xCFE5: 65, 0xD06D: packed, 0xD014: species, 0xCC2F: index,
            **{0xD01C+i: move for i, move in enumerate(moves)}}


def state(packed=0x12, **kwargs):
    return battle.read_battle_state(SimpleNamespace(memory=memory(packed, **kwargs)))


def moves_menu():
    return text_at((1, 0, 'VENONAT'), (10, 7, 'FEAROW'), (12, 10, '60/60'),
                   (6, 12, '35/35'), (6, 13, 'PECK'), (6, 14, 'GROWL'),
                   (6, 15, 'LEER'), (6, 16, 'FURY ATTACK'), (5, 13, '▶'))


def test_fixed_source_nibbles_identify_player_owner_and_move_slot():
    result = state()['player_disabled_move']
    assert result['raw'] == 0x12 and result['slot'] == 0 and result['turns_left'] == 2
    assert result['species'] == 35 and result['party_index'] == 0 and result['move_id'] == 64
    assert result['battle_moves'] == [64, 45, 43, 31] and result['valid']
    assert result['source_commit'] == 'a53671100ec22e5394ff26ec028d0812a238dae2'


def test_disabled_peck_chooses_next_damaging_move_without_mutating_any_party_pp():
    party = [deepcopy(FEAROW), deepcopy(IVYSAUR)]
    original = deepcopy(party)
    result = battle.battle_context(moves_menu(), state(), party)
    assert result['chosen_move'] == 'FURY_ATTACK' and result['objective'] == 'Move DOWN.'
    assert result['player_disabled_move']['move_id'] == 64
    assert party == original


def test_clear_disable_requires_no_owner_memory_and_peck_is_available_again():
    pyboy = SimpleNamespace(memory={0xD057: 2, 0xCFE5: 65, 0xD06D: 0})
    clear = battle.read_battle_state(pyboy)
    assert clear['player_disabled_move']['state'] == 'clear'
    result = battle.battle_context(moves_menu(), clear, [deepcopy(FEAROW)])
    assert result['chosen_move'] == 'PECK' and result['objective'] == 'Confirm the current selection.'


def test_disable_expiration_has_no_stale_cached_mask():
    party = [deepcopy(FEAROW)]
    assert battle.battle_context(moves_menu(), state(), party)['chosen_move'] == 'FURY_ATTACK'
    assert battle.battle_context(moves_menu(), state(0), party)['chosen_move'] == 'PECK'
    assert party[0]['pp'] == [35, 40, 30, 20]


def test_a_different_disabled_slot_does_not_blacklist_peck_by_name():
    assert battle.battle_context(moves_menu(), state(0x42), [deepcopy(FEAROW)])['chosen_move'] == 'PECK'


def test_mask_is_bound_to_exact_party_index_and_does_not_leak_to_same_move_on_other_mon():
    another = {**deepcopy(FEAROW), 'species': 5, 'level': 19}
    party = [deepcopy(FEAROW), another]
    original = deepcopy(party)
    masked, error = battle._disabled_policy_party(party, state()['player_disabled_move'])
    assert error is None and masked[0]['pp'][0] == 0
    assert masked[1]['pp'][0] == 35 and party == original


def test_switching_to_another_mon_with_cleared_disable_uses_its_original_moves():
    party = [deepcopy(FEAROW), deepcopy(IVYSAUR)]
    battle.battle_context(moves_menu(), state(), party)
    ivy_menu = text_at((1, 0, 'VENONAT'), (10, 7, 'IVYSAUR'),
                       (6, 13, 'POISONPOWDER'), (6, 14, 'CUT'),
                       (6, 15, 'LEECH SEED'), (6, 16, 'VINE WHIP'), (5, 14, '▶'))
    result = battle.battle_context(ivy_menu, state(0), party)
    assert result['chosen_move'] == 'CUT'
    assert party[1]['pp'] == [35, 30, 10, 10]


@pytest.mark.parametrize('packed', [1, 0x10, 0x19, 0x51, 255, True, -1])
def test_invalid_nibble_or_nonbyte_signal_stops_instead_of_guessing(packed):
    signal = state(packed)
    assert signal['player_disabled_move']['valid'] is False
    result = battle.battle_context(moves_menu(), signal, [deepcopy(FEAROW)])
    assert result['phase'] == 'strategy_review' and result['available_actions'] == ['wait']


@pytest.mark.parametrize('kwargs', [{'species': 255}, {'index': 6}, {'moves': (0, 45, 43, 31)},
                                  {'moves': (166, 45, 43, 31)}])
def test_invalid_owner_and_disabled_move_slot_are_not_accepted(kwargs):
    signal = state(**kwargs)
    assert not signal['player_disabled_move']['valid']
    assert battle.battle_context(moves_menu(), signal, [deepcopy(FEAROW)])['phase'] == 'strategy_review'


def test_read_signal_unavailable_is_unknown_and_halts_even_without_readable_cells():
    signal = battle.read_battle_state(SimpleNamespace(memory={0xD057: 2, 0xCFE5: 65}))
    assert signal['player_disabled_move']['state'] == 'unknown'
    result = battle.battle_context({'cells': []}, signal, [deepcopy(FEAROW)])
    assert result['review_reason'] == 'player_disabled_move_signal_not_verified'


@pytest.mark.parametrize('change', ['species', 'moves', 'owner_index', 'pp'])
def test_party_crosscheck_rejects_stale_or_unreadable_owner_snapshot(change):
    party = [deepcopy(FEAROW)]
    if change == 'species':
        party[0]['species'] = 5
    elif change == 'moves':
        party[0]['moves'][0] = 33
    elif change == 'owner_index':
        party = []
    else:
        party[0]['pp'] = None
    result = battle.battle_context(moves_menu(), state(), party)
    assert result['phase'] == 'strategy_review' and result['available_actions'] == ['wait']


@pytest.mark.parametrize('change,value', [('turns_left', None), ('turns_left', '2'),
                                        ('slot', True), ('raw', True)])
def test_malformed_metadata_returns_review_without_raising(change, value):
    signal = state()
    signal['player_disabled_move'][change] = value
    result = battle.battle_context(moves_menu(), signal, [deepcopy(FEAROW)])
    assert result['phase'] == 'strategy_review'


def test_visible_disabled_message_is_dismissed_only_after_verified_signal():
    text = text_at((1, 14, 'The move is'), (1, 16, 'disabled!'))
    result = battle.battle_context(text, state(), [deepcopy(FEAROW)])
    assert result['battle_tactic'] == 'dismiss_verified_disabled_move_message'
    assert result['available_actions'] == ['a', 'wait']
    assert battle.battle_context(text, state(0), [deepcopy(FEAROW)])['review_reason'] == 'disabled_move_message_without_verified_signal'
    assert battle.battle_context(text, {'active': True}, [deepcopy(FEAROW)])['phase'] == 'strategy_review'


def test_outside_battle_does_not_read_or_reuse_a_disabled_move():
    signal = battle.read_battle_state(SimpleNamespace(memory={0xD057: 0}))
    assert signal['player_disabled_move']['state'] == 'not_in_battle'
    assert battle.battle_context(moves_menu(), signal, [deepcopy(FEAROW)]) is None


def test_natural_move_integration_receives_actual_verified_progress():
    party = [deepcopy(IVYSAUR)]
    party[0]['level'] = 30
    progress = {'party_read_valid': True, 'party': party}
    intro = text_at((1, 14, 'IVYSAUR is'), (1, 16, 'trying to learn'))
    result = battle.learning_context(intro, party, progress=progress)
    assert result['learning_controller'] == 'bounded_natural_move_candidate'
    assert result['learn_move_plan']['forget'] == 'POISONPOWDER'


def test_without_real_progress_natural_move_does_not_fabricate_validity():
    party = [deepcopy(IVYSAUR)]
    party[0]['level'] = 30
    intro = text_at((1, 14, 'IVYSAUR is'), (1, 16, 'trying to learn'))
    result = battle.learning_context(intro, party)
    assert result['review_reason'] == 'forget_move_menu_requires_live_calibration'
    assert battle.levelup_moves._SESSION is None


def test_natural_move_progress_must_match_the_same_party_snapshot():
    intro = text_at((1, 14, 'IVYSAUR is'), (1, 16, 'trying to learn'))
    result = battle.learning_context(intro, [deepcopy(IVYSAUR)], progress={'party': []})
    assert result['review_reason'] == 'natural_learning_progress_party_mismatch'


@pytest.mark.parametrize('first,second', [('Delete an older', 'move to make room'),
                                        ('Abandon learning', 'RAZOR LEAF?'),
                                        ('IVYSAUR forgot', 'POISONPOWDER!'),
                                        ('1, 2 and... Poof!', '')])
def test_generic_guard_recognizes_real_source_learning_pages_after_process_restart(first, second):
    result = battle.learning_context(text_at((1, 14, first), (1, 16, second)), [deepcopy(IVYSAUR)])
    assert result['phase'] == 'strategy_review'
    assert result['review_reason'] == 'forget_move_menu_requires_live_calibration'
