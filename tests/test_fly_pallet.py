"""固定官方RLE與六人原生格的純合成測試；禁止模擬器、IO及真遊戲輸入。"""
from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace

import pytest

from laya_pokemon import fly_pallet as fly
from tests.test_cut_six_party_background import progress as cut_progress, RAW_ROWS
from tests.test_hm_teaching import canvas, put, packet, start


CONSTANTS = SimpleNamespace(STATUS_FLAGS3_ADDRESS=0xD72D, EVENT_FLAGS_ADDRESS=0xD747,
    OBTAINED_BADGES_ADDRESS=0xD356, PARTY_COUNT_ADDRESS=0xD163,
    MAPS={"pallet_town":0,"route_16":27}, BADGES={"thunder":2})


class Memory:
    def __init__(self):
        self.values = {0xD35E:27,0xD361:6,0xD362:7,0xD70B:255,0xD70C:7,
                       0xD71A:6,0xD732:1,0xD733:0,0xD700:0,
                       0xCD6B:0,0xCFC5:0,0xCD38:0,0xFF40:0x81}
        self.reads = []
        self.hook = None

    def __getitem__(self, address):
        self.reads.append(address)
        if self.hook:
            return self.hook(address, self.values[address])
        return self.values[address]

    def __setitem__(self, *args):
        raise AssertionError("reader must never write")


class TileMap:
    def __init__(self):
        self.ids = [383]*360
        self.reads = 0
        self.hook = None

    def __getitem__(self, position):
        x,y = position
        self.reads += 1
        value = self.ids[y*20+x]
        return self.hook(self.reads, value) if self.hook else value


class FakePyBoy:
    def __init__(self):
        self.frame_count = 1
        self.memory = Memory()
        self.tilemap_background = self.tilemap_window = TileMap()
        self.screen = SimpleNamespace(tilemap_position_list=[[0,0,0,144] for _ in range(144)])

    def tick(self, *args):
        raise AssertionError("no emulator stepping")

    def save_state(self, *args):
        raise AssertionError("no state writes")


def progress():
    p = cut_progress()
    p["inventory"].append(dict(item=197,quantity=1))
    p["party"][4]["moves"][2], p["party"][4]["pp"][2] = 19,15
    return p


def party(index=4):
    r = canvas()
    for i,mon in enumerate(progress()["party"]):
        put(r,3,2*i,mon["species_name"])
        put(r,13,2*i,f'{mon["level"]:3}')
        put(r,13,2*i+1,f'{mon["hp"]:3}/{mon["max_hp"]:3}')
    put(r,1,14,"Choose a POKéMON.")
    return put(r,0,2*index+1,"▶")


def field(y=10):
    # 真Cut六人子選單的相同來源版面，改成Fly文字及正確FEAROW靜態槽位。
    r = [list(row) for row in RAW_ROWS]
    r[7][0], r[9][0], r[10][12] = " ","▷"," "
    r[10][13:16] = list("FLY")
    r[y][12] = "▶"
    return r


MAP_ROWS = [list("To PALLET TOWN    ▶▼")] + canvas()[1:]


def grid(location, frame):
    tiles = [[0x2C]*40 for _ in range(20)]
    if location == fly.LANDING:
        tiles[6][5] = 0x23
    return dict(tileset_id=0,screen_cells_verified=90,observation_frame=frame,
                verified_location=[location[k] for k in ("map_id","x","y")],
                tiles=tiles,walkable=[[1]*40 for _ in range(20)])


class Session:
    def __init__(self):
        self.p = progress()
        self.c = fly.FlyPalletController(deepcopy(fly.FLY_PALLET_INTENT))
        self.pb = FakePyBoy()
        self.now = 0.0
        self.previous = []
        self.last = None

    def call(self, rows=None, *, ready=False, window=True, raw=None, same=False,
             previous=None, location=None, signal_change=None, text_change=None, lcdc=None):
        if not same:
            self.pb.frame_count += 1
            self.now += .05
        location = deepcopy(location or fly.START)
        self.pb.memory.values.update({0xD35E:location["map_id"],0xD361:location["y"],0xD362:location["x"]})
        self.pb.memory.values[0xFF40] = (0xA1 if window else 0x81) if lcdc is None else lcdc
        self.pb.screen.tilemap_position_list = [[0,0,0,0 if window else 144] for _ in range(144)]
        raw = [0x7F]*360 if raw is None else raw
        self.pb.tilemap_background.ids = [((b^128)-128)+256 for b in raw]
        signal = fly.read_fly_observation(self.pb,self.pb.frame_count,CONSTANTS)
        assert signal["read_valid"] is True
        if signal_change:
            signal_change(signal)
        t = packet(rows,window)
        if text_change:
            text_change(t)
        previous = self.previous if previous is None else previous
        out = self.c.context(t,self.p,location=location,
            battle_state=dict(kind="none",active=False,raw=0,observation_frame=self.pb.frame_count),
            grid=grid(location,self.pb.frame_count),signal=signal,frame=self.pb.frame_count,
            previous=previous,now=self.now,overworld_ready=ready)
        self.last = out
        return out

    def expected(self, rows, action, **kwargs):
        out = self.call(rows,**kwargs)
        assert out["available_actions"] == [action,"wait"],out
        self.previous = [action]
        return out

    def to_field(self):
        self.expected(canvas(),"start",ready=True,window=False)
        self.expected(start(2),"down")
        self.expected(start(4),"a")
        for i in range(5):
            self.expected(party(i),"a" if i==4 else "down")

    def to_destination(self):
        self.to_field()
        self.expected(field(12),"up")
        self.expected(field(10),"a")

    def confirm_destination(self):
        self.to_destination()
        assert self.call(MAP_ROWS,window=False,raw=list(fly.PALLET_RAW))["available_actions"] == ["wait"]
        self.previous = ["wait"]
        self.expected(MAP_ROWS,"a",window=False,raw=list(fly.PALLET_RAW))


def review(out):
    assert out["phase"]=="campaign_review" and out["available_actions"]==["wait"],out


def test_fixed_source_raw_hash_and_signed_domain_are_not_legacy_text_cells():
    assert len(fly.PALLET_RAW)==360
    assert sha256(bytes(fly.PALLET_RAW)).hexdigest()=="09e05d374b548445aa7957ab16bec475719b6d19e72182d368be6bdeb800ec61"
    pb=FakePyBoy()
    pb.tilemap_background.ids=[((b^128)-128)+256 for b in fly.PALLET_RAW]
    s=fly.read_fly_observation(pb,1,CONSTANTS)
    assert s["read_valid"] and s["raw_bytes"]==list(fly.PALLET_RAW)
    assert s["raw_identifiers"][2]==0x167 and s["raw_bytes"][2]==0x67
    assert s["raw_identifiers"][18:20]==[0xED,0xEE]
    assert pb.tilemap_background.reads==720
    assert pb.memory.reads.count(0xD70B)==pb.memory.reads.count(0xD71A)==2


def test_full_native_flow_actual_actions_two_fresh_map_and_landing_preserve_everything():
    s=Session();before=deepcopy(s.p)
    s.confirm_destination()
    assert not s.c.destination_confirmed
    s.pb.memory.values.update({0xD71A:0,0xD732:13,0xD733:128,0xCD6B:255})
    assert s.call(window=False)["available_actions"]==["wait"]
    assert s.c.destination_confirmed and not s.last["fly_pallet_complete"]
    s.previous=["wait"]
    s.pb.memory.values.update({0xD732:1,0xD733:0,0xCD6B:0})
    assert not s.call(ready=True,window=False,location=fly.LANDING)["fly_pallet_complete"]
    assert not s.call(ready=True,window=False,location=fly.LANDING,same=True)["fly_pallet_complete"]
    out=s.call(ready=True,window=False,location=fly.LANDING)
    assert out["fly_pallet_complete"] and out["available_actions"]==["wait"]
    assert s.p==before and s.c.baseline["party"]==before["party"]


@pytest.mark.parametrize("change", [
    lambda c:setattr(c,"STATUS_FLAGS3_ADDRESS",True),
    lambda c:c.MAPS.update(pallet_town=True),
    lambda c:c.BADGES.update(thunder=3),
])
def test_reader_sdk_unknown_or_mismatched_anchors_give_unknown(change):
    c=deepcopy(CONSTANTS);change(c)
    s=fly.read_fly_observation(FakePyBoy(),1,c)
    assert s["read_valid"] is False and s["location"] is None and s["destination"] is None


@pytest.mark.parametrize("bad", [True,-1,256,None,"0"])
def test_reader_unknown_byte_never_becomes_safe_zero(bad):
    pb=FakePyBoy();pb.memory.values[0xD70B]=bad
    s=fly.read_fly_observation(pb,1,CONSTANTS)
    assert s["read_valid"] is False and s["visited"] is None


@pytest.mark.parametrize("field,value", [
    ("screen_read_valid",False),("signed_tile_data",None),("raw_bytes",None),
    ("raw_identifiers",[0x7F]*360),("read_valid",1),
])
def test_initial_true_profile_cannot_replace_complete_raw_screen_proof(field,value):
    s=Session()
    review(s.call(ready=True,window=False,signal_change=lambda q:q.update({field:value})))
    assert s.c.baseline is None and s.c.pending is None


def test_constants_getter_exception_is_unknown_not_an_exception_or_zero():
    class Broken:
        @property
        def STATUS_FLAGS3_ADDRESS(self):
            raise OSError("fake constants getter")
    signal=fly.read_fly_observation(FakePyBoy(),1,Broken())
    assert signal["read_valid"] is False and signal["location"] is None


@pytest.mark.parametrize("change", ["ram","screen","frame","getter","unsigned","alignment","identifier"])
def test_reader_double_read_domain_and_getter_fail_closed(change):
    pb=FakePyBoy()
    if change=="ram":
        pb.memory.hook=lambda a,v:0 if a==0xD35E and pb.memory.reads.count(a)>1 else v
    elif change=="screen":
        pb.tilemap_background.hook=lambda n,v:382 if n==361 else v
    elif change=="frame":
        def changing(n,v):
            if n==360:pb.frame_count+=1
            return v
        pb.tilemap_background.hook=changing
    elif change=="getter":
        def broken(a,v):raise OSError("fake getter failure")
        pb.memory.hook=broken
    elif change=="unsigned":pb.memory.values[0xFF40]=0x91
    elif change=="alignment":pb.screen.tilemap_position_list[1][0]=1
    else:pb.tilemap_background.ids[2]=0x67
    signal=fly.read_fly_observation(pb,1,CONSTANTS)
    assert signal["read_valid"] is False and signal["raw_bytes"] is None


def test_changed_page_without_actual_previous_never_advances_or_confirms():
    s=Session();s.expected(canvas(),"start",ready=True,window=False)
    review(s.call(start(4),previous=[]))
    assert s.c.stage=="initial" and not s.c.selected_user


def test_same_old_page_missing_execution_only_waits_and_does_not_resend_start():
    s=Session();s.expected(canvas(),"start",ready=True,window=False)
    out=s.call(canvas(),ready=True,window=False,previous=["wait"])
    assert out["available_actions"]==["wait"] and s.c.stage=="initial"


@pytest.mark.parametrize("part", ["field","party"])
def test_foreign_cursor_or_wrong_native_name_never_gets_a(part):
    s=Session()
    if part=="field":s.to_field();r=field();r[7][0]="▷"
    else:
        s.expected(canvas(),"start",ready=True,window=False);s.expected(start(4),"a")
        r=party();r[0][3]="X"
    review(s.call(r))


@pytest.mark.parametrize("window,lcdc", [(False,0x81),(True,0xE3)])
def test_complete_heading_before_true_arrow_pair_is_wait_then_two_fresh_ready_pages(window,lcdc):
    s=Session();s.to_destination()
    raw=list(fly.PALLET_RAW);raw[18:20]=[0x7F,0x67]
    rows=deepcopy(MAP_ROWS);rows[0][18:20]=[" "," "]
    assert s.call(rows,window=window,lcdc=lcdc,raw=raw)["available_actions"]==["wait"]
    assert s.c.destination_frame is None
    s.previous=["wait"]
    assert s.call(MAP_ROWS,window=window,lcdc=lcdc,raw=list(fly.PALLET_RAW))["available_actions"]==["wait"]
    s.expected(MAP_ROWS,"a",window=window,lcdc=lcdc,raw=list(fly.PALLET_RAW))


def test_actual_e3_visible_window_destination_needs_two_fresh_frames_not_a_same_frame_repeat():
    # clone1封包的原生值：visited FF04、destination0、LCDC E3、完整Window頁。
    # 不依賴outputs、不讀checkpoint；360格仍核固定primary SHA。
    s=Session();s.to_destination()
    s.pb.memory.values.update({0xD70B:255,0xD70C:4,0xD71A:0})
    first=s.call(MAP_ROWS,window=True,lcdc=0xE3,raw=list(fly.PALLET_RAW))
    assert first["available_actions"]==["wait"] and s.c.destination_frame==s.pb.frame_count
    again=s.call(MAP_ROWS,window=True,lcdc=0xE3,raw=list(fly.PALLET_RAW),same=True)
    assert again["available_actions"]==["wait"] and not s.c.destination_confirmed
    s.expected(MAP_ROWS,"a",window=True,lcdc=0xE3,raw=list(fly.PALLET_RAW))


def test_visible_window_acceptance_still_requires_text_and_raw_layer_proofs_agree():
    s=Session();s.to_destination()
    review(s.call(MAP_ROWS,window=True,lcdc=0xE3,raw=list(fly.PALLET_RAW),
                  text_change=lambda t:t.update(window_visible=False)))
    assert not s.c.destination_confirmed


@pytest.mark.parametrize("change", ["other_town","raw_body","raw_domain","no_actual_fly","sameframe_conflict"])
@pytest.mark.parametrize("window,lcdc", [(False,0x81),(True,0xE3)])
def test_unknown_destination_or_unexecuted_fly_never_gets_confirmation_a(change,window,lcdc):
    s=Session();s.to_destination();raw=list(fly.PALLET_RAW);rows=deepcopy(MAP_ROWS)
    kwargs={}
    if change=="other_town":raw[3]=0x95;rows[0][3]="V"
    elif change=="raw_body":raw[20]^=1
    elif change=="raw_domain":kwargs["signal_change"]=lambda q:q["raw_identifiers"].__setitem__(2,0x67)
    elif change=="no_actual_fly":kwargs["previous"]=["wait"]
    else:
        s.call(MAP_ROWS,window=window,lcdc=lcdc,raw=raw)
        kwargs["same"]=True;raw[20]^=1
    review(s.call(rows,window=window,lcdc=lcdc,raw=raw,**kwargs))
    assert not s.c.destination_confirmed


@pytest.mark.parametrize("mutation", [
    lambda p:p.update(money=55371),
    lambda p:p["inventory"].pop(),
    lambda p:p["party"][4]["pp"].__setitem__(2,14),
    lambda p:p["party"].reverse(),
    lambda p:p["party"][0].update(hp=120),
])
def test_party_bag_money_and_every_pp_are_conserved_through_field_fly(mutation):
    s=Session();s.to_field();mutation(s.p)
    review(s.call(field()))


def test_map_id_and_flags_cleared_during_entry_animation_are_not_completion():
    s=Session();s.confirm_destination()
    s.pb.memory.values.update({0xD71A:0,0xD732:1,0xD733:0,0xCD6B:255})
    out=s.call(ready=True,window=False,location=fly.LANDING)
    assert out["available_actions"]==["wait"] and not out["fly_pallet_complete"]
    assert s.c.closed_frame is None


def test_pending_and_budget_survive_class_hot_reload_without_new_baseline():
    s=Session();s.to_field();base=s.c.baseline;started=s.c.started
    s.c.__class__=fly.FlyPalletController
    s.c.waits=30
    out=s.call(party(4))
    review(out)
    assert s.c.baseline is base and s.c.started==started
    assert out["review_reason"]=="fly_pallet_wait_budget_exhausted"


def test_timeout_and_regressed_frame_never_offer_inputs():
    s=Session();s.expected(canvas(),"start",ready=True,window=False)
    s.now=61
    review(s.call(start(4)))
    s=Session();s.expected(canvas(),"start",ready=True,window=False)
    s.pb.frame_count=0
    review(s.call(start(4)))
