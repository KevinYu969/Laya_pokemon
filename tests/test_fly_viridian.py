"""Source candidate tests: exact staged module, pure fake reads; no emulator/ticks/inputs."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import json
import pytest

TEST_DIR = Path(__file__).resolve().parent
if TEST_DIR.name == "staged-fly-portable-fixture-20261025" and TEST_DIR.parent.name == ".local":
    REPO_ROOT = TEST_DIR.parent.parent
    CANDIDATE = REPO_ROOT / "src/laya_pokemon/fly_viridian.py"
    SOURCE_FIXTURE = TEST_DIR / "fly_viridian_source.json"
elif TEST_DIR.name == "tests":
    REPO_ROOT = TEST_DIR.parent
    CANDIDATE = REPO_ROOT / "src/laya_pokemon/fly_viridian.py"
    SOURCE_FIXTURE = TEST_DIR / "fixtures/fly_viridian_source.json"
else:
    raise RuntimeError("Only exact staged or formal test directory is supported")
CANDIDATE = CANDIDATE.resolve(strict=True)
SOURCE_FIXTURE = SOURCE_FIXTURE.resolve(strict=True)
spec = importlib.util.spec_from_file_location("laya_pokemon._staged_fly_viridian", CANDIDATE)
fly = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fly)
assert Path(fly.__file__).resolve() == CANDIDATE
from tests.test_fly_pallet import FakePyBoy, progress as original_progress
from tests.test_hm_teaching import canvas, put, packet, start

CONSTANTS = SimpleNamespace(STATUS_FLAGS3_ADDRESS=0xD72D, EVENT_FLAGS_ADDRESS=0xD747,
    OBTAINED_BADGES_ADDRESS=0xD356, PARTY_COUNT_ADDRESS=0xD163,
    MAPS={"pallet_town":0,"viridian_city":1,"cinnabar_island":8}, BADGES={"thunder":2})


def progress():
    p = original_progress()
    lapras = next(m for m in p["party"] if m["species"] == 19)
    lapras.update(level=39, exp=74088, hp=130, max_hp=160, moves=[57,34,58,109], pp=[7,15,8,10])
    used = {i["item"] for i in p["inventory"]}
    p["inventory"].append(dict(item=next(i for i in range(1,60) if i not in used),quantity=3))
    p["money"] = 123456
    p["badges_raw"] = 127
    return p


def party(p, index=4):
    r=canvas()
    for i,m in enumerate(p["party"]):
        put(r,3,2*i,m["species_name"])
        put(r,13,2*i,f'{m["level"]:3}')
        put(r,13,2*i+1,f'{m["hp"]:3}/{m["max_hp"]:3}')
    put(r,1,14,"Choose a POKéMON.")
    return put(r,0,2*index+1,"▶")


def field(p,y=10):
    index=next(i for i,m in enumerate(p["party"]) if m["species"]==35)
    r=party(p,index)
    r[2*index+1][0]="▷"
    for yy in range(8,18):r[yy][11:20]=[" "]*9
    for yy,label in [(10,"FLY"),(12,"STATS"),(14,"SWITCH"),(16,"CANCEL")]:put(r,13,yy,label)
    return put(r,12,y,"▶")


def grid(loc,frame):
    height,width = (18,20) if loc["map_id"]==8 else (36,40)
    tiles=[[0x2c]*width for _ in range(height)]
    tiles[loc["y"]][loc["x"]]=0x39
    return dict(tileset_id=0,screen_cells_verified=90,observation_frame=frame,
        verified_location=[loc[k] for k in ("map_id","x","y")],tiles=tiles,
        walkable=[[1]*width for _ in range(height)])


class Session:
    def __init__(self):
        self.p=progress(); self.c=fly.FlyViridianController(deepcopy(fly.FLY_VIRIDIAN_INTENT))
        self.pb=FakePyBoy(); self.now=0.; self.previous=[]
        self.pb.memory.values.update({0xD70B:255,0xD70C:7})
    def call(self,rows=None,*,ready=False,window=True,raw=None,same=False,previous=None,
             location=None,signal_change=None,text_change=None,grid_change=None):
        if not same:self.pb.frame_count+=1;self.now+=.05
        loc=deepcopy(location or fly.START)
        self.pb.memory.values.update({0xD35E:loc["map_id"],0xD361:loc["y"],0xD362:loc["x"],0xFF40:0xa1 if window else 0x81})
        self.pb.screen.tilemap_position_list=[[0,0,0,0 if window else 144] for _ in range(144)]
        raw=[0x7f]*360 if raw is None else raw
        self.pb.tilemap_background.ids=[((b^128)-128)+256 for b in raw]
        signal=fly.read_fly_observation(self.pb,self.pb.frame_count,CONSTANTS)
        assert signal["read_valid"] is True
        if signal_change:signal_change(signal)
        text=packet(rows,window)
        if text_change:text_change(text)
        g=grid(loc,self.pb.frame_count)
        if grid_change:grid_change(g)
        return self.c.context(text,self.p,location=loc,
            battle_state=dict(kind="none",active=False,raw=0,observation_frame=self.pb.frame_count),
            grid=g,signal=signal,frame=self.pb.frame_count,
            previous=self.previous if previous is None else previous,now=self.now,overworld_ready=ready)
    def expect(self,rows,action,**kwargs):
        o=self.call(rows,**kwargs);assert o["available_actions"]==[action,"wait"],o
        self.previous=[action];return o
    def to_destination(self):
        self.expect(canvas(),"start",ready=True,window=False)
        self.expect(start(2),"down");self.expect(start(4),"a")
        target=next(i for i,m in enumerate(self.p["party"]) if m["species"]==35)
        for i in range(target+1):self.expect(party(self.p,i),"a" if i==target else "down")
        self.expect(field(self.p,12),"up");self.expect(field(self.p,10),"a")
    def to_viridian(self):
        self.to_destination()
        assert self.call([list(x) for x in fly._INITIAL_MAP_ROWS],raw=list(fly.INITIAL_PALLET_RAW))["available_actions"]==["wait"]
        self.previous=["wait"]
        self.expect([list(x) for x in fly._INITIAL_MAP_ROWS],"up",raw=list(fly.INITIAL_PALLET_RAW))
    def confirm(self):
        self.to_viridian()
        assert self.call([list(x) for x in fly._MAP_ROWS],raw=list(fly.VIRIDIAN_RAW))["available_actions"]==["wait"]
        self.previous=["wait"]
        self.expect([list(x) for x in fly._MAP_ROWS],"a",raw=list(fly.VIRIDIAN_RAW))
    def finish(self):
        self.pb.memory.values.update({0xD71A:1,0xD732:1,0xD733:0,0xCD6B:0})
        first=self.call(ready=True,window=False,location=fly.LANDING)
        assert not first["fly_viridian_complete"]
        assert not self.call(ready=True,window=False,location=fly.LANDING,same=True)["fly_viridian_complete"]
        self.previous=["wait"]
        out=self.call(ready=True,window=False,location=fly.LANDING)
        assert out["fly_viridian_complete"] and out["available_actions"]==["wait"]
        return out


def review(out):
    assert out["phase"]=="campaign_review" and out["available_actions"]==["wait"],out


def test_complete_dynamic_39_injured_20_bag_money_baseline_and_two_fresh_native_landing():
    s=Session();before=deepcopy(s.p);s.confirm();s.finish()
    assert s.p==before and s.c.baseline["party"]==before["party"]
    assert len(s.p["inventory"])==20 and s.p["money"]==123456


def test_fly_user_can_be_leader_or_other_slot_and_move_set_is_preserved():
    s=Session();s.p["party"][0],s.p["party"][4]=s.p["party"][4],s.p["party"][0]
    s.p["party"][0]["moves"][3]=43
    s.p["party"][0]["pp"][3]=30
    before=deepcopy(s.p);s.confirm();s.finish();assert s.p==before


@pytest.mark.parametrize("key,value",[("map_id",True),("map_id",27),("destination_map",0),("player_x",17),("landing_y",25),("species",19),("move",57),("kind","fly_pallet")])
def test_exact_intent_rejects_changed_fields_or_boolean(key,value):
    intent=deepcopy(fly.FLY_VIRIDIAN_INTENT);intent[key]=value
    with pytest.raises(ValueError):fly.FlyViridianController(intent)


@pytest.mark.parametrize("key",["viridian_city","cinnabar_island","pallet_town"])
def test_sdk_map_anchor_required(key):
    c=deepcopy(CONSTANTS);c.MAPS[key]=True
    signal=fly.read_fly_observation(FakePyBoy(),1,c)
    assert signal["read_valid"] is False and signal["location"] is None


def test_reader_exact_source_bytes_twice_without_write_or_tick():
    pb=FakePyBoy();pb.tilemap_background.ids=[((b^128)-128)+256 for b in fly.VIRIDIAN_RAW]
    signal=fly.read_fly_observation(pb,1,CONSTANTS)
    assert signal["raw_bytes"]==list(fly.VIRIDIAN_RAW)
    assert pb.tilemap_background.reads==720 and pb.memory.reads.count(0xD70B)==2


@pytest.mark.parametrize("bit_value",[0,1,2])
def test_both_pallet_and_viridian_visited_bits_required(bit_value):
    s=Session();s.pb.memory.values[0xD70B]=bit_value
    review(s.call(ready=True,window=False));assert s.c.baseline is None


@pytest.mark.parametrize("field,value",[("read_valid",False),("signed_tile_data",None),("raw_bytes",None),("raw_identifiers",[127]*360),("read_error","fake"),("screen_read_valid",1)])
def test_profile_alone_cannot_replace_complete_native_pixel_domain(field,value):
    s=Session();review(s.call(ready=True,window=False,signal_change=lambda q:q.update({field:value})))
    assert s.c.baseline is None


@pytest.mark.parametrize("change",[
    lambda p:p.update(money=True),lambda p:p.update(money=1000000),
    lambda p:p.update(party_count=5),lambda p:p.update(badges_raw=0),
    lambda p:p["party"][0].update(status=8),lambda p:p["party"][0].update(hp=0),
    lambda p:p["party"][4]["moves"].__setitem__(2,64),
    lambda p:p["party"][0]["moves"].__setitem__(0,19),
    lambda p:p["party"][0]["pp"].__setitem__(0,255),
])
def test_invalid_baseline_rejects_before_first_action(change):
    s=Session();change(s.p);review(s.call(ready=True,window=False));assert s.c.pending is None


@pytest.mark.parametrize("change",[
    lambda p:p.update(money=p["money"]+1),lambda p:p.update(badges_raw=255),
    lambda p:p["party"][0].update(hp=129),lambda p:p["party"][0].update(exp=74089),
    lambda p:p["party"][0]["pp"].__setitem__(0,6),
    lambda p:p["inventory"][0].update(quantity=5),lambda p:p["inventory"].reverse(),
    lambda p:p["party"][0].update(extra_unknown="changed"),
])
def test_complete_party_bag_order_money_and_badges_fingerprint_is_constant(change):
    s=Session();s.expect(canvas(),"start",ready=True,window=False);change(s.p)
    review(s.call(start(2)));assert s.c.error


def test_initial_viridian_page_without_native_up_is_rejected():
    s=Session();s.to_destination();review(s.call([list(x) for x in fly._MAP_ROWS],raw=list(fly.VIRIDIAN_RAW)))
    assert not s.c.destination_confirmed


def test_true_previous_up_must_arrive_before_viridian_page():
    s=Session();s.to_viridian()
    review(s.call([list(x) for x in fly._MAP_ROWS],raw=list(fly.VIRIDIAN_RAW),previous=["wait"]))
    assert not s.c.destination_confirmed


def test_pallet_two_fresh_frames_produce_up_never_a_and_wrong_raw_map_is_rejected():
    s=Session();s.to_destination();rows=[list(x) for x in fly._INITIAL_MAP_ROWS]
    assert s.call(rows,raw=list(fly.INITIAL_PALLET_RAW))["available_actions"]==["wait"]
    out=s.call(rows,raw=list(fly.INITIAL_PALLET_RAW),same=True)
    assert out["available_actions"]==["wait"]
    s.previous=["wait"];s.expect(rows,"up",raw=list(fly.INITIAL_PALLET_RAW))
    wrong=list(fly.VIRIDIAN_RAW);wrong[100]^=1
    review(s.call([list(x) for x in fly._MAP_ROWS],raw=wrong))


def test_landing_location_or_map_alone_never_completes():
    s=Session();s.to_destination();review(s.call(ready=True,window=False,location=fly.LANDING))
    assert s.c.stage!="complete"


@pytest.mark.parametrize("change",[
    lambda g:g["tiles"][26].__setitem__(23,0x23),
    lambda g:g.update(verified_location=[1,23,True]),
    lambda g:g.update(observation_frame=g["observation_frame"]-1),
    lambda g:g["walkable"][26].__setitem__(23,True),
    lambda g:g["tiles"].pop(),
])
def test_landing_tile_grid_and_frame_must_be_exact_two_fresh_closed_world(change):
    s=Session();s.confirm();s.pb.memory.values[0xD71A]=1
    out=s.call(ready=True,window=False,location=fly.LANDING,grid_change=change)
    assert not out["fly_viridian_complete"] and s.c.closed_frame is None


def test_same_frame_conflict_sticky_error_and_budget_not_reset():
    s=Session();s.expect(canvas(),"start",ready=True,window=False)
    review(s.call(start(2),same=True));error=s.c.error
    review(s.call(ready=True,window=False));assert s.c.error==error
    t=Session();t.expect(canvas(),"start",ready=True,window=False);t.now=61
    review(t.call(start(2)));assert t.c.started==.05


def test_controller_never_mutates_inputs_or_performs_input_io():
    s=Session();p=deepcopy(s.p);s.confirm();s.finish();assert s.p==p
    with pytest.raises(AssertionError):s.pb.tick()
    with pytest.raises(AssertionError):s.pb.memory[0xD71A]=1


def test_reader_boolean_visited_byte_stays_unknown():
    pb=FakePyBoy();pb.memory.values[0xD70B]=False
    signal=fly.read_fly_observation(pb,1,CONSTANTS)
    assert signal["read_valid"] is False and signal["visited"] is None


def test_primary_rle_blob_and_full_destination_map_raw_proof():
    from hashlib import sha1, sha256
    fixture=json.loads(SOURCE_FIXTURE.read_text(encoding="utf-8"))
    assert fixture["schema"]=="fly-viridian-primary-fragments-v1"
    assert fixture["source_repo"]=="pret/pokered" and fixture["source_commit"]==fly.SOURCE_COMMIT
    town=fixture["town_map"];source=town["source"];raw=bytes.fromhex(town["rle_hex"])
    assert len(raw)==source["bytes"]==171
    assert source["path"]=="gfx/town_map/town_map.rle"
    assert source["url"]==f"https://github.com/pret/pokered/blob/{fly.SOURCE_COMMIT}/"+source["path"]
    assert sha1(("blob "+str(len(raw))+"\0").encode()+raw).hexdigest()==source["git_blob_sha1"]=="f9ede0ec78bf5e198a7fed8b1d1394e9837abaa8"
    assert sha256(raw).hexdigest()==source["sha256"]=="d034ce912040a8ab68be68833e21b433bac6dfb35d7da8d0e672cce3d58d62d1"
    assert raw==fly._RLE
    expanded=[]
    for b in raw:
        if not b:break
        expanded.extend([0x60+(b>>4)]*(b&15))
    assert expanded==fly._BASE_MAP and len(expanded)==360
    name=fixture["destination_name"]
    assert name["label"]=="VIRIDIAN CITY@" and name["line"]==2
    assert name["line_text"]=='ViridianCityName:    db "VIRIDIAN CITY@"'
    assert sha256(name["line_text"].encode("utf-8")).hexdigest()==name["line_utf8_sha256"]
    assert name["source"]["path"]=="data/maps/names.asm"
    assert name["source"]["sha256"]=="6aee8a1dfa1f627e24340df5b6a2645896c625a896ae81be7c5b2a079094b217"
    assert name["source"]["git_blob_sha1"]=="805c57c909801d1b1cc20762b18448769451b9c1"
    assert name["source"]["url"]==f"https://github.com/pret/pokered/blob/{fly.SOURCE_COMMIT}/data/maps/names.asm"
    assert len(fly._MAP_ROWS)==18 and all(len(r)==20 for r in fly._MAP_ROWS)
    assert fly._MAP_ROWS[0]=="TO VIRIDIAN CITY  ▶▼"
    assert list(fly.VIRIDIAN_RAW)[20:]==expanded[20:]


def test_primary_source_start_and_landing_lower_left_tile_are_39():
    from hashlib import sha256
    fixture=json.loads(SOURCE_FIXTURE.read_text(encoding="utf-8"))
    assert fixture["source_commit"]==fly.SOURCE_COMMIT
    points=fixture["tile_points"]
    assert [(p["name"],p["map_id"],p["point"],p["width_blocks"]) for p in points]==[
        ("CinnabarIsland",8,[18,4],10),("ViridianCity",1,[23,26],20)]
    assert [p["block_index"] for p in points]==[29,271]
    assert [p["block_value"] for p in points]==[0x7b,0x1a]
    for p in points:
        x,y=p["point"];fragment=bytes.fromhex(p["fragment_hex"])
        assert p["block_index"]==(y//2)*p["width_blocks"]+x//2
        assert p["fragment_offset"]==p["block_value"]*16
        assert len(fragment)==16 and sha256(fragment).hexdigest()==p["fragment_sha256"]
        assert p["map_source"]["path"]=="maps/"+p["name"]+".blk"
        assert p["blockset_source"]["path"]=="gfx/blocksets/overworld.bst"
        assert p["blockset_source"]["sha256"]=="c4f6d88cc7dea8196aa51d3aa059c6d1da0ea45718dd12870fcddee9f9304d50"
        assert p["blockset_source"]["git_blob_sha1"]=="18ceef979e6e410f849a4880a453dccb792182a0"
        assert p["lower_left_offset"]==(y%2*2+1)*4+x%2*2
        assert fragment[p["lower_left_offset"]]==p["expected_tile"]==0x39
