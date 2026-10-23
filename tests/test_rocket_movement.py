"""唯讀 adapter 的合成 getter 測試；不建立模擬器、不讀 ROM／存檔。"""
from copy import deepcopy

import pytest

from laya_pokemon.arrow_floor import ArrowFloorController
from laya_pokemon.rocket_movement import (
    read_rocket_movement, SOURCE_COMMIT, MOVEMENT_PROFILE,
    SIMULATED_JOYPAD_INDEX_ADDRESS, JOY_IGNORE_ADDRESS,
    WALK_COUNTER_ADDRESS, MOVEMENT_FLAGS_ADDRESS, SPINNING_MASK,
)


ADDRESSES = (0xCD38, 0xCD6B, 0xCFC5, 0xD736)


class ReadOnlyMemory:
    def __init__(self, values=None, fail_at=None):
        self.values = dict(zip(ADDRESSES, (0, 0, 0, 0)))
        self.values.update(values or {})
        self.reads, self.fail_at = [], fail_at

    def __getitem__(self, address):
        self.reads.append(address)
        if address == self.fail_at:
            raise RuntimeError('synthetic getter failure')
        return self.values[address]

    def __setitem__(self, address, value):
        raise AssertionError('adapter 不得寫 RAM')


class ReadOnlyPyBoy:
    def __init__(self, values=None, frames=(100, 100), fail_at=None):
        self._memory = ReadOnlyMemory(values, fail_at)
        self._frames, self.frame_reads, self.memory_reads = iter(frames), 0, 0

    @property
    def frame_count(self):
        self.frame_reads += 1
        return next(self._frames)

    @property
    def memory(self):
        self.memory_reads += 1
        return self._memory

    def __getattr__(self, name):
        raise AssertionError(f'adapter 不得存取其他模擬器介面：{name}')


def test_idle_reads_exactly_four_proven_addresses_and_never_mutates_input():
    pyboy = ReadOnlyPyBoy()
    before = deepcopy(pyboy._memory.values)
    result = read_rocket_movement(pyboy, observation_frame=100)
    assert result == {'read_valid': True, 'profile': MOVEMENT_PROFILE,
                      'source_commit': SOURCE_COMMIT, 'observation_frame': 100,
                      'spinning': False, 'simulated_remaining': 0, 'joy_ignore': 0,
                      'walk_counter': 0, 'movement_flags': 0}
    assert pyboy._memory.reads == list(ADDRESSES)
    assert pyboy._memory.values == before
    assert pyboy.frame_reads == 2 and pyboy.memory_reads == 1
    assert (SIMULATED_JOYPAD_INDEX_ADDRESS, JOY_IGNORE_ADDRESS,
            WALK_COUNTER_ADDRESS, MOVEMENT_FLAGS_ADDRESS) == ADDRESSES
    assert SPINNING_MASK == 0x80


@pytest.mark.parametrize('flags,spinning', [(0, False), (1, False), (2, False), (4, False),
                                           (0x40, False), (0x80, True), (0xC7, True)])
def test_spinning_comes_only_from_source_bit7_not_other_known_flags(flags, spinning):
    result = read_rocket_movement(ReadOnlyPyBoy({0xD736: flags}), observation_frame=100)
    assert result['read_valid'] and result['spinning'] is spinning
    assert result['movement_flags'] == flags


def test_forced_motion_keeps_actual_byte_values_for_controller_to_wait():
    result = read_rocket_movement(ReadOnlyPyBoy({0xCD38: 5, 0xCD6B: 255, 0xCFC5: 8,
                                                0xD736: 0x80}), observation_frame=100)
    assert result['read_valid'] and result['spinning'] is True
    assert (result['simulated_remaining'], result['joy_ignore'], result['walk_counter']) == (5, 255, 8)


@pytest.mark.parametrize('address', ADDRESSES)
@pytest.mark.parametrize('value', [None, True, False, -1, 256, 0.0, '0'])
def test_unknown_or_nonbyte_read_never_becomes_zero_or_idle(address, value):
    result = read_rocket_movement(ReadOnlyPyBoy({address: value}), observation_frame=100)
    assert not result['read_valid'] and result['read_error'] == 'movement_byte_invalid'
    for key in ('spinning', 'simulated_remaining', 'joy_ignore', 'walk_counter', 'movement_flags'):
        assert result[key] is None


@pytest.mark.parametrize('ignored', [1, 16, 127, 254])
def test_other_scripts_input_masks_do_not_unlock_arrow_profile(ignored):
    result = read_rocket_movement(ReadOnlyPyBoy({0xCD6B: ignored}), observation_frame=100)
    assert not result['read_valid']
    assert result['read_error'] == 'movement_input_ignore_mask_unknown'


@pytest.mark.parametrize('flags', [8, 16, 32, 0xB8, 255])
def test_source_unused_flag_bits_require_review(flags):
    result = read_rocket_movement(ReadOnlyPyBoy({0xD736: flags}), observation_frame=100)
    assert not result['read_valid'] and result['read_error'] == 'movement_unused_flag_bits_set'


@pytest.mark.parametrize('frame', [None, True, -1, 100.0, '100'])
def test_invalid_requested_frame_never_accesses_emulator(frame):
    pyboy = ReadOnlyPyBoy()
    result = read_rocket_movement(pyboy, observation_frame=frame)
    assert not result['read_valid'] and result['observation_frame'] is None
    assert pyboy.frame_reads == pyboy.memory_reads == 0 and pyboy._memory.reads == []


@pytest.mark.parametrize('before', [99, 101, None, True, 100.0, '100'])
def test_stale_or_invalid_emulator_frame_does_not_even_read_memory(before):
    pyboy = ReadOnlyPyBoy(frames=(before, 100))
    result = read_rocket_movement(pyboy, observation_frame=100)
    assert not result['read_valid'] and result['read_error'] == 'movement_frame_not_current'
    assert pyboy.memory_reads == 0 and pyboy._memory.reads == []


@pytest.mark.parametrize('after', [99, 101, None, True, 100.0, '100'])
def test_frame_change_or_invalid_second_frame_discards_snapshot(after):
    result = read_rocket_movement(ReadOnlyPyBoy(frames=(100, after)), observation_frame=100)
    assert not result['read_valid']
    assert result['read_error'] == 'movement_frame_changed_during_read'
    assert result['spinning'] is result['walk_counter'] is None


@pytest.mark.parametrize('address', ADDRESSES)
def test_getter_exception_discards_every_partial_read(address):
    result = read_rocket_movement(ReadOnlyPyBoy(fail_at=address), observation_frame=100)
    assert not result['read_valid'] and result['read_error'] == 'movement_getter_failed'
    assert result['simulated_remaining'] is result['joy_ignore'] is None


@pytest.mark.parametrize('frames', [(), (100,)])
def test_frame_getter_exception_fails_closed(frames):
    result = read_rocket_movement(ReadOnlyPyBoy(frames=frames), observation_frame=100)
    assert not result['read_valid'] and result['read_error'] == 'movement_getter_failed'


def test_caller_cannot_supply_profile_spinning_or_verified_switch():
    for key in ('profile', 'spinning', 'verified', 'source_commit'):
        with pytest.raises(TypeError):
            read_rocket_movement(ReadOnlyPyBoy(), observation_frame=100, **{key: True})


def _controller_context(controller, frame, point, movement, now):
    x, y = point
    tiles = [[1] * 30 for _ in range(28)]
    tiles[11][12], tiles[11][10] = 0x20, 0x5E
    visible = {(xx, yy) for yy in range(y - 2, y + 3) for xx in range(x - 2, x + 3)}
    grid = {'tileset_id': 22, 'tiles': tiles, 'walkable': [[1] * 30 for _ in range(28)],
            'observation_frame': frame, 'verified_location': [201, x, y],
            'visible_verified_cells': [list(p) for p in sorted(visible)],
            'screen_cells_verified': len(visible)}
    return controller.context({'map_id': 201, 'x': x, 'y': y}, grid, movement,
                              frame=frame, now=now, overworld_ready=True)


def test_real_adapter_contract_drives_one_entry_forced_wait_and_two_idle_samples():
    # 僅合成端到端契約；不是實機滑行已成功的證據。
    controller = ArrowFloorController(201, (12, 11))
    idle = read_rocket_movement(ReadOnlyPyBoy(), observation_frame=100)
    assert _controller_context(controller, 100, (13, 11), idle, 1)['available_actions'] == ['left', 'wait']
    active = read_rocket_movement(ReadOnlyPyBoy({0xCD38: 2, 0xCD6B: 255, 0xD736: 0x80},
                                               frames=(132, 132)), observation_frame=132)
    result = _controller_context(controller, 132, (12, 11), active, 1.2)
    assert result['available_actions'] == ['wait'] and not result.get('arrow_floor_complete')
    for frame, now in ((164, 1.4), (196, 1.6)):
        idle = read_rocket_movement(ReadOnlyPyBoy(frames=(frame, frame)), observation_frame=frame)
        result = _controller_context(controller, frame, (10, 11), idle, now)
    assert result['arrow_floor_complete'] and result['available_actions'] == ['wait']


def test_unverified_adapter_result_cannot_send_entry_to_arrow_controller():
    controller = ArrowFloorController(201, (12, 11))
    invalid = read_rocket_movement(ReadOnlyPyBoy(frames=(99, 99)), observation_frame=100)
    result = _controller_context(controller, 100, (13, 11), invalid, 1)
    assert result['phase'] == 'campaign_review' and result['available_actions'] == ['wait']
