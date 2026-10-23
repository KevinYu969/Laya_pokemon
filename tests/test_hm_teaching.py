"""純合成物理格與上游字典；不建立PyBoy、不讀ROM/state/plan、不送鍵。"""
from copy import deepcopy
import pytest

from laya_pokemon.hm_teaching import (
    HMTeachingController, SURF_INTENT, STRENGTH_INTENT,
    TEXT_PROFILE, PROGRESS_PROFILE, MAX_CALLS, MAX_WAITS,
)

INTENTS = (SURF_INTENT, STRENGTH_INTENT)
LOCATION = {"map_id": 154, "x": 3, "y": 3}
NAMES = {132: "SNORLAX", 7: "NIDOKING", 102: "EEVEE", 154: "VENUSAUR", 35: "FEAROW"}
BAG_LABELS = {198: "HM03", 199: "HM04", 4: "POKÉ BALL", 196: "HM01", 211: "TM11"}
MOVE_NAMES = {61: "BUBBLEBEAM", 33: "TACKLE", 30: "HORN ATTACK", 40: "POISON STING",
              29: "HEADBUTT", 133: "AMNESIA", 156: "REST", 34: "BODY SLAM"}

def progress():
    specs = [
        (132, 35, 168, [29, 133, 156, 34], [15, 20, 10, 15]),
        (7, 36, 121, [61, 33, 30, 40], [20, 35, 25, 35]),
        (102, 35, 90, [33, 28, 98, 39], [35, 15, 30, 30]),
        (154, 35, 111, [75, 15, 73, 22], [25, 30, 10, 10]),
        (35, 35, 108, [64, 65, 43, 31], [35, 20, 30, 20]),
    ]
    return dict(profile=PROGRESS_PROFILE, initialization_candidate=True, party_read_valid=True,
                party_count=5, player_name_raw="KEVIN", money=41066,
                inventory=[{"item": i, "quantity": q} for i, q in [(198, 1), (199, 1), (4, 6), (196, 1), (211, 1)]],
                party=[dict(species=s, species_name=NAMES[s], level=lv, hp=hp, max_hp=hp,
                            status=0, exp=lv**3, moves=list(m), pp=list(pp)) for s, lv, hp, m, pp in specs])

def canvas():
    return [[" "] * 20 for _ in range(18)]

def put(r, x, y, text):
    text = text.replace("'t", "t").replace("'l", "l").upper()
    assert x + len(text) <= 20
    r[y][x:x+len(text)] = list(text)
    return r

def clear(r, a, b, c, d):
    for y in range(b, d+1):
        for x in range(a, c+1):
            r[y][x] = " "
    return r

def packet(r=None, window=True):
    return dict(profile=TEXT_PROFILE, read_valid=True, alignment_verified=True,
                read_error=None, window_visible=window, cells=deepcopy(r or canvas()))

def start(row=6):
    r = canvas()
    for y, name in [(2, "POKÉDEX"), (4, "POKÉMON"), (6, "ITEM"), (8, "KEVIN"),
                    (10, "SAVE"), (12, "OPTION"), (14, "EXIT")]:
        put(r, 12, y, name)
    return put(r, 11, row, "▶")

def bag(p, offset=0, cursor=0, marker="▶"):
    r = clear(start(), 4, 2, 19, 12)
    for n in range(4):
        idx, y = offset+n, 4+n*2
        if idx == len(p["inventory"]):
            put(r, 6, y, "CANCEL")
            break
        if idx > len(p["inventory"]):
            break
        entry = p["inventory"][idx]
        put(r, 6, y, BAG_LABELS[entry["item"]])
        if entry["item"] not in (198, 199, 196):
            put(r, 14, y+1, f'×{entry["quantity"]:2}')
    return put(r, 5, 4+cursor*2, marker)

def use(p, offset, cursor, y=11, marker="▶"):
    r = clear(bag(p, offset, cursor, "▷"), 13, 10, 19, 15)
    put(r, 15, 11, "USE")
    put(r, 15, 13, "TOSS")
    return put(r, 14, y, marker)

def party(p, index=0, marker="▶"):
    r = canvas()
    for i, mon in enumerate(p["party"]):
        put(r, 3, i*2, mon["species_name"])
        put(r, 13, i*2, f'{mon["level"]:3}')
        put(r, 12, i*2+1, "ABLE" if mon["species"] in (7, 132) else "NOT ABLE")
    put(r, 0, index*2+1, marker)
    put(r, 1, 14, "Use TM on which")
    return put(r, 1, 16, "POKéMON?")

class Session:
    def __init__(self, intent=SURF_INTENT, p=None):
        self.intent, self.p = deepcopy(intent), deepcopy(p or progress())
        self.c = HMTeachingController(self.intent)
        self.frame = 0
        self.now = 0.
        self.target = next(i for i, m in enumerate(self.p["party"]) if m["species"] == intent["species"])
        self.hm_index = next(i for i, v in enumerate(self.p["inventory"]) if v["item"] == intent["item"])
        self.offset, self.cursor = max(0, self.hm_index-2), min(2, self.hm_index)
        self.name = NAMES[intent["species"]]
        self.move = "SURF" if intent["item"] == 198 else "STRENGTH"
        self.old = MOVE_NAMES[intent["replace_move"]]

    def call(self, r=None, *, ready=False, same=False, window=True, text=None, p=None, **kwargs):
        if not same:
            self.frame += 1
            self.now += .05
        return self.c.context(text or packet(r, window), self.p if p is None else p,
                              location=kwargs.pop("location", LOCATION), frame=kwargs.pop("frame", self.frame),
                              now=kwargs.pop("now", self.now), overworld_ready=ready,
                              battle_active=kwargs.pop("battle_active", False), **kwargs)

    def expected(self, r, action, **kwargs):
        out = self.call(r, **kwargs)
        assert out["available_actions"] == [action, "wait"], out
        return out

    def dialog(self, lines, *, choose=False, y=8, marker="▶", on_party=False, arrow=None):
        r = party(self.p, self.target, "▷") if on_party else use(self.p, self.offset, self.cursor, marker="▷")
        clear(r, 0, 12, 19, 17)
        if choose:
            clear(r, 14, 7, 19, 12)
            put(r, 16, 8, "YES")
            put(r, 16, 10, "NO")
            put(r, 15, y, marker)
        for row, text in lines:
            put(r, 1, row, text)
        if arrow:
            put(r, 18, arrow, "▼")
        return r

    def teach(self, y=8):
        return self.dialog([(14, "Teach "+self.move), (16, "to a POKéMON?")], choose=True, y=y)

    def delete(self, y=8):
        return self.dialog([(13, "Delete an older"), (14, "move to make room"),
                            (16, "for "+self.move+"?")], choose=True, y=y, on_party=True)

    def forget(self, y=None):
        if y is None:
            y = 8+self.intent["replace_index"]
        r = clear(party(self.p, self.target, "▷"), 4, 7, 19, 12)
        clear(r, 0, 12, 19, 17)
        original = [61, 33, 30, 40] if self.intent["species"] == 7 else [29, 133, 156, 34]
        for i, move in enumerate(original):
            put(r, 6, 8+i, MOVE_NAMES[move])
        put(r, 5, y, "▶")
        put(r, 1, 14, "Which move should")
        return put(r, 1, 16, "be forgotten?")

    def to_use(self):
        self.expected(canvas(), "start", ready=True, window=False)
        self.expected(start(2), "down")
        self.expected(start(4), "down")
        self.expected(start(6), "a")
        for current in range(self.hm_index+1):
            off, cur = max(0, current-2), min(2, current)
            self.expected(bag(self.p, off, cur), "a" if current == self.hm_index else "down")
        return use(self.p, self.offset, self.cursor)

    def to_party(self):
        self.to_use()
        self.expected(use(self.p, self.offset, self.cursor, 13), "up")
        self.expected(use(self.p, self.offset, self.cursor), "a")
        self.expected(self.dialog([(14, "Booted up an HM!")], arrow=16), "a")
        self.expected(self.dialog([(14, "It contained"), (16, self.move+"!")], arrow=16), "a")
        self.expected(self.teach(10), "up")
        self.expected(self.teach(), "a")

    def to_intro(self):
        self.to_party()
        for i in range(self.target+1):
            self.expected(party(self.p, i), "a" if i == self.target else "down")

    def to_delete(self):
        self.to_intro()
        for lines in [
            [(14, self.name+" is"), (16, "trying to learn")],
            [(14, "trying to learn"), (16, self.move+"!")],
            [(14, "But, "+self.name), (16, "can't learn more")],
            [(14, "can't learn more"), (16, "than 4 moves!")],
        ]:
            self.expected(self.dialog(lines, on_party=True), "a")

    def to_forget(self):
        self.to_delete()
        self.expected(self.delete(), "a")

    def to_receipt(self):
        self.to_forget()
        if self.intent["replace_index"] == 1:
            self.expected(self.forget(8), "down")
        self.expected(self.forget(), "a")

    def install(self):
        mon = self.p["party"][self.target]
        mon["moves"][self.intent["replace_index"]] = self.intent["move"]
        mon["pp"][self.intent["replace_index"]] = 15

    def to_closing(self):
        self.to_receipt()
        auto = self.dialog([(14, "1, 2 and...")], on_party=True)
        assert self.call(auto)["available_actions"] == ["wait"]
        self.expected(self.dialog([(14, "1, 2 and... Poof!")], on_party=True, arrow=16), "a")
        self.expected(self.dialog([(14, self.name+" forgot"), (16, self.old+"!")], on_party=True, arrow=16), "a")
        self.expected(self.dialog([(14, "And...")], on_party=True, arrow=16), "a")
        self.install()
        self.expected(self.dialog([(14, self.name+" learned"), (16, self.move+"!")], on_party=True, arrow=16), "a")

def review(out):
    assert out["phase"] == "campaign_review" and out["available_actions"] == ["wait"], out

@pytest.mark.parametrize("intent", INTENTS)
def test_complete_exact_normal_hm_flow_preserves_bag_money_and_other_bytes(intent):
    s = Session(intent)
    original = deepcopy(s.p)
    s.to_closing()
    s.expected(bag(s.p, s.offset, s.cursor), "b")
    s.expected(start(), "b")
    assert s.call(ready=True, window=False)["available_actions"] == ["wait"]
    assert not s.call(ready=True, window=False, same=True).get("hm_teaching_complete")
    result = s.call(ready=True, window=False)
    assert result["hm_teaching_complete"] is True and result["hm_quantity_used"] == 0
    assert s.p["inventory"] == original["inventory"] and s.p["money"] == original["money"]
    i = intent["replace_index"]
    before = original["party"][s.target]
    after = deepcopy(before)
    after["moves"][i], after["pp"][i] = intent["move"], 15
    assert s.p["party"][s.target] == after
    assert all(s.p["party"][j] == m for j, m in enumerate(original["party"]) if j != s.target)

@pytest.mark.parametrize("bad", [
    {}, {**SURF_INTENT, "species":167}, {**SURF_INTENT, "move":95},
    {**SURF_INTENT, "replace_index":0}, {**STRENGTH_INTENT, "move":80},
    {**SURF_INTENT, "item":True}, {**SURF_INTENT, "extra":1},
])
def test_constructor_rejects_noncontract_intents(bad):
    with pytest.raises(ValueError):
        HMTeachingController(bad)

@pytest.mark.parametrize("field,value", [
    ("profile", "legacy"), ("read_valid", False), ("read_valid", 1),
    ("alignment_verified", False), ("read_error", "partial"), ("window_visible", None),
])
def test_missing_native_proof_never_opens_menu(field, value):
    s = Session()
    t = packet(window=False); t[field] = value
    review(s.call(text=t, ready=True))

@pytest.mark.parametrize("bad", [
    None, [], [[" "]*20]*17, [[" "]*19]*18, [" "*20]*18,
    [[" "]*20]*17+[["'s"]+[" "]*19],
])
def test_requires_full_physical_cells(bad):
    s = Session(); t = packet(window=False); t["cells"] = bad
    review(s.call(text=t, ready=True))

@pytest.mark.parametrize("mutate", [
    lambda p:p.update(profile="other"),
    lambda p:p.update(initialization_candidate=1),
    lambda p:p.update(party_read_valid=False),
    lambda p:p.update(party_count=True),
    lambda p:p.update(party_count=4),
    lambda p:p.update(money=True),
    lambda p:p.update(money=-1),
    lambda p:p["party"][1].update(species=167, species_name="NIDORINO"),
    lambda p:p["party"][1].update(moves=[57,33,30,40]),
    lambda p:p["party"][0].update(status=True),
    lambda p:p["party"][2].update(hp=0),
    lambda p:p["party"][1].update(exp=True),
    lambda p:p["party"][1].update(pp=[255,35,25,35]),
    lambda p:p["inventory"].append(deepcopy(p["inventory"][0])),
    lambda p:p["inventory"][0].update(quantity=2),
])
def test_initial_upstream_fingerprint_fail_closed(mutate):
    p=progress(); mutate(p); s=Session()
    review(s.call(p=p, ready=True, window=False))

@pytest.mark.parametrize("mutation", [
    lambda p:p["inventory"].reverse(),
    lambda p:p["inventory"][0].update(quantity=2),
    lambda p:p["inventory"].pop(0),
    lambda p:p.update(money=41065),
    lambda p:p["party"][2].update(hp=89),
    lambda p:p["party"][1].update(status=8),
    lambda p:p["party"][1].update(exp=999),
    lambda p:p["party"][1].update(level=37),
    lambda p:p["party"].reverse(),
])
def test_invariants_run_before_blank_wait(mutation):
    s=Session(); s.to_use(); p=deepcopy(s.p); mutation(p)
    review(s.call(p=p))
    assert not s.c.replacement_selected

def test_hm_not_tm_consumption_after_verified_replacement_is_rejected():
    s=Session(); s.to_receipt(); s.install()
    s.p["inventory"].pop(0)
    review(s.call(s.dialog([(14,"And...")],on_party=True)))

@pytest.mark.parametrize("new_moves,new_pp", [
    ([57,33,30,40],[15,35,25,35]),
    ([61,57,30,40],[20,20,25,35]),
    ([61,57,30,40],[19,15,25,35]),
    ([61,57,30,40],[20,15,24,35]),
    ([61,57,30,0],[20,15,25,0]),
])
def test_changed_moves_or_other_pp_bytes_cannot_pass(new_moves,new_pp):
    s=Session();s.to_receipt()
    s.p["party"][s.target].update(moves=new_moves,pp=new_pp)
    review(s.call())

def test_expected_move_change_before_forget_confirmation_is_not_success():
    s=Session();s.to_forget();s.install()
    review(s.call(s.forget()))
    assert s.c.seen_learned is False

def test_hm_does_not_clear_other_moves_pp_up_bits():
    p=progress();p["party"][1]["pp"]=[0x40+24,35,0x80+30,35]
    s=Session(p=p);s.to_closing()
    assert s.p["party"][1]["pp"]==[88,15,158,35]

@pytest.mark.parametrize("stage", ["start","bag","use","teach","party","forget"])
def test_direction_pending_survives_blank_and_unchanged_old_cursor(stage):
    s=Session()
    if stage=="start":
        s.expected(canvas(),"start",ready=True,window=False); old=start(2)
    elif stage=="bag":
        s=Session(STRENGTH_INTENT);s.expected(canvas(),"start",ready=True,window=False)
        s.expected(start(),"a");old=bag(s.p,0,0)
    elif stage=="use":
        s.to_use();old=use(s.p,s.offset,s.cursor,13)
    elif stage=="teach":
        s.to_use();s.expected(use(s.p,s.offset,s.cursor),"a")
        s.expected(s.dialog([(14,"Booted up an HM!")],arrow=16),"a")
        s.expected(s.dialog([(14,"It contained"),(16,s.move+"!")],arrow=16),"a");old=s.teach(10)
    elif stage=="party":
        s.to_party();old=party(s.p,0)
    else:
        s.to_forget();old=s.forget(8)
    first=s.call(old); assert first["available_actions"] in (["up","wait"],["down","wait"]),first
    assert s.call()["available_actions"]==["wait"]
    assert s.call(old)["available_actions"]==["wait"]
    assert s.c.error is None

def test_direction_wrong_jump_does_not_confirm_an_unseen_item():
    s=Session(STRENGTH_INTENT)
    s.expected(canvas(),"start",ready=True,window=False);s.expected(start(),"a")
    s.expected(bag(s.p,0,0),"down")
    review(s.call(bag(s.p,0,2)))

@pytest.mark.parametrize("at", ["use","teach","party","delete","forget"])
def test_a_semantic_pending_survives_blank_and_old_page(at):
    s=Session()
    if at=="use":
        s.to_use();old=use(s.p,s.offset,s.cursor)
    elif at=="teach":
        s.to_use();s.expected(use(s.p,s.offset,s.cursor),"a")
        s.expected(s.dialog([(14,"Booted up an HM!")],arrow=16),"a")
        s.expected(s.dialog([(14,"It contained"),(16,s.move+"!")],arrow=16),"a");old=s.teach()
    elif at=="party":
        s.to_party();s.expected(party(s.p,0),"down");old=party(s.p,1)
    elif at=="delete":
        s.to_delete();old=s.delete()
    else:
        s.to_forget();s.expected(s.forget(8),"down");old=s.forget()
    s.expected(old,"a")
    assert s.call()["available_actions"]==["wait"]
    assert s.call(old)["available_actions"]==["wait"]
    assert s.c.error is None

@pytest.mark.parametrize("screen", ["start","bag","use","party","delete","forget","learned"])
def test_full_page_text_pollution_prevents_a(screen):
    s=Session()
    if screen=="start":
        s.expected(canvas(),"start",ready=True,window=False);r=start()
    elif screen=="bag":
        s.expected(canvas(),"start",ready=True,window=False);s.expected(start(),"a");r=bag(s.p)
    elif screen=="use":
        s.to_use();r=use(s.p,s.offset,s.cursor)
    elif screen=="party":
        s.to_party();r=party(s.p,0)
    elif screen=="delete":
        s.to_delete();r=s.delete()
    elif screen=="forget":
        s.to_forget();r=s.forget(9)
    else:
        s.to_receipt()
        s.expected(s.dialog([(14,s.name+" forgot"),(16,s.old+"!")],on_party=True,arrow=16),"a")
        s.expected(s.dialog([(14,"And...")],on_party=True,arrow=16),"a")
        s.install();r=s.dialog([(14,s.name+" learned"),(16,s.move+"!")],on_party=True)
    put(r,0,0,"X")
    review(s.call(r))

def test_delete_preserves_only_source_cropped_not_able_background_no():
    s=Session();s.to_delete();r=s.delete()
    assert "".join(r[7][12:14])=="NO" and "".join(r[9][12:14])=="NO"
    s.expected(r,"a")

@pytest.mark.parametrize("xy",[(0,0),(12,3),(0,5),(0,11)])
def test_unknown_additional_no_not_ignored(xy):
    s=Session();s.to_delete();r=s.delete();put(r,*xy,"NO")
    review(s.call(r))

def test_hm_use_toss_has_no_cancel_and_never_a_on_toss():
    s=Session();s.to_use();r=use(s.p,s.offset,s.cursor,13)
    s.expected(r,"up")
    put(r,15,15,"CANCE")
    review(s.call(r))

def test_incorrect_able_member_data_does_not_select():
    s=Session();s.to_party();r=party(s.p,0)
    r[3][12:20]=list("NOT ABLE")
    review(s.call(r))

def test_wrong_four_move_order_is_not_forget_selection():
    s=Session();s.to_forget();r=s.forget(9)
    clear(r,6,8,19,9);put(r,6,8,"TACKLE");put(r,6,9,"BUBBLEBEAM")
    review(s.call(r));assert not s.c.replacement_selected

def test_wrong_forgot_name_or_move_is_not_receipt():
    s=Session();s.to_receipt()
    review(s.call(s.dialog([(14,s.name+" forgot"),(16,"HORN ATTACK!")],on_party=True)))
    assert not s.c.seen_forgot

def test_learned_requires_forgot_and_and_receipts():
    s=Session();s.to_receipt();s.install()
    review(s.call(s.dialog([(14,s.name+" learned"),(16,s.move+"!")],on_party=True)))
    assert not s.c.seen_learned

def test_learned_ram_change_alone_cannot_complete():
    s=Session();s.to_receipt();s.install()
    review(s.call(ready=True,window=False))
    assert not s.c.seen_learned

def test_expected_move_without_correct_pp_is_review_even_if_learned_page_complete():
    s=Session();s.to_receipt()
    s.expected(s.dialog([(14,s.name+" forgot"),(16,s.old+"!")],on_party=True,arrow=16),"a")
    s.expected(s.dialog([(14,"And...")],on_party=True,arrow=16),"a")
    s.install();s.p["party"][s.target]["pp"][1]=14
    review(s.call(s.dialog([(14,s.name+" learned"),(16,s.move+"!")],on_party=True)))

def test_known_partial_question_is_wait_then_one_yes_only():
    s=Session();s.to_delete();r=s.delete()
    r[8][16:19]=list("Y  ")
    assert s.call(r)["available_actions"]==["wait"]
    s.expected(s.delete(),"a")
    assert s.call(r)["available_actions"]==["wait"]
    assert s.call(s.delete())["available_actions"]==["wait"]

def test_ligature_cant_retains_one_physical_cell():
    s=Session();s.to_intro()
    s.expected(s.dialog([(14,s.name+" is"),(16,"trying to learn")],on_party=True),"a")
    s.expected(s.dialog([(14,"trying to learn"),(16,s.move+"!")],on_party=True),"a")
    r=s.dialog([(14,"But, "+s.name),(16,"can't learn more")],on_party=True)
    assert r[16][4]=="T";r[16][4]="'t"
    s.expected(r,"a")

@pytest.mark.parametrize("ligature,where",[("'t",(1,14)),("'l",(11,16)),("'s",(1,14))])
def test_arbitrary_ligature_cannot_replace_literal_letter(ligature,where):
    s=Session();s.to_intro()
    r=s.dialog([(14,s.name+" is"),(16,"trying to learn")],on_party=True)
    r[where[1]][where[0]]=ligature
    review(s.call(r))

def test_same_frame_same_packet_is_wait_and_conflict_is_review():
    s=Session();t=packet(window=False)
    s.call(text=t,ready=True)
    assert s.call(text=t,ready=True,same=True)["available_actions"]==["wait"]
    changed=deepcopy(t);changed["cells"][0][0]="X"
    review(s.call(text=changed,ready=True,same=True))

@pytest.mark.parametrize("field,value",[("frame",True),("frame",-1),("now",float("nan")),
                                      ("now",True),("now",-1),("battle_active",True)])
def test_bad_clock_frame_battle_never_opens(field,value):
    s=Session();review(s.call(ready=True,window=False,**{field:value}))

def test_frame_or_clock_regression_is_review():
    s=Session();s.call(ready=True,window=False)
    review(s.call(start(),frame=0))

def test_time_budget_sixty_seconds():
    s=Session();s.call(ready=True,window=False)
    review(s.call(now=60.2))

def test_call_and_wait_budgets_are_independent():
    s=Session();s.call(ready=True,window=False);s.c.calls=MAX_CALLS
    review(s.call())
    s=Session();s.call(ready=True,window=False)
    for _ in range(MAX_WAITS):
        assert s.call()["available_actions"]==["wait"] and s.c.error is None
    review(s.call())

@pytest.mark.parametrize("owner",["text","progress","location"])
def test_optional_observation_frames_must_match_current(owner):
    s=Session()
    kwargs={}
    t=packet(window=False);p=deepcopy(s.p);loc=deepcopy(LOCATION)
    {"text":t,"progress":p,"location":loc}[owner]["observation_frame"]=999
    review(s.call(text=t,p=p,location=loc,ready=True))

def test_no_input_progress_text_or_location_mutation():
    s=Session()
    t=packet(window=False);p=deepcopy(s.p);loc=deepcopy(LOCATION)
    original=deepcopy((t,p,loc))
    s.call(text=t,p=p,location=loc,ready=True)
    assert (t,p,loc)==original

def test_closed_world_needs_two_different_frames_and_canonical_screen():
    s=Session();s.to_closing()
    s.expected(bag(s.p,s.offset,s.cursor),"b");s.expected(start(),"b")
    first=s.call(ready=True,window=False)
    assert not first.get("hm_teaching_complete")
    second=s.call(ready=True,window=False)
    assert second["hm_teaching_complete"] is True
    bad=canvas();put(bad,1,14,"YES")
    review(s.call(bad,ready=True,window=False))

def test_down_scroll_uses_real_order_not_preview_as_selectable():
    p=progress();p["inventory"]=[p["inventory"][2],p["inventory"][3],p["inventory"][4],
                                p["inventory"][1],p["inventory"][0]]
    s=Session(p=p);s.to_use()
    assert s.c.bag_offset==2 and s.c.bag_cursor==2

def test_both_targets_able_still_requires_exact_name_level_and_index():
    s=Session();s.to_party()
    r=party(s.p,0)
    assert "".join(r[1][12:16])=="ABLE" and "".join(r[3][12:16])=="ABLE"
    s.expected(r,"down")
    wrong=party(s.p,1);put(wrong,14,2,"35")
    review(s.call(wrong))


# 原生長袋右下▼是preview仍有項目的提示，不能當active cursor或選取列。
def long_bag(r):
    put(r,18,11,"▼")
    return r


def open_bag_only(s):
    s.expected(canvas(),"start",ready=True,window=False)
    s.expected(start(6),"a")


@pytest.mark.parametrize("intent",INTENTS)
def test_long_bag_arrow_preserves_exact_hm_target_and_never_selects_preview(intent):
    p=progress()
    p["inventory"]=[p["inventory"][2],p["inventory"][4],p["inventory"][3],
                    p["inventory"][1],p["inventory"][0]]
    s=Session(intent,p=p);original=deepcopy(s.p);open_bag_only(s)
    # current1是TM11，▼18,11不能讓它變成下方可見HM。
    s.expected(long_bag(bag(s.p,0,1)),"down")
    assert s.call(bag(s.p,0,1))["available_actions"]==["wait"]
    assert s.call(long_bag(bag(s.p,0,1)))["available_actions"]==["wait"]
    s.expected(long_bag(bag(s.p,0,2)),"down")
    if intent["item"]==199:
        selected=s.expected(long_bag(bag(s.p,1,2)),"a")
        assert selected["menu_label"]=="HM04"
    else:
        # offset1的preview已看見HM03，但active在HM04，必須先向下。
        s.expected(long_bag(bag(s.p,1,2)),"down")
        selected=s.expected(bag(s.p,2,2),"a")
        assert selected["menu_label"]=="HM03"
    assert s.c.stage=="item_selected" and s.p==original


@pytest.mark.parametrize("intent",INTENTS)
def test_valid_scroll_decoration_does_not_move_the_active_cursor(intent):
    s=Session(intent);open_bag_only(s)
    # 仍是原袋游標的0或1，額外▼不改物品身分。
    if s.hm_index==1:
        s.expected(long_bag(bag(s.p,0,0)),"down")
    result=s.expected(long_bag(bag(s.p,0,s.hm_index)),"a")
    assert result["menu_label"]==("HM03" if intent["item"]==198 else "HM04")
    assert s.c.bag_cursor==s.hm_index and s.c.bag_offset==0


@pytest.mark.parametrize("xy",[(17,11),(19,11),(18,9),(18,10),(18,12),(5,6),(5,10)])
def test_scroll_arrow_at_other_coordinates_never_selects_an_hm(xy):
    s=Session();open_bag_only(s);r=bag(s.p,0,0);put(r,*xy,"▼")
    result=s.call(r)
    assert result["available_actions"]==["wait"] and s.c.stage!="item_selected"


@pytest.mark.parametrize("offset,cursor",[(2,0),(2,2),(3,0),(4,0)])
def test_cancel_or_ended_bag_pages_cannot_claim_more_items_with_scroll_arrow(offset,cursor):
    s=Session();open_bag_only(s);r=long_bag(bag(s.p,offset,cursor))
    assert offset+3>=len(s.p["inventory"])
    result=s.call(r)
    assert result["available_actions"]==["wait"] and s.c.stage!="item_selected"


@pytest.mark.parametrize("xy,marker",[((5,6),"▶"),((11,6),"▶"),((18,9),"▼"),
                                     ((18,11),"▶"),((18,11),"▷")])
def test_long_bag_foreign_or_duplicate_markers_are_not_hm_selection(xy,marker):
    s=Session();open_bag_only(s);r=long_bag(bag(s.p,0,0));put(r,*xy,marker)
    result=s.call(r)
    assert result["available_actions"]==["wait"] and s.c.stage!="item_selected"


def test_arrow_cannot_replace_the_only_active_item_cursor():
    s=Session();open_bag_only(s);r=long_bag(bag(s.p,0,0));put(r,5,4,"▼")
    result=s.call(r)
    assert result["available_actions"]==["wait"] and s.c.stage!="item_selected"


def test_long_bag_inactive_cursor_only_waits_until_the_same_item_is_active():
    s=Session();open_bag_only(s)
    assert s.call(long_bag(bag(s.p,0,0,"▷")))["available_actions"]==["wait"]
    assert s.c.stage!="item_selected"
    s.expected(long_bag(bag(s.p,0,0)),"a")


def test_decorated_selected_bag_blinking_cannot_resend_selection_a():
    s=Session();open_bag_only(s);r=long_bag(bag(s.p,0,0))
    s.expected(r,"a")
    assert s.call(bag(s.p,0,0))["available_actions"]==["wait"]
    assert s.call(r)["available_actions"]==["wait"]


# 固定Booted=prompt、contained=para：文字完整不等於已出現可確認prompt。
def at_machine_boot(intent=SURF_INTENT):
    s=Session(intent);s.to_use();s.expected(use(s.p,s.offset,s.cursor),"a")
    assert s.c.stage=="boot"
    return s


def boot_page(s,arrow=None):
    return s.dialog([(14,"Booted up an HM!")],arrow=arrow)


def contained_page(s,arrow=None):
    return s.dialog([(14,"It contained"),(16,s.move+"!")],arrow=arrow)


@pytest.mark.parametrize("intent",INTENTS)
def test_boot_and_contained_without_native_arrow_do_not_advance_stage(intent):
    s=at_machine_boot(intent);before=deepcopy(s.c.baseline)
    assert s.call(boot_page(s))["available_actions"]==["wait"]
    assert s.c.stage=="boot" and "boot" not in s.c.machine_prompt_sent
    s.expected(boot_page(s,16),"a")
    assert s.c.stage=="contained" and s.c.machine_prompt_sent=={"boot"}
    assert s.call(contained_page(s))["available_actions"]==["wait"]
    assert s.c.stage=="contained" and "contained" not in s.c.machine_prompt_sent
    s.expected(contained_page(s,16),"a")
    assert s.c.stage=="teach" and s.c.machine_prompt_sent=={"boot","contained"}
    assert s.c.baseline==before


@pytest.mark.parametrize("intent",INTENTS)
def test_native_machine_prompt_a_is_not_resent_across_old_page_or_arrow_blink(intent):
    s=at_machine_boot(intent);s.expected(boot_page(s,16),"a")
    for arrow in (16,None,16):
        assert s.call(boot_page(s,arrow))["available_actions"]==["wait"]
    s.expected(contained_page(s,16),"a")
    for page_fn,arrow in [(contained_page,16),(contained_page,None),(contained_page,16),(boot_page,16)]:
        assert s.call(page_fn(s,arrow))["available_actions"]==["wait"]
    assert s.c.machine_prompt_sent=={"boot","contained"} and s.c.stage=="teach"


@pytest.mark.parametrize("intent",INTENTS)
def test_legacy_early_boot_a_recovers_once_on_real_prompt_without_baseline_reset(intent):
    s=at_machine_boot(intent)
    # 舊版曾在全文但無prompt時送A、記舊token並提早進contained；模擬熱載前狀態。
    s.c.actions.add(("boot","advance_boot","a"));s.c.stage="contained"
    del s.c.machine_prompt_sent
    baseline=deepcopy(s.c.baseline);before=deepcopy(s.p);old_actions=deepcopy(s.c.actions)
    assert s.call(boot_page(s))["available_actions"]==["wait"]
    assert s.c.stage=="contained" and s.c.machine_prompt_sent==set()
    s.expected(boot_page(s,16),"a")
    assert s.c.stage=="contained" and s.c.machine_prompt_sent=={"boot"}
    assert s.c.actions>=old_actions
    for arrow in (16,None,16):
        assert s.call(boot_page(s,arrow))["available_actions"]==["wait"]
    s.expected(contained_page(s,16),"a")
    assert s.c.stage=="teach" and s.c.machine_prompt_sent=={"boot","contained"}
    assert s.c.baseline==baseline and s.p==before


@pytest.mark.parametrize("case",["partial","wrong_machine","foreign_letter","wrong_arrow","extra_cursor"])
def test_legacy_recovery_needs_full_exact_boot_native_prompt(case):
    s=at_machine_boot();s.c.actions.add(("boot","advance_boot","a"));s.c.stage="contained"
    del s.c.machine_prompt_sent
    r=boot_page(s,16)
    if case=="partial":r=s.dialog([(14,"Booted up")],arrow=16)
    elif case=="wrong_machine":r=s.dialog([(14,"Booted up a TM!")],arrow=16)
    elif case=="foreign_letter":put(r,0,0,"X")
    elif case=="wrong_arrow":put(r,18,16," ");put(r,17,16,"▼")
    else:put(r,0,0,"▶")
    result=s.call(r)
    assert result["available_actions"]==["wait"]
    assert "boot" not in getattr(s.c,"machine_prompt_sent",set())
    assert s.c.stage=="contained"


def test_contained_wrong_move_or_partial_arrow_never_sets_prompt_acknowledged():
    s=at_machine_boot();s.expected(boot_page(s,16),"a")
    r=s.dialog([(14,"It contained"),(16,"SU")],arrow=16)
    assert s.call(r)["available_actions"]==["wait"]
    assert s.c.stage=="contained" and "contained" not in s.c.machine_prompt_sent
    r=s.dialog([(14,"It contained"),(16,"STRENGTH!")],arrow=16)
    review(s.call(r))
    assert s.c.stage=="contained" and "contained" not in s.c.machine_prompt_sent


@pytest.mark.parametrize("intent",INTENTS)
def test_forget_question_on_complete_party_background_waits_until_real_four_move_box(intent):
    s=Session(intent);s.to_forget();before=deepcopy(s.p);baseline=deepcopy(s.c.baseline)
    for lines in [[(14,"Which m")],[(14,"Which move should"),(16,"be f")],
                  [(14,"Which move should"),(16,"be forgotten?")]]:
        hint=s.call(s.dialog(lines,on_party=True))
        assert hint["available_actions"]==["wait"] and s.c.stage=="forget"
        assert not s.c.replacement_selected and s.p==before and s.c.baseline==baseline
    # 只有完整、順序正確的四招與active游標出現，才走到授權槽位。
    if intent["replace_index"]==1:s.expected(s.forget(8),"down")
    chosen=s.expected(s.forget(),"a")
    assert chosen["forgotten_move"]==intent["replace_move"]
    assert s.c.replacement_selected and s.c.stage=="receipt" and s.p==before


@pytest.mark.parametrize("change",["background_pollution","active_party_cursor","wrong_question_word","extra_which"])
def test_forget_drawing_does_not_accept_polluted_background_or_select_a_slot(change):
    s=Session();s.to_forget()
    r=s.dialog([(14,"Which move should"),(16,"be forgotten?")],on_party=True)
    if change=="background_pollution":put(r,0,0,"X")
    elif change=="active_party_cursor":put(r,0,s.target*2+1,"▶")
    elif change=="wrong_question_word":
        clear(r,0,16,19,16);put(r,1,16,"be chosen?")
    else:put(r,1,13,"Which")
    hint=s.call(r)
    assert hint["available_actions"]==["wait"] and not s.c.replacement_selected


@pytest.mark.parametrize("stage",["intro","delete"])
def test_forget_drawing_question_cannot_skip_the_delete_yes_stage(stage):
    s=Session()
    if stage=="intro":s.to_intro()
    else:s.to_delete()
    before=s.c.stage
    hint=s.call(s.dialog([(14,"Which move should"),(16,"be forgotten?")],on_party=True))
    assert hint["available_actions"]==["wait"] and not s.c.replacement_selected
    assert s.c.stage==before


def receipt_page(s,kind,arrow=None):
    lines={"forgot":[(14,s.name+" forgot"),(16,s.old+"!")],
           "and":[(14,"And...")],
           "learned":[(14,s.name+" learned"),(16,s.move+"!")]}
    return s.dialog(lines[kind],on_party=True,arrow=arrow)


@pytest.mark.parametrize("intent",INTENTS)
def test_receipts_wait_for_native_prompt_and_acknowledge_each_only_once(intent):
    s=Session(intent);s.to_receipt();baseline=deepcopy(s.c.baseline)
    for kind in ("forgot","and","learned"):
        if kind=="learned":s.install()
        before=deepcopy(s.p);sent=deepcopy(s.c.receipt_prompt_sent)
        flags=(s.c.seen_forgot,s.c.seen_and,s.c.seen_learned)
        assert s.call(receipt_page(s,kind))["available_actions"]==["wait"]
        assert s.c.stage=="receipt" and s.c.receipt_prompt_sent==sent
        assert (s.c.seen_forgot,s.c.seen_and,s.c.seen_learned)==flags
        s.expected(receipt_page(s,kind,16),"a")
        assert kind in s.c.receipt_prompt_sent and getattr(s.c,"seen_"+kind)
        actions=deepcopy(s.c.actions)
        for arrow in (16,None,16):
            assert s.call(receipt_page(s,kind,arrow))["available_actions"]==["wait"]
        assert s.c.actions==actions and s.c.baseline==baseline and s.p==before
    assert s.c.stage=="closing" and s.c.receipt_prompt_sent=={"forgot","and","learned"}
    assert s.c.error is None


def legacy_receipt_closing(intent=SURF_INTENT):
    s=Session(intent);s.to_closing()
    # 舊控制器已記學會、但無prompt的A只加速印字；保留原交易與舊action token。
    del s.c.receipt_prompt_sent
    s.c.actions.discard(("receipt","dismiss_exact_learned_native_prompt","a"))
    s.c.actions.add(("receipt","dismiss_exact_learned","a"))
    return s


@pytest.mark.parametrize("intent",INTENTS)
def test_legacy_learned_closing_recovers_once_then_requires_normal_b_and_two_closed_frames(intent):
    s=legacy_receipt_closing(intent)
    baseline=deepcopy(s.c.baseline);before=deepcopy(s.p);old_actions=deepcopy(s.c.actions)
    assert s.call(receipt_page(s,"learned"))["available_actions"]==["wait"]
    assert s.c.stage=="closing" and s.c.receipt_prompt_sent==set()
    s.expected(receipt_page(s,"learned",16),"a")
    assert s.c.stage=="closing" and s.c.receipt_prompt_sent=={"learned"}
    assert s.c.actions>=old_actions
    actions=deepcopy(s.c.actions)
    for arrow in (16,None,16):
        out=s.call(receipt_page(s,"learned",arrow))
        assert out["available_actions"]==["wait"] and not out.get("hm_teaching_complete")
    assert s.c.actions==actions and s.c.baseline==baseline and s.p==before
    s.expected(bag(s.p,s.offset,s.cursor),"b");s.expected(start(),"b")
    assert not s.call(ready=True,window=False).get("hm_teaching_complete")
    assert not s.call(ready=True,window=False,same=True).get("hm_teaching_complete")
    assert s.call(ready=True,window=False)["hm_teaching_complete"] is True
    assert s.c.baseline==baseline and s.p==before


@pytest.mark.parametrize("change",["wrong_name","wrong_move","wrong_pp","foreign_cursor"])
def test_legacy_learned_prompt_recovery_rejects_wrong_identity_move_pp_or_marker(change):
    s=legacy_receipt_closing();baseline=deepcopy(s.c.baseline)
    r=receipt_page(s,"learned",16)
    if change=="wrong_name":
        clear(r,0,14,19,14);put(r,1,14,"SNORLAX learned")
    elif change=="wrong_move":
        clear(r,0,16,17,16);put(r,1,16,"STRENGTH!")
    elif change=="wrong_pp":s.p["party"][s.target]["pp"][s.intent["replace_index"]]=14
    else:put(r,0,0,"▶")
    old_actions=deepcopy(s.c.actions)
    review(s.call(r))
    assert "learned" not in getattr(s.c,"receipt_prompt_sent",set())
    assert s.c.actions==old_actions and s.c.baseline==baseline


@pytest.mark.parametrize("intent",INTENTS)
def test_partial_learned_text_with_arrow_cannot_acknowledge_legacy_prompt(intent):
    s=legacy_receipt_closing(intent);old_actions=deepcopy(s.c.actions)
    r=s.dialog([(14,s.name+" learned"),(16,s.move[:2])],on_party=True,arrow=16)
    out=s.call(r)
    assert out["available_actions"]==["wait"] and not out.get("hm_teaching_complete")
    assert "learned" not in getattr(s.c,"receipt_prompt_sent",set())
    assert s.c.stage=="closing" and s.c.actions==old_actions


def inactive_start(row=6):
    return put(start(row),11,row,"▷")


def test_inactive_start_and_opening_bag_wait_until_native_active_menu():
    s=Session();s.expected(canvas(),"start",ready=True,window=False)
    before=deepcopy(s.c.actions)
    assert s.call(inactive_start())["available_actions"]==["wait"]
    assert s.c.stage=="start" and s.c.actions==before
    s.expected(start(),"a")
    before=deepcopy(s.c.actions)
    assert s.call(inactive_start())["available_actions"]==["wait"]
    assert s.c.stage=="opening_bag" and s.c.actions==before
    s.expected(bag(s.p),"a")
    assert s.c.stage=="item_selected"


def test_closing_inactive_start_cannot_close_or_complete_until_active_and_two_world_frames():
    s=Session();s.to_closing();s.expected(bag(s.p,s.offset,s.cursor),"b")
    baseline=deepcopy(s.c.baseline);before=deepcopy(s.c.actions)
    out=s.call(inactive_start())
    assert out["available_actions"]==["wait"] and not out.get("hm_teaching_complete")
    assert s.c.stage=="closing" and s.c.close_frame is None and s.c.actions==before
    s.expected(start(),"b")
    assert not s.call(ready=True,window=False).get("hm_teaching_complete")
    assert not s.call(ready=True,window=False,same=True).get("hm_teaching_complete")
    assert s.call(ready=True,window=False)["hm_teaching_complete"] is True
    assert s.c.baseline==baseline


@pytest.mark.parametrize("change",["wrong_position","duplicate_marker","foreign_text"])
def test_closing_inactive_start_with_unknown_marker_or_pollution_never_sends_a_or_b(change):
    s=Session();s.to_closing();r=inactive_start()
    if change=="wrong_position":put(r,11,6," ");put(r,11,5,"▷")
    elif change=="duplicate_marker":put(r,11,4,"▶")
    else:put(r,0,0,"X")
    before=deepcopy(s.c.actions)
    review(s.call(r))
    assert s.c.stage=="closing" and s.c.close_frame is None and s.c.actions==before


def test_partial_inactive_start_only_waits_and_does_not_unlock_item_selection():
    s=Session();s.expected(canvas(),"start",ready=True,window=False)
    r=inactive_start();clear(r,12,14,19,14)
    before=deepcopy(s.c.actions)
    assert s.call(r)["available_actions"]==["wait"]
    assert s.c.stage=="start" and s.c.actions==before
    assert s.call(inactive_start())["available_actions"]==["wait"]
    s.expected(start(),"a")

