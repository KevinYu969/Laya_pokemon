"""希魯夫7F固定五人隊領Lapras的純候選；未接bridge/live。
固定pret/pokered a536711。AskName前先增count/species、後寫mon資料，
故命名期間以同幀原五人raw前綴保護，不填補新隊員HP/EXP。
"""
from copy import deepcopy
import math
import re

from .observation import PROFILE as TEXT_PROFILE
from .party_control import command
from .mart_purchase import _party, _inventory
from .team_strategy import reference, move_key

SOURCE_COMMIT = "a53671100ec22e5394ff26ec028d0812a238dae2"
PROFILE = "red-en-silph-lapras-gift-source-v1-unvalidated"
INTENT = dict(kind="silph_lapras_gift", map_id=212, player_x=2, player_y=5,
              facing="left", species=19, level=15, decline_nickname=True)
INITIAL_SPECIES = {132, 7, 102, 154, 35}
MAX_SECONDS, MAX_CALLS, MAX_WAITS, MIN_DONE_STABLE_FRAMES = 60, 240, 120, 16
SDK_ANCHORS = dict(STATUS_FLAGS3_ADDRESS=0xD72D, OBTAINED_BADGES_ADDRESS=0xD356,
    PARTY_COUNT_ADDRESS=0xD163, PARTY_SPECIES_ADDRESS=0xD164, PARTY_MONS_ADDRESS=0xD16B,
    PARTY_MON_SIZE=44, PARTY_MON_OT_ADDRESS=0xD273, PARTY_MON_NICKNAME_ADDRESS=0xD2B5, PARTY_LENGTH=6)
SOURCES = [f"https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/{p}" for p in (
    "scripts/SilphCo7F.asm", "text/SilphCo7F.asm", "engine/events/give_pokemon.asm",
    "engine/pokemon/add_mon.asm", "engine/menus/naming_screen.asm", "home/window.asm",
    "engine/menus/text_box.asm", "data/yes_no_menu_strings.asm", "data/text/text_2.asm",
    "data/text/text_5.asm", "constants/charmap.asm", "ram/wram.asm", "macros/ram.asm",
    "constants/ram_constants.asm", "data/pokemon/base_stats/lapras.asm",
    "data/pokemon/evos_moves.asm", "home/move_mon.asm", "data/growth_rates.asm")]
# 一個原生tile保持一個內部字位；不把縮寫展成兩格。
LIGATURES = {"'r": "\ue010", "'s": "\ue011", "'l": "\ue012"}
INTRO = (
    ("Oh! Hi! You're", "not a ROCKET! You", "cont"),
    ("not a ROCKET! You", "came to save us?", "cont"),
    ("came to save us?", "Why, thank you!", "para"),
    ("I want you to", "have this POKéMON", "cont"),
    ("have this POKéMON", "for saving us.", "prompt"),
)
QUESTION = ("Do you want to", "give a nickname")
NICKNAME = ("give a nickname", "to LAPRAS?")
DESCRIPTION = (
    ("It's LAPRAS. It's", "very intelligent.", "para"),
    ("We kept it in our", "lab, but it will", "cont"),
    ("lab, but it will", "be much better", "cont"),
    ("be much better", "off with you!", "para"),
    ("I think you will", "be a good trainer", "cont"),
    ("be a good trainer", "for LAPRAS!", "para"),
    ("It's a good", "swimmer. It'll", "cont"),
    ("swimmer. It'll", "give you a lift!", "done"),
)


def _int(v, low=0, high=255):
    return type(v) is int and low <= v <= high


def _valid_intent(v):
    return isinstance(v, dict) and v == INTENT and all(type(v.get(k)) is type(x) for k, x in INTENT.items())


def read_lapras_gift(pyboy, *, observation_frame, expected_location, constants):
    """同幀雙讀source/SDK錨定的flags4、map/XY、count/list、party44與OT/nick11。
    原五人raw不是重建progress的資料；只證AddPartyMon命名期間舊前綴未被改動。
    """
    unknown = dict(profile=PROFILE, source_commit=SOURCE_COMMIT, read_valid=False,
                   unknown_reason="source_contract_unverified", live_calibrated=False)
    try:
        if (not _int(observation_frame, 0, 0x7FFFFFFFFFFFFFFF)
                or type(getattr(pyboy, "frame_count", None)) is not int
                or pyboy.frame_count != observation_frame
                or expected_location != dict(map_id=212, x=2, y=5)
                or not isinstance(expected_location, dict)
                or any(type(v) is not int for v in expected_location.values())
                or any(type(getattr(constants, k, None)) is not int or getattr(constants, k) != v
                       for k, v in SDK_ANCHORS.items())
                or not isinstance(getattr(constants, "MAPS", None), dict)
                or type(constants.MAPS.get("silph_co_7f")) is not int
                or constants.MAPS["silph_co_7f"] != 212):
            return unknown
        # flags4在SDK flags3下一byte；map/XY由SDK badges+8/+11/+12。
        addresses = (0xD72E, 0xD35E, 0xD361, 0xD362, 0xD163)
        addresses += tuple(range(0xD164, 0xD16B))
        addresses += tuple(range(0xD16B, 0xD273))
        addresses += tuple(range(0xD273, 0xD2B5))
        addresses += tuple(range(0xD2B5, 0xD2F7))
        first = tuple(pyboy.memory[a] for a in addresses)
        second = tuple(pyboy.memory[a] for a in addresses)
        end = getattr(pyboy, "frame_count", None)
        if (first != second or any(not _int(v) for v in first + second)
                or type(end) is not int or end != observation_frame):
            return {**unknown, "unknown_reason": "read_torn_or_frame_changed"}
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, RuntimeError):
        return {**unknown, "unknown_reason": "getter_unreadable"}
    flags, mid, y, x, count = first[:5]
    species, mons, ots, nicks = first[5:12], first[12:276], first[276:342], first[342:408]
    if ((mid, x, y) != (212, 2, 5) or count not in (5, 6)
            or len(set(species[:5])) != 5 or set(species[:5]) != INITIAL_SPECIES
            or species[count] != 255 or count == 6 and species[5] != 19):
        return {**unknown, "unknown_reason": "map_party_count_or_species_disagrees"}
    return {**unknown, "read_valid": True, "unknown_reason": None,
        "observation_frame": observation_frame, "location": dict(map_id=mid, x=x, y=y),
        "raw_flags": flags, "got_lapras": bool(flags & 1), "party_count": count,
        "party_species": list(species[:count]), "prefix_mons_raw": list(mons[:220]),
        "prefix_ot_raw": list(ots[:55]), "prefix_nicks_raw": list(nicks[:55]),
        "new_mon_raw": list(mons[220:]) if count == 6 else None,
        "new_ot_raw": list(ots[55:]) if count == 6 else None,
        "new_nickname_raw": list(nicks[55:]) if count == 6 else None}


def _encoded(s):
    for native, marker in LIGATURES.items():
        s = s.replace(native, marker)
    return s.upper()


def _rows(t):
    if (not isinstance(t, dict) or t.get("profile") != TEXT_PROFILE
            or t.get("read_valid") is not True or t.get("alignment_verified") is not True
            or t.get("read_error") is not None or type(t.get("window_visible")) is not bool):
        return None
    cells = t.get("cells")
    if (not isinstance(cells, (list, tuple)) or len(cells) != 18
            or any(not isinstance(r, (list, tuple)) or len(r) != 20 for r in cells)):
        return None
    rows = []
    for r in cells:
        line = []
        for c in r:
            if isinstance(c, str) and c in LIGATURES:
                line.append(LIGATURES[c])
            elif (isinstance(c, str) and len(c) == 1 and
                  (c == " " or c in "éÉ'.,!?▶▷▼" or c.isascii() and c.isalnum())):
                line.append(c.upper())
            else:
                return None
        rows.append("".join(line))
    pairs = [(y, "".join(r).rstrip()) for y, r in enumerate(cells)
             if re.search(r"[A-Za-z0-9]{2,}", "".join(r))][:12]
    if ("lines" in t and t["lines"] != [r for _, r in pairs]
            or "line_rows" in t and t["line_rows"] != [y for y, _ in pairs]):
        return None
    return tuple(rows)


def _screen(lines=(), *, arrow=False, scroll=False, cursor=None):
    r = [[" "] * 20 for _ in range(18)]
    for y, s in zip((13, 15) if scroll else (14, 16), lines):
        v = _encoded(s)
        r[y][1:1 + len(v)] = v
    if arrow:
        r[16][18] = "▼"
    if cursor is not None:
        r[8][16:19] = "YES"
        r[10][16:18] = "NO"
        r[cursor][15] = "▶"
    return tuple("".join(line) for line in r)


def _subset(rows, target):
    return all(a == " " or a == b for r, want in zip(rows, target) for a, b in zip(r, want))


def _raw_mon(raw):
    if not isinstance(raw, list) or len(raw) != 44 or any(not _int(v) for v in raw):
        return None
    return dict(species=raw[0], hp=raw[1] * 256 + raw[2], status=raw[4], moves=raw[8:12],
                exp=int.from_bytes(bytes(raw[14:17]), "big"), pp=raw[29:33],
                level=raw[33], max_hp=raw[34] * 256 + raw[35])


def _raw_name(raw):
    if not isinstance(raw, list) or len(raw) != 11 or any(not _int(v) for v in raw):
        return None
    if 0x50 not in raw:
        return None
    values = raw[:raw.index(0x50)]
    return "".join(chr(v - 0x80 + 65) for v in values) if all(0x80 <= v <= 0x99 for v in values) else None


def _matches(mon, raw):
    return raw is not None and all(mon.get(k) == v and type(mon.get(k)) is type(v) for k, v in raw.items())


def _new_lapras(progress, s):
    party = _party(progress)
    raw = s["new_mon_raw"]
    mon = _raw_mon(raw)
    if party is None or len(party) != 6 or mon is None or not _matches(party[5], mon):
        return None
    # 新贈送不沿用未初始化EV；source最終寫0，DV隨機，HP要按真DV精算。
    dv1, dv2 = raw[27:29]
    hp_dv = ((dv1 >> 4 & 1) << 3) | ((dv1 & 1) << 2) | ((dv2 >> 4 & 1) << 1) | (dv2 & 1)
    hp = (2 * (130 + hp_dv) * 15) // 100 + 25
    if (mon != dict(species=19, hp=hp, max_hp=hp, status=0, level=15, exp=4218,
                    moves=[55, 45, 0, 0], pp=[25, 40, 0, 0])
            or any(raw[17:27]) or raw[3] != 0
            or _raw_name(s["new_nickname_raw"]) != "LAPRAS" or _raw_name(s["new_ot_raw"]) != "KEVIN"):
        return None
    return deepcopy(dict(mon=party[5], raw=raw, nickname=s["new_nickname_raw"], ot=s["new_ot_raw"]))


class LaprasGiftController:
    """限定來源多頁、正常NO與一個第六隊員；未知不A，不接命名輸字畫面。"""
    def __init__(self, intent):
        if not _valid_intent(intent):
            raise ValueError("只允許Silph7F固定Lapras15正常NO禮物")
        self.intent = deepcopy(intent)
        self.stage, self.index, self.error, self.baseline = "initial", 0, None, None
        self.started = self.last_now = self.last_packet = None
        self.last_frame = -1
        self.calls = self.waits = 0
        self.accepted = []
        self.last_scroll = None
        self.receipt_seen = self.question_ack = self.down_pending = self.no_issued = False
        self.append_seen = self.flag_seen = False
        self.new_member = None
        self.done_start = None
        self.closed_frames = []

    def _fail(self, reason):
        self.error = "lapras_gift_" + reason.removeprefix("lapras_gift_")
        return dict(phase="campaign_review", objective="Wait.", available_actions=["wait"],
                    review_reason=self.error, lapras_gift_stage=self.stage, source_commit=SOURCE_COMMIT)

    def _wait(self, reason):
        self.waits += 1
        if self.waits > MAX_WAITS:
            return self._fail("wait_budget_exhausted")
        return dict(phase="lapras_gift", objective="Wait.", available_actions=["wait"],
                    lapras_gift_tactic=reason, source_waits=self.waits)

    def _send(self, action, reason):
        return command(action, "lapras_gift", dict(lapras_gift_tactic=reason,
                       source_commit=SOURCE_COMMIT, sources=SOURCES))

    def _signal(self, s, frame):
        if (not isinstance(s, dict) or s.get("profile") != PROFILE or s.get("read_valid") is not True
                or s.get("source_commit") != SOURCE_COMMIT or s.get("unknown_reason") is not None
                or type(s.get("observation_frame")) is not int or s["observation_frame"] != frame
                or s.get("location") != dict(map_id=212, x=2, y=5)
                or any(type(v) is not int for v in s["location"].values())
                or not _int(s.get("raw_flags")) or type(s.get("got_lapras")) is not bool
                or s["got_lapras"] != bool(s["raw_flags"] & 1)
                or not _int(s.get("party_count"), 5, 6)):
            return False
        count = s["party_count"]
        ids = s.get("party_species")
        if (not isinstance(ids, list) or len(ids) != count or any(not _int(v, 1, 190) for v in ids)
                or len(set(ids[:5])) != 5 or set(ids[:5]) != INITIAL_SPECIES
                or count == 6 and ids[5] != 19):
            return False
        for k, size in (("prefix_mons_raw", 220), ("prefix_ot_raw", 55), ("prefix_nicks_raw", 55)):
            if not isinstance(s.get(k), list) or len(s[k]) != size or any(not _int(v) for v in s[k]):
                return False
        for k, size in (("new_mon_raw", 44), ("new_ot_raw", 11), ("new_nickname_raw", 11)):
            if count == 5:
                if s.get(k) is not None:
                    return False
            elif not isinstance(s.get(k), list) or len(s[k]) != size or any(not _int(v) for v in s[k]):
                return False
        return True

    def _progress(self, p, s):
        bag = _inventory(p.get("inventory"))
        if (p.get("profile") != "gen1-wrapper-ram-progress-v1-unvalidated" or bag is None
                or not _int(p.get("money"), 0, 999999) or p.get("player_name_raw") != "KEVIN"
                or type(p.get("party_count")) is not int or p["party_count"] != s["party_count"]
                or not _int(p.get("badges_raw"))):
            return "progress_bag_money_or_identity_unverified"
        prefix = dict(mons=s["prefix_mons_raw"], ot=s["prefix_ot_raw"],
                      nicks=s["prefix_nicks_raw"], species=s["party_species"][:5])
        if self.baseline is None:
            party = _party(p)
            if (party is None or p.get("initialization_candidate") is not True
                    or len(party) != 5 or s["party_count"] != 5 or s["got_lapras"]
                    or {m["species"] for m in party} != INITIAL_SPECIES
                    or [m["species"] for m in party] != s["party_species"]
                    or any(not _matches(m, _raw_mon(s["prefix_mons_raw"][n*44:(n+1)*44]))
                           for n, m in enumerate(party))):
                return "initial_five_source_prefix_unverified"
            ref = reference()
            if ref.get("source_commit") != SOURCE_COMMIT:
                return "fixed_move_reference_unverified"
            for mon in party:
                if mon["status"] not in (*range(8), 8, 16, 32, 64):
                    return "initial_status_invalid"
                for move, pp in zip(mon["moves"], mon["pp"]):
                    name = move_key(move) if move else None
                    if (not move and pp or move and (name is None
                            or (pp & 63) > min(63, int(ref["moves"][name]["pp"]) * (5 + (pp >> 6)) // 5))):
                        return "initial_move_pp_invalid"
            self.baseline = deepcopy(dict(party=party, bag=bag, money=p["money"], prefix=prefix,
                                          flags=s["raw_flags"], badges=p["badges_raw"], name="KEVIN"))
        b = self.baseline
        if (prefix != b["prefix"] or bag != b["bag"] or p["money"] != b["money"]
                or p["badges_raw"] != b["badges"]):
            return "original_five_or_inventory_fingerprint_changed"
        if s["raw_flags"] not in (b["flags"], b["flags"] | 1) or self.flag_seen and not s["got_lapras"]:
            return "unrelated_flags_or_lapras_flag_reverted"
        if s["got_lapras"] and not (self.stage in ("closing", "complete")
                or self.stage == "description" and self.index == len(DESCRIPTION)-1):
            return "flag_before_source_last_description"
        if s["got_lapras"]:
            self.flag_seen = True
        if self.append_seen and s["party_count"] != 6:
            return "sixth_slot_reverted"
        if s["party_count"] == 6:
            if self.stage in ("initial", "intro"):
                return "append_before_own_gift_request"
            self.append_seen = True
        if p.get("party_read_valid") is True:
            current = p.get("party")
            if (p.get("initialization_candidate") is not True or not isinstance(current, list)
                    or current[:5] != b["party"] or len(current) != s["party_count"]):
                return "semantic_original_party_or_count_changed"
            if s["party_count"] == 5 and _party(p) is None:
                return "original_party_invalid"
        elif (p.get("party_read_valid") is not False or p.get("initialization_candidate") is not False
                or p.get("party") != [] or s["party_count"] != 6
                or self.stage not in ("gift", "nickname", "post_no")):
            return "unknown_party_not_source_askname_transition"
        if self.no_issued:
            new = _new_lapras(p, s)
            if p.get("party_read_valid") is True and new is None:
                return "complete_new_party_disagrees_with_source_lapras"
            if self.new_member is not None and new != self.new_member:
                return "new_lapras_changed_or_became_unknown"
            if new is not None:
                self.new_member = new
        return None

    def context(self, text, progress, *, location, battle_state, gift_signal,
                frame, now, overworld_ready=False):
        if self.error:
            return self._fail(self.error)
        self.calls += 1
        if (not _valid_intent(self.intent) or not _int(frame, 0, 0x7FFFFFFFFFFFFFFF)
                or frame < self.last_frame or type(now) not in (int, float)
                or not math.isfinite(now) or now < 0 or self.last_now is not None and now < self.last_now):
            return self._fail("intent_clock_or_frame_invalid")
        self.started = now if self.started is None else self.started
        self.last_now = now
        if self.calls > MAX_CALLS or now-self.started > MAX_SECONDS:
            return self._fail("transaction_budget_exhausted")
        if (not isinstance(progress, dict) or not isinstance(location, dict)
                or (location.get("map_id"), location.get("x"), location.get("y"), location.get("facing")) != (212,2,5,"left")
                or any(type(location.get(k)) is not int for k in ("map_id","x","y"))
                or type(location.get("facing_raw")) is not int or location["facing_raw"] != 8
                or type(overworld_ready) is not bool or not isinstance(battle_state, dict)
                or battle_state.get("kind") != "none" or battle_state.get("active") is not False
                or type(battle_state.get("raw")) is not int or battle_state["raw"] != 0):
            return self._fail("fixed_nonbattle_stance_required")
        for p in (text, progress, location, battle_state):
            if not isinstance(p, dict) or ("observation_frame" in p and
                    (type(p["observation_frame"]) is not int or p["observation_frame"] != frame)):
                return self._fail("packet_frame_disagrees")
        if not self._signal(gift_signal, frame):
            return self._fail("source_signal_unverified")
        rows = _rows(text)
        if rows is None:
            self.done_start = None
            return self._fail("full_native_decoder_required")
        if self.baseline is None and (rows != _screen() or text["window_visible"] or not overworld_ready):
            return self._fail("initial_canonical_closed_world_required")
        error = self._progress(progress, gift_signal)
        if error:
            return self._fail(error)
        packet = deepcopy((text,progress,location,battle_state,gift_signal,overworld_ready))
        if frame == self.last_frame:
            if packet != self.last_packet:
                return self._fail("same_frame_packet_conflict")
            return self._wait("same_observation_no_resend")
        self.last_frame, self.last_packet = frame, packet
        if self.stage == "initial":
            self.stage = "intro"
            return self._send("a", "talk_to_only_lapras_worker_once")
        blank = rows == _screen()
        if self.stage in ("closing","complete") and blank and text["window_visible"] is False and overworld_ready:
            if self.new_member is None or not gift_signal["got_lapras"] or not self.no_issued:
                return self._fail("closed_world_missing_real_lapras_receipt")
            self.closed_frames.append(frame)
            if len(self.closed_frames)<2:
                return self._wait("first_closed_lapras_world")
            self.stage = "complete"
            return dict(phase="lapras_gift_complete",objective="Wait.",available_actions=["wait"],
                lapras_gift_complete=True,species=19,level=15,party_slot=6,
                hp=self.new_member["mon"]["hp"],exp=self.new_member["mon"]["exp"],
                nickname="LAPRAS",first_closed_frame=self.closed_frames[0],
                closed_observation_frame=frame,source_commit=SOURCE_COMMIT,sources=SOURCES)
        self.closed_frames.clear()
        if blank:
            self.done_start = None
            return self._wait("source_blank_no_resend")
        if overworld_ready or text["window_visible"] is not True:
            return self._fail("dialogue_world_or_window_conflict")
        if self.stage == "intro":
            return self._dialogue(rows, INTRO, "gift")
        receipt = _screen(("KEVIN got","LAPRAS!"))
        if self.stage == "gift":
            if rows == receipt:
                self.receipt_seen=True
                return self._wait("automatic_got_lapras_receipt_no_a")
            if rows in (_screen(QUESTION),_screen(QUESTION,arrow=True)):
                if not self.receipt_seen or not self.append_seen:
                    return self._fail("nickname_without_own_receipt_and_slot6")
                if rows != _screen(QUESTION,arrow=True):
                    return self._wait("await_nickname_cont_true_prompt")
                self.question_ack=True
                self.accepted.append(_screen(QUESTION,arrow=True))
                self.last_scroll=_screen(QUESTION,scroll=True)
                self.stage="nickname"
                return self._send("a","advance_nickname_cont_once")
        elif self.stage == "nickname":
            for cursor in (8,10):
                if rows != _screen(NICKNAME,cursor=cursor):
                    continue
                if not self.question_ack or not self.receipt_seen or not self.append_seen:
                    return self._fail("nickname_menu_without_normal_source_flow")
                if cursor==8:
                    if self.down_pending:
                        return self._wait("nickname_direction_pending_no_resend")
                    self.down_pending=True
                    return self._send("down","select_only_no_nickname")
                if not self.down_pending:
                    return self._fail("no_cursor_without_own_down")
                self.no_issued=True
                self.stage="post_no"
                return self._send("a","confirm_complete_unique_no_once")
        elif self.stage == "post_no":
            if rows in (_screen(NICKNAME),_screen(NICKNAME,cursor=8),_screen(NICKNAME,cursor=10)):
                return self._wait("nickname_no_pending_no_resend")
            if _subset(rows,_screen(DESCRIPTION[0][:2],arrow=True)):
                if self.new_member is None:
                    return self._fail("source_description_without_initialized_lapras")
                self.stage,self.index="description",0
        if self.stage == "description":
            if self.new_member is None:
                return self._fail("description_before_valid_new_mon")
            return self._dialogue(rows,DESCRIPTION,"closing",gift_signal["got_lapras"],frame)
        if self.stage == "closing":
            if rows in (_screen(DESCRIPTION[-1][:2]),):
                return self._wait("final_outer_close_pending_no_resend")
        self.done_start=None
        allowed=list(self.accepted)
        if self.last_scroll is not None:
            allowed.append(self.last_scroll)
        if self.stage=="gift":
            allowed += [receipt,_screen(QUESTION,arrow=True)]
        elif self.stage=="nickname":
            allowed += [_screen(NICKNAME),_screen(NICKNAME,cursor=8),_screen(NICKNAME,cursor=10)]
        elif self.stage=="post_no":
            allowed += [_screen(NICKNAME),_screen(NICKNAME,cursor=8),_screen(NICKNAME,cursor=10),
                        _screen(DESCRIPTION[0][:2],arrow=True)]
        if any(_subset(rows,t) for t in allowed):
            return self._wait("known_source_partial_or_old_page_no_a")
        return self._fail("unknown_or_polluted_lapras_page")

    def _dialogue(self, rows, pages, next_stage, got=False, frame=None):
        a,b,kind=pages[self.index]
        full=_screen((a,b),arrow=kind!="done")
        no_arrow=_screen((a,b))
        if kind=="done" and rows==no_arrow:
            if not got:
                self.done_start=None
                return self._wait("await_true_got_lapras_flag_after_done")
            if self.done_start is None:
                self.done_start=frame
                return self._wait("start_final_sixteen_frame_stability")
            if frame-self.done_start<MIN_DONE_STABLE_FRAMES:
                return self._wait("await_final_sixteen_stable_frames")
            self.stage=next_stage
            return self._send("a","close_complete_source_lapras_description_once")
        self.done_start=None
        if rows==full and kind!="done":
            self.accepted.append(full)
            self.last_scroll=_screen((a,b),scroll=True) if kind=="cont" else None
            self.index+=1
            if self.index==len(pages):
                self.index=0
                self.stage=next_stage
            return self._send("a","advance_verified_source_"+kind)
        allowed=[full,no_arrow]+self.accepted
        if self.last_scroll is not None:
            allowed.append(self.last_scroll)
        if any(_subset(rows,t) for t in allowed):
            return self._wait("source_dialogue_partial_prompt_or_old_page")
        return self._fail("unexpected_source_dialogue_page")

