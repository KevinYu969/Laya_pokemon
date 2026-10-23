"""野生非捕捉目標的全招抗性退避；純合成，不操作模擬器。"""
from copy import deepcopy

import pytest

import laya_pokemon.battle as battle
from tests.test_battle import text_at


FEAROW = {'species': 35, 'level': 22, 'hp': 70, 'max_hp': 70,
          'moves': [64, 45, 43, 31], 'pp': [35, 40, 30, 20]}
IVYSAUR = {'species': 9, 'level': 27, 'hp': 80, 'max_hp': 80,
           'moves': [77, 15, 73, 22], 'pp': [35, 30, 10, 10]}


@pytest.fixture(autouse=True)
def reset_pending(monkeypatch):
    monkeypatch.setattr(battle, '_no_pp_switch', None)


def command(enemy='GEODUDE', player='FEAROW', hp='70/70'):
    return text_at((1, 0, enemy), (10, 7, player), (12, 10, hp),
                   (9, 14, '▶FIGHT'), (10, 16, 'ITEM'), (16, 16, 'RUN'))


def test_fearow_wild_rock_encounter_runs_when_every_available_damage_move_is_resisted():
    result = battle.battle_context(command(), {'active': True, 'kind': 'wild'}, [deepcopy(FEAROW)])
    assert result['battle_tactic'] == 'retreat' and result['objective'] == 'Move DOWN.'
    assert result['retreat_reason'] == 'all_available_damage_moves_resisted'
    assert {move['move'] for move in result['resisted_attacks']} == {'PECK', 'FURY_ATTACK'}
    assert all(move['effective_power'] < move['base_effective_power'] for move in result['resisted_attacks'])


def test_resisted_moves_menu_cancels_back_to_run_instead_of_committing_another_attack():
    menu = text_at((1, 0, 'GEODUDE'), (10, 7, 'FEAROW'), (12, 10, '70/70'),
                   (6, 13, 'PECK'), (6, 14, 'GROWL'), (6, 15, 'LEER'),
                   (6, 16, 'FURY ATTACK'), (5, 13, '▶'))
    result = battle.battle_context(menu, {'active': True, 'kind': 'wild'}, [deepcopy(FEAROW)])
    assert result['available_actions'] == ['b', 'wait']
    assert result['retreat_reason'] == 'all_available_damage_moves_resisted'


def test_vine_whip_against_rock_is_not_all_resisted_and_does_not_request_run():
    result = battle.battle_context(command(player='IVYSAUR', hp='80/80'),
                                   {'active': True, 'kind': 'wild'}, [deepcopy(IVYSAUR)])
    assert result['battle_tactic'] == 'damage' and 'retreat_reason' not in result


def test_trainer_fight_never_runs_due_to_type_resistance():
    result = battle.battle_context(command(), {'active': True, 'kind': 'trainer'}, [deepcopy(FEAROW)])
    assert result['battle_tactic'] == 'damage' and 'retreat_reason' not in result


def test_capture_target_is_preserved_even_when_the_only_attack_is_resisted():
    ivy = {**deepcopy(IVYSAUR), 'moves': [77, 45, 73, 22], 'pp': [35, 40, 10, 10]}
    result = battle.battle_context(command(enemy='CATERPIE', player='IVYSAUR', hp='80/80'),
                                   {'active': True, 'kind': 'wild'}, [ivy], [{'item': 4, 'quantity': 6}])
    assert result['battle_tactic'] == 'capture' and 'retreat_reason' not in result


def test_unknown_active_or_enemy_is_not_assumed_to_be_the_resisted_case():
    for page in (command(player=''), command(enemy='')):
        result = battle.battle_context(page, {'active': True, 'kind': 'wild'}, [deepcopy(FEAROW)])
        assert result.get('retreat_reason') != 'all_available_damage_moves_resisted'


def test_ambiguous_visible_enemy_does_not_trigger_new_type_retreat():
    page = command()
    page['cells'][2][1:5] = list('ONIX')
    result = battle.battle_context(page, {'active': True, 'kind': 'wild'}, [deepcopy(FEAROW)])
    assert result.get('retreat_reason') != 'all_available_damage_moves_resisted'


def test_existing_low_health_retreat_keeps_its_original_reason_and_flow():
    result = battle.battle_context(command(hp='20/70'), {'active': True, 'kind': 'wild'}, [deepcopy(FEAROW)])
    assert result['battle_tactic'] == 'retreat'
    assert 'retreat_reason' not in result


def test_disabled_pp_copy_is_respected_without_mutating_the_original_party():
    party = [deepcopy(IVYSAUR)]
    original = deepcopy(party)
    signal = {'state': 'disabled', 'valid': True, 'raw': 0x42, 'slot': 3, 'turns_left': 2,
              'party_index': 0, 'species': 9, 'battle_moves': [77, 15, 73, 22], 'move_id': 22}
    state = {'active': True, 'kind': 'wild', 'player_disabled_move': signal}
    result = battle.battle_context(command(player='IVYSAUR', hp='80/80'), state, party)
    assert result['retreat_reason'] == 'all_available_damage_moves_resisted'
    assert [row['move'] for row in result['resisted_attacks']] == ['CUT']
    assert party == original
    state['player_disabled_move'] = {'state': 'clear', 'valid': True, 'raw': 0}
    assert 'retreat_reason' not in battle.battle_context(command(player='IVYSAUR', hp='80/80'), state, party)


def test_no_usable_damage_moves_does_not_vacuously_claim_all_moves_resisted():
    fearow = {**deepcopy(FEAROW), 'pp': [0, 40, 30, 0]}
    result = battle.battle_context(command(), {'active': True, 'kind': 'wild'}, [fearow])
    assert result.get('retreat_reason') != 'all_available_damage_moves_resisted'


def test_a_single_neutral_available_attack_prevents_all_resisted_retreat():
    # 一般型招式對幽靈無效，但啄仍能中性傷害，不可把部分無效當成全部無效。
    result = battle.battle_context(command(enemy='GASTLY'), {'active': True, 'kind': 'wild'}, [deepcopy(FEAROW)])
    assert result.get('retreat_reason') != 'all_available_damage_moves_resisted'
