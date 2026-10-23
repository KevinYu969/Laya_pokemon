from collections import defaultdict
from types import SimpleNamespace
from laya_pokemon.world_map import read_npc_obstacles


def test_moved_trainer_is_blocked_at_actual_position_with_source_anchor():
    memory=defaultdict(int)
    for slot,x,y in [(1,2,2),(2,7,23)]:
        memory[0xC100+16*slot]=4;memory[0xC200+16*slot+5]=x+4;memory[0xC200+16*slot+4]=y+4
    result=read_npc_obstacles(SimpleNamespace(memory=memory),{'walkable':[[1]*40 for _ in range(36)]},[(2,2),(7,22)])
    assert result['source_anchor_matches']==1 and (7,23) in result['positions']


def test_npc_reader_rejects_unanchored_or_unavailable_memory():
    grid={'walkable':[[1]*10 for _ in range(10)]}
    assert read_npc_obstacles(None,grid,[(2,2)]) is None
    assert read_npc_obstacles(SimpleNamespace(memory=defaultdict(int)),grid,[(2,2)]) is None


def test_failed_walk_edge_is_avoided_without_declaring_the_destination_a_wall():
    from laya_pokemon.world_map import world_direction
    grid={'walkable':[[1]*3 for _ in range(3)],'screen_cells_verified':9}
    result=world_direction(grid,{'x':1,'y':1},{'x':0,'y':1},blocked_edges={((1,1),(0,1))})
    assert result['direction']=='up' and result['path_length']==3


def test_three_actual_unmoved_direction_inputs_teach_one_edge(monkeypatch):
    import laya_pokemon.campaign_route as route
    monkeypatch.setattr(route,'_LAST_ATTEMPT',None);monkeypatch.setattr(route,'_LEARNED_EDGES',{})
    monkeypatch.setattr(route,'read_world_grid',lambda *a:{'walkable':[[1]*3 for _ in range(3)],'screen_cells_verified':9})
    state={'location':{'map_id':59,'x':1,'y':1},'progress':{'story_event_bits':{},'party':[]}}
    plan={'steps':[{'id':'walk','map_id':59,'target':[0,1],'kind':'move'}]}
    emulator=SimpleNamespace()
    for _ in range(3):assert route.waypoint(emulator,state,plan,'walk',['left'])[0]['objective']=='Move LEFT.'
    result,_=route.waypoint(emulator,state,plan,'walk',['left'])
    assert result['objective']=='Move UP.' and result['world_path_hint']['observed_blocked_edges']


def test_acquired_fossil_is_not_a_ghost_obstacle(monkeypatch):
    import laya_pokemon.campaign_route as route
    cells=[[0]*20 for _ in range(20)]
    for y in [5,6,7]:cells[y][13]=1
    monkeypatch.setattr(route,'read_world_grid',lambda *a:{'walkable':cells,'screen_cells_verified':90})
    monkeypatch.setattr(route.world_map,'read_npc_obstacles',lambda *a:{'positions':[(13,6)],'source_anchor_matches':1})
    state={'location':{'map_id':61,'x':13,'y':7},'progress':{'story_event_bits':{'got_helix_fossil':True},'party':[]}}
    plan={'blocked':{'61':[[13,6]]},'steps':[{'id':'exit','map_id':61,'target':[13,5],'kind':'move','next_map':60}]}
    result,_=route.waypoint(None,state,plan,'exit',[])
    assert result['objective']=='Move UP.' and result['world_path_hint']['cleared_story_objects']==[(13,6)]


def test_verified_overworld_ledge_is_a_directed_two_cell_path_edge():
    from laya_pokemon.world_map import world_direction
    grid={'walkable':[[1]*3,[0]*3,[1]*3,[1]*3],'tiles':[[0x39]*3,[0x36]*3,[0x39]*3,[0x39]*3],'tileset_id':0,'screen_cells_verified':12}
    result=world_direction(grid,{'x':1,'y':0},{'x':1,'y':3})
    assert result['direction']=='down' and result['ledge_jump'] is True
    grid['tileset_id']=17
    assert world_direction(grid,{'x':1,'y':0},{'x':1,'y':3}) is None
