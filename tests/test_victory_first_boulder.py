"""Portable real pure/getter tests; small public-source JSON, no research cache."""
from copy import deepcopy
from pathlib import Path
import importlib.util
import json
from hashlib import sha256
import pytest
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as CONSTANTS
from laya_pokemon.hm_teaching import TEXT_PROFILE

HERE=Path(__file__).resolve().parent
if HERE.name=="staged-victory-first-boulder-postreview-20261025" and HERE.parent.name==".local":
    ROOT=HERE.parent.parent;SOURCE=ROOT/".local/staged-victory-first-boulder-postreview-20261025/victory_first_boulder.py"
    FIXTURE=HERE/"victory_first_boulder_fixture.json"
elif HERE.name=="tests":
    ROOT=HERE.parent;SOURCE=ROOT/"src/laya_pokemon/victory_first_boulder.py"
    FIXTURE=HERE/"fixtures/victory_first_boulder.json"
else:raise RuntimeError("Only exact stage or formal first-boulder tests are supported")

def load(name,path):
    path=path.resolve(strict=True);spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert Path(module.__file__).resolve()==path
    return module

b=load("laya_pokemon._exact_first_boulder_candidate",SOURCE)
FIXTURE_SHA256="a33c7315a7601875576bb8ef87d98ed5c73ec0738c1bd22b8c1b39e0f9f26b88"
assert sha256(FIXTURE.read_bytes()).hexdigest() in {FIXTURE_SHA256,"a1f7a92700c1a944d599ddf9b641388716f17ceba80a1618c022ebc2b8d8b18a"}
assert sha256(SOURCE.read_bytes()).hexdigest() in {"78870aa893c3461b320b7c5abf19d20ff31768202a8599f872591fa85e1a718f","61c8290018078352ed1cd91d8b892e786c97dc75f25ce82e722efe74def12da9"}
data=json.loads(FIXTURE.read_text(encoding="utf-8"))

class PublicSourceTerrain:
    TILES=tuple(tuple(row) for row in data["tiles"])
    PASSABLE=frozenset(data["passable_tiles"])
    @staticmethod
    def arrival_warps(point,direction):
        if list(point) not in data["warp_coords"]:return False
        if data["tiles"][point[1]][point[0]] in data["immediate_warp_tiles"]:return True
        return ((direction=="down" and point[1]==17) or (direction=="up" and point[1]==0)
                or (direction=="left" and point[0]==0) or (direction=="right" and point[0]==19))

route=PublicSourceTerrain()

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
    def __init__(self):
        self.values={a:0 for a in b.ADDRESSES.values()};self.reads=[];self.hook=None
        self.values.update({0xD35E:108,0xD361:16,0xD362:8,0xD367:17,0xD368:9,0xD369:10,
                            0xD4E1:7,0xD728:65,0xD732:1,0xC77F:0x25})
        for slot,(x,y) in enumerate(b.STATIC_POSITIONS,1):
            p,q=0xC100+16*slot,0xC200+16*slot;pic=63 if slot>=5 else 1
            self.values.update({p:pic,p+1:1,q:0,q+4:y+4,q+5:x+4,q+6:255,q+13:0,
                                0xD4E4+2*(slot-1):16 if slot>=5 else 255,0xD4E5+2*(slot-1):slot})
    def __getitem__(self,address):
        self.reads.append(address);v=self.values[address]
        return self.hook(address,v) if self.hook else v
    def __setitem__(self,*args):raise AssertionError("No memory writes")

class ReadOnlyPyBoy:
    def __init__(self):self.memory=Memory();self.frame_count=1
    def tick(self,*args):raise AssertionError("No ticks")
    def save_state(self,*args):raise AssertionError("No state saves")

def grid(frame,player,opened=False):
    tiles=[list(row) for row in route.TILES]
    if opened:tiles[12][9]=5
    visible=[[x,16] for x in range(12)]
    return dict(tileset_id=17,observation_frame=frame,verified_location=[108,*player],
        screen_cells_verified=12,visible_verified_cells=visible,tiles=tiles,
        walkable=[[int(t in route.PASSABLE) for t in row] for row in tiles])

def review(out):
    assert out["phase"]=="campaign_review" and out["available_actions"]==["wait"],out

class Session:
    def __init__(self):
        self.c=b.VictoryFirstBoulderController();self.pb=ReadOnlyPyBoy();self.p=progress()
        self.previous=[];self.now=0.;self.trace=[];self.owner="fixed-vr1-slot5"
    @property
    def player(self):return self.pb.memory.values[0xD362],self.pb.memory.values[0xD361]
    @property
    def stone(self):return self.pb.memory.values[0xC255]-4,self.pb.memory.values[0xC254]-4
    def place(self,player=None,stone=None,action=None):
        m=self.pb.memory.values
        if player is not None:
            m[0xD362],m[0xD361]=player
            m[0xD736]=4 if player in ((8,17),(9,17)) else 0
        if stone is not None:m[0xC255],m[0xC254]=stone[0]+4,stone[1]+4
        if action is not None:m[0xC109]=b.FACING[action]
    def call(self,*,same=False,previous=None,raw=0,kind=None,active=None,ready=True,
             window=False,no_grid=False,signal_change=None,grid_change=None,text_change=None,now=None):
        if not same:self.pb.frame_count+=1;self.now+=.05
        if now is not None:self.now=now
        f=self.pb.frame_count
        signal=b.read_first_boulder_observation(self.pb,f,CONSTANTS)
        if signal_change:signal_change(signal)
        g=grid(f,self.player,self.pb.memory.values[0xC77F]==0x1D)
        if grid_change:grid_change(g)
        text=dict(profile=TEXT_PROFILE,read_valid=True,alignment_verified=True,read_error=None,
                  cells=[[" "]*20 for _ in range(18)],window_visible=window,observation_frame=f)
        if text_change:text_change(text)
        state=dict(frame=f,location=dict(map_id=108,x=self.player[0],y=self.player[1]),progress=deepcopy(self.p),
            battle_state=dict(raw=raw,kind=("wild" if raw==1 else "none") if kind is None else kind,
                              active=(raw!=0) if active is None else active,observation_frame=f))
        return self.c.context(state,text=text,grid=None if no_grid else g,signal=signal,
            previous=self.previous if previous is None else previous,now=self.now,owner=self.owner,overworld_ready=ready)
    def advance(self,*,follow=False,sample_phases=True):
        p=deepcopy(self.c.pending);assert p
        action=p["action"];self.previous=[action]
        if p["kind"]=="walk":
            assert (p["player"],p["expected_player"]) not in b.BAD_EDGES
            assert not route.arrival_warps(p["expected_player"],action)
            self.place(player=p["expected_player"],action=action)
            self.trace.append(("walk",action,self.player,self.stone));return self.call()
        self.place(action=action);m=self.pb.memory.values;m[0xD718]=5
        if sample_phases:
            m[0xCD60]=64
            out=self.call();assert out["available_actions"]==[action,"wait"],out
            # This second real native contact starts MoveSprite, not player follow.
            self.previous=[action];self.place(stone=p["expected_stone"])
            m.update({0xCD60:66,0xD730:1,0xCD6B:255,0xD4EC:255,0xC256:0,0xC250:16,0xC151:3})
            out=self.call(no_grid=True);assert out["available_actions"]==["wait"],out
            assert not out["first_boulder_complete"] and self.c.push_index<len(b.PUSHES)
        self.place(stone=p["expected_stone"],player=p["stone"] if follow else p["player"])
        m.update({0xCD60:128,0xD730:0,0xCD6B:0,0xD4EC:16,0xC256:255,0xC250:0,0xC151:2})
        self.previous=["wait"] if sample_phases else [action]
        self.trace.append(("push",action,self.player,self.stone));return self.call()
    def to_index(self,index,**kwargs):
        out=self.call() if self.c.baseline is None else None
        for _ in range(140):
            if self.c.push_index==index:return out
            out=self.advance(**kwargs);assert out["phase"]!="campaign_review",out
        raise AssertionError("bounded fixed route did not progress")
    def finish(self,**kwargs):
        self.to_index(18,**kwargs);m=self.pb.memory.values
        m[0xD869]=128
        out=self.call();assert not out["first_boulder_complete"] and self.c.closed_frame is None
        m[0xC77F]=0x1D
        out=self.call();assert not out["first_boulder_complete"] and self.c.closed_frame is not None
        assert not self.call(same=True)["first_boulder_complete"]
        out=self.call();assert out["first_boulder_complete"] and out["available_actions"]==["wait"],out
        return out

def test_full_fixed_route_uses_real_getter_and_keeps_player_independent():
    s=Session();before=deepcopy(s.p);out=s.finish()
    assert (len(s.trace),sum(x[0]=="walk" for x in s.trace),sum(x[0]=="push" for x in s.trace))==(56,38,18)
    assert s.player==(17,11) and s.stone==(17,13) and s.p==before
    assert out["contact_arm_seen"] and out["native_script_seen"] and out["dust_seen"]
    assert s.c.calls<2400 and s.c.error is None

def test_single_held_request_can_span_both_native_contacts_without_fake_phase_claim():
    s=Session();out=s.finish(sample_phases=False)
    assert not out["contact_arm_seen"] and not out["native_script_seen"] and not out["dust_seen"]
    assert len(s.trace)==56

def test_actual_player_follow_is_observed_not_required_or_invented():
    s=Session();s.finish(follow=True)
    assert s.stone==(17,13) and s.player==(17,12)
    assert sum(x[0]=="push" for x in s.trace)==18

def test_two_contacts_dust_and_type_ff_do_not_advance_before_true_idle():
    s=Session();s.to_index(0)
    while s.c.pending["kind"]!="push":s.advance()
    p=deepcopy(s.c.pending);m=s.pb.memory.values;s.previous=[p["action"]]
    s.place(action=p["action"]);m[0xD718]=5;m[0xCD60]=64
    out=s.call();assert s.c.push_index==0 and out["available_actions"]==[p["action"],"wait"]
    s.place(stone=p["expected_stone"]);m.update({0xD730:1,0xD4EC:255,0xCD60:66,0xC250:16})
    out=s.call(no_grid=True);assert s.c.push_index==0 and out["available_actions"]==["wait"]
    m.update({0xD730:0,0xC250:0})
    out=s.call(no_grid=True);assert s.c.push_index==0 and out["available_actions"]==["wait"]

def test_entrance_pad_path_uses_side_entry_then_up_never_down_warp():
    s=Session();s.to_index(6)
    walks=[(a,p) for k,a,p,_ in s.trace if k=="walk"]
    assert ("down",(7,17)) in walks and ("right",(8,17)) in walks and ("right",(9,17)) in walks
    assert not any(p in ((8,17),(9,17)) and a=="down" for a,p in walks)

def test_readonly_getter_reads_every_declared_byte_twice_and_returns_true_slot():
    s=Session();o=b.read_first_boulder_observation(s.pb,1,CONSTANTS)
    assert o["read_valid"] and o["idle"] and o["stone"]["slot"]==5 and o["stone"]["movement_byte2"]==16
    assert len(s.pb.memory.reads)==2*(len(b.ADDRESSES)+7*9)
    assert all(s.pb.memory.reads.count(a)==2 for a in b.ADDRESSES.values())

@pytest.mark.parametrize("address,value",[(0xD35E,1),(0xD367,0),(0xD4E1,6),(0xC150,1),
    (0xC25D,1),(0xD4EC,15),(0xD4ED,6),(0xC160,1),(0xD4F1,1),(0xD728,True)])
def test_getter_rejects_unanchored_map_or_slot_or_nonbyte(address,value):
    s=Session();s.pb.memory.values[address]=value
    assert b.read_first_boulder_observation(s.pb,1,CONSTANTS)["read_valid"] is False

def test_getter_validates_both_snapshots_before_false_equals_zero():
    s=Session();address=0xD700
    def hook(a,v):return False if a==address and s.pb.memory.reads.count(a)==2 else v
    s.pb.memory.hook=hook
    assert b.read_first_boulder_observation(s.pb,1,CONSTANTS)["read_error"]=="byte_or_slot_identity_invalid"

def test_getter_detects_torn_bytes_frame_or_invalid_sdk():
    s=Session();address=0xCD60
    s.pb.memory.hook=lambda a,v:v+1 if a==address and s.pb.memory.reads.count(a)==2 else v
    assert b.read_first_boulder_observation(s.pb,1,CONSTANTS)["read_error"]=="torn_frame_or_snapshot"
    assert b.read_first_boulder_observation(s.pb,2,CONSTANTS)["read_error"]=="frame_not_current"
    assert b.read_first_boulder_observation(s.pb,1,{})["read_error"]=="sdk_source_anchors_unverified"

def test_offer_does_not_execute_and_coordinate_change_without_actual_previous_fails():
    s=Session();s.call();p=deepcopy(s.c.pending)
    out=s.call(previous=["wait"]);assert out["available_actions"]==[p["action"],"wait"] and not s.c.pending["executed"]
    s.place(player=p["expected_player"],action=p["action"])
    review(s.call(previous=["wait"]))

def test_unexecuted_pending_does_not_reoffer_during_native_busy():
    s=Session();s.call();s.pb.memory.values[0xCFC5]=8
    out=s.call(previous=["wait"])
    assert out["available_actions"]==["wait"] and not s.c.pending["executed"]

def test_true_walk_busy_without_grid_waits_then_needs_verified_grid():
    s=Session();s.call();p=deepcopy(s.c.pending);s.previous=[p["action"]]
    s.place(player=p["expected_player"],action=p["action"]);s.pb.memory.values[0xCFC5]=8
    out=s.call(no_grid=True);assert out["available_actions"]==["wait"] and s.c.pending["executed"]
    s.pb.memory.values[0xCFC5]=0
    review(s.call(no_grid=True))

def test_same_frame_duplicate_never_resends_and_conflict_cannot_ack():
    s=Session();s.call();pending=s.c.pending
    out=s.call(same=True);assert out["available_actions"]==["wait"] and not pending["executed"]
    review(s.call(same=True,previous=[pending["action"]]))
    assert not pending["executed"]

def test_same_frame_wild_conflict_cannot_ack_or_rebind():
    s=Session();s.call();p=s.c.pending
    out=s.call(raw=1,previous=["wait"]);assert out["first_boulder_battle_handoff"]
    review(s.call(same=True,raw=1,previous=[p["action"]]))
    assert not p["executed"] and s.c.suspended

def test_owned_wild_return_rebases_bounded_attrition_without_resetting_push_sequence():
    s=Session();s.to_index(3);p=deepcopy(s.c.pending);baseline=s.c.baseline
    out=s.call(raw=1,previous=["wait"],no_grid=True,window=True,ready=False)
    assert out["first_boulder_battle_handoff"] and s.c.push_index==3 and s.c.suspended
    s.p["party"][0]["hp"]-=4;s.p["party"][0]["exp"]+=100;s.p["party"][0]["pp"][0]-=1
    s.p["inventory"][0]["quantity"]-=1
    out=s.call(window=True,ready=False,no_grid=True,previous=["a"])
    assert out["first_boulder_battle_handoff"] and s.c.baseline is baseline
    out=s.call(previous=["wait"])
    assert out["phase"]!="campaign_review" and s.c.push_index==3 and s.c.battle_returns==1
    assert s.stone==b.PUSHES[3][2] and s.c.pending["player"]==p["player"]
    assert s.c.baseline["party"][0]["hp"]==s.p["party"][0]["hp"]

@pytest.mark.parametrize("change",[lambda p:p.update(money=p["money"]+1),
    lambda p:p["inventory"].append(dict(item=99,quantity=1)),
    lambda p:p["party"][0]["pp"].__setitem__(0,6),
    lambda p:p["party"].reverse(),lambda p:p["party"][0].update(exp=0),
    lambda p:p["party"][0].update(status=8),lambda p:p["party"][0].update(hp=0)])
def test_wild_return_unreceipted_gains_reorder_or_unfit_party_require_review(change):
    s=Session();s.call();s.call(raw=1,no_grid=True,ready=False);change(s.p)
    review(s.call());assert s.c.suspended and s.c.push_index==0

@pytest.mark.parametrize("raw,kind,active",[(2,"wild",True),(2,"trainer",True),(1,"trainer",True),
    (1,"wild",False),(0,"wild",True)])
def test_only_true_raw1_wild_is_delegated(raw,kind,active):
    s=Session();s.call();review(s.call(raw=raw,kind=kind,active=active,no_grid=True))

@pytest.mark.parametrize("change",[lambda s:s.p.update(money=1),
    lambda s:s.p["party"][0]["pp"].__setitem__(0,4),
    lambda s:s.pb.memory.values.update({0xD728:64}),
    lambda s:s.pb.memory.values.update({0xD728:1}),
    lambda s:s.place(stone=(6,15))])
def test_resources_strength_unrelated_flags_and_stone_are_conserved(change):
    s=Session();s.call();change(s);review(s.call(previous=["wait"]))

@pytest.mark.parametrize("key,value",[("map_id",1),("slot",6),("slot",True),
    ("start_player",[9,16]),("goal_boulder",[17,12]),("event_id",0x918)])
def test_only_fixed_source_intent(key,value):
    intent=deepcopy(b.INTENT);intent[key]=value
    with pytest.raises(ValueError):b.VictoryFirstBoulderController(intent)

def test_source_signal_and_grid_require_genuine_sameframe_full_evidence():
    mutations=[dict(signal_change=lambda o:o.update(observation_frame=False)),
        dict(signal_change=lambda o:o["raw"].update(flags1=True)),
        dict(signal_change=lambda o:o["objects"][4].update(slot=True)),
        dict(grid_change=lambda g:g.update(observation_frame=1)),
        dict(grid_change=lambda g:g.update(tileset_id=17.0)),
        dict(grid_change=lambda g:g.update(screen_cells_verified=11)),
        dict(grid_change=lambda g:g["walkable"][16].__setitem__(8,True)),
        dict(text_change=lambda t:t.update(observation_frame=1))]
    for mutation in mutations:review(Session().call(**mutation))

def test_wrong_boulder_native_index_is_not_slot5_progress():
    s=Session();s.call()
    while s.c.pending["kind"]!="push":s.advance()
    p=s.c.pending;s.previous=[p["action"]];s.pb.memory.values.update({0xD718:6,0xD730:1})
    review(s.call(no_grid=True));assert s.c.push_index==0

def test_event_block_tile_and_two_fresh_idle_frames_are_all_required():
    s=Session();s.to_index(18);m=s.pb.memory.values
    m[0xD869]=128
    assert not s.call()["first_boulder_complete"] and s.c.closed_frame is None
    m[0xC77F]=0x1D
    out=s.call(grid_change=lambda g:g["tiles"][12].__setitem__(9,0x24))
    assert not out["first_boulder_complete"] and s.c.closed_frame is None
    assert not s.call()["first_boulder_complete"]
    closed=s.c.closed_frame;m[0xCFC5]=8
    assert not s.call()["first_boulder_complete"] and s.c.closed_frame is None
    m[0xCFC5]=0
    assert not s.call()["first_boulder_complete"] and s.c.closed_frame>closed
    assert s.call()["first_boulder_complete"]

def test_battle_breaks_closed_completion_pair():
    s=Session();s.to_index(18);s.pb.memory.values.update({0xD869:128,0xC77F:0x1D})
    assert not s.call()["first_boulder_complete"] and s.c.closed_frame is not None
    assert s.call(raw=1,no_grid=True)["first_boulder_battle_handoff"] and s.c.closed_frame is None
    assert not s.call()["first_boulder_complete"]
    assert s.call()["first_boulder_complete"]

def test_budget_error_is_sticky_and_owner_clock_do_not_reset():
    s=Session();s.call();started=s.c.started;pending=s.c.pending
    out=s.call(now=61);review(out);reason=out["review_reason"]
    assert s.c.started==started and s.c.pending is pending
    assert s.call(now=0)["review_reason"]==reason
    s=Session();s.call();s.owner="different-owner";review(s.call())

def test_per_step_wait_budget_is_retained_on_native_busy():
    s=Session();s.call();s.previous=[s.c.pending["action"]];s.pb.memory.values[0xCFC5]=8
    for _ in range(b.MAX_STEP_WAITS):assert s.call(no_grid=True)["phase"]!="campaign_review"
    review(s.call(no_grid=True));assert s.c.waits==31

def test_invalid_initial_state_is_not_recovered_or_claimed_complete():
    for change in (lambda s:s.place(player=(9,16)),lambda s:s.place(stone=(17,13)),
                   lambda s:s.pb.memory.values.update({0xD869:128,0xC77F:0x1D})):
        s=Session();change(s);review(s.call());assert s.c.baseline is None

@pytest.mark.parametrize("change",[
    lambda o:o["raw"].update(walk_counter=8),lambda o:o["raw"].update(flags5=1),
    lambda o:o["raw"].update(map_id=1),lambda o:o["raw"].update(x=9),
    lambda o:o["raw"].update(object_count=6),lambda o:o["stone"].update(picture=1),
    lambda o:o["stone"].update(picture2=63),lambda o:o["stone"].update(text=6)])
def test_pure_recomputes_native_idle_and_source_identity_instead_of_trusting_labels(change):
    review(Session().call(signal_change=change))

def test_unexecuted_offer_retry_counts_requests_without_resetting_pending_or_clock():
    s=Session();s.call();p=s.c.pending;started=s.c.step_started
    for _ in range(b.MAX_REQUESTS-1):
        out=s.call(previous=["wait"])
        assert out["available_actions"]==[p["action"],"wait"] and s.c.pending is p and not p["executed"]
    review(s.call(previous=["wait"]))
    assert s.c.requests==9 and s.c.step_started==started

def test_same_level_max_hp_or_extra_mon_metadata_cannot_rebase_after_owned_wild():
    for change in (lambda p:p["party"][0].update(max_hp=999),
                   lambda p:p["party"][0].update(unreceipted="changed")):
        s=Session();s.call();s.call(raw=1,no_grid=True);change(s.p);review(s.call())

def test_level_learned_move_starts_without_unreceipted_pp_ups_and_hms_are_preserved():
    baseline=b._resources(progress());ref=b.reference();mon=baseline["party"][0]
    future=next(m for m in ref["species"][b.species_key(mon["species"])]["level_moves"]
                if m["level"]>mon["level"] and m["move"] not in {b.move_key(x) for x in mon["moves"]})
    move_id=next(i for i in range(1,166) if b.move_key(i)==future["move"])
    changed=deepcopy(baseline);target=changed["party"][0]
    target.update(level=future["level"],exp=future["level"]**3,max_hp=mon["max_hp"]+2)
    target["moves"][1]=move_id;target["pp"][1]=1
    assert b._wild_return(baseline,changed)
    target["pp"][1]=65;assert not b._wild_return(baseline,changed)
    target["pp"][1]=1;target["moves"][0]=move_id;target["pp"][0]=1
    assert not b._wild_return(baseline,changed)  # SURF never deleted.

def test_final_player_is_bound_before_two_closed_world_frames():
    s=Session();s.to_index(18);s.pb.memory.values.update({0xD869:128,0xC77F:0x1D})
    assert not s.call()["first_boulder_complete"]
    s.place(player=(15,12));review(s.call(previous=["wait"]))
    assert s.c.final_player==(17,11)

@pytest.mark.parametrize("change",[lambda p:p["party"][1]["moves"].__setitem__(0,33),
    lambda p:p["party"][0]["moves"].__setitem__(1,70),lambda p:p.update(badges_raw=247)])
def test_source_strength_user_and_rainbow_badge_remain_real(change):
    s=Session();change(s.p);review(s.call())

def test_public_fixture_is_pinned_and_formal_imports_use_only_checkout_src_tests():
    assert data["source_commit"]==b.SOURCE_COMMIT and data["derived_public_source_fixture"] is True
    assert data["not_rom_data"] is True and len(data["tiles"])==18 and all(len(r)==20 for r in data["tiles"])
    assert data["objects"]==[list(p) for p in b.STATIC_POSITIONS] and len(data["primary_sources"])==8
    for entry in data["primary_sources"]:
        assert len(entry["git_blob_sha1"])==40 and len(entry["sha256"])==64
        assert entry["url"]=="https://raw.githubusercontent.com/pret/pokered/"+b.SOURCE_COMMIT+"/"+entry["path"]
    from laya_pokemon import hm_teaching,team_strategy,world_map
    for module in (hm_teaching,team_strategy,world_map):
        assert Path(module.__file__).resolve().is_relative_to((ROOT/"src").resolve())
