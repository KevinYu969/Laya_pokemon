"""Portable public-source case/trace checks. No source-cache or game dependency."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import pytest

HERE=Path(__file__).resolve().parent
if HERE.name=="staged-victory-later-boulders-bridge-20261025" and HERE.parent.name==".local":
    FIXTURE=HERE/"later_cases_fixture.json"
elif HERE.name=="tests":FIXTURE=HERE/"fixtures/victory_later_cases.json"
else:raise RuntimeError("Only exact later-case stage or formal tests directory supported")
SHA256="f0e11e5303fdd6365005cf2f4222300b1f782ac2a46af6aa52eb3ebad750e075"
data=json.loads(FIXTURE.read_text(encoding="utf-8"))
DELTAS=dict(up=(0,-1),down=(0,1),left=(-1,0),right=(1,0))
PAIRS={frozenset(p) for p in ((0x20,5),(0x41,5),(0x2A,5),(5,0x21))}

def terrain(c):
    tiles=deepcopy(data["base_terrain"][str(c["map_id"])])
    for x,y,block in c["patches_at_binding"]:
        gate=next(v["gate"] for v in data["cases"].values() if v["map_id"]==c["map_id"] and v["gate"] and v["gate"]["block_xy"]==[x,y])
        assert block==gate["after"]
        for xx,yy,old,new in gate["cells"]:assert tiles[yy][xx]==old;tiles[yy][xx]=new
    return tiles

def warps(c,p,action,tiles):
    if list(p) not in c["normal_warp_coords"]:return False
    if tiles[p[1]][p[0]] in (0x18,0x1A,0x22):return True
    return ((action=="down" and p[1]==17) or (action=="up" and p[1]==0)
            or (action=="left" and p[0]==0) or (action=="right" and p[0]==29))

def test_public_fixture_integrity_and_four_case_whitelist():
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() in {SHA256,"163cf7a100deb163043599e48b12097296de795d274bab634e93011f7f40ff31"}
    assert data["source_commit"]=="a53671100ec22e5394ff26ec028d0812a238dae2"
    assert set(data["cases"])=={"2f_switch1","3f_switch1","3f_hole","2f_switch2"}
    assert data["caller_ram_addresses_allowed"] is False and data["runtime_controller_implemented"] is False
    assert data["public_source_derived"] and data["not_rom_or_state"]

@pytest.mark.parametrize("key",["2f_switch1","3f_switch1","3f_hole","2f_switch2"])
def test_all_compact_coordinate_traces_replay_true_push_player_rules(key):
    c=data["cases"][key];tiles=terrain(c);p=tuple(c["start_player"]);rock=tuple(c["start_stone"])
    visible={(o["x"],o["y"]) for o in c["source_visible_objects"] if o["slot"]!=c["slot"]}
    all_c2={(o["x"],o["y"]) for o in c["source_all_c2_objects"] if o["slot"]!=c["slot"]}
    pushes=[]
    for kind,action,x,y,rx,ry in c["coordinate_trace"]:
        dx,dy=DELTAS[action];q=(x,y);r=(rx,ry)
        assert 0<=x<30 and 0<=y<18 and 0<=rx<30 and 0<=ry<18
        if kind=="walk":
            assert q==(p[0]+dx,p[1]+dy) and r==rock and q!=rock and q not in visible
            assert tiles[y][x] in data["passable_tiles"] and not warps(c,q,action,tiles)
            assert c["map_id"]!=198 or q!=(23,15)
            assert frozenset((tiles[p[1]][p[0]],tiles[y][x])) not in PAIRS
        else:
            assert kind=="push" and q==p and rock==(p[0]+dx,p[1]+dy) and r==(rock[0]+dx,rock[1]+dy)
            assert r not in all_c2 and tiles[ry][rx] in data["passable_tiles"] and tiles[ry][rx]!=0x15
            assert frozenset((tiles[p[1]][p[0]],tiles[ry][rx])) not in PAIRS and not warps(c,p,action,tiles)
            pushes.append(dict(direction=action,player_before=list(p),boulder_before=list(rock),boulder_after=list(r)))
        p,rock=q,r
    assert pushes==c["fixed_pushes"] and rock==tuple(c["goal_stone"]) and list(p)==c["source_no_follow_player_end"]

@pytest.mark.parametrize("key",["2f_switch1","3f_switch1","3f_hole","2f_switch2"])
def test_getter_contract_addresses_derive_only_from_fixed_slot_source_anchors(key):
    c=data["cases"][key];slot=c["slot"];a,b=0xC100+16*slot,0xC200+16*slot
    assert c["slot_addresses"]==dict(picture=a,status=a+1,image_index=a+2,walk_counter=b,
        y_raw=b+4,x_raw=b+5,movement1=b+6,temporary_picture=b+13,
        movement2=0xD4E4+2*(slot-1),text=0xD4E5+2*(slot-1))
    assert c["event"]["address"]==0xD747+c["event"]["id"]//8 and c["event"]["bit"]==c["event"]["id"]%8
    assert c["object_count"]==(13 if c["map_id"]==194 else 10) and c["tileset"]==17
    assert c["source_picture"]==63 and c["temporary_picture_after_load"]==0
    if c["gate"]:
        g=c["gate"];x,y=g["block_xy"];assert g["address"]==0xC6E8+(y+3)*21+x+3

@pytest.mark.parametrize("index",range(6))
def test_normal_navigation_traces_do_not_contain_unexplained_displacements(index):
    c=data["navigation"][index];p=c["start"]
    assert len(c["coordinate_trace"])==c["walks"]
    for action,x,y,nx,ny in c["coordinate_trace"]:
        assert [x,y]==p;dx,dy=DELTAS[action];assert (nx-x,ny-y)==(dx,dy);p=[nx,ny]
    assert p==c["goal"]

def test_hole_completion_is_toggle_pair_not_fake_gate_or_fall_completion():
    c=data["cases"]["3f_hole"];pair=c["completion_toggle_pair"]
    assert c["gate"] is None and c["goal_stone_tile"]==0x22 and c["source_no_follow_player_end"]==[21,15]
    assert pair["hidden_3f_slot10"]==dict(index=0x7A,address=0xD5B5,bit=2,hidden=True)
    assert pair["visible_2f_slot13"]==dict(index=0x60,address=0xD5B2,bit=0,hidden=False)
    assert data["navigation"][2]["destination"]==[194,22,16]

def test_primary_provenance_and_final_route23_destination_are_fixed():
    assert len(data["primary_sources"])==33
    for r in data["primary_sources"]:
        assert len(r["git_blob_sha1"])==40 and len(r["sha256"])==64
        assert r["url"]=="https://raw.githubusercontent.com/pret/pokered/"+data["source_commit"]+"/"+r["path"]
    assert data["navigation"][-1]["destination"]==[34,14,31]
