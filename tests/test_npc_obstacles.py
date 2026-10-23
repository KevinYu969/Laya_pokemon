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
