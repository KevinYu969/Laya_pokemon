"""合成可見選單與唯讀旗標；不載入 ROM 或模型。"""
from types import SimpleNamespace

import pytest

from laya_pokemon.battle import battle_context, read_battle_state
from laya_pokemon.navigation import opening_waypoint


def text_at(*entries):
    cells = [[" "] * 20 for _ in range(18)]
    for x, y, word in entries:
        cells[y][x:x + len(word)] = list(word)
    rows = ["".join(row) for row in cells]
    return {"cells": cells, "lines": [row for row in rows if row.strip()],
            "line_rows": [y for y, row in enumerate(rows) if row.strip()]}


def test_read_battle_state_never_equates_active_or_lost_to_win():
    for raw, active in [(0, False), (1, True), (2, True), (255, False), (17, None)]:
        result = read_battle_state(SimpleNamespace(memory={0xD057: raw}))
        assert result["active"] is active and result["victory_confirmed"] is None
    with pytest.raises(ValueError):
        read_battle_state(SimpleNamespace(memory={0xD057: True}))


@pytest.mark.parametrize("cursor,objective", [((9, 14), "Confirm the current selection."),
                                              ((9, 16), "Move UP."), ((15, 14), "Move LEFT.")])
def test_command_menu_goes_to_fight_instead_of_confirming_run(cursor, objective):
    text = text_at((10, 14, "FIGHT"), (10, 16, "ITEM"), (16, 16, "RUN"), (*cursor, "▶"))
    result = battle_context(text, {"active": True})
    assert result["objective"] == objective and result["battle_menu"] == "command"
    assert "action" not in result and len(result["available_actions"]) > 1


def test_moves_choose_tackle_from_growl_and_require_a_single_cursor():
    text = text_at((5, 13, "TACKLE"), (5, 14, "GROWL"), (4, 14, "▶"))
    assert battle_context(text, {"active": True})["objective"] == "Move UP."
    text["cells"][13][4] = "▶"
    assert battle_context(text, {"active": True})["available_actions"] == ["wait", "b"]


def test_tackle_mentioned_in_dialogue_is_not_a_moves_menu():
    text = text_at((1, 14, "BULBASAUR used"), (1, 16, "TACKLE!"))
    assert battle_context(text, {"active": True})["phase"] == "battle_dialogue"
    assert battle_context(text, {"active": False}) is None


def test_animation_is_not_overworld_navigation():
    assert battle_context(text_at(), {"active": True})["phase"] == "battle_animation"


def test_low_visible_hp_retreats_only_in_wild_battle_and_not_using_move_pp():
    text = text_at((12, 11, "10/21"), (10, 14, "FIGHT"), (10, 16, "ITEM"), (16, 16, "RUN"), (9, 14, "▶"))
    wild = battle_context(text, {"active": True, "kind": "wild"})
    assert wild["battle_tactic"] == "retreat" and wild["objective"] == "Move DOWN."
    trainer = battle_context(text, {"active": True, "kind": "trainer"})
    assert trainer["battle_tactic"] == "damage" and trainer["objective"] == "Confirm the current selection."
    moves = text_at((12, 11, "10/21"), (5, 12, "30/35"), (6, 13, "TACKLE"), (6, 14, "GROWL"), (5, 13, "▶"))
    assert battle_context(moves, {"active": True, "kind": "wild"})["available_actions"] == ["b", "wait"]
    moves["cells"][11] = [" "] * 20
    assert battle_context(moves, {"active": True, "kind": "wild"})["objective"] == "Confirm the current selection."


def test_injured_party_visits_nurse_then_healthy_party_exits_center():
    kwargs = {"story_flags": {"battled_rival_in_oaks_lab": True}, "has_party": True, "stage": "to_parcel"}
    city = {"map_id": 1, "x": 20, "y": 30}
    assert opening_waypoint(city, party_injured=True, **kwargs)["controller_waypoint"] == {"map_id": 1, "x": 23, "y": 26}
    center = {"map_id": 41, "x": 3, "y": 3}
    assert opening_waypoint(center, party_injured=True, **kwargs)["goal"] == "face_nurse"
    assert opening_waypoint(center, ("up",), party_injured=True, **kwargs)["goal"] == "interact_with_nurse"
    assert opening_waypoint(center, party_injured=False, **kwargs)["goal"] == "reach_center_exit"


def test_lab_rival_requires_completed_starter_script_then_triggers_y6():
    location = {"map_id": 40, "x": 8, "y": 4}
    kwargs = {"has_party": True, "stage": "lab_rival"}
    assert opening_waypoint(location, **kwargs)["goal"] == "wait_for_rival_starter"
    assert opening_waypoint(location, story_flags={"got_starter": True}, **kwargs)["objective"] == "Move LEFT."
    location["x"] = 5
    assert opening_waypoint(location, story_flags={"got_starter": True}, **kwargs)["objective"] == "Move DOWN."
    location["y"] = 6
    assert opening_waypoint(location, story_flags={"got_starter": True}, **kwargs)["objective"] == "Wait."
    assert opening_waypoint(location, story_flags={"battled_rival_in_oaks_lab": True}, **kwargs)["goal"] == "lab_rival_finished"


def test_parcel_route_does_not_skip_battle_or_treat_received_parcel_as_delivered():
    kwargs = {"has_party": True, "stage": "to_parcel"}
    location = {"map_id": 40, "x": 5, "y": 6}
    assert opening_waypoint(location, **kwargs)["goal"] == "parcel_requires_lab_battle"
    assert opening_waypoint(location, story_flags={"battled_rival_in_oaks_lab": True}, **kwargs)["controller_waypoint"] == {"map_id": 40, "x": 5, "y": 11}
    result = opening_waypoint(location, story_flags={"got_oaks_parcel": True}, **kwargs)
    assert result["goal"] == "parcel_collected" and result["objective"] == "Wait."


@pytest.mark.parametrize("map_id,x,y,target", [(40, 5, 11, (5, 12)), (0, 12, 12, (9, 12)),
                                              (0, 9, 12, (9, 6)), (0, 10, 0, (10, -1)),
                                              (12, 10, 30, (10, -1)), (1, 29, 20, (29, 19))])
def test_parcel_route_has_explicit_aisles_and_map_edges(map_id, x, y, target):
    result = opening_waypoint({"map_id": map_id, "x": x, "y": y},
                              story_flags={"battled_rival_in_oaks_lab": True}, has_party=True, stage="to_parcel")
    assert result["controller_waypoint"] == {"map_id": map_id, "x": target[0], "y": target[1]}


def test_delivery_requires_parcel_then_prioritizes_healing_and_stops_at_pokedex():
    kwargs = {"has_party": True, "stage": "deliver_parcel"}
    location = {"map_id": 1, "x": 29, "y": 20}
    assert opening_waypoint(location, **kwargs)["goal"] == "delivery_requires_parcel"
    flags = {"got_oaks_parcel": True}
    assert opening_waypoint(location, story_flags=flags, party_injured=True, **kwargs)["goal"] == "reach_viridian_center"
    assert opening_waypoint(location, story_flags=flags, **kwargs)["controller_waypoint"]["y"] == 36
    flags["got_pokedex"] = True
    assert opening_waypoint(location, story_flags=flags, **kwargs)["goal"] == "pokedex_received"


@pytest.mark.parametrize("map_id,x,y,target", [(42, 3, 7, (3, 8)), (12, 10, 5, (10, 36)),
                                              (0, 10, 0, (10, 6)), (0, 9, 6, (9, 12)),
                                              (0, 12, 12, (12, 11)), (40, 5, 8, (5, 3))])
def test_delivery_route_has_verified_map_edges_and_oak_interaction(map_id, x, y, target):
    result = opening_waypoint({"map_id": map_id, "x": x, "y": y}, story_flags={"got_oaks_parcel": True},
                              has_party=True, stage="deliver_parcel")
    assert result["controller_waypoint"] == {"map_id": map_id, "x": target[0], "y": target[1]}
