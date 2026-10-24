"""Lapras正常贈送source-only合成測試；不操作遊戲／ROM／state。"""
from copy import deepcopy
from types import SimpleNamespace
import pytest

from laya_pokemon.lapras_gift import (
    LaprasGiftController, read_lapras_gift, INTENT, SOURCE_COMMIT, PROFILE,
    TEXT_PROFILE, SDK_ANCHORS, MAX_WAITS,
)
LOC=dict(map_id=212,x=2,y=5,facing="left",facing_raw=8)
INTRO=[
 ("Oh! Hi! You're","not a ROCKET! You"),
 ("not a ROCKET! You","came to save us?"),
 ("came to save us?","Why, thank you!"),
 ("I want you to","have this POKéMON"),
 ("have this POKéMON","for saving us.")]
DESC=[
 ("It's LAPRAS. It's","very intelligent."),
 ("We kept it in our","lab, but it will"),
 ("lab, but it will","be much better"),
 ("be much better","off with you!"),
 ("I think you will","be a good trainer"),
 ("be a good trainer","for LAPRAS!"),
 ("It's a good","swimmer. It'll"),
 ("swimmer. It'll","give you a lift!")]
Q=("Do you want to","give a nickname")
N=("give a nickname","to LAPRAS?")
SDK=SimpleNamespace(**SDK_ANCHORS,MAPS={"silph_co_7f":212})


def progress():
    specs=[(132,"SNORLAX",35,168,[29,133,156,34],[15,20,10,15]),
           (7,"NIDOKING",36,121,[61,57,30,40],[20,15,25,35]),
           (102,"EEVEE",35,90,[33,28,98,39],[35,15,30,30]),
           (154,"VENUSAUR",35,111,[75,15,73,22],[25,30,10,10]),
           (35,"FEAROW",35,108,[64,65,43,31],[35,20,30,20])]
    return dict(profile="gen1-wrapper-ram-progress-v1-unvalidated",party_read_valid=True,
        initialization_candidate=True,party_count=5,money=40000,player_name_raw="KEVIN",badges_raw=31,
        inventory=[dict(item=48,quantity=1),dict(item=198,quantity=1),dict(item=199,quantity=1)],
        party=[dict(species=s,species_name=n,level=lv,exp=lv**3,hp=hp,max_hp=hp,status=0,moves=m,pp=p)
               for s,n,lv,hp,m,p in specs])


def raw_mon(m,dvs=(0,0)):
    r=[0]*44
    r[0]=m["species"];r[1:3]=list(m["hp"].to_bytes(2,"big"));r[4]=m["status"]
    r[8:12]=m["moves"];r[14:17]=list(m["exp"].to_bytes(3,"big"))
    r[27:29]=dvs;r[29:33]=m["pp"];r[33]=m["level"]
    r[34:36]=list(m["max_hp"].to_bytes(2,"big"))
    return r


def native_name(s):
    assert len(s)<=10
    return [ord(c)-65+0x80 for c in s]+[0x50]*(11-len(s))


def new_lapras(dvs=(0xAA,0xBB)):
    a,b=dvs;dv=((a>>4&1)<<3)|((a&1)<<2)|((b>>4&1)<<1)|(b&1)
    hp=2*(130+dv)*15//100+25
    m=dict(species=19,species_name="LAPRAS",level=15,exp=4218,hp=hp,max_hp=hp,
           status=0,moves=[55,45,0,0],pp=[25,40,0,0])
    return m,raw_mon(m,dvs)


def cells(lines=(),arrow=False,scroll=False,cursor=None):
    out=[[" "]*20 for _ in range(18)]
    for y,s in zip((13,15) if scroll else (14,16),lines):
        row=[];j=0
        while j<len(s):
            if s[j:j+2] in ("'r","'s","'l"):
                row.append(s[j:j+2]);j+=2
            else:row.append(s[j]);j+=1
        assert len(row)<=18
        out[y][1:1+len(row)]=row
    if arrow:out[16][18]="▼"
    if cursor:
        out[8][16:19]=list("YES");out[10][16:18]=list("NO")
        out[cursor][15]="▶"
    return out


def packet(rows=None,window=True,summary=False):
    rows=deepcopy(cells() if rows is None else rows)
    t=dict(profile=TEXT_PROFILE,read_valid=True,alignment_verified=True,read_error=None,
           window_visible=window,cells=rows)
    if summary:
        import re
        pairs=[(y,"".join(r).rstrip()) for y,r in enumerate(rows)
               if re.search(r"[A-Za-z0-9]{2,}","".join(r))][:12]
        t.update(lines=[r for _,r in pairs],line_rows=[y for y,_ in pairs])
    return t


class Session:
    def __init__(self,order=None):
        self.p=progress()
        if order:self.p["party"]=[self.p["party"][i] for i in order]
        self.old=deepcopy(self.p);self.frame=0;self.now=0.
        self.c=LaprasGiftController(deepcopy(INTENT))
        self.s=dict(profile=PROFILE,source_commit=SOURCE_COMMIT,read_valid=True,unknown_reason=None,
            live_calibrated=False,observation_frame=0,location=dict(map_id=212,x=2,y=5),
            raw_flags=0xA8,got_lapras=False,party_count=5,
            party_species=[m["species"] for m in self.p["party"]],
            prefix_mons_raw=sum([raw_mon(m) for m in self.p["party"]],[]),
            prefix_ot_raw=native_name("KEVIN")*5,
            prefix_nicks_raw=sum([native_name(m["species_name"]) for m in self.p["party"]],[]),
            new_mon_raw=None,new_ot_raw=None,new_nickname_raw=None)

    def call(self,rows=None,*,same=False,ready=False,window=True,**kw):
        if not same:self.frame+=1
        self.now+=.1
        s=deepcopy(self.s);s["observation_frame"]=self.frame
        return self.c.context(kw.pop("text",packet(rows,window)),kw.pop("progress",self.p),
            location=kw.pop("location",LOC),battle_state=kw.pop("battle_state",dict(kind="none",active=False,raw=0)),
            gift_signal=kw.pop("gift_signal",s),frame=kw.pop("frame",self.frame),
            now=kw.pop("now",self.now),overworld_ready=ready,**kw)

    def action(self,rows=None,action="a",**kw):
        out=self.call(rows,**kw)
        assert out["available_actions"]==[action,"wait"],out
        return out

    def start(self):self.action(ready=True,window=False)

    def intro(self):
        self.start()
        for p in INTRO:self.action(cells(p,True))
        assert self.c.stage=="gift"

    def begin_askname(self):
        self.intro()
        assert self.call(cells(("KEVIN got","LAPRAS!")))["available_actions"]==["wait"]
        self.s.update(party_count=6,party_species=self.s["party_species"]+[19],
                      new_mon_raw=[0]*44,new_ot_raw=native_name("KEVIN"),new_nickname_raw=[0]*11)
        self.p.update(party_count=6,party=[],party_read_valid=False,initialization_candidate=False)
        self.action(cells(Q,True))
        assert self.c.stage=="nickname"

    def no(self):
        self.begin_askname()
        self.action(cells(N,cursor=8),action="down")
        self.action(cells(N,cursor=10))
        assert self.c.no_issued and self.c.stage=="post_no"

    def fill_new(self,dvs=(0xAA,0xBB)):
        m,raw=new_lapras(dvs)
        self.s.update(new_mon_raw=raw,new_nickname_raw=native_name("LAPRAS"))
        self.p.update(party=deepcopy(self.old["party"])+[m],party_read_valid=True,initialization_candidate=True)

    def description(self):
        self.no();self.fill_new()
        for p in DESC[:-1]:self.action(cells(p,True))
        assert self.c.index==7 and self.c.stage=="description"

    def closing(self):
        self.description();self.s.update(got_lapras=True,raw_flags=0xA9)
        assert self.call(cells(DESC[-1]))["available_actions"]==["wait"]
        self.frame+=15;self.action(cells(DESC[-1]))
        assert self.c.stage=="closing"

    def complete(self):
        self.closing();assert self.call(ready=True,window=False)["available_actions"]==["wait"]
        out=self.call(ready=True,window=False);assert out["lapras_gift_complete"]
        return out


def review(out):
    assert out["phase"]=="campaign_review" and out["available_actions"]==["wait"],out


@pytest.mark.parametrize("order",[None,[1,4,2,0,3]])
def test_complete_gift_append_one_no_nickname_flag_and_two_closed_frames(order):
    s=Session(order);out=s.complete()
    assert s.p["party"][:5]==s.old["party"] and s.p["inventory"]==s.old["inventory"]
    assert s.p["money"]==40000 and out["species"]==19 and out["level"]==15
    assert out["nickname"]=="LAPRAS" and out["exp"]==4218 and out["party_slot"]==6
    assert s.c.baseline["party"]==s.old["party"] and s.c.new_member["mon"]==s.p["party"][5]
    assert s.call(ready=True,window=False)["lapras_gift_complete"]


@pytest.mark.parametrize("dvs",[(0,0),(255,255),(0x10,0),(0,1),(0,0x10),(1,0),(0xAB,0xCD)])
def test_real_new_hp_is_computed_from_observed_dvs_not_filled_from_old_party(dvs):
    s=Session();s.no();s.fill_new(dvs)
    out=s.action(cells(DESC[0],True))
    assert out["available_actions"]==["a","wait"]
    assert 64<=s.c.new_member["mon"]["hp"]<=68 and s.c.new_member["mon"]["hp"]==s.p["party"][5]["hp"]


@pytest.mark.parametrize("mutation",[
    lambda p:p.update(party_count=6),
    lambda p:p.update(party_read_valid=False),
    lambda p:p.update(initialization_candidate=False),
    lambda p:p.update(profile="wrong"),
    lambda p:p.update(player_name_raw="RED"),
    lambda p:p["party"][0].update(species=19,species_name="LAPRAS"),
    lambda p:p["party"][0].update(pp=[255,20,10,15]),
])
def test_initial_source_five_and_kevin_identity_required(mutation):
    s=Session();mutation(s.p);review(s.call(ready=True,window=False))


@pytest.mark.parametrize("bad",["flag","six","raw_hp","species_list","menu","missing_init"])
def test_initial_cannot_claim_existing_gift_or_mismatching_raw_baseline(bad):
    s=Session();t=packet(window=False)
    if bad=="flag":s.s.update(raw_flags=0xA9,got_lapras=True)
    elif bad=="six":s.s["party_count"]=6;s.s["party_species"].append(19)
    elif bad=="raw_hp":s.s["prefix_mons_raw"][2]-=1
    elif bad=="species_list":s.s["party_species"].reverse()
    elif bad=="menu":t=packet(cells(N,cursor=10),False)
    else:s.p.pop("initialization_candidate")
    review(s.call(text=t,ready=True))


@pytest.mark.parametrize("field,value",[("map_id",211),("x",3),("y",6),("facing","up"),("facing_raw",4),("facing_raw",True)])
def test_fixed_npc_stance_not_navigation(field,value):
    s=Session();loc={**LOC,field:value};review(s.call(ready=True,window=False,location=loc))


@pytest.mark.parametrize("field,value",[("species",102),("map_id",132),("decline_nickname",1),("level",16),("kind","capture")])
def test_exact_intent_and_owner_not_generic(field,value):
    i={**INTENT,field:value}
    with pytest.raises(ValueError):LaprasGiftController(i)
    s=Session();s.c.intent[field]=value;review(s.call(ready=True,window=False))


@pytest.mark.parametrize("mutation",[
    lambda s:s.s["prefix_mons_raw"].__setitem__(2,100),
    lambda s:s.s["prefix_ot_raw"].__setitem__(0,0x81),
    lambda s:s.s["prefix_nicks_raw"].__setitem__(0,0x81),
    lambda s:s.p["inventory"].reverse(),
    lambda s:s.p["inventory"][0].update(quantity=2),
    lambda s:s.p.update(money=39800),
    lambda s:s.p.update(badges_raw=63),
    lambda s:s.p.update(player_name_raw="KEVINX"),
])
def test_askname_invalid_sixth_is_allowed_only_with_old_raw_prefix_exact(mutation):
    s=Session();s.begin_askname();base=deepcopy(s.c.baseline);mutation(s)
    review(s.call(cells(N,cursor=8)));assert s.c.baseline==base


def test_askname_does_not_require_fake_valid_sixth_struct_to_select_no():
    s=Session();s.begin_askname()
    assert s.p["party"]==[] and s.p["party_read_valid"] is False and s.s["new_mon_raw"]==[0]*44
    s.action(cells(N,cursor=8),action="down");s.action(cells(N,cursor=10))
    assert s.c.new_member is None
    # NO後原生15幀選單返回期仍可空白/舊選單等待，不偽造第6struct。
    assert s.call()["available_actions"]==["wait"]
    s.fill_new();s.action(cells(DESC[0],True))
    assert s.c.new_member is not None


@pytest.mark.parametrize("bad",["count5_invalid","unknown_party_nonempty","wrong_init","count7","count_revert","early_append"])
def test_unknown_party_not_loosely_treated_as_known_transition(bad):
    s=Session()
    if bad=="early_append":
        s.start();s.s.update(party_count=6,party_species=s.s["party_species"]+[19],
            new_mon_raw=[0]*44,new_ot_raw=[0]*11,new_nickname_raw=[0]*11)
        s.p.update(party_count=6,party=[],party_read_valid=False,initialization_candidate=False)
    else:
        s.begin_askname()
        if bad=="count5_invalid":s.p["party_count"]=5
        elif bad=="unknown_party_nonempty":s.p["party"]=[{}]
        elif bad=="wrong_init":s.p["initialization_candidate"]=True
        elif bad=="count7":s.p["party_count"]=7;s.s["party_count"]=7
        else:s.s.update(party_count=5,party_species=s.s["party_species"][:5],
                       new_mon_raw=None,new_ot_raw=None,new_nickname_raw=None);s.p=deepcopy(s.old)
    review(s.call())


@pytest.mark.parametrize("where",["intro","question","description"])
def test_prompt_full_without_arrow_is_not_advance(where):
    s=Session()
    if where=="intro":s.start();p=INTRO[0]
    elif where=="question":
        s.begin_askname()
        # 已確認的舊question，沒有箭頭也不得重送。
        p=Q
    else:s.no();s.fill_new();p=DESC[0]
    out=s.call(cells(p));assert out["available_actions"]==["wait"] and s.c.error is None
    if where=="intro":assert s.c.index==0


@pytest.mark.parametrize("bad",["before_receipt","no_slot6","future_page","no_own_down"])
def test_nickname_requires_exact_own_receipt_sequence_and_direction(bad):
    s=Session()
    if bad=="before_receipt":
        s.intro();s.s.update(party_count=6,party_species=s.s["party_species"]+[19],
            new_mon_raw=[0]*44,new_ot_raw=[0]*11,new_nickname_raw=[0]*11)
        s.p.update(party_count=6,party=[],party_read_valid=False,initialization_candidate=False)
        review(s.call(cells(Q,True)))
    elif bad=="no_slot6":
        s.intro();s.call(cells(("KEVIN got","LAPRAS!")));review(s.call(cells(Q,True)))
    elif bad=="future_page":s.start();review(s.call(cells(INTRO[1],True)))
    else:s.begin_askname();review(s.call(cells(N,cursor=10)))


@pytest.mark.parametrize("change",["extra_no","not_label","missing_yes","wrong_cursor","inactive","unknown","offset","other_species"])
def test_full_unique_native_yes_no_and_question_required_before_a(change):
    s=Session();s.begin_askname();r=cells(N,cursor=8)
    if change=="extra_no":r[0][0:2]=list("NO")
    elif change=="not_label":r[10][18]="T"
    elif change=="missing_yes":r[8][16:19]=[" "]*3
    elif change=="wrong_cursor":r[8][15]=" ";r[9][15]="▶"
    elif change=="inactive":r[8][15]="▷"
    elif change=="unknown":r[0][0]="X"
    elif change=="offset":r[10]=[" "]*20;r[10][15:17]=list("NO")
    else:r[16][4:10]=list("EEVEE?")
    out=s.call(r)
    assert out["available_actions"]==["wait"] and not s.c.no_issued


def test_direction_and_no_pending_survive_blank_old_page_without_resend():
    s=Session();s.begin_askname();s.action(cells(N,cursor=8),action="down")
    for r in (None,cells(N,cursor=8),None):
        assert s.call(r)["available_actions"]==["wait"]
    s.action(cells(N,cursor=10))
    for r in (None,cells(N,cursor=10),cells(N,cursor=8)):
        assert s.call(r)["available_actions"]==["wait"]
    assert s.c.no_issued and s.c.new_member is None


@pytest.mark.parametrize("which",["intro","question","description"])
def test_exact_cont_scroll_rows_allowed_only_as_wait(which):
    s=Session()
    if which=="intro":s.start();s.action(cells(INTRO[0],True));p=INTRO[0]
    elif which=="question":s.begin_askname();p=Q
    else:s.no();s.fill_new();s.action(cells(DESC[0],True));s.action(cells(DESC[1],True));p=DESC[1]
    assert s.call(cells(p,scroll=True))["available_actions"]==["wait"] and s.c.error is None


@pytest.mark.parametrize("kind",["r","s","l"])
def test_native_contractions_are_single_cells_and_ascii_expansion_not_accepted(kind):
    s=Session()
    if kind=="r":s.start();p=INTRO[0];r=cells(p,True);target="'r"
    else:s.no();s.fill_new();p=DESC[0] if kind=="s" else DESC[6];r=cells(p,True);target="'s" if kind=="s" else "'l"
    # 單格縮寫在固定template才能用；額外任意位置無法按。
    pos=next((x,y) for y,row in enumerate(r) for x,c in enumerate(row) if c==target)
    x,y=pos;r[y][x:x+1]=list(target);r[y]=r[y][:20]
    review(s.call(r))


@pytest.mark.parametrize("field,value",[("profile","wrong"),("read_valid",False),("alignment_verified",False),
    ("read_error","visible_tile_alignment_incomplete"),("window_visible",None)])
def test_native_proof_required(field,value):
    s=Session();t=packet(window=False);t[field]=value;review(s.call(text=t,ready=True))


@pytest.mark.parametrize("badcell",[None,[],{},1,"'m","XX"])
def test_unknown_or_nonstring_cell_never_throws_or_a(badcell):
    s=Session();t=packet(window=False);t["cells"][0][0]=badcell;review(s.call(text=t,ready=True))


@pytest.mark.parametrize("change",["species","level","hp","max_hp","exp","status","moves","pp","ev","nickname","ot","progress_only"])
def test_new_lapras_must_match_real_raw_and_exact_source_after_no(change):
    s=Session();s.no();s.fill_new()
    if change=="species":s.s["new_mon_raw"][0]=102
    elif change=="level":s.s["new_mon_raw"][33]=16
    elif change=="hp":s.s["new_mon_raw"][2]-=1
    elif change=="max_hp":s.s["new_mon_raw"][35]+=1
    elif change=="exp":s.s["new_mon_raw"][16]+=1
    elif change=="status":s.s["new_mon_raw"][4]=8
    elif change=="moves":s.s["new_mon_raw"][8]=57
    elif change=="pp":s.s["new_mon_raw"][29]=24
    elif change=="ev":s.s["new_mon_raw"][18]=1
    elif change=="nickname":s.s["new_nickname_raw"]=native_name("KEVIN")
    elif change=="ot":s.s["new_ot_raw"]=native_name("RED")
    else:s.p["party"][5]["exp"]=4219
    out=s.call(cells(DESC[0],True))
    review(out)
    assert s.c.new_member is None


def test_valid_new_member_cannot_mutate_disappear_or_duplicate_after_observed():
    s=Session();s.no();s.fill_new();s.action(cells(DESC[0],True))
    s.p["party"][5]["hp"]-=1;review(s.call())


@pytest.mark.parametrize("bad",["flag_early","unrelated_flags","flag_revert","old_party","sixth_revert"])
def test_flag_and_native_append_are_not_false_completion(bad):
    s=Session()
    if bad=="flag_early":s.start();s.s.update(got_lapras=True,raw_flags=0xA9)
    elif bad=="unrelated_flags":s.start();s.s["raw_flags"]^=2
    elif bad=="flag_revert":
        s.description();s.s.update(got_lapras=True,raw_flags=0xA9);s.call(cells(DESC[-1]))
        s.s.update(got_lapras=False,raw_flags=0xA8)
    elif bad=="old_party":s.no();s.fill_new();s.p["party"][0]["hp"]-=1
    else:
        s.no();s.fill_new();s.action(cells(DESC[0],True))
        s.s.update(party_count=5,party_species=s.s["party_species"][:5],new_mon_raw=None,
            new_ot_raw=None,new_nickname_raw=None);s.p=deepcopy(s.old)
    review(s.call())


def test_final_done_needs_flag_and_continuous_sixteen_emulator_frames():
    s=Session();s.description()
    assert s.call(cells(DESC[-1]))["available_actions"]==["wait"] and s.c.done_start is None
    s.s.update(got_lapras=True,raw_flags=0xA9)
    s.call(cells(DESC[-1]));start=s.c.done_start
    for d in (1,15):
        s.frame=start+d-1
        assert s.call(cells(DESC[-1]))["available_actions"]==["wait"] and s.c.stage=="description"
    s.frame=start+15;s.action(cells(DESC[-1]))
    for r in (None,cells(DESC[-1]),cells(DESC[-1])):
        assert s.call(r)["available_actions"]==["wait"]


@pytest.mark.parametrize("interrupt",["blank","partial","old_page","scroll"])
def test_final_stability_resets_on_any_nonfull_source_page(interrupt):
    s=Session();s.description();s.s.update(got_lapras=True,raw_flags=0xA9)
    s.call(cells(DESC[-1]));start=s.c.done_start
    if interrupt=="blank":r=None
    elif interrupt=="partial":
        r=cells(DESC[-1]);r[16][5:19]=[" "]*14
    elif interrupt=="old_page":r=cells(DESC[-2],True)
    else:r=cells(DESC[-2],scroll=True)
    s.frame=start+15;assert s.call(r)["available_actions"]==["wait"] and s.c.done_start is None
    s.call(cells(DESC[-1]));s.frame+=15;s.action(cells(DESC[-1]))


def test_closed_world_requires_two_consecutive_full_receipts():
    s=Session();s.closing();s.call(ready=True,window=False)
    s.call(cells(DESC[-1]))
    assert not s.call(ready=True,window=False).get("lapras_gift_complete")
    assert s.call(ready=True,window=False)["lapras_gift_complete"]


@pytest.mark.parametrize("where",["initial","prompt","menu","final"])
def test_same_frame_cannot_repeat_or_change_packet(where):
    s=Session()
    if where=="initial":s.start();r=None;kw=dict(ready=True,window=False)
    elif where=="prompt":s.start();s.action(cells(INTRO[0],True));r=cells(INTRO[0],True);kw={}
    elif where=="menu":s.begin_askname();s.action(cells(N,cursor=8),action="down");r=cells(N,cursor=8);kw={}
    else:s.closing();r=cells(DESC[-1]);kw={}
    assert s.call(r,same=True,**kw)["available_actions"]==["wait"]
    t=packet(r,kw.get("window",True));t["cells"][0][0]="X"
    review(s.call(same=True,text=t,**kw))


@pytest.mark.parametrize("bad",["backframe","boolframe","backclock","nan","timeout","calls","waits"])
def test_clock_and_cumulative_budgets_are_not_reset_by_action(bad):
    s=Session();s.start()
    if bad=="backframe":kw=dict(frame=0)
    elif bad=="boolframe":kw=dict(frame=True)
    elif bad=="backclock":kw=dict(now=0)
    elif bad=="nan":kw=dict(now=float("nan"))
    elif bad=="timeout":kw=dict(now=61)
    elif bad=="calls":s.c.calls=240;kw={}
    else:s.c.waits=MAX_WAITS;kw={}
    review(s.call(**kw))


class Memory:
    def __init__(self,data,hook=None):self.data=data;self.hook=hook;self.reads=[]
    def __getitem__(self,a):
        self.reads.append(a)
        return self.hook(self,a,len(self.reads)) if self.hook else self.data[a]
    def __setitem__(self,*a):raise AssertionError("no writes")


def fake():
    s=Session()
    d={0xD72E:0xA8,0xD35E:212,0xD361:5,0xD362:2,0xD163:5}
    for a,v in enumerate(s.s["party_species"]+[255,0],0xD164):d[a]=v
    for a,v in enumerate(s.s["prefix_mons_raw"]+[0]*44,0xD16B):d[a]=v
    for a,v in enumerate(s.s["prefix_ot_raw"]+[0]*11,0xD273):d[a]=v
    for a,v in enumerate(s.s["prefix_nicks_raw"]+[0]*11,0xD2B5):d[a]=v
    return SimpleNamespace(memory=Memory(d),frame_count=77),s


def test_reader_source_sdk_sameframe_double_read_and_no_setter():
    p,s=fake();loc=dict(map_id=212,x=2,y=5)
    r=read_lapras_gift(p,observation_frame=77,expected_location=loc,constants=SDK)
    assert r["read_valid"] and not r["got_lapras"] and r["party_count"]==5
    assert r["prefix_mons_raw"]==s.s["prefix_mons_raw"] and r["new_mon_raw"] is None
    assert len(p.memory.reads)==816 and p.memory.reads[:408]==p.memory.reads[408:]
    p.memory.data[0xD72E]|=1
    assert read_lapras_gift(p,observation_frame=77,expected_location=loc,constants=SDK)["got_lapras"]


@pytest.mark.parametrize("value",[None,True,-1,256,"0",1.5])
def test_reader_invalid_byte_anywhere_is_not_gift_false(value):
    p,s=fake();p.memory.data[0xD16B]=value
    r=read_lapras_gift(p,observation_frame=77,expected_location=dict(map_id=212,x=2,y=5),constants=SDK)
    assert not r["read_valid"] and "got_lapras" not in r


@pytest.mark.parametrize("bad",["flags_anchor","party_anchor","size","map_id","count","species","sentinel",
    "wrong_map","wrong_x","torn","frame_changed","getter","frame_getter","sdk_getter"])
def test_reader_unknown_source_or_torn_snapshot_is_unknown(bad):
    p,s=fake();c=deepcopy(SDK)
    if bad=="flags_anchor":c.STATUS_FLAGS3_ADDRESS=0xD72C
    elif bad=="party_anchor":c.PARTY_MONS_ADDRESS=0xD16C
    elif bad=="size":c.PARTY_MON_SIZE=True
    elif bad=="map_id":c.MAPS["silph_co_7f"]=211
    elif bad=="count":p.memory.data[0xD163]=4
    elif bad=="species":p.memory.data[0xD164]=19
    elif bad=="sentinel":p.memory.data[0xD169]=0
    elif bad=="wrong_map":p.memory.data[0xD35E]=235
    elif bad=="wrong_x":p.memory.data[0xD362]=3
    elif bad=="torn":
        p.memory.hook=lambda m,a,n:(m.data[a]^1) if n>408 and a==0xD72E else m.data[a]
    elif bad=="frame_changed":
        def hook(m,a,n):
            if n==816:p.frame_count+=1
            return m.data[a]
        p.memory.hook=hook
    elif bad=="getter":
        def hook(m,a,n):raise RuntimeError("unknown")
        p.memory.hook=hook
    elif bad=="frame_getter":
        class Broken:
            @property
            def frame_count(self):raise RuntimeError("unknown")
        p=Broken()
    else:
        class Broken:
            @property
            def STATUS_FLAGS3_ADDRESS(self):raise RuntimeError("unknown")
        c=Broken()
    r=read_lapras_gift(p,observation_frame=77,expected_location=dict(map_id=212,x=2,y=5),constants=c)
    assert not r["read_valid"] and "got_lapras" not in r


def test_official_sdk_source_anchors_and_native_multichar_cells():
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as c
    for k,v in SDK_ANCHORS.items():assert getattr(c,k)==v
    assert c.MAPS["silph_co_7f"]==212
    assert c.POKEMON_TEXT_DECODING[0xe4]=="'r"
    assert c.POKEMON_TEXT_DECODING[0xbd]=="'s"
    assert c.POKEMON_TEXT_DECODING[0xbc]=="'l"

