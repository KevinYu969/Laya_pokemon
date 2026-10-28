"""Actual NPC/toggle reader, synthetic fixed-source memory, no game inputs."""
from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest
from laya_pokemon import victory_later_boulders as boulder

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent

def load(name,path):
    spec=importlib.util.spec_from_file_location('laya_pokemon._victory_navigation_'+name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert Path(module.__file__).resolve()==path.resolve();return module

world=importlib.import_module('laya_pokemon.world_map')
assert Path(world.__file__).resolve()==ROOT/'src/laya_pokemon/world_map.py'
nav=importlib.import_module('laya_pokemon.victory_road_navigation')
assert Path(nav.__file__).resolve()==ROOT/'src/laya_pokemon/victory_road_navigation.py'
source=importlib.import_module('test_victory_later_boulders')

class Session:
    def __init__(self,key='3f_hole'):
        self.key=key;self.pb=source.ReadOnlyPyBoy(key);self.pb.frame_count=7233
        c=boulder.CASES[key]
        self.location=dict(map_id=c['map_id'],x=c['start_player'][0],y=c['start_player'][1])
        self.grid=source.grid(key,self.pb.frame_count,tuple(c['start_player']),self.pb.memory.values)
        self.grid['source']=nav.GRID_SOURCE
    def place(self,slot,x,y):
        self.pb.memory.values[0xC200+16*slot+5]=x+4;self.pb.memory.values[0xC200+16*slot+4]=y+4
    def hide(self,index):self.pb.memory.values[0xD5A6+index//8]|=1<<(index%8)
    def read(self,**kw):
        before=deepcopy((self.grid,self.location,dict(self.pb.memory.values)))
        args=dict(world_map_module=world,boulder_module=boulder,overworld_ready=True);args.update(kw)
        out=nav.read_victory_road_npcs(self.pb,self.grid,self.location,**args)
        assert before==(self.grid,self.location,dict(self.pb.memory.values));return out

@pytest.mark.parametrize('key',('2f_switch1','3f_switch1','3f_hole','2f_switch2'))
def test_independent_case_anchors_enable_real_npc_read_without_plan_blocked(key):
    s=Session(key);out=s.read()
    assert out['read_valid'] and out['toggle_source_calibrated']
    assert out['source_anchor_matches']>0 and out['observation_frame']==7233
    assert out['source_commit']==boulder.SOURCE_COMMIT

def test_moved_auxiliary_stone_blocks_only_actual_position_not_its_source_anchor():
    s=Session();s.place(8,13,13)
    assert world.read_npc_obstacles(s.pb,s.grid,[],overworld_ready=True) is None
    out=s.read();assert out['read_valid']
    assert (13,12) in nav.source_anchors(198,boulder_module=boulder)
    assert (13,13) in out['positions'] and (13,12) not in out['positions']
    blocked=nav.blocked_for_move([],out,location=s.location,target={'x':21,'y':15})
    assert (13,13) in blocked and (13,12) not in blocked
    # At the historical second DOWN opportunity, use current NPCs to detour.
    grid=deepcopy(s.grid);grid['tiles']=[[1]*30 for _ in range(18)];grid['walkable']=[[1]*30 for _ in range(18)]
    hint=world.world_direction(grid,{'x':13,'y':12},{'x':13,'y':14},blocked)
    assert hint and hint['direction'] in ('left','right')

def test_visible_stone_at_an_ordinary_move_endpoint_is_not_removed_for_bfs():
    s=Session();s.place(8,13,13);out=s.read()
    assert nav.blocked_for_move([],out,location={'x':13,'y':12},target={'x':13,'y':13}) is None

def test_terminal_clamped_endpoint_cannot_bypass_visible_npc():
    s=Session();s.place(9,29,7);out=s.read()
    assert nav.blocked_for_move([],out,location=s.location,target={'x':30,'y':7}) is None

def test_hidden_hole_stone_releases_current_hole_and_old_source_position():
    s=Session();s.place(10,23,15);s.hide(122);out=s.read()
    assert out['read_valid'] and out['toggle_source_calibrated']
    assert (23,15) not in out['positions'] and (22,15) in out['hidden_source_positions']
    blocked=nav.blocked_for_move([(22,15),(0,0)],out,location=s.location,target={'x':23,'y':15})
    assert (22,15) not in blocked and (23,15) not in blocked and (0,0) in blocked
    grid=deepcopy(s.grid);grid['tiles']=[[1]*30 for _ in range(18)];grid['walkable']=[[1]*30 for _ in range(18)]
    hint=world.world_direction(grid,s.location,{'x':23,'y':15},blocked)
    assert hint['direction']=='right' and hint['path_length']==2

@pytest.mark.parametrize('mid,slot,index',[(198,5,120),(198,6,121),(198,10,122),
    (194,6,91),(194,7,92),(194,8,93),(194,9,94),(194,10,95),(194,13,96)])
def test_every_fixed_toggle_hides_only_its_actual_slot(mid,slot,index):
    s=Session('3f_hole' if mid==198 else '2f_switch1')
    s.place(slot,28,16);s.hide(index);out=s.read()
    assert out['read_valid'] and (28,16) not in out['positions']
    assert tuple((o['slot'],o['index']) for o in out['toggle_snapshot']['objects'])==nav.TOGGLES[mid]

@pytest.mark.parametrize('bad',('not_ready','frame','tileset','map_header','count','bad_byte','bad_position','table','missing_grid'))
def test_known_floor_unknown_never_authorizes_navigation(bad):
    s=Session();kwargs={}
    if bad=='not_ready':kwargs['overworld_ready']=False
    if bad=='frame':s.grid['observation_frame']-=1
    if bad=='tileset':s.grid['tileset_id']=0
    if bad=='map_header':s.pb.memory.values[0xD35E]=194
    if bad=='count':s.pb.memory.values[0xD4E1]=9
    if bad=='bad_byte':s.pb.memory.values[0xC180]=63.0
    if bad=='bad_position':s.pb.memory.values[0xC285]=3
    if bad=='table':s.pb.memory.values[0xD5CE]=6
    if bad=='missing_grid':s.grid=None
    out=s.read(**kwargs)
    assert out['read_valid'] is False and out['review_reason'].startswith('victory_navigation_')
    assert nav.blocked_for_move([],out,location=s.location,target={'x':21,'y':15}) is None

def test_torn_current_sprite_snapshot_is_not_navigation_proof():
    s=Session();count=0
    def hook(address,value):
        nonlocal count
        if address==0xC285:
            count+=1
            if count>=3:return value+1
        return value
    s.pb.memory.hook=hook
    out=s.read();assert out['read_valid'] is False and out['read_error']=='torn_native_snapshot'

def test_reader_must_really_calibrate_toggle_not_fall_back_to_visible_positions(monkeypatch):
    s=Session();original=world.read_npc_obstacles
    def altered(*a,**kw):
        result=original(*a,**kw);result['toggle_source_calibrated']=False;return result
    monkeypatch.setattr(world,'read_npc_obstacles',altered)
    assert s.read()['read_valid'] is False

def test_other_floors_keep_existing_path_and_no_memory_read():
    s=Session();s.location['map_id']=108;s.pb.memory.reads.clear()
    assert s.read() is None and not s.pb.memory.reads
    assert nav.applies(108) is False and nav.applies(198.0) is False

def test_source_coordinates_are_never_merged_into_plan_walls():
    s=Session();s.place(7,3,5);out=s.read()
    blocked=nav.blocked_for_move([(0,0)],out,location=s.location,target={'x':21,'y':15})
    assert (22,3) in out['source_anchors'] and (22,3) not in blocked
    assert (3,5) in blocked and (0,0) in blocked

def test_static_source_profile_conflict_fails_closed():
    s=Session();bad=SimpleNamespace(SOURCE_COMMIT=boulder.SOURCE_COMMIT,CASES=boulder.CASES,TOGGLE_TABLES={})
    assert s.read(boulder_module=bad)['read_valid'] is False
