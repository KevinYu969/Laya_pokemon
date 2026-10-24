"""娜姿新事件只讀契約；純fake memory，無ROM／模擬器／網路。"""
from copy import deepcopy

import pytest

from laya_pokemon.progress import STORY_EVENT_NAMES, read_progress
from tests.test_progress import fuchsia_constants, fuchsia_game


# Independent fixed-source expected IDs, not imported from implementation or
# ignored outputs: pret/pokered a536711 event_constants.asm:207-215.
# https://github.com/pret/pokered/blob/a53671100ec22e5394ff26ec028d0812a238dae2/constants/event_constants.asm#L207-L215
EXPECTED = {
    'got_tm46': 0x360, 'beat_sabrina': 0x361,
    'beat_saffron_gym_trainer_0': 0x362, 'beat_saffron_gym_trainer_1': 0x363,
    'beat_saffron_gym_trainer_2': 0x364, 'beat_saffron_gym_trainer_3': 0x365,
    'beat_saffron_gym_trainer_4': 0x366, 'beat_saffron_gym_trainer_5': 0x367,
    'beat_saffron_gym_trainer_6': 0x368,
}
ADDED = set(EXPECTED) - {'beat_sabrina'}


def game_bytes(first=0, second=0):
    constants = fuchsia_constants()
    constants.EVENT_FLAGS = dict(constants.EVENT_FLAGS)
    game = fuchsia_game(constants,0)
    game.memory.data.update({0xD7B3:first,0xD7B4:second})
    return game,constants


def test_fixed_source_matches_all_nine_official_sdk_anchors_and_two_addresses():
    constants = fuchsia_constants()
    assert type(constants.EVENT_FLAGS_ADDRESS) is int and constants.EVENT_FLAGS_ADDRESS == 0xD747
    assert all(type(constants.EVENT_FLAGS[name]) is int and constants.EVENT_FLAGS[name] == event
               for name,event in EXPECTED.items())
    assert {0xD747 + event//8 for event in EXPECTED.values()} == {0xD7B3,0xD7B4}
    assert set(EXPECTED) <= set(STORY_EVENT_NAMES)
    assert len(ADDED) == 8


@pytest.mark.parametrize('first,tm46,boss',[(1,True,False),(2,False,True),(0,False,False)])
def test_tm46_and_existing_sabrina_bit_remain_independent(first,tm46,boss):
    game,constants = game_bytes(first)
    result = read_progress(game,constants)
    assert result['story_event_bits']['got_tm46'] is tm46
    assert result['story_event_bits']['beat_sabrina'] is boss
    assert all(result['story_event_bits'][name] is False for name in ADDED-{'got_tm46'})


def test_all_trainer_bits_are_independent_including_trainer6_across_byte():
    for index in range(7):
        game,constants = game_bytes(1<<(index+2) if index<6 else 0,1 if index==6 else 0)
        result = read_progress(game,constants)
        assert {name:result['story_event_bits'][name] for name in ADDED} == {
            name:name==f'beat_saffron_gym_trainer_{index}' for name in ADDED},index
        assert result['story_event_bits']['beat_sabrina'] is False
        assert game.memory.reads[0xD7B3] == 1 and game.memory.reads[0xD7B4] == 1


def test_full_source_bytes_are_cached_once_without_memory_writes_or_hof_claim():
    game,constants = game_bytes(255,255)
    before = deepcopy(game.memory.data)
    result = read_progress(game,constants)
    assert all(result['story_event_bits'][name] is True for name in EXPECTED)
    assert game.memory.reads[0xD7B3] == game.memory.reads[0xD7B4] == 1
    assert game.memory.data == before
    assert result['badges_raw'] == 15 and result['badge_count'] == 4
    assert result['champion_observed'] is False and result['hall_of_fame_confirmed'] is None


def test_each_of_nine_required_sdk_anchors_is_fail_closed_for_all_eight_new_fields():
    for missing in EXPECTED:
        game,constants = game_bytes(255,1)
        constants.EVENT_FLAGS.pop(missing)
        result = read_progress(game,constants)
        assert all(result['story_event_bits'][name] is None for name in ADDED),missing
        # Existing boss keeps its independent generic mapping; new gate must not
        # reinterpret it or depend its result on a different missing anchor.
        assert result['story_event_bits']['beat_sabrina'] is (None if missing=='beat_sabrina' else True)
        assert game.memory.reads[0xD7B4] == 0


@pytest.mark.parametrize('bad',['shifted','boolean_id','float_id','other_base','boolean_base'])
def test_unrecognized_sdk_contract_keeps_new_bits_unknown(bad):
    game,constants = game_bytes(255,1)
    if bad=='shifted': constants.EVENT_FLAGS['beat_saffron_gym_trainer_6'] = 0x369
    elif bad=='boolean_id': constants.EVENT_FLAGS['got_tm46'] = True
    elif bad=='float_id': constants.EVENT_FLAGS['beat_sabrina'] = float(0x361)
    elif bad=='other_base': constants.EVENT_FLAGS_ADDRESS = 0xD746
    else: constants.EVENT_FLAGS_ADDRESS = True
    result = read_progress(game,constants)
    assert all(result['story_event_bits'][name] is None for name in ADDED)
    assert game.memory.reads[0xD7B4] == 0


@pytest.mark.parametrize('invalid_boss_id',[True,-1])
def test_invalid_legacy_boss_id_is_unknown_without_interrupting_new_field_contract(invalid_boss_id):
    # First target run exposed float(0x361) raising in the legacy boss bit shift
    # (290 passed / 1 failed). Keep that original float_id case above; parent
    # authorized only this boss's invalid-type/nonnegative guard, not generic
    # changes to other legacy events or the normal Sabrina mapping.
    game,constants = game_bytes(255,1)
    constants.EVENT_FLAGS['beat_sabrina'] = invalid_boss_id
    result = read_progress(game,constants)
    assert result['story_event_bits']['beat_sabrina'] is None
    assert all(result['story_event_bits'][name] is None for name in ADDED)
    assert game.memory.reads[0xD7B4] == 0


@pytest.mark.parametrize('address',[0xD7B3,0xD7B4])
@pytest.mark.parametrize('unknown',[None,False,KeyError('unreadable')])
def test_unreadable_or_boolean_false_byte_stays_unknown_and_does_not_poison_other_byte(address,unknown):
    game,constants = game_bytes(255,1)
    game.memory.data[address] = unknown
    result = read_progress(game,constants)
    for name in ADDED:
        expected_address = 0xD747 + EXPECTED[name]//8
        assert result['story_event_bits'][name] is (None if expected_address==address else True)
    assert game.memory.reads[0xD7B3] == game.memory.reads[0xD7B4] == 1
    assert result['hall_of_fame_confirmed'] is None
