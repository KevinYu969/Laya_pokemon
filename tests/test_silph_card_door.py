"""固定來源合成Card Key兩門回執；不使用遊戲/ROM/state或任何setter。"""
from copy import deepcopy
from types import SimpleNamespace
import pytest

from laya_pokemon.silph_card_door import (
    SilphCardDoorController, read_silph_card_door, THREE_F_INTENT, ELEVEN_F_INTENT,
    TEXT_PROFILE, PROFILE, SOURCE_COMMIT, GRID_SOURCE, EVENTS, MAPS, MAX_WAITS,
)

INTENTS = (THREE_F_INTENT, ELEVEN_F_INTENT)
SDK = SimpleNamespace(EVENT_FLAGS_ADDRESS=0xD747, OBTAINED_BADGES_ADDRESS=0xD356,
    EVENT_FLAGS={"silph_co_3_unlocked_door2":0x709,"silph_co_11_unlocked_door":0x788},
    MAPS={"silph_co_3f":208,"silph_co_11f":235})


def party_progress():
    rows=[(132,"SNORLAX",35,168,[29,133,156,34],[15,20,10,15]),
          (7,"NIDOKING",36,121,[61,33,30,40],[20,35,25,35]),
          (102,"EEVEE",35,90,[33,28,98,39],[35,15,30,30]),
          (154,"VENUSAUR",35,111,[75,15,73,22],[25,30,10,10]),
          (35,"FEAROW",35,108,[64,65,43,31],[35,20,30,20])]
    return dict(profile="gen1-wrapper-ram-progress-v1-unvalidated", initialization_candidate=True,
        party_read_valid=True, party_count=5, money=40000, player_name_raw="KEVIN", badges_raw=31,
        inventory=[dict(item=4,quantity=6),dict(item=48,quantity=1),dict(item=198,quantity=1)],
        party=[dict(species=s,species_name=n,level=lv,exp=lv**3,hp=hp,max_hp=hp,
                    status=0,moves=m,pp=pp) for s,n,lv,hp,m,pp in rows])


def page(first="",second="",arrow=False,scroll=False):
    r=[[" "]*20 for _ in range(18)]
    for y,v in zip((13,15) if scroll else (14,16),(first,second)):
        r[y][1:1+len(v)]=list(v)
    if arrow:r[16][18]="▼"
    return r


def packet(rows=None,window=True,summary=False):
    rows=deepcopy(page() if rows is None else rows)
    t=dict(profile=TEXT_PROFILE,read_valid=True,alignment_verified=True,read_error=None,
           window_visible=window,cells=rows)
    if summary:
        import re
        pairs=[(y,"".join(r).rstrip()) for y,r in enumerate(rows)
               if re.search(r"[A-Za-z0-9]{2,}","".join(r))][:12]
        t.update(lines=[r for _,r in pairs],line_rows=[y for y,_ in pairs])
    return t


def first(arrow=True):
    return page("Bingo!","The CARD KEY",arrow)


def final():
    return page("The CARD KEY","opened the door!")


def grid(i,frame,opened=False):
    mid,x,y=i["map_id"],i["player_x"],i["player_y"]
    tileset,w,h,stance,closed,open_tile=MAPS[mid]
    tiles=[[stance]*w for _ in range(h)];walk=[[1]*w for _ in range(h)]
    dx,dy=i["door_x"],i["door_y"]
    tiles[dy][dx]=open_tile if opened else closed
    walk[dy][dx]=1 if opened else 0
    cells=[[cx,cy] for cy in range(y-1,y+2) for cx in range(x-2,x+3)]
    return dict(source=GRID_SOURCE,observation_frame=frame,tileset_id=tileset,
                verified_location=[mid,x,y],tiles=tiles,walkable=walk,
                screen_cells_verified=len(cells),visible_verified_cells=cells)


def signal(i,frame,opened=False):
    name,eid,address,bit=EVENTS[i["map_id"]]
    return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,read_valid=True,unknown_reason=None,
        live_calibrated=False,observation_frame=frame,
        location=dict(map_id=i["map_id"],x=i["player_x"],y=i["player_y"]),
        event_name=name,event_id=eid,address=address,bit=bit,
        raw_flags=0xA0 | ((1<<bit) if opened else 0),unlocked=opened)


class Session:
    def __init__(self,i=THREE_F_INTENT):
        self.i=deepcopy(i);self.p=party_progress();self.c=SilphCardDoorController(i)
        self.frame=0;self.now=0.;self.opened=False
        self.loc=dict(map_id=i["map_id"],x=i["player_x"],y=i["player_y"],facing=i["facing"],
                      facing_raw=8 if i["facing"]=="left" else 4)

    def call(self,rows=None,*,same=False,ready=False,window=True,with_grid=False,**kw):
        if not same:self.frame+=1
        self.now+=.1
        t=kw.pop("text",packet(rows,window))
        s=kw.pop("door_signal",signal(self.i,self.frame,self.opened))
        g=kw.pop("world_grid",grid(self.i,self.frame,self.opened) if with_grid else None)
        return self.c.context(t,kw.pop("progress",self.p),location=kw.pop("location",self.loc),
            battle_state=kw.pop("battle_state",dict(kind="none",active=False,raw=0)),
            door_signal=s,world_grid=g,frame=kw.pop("frame",self.frame),
            now=kw.pop("now",self.now),overworld_ready=ready,**kw)

    def action(self,rows=None,**kw):
        out=self.call(rows,**kw)
        assert out["available_actions"]==["a","wait"],out
        return out

    def start(self):
        self.action(ready=True,window=False,with_grid=True)

    def to_final(self):
        self.start();self.action(first())
        out=self.call(final());assert out["available_actions"]==["wait"]
        assert not self.c.final_ack

    def closing(self):
        self.to_final();self.frame+=15;self.action(final())
        assert self.c.final_ack
        self.opened=True

    def complete(self):
        self.closing()
        assert self.call(ready=True,window=False,with_grid=True)["available_actions"]==["wait"]
        out=self.call(ready=True,window=False,with_grid=True)
        assert out["silph_card_door_complete"] is True
        return out


def review(out):
    assert out["phase"]=="campaign_review" and out["available_actions"]==["wait"],out


@pytest.mark.parametrize("i",INTENTS)
def test_normal_source_prompt_done_and_two_closed_frames(i):
    s=Session(i);original=deepcopy(s.p);out=s.complete()
    assert s.p==original and s.c.baseline["party"]==original["party"]
    assert s.c.baseline["inventory"]==original["inventory"] and s.c.baseline["money"]==40000
    assert out["event_id"]==i["event_id"] and out["opened_tile"]==MAPS[i["map_id"]][5]
    assert out["card_key_consumed"] is False and s.c.stage=="complete"
    # 第三個新閉合幀仍僅回完成，絕不重新面門A。
    assert s.call(ready=True,window=False,with_grid=True)["silph_card_door_complete"]


@pytest.mark.parametrize("i",INTENTS)
@pytest.mark.parametrize("bad",["initial_open","event_only","tile_only","missing_grid","wrong_tile",
                               "stance_wrong","invisible_door","wrong_tileset","wrong_map","stale_grid"])
def test_initial_must_prove_new_closed_door_and_false_event(i,bad):
    s=Session(i);s.frame=1;g=grid(i,2);sig=signal(i,2)
    if bad=="initial_open":g=grid(i,2,True);sig=signal(i,2,True)
    elif bad=="event_only":sig=signal(i,2,True)
    elif bad=="tile_only":g=grid(i,2,True)
    elif bad=="missing_grid":g=None
    elif bad=="wrong_tile":g["tiles"][i["door_y"]][i["door_x"]]=0x24 if i["map_id"]==235 else 0x5E
    elif bad=="stance_wrong":g["walkable"][i["player_y"]][i["player_x"]]=0
    elif bad=="invisible_door":
        g["visible_verified_cells"].remove([i["door_x"],i["door_y"]]);g["screen_cells_verified"]-=1
    elif bad=="wrong_tileset":g["tileset_id"]=16 if i["map_id"]==208 else 22
    elif bad=="wrong_map":g["verified_location"][0]=0
    elif bad=="stale_grid":g["observation_frame"]=1
    review(s.call(ready=True,window=False,world_grid=g,door_signal=sig))
    assert s.c.baseline is None


@pytest.mark.parametrize("bad",["kind","map","stance","facing","door","event","bool"])
def test_only_two_exact_typed_intents(bad):
    i=deepcopy(THREE_F_INTENT)
    if bad=="kind":i["kind"]="use_item"
    elif bad=="map":i["map_id"]=209
    elif bad=="stance":i["player_x"]=17
    elif bad=="facing":i["facing"]="up"
    elif bad=="door":i["door_x"]=16
    elif bad=="event":i["event_id"]=0x708
    else:i["map_id"]=True
    with pytest.raises(ValueError):SilphCardDoorController(i)


@pytest.mark.parametrize("field,value",[("map_id",235),("x",17),("y",9),("facing","right"),
                                        ("facing_raw",12),("facing_raw",True)])
def test_exact_stance_and_direction_are_not_navigation(field,value):
    s=Session();s.loc[field]=value;review(s.call(ready=True,window=False,with_grid=True))


@pytest.mark.parametrize("mutation",[
    lambda p:p["inventory"].pop(1),
    lambda p:p["inventory"][1].update(quantity=2),
    lambda p:p["inventory"].append(dict(item=48,quantity=1)),
    lambda p:p.update(profile="unknown"),
    lambda p:p.update(party_read_valid=False),
    lambda p:p.update(initialization_candidate=1),
    lambda p:p.update(party_count=True),
    lambda p:p["party"][0].update(status=255),
    lambda p:p["party"][0].update(pp=[255,20,10,15]),
    lambda p:p.update(money=True),
])
def test_full_key_and_progress_preconditions(mutation):
    s=Session();mutation(s.p);review(s.call(ready=True,window=False,with_grid=True))


@pytest.mark.parametrize("mutation",[
    lambda p:p["party"].reverse(),
    lambda p:p["party"][0].update(hp=100),
    lambda p:p["party"][0].update(max_hp=170),
    lambda p:p["party"][0].update(status=8),
    lambda p:p["party"][0].update(level=36),
    lambda p:p["party"][0].update(exp=999),
    lambda p:p["party"][0]["moves"].__setitem__(0,70),
    lambda p:p["party"][0]["pp"].__setitem__(0,14),
    lambda p:p["inventory"].reverse(),
    lambda p:p["inventory"][0].update(quantity=5),
    lambda p:p["inventory"].pop(1),
    lambda p:p.update(money=39800),
    lambda p:p.update(player_name_raw="RED"),
    lambda p:p.update(badges_raw=63),
])
def test_fingerprint_is_immutable_even_on_blank_or_partial(mutation):
    s=Session();s.start();base=deepcopy(s.c.baseline);mutation(s.p)
    review(s.call());assert s.c.baseline==base


@pytest.mark.parametrize("bad",[False,True,"wrong_row"])
def test_first_source_cont_prompt_requires_true_arrow_then_no_resend(bad):
    s=Session();s.start()
    r=first(False)
    if bad=="wrong_row":r[17][18]="▼"
    elif bad:r[16][18]=" "
    out=s.call(r)
    assert out["available_actions"]==["wait"] and not s.c.prompt_ack
    if bad=="wrong_row":
        review(out);return
    for row in (None,first(False)):
        assert s.call(row)["available_actions"]==["wait"] and not s.c.prompt_ack
    s.action(first());assert s.c.prompt_ack
    for row in (None,first(False),first()):
        assert s.call(row)["available_actions"]==["wait"]
    assert not s.c.final_ack


def test_native_cont_scroll_has_known_intermediate_rows_only_after_ack():
    s=Session();s.start();s.action(first())
    assert s.call(page("Bingo!","The CARD KEY",scroll=True))["available_actions"]==["wait"]
    assert s.c.error is None
    s.call(final());s.frame+=15;s.action(final())
    t=Session();t.start();review(t.call(page("Bingo!","The CARD KEY",scroll=True)))


def test_done_full_must_stay_two_consecutive_new_observations_before_single_outer_a():
    s=Session();s.start();s.action(first())
    assert s.call(final())["available_actions"]==["wait"]
    assert s.call(final(),same=True)["available_actions"]==["wait"] and not s.c.final_ack
    assert s.call()["available_actions"]==["wait"] # blank重設完整頁穩定證據
    assert s.call(final())["available_actions"]==["wait"]
    s.frame+=15;s.action(final())
    for row in (None,final(),final()):
        assert s.call(row)["available_actions"]==["wait"]
    assert s.c.error is None


@pytest.mark.parametrize("i",INTENTS)
@pytest.mark.parametrize("bits,tiles",[(True,False),(False,True),(False,False)])
def test_single_bit_or_single_tile_is_not_completion(i,bits,tiles):
    s=Session(i);s.to_final();s.frame+=15;s.action(final())
    for _ in range(3):
        f=s.frame+1
        out=s.call(ready=True,window=False,door_signal=signal(i,f,bits),world_grid=grid(i,f,tiles))
        assert out["available_actions"]==["wait"] and not out.get("silph_card_door_complete")
    s.opened=True;s.call(ready=True,window=False,with_grid=True)
    assert s.call(ready=True,window=False,with_grid=True)["silph_card_door_complete"]


def test_two_closed_frames_must_be_consecutive_complete_observations():
    s=Session();s.closing();s.call(ready=True,window=False,with_grid=True)
    s.call(final())
    assert not s.call(ready=True,window=False,with_grid=True).get("silph_card_door_complete")
    assert s.call(ready=True,window=False,with_grid=True)["silph_card_door_complete"]


@pytest.mark.parametrize("early",["event","tile","both"])
def test_opening_before_own_final_dialogue_is_not_receipt(early):
    s=Session();s.start();f=s.frame+1
    review(s.call(first(),door_signal=signal(s.i,f,early in ("event","both")),
                  world_grid=grid(s.i,f,early in ("tile","both"))))


@pytest.mark.parametrize("change",["unrelated_bit","event_revert","tile_revert"])
def test_flags_and_open_tile_cannot_revert_or_change_other_bits(change):
    s=Session();s.closing()
    s.call(ready=True,window=False,with_grid=True)
    f=s.frame+1;sig=signal(s.i,f,True);g=grid(s.i,f,True)
    if change=="unrelated_bit":sig["raw_flags"]^=4
    elif change=="event_revert":sig=signal(s.i,f,False)
    else:g=grid(s.i,f,False)
    review(s.call(ready=True,window=False,door_signal=sig,world_grid=g))


@pytest.mark.parametrize("field,value",[("profile","wrong"),("read_valid",False),("read_valid",1),
    ("alignment_verified",False),("read_error","visible_tile_alignment_incomplete"),
    ("window_visible",None)])
def test_full_native_decoder_proof_required(field,value):
    s=Session();t=packet(window=False);t[field]=value
    review(s.call(text=t,ready=True,with_grid=True))


@pytest.mark.parametrize("where",["first","final"])
@pytest.mark.parametrize("bad",["offset","unknown","extra_arrow","foreign_menu","summary"])
def test_polluted_source_page_never_a(where,bad):
    s=Session();s.start()
    if where=="final":s.action(first())
    r=first() if where=="first" else final()
    if bad=="offset":r[14]=[" "]+r[14][:-1]
    elif bad=="unknown":r[0][0]="X"
    elif bad=="extra_arrow":r[14][18]="▼"
    elif bad=="foreign_menu":r[3][1:4]=list("YES")
    t=packet(r)
    if bad=="summary":t["lines"]=["opened the door!"];t["line_rows"]=[0]
    review(s.call(text=t))


@pytest.mark.parametrize("where",["first","final"])
def test_exact_partial_source_only_wait(where):
    s=Session();s.start()
    if where=="final":s.action(first())
    r=first(False) if where=="first" else final()
    r[16][4:19]=[" "]*15
    assert s.call(r)["available_actions"]==["wait"] and s.c.error is None


def test_native_line_summaries_consistent_without_replacing_cells():
    s=Session();s.start();s.action(text=packet(first(),summary=True))
    s.call(text=packet(final(),summary=True));s.frame+=15;s.action(text=packet(final(),summary=True))


@pytest.mark.parametrize("where",["initial","after_start","final"])
def test_same_frame_packet_conflict_and_no_duplicate_a(where):
    s=Session()
    if where=="initial":s.start();kw=dict(ready=True,window=False,with_grid=True);r=None
    elif where=="after_start":s.start();s.action(first());kw={};r=first()
    else:s.to_final();s.frame+=15;s.action(final());kw={};r=final()
    assert s.call(r,same=True,**kw)["available_actions"]==["wait"]
    t=packet(r,kw.get("window",True));t["cells"][0][0]="X"
    review(s.call(same=True,text=t,**kw))


@pytest.mark.parametrize("bad",["frame_back","bool_frame","clock_back","nan","timeout","calls","waits"])
def test_bounded_transaction_and_clock(bad):
    s=Session();s.start()
    if bad=="frame_back":kw=dict(frame=0)
    elif bad=="bool_frame":kw=dict(frame=True)
    elif bad=="clock_back":kw=dict(now=0.)
    elif bad=="nan":kw=dict(now=float("nan"))
    elif bad=="timeout":kw=dict(now=61.)
    elif bad=="calls":s.c.calls=240;kw={}
    else:s.c.waits=MAX_WAITS;kw={}
    review(s.call(**kw))


@pytest.mark.parametrize("field,value",[("event_id",0x708),("event_id",True),("address",0xD829),
    ("bit",0),("raw_flags",True),("unlocked",1),("read_valid",False),("profile","wrong"),
    ("source_commit","HEAD"),("observation_frame",0),("unknown_reason","memory_unreadable")])
def test_source_signal_cannot_be_faked_by_single_unlock_bool(field,value):
    s=Session();sig=signal(s.i,1);sig[field]=value
    review(s.call(ready=True,window=False,with_grid=True,door_signal=sig))


@pytest.mark.parametrize("kind",["wild","trainer"])
def test_no_battle_transaction(kind):
    s=Session();review(s.call(ready=True,window=False,with_grid=True,
                      battle_state=dict(kind=kind,active=True,raw=1 if kind=="wild" else 2)))


class Memory:
    def __init__(self,data,hook=None):self.data=data;self.hook=hook;self.reads=[]
    def __getitem__(self,address):
        self.reads.append(address)
        if self.hook:return self.hook(self,address,len(self.reads))
        return self.data[address]
    def __setitem__(self,*a):raise AssertionError("no writes")


def fake(i=THREE_F_INTENT):
    loc=dict(map_id=i["map_id"],x=i["player_x"],y=i["player_y"])
    address=EVENTS[i["map_id"]][2]
    mem=Memory({address:0xA0,0xD35E:loc["map_id"],0xD361:loc["y"],0xD362:loc["x"]})
    p=SimpleNamespace(memory=mem,frame_count=77)
    return p,loc


@pytest.mark.parametrize("i",INTENTS)
def test_reader_double_read_address_and_exact_sdk_contract(i):
    p,loc=fake(i)
    r=read_silph_card_door(p,intent=i,observation_frame=77,expected_location=loc,constants=SDK)
    assert r["read_valid"] and r["unlocked"] is False
    name,eid,address,bit=EVENTS[i["map_id"]]
    assert (r["event_name"],r["event_id"],r["address"],r["bit"])==(name,eid,address,bit)
    assert p.memory.reads==[address,0xD35E,0xD361,0xD362]*2
    p.memory.data[address]|=1<<bit
    assert read_silph_card_door(p,intent=i,observation_frame=77,expected_location=loc,
                               constants=SDK)["unlocked"] is True


@pytest.mark.parametrize("value",[None,True,-1,256,1.5,"0"])
def test_reader_unknown_byte_is_not_false(value):
    p,loc=fake();p.memory.data[0xD828]=value
    r=read_silph_card_door(p,intent=THREE_F_INTENT,observation_frame=77,expected_location=loc,constants=SDK)
    assert not r["read_valid"] and "unlocked" not in r


@pytest.mark.parametrize("bad",["anchor","bool_anchor","event","map","frame","bool_frame","wrong_map",
                               "wrong_y","torn_byte","torn_frame","getter"])
def test_reader_unknown_contract_torn_or_wrong_location(bad):
    p,loc=fake();c=deepcopy(SDK);frame=77
    if bad=="anchor":c.EVENT_FLAGS_ADDRESS=0xD748
    elif bad=="bool_anchor":c.OBTAINED_BADGES_ADDRESS=True
    elif bad=="event":c.EVENT_FLAGS["silph_co_3_unlocked_door2"]=0x708
    elif bad=="map":c.MAPS["silph_co_11f"]=234
    elif bad=="frame":frame=76
    elif bad=="bool_frame":frame=True
    elif bad=="wrong_map":p.memory.data[0xD35E]=235
    elif bad=="wrong_y":p.memory.data[0xD361]=9
    elif bad=="torn_byte":
        p.memory.hook=lambda m,a,n:m.data[a] if n<=4 else (m.data[a]^1 if a==0xD828 else m.data[a])
    elif bad=="torn_frame":
        def hook(m,a,n):
            if n==8:p.frame_count+=1
            return m.data[a]
        p.memory.hook=hook
    else:
        def hook(m,a,n):raise RuntimeError("no getter")
        p.memory.hook=hook
    r=read_silph_card_door(p,intent=THREE_F_INTENT,observation_frame=frame,expected_location=loc,constants=c)
    assert not r["read_valid"] and "unlocked" not in r


def test_installed_official_sdk_matches_fixed_source_event_enum_and_offsets():
    # 只匯入SDK公開constants，不建PyBoy或讀遊戲；固定source const_next/skip推導另記MD。
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as c
    assert c.EVENT_FLAGS_ADDRESS==0xD747 and c.OBTAINED_BADGES_ADDRESS==0xD356
    assert c.EVENT_FLAGS["silph_co_3_unlocked_door2"]==0x709
    assert c.EVENT_FLAGS["silph_co_11_unlocked_door"]==0x788
    assert c.MAPS["silph_co_3f"]==208 and c.MAPS["silph_co_11f"]==235


@pytest.mark.parametrize("bad",["frame_getter","sdk_getter","location_bool","missing_memory"])
def test_reader_property_exception_and_malformed_location_stay_unknown(bad):
    p,loc=fake();c=SDK
    if bad=="frame_getter":
        class BrokenFrame:
            @property
            def frame_count(self):raise RuntimeError("frame unreadable")
        p=BrokenFrame()
    elif bad=="sdk_getter":
        class BrokenSDK:
            @property
            def EVENT_FLAGS_ADDRESS(self):raise RuntimeError("constants unreadable")
        c=BrokenSDK()
    elif bad=="location_bool":loc["x"]=True
    else:p=SimpleNamespace(frame_count=77)
    r=read_silph_card_door(p,intent=THREE_F_INTENT,observation_frame=77,
                          expected_location=loc,constants=c)
    assert not r["read_valid"] and "unlocked" not in r


@pytest.mark.parametrize("i",INTENTS)
def test_final_done_needs_sixteen_emulator_frames_not_two_sample_calls(i):
    s=Session(i);s.to_final();start=s.c.final_full_frame
    for delta in (1,15):
        s.frame=start+delta-1
        assert s.call(final())["available_actions"]==["wait"]
        assert not s.c.final_ack and s.c.final_full_frame==start
    s.frame=start+15;s.action(final())
    assert s.c.final_ack


@pytest.mark.parametrize("i",INTENTS)
@pytest.mark.parametrize("interruption",["blank","partial","old_prompt","scroll"])
def test_final_stable_sixteen_frames_restart_after_any_nonfull_source_page(i,interruption):
    s=Session(i);s.to_final();start=s.c.final_full_frame
    if interruption=="blank":r=None
    elif interruption=="partial":
        r=final();r[16][8:19]=[" "]*11
    elif interruption=="old_prompt":r=first()
    else:r=page("Bingo!","The CARD KEY",scroll=True)
    s.frame=start+15
    assert s.call(r)["available_actions"]==["wait"] and s.c.final_full_frame is None
    assert s.call(final())["available_actions"]==["wait"]
    restarted=s.c.final_full_frame
    s.frame=restarted+14
    assert s.call(final())["available_actions"]==["wait"] and not s.c.final_ack
    s.action(final());assert s.c.final_ack


@pytest.mark.parametrize("i",INTENTS)
def test_decoder_transition_clears_done_stability_and_reviews_without_a(i):
    s=Session(i);s.to_final();t=packet(final())
    t.update(read_valid=False,alignment_verified=False,read_error="visible_tile_alignment_incomplete")
    review(s.call(text=t))
    assert s.c.final_full_frame is None and not s.c.final_ack

