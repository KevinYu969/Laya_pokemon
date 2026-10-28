"""Portable contracts using the real pure controller, readonly getters and SDK.

Only synthetic memory is provided; no ROM, saved state, game, source cache,
model, or network is opened. Formal tests load only src and tests fixtures.
"""
from copy import deepcopy
import importlib.util
import importlib
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import pytest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
if HERE.name == "staged-route23-land-guards-20261028" and HERE.parent.name == ".local":
    ROOT = HERE.parent.parent
    PURE_PATH = HERE / "route23_land_guards.py"
elif HERE.name == "tests":
    ROOT = HERE.parent
    PURE_PATH = ROOT / "src/laya_pokemon/route23_land_guards.py"
else:
    raise RuntimeError("This test requires the exact stage or formal tests directory")

from laya_pokemon import route23_surf as surf, route23_water as water
from laya_pokemon.observation import PROFILE as TEXT_PROFILE
from laya_pokemon.progress import PROFILE as PROGRESS_PROFILE
from laya_pokemon.rocket_movement import read_rocket_movement
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as SDK
import laya_pokemon

for dependency in (surf, water):
    assert Path(dependency.__file__).resolve() == (ROOT / "src/laya_pokemon" / Path(dependency.__file__).name).resolve()
if HERE.name != 'tests':raise RuntimeError('正式測試只載formal module；stage另有凍結測試')
pure=importlib.import_module('laya_pokemon.route23_land_guards')
assert Path(pure.__file__).resolve()==PURE_PATH.resolve()
BRIDGE_PATH = PURE_PATH.with_name("route23_land_guards_bridge.py")
bridge=importlib.import_module('laya_pokemon.route23_land_guards_bridge')
assert Path(bridge.__file__).resolve()==BRIDGE_PATH.resolve()

KEYS = ("cascade", "thunder", "rainbow", "volcano", "earth")
BADGES = {"cascade": (0, "CASCADEBADGE"), "thunder": (1, "THUNDERBADGE"),
          "rainbow": (2, "RAINBOWBADGE"), "volcano": (5, "VOLCANOBADGE"), "earth": (6, "EARTHBADGE")}
EXPECTED_GEOMETRY = {"cascade": (7, 136, 0x23), "thunder": (9, 119, 0x23),
                     "rainbow": (10, 105, 0x2c), "volcano": (11, 56, 0x2c), "earth": (7, 35, 0x2c)}


def progress():
    # Legal dynamic six-party values, different from the old Route23 job.
    data = [(19, "LAPRAS", 42, 171, [57, 34, 58, 109], [15, 15, 10, 10]),
            (132, "SNORLAX", 43, 209, [70, 133, 156, 34], [15, 20, 10, 15]),
            (102, "EEVEE", 37, 96, [33, 28, 98, 39], [35, 15, 30, 30]),
            (154, "VENUSAUR", 38, 120, [75, 15, 73, 22], [25, 30, 10, 10]),
            (35, "FEAROW", 39, 121, [64, 65, 19, 31], [35, 20, 15, 20]),
            (7, "NIDOKING", 40, 137, [61, 57, 30, 40], [20, 15, 25, 35])]
    return dict(profile=PROGRESS_PROFILE, initialization_candidate=True, party_read_valid=True,
                party_count=6, party=[dict(species=s, species_name=n, level=l, hp=h, max_hp=h,
                exp=91000, status=0, moves=m, pp=pp) for s,n,l,h,m,pp in data],
                inventory=[dict(item=18, quantity=7), dict(item=52, quantity=6), dict(item=4, quantity=1)],
                money=48123, badges_raw=255, player_name_raw="KEVIN")


def text(rows=None, *, window=False):
    cells = [list(row) for row in (surf._blank() if rows is None else rows)]
    visible = [(y, "".join(row).rstrip()) for y, row in enumerate(cells)
               if re.search(r"[A-Za-z0-9]{2,}", "".join(row))][:12]
    return dict(profile=TEXT_PROFILE, read_valid=True, alignment_verified=True, read_error=None,
                window_visible=window, cells=cells, lines=[v for _,v in visible], line_rows=[y for y,_ in visible])


def page(case, number, arrow=None):
    badge = BADGES[case][1]
    pairs = (("YOU CAN PASS HERE", "ONLY IF YOU HAVE"), ("ONLY IF YOU HAVE", "THE " + badge + "!"),
             ("OH! THAT IS THE", badge + "!"), ("OK THEN! PLEASE,", "GO RIGHT AHEAD!"))
    rows = [list(row) for row in surf._blank()]
    for y, line in zip((14, 16), pairs[number]):
        surf._put(rows, 1, y, line)
    if arrow is None:
        arrow = number < 3
    if arrow:
        surf._put(rows, 18, 16, "▼")
    return rows


def partial(case="cascade"):
    rows = page(case, 0, False)
    rows[14] = list(" " * 20)
    rows[16] = list(" " * 20)
    surf._put(rows, 1, 14, "YOU CAN")
    return rows


def grid(loc, frame, case):
    tiles = [[0x2c] * 20 for _ in range(144)]
    walkable = [[1] * 20 for _ in range(144)]
    tiles[loc["y"]][loc["x"]] = pure.CASES[case]["tile"]
    cells = sorted(([x, y] for y in range(144) for x in range(20)),
                   key=lambda p: (abs(p[0]-loc["x"]) + abs(p[1]-loc["y"]), p[1], p[0]))[:20]
    return dict(tileset_id=23, observation_frame=frame, verified_location=[loc[k] for k in ("map_id", "x", "y")],
                tiles=tiles, walkable=walkable, visible_verified_cells=cells, screen_cells_verified=len(cells))


class Memory:
    """Synthetic readonly byte interface; the production getters remain real."""
    def __init__(self, loc, flags, script, *, mode=0, battle=0, movement=None):
        self.values = {address: 0 for address in surf.ADDRESSES.values()}
        self.values.update({0xD35E: loc["map_id"], 0xD361: loc["y"], 0xD362: loc["x"],
                            0xC109: 4, 0xD356: 255, 0xD7ED: flags, 0xD667: script,
                            0xD700: mode, 0xD057: battle})
        for slot, (x, y) in enumerate(surf.NPC_POSITIONS, 1):
            self.values.update({0xC100+16*slot: 1, 0xC200+16*slot+5: x+4, 0xC200+16*slot+4: y+4})
        self.values.update(movement or {})

    def __getitem__(self, address):
        return self.values.get(address, 0)

    def __setitem__(self, address, value):
        raise AssertionError("Readonly getters must never write memory")


class Guard:
    def __init__(self, case="cascade", *, flags=None, party=None):
        self.case = case
        self.spec = pure.CASES[case]
        self.c = pure.Route23LandGuardController(deepcopy(pure.INTENTS[case]))
        self.loc = dict(map_id=34, x=self.spec["x"], y=self.spec["y"])
        self.flags = (1 << self.spec["bit"]) - 1 if flags is None else flags
        self.p = progress() if party is None else deepcopy(party)
        self.f = 100
        self.now = 0.0
        self.last = None

    def call(self, rows=None, prev=("wait",), *, script=0, mode=0, battle=0,
             window=None, now=None, same=False, mutate=None, movement_bytes=None):
        if not same:
            self.f += 40
        self.now = self.now + .1 if now is None else now
        pb = SimpleNamespace(frame_count=self.f, memory=Memory(self.loc, self.flags, script,
                              mode=mode, battle=battle, movement=movement_bytes))
        signal = surf.read_surf_observation(pb, self.f, SDK)
        movement = read_rocket_movement(pb, observation_frame=self.f)
        state = dict(frame=self.f, location=deepcopy(self.loc), progress=deepcopy(self.p),
                     text=text(rows, window=rows is not None if window is None else window),
                     battle_state=dict(raw=battle, kind="wild" if battle == 1 else "none",
                                       active=battle != 0, observation_frame=self.f))
        args = dict(grid=grid(self.loc, self.f, self.case), signal=signal, movement=movement,
                    previous=prev, now=self.now)
        if mutate:
            mutate(state, args)
        self.last = deepcopy((state, args))
        self.pb = pb
        before = deepcopy((state, args))
        result = self.dispatch(state, args, pb)
        assert (state, args) == before, "Pure context mutated its observation inputs"
        return result

    def repeat(self):
        state, args = deepcopy(self.last)
        before = deepcopy((state, args))
        result = self.dispatch(state, args, self.pb)
        assert (state, args) == before
        return result

    def dispatch(self, state, args, pb):
        return self.c.context(state, **args)

    def offer_done(self):
        assert_action(self.call(page(self.case, 0)), "a")
        assert_action(self.call(page(self.case, 1), ("a",)), "a")
        assert_action(self.call(page(self.case, 2), ("a",)), "a")
        assert_action(self.call(page(self.case, 3), ("a",)), "wait")
        assert_action(self.call(page(self.case, 3)), "a")

    def close(self, *, observe_script2=False):
        self.flags |= 1 << self.spec["bit"]
        first = self.call(prev=("a",), script=2 if observe_script2 else 0)
        assert not first["route23_land_guard_complete"]
        if observe_script2:
            assert not self.call()["route23_land_guard_complete"]
        return self.call()


def assert_action(result, action):
    assert result["available_actions"] == (["wait"] if action == "wait" else [action, "wait"])
    assert result["phase"] == "route23_land_guard"
    assert not result["route23_land_guard_complete"]


def review(result):
    assert result["phase"] == "campaign_review"
    assert result["available_actions"] == ["wait"]
    assert not result["route23_land_guard_complete"]
    return result["review_reason"]


def test_exact_portable_loader_and_public_fixture_sdk_event_anchors():
    assert Path(pure.__file__).resolve() == PURE_PATH.resolve()
    assert set(pure.CASES) == set(pure.INTENTS) == set(KEYS)
    fixture = json.loads((ROOT / "tests/fixtures/route23_source.json").read_text(encoding="utf-8"))
    assert fixture["source_commit"] == surf.SOURCE_COMMIT
    assert fixture["event_byte_address"] == surf.ADDRESSES["guard_flags"] == 0xD7ED
    for key, (bit, badge) in BADGES.items():
        assert pure.CASES[key]["bit"] == bit and pure.CASES[key]["badge"] == badge
        assert tuple(pure.CASES[key][k] for k in ("x", "y", "tile")) == EXPECTED_GEOMETRY[key]
        assert SDK.EVENT_FLAGS["passed_" + key + "badge_check"] == 0x530 + bit


@pytest.mark.parametrize("observe_script2", [False, True])
def test_postreview_own_bit_cannot_regress_after_being_observed_even_before_world_closure(observe_script2):
    s = Guard()
    s.offer_done()
    original = s.flags
    s.flags |= 1 << s.spec["bit"]
    assert not s.call(prev=("a",), script=2 if observe_script2 else 0)["route23_land_guard_complete"]
    assert s.c.event_seen is True
    s.flags = original
    reason = review(s.call())
    s.flags |= 1 << s.spec["bit"]
    assert review(s.call()) == reason


@pytest.mark.parametrize("case", KEYS)
@pytest.mark.parametrize("script2", [False, True])
def test_five_true_four_page_transactions_require_actual_a_and_two_fresh_closed_frames(case, script2):
    s = Guard(case)
    baseline = deepcopy(s.p)
    s.offer_done()
    result = s.close(observe_script2=script2)
    assert result["route23_land_guard_complete"] is True
    assert result["available_actions"] == ["wait"]
    assert s.p == baseline
    assert s.flags == ((1 << s.spec["bit"]) - 1) | (1 << s.spec["bit"])


@pytest.mark.parametrize("case", KEYS)
def test_initial_blank_window_partial_and_arrow_blink_do_not_require_an_invented_start_a(case):
    s = Guard(case)
    assert_action(s.call(window=True), "wait")
    assert_action(s.call(partial(case)), "wait")
    assert_action(s.call(page(case, 0, False)), "wait")
    assert_action(s.call(page(case, 0)), "a")


@pytest.mark.parametrize("page_number", [0, 1, 2])
def test_offered_a_is_not_an_actual_receipt_and_cannot_advance_page(page_number):
    s = Guard()
    for n in range(page_number + 1):
        assert_action(s.call(page(s.case, n), ("a",) if n else ("wait",)), "a")
    review(s.call(page(s.case, page_number + 1), ("wait",)))


def test_actual_a_ack_can_wait_on_unchanged_old_rows_before_native_next_page():
    s = Guard()
    assert_action(s.call(page(s.case, 0)), "a")
    assert_action(s.call(page(s.case, 0), ("a",)), "wait")
    assert_action(s.call(page(s.case, 0)), "wait")
    assert_action(s.call(page(s.case, 1)), "a")


def test_previous_last_action_is_the_receipt_not_an_earlier_a_in_the_list():
    s = Guard()
    s.call(page(s.case, 0))
    review(s.call(page(s.case, 1), ("a", "wait")))
    s = Guard()
    s.call(page(s.case, 0))
    assert_action(s.call(page(s.case, 1), ("wait", "a")), "a")


@pytest.mark.parametrize("fault", ["unknown", "wrong_badge", "extra_marker", "extra_letter", "wrong_row", "early_arrow"])
def test_unknown_or_polluted_page_never_becomes_a_source_prompt(fault):
    s = Guard()
    rows = page(s.case, 0)
    if fault == "unknown":
        surf._put(rows, 1, 14, "HELLO STRANGER!")
    elif fault == "wrong_badge":
        rows = page("earth", 1)
    elif fault == "extra_marker":
        surf._put(rows, 0, 0, "▶")
    elif fault == "extra_letter":
        surf._put(rows, 0, 14, "X")
    elif fault == "wrong_row":
        rows[13], rows[14] = rows[14], rows[13]
    else:
        rows = partial()
        surf._put(rows, 18, 16, "▼")
    review(s.call(rows))


def test_done_has_no_arrow_and_requires_two_distinct_full_frames_before_offer():
    s = Guard()
    s.call(page(s.case, 0))
    s.call(page(s.case, 1), ("a",))
    s.call(page(s.case, 2), ("a",))
    review(s.call(page(s.case, 3, True), ("a",)))
    s = Guard()
    s.call(page(s.case, 0))
    s.call(page(s.case, 1), ("a",))
    s.call(page(s.case, 2), ("a",))
    assert_action(s.call(page(s.case, 3), ("a",)), "wait")
    assert_action(s.repeat(), "wait")
    assert_action(s.call(page(s.case, 3)), "a")


def test_unexecuted_final_a_retry_does_not_accept_a_done_page_with_prompt_arrow():
    s = Guard()
    s.offer_done()
    pending = s.c.pending
    review(s.call(page(s.case, 3, True)))
    assert s.c.pending is pending and pending["executed"] is False


@pytest.mark.parametrize("moment", ["page0", "done_offer_without_ack"])
@pytest.mark.parametrize("bit_kind", ["own", "other"])
def test_event_changes_before_true_done_a_or_unrelated_bit_changes_review(moment, bit_kind):
    s = Guard()
    if moment == "page0":
        s.call(page(s.case, 0))
    else:
        s.offer_done()
    s.flags ^= 1 << (s.spec["bit"] if bit_kind == "own" else 6)
    review(s.call(page(s.case, 0) if moment == "page0" else None))


def test_other_event_bit_after_true_done_ack_cannot_close():
    s = Guard()
    s.offer_done()
    s.flags |= (1 << s.spec["bit"]) | (1 << 6)
    review(s.call(prev=("a",)))


@pytest.mark.parametrize("fault", ["garbage", "done_arrow"])
def test_final_actual_a_and_script2_do_not_hide_an_unknown_or_arrow_done_page(fault):
    s = Guard()
    s.offer_done()
    s.flags |= 1 << s.spec["bit"]
    rows = page(s.case, 3, fault == "done_arrow")
    if fault == "garbage":
        surf._put(rows, 1, 14, "UNEXPECTED TEXT!")
    review(s.call(rows, ("a",), script=2))
    assert s.c.final_ack is True and not s.c.closed_frames


@pytest.mark.parametrize("case", KEYS)
def test_already_set_own_event_is_not_a_completion_shortcut(case):
    s = Guard(case, flags=1 << BADGES[case][0])
    review(s.call(page(case, 0)))


@pytest.mark.parametrize("when", ["initial", "after_done"])
def test_native_script1_is_rejected_even_if_event_and_world_look_ready(when):
    s = Guard()
    if when == "after_done":
        s.offer_done()
        s.flags |= 1 << s.spec["bit"]
    review(s.call(None if when == "after_done" else page(s.case, 0), ("a",), script=1))


@pytest.mark.parametrize("field,value", [("kind", "route23_water"), ("map_id", 0), ("player_x", True),
                                          ("player_y", 1.0), ("case", "soul"), ("badge", "SOULBADGE"),
                                          ("bit", True), ("extra", 1)])
def test_only_exact_fixed_typed_intent_is_constructible(field, value):
    intent = deepcopy(pure.INTENTS["cascade"])
    intent[field] = value
    with pytest.raises(ValueError):
        pure.Route23LandGuardController(intent)


@pytest.mark.parametrize("fault", ["frame_bool", "frame_float", "location_float", "location_bool", "signal_frame",
                                   "grid_frame", "movement_frame", "battle_frame", "bad_profile", "bad_text_profile",
                                   "text_unaligned", "signal_mode_bool", "flag_bool", "script_bool", "wrong_map", "wrong_position"])
def test_typed_same_frame_source_grid_and_decoder_contract_fail_closed(fault):
    s = Guard()
    def mutate(st, args):
        if fault == "frame_bool": st["frame"] = True
        elif fault == "frame_float": st["frame"] = float(st["frame"])
        elif fault == "location_float": st["location"]["x"] = float(st["location"]["x"])
        elif fault == "location_bool": st["location"]["map_id"] = True
        elif fault == "signal_frame": args["signal"]["observation_frame"] -= 1
        elif fault == "grid_frame": args["grid"]["observation_frame"] -= 1
        elif fault == "movement_frame": args["movement"]["observation_frame"] -= 1
        elif fault == "battle_frame": st["battle_state"]["observation_frame"] -= 1
        elif fault == "bad_profile": args["signal"]["profile"] = "invented"
        elif fault == "bad_text_profile": st["text"]["profile"] = "invented"
        elif fault == "text_unaligned": st["text"]["alignment_verified"] = False
        elif fault == "signal_mode_bool": args["signal"]["mode"] = False
        elif fault == "flag_bool": args["signal"]["guard_flags"] = False
        elif fault == "script_bool": args["signal"]["route23_script"] = False
        elif fault == "wrong_map": st["location"]["map_id"] = 33
        else: st["location"]["y"] -= 1
    review(s.call(page(s.case, 0), mutate=mutate))


@pytest.mark.parametrize("fault", ["tile_bool", "tile_wrong", "not_visible", "duplicate_visible"])
def test_bad_closure_world_never_completes_and_exhausts_bounded_waits(fault):
    # The native textbox may obscure the grid during pages. The completion
    # evidence, after real final A and own event, must still be a true grid.
    s = Guard()
    s.offer_done()
    s.flags |= 1 << s.spec["bit"]
    def mutate(st, args):
        if fault == "tile_bool": args["grid"]["tiles"][s.loc["y"]][s.loc["x"]] = True
        elif fault == "tile_wrong": args["grid"]["tiles"][s.loc["y"]][s.loc["x"]] ^= 1
        elif fault == "not_visible":
            args["grid"]["visible_verified_cells"].remove([s.loc["x"], s.loc["y"]])
            args["grid"]["screen_cells_verified"] -= 1
        else: args["grid"]["visible_verified_cells"][-1] = args["grid"]["visible_verified_cells"][0][:]
    results = [s.call(prev=("a",) if i == 0 else ("wait",), mutate=mutate) for i in range(31)]
    assert all(r["available_actions"] == ["wait"] and not r["route23_land_guard_complete"] for r in results)
    reason = review(results[-1])
    assert review(s.call()) == reason


@pytest.mark.parametrize("fault", ["hp", "faint", "pp", "exp", "level", "max_hp", "status", "moves", "roster", "bag", "money"])
def test_dynamic_full_party_inventory_and_money_are_conserved_and_errors_stay_sticky(fault):
    s = Guard()
    s.call(page(s.case, 0))
    baseline = deepcopy(s.p)
    if fault == "hp": s.p["party"][0]["hp"] -= 1
    elif fault == "faint": s.p["party"][2]["hp"] = 0
    elif fault == "pp": s.p["party"][4]["pp"][0] -= 1
    elif fault == "exp": s.p["party"][1]["exp"] += 1
    elif fault == "level": s.p["party"][1]["level"] += 1
    elif fault == "max_hp": s.p["party"][0]["max_hp"] += 1
    elif fault == "status": s.p["party"][0]["status"] = 8
    elif fault == "moves": s.p["party"][2]["moves"][0] = 45
    elif fault == "roster": s.p["party"].reverse()
    elif fault == "bag": s.p["inventory"][0]["quantity"] -= 1
    else: s.p["money"] += 1
    reason = review(s.call(page(s.case, 0)))
    s.p = baseline
    assert review(s.call(page(s.case, 0))) == reason


@pytest.mark.parametrize("battle", [1, 2])
def test_wild_and_nonwild_battle_are_review_not_a_guard_handoff(battle):
    s = Guard()
    s.call(page(s.case, 0))
    review(s.call(page(s.case, 0), battle=battle))


@pytest.mark.parametrize("now", [True, -1, float("nan"), float("inf")])
def test_invalid_clock_cannot_start_or_recredit_a_transaction(now):
    s = Guard()
    review(s.call(page(s.case, 0), now=now))


def test_clock_reversal_elapsed_budget_and_error_do_not_reset_owner():
    for now in (0.0, 60.11):
        s = Guard()
        s.call(page(s.case, 0), now=.1)
        controller = s.c
        reason = review(s.call(page(s.case, 0), now=now))
        assert s.c is controller
        assert review(s.call(page(s.case, 0), now=.2)) == reason


def test_same_frame_identical_packet_never_resends_and_changed_previous_cannot_ack():
    s = Guard()
    assert_action(s.call(page(s.case, 0)), "a")
    assert_action(s.repeat(), "wait")
    review(s.call(page(s.case, 0), ("a",), same=True))


def test_same_frame_changed_party_or_native_event_is_a_conflict():
    for fault in ("party", "event"):
        s = Guard()
        s.call(page(s.case, 0))
        if fault == "party": s.p["party"][0]["hp"] -= 1
        else: s.flags |= 1
        review(s.call(page(s.case, 0), same=True))


def test_initial_partial_wait_budget_is_bounded_without_sending_a():
    s = Guard()
    results = [s.call(partial()) for _ in range(31)]
    assert all(r["available_actions"] == ["wait"] for r in results)
    review(results[-1])


def test_identical_frame_calls_still_consume_the_owner_call_budget():
    s = Guard()
    s.call(page(s.case, 0))
    result = None
    for _ in range(240):
        result = s.repeat()
    review(result)


def test_two_closure_frames_must_be_fresh_and_native_idle():
    s = Guard()
    s.offer_done()
    s.flags |= 1 << s.spec["bit"]
    assert not s.call(prev=("a",))["route23_land_guard_complete"]
    assert not s.repeat()["route23_land_guard_complete"]
    assert not s.call(movement_bytes={0xCFC5: 1})["route23_land_guard_complete"]
    assert not s.call()["route23_land_guard_complete"]
    assert s.call()["route23_land_guard_complete"]


def test_real_getter_rejects_wrong_badges_npc_and_untyped_raw_bytes_before_pure_uses_them():
    s = Guard()
    for address, bad in ((0xD356, 127), (0xC215, 255), (0xD7ED, True), (0xD667, True)):
        mem = Memory(s.loc, s.flags, 0)
        mem.values[address] = bad
        signal = surf.read_surf_observation(SimpleNamespace(frame_count=40, memory=mem), 40, SDK)
        if address == 0xD356:
            assert signal["read_valid"] and signal["badges_raw"] == 127
        else:
            assert not signal["read_valid"]


@pytest.fixture
def bridge_env(monkeypatch):
    # Registries and caller clock are test isolation; pure/getter/SDK remain real.
    for name, value in (("_CONTROLLERS", {}), ("_BINDINGS", {}), ("_COMPLETED", set()), ("_ERRORS", {})):
        monkeypatch.setattr(bridge, name, value)
    from laya_pokemon import route23_bridge as peer
    for name, value in (("_CONTROLLERS", {}), ("_BINDINGS", {}), ("_COMPLETED", set())):
        monkeypatch.setattr(peer, name, value)
    monkeypatch.setattr(bridge, "_PEERS", ("route23_bridge",))
    clock = {"now": 0.0}
    def install_clock():
        monkeypatch.setattr(bridge, "time", SimpleNamespace(monotonic=lambda: clock["now"]))
    install_clock()
    return SimpleNamespace(clock=clock, peer=peer, install_clock=install_clock)


class BridgeGuard(Guard):
    def __init__(self, env, case="cascade"):
        super().__init__(case)
        self.env = env
        self.step_id = "land-" + case
        self.step = dict(id=self.step_id, kind="interact", mechanic="route23_land_guard", map_id=34,
                         target=[self.spec["x"], self.spec["y"]], guard_case=case,
                         guard_intent=deepcopy(pure.INTENTS[case]))
        self.plan = dict(training_job="source-land-guard-contract-v1", steps=[self.step, dict(id="after-guard", kind="move")])
        self.next_id = None

    def dispatch(self, state, args, pb):
        self.env.clock["now"] = args["now"]
        before = deepcopy(self.plan)
        result = bridge.context(pb, state, self.plan, self.step_id, state["text"], args["grid"], args["previous"])
        assert self.plan == before
        if result is None:
            return None
        output, self.next_id = result
        self.c = bridge._CONTROLLERS.get(self.step_id, self.c)
        return output


def bridge_review(result):
    assert result["phase"] == "campaign_review"
    assert result["available_actions"] == ["wait"]
    assert result.get("field_move_complete") is not True
    return result["review_reason"]


@pytest.mark.parametrize("case", KEYS)
def test_real_bridge_getters_and_pure_five_case_closure_advance_exactly_one_step(bridge_env, case):
    s = BridgeGuard(bridge_env, case)
    baseline = deepcopy(s.p)
    s.offer_done()
    assert s.next_id == s.step_id
    result = s.close()
    assert result["route23_land_guard_complete"] and result["field_move_complete"]
    assert result["field_move_kind"] == "route23-land-guard"
    assert result["route23_land_guard_owner"] == s.step_id and s.next_id == "after-guard"
    assert bridge._COMPLETED == {s.step_id} and s.p == baseline
    assert bridge._CONTROLLERS[s.step_id] is s.c
    assert s.c.final_ack is True and s.c.pending is None and len(s.c.closed_frames) == 2
    assert s.c.script2_seen is False


def test_bridge_true_previous_pending_baseline_clock_and_registries_survive_reload(bridge_env):
    s = BridgeGuard(bridge_env)
    assert_action(s.call(page(s.case, 0)), "a")
    c, pending = s.c, s.c.pending
    fingerprint, started = deepcopy(c.fingerprint), c.started
    registries = (bridge._CONTROLLERS, bridge._BINDINGS, bridge._ERRORS, bridge._COMPLETED)
    importlib.reload(bridge)
    bridge_env.install_clock()
    assert all(a is b for a,b in zip(registries, (bridge._CONTROLLERS, bridge._BINDINGS, bridge._ERRORS, bridge._COMPLETED)))
    assert_action(s.call(page(s.case, 0), ("a",)), "wait")
    assert s.c is c and c.pending is pending and pending["executed"]
    assert c.fingerprint == fingerprint and c.started == started
    assert_action(s.call(page(s.case, 1)), "a")


@pytest.mark.parametrize("fault", ["job", "target", "removed_mechanic", "missing_step", "missing_controller", "missing_binding"])
def test_bridge_binding_edits_and_orphans_hold_truthy_sticky_owner_review(bridge_env, fault):
    s = BridgeGuard(bridge_env)
    s.call(page(s.case, 0))
    controller = s.c
    if fault == "job": s.plan["training_job"] = "changed"
    elif fault == "target": s.step["target"][0] += 1
    elif fault == "removed_mechanic": s.step.pop("mechanic")
    elif fault == "missing_step": s.plan["steps"] = [dict(id="different", kind="move")]
    elif fault == "missing_controller": bridge._CONTROLLERS.pop(s.step_id)
    else: bridge._BINDINGS.pop(s.step_id)
    assert bridge.applies("some-other-id", {"kind": "move"})
    result = s.call(page(s.case, 0))
    reason = bridge_review(result)
    assert bridge._ERRORS[s.step_id] == reason and s.next_id == s.step_id
    assert s.c is controller
    assert bridge_review(s.call(page(s.case, 0))) == reason


def test_bridge_error_without_controller_cannot_be_cleared_by_fixing_the_step(bridge_env):
    s = BridgeGuard(bridge_env)
    s.step["terminal"] = True
    reason = bridge_review(s.call(page(s.case, 0)))
    assert not bridge._CONTROLLERS and s.step_id in bridge._ERRORS
    errors = bridge._ERRORS
    importlib.reload(bridge)
    bridge_env.install_clock()
    assert bridge._ERRORS is errors and errors[s.step_id] == reason
    s.step.pop("terminal")
    assert bridge_review(s.call(page(s.case, 0))) == reason
    assert not bridge._CONTROLLERS


def test_bridge_real_pure_error_pending_and_budget_survive_reload_without_recredit(bridge_env):
    s = BridgeGuard(bridge_env)
    s.call(page(s.case, 0))
    baseline = deepcopy(s.p)
    s.p["party"][0]["pp"][0] -= 1
    reason = bridge_review(s.call(page(s.case, 0)))
    c, pending = s.c, s.c.pending
    fingerprint = deepcopy(c.fingerprint)
    counters = (c.started, c.last_now, c.calls, c.waits)
    importlib.reload(bridge)
    bridge_env.install_clock()
    s.p = baseline
    assert bridge_review(s.call(page(s.case, 0))) == reason
    assert s.c is c and c.pending is pending and c.fingerprint == fingerprint
    assert (c.started, c.last_now, c.calls, c.waits) == counters


def test_bridge_active_owner_blocks_unrelated_step_and_peer_registry_is_checked(bridge_env):
    s = BridgeGuard(bridge_env)
    s.call(page(s.case, 0))
    old_owner = s.step_id
    s.step_id = "unrelated"
    result = s.call(page(s.case, 0))
    bridge_review(result)
    assert result["route23_land_guard_owner"] == old_owner
    assert bridge._CONTROLLERS[old_owner] is s.c and "unrelated" not in bridge._CONTROLLERS


def test_bridge_loaded_real_peer_binding_blocks_new_transaction(bridge_env):
    s = BridgeGuard(bridge_env)
    bridge_env.peer._BINDINGS["water-owner"] = ("real-registry-contract",)
    bridge_review(s.call(page(s.case, 0)))
    assert not bridge._CONTROLLERS and not bridge._BINDINGS


def test_bridge_far_start_declines_without_binding_or_error_but_active_far_owner_reviews(bridge_env):
    s = BridgeGuard(bridge_env)
    s.loc["x"] += 1
    assert s.call(page(s.case, 0)) is None
    assert not bridge._CONTROLLERS and not bridge._BINDINGS and not bridge._ERRORS
    s.loc["x"] -= 1
    s.call(page(s.case, 0))
    s.loc["x"] += 1
    bridge_review(s.call(page(s.case, 0)))
    assert s.step_id in bridge._ERRORS and s.step_id not in bridge._COMPLETED


def test_bridge_completion_independently_rejects_corrupted_true_controller_ack_receipt(bridge_env):
    s = BridgeGuard(bridge_env)
    s.offer_done()
    s.flags |= 1 << s.spec["bit"]
    assert not s.call(prev=("a",))["route23_land_guard_complete"]
    s.c.final_ack_frame = True
    bridge_review(s.call())
    assert s.step_id not in bridge._COMPLETED and s.step_id in bridge._ERRORS


def test_bridge_completed_owner_reentry_is_sticky_review_and_never_credits_again(bridge_env):
    s = BridgeGuard(bridge_env)
    s.offer_done()
    assert s.close()["field_move_complete"]
    bridge_review(s.call())
    assert bridge._COMPLETED == {s.step_id}


def test_bridge_actual_a_is_required_and_native_source_frame_is_not_fabricated(bridge_env):
    s = BridgeGuard(bridge_env)
    s.call(page(s.case, 0))
    pending = s.c.pending
    bridge_review(s.call(page(s.case, 1), ("wait",)))
    assert s.c.pending is pending and pending["executed"] is False
    assert s.step_id in bridge._ERRORS and s.step_id not in bridge._COMPLETED
