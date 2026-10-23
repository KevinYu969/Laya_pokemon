"""以純唯讀 fake getter 核對 Route12 隱藏覆蓋；不讀 ROM／存檔或操作遊戲。"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from laya_pokemon.world_map import TOWER_TOGGLE_OBJECTS, read_npc_obstacles, world_direction


FIXTURE = Path(__file__).parent / 'data' / 'toggleable-source-fixture.json'
ORIGINS = [(10, 62), (14, 31), (5, 39), (11, 92), (14, 76),
           (12, 40), (9, 52), (6, 87), (14, 35), (5, 89)]
PAIRS = (1, 29, 9, 30, 10, 31, 255)


class ReadOnlyMemory:
    def __init__(self, values, *, fail_at=None, sequence=None):
        self.values = values
        self.fail_at = fail_at
        self.sequence = {k: iter(v) for k, v in (sequence or {}).items()}

    def __getitem__(self, address):
        if address == self.fail_at:
            raise RuntimeError('synthetic getter failure')
        if address in self.sequence:
            return next(self.sequence[address])
        return self.values[address]

    def __setitem__(self, address, value):
        raise AssertionError('不得寫入記憶體')


class GetterOnly:
    def __init__(self, memory, frames):
        self.memory = memory
        self.frames = iter(frames)

    @property
    def frame_count(self):
        return next(self.frames)

    def __getattr__(self, name):
        raise AssertionError(f'不得使用模擬器操作：{name}')


def setup(flags=0x20, *, pairs=PAIRS, count=10, frame=50,
          frames=(50, 50), fail_at=None, sequence=None):
    values = {a: 0 for a in range(0xC100, 0xC300)}
    values.update({a: 0 for a in range(0xD5A6, 0xD5C6)})
    values.update({a: 0 for a in range(0xD5CE, 0xD5EF)})
    values.update({0xD35E: 23, 0xD4E1: count, 0xD5A9: flags})
    values.update({0xD5CE + i: b for i, b in enumerate(pairs)})
    for slot, (x, y) in enumerate(ORIGINS, 1):
        values[0xC100 + 16 * slot] = 1
        values[0xC102 + 16 * slot] = 255  # 離屏不是已隱藏。
        values[0xC204 + 16 * slot] = y + 4
        values[0xC205 + 16 * slot] = x + 4
    memory = ReadOnlyMemory(values, fail_at=fail_at, sequence=sequence)
    grid = {'walkable': [[1] * 20 for _ in range(108)],
            'verified_location': [23, 10, 61], 'observation_frame': frame,
            'screen_cells_verified': 90}
    return GetterOnly(memory, frames), grid


def observe(pyboy, grid, *, ready=True):
    return read_npc_obstacles(pyboy, grid, ORIGINS, overworld_ready=ready)


def merged(result):
    """重現既有呼叫端的靜態障礙扣除／動態障礙聯集，不產生操作。"""
    hidden = result['hidden_source_positions'] if result['toggle_source_calibrated'] is True else []
    return (set(ORIGINS) - set(hidden)) | set(result['positions'])


def test_full_ten_object_source_fixture_and_whitelist_are_exact():
    source = json.loads(FIXTURE.read_text(encoding='utf-8'))
    route = source['maps']['23']
    assert route['source_object_count'] == 10
    assert [o['slot'] for o in route['all_source_objects']] == list(range(1, 11))
    assert [tuple(o['source_position']) for o in route['all_source_objects']] == ORIGINS
    assert route['expected_list_prefix'] == list(PAIRS)
    assert [(o['slot'], o['index'], o['flag_address'], o['flag_mask'])
            for o in route['objects']] == [(1, 29, 0xD5A9, 0x20),
                                          (9, 30, 0xD5A9, 0x40),
                                          (10, 31, 0xD5A9, 0x80)]
    assert TOWER_TOGGLE_OBJECTS[23] == (10, ((1, 29, (10, 62)),
                                          (9, 30, (14, 35)),
                                          (10, 31, (5, 89))))


@pytest.mark.parametrize('flags,hidden_slots', [
    (0, ()), (0x20, (1,)), (0x40, (9,)), (0x80, (10,)),
    (0x60, (1, 9)), (0xA0, (1, 10)), (0xC0, (9, 10)),
    (0xE0, (1, 9, 10)), (0x1F, ()), (0xFF, (1, 9, 10)),
])
def test_only_true_hidden_source_slots_and_origins_removed(flags, hidden_slots):
    pyboy, grid = setup(flags)
    before = deepcopy(pyboy.memory.values), deepcopy(grid)
    result = observe(pyboy, grid)
    hidden = [ORIGINS[s - 1] for s in hidden_slots]
    assert result['toggle_source_calibrated'] is True
    assert result['hidden_source_positions'] == hidden
    assert result['positions'] == [p for s, p in enumerate(ORIGINS, 1) if s not in hidden_slots]
    assert merged(result) == set(ORIGINS) - set(hidden)
    assert (pyboy.memory.values, grid) == before


@pytest.mark.parametrize('pairs', [
    (1, 29, 255), (1, 29, 9, 30, 255), (9, 30, 10, 31, 255),
    (1, 29, 10, 30, 9, 31, 255), (1, 29, 9, 31, 10, 30, 255),
    (9, 30, 1, 29, 10, 31, 255), (1, 29, 9, 30, 10, 31, 2, 32, 255),
    (1, 33, 9, 30, 10, 31, 255), (1, 29, 1, 30, 10, 31, 255),
    (1, 29, 9, 29, 10, 31, 255), (1, 29, 9, 30, 10, 228, 255),
    (1, 29, 9, 30, 10, 31) + (0,) * 27,
    (1, 29, 9, 30, 10, 31, True), (1, 29, 9, 30, 11, 31, 255),
])
def test_incomplete_reordered_wrong_or_invalid_source_table_never_clears(pairs):
    pyboy, grid = setup(0xE0, pairs=pairs)
    result = observe(pyboy, grid)
    assert result['toggle_source_calibrated'] is False
    assert result['hidden_source_positions'] == []
    assert result['positions'] == ORIGINS and merged(result) == set(ORIGINS)


@pytest.mark.parametrize('count', [0, 3, 9, 11, 15, 16, True])
def test_wrong_source_object_count_never_clears(count):
    pyboy, grid = setup(0xE0, count=count)
    result = observe(pyboy, grid)
    assert result['toggle_source_calibrated'] is False
    assert not result['hidden_source_positions'] and merged(result) == set(ORIGINS)


@pytest.mark.parametrize('ready', [False, None, 0, 1, 'true'])
def test_unverified_overworld_cannot_clear_anything(ready):
    pyboy, grid = setup(0xE0)
    result = observe(pyboy, grid, ready=ready)
    assert result['toggle_source_calibrated'] is False
    assert result['toggle_snapshot'] is None and merged(result) == set(ORIGINS)


@pytest.mark.parametrize('change', [
    lambda p, g: p.memory.values.update({0xD35E: 24}),
    lambda p, g: p.memory.values.update({0xD5A9: True}),
    lambda p, g: p.memory.values.update({0xD5A9: -1}),
    lambda p, g: p.memory.values.update({0xD5EE: 256}),
    lambda p, g: g.update(observation_frame=49),
    lambda p, g: g.pop('observation_frame'),
    lambda p, g: g.update(verified_location=[24, 10, 61]),
])
def test_unknown_read_map_or_frame_keeps_all_static_obstacles(change):
    pyboy, grid = setup(0xE0)
    change(pyboy, grid)
    result = observe(pyboy, grid)
    assert result['toggle_source_calibrated'] is False
    assert not result['hidden_source_positions'] and merged(result) == set(ORIGINS)


@pytest.mark.parametrize('kwargs', [
    {'frames': (50, 51)}, {'frames': (49, 49)}, {'fail_at': 0xD5A9},
    {'fail_at': 0xD5EE}, {'sequence': {0xD35E: (23, 24)}},
    {'sequence': {0xD4E1: (10, 9)}},
])
def test_getter_failure_or_changed_frame_map_count_does_not_clear(kwargs):
    pyboy, grid = setup(0xE0, **kwargs)
    result = observe(pyboy, grid)
    assert result['toggle_source_calibrated'] is False
    assert result['toggle_snapshot']['read_valid'] is False
    assert result['toggle_snapshot']['objects'] is None
    assert merged(result) == set(ORIGINS)


def test_trailing_bytes_after_real_terminator_are_not_mistaken_for_more_pairs():
    pyboy, grid = setup()
    pyboy.memory.values.update({a: 254 for a in range(0xD5D5, 0xD5EF)})
    result = observe(pyboy, grid)
    assert result['toggle_source_calibrated'] is True
    assert result['hidden_source_positions'] == [(10, 62)]


def test_hidden_stale_sprite_and_origin_clear_but_moved_trainer_remains():
    pyboy, grid = setup()
    values = pyboy.memory.values
    # 隱藏slot1殘留其他位置；正常slot2走位，兩者不可互相替代。
    values.update({0xC214: 65 + 4, 0xC215: 10 + 4,
                   0xC224: 32 + 4, 0xC225: 14 + 4})
    result = observe(pyboy, grid)
    assert result['toggle_source_calibrated'] is True
    assert (10, 65) not in result['positions'] and (14, 32) in result['positions']
    assert result['hidden_source_positions'] == [(10, 62)]
    assert (10, 62) not in merged(result) and (14, 32) in merged(result)
    assert (14, 35) in merged(result) and (5, 89) in merged(result)


def test_hidden_sprite_header_already_cleared_still_removes_original_static_anchor():
    pyboy, grid = setup()
    pyboy.memory.values[0xC110] = 0
    result = observe(pyboy, grid)
    assert result['hidden_source_positions'] == [(10, 62)]
    assert (10, 62) not in merged(result)


def test_other_dynamic_npc_on_hidden_origin_still_blocks_that_cell():
    pyboy, grid = setup()
    pyboy.memory.values.update({0xC224: 62 + 4, 0xC225: 10 + 4})
    result = observe(pyboy, grid)
    assert result['hidden_source_positions'] == [(10, 62)]
    assert (10, 62) in result['positions'] and (10, 62) in merged(result)


@pytest.mark.parametrize('hidden', [False, True])
def test_bfs_only_crosses_narrow_snorlax_path_after_source_verified_hidden(hidden):
    pyboy, grid = setup(0x20 if hidden else 0)
    grid['walkable'] = [[0] * 20 for _ in range(108)]
    for y in range(61, 65):
        grid['walkable'][y][10] = 1
    result = observe(pyboy, grid)
    hint = world_direction(grid, {'x': 10, 'y': 61}, {'x': 10, 'y': 64}, merged(result))
    if hidden:
        assert hint['direction'] == 'down' and hint['path_length'] == 3
    else:
        assert hint is None


def test_no_source_anchor_does_not_create_a_source_calibration():
    pyboy, grid = setup()
    assert read_npc_obstacles(pyboy, grid, [(0, 0)], overworld_ready=True) is None
