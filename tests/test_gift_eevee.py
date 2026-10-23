"""正常伊布禮物控制器的合成觀測測試；不啟動遊戲、模型或網路。"""
from copy import deepcopy

import pytest

from laya_pokemon.gift_eevee import (
    EeveeGiftController, GIFT_REMOVED_FLAG_ADDRESS, GIFT_REMOVED_FLAG_BIT,
    GIFT_REMOVED_FLAG_MASK, GIFT_TOGGLE_INDEX, gift_removed_flag,
)
from tests.test_battle import text_at


LOCATION = {"map_id": 132, "x": 5, "y": 3, "facing": "left"}


def progress():
    return {"party_read_valid": True, "party_count": 3, "player_name_raw": "Kevin",
            "party": [
                {"species": 9, "level": 28, "hp": 79, "max_hp": 79,
                 "moves": [77, 15, 73, 22], "pp": [35, 30, 10, 10], "status": 0, "exp": 19000},
                {"species": 167, "level": 25, "hp": 68, "max_hp": 68,
                 "moves": [43, 33, 30, 40], "pp": [30, 35, 25, 35], "status": 0, "exp": 12000},
                {"species": 35, "level": 22, "hp": 60, "max_hp": 60,
                 "moves": [64, 45, 31, 43], "pp": [35, 40, 20, 30], "status": 0, "exp": 9000},
            ]}


def gifted(state=None):
    result = deepcopy(state or progress())
    result["party"].append({"species": 102, "level": 25, "hp": 67, "max_hp": 67,
                            "moves": [33, 28, 0, 0], "pp": [35, 15, 0, 0],
                            "status": 0, "exp": 15625})
    result["party_count"] = len(result["party"])
    return result


def receipt():
    return text_at((1, 14, "Kevin got"), (1, 16, "EEVEE!"))


def intro(marker="▼"):
    cells = [(1, 14, "Do you want to"), (1, 16, "give a nickname")]
    if marker:
        cells.append((18, 16, marker))
    return text_at(*cells)


def question(cursor="▶", *, selected="YES", full=False):
    cells = [(1, 14, "give a nickname"), (1, 16, "to EEVEE?"),
             (16, 8, "YES"), (16, 10, "NO")]
    if full:
        cells.append((1, 13, "Do you want to"))
    if cursor:
        cells.append((15, 8 if selected == "YES" else 10, cursor))
    return text_at(*cells)


def call(controller, text=None, state=None, *, ready=False, hidden=False, **extra):
    return controller.context(text if text is not None else text_at(),
                              state if state is not None else progress(),
                              location=deepcopy(LOCATION), overworld_ready=ready,
                              gift_object_hidden=hidden, **extra)


def start(controller, state=None):
    result = call(controller, state=state, ready=True)
    assert result["available_actions"] == ["a", "wait"]
    return result


def decline(controller, state=None):
    start(controller, state)
    assert call(controller, receipt(), state)["available_actions"] == ["wait"]
    assert call(controller, intro(), state)["available_actions"] == ["a", "wait"]
    assert call(controller, question(), state)["available_actions"] == ["down", "wait"]
    assert call(controller, question(selected="NO"), state)["available_actions"] == ["a", "wait"]


def test_complete_requires_own_baseline_nickname_closed_new_member_and_removed_ball():
    controller, original = EeveeGiftController(), progress()
    snapshot = deepcopy(original)
    decline(controller, original)
    new = gifted(original)
    assert call(controller, question(selected="NO"), new, hidden=True)["available_actions"] == ["wait"]
    waiting = call(controller, state=new, ready=True, hidden=False)
    assert waiting["gift_tactic"] == "wait_gift_ball_removed_evidence"
    complete = call(controller, state=new, ready=True, hidden=True)
    assert complete["gift_eevee_complete"] and complete["nickname_declined"]
    assert complete["gift_moves"] == [33, 28, 0, 0]
    assert complete["gift_pp"] == [35, 15, 0, 0]
    assert complete["existing_members_unchanged"]
    assert original == snapshot  # 純控制器不可改呼叫端的唯讀資料。
    assert call(controller, state=new, ready=True, hidden=True)["gift_eevee_complete"]


def test_automatic_receipt_waits_and_validates_partial_and_transient_party():
    controller = EeveeGiftController()
    start(controller)
    transient = progress()
    transient.update(party_read_valid=False, party_count=4)
    assert call(controller, text_at((1, 14, "Kevin go")), transient)["available_actions"] == ["wait"]
    assert call(controller, receipt(), transient)["gift_tactic"] == "wait_automatic_gift_receipt"
    assert call(controller, intro(), transient)["available_actions"] == ["a", "wait"]
    assert call(controller, question(selected="NO"), transient)["available_actions"] == ["a", "wait"]
    assert call(controller, state=transient, ready=True, hidden=True)["available_actions"] == ["wait"]
    assert call(controller, state=gifted(), ready=True, hidden=True)["gift_eevee_complete"]


def test_full_question_observed_in_one_screen_can_safely_decline_without_receipt_sampling():
    controller = EeveeGiftController()
    start(controller)
    assert call(controller, question(selected="NO", full=True))["gift_tactic"] == "confirm_no_nickname"
    assert call(controller, state=gifted(), ready=True, hidden=True)["gift_eevee_complete"]


def test_inactive_cursors_and_stale_frames_never_issue_extra_confirmation_or_down():
    controller = EeveeGiftController()
    start(controller)
    assert call(controller, intro("▷"))["available_actions"] == ["wait"]
    assert call(controller, intro("▶"))["available_actions"] == ["a", "wait"]
    assert call(controller, intro("▶"))["available_actions"] == ["wait"]
    assert call(controller, question("▷"))["available_actions"] == ["wait"]
    assert call(controller, question())["available_actions"] == ["down", "wait"]
    assert call(controller, question())["available_actions"] == ["wait"]
    assert call(controller, question("▷", selected="NO"))["available_actions"] == ["wait"]
    assert call(controller, question(selected="NO"))["available_actions"] == ["a", "wait"]
    assert call(controller, question(selected="NO"))["available_actions"] == ["wait"]


@pytest.mark.parametrize("mutation,reason", [
    (lambda p: p.update(party_read_valid=False), "eevee_gift_initial_party_unverified"),
    (lambda p: p.update(party_count=4), "eevee_gift_initial_party_unverified"),
    (lambda p: p.update(player_name_raw="Blue"), "eevee_gift_player_name_not_kevin"),
    (lambda p: p.update(party=gifted()["party"], party_count=4), "eevee_already_present_without_baseline"),
    (lambda p: p.update(party=p["party"] * 2, party_count=6), "eevee_gift_requires_party_space"),
])
def test_initial_context_requires_verified_baseline_and_space(mutation, reason):
    state = progress()
    mutation(state)
    result = call(EeveeGiftController(), state=state, ready=True)
    assert result["phase"] == "campaign_review" and result["review_reason"] == reason
    assert result["available_actions"] == ["wait"]


@pytest.mark.parametrize("hidden", [None, True, 1, "False"])
def test_initial_ball_must_be_explicitly_visible_not_truthy_coercion(hidden):
    assert call(EeveeGiftController(), ready=True, hidden=hidden)["phase"] == "campaign_review"


@pytest.mark.parametrize("location", [
    {"map_id": 131, "x": 5, "y": 3, "facing": "left"},
    {"map_id": 132, "x": 4, "y": 4, "facing": "up"},
    {"map_id": 132, "x": 5, "y": 3, "facing": "right"},
])
def test_scope_is_exact_source_stance_not_general_menu_handler(location):
    result = EeveeGiftController().context(text_at(), progress(), location=location,
                                          overworld_ready=True, gift_object_hidden=False)
    assert result["review_reason"] == "eevee_gift_stance_unverified"


def test_complete_menu_labels_cannot_confirm_unknown_or_unseen_question():
    controller = EeveeGiftController()
    start(controller)
    unknown = text_at((1, 14, "Delete this name?"), (16, 8, "YES"),
                      (16, 10, "NO"), (15, 10, "▶"))
    result = call(controller, unknown)
    assert result["review_reason"] == "eevee_gift_nickname_question_unverified"
    assert call(controller, question(full=True))["available_actions"] == ["wait"]
    unstarted = call(EeveeGiftController(), question(full=True), ready=True)
    assert unstarted["phase"] == "campaign_review"


def test_partial_text_or_menu_waits_without_confirming_and_has_finite_budget():
    controller = EeveeGiftController(max_waits=2)
    start(controller)
    partial = text_at((1, 14, "Do you want"), (18, 16, "▶"))
    assert call(controller, partial)["available_actions"] == ["wait"]
    assert call(controller, partial)["available_actions"] == ["wait"]
    assert call(controller, partial)["review_reason"] == "eevee_gift_wait_budget_exhausted"
    controller = EeveeGiftController()
    start(controller)
    call(controller, intro())
    partial_menu = question()
    partial_menu["cells"][10][16:18] = [" ", " "]
    assert call(controller, partial_menu)["gift_tactic"] == "wait_complete_yes_no_labels"


def test_missing_final_question_mark_is_not_complete_nickname_question():
    controller = EeveeGiftController()
    start(controller)
    call(controller, intro())
    partial = question(selected="NO")
    partial["cells"][16][9] = " "
    result = call(controller, partial)
    assert result["available_actions"] == ["wait"]
    assert result["gift_tactic"] == "wait_complete_nickname_question_mark"


@pytest.mark.parametrize("edit", [
    lambda t: t["cells"][10].__setitem__(15, "▶"),  # 雙active cursor。
    lambda t: t["cells"][10].__setitem__(15, "▷"),  # active與inactive混用。
    lambda t: (t["cells"][8].__setitem__(15, " "), t["cells"][8].__setitem__(14, "▶")),
])
def test_ambiguous_or_wrong_position_cursor_stops(edit):
    controller = EeveeGiftController()
    start(controller)
    call(controller, intro())
    bad = question()
    edit(bad)
    assert call(controller, bad)["review_reason"] == "eevee_gift_nickname_cursor_unverified"


@pytest.mark.parametrize("mutation", [
    lambda p: p["party"][0].update(hp=78),
    lambda p: p["party"].reverse(),
    lambda p: p["party"][1]["moves"].__setitem__(1, 91),
])
def test_other_party_member_any_change_invalidates_gift_claim(mutation):
    controller = EeveeGiftController()
    decline(controller)
    new = gifted()
    mutation(new)
    assert call(controller, state=new, ready=True, hidden=True)["review_reason"] == "eevee_existing_members_changed"


@pytest.mark.parametrize("mutation", [
    lambda m: m.update(level=24),
    lambda m: m.update(moves=[33, 28, 98, 0]),
    lambda m: m.update(pp=[34, 15, 0, 0]),
    lambda m: m.update(hp=66),
    lambda m: m.update(status=8),
    lambda m: m.update(exp=10000),
])
def test_new_member_must_match_source_level_initial_moves_pp_and_health(mutation):
    controller = EeveeGiftController()
    decline(controller)
    new = gifted()
    mutation(new["party"][-1])
    assert call(controller, state=new, ready=True, hidden=True)["review_reason"] == "eevee_gift_new_member_source_mismatch"


def test_no_completion_before_nickname_finished_even_with_party_and_toggle():
    controller = EeveeGiftController()
    start(controller)
    result = call(controller, state=gifted(), ready=True, hidden=True)
    assert result["available_actions"] == ["wait"] and not result.get("gift_eevee_complete")
    assert call(EeveeGiftController(), state=gifted(), ready=True, hidden=True)["review_reason"] == "eevee_already_present_without_baseline"


def test_never_enters_letter_naming_or_overwrites_kevin_and_checks_name_unchanged():
    controller = EeveeGiftController()
    start(controller)
    naming = text_at((1, 1, "YOUR NAME?"))
    assert call(controller, naming)["review_reason"] == "eevee_gift_unexpected_naming_screen"
    controller = EeveeGiftController()
    start(controller)
    altered = progress()
    altered["player_name_raw"] = "KEVIN"
    assert call(controller, receipt(), altered)["review_reason"] == "eevee_gift_player_name_changed"


def test_full_cells_battle_and_operation_time_limits_fail_closed(monkeypatch):
    assert call(EeveeGiftController(), {"cells": []}, ready=True)["review_reason"] == "eevee_gift_full_cells_required"
    assert call(EeveeGiftController(), ready=True, battle_active=True)["review_reason"] == "eevee_gift_requires_verified_nonbattle"
    controller = EeveeGiftController(max_calls=1)
    start(controller)
    assert call(controller)["review_reason"] == "eevee_gift_budget_exhausted"
    clock = iter([100.0, 160.1])
    monkeypatch.setattr("laya_pokemon.gift_eevee.time.monotonic", lambda: next(clock))
    timed = EeveeGiftController()
    start(timed)
    assert call(timed)["review_reason"] == "eevee_gift_budget_exhausted"


def test_flag_contract_is_removed_bit_not_toggle_on_off_value():
    assert (GIFT_TOGGLE_INDEX, GIFT_REMOVED_FLAG_ADDRESS,
            GIFT_REMOVED_FLAG_BIT, GIFT_REMOVED_FLAG_MASK) == (69, 0xD5AE, 5, 0x20)
    assert gift_removed_flag(0x20) is True
    assert gift_removed_flag(0xDF) is False
    assert gift_removed_flag(0x11) is False and gift_removed_flag(0x15) is False
    for invalid in (True, None, -1, 256, "32"):
        with pytest.raises(ValueError):
            gift_removed_flag(invalid)


@pytest.mark.parametrize("limits", [
    {"max_calls": 0}, {"max_waits": 0}, {"max_seconds": 0},
    {"max_seconds": float("nan")}, {"max_seconds": True},
])
def test_invalid_limits_are_rejected(limits):
    with pytest.raises(ValueError):
        EeveeGiftController(**limits)


@pytest.mark.parametrize("edit", [
    lambda t: t["cells"][10].__setitem__(18, "T"),  # NOT不能被NO切片冒充。
    lambda t: t["cells"][10].__setitem__(18, "1"),
    lambda t: t["cells"][10].__setitem__(18, "!"),
    lambda t: t["cells"][8].__setitem__(19, "S"),  # YESS也不是YES。
    lambda t: t["cells"][8].__setitem__(19, "!"),
    lambda t: t["cells"][0].__setitem__(slice(0, 2), list("NO")),
    lambda t: t["cells"][1].__setitem__(slice(0, 3), list("YES")),
    lambda t: (t["cells"][10].__setitem__(slice(16, 18), [" ", " "]),
               t["cells"][10].__setitem__(slice(1, 3), list("NO"))),
    lambda t: (t["cells"][8].__setitem__(slice(16, 19), [" ", " ", " "]),
               t["cells"][7].__setitem__(slice(16, 19), list("YES"))),
])
def test_nickname_labels_must_be_complete_unique_and_at_source_coordinates(edit):
    controller = EeveeGiftController()
    start(controller)
    call(controller, intro())
    bad = question(selected="NO")
    edit(bad)
    original = deepcopy(bad)
    result = call(controller, bad)
    assert result["review_reason"] == "eevee_gift_nickname_labels_unverified"
    assert result["phase"] == "campaign_review" and result["available_actions"] == ["wait"]
    assert not controller.decline_issued and bad == original
    # 矛盾已鎖定後，即使再給正確NO也不能自動解除。
    assert call(controller, question(selected="NO")) == result


@pytest.mark.parametrize("marker,x,y", [("▶", 0, 0), ("▷", 0, 0), ("▼", 18, 16),
                                      ("▶", 15, 8), ("▷", 15, 10)])
def test_initial_overworld_claim_cannot_override_any_visible_menu_marker(marker, x, y):
    controller = EeveeGiftController()
    page = text_at((x, y, marker))
    result = call(controller, page, ready=True)
    assert result["review_reason"] == "eevee_gift_initial_menu_marker_unverified"
    assert result["phase"] == "campaign_review" and result["available_actions"] == ["wait"]
    assert controller.baseline is None and not controller.decline_issued


@pytest.mark.parametrize("label", ["ITEM", "POKéMON", "POKéDEX", "CANCEL", "USE", "TOSS", "EXIT"])
def test_initial_known_menu_label_is_rejected_even_without_a_cursor(label):
    controller = EeveeGiftController()
    result = call(controller, text_at((1, 2, label)), ready=True)
    assert result["review_reason"] == "eevee_gift_initial_menu_marker_unverified"
    assert result["available_actions"] == ["wait"]
    assert controller.baseline is None and not controller.decline_issued


@pytest.mark.parametrize("yes,no", [("Y", ""), ("YE", "N"), ("YES", "N"), ("YES", "")])
def test_known_partial_labels_only_wait_and_never_confirm_no(yes, no):
    controller = EeveeGiftController()
    start(controller)
    call(controller, intro())
    page = question(selected="NO")
    page["cells"][8][16:19] = list(yes.ljust(3))
    page["cells"][10][16:19] = list(no.ljust(3))
    result = call(controller, page)
    assert result["available_actions"] == ["wait"] and not controller.decline_issued
    assert result["gift_tactic"] == "wait_complete_yes_no_labels"
    # 完整來源標籤真正到齊後才允許NO確認，仍需後續成員／球消失驗證。
    result = call(controller, question(selected="NO"))
    assert result["gift_tactic"] == "confirm_no_nickname" and not result.get("gift_eevee_complete")


def test_full_source_nickname_menu_still_declines_without_renaming_kevin_or_existing_party():
    controller, state = EeveeGiftController(), progress()
    original = deepcopy(state)
    start(controller, state)
    result = call(controller, question(selected="NO", full=True), state)
    assert result["available_actions"] == ["a", "wait"] and result["menu_label"] == "NO"
    assert controller.decline_issued and state == original
    assert call(controller, state=gifted(state), ready=True, hidden=True)["gift_eevee_complete"]
