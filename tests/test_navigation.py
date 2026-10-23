"""只使用合成座標／記憶體，未啟動遊戲或模型。"""
from types import SimpleNamespace

import pytest

from laya_pokemon.navigation import LOCATION_ADDRESSES, collision_direction, opening_waypoint, read_location


def location(map_id, x, y):
    return {"map_id": map_id, "x": x, "y": y}


@pytest.mark.parametrize("x,y,objective", [(3, 6, "Move RIGHT."), (8, 1, "Move LEFT."),
                                          (7, 5, "Move UP."), (7, 0, "Move DOWN."), (7, 1, "Wait.")])
def test_second_floor_reaches_stairs_x_before_y(x, y, objective):
    result = opening_waypoint(location(0x26, x, y))
    assert result["objective"] == objective
    assert result["controller_waypoint"] == location(0x26, 7, 1)


@pytest.mark.parametrize("x,y,objective", [(7, 1, "Move DOWN."), (1, 8, "Move UP."),
                                          (7, 6, "Move LEFT."), (1, 6, "Move RIGHT."),
                                          (3, 6, "Move DOWN."), (3, 7, "Move DOWN.")])
def test_first_floor_exit_row_then_column_then_door(x, y, objective):
    assert opening_waypoint(location(0x25, x, y))["objective"] == objective


@pytest.mark.parametrize("x,y,objective", [(5, 6, "Move RIGHT."), (11, 3, "Move LEFT."),
                                          (10, 5, "Move UP."), (10, 0, "Move DOWN."), (10, 1, "Wait.")])
def test_pallet_goes_to_north_trigger_by_column_first(x, y, objective):
    assert opening_waypoint(location(0, x, y))["objective"] == objective


def test_followed_oak_waits_instead_of_navigating_pallet_again():
    result = opening_waypoint(location(0, 5, 6), story_flags={"followed_oak_into_lab": True})
    assert result["goal"] == "wait_for_oak_story" and result["objective"] == "Wait."
    assert result["available_actions"] == ["wait", "a", "b"]


@pytest.mark.parametrize("flags", [None, {}, {"oak_asked_to_choose_mon": False}])
def test_lab_waits_for_oak_instruction_before_navigating(flags):
    result = opening_waypoint(location(0x28, 5, 3), story_flags=flags)
    assert result["goal"] == "wait_for_oak_starter_instruction"
    assert result["objective"] == "Wait."


@pytest.mark.parametrize("x,y,objective", [(5, 3, "Move DOWN."), (5, 5, "Move UP."),
                                          (5, 4, "Move RIGHT."), (9, 4, "Move LEFT."), (8, 4, "Move UP.")])
def test_lab_bulbasaur_target_row_before_column_then_face_north(x, y, objective):
    result = opening_waypoint(location(0x28, x, y), story_flags={"oak_asked_to_choose_mon": True})
    assert result["objective"] == objective


def test_bulbasaur_interaction_requires_last_executed_action_up():
    kwargs = {"story_flags": {"oak_asked_to_choose_mon": True}}
    result = opening_waypoint(location(0x28, 8, 4), ("right", "up"), **kwargs)
    assert result["goal"] == "interact_with_bulbasaur_ball"
    assert result["available_actions"] == ["a", "b", "wait"]
    assert result["controller_waypoint"] == location(0x28, 8, 3)
    assert opening_waypoint(location(0x28, 8, 4), ("up", "right"), **kwargs)["goal"] == "face_bulbasaur_ball"


def test_owned_party_stops_this_stage_without_selecting_another_ball():
    result = opening_waypoint(location(0x28, 8, 4), has_party=True)
    assert result["goal"] == "starter_acquired" and result["objective"] == "Wait."


def test_unverified_starter_is_explicitly_unsupported():
    result = opening_waypoint(location(0x28, 8, 4), starter="SQUIRTLE",
                              story_flags={"oak_asked_to_choose_mon": True})
    assert result["status"] == "unsupported" and result["controller_waypoint"] is None


def test_unknown_location_does_not_invent_waypoints():
    assert opening_waypoint(None) is None
    assert opening_waypoint(location(99, 2, 3)) is None


def test_read_location_uses_verified_addresses_and_does_not_write():
    class ReadOnlyMemory:
        def __getitem__(self, address):
            return {0xD35E: 0x26, 0xD362: 7, 0xD361: 1}[address]

    assert read_location(SimpleNamespace(memory=ReadOnlyMemory())) == location(0x26, 7, 1)
    assert LOCATION_ADDRESSES == {"map_id": 0xD35E, "x": 0xD362, "y": 0xD361}


@pytest.mark.parametrize("invalid", [-1, 256, True, "1", 1.5, None])
def test_non_byte_location_values_are_rejected(invalid):
    game = SimpleNamespace(memory={0xD35E: invalid, 0xD362: 7, 0xD361: 1})
    with pytest.raises(ValueError):
        read_location(game)
    with pytest.raises(ValueError):
        opening_waypoint(location(0x26, invalid, 1))


def test_all_waypoints_offer_multiple_candidates_and_no_button_decision():
    cases = [opening_waypoint(location(0x26, 3, 6)), opening_waypoint(location(0, 10, 1)),
             opening_waypoint(location(0x28, 8, 4), ("up",), {"oak_asked_to_choose_mon": True})]
    for result in cases:
        assert len(result["available_actions"]) >= 2 and result["source"]
        assert "action" not in result and "button" not in result


def test_does_not_modify_supplied_location_or_flags():
    current, flags = location(0x28, 5, 4), {"oak_asked_to_choose_mon": True}
    opening_waypoint(current, story_flags=flags)
    assert current == location(0x28, 5, 4) and flags == {"oak_asked_to_choose_mon": True}


def test_collision_bfs_detours_around_blocked_direct_step():
    walkable = [[1] * 5 for _ in range(5)]
    walkable[2][2] = 0
    result = collision_direction(walkable, (1, 2), {"x": 11, "y": 12}, {"x": 13, "y": 12})
    assert result["direction"] == "up" and result["endpoint"] == [13, 12]
    assert result["world_offset"] == [10, 10]
    assert result["path_world"][0] == [11, 12] and len(result["path_world"]) == 5
    assert [12, 12] not in result["path_world"]
    for x, y in result["path_world"]:
        assert walkable[y - 10][x - 10] == 1


def test_collision_bfs_offscreen_target_uses_nearest_reachable_frontier():
    walkable = [[1] * 5 for _ in range(5)]
    result = collision_direction(walkable, (2, 2), (10, 10), (20, 10))
    assert result["direction"] == "right" and result["endpoint"] == [12, 10]
    assert result["path_world"] == [[10, 10], [11, 10], [12, 10]]


def test_collision_bfs_equal_target_distances_choose_shortest_route():
    walkable = [[1] * 5 for _ in range(3)]
    walkable[1][2] = 0
    result = collision_direction(walkable, (0, 1), (0, 1), (2, 1))
    # (1,1)、(2,0)、(2,2) 與被擋目標等距；選到達步數最少者。
    assert result["endpoint"] == [1, 1] and result["path_world"] == [[0, 1], [1, 1]]


def test_collision_bfs_offscreen_diagonal_target_reaches_nearest_corner():
    walkable = [[1] * 5 for _ in range(5)]
    result = collision_direction(walkable, (2, 1), (2, 1), (8, 8))
    assert result["endpoint"] == [4, 4] and len(result["path_world"]) == 6


def test_collision_bfs_unreachable_or_no_improving_endpoint_is_none():
    assert collision_direction([[0, 0, 0], [0, 1, 0], [0, 0, 0]], (1, 1), (5, 5), (6, 5)) is None
    # 目標本身被擋，起點已是可達集合中最近的一格。
    assert collision_direction([[1, 0, 0], [1, 0, 0], [1, 0, 0]], (0, 1), (0, 1), (1, 1)) is None


def test_collision_bfs_at_goal_and_blocked_player_cell_are_none():
    assert collision_direction([[1]], (0, 0), (3, 4), (3, 4)) is None
    assert collision_direction([[0, 1]], (0, 0), (3, 4), (4, 4)) is None
    assert collision_direction([], (0, 0), (3, 4), (4, 4)) is None


def test_collision_bfs_offscreen_target_without_reachable_frontier_is_none():
    walkable = [[0] * 5 for _ in range(5)]
    walkable[2][2] = walkable[2][3] = 1
    assert collision_direction(walkable, (2, 2), (5, 5), (20, 5)) is None


def test_collision_bfs_does_not_mutate_any_inputs():
    walkable, point, target = [[1] * 3 for _ in range(3)], {"x": 7, "y": 8}, {"x": 8, "y": 9}
    before = [row[:] for row in walkable]
    collision_direction(walkable, (1, 1), point, target)
    assert walkable == before and point == {"x": 7, "y": 8} and target == {"x": 8, "y": 9}
