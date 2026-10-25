"""Four portable source cases against the real pure/getter and installed SDK.

Synthetic memory, text and terrain only; no emulator, ticks, input or source cache.
"""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import importlib.util
import json

import pytest
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as SDK
from laya_pokemon.hm_teaching import TEXT_PROFILE

HERE=Path(__file__).resolve().parent
if HERE.name=="staged-victory-later-boulders-bridge-20261025" and HERE.parent.name==".local":
    SOURCE=HERE.parent.parent/".local/staged-victory-later-boulders-20261025/victory_later_boulders.py";FIXTURE=HERE/"later_cases_fixture.json"
elif HERE.name=="tests":
    SOURCE=HERE.parent/"src/laya_pokemon/victory_later_boulders.py"
    FIXTURE=HERE/"fixtures/victory_later_cases.json"
else:raise RuntimeError("Only exact later-boulder stage or formal tests directories are supported")
SOURCE=SOURCE.resolve(strict=True);FIXTURE=FIXTURE.resolve(strict=True)
spec=importlib.util.spec_from_file_location("laya_pokemon._exact_later_boulder_candidate",SOURCE)
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
assert Path(b.__file__).resolve()==SOURCE
DATA=json.loads(FIXTURE.read_text(encoding="utf-8"))
ORDER=("2f_switch1","3f_switch1","3f_hole","2f_switch2")
DELTAS=dict(up=(0,-1),down=(0,1),left=(-1,0),right=(1,0))
FACING=dict(down=0,up=4,left=8,right=12)
PAIRS={frozenset(p) for p in ((0x20,5),(0x41,5),(0x2A,5),(5,0x21))}


def progress():
    mons=[(19,"LAPRAS",44,140,180,[57,34,58,109],[5,15,8,10]),
          (132,"SNORLAX",42,170,200,[70,133,156,34],[14,20,10,15]),
          (102,"EEVEE",35,89,90,[33,28,98,39],[30,15,30,30]),
          (154,"VENUSAUR",40,120,133,[75,15,73,22],[25,30,10,10]),
          (35,"FEAROW",40,110,125,[64,65,19,31],[35,20,15,20]),
          (7,"NIDOKING",40,124,140,[61,57,30,40],[20,15,25,35])]
    return dict(profile="gen1-wrapper-ram-progress-v1-unvalidated",initialization_candidate=True,
        party_read_valid=True,party_count=6,player_name_raw="KEVIN",money=54321,badges_raw=255,
        inventory=[dict(item=i,quantity=3) for i in range(1,21)],
        party=[dict(species=s,species_name=n,level=lv,hp=hp,max_hp=mh,exp=lv**3,status=0,moves=m,pp=pp)
               for s,n,lv,hp,mh,m,pp in mons])


class Memory:
    def __init__(self,key):
        c=DATA["cases"][key];self.values={a:0 for a in range(0xC000,0xE000)}
        self.reads=[];self.hook=None;m=self.values
        m.update({0xD35E:c["map_id"],0xD361:c["start_player"][1],0xD362:c["start_player"][0],
                  0xD367:17,0xD368:9,0xD369:15,0xD4E1:c["object_count"],0xD728:65,0xD732:1,
                  0xC781:0x37,0xC796:0x25,0xC7C8:0x25,0xD5B2:1})
        for previous in ORDER[:ORDER.index(key)]:
            e=DATA["cases"][previous]["event"];m[e["address"]]|=1<<e["bit"]
        if key!="2f_switch1":m[0xC781]=0x15
        if key in ("3f_hole","2f_switch2"):m[0xC796]=0x1D
        if key=="2f_switch2":m[0xD5B2]=0;m[0xD5B5]=4
        table=[v for pair in DATA["expected_toggle_tables"][str(c["map_id"]) ] for v in pair]+[255]
        for i,v in enumerate(table):m[0xD5CE+i]=v
        pictures=([14,12,7,12,12,9,61,61,61,61,63,63,63]
                  if c["map_id"]==194 else [7,6,7,6,61,61,63,63,63,63])
        directions=([0xD2,0xD2,0xD0,0xD0,0xD2,0xD1,255,255,255,255,16,16,16]
                    if c["map_id"]==194 else [0xD2,0xD3,0xD2,0xD3,255,255,16,16,16,16])
        for o,pic,direction in zip(c["source_all_c2_objects"],pictures,directions):
            slot=o["slot"];p,q=0xC100+16*slot,0xC200+16*slot
            m.update({p:pic,p+1:1,p+2:0,q:0,q+4:o["y"]+4,q+5:o["x"]+4,q+6:255,q+13:0,
                      0xD4E4+2*(slot-1):direction,0xD4E5+2*(slot-1):slot})
        if key=="2f_switch1":m[0xC1D2]=255

    def __getitem__(self,address):
        self.reads.append(address);v=self.values[address]
        return self.hook(address,v) if self.hook else v

    def __setitem__(self,*args):raise AssertionError("No memory writes")


class ReadOnlyPyBoy:
    def __init__(self,key):self.memory=Memory(key);self.frame_count=1
    def tick(self,*args):raise AssertionError("No ticks")
    def button(self,*args):raise AssertionError("No inputs")
    def save_state(self,*args):raise AssertionError("No states")


def terrain(key,m):
    c=DATA["cases"][key];tiles=deepcopy(DATA["base_terrain"][str(c["map_id"])])
    for other in DATA["cases"].values():
        gate=other["gate"]
        if other["map_id"]==c["map_id"] and gate and m[gate["address"]]==gate["after"]:
            for x,y,old,new in gate["cells"]:tiles[y][x]=new
    return tiles


def grid(key,frame,player,m):
    c=DATA["cases"][key];tiles=terrain(key,m)
    return dict(tileset_id=17,observation_frame=frame,verified_location=[c["map_id"],*player],
        screen_cells_verified=12,visible_verified_cells=[[x,player[1]] for x in range(12)],tiles=tiles,
        walkable=[[int(t in DATA["passable_tiles"]) for t in row] for row in tiles])


def review(out):
    assert out["phase"]=="campaign_review" and out["available_actions"]==["wait"],out
    assert out["later_boulder_complete"] is False


class Session:
    def __init__(self,key="2f_switch1"):
        self.key=key;self.case=DATA["cases"][key];self.c=b.VictoryLaterBoulderController(key)
        self.pb=ReadOnlyPyBoy(key);self.p=progress();self.previous=[];self.now=0.
        self.owner="fixed-later-"+key;self.trace=[]

    @property
    def player(self):return self.pb.memory.values[0xD362],self.pb.memory.values[0xD361]
    @property
    def stone(self):
        a=self.case["slot_addresses"];m=self.pb.memory.values
        return m[a["x_raw"]]-4,m[a["y_raw"]]-4

    def place(self,player=None,stone=None,action=None):
        m=self.pb.memory.values;a=self.case["slot_addresses"]
        if player is not None:m[0xD362],m[0xD361]=player
        if stone is not None:m[a["x_raw"]],m[a["y_raw"]]=stone[0]+4,stone[1]+4
        if action is not None:m[0xC109]=FACING[action]

    def call(self,*,same=False,previous=None,raw=0,kind=None,active=None,ready=True,window=False,
             no_grid=False,signal_change=None,grid_change=None,text_change=None,now=None):
        if not same:self.pb.frame_count+=1;self.now+=.05
        if now is not None:self.now=now
        m=self.pb.memory.values;m[0xD057]=raw;f=self.pb.frame_count
        signal=b.read_later_boulder_observation(self.pb,f,SDK,case_key=self.key)
        if signal_change:signal_change(signal)
        g=grid(self.key,f,self.player,m)
        if grid_change:grid_change(g)
        text=dict(profile=TEXT_PROFILE,read_valid=True,alignment_verified=True,read_error=None,
                  cells=[[" "]*20 for _ in range(18)],window_visible=window,observation_frame=f)
        if text_change:text_change(text)
        state=dict(frame=f,location=dict(map_id=m[0xD35E],x=self.player[0],y=self.player[1]),
            progress=deepcopy(self.p),battle_state=dict(raw=raw,
                kind=("wild" if raw==1 else "none") if kind is None else kind,
                active=(raw!=0) if active is None else active,observation_frame=f))
        return self.c.context(state,text=text,grid=None if no_grid else g,signal=signal,
            previous=self.previous if previous is None else previous,now=self.now,
            owner=self.owner,overworld_ready=ready)

    def advance(self,*,phases=True,follow=False):
        p=deepcopy(self.c.pending);assert p
        action=p["action"];self.previous=[action];m=self.pb.memory.values;a=self.case["slot_addresses"]
        if p["kind"]=="walk":
            self.place(player=p["expected_player"],action=action)
            self.trace.append(["walk",action,*self.player,*self.stone]);return self.call()
        expected=self.case["fixed_pushes"][self.c.push_index]
        assert (action,list(p["player"]),list(p["stone"]),list(p["expected_stone"]))==(
            expected["direction"],expected["player_before"],expected["boulder_before"],expected["boulder_after"])
        self.place(action=action);m[0xD718]=self.case["slot"]
        if phases:
            index=self.c.push_index;m[0xCD60]=64
            out=self.call();assert out["available_actions"]==[action,"wait"] and self.c.push_index==index
            self.previous=[action];self.place(stone=p["expected_stone"])
            m.update({0xCD60:66,0xD730:1,0xCD6B:255,a["movement2"]:255,
                      a["movement1"]:0,a["walk_counter"]:16,a["status"]:3})
            out=self.call(no_grid=True);assert out["available_actions"]==["wait"] and self.c.push_index==index
            assert not out["later_boulder_complete"]
        self.place(stone=p["expected_stone"],player=p["stone"] if follow else p["player"])
        m.update({0xCD60:128,0xD730:0,0xCD6B:0,a["movement2"]:16,
                  a["movement1"]:255,a["walk_counter"]:0,a["status"]:2})
        self.previous=["wait"] if phases else [action]
        self.trace.append(["push",action,*self.player,*self.stone]);return self.call()

    def to_index(self,index,**kwargs):
        out=self.call() if self.c.baseline is None else None
        for _ in range(200):
            if self.c.push_index==index:return out
            assert out is None or out["phase"]!="campaign_review",out
            out=self.advance(**kwargs)
        raise AssertionError("Bounded four-case route did not progress")

    def first_push(self):
        self.to_index(0)
        for _ in range(100):
            if self.c.pending["kind"]=="push":return
            out=self.advance();assert out["phase"]!="campaign_review",out
        raise AssertionError("No fixed first push")

    def set_goal_event(self):
        e=self.case["event"];self.pb.memory.values[e["address"]]|=1<<e["bit"]

    def set_physical_goal(self):
        m=self.pb.memory.values;gate=self.case["gate"]
        if gate:m[gate["address"]]=gate["after"]
        else:m[0xD5B5]|=4;m[0xD5B2]&=254;m[self.case["slot_addresses"]["image_index"]]=255

    def finish(self,**kwargs):
        self.to_index(len(self.case["fixed_pushes"]),**kwargs)
        self.set_goal_event();self.set_physical_goal()
        out=self.call();assert not out["later_boulder_complete"] and self.c.closed_frame is not None,out
        assert not self.call(same=True)["later_boulder_complete"]
        out=self.call();assert out["later_boulder_complete"] and out["available_actions"]==["wait"],out
        return out


def test_portable_fixture_and_runtime_are_exactly_four_fixed_cases():
    assert sha256(FIXTURE.read_bytes()).hexdigest() in {"f0e11e5303fdd6365005cf2f4222300b1f782ac2a46af6aa52eb3ebad750e075","163cf7a100deb163043599e48b12097296de795d274bab634e93011f7f40ff31"}
    assert set(b.CASES)==set(DATA["cases"])==set(ORDER)
    assert DATA["source_commit"]==b.SOURCE_COMMIT
    for key in ORDER:
        c=DATA["cases"][key];r=b.CASES[key]
        assert (r["map_id"],r["slot"],r["start_player"],r["start_stone"],r["goal_stone"])==(
            c["map_id"],c["slot"],c["start_player"],c["start_stone"],c["goal_stone"])


@pytest.mark.parametrize("key",ORDER)
def test_full_fixed_case_uses_real_getter_preserves_resources_and_never_invents_follow(key):
    s=Session(key);before=deepcopy(s.p);out=s.finish()
    assert s.trace==s.case["coordinate_trace"]
    assert list(s.player)==s.case["source_no_follow_player_end"] and list(s.stone)==s.case["goal_stone"]
    assert s.p==before and s.c.baseline["party"]==before["party"] and s.c.error is None
    assert out["later_boulder_case"]==key and out["later_boulder_push_index"]==len(s.case["fixed_pushes"])
    assert out["contact_arm_seen"] and out["native_script_seen"] and out["dust_seen"]


@pytest.mark.parametrize("key",ORDER)
def test_one_held_request_may_span_both_native_contacts_without_sampled_phase_claim(key):
    s=Session(key);out=s.finish(phases=False)
    assert s.trace==s.case["coordinate_trace"]
    assert not out["contact_arm_seen"] and not out["native_script_seen"] and not out["dust_seen"]


def test_actual_follow_is_observed_and_hole_completion_does_not_require_falling():
    s=Session("2f_switch2");s.finish(follow=True)
    assert s.stone==(9,16) and s.player==(10,16)
    h=Session("3f_hole");h.finish()
    assert h.pb.memory.values[0xD35E]==198 and h.player==(21,15) and h.stone==(23,15)
    assert h.pb.memory.values[0xD5B5]&4 and not h.pb.memory.values[0xD5B2]&1


@pytest.mark.parametrize("key",ORDER)
def test_getter_double_reads_all_declared_native_bytes_toggle_arrays_and_source_slots(key):
    s=Session(key);o=b.read_later_boulder_observation(s.pb,1,SDK,case_key=key)
    assert o["read_valid"] and o["idle"] and o["stone"]["slot"]==s.case["slot"]
    assert len(s.pb.memory.reads)==2*(len(b._addresses(key))+s.case["object_count"]*9+65)
    assert set(Counter(s.pb.memory.reads).values())=={2}
    assert len(o["objects"])==s.case["object_count"] and len(o["toggle_flags"])==32 and len(o["toggle_table"])==33
    assert all(o["objects"][slot-1]["picture"]==63 and o["objects"][slot-1]["picture2"]==0
               for slot in b.CASES[key]["source_stones"])


@pytest.mark.parametrize("key",ORDER)
@pytest.mark.parametrize("field,value",[("picture",0),("temporary_picture",63),("movement2",15),("text",0)])
def test_getter_rejects_wrong_active_stone_identity(key,field,value):
    s=Session(key);s.pb.memory.values[s.case["slot_addresses"][field]]=value
    assert b.read_later_boulder_observation(s.pb,1,SDK,case_key=key)["read_valid"] is False


@pytest.mark.parametrize("address",[0xD728,0xD700,0xD5A6,0xD5CE])
def test_each_snapshot_is_typed_before_false_equals_zero(address):
    s=Session()
    s.pb.memory.hook=lambda a,v:False if a==address and s.pb.memory.reads.count(a)==2 else v
    assert not b.read_later_boulder_observation(s.pb,1,SDK,case_key=s.key)["read_valid"]


def test_getter_rejects_torn_snapshots_wrong_frame_or_wrong_toggle_source_table():
    s=Session();s.pb.memory.hook=lambda a,v:v^1 if a==0xCD60 and s.pb.memory.reads.count(a)==2 else v
    assert not b.read_later_boulder_observation(s.pb,1,SDK,case_key=s.key)["read_valid"]
    s=Session();assert not b.read_later_boulder_observation(s.pb,2,SDK,case_key=s.key)["read_valid"]
    s.pb.memory.values[0xD5CE]=7
    assert not b.read_later_boulder_observation(s.pb,1,SDK,case_key=s.key)["read_valid"]


def test_hidden_slot_keeps_current_c2_coordinates_and_cannot_be_ignored_for_stone_collision():
    s=Session();o=b.read_later_boulder_observation(s.pb,1,SDK,case_key=s.key)
    hidden=o["objects"][12];assert hidden["hidden"] and (hidden["x"],hidden["y"])==(23,16)
    s.pb.memory.values[0xC1D2]=0  # image appearance does not decide hidden.
    assert b.read_later_boulder_observation(s.pb,1,SDK,case_key=s.key)["objects"][12]["hidden"]
    s.pb.memory.values[0xC2D5]=7;s.pb.memory.values[0xC2D4]=18  # hidden object at first push destination3,14.
    review(s.call());assert s.c.push_index==0


@pytest.mark.parametrize("key",ORDER)
def test_goal_event_alone_cannot_complete_without_native_block_tiles_or_hole_pair(key):
    s=Session(key);s.to_index(len(s.case["fixed_pushes"]));s.set_goal_event()
    assert not s.call()["later_boulder_complete"] and s.c.closed_frame is None


def test_hole_requires_both_hidden_source_stone_and_shown_destination_stone():
    for hidden,shown in [(False,False),(True,False),(False,True)]:
        s=Session("3f_hole");s.to_index(1);s.set_goal_event();m=s.pb.memory.values
        if hidden:m[0xD5B5]|=4
        if shown:m[0xD5B2]&=254
        assert not s.call()["later_boulder_complete"] and s.c.closed_frame is None


@pytest.mark.parametrize("key",ORDER)
def test_closed_pair_is_broken_by_native_busy_or_wild_battle(key):
    s=Session(key);s.to_index(len(s.case["fixed_pushes"]));s.set_goal_event();s.set_physical_goal()
    assert not s.call()["later_boulder_complete"] and s.c.closed_frame is not None
    s.pb.memory.values[0xCFC5]=8
    assert not s.call()["later_boulder_complete"] and s.c.closed_frame is None
    s.pb.memory.values[0xCFC5]=0
    assert not s.call()["later_boulder_complete"]
    assert s.call(raw=1,ready=False,no_grid=True)["later_boulder_battle_handoff"] and s.c.closed_frame is None
    assert not s.call()["later_boulder_complete"]
    assert s.call()["later_boulder_complete"]


@pytest.mark.parametrize("key,address,mask,removed",[
    ("2f_switch1",0xD5B5,4,True),
    ("3f_switch1",0xD5B2,1,False),
    ("2f_switch2",0xD5B5,4,False),
])
def test_nonhole_final_closure_cannot_hide_foreign_floor_toggle_changes(key,address,mask,removed):
    s=Session(key);count=len(s.case["fixed_pushes"]);s.to_index(count)
    s.set_goal_event();s.set_physical_goal()
    assert not s.call()["later_boulder_complete"] and s.c.closed_frame is not None
    if removed:s.pb.memory.values[address]|=mask
    else:s.pb.memory.values[address]&=255^mask
    out=s.call(previous=["wait"]);review(out)
    assert s.c.push_index==count and s.c.pending is None
    reason=s.c.error
    out=s.call(previous=["wait"]);review(out)
    assert s.c.error==reason and s.c.push_index==count and not out["later_boulder_complete"]


@pytest.mark.parametrize("key,address,value",[
    ("2f_switch1",0xC7C8,0x1D),
    ("2f_switch2",0xC781,0x37),
    ("3f_hole",0xC796,0x25),
])
def test_final_transition_preserves_every_gate_other_than_this_cases_own_goal(key,address,value):
    s=Session(key);count=len(s.case["fixed_pushes"]);s.to_index(count)
    s.set_goal_event();s.set_physical_goal()
    assert not s.call()["later_boulder_complete"] and s.c.closed_frame is not None
    s.pb.memory.values[address]=value
    out=s.call(previous=["wait"]);review(out)
    assert s.c.push_index==count and s.c.pending is None
    reason=s.c.error
    out=s.call(previous=["wait"]);review(out)
    assert s.c.error==reason and s.c.push_index==count and not out["later_boulder_complete"]


def test_offer_is_not_execution_sameframe_conflict_cannot_ack_and_error_is_sticky():
    s=Session();s.call();pending=s.c.pending;started=s.c.started
    assert s.call(same=True)["available_actions"]==["wait"] and not pending["executed"]
    review(s.call(same=True,previous=[pending["action"]]));reason=s.c.error
    review(s.call());assert s.c.error==reason and s.c.started==started
    s=Session();s.call();pending=s.c.pending;s.place(player=pending["expected_player"])
    review(s.call(previous=["wait"]));assert not pending["executed"]


@pytest.mark.parametrize("key",ORDER)
def test_owned_wild_rebind_keeps_case_push_index_pending_owner_and_budget(key):
    s=Session(key);index=min(1,len(s.case["fixed_pushes"])-1);s.to_index(index)
    pending=s.c.pending;started=s.c.started;step_started=s.c.step_started;baseline=s.c.baseline
    out=s.call(raw=1,ready=False,window=True,no_grid=True,previous=["wait"])
    assert out["later_boulder_battle_handoff"] and s.c.suspended and s.c.pending is pending
    s.p["party"][0]["hp"]-=4;s.p["party"][0]["exp"]+=100;s.p["party"][0]["pp"][0]-=1
    s.p["inventory"][0]["quantity"]-=1
    assert s.call(ready=False,window=True,no_grid=True,previous=["a"])["later_boulder_battle_handoff"]
    assert s.c.baseline is baseline
    out=s.call(previous=["wait"])
    assert out["phase"]!="campaign_review" and s.c.push_index==index and s.c.battle_returns==1
    assert s.c.started==started and s.c.step_started==step_started and s.c.owner==s.owner
    assert s.c.pending is pending and s.c.baseline["party"]==s.p["party"]


@pytest.mark.parametrize("raw,kind,active",[(2,"wild",True),(2,"trainer",True),(1,"trainer",True),(1,"wild",False),(0,"wild",True)])
def test_only_true_raw1_wild_is_delegated(raw,kind,active):
    s=Session();s.call();review(s.call(raw=raw,kind=kind,active=active,no_grid=True))


def test_same_frame_wild_conflict_cannot_ack_or_reset_suspended_owner():
    s=Session();s.call();p=s.c.pending
    assert s.call(raw=1,previous=["wait"],no_grid=True)["later_boulder_battle_handoff"]
    review(s.call(raw=1,same=True,previous=[p["action"]],no_grid=True))
    assert s.c.pending is p and not p["executed"] and s.c.suspended


def test_battle_or_return_ui_direction_coincidence_cannot_ack_unexecuted_field_offer():
    s=Session();s.call();p=s.c.pending
    assert s.call(raw=1,previous=["wait"],no_grid=True,ready=False)["later_boulder_battle_handoff"]
    assert not p["executed"]
    for kwargs in (dict(raw=1,no_grid=True,ready=False),dict(raw=0,no_grid=True,ready=False,window=True)):
        out=s.call(previous=[p["action"]],**kwargs)
        assert out["later_boulder_battle_handoff"] and s.c.pending is p and not p["executed"]
    out=s.call(previous=[p["action"]])
    assert out["available_actions"]==[p["action"],"wait"] and s.c.pending is p and not p["executed"]


@pytest.mark.parametrize("address,mask,removed",[(0xD5B5,4,True),(0xD5B2,1,False)])
def test_hole_pending_cannot_resend_right_after_one_sided_early_toggle(address,mask,removed):
    s=Session("3f_hole");assert s.call()["available_actions"]==["right","wait"]
    pending=s.c.pending;assert not pending["executed"]
    if removed:s.pb.memory.values[address]|=mask
    else:s.pb.memory.values[address]&=255^mask
    out=s.call(previous=["wait"]);review(out)
    assert s.c.pending is pending and not pending["executed"] and s.c.push_index==0


def test_postwild_displacement_without_first_entry_receipt_is_not_late_battle_ack():
    s=Session();s.call();p=s.c.pending
    s.call(raw=1,previous=["wait"],ready=False,no_grid=True)
    s.place(player=p["expected_player"],action=p["action"])
    assert s.call(raw=1,previous=[p["action"]],ready=False,no_grid=True)["later_boulder_battle_handoff"]
    assert not p["executed"]
    review(s.call(previous=[p["action"]]));assert not p["executed"] and s.c.push_index==0


def test_first_true_wild_entry_receipt_can_ack_field_walk_but_raw2_cannot():
    s=Session();s.call();p=s.c.pending;s.place(player=p["expected_player"],action=p["action"])
    assert s.call(raw=1,previous=[p["action"]],ready=False,no_grid=True)["later_boulder_battle_handoff"]
    assert p["executed"]
    assert s.call(previous=["wait"])["phase"]!="campaign_review" and s.c.push_index==0
    t=Session();t.call();pending=t.c.pending
    review(t.call(raw=2,kind="trainer",active=True,previous=[pending["action"]],no_grid=True))
    assert not pending["executed"]


@pytest.mark.parametrize("picture",[61,0])
def test_negative_hidden_or_unused_picture_slot_still_obstructs_fixed_push_destination(picture):
    s=Session("3f_hole");m=s.pb.memory.values
    # Negative read packet, not a claimed source-reachable item move: native
    # stone collision scans every counted C2 record, even hidden/imageFF/pic0.
    m[0xD5B5]|=1;m[0xC150]=picture;m[0xC152]=255
    m[0xC254]=19;m[0xC255]=27  # slot5 at the fixed stone destination23,15.
    signal=b.read_later_boulder_observation(s.pb,1,SDK,case_key=s.key)
    assert signal["read_valid"] and signal["objects"][4]["hidden"]
    out=s.call();review(out)
    assert out["review_reason"].endswith("source_push_destination_blocked") and s.c.push_index==0


def test_visible_stance_occupant_is_not_removed_as_bfs_goal_obstacle():
    s=Session();m=s.pb.memory.values
    m[0xC214]=18;m[0xC215]=9  # visible slot1 at first fixed stance5,14.
    out=s.call();review(out);assert out["review_reason"].endswith("fixed_stance_occupied")


def test_foreign_native_contact_does_not_count_as_owned_stone_progress():
    s=Session();s.first_push();index=s.c.push_index;p=s.c.pending;s.previous=[p["action"]]
    s.pb.memory.values.update({0xD718:12,0xD730:1,0xCD6B:255})
    review(s.call(no_grid=True));assert s.c.push_index==index and s.c.pending is p


def test_final_player_and_blank_world_are_retained_across_two_closed_frames():
    s=Session();s.to_index(len(s.case["fixed_pushes"]));s.set_goal_event();s.set_physical_goal()
    assert not s.call()["later_boulder_complete"] and s.c.closed_frame is not None
    out=s.call(text_change=lambda t:t["cells"][0].__setitem__(0,"A"))
    assert not out["later_boulder_complete"] and s.c.closed_frame is None
    assert not s.call()["later_boulder_complete"]
    s.place(player=(4,16));review(s.call(previous=["wait"]))


@pytest.mark.parametrize("change",[
    lambda s:s.p.update(money=1),lambda s:s.p["party"][0]["pp"].__setitem__(0,4),
    lambda s:s.p["inventory"].reverse(),lambda s:s.p["party"][0].update(extra="changed"),
    lambda s:s.pb.memory.values.update({0xD728:64}),lambda s:s.pb.memory.values.update({0xD728:1})])
def test_complete_party_inventory_money_pp_strength_and_unrelated_flags_are_conserved(change):
    s=Session();s.call();change(s);review(s.call(previous=["wait"]))


@pytest.mark.parametrize("key",ORDER[1:])
def test_prior_puzzle_chain_cannot_be_skipped(key):
    s=Session(key);s.pb.memory.values[0xD7EE]&=254;review(s.call())


def test_unexecuted_offer_budget_cannot_be_reset_by_repeated_wait_or_owner_change():
    s=Session();s.call();p=s.c.pending;started=s.c.step_started
    for _ in range(b.MAX_REQUESTS-1):
        assert s.call(previous=["wait"])["available_actions"]==[p["action"],"wait"]
        assert s.c.pending is p and not p["executed"] and s.c.step_started==started
    review(s.call(previous=["wait"]));assert s.c.requests==b.MAX_REQUESTS+1
    s=Session();s.call();s.owner="other-owner";review(s.call())


def test_source_clock_and_native_wait_budget_survive_pending_operations():
    s=Session();s.call();p=s.c.pending;started=s.c.started;review(s.call(now=61))
    reason=s.c.error;assert s.c.started==started and s.c.pending is p
    assert s.call(now=0)["review_reason"]==reason
    s=Session();s.call();s.previous=[s.c.pending["action"]];s.pb.memory.values[0xCFC5]=8
    for _ in range(b.MAX_STEP_WAITS):assert s.call(no_grid=True)["phase"]!="campaign_review"
    review(s.call(no_grid=True));assert s.c.waits==b.MAX_STEP_WAITS+1


@pytest.mark.parametrize("key",["unknown","",True,194,{"map_id":194,"slot":11}])
def test_only_whitelisted_case_keys_are_accepted(key):
    with pytest.raises(ValueError):b.VictoryLaterBoulderController(key)


def test_source_signal_native_idle_and_sameframe_grid_evidence_are_recomputed():
    mutations=[dict(signal_change=lambda o:o.update(idle=True,native_push_busy=True)),
        dict(signal_change=lambda o:o["raw"].update(walk_counter=8)),
        dict(signal_change=lambda o:o["objects"][12].update(hidden=False)),
        dict(signal_change=lambda o:o.update(case_key="3f_switch1")),
        dict(grid_change=lambda g:g.update(observation_frame=1)),
        dict(grid_change=lambda g:g.update(tileset_id=17.0)),
        dict(grid_change=lambda g:g["walkable"][9].__setitem__(0,True)),
        dict(text_change=lambda t:t.update(observation_frame=1))]
    for mutation in mutations:review(Session().call(**mutation))


def test_no_readonly_packet_can_issue_inputs_ticks_or_memory_writes():
    s=Session("3f_hole");before=deepcopy(s.p);s.finish();assert s.p==before
    with pytest.raises(AssertionError):s.pb.memory[0xD728]=1
    with pytest.raises(AssertionError):s.pb.tick()
    with pytest.raises(AssertionError):s.pb.button("right")

