"""HM02 固定教學的六人原生格合成測試；不建立模擬器或操作遊戲。"""
from copy import deepcopy

import pytest

from laya_pokemon import hm_teaching as hm
from laya_pokemon import hm_teaching_bridge as bridge
from tests.test_hm_teaching import canvas, clear, packet, put, start


LOCATION = {"map_id": 188, "x": 1, "y": 3}
BEFORE_MOVES = [64, 65, 43, 31]
AFTER_MOVES = [64, 65, 19, 31]
MOVE_NAMES = ("PECK", "DRILL PECK", "LEER", "FURY ATTACK")
BAG_LABELS = {197: "HM02", 198: "HM03", 199: "HM04", 4: "POKÉ BALL",
              196: "HM01", 211: "TM11"}


def fly_progress(*, fearow_index=5, hm_index=0):
    specs = [
        (19, "LAPRAS", [55, 34, 47, 54], [25, 15, 15, 30], 135),
        (132, "SNORLAX", [70, 133, 156, 34], [15, 20, 10, 15], 168),
        (7, "NIDOKING", [61, 57, 30, 40], [20, 15, 25, 35], 121),
        (102, "EEVEE", [33, 28, 98, 39], [35, 15, 30, 30], 90),
        (154, "VENUSAUR", [75, 15, 73, 22], [25, 30, 10, 10], 111),
        (35, "FEAROW", BEFORE_MOVES, [35, 20, 30, 20], 108),
    ]
    specs.insert(fearow_index, specs.pop())
    inventory = [(198, 1), (199, 1), (4, 6), (196, 1), (211, 1)]
    inventory.insert(hm_index, (197, 1))
    return dict(
        profile=hm.PROGRESS_PROFILE, initialization_candidate=True,
        party_read_valid=True, party_count=6, player_name_raw="KEVIN", money=41066,
        inventory=[dict(item=i, quantity=q) for i, q in inventory],
        party=[dict(species=s, species_name=name, level=35, hp=hp, max_hp=hp,
                    status=0, exp=35**3, moves=list(moves), pp=list(pp))
               for s, name, moves, pp, hp in specs],
    )


def bag(p, offset=0, cursor=0, marker="▶"):
    r = clear(start(), 4, 2, 19, 12)
    for n in range(4):
        idx, y = offset + n, 4 + n * 2
        if idx == len(p["inventory"]):
            put(r, 6, y, "CANCEL")
            break
        if idx > len(p["inventory"]):
            break
        entry = p["inventory"][idx]
        put(r, 6, y, BAG_LABELS[entry["item"]])
        if entry["item"] not in (196, 197, 198, 199):
            put(r, 14, y + 1, f'×{entry["quantity"]:2}')
    return put(r, 5, 4 + cursor * 2, marker)


def use(p, offset, cursor, y=11, marker="▶"):
    r = clear(bag(p, offset, cursor, "▷"), 13, 10, 19, 15)
    put(r, 15, 11, "USE")
    put(r, 15, 13, "TOSS")
    return put(r, 14, y, marker)


def party(p, index=0, marker="▶"):
    r = canvas()
    for i, mon in enumerate(p["party"]):
        put(r, 3, i * 2, mon["species_name"])
        put(r, 13, i * 2, f'{mon["level"]:3}')
        put(r, 12, i * 2 + 1, "ABLE" if mon["species"] == 35 else "NOT ABLE")
    put(r, 0, index * 2 + 1, marker)
    put(r, 1, 14, "Use TM on which")
    return put(r, 1, 16, "POKéMON?")


def plan():
    return {"steps": [
        dict(id="fly", kind="interact", map_id=188, target=[1, 3],
             mechanic="teach_fly_fearow", hm_intent=deepcopy(hm.FLY_INTENT)),
        dict(id="next", kind="move", map_id=188, target=[1, 4]),
    ]}


@pytest.fixture(autouse=True)
def isolated_bridge(monkeypatch):
    monkeypatch.setattr(bridge, "_CONTROLLERS", {})
    monkeypatch.setattr(bridge, "_BINDINGS", {})
    monkeypatch.setattr(bridge, "_COMPLETED", set())
    monkeypatch.setattr("laya_pokemon.campaign_transactions.ui_overworld_ready",
                        lambda text, grid: text["window_visible"] is False
                        and text["cells"] == canvas())


class FlySession:
    """獨立 FLY 格模板；不沿用舊測試的 Surf/Strength 二選一資料。"""

    def __init__(self, *, fearow_index=5, hm_index=0, via_bridge=False):
        self.p = fly_progress(fearow_index=fearow_index, hm_index=hm_index)
        self.target, self.hm_index = fearow_index, hm_index
        self.offset, self.cursor = max(0, hm_index - 2), min(2, hm_index)
        self.frame, self.now = 0, 0.0
        self.via_bridge, self.plan = via_bridge, plan()
        self.controller = hm.HMTeachingController(hm.FLY_INTENT) if not via_bridge else None
        self.next_step = "fly"

    @property
    def c(self):
        return bridge._CONTROLLERS["fly"] if self.via_bridge else self.controller

    def call(self, r=None, *, ready=False, same=False, window=True, p=None,
             location=None, text=None):
        if not same:
            self.frame += 1
            self.now += .05
        p = self.p if p is None else p
        text = packet(r, window) if text is None else text
        location = deepcopy(LOCATION if location is None else location)
        if self.via_bridge:
            state = dict(frame=self.frame, location=location, progress=p,
                         battle_state=dict(kind="none", active=False, raw=0,
                                           observation_frame=self.frame))
            result = bridge.context(state, self.plan, "fly", text, object())
            assert result is not None
            out, self.next_step = result
            return out
        return self.c.context(text, p, location=location, frame=self.frame,
                              now=self.now, overworld_ready=ready, battle_active=False)

    def expected(self, r, action, **kwargs):
        out = self.call(r, **kwargs)
        assert out["available_actions"] == [action, "wait"], out
        return out

    def dialog(self, lines, *, on_party=False, choose=False, y=8, arrow=None):
        r = party(self.p, self.target, "▷") if on_party else use(
            self.p, self.offset, self.cursor, marker="▷")
        clear(r, 0, 12, 19, 17)
        if choose:
            clear(r, 14, 7, 19, 12)
            put(r, 16, 8, "YES")
            put(r, 16, 10, "NO")
            put(r, 15, y, "▶")
        for row, text in lines:
            put(r, 1, row, text)
        if arrow is not None:
            put(r, 18, arrow, "▼")
        return r

    def forget(self, y=10):
        r = clear(party(self.p, self.target, "▷"), 4, 7, 19, 12)
        clear(r, 0, 12, 19, 17)
        for i, name in enumerate(MOVE_NAMES):
            put(r, 6, 8 + i, name)
        put(r, 5, y, "▶")
        put(r, 1, 14, "Which move should")
        return put(r, 1, 16, "be forgotten?")

    def to_party(self):
        self.expected(canvas(), "start", ready=True, window=False)
        self.expected(start(2), "down")
        self.expected(start(4), "down")
        self.expected(start(6), "a")
        for current in range(self.hm_index + 1):
            off, cur = max(0, current - 2), min(2, current)
            self.expected(bag(self.p, off, cur),
                          "a" if current == self.hm_index else "down")
        self.expected(use(self.p, self.offset, self.cursor, 13), "up")
        self.expected(use(self.p, self.offset, self.cursor), "a")
        self.expected(self.dialog([(14, "Booted up an HM!")], arrow=16), "a")
        self.expected(self.dialog([(14, "It contained"), (16, "FLY!")], arrow=16), "a")
        self.expected(self.dialog([(14, "Teach FLY"), (16, "to a POKéMON?")],
                                  choose=True, y=10), "up")
        self.expected(self.dialog([(14, "Teach FLY"), (16, "to a POKéMON?")],
                                  choose=True), "a")

    def to_forget(self):
        self.to_party()
        for index in range(self.target + 1):
            self.expected(party(self.p, index), "a" if index == self.target else "down")
        for lines in (
            [(14, "FEAROW is"), (16, "trying to learn")],
            [(14, "trying to learn"), (16, "FLY!")],
            [(14, "But, FEAROW"), (16, "can't learn more")],
            [(14, "can't learn more"), (16, "than 4 moves!")],
        ):
            self.expected(self.dialog(lines, on_party=True), "a")
        self.expected(self.dialog([(13, "Delete an older"), (14, "move to make room"),
                                   (16, "for FLY?")], on_party=True, choose=True), "a")

    def to_receipt(self):
        self.to_forget()
        self.expected(self.forget(8), "down")
        self.expected(self.forget(9), "down")
        out = self.expected(self.forget(10), "a")
        assert out["forgotten_move"] == 43

    def install(self):
        self.p["party"][self.target]["moves"][2] = 19
        self.p["party"][self.target]["pp"][2] = 15

    def to_closing(self):
        self.to_receipt()
        assert self.call(self.dialog([(14, "1, 2 and...")], on_party=True))[
            "available_actions"] == ["wait"]
        self.expected(self.dialog([(14, "1, 2 and... Poof!")],
                                  on_party=True, arrow=16), "a")
        self.expected(self.dialog([(14, "FEAROW forgot"), (16, "LEER!")],
                                  on_party=True, arrow=16), "a")
        self.expected(self.dialog([(14, "And...")], on_party=True, arrow=16), "a")
        self.install()
        self.expected(self.dialog([(14, "FEAROW learned"), (16, "FLY!")],
                                  on_party=True, arrow=16), "a")

    def finish(self):
        self.to_closing()
        self.expected(bag(self.p, self.offset, self.cursor), "b")
        self.expected(start(), "b")
        assert self.call(ready=True, window=False)["available_actions"] == ["wait"]
        assert not self.call(ready=True, window=False, same=True).get("hm_teaching_complete")
        return self.call(ready=True, window=False)


def review(out):
    assert out["phase"] == "campaign_review" and out["available_actions"] == ["wait"], out


@pytest.mark.parametrize("fearow_index,hm_index,via_bridge", [
    (5, 0, False), (4, 4, False), (0, 5, False), (5, 4, True),
])
def test_complete_six_member_fly_flow_changes_only_leer_and_its_pp(
        fearow_index, hm_index, via_bridge):
    s = FlySession(fearow_index=fearow_index, hm_index=hm_index, via_bridge=via_bridge)
    # 保護非目標槽的既有 PP Up 高位與剩餘 PP。
    s.p["party"][s.target]["pp"] = [0x40 + 40, 0x80 + 25, 30, 0x40 + 23]
    before = deepcopy(s.p)
    out = s.finish()
    expected = deepcopy(before)
    expected["party"][s.target]["moves"][2] = 19
    expected["party"][s.target]["pp"][2] = 15
    assert s.p == expected
    assert out["hm_teaching_complete"] is True
    assert out["hm_teaching_kind"] == "teach_fly_fearow"
    assert out["moves_verified"] == AFTER_MOVES
    assert out["hm_preserved"] == 197 and out["hm_quantity_used"] == 0
    assert out["available_actions"] == ["wait"]
    assert s.c.location == LOCATION and s.c.baseline == before["party"]
    if via_bridge:
        assert s.next_step == "next" and bridge._COMPLETED == {"fly"}


@pytest.mark.parametrize("field,value", [
    ("species", 7), ("species", True), ("item", 198), ("move", 57),
    ("replace_move", 65), ("replace_index", 1), ("replace_index", True),
    ("kind", "teach_strength_snorlax"),
])
def test_fly_constructor_accepts_only_exact_fixed_contract(field, value):
    bad = deepcopy(hm.FLY_INTENT)
    bad[field] = value
    with pytest.raises(ValueError):
        hm.HMTeachingController(bad)


@pytest.mark.parametrize("mutation", [
    lambda p: p["party"][-1].update(moves=AFTER_MOVES, pp=[35, 20, 15, 20]),
    lambda p: p["party"][-1].update(moves=[64, 65, 45, 31]),
    lambda p: p["party"][-1].update(species=21, species_name="SPEAROW"),
    lambda p: p["party"].__setitem__(0, deepcopy(p["party"][-1])),
    lambda p: p["inventory"].pop(0),
    lambda p: p["inventory"][0].update(quantity=2),
])
def test_initial_already_fly_wrong_learner_or_hm_never_starts(mutation):
    s = FlySession()
    mutation(s.p)
    review(s.call(ready=True, window=False))
    assert not s.c.actions and not s.c.replacement_selected


def test_foreget_cursor_moves_past_drill_peck_without_confirming_it():
    s = FlySession()
    s.to_forget()
    s.expected(s.forget(8), "down")
    assert s.call()["available_actions"] == ["wait"]
    assert s.call(s.forget(8))["available_actions"] == ["wait"]
    s.expected(s.forget(9), "down")
    assert s.c.replacement_selected is False
    s.expected(s.forget(10), "a")
    assert s.c.replacement_selected is True
    assert s.call(s.forget(10), same=True)["available_actions"] == ["wait"]


@pytest.mark.parametrize("bad_page", ["wrong_label", "duplicate_cursor", "wrong_receipt"])
def test_wrong_forget_target_or_receipt_never_gets_a(bad_page):
    s = FlySession()
    s.to_forget()
    if bad_page == "wrong_receipt":
        r = s.dialog([(14, "FEAROW forgot"), (16, "DRILL PECK!")], on_party=True, arrow=16)
    else:
        r = s.forget(10)
        if bad_page == "wrong_label":
            clear(r, 6, 10, 19, 10)
            put(r, 6, 10, "PECK")
        else:
            put(r, 5, 9, "▶")
    review(s.call(r))
    assert s.c.replacement_selected is False


@pytest.mark.parametrize("mutation", [
    lambda p: p["party"][-1].update(moves=[64, 19, 43, 31], pp=[35, 15, 30, 20]),
    lambda p: p["party"][-1]["pp"].__setitem__(0, 34),
    lambda p: p["inventory"].pop(0),
    lambda p: p.update(money=41065),
    lambda p: p["party"][0].update(hp=134),
    lambda p: p["party"][0]["pp"].__setitem__(0, 24),
])
def test_post_selection_wrong_slot_consumed_hm_or_other_changes_review(mutation):
    s = FlySession()
    s.to_receipt()
    s.install()
    mutation(s.p)
    review(s.call())
    assert not s.c.seen_learned


@pytest.mark.parametrize("field,value", [
    ("map_id", 155), ("target", [2, 6]), ("target", [True, 3]),
    ("kind", "move"), ("hm_intent", hm.STRENGTH_INTENT),
    ("hm_intent", {**hm.FLY_INTENT, "replace_index": 1}),
])
def test_bridge_rejects_wrong_map_stance_or_intent_without_binding(field, value):
    p = plan()
    p["steps"][0][field] = deepcopy(value)
    state = dict(frame=1, location=deepcopy(LOCATION), progress=fly_progress(),
                 battle_state=dict(kind="none", active=False, raw=0, observation_frame=1))
    out, step_id = bridge.context(state, p, "fly", packet(window=False), object())
    review(out)
    assert step_id == "fly" and not bridge._CONTROLLERS and not bridge._BINDINGS


@pytest.mark.parametrize("location", [
    {"map_id": 155, "x": 4, "y": 5}, {"map_id": 188, "x": 2, "y": 6},
])
def test_bridge_initial_actual_location_must_be_exact_approved_fly_stance(location):
    state = dict(frame=1, location=location, progress=fly_progress())
    assert bridge.context(state, plan(), "fly", packet(window=False), object()) is None
    assert not bridge._CONTROLLERS


@pytest.mark.parametrize("mechanic,intent", [
    ("teach_surf_nidoking", hm.SURF_INTENT),
    ("teach_strength_snorlax", hm.STRENGTH_INTENT),
])
def test_existing_hm_intents_cannot_use_new_fly_house_location(mechanic, intent):
    p = plan()
    p["steps"][0].update(mechanic=mechanic, hm_intent=deepcopy(intent))
    state = dict(frame=1, location=deepcopy(LOCATION), progress=fly_progress())
    out, _ = bridge.context(state, p, "fly", packet(window=False), object())
    review(out)
    assert not bridge._CONTROLLERS


def test_bound_fly_intent_cannot_be_changed_into_legacy_strength_or_rebuilt():
    s = FlySession(via_bridge=True)
    s.expected(canvas(), "start", ready=True, window=False)
    c, baseline = s.c, deepcopy(s.c.baseline)
    s.plan["steps"][0].update(mechanic="teach_strength_snorlax", map_id=155,
                              target=[4, 5], hm_intent=deepcopy(hm.STRENGTH_INTENT))
    review(s.call(start()))
    assert s.c is c and s.c.baseline == baseline


def test_fly_machine_prompt_requires_arrow_and_old_page_cannot_resend_a():
    s = FlySession()
    s.expected(canvas(), "start", ready=True, window=False)
    s.expected(start(), "a")
    s.expected(bag(s.p), "a")
    s.expected(use(s.p, 0, 0), "a")
    full_without_prompt = s.dialog([(14, "Booted up an HM!")])
    assert s.call(full_without_prompt)["available_actions"] == ["wait"]
    s.expected(s.dialog([(14, "Booted up an HM!")], arrow=16), "a")
    assert s.call()["available_actions"] == ["wait"]
    assert s.call(full_without_prompt)["available_actions"] == ["wait"]
    assert s.c.error is None
