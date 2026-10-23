"""以合成網格核對洞穴高低差禁邊；不讀 ROM、存檔或遊戲狀態。"""
from copy import deepcopy

import pytest

from laya_pokemon.world_map import (CAVERN_LAND_TILE_PAIRS, CAVERN_TILESET_ID,
                                    cavern_pair_blocked_edges, world_direction,visible_map_proof)


def test_visible_proof_is_only_actual_matching_in_bounds_cells():
    tiles=[[y*8+x for x in range(8)] for y in range(6)]
    screen=[r[2:6] for r in tiles[1:4]]
    assert visible_map_proof(tiles,screen,2,1)==[[x,y] for y in range(1,4) for x in range(2,6)]
    assert visible_map_proof(tiles,screen[:2],2,1) is None
    wrong=deepcopy(screen);wrong[-1][-1]=255
    assert visible_map_proof(tiles,wrong,2,1) is None
    assert tiles[3][5]==29


def grid(tiles, tileset=CAVERN_TILESET_ID):
    result = {'walkable': [[1]*len(row) for row in tiles], 'tiles': deepcopy(tiles),
              'screen_cells_verified': 90}
    if tileset is not None:
        result['tileset_id'] = tileset
    return result


def loc(x, y):
    return {'x': x, 'y': y}


@pytest.mark.parametrize('pair', CAVERN_LAND_TILE_PAIRS)
@pytest.mark.parametrize('reverse', [False, True])
def test_cavern_horizontal_pair_is_bidirectional_and_destination_still_reachable(pair, reverse):
    first, second = pair
    current = grid([[0x30, 0x30], [first, second]])
    start, end = (loc(1, 1), loc(0, 1)) if reverse else (loc(0, 1), loc(1, 1))
    result = world_direction(current, start, end)
    assert result['direction'] == 'up' and result['path_length'] == 3
    assert current['walkable'] == [[1, 1], [1, 1]]


@pytest.mark.parametrize('pair', CAVERN_LAND_TILE_PAIRS)
@pytest.mark.parametrize('reverse', [False, True])
def test_cavern_vertical_pair_also_requires_detour_in_both_directions(pair, reverse):
    first, second = pair
    current = grid([[0x30, first], [0x30, second]])
    start, end = (loc(1, 1), loc(1, 0)) if reverse else (loc(1, 0), loc(1, 1))
    result = world_direction(current, start, end)
    assert result['direction'] == 'left' and result['path_length'] == 3


@pytest.mark.parametrize('pair', CAVERN_LAND_TILE_PAIRS)
@pytest.mark.parametrize('reverse', [False, True])
def test_cavern_pair_with_no_alternate_path_does_not_return_an_impossible_step(pair, reverse):
    current = grid([list(pair)])
    start, end = (loc(1, 0), loc(0, 0)) if reverse else (loc(0, 0), loc(1, 0))
    assert world_direction(current, start, end) is None


@pytest.mark.parametrize('tileset', [0, 3, 16, 23, None])
def test_cavern_rules_do_not_leak_into_other_tilesets_or_untagged_grids(tileset):
    current = grid([[0x20, 0x05]], tileset)
    result = world_direction(current, loc(0, 0), loc(1, 0))
    assert result['direction'] == 'right' and result['path_length'] == 1
    assert cavern_pair_blocked_edges(current) == set()


def test_generic_walkable_only_grid_preserves_existing_bfs():
    current = {'walkable': [[1, 1, 1]], 'screen_cells_verified': 90}
    result = world_direction(current, loc(0, 0), loc(2, 0))
    assert result['direction'] == 'right' and result['path_length'] == 2


def test_pair_edges_merge_with_existing_directed_failed_walk_edges():
    current = grid([[0x30]*3, [0x30, 0x20, 0x05], [0x30]*3])
    learned = {((1, 1), (1, 0))}
    snapshot = deepcopy(current)
    result = world_direction(current, loc(1, 1), loc(2, 1), blocked_edges=learned)
    assert result['direction'] == 'down' and result['path_length'] == 3
    # 舊學習邊仍保持單向；新的來源雙格邊不取代它，也不改輸入物件。
    reverse = world_direction(current, loc(1, 0), loc(1, 1), blocked_edges=learned)
    assert reverse['direction'] == 'down' and reverse['path_length'] == 1
    assert learned == {((1, 1), (1, 0))} and current == snapshot


def test_equal_tile_ids_at_nonadjacent_cells_are_not_a_global_wall_or_teleport_edge():
    result = world_direction(grid([[0x20, 0x30, 0x05]]), loc(0, 0), loc(2, 0))
    assert result['direction'] == 'right' and result['path_length'] == 2


def test_cavern_public_helper_does_not_add_water_or_forest_table_pairs():
    # 舊洞窟API仍不負責Forest；world_direction的Forest功能另行核對。
    for tileset, pair in [(17, (0x14, 0x05)), (17, (0x30, 0x2E)), (3, (0x30, 0x2E))]:
        assert cavern_pair_blocked_edges(grid([list(pair)], tileset)) == set()


def test_world_land_controller_does_not_add_water_or_wrong_tileset_pairs():
    for tileset, pair in [(17, (0x14, 0x05)), (17, (0x30, 0x2E)),
                          (3, (0x14, 0x2E)), (3, (0x48, 0x2E)), (3, (0x20, 0x05))]:
        result = world_direction(grid([list(pair)], tileset), loc(0, 0), loc(1, 0))
        assert result['direction'] == 'right' and result['path_length'] == 1


def test_world_direction_now_applies_forest_land_table_without_changing_cavern_api():
    current = grid([[0x30, 0x2E]], 3)
    assert cavern_pair_blocked_edges(current) == set()
    assert world_direction(current, loc(0, 0), loc(1, 0)) is None


@pytest.mark.parametrize('tiles', [None, [[0x20]], [[0x20, 'unknown']]])
def test_cavern_tag_without_matching_complete_tile_matrix_fails_closed(tiles):
    current = grid([[0x20, 0x05]])
    current['tiles'] = tiles
    assert cavern_pair_blocked_edges(current) is None
    assert world_direction(current, loc(0, 0), loc(1, 0)) is None
