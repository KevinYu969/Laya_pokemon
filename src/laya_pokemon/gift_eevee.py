"""正常領取玉虹屋頂伊布的純子目標候選；不讀寫模擬器，也不執行按鍵。

固定 pret/pokered a53671100ec22e5394ff26ec028d0812a238dae2：
scripts/CeladonMansionRoofHouse.asm、engine/events/give_pokemon.asm、
engine/pokemon/add_mon.asm、engine/menus/naming_screen.asm。

呼叫端先正常走到 map132 (5,3) 面向 left，並提供完整20x18文字格、
唯讀 progress 和明確的 overworld_ready。gift_object_hidden 是公開可見球
的移除證據；可由經畫面核對的唯讀 toggle bit 取得，不能由控制器寫入。
此候選不接入 runner、不自行啟用，也不進入任何輸入字母的命名畫面。
"""
from __future__ import annotations

from copy import deepcopy
import math
import re
import time


SOURCE_COMMIT = "a53671100ec22e5394ff26ec028d0812a238dae2"
SOURCE_ROOT = f"https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/"
SOURCE_ANCHORS = {
    "gift": SOURCE_ROOT + "scripts/CeladonMansionRoofHouse.asm#L12",
    "give": SOURCE_ROOT + "engine/events/give_pokemon.asm#L1",
    "nickname_call": SOURCE_ROOT + "engine/pokemon/add_mon.asm#L40",
    "nickname_menu": SOURCE_ROOT + "engine/menus/naming_screen.asm#L1",
    "nickname_text": SOURCE_ROOT + "data/text/text_2.asm#L1756",
    "receipt_text": SOURCE_ROOT + "data/text/text_5.asm#L75",
    "initial_moves": SOURCE_ROOT + "data/pokemon/base_stats/eevee.asm#L13",
    "learnset": SOURCE_ROOT + "data/pokemon/evos_moves.asm#L1252",
    "toggle_index": SOURCE_ROOT + "constants/toggle_constants.asm#L140",
    "toggle_flags": SOURCE_ROOT + "ram/wram.asm#L1910",
    "toggle_bit": SOURCE_ROOT + "engine/overworld/toggleable_objects.asm#L137",
}

MAP_ID, EEVEE, GIFT_LEVEL = 132, 102, 25
GIFT_STANCE, GIFT_FACE, GIFT_BALL = (5, 3), "left", (4, 3)
INITIAL_MOVES, INITIAL_PP = (33, 28, 0, 0), (35, 15, 0, 0)
# 公開 WRAM 宣告：PartyData404 bytes，MainData基址D2F7，flags偏移2AF。
# 既有靜態 PyBoy PARTY_COUNT_ADDRESS=D163；此模組不匯入／讀取 PyBoy。
# wToggleableObjectFlags D5A6 + (69 >> 3) = D5AE，bit set 表示已移除。
GIFT_TOGGLE_INDEX = 69
GIFT_REMOVED_FLAG_ADDRESS, GIFT_REMOVED_FLAG_BIT = 0xD5AE, 5
GIFT_REMOVED_FLAG_MASK = 0x20

_INTRO = "DOYOUWANTTOGIVEANICKNAME"
_TAIL = "GIVEANICKNAMETOEEVEE"
_FULL_QUESTION = _INTRO + "TOEEVEE"
_RECEIPT = "KEVINGOTEEVEE"
_NAMING_TITLES = ("YOURNAME", "RIVALSNAME", "EEVEESNICKNAME", "NICKNAME")


def gift_removed_flag(raw_byte):
    """純解碼已由呼叫端取得的單一byte；不讀RAM、不把ON/OFF常數當旗標。"""
    if type(raw_byte) is not int or not 0 <= raw_byte <= 255:
        raise ValueError("伊布球移除旗標必須是單一合法byte")
    return bool(raw_byte & GIFT_REMOVED_FLAG_MASK)


def _compact(value):
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _rows(text):
    if not isinstance(text, dict):
        return None
    cells = text.get("cells")
    if (not isinstance(cells, (list, tuple)) or len(cells) != 18
            or any(not isinstance(row, (list, tuple, str)) or len(row) != 20
                   for row in cells)
            or any(not isinstance(cell, str) or len(cell) != 1
                   for row in cells for cell in row)):
        return None
    return ["".join(row).upper() for row in cells]


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _nickname_menu(rows):
    """固定YES/NO座標及完整唯一標籤；逐字尚未成形可等，矛盾不可確認。"""
    expected = {"YES": (16, 8), "NO": (16, 10)}
    positions = {label: [(match.start(), y) for y, row in enumerate(rows)
                         for match in re.finditer(r"(?<![A-Z])" + label + r"(?![A-Z])", row)]
                 for label in expected}
    slots = {label: rows[y][x:19].strip() for label, (x, y) in expected.items()}
    present = (any(positions.values()) or slots["YES"].startswith("Y")
               or slots["NO"].startswith("N"))
    if not present:
        return "absent"
    for label, position in expected.items():
        if positions[label] not in ([], [position]):
            return "invalid"
        if slots[label] and not label.startswith(slots[label]):
            return "invalid"
        if positions[label] and slots[label] != label:
            return "invalid"
        if slots[label] == label and not positions[label]:
            return "invalid"
        if rows[position[1]][19] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!?":
            return "invalid"
    return ("complete" if all(positions[label] == [position] and slots[label] == label
                              for label, position in expected.items()) else "partial")


def initial_screen_error(rows, overworld_ready):
    """方向微調與真正領取共用的純畫面前置檢查，不建立交易或發送按鍵。"""
    if rows is None:
        return 'eevee_gift_full_cells_required'
    markers = any(char in ''.join(rows) for char in ('▶', '▷', '▼'))
    menu_words = {'YES', 'NO', 'ITEM', 'POKÉMON', 'POKÉDEX', 'POKEMON', 'POKEDEX',
                  'SAVE', 'OPTION', 'EXIT', 'CANCEL', 'USE', 'TOSS'}
    if markers or any(row.strip() in menu_words for row in rows):
        return 'eevee_gift_initial_menu_marker_unverified'
    if overworld_ready is not True or _compact(''.join(rows[12:18])) or _nickname_menu(rows) != 'absent':
        return 'eevee_gift_requires_initial_overworld'
    return None


def _party(progress):
    if not isinstance(progress, dict) or progress.get("party_read_valid") is not True:
        return None
    party = progress.get("party")
    if (not isinstance(party, list) or not 1 <= len(party) <= 6
            or type(progress.get("party_count")) is not int
            or progress["party_count"] != len(party)):
        return None
    for mon in party:
        if (not isinstance(mon, dict)
                or not _integer(mon.get("species"), 1, 190)
                or not _integer(mon.get("level"), 1, 100)
                or not _integer(mon.get("max_hp"), 1, 999)
                or not _integer(mon.get("hp"), 0, mon["max_hp"])):
            return None
        for key, high in (("moves", 165), ("pp", 255)):
            if (not isinstance(mon.get(key), list) or len(mon[key]) != 4
                    or any(not _integer(value, 0, high) for value in mon[key])):
                return None
    return party


class EeveeGiftController:
    """單次禮物流程，未知畫面鎖定REVIEW；重啟不冒稱已有伊布是新取得。

    ``context(text, progress, *, location, overworld_ready,
    gift_object_hidden=None, battle_active=False)`` 只回Laya子目標。
    ``gift_object_hidden`` 必須為 bool/None；初始須明確False，完成須明確True。
    每次建議後都須重新採樣，不能把多次回傳批次當成按鍵腳本。
    """

    def __init__(self, *, max_calls=160, max_waits=30, max_seconds=60.0):
        if (type(max_calls) is not int or max_calls < 1
                or type(max_waits) is not int or max_waits < 1
                or isinstance(max_seconds, bool)
                or not isinstance(max_seconds, (int, float))
                or not math.isfinite(max_seconds) or max_seconds <= 0):
            raise ValueError("伊布禮物操作與時間上限必須為正數")
        self.max_calls, self.max_waits, self.max_seconds = max_calls, max_waits, max_seconds
        self.stage = "initial"
        self.baseline = None
        self.player_name = None
        self.calls = self.wait_count = 0
        self.started_at = None
        self.error = None
        self.seen_receipt = self.seen_intro = self.seen_question = False
        self.decline_issued = False
        self._advanced_pages = set()
        self._menu_down_pending = False

    def _metadata(self):
        return {"gift_controller": "source_verified_eevee_candidate",
                "gift_stage": self.stage, "gift_calls": self.calls,
                "gift_wait_count": self.wait_count, "source_commit": SOURCE_COMMIT,
                "sources": SOURCE_ANCHORS}

    def _review(self, reason):
        self.error = reason
        return {"phase": "campaign_review", "review_reason": reason,
                "objective": "Wait.", "available_actions": ["wait"], **self._metadata()}

    def _command(self, action, tactic, **extra):
        objectives = {"a": "Confirm the current selection.", "down": "Move DOWN.",
                      "wait": "Wait."}
        return {"phase": "gift_menu", "objective": objectives[action],
                "available_actions": [action, "wait"] if action != "wait" else ["wait"],
                "controller_menu_verified": True, "gift_tactic": tactic,
                "phase_source": "bounded source-verified visible Eevee gift controller",
                **self._metadata(), **extra}

    def _wait(self, tactic):
        self.wait_count += 1
        if self.wait_count > self.max_waits:
            return self._review("eevee_gift_wait_budget_exhausted")
        return self._command("wait", tactic)

    def _act(self, action, tactic, **extra):
        self.wait_count = 0
        return self._command(action, tactic, **extra)

    def _check_members(self, party):
        if party is None:
            return None
        count = len(self.baseline)
        if len(party) not in (count, count + 1) or party[:count] != self.baseline:
            return "eevee_existing_members_changed"
        if len(party) == count + 1 and party[-1]["species"] != EEVEE:
            return "eevee_unexpected_new_species"
        return None

    def context(self, text, progress, *, location, overworld_ready,
                gift_object_hidden=None, battle_active=False):
        if self.error:
            return self._review(self.error)
        now = time.monotonic()
        if self.started_at is None:
            self.started_at = now
        self.calls += 1
        if self.calls > self.max_calls or now - self.started_at > self.max_seconds:
            return self._review("eevee_gift_budget_exhausted")
        if battle_active is not False:
            return self._review("eevee_gift_requires_verified_nonbattle")
        if (not isinstance(location, dict) or type(location.get("map_id")) is not int
                or location["map_id"] != MAP_ID
                or type(location.get("x")) is not int or type(location.get("y")) is not int
                or (location["x"], location["y"]) != GIFT_STANCE
                or location.get("facing") != GIFT_FACE):
            return self._review("eevee_gift_stance_unverified")
        if gift_object_hidden is not None and type(gift_object_hidden) is not bool:
            return self._review("eevee_gift_hidden_signal_invalid")
        rows = _rows(text)
        if rows is None:
            return self._review("eevee_gift_full_cells_required")
        if not isinstance(progress, dict):
            return self._review("eevee_gift_progress_invalid")
        name = progress.get("player_name_raw")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z]{1,7}", name) or name.upper() != "KEVIN":
            return self._review("eevee_gift_player_name_not_kevin")
        if self.player_name is not None and name != self.player_name:
            return self._review("eevee_gift_player_name_changed")
        party = _party(progress)
        raw_lower = "\n".join(rows[12:18])
        lower = _compact(raw_lower)
        menu_state = _nickname_menu(rows)
        menu_labels = menu_state == "complete"
        any_menu_label = menu_state != "absent"
        # 一律不接管字母命名畫面，也不呼叫既有player naming控制器。
        if any(token in _compact("".join(rows[:5])) for token in _NAMING_TITLES):
            return self._review("eevee_gift_unexpected_naming_screen")
        if menu_state == "invalid":
            return self._review("eevee_gift_nickname_labels_unverified")

        if self.baseline is None:
            if party is None:
                return self._review("eevee_gift_initial_party_unverified")
            if any(mon["species"] == EEVEE for mon in party):
                return self._review("eevee_already_present_without_baseline")
            if len(party) > 5:
                return self._review("eevee_gift_requires_party_space")
            screen_error = initial_screen_error(rows, overworld_ready)
            if screen_error:
                return self._review(screen_error)
            if gift_object_hidden is not False:
                return self._review("eevee_gift_ball_visibility_unverified")
            self.baseline, self.player_name = deepcopy(party), name
            self.stage = "awaiting_gift"
            return self._act("a", "inspect_source_gift_ball", gift_ball=list(GIFT_BALL))

        changed = self._check_members(party)
        if changed:
            return self._review(changed)
        if self.stage == "complete":
            return self._completion(rows, party, overworld_ready, gift_object_hidden)

        if self.decline_issued:
            if overworld_ready is True and not lower and not any_menu_label:
                return self._completion(rows, party, overworld_ready, gift_object_hidden)
            # NO後不再送A；舊選單或尾頁尚在時只能有限等待。
            if (not lower or lower in (_INTRO, _TAIL, _FULL_QUESTION)
                    or self.seen_intro and lower == "TOEEVEE"):
                return self._wait("await_all_nickname_pages_closed")
            return self._review("eevee_gift_unknown_after_decline")

        if lower.startswith(_RECEIPT):
            if lower != _RECEIPT:
                return self._review("eevee_gift_receipt_unexpected_text")
            self.seen_receipt = True
            self.stage = "receipt"
            # _GotMonText以text_end結束，沒有press-A等待；等待正常進暱稱流程。
            return self._wait("wait_automatic_gift_receipt")
        if lower and _RECEIPT.startswith(lower):
            return self._wait("wait_partial_gift_receipt")

        full_question = lower == _FULL_QUESTION
        intro = lower == _INTRO
        tail = lower == _TAIL or self.seen_intro and lower == "TOEEVEE"
        if intro or full_question:
            self.seen_intro = True
        if full_question or self.seen_intro and tail:
            self.seen_question = True

        if menu_labels:
            if not self.seen_question:
                # 完整YES/NO不能替代完整已來源核對的伊布提問。
                if lower and any(value.startswith(lower) for value in (_INTRO, _TAIL, _FULL_QUESTION)):
                    return self._wait("wait_full_nickname_question")
                return self._review("eevee_gift_nickname_question_unverified")
            if lower not in (_TAIL, _FULL_QUESTION, "TOEEVEE"):
                return self._review("eevee_gift_nickname_menu_text_mismatch")
            if not re.search(r"TO\s+EEVEE\s*\?", raw_lower):
                return self._wait("wait_complete_nickname_question_mark")
            self.stage = "nickname_menu"
            active = [(x, y) for y, row in enumerate(rows) for x, char in enumerate(row) if char == "▶"]
            inactive = [(x, y) for y, row in enumerate(rows) for x, char in enumerate(row) if char == "▷"]
            if not active and len(inactive) == 1 and inactive[0] in ((15, 8), (15, 10)):
                return self._wait("wait_active_nickname_cursor")
            if len(active) != 1 or active[0] not in ((15, 8), (15, 10)) or inactive:
                return self._review("eevee_gift_nickname_cursor_unverified")
            if active[0] == (15, 8):
                if self._menu_down_pending:
                    return self._wait("wait_nickname_cursor_move")
                self._menu_down_pending = True
                return self._act("down", "select_no_nickname", menu_label="NO")
            self._menu_down_pending = False
            self.decline_issued = True
            self.stage = "awaiting_overworld"
            return self._act("a", "confirm_no_nickname", menu_label="NO")

        if any_menu_label:
            if intro or tail or full_question or any(value.startswith(lower) for value in (_INTRO, _TAIL, _FULL_QUESTION)):
                return self._wait("wait_complete_yes_no_labels")
            return self._review("eevee_gift_unknown_partial_menu")
        if intro:
            self.stage = "nickname_question"
            markers = [(x, y, char) for y, row in enumerate(rows) for x, char in enumerate(row)
                       if char in {"▶", "▷", "▼"}]
            if markers == [(18, 16, "▶")] or markers == [(18, 16, "▼")]:
                if lower in self._advanced_pages:
                    return self._wait("wait_nickname_question_scroll")
                self._advanced_pages.add(lower)
                return self._act("a", "advance_verified_nickname_question")
            if not markers or markers == [(18, 16, "▷")]:
                return self._wait("wait_nickname_page_marker")
            return self._review("eevee_gift_question_marker_unverified")
        if tail or full_question:
            return self._wait("wait_visible_yes_no_menu")
        if lower and any(value.startswith(lower) for value in (_INTRO, _TAIL, _FULL_QUESTION)):
            return self._wait("wait_partial_nickname_text")
        if not lower and not any_menu_label:
            return self._wait("wait_gift_ui_transition")
        return self._review("eevee_gift_unknown_screen")

    def _completion(self, rows, party, overworld_ready, hidden):
        if (overworld_ready is not True or _compact("".join(rows[12:18]))
                or any(char in "".join(rows) for char in ("▶", "▷", "▼"))):
            return self._wait("await_verified_overworld_after_gift")
        if party is None or len(party) == len(self.baseline):
            return self._wait("wait_initialized_gift_party")
        mon = party[-1]
        if (mon["species"] != EEVEE or mon["level"] != GIFT_LEVEL
                or tuple(mon["moves"]) != INITIAL_MOVES or tuple(mon["pp"]) != INITIAL_PP
                or mon["hp"] != mon["max_hp"] or type(mon.get("status")) is not int
                or mon["status"] != 0
                or "exp" in mon and mon["exp"] != GIFT_LEVEL ** 3):
            return self._review("eevee_gift_new_member_source_mismatch")
        if hidden is not True:
            return self._wait("wait_gift_ball_removed_evidence")
        if not self.decline_issued or not self.seen_question:
            return self._review("eevee_gift_nickname_flow_not_verified")
        self.stage = "complete"
        self.wait_count = 0
        return self._command("wait", "gift_verified_complete", gift_eevee_complete=True,
                             gift_species=EEVEE, gift_level=GIFT_LEVEL,
                             gift_moves=list(INITIAL_MOVES), gift_pp=list(INITIAL_PP),
                             gift_toggle_index=GIFT_TOGGLE_INDEX,
                             existing_members_unchanged=True, nickname_declined=True)
