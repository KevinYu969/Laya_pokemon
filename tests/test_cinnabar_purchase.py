"""Independent source-layout fixtures; no emulator, model, ROM, or live state."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

import laya_pokemon
REPO = Path(laya_pokemon.__file__).resolve().parents[2]
STAGE = REPO / '.local/staged-cinnabar-purchase-20261024'

def source_path(test_path):
    p = Path(test_path).resolve()
    if p == STAGE / 'test_cinnabar_purchase.py':
        return STAGE / 'cinnabar_purchase.py'
    if p == REPO / 'tests/test_cinnabar_purchase.py':
        return REPO / 'src/laya_pokemon/cinnabar_purchase.py'
    raise RuntimeError('Only the specified staged or formal tests path is allowed')

spec = importlib.util.spec_from_file_location("staged_cinnabar_purchase", source_path(__file__))
cp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cp)

# Independent literal fixtures from a536 marts/prices/list_menu/pokemart.
STOCK = [("ULTRA BALL",1200),("GREAT BALL",600),("HYPER POTION",1500),
         ("MAX REPEL",700),("ESCAPE ROPE",550),("FULL HEAL",600),("REVIVE",1500)]
INTENTS = [cp.HYPER_POTION_INTENT, cp.FULL_HEAL_INTENT]
LOC = {"map_id":172,"x":2,"y":5,"facing":"left","facing_raw":8}
NONBATTLE = {"raw":0,"kind":"none","active":False}


def progress():
    names = [(19,"LAPRAS"),(132,"SNORLAX"),(7,"NIDOKING"),(102,"EEVEE"),
             (154,"VENUSAUR"),(35,"FEAROW")]
    return {"profile":"gen1-wrapper-ram-progress-v1-unvalidated",
            "initialization_candidate":True,"party_read_valid":True,"party_count":6,
            "money":69332,"inventory":[{"item":4,"quantity":6},{"item":49,"quantity":1},
                                      {"item":197,"quantity":1},{"item":43,"quantity":1}],
            "party":[dict(species=s,species_name=n,level=38,exp=60000,hp=150,
                          max_hp=150,status=0,moves=[33,0,0,0],pp=[35,0,0,0])
                     for s,n in names]}


def native(money=69332, *, view="main", offset=0, cursor=0, active=True,
           q=10, item=18, words="buying", arrow=False, yes=None):
    a=[[" "]*20 for _ in range(18)]
    def at(x,y,s): a[y][x:x+len(s)] = list(s)
    def erase(x1,y1,x2,y2):
        for y in range(y1,y2+1): a[y][x1:x2+1] = [" "]*(x2-x1+1)
    for label,y in [("BUY",1),("SELL",3),("QUIT",5)]:at(2,y,label)
    at(13,0,"MONEY");at(12,1,("¥"+str(money)).rjust(7))
    at(1,1,"▶" if view=="main" and active else "▷")
    if view!="main":
        erase(4,2,19,12)
        for j,(name,cost) in enumerate(STOCK[offset:offset+4]):
            at(6,4+2*j,name);at(11,5+2*j,("¥"+str(cost)).rjust(7))
        at(5,4+2*cursor,"▶" if view=="shop" and active else "▷")
        if view=="shop" and arrow:at(18,11,"▼")
    cost=1500 if item==18 else 600
    if view in ("quantity","yesno"):
        erase(7,9,19,11);at(8,10,"×"+str(q).zfill(2))
        at(12,10,("¥"+str(q*cost)).rjust(7))
    if view=="yesno":
        erase(14,7,19,11);at(16,8,"YES");at(16,10,"NO")
        at(15,8 if yes in (None,0) else 10,"▶")
    label="HYPER POTION" if item==18 else "FULL HEAL"
    texts={"greeting":("HI THERE!","MAY I HELP YOU?"),"buying":("TAKE YOUR TIME.",""),
           "prefix":(label+"?","THAT WILL BE"),"tail":("THAT WILL BE","¥"+str(q*cost)+". OK?"),
           "bought":("HERE YOU ARE!","THANK YOU!"),"else":("IS THERE ANYTHING","ELSE I CAN DO?"),
           "thanks":("THANK YOU!","")}
    erase(0,12,19,17);at(1,14,texts[words][0]);at(1,16,texts[words][1])
    if arrow and words in ("prefix","bought"):at(18,16,"▼")
    return a


def text(cells=None, *, window=True):
    return {"profile":cp.TEXT_PROFILE,"read_valid":True,"alignment_verified":True,
            "read_error":None,"window_visible":window,
            "cells":deepcopy(cells if cells is not None else [[" "]*20 for _ in range(18)])}


class Session:
    def __init__(self,intent=cp.HYPER_POTION_INTENT, **budget):
        self.intent=deepcopy(intent);self.c=cp.CinnabarPurchaseController(self.intent,**budget)
        self.p=progress();self.frame=0;self.now=0.;self.prev=[]
        self.off=0 if self.intent["item"]==18 else 3
        self.cost=self.intent["total_price"];self.item=self.intent["item"]
        self.before=deepcopy(self.p);self.last_kwargs=None
    def call(self,cells=None, *, window=True, ready=False, advance=40, **overrides):
        if self.last_kwargs is not None:self.frame+=advance;self.now+=.1
        kw=dict(text=text(cells,window=window),progress=deepcopy(self.p),
                location=deepcopy(LOC),battle_state=deepcopy(NONBATTLE),
                frame=self.frame,now=self.now,previous=list(self.prev),overworld_ready=ready)
        kw.update(overrides);self.last_kwargs=deepcopy(kw)
        r=self.c.context(**kw)
        self.prev=[r["available_actions"][0]]
        return r
    def row(self,**kw):
        return native(self.p["money"],item=self.item,**kw)
    def start(self):
        assert self.call(window=False,ready=True)["available_actions"][0]=="a"
        assert self.call(self.row(words="greeting"))["available_actions"][0]=="a"
    def choose(self):
        self.start();off=cur=0
        r=self.call(self.row(view="shop",offset=off,cursor=cur,arrow=True))
        target=2 if self.item==18 else 5
        for _ in range(target):
            assert r["available_actions"][0]=="down"
            if cur<2:cur+=1
            else:off+=1
            r=self.call(self.row(view="shop",offset=off,cursor=cur,arrow=True))
        assert r["available_actions"][0]=="a"
        assert (off,cur)==(self.off,2)
    def quantity(self):
        self.choose()
        for q in range(1,11):
            r=self.call(self.row(view="quantity",offset=self.off,cursor=2,q=q))
            assert r["available_actions"][0]==("up" if q<10 else "a")
    def confirm(self, *, no_first=False):
        self.quantity()
        r=self.call(self.row(view="quantity",offset=self.off,cursor=2,words="prefix"))
        assert r["available_actions"]==["wait"]  # full text is before real cont prompt
        r=self.call(self.row(view="quantity",offset=self.off,cursor=2,words="prefix",arrow=True))
        assert r["available_actions"][0]=="a"
        if no_first:
            r=self.call(self.row(view="yesno",offset=self.off,cursor=2,words="tail",yes=1))
            assert r["available_actions"][0]=="up"
        r=self.call(self.row(view="yesno",offset=self.off,cursor=2,words="tail",yes=0))
        assert r["available_actions"][0]=="a"
    def observe_purchase(self):
        match=next((x for x in self.p["inventory"] if x["item"]==self.item),None)
        if match:match["quantity"]+=10
        else:self.p["inventory"].append({"item":self.item,"quantity":10})
        self.p["money"]-=self.cost
    def close(self):
        assert self.call(self.row(view="quantity",offset=self.off,cursor=2,words="bought",arrow=True))["available_actions"][0]=="a"
        # Source retains scroll offset but resets current cursor to zero.
        assert self.call(self.row(view="shop",offset=self.off,cursor=0,arrow=True))["available_actions"][0]=="b"
        assert self.call(self.row(words="else"))["available_actions"][0]=="b"
        assert self.call(self.row(words="thanks",active=False))["available_actions"]==["wait"]
        assert self.call(self.row(words="thanks",active=False),advance=16)["available_actions"][0]=="a"
        assert not self.call(window=False,ready=True).get("cinnabar_purchase_complete")
        return self.call(window=False,ready=True,advance=3)


@pytest.mark.parametrize("intent",INTENTS)
@pytest.mark.parametrize("existing",[0,8])
@pytest.mark.parametrize("no_first",[False,True])
def test_complete_independent_native_flow(intent,existing,no_first):
    s=Session(intent)
    if existing:s.p["inventory"].append({"item":s.item,"quantity":existing})
    old=deepcopy(s.p)
    s.confirm(no_first=no_first);s.observe_purchase();r=s.close()
    assert r["cinnabar_purchase_complete"] is True
    assert r["quantity_purchased"]==10 and r["money_spent"]==intent["total_price"]
    assert s.p["money"]==old["money"]-intent["total_price"]
    assert s.p["party"]==old["party"]
    assert s.p["inventory"]==old["inventory"]+[{"item":s.item,"quantity":10}] if not existing else s.p["inventory"][:-1]==old["inventory"][:-1]
    assert next(i["quantity"] for i in s.p["inventory"] if i["item"]==s.item)==existing+10


@pytest.mark.parametrize("key,value",[("map_id",150),("player_x",1),("player_y",4),
    ("facing","right"),("item",3),("quantity",20),("unit_price",1200),
    ("total_price",12000),("map_id",True),("quantity",10.0),("item",18.0),("kind","buy_any")])
def test_wrong_intent_rejected(key,value):
    intent=deepcopy(cp.HYPER_POTION_INTENT);intent[key]=value
    with pytest.raises(ValueError):cp.CinnabarPurchaseController(intent)


@pytest.mark.parametrize("key,value",[("map_id",173),("x",1),("y",4),("facing","up"),
    ("facing_raw",4),("facing_raw",True)])
def test_stance_rejects_unknown_or_other_map(key,value):
    s=Session();loc={**LOC,key:value}
    r=s.call(window=False,ready=True,location=loc)
    assert r["available_actions"]==["wait"] and "review_reason" in r


@pytest.mark.parametrize("field,value",[("profile","legacy"),("read_valid",False),
    ("alignment_verified",False),("window_visible",None),("read_error","unknown")])
def test_full_decoder_proof_required(field,value):
    s=Session();t=text(window=False);t[field]=value
    assert "review_reason" in s.call(text=t,ready=True)


@pytest.mark.parametrize("case",["money","bag_capacity","stack99","faint","status",
    "party_missing","party_duplicate","inventory_duplicate","unknown_item","party_unreadable"])
def test_baseline_invalid(case):
    s=Session()
    if case=="money":s.p["money"]=19999
    elif case=="bag_capacity":s.p["inventory"]=[{"item":i,"quantity":1} for i in range(1,20)]
    elif case=="stack99":s.p["inventory"].append({"item":18,"quantity":90})
    elif case=="faint":s.p["party"][0]["hp"]=0
    elif case=="status":s.p["party"][0]["status"]=16
    elif case=="party_missing":s.p["party"].pop();s.p["party_count"]=5
    elif case=="party_duplicate":s.p["party"][-1]=deepcopy(s.p["party"][0])
    elif case=="inventory_duplicate":s.p["inventory"].append(deepcopy(s.p["inventory"][0]))
    elif case=="unknown_item":s.p["inventory"].append({"item":44,"quantity":1})
    elif case=="party_unreadable":s.p["party_read_valid"]=False
    assert "review_reason" in s.call(window=False,ready=True)


@pytest.mark.parametrize("mutator",["cursor","foreigncursor","wrongname","wrongprice","offset","extra"])
def test_source_goods_unknown_is_not_a(mutator):
    s=Session(cp.FULL_HEAL_INTENT);s.start()
    a=s.row(view="shop",arrow=True)
    if mutator=="cursor":a[4][5]=" ";a[6][5]="▶"
    elif mutator=="foreigncursor":a[0][0]="▶"
    elif mutator=="wrongname":a[4][6]="X"
    elif mutator=="wrongprice":a[5][17]="9"
    elif mutator=="offset":a=s.row(view="shop",offset=3,arrow=True)
    elif mutator=="extra":a[17][0]="X"
    r=s.call(a);assert "review_reason" in r and r["available_actions"]==["wait"]


@pytest.mark.parametrize("intent",INTENTS)
def test_true_source_third_row_overwrite_by_yesno(intent):
    s=Session(intent);s.quantity()
    s.call(s.row(view="quantity",offset=s.off,cursor=2,words="prefix",arrow=True))
    a=s.row(view="yesno",offset=s.off,cursor=2,words="tail")
    assert "".join(a[8][6:14])==("HYPER PO" if s.item==18 else "FULL HEA")
    assert "".join(a[8][16:19])=="YES"
    assert s.call(a)["available_actions"][0]=="a"


def test_full_heal_after_receipt_keeps_offset3_not_initial_view():
    s=Session(cp.FULL_HEAL_INTENT);s.confirm();s.observe_purchase()
    s.call(s.row(view="quantity",offset=3,cursor=2,words="bought",arrow=True))
    assert "review_reason" in s.call(s.row(view="shop",offset=0,cursor=0,arrow=True))


@pytest.mark.parametrize("q,price_bad",[(9,False),(11,False),(10,True)])
def test_quantity_or_price_wrong_never_confirm(q,price_bad):
    s=Session();s.choose();a=s.row(view="quantity",cursor=2,q=q)
    if price_bad:a[10][18]="9"
    r=s.call(a);assert r["available_actions"]==["wait"] and "review_reason" in r


def test_blank_then_old_quantity_does_not_repeat_direction():
    s=Session();s.choose()
    q1=s.row(view="quantity",cursor=2,q=1)
    assert s.call(q1)["available_actions"][0]=="up"
    assert s.call()["available_actions"]==["wait"]
    for _ in range(3):
        r=s.call(q1);assert r["available_actions"]==["wait"] and not s.c.error
    assert s.call(s.row(view="quantity",cursor=2,q=2))["available_actions"][0]=="up"


def test_scroll_pending_blank_old_page_no_repeat():
    s=Session(cp.FULL_HEAL_INTENT);s.start()
    a=s.row(view="shop",arrow=True)
    assert s.call(a)["available_actions"][0]=="down"
    assert s.call()["available_actions"]==["wait"]
    assert s.call(a)["available_actions"]==["wait"]
    assert s.call(s.row(view="shop",cursor=1,arrow=True))["available_actions"][0]=="down"


def test_no_actual_previous_cannot_consume_offer():
    s=Session();s.call(window=False,ready=True)
    r=s.call(s.row(words="greeting"),previous=[])
    assert "review_reason" in r and not s.c.yes_issued


def test_same_frame_exact_only_wait_but_conflict_reviews():
    s=Session();s.call(window=False,ready=True)
    kw=deepcopy(s.last_kwargs)
    r=s.c.context(**kw);assert r["available_actions"]==["wait"]
    kw["progress"]["money"]-=1
    assert "review_reason" in s.c.context(**kw)


@pytest.mark.parametrize("field",["party","money","inventory"])
def test_data_before_yes_cannot_change(field):
    s=Session();s.start()
    if field=="party":s.p["party"][0]["hp"]-=1
    elif field=="money":s.p["money"]-=1
    else:s.p["inventory"].append({"item":18,"quantity":10})
    assert "review_reason" in s.call(s.row(view="shop",arrow=True))


@pytest.mark.parametrize("case",["money_only","wrong_quantity","wrong_item","party","reverse_order","old_money_after_observed"])
def test_purchase_delta_not_fabricated(case):
    s=Session();s.confirm()
    if case=="money_only":s.p["money"]-=15000
    else:
        s.observe_purchase()
        if case=="wrong_quantity":s.p["inventory"][-1]["quantity"]=9
        elif case=="wrong_item":s.p["inventory"][-1]["item"]=52
        elif case=="party":s.p["party"][0]["exp"]+=1
        elif case=="reverse_order":s.p["inventory"].reverse()
        elif case=="old_money_after_observed":
            assert s.call(s.row(view="quantity",cursor=2,words="bought",arrow=True))["available_actions"][0]=="a"
            s.p["money"]+=15000
    assert "review_reason" in s.call(s.row(view="quantity",cursor=2,words="bought",arrow=True))


def test_source_inventory_before_money_transition_waits_not_claims():
    s=Session();s.confirm()
    s.p["inventory"].append({"item":18,"quantity":10})
    r=s.call(s.row(view="quantity",cursor=2,words="bought",arrow=True))
    assert r["available_actions"]==["wait"] and not s.c.receipt_seen
    s.p["money"]-=15000
    assert s.call(s.row(view="quantity",cursor=2,words="bought",arrow=True))["available_actions"][0]=="a"


@pytest.mark.parametrize("delta,action",[(1,"wait"),(15,"wait"),(16,"a")])
def test_thank_you_full_done_stable16(delta,action):
    s=Session();s.confirm();s.observe_purchase()
    s.call(s.row(view="quantity",cursor=2,words="bought",arrow=True))
    s.call(s.row(view="shop",cursor=0,arrow=True));s.call(s.row(words="else"))
    full=s.row(words="thanks",active=False)
    assert s.call(full)["available_actions"]==["wait"]
    assert s.call(full,advance=delta)["available_actions"][0]==action


def test_thanks_blank_resets_stability():
    s=Session();s.confirm();s.observe_purchase()
    s.call(s.row(view="quantity",cursor=2,words="bought",arrow=True))
    s.call(s.row(view="shop",cursor=0,arrow=True));s.call(s.row(words="else"))
    full=s.row(words="thanks",active=False);s.call(full)
    s.call()
    assert s.call(full,advance=15)["available_actions"]==["wait"]
    assert not s.c.exit_seen


@pytest.mark.parametrize("key,value",[("max_waits",31),("max_waits",True),
    ("max_calls",241),("max_seconds",61),("max_seconds",float("nan"))])
def test_budget_cannot_expand(key,value):
    with pytest.raises(ValueError):cp.CinnabarPurchaseController(cp.HYPER_POTION_INTENT,**{key:value})


def test_cumulative_wait30_and_sticky_error():
    s=Session();s.start();blank=text()
    for _ in range(30):
        assert "review_reason" not in s.call(text=blank)
    r=s.call(text=blank);assert r["review_reason"].endswith("wait_budget_exhausted")
    assert s.call(s.row(view="shop",arrow=True))["review_reason"]==r["review_reason"]


@pytest.mark.parametrize("case",["timeout","negative","backward","framebool","unknownbattle","frame_mismatch"])
def test_clock_frame_battle_safety(case):
    s=Session();s.call(window=False,ready=True)
    kw={}
    if case=="timeout":kw["now"]=60.01
    elif case=="negative":kw["now"]=-1
    elif case=="backward":s.now=3.;s.call(s.row(words="greeting"));kw["now"]=2.
    elif case=="framebool":kw["frame"]=True
    elif case=="unknownbattle":kw["battle_state"]={"raw":None,"active":None,"kind":"unknown"}
    elif case=="frame_mismatch":kw["progress"]={**s.p,"observation_frame":999}
    assert "review_reason" in s.call(s.row(words="greeting"),**kw)


def test_intent_mutation_cannot_reset_owner_or_budget():
    s=Session();s.start()
    old_calls=s.c.calls
    s.c.intent["item"]=52
    r=s.call(s.row(view="shop",arrow=True))
    assert "review_reason" in r and s.c.calls>old_calls and s.c.started==0.


def test_source_receipts_and_scroll_algorithm_are_fixed_primary():
    fixture=json.loads((REPO/"tests/data/lavender-mart-source-fixture.json").read_text(encoding="utf-8"))
    assert fixture["commit"]==cp.SOURCE_COMMIT
    for name in ("home/list_menu.asm","engine/events/pokemart.asm","data/items/marts.asm","data/items/prices.asm"):
        d=fixture["files"][name];assert hashlib.sha256(d["text"].encode()).hexdigest()==d["sha256"]
    text=fixture["files"]["home/list_menu.asm"]["text"]
    assert "ld b, 4 ; print 4 names" in text and "ld a, 2 ; max menu item" in text
    assert "inc [hl] ; if not, go down" in text
    mart=fixture["files"]["engine/events/pokemart.asm"]["text"]
    assert "ld [wCurrentMenuItem], a" in mart and "call AddItemToInventory" in mart

@pytest.mark.parametrize("mode",["both_changed","extra_intent_key","caller_wrong","caller_bool"])
def test_typed_immutable_binding(mode):
    s=Session();s.start();kw={}
    if mode=="both_changed":
        s.c.intent=deepcopy(cp.FULL_HEAL_INTENT);s.c.contract=deepcopy(cp.FULL_HEAL_INTENT)
    elif mode=="extra_intent_key":s.c.intent["owner"]="foreign"
    elif mode=="caller_wrong":kw["intent"]=cp.FULL_HEAL_INTENT
    else:kw["intent"]={**s.intent,"quantity":True}
    r=s.call(s.row(view="shop",arrow=True),**kw)
    assert "review_reason" in r and r["available_actions"]==["wait"]


def test_calls_budget_is_preserved_on_same_instance():
    s=Session(max_calls=1);s.call(window=False,ready=True)
    r=s.call(s.row(words="greeting"))
    assert r["review_reason"].endswith("time_or_call_budget_exhausted")
    assert s.c.calls==2 and s.c.started==0.


@pytest.mark.parametrize("intent",INTENTS)
def test_receipt_without_real_delta_only_waits(intent):
    s=Session(intent);s.confirm()
    full=s.row(view="quantity",offset=s.off,cursor=2,words="bought",arrow=True)
    for _ in range(2):
        r=s.call(full);assert r["available_actions"]==["wait"] and not s.c.receipt_seen
    assert not s.c.complete


@pytest.mark.parametrize("intent",INTENTS)
def test_wrong_confirmation_quantity_or_total_reviews(intent):
    s=Session(intent);s.quantity()
    s.call(s.row(view="quantity",offset=s.off,cursor=2,words="prefix",arrow=True))
    a=s.row(view="yesno",offset=s.off,cursor=2,words="tail")
    a[10][10]="9"
    r=s.call(a)
    assert "review_reason" in r and not s.c.yes_issued


def test_full_heal_receipt_cannot_return_to_selected_cursor2():
    s=Session(cp.FULL_HEAL_INTENT);s.confirm();s.observe_purchase()
    s.call(s.row(view="quantity",offset=3,cursor=2,words="bought",arrow=True))
    r=s.call(s.row(view="shop",offset=3,cursor=2,arrow=True))
    assert "review_reason" in r


@pytest.mark.parametrize("window,ready",[(True,True),(False,False)])
def test_final_blank_without_closed_world_cannot_complete(window,ready):
    s=Session();s.confirm();s.observe_purchase()
    s.call(s.row(view="quantity",cursor=2,words="bought",arrow=True))
    s.call(s.row(view="shop",cursor=0,arrow=True));s.call(s.row(words="else"))
    s.call(s.row(words="thanks",active=False));s.call(s.row(words="thanks",active=False),advance=16)
    for _ in range(2):
        r=s.call(window=window,ready=ready);assert not r.get("cinnabar_purchase_complete")
    assert s.c.world_start is None


@pytest.mark.parametrize("item", [18,52])
def test_keep_tm38_slot_and_accept_exact_stack_capacity(item):
    p=progress();intent=cp.INTENTS[item]
    # Distinct known item IDs, with 18 baseline slots; a new medicine makes19.
    ids=[1,2,3,4,5,6,8,9,10,11,12,13,14,15,16,17,19,20]
    if item==52:
        ids[-1]=18
    p["inventory"]=[{"item":i,"quantity":1} for i in ids]
    assert len(cp.purchase_expectation(p,intent)["inventory"])==19
    p["inventory"].append({"item":49,"quantity":1})
    assert cp.purchase_expectation(p,intent) is None
    p=progress();p["inventory"].append({"item":item,"quantity":89})
    assert cp.purchase_expectation(p,intent)["inventory"][-1]["quantity"]==99
    p["inventory"][-1]["quantity"]=90
    assert cp.purchase_expectation(p,intent) is None




@pytest.mark.parametrize("first_frame", [1732097, 2147483648, 1000000000000])
@pytest.mark.parametrize("intent", INTENTS)
def test_actual_long_campaign_frames_complete(first_frame, intent):
    s = Session(intent)
    s.frame = first_frame
    s.confirm()
    s.observe_purchase()
    assert s.close()["cinnabar_purchase_complete"] is True

@pytest.mark.parametrize("value", [True, False, -1, 1732097.0, 2**63])
def test_frame_not_byte_but_still_typed_and_bounded(value):
    s = Session()
    assert s.call(window=False, ready=True, frame=value)["review_reason"].endswith("clock_or_frame_invalid")

def test_source_path_rejects_unrelated_copy():
    with pytest.raises(RuntimeError):
        source_path(REPO / 'unrelated/test_cinnabar_purchase.py')
