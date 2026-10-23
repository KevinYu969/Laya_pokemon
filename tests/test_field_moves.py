"""以合成可見文字校對 HM 狀態鎖；不啟動遊戲、模型或網路。"""
from copy import deepcopy

import pytest

from laya_pokemon.field_moves import (CutController, MAX_SAFE_TEXT_WAITS,
                                    MAX_BAG_DOWN_REQUESTS, MAX_BAG_STAGNANT_REQUESTS)
from tests.test_battle import text_at


def progress(*, cut=False):
    return {"party_read_valid": True, "badges_raw": 3,
            "inventory": [{"item": 196, "quantity": 1}],
            "party": [{"species": 9, "moves": [77, 15 if cut else 45, 73, 22]},
                      {"species": 167, "moves": [43, 33, 30, 40]},
                      {"species": 5, "moves": [64, 45, 43, 31]}]}


START = text_at((13, 2, "POKéDEX"), (13, 4, "POKéMON"), (12, 6, "▶ITEM"))
BAG = text_at((1, 2, "POTION"), (0, 4, "▶HM01"), (1, 6, "CANCEL"))
ITEM_MENU = text_at((13, 10, "▶USE"), (14, 12, "TOSS"), (14, 14, "CANCEL"))
PARTY_TEACH = text_at((3, 0, "IVYSAUR"), (0, 1, "▶"), (12, 1, "ABLE"),
                      (3, 2, "NIDORINO"), (12, 3, "NOT ABLE"),
                      (3, 4, "SPEAROW"), (12, 5, "NOT ABLE"),
                      (1, 14, "Use TM on which"), (1, 16, "POKéMON?"))
TEACH_QUESTION = text_at((1, 14, "Teach CUT to a"), (1, 16, "POKéMON?"),
                         (15, 8, "▶YES"), (16, 10, "NO"))
DELETE_QUESTION = text_at((1, 13, "Delete an older"), (1, 14, "move to make room"),
                          (1, 16, "for CUT?"), (15, 8, "▶YES"), (16, 10, "NO"))
FORGET = text_at((1, 14, "Which move should"), (1, 16, "be forgotten?"),
                  (6, 8, "POISONPOWDER"), (5, 8, "▶"), (6, 9, "GROWL"),
                  (6, 10, "LEECH SEED"), (6, 11, "VINE WHIP"))


def teacher():
    return CutController({"kind": "teach_cut", "species": 9, "replace_move": 45})


def to_learning(controller, state):
    for text, kwargs in [
        (text_at(), {"overworld_ready": True}), (START, {}), (BAG, {}), (ITEM_MENU, {}),
        (text_at((1, 14, "Booted up an HM!")), {}),
        (text_at((1, 14, "It contained CUT!")), {}), (TEACH_QUESTION, {}), (PARTY_TEACH, {}),
        (text_at((1, 14, "IVYSAUR is"), (1, 16, "trying to learn")), {}),
        (text_at((1, 14, "CUT!"), (18, 16, "▼")), {}),
        (text_at((1, 14, "But, IVYSAUR"), (1, 16, "can't learn more")), {}),
    ]:
        result = controller.context(text, state, **kwargs)
        assert result["phase"] != "campaign_review", result


def test_intent_only_allows_source_checked_learner_and_replace_growl():
    with pytest.raises(ValueError):
        CutController({"kind": "teach_cut", "species": 167, "replace_move": 45})
    with pytest.raises(ValueError):
        CutController({"kind": "teach_cut", "species": 9, "replace_move": 22})


def test_hm_teaching_full_visible_sequence_replaces_only_growl_and_checks_party():
    controller, state = teacher(), progress()
    to_learning(controller, state)
    result = controller.context(DELETE_QUESTION, state)
    assert result["menu_label"] == "YES" and result["controller_menu_verified"]
    assert controller.context(FORGET, state)["objective"] == "Move DOWN."
    chosen = deepcopy(FORGET)
    chosen["cells"][8][5] = " "
    chosen["cells"][9][5] = "▶"
    result = controller.context(chosen, state)
    assert result["available_actions"] == ["a", "wait"] and result["forgotten_move"] == 45
    assert controller.context(text_at((1, 14, "1, 2 and... Poof!")), state)["available_actions"] == ["a", "wait"]
    assert controller.context(text_at((1, 14, "IVYSAUR forgot"), (1, 16, "GROWL!")), state)["field_move_tactic"] == "advance_verified_growl_forget"
    assert controller.context(text_at((0,3,'▷'),(1,14,'And...')),state)['field_move_tactic']=='advance_verified_cut_learning_and'
    state["party"][0]["moves"][1] = 15
    assert controller.context(text_at((1, 14, "IVYSAUR learned"), (1, 16, "CUT!")), state)["controller_menu_verified"]
    assert controller.context(BAG, state)["available_actions"] == ["b", "wait"]
    result = controller.context(text_at(), state, overworld_ready=True)
    assert result["field_move_complete"] and result["moves_verified"] == [77, 15, 73, 22]
    assert result["protected_move"] == 22


def test_wrapped_delete_question_lock_survives_page_without_delete_text():
    controller, state = teacher(), progress()
    to_learning(controller, state)
    assert controller.context(text_at((1, 14, "Delete an older"), (1, 16, "move to make room"), (18, 17, "▼")), state)["available_actions"] == ["a", "wait"]
    result = controller.context(text_at((1, 14, "for CUT?"), (15, 8, "▶YES"), (16, 10, "NO")), state)
    assert result["menu_label"] == "YES" and result["field_move_tactic"] == "accept_replace_growl"


def test_wait_does_not_break_hm_or_forget_menu_state():
    controller, state = teacher(), progress()
    controller.context(text_at(), state, overworld_ready=True)
    controller.context(START, state)
    first = controller.context(BAG, state)
    assert controller.context(BAG, state)["objective"] == first["objective"]
    controller, state = teacher(), progress()
    to_learning(controller, state)
    controller.context(DELETE_QUESTION, state)
    chosen = deepcopy(FORGET)
    chosen["cells"][8][5] = " "
    chosen["cells"][9][5] = "▶"
    assert controller.context(chosen, state)["objective"] == "Confirm the current selection."
    assert controller.context(chosen, state)["objective"] == "Confirm the current selection."


def test_item_submenu_takes_precedence_over_visible_hm_bag_background():
    controller, state = teacher(), progress()
    controller.context(text_at(), state, overworld_ready=True)
    controller.context(START, state)
    controller.context(BAG, state)
    result = controller.context(text_at((1, 4, "HM01"), (13, 10, "▶USE"),
                                        (14, 12, "TOSS"), (14, 14, "CANCEL")), state)
    assert result["menu_label"] == "USE" and result["available_actions"] == ["a", "wait"]


@pytest.mark.parametrize("mutation,reason", [
    (lambda p: p.update(inventory=[]), "cut_hm01_not_verified_in_inventory"),
    (lambda p: p["party"][0].update(moves=[77, 0, 73, 22]), "cut_requires_growl_and_protected_vine_whip"),
    (lambda p: p["party"][0].update(moves=[77, 45, 73, 0]), "cut_requires_growl_and_protected_vine_whip"),
    (lambda p: p.update(party_read_valid=False), "cut_target_party_not_verified"),
])
def test_teaching_requires_explicit_verified_resources(mutation, reason):
    state = progress()
    mutation(state)
    assert teacher().context(text_at(), state, overworld_ready=True)["review_reason"] == reason


def test_unknown_question_latches_review_and_never_confirms_it():
    controller, state = teacher(), progress()
    controller.context(text_at(), state, overworld_ready=True)
    result = controller.context(TEACH_QUESTION, state)
    assert result["phase"] == "campaign_review" and result["available_actions"] == ["wait"]
    assert controller.context(START, state) == result


def test_learner_not_able_is_not_selected():
    controller, state = teacher(), progress()
    for text, kwargs in [(text_at(), {"overworld_ready": True}), (START, {}), (BAG, {}),
                         (text_at((1, 14, "Booted up an HM!")), {}), (TEACH_QUESTION, {})]:
        controller.context(text, state, **kwargs)
    bad = deepcopy(PARTY_TEACH)
    bad["cells"][1][12:] = list("NOT ABLE")
    assert controller.context(bad, state)["review_reason"] == "cut_learner_able_label_not_verified"


def test_forget_requires_all_four_source_ordered_visible_moves_and_unique_cursor():
    controller, state = teacher(), progress()
    to_learning(controller, state)
    controller.context(DELETE_QUESTION, state)
    wrong = deepcopy(FORGET)
    wrong["cells"][9][6:] = list("TACKLE        ")
    result = controller.context(wrong, state)
    assert result["phase"] == "campaign_review" and result["available_actions"] == ["wait"]


def test_unexpected_actual_move_change_stops_even_if_new_cut_is_present():
    controller, state = teacher(), progress()
    to_learning(controller, state)
    state["party"][0]["moves"] = [77, 45, 73, 15]
    result = controller.context(text_at((1, 14, "IVYSAUR learned"), (1, 16, "CUT!")), state)
    assert result["review_reason"] == "cut_unexpected_move_replacement"


def field():
    return CutController({"kind": "use_cut", "species": 9, "map_id": 5, "tree_x": 15, "tree_y": 18})


def world(*, removed=False):
    tiles, walkable = [[0x2C]*20 for _ in range(20)], [[1]*20 for _ in range(20)]
    if not removed:
        tiles[18][15], walkable[18][15] = 0x3D, 0
    return {"tileset_id": 0, "screen_cells_verified": 90, "tiles": tiles, "walkable": walkable}


LOCATION = {"map_id": 5, "x": 15, "y": 17, "facing": "down"}
FIELD_PARTY = text_at((3, 0, "IVYSAUR"), (0, 1, "▶"), (3, 2, "NIDORINO"), (3, 4, "SPEAROW"))
CUT_MENU = text_at((12, 8, "▶CUT"), (13, 10, "STATS"), (13, 12, "SWITCH"), (13, 14, "CANCEL"))


def to_field_selection(controller, state):
    assert controller.context(text_at(), state, location=LOCATION, grid=world(), overworld_ready=True)["available_actions"] == ["start", "wait"]
    assert controller.context(START, state)["menu_label"] == "POKÉMON"
    assert controller.context(FIELD_PARTY, state)["party_target_index"] == 0
    assert controller.context(CUT_MENU, state)["menu_label"] == "CUT"


def test_cut_uses_normal_party_menu_and_verifies_exact_tree_change():
    controller, state = field(), progress(cut=True)
    to_field_selection(controller, state)
    # Laya 可以選 wait；不可因已發出確認目標就假定選單完成。
    assert controller.context(CUT_MENU, state)["menu_label"] == "CUT"
    result = controller.context(text_at((1, 14, "IVYSAUR hacked"), (1, 16, "away with CUT!")), state)
    assert result["field_move_tactic"] == "advance_verified_cut_field_message"
    assert controller.context(text_at(), state)["available_actions"] == ["wait"]
    result = controller.context(text_at(), state, location=LOCATION, grid=world(removed=True), overworld_ready=True)
    assert result["tree_removal_verified"] and result["before_tile"] == 0x3D and result["after_tile"] == 0x2C


def test_celadon_gym_cut_requires_its_exact_tileset_tree_and_floor():
    controller=CutController({'kind':'use_cut','species':9,'map_id':134,'tree_x':5,'tree_y':7,'tileset_id':7})
    state=progress(cut=True);location={'map_id':134,'x':5,'y':8,'facing':'up'}
    grid={'tileset_id':7,'screen_cells_verified':90,'tiles':[[0x2B]*10 for _ in range(12)],'walkable':[[1]*10 for _ in range(12)]}
    grid['tiles'][7][5]=0x50;grid['walkable'][7][5]=0
    assert controller.context(text_at(),state,location=location,grid=grid,overworld_ready=True)['available_actions']==['start','wait']
    controller.context(START,state);controller.context(FIELD_PARTY,state);controller.context(CUT_MENU,state)
    controller.context(text_at((1,14,'IVYSAUR hacked'),(1,16,'away with CUT!')),state)
    grid['tiles'][7][5]=0x2B;grid['walkable'][7][5]=1
    result=controller.context(text_at(),state,location=location,grid=grid,overworld_ready=True)
    assert result['field_move_complete'] and (result['before_tile'],result['after_tile'])==(0x50,0x2B)
    other=CutController({'kind':'use_cut','species':9,'map_id':134,'tree_x':5,'tree_y':7})
    assert other.context(text_at(),state,location=location,grid=grid,overworld_ready=True)['phase']=='campaign_review'
    with pytest.raises(ValueError):CutController({'kind':'use_cut','species':9,'map_id':92,'tree_x':5,'tree_y':7,'tileset_id':7})


@pytest.mark.parametrize("changes,reason", [
    ({"badges_raw": 1}, "cut_cascade_badge_not_verified"),
    ({"party_read_valid": False}, "cut_target_party_not_verified"),
])
def test_field_prerequisites_are_readonly_verified(changes, reason):
    state = progress(cut=True)
    state.update(changes)
    assert field().context(text_at(), state, location=LOCATION, grid=world(), overworld_ready=True)["review_reason"] == reason


def test_cut_rejects_unknown_facing_and_unverified_tree_grid():
    assert field().context(text_at(), progress(cut=True), location={**LOCATION, "facing": "up"}, grid=world(), overworld_ready=True)["review_reason"] == "cut_player_not_adjacent_and_facing_tree"
    bad = world()
    bad["screen_cells_verified"] = 0
    assert field().context(text_at(), progress(cut=True), location=LOCATION, grid=bad, overworld_ready=True)["review_reason"] == "cut_tree_not_verified_in_overworld"


def test_text_only_success_and_other_walkable_tile_are_not_enough():
    controller, state = field(), progress(cut=True)
    to_field_selection(controller, state)
    controller.context(text_at((1, 14, "IVYSAUR hacked"), (1, 16, "away with CUT!")), state)
    bad = world(removed=True)
    bad["tiles"][18][15] = 0x52
    assert controller.context(text_at(), state, location=LOCATION, grid=bad, overworld_ready=True)["review_reason"] == "cut_tree_removal_not_verified"


def test_cut_tree_change_without_normal_visible_use_is_not_accepted():
    controller, state = field(), progress(cut=True)
    to_field_selection(controller, state)
    result = controller.context(text_at(), state, location=LOCATION, grid=world(removed=True), overworld_ready=True)
    assert result["phase"] == "campaign_review" and not result.get("field_move_complete")


def test_cut_failure_keeps_tree_evidence_and_pauses():
    controller, state = field(), progress(cut=True)
    to_field_selection(controller, state)
    result = controller.context(text_at((1, 14, "There isn't"), (1, 16, "anything to CUT!")), state)
    assert result["review_reason"] == "cut_field_use_rejected"


def to_hm_selected(controller, state):
    controller.context(text_at(), state, overworld_ready=True)
    controller.context(START, state)
    controller.context(BAG, state)


@pytest.mark.parametrize("partial,full", [
    ("Booted", "Booted up an HM!"), ("It contained", "It contained CUT!"),
    ("It contained C", "It contained CUT!"), ("Booted up an HM", "Booted up an HM!"),
    ("It contained CUT", "It contained CUT!"),
])
def test_hm_printing_prefix_waits_without_a_until_complete(partial, full):
    controller, state = teacher(), progress()
    to_hm_selected(controller, state)
    result = controller.context(text_at((1, 14, partial)), state)
    assert result["available_actions"] == ["wait"] and result["safe_wait_limit"] == MAX_SAFE_TEXT_WAITS
    result = controller.context(text_at((1, 14, full)), state)
    assert result["available_actions"] == ["a", "wait"]


def test_real_delete_partial_waits_then_selects_verified_yes_no():
    controller, state = teacher(), progress()
    to_learning(controller, state)
    for phrase in ["Delete", "Delete an", "Delete an older", "move to make room", "for CUT?"]:
        result = controller.context(text_at((1, 14, phrase)), state)
        assert result["available_actions"] == ["wait"], result
    result = controller.context(text_at((1, 14, "for CUT?"), (15, 8, "▶YES"), (16, 10, "NO")), state)
    assert result["menu_label"] == "YES" and result["available_actions"] == ["a", "wait"]


def test_teach_partial_keeps_question_lock_until_choices_arrive():
    controller, state = teacher(), progress()
    to_hm_selected(controller, state)
    controller.context(text_at((1, 14, "It contained CUT!")), state)
    for phrase in ["Teach", "Teach C", "Teach CUT to a"]:
        assert controller.context(text_at((1, 14, phrase)), state)["available_actions"] == ["wait"]
    result = controller.context(TEACH_QUESTION, state)
    assert result["menu_label"] == "YES"


def test_partial_text_wait_budget_does_not_reset_when_letters_progress():
    controller, state = teacher(), progress()
    to_learning(controller, state)
    phrases = ["D", "De", "Del", "Dele", "Delet", "Delete", "Delete an", "Delete an older"]
    for i in range(MAX_SAFE_TEXT_WAITS):
        result = controller.context(text_at((1, 14, phrases[min(i, len(phrases)-1)])), state)
        assert result["available_actions"] == ["wait"] and result["safe_wait_count"] == i+1
    result = controller.context(text_at((1, 14, "Delete an older")), state)
    assert result["review_reason"] == "cut_known_transition_wait_exhausted"


def test_unknown_text_during_known_transition_still_latches_review():
    controller, state = teacher(), progress()
    to_hm_selected(controller, state)
    assert controller.context(text_at((1, 14, "Booted")), state)["available_actions"] == ["wait"]
    result = controller.context(text_at((1, 14, "A mysterious error")), state)
    assert result["phase"] == "campaign_review" and result["available_actions"] == ["wait"]
    assert controller.context(text_at((1, 14, "Booted")), state) == result


def test_prefix_wait_never_hides_wrong_move_fingerprint_or_unexpected_forget():
    controller, state = teacher(), progress()
    to_learning(controller, state)
    state["party"][0]["moves"] = [77, 45, 73, 15]
    assert controller.context(text_at((1, 14, "Delete")), state)["review_reason"] == "cut_unexpected_move_replacement"
    controller, state = teacher(), progress()
    to_learning(controller, state)
    assert controller.context(text_at((1, 14, "IVYSAUR forgot")), state)["review_reason"] == "cut_forget_animation_without_selection"


def test_expected_growl_forget_can_print_slowly_but_wrong_move_cannot():
    controller, state = teacher(), progress()
    to_learning(controller, state)
    controller.context(DELETE_QUESTION, state)
    chosen = deepcopy(FORGET)
    chosen["cells"][8][5] = " "
    chosen["cells"][9][5] = "▶"
    controller.context(chosen, state)
    for phrase in ["IVYSAUR for", "IVYSAUR forgot", "IVYSAUR forgot G"]:
        assert controller.context(text_at((1, 14, phrase)), state)["available_actions"] == ["wait"]
    result = controller.context(text_at((1, 14, "IVYSAUR forgot"), (1, 16, "VINE W")), state)
    assert result["review_reason"] == "cut_forgot_move_not_visually_growl"


def test_partial_wait_does_not_mask_visible_choices_or_page_marker():
    controller, state = teacher(), progress()
    to_learning(controller, state)
    result = controller.context(text_at((1, 14, "Delete"), (18, 16, "▼")), state)
    assert result["phase"] == "campaign_review"
    controller, state = teacher(), progress()
    to_learning(controller, state)
    controller.context(text_at((1, 14, "Delete")), state)
    result = controller.context(text_at((1, 14, "for CUT?"), (16, 8, "YES"), (16, 10, "NO")), state)
    assert result["phase"] == "campaign_review" and "cursor_unreadable" in result["review_reason"]


def test_only_known_transition_can_wait_for_blank_and_wait_is_bounded():
    controller, state = teacher(), progress()
    controller.context(text_at(), state, overworld_ready=True)
    assert controller.context(text_at(), state)["phase"] == "campaign_review"
    controller, state = teacher(), progress()
    to_hm_selected(controller, state)
    for _ in range(MAX_SAFE_TEXT_WAITS):
        assert controller.context(text_at(), state)["available_actions"] == ["wait"]
    assert controller.context(text_at(), state)["review_reason"] == "cut_known_transition_wait_exhausted"


def test_field_hacked_partial_and_animation_blank_have_shared_bounded_waits():
    controller, state = field(), progress(cut=True)
    to_field_selection(controller, state)
    for phrase in ["IVYSAUR hack", "IVYSAUR hacked", "away with C"]:
        assert controller.context(text_at((1, 14, phrase)), state)["available_actions"] == ["wait"]
    result = controller.context(text_at((1, 14, "IVYSAUR hacked"), (1, 16, "away with CUT!")), state)
    assert result["available_actions"] == ["a", "wait"]
    for _ in range(MAX_SAFE_TEXT_WAITS):
        assert controller.context(text_at(), state)["available_actions"] == ["wait"]
    assert controller.context(text_at(), state)["review_reason"] == "cut_known_transition_wait_exhausted"


def test_field_animation_unknown_text_is_not_hidden_by_wait():
    controller, state = field(), progress(cut=True)
    to_field_selection(controller, state)
    controller.context(text_at((1, 14, "IVYSAUR hacked"), (1, 16, "away with CUT!")), state)
    result = controller.context(text_at((1, 14, "SOMETHING ELSE")), state)
    assert result["review_reason"] == "cut_field_animation_screen_unrecognized"


def test_partial_learned_cut_waits_and_still_requires_expected_installed_moves():
    controller, state = teacher(), progress()
    to_learning(controller, state)
    controller.context(DELETE_QUESTION, state)
    chosen = deepcopy(FORGET)
    chosen["cells"][8][5] = " "
    chosen["cells"][9][5] = "▶"
    controller.context(chosen, state)
    state["party"][0]["moves"][1] = 15
    assert controller.context(text_at((1, 14, "IVYSAUR learned")), state)["available_actions"] == ["wait"]
    assert controller.context(text_at((1, 14, "IVYSAUR learned"), (1, 16, "CUT!")), state)["available_actions"] == ["a", "wait"]
    state["party"][0]["moves"][1] = 45
    result = controller.context(text_at(), state)
    assert result["review_reason"] == "cut_learned_message_without_expected_moves"


LIVE_INVENTORY = [{"item": item, "quantity": quantity} for item, quantity in
                  [(4, 6), (234, 1), (42, 1), (211, 1), (49, 1), (63, 1), (228, 1), (196, 1)]]
LIVE_ITEM_LABELS = {4: "POKé BALL", 234: "TM34", 42: "HELIX FOSSIL", 211: "TM11",
                    49: "NUGGET", 63: "S.S.TICKET", 228: "TM28", 196: "HM01"}


def live_bag(offset=0, cursor=0, *, inventory=None):
    inventory = LIVE_INVENTORY if inventory is None else inventory
    entries = [(12, 14, "EXIT"), (5, 4+2*cursor, "▶")]
    for index in range(4):
        y = 4+index*2
        if offset+index == len(inventory):
            entries.append((6, y, "CANCEL"))
            break
        item = inventory[offset+index]
        entries.append((6, y, LIVE_ITEM_LABELS[item["item"]]))
        if item["item"] not in {42, 63, 196}:
            entries.append((14, y+1, f"×{item['quantity']:2d}"))
    return text_at(*entries)


def teacher_at_real_bag():
    controller, state = teacher(), progress()
    state["inventory"] = deepcopy(LIVE_INVENTORY)
    controller.context(text_at(), state, overworld_ready=True)
    controller.context(START, state)
    return controller, state


def test_real_bag_first_page_is_verified_against_all_four_ordered_labels_and_quantities():
    controller, state = teacher_at_real_bag()
    result = controller.context(live_bag(), state)
    assert result["available_actions"] == ["down", "wait"]
    assert result["bag_visible_item_ids"] == [4, 234, 42, 211]
    assert result["bag_cursor_inventory_index"] == 0 and result["bag_hm01_inventory_index"] == 7
    assert result["controller_menu_verified"] and result["bag_down_requests"] == 1


def test_normal_down_scrolling_reaches_eighth_item_without_confirming_other_items():
    controller, state = teacher_at_real_bag()
    pages = [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2), (3, 2), (4, 2)]
    for offset, cursor in pages:
        result = controller.context(live_bag(offset, cursor), state)
        assert result["available_actions"] == ["down", "wait"], result
        assert "a" not in result["available_actions"]
    # HM01 第四列只是預覽，必須再捲一格；真正移到可選第三列才確認。
    assert result["bag_visible_item_ids"] == [49, 63, 228, 196]
    result = controller.context(live_bag(5, 2), state)
    assert result["available_actions"] == ["a", "wait"] and result["menu_label"] == "HM01"
    assert controller.stage == "hm_selected" and result["bag_cursor_inventory_index"] == 7


@pytest.mark.parametrize("change,reason", [
    (lambda text: text["cells"][5].__setitem__(slice(14, 18), list("× 5 ")),
     "cut_bag_visible_quantity_mismatch"),
    (lambda text: text["cells"][9].__setitem__(slice(14, 18), list("× 1 ")),
     "cut_bag_key_item_quantity_layout_mismatch"),
    (lambda text: text["cells"][4].__setitem__(slice(6, 19), list("ULTRA BALL   ")),
     "cut_bag_visible_item_label_unknown"),
    (lambda text: text["cells"][6].__setitem__(slice(6, 19), list("TM28         ")),
     "cut_bag_visible_order_mismatch"),
    (lambda text: text["cells"][6].__setitem__(5, "▷"),
     "cut_bag_cursor_or_swap_marker_unverified"),
])
def test_unverified_real_bag_never_scrolls_or_confirms(change, reason):
    controller, state = teacher_at_real_bag()
    text = live_bag()
    change(text)
    result = controller.context(text, state)
    assert result["review_reason"] == reason and result["available_actions"] == ["wait"]


def test_scrolling_stalls_after_three_unanswered_down_requests():
    controller, state = teacher_at_real_bag()
    for _ in range(MAX_BAG_STAGNANT_REQUESTS):
        assert controller.context(live_bag(), state)["available_actions"] == ["down", "wait"]
    result = controller.context(live_bag(), state)
    assert result["review_reason"] == "cut_bag_down_made_no_visible_progress"
    assert controller.context(live_bag(0, 1), state) == result


def test_scrolling_request_limit_is_fail_closed_and_legacy_objects_use_lazy_fields():
    controller, state = teacher_at_real_bag()
    assert not hasattr(controller, "bag_down_requests")
    controller.bag_down_requests = MAX_BAG_DOWN_REQUESTS
    result = controller.context(live_bag(), state)
    assert result["review_reason"] == "cut_bag_down_request_limit"
    controller, state = teacher_at_real_bag()
    assert not hasattr(controller, "bag_inventory_fingerprint")
    assert controller.context(live_bag(), state)["bag_down_requests"] == 1


def test_changed_inventory_or_backward_cursor_stops_the_scroll_session():
    controller, state = teacher_at_real_bag()
    controller.context(live_bag(), state)
    state["inventory"][0]["quantity"] = 5
    result = controller.context(live_bag(0, 1, inventory=state["inventory"]), state)
    assert result["review_reason"] == "cut_bag_inventory_changed_during_selection"
    controller, state = teacher_at_real_bag()
    controller.context(live_bag(0, 2), state)
    assert controller.context(live_bag(0, 1), state)["review_reason"] == "cut_bag_cursor_moved_backwards"


def test_hm01_above_current_visible_page_is_not_guessed_down():
    controller, state = teacher_at_real_bag()
    state["inventory"] = [state["inventory"][-1], *state["inventory"][:-1]]
    result = controller.context(live_bag(1, 0, inventory=state["inventory"]), state)
    assert result["review_reason"] == "cut_bag_hm01_not_below_visible_page"


def test_visible_hm_is_selected_only_after_the_actual_label_order_is_verified():
    controller, state = teacher_at_real_bag()
    text = live_bag(5, 2)
    text["cells"][4][6:19] = list("NUGGET       ")
    result = controller.context(text, state)
    assert result["phase"] == "campaign_review" and "a" not in result["available_actions"]
