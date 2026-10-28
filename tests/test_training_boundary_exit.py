"""MART南界與CAVERN東界：站在warp格仍須真方向鍵才能觸發。"""
import pytest
from laya_pokemon import league_training_supervisor as training
from laya_pokemon.world_map import world_direction


@pytest.mark.parametrize('mid,cell,size,direction,next_map',[
    (174,(7,11),(16,12),'down',9),
    (194,(29,7),(30,18),'right',34),
])
def test_training_exit_emits_edge_key_instead_of_waiting_on_warp(mid,cell,size,direction,next_map):
    # a536711 map_constants + object warp events give these dimensions/cells.
    width,height=size;grid=dict(walkable=[[1]*width for _ in range(height)],screen_cells_verified=12)
    loc=dict(map_id=mid,x=cell[0],y=cell[1])
    old=dict(x=cell[0],y=cell[1])
    assert world_direction(grid,loc,old) is None
    steps=training.outbound() if mid==174 else training.recovery(dict(map_id=194,x=28,y=7))
    step=next(s for s in steps if s['map_id']==mid and s.get('next_map')==next_map)
    target=dict(zip(('x','y'),step['target']))
    result=world_direction(grid,loc,target)
    assert result['kind']=='map_exit' and result['direction']==direction and result['path_length']==1
    before=dict(loc)
    before['y' if direction=='down' else 'x']-=1
    approach=world_direction(grid,before,target)
    assert approach['direction']==direction and approach['endpoint']==list(cell)
