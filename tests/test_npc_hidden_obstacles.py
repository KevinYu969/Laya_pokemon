"""隱藏物不等於offscreen；只移除已校準Tower表內的真隱藏物。"""
from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path
import json
import pytest
from laya_pokemon.world_map import read_npc_obstacles

def setup(hidden=True):
    memory={address:0 for address in range(0xC100,0xC300)}
    memory.update({a:0 for a in range(0xD5A6,0xD5A6+32)})
    memory.update({a:0 for a in range(0xD5CE,0xD5CE+33)})
    memory.update({0xD35E:147,0xD4E1:5,0xD5CE:4,0xD5CF:62,0xD5D0:5,0xD5D1:63,0xD5D2:255})
    memory[0xD5AD]=64 if hidden else 0
    points=[(12,10),(9,5),(16,5),(6,8),(14,14)]
    for slot,(x,y) in enumerate(points,1):
        memory[0xC100+slot*16]=1
        memory[0xC102+slot*16]=255  # offscreen不等於hidden。
        memory[0xC204+slot*16]=y+4;memory[0xC205+slot*16]=x+4
    emulator=SimpleNamespace(frame_count=50,memory=memory)
    grid={'walkable':[[1]*20 for _ in range(18)],'verified_location':[147,6,7],'observation_frame':50}
    return emulator,grid,points

def test_only_true_hidden_slot_removed_in_verified_overworld():
    p,g,points=setup();before=deepcopy(p.memory)
    n=read_npc_obstacles(p,g,points,overworld_ready=True)
    assert n['toggle_source_calibrated'] is True
    assert (6,8) not in n['positions'] and (14,14) in n['positions']
    assert n['hidden_source_positions']==[(6,8)] and p.memory==before

@pytest.mark.parametrize('ready',[False,None,1])
def test_no_overworld_proof_preserves_every_obstacle(ready):
    p,g,points=setup();n=read_npc_obstacles(p,g,points,overworld_ready=ready)
    assert n['positions']==points and n['hidden_source_positions']==[]
    assert n['toggle_source_calibrated'] is False

def test_offscreen_active_ball_is_not_removed():
    p,g,points=setup(False);n=read_npc_obstacles(p,g,points,overworld_ready=True)
    assert n['positions']==points and n['hidden_source_positions']==[]
    assert n['toggle_source_calibrated'] is True

@pytest.mark.parametrize('change',[
    lambda p,g:p.memory.update({0xD5CF:63,0xD5D1:62}),
    lambda p,g:p.memory.update({0xD5D2:0}),
    lambda p,g:p.memory.update({0xD4E1:6}),
    lambda p,g:p.memory.update({0xD5AD:True}),
    lambda p,g:g.update(observation_frame=49),
    lambda p,g:g.pop('observation_frame'),
    lambda p,g:g.update(verified_location=[141,6,7]),
    lambda p,g:p.memory.update({0xD35E:148}),
])
def test_unknown_or_uncalibrated_toggle_never_clears_obstacles(change):
    p,g,points=setup();change(p,g)
    n=read_npc_obstacles(p,g,points,overworld_ready=True)
    assert n['positions']==points and n['hidden_source_positions']==[]
    assert n['toggle_source_calibrated'] is False

def test_tower7_hidden_rocket_clears_original_anchor_after_normal_walk_away():
    p,g,_=setup();p.memory.update({0xD35E:148,0xD4E1:4,0xD5AE:1,
        0xD5CE:1,0xD5CF:64,0xD5D0:2,0xD5D1:65,0xD5D2:3,0xD5D3:66,
        0xD5D4:4,0xD5D5:67,0xD5D6:255})
    p.memory[0xC150]=0
    points=[(9,13),(12,9),(9,7),(10,3)]
    for slot,(x,y) in enumerate(points,1):p.memory[0xC204+16*slot]=y+4;p.memory[0xC205+16*slot]=x+4
    g['verified_location']=[148,9,12]
    n=read_npc_obstacles(p,g,[(9,11),(12,9),(9,7),(10,3)],overworld_ready=True)
    assert n['toggle_source_calibrated'] is True and (9,13) not in n['positions']
    assert n['hidden_source_positions']==[(9,11)]

def test_complete_calibration_includes_all_public_source_objects_including_fuji():
    from laya_pokemon.world_map import TOWER_TOGGLE_OBJECTS
    source=json.loads((Path(__file__).parent/'data/toggleable-source-fixture.json').read_text(encoding='utf-8'))
    for mid,(count,objects) in TOWER_TOGGLE_OBJECTS.items():
        expected=source['maps'][str(mid)]
        assert count==expected['source_object_count']
        assert objects==tuple((o['slot'],o['index'],tuple(o['source_position'])) for o in expected['objects'])
