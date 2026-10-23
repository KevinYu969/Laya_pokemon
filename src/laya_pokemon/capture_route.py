"""取得圖鑑後的有限捕捉路線；先補球，再在22號道路東側找尼多朗♂。"""
from .navigation import _goal, _parcel_waypoint, _center_waypoint
from .team_strategy import family


SOURCES = ["data/maps/objects/Route22.asm", "scripts/Route22.asm", "data/wild/maps/Route22.asm"]


def team_waypoint(location, flags, party, balls, previous_actions=(), grass_world=(), *, training=False):
    mid, x, y = (location[key] for key in ("map_id", "x", "y"))
    from .team_strategy import effective_power
    low_pp=any(sum((pp&63) for move,pp in zip(mon.get('moves',[]),mon.get('pp',[]))
                   if effective_power(move,mon['species'])>0)<=3 for mon in party[:1] if 'moves' in mon and 'pp' in mon)
    injured = any(mon["hp"] < mon["max_hp"] or mon.get('status',0) for mon in party) or low_pp
    owned = {family(mon["species"]) for mon in party}
    if training and party and party[0]["level"] >= 13:
        return _goal("lead_training_complete", "Wait.", mid, None, SOURCES, waiting=True)
    if not training and "NIDORAN_M" in owned:
        return _goal("first_team_capture_complete", "Wait.", mid, None, SOURCES, waiting=True)
    if balls is None or not flags.get("got_pokedex"):
        return _goal("capture_requires_verified_inventory_and_pokedex", "Wait.", mid, None, SOURCES, waiting=True)
    if len(party) >= 6:
        return _goal("capture_requires_pc_review", "Wait.", mid, None, SOURCES, waiting=True)
    # 缺球或受傷則原路回城；不往西踩勁敵觸發格(29,4)/(29,5)。
    if mid == 33:
        if any(mon["hp"] * 3 <= mon["max_hp"] * 2 or mon.get('status',0) for mon in party) or balls == 0 or low_pp:
            return _goal("return_route22_east", "Move RIGHT.", mid, (40, 9), SOURCES)
        candidates = [(gx, gy) for gx, gy in grass_world if 30 <= gx <= 39 and 6 <= gy <= 17 and (gx, gy) != (x, y)]
        target = min(candidates, key=lambda p: (abs(p[0]-x)+abs(p[1]-y), p)) if candidates else (33, 12)
        return _goal("patrol_route22_east_grass", "Move LEFT.", mid, target, SOURCES)
    center = _center_waypoint(mid, x, y, injured, previous_actions, SOURCES)
    if center:
        return center
    if mid == 42 and balls >= 8:
        if x != 3:
            return _goal("reach_mart_exit_column", "Move RIGHT." if x < 3 else "Move LEFT.", mid, (3, y), SOURCES)
        return _goal("reach_mart_exit" if y < 7 else "step_out_mart", "Move DOWN.", mid, (3, 7 if y < 7 else 8), SOURCES)
    if mid == 1 and balls >= 3:
        # 西側連接：Route22 y10 = Viridian y18；先走街道後往西。
        if x > 10:
            return _goal("reach_viridian_west_road", "Move LEFT.", mid, (10, 18), SOURCES)
        return _goal("leave_viridian_west", "Move LEFT.", mid, (-1, 18), SOURCES)
    return _parcel_waypoint(mid, x, y, flags, injured, previous_actions, resupply=True)


def visible_grass_world(pyboy, location):
    """與固定PyBoy碰撞來源一致的草地字塊；不推進幀或修改資料。"""
    grass = int(pyboy.memory[0xD535])
    if grass == 255:
        return []
    sprites = [pyboy.get_sprite(index) for index in range(4)]
    sx, sy = min(s.x for s in sprites), min(s.y for s in sprites)
    if sx % 16 or (sy + 4) % 16:
        return []
    tiles = pyboy.game_wrapper._get_screen_background_tilemap()[1::2, ::2]
    walkable = pyboy.game_wrapper.game_area_collision()[::2, ::2]
    ox, oy = location["x"] - sx // 16, location["y"] - (sy + 4) // 16
    return [(x + ox, y + oy) for y, row in enumerate(tiles) for x, tile in enumerate(row)
            if int(tile) % 256 == grass and walkable[y][x] == 1]
