"""固定Forest陸地雙格碰撞；合成純網格，不讀遊戲、ROM或存檔。"""
from copy import deepcopy

import pytest

from laya_pokemon.world_map import (
    FOREST_LAND_TILE_PAIRS, FOREST_TILESET_ID, cavern_pair_blocked_edges,
    tileset_pair_blocked_edges, world_direction,
)


# 固定pret/pokered a536711；pair表blob848695568f30ebe56c88528ae6f5062247f8d37d。
# 獨立列原文數值，不只從待測常數產生期望。
SOURCE_FOREST_PAIRS = ((0x30, 0x2E), (0x52, 0x2E), (0x55, 0x2E),
                       (0x56, 0x2E), (0x20, 0x2E), (0x5E, 0x2E), (0x5F, 0x2E))


def grid(tiles, tileset=FOREST_TILESET_ID):
    result = {'walkable': [[1]*len(row) for row in tiles], 'tiles': deepcopy(tiles),
              'screen_cells_verified': 90}
    if tileset is not None:
        result['tileset_id'] = tileset
    return result


def loc(x, y):
    return {'x': x, 'y': y}


def test_fixed_source_land_table_and_forest_id_match_exactly():
    assert FOREST_TILESET_ID == 3
    assert FOREST_LAND_TILE_PAIRS == SOURCE_FOREST_PAIRS


@pytest.mark.parametrize('pair', SOURCE_FOREST_PAIRS)
@pytest.mark.parametrize('reverse', [False, True])
def test_horizontal_pair_is_bidirectional_but_can_detour_to_same_tile(pair, reverse):
    current = grid([[1, 1], list(pair)])
    before = deepcopy(current)
    a,b = (loc(1,1),loc(0,1)) if reverse else (loc(0,1),loc(1,1))
    edges = tileset_pair_blocked_edges(current)
    assert edges == {((0,1),(1,1)),((1,1),(0,1))}
    result = world_direction(current,a,b)
    assert result['direction']=='up' and result['path_length']==3
    assert current == before


@pytest.mark.parametrize('pair', SOURCE_FOREST_PAIRS)
@pytest.mark.parametrize('reverse', [False, True])
def test_vertical_pair_is_bidirectional_but_can_detour_to_same_tile(pair, reverse):
    first,second = pair
    current = grid([[1, first], [1, second]])
    a,b = (loc(1,1),loc(1,0)) if reverse else (loc(1,0),loc(1,1))
    assert tileset_pair_blocked_edges(current) == {((1,0),(1,1)),((1,1),(1,0))}
    result=world_direction(current,a,b)
    assert result['direction']=='left' and result['path_length']==3


@pytest.mark.parametrize('pair', SOURCE_FOREST_PAIRS)
@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('vertical', [False, True])
def test_no_alternate_path_does_not_offer_an_impossible_walk(pair,reverse,vertical):
    current=grid([[pair[0]],[pair[1]]] if vertical else [list(pair)])
    a,b=(loc(0,0),loc(0,1)) if vertical else (loc(0,0),loc(1,0))
    if reverse:a,b=b,a
    assert world_direction(current,a,b) is None


@pytest.mark.parametrize('pair', SOURCE_FOREST_PAIRS)
def test_nonadjacent_tiles_are_not_walls_or_long_distance_blocked_edges(pair):
    current=grid([[pair[0],1,pair[1]]])
    assert tileset_pair_blocked_edges(current)==set()
    assert world_direction(current,loc(0,0),loc(2,0))['path_length']==2


@pytest.mark.parametrize('pair', SOURCE_FOREST_PAIRS)
def test_source_edges_merge_with_directed_learned_edges_without_mutation(pair):
    current=grid([[1,1,1],[1,pair[0],pair[1]],[1,1,1]])
    before=deepcopy(current); learned={((1,1),(1,0))}
    result=world_direction(current,loc(1,1),loc(2,1),blocked_edges=learned)
    assert result['direction']=='down' and result['path_length']==3
    reverse=world_direction(current,loc(1,0),loc(1,1),blocked_edges=learned)
    assert reverse['direction']=='down' and reverse['path_length']==1
    assert learned=={((1,1),(1,0))} and current==before


@pytest.mark.parametrize('tileset',[0,1,2,16,17,23,None])
@pytest.mark.parametrize('pair',SOURCE_FOREST_PAIRS)
def test_forest_table_does_not_leak_into_other_or_untagged_tilesets(pair,tileset):
    current=grid([list(pair)],tileset)
    assert tileset_pair_blocked_edges(current)==set()
    result=world_direction(current,loc(0,0),loc(1,0))
    assert result['direction']=='right' and result['path_length']==1


@pytest.mark.parametrize('pair',[(0x14,0x2E),(0x48,0x2E)])
@pytest.mark.parametrize('reverse',[False,True])
def test_water_table_is_not_applied_by_land_dispatcher(pair,reverse):
    if reverse:pair=pair[::-1]
    current=grid([list(pair)])
    assert tileset_pair_blocked_edges(current)==set()
    assert world_direction(current,loc(0,0),loc(1,0))['direction']=='right'


@pytest.mark.parametrize('tiles',[None,[],[[]],[[0x30]],[[0x30,0x2E],[1,1]],
                                 [[0x30,'unknown']],[[0x30,None]],[[0x30,True]],
                                 [[0x30,46.0]],[[0x30,-1]],[[0x30,256]],
                                 'not-a-matrix',[0x30,0x2E]])
def test_forest_incomplete_or_nonbyte_tile_matrix_fails_closed(tiles):
    current=grid([[0x30,0x2E]]); current['tiles']=tiles
    assert tileset_pair_blocked_edges(current) is None
    assert world_direction(current,loc(0,0),loc(1,0)) is None
    # 舊洞窟函式仍不接管Forest，就算它的tiles壞掉也一樣。
    assert cavern_pair_blocked_edges(current)==set()


def test_forest_missing_tile_matrix_fails_closed():
    current=grid([[0x30,0x2E]]);del current['tiles']
    assert tileset_pair_blocked_edges(current) is None
    assert world_direction(current,loc(0,0),loc(1,0)) is None


@pytest.mark.parametrize('cells',[None,[],[[]],[1],['xx'],[[1],[1,1]]])
def test_malformed_forest_walkable_shape_fails_closed_before_bfs_indexing(cells):
    current=grid([[0x30,0x2E]]);current['walkable']=cells
    assert tileset_pair_blocked_edges(current) is None
    assert world_direction(current,loc(0,0),loc(1,0)) is None


def test_ragged_forest_tiles_and_walkable_rows_fail_closed():
    current=grid([[1,0x30],[1,0x2E]])
    current['tiles'][1].pop()
    assert world_direction(current,loc(1,0),loc(1,1)) is None
    current=grid([[1,0x30],[1,0x2E]])
    current['walkable'][1].pop()
    assert world_direction(current,loc(1,0),loc(1,1)) is None


def test_tuple_matrix_supported_and_never_rewritten():
    current={'tileset_id':3,'walkable':((1,1),(1,1)),
             'tiles':((1,1),(0x30,0x2E)),'screen_cells_verified':90}
    before=deepcopy(current)
    assert world_direction(current,loc(0,1),loc(1,1))['path_length']==3
    assert current==before
