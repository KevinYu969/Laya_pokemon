"""已核對開場地點的局部導航目標；此控制器不選擇或執行按鍵。"""
from __future__ import annotations

from collections.abc import Mapping
from collections import deque
from numbers import Integral


LOCATION_ADDRESSES = {"map_id": 0xD35E, "x": 0xD362, "y": 0xD361}
LOCATION_SOURCE = "https://raw.githubusercontent.com/PWhiddy/PokemonRedExperiments/master/baselines/memory_addresses.py"
_BASE = "https://raw.githubusercontent.com/pret/pokered/master/"
_DIRECTIONS = ["up", "down", "left", "right", "wait"]
_WAIT = ["wait", "a", "b"]
_INTERACTION = ["a", "b", "wait"]


def _byte(value):
    if not isinstance(value, Integral) or isinstance(value, bool) or not 0 <= value <= 255:
        raise ValueError("位置讀值須為 0 至 255 的整數")
    return int(value)


def read_location(pyboy) -> dict:
    """僅讀取已公開核對的英文版 map/x/y 位址，不寫遊戲記憶體。"""
    return {name: _byte(pyboy.memory[address]) for name, address in LOCATION_ADDRESSES.items()}


def _xy(value):
    if isinstance(value, Mapping):
        pair = value["x"], value["y"]
    else:
        if len(value) != 2:
            raise ValueError("座標須包含 x、y")
        pair = value[0], value[1]
    if any(not isinstance(coordinate, Integral) or isinstance(coordinate, bool) for coordinate in pair):
        raise ValueError("座標須為整數")
    return tuple(int(coordinate) for coordinate in pair)


def collision_direction(walkable, player_cell, location, target) -> dict | None:
    """在唯讀碰撞格上 BFS，提供可走局部路徑，不執行任何動作。

    ``walkable[y][x] == 1`` 才可通行；``player_cell`` 是螢幕碰撞格座標。
    視窗外目標使用可達邊界格，等距取最短路線；沒有比起點更近的端點則回 None。
    ``path_world`` 包含起點，所有輸出座標為玩家行走格 ``[x, y]``。
    """
    height = len(walkable)
    if height == 0:
        return None
    width = len(walkable[0])
    if width == 0:
        return None
    if any(len(row) != width for row in walkable):
        raise ValueError("碰撞格必須為矩形")
    if any(not isinstance(cell, Integral) or cell not in (0, 1) for row in walkable for cell in row):
        raise ValueError("碰撞格只能包含 0 或 1")
    start = _xy(player_cell)
    world_start, world_target = _xy(location), _xy(target)
    if world_start == world_target:
        return None
    if not 0 <= start[0] < width or not 0 <= start[1] < height or walkable[start[1]][start[0]] != 1:
        return None
    offset = world_start[0] - start[0], world_start[1] - start[1]
    local_target = world_target[0] - offset[0], world_target[1] - offset[1]
    offscreen = not (0 <= local_target[0] < width and 0 <= local_target[1] < height)

    def distance(point):
        return abs(point[0] - local_target[0]) + abs(point[1] - local_target[1])

    parents, depths = {start: None}, {start: 0}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            neighbour = current[0] + dx, current[1] + dy
            nx, ny = neighbour
            if (0 <= nx < width and 0 <= ny < height and walkable[ny][nx] == 1
                    and neighbour not in parents):
                parents[neighbour] = current
                depths[neighbour] = depths[current] + 1
                queue.append(neighbour)
    candidates = list(parents)
    if offscreen:
        candidates = [point for point in candidates if point[0] in (0, width - 1) or point[1] in (0, height - 1)]
        if not candidates:
            return None
    endpoint = min(candidates, key=lambda point: (distance(point), depths[point]))
    if distance(endpoint) >= distance(start):
        return None
    path = []
    node = endpoint
    while node is not None:
        path.append(node)
        node = parents[node]
    path.reverse()
    step = path[1][0] - start[0], path[1][1] - start[1]
    direction = {(0, -1): "up", (0, 1): "down", (-1, 0): "left", (1, 0): "right"}[step]
    return {"direction": direction, "path_world": [[x + offset[0], y + offset[1]] for x, y in path],
            "endpoint": [endpoint[0] + offset[0], endpoint[1] + offset[1]], "world_offset": list(offset)}


def _goal(goal, objective, map_id, target, sources, *, interaction=False, waiting=False):
    return {
        "goal": goal, "objective": objective,
        "available_actions": list(_WAIT if waiting else _INTERACTION if interaction else _DIRECTIONS),
        "controller_waypoint": None if target is None else {"map_id": map_id, "x": target[0], "y": target[1]},
        "source": [_BASE + source for source in sources],
    }


def _move_toward(goal, current, target, axis, map_id, waypoint, sources):
    negative, positive = ("LEFT", "RIGHT") if axis == "x" else ("UP", "DOWN")
    direction = negative if current > target else positive
    return _goal(goal, f"Move {direction}.", map_id, waypoint, sources)


def opening_waypoint(location, previous_actions=(), story_flags=None, has_party=False, starter="BULBASAUR") -> dict | None:
    """提供開場 waypoint 與候選集合，實際按鍵仍交本機 Laya 決定。

    ``previous_actions`` 是已執行動作名稱的字串序列。這些目標不是完整通關策略，
    也不保證家具、NPC 或劇情中的道路可通行；主控必須另行記錄控制器貢獻。
    """
    if location is None:
        return None
    if not isinstance(location, Mapping) or not all(key in location for key in LOCATION_ADDRESSES):
        raise ValueError("位置須包含 map_id、x、y")
    map_id, x, y = (_byte(location[key]) for key in ("map_id", "x", "y"))
    flags = {} if story_flags is None else story_flags
    if map_id == 0x26:
        sources, target = ["data/maps/objects/RedsHouse2F.asm"], (7, 1)
        if x != 7:
            return _move_toward("reach_2f_stairs_x", x, 7, "x", map_id, target, sources)
        if y != 1:
            return _move_toward("reach_2f_stairs_y", y, 1, "y", map_id, target, sources)
        return _goal("wait_for_stairs_transition", "Wait.", map_id, target, sources, waiting=True)
    if map_id == 0x25:
        sources = ["data/maps/objects/RedsHouse1F.asm"]
        if (x, y) == (3, 7):
            # 站上門格尚未切圖；本 ROM 的唯讀存檔探測確認須再向下走一步。
            return _goal("step_out_house", "Move DOWN.", map_id, (3, 8), sources)
        if y != 6:
            return _move_toward("reach_1f_exit_row", y, 6, "y", map_id, (x, 6), sources)
        if x != 3:
            return _move_toward("reach_1f_door_column", x, 3, "x", map_id, (3, 6), sources)
        return _goal("enter_1f_exit", "Move DOWN.", map_id, (3, 7), sources)
    if map_id == 0x00:
        sources = ["scripts/PalletTown.asm"]
        if flags.get("followed_oak_into_lab") is True:
            return _goal("wait_for_oak_story", "Wait.", map_id, None, sources, waiting=True)
        if x != 10:
            return _move_toward("reach_pallet_north_column", x, 10, "x", map_id, (10, y), sources)
        if y != 1:
            return _move_toward("trigger_oak_at_north_exit", y, 1, "y", map_id, (10, 1), sources)
        return _goal("wait_for_oak_trigger", "Wait.", map_id, (10, 1), sources, waiting=True)
    if map_id == 0x28:
        sources = ["scripts/OaksLab.asm", "data/maps/objects/OaksLab.asm"]
        if has_party:
            return _goal("starter_acquired", "Wait.", map_id, None, sources, waiting=True)
        if not isinstance(starter, str) or starter.upper() != "BULBASAUR":
            result = _goal("unsupported_starter", "Unsupported starter; wait for a verified waypoint.",
                           map_id, None, sources, waiting=True)
            result["status"] = "unsupported"
            return result
        if flags.get("oak_asked_to_choose_mon") is not True:
            return _goal("wait_for_oak_starter_instruction", "Wait.", map_id, None, sources, waiting=True)
        if y != 4:
            return _move_toward("reach_starter_interaction_row", y, 4, "y", map_id, (x, 4), sources)
        if x != 8:
            return _move_toward("reach_bulbasaur_ball", x, 8, "x", map_id, (8, 4), sources)
        if not previous_actions or previous_actions[-1] != "up":
            return _goal("face_bulbasaur_ball", "Move UP.", map_id, (8, 3), sources)
        return _goal("interact_with_bulbasaur_ball", "Interact with the Bulbasaur Poke Ball.",
                     map_id, (8, 3), sources, interaction=True)
    return None
