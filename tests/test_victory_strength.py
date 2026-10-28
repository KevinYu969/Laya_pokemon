"""Fixed-source native menu tests; fake reads only, no emulator, writes or game input."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import pytest

HERE=Path(__file__).resolve().parent
if HERE.name=="staged-victory-strength-floors-20261025" and HERE.parent.name==".local":
    ROOT=HERE.parent.parent;SOURCE=ROOT/".local/staged-victory-strength-floors-20261025/victory_strength.py"
elif HERE.name=="tests":
    ROOT=HERE.parent;SOURCE=ROOT/"src/laya_pokemon/victory_strength.py"
else:raise RuntimeError("Only exact staged or formal Strength tests are supported")
spec=importlib.util.spec_from_file_location("laya_pokemon._exact_victory_strength_candidate",SOURCE.resolve(strict=True))
strength=importlib.util.module_from_spec(spec);spec.loader.exec_module(strength)
assert Path(strength.__file__).resolve()==SOURCE.resolve()
from laya_pokemon.hm_teaching import TEXT_PROFILE,PROGRESS_PROFILE

def canvas():return [[" "]*20 for _ in range(18)]

def put(rows,x,y,value):
    value=value.replace("'t","t").replace("'l","l").upper()
    assert x+len(value)<=20
    rows[y][x:x+len(value)]=list(value);return rows

def packet(rows=None,window=True):
    return dict(profile=TEXT_PROFILE,read_valid=True,alignment_verified=True,read_error=None,
                window_visible=window,cells=deepcopy(rows or canvas()))

def start(row=6):
    rows=canvas()
    for y,label in ((2,"POKÉDEX"),(4,"POKÉMON"),(6,"ITEM"),(8,"KEVIN"),(10,"SAVE"),(12,"OPTION"),(14,"EXIT")):
        put(rows,12,y,label)
    return put(rows,11,row,"▶")
import json
FIXTURE=HERE/"strength_floors_fixture.json" if HERE.name!="tests" else HERE/"fixtures/victory_strength_floors.json"
from hashlib import sha256
assert sha256(FIXTURE.read_bytes()).hexdigest() in {"b810e34273cbcc04c233b0b6f4ef7813a17aba73e39f985a9b521ad2d2c7b8d9","d3698cef1b49542e121c2b4c53190b18f89da8542f3115f9b032edabe2918601"}
DATA=json.loads(FIXTURE.read_text(encoding="utf-8"))
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as REAL_CONSTANTS


def progress():
    rows=[(19,"LAPRAS",44,140,180,[57,34,58,109],[5,15,8,10]),
          (132,"SNORLAX",42,170,200,[70,133,156,34],[14,20,10,15]),
          (102,"EEVEE",35,89,90,[33,28,98,39],[30,15,30,30]),
          (154,"VENUSAUR",40,120,133,[75,15,73,22],[25,30,10,10]),
          (35,"FEAROW",40,110,125,[64,65,19,31],[35,20,15,20]),
          (7,"NIDOKING",40,124,140,[61,57,30,40],[20,15,25,35])]
    return dict(profile=PROGRESS_PROFILE,initialization_candidate=True,party_read_valid=True,
        party_count=6,player_name_raw="KEVIN",money=54321,badges_raw=255,
        inventory=[dict(item=i,quantity=3) for i in range(1,21)],
        party=[dict(species=s,species_name=name,level=lv,hp=hp,max_hp=maxhp,exp=lv**3,
                    status=0,moves=m,pp=pp) for s,name,lv,hp,maxhp,m,pp in rows])


def party(p,index=1,marker="▶"):
    r=canvas()
    for i,m in enumerate(p["party"]):
        put(r,3,2*i,m["species_name"]);put(r,13,2*i,f'{m["level"]:3}')
        put(r,13,2*i+1,f'{m["hp"]:3}/{m["max_hp"]:3}')
    put(r,0,2*index+1,marker);put(r,1,14,"Choose a POKéMON.")
    return r


def field(p,y=10,marker="▶"):
    index=next(i for i,m in enumerate(p["party"]) if m["species"]==132)
    r=party(p,index,"▷")
    for yy in range(8,18):r[yy][9:20]=[" "]*11
    for yy,label in [(10,"STRENGTH"),(12,"STATS"),(14,"SWITCH"),(16,"CANCEL")]:put(r,11,yy,label)
    return put(r,10,y,marker)


def message(p,kind="can",arrow=False,blank_background=False):
    index=next(i for i,m in enumerate(p["party"]) if m["species"]==132)
    r=canvas() if blank_background else party(p,index,"▷")
    for yy in range(12,18):r[yy]=[" "]*20
    first,second=("SNORLAX used","STRENGTH.") if kind=="used" else ("SNORLAX can","move boulders.")
    put(r,1,14,first);put(r,1,16,second)
    if arrow:put(r,18,16,"▼")
    return r


def grid(frame,key="1f_entry"):
    c=DATA["stances"][key];loc=c["start"];tiles=deepcopy(DATA["terrains"][str(loc["map_id"])])
    visible=[[x,loc["y"]] for x in range(12)]
    return dict(tileset_id=17,observation_frame=frame,verified_location=[loc["map_id"],loc["x"],loc["y"]],
        screen_cells_verified=12,visible_verified_cells=visible,tiles=tiles,
        walkable=[[int(t in {5,21,24,26,32,33,34,42,45,48}) for t in row] for row in tiles])


class Memory:
    def __init__(self,key="1f_entry"):
        self.values={address:0 for address in strength.ADDRESSES.values()}
        self.values.update({0xD728:64,0xD35E:108,0xD361:16,0xD362:8,0xD356:255,
                            0xD163:6,0xD732:1})
        c=DATA["stances"][key];loc=c["start"]
        self.values.update({0xD35E:loc["map_id"],0xD361:loc["y"],0xD362:loc["x"],
            0xD367:17,0xD368:9,0xD369:c["width"]//2,0xC104:60,0xC106:64})
        for value in DATA["stances"].values():self.values[value["block_address"]]=value["block_id"]
        self.reads=[];self.hook=None
    def __getitem__(self,address):
        self.reads.append(address);value=self.values[address]
        return self.hook(address,value) if self.hook else value
    def __setitem__(self,*args):raise AssertionError("No memory writes")


class FakePyBoy:
    def __init__(self,key="1f_entry"):self.frame_count=1;self.memory=Memory(key)
    def tick(self,*args):raise AssertionError("No stepping")
    def save_state(self,*args):raise AssertionError("No saves")


class Session:
    def __init__(self,key="1f_entry"):
        self.key=key;self.intent=deepcopy(strength.INTENTS[key]);self.location=deepcopy(DATA["stances"][key]["start"])
        self.c=strength.VictoryStrengthController(self.intent);self.p=progress()
        self.pb=FakePyBoy(key);self.previous=[];self.now=0.
    def call(self,rows=None,*,window=True,ready=False,same=False,previous=None,
             signal_change=None,grid_change=None,text_change=None,location=None):
        if not same:self.pb.frame_count+=1;self.now+=.05
        signal=strength.read_strength_observation(self.pb,self.pb.frame_count,REAL_CONSTANTS)
        if signal_change:signal_change(signal)
        text=packet(rows,window)
        if text_change:text_change(text)
        g=grid(self.pb.frame_count,self.key)
        if grid_change:grid_change(g)
        return self.c.context(text,self.p,location=deepcopy(location or self.location),
            battle_state=dict(kind="none",active=False,raw=0,observation_frame=self.pb.frame_count),
            grid=g,signal=signal,frame=self.pb.frame_count,
            previous=self.previous if previous is None else previous,now=self.now,overworld_ready=ready)
    def expect(self,rows,action,**kwargs):
        out=self.call(rows,**kwargs);assert out["available_actions"]==[action,"wait"],out
        self.previous=[action];return out
    def to_messages(self):
        self.expect(canvas(),"start",ready=True,window=False)
        self.expect(start(2),"down");self.expect(start(4),"a")
        target=next(i for i,m in enumerate(self.p["party"]) if m["species"]==132)
        for i in range(target+1):self.expect(party(self.p,i),"a" if i==target else "down")
        self.expect(field(self.p,12),"up");self.expect(field(self.p,10),"a")
        assert self.c.strength_selected is False
    def confirm(self,see_used=True):
        self.to_messages();self.pb.memory.values[0xD728]=65
        if see_used:
            out=self.call(message(self.p,"used"));assert out["available_actions"]==["wait"]
            self.previous=["wait"];assert self.c.seen_used_full
        self.expect(message(self.p,"can",True),"a")
        assert self.c.prompt_ack is False
    def finish(self):
        assert not self.call(canvas(),window=False,ready=True)["victory_strength_complete"]
        assert self.c.prompt_ack and self.c.closed_frame is not None
        assert not self.call(canvas(),window=False,ready=True,same=True)["victory_strength_complete"]
        self.previous=["wait"]
        out=self.call(canvas(),window=False,ready=True)
        assert out["victory_strength_complete"] is True and out["available_actions"]==["wait"]
        return out


def review(out):assert out["phase"]=="campaign_review" and out["available_actions"]==["wait"],out


def test_complete_native_strength_with_automatic_first_page_and_two_fresh_closed_frames():
    s=Session();before=deepcopy(s.p);s.confirm();s.finish()
    assert s.p==before and s.c.baseline["party"]==before["party"]
    assert s.pb.memory.values[0xD728]==65 and len(s.p["inventory"])==20


def test_source_automatic_used_page_may_not_be_sampled_no_fake_observation_claim():
    s=Session();s.confirm(see_used=False);s.finish()
    assert s.c.seen_used_full is False and s.c.seen_can_prompt is True


def test_snorlax_can_be_another_slot_with_dynamic_level_hp_money_bag_and_pp():
    s=Session();s.p["party"][0],s.p["party"][1]=s.p["party"][1],s.p["party"][0]
    s.p["party"][0].update(level=50,hp=50,exp=125000);s.p["money"]=3;s.p["inventory"]=[]
    s.confirm();s.finish();assert s.c.target_index==0


@pytest.mark.parametrize("key,value",[("map_id",1),("map_id",True),("player_x",9),
    ("player_y",17),("species",7),("move",57),("kind","strength_anywhere")])
def test_fixed_intent_never_generalizes(key,value):
    intent=deepcopy(strength.INTENT);intent[key]=value
    with pytest.raises(ValueError):strength.VictoryStrengthController(intent)


def test_offer_is_not_execution_and_wait_can_retry_same_pending_without_reset():
    s=Session();s.expect(canvas(),"start",window=False,ready=True)
    pending=s.c.pending;started=s.c.started
    s.previous=["wait"]
    out=s.call(canvas(),window=False,ready=True)
    assert out["available_actions"]==["start","wait"] and s.c.pending is pending
    assert s.c.stage=="initial" and s.c.started==started and s.c.calls==2
    s.expect(start(2),"down",previous=["start"])


def test_true_strength_a_must_precede_flag_and_message_not_just_offer():
    s=Session();s.to_messages();pending=s.c.pending
    s.pb.memory.values[0xD728]=65
    review(s.call(message(s.p,"can",True),previous=["wait"]))
    assert not s.c.strength_selected and not pending["executed"] and not s.c.prompt_ack


def test_prompt_offer_does_not_ack_and_cannot_close_without_real_previous_a():
    s=Session();s.confirm();assert not s.c.prompt_ack
    review(s.call(canvas(),window=False,ready=True,previous=["wait"]))
    assert not s.c.prompt_ack and s.c.closed_frame is None


def test_prompt_wait_reoffers_same_a_pending_without_claiming_or_refunding_execution():
    s=Session();s.confirm();pending=s.c.pending;started=s.c.started;calls=s.c.calls
    s.previous=["wait"]
    out=s.call(message(s.p,"can",True))
    assert out["available_actions"]==["a","wait"] and s.c.pending is pending
    assert not s.c.prompt_ack and not pending["executed"] and s.c.started==started and s.c.calls==calls+1
    s.previous=["a"];s.finish()


def test_used_full_page_flag_true_never_offers_a():
    s=Session();s.to_messages();s.pb.memory.values[0xD728]=65
    for _ in range(3):
        assert s.call(message(s.p,"used"))["available_actions"]==["wait"]
        s.previous=["wait"]
    assert not s.c.prompt_ack and s.c.seen_used_full


def test_can_full_without_prompt_arrow_never_offers_a_even_stable():
    s=Session();s.to_messages();s.pb.memory.values[0xD728]=65
    for _ in range(3):
        assert s.call(message(s.p,"can"))["available_actions"]==["wait"]
        s.previous=["wait"]
    s.expect(message(s.p,"can",True),"a")


def test_first_page_with_foreign_prompt_arrow_is_rejected():
    s=Session();s.to_messages();s.pb.memory.values[0xD728]=65
    review(s.call(message(s.p,"used",True)))


def test_partial_known_lines_wait_but_unknown_added_text_or_cursor_rejects():
    s=Session();s.to_messages();s.pb.memory.values[0xD728]=65
    r=message(s.p,"can");r[14][6:]=[" "]*14;r[16]=[" "]*20
    assert s.call(r)["available_actions"]==["wait"]
    s.previous=["wait"];r=message(s.p,"can",True);r[13][4]="X"
    review(s.call(r))


def test_no_blank_background_fallback_before_actual_prompt_a():
    s=Session();s.to_messages();s.pb.memory.values[0xD728]=65
    review(s.call(message(s.p,"can",True,blank_background=True)))


def test_native_flag_can_precede_redrawn_field_page_only_wait_after_actual_a():
    s=Session();s.to_messages();s.pb.memory.values[0xD728]=65
    assert s.call(field(s.p,10))["available_actions"]==["wait"]
    assert s.c.strength_selected and s.c.pending is None
    s.previous=["wait"];s.expect(message(s.p,"can",True),"a")


@pytest.mark.parametrize("change",[
    lambda p:p.update(money=True),lambda p:p.update(money=1000000),lambda p:p.update(badges_raw=247),
    lambda p:p.update(party_count=5),lambda p:p["party"][0].update(hp=0),
    lambda p:p["party"][0].update(status=8),lambda p:p["party"][0]["moves"].__setitem__(0,70),
    lambda p:p["party"][1]["moves"].__setitem__(0,57),lambda p:p["party"][1]["moves"].__setitem__(3,57),
    lambda p:p["party"][1]["moves"].__setitem__(0,0),lambda p:p["party"][0]["pp"].__setitem__(0,255),
])
def test_invalid_baseline_or_extra_field_move_rejected_before_input(change):
    s=Session();change(s.p);review(s.call(canvas(),window=False,ready=True));assert s.c.pending is None


@pytest.mark.parametrize("change",[
    lambda p:p.update(money=2),lambda p:p.update(badges_raw=127),
    lambda p:p["party"][0].update(hp=139),lambda p:p["party"][0].update(exp=999999),
    lambda p:p["party"][0]["pp"].__setitem__(0,4),lambda p:p["inventory"].reverse(),
    lambda p:p["inventory"][0].update(quantity=2),lambda p:p["party"][0].update(extra="changed"),
])
def test_complete_party_inventory_order_and_pp_fingerprint_stays_constant(change):
    s=Session();s.expect(canvas(),"start",window=False,ready=True);change(s.p)
    review(s.call(start(2)))


@pytest.mark.parametrize("address,value",[(0xD728,65),(0xCD6B,255),(0xCFC5,8),
    (0xCD38,1),(0xD700,2),(0xD057,2),(0xD730,32),
    (0xD736,4),(0xD72D,16),(0xD732,8),(0xD732,16),(0xD732,64),(0xD733,4)])
def test_start_must_be_native_idle_not_active_or_battle_or_surf(address,value):
    s=Session();s.pb.memory.values[address]=value
    review(s.call(canvas(),window=False,ready=True));assert s.c.baseline is None


@pytest.mark.parametrize("change",[
    lambda g:g["tiles"][16].__setitem__(8,5),lambda g:g.update(tileset_id=0),
    lambda g:g.update(verified_location=[108,8,17]),lambda g:g.update(screen_cells_verified=90),
    lambda g:g["walkable"][16].__setitem__(8,True),lambda g:g["visible_verified_cells"].append([0,16]),
])
def test_source_grid_tile_shape_visible_proof_is_required(change):
    s=Session();review(s.call(canvas(),window=False,ready=True,grid_change=change))
    assert s.c.pending is None


def test_unrelated_d728_bits_must_remain_constant():
    s=Session();s.to_messages();s.pb.memory.values[0xD728]=67
    review(s.call(message(s.p,"can",True)));assert not s.c.prompt_ack


def test_location_change_cannot_claim_strength_active_on_another_map():
    s=Session();s.confirm()
    review(s.call(canvas(),window=False,ready=True,location=dict(map_id=194,x=0,y=8)))
    assert s.c.closed_frame is None


def test_flag_true_or_full_blank_world_without_prompt_receipt_never_completes():
    s=Session();s.to_messages();s.pb.memory.values[0xD728]=65
    review(s.call(canvas(),window=False,ready=True));assert not s.c.prompt_ack


def test_after_ack_prompt_blink_never_resends_a():
    s=Session();s.confirm()
    assert s.call(message(s.p,"can",False))["available_actions"]==["wait"]
    assert s.c.prompt_ack


def test_sticky_error_and_clock_call_wait_budgets_survive_continued_calls():
    s=Session();s.expect(canvas(),"start",window=False,ready=True)
    review(s.call(start(2),same=True));error=s.c.error;started=s.c.started
    review(s.call(start(2)));assert s.c.error==error and s.c.started==started
    t=Session();t.expect(canvas(),"start",window=False,ready=True);t.now=61
    review(t.call(start(2)));assert t.c.started==.05
    u=Session();u.c.calls=240;review(u.call(canvas(),window=False,ready=True))
    v=Session();v.to_messages();v.pb.memory.values[0xD728]=65
    for _ in range(31):
        out=v.call(message(v.p,"used"));v.previous=["wait"]
    review(out)


def test_reader_double_reads_flags1_and_coordinates_against_real_sdk_without_writes():
    pb=FakePyBoy();signal=strength.read_strength_observation(pb,1,REAL_CONSTANTS)
    assert signal["read_valid"] and signal["raw_flags"]==64 and signal["strength_active"] is False
    assert signal["idle"] is True and signal["location"]==strength.START
    assert all(pb.memory.reads.count(a)==2 for a in strength.ADDRESSES.values())
    assert getattr(REAL_CONSTANTS,"STATUS_FLAGS1_ADDRESS",None) is None
    with pytest.raises(AssertionError):pb.tick()
    with pytest.raises(AssertionError):pb.memory[0xD728]=65


@pytest.mark.parametrize("key,value",[("STATUS_FLAGS3_ADDRESS",True),("EVENT_FLAGS_ADDRESS",0),
    ("OBTAINED_BADGES_ADDRESS",True),("PARTY_COUNT_ADDRESS",0)])
def test_reader_sdk_anchors_must_be_exact_integer(key,value):
    c=SimpleNamespace(**{k:getattr(REAL_CONSTANTS,k) for k in ["STATUS_FLAGS3_ADDRESS","EVENT_FLAGS_ADDRESS",
        "OBTAINED_BADGES_ADDRESS","PARTY_COUNT_ADDRESS","MAPS","BADGES"]});setattr(c,key,value)
    signal=strength.read_strength_observation(FakePyBoy(),1,c)
    assert not signal["read_valid"] and signal["strength_active"] is None


@pytest.mark.parametrize("value",[False,None,-1,256,"65"])
def test_reader_unknown_flag_byte_never_coerces_to_false(value):
    pb=FakePyBoy();pb.memory.values[0xD728]=value
    signal=strength.read_strength_observation(pb,1,REAL_CONSTANTS)
    assert signal["read_valid"] is False and signal["raw_flags"] is None and signal["idle"] is None


def test_reader_torn_double_read_and_frame_change_never_publish_flag():
    pb=FakePyBoy();seen=0
    def hook(address,value):
        nonlocal seen
        if address==0xD728:seen+=1;return 64 if seen==1 else 65
        return value
    pb.memory.hook=hook
    assert strength.read_strength_observation(pb,1,REAL_CONSTANTS)["strength_active"] is None
    pb=FakePyBoy()
    def moved(address,value):pb.frame_count=2;return value
    pb.memory.hook=moved
    assert strength.read_strength_observation(pb,1,REAL_CONSTANTS)["read_valid"] is False


def test_public_source_fixture_keeps_native_terminal_codes_and_all_four_tiles():
    assert 'line "STRENGTH.@"' in DATA["used_source"] and "prompt" not in DATA["used_source"]
    assert "\tprompt" in DATA["can_source"]
    for key,c in DATA["stances"].items():
        assert c["tile"]==(42 if key=="2f_after_fall" else 32)
        assert DATA["terrains"][str(c["start"]["map_id"])][c["start"]["y"]][c["start"]["x"]]==c["tile"]


def test_public_source_fixture_provenance_is_exact_fixed_commit_without_cache_reads():
    assert DATA["source_commit"]==strength.SOURCE_COMMIT and DATA["public_source_derived"] and DATA["not_rom_or_state"]
    assert len(DATA["stances"])==4 and len(DATA["primary_sources"])==8
    for r in DATA["primary_sources"]:
        assert len(r["git_blob_sha1"])==40 and len(r["sha256"])==64
        assert r["url"]=="https://raw.githubusercontent.com/pret/pokered/"+strength.SOURCE_COMMIT+"/"+r["path"]


def test_every_nonwait_offer_has_action_and_wait_and_does_not_mutate_source_inputs():
    s=Session();before=deepcopy(s.p)
    result=s.call(canvas(),window=False,ready=True)
    assert result["available_actions"]==["start","wait"] and s.p==before
