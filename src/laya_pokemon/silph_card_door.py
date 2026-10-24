"""希魯夫3F/11F兩扇Card Key門的純候選，未接即時遊戲。
固定來源a536711；面門A，不使用袋中Card Key。只回Laya子目標。
reader只讀呼叫端memory；controller不讀ROM/RAM/存檔或推進遊戲。
"""
from copy import deepcopy
from collections.abc import Mapping
import math
import re

from .observation import PROFILE as TEXT_PROFILE
from .party_control import command
from .mart_purchase import _party, _inventory
from .team_strategy import reference, move_key

SOURCE_COMMIT = "a53671100ec22e5394ff26ec028d0812a238dae2"
PROFILE = "red-en-silph-card-door-source-v1-unvalidated"
THREE_F_INTENT = dict(kind="silph_card_door", map_id=208, player_x=18, player_y=8,
                      facing="left", door_x=17, door_y=8, event_id=0x709)
ELEVEN_F_INTENT = dict(kind="silph_card_door", map_id=235, player_x=6, player_y=14,
                       facing="up", door_x=6, door_y=13, event_id=0x788)
MAX_SECONDS, MAX_CALLS, MAX_WAITS = 60, 240, 120
MIN_DONE_STABLE_FRAMES = 16  # PrintLetterDelay用options低4bit，最後字可仍延遲至15幀。
EVENTS = {208: ("silph_co_3_unlocked_door2", 0x709, 0xD828, 1),
          235: ("silph_co_11_unlocked_door", 0x788, 0xD838, 0)}
# tileset, width/height(移動格), stance tile, closed/open door tile。
MAPS = {208: (22, 30, 18, 0x01, 0x24, 0x01),
        235: (16, 18, 18, 0x1F, 0x5E, 0x1F)}
GRID_SOURCE = "wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM"
SDK_ANCHORS = {"EVENT_FLAGS_ADDRESS": 0xD747, "OBTAINED_BADGES_ADDRESS": 0xD356}
SOURCES = [f"https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/{p}" for p in (
    "engine/events/card_key.asm", "scripts/SilphCo3F.asm", "scripts/SilphCo11F.asm",
    "scripts/SilphCo2F.asm", "data/text/text_1.asm", "home/predef_text.asm",
    "home/text_script.asm", "home/text.asm", "constants/event_constants.asm",
    "constants/map_constants.asm", "ram/wram.asm", "data/tilesets/collision_tile_ids.asm",
    "maps/SilphCo3F.blk", "maps/SilphCo11F.blk", "gfx/blocksets/facility.bst",
    "gfx/blocksets/interior.bst")]
FIRST = ("BINGO!", "THE CARD KEY")
FINAL = ("THE CARD KEY", "OPENED THE DOOR!")


def _int(value, low=0, high=255):
    return type(value) is int and low <= value <= high


def _intent(intent):
    return (isinstance(intent, dict) and any(
        intent == fixed and all(type(intent.get(k)) is type(v) for k, v in fixed.items())
        for fixed in (THREE_F_INTENT, ELEVEN_F_INTENT)))


def read_silph_card_door(pyboy, *, intent, observation_frame, expected_location, constants):
    """SDK錨+固定WRAM偏移，event與map/Y/X同幀雙讀；未知不當門已關/已開。
    不呼tick、load_state、get_screen或RAM setter。expected_location僅map_id/x/y。
    wObtainedBadges D356後：unused1+letter1+ID2+music2+palette1 -> CurMap D35E，
    接view pointer2 -> Y D361 / X D362；event base D747+ID//8，bit ID%8。
    """
    unknown = dict(profile=PROFILE, source_commit=SOURCE_COMMIT, read_valid=False,
                   unknown_reason="source_contract_unverified", live_calibrated=False)
    try:
        if (not _intent(intent) or not _int(observation_frame, 0, 0x7FFFFFFFFFFFFFFF)
                or type(getattr(pyboy, "frame_count", None)) is not int
                or pyboy.frame_count != observation_frame
                or not isinstance(expected_location, dict)
                or set(expected_location) != {"map_id", "x", "y"}
                or any(not _int(v) for v in expected_location.values())
                or expected_location != dict(map_id=intent["map_id"], x=intent["player_x"], y=intent["player_y"])
                or any(type(getattr(constants, k, None)) is not int or getattr(constants, k) != v
                       for k, v in SDK_ANCHORS.items())):
            return unknown
        flags, maps = getattr(constants, "EVENT_FLAGS", None), getattr(constants, "MAPS", None)
        if (not isinstance(flags, Mapping) or not isinstance(maps, Mapping)
                or any(type(flags.get(name)) is not int or flags[name] != eid
                       for name, eid, _, _ in EVENTS.values())
                or any(type(maps.get(name)) is not int or maps[name] != mid
                       for name, mid in (("silph_co_3f", 208), ("silph_co_11f", 235)))):
            return unknown
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, RuntimeError):
        return {**unknown, "unknown_reason": "source_contract_unreadable"}
    name, eid, address, bit = EVENTS[intent["map_id"]]
    addresses = (address, 0xD35E, 0xD361, 0xD362)
    try:
        before = tuple(pyboy.memory[a] for a in addresses)
        after = tuple(pyboy.memory[a] for a in addresses)
        last_frame = getattr(pyboy, "frame_count", None)
        if (any(not _int(v) for v in before + after) or before != after
                or type(last_frame) is not int or last_frame != observation_frame):
            return {**unknown, "unknown_reason": "read_torn_or_frame_changed"}
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, RuntimeError):
        return {**unknown, "unknown_reason": "memory_unreadable"}
    raw, mid, y, x = before
    loc = dict(map_id=mid, x=x, y=y)
    if loc != expected_location:
        return {**unknown, "unknown_reason": "map_or_location_disagrees"}
    return {**unknown, "read_valid": True, "unknown_reason": None,
            "observation_frame": observation_frame, "location": loc, "event_name": name,
            "event_id": eid, "address": address, "bit": bit, "raw_flags": raw,
            "unlocked": bool(raw & (1 << bit))}


def _rows(text):
    if (not isinstance(text, dict) or text.get("profile") != TEXT_PROFILE
            or text.get("read_valid") is not True or text.get("alignment_verified") is not True
            or text.get("read_error") is not None or type(text.get("window_visible")) is not bool):
        return None
    cells = text.get("cells")
    if (not isinstance(cells, (list, tuple)) or len(cells) != 18
            or any(not isinstance(r, (list, tuple)) or len(r) != 20 for r in cells)):
        return None
    if any(not isinstance(c, str) or len(c) != 1
           or c != " " and c not in "!.▼" and not (c.isascii() and c.isalnum())
           for r in cells for c in r):
        return None
    rows = tuple("".join(r).upper() for r in cells)
    pairs = [(i, "".join(r).rstrip()) for i, r in enumerate(cells)
             if re.search(r"[A-Za-z0-9]{2,}", "".join(r))][:12]
    if ("lines" in text and text["lines"] != [r for _, r in pairs]
            or "line_rows" in text and text["line_rows"] != [i for i, _ in pairs]):
        return None
    return rows


def _page(lines=(), arrow=False, *, scroll=False):
    rows = [[" "] * 20 for _ in range(18)]
    for y, value in zip((13, 15) if scroll else (14, 16), lines):
        rows[y][1:1 + len(value)] = value
    if arrow:
        rows[16][18] = "▼"
    return tuple("".join(row) for row in rows)


def _partial(rows, template):
    # 未知字不會被忽略；已知頁的部分字只能WAIT，永不確認。
    return all(a == " " or a == b for row, target in zip(rows, template)
               for a, b in zip(row, target))


def _fingerprint(p):
    party = _party(p)
    bag = _inventory(p.get("inventory")) if isinstance(p, dict) else None
    if party is None or bag is None or not _int(p.get("money"), 0, 999999):
        return None
    ref = reference()
    if ref.get("source_commit") != SOURCE_COMMIT:
        return None
    for mon in party:
        if mon["status"] not in (*range(8), 8, 16, 32, 64):
            return None
        for move, pp in zip(mon["moves"], mon["pp"]):
            name = move_key(move) if move else None
            if (not move and pp or move and (name is None
                    or (pp & 63) > min(63, int(ref["moves"][name]["pp"]) * (5 + (pp >> 6)) // 5))):
                return None
    if [i for i in bag if i["item"] == 48] != [{"item": 48, "quantity": 1}]:
        return None
    identity = {k: deepcopy(p[k]) for k in ("player_name_raw", "badges_raw", "party_count") if k in p}
    if ("badges_raw" in identity and not _int(identity["badges_raw"])
            or "player_name_raw" in identity and not isinstance(identity["player_name_raw"], str)):
        return None
    return deepcopy(dict(party=party, inventory=bag, money=p["money"], identity=identity))


def _grid(grid, intent, frame):
    if not isinstance(grid, dict):
        return None
    mid, x, y = intent["map_id"], intent["player_x"], intent["player_y"]
    tileset, width, height, stance, closed, opened = MAPS[mid]
    if (grid.get("source") != GRID_SOURCE or type(grid.get("observation_frame")) is not int
            or grid["observation_frame"] != frame or grid.get("verified_location") != [mid, x, y]
            or any(type(v) is not int for v in grid.get("verified_location", []))
            or type(grid.get("tileset_id")) is not int or grid["tileset_id"] != tileset):
        return None
    tiles, walk = grid.get("tiles"), grid.get("walkable")
    if any(not isinstance(a, (list, tuple)) or len(a) != height for a in (tiles, walk)):
        return None
    for matrix, high in ((tiles, 255), (walk, 1)):
        if any(not isinstance(r, (list, tuple)) or len(r) != width
               or any(not _int(v, 0, high) for v in r) for r in matrix):
            return None
    visible = grid.get("visible_verified_cells")
    if (not isinstance(visible, list) or type(grid.get("screen_cells_verified")) is not int
            or grid["screen_cells_verified"] != len(visible) or len(visible) < 12
            or any(not isinstance(v, list) or len(v) != 2
                   or not _int(v[0], 0, width - 1) or not _int(v[1], 0, height - 1) for v in visible)
            or len({tuple(v) for v in visible}) != len(visible)
            or [x, y] not in visible or [intent["door_x"], intent["door_y"]] not in visible
            or tiles[y][x] != stance or walk[y][x] != 1):
        return None
    dx, dy = intent["door_x"], intent["door_y"]
    value = tiles[dy][dx], walk[dy][dx]
    return "closed" if value == (closed, 0) else "open" if value == (opened, 1) else None


class SilphCardDoorController:
    """兩個明確意圖；首次closed/eventFalse→正常完整文字→open/eventTrue的回執。"""
    def __init__(self, intent):
        if not _intent(intent):
            raise ValueError("只允許固定3F第二門或11F門")
        self.intent = deepcopy(intent)
        self.stage, self.error, self.baseline = "initial", None, None
        self.started = self.last_now = self.last_packet = None
        self.last_frame = -1
        self.calls = self.waits = 0
        self.initial_flags = None
        self.prompt_ack = self.final_ack = False
        self.final_full_frame = None
        self.closed_frames = []
        self.event_seen = self.tile_seen = False

    def _fail(self, reason):
        self.error = "silph_card_door_" + reason.removeprefix("silph_card_door_")
        return dict(phase="campaign_review", objective="Wait.", available_actions=["wait"],
                    review_reason=self.error, silph_card_door_stage=self.stage,
                    source_commit=SOURCE_COMMIT)

    def _wait(self, reason):
        self.waits += 1
        if self.waits > MAX_WAITS:
            return self._fail("wait_budget_exhausted")
        return dict(phase="silph_card_door", objective="Wait.", available_actions=["wait"],
                    silph_card_door_tactic=reason, source_waits=self.waits)

    def _send(self, reason):
        return command("a", "silph_card_door", dict(
            silph_card_door_tactic=reason, source_commit=SOURCE_COMMIT, sources=SOURCES))

    def context(self, text, progress, *, location, battle_state, door_signal,
                world_grid, frame, now, overworld_ready=False):
        if self.error:
            return self._fail(self.error)
        self.calls += 1
        if (not _intent(self.intent) or not _int(frame, 0, 0x7FFFFFFFFFFFFFFF)
                or type(now) not in (int, float) or not math.isfinite(now) or now < 0
                or self.last_now is not None and now < self.last_now or frame < self.last_frame):
            return self._fail("intent_clock_or_frame_invalid")
        self.started = now if self.started is None else self.started
        self.last_now = now
        if self.calls > MAX_CALLS or now - self.started > MAX_SECONDS:
            return self._fail("transaction_budget_exhausted")
        i = self.intent
        loc = dict(map_id=i["map_id"], x=i["player_x"], y=i["player_y"])
        if (not isinstance(location, dict) or any(type(location.get(k)) is not int for k in loc)
                or any(location.get(k) != v for k, v in loc.items())
                or location.get("facing") != i["facing"]
                or type(location.get("facing_raw")) is not int
                or location["facing_raw"] != (8 if i["facing"] == "left" else 4)
                or type(overworld_ready) is not bool
                or not isinstance(battle_state, dict) or battle_state.get("kind") != "none"
                or battle_state.get("active") is not False or type(battle_state.get("raw")) is not int
                or battle_state["raw"] != 0):
            return self._fail("fixed_nonbattle_stance_unverified")
        for p in (text, progress, location, battle_state):
            if not isinstance(p, dict) or ("observation_frame" in p and
                    (type(p["observation_frame"]) is not int or p["observation_frame"] != frame)):
                return self._fail("observation_frame_disagrees")
        name, eid, address, bit = EVENTS[i["map_id"]]
        s = door_signal
        if (not isinstance(s, dict) or s.get("profile") != PROFILE or s.get("read_valid") is not True
                or s.get("source_commit") != SOURCE_COMMIT or s.get("unknown_reason") is not None
                or type(s.get("observation_frame")) is not int or s["observation_frame"] != frame
                or s.get("location") != loc or any(type(v) is not int for v in s.get("location", {}).values())
                or s.get("event_name") != name or not _int(s.get("event_id"), 0, 0xFFFF) or s["event_id"] != eid
                or not _int(s.get("address"), 0, 0xFFFF) or s["address"] != address
                or not _int(s.get("bit"), 0, 7) or s["bit"] != bit
                or not _int(s.get("raw_flags")) or type(s.get("unlocked")) is not bool
                or s["unlocked"] != bool(s["raw_flags"] & (1 << bit))):
            return self._fail("door_event_signal_unverified")
        fp = _fingerprint(progress)
        if fp is None:
            return self._fail("full_party_bag_key_money_unverified")
        if self.baseline is not None and fp != self.baseline:
            return self._fail("original_fingerprint_changed")
        rows = _rows(text)
        if rows is None:
            self.final_full_frame = None
            return self._fail("full_native_decoder_unverified")
        grid_state = _grid(world_grid, i, frame) if world_grid is not None else None
        if world_grid is not None and grid_state is None:
            return self._fail("provided_grid_unverified_or_wrong_door_tile")
        packet = deepcopy((text, progress, location, battle_state, door_signal, world_grid, overworld_ready))
        if frame == self.last_frame:
            if packet != self.last_packet:
                return self._fail("same_frame_packet_conflict")
            return self._wait("same_observation_no_resend")
        self.last_frame, self.last_packet = frame, packet
        blank = rows == _page()
        if self.stage == "initial":
            if (not blank or text["window_visible"] or not overworld_ready
                    or grid_state != "closed" or s["unlocked"]):
                return self._fail("new_closed_door_baseline_required")
            self.baseline, self.initial_flags = fp, s["raw_flags"]
            self.stage = "first_prompt"
            return self._send("face_door_interact_once")
        if s["raw_flags"] not in (self.initial_flags, self.initial_flags | (1 << bit)):
            return self._fail("unrelated_event_bits_changed")
        if not self.final_ack and (s["unlocked"] or grid_state == "open"):
            return self._fail("opened_before_own_complete_dialogue")
        if self.event_seen and not s["unlocked"] or self.tile_seen and grid_state == "closed":
            return self._fail("opened_event_or_tile_reverted")
        if s["unlocked"]:
            self.event_seen = True
        if grid_state == "open":
            self.tile_seen = True
        if self.stage in ("closing", "complete") and blank and text["window_visible"] is False and overworld_ready:
            if grid_state is None:
                self.closed_frames.clear()
                return self._wait("await_verified_visible_door_grid")
            if not s["unlocked"] or grid_state != "open":
                self.closed_frames.clear()
                return self._wait("await_normal_tile_and_map_callback_event")
            self.closed_frames.append(frame)
            if len(self.closed_frames) < 2:
                return self._wait("first_closed_world_receipt")
            self.stage = "complete"
            return dict(phase="silph_card_door_complete", objective="Wait.", available_actions=["wait"],
                        silph_card_door_complete=True, map_id=i["map_id"], event_id=eid,
                        door=[i["door_x"], i["door_y"]], opened_tile=MAPS[i["map_id"]][5],
                        first_closed_frame=self.closed_frames[0], closed_observation_frame=frame,
                        card_key_consumed=False, source_commit=SOURCE_COMMIT, sources=SOURCES)
        self.closed_frames.clear()
        first = (_page(FIRST), _page(FIRST, True))
        if blank:
            self.final_full_frame = None
            return self._wait("native_blank_no_resend")
        if overworld_ready or text["window_visible"] is not True:
            return self._fail("dialogue_world_or_window_conflict")
        if rows in first:
            self.final_full_frame = None
            if self.stage != "first_prompt" or self.prompt_ack:
                return self._wait("old_prompt_no_resend")
            if rows != first[1]:
                return self._wait("await_real_cont_prompt")
            self.prompt_ack, self.stage = True, "final_text"
            return self._send("advance_card_key_cont_once")
        final = _page(FINAL)
        if rows == final:
            if not self.prompt_ack:
                return self._fail("final_without_own_cont_confirmation")
            if self.final_ack:
                return self._wait("outer_close_pending_no_resend")
            if self.final_full_frame is None:
                self.final_full_frame = frame
                return self._wait("full_done_text_stability_before_outer_wait")
            if frame - self.final_full_frame < MIN_DONE_STABLE_FRAMES:
                return self._wait("await_sixteen_source_done_stable_frames")
            self.final_ack, self.stage = True, "closing"
            return self._send("close_complete_opened_door_done_once")
        self.final_full_frame = None
        allowed = list(first) if self.stage == "first_prompt" else []
        if self.prompt_ack:
            allowed += list(first) + [_page(FIRST, scroll=True), final]
        if any(_partial(rows, page) for page in allowed):
            return self._wait("exact_source_partial_or_scroll_no_input")
        return self._fail("unknown_or_polluted_card_key_page")

