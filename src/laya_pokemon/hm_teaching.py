"""固定紅版 HM 教學意圖的純子目標候選；不操作模擬器或橋接。
固定 pret/pokered a53671100ec22e5394ff26ec028d0812a238dae2。
僅 NIDOKING7 HM03/SURF57 取代槽1 TACKLE33、SNORLAX132
HM04/STRENGTH70 取代槽0 HEADBUTT29；FEAROW的FLY及LAPRAS的SURF
也由固定資料契約限定。HM原量原序保留。
context只用呼叫端同次完整觀測；來源字頁白名單不等於實機校準。
"""
from copy import deepcopy
import math
import re

from .party_control import command
from .team_strategy import reference, species_key, move_key

SOURCE_COMMIT = "a53671100ec22e5394ff26ec028d0812a238dae2"
TEXT_PROFILE = "gen1-visible-tile-text-candidates-v1-unvalidated"
PROGRESS_PROFILE = "gen1-wrapper-ram-progress-v1-unvalidated"
MAX_SECONDS, MAX_CALLS, MAX_WAITS = 60, 240, 30
SURF_INTENT = dict(kind="teach_surf_nidoking", species=7, item=198,
                   move=57, replace_move=33, replace_index=1)
STRENGTH_INTENT = dict(kind="teach_strength_snorlax", species=132, item=199,
                       move=70, replace_move=29, replace_index=0)
FLY_INTENT = dict(kind="teach_fly_fearow", species=35, item=197,
                  move=19, replace_move=43, replace_index=2)
LAPRAS_SURF_INTENT = dict(kind="teach_surf_lapras", species=19, item=198,
                         move=57, replace_move=55, replace_index=0)
_CONTRACTS = {
    "teach_surf_nidoking": (SURF_INTENT, (61, 33, 30, 40), "NIDOKING", "SURF"),
    "teach_strength_snorlax": (STRENGTH_INTENT, (29, 133, 156, 34), "SNORLAX", "STRENGTH"),
    "teach_fly_fearow": (FLY_INTENT, (64, 65, 43, 31), "FEAROW", "FLY"),
    "teach_surf_lapras": (LAPRAS_SURF_INTENT, (55, 34, 47, 54), "LAPRAS", "SURF"),
}
SOURCES = [f"https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/{p}" for p in (
    "engine/items/item_effects.asm#L2154", "engine/pokemon/learn_move.asm",
    "engine/menus/party_menu.asm#L83", "engine/menus/start_sub_menus.asm#L331",
    "home/window.asm#L136", "home/pokemon.asm#L240", "data/text/text_4.asm#L84",
    "data/text/text_6.asm#L160", "data/text/text_2.asm#L1375",
    "data/items/names.asm", "data/pokemon/base_stats/nidoking.asm",
    "data/pokemon/base_stats/snorlax.asm")]
# 固定公開 data/items/names.asm，非SDK底線名稱猜回畫面字串。
_ITEM_NAMES = (
    "", "MASTER BALL", "ULTRA BALL", "GREAT BALL", "POKÉ BALL", "TOWN MAP",
    "BICYCLE", "?????", "SAFARI BALL", "POKÉDEX", "MOON STONE", "ANTIDOTE",
    "BURN HEAL", "ICE HEAL", "AWAKENING", "PARLYZ HEAL", "FULL RESTORE",
    "MAX POTION", "HYPER POTION", "SUPER POTION", "POTION", "BOULDERBADGE",
    "CASCADEBADGE", "THUNDERBADGE", "RAINBOWBADGE", "SOULBADGE", "MARSHBADGE",
    "VOLCANOBADGE", "EARTHBADGE", "ESCAPE ROPE", "REPEL", "OLD AMBER",
    "FIRE STONE", "THUNDERSTONE", "WATER STONE", "HP UP", "PROTEIN", "IRON",
    "CARBOS", "CALCIUM", "RARE CANDY", "DOME FOSSIL", "HELIX FOSSIL",
    "SECRET KEY", "?????", "BIKE VOUCHER", "X ACCURACY", "LEAF STONE",
    "CARD KEY", "NUGGET", "PP UP", "POKÉ DOLL", "FULL HEAL", "REVIVE",
    "MAX REVIVE", "GUARD SPEC.", "SUPER REPEL", "MAX REPEL", "DIRE HIT",
    "COIN", "FRESH WATER", "SODA POP", "LEMONADE", "S.S.TICKET", "GOLD TEETH",
    "X ATTACK", "X DEFEND", "X SPEED", "X SPECIAL", "COIN CASE", "OAK'S PARCEL",
    "ITEMFINDER", "SILPH SCOPE", "POKÉ FLUTE", "LIFT KEY", "EXP.ALL",
    "OLD ROD", "GOOD ROD", "SUPER ROD", "PP UP", "ETHER", "MAX ETHER",
    "ELIXER", "MAX ELIXER")
_KEY_ITEMS = {5, 6, 7, 8, 9, *range(21, 29), 31, 41, 42, 43, 44, 45, 48,
              63, 64, *range(69, 75), 76, 77, 78, *range(196, 201)}


def _int(v, low, high):
    return type(v) is int and low <= v <= high


def _label(item):
    if 196 <= item <= 200:
        return f"HM{item - 195:02}"
    if 201 <= item <= 250:
        return f"TM{item - 200:02}"
    return _ITEM_NAMES[item] if 0 < item < len(_ITEM_NAMES) else None


def _rows(text):
    if (not isinstance(text, dict) or text.get("profile") != TEXT_PROFILE
            or text.get("read_valid") is not True or text.get("alignment_verified") is not True
            or text.get("read_error") is not None or type(text.get("window_visible")) is not bool):
        return None
    cells = text.get("cells")
    if not isinstance(cells, (list, tuple)) or len(cells) != 18:
        return None
    rows, ligatures = [], []
    for y, row in enumerate(cells):
        if not isinstance(row, (list, tuple)) or len(row) != 20:
            return None
        chars = []
        for c in row:
            if y >= 12 and c in ("'t", "'l"):
                ligatures.append((len(chars), y, c))
                chars.append(c[-1].upper())
            elif isinstance(c, str) and len(c) == 1 and (
                    c == " " or c in "éÉ'():;[]#?!.▷▶▼♂¥×/,-♀"
                    or c.isascii() and c.isalnum()):
                chars.append(c.upper())
            else:
                return None
        rows.append("".join(chars))
    for x, y, c in ligatures:
        if (c == "'t" and (rows[y][max(0, x-3):x] != "CAN"
                           or x + 1 < 20 and rows[y][x+1] != " ")
                or c == "'l" and (x == 0 or rows[y][x-1] != "I"
                                  or x + 1 >= 20 or rows[y][x+1] != "L")):
            return None
    # lines由真正物理cell在native decoder正規化前產生，不讓它覆蓋cells。
    raw_rows = ["".join(row).rstrip() for row in cells]
    pairs = [(y, r) for y, r in enumerate(raw_rows) if re.search(r"[A-Za-z0-9]{2,}", r)][:12]
    if ("lines" in text and text["lines"] != [r for _, r in pairs]
            or "line_rows" in text and text["line_rows"] != [y for y, _ in pairs]):
        return None
    return tuple(rows)


def _blank():
    return [[" "] * 20 for _ in range(18)]


def _put(rows, x, y, text):
    value = text.replace("'t", "t").replace("'l", "l").upper()
    if not 0 <= x <= 20 - len(value):
        raise ValueError("fixed source text exceeds row")
    rows[y][x:x + len(value)] = list(value)


def _clear(rows, x1, y1, x2, y2):
    for y in range(y1, y2 + 1):
        rows[y][x1:x2 + 1] = [" "] * (x2 - x1 + 1)


def _serial(rows):
    return tuple("".join(row) for row in rows)


def _subset(actual, expected):
    return all(a == " " or a == e for ra, rexp in zip(actual, expected)
               for a, e in zip(ra, rexp))


def _inventory(items):
    if (not isinstance(items, list) or not 1 <= len(items) <= 20
            or any(not isinstance(x, dict) or set(x) != {"item", "quantity"}
                   or not _int(x["item"], 1, 250) or _label(x["item"]) is None
                   or not _int(x["quantity"], 1, 99) for x in items)):
        return None
    pairs = [(x["item"], x["quantity"]) for x in items]
    return pairs if len({item for item, _ in pairs}) == len(pairs) else None


class HMTeachingController:
    """單一意圖／單一實例；frame、now及location來自同次上游觀測。

    未改暱稱的完整健康隊伍，首幀須canonical空白野外。只回正常按鍵
    子目標；60秒／240calls／總30WAIT。沒有bridge、RAM或任何模型呼叫。
    公開reference()是既有封裝靜態資料的唯讀查詢，不讀遊戲資料。
    """

    def __init__(self, intent):
        if (not isinstance(intent, dict) or intent.get("kind") not in _CONTRACTS
                or intent != _CONTRACTS[intent["kind"]][0]
                or any(type(intent.get(k)) is not int for k in
                       ("species", "item", "move", "replace_move", "replace_index"))):
            raise ValueError("只允許已列冊的固定HM教學意圖")
        self.intent = deepcopy(intent)
        _, before, self.name, self.move = _CONTRACTS[intent["kind"]]
        self.before_moves = list(before)
        self.after_moves = list(before)
        self.after_moves[intent["replace_index"]] = intent["move"]
        self.old_move = move_key(intent["replace_move"]).replace("_", " ")
        self.stage, self.error = "initial", None
        self.baseline = self.inventory = self.money = self.location = self.player_name = None
        self.target_index = self.bag_offset = self.bag_cursor = None
        self.calls = self.waits = 0
        self.started = self.last_time = self.last_frame = self.last_packet = None
        self.direction_pending = None
        self.actions = set()
        self.intro_index = 0
        self.replacement_selected = self.seen_forgot = self.seen_and = self.seen_learned = False
        self.close_frame = None
        self.machine_prompt_sent = set()
        self.receipt_prompt_sent = set()

    def _fail(self, reason):
        self.error = "hm_teaching_" + reason.removeprefix("hm_teaching_")
        return {"phase": "campaign_review", "objective": "Wait.", "available_actions": ["wait"],
                "review_reason": self.error, "hm_teaching_controller": self.intent["kind"],
                "source_commit": SOURCE_COMMIT, "sources": SOURCES}

    def _wait(self, why):
        self.waits += 1
        if self.waits > MAX_WAITS:
            return self._fail("wait_budget_exhausted")
        return {"phase": "hm_teaching_menu", "objective": "Wait.", "available_actions": ["wait"],
                "hm_teaching_tactic": why, "hm_teaching_controller": self.intent["kind"],
                "safe_wait_count": self.waits, "source_commit": SOURCE_COMMIT}

    def _send(self, action, key, *, direction=None, **meta):
        token = (self.stage, key, action)
        if token in self.actions:
            return self._wait("pending_same_semantic_page")
        self.actions.add(token)
        if direction:
            self.direction_pending = direction
        return command(action, "hm_teaching_menu", {
            "hm_teaching_controller": self.intent["kind"], "hm_teaching_tactic": key,
            "source_commit": SOURCE_COMMIT, "sources": SOURCES, **meta})

    def _check_progress(self, p):
        if (not isinstance(p, dict) or p.get("profile") != PROGRESS_PROFILE
                or p.get("initialization_candidate") is not True or p.get("party_read_valid") is not True):
            return "upstream_profile_or_party_unverified"
        party = p.get("party")
        if (not isinstance(party, list) or not 1 <= len(party) <= 6
                or not _int(p.get("party_count"), 1, 6) or p["party_count"] != len(party)):
            return "party_count_invalid"
        ref = reference()
        if ref.get("source_commit") != SOURCE_COMMIT:
            return "reference_commit_mismatch"
        for mon in party:
            if (not isinstance(mon, dict) or not _int(mon.get("species"), 1, 190)
                    or species_key(mon["species"]) is None
                    or mon.get("species_name") != species_key(mon["species"])
                    or not _int(mon.get("level"), 1, 100) or not _int(mon.get("exp"), 0, 0xFFFFFF)
                    or not _int(mon.get("max_hp"), 1, 999) or not _int(mon.get("hp"), 1, mon["max_hp"])
                    or mon.get("status") != 0 or type(mon.get("status")) is not int
                    or any(not isinstance(mon.get(k), list) or len(mon[k]) != 4
                           or any(not _int(v, 0, hi) for v in mon[k])
                           for k, hi in (("moves", 165), ("pp", 255)))):
                return "party_fingerprint_invalid"
            for move, pp in zip(mon["moves"], mon["pp"]):
                key = move_key(move) if move else None
                if move == 0 and pp != 0 or move and (
                        key is None or (pp & 63) > ref["moves"][key]["pp"] * (5 + (pp >> 6)) // 5):
                    return "party_pp_invalid"
        if len({m["species"] for m in party}) != len(party):
            return "party_species_not_unique"
        inv = _inventory(p.get("inventory"))
        if inv is None or not _int(p.get("money"), 0, 999999):
            return "inventory_or_money_invalid"
        if self.baseline is None:
            matches = [i for i, m in enumerate(party) if m["species"] == self.intent["species"]]
            if len(matches) != 1 or party[matches[0]]["moves"] != self.before_moves:
                return "initial_target_or_four_moves_invalid"
            if self.move not in ref["species"][self.name]["tmhm"]:
                return "source_compatibility_mismatch"
            if (ref["moves"][self.move]["id"], ref["moves"][self.move]["pp"]) != (self.intent["move"], 15):
                return "source_move_id_or_pp_mismatch"
            if (self.intent["item"], 1) not in inv:
                return "unique_hm_quantity_one_required"
            if not isinstance(p.get("player_name_raw"), str) or not re.fullmatch(r"[A-Z]{1,7}", p["player_name_raw"]):
                return "player_name_for_start_menu_unverified"
            self.target_index, self.baseline = matches[0], deepcopy(party)
            self.inventory, self.money, self.player_name = inv, p["money"], p["player_name_raw"]
        if inv != self.inventory or p["money"] != self.money:
            return "hm_inventory_or_money_changed"
        if p.get("player_name_raw") != self.player_name or len(party) != len(self.baseline):
            return "party_or_player_identity_changed"
        for i, (mon, old) in enumerate(zip(party, self.baseline)):
            if i != self.target_index:
                if mon != old:
                    return "other_party_member_changed"
                continue
            if {k: v for k, v in mon.items() if k not in {"moves", "pp"}} != {
                    k: v for k, v in old.items() if k not in {"moves", "pp"}}:
                return "target_nonmove_data_changed"
            expected_pp = list(old["pp"])
            expected_pp[self.intent["replace_index"]] = 15
            if mon["moves"] == self.before_moves and mon["pp"] == old["pp"]:
                if self.seen_learned:
                    return "completed_moves_reverted"
            elif (self.replacement_selected and mon["moves"] == self.after_moves and mon["pp"] == expected_pp):
                pass
            else:
                return "unexpected_move_or_pp_change"
        return None

    def context(self, text, progress, *, location, frame, now,
                overworld_ready=False, battle_active=False):
        if self.error:
            return self._fail(self.error)
        self.calls += 1
        if (type(now) not in (int, float) or not math.isfinite(now) or now < 0
                or self.last_time is not None and now < self.last_time):
            return self._fail("clock_invalid")
        if self.started is None:
            self.started = now
        if self.calls > MAX_CALLS or now - self.started > MAX_SECONDS:
            return self._fail("transaction_budget_exhausted")
        self.last_time = now
        if not _int(frame, 0, 0x7FFFFFFFFFFFFFFF) or self.last_frame is not None and frame < self.last_frame:
            return self._fail("frame_invalid_or_regressed")
        if type(overworld_ready) is not bool or battle_active is not False:
            return self._fail("nonbattle_or_world_assertion_invalid")
        if (not isinstance(location, dict)
                or any(not _int(location.get(k), 0, 255) for k in ("map_id", "x", "y"))):
            return self._fail("location_invalid")
        pos = {k: location[k] for k in ("map_id", "x", "y")}
        if self.location is not None and pos != self.location:
            return self._fail("location_changed")
        rows = _rows(text)
        if rows is None:
            return self._fail("full_native_decoder_proof_required")
        for p in (text, progress, location):
            if ("observation_frame" in p and
                    (type(p["observation_frame"]) is not int or p["observation_frame"] != frame)):
                return self._fail("observation_frame_conflict")
        error = self._check_progress(progress)
        if error:
            return self._fail(error)
        packet = deepcopy((text, progress, pos, overworld_ready, battle_active))
        if frame == self.last_frame:
            if packet != self.last_packet:
                return self._fail("same_frame_packet_conflict")
            return self._wait("same_frame_no_resend")
        self.last_frame, self.last_packet = frame, packet
        if self.location is None:
            self.location = pos
        return self._context(rows, progress, text["window_visible"], overworld_ready, frame)

    def _start(self, cursor):
        r = _blank()
        for y, label in ((2, "POKÉDEX"), (4, "POKÉMON"), (6, "ITEM"),
                         (8, self.player_name), (10, "SAVE"), (12, "OPTION"), (14, "EXIT")):
            _put(r, 12, y, label)
        _put(r, 11, cursor, "▶")
        return r

    def _bag(self, offset, cursor, marker="▶"):
        r = self._start(6)
        _clear(r, 4, 2, 19, 12)
        for n in range(4):
            y, index = 4 + n * 2, offset + n
            if index == len(self.inventory):
                _put(r, 6, y, "CANCEL")
                break
            if index > len(self.inventory):
                break
            item, quantity = self.inventory[index]
            _put(r, 6, y, _label(item))
            if item not in _KEY_ITEMS:
                _put(r, 14, y + 1, f"×{quantity:2}")
        _put(r, 5, 4 + cursor * 2, marker)
        return r

    def _use(self, cursor=11, marker="▶"):
        r = self._bag(self.bag_offset, self.bag_cursor, "▷")
        _clear(r, 13, 10, 19, 15)
        _put(r, 15, 11, "USE")
        _put(r, 15, 13, "TOSS")
        _put(r, 14, cursor, marker)
        return r

    def _party(self, cursor=None, marker="▶"):
        r = _blank()
        for i, mon in enumerate(self.baseline):
            _put(r, 3, i * 2, mon["species_name"])
            _put(r, 13, i * 2, f"{mon['level']:3}")
            able = self.move in reference()["species"][mon["species_name"]]["tmhm"]
            _put(r, 12, i * 2 + 1, "ABLE" if able else "NOT ABLE")
        if cursor is not None:
            _put(r, 0, cursor * 2 + 1, marker)
        _put(r, 1, 14, "Use TM on which")
        _put(r, 1, 16, "POKéMON?")
        return r

    def _dialog(self, lines, *, question=False, cursor=8, inactive=False, party=False, arrow=None):
        r = self._party(self.target_index, "▷") if party else self._use(11, "▷")
        _clear(r, 0, 12, 19, 17)
        if question:
            _clear(r, 14, 7, 19, 12)
            _put(r, 16, 8, "YES")
            _put(r, 16, 10, "NO")
            _put(r, 15, cursor, "▷" if inactive else "▶")
        for y, text in lines:
            _put(r, 1, y, text)
        if arrow:
            _put(r, 18, arrow, "▼")
        return r

    def _forget(self, cursor):
        r = self._party(self.target_index, "▷")
        _clear(r, 4, 7, 19, 12)
        _clear(r, 0, 12, 19, 17)
        for i, move in enumerate(self.before_moves):
            _put(r, 6, 8 + i, move_key(move).replace("_", " "))
        _put(r, 5, cursor, "▶")
        _put(r, 1, 14, "Which move should")
        _put(r, 1, 16, "be forgotten?")
        return r

    def _templates(self):
        views = []
        def add(kind, key, r):
            views.append((kind, key, _serial(r)))
        for y in (2, 4, 6, 8, 10, 12, 14):
            add("start", y, self._start(y))
            inactive=self._start(y)
            _put(inactive,11,y,'▷')
            add('start_inactive',y,inactive)
        for offset in range(len(self.inventory)):
            for cursor in range(min(3, len(self.inventory) - offset)):
                for marker in ("▶", "▷"):
                    bag=self._bag(offset, cursor, marker)
                    add("bag", (offset, cursor, marker), bag)
                    if offset+3<len(self.inventory):
                        _put(bag,18,11,"▼")
                        add("bag", (offset, cursor, marker), bag)
        if self.bag_offset is not None:
            for y in (11, 13):
                for marker in ("▶", "▷"):
                    add("use", (y, marker), self._use(y, marker))
            for arrow in (None, 16, 17):
                add("boot", arrow is not None, self._dialog([(14, "Booted up an HM!")], arrow=arrow))
                add("contained", arrow is not None, self._dialog([(14, "It contained"), (16, self.move + "!")], arrow=arrow))
            for y in (8, 10):
                for inactive in (False, True):
                    add("teach", (y, inactive), self._dialog(
                        [(14, "Teach " + self.move), (16, "to a POKéMON?")],
                        question=True, cursor=y, inactive=inactive))
            add("teach_partial", None, self._dialog([(14, "Teach " + self.move), (16, "to a POKéMON?")]))
        for i in range(len(self.baseline)):
            for marker in ("▶", "▷"):
                add("party", (i, marker), self._party(i, marker))
        pages = [
            [[(14, self.name + " is"), (16, "trying to learn")]],
            [[(14, "trying to learn"), (16, self.move + "!")], [(14, self.move + "!")]],
            [[(14, "But, " + self.name), (16, "can't learn more")]],
            [[(14, "can't learn more"), (16, "than 4 moves!")], [(14, "than 4 moves!")]],
        ]
        for index, variants in enumerate(pages):
            for lines in variants:
                for arrow in (None, 16, 17):
                    add("intro", index, self._dialog(lines, party=True, arrow=arrow))
        delete_variants = [
            [(14, "move to make room"), (16, "for " + self.move + "?")],
            [(13, "Delete an older"), (14, "move to make room"), (16, "for " + self.move + "?")]]
        for lines in delete_variants:
            add("delete_partial", None, self._dialog(lines, party=True))
            for y in (8, 10):
                for inactive in (False, True):
                    add("delete", (y, inactive), self._dialog(lines, party=True, question=True,
                                                            cursor=y, inactive=inactive))
        for arrow in (None, 16, 17):
            add("delete_scroll", None, self._dialog(
                [(14, "Delete an older"), (16, "move to make room")], party=True, arrow=arrow))
        for y in range(8, 12):
            add("forget", y, self._forget(y))
        add('forget_drawing',None,self._dialog(
            [(14,'Which move should'),(16,'be forgotten?')],party=True))
        for arrow in (None, 16, 17):
            for text in ("1, 2 and...", "1, 2 and... Poof!"):
                add("poof", (text, arrow), self._dialog([(14, text)], party=True, arrow=arrow))
            add("forgot", arrow is not None, self._dialog([(14, self.name + " forgot"),
                                            (16, self.old_move + "!")], party=True, arrow=arrow))
            add("and", arrow is not None, self._dialog([(14, "And...")], party=True, arrow=arrow))
            add("learned", arrow is not None, self._dialog([(14, self.name + " learned"),
                                             (16, self.move + "!")], party=True, arrow=arrow))
        return views

    def _direction(self, kind, current):
        if self.direction_pending is None:
            return None
        expected_kind, old, new = self.direction_pending
        if kind != expected_kind:
            return self._fail("menu_changed_while_direction_pending")
        if current == old:
            return self._wait("await_observed_cursor_motion")
        if current != new:
            return self._fail("cursor_did_not_move_one_verified_item")
        self.direction_pending = None
        return None

    def _context(self, rows, p, window, ready, frame):
        if self.stage == "initial":
            if not ready or window or rows != (" " * 20,) * 18:
                return self._fail("initial_canonical_overworld_required")
            self.stage = "start"
            return self._send("start", "open_start")
        changed = p["party"][self.target_index]["moves"] == self.after_moves
        if self.stage == "complete":
            if not changed or not ready or window or rows != (" " * 20,) * 18:
                return self._fail("complete_observation_changed")
            return self._complete()
        if self.stage == "closing" and ready and not window and rows == (" " * 20,) * 18:
            if not changed or not self.seen_learned:
                return self._fail("closed_without_learning_receipt")
            if self.close_frame is None:
                self.close_frame = frame
                return self._wait("first_closed_overworld_frame")
            if frame <= self.close_frame:
                return self._wait("await_second_closed_frame")
            self.stage = "complete"
            return self._complete()
        if ready:
            return self._fail("overworld_before_completed_teaching")
        if rows == (" " * 20,) * 18:
            return self._wait("known_transition_blank")
        views = self._templates()
        full = [(kind, key) for kind, key, template in views if rows == template]
        if not full:
            if any(_subset(rows, template) for _, _, template in views):
                return self._wait("known_source_partial_no_input")
            return self._fail("unknown_or_polluted_source_page")
        kind, key = full[0]
        if kind=='start_inactive':
            if self.stage not in {'start','opening_bag','closing'}:
                return self._fail('unexpected_inactive_start_menu')
            return self._wait('native_start_inactive_cursor')
        if kind == "start":
            if self.stage == "closing":
                return self._send("b", "close_start")
            if self.stage == "opening_bag":
                return self._wait("start_item_confirmation_pending")
            if self.stage != "start":
                return self._fail("unexpected_start_menu")
            pending = self._direction("start", key)
            if pending:
                return pending
            if key == 6:
                result = self._send("a", "open_item_bag")
                self.stage = "opening_bag"
                return result
            target = key + (2 if key < 6 else -2)
            return self._send("down" if key < 6 else "up", ("start_cursor", key),
                              direction=("start", key, target))
        if kind == "bag":
            offset, cursor, marker = key
            current = offset + cursor
            if self.stage == "closing":
                return self._send("b", ("close_bag", current))
            if self.stage == "item_selected":
                return self._wait("bag_item_confirmation_pending")
            if self.stage not in {"opening_bag", "bag"}:
                return self._fail("unexpected_bag")
            if marker != "▶":
                return self._wait("await_active_bag_cursor")
            pending = self._direction("bag", current)
            if pending:
                return pending
            self.stage = "bag"
            target = next(i for i, (item, _) in enumerate(self.inventory) if item == self.intent["item"])
            if current == target:
                self.bag_offset, self.bag_cursor = offset, cursor
                result = self._send("a", "select_exact_hm", menu_label=_label(self.intent["item"]))
                self.stage = "item_selected"
                return result
            direction = 1 if current < target else -1
            return self._send("down" if direction == 1 else "up", ("bag_cursor", current),
                              direction=("bag", current, current + direction))
        if kind == "use":
            y, marker = key
            if self.stage == "boot":
                return self._wait("use_confirmation_pending")
            if self.stage != "item_selected":
                return self._fail("unexpected_use_toss")
            if marker != "▶":
                return self._wait("await_active_use_cursor")
            pending = self._direction("use", y)
            if pending:
                return pending
            if y == 13:
                return self._send("up", "move_toss_to_use", direction=("use", 13, 11))
            result = self._send("a", "confirm_use_only", menu_label="USE")
            self.stage = "boot"
            return result
        if kind in {"boot", "contained"}:
            expected = "boot" if kind == "boot" else "contained"
            order = {"boot": 0, "contained": 1, "teach": 2}
            sent=getattr(self,'machine_prompt_sent',set())
            self.machine_prompt_sent=sent
            if self.stage in order and order[self.stage] > order[expected]:
                # 已部署舊版曾在文字完整、原生prompt尚未出現時送A；只補一次真prompt。
                if key and kind not in sent:
                    result=self._send('a','advance_'+kind+'_native_prompt')
                    sent.add(kind)
                    return result
                return self._wait("prior_machine_page_pending")
            if self.stage != expected:
                return self._fail("machine_dialogue_out_of_order")
            if not key:return self._wait('await_machine_prompt_arrow')
            result = self._send("a", "advance_" + kind+'_native_prompt')
            sent.add(kind)
            self.stage = "contained" if kind == "boot" else "teach"
            return result
        if kind in {"teach_partial", "delete_partial"}:
            return self._wait("await_full_yes_no_box")
        if kind in {"teach", "delete"}:
            y, inactive = key
            expected = "teach" if kind == "teach" else "delete"
            if self.stage in ({"party", "intro", "delete", "forget", "receipt", "closing"} if kind == "teach"
                              else {"forget", "receipt", "closing"}):
                if y != 8:
                    return self._fail("old_question_changed_after_yes")
                return self._wait("question_yes_semantic_pending")
            if self.stage != expected or inactive:
                return self._fail("unexpected_or_inactive_yes_no")
            pending = self._direction(kind, y)
            if pending:
                return pending
            if y == 10:
                return self._send("up", "select_" + kind + "_yes", direction=(kind, 10, 8))
            result = self._send("a", "confirm_" + kind + "_yes", menu_label="YES")
            self.stage = "party" if kind == "teach" else "forget"
            return result
        if kind == "party":
            index, marker = key
            if self.stage == "intro":
                if index != self.target_index:
                    return self._fail("old_party_changed_after_selection")
                return self._wait("learner_confirmation_pending")
            if self.stage != "party":
                return self._fail("unexpected_party_menu")
            if marker != "▶":
                return self._wait("await_active_learner_cursor")
            pending = self._direction("party", index)
            if pending:
                return pending
            if index != self.target_index:
                d = 1 if index < self.target_index else -1
                return self._send("down" if d == 1 else "up", ("learner_cursor", index),
                                  direction=("party", index, index + d))
            result = self._send("a", "choose_exact_learner", party_target_index=index)
            self.stage = "intro"
            return result
        if kind == "intro":
            if self.stage not in {"intro", "delete"}:
                return self._fail("unexpected_learning_intro")
            if key < self.intro_index:
                return self._wait("prior_intro_page_pending")
            if self.stage != "intro" or key != self.intro_index:
                return self._fail("learning_intro_sequence_incomplete")
            result = self._send("a", ("advance_intro", key))
            self.intro_index += 1
            if self.intro_index == 4:
                self.stage = "delete"
            return result
        if kind == "delete_scroll":
            if self.stage == "delete":
                return self._send("a", "advance_delete_scroll")
            if self.stage in {"forget", "receipt", "closing"}:
                return self._wait("prior_delete_scroll")
            return self._fail("delete_without_learning_intro")
        if kind == 'forget_drawing':
            if self.stage!='forget':return self._fail('unexpected_forget_drawing_page')
            return self._wait('await_full_forget_menu')
        if kind == "forget":
            if self.stage == "receipt":
                if key != 8 + self.intent["replace_index"]:
                    return self._fail("old_forget_cursor_changed")
                return self._wait("replacement_confirmation_pending")
            if self.stage != "forget":
                return self._fail("unexpected_forget_menu")
            pending = self._direction("forget", key)
            if pending:
                return pending
            target = 8 + self.intent["replace_index"]
            if key != target:
                d = 1 if key < target else -1
                return self._send("down" if d == 1 else "up", ("forget_cursor", key),
                                  direction=("forget", key, key + d))
            result = self._send("a", "forget_only_intended_move", forgotten_move=self.intent["replace_move"])
            self.replacement_selected, self.stage = True, "receipt"
            return result
        if kind in {"poof", "forgot", "and", "learned"}:
            sent=getattr(self,'receipt_prompt_sent',set())
            self.receipt_prompt_sent=sent
            if self.stage == "closing":
                if (kind=='learned' and key and kind not in sent and changed
                        and self.seen_forgot and self.seen_and and self.seen_learned):
                    result=self._send('a','dismiss_exact_learned_native_prompt')
                    sent.add(kind)
                    return result
                return self._wait("learned_confirmation_pending")
            if self.stage != "receipt":
                return self._fail("receipt_before_verified_replacement")
            if kind == "poof":
                if key[0] != "1, 2 and... Poof!" or key[1] is None:
                    return self._wait("known_forget_animation")
                return self._send("a", "advance_complete_poof_prompt")
            if kind == "forgot":
                if not key:return self._wait('await_receipt_prompt_arrow')
                if kind in sent:return self._wait('prior_receipt_prompt_pending')
                result = self._send("a", "advance_exact_forgot_native_prompt")
                sent.add(kind)
                self.seen_forgot = True
                return result
            if kind == "and":
                if not self.seen_forgot:
                    return self._fail("and_without_forgot_receipt")
                if not key:return self._wait('await_receipt_prompt_arrow')
                if kind in sent:return self._wait('prior_receipt_prompt_pending')
                result = self._send("a", "advance_exact_and_native_prompt")
                sent.add(kind)
                self.seen_and = True
                return result
            if not self.seen_forgot or not self.seen_and or not changed:
                return self._fail("learned_without_expected_transaction")
            if not key:return self._wait('await_receipt_prompt_arrow')
            result = self._send("a", "dismiss_exact_learned_native_prompt")
            sent.add(kind)
            self.seen_learned, self.stage = True, "closing"
            return result
        return self._fail("unsupported_source_page")

    def _complete(self):
        return {"phase": "hm_teaching_complete", "objective": "Wait.", "available_actions": ["wait"],
                "hm_teaching_complete": True, "hm_teaching_kind": self.intent["kind"],
                "hm_preserved": self.intent["item"], "hm_quantity_used": 0,
                "moves_verified": list(self.after_moves), "source_commit": SOURCE_COMMIT,
                "closed_observation_frame": self.last_frame}

