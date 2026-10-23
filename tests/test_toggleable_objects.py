"""純 fake getter 矩陣；沒有模擬器、ROM、存檔、按鍵或外部來源依賴。"""
from copy import deepcopy
import json
from pathlib import Path
import re

import pytest

from laya_pokemon.toggleable_objects import (
    CURRENT_MAP_ADDRESS, MAX_MAP_SPRITES, NUM_SPRITES_ADDRESS,
    NUM_TOGGLEABLE_OBJECTS, PROFILE, SOURCE_COMMIT, TOGGLE_FLAGS_ADDRESS,
    TOGGLE_FLAGS_LENGTH, TOGGLE_LIST_ADDRESS, TOGGLE_LIST_LENGTH,
    read_toggleable_objects,
)


FLAG_ADDRESSES = tuple(range(0xD5A6, 0xD5C6))
TABLE_ADDRESSES = tuple(range(0xD5CE, 0xD5EF))
SNAPSHOT_ADDRESSES = (0xD35E, 0xD4E1) + FLAG_ADDRESSES + TABLE_ADDRESSES
FIXTURE = Path(__file__).parent / 'data' / 'toggleable-source-fixture.json'


class ReadOnlyMemory:
    def __init__(self, values=None, *, pairs=(4, 62, 5, 63, 255), count=5,
                 fail_at=None, on_read=None, sequence=None):
        self.values = {address: 0 for address in FLAG_ADDRESSES + TABLE_ADDRESSES}
        self.values.update({0xD35E: 147, 0xD4E1: count})
        self.values.update({0xD5CE + i: value for i, value in enumerate(pairs)})
        self.values.update(values or {})
        self.reads, self.fail_at, self.on_read = [], fail_at, on_read
        self.sequence = {key: iter(values) for key, values in (sequence or {}).items()}

    def __getitem__(self, address):
        self.reads.append(address)
        if address == self.fail_at:
            raise RuntimeError('synthetic memory getter')
        if self.on_read is not None:
            self.on_read(address)
        if address in self.sequence:
            return next(self.sequence[address])
        return self.values[address]

    def __setitem__(self, address, value):
        raise AssertionError('不得寫入 RAM')


class GetterOnlyPyBoy:
    def __init__(self, memory=None, frames=(100, 100)):
        self._memory = memory if memory is not None else ReadOnlyMemory()
        self._frames = iter(frames)
        self.memory_reads = self.frame_reads = 0

    @property
    def memory(self):
        self.memory_reads += 1
        return self._memory

    @property
    def frame_count(self):
        self.frame_reads += 1
        value = next(self._frames)
        if isinstance(value, Exception):
            raise value
        return value

    def __getattr__(self, name):
        raise AssertionError(f'不得存取額外模擬器功能: {name}')


def read(pyboy=None, *, map_id=147, observation_frame=100):
    return read_toggleable_objects(
        pyboy if pyboy is not None else GetterOnlyPyBoy(),
        map_id=map_id, observation_frame=observation_frame)


def assert_unknown(result):
    assert result['read_valid'] is False
    assert result['observed_frame'] is None
    assert result['map'] is None
    assert result['sprite_count'] is None
    assert result['objects'] is None
    assert isinstance(result['error'], str) and result['error']
    assert result['profile'] == PROFILE and result['source_commit'] == SOURCE_COMMIT


def test_exact_proven_address_contract_and_getter_only_success():
    pyboy = GetterOnlyPyBoy()
    before = deepcopy(pyboy._memory.values)
    result = read(pyboy)
    assert result == {
        'read_valid': True, 'observed_frame': 100, 'map': 147,
        'sprite_count': 5, 'objects': [
            {'slot': 4, 'index': 62, 'hidden': False},
            {'slot': 5, 'index': 63, 'hidden': False}],
        'error': None, 'profile': PROFILE, 'source_commit': SOURCE_COMMIT,
    }
    assert pyboy._memory.reads == list(SNAPSHOT_ADDRESSES) + [0xD35E, 0xD4E1]
    assert pyboy.frame_reads == 2 and pyboy.memory_reads == 1
    assert pyboy._memory.values == before
    assert (CURRENT_MAP_ADDRESS, NUM_SPRITES_ADDRESS, TOGGLE_FLAGS_ADDRESS,
            TOGGLE_FLAGS_LENGTH, TOGGLE_LIST_ADDRESS, TOGGLE_LIST_LENGTH) == (
                0xD35E, 0xD4E1, 0xD5A6, 32, 0xD5CE, 33)
    assert MAX_MAP_SPRITES == 15 and NUM_TOGGLEABLE_OBJECTS == 228


@pytest.mark.parametrize('flags,expected', [
    (0, [False, False]), (0x40, [True, False]),
    (0x80, [False, True]), (0xC0, [True, True]),
    (0x3F, [False, False]), (0xFF, [True, True]),
])
def test_candy_and_xaccuracy_use_distinct_bits_of_same_byte(flags, expected):
    memory = ReadOnlyMemory({0xD5AD: flags})
    result = read(GetterOnlyPyBoy(memory))
    assert result['read_valid']
    assert [o['hidden'] for o in result['objects']] == expected


@pytest.mark.parametrize('image', [0x00, 0x11, 0xFF])
@pytest.mark.parametrize('hidden', [False, True])
def test_imageindex_offscreen_or_visible_cannot_override_removed_flag(image, hidden):
    memory = ReadOnlyMemory({0xC142: image, 0xC140: 0x3D,
                             0xD5AD: 0x40 if hidden else 0})
    result = read(GetterOnlyPyBoy(memory))
    assert result['read_valid'] and result['objects'][0]['hidden'] is hidden
    assert 0xC142 not in memory.reads and 0xC140 not in memory.reads


@pytest.mark.parametrize('count', [0, 1, 5, 15])
def test_valid_empty_terminated_table_is_distinct_from_unknown(count):
    result = read(GetterOnlyPyBoy(ReadOnlyMemory(pairs=(255,), count=count)))
    assert result['read_valid'] and result['objects'] == []
    assert result['sprite_count'] == count


def test_trailing_stale_but_valid_bytes_after_terminator_are_ignored_semantically():
    pairs = (4, 62, 255) + (255, 0, 0, 227, 15, 228) * 5
    memory = ReadOnlyMemory(pairs=pairs)
    result = read(GetterOnlyPyBoy(memory))
    assert result['read_valid']
    assert result['objects'] == [{'slot': 4, 'index': 62, 'hidden': False}]


def test_all_fifteen_slots_and_terminator_at_offset_thirty():
    pairs = tuple(n for slot in range(1, 16) for n in (slot, slot - 1)) + (255, 123, 234)
    memory = ReadOnlyMemory({a: 255 for a in FLAG_ADDRESSES}, pairs=pairs, count=15)
    result = read(GetterOnlyPyBoy(memory))
    assert result['read_valid'] and len(result['objects']) == 15
    assert all(o['hidden'] is True for o in result['objects'])


@pytest.mark.parametrize('index', [0, 7, 8, 31, 62, 63, 64, 127, 128, 224, 227])
def test_flag_address_and_bit_algorithm_across_defined_index_range(index):
    address, bit = 0xD5A6 + index // 8, index % 8
    memory = ReadOnlyMemory({address: 1 << bit}, pairs=(1, index, 255), count=1)
    result = read(GetterOnlyPyBoy(memory))
    assert result['read_valid']
    assert result['objects'] == [{'slot': 1, 'index': index, 'hidden': True}]


@pytest.mark.parametrize('pairs,count,error', [
    ((0, 62, 255), 5, 'toggle_slot_out_of_bounds'),
    ((6, 62, 255), 5, 'toggle_slot_out_of_bounds'),
    ((16, 62, 255), 15, 'toggle_slot_out_of_bounds'),
    ((1, 62, 255), 0, 'toggle_slot_out_of_bounds'),
    ((4, 62, 4, 63, 255), 5, 'toggle_duplicate_slot'),
    ((4, 62, 5, 62, 255), 5, 'toggle_duplicate_global_index'),
    ((4, 228, 255), 5, 'toggle_global_index_invalid'),
    ((4, 254, 255), 5, 'toggle_global_index_invalid'),
    ((4, 255, 255), 5, 'toggle_global_index_invalid'),
])
def test_malformed_pairs_fail_whole_snapshot(pairs, count, error):
    result = read(GetterOnlyPyBoy(ReadOnlyMemory(pairs=pairs, count=count)))
    assert_unknown(result)
    assert result['error'] == error


def test_no_terminator_and_incomplete_final_pair_fail_closed():
    result = read(GetterOnlyPyBoy(ReadOnlyMemory(pairs=(1, 62) * 16 + (1,), count=15)))
    assert_unknown(result)
    assert result['error'] == 'toggle_table_terminator_missing'


def test_ff_in_index_position_is_not_a_terminator():
    result = read(GetterOnlyPyBoy(ReadOnlyMemory(pairs=(4, 255) + (0,) * 31)))
    assert_unknown(result)
    assert result['error'] == 'toggle_table_terminator_missing'


@pytest.mark.parametrize('count', [16, 17, 255])
def test_sprite_count_cannot_use_player_or_nonexistent_slots(count):
    result = read(GetterOnlyPyBoy(ReadOnlyMemory(count=count)))
    assert_unknown(result)
    assert result['error'] == 'toggle_sprite_count_invalid'


@pytest.mark.parametrize('address', [
    0xD35E, 0xD4E1, 0xD5A6, 0xD5C5, 0xD5CE, 0xD5CF, 0xD5EE])
@pytest.mark.parametrize('value', [None, True, False, -1, 256, 0.0, '0'])
def test_every_field_rejects_unknown_wrong_type_and_bool_byte(address, value):
    result = read(GetterOnlyPyBoy(ReadOnlyMemory({address: value})))
    assert_unknown(result)
    assert result['error'] == 'toggle_byte_invalid'


@pytest.mark.parametrize('address', SNAPSHOT_ADDRESSES)
def test_getter_exception_anywhere_discards_partial_data(address):
    result = read(GetterOnlyPyBoy(ReadOnlyMemory(fail_at=address)))
    assert_unknown(result)
    assert result['error'] == 'toggle_getter_failed'


@pytest.mark.parametrize('frame', [None, True, False, -1, 100.0, '100'])
def test_invalid_requested_frame_never_accesses_emulator(frame):
    pyboy = GetterOnlyPyBoy()
    assert_unknown(read(pyboy, observation_frame=frame))
    assert pyboy.memory_reads == pyboy.frame_reads == 0
    assert pyboy._memory.reads == []


@pytest.mark.parametrize('map_id', [None, True, False, -1, 256, 147.0, '147'])
def test_invalid_map_argument_never_accesses_emulator(map_id):
    pyboy = GetterOnlyPyBoy()
    assert_unknown(read(pyboy, map_id=map_id))
    assert pyboy.memory_reads == pyboy.frame_reads == 0


@pytest.mark.parametrize('before', [99, 101, None, True, False, 100.0, '100'])
def test_stale_or_invalid_first_frame_skips_memory(before):
    pyboy = GetterOnlyPyBoy(frames=(before, 100))
    result = read(pyboy)
    assert_unknown(result)
    assert result['error'] == 'toggle_frame_not_current'
    assert pyboy.memory_reads == 0 and pyboy._memory.reads == []


@pytest.mark.parametrize('after', [99, 101, None, True, False, 100.0, '100'])
def test_crossframe_or_invalid_final_frame_discards_whole_snapshot(after):
    result = read(GetterOnlyPyBoy(frames=(100, after)))
    assert_unknown(result)
    assert result['error'] == 'toggle_frame_changed_during_read'


def test_tick_during_table_getter_is_detected_without_calling_tick():
    class StatefulFramePyBoy(GetterOnlyPyBoy):
        current_frame = 100

        @property
        def frame_count(self):
            self.frame_reads += 1
            return self.current_frame

    pyboy = StatefulFramePyBoy()
    pyboy._memory.on_read = lambda address: (
        setattr(pyboy, 'current_frame', 101) if address == 0xD5D0 else None)
    result = read(pyboy)
    assert_unknown(result)
    assert result['error'] == 'toggle_frame_changed_during_read'


@pytest.mark.parametrize('frames', [(), (100,), (RuntimeError(),), (100, RuntimeError())])
def test_frame_getter_failure_fails_closed(frames):
    result = read(GetterOnlyPyBoy(frames=frames))
    assert_unknown(result)
    assert result['error'] == 'toggle_getter_failed'


@pytest.mark.parametrize('actual_map', [0, 146, 148, 255])
def test_wrong_live_map_does_not_read_or_report_toggle_flags(actual_map):
    memory = ReadOnlyMemory({0xD35E: actual_map})
    result = read(GetterOnlyPyBoy(memory))
    assert_unknown(result)
    assert result['error'] == 'toggle_map_mismatch'
    assert memory.reads == [0xD35E]


@pytest.mark.parametrize('address,sequence,error', [
    (0xD35E, (147, 148), 'toggle_map_changed_during_read'),
    (0xD4E1, (5, 4), 'toggle_sprite_count_changed_during_read'),
])
def test_map_or_count_drift_even_same_frame_is_unknown(address, sequence, error):
    memory = ReadOnlyMemory(sequence={address: sequence})
    result = read(GetterOnlyPyBoy(memory))
    assert_unknown(result)
    assert result['error'] == error


@pytest.mark.parametrize('address', [0xD35E, 0xD4E1])
@pytest.mark.parametrize('final', [True, None, 256])
def test_invalid_final_map_count_reread_is_not_accepted(address, final):
    first = 147 if address == 0xD35E else 5
    result = read(GetterOnlyPyBoy(ReadOnlyMemory(sequence={address: (first, final)})))
    assert_unknown(result)
    assert result['error'] == 'toggle_byte_invalid'


def test_memory_property_exception_cannot_report_empty_objects():
    class BadMemory:
        frame_count = 100

        @property
        def memory(self):
            raise RuntimeError('synthetic property')

    result = read(BadMemory())
    assert_unknown(result)
    assert result['error'] == 'toggle_getter_failed'


def test_caller_cannot_inject_hidden_profile_or_calibration_bool():
    for key in ('hidden', 'profile', 'verified', 'source_commit', 'objects'):
        with pytest.raises(TypeError):
            read_toggleable_objects(
                GetterOnlyPyBoy(), map_id=147, observation_frame=100, **{key: True})


def test_public_fixture_addresses_source_receipts_and_tower_calibration_are_fixed():
    f = json.loads(FIXTURE.read_text(encoding='utf-8'))
    assert f['source_commit'] == SOURCE_COMMIT
    assert f['kind'] == 'public_source_only_not_live_snapshot'
    assert f['num_toggleable_objects'] == NUM_TOGGLEABLE_OBJECTS
    assert f['last_defined_toggle'] == {'name': 'TOGGLE_ARTICUNO', 'index': 227}
    assert f['addresses']['wCurMap'] == CURRENT_MAP_ADDRESS
    assert f['addresses']['wNumSprites'] == NUM_SPRITES_ADDRESS
    assert f['addresses']['wToggleableObjectFlags'] == TOGGLE_FLAGS_ADDRESS
    assert f['addresses']['wToggleableObjectList'] == TOGGLE_LIST_ADDRESS
    assert f['main_data_base'] == 0xD2F7
    assert f['party_data_crosscheck']['derived_main_data_start'] == 0xD2F7
    assert all(a['sdk_address'] == a['derived_address'] for a in f['cross_sdk_anchors'])
    for record in f['source_files']:
        assert re.fullmatch('[0-9a-f]{64}', record['sha256'])
        assert record['url'].startswith(
            f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/')
    assert f['maps']['147']['expected_list_prefix'] == [4, 62, 5, 63, 255]
    assert f['maps']['148']['expected_list_prefix'] == [1, 64, 2, 65, 3, 66, 4, 67, 255]
    route = f['maps']['23']
    assert route['source_object_count'] == 10
    assert route['expected_list_prefix'] == [1, 29, 9, 30, 10, 31, 255]
    assert [(o['slot'], o['index']) for o in route['objects']] == [(1, 29), (9, 30), (10, 31)]
    assert [(o['slot'], o['source_position']) for o in route['all_source_objects']] == [
        (1, [10, 62]), (2, [14, 31]), (3, [5, 39]), (4, [11, 92]),
        (5, [14, 76]), (6, [12, 40]), (7, [9, 52]), (8, [6, 87]),
        (9, [14, 35]), (10, [5, 89])]


@pytest.mark.parametrize('map_id', [23, 147, 148])
def test_tower_source_fixtures_decode_each_flag_independently(map_id):
    f = json.loads(FIXTURE.read_text(encoding='utf-8'))
    profile = f['maps'][str(map_id)]
    for hidden_object in profile['objects']:
        memory = ReadOnlyMemory(
            {0xD35E: map_id,
             hidden_object['flag_address']: hidden_object['flag_mask']},
            pairs=profile['expected_list_prefix'], count=profile['source_object_count'])
        result = read(GetterOnlyPyBoy(memory), map_id=map_id)
        assert result['read_valid']
        for obj in result['objects']:
            assert obj['hidden'] is (obj['index'] == hidden_object['index'])


def test_generic_valid_table_is_not_mislabelled_as_complete_map_source_calibration():
    # 結構有效但不是Tower6來源的slot/index，reader只報getter結果；父層須另校準。
    memory = ReadOnlyMemory(pairs=(1, 0, 255), count=5)
    result = read(GetterOnlyPyBoy(memory))
    assert result['read_valid'] and result['objects'] == [
        {'slot': 1, 'index': 0, 'hidden': False}]
    assert 'rom_verified' not in result and 'map_source_calibrated' not in result

