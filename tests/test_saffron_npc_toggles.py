"""固定金黃市15物件：真getter＋真overlay，僅使用禁止寫入的fake memory。"""
from copy import deepcopy

import pytest

from laya_pokemon.toggleable_objects import read_toggleable_objects
from laya_pokemon.world_map import TOWER_TOGGLE_OBJECTS, read_npc_obstacles, world_direction


# pret/pokered a53671100ec22e5394ff26ec028d0812a238dae2
# objects/SaffronCity.asm blob ce8772a5e822276bb5d2ebc0437dc30a805aa560
# toggleable_objects.asm blob 90f9e6892ba779ebaa6bdfead00335cf72a8fb8b
# toggle_constants.asm blob 64712306d6b47395c000ce73ee27d5a469fd07f2
SOURCE_ROWS = (
    (1, 10, (7, 6)), (2, 11, (20, 8)), (3, 12, (34, 4)),
    (4, 13, (13, 12)), (5, 14, (11, 25)), (6, 15, (32, 13)),
    (7, 16, (18, 30)), (8, 17, (8, 14)), (9, 18, (23, 23)),
    (10, 19, (17, 30)), (11, 20, (30, 12)), (12, 21, (31, 12)),
    (13, 22, (18, 8)), (14, 23, (18, 22)), (15, 24, (19, 22)),
)
ORIGINS = [row[2] for row in SOURCE_ROWS]
PAIRS = tuple(value for slot, index, _ in SOURCE_ROWS for value in (slot, index)) + (255,)


class ReadOnlyMemory:
    def __init__(self, values, *, sequence=None, fail_at=None):
        self.values = values
        self.sequence = {address: iter(seq) for address, seq in (sequence or {}).items()}
        self.fail_at = fail_at

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


def setup(hidden=(), *, pairs=PAIRS, count=15, frames=(100, 100),
          sequence=None, fail_at=None):
    values = {address: 0 for address in range(0xC100, 0xC300)}
    values.update({address: 0 for address in range(0xD5A6, 0xD5C6)})
    values.update({address: 0 for address in range(0xD5CE, 0xD5EF)})
    values.update({0xD35E: 10, 0xD4E1: count})
    values.update({0xD5CE + offset: byte for offset, byte in enumerate(pairs)})
    for slot, index, (x, y) in SOURCE_ROWS:
        values[0xC100 + 16 * slot] = 1
        values[0xC102 + 16 * slot] = 255  # 圖像離屏狀態不是hidden證據。
        values[0xC204 + 16 * slot] = y + 4
        values[0xC205 + 16 * slot] = x + 4
        if slot in hidden:
            values[0xD5A6 + index // 8] |= 1 << (index % 8)
    grid = {'walkable': [[1] * 40 for _ in range(36)],
            'verified_location': [10, 18, 23], 'observation_frame': 100,
            'screen_cells_verified': 90}
    return GetterOnly(ReadOnlyMemory(values, sequence=sequence, fail_at=fail_at), frames), grid


def observe(pyboy, grid, *, ready=True):
    return read_npc_obstacles(pyboy, grid, ORIGINS, overworld_ready=ready)


def blocked(result, extra=()):
    """沿用呼叫端：只扣已校準hidden origin，再聯集當前NPC與其他障礙。"""
    hidden = result['hidden_source_positions'] if result['toggle_source_calibrated'] is True else []
    return (set(ORIGINS) - set(hidden)) | set(result['positions']) | set(extra)


def assert_not_cleared(result):
    assert result['toggle_source_calibrated'] is False
    assert result['hidden_source_positions'] == []
    assert result['positions'] == ORIGINS
    assert blocked(result) == set(ORIGINS)


def test_complete_fifteen_source_table_and_existing_maps_are_exact():
    assert TOWER_TOGGLE_OBJECTS[10] == (15, SOURCE_ROWS)
    assert PAIRS == (1, 10, 2, 11, 3, 12, 4, 13, 5, 14, 6, 15, 7, 16,
                     8, 17, 9, 18, 10, 19, 11, 20, 12, 21, 13, 22, 14, 23, 15, 24, 255)
    assert TOWER_TOGGLE_OBJECTS[23] == (10, ((1, 29, (10, 62)),
                                          (9, 30, (14, 35)), (10, 31, (5, 89))))
    assert TOWER_TOGGLE_OBJECTS[147] == (5, ((4, 62, (6, 8)), (5, 63, (14, 14))))
    assert TOWER_TOGGLE_OBJECTS[148] == (4, ((1, 64, (9, 11)), (2, 65, (12, 9)),
                                          (3, 66, (9, 7)), (4, 67, (10, 3))))


@pytest.mark.parametrize('hidden_slot', range(1, 16))
def test_each_single_hidden_bit_uses_real_getter_and_only_clears_its_slot(hidden_slot):
    pyboy, _ = setup((hidden_slot,))
    snapshot = read_toggleable_objects(pyboy, map_id=10, observation_frame=100)
    assert snapshot['read_valid'] is True and snapshot['sprite_count'] == 15
    assert [(o['slot'], o['index']) for o in snapshot['objects']] == [(s, i) for s, i, _ in SOURCE_ROWS]
    assert [o['slot'] for o in snapshot['objects'] if o['hidden'] is True] == [hidden_slot]
    pyboy, grid = setup((hidden_slot,))
    before = deepcopy(pyboy.memory.values), deepcopy(grid)
    result = observe(pyboy, grid)
    assert result['toggle_source_calibrated'] is True
    assert result['hidden_source_positions'] == [ORIGINS[hidden_slot - 1]]
    assert result['positions'] == [p for slot, p in enumerate(ORIGINS, 1) if slot != hidden_slot]
    assert blocked(result) == set(ORIGINS) - {ORIGINS[hidden_slot - 1]}
    assert (pyboy.memory.values, grid) == before


def test_fuji_hides_old_silph_blocker_but_preserves_replacement_and_gym_guard():
    # 原始初始化隱藏市民8..13、Rocket9(slot15)；救援才Hide23、Show24。
    pyboy, grid = setup((*range(8, 14), 14))
    result = observe(pyboy, grid)
    assert result['toggle_source_calibrated'] is True
    assert (18, 22) not in blocked(result)
    assert (19, 22) in blocked(result)
    assert (34, 4) in blocked(result)
    assert result['positions'] == [p for slot, p in enumerate(ORIGINS, 1)
                                   if slot in (*range(1, 8), 15)]


def test_giovanni_hide_show_mode_preserves_all_six_citizens():
    pyboy, grid = setup((*range(1, 8), 14, 15))
    result = observe(pyboy, grid)
    assert result['toggle_source_calibrated'] is True
    assert result['positions'] == ORIGINS[7:13]
    assert blocked(result) == set(ORIGINS[7:13])
    assert (34, 4) not in blocked(result)


@pytest.mark.parametrize('pairs', [
    PAIRS[:-3] + (255,),                         # 完整表缺slot15。
    PAIRS[2:-1] + (255,),                       # 缺第一對。
    PAIRS[2:4] + PAIRS[:2] + PAIRS[4:],         # 正確pairs但重排。
    (1, 25) + PAIRS[2:],                        # 已知範圍但錯global index。
    PAIRS[:26] + (14, 24, 15, 23, 255),        # 兩個門前NPC對錯index。
    PAIRS[:28] + (14, 24, 255),                 # 重複slot。
    PAIRS[:28] + (15, 23, 255),                 # 重複index。
    PAIRS[:-1] + (0, 0, 0),                    # 未終止。
])
def test_missing_reordered_wrong_or_duplicate_pairs_keep_phantom_blockers(pairs):
    pyboy, grid = setup((14,), pairs=pairs)
    assert_not_cleared(observe(pyboy, grid))


@pytest.mark.parametrize('count', [0, 14, 16, True])
def test_wrong_count_cannot_remove_old_silph_guard(count):
    pyboy, grid = setup((14,), count=count)
    assert_not_cleared(observe(pyboy, grid))


@pytest.mark.parametrize('ready', [False, None, 0, 1, 'true'])
def test_readiness_requires_exact_true_bool(ready):
    pyboy, grid = setup((14,))
    result = observe(pyboy, grid, ready=ready)
    assert_not_cleared(result)
    assert result['toggle_snapshot'] is None


@pytest.mark.parametrize('change', [
    lambda p, g: p.memory.values.update({0xD35E: 11}),
    lambda p, g: g.update(verified_location=[11, 18, 23]),
    lambda p, g: g.update(observation_frame=99),
    lambda p, g: g.update(observation_frame=True),
    lambda p, g: g.pop('observation_frame'),
    lambda p, g: p.memory.values.update({0xD5A8: True}),
    lambda p, g: p.memory.values.update({0xD5A8: -1}),
    lambda p, g: p.memory.values.update({0xD5EE: 256}),
])
def test_wrong_map_frame_or_invalid_bytes_do_not_remove_phantom(change):
    pyboy, grid = setup((14,))
    change(pyboy, grid)
    assert_not_cleared(observe(pyboy, grid))


@pytest.mark.parametrize('kwargs', [
    {'frames': (100, 101)}, {'frames': (99, 99)},
    {'sequence': {0xD35E: (10, 11)}},
    {'sequence': {0xD4E1: (15, 14)}},
    {'fail_at': 0xD5A8}, {'fail_at': 0xD5EE},
])
def test_torn_frame_map_count_or_failed_getter_is_unknown(kwargs):
    pyboy, grid = setup((14,), **kwargs)
    result = observe(pyboy, grid)
    assert_not_cleared(result)
    assert result['toggle_snapshot']['read_valid'] is False
    assert result['toggle_snapshot']['objects'] is None


def test_moving_alive_sprite_and_hidden_stale_sprite_are_not_interchanged():
    pyboy, grid = setup((14,))
    values = pyboy.memory.values
    values.update({0xC204 + 16 * 14: 24 + 4, 0xC205 + 16 * 14: 18 + 4,
                   0xC204 + 16 * 2: 9 + 4, 0xC205 + 16 * 2: 21 + 4})
    result = observe(pyboy, grid)
    assert result['hidden_source_positions'] == [(18, 22)]
    assert (18, 24) not in result['positions']
    assert (21, 9) in result['positions'] and (21, 9) in blocked(result)
    assert (19, 22) in blocked(result)


def test_alive_other_slot_on_hidden_origin_still_blocks_cell():
    pyboy, grid = setup((14,))
    pyboy.memory.values.update({0xC204 + 16 * 2: 22 + 4, 0xC205 + 16 * 2: 18 + 4})
    result = observe(pyboy, grid)
    assert result['hidden_source_positions'] == [(18, 22)]
    assert (18, 22) in result['positions'] and (18, 22) in blocked(result)


def test_already_absent_hidden_sprite_header_can_clear_origin_with_other_anchor():
    pyboy, grid = setup((14,))
    pyboy.memory.values[0xC100 + 16 * 14] = 0
    result = observe(pyboy, grid)
    assert result['toggle_source_calibrated'] is True
    assert (18, 22) not in blocked(result)


def test_no_source_anchor_produces_no_overlay():
    pyboy, grid = setup((14,))
    assert read_npc_obstacles(pyboy, grid, [(0, 0)], overworld_ready=True) is None


def test_silph_warp_blocking_is_preserved_after_old_guard_is_hidden():
    pyboy, grid = setup((14,))
    result = observe(pyboy, grid)
    grid['walkable'] = [[0] * 40 for _ in range(36)]
    for y in range(20, 24):
        grid['walkable'][y][18] = 1
    assert (18, 22) not in blocked(result)
    assert (18, 21) in blocked(result, [(18, 21)])
    assert world_direction(grid, {'x': 18, 'y': 23}, {'x': 18, 'y': 20},
                           blocked(result, [(18, 21)])) is None
    assert world_direction(grid, {'x': 18, 'y': 23}, {'x': 18, 'y': 20},
                           blocked(result))['direction'] == 'up'


@pytest.mark.parametrize('hidden', [False, True])
def test_narrow_silph_front_route_only_opens_on_verified_hidden_bit(hidden):
    pyboy, grid = setup((14,) if hidden else ())
    result = observe(pyboy, grid)
    grid['walkable'] = [[0] * 40 for _ in range(36)]
    for y in range(21, 24):
        grid['walkable'][y][18] = 1
    route = world_direction(grid, {'x': 18, 'y': 23}, {'x': 18, 'y': 21}, blocked(result))
    if hidden:
        assert route['direction'] == 'up' and route['path_length'] == 2
    else:
        assert route is None
