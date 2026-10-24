"""固定公開11樓來源＋唯讀fake memory；不讀ROM／存檔、不操作遊戲。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

import pytest

from laya_pokemon.world_map import TOWER_TOGGLE_OBJECTS, read_npc_obstacles, world_direction


FIXTURE = Path(__file__).parent / 'data' / 'toggleable-source-fixture.json'
SOURCE_ROWS = ((3, 183, (6, 9)), (4, 184, (3, 16)), (5, 185, (15, 9)))
ORIGINS = [(7, 5), (10, 5), (6, 9), (3, 16), (15, 9)]
PAIRS = (3, 183, 4, 184, 5, 185, 255)


class ReadOnlyMemory:
    def __init__(self, values, *, fail_at=None, sequence=None):
        self.values = values
        self.fail_at = fail_at
        self.sequence = {key: iter(values) for key, values in (sequence or {}).items()}

    def __getitem__(self, address):
        if address == self.fail_at:
            raise RuntimeError('synthetic getter failure')
        if address in self.sequence:
            return next(self.sequence[address])
        return self.values[address]

    def __setitem__(self, address, value):
        raise AssertionError('不得寫入RAM')


class GetterOnly:
    def __init__(self, memory, frames):
        self.memory = memory
        self.frames = iter(frames)

    @property
    def frame_count(self):
        return next(self.frames)

    def __getattr__(self, name):
        raise AssertionError(f'不得操作模擬器：{name}')


def setup(hidden=(), *, pairs=PAIRS, count=5, frames=(100, 100),
          fail_at=None, sequence=None):
    values = {address: 0 for address in range(0xC100, 0xC300)}
    values.update({address: 0 for address in range(0xD5A6, 0xD5C6)})
    values.update({address: 0 for address in range(0xD5CE, 0xD5EF)})
    values.update({0xD35E: 235, 0xD4E1: count})
    values.update({0xD5CE + offset: byte for offset, byte in enumerate(pairs)})
    for slot, (x, y) in enumerate(ORIGINS, 1):
        values[0xC100 + 16 * slot] = 1
        values[0xC102 + 16 * slot] = 255  # FF可能僅離屏，不能作hidden證據。
        values[0xC204 + 16 * slot] = y + 4
        values[0xC205 + 16 * slot] = x + 4
    for slot, index, _ in SOURCE_ROWS:
        if slot in hidden:
            values[0xD5A6 + index // 8] |= 1 << (index % 8)
    grid = {'walkable': [[1] * 18 for _ in range(18)],
            'verified_location': [235, 6, 14], 'observation_frame': 100,
            'screen_cells_verified': 80}
    return GetterOnly(ReadOnlyMemory(values, fail_at=fail_at, sequence=sequence), frames), grid


def observe(pyboy, grid, *, ready=True):
    return read_npc_obstacles(pyboy, grid, ORIGINS, overworld_ready=ready)


def blocked(result, extra=()):
    """照既有呼叫端：扣真hidden來源，再聯集當前NPC及其他障礙。"""
    cleared = result['hidden_source_positions'] if result['toggle_source_calibrated'] is True else []
    return (set(ORIGINS) - set(cleared)) | set(result['positions']) | set(extra)


def assert_not_cleared(result):
    assert result['toggle_source_calibrated'] is False
    assert result['hidden_source_positions'] == []
    assert result['positions'] == ORIGINS
    assert blocked(result) == set(ORIGINS)


def test_fixed_public_fixture_count_order_positions_and_flag_bits():
    fixture = json.loads(FIXTURE.read_text(encoding='utf-8'))
    source = fixture['maps']['235']
    assert fixture['source_commit'] == 'a53671100ec22e5394ff26ec028d0812a238dae2'
    assert fixture['kind'] == 'public_source_only_not_live_snapshot'
    assert source['source_only_not_snapshot'] is True
    assert source['source_object_count'] == 5
    assert TOWER_TOGGLE_OBJECTS[235] == (5, SOURCE_ROWS)
    assert source['expected_list_prefix'] == list(PAIRS)
    assert [o['slot'] for o in source['all_source_objects']] == [1, 2, 3, 4, 5]
    assert [tuple(o['source_position']) for o in source['all_source_objects']] == ORIGINS
    assert [(o['slot'], o['index'], tuple(o['source_position']))
            for o in source['objects']] == list(SOURCE_ROWS)
    assert [(o['flag_address'], o['flag_bit'], o['flag_mask'])
            for o in source['objects']] == [(0xD5BC, 7, 128), (0xD5BD, 0, 1), (0xD5BD, 1, 2)]
    proof = source['source_proof']
    full = proof['objects']['text'].encode('utf-8')
    assert hashlib.sha256(full).hexdigest() == '8c1b9dfaaf8644b973cc02a2f9c91437eeb8fdc1e3af4e4d3df59d7ffcfb0438'
    assert hashlib.sha1(b'blob ' + str(len(full)).encode() + b'\0' + full).hexdigest() == 'b1f5a9f09062c438c56666a9304a7dbf7f699055'
    rows = re.findall(r'^\s*object_event\s+(\d+),\s*(\d+),\s*(\w+)',
                      proof['objects']['text'], re.MULTILINE)
    assert [(int(x), int(y)) for x, y, _ in rows] == ORIGINS
    assert [o['source_object'] for o in source['all_source_objects']] == re.findall(
        r'^\s*const_export (\w+)', proof['objects']['text'], re.MULTILINE)
    assert re.findall(r'toggle_object_state\s+(\w+),\s*ON', proof['toggle_table']['excerpt']) == [
        'SILPHCO11F_GIOVANNI', 'SILPHCO11F_ROCKET1', 'SILPHCO11F_ROCKET2']
    assert re.findall(r'const (TOGGLE_SILPH_CO_11F_\d)\s*; ([0-9A-F]+)',
                      proof['toggle_constants']['excerpt']) == [
        ('TOGGLE_SILPH_CO_11F_1', 'B7'), ('TOGGLE_SILPH_CO_11F_2', 'B8'),
        ('TOGGLE_SILPH_CO_11F_3', 'B9')]
    receipts = {item['path']: item['sha256'] for item in fixture['source_files']}
    for item in proof.values():
        assert receipts[item['path']] == item['sha256']


@pytest.mark.parametrize('hidden', [(), (3,), (4,), (5,), (3, 4), (3, 5), (4, 5), (3, 4, 5)])
def test_real_getter_only_clears_true_hidden_slots_and_preserves_president_secretary(hidden):
    pyboy, grid = setup(hidden)
    before = deepcopy(pyboy.memory.values), deepcopy(grid)
    result = observe(pyboy, grid)
    cleared = [pos for slot, _, pos in SOURCE_ROWS if slot in hidden]
    assert result['toggle_source_calibrated'] is True
    assert result['hidden_source_positions'] == cleared
    assert result['positions'] == [pos for slot, pos in enumerate(ORIGINS, 1) if slot not in hidden]
    assert blocked(result) == set(ORIGINS) - set(cleared)
    assert {(7, 5), (10, 5)} <= blocked(result)
    assert (pyboy.memory.values, grid) == before


def test_unrelated_bits_and_offscreen_image_never_hide_visible_npcs():
    pyboy, grid = setup()
    pyboy.memory.values.update({0xD5BC: 0x7F, 0xD5BD: 0xFC})
    result = observe(pyboy, grid)
    assert result['toggle_source_calibrated'] is True
    assert result['hidden_source_positions'] == [] and blocked(result) == set(ORIGINS)


@pytest.mark.parametrize('pairs', [
    (3, 183, 255), (3, 183, 4, 184, 255),
    (4, 184, 3, 183, 5, 185, 255), (3, 184, 4, 183, 5, 185, 255),
    (3, 183, 4, 184, 5, 186, 255), (3, 183, 3, 184, 5, 185, 255),
    (3, 183, 4, 184, 5, 183, 255), PAIRS[:-1] + (0,) * 27,
])
def test_incomplete_reordered_wrong_or_duplicate_pairs_keep_all_blockers(pairs):
    pyboy, grid = setup((3, 4, 5), pairs=pairs)
    assert_not_cleared(observe(pyboy, grid))


@pytest.mark.parametrize('count', [4, 6, True])
def test_wrong_source_object_count_does_not_clear(count):
    pyboy, grid = setup((3,), count=count)
    assert_not_cleared(observe(pyboy, grid))


@pytest.mark.parametrize('ready', [False, None, 0, 1])
def test_not_exact_overworld_ready_keeps_all_blockers(ready):
    pyboy, grid = setup((3, 4, 5))
    result = observe(pyboy, grid, ready=ready)
    assert_not_cleared(result)
    assert result['toggle_snapshot'] is None


@pytest.mark.parametrize('change', [
    lambda p, g: p.memory.values.update({0xD35E: 234}),
    lambda p, g: g.update(verified_location=[234, 6, 14]),
    lambda p, g: g.update(observation_frame=99),
    lambda p, g: g.pop('observation_frame'),
    lambda p, g: p.memory.values.update({0xD5BC: True}),
    lambda p, g: p.memory.values.update({0xD5BD: -1}),
])
def test_unknown_map_frame_or_byte_never_means_hidden(change):
    pyboy, grid = setup((3, 4, 5))
    change(pyboy, grid)
    assert_not_cleared(observe(pyboy, grid))


@pytest.mark.parametrize('kwargs', [
    {'frames': (100, 101)}, {'fail_at': 0xD5BC},
    {'sequence': {0xD35E: (235, 234)}}, {'sequence': {0xD4E1: (5, 4)}},
])
def test_torn_or_failed_read_keeps_all_blockers(kwargs):
    pyboy, grid = setup((3, 4, 5), **kwargs)
    result = observe(pyboy, grid)
    assert_not_cleared(result)
    assert result['toggle_snapshot']['read_valid'] is False


@pytest.mark.parametrize('hidden', [False, True])
def test_moved_giovanni_is_removed_only_if_hidden_but_moved_secretary_stays(hidden):
    pyboy, grid = setup((3,) if hidden else ())
    pyboy.memory.values.update({0xC204 + 16 * 3: 10 + 4, 0xC205 + 16 * 3: 6 + 4,
                               0xC204 + 16 * 2: 6 + 4, 0xC205 + 16 * 2: 10 + 4})
    result = observe(pyboy, grid)
    assert (7, 5) in blocked(result) and (10, 6) in result['positions']
    assert ((6, 10) in result['positions']) is not hidden
    assert ((6, 9) in blocked(result)) is not hidden
    assert result['hidden_source_positions'] == ([(6, 9)] if hidden else [])


def test_other_live_slot_on_hidden_origin_still_blocks_that_cell():
    pyboy, grid = setup((3,))
    pyboy.memory.values.update({0xC204 + 16 * 2: 9 + 4, 0xC205 + 16 * 2: 6 + 4})
    result = observe(pyboy, grid)
    assert result['hidden_source_positions'] == [(6, 9)]
    assert (6, 9) in result['positions'] and (6, 9) in blocked(result)
    assert (7, 5) in blocked(result)


def test_hidden_absent_header_still_clears_source_with_other_anchors():
    pyboy, grid = setup((3,))
    pyboy.memory.values[0xC100 + 16 * 3] = 0
    result = observe(pyboy, grid)
    assert result['toggle_source_calibrated'] is True
    assert (6, 9) not in blocked(result)
    assert {(7, 5), (10, 5)} <= blocked(result)


def test_no_source_anchor_returns_unknown_without_clearing():
    pyboy, grid = setup((3, 4, 5))
    assert read_npc_obstacles(pyboy, grid, [(0, 0)], overworld_ready=True) is None


@pytest.mark.parametrize('hidden', [False, True])
def test_corridor_only_opens_on_true_hidden_and_other_warp_obstacle_stays(hidden):
    pyboy, grid = setup((3,) if hidden else ())
    result = observe(pyboy, grid)
    grid['walkable'] = [[0] * 18 for _ in range(18)]
    for y in range(8, 11):
        grid['walkable'][y][6] = 1
    route = world_direction(grid, {'x': 6, 'y': 10}, {'x': 6, 'y': 8}, blocked(result))
    if hidden:
        assert route['direction'] == 'up' and route['path_length'] == 2
        assert world_direction(grid, {'x': 6, 'y': 10}, {'x': 6, 'y': 8},
                               blocked(result, [(6, 9)])) is None
    else:
        assert route is None
