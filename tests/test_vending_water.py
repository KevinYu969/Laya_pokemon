"""獨立固定來源合成販賣機測試；無ROM/存檔/模擬器/遊戲按鍵或網路。"""
from copy import deepcopy
import pytest

from laya_pokemon.vending_water import (
    VendingWaterController, INTENT, TEXT_PROFILE, MAX_CALLS, MAX_WAITS,
    MIN_DELIVERY_FRAMES, water_expectation,
)

STANCE = dict(map_id=126, x=11, y=2, facing="up", facing_raw=4)
NONE = dict(kind="none", active=False, raw=0)

def progress(money=41066, inventory=None):
    specs=[
        (132,"SNORLAX",35,168,[29,133,156,34],[15,20,10,15]),
        (7,"NIDOKING",36,121,[61,33,30,40],[20,35,25,35]),
        (102,"EEVEE",35,90,[33,28,98,39],[35,15,30,30]),
        (154,"VENUSAUR",35,111,[75,15,73,22],[25,30,10,10]),
        (35,"FEAROW",35,108,[64,65,43,31],[35,20,30,20])]
    return dict(profile="gen1-wrapper-ram-progress-v1-unvalidated",initialization_candidate=True,
                party_read_valid=True,party_count=5,money=money,player_name_raw="KEVIN",badges_raw=31,
                inventory=deepcopy(inventory if inventory is not None else [
                    {"item":4,"quantity":6},{"item":198,"quantity":1},{"item":199,"quantity":1}]),
                party=[dict(species=s,species_name=n,level=lv,exp=lv**3,hp=hp,max_hp=hp,
                            status=0,moves=m,pp=pp) for s,n,lv,hp,m,pp in specs])

def blank():
    return [[" "]*20 for _ in range(18)]

def put(r,x,y,value):
    # 直接依來源charmap把's存一個實體格；不借用controller的formatter。
    parts=[]
    i=0
    while i<len(value):
        if value[i:i+2].lower()=="'s":
            parts.append("'s");i+=2
        else:
            parts.append(value[i]);i+=1
    assert x+len(parts)<=20
    r[y][x:x+len(parts)]=parts
    return r

def packet(r=None,window=True,lines=False):
    cells=deepcopy(blank() if r is None else r)
    p=dict(profile=TEXT_PROFILE,read_valid=True,alignment_verified=True,read_error=None,
           window_visible=window,cells=cells)
    if lines:
        import re
        pairs=[(y,"".join(row).rstrip()) for y,row in enumerate(cells)
               if re.search(r"[A-Za-z0-9]{2,}","".join(row))][:12]
        p.update(lines=[v for _,v in pairs],line_rows=[y for y,_ in pairs])
    return p

def text(lines, *, money=None, cursor=None, arrow=None):
    r=blank()
    if money is not None:
        put(r,13,0,"MONEY");put(r,12,1,f"¥{money}".rjust(7))
    if cursor is not None:
        for y,v in [(5,"FRESH WATER"),(7,"SODA POP"),(9,"LEMONADE"),(11,"CANCEL")]:
            put(r,2,y,v)
        for y,v in [(6,"¥200"),(8,"¥300"),(10,"¥350")]:
            put(r,9,y,v)
        put(r,1,cursor,"▶")
    put(r,1,14,lines[0]);put(r,1,16,lines[1])
    if arrow:put(r,18,arrow,"▼")
    return r

INTRO=("A vending machine!","Here's the menu!")
RECEIPT=("FRESH WATER","popped out!")

def menu(money=41066,cursor=5):
    return text(INTRO,money=money,cursor=cursor)

def receipt(money=40866):
    return text(RECEIPT,money=money,cursor=5)

class Session:
    def __init__(self,p=None):
        self.p=deepcopy(p if p is not None else progress())
        self.before=deepcopy(self.p)
        self.c=VendingWaterController(deepcopy(INTENT))
        self.frame=0;self.now=0.

    def call(self,r=None,*,same=False,ready=False,window=True,text_packet=None,**kw):
        if not same:self.frame+=40
        self.now+=.1
        return self.c.context(text_packet or packet(r,window),kw.pop("progress",self.p),
                              location=kw.pop("location",deepcopy(STANCE)),
                              battle_state=kw.pop("battle_state",deepcopy(NONE)),
                              frame=kw.pop("frame",self.frame),now=kw.pop("now",self.now),
                              overworld_ready=ready,**kw)

    def expect(self,r,action,**kw):
        out=self.call(r,**kw)
        assert out["available_actions"]==[action,"wait"],out
        return out

    def to_menu(self):
        self.expect(None,"a",ready=True,window=False)
        self.expect(text(INTRO,arrow=16),"a")

    def buy(self):
        self.to_menu()
        self.expect(menu(self.before["money"]),"a")

    def deliver(self):
        items=self.p["inventory"]
        water=next((v for v in items if v["item"]==60),None)
        if water:water["quantity"]+=1
        else:items.append(dict(item=60,quantity=1))

    def to_receipt(self):
        self.buy();self.deliver()
        assert self.call(menu(self.before["money"]))["available_actions"]==["wait"]
        assert self.call(menu(self.before["money"]))["available_actions"]==["wait"]
        # 此幀距離purchase已120frame，但正常扣款尚未發生。
        assert self.call(receipt(self.before["money"]))["available_actions"]==["wait"]
        self.p["money"]-=200

    def to_closing(self):
        self.to_receipt()
        self.expect(receipt(self.p["money"]),"a")

def review(out):
    assert out["phase"]=="campaign_review" and out["available_actions"]==["wait"],out

@pytest.mark.parametrize("inventory",[
    [],[dict(item=4,quantity=6)],
    [dict(item=60,quantity=1),dict(item=4,quantity=6)],
    [dict(item=4,quantity=6),dict(item=60,quantity=98)],
])
def test_complete_one_water_append_or_increase_and_two_closed_frames(inventory):
    s=Session(progress(inventory=inventory));s.to_closing()
    assert s.call(ready=True,window=False)["available_actions"]==["wait"]
    assert not s.call(same=True,ready=True,window=False).get("vending_water_complete")
    out=s.call(ready=True,window=False)
    assert out["vending_water_complete"] and out["quantity_purchased"]==1
    assert out["money_spent"]==200
    expected=water_expectation(s.before)
    assert s.p["inventory"]==expected["inventory"] and s.p["party"]==s.before["party"]
    assert s.p["money"]==s.before["money"]-200
    assert s.c.baseline["inventory"]==s.before["inventory"]

def test_exactly_two_hundred_can_buy_then_zero_money_display():
    s=Session(progress(money=200));s.to_closing()
    assert s.p["money"]==0
    s.call(ready=True,window=False)
    assert s.call(ready=True,window=False)["vending_water_complete"]

@pytest.mark.parametrize("bad",[
    {},{**INTENT,"item":61},{**INTENT,"quantity":2},{**INTENT,"unit_price":300},
    {**INTENT,"player_x":12},{**INTENT,"map_id":True},{**INTENT,"extra":1},
])
def test_no_other_intent(bad):
    with pytest.raises(ValueError):VendingWaterController(bad)

@pytest.mark.parametrize("money",[0,199,-1,True,1000000,None])
def test_bad_or_insufficient_initial_money_never_interacts(money):
    s=Session(progress(money=money));review(s.call(ready=True,window=False))

def test_full_twenty_slot_bag_without_water_rejected_before_interaction():
    p=progress(inventory=[dict(item=i,quantity=1) for i in range(1,21)])
    s=Session(p);review(s.call(ready=True,window=False))

def test_full_twenty_slot_bag_with_existing_water_can_increase():
    p=progress(inventory=[dict(item=i,quantity=1) for i in range(1,20)]+[dict(item=60,quantity=2)])
    s=Session(p);s.to_closing()
    assert len(s.p["inventory"])==20 and s.p["inventory"][-1]["quantity"]==3

@pytest.mark.parametrize("inventory",[
    [dict(item=60,quantity=99)],
    [dict(item=60,quantity=True)],
    [dict(item=60,quantity=1),dict(item=60,quantity=1)],
])
def test_stack_overflow_or_invalid_bag_rejected(inventory):
    s=Session(progress(inventory=inventory));review(s.call(ready=True,window=False))

@pytest.mark.parametrize("patch",[
    dict(map_id=125),dict(x=10),dict(y=1),dict(facing="down"),
    dict(facing_raw=0),dict(facing_raw=True),dict(x=True),
])
def test_fixed_bg_stance_and_facing_required(patch):
    s=Session();loc={**STANCE,**patch};review(s.call(ready=True,window=False,location=loc))

@pytest.mark.parametrize("field,value",[
    ("profile","other"),("read_valid",False),("read_valid",1),
    ("alignment_verified",False),("read_error","visible_tile_alignment_incomplete"),
    ("window_visible",None),
])
def test_native_profile_proof_required(field,value):
    s=Session();t=packet(window=False);t[field]=value
    review(s.call(text_packet=t,ready=True))

@pytest.mark.parametrize("cells",[
    [],[[" "]*20]*17,[[" "]*19]*18,[" "*20]*18,
    [["'l"]+[" "]*19]+[[" "]*20]*17,
])
def test_physical_grid_not_legacy_lines(cells):
    s=Session();t=packet(window=False);t["cells"]=cells
    review(s.call(text_packet=t,ready=True))

def test_native_here_s_single_cell_and_line_summaries_are_consistent():
    s=Session();s.expect(None,"a",ready=True,window=False)
    r=text(INTRO,arrow=16);assert r[16][5]=="'s"
    s.expect(None,"a",text_packet=packet(r,lines=True))
    assert s.c.intro_ack

@pytest.mark.parametrize("arrow", [None,17])
def test_full_intro_without_real_prompt_does_not_ack_or_advance(arrow):
    s=Session();s.expect(None,"a",ready=True,window=False)
    out=s.call(text(INTRO,arrow=arrow))
    assert out["available_actions"]==["wait"]
    assert not s.c.intro_ack and s.c.stage=="intro" and s.c.error is None
    assert s.call()["available_actions"]==["wait"]
    assert s.call(text(INTRO,arrow=arrow))["available_actions"]==["wait"]
    assert not s.c.intro_ack
    s.expect(text(INTRO,arrow=16),"a")
    assert s.c.intro_ack and s.c.stage=="menu"
    # 真正prompt確認後，blank/blink與舊真prompt都不能再次A。
    for r in (None,text(INTRO),text(INTRO,arrow=16),text(INTRO,arrow=17)):
        assert s.call(r)["available_actions"]==["wait"]
    assert s.c.error is None and not s.c.purchase_issued
    s.expect(menu(),"a")

def test_partial_intro_then_early_full_then_prompt_only_confirms_once():
    s=Session();s.expect(None,"a",ready=True,window=False)
    partial=text(INTRO);partial[16][6:19]=[" "]*13
    for r in (partial,text(INTRO),None,text(INTRO)):
        assert s.call(r)["available_actions"]==["wait"]
        assert not s.c.intro_ack and s.c.stage=="intro"
    s.expect(text(INTRO,arrow=16),"a")
    assert s.call(text(INTRO,arrow=16))["available_actions"]==["wait"]
    s.expect(menu(),"a")

def test_wrong_ligature_position_rejected():
    s=Session();s.expect(None,"a",ready=True,window=False)
    r=text(INTRO);r[14][1]="'s"
    review(s.call(r))

def test_conflicting_lines_do_not_override_cells():
    s=Session();t=packet(window=False,lines=True);t["lines"]=["YES"]
    review(s.call(text_packet=t,ready=True))

@pytest.mark.parametrize("mutation",[
    lambda p:p.update(profile="other"),
    lambda p:p.update(initialization_candidate=1),
    lambda p:p.update(party_read_valid=False),
    lambda p:p.update(party_count=True),
    lambda p:p["party"][1].update(exp=True),
    lambda p:p["party"][1].update(status=255),
    lambda p:p["party"][1].update(pp=[255,35,25,35]),
    lambda p:p["party"][1].update(species_name="NIDORINO"),
    lambda p:p["party"].append(deepcopy(p["party"][0])),
])
def test_upstream_invalid_is_not_initial_baseline(mutation):
    p=progress();mutation(p);s=Session(p);review(s.call(ready=True,window=False))

@pytest.mark.parametrize("mutation",[
    lambda p:p["party"].reverse(),
    lambda p:p["party"][0].update(hp=100),
    lambda p:p["party"][0].update(status=8),
    lambda p:p["party"][0].update(exp=999),
    lambda p:p["party"][0].update(level=36),
    lambda p:p["party"][0]["moves"].__setitem__(0,70),
    lambda p:p["party"][0]["pp"].__setitem__(0,14),
    lambda p:p["inventory"].reverse(),
    lambda p:p["inventory"][0].update(quantity=5),
    lambda p:p.update(player_name_raw="OTHER"),
])
def test_all_original_party_and_bag_fields_protected_before_partial_wait(mutation):
    s=Session();s.buy();p=deepcopy(s.p);mutation(p)
    review(s.call(progress=p))

def test_delivery_then_debit_order_is_accepted_without_second_purchase():
    s=Session();s.buy();s.deliver()
    for _ in range(3):
        out=s.call(menu(s.before["money"]))
        assert out["available_actions"]==["wait"] and s.c.purchase_issued
    assert s.c.delivery_observed and not s.c.paid_observed
    s.p["money"]-=200
    s.expect(receipt(s.p["money"]),"a")
    assert s.c.receipt_ack

def test_no_data_change_before_confirming_buy():
    s=Session();s.to_menu();s.deliver()
    review(s.call(menu(s.before["money"])))

def test_money_before_water_is_not_normal_purchase():
    s=Session();s.buy();s.p["money"]-=200
    review(s.call(menu(s.before["money"])))

@pytest.mark.parametrize("wrong",["quantity2","soda","price300","price199"])
def test_wrong_quantity_item_or_price_rejected(wrong):
    s=Session();s.buy();s.deliver()
    if wrong=="quantity2":s.p["inventory"][-1]["quantity"]=2
    elif wrong=="soda":s.p["inventory"][-1]["item"]=61
    elif wrong=="price300":s.p["money"]-=300
    else:s.p["money"]-=199
    review(s.call())

def test_delivered_water_cannot_revert_to_initial_baseline():
    s=Session();s.buy();s.deliver();s.call(menu(s.before["money"]))
    s.p["inventory"]=deepcopy(s.before["inventory"])
    review(s.call())

def test_no_refund_or_rebaseline_after_paid():
    s=Session();s.to_closing();base=deepcopy(s.c.baseline)
    s.p["money"]+=200
    review(s.call(receipt(s.before["money"])))
    assert s.c.baseline==base

@pytest.mark.parametrize("cursor", [7,9,11])
def test_only_normal_up_moves_toward_fresh_from_other_known_cursor(cursor):
    s=Session();s.to_menu()
    for y in range(cursor,5,-2):
        s.expect(menu(s.before["money"],y),"up")
    s.expect(menu(s.before["money"],5),"a")
    assert s.c.purchase_issued

def test_direction_pending_survives_blank_then_old_cursor_without_resend():
    s=Session();s.to_menu();s.expect(menu(cursor=9),"up")
    assert s.call()["available_actions"]==["wait"]
    assert s.call(menu(cursor=9))["available_actions"]==["wait"]
    s.expect(menu(cursor=7),"up")
    s.expect(menu(cursor=5),"a")

def test_cursor_jump_not_assumed_or_wrapped():
    s=Session();s.to_menu();s.expect(menu(cursor=11),"up")
    review(s.call(menu(cursor=5)))

@pytest.mark.parametrize("target", ["interaction","intro","purchase","receipt"])
def test_pending_a_survives_blank_and_old_full_page(target):
    s=Session()
    if target=="interaction":
        s.expect(None,"a",ready=True,window=False)
        # 再次關閉野外並不證新互動可重送。
        review(s.call(ready=True,window=False))
        return
    if target=="intro":
        s.to_menu();old=text(INTRO)
    elif target=="purchase":
        s.buy();old=menu()
    else:
        s.to_closing();old=receipt(s.p["money"])
    assert s.call()["available_actions"]==["wait"]
    assert s.call(old)["available_actions"]==["wait"]
    assert s.c.error is None

@pytest.mark.parametrize("where",["intro","menu","receipt"])
def test_partial_source_page_only_wait(where):
    s=Session()
    if where=="intro":
        s.expect(None,"a",ready=True,window=False);r=text(INTRO)
        r[14][7:19]=[" "]*12;r[16]=[" "]*20
    elif where=="menu":
        s.to_menu();r=menu();r[9][2:10]=[" "]*8
    else:
        s.to_receipt();r=receipt(s.p["money"]);r[16][5:19]=[" "]*14
    out=s.call(r)
    assert out["available_actions"]==["wait"] and s.c.error is None

@pytest.mark.parametrize("where",["intro","menu","receipt"])
def test_unknown_letter_outside_source_mask_is_review(where):
    s=Session()
    if where=="intro":
        s.expect(None,"a",ready=True,window=False);r=text(INTRO)
    elif where=="menu":s.to_menu();r=menu()
    else:s.to_receipt();r=receipt(s.p["money"])
    put(r,0,0,"X");review(s.call(r))

@pytest.mark.parametrize("change",["label_offset","price_offset","extra_arrow","wrong_price","duplicate_label","missing_cancel"])
def test_invalid_menu_never_purchases(change):
    s=Session();s.to_menu();r=menu()
    if change=="label_offset":
        r[5]=[" "]*20;put(r,1,5,"▶");put(r,3,5,"FRESH WATER")
    elif change=="price_offset":
        r[6]=[" "]*20;put(r,10,6,"¥200")
    elif change=="extra_arrow":put(r,1,7,"▶")
    elif change=="wrong_price":put(r,9,6,"¥300")
    elif change=="duplicate_label":put(r,2,3,"FRESH WATER")
    else:r[11]=[" "]*20
    out=s.call(r)
    assert out["available_actions"]==["wait"] and not s.c.purchase_issued

@pytest.mark.parametrize("lines",[("Oops, not enough","money!"),
                                  ("There's no more","room for stuff!"),("Not thirsty!","")])
def test_exact_failure_or_cancel_does_not_auto_refund_retry_or_finish(lines):
    s=Session();s.buy()
    review(s.call(text(lines,money=s.before["money"],cursor=5)))

def test_receipt_requires_full_water_name_and_popped_out():
    s=Session();s.to_receipt();r=receipt(s.p["money"])
    r[14]=[" "]*20;put(r,1,14,"SODA POP")
    review(s.call(r));assert not s.c.receipt_ack

def test_receipt_before_120_source_frames_is_rejected_even_if_data_paid():
    s=Session();s.buy();s.deliver();s.p["money"]-=200
    review(s.call(receipt(s.p["money"])))
    assert not s.c.receipt_ack

def test_paid_progress_but_old_money_box_waits_for_redraw():
    s=Session();s.to_receipt()
    out=s.call(receipt(s.before["money"]))
    assert out["available_actions"]==["wait"] and not s.c.receipt_ack
    s.expect(receipt(s.p["money"]),"a")

def test_receipt_without_arrow_is_confirmed_once_after_actual_payment():
    s=Session();s.to_closing()
    out=s.call(receipt(s.p["money"]))
    assert out["available_actions"]==["wait"] and s.c.receipt_ack

def test_two_closed_frames_must_be_consecutive_verified_closed_observations():
    s=Session();s.to_closing()
    s.call(ready=True,window=False);first=s.c.closed_frame
    s.call(receipt(s.p["money"]))
    assert s.c.closed_frame is None
    assert not s.call(ready=True,window=False).get("vending_water_complete")
    assert s.c.closed_frame>first
    assert s.call(ready=True,window=False)["vending_water_complete"]

@pytest.mark.parametrize("kind,raw,active",[("wild",1,True),("unknown",None,False),("none",True,False),("none",0,None)])
def test_nonbattle_must_be_native_none(kind,raw,active):
    s=Session();review(s.call(ready=True,window=False,battle_state=dict(kind=kind,raw=raw,active=active)))

def test_same_frame_identical_wait_and_conflict_review():
    s=Session();t=packet(window=False)
    s.call(text_packet=t,ready=True)
    assert s.call(text_packet=t,ready=True,same=True)["available_actions"]==["wait"]
    t["cells"][0][0]="X"
    review(s.call(text_packet=t,ready=True,same=True))

@pytest.mark.parametrize("packet_name",["text","progress","location","battle_state"])
def test_explicit_observation_frame_conflicts_are_unknown(packet_name):
    s=Session();t=packet(window=False);p=deepcopy(s.p);loc=deepcopy(STANCE);b=deepcopy(NONE)
    {"text":t,"progress":p,"location":loc,"battle_state":b}[packet_name]["observation_frame"]=999
    review(s.call(text_packet=t,progress=p,location=loc,battle_state=b,ready=True))

@pytest.mark.parametrize("field,value",[("frame",True),("frame",-1),("now",True),
                                        ("now",-1),("now",float("nan")),("now",float("inf"))])
def test_clock_and_frame_validation(field,value):
    s=Session();review(s.call(ready=True,window=False,**{field:value}))

def test_regressed_frame_and_time_fail():
    s=Session();s.to_menu();review(s.call(frame=1))
    s=Session();s.to_menu();review(s.call(now=0.))

def test_sixty_second_budget_does_not_reinitialize():
    s=Session();s.to_menu();base=deepcopy(s.c.baseline)
    review(s.call(now=60.5));assert s.c.baseline==base

def test_call_budget():
    s=Session();s.to_menu();s.c.calls=MAX_CALLS
    review(s.call())

def test_cumulative_source_wait_limit():
    s=Session();s.to_menu()
    for _ in range(MAX_WAITS):
        assert s.call()["available_actions"]==["wait"] and s.c.error is None
    review(s.call())

def test_input_packets_and_expected_calculator_are_not_mutated():
    p=progress();original=deepcopy(p);e=water_expectation(p)
    assert p==original and e["inventory"]!=p["inventory"]
    s=Session(p);t=packet(window=False);loc=deepcopy(STANCE);b=deepcopy(NONE)
    saved=deepcopy((t,p,loc,b))
    s.call(text_packet=t,progress=p,location=loc,battle_state=b,ready=True)
    assert (t,p,loc,b)==saved

def test_complete_never_issues_another_purchase_on_new_context():
    s=Session();s.to_closing();s.call(ready=True,window=False)
    assert s.call(ready=True,window=False)["vending_water_complete"]
    assert s.call(ready=True,window=False)["vending_water_complete"]
    review(s.call(menu(s.p["money"])))

def test_intent_mutation_cannot_request_second_item():
    s=Session();s.to_menu();s.c.intent["item"]=61
    review(s.call(menu()))

