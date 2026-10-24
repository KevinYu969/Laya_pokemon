"""固定 Route16→Pallet 原生 Fly 候選；getter與純子目標，不操作遊戲。

pret/pokered a536711；來源收據 fly-pallet-source-contract-20261024。
目前 Fly 選項是 CPU HL，絕不把普通 TownMap scratch byte 當 selector。
"""
from copy import deepcopy
from collections.abc import Mapping
import math

from .hm_teaching import _rows, _inventory, PROGRESS_PROFILE
from .observation import _source_at
from .team_strategy import reference, species_key, move_key

SOURCE_COMMIT = "a53671100ec22e5394ff26ec028d0812a238dae2"
PROFILE = "red-en-fly-pallet-source-v1"
FLY_PALLET_INTENT = dict(kind="fly_pallet", species=35, move=19, map_id=27,
                         player_x=7, player_y=6, destination_map=0, landing_x=5, landing_y=6)
START = dict(map_id=27, x=7, y=6)
LANDING = dict(map_id=0, x=5, y=6)
MAX_SECONDS, MAX_CALLS, MAX_WAITS = 60, 240, 30
_ADDRESSES = dict(map_id=0xD35E, y=0xD361, x=0xD362,
                  visited_low=0xD70B, visited_high=0xD70C, destination=0xD71A,
                  flags6=0xD732, flags7=0xD733, walk_mode=0xD700,
                  joy_ignore=0xCD6B, walk_counter=0xCFC5, simulated=0xCD38, lcdc=0xFF40)
# 固定公開 gfx/town_map/town_map.rle，blob f9ede0ec78bf5e198a7fed8b1d1394e9837abaa8。
_RLE = bytes.fromhex(
    "7f756c7381446c7164814262516471c173517462416271615173647163c161b14162c161c167716371b1426271617161735172517351436271617161716571637143627161716171b1a16371637143627251617143a1617163714361b1a16171617161436151749142b14261716171b143a16471b142436151b1f14561744343a17141f142916371624444f141d1e172517361b1444391718142a16171b14843615171e1c1e2d1494f4500")
_BASE_MAP = []
for _b in _RLE:
    if not _b:
        break
    _BASE_MAP.extend([0x60 + (_b >> 4)] * (_b & 15))
assert len(_BASE_MAP) == 360
PALLET_RAW = list(_BASE_MAP)
PALLET_RAW[:2] = [0x93, 0xAE]
PALLET_RAW[3:18] = [0x7F] * 15
for _i, _c in enumerate("PALLET TOWN"):
    PALLET_RAW[3 + _i] = 0x7F if _c == " " else 0x80 + ord(_c) - 65
PALLET_RAW[18:20] = [0xED, 0xEE]
PALLET_RAW = tuple(PALLET_RAW)
_MAP_ROWS = ("TO PALLET TOWN    ▶▼",) + (" " * 20,) * 17


def _int(value, lo=0, hi=255):
    return type(value) is int and lo <= value <= hi


def _get(obj, key):
    return obj.get(key) if isinstance(obj, Mapping) else getattr(obj, key, None)


def _anchors(constants):
    anchors = {"STATUS_FLAGS3_ADDRESS": 0xD72D, "EVENT_FLAGS_ADDRESS": 0xD747,
               "OBTAINED_BADGES_ADDRESS": 0xD356, "PARTY_COUNT_ADDRESS": 0xD163}
    if any(type(_get(constants, k)) is not int or _get(constants, k) != v
           for k, v in anchors.items()):
        return False
    maps, badges = _get(constants, "MAPS"), _get(constants, "BADGES")
    return (isinstance(maps, Mapping) and isinstance(badges, Mapping)
            and type(maps.get("pallet_town")) is int and maps["pallet_town"] == 0
            and type(maps.get("route_16")) is int and maps["route_16"] == 27
            and type(badges.get("thunder")) is int and badges["thunder"] == 2)


def _invalid(frame, reason):
    return dict(profile=PROFILE, source_commit=SOURCE_COMMIT, observation_frame=frame,
                read_valid=False, ram_read_valid=False, screen_read_valid=False,
                read_error=reason, location=None, visited=None, destination=None,
                flags6=None, flags7=None, walk_mode=None, joy_ignore=None,
                walk_counter=None, simulated=None, lcdc=None, raw_identifiers=None,
                raw_bytes=None, signed_tile_data=None, window_visible=None)


def _screen_once(pyboy, lcdc):
    if not lcdc & 0x80 or not lcdc & 1:
        return None, None, None, "native_lcd_disabled"
    if lcdc & 0x10:
        return None, None, None, "unsigned_tile_domain_unsupported"
    positions = pyboy.screen.tilemap_position_list
    if (not isinstance(positions, (list, tuple)) or len(positions) < 144
            or any(not isinstance(p, (list, tuple)) or len(p) != 4
                   or any(type(v) is not int for v in p)
                   or not (0 <= p[0] <= 255 and 0 <= p[1] <= 255
                           and -7 <= p[2] <= 248 and 0 <= p[3] <= 255)
                   for p in positions[:144])):
        return None, None, None, "scanlines_invalid"
    positions = tuple(tuple(p) for p in positions[:144])
    window_enabled = bool(lcdc & 0x20)
    window_visible = window_enabled and any(y >= wy and wx < 160 and wy < 144
                                           for y, (_, _, wx, wy) in enumerate(positions))
    ids = []
    for row in range(18):
        for col in range(20):
            x, y = col * 8, row * 8
            layer, sx, sy = _source_at(x, y, positions[y], window_enabled)
            if (sx % 8 or sy % 8 or any(
                    _source_at(x, y + dy, positions[y + dy], window_enabled) != (layer, sx, sy + dy)
                    or _source_at(x + 7, y + dy, positions[y + dy], window_enabled) != (layer, sx + 7, sy + dy)
                    for dy in range(8))):
                return None, positions, window_visible, "native_visible_alignment_incomplete"
            tilemap = pyboy.tilemap_window if layer == "window" else pyboy.tilemap_background
            identifier = tilemap[sx // 8, sy // 8]
            if not _int(identifier, 128, 383):
                return None, positions, window_visible, "signed_tile_identifier_invalid"
            ids.append(identifier)
    return tuple(ids), positions, window_visible, None


def read_fly_observation(pyboy, observation_frame, constants):
    """同frame兩遍唯讀完整畫面與來源RAM；未知不填0／False。"""
    if not _int(observation_frame, 0, 2**63 - 1):
        return _invalid(None, "frame_invalid")
    try:
        if not _anchors(constants):
            return _invalid(observation_frame, "sdk_source_anchors_unverified")
    except Exception:
        return _invalid(observation_frame, "sdk_source_anchor_getter_failed")
    try:
        before = pyboy.frame_count
        if type(before) is not int or before != observation_frame:
            return _invalid(observation_frame, "frame_not_current")
        samples = []
        for _ in range(2):
            ram = {key: pyboy.memory[address] for key, address in _ADDRESSES.items()}
            if any(not _int(v) for v in ram.values()):
                return _invalid(observation_frame, "byte_invalid")
            screen = _screen_once(pyboy, ram["lcdc"])
            samples.append((ram, screen))
        after = pyboy.frame_count
    except Exception:
        return _invalid(observation_frame, "getter_failed")
    if type(after) is not int or after != before or samples[0] != samples[1]:
        return _invalid(observation_frame, "torn_frame_or_snapshot")
    ram, (ids, _, window, error) = samples[0]
    return dict(profile=PROFILE, source_commit=SOURCE_COMMIT, observation_frame=before,
                read_valid=error is None, ram_read_valid=True, screen_read_valid=error is None,
                read_error=error, location={k: ram[k] for k in ("map_id", "x", "y")},
                visited=[ram["visited_low"], ram["visited_high"]],
                **{k: ram[k] for k in ("destination", "flags6", "flags7", "walk_mode",
                                       "joy_ignore", "walk_counter", "simulated", "lcdc")},
                raw_identifiers=list(ids) if ids is not None else None,
                raw_bytes=[i if i < 256 else i - 256 for i in ids] if ids is not None else None,
                signed_tile_data=not bool(ram["lcdc"] & 0x10), window_visible=window)


def _blank():
    return [[" "] * 20 for _ in range(18)]


def _put(rows, x, y, value):
    rows[y][x:x + len(value)] = list(value.upper())


def _serial(rows):
    return tuple("".join(r) for r in rows)


def _screen_proof(signal):
    raw, ids = signal.get("raw_bytes"), signal.get("raw_identifiers")
    return (signal.get("read_valid") is True and signal.get("screen_read_valid") is True
            and signal.get("read_error") is None and signal.get("signed_tile_data") is True
            and type(signal.get("window_visible")) is bool
            and signal["lcdc"] & 0x91 == 0x81
            and isinstance(raw,list) and len(raw) == 360 and all(_int(b) for b in raw)
            and isinstance(ids,list) and len(ids) == 360
            and all(_int(i,128,383) and ((b^128)-128)+256 == i for b,i in zip(raw,ids)))


class FlyPalletController:
    """固定意圖、同一實例；熱載入不得重建原基線、pending與預算。"""

    def __init__(self, intent=FLY_PALLET_INTENT):
        if (type(intent) is not dict or intent != FLY_PALLET_INTENT
                or any(type(v) is not int for k, v in intent.items() if k != "kind")):
            raise ValueError("僅允許Route16(7,6)大嘴雀原生Fly至Pallet(5,6)")
        self.intent = deepcopy(intent)
        self.contract = deepcopy(intent)
        self.stage, self.error = "initial", None
        self.started = self.last_now = None
        self.last_frame, self.last_packet = -1, None
        self.baseline = self.pending = self.expected = None
        self.target_index = None
        self.calls = self.waits = 0
        self.selected_user = False
        self.destination_frame = self.closed_frame = None
        self.destination_confirmed = False

    def _hint(self, action, tactic, complete=False):
        objectives = dict(wait="Wait.", start="Press START.", a="Press A.",
                          up="Move UP.", down="Move DOWN.")
        return dict(phase="fly_pallet_complete" if complete else "fly_pallet_menu",
                    objective=objectives[action], available_actions=["wait"] if action == "wait" else [action, "wait"],
                    fly_pallet_tactic=tactic, fly_pallet_stage=self.stage,
                    fly_pallet_complete=complete, source_commit=SOURCE_COMMIT,
                    controller_menu_verified=action != "wait")

    def _fail(self, reason):
        self.error = self.error or "fly_pallet_" + reason
        return {**self._hint("wait", "review"), "phase": "campaign_review", "review_reason": self.error}

    def _wait(self, reason):
        self.waits += 1
        return self._fail("wait_budget_exhausted") if self.waits > MAX_WAITS else self._hint("wait", reason)

    def _offer(self, action, stage, view, expected=None):
        self.pending = dict(action=action, stage=stage, frame=self.last_frame,
                            view=deepcopy(view), executed=False, expected=expected)
        return self._hint(action, "offer_" + stage)

    def _progress(self, p):
        if (not isinstance(p, dict) or p.get("profile") != PROGRESS_PROFILE
                or p.get("party_read_valid") is not True or p.get("initialization_candidate") is not True
                or type(p.get("party_count")) is not int or p["party_count"] != 6
                or not isinstance(p.get("party"), list) or len(p["party"]) != 6
                or not _int(p.get("badges_raw")) or not p["badges_raw"] & 4
                or p.get("player_name_raw") != "KEVIN"):
            return None
        party, inv = p["party"], _inventory(p.get("inventory"))
        if (inv is None or len(inv) != 19 or (197, 1) not in inv
                or type(p.get("money")) is not int or p["money"] != 55372
                or any(not isinstance(m,dict) or type(m.get("species")) is not int for m in party)
                or {m.get("species") for m in party if isinstance(m, dict)} != {7,132,102,154,35,19}):
            return None
        ref = reference()
        if ref.get("source_commit") != SOURCE_COMMIT:
            return None
        for mon in party:
            if (not isinstance(mon, dict) or type(mon.get("species")) is not int
                    or species_key(mon["species"]) != mon.get("species_name")
                    or not _int(mon.get("level"), 1, 100) or not _int(mon.get("exp"), 0, 0xFFFFFF)
                    or not _int(mon.get("max_hp"), 1, 999) or not _int(mon.get("hp"), 1, mon["max_hp"])
                    or type(mon.get("status")) is not int or mon["status"] != 0
                    or any(not isinstance(mon.get(k), list) or len(mon[k]) != 4
                           or any(not _int(v, 0, high) for v in mon[k]) for k, high in (("moves",165),("pp",255)))):
                return None
            for move, pp in zip(mon["moves"], mon["pp"]):
                key = move_key(move) if move else None
                if (not move and pp or move and (key not in ref["moves"]
                        or (pp & 63) > ref["moves"][key]["pp"] * (5 + (pp >> 6)) // 5)):
                    return None
        target = next(i for i, m in enumerate(party) if m["species"] == 35)
        if (party[target]["moves"] != [64,65,19,31]
                or [i for i, m in enumerate(party) if 19 in m["moves"]] != [target]):
            return None
        return dict(party=deepcopy(party), inventory=deepcopy(p["inventory"]), money=p["money"],
                    badges_raw=p["badges_raw"], player_name_raw=p["player_name_raw"])

    def _start(self, cursor, marker="▶"):
        r = _blank()
        for y, name in ((2,"POKÉDEX"),(4,"POKÉMON"),(6,"ITEM"),(8,"KEVIN"),
                        (10,"SAVE"),(12,"OPTION"),(14,"EXIT")):
            _put(r,12,y,name)
        _put(r,11,cursor,marker)
        return _serial(r)

    def _party(self, index, marker="▶"):
        r = _blank()
        for i, mon in enumerate(self.baseline["party"]):
            _put(r,3,2*i,mon["species_name"])
            _put(r,13,2*i,f'{mon["level"]:3}')
            _put(r,13,2*i+1,f'{mon["hp"]:3}/{mon["max_hp"]:3}')
        _put(r,0,2*index+1,marker)
        _put(r,1,14,"Choose a POKéMON.")
        return _serial(r)

    def _field(self, y, marker="▶"):
        r = [list(row) for row in self._party(self.target_index,"▷")]
        for row in range(8,18):
            r[row][11:20] = [" "]*9
        for row, name in ((10,"FLY"),(12,"STATS"),(14,"SWITCH"),(16,"CANCEL")):
            _put(r,13,row,name)
        _put(r,12,y,marker)
        return _serial(r)

    @staticmethod
    def _world(grid, loc, frame):
        if (not isinstance(grid, dict) or grid.get("tileset_id") != 0
                or not _int(grid.get("screen_cells_verified"), 12, 360)
                or type(grid.get("observation_frame")) is not int or grid["observation_frame"] != frame
                or grid.get("verified_location") != [loc["map_id"],loc["x"],loc["y"]]):
            return False
        try:
            tile, walk = grid["tiles"][loc["y"]][loc["x"]], grid["walkable"][loc["y"]][loc["x"]]
        except (KeyError, IndexError, TypeError):
            return False
        return type(tile) is int and type(walk) is int and walk == 1 and (loc != LANDING or tile == 0x23)

    def context(self, text, progress, *, location, battle_state, grid, signal,
                frame, previous, now, overworld_ready=False):
        if self.error:
            return self._fail(self.error.removeprefix("fly_pallet_"))
        self.calls += 1
        if (self.intent != self.contract or not _int(frame,0,2**63-1)
                or frame < self.last_frame or type(now) not in (int,float) or not math.isfinite(now)
                or now < 0 or self.last_now is not None and now < self.last_now):
            return self._fail("owner_frame_or_clock_invalid")
        if self.started is None:
            self.started = now
        if self.calls > MAX_CALLS or now - self.started > MAX_SECONDS:
            return self._fail("budget_exhausted")
        self.last_now = now
        if (type(previous) not in (list,tuple) or any(type(a) is not str or a not in
                ("a","b","up","down","left","right","start","wait") for a in previous)
                or type(overworld_ready) is not bool or not isinstance(location,dict)
                or any(not _int(location.get(k)) for k in ("map_id","x","y"))):
            return self._fail("location_or_actual_previous_invalid")
        loc = {k:location[k] for k in ("map_id","x","y")}
        if (not isinstance(battle_state,dict) or battle_state.get("kind") != "none"
                or battle_state.get("active") is not False or type(battle_state.get("raw")) is not int
                or battle_state["raw"] != 0 or type(battle_state.get("observation_frame")) is not int
                or battle_state["observation_frame"] != frame):
            return self._fail("battle_not_verified_none")
        for item in (text, progress, location):
            if isinstance(item,dict) and "observation_frame" in item and (
                    type(item["observation_frame"]) is not int or item["observation_frame"] != frame):
                return self._fail("observation_frame_conflict")
        if (not isinstance(signal,dict) or signal.get("profile") != PROFILE
                or signal.get("source_commit") != SOURCE_COMMIT or signal.get("ram_read_valid") is not True
                or type(signal.get("observation_frame")) is not int or signal["observation_frame"] != frame
                or signal.get("location") != loc
                or any(not _int(signal.get(k)) for k in ("destination","flags6","flags7","walk_mode",
                                                         "joy_ignore","walk_counter","simulated","lcdc"))
                or type(signal.get("visited")) is not list or len(signal["visited"]) != 2
                or any(not _int(v) for v in signal["visited"]) or not signal["visited"][0] & 1
                or signal["flags6"] & 0xD2 or signal["flags7"] & 0x68):
            return self._fail("fly_source_signal_unverified")
        current = self._progress(progress)
        if current is None or self.baseline is not None and current != self.baseline:
            return self._fail("party_bag_money_or_pp_changed")
        rows = _rows(text)
        if (rows is not None and signal.get("screen_read_valid") is True
                and text.get("window_visible") is not signal.get("window_visible")):
            return self._fail("text_screen_layer_conflict")
        view = deepcopy((rows,signal.get("raw_bytes")))
        packet = deepcopy((text,progress,loc,battle_state,grid,signal,previous,overworld_ready))
        if frame == self.last_frame:
            return self._fail("same_frame_conflict") if packet != self.last_packet else self._wait("same_frame_no_resend")
        self.last_frame, self.last_packet = frame, packet
        if self.baseline is None:
            if (loc != START or rows != (" "*20,)*18 or not overworld_ready
                    or text.get("window_visible") is not False or not _screen_proof(signal)
                    or signal.get("read_error") is not None or not self._world(grid,loc,frame)
                    or signal["joy_ignore"] or signal["walk_counter"] or signal["simulated"]
                    or signal["flags6"] & 12 or signal["flags7"] & 128 or signal["walk_mode"] != 0):
                return self._fail("initial_closed_route16_unverified")
            if any(m["hp"] != m["max_hp"] for m in current["party"]):
                return self._fail("initial_full_health_required")
            self.baseline = current
            self.target_index = next(i for i,m in enumerate(current["party"]) if m["species"] == 35)
            return self._offer("start","start",view)
        if self.pending:
            p = self.pending
            if not p["executed"]:
                if frame > p["frame"] and previous and previous[-1] == p["action"]:
                    p["executed"] = True
                    self.stage, self.expected = p["stage"], p["expected"]
                    if self.stage == "flying":
                        self.destination_confirmed = True
                elif view == p["view"]:
                    return self._wait("await_actual_previous_action")
                else:
                    return self._fail("changed_page_without_actual_previous")
            if view == p["view"]:
                return self._wait("await_actual_action_effect")
        if self.stage in ("flying","complete"):
            if not self.destination_confirmed or signal["destination"] != 0 or loc["map_id"] not in (27,0):
                return self._fail("unverified_fly_handoff_or_destination")
            closed = (loc == LANDING and rows == (" "*20,)*18 and overworld_ready
                      and text.get("window_visible") is False and _screen_proof(signal)
                      and signal.get("read_error") is None and self._world(grid,loc,frame)
                      and signal["joy_ignore"] == signal["walk_counter"] == signal["simulated"] == 0
                      and signal["walk_mode"] == 0 and not signal["flags6"] & 12
                      and not signal["flags7"] & 128)
            if closed:
                if self.closed_frame is None:
                    self.closed_frame = frame
                    return self._wait("first_closed_pallet_frame")
                if frame > self.closed_frame:
                    self.stage = "complete"
                    return self._hint("wait","verified_pallet_landing",True)
            else:
                self.closed_frame = None
            if self.stage == "complete":
                return self._fail("completed_landing_changed")
            if signal.get("read_error") not in (None,"native_lcd_disabled","native_visible_alignment_incomplete"):
                return self._fail("unknown_native_screen_failure")
            return self._wait("native_fly_animation_only")
        if loc != START:
            return self._fail("location_changed_before_destination_confirmation")
        if not _screen_proof(signal) or rows is None:
            return self._fail("native_menu_decoder_unverified")
        if self.stage == "start":
            for y in (2,4,6,8,10,12,14):
                if rows == self._start(y):
                    if self.expected is not None and self.expected != ("start",y):
                        return self._fail("start_cursor_not_one_observed_step")
                    self.expected = None
                    if y == 4:
                        return self._offer("a","party",view)
                    dy = 2 if y < 4 else -2
                    return self._offer("down" if dy > 0 else "up","start",view,("start",y+dy))
        elif self.stage == "party":
            if rows == self._start(4,"▷"):
                return self._wait("native_start_confirmation")
            for i in range(6):
                if rows == self._party(i):
                    if self.expected is not None and self.expected != ("party",i):
                        return self._fail("party_cursor_not_one_observed_step")
                    self.expected = None
                    if i == self.target_index:
                        self.selected_user = True
                        return self._offer("a","field",view)
                    di = 1 if i < self.target_index else -1
                    return self._offer("down" if di > 0 else "up","party",view,("party",i+di))
        elif self.stage == "field":
            if not self.selected_user:
                return self._fail("fly_user_not_confirmed")
            if rows == self._party(self.target_index,"▷"):
                return self._wait("native_party_confirmation")
            for y in (10,12,14,16):
                if rows == self._field(y):
                    if self.expected is not None and self.expected != ("field",y):
                        return self._fail("field_cursor_not_one_observed_step")
                    self.expected = None
                    if y == 10:
                        return self._offer("a","destination",view)
                    return self._offer("up","field",view,("field",y-2))
        elif self.stage == "destination":
            if rows == self._field(10,"▷"):
                return self._wait("native_fly_field_confirmation")
            raw = signal.get("raw_bytes")
            ids = signal.get("raw_identifiers")
            if (signal.get("signed_tile_data") is not True or signal["lcdc"] & 0x10
                    or not isinstance(raw,list) or len(raw) != 360
                    or any(not _int(x) for x in raw) or not isinstance(ids,list) or len(ids) != 360
                    or any(not _int(i,128,383) or ((b^128)-128)+256 != i for b,i in zip(raw,ids))):
                return self._fail("destination_raw_domain_unverified")
            # 原生TownMap可經可見Window呈現（實測LCDC E3）；畫面來源已由
            # _screen_proof及text_screen_layer_conflict逐格核對，不能以Window=True否決。
            if tuple(raw) == PALLET_RAW and rows == _MAP_ROWS:
                if self.destination_frame is None:
                    self.destination_frame = frame
                    return self._wait("first_full_pallet_destination_frame")
                if frame > self.destination_frame:
                    return self._offer("a","flying",view)
            else:
                self.destination_frame = None
                # Source名稱完整仍需Delay15後才畫ED/EE；僅接受已知箭頭未就緒。
                partial = list(PALLET_RAW)
                partial[18:20] = raw[18:20]
                if (raw == partial and raw[18] in (0x67,0x7F,0xED)
                        and raw[19] in (0x67,0x7F,0xEE) and tuple(raw) != PALLET_RAW):
                    return self._wait("await_native_destination_arrows")
                return self._fail("not_exact_initial_pallet_destination")
        return self._fail("unknown_or_polluted_native_page")
