"""正常 HM01 教學與 CUT 野外選單候選控制器；不執行按鍵或讀寫模擬器。

呼叫端必須明確指定意圖並提供唯讀進度、可見文字與已核對的野外地圖。
HM01教妙蛙草、地面與玉虹館內CUT已實機核對；妙蛙花使用仍為合成候選。
未知畫面一律回到檢討，不以連按 A 探路。
"""
from __future__ import annotations

import re
from copy import deepcopy
from functools import lru_cache

from .party_control import command, party_choice, selection
from .team_strategy import move_key, normalize, reference, species_key


SOURCE_COMMIT = "a53671100ec22e5394ff26ec028d0812a238dae2"
SOURCE_ROOT = f"https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/"
SOURCES = [SOURCE_ROOT + path for path in (
    "engine/items/item_effects.asm", "engine/pokemon/learn_move.asm",
    "engine/menus/start_sub_menus.asm", "engine/overworld/cut.asm", "home/window.asm",
    "data/text/text_4.asm", "data/text/text_6.asm", "data/text/text_7.asm",
    "data/pokemon/base_stats/ivysaur.asm", "data/pokemon/base_stats/venusaur.asm",
    "data/pokemon/evos_moves.asm", "constants/pokemon_constants.asm",
    "engine/menus/party_menu.asm", "engine/menus/text_box.asm", "home/list_menu.asm",
    "data/items/names.asm", "data/items/key_items.asm", "constants/item_constants.asm")]
HM01, CUT, IVYSAUR, GROWL, VINE_WHIP = 196, 15, 9, 45, 22
VENUSAUR = 154
_CUT_USERS = {IVYSAUR: "IVYSAUR", VENUSAUR: "VENUSAUR"}
MAX_SAFE_TEXT_WAITS = 30
MAX_BAG_DOWN_REQUESTS = 20
MAX_BAG_STAGNANT_REQUESTS = 3
# 固定Cut樹替換規則：Overworld及玉虹館內Gym；不接受任意可走格作成功。
_CUT_TILES = {0: (0x3D, 0x2C), 7: (0x50, 0x2B)}
# 固定 KeyItemFlags 為 TRUE 的 ID；秘傳機由 IsKeyItem 另行識別。
_KEY_ITEM_IDS = {5, 6, 7, 8, 9, *range(21, 29), 31, 41, 42, 43, 44, 45, 48,
                 63, 64, *range(69, 75), 76, 77, 78, *range(196, 201)}


@lru_cache(maxsize=1)
def _item_labels():
    """讀取 PyBoy 靜態 ID 表；不建立模擬器、不讀遊戲 RAM。"""
    try:
        from pyboy.plugins.game_wrapper_pokemon_gen1_constants import ITEMS
    except ImportError:
        return {}
    labels = {value: normalize(name) for name, value in ITEMS.items()}
    labels.update({item: f"HM{item-195:02d}" for item in range(196, 201)})
    labels.update({item: f"TM{item-200:02d}" for item in range(201, 251)})
    return labels

# 固定 pret/pokered text_4/6/7 的頁面及捲動後可見尾段；只接受開頭前綴。
_HM_PAGES = ("BOOTEDUPANHM", "ITCONTAINEDCUT")
_TEACH_PAGES = ("TEACHCUTTOAPOKEMON",)
_LEARN_PAGES = ("IVYSAURISTRYINGTOLEARNCUT", "TRYINGTOLEARNCUT", "CUT",
                "BUTIVYSAURCANTLEARNMORETHAN4MOVES", "IVYSAURCANTLEARNMORETHAN4MOVES",
                "CANTLEARNMORETHAN4MOVES", "THAN4MOVES")
_DELETE_PAGES = ("DELETEANOLDERMOVETOMAKEROOMFORCUT", "MOVETOMAKEROOMFORCUT", "FORCUT")
_FORGET_PAGES = ("WHICHMOVESHOULDBEFORGOTTEN", "BEFORGOTTEN")
_FORGOT_PAGES = ("12ANDPOOF", "12AND", "POOF", "IVYSAURFORGOTGROWLAND", "IVYSAURFORGOTGROWL", "GROWLAND", "GROWL", "AND")
_LEARNED_PAGES = ("IVYSAURLEARNEDCUT", "LEARNEDCUT", "CUT")


def _review(reason):
    """停在可記錄的檢討狀態；不提供可能確認錯誤選項的按鍵。"""
    return {"phase": "campaign_review", "objective": "Wait.",
            "available_actions": ["wait"], "review_reason": reason,
            "field_move_controller": "experimental_visible_cut", "sources": SOURCES}


def _rows(text):
    cells = text.get("cells", [])
    if len(cells) != 18 or any(len(row) != 20 for row in cells):
        return None
    return ["".join(row).upper() for row in cells]


def _hint(action, tactic, **extra):
    if action == "wait":
        return {"phase": "field_move_menu", "objective": "Wait.", "available_actions": ["wait"],
                "controller_menu_verified": True, "field_move_tactic": tactic,
                "field_move_controller": "experimental_visible_cut", "sources": SOURCES, **extra}
    return command(action, "field_move_menu", {
        "field_move_tactic": tactic, "field_move_controller": "experimental_visible_cut",
        "sources": SOURCES, **extra})


def _choose(rows, label, tactic):
    result = selection(rows, label, "field_move_menu")
    if result:
        return {**result, "field_move_tactic": tactic, "sources": SOURCES}
    return _review(f"cut_{tactic}_cursor_unreadable")


class CutController:
    """每次明確意圖建立一個實例，保留跨頁提問與不可逆刪招階段。

    ``intent={'kind':'teach_cut','species':9,'replace_move':45}`` 僅允許將
    HM01 合法教給妙蛙草，四招時替換叫聲並保留藤鞭。已會 CUT 可直接核對。
    ``intent={'kind':'use_cut','species':9,'map_id':5,'tree_x':15,'tree_y':18}``
    必須從與樹相鄰、朝向樹、已核對的野外畫面開始；樹格由 ``grid`` 驗證。
    使用者只接受9或154，且必須是全隊唯一實際會CUT15的成員。自然進化後
    由呼叫端核對實際物種再建立species154的新意圖，不以family猜測或改隊伍。

    ``context`` 的 ``overworld_ready`` 是呼叫端完成畫面校驗後的明確聲明；
    ``grid`` 接既有 ``read_world_grid`` 結果，``location`` 接唯讀座標與朝向。
    不以缺少文字自行推定野外，也不操作 ROM、記憶體、存檔或系統按鍵。
    """

    def __init__(self, intent):
        self.intent = deepcopy(intent)
        if intent.get("kind") not in {"teach_cut", "use_cut"}:
            raise ValueError("僅允許 teach_cut 或 use_cut 明確意圖")
        species = intent.get("species")
        if (type(species) is not int
                or intent["kind"] == "teach_cut" and species != IVYSAUR
                or intent["kind"] == "use_cut" and species not in _CUT_USERS):
            raise ValueError("教學僅限妙蛙草9；使用僅限已核對CUT的妙蛙草9／妙蛙花154")
        if intent["kind"] == "teach_cut" and intent.get("replace_move", GROWL) != GROWL:
            raise ValueError("四招時僅允許替換叫聲；不得刪除藤鞭")
        if intent["kind"] == "use_cut":
            for name in ("map_id", "tree_x", "tree_y"):
                value = intent.get(name)
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    raise ValueError(f"{name} 必須為非負整數")
            tileset=intent.get('tileset_id',0)
            if type(tileset) is not int or tileset not in _CUT_TILES:
                raise ValueError('CUT圖格組未經來源核對')
            if tileset==7 and (intent['map_id']!=134 or (intent['tree_x'],intent['tree_y']) not in {(5,7),(2,4),(7,5)}):
                raise ValueError('館內CUT僅允許玉虹已核對樹格')
        self.stage = "initial"
        self.baseline = None
        self.target_index = None
        self.expected_moves = None
        self.seen_cut_name = False
        self.seen_learner = False
        self.seen_learned = False
        self.seen_used_cut = False
        self.error = None
        self.safe_wait_count = 0
        self.safe_wait_stage = None
        self.field_user_confirmed = False

    def _fail(self, reason):
        self.error = reason
        return _review(reason)

    def context(self, text, progress, *, location=None, grid=None,
                overworld_ready=False, battle_active=False):
        """依當前可見證據回傳一個 Laya 按鍵目標；未知或矛盾即鎖定檢討。"""
        if self.error:
            return _review(self.error)
        if battle_active is not False:
            return self._fail("cut_requires_verified_nonbattle")
        rows = _rows(text)
        if rows is None:
            return self._fail("cut_visible_cells_invalid")
        party = progress.get("party", [])
        targets = [i for i, mon in enumerate(party) if mon.get("species") == self.intent["species"]]
        if len(targets) != 1 or progress.get("party_read_valid") is not True:
            return self._fail("cut_target_party_not_verified")
        target = party[targets[0]]
        moves = target.get("moves")
        if not isinstance(moves, list) or len(moves) != 4:
            return self._fail("cut_target_moves_unreadable")
        target_name = _CUT_USERS[self.intent["species"]]
        if "CUT" not in reference()["species"][target_name]["tmhm"]:
            return self._fail("cut_source_compatibility_missing")
        if self.intent["kind"] == "use_cut":
            if (not 1 <= len(party) <= 6
                    or any(species_key(mon.get("species")) is None
                           or not isinstance(mon.get("moves"), list) or len(mon["moves"]) != 4
                           or any(type(move) is not int or not 0 <= move <= 165 for move in mon["moves"])
                           for mon in party)):
                return self._fail("cut_field_party_unverifiable")
            if CUT not in moves:
                return self._fail("cut_field_move_not_known")
            if moves.count(CUT) != 1:
                return self._fail("cut_field_duplicate_cut_slots")
            if [i for i, mon in enumerate(party) if CUT in mon["moves"]] != targets:
                return self._fail("cut_field_multiple_cut_users")
        if self.baseline is None:
            self.target_index = targets[0]
            self.baseline = [(mon.get("species"), list(mon.get("moves", []))) for mon in party]
        if (len(party) != len(self.baseline) or targets[0] != self.target_index
                or any(mon.get("species") != before[0]
                       or (i != self.target_index and mon.get("moves") != before[1])
                       for i, (mon, before) in enumerate(zip(party, self.baseline)))):
            return self._fail("cut_party_changed_unexpectedly")
        if self.intent["kind"] == "teach_cut":
            result = self._teach(rows, progress, moves, overworld_ready)
        else:
            result = self._use(rows, progress, moves, location, grid, overworld_ready)
        if result.get("phase") == "campaign_review":
            self.error = result["review_reason"]
        elif result.get("available_actions") != ["wait"]:
            self.safe_wait_count = 0
            self.safe_wait_stage = None
        return result

    def _bounded_wait(self, tactic):
        """同一已知轉場最多等待三十步；文字逐字增加不會重置計數。"""
        if self.safe_wait_stage != self.stage:
            self.safe_wait_stage, self.safe_wait_count = self.stage, 0
        if self.safe_wait_count >= MAX_SAFE_TEXT_WAITS:
            return self._fail("cut_known_transition_wait_exhausted")
        self.safe_wait_count += 1
        return _hint("wait", tactic, safe_wait_count=self.safe_wait_count,
                     safe_wait_limit=MAX_SAFE_TEXT_WAITS)

    def _partial_wait(self, rows, *, field=False):
        """僅對階段吻合的固定下方文字前綴等待；選單、▼、錯誤交由原流程。"""
        if any(char in " ".join(rows) for char in ("▶", "▼")):
            return None
        lower = normalize(" ".join(rows[12:18]))
        if any(normalize(row.strip()) in {"YES", "NO"} for row in rows):
            return None
        field_pages = (self._field_message(), "AWAYWITHCUT")
        pages = ({"cut_selected": field_pages, "cut_animation": field_pages} if field else {
            "hm_selected": _HM_PAGES, "hm_dialogue": _HM_PAGES + _TEACH_PAGES,
            "teach_question": _TEACH_PAGES,
            "choose_learner": _LEARN_PAGES,
            "learning_intro": _LEARN_PAGES + (_DELETE_PAGES if self.seen_learner else ()),
            "delete_question": _DELETE_PAGES + _FORGET_PAGES,
            "forget_menu": _FORGET_PAGES,
            "forget_selected": _FORGOT_PAGES + _LEARNED_PAGES,
            "learned": _LEARNED_PAGES,
        }).get(self.stage, ())
        if not lower:
            # 只有已知轉場且整個可讀文字面為空，才容許有限動畫等待。
            transition = {"hm_selected", "hm_dialogue", "teach_question", "choose_learner",
                          "learning_intro", "delete_question", "forget_selected", "learned",
                          "closing", "cut_selected", "cut_animation"}
            if self.stage in transition and not normalize(" ".join(rows)):
                return self._bounded_wait("await_known_cut_transition_blank")
            return None
        matches = [page for page in pages if page.startswith(lower)]
        if not matches:
            return None
        # 完整提問仍可等 YES/NO；其餘完整訊息留給已校對的正常確認分支。
        question = any(page in _TEACH_PAGES + _DELETE_PAGES + _FORGET_PAGES for page in matches)
        punctuation_complete = any(mark in " ".join(rows[12:18]) for mark in ("!", "..."))
        if lower in matches and not question and punctuation_complete:
            return None
        if not field and any(page in _DELETE_PAGES for page in matches) and self.seen_learner:
            self.stage = "delete_question"
        elif not field and any(page in _TEACH_PAGES for page in matches):
            self.stage = "teach_question"
        elif not field and "IVYSAURISTRYINGTOLEARN" in lower:
            self.seen_learner = True
            self.stage = "learning_intro"
        return self._bounded_wait("await_verified_cut_text_prefix")

    def _complete(self, kind, **extra):
        self.stage = "complete"
        return {"phase": "field_move_complete", "objective": "Wait.",
                "available_actions": ["wait"], "field_move_complete": True,
                "field_move_kind": kind, "sources": SOURCES, **extra}

    def _teach(self, rows, progress, moves, overworld_ready):
        compact = normalize(" ".join(rows))
        if self.stage == "initial":
            if CUT in moves:
                return self._complete("teach_cut", cut_already_known=True, moves_verified=list(moves))
            if VINE_WHIP not in moves or moves.count(GROWL) != 1:
                return self._fail("cut_requires_growl_and_protected_vine_whip")
            if any(not move for move in moves):
                return self._fail("cut_empty_move_slot_flow_not_calibrated")
            inventory = progress.get("inventory")
            if not isinstance(inventory, list) or sum(
                    item.get("quantity", 0) for item in inventory if item.get("item") == HM01) < 1:
                return self._fail("cut_hm01_not_verified_in_inventory")
            if not overworld_ready:
                return self._fail("cut_teaching_start_not_verified_overworld")
            self.expected_moves = list(moves)
            self.expected_moves[moves.index(GROWL)] = CUT
            self.stage = "start_menu"
            return _hint("start", "open_items_for_hm01")
        baseline_moves = self.baseline[self.target_index][1]
        if moves != baseline_moves and moves != self.expected_moves:
            return self._fail("cut_unexpected_move_replacement")
        if moves == self.expected_moves:
            if self.stage not in {"forget_selected", "learned", "closing", "complete"}:
                return self._fail("cut_move_changed_before_verified_forget_selection")
            if self.seen_learned and overworld_ready:
                return self._complete("teach_cut", moves_verified=list(moves),
                                      forgotten_move=GROWL, protected_move=VINE_WHIP)
        if any(token in compact for token in ("NOTCOMPATIBLE", "HMCANT",
                                              "CANTBEDELETED", "DIDNOTLEARN", "ALREADYKNOWS")):
            return self._fail("cut_learning_rejected_or_ambiguous")
        if "ABANDONLEARNING" in compact or "STOPLEARNING" in compact:
            return self._fail("cut_learning_unexpected_abandon_prompt")
        if self.stage in {"learned", "closing"} and moves != self.expected_moves:
            return self._fail("cut_learned_message_without_expected_moves")
        if re.search(r"\bFORGOT\b", " ".join(rows)) and self.stage != "forget_selected":
            return self._fail("cut_forget_animation_without_selection")
        partial = self._partial_wait(rows)
        if partial:
            return partial
        if "CANTLEARN" in compact and not (self.stage == "learning_intro" and "CANTLEARNMORE" in compact):
            return self._fail("cut_learning_rejected_or_ambiguous")
        # 只有本流程記住的刪招確認後才接受忘招畫面；四招逐列與唯讀順序核對。
        if "WHICHMOVESHOULD" in compact or "BEFORGOTTEN" in compact:
            if self.stage not in {"delete_question", "forget_menu", "forget_selected"}:
                return self._fail("cut_unexpected_forget_menu")
            self.stage = "forget_menu"
            return self._forget(rows, baseline_moves)
        if any(token in compact for token in ("POOF", "FORGOT", "12AND")):
            if self.stage != "forget_selected":
                return self._fail("cut_forget_animation_without_selection")
            if "FORGOT" in compact and "GROWL" not in compact:
                return self._fail("cut_forgot_move_not_visually_growl")
            return _hint("a", "advance_verified_growl_forget")
        if "LEARNED" in compact:
            if self.stage not in {"forget_selected", "learned"} or "IVYSAUR" not in compact or "CUT" not in compact:
                return self._fail("cut_learned_message_not_verified")
            self.seen_learned = True
            self.stage = "learned"
            return _hint("a", "dismiss_verified_cut_learned")
        if self.stage=='forget_selected' and normalize(' '.join(rows[12:18]))=='AND':
            return _hint('a','advance_verified_cut_learning_and')
        if self.stage in {"learned", "closing"}:
            self.stage = "closing"
            if moves != self.expected_moves:
                return self._fail("cut_learned_message_without_expected_moves")
            # HM 成功回背包，僅在可辨識的選單按 B 逐層關閉。
            if self._start_menu(rows) or self._bag_hm_visible(rows):
                return _hint("b", "close_after_verified_cut_learning")
            return self._fail("cut_post_learning_screen_unrecognized")
        # 問題文字和 YES/NO 可能同幀出現，先辨識並鎖住問題，再解析游標。
        if "DELETEANOLDER" in compact or "MOVETOMAKEROOM" in compact:
            if self.stage not in {"learning_intro", "delete_question"} or not self.seen_cut_name or not self.seen_learner:
                return self._fail("cut_delete_question_without_known_learner")
            self.stage = "delete_question"
            if "YES" in compact and "NO" in compact:
                return _choose(rows, "YES", "accept_replace_growl")
            return _hint("a", "advance_wrapped_cut_delete_question") if "▼" in " ".join(rows) else self._bounded_wait("await_cut_delete_choices")
        if "TEACH" in compact and "CUT" in compact:
            if self.stage not in {"hm_dialogue", "teach_question"}:
                return self._fail("cut_unexpected_teach_question")
            self.seen_cut_name = True
            self.stage = "teach_question"
            if "YES" in compact and "NO" in compact:
                return _choose(rows, "YES", "accept_teach_cut")
            return _hint("a", "advance_wrapped_teach_cut_question") if "▼" in " ".join(rows) else self._bounded_wait("await_teach_cut_choices")
        if "YES" in compact and "NO" in compact:
            if self.stage == "teach_question" and self.seen_cut_name:
                return _choose(rows, "YES", "accept_teach_cut")
            if self.stage == "delete_question" and self.seen_cut_name and self.seen_learner:
                return _choose(rows, "YES", "accept_replace_growl")
            return self._fail("cut_yes_no_question_not_verified")
        if "TRYINGTOLEARN" in compact:
            if self.stage not in {"choose_learner", "learning_intro"} or "IVYSAUR" not in compact:
                return self._fail("cut_learning_wrong_or_unverified_learner")
            self.seen_learner = True
            self.stage = "learning_intro"
            if "CUT" in compact:
                self.seen_cut_name = True
            return _hint("a", "advance_verified_cut_learning_intro")
        if self.stage == "learning_intro" and ("THAN4MOVES" in compact or "CANTLEARNMORE" in compact
                                                or re.search(r"\bCUT[!?]?[ ▼]*$", " ".join(rows).strip())):
            return _hint("a", "advance_verified_cut_learning_capacity")
        if "BOOTEDUPANHM" in compact or "ITCONTAINED" in compact:
            if self.stage not in {"hm_selected", "hm_dialogue", "teach_question"}:
                return self._fail("cut_hm_dialogue_without_hm01_selection")
            if "ITCONTAINED" in compact:
                if not re.search(r"\bCUT\b", " ".join(rows)):
                    return self._fail("cut_hm_contained_move_not_cut")
                self.seen_cut_name = True
            self.stage = "hm_dialogue"
            return _hint("a", "advance_verified_hm01_dialogue")
        # TMHM party 頁同時驗證妙蛙草旁的 ABLE；絕不選 NOT ABLE 成員。
        if self.stage in {"teach_question", "choose_learner"} and ("USE" in compact and "ONWHICH" in compact):
            party = progress["party"]
            name_rows = [y for y, row in enumerate(rows) if "IVYSAUR" in row]
            if len(name_rows) != 1 or name_rows[0]+1 >= len(rows) or rows[name_rows[0]+1][12:].strip() != "ABLE":
                return self._fail("cut_learner_able_label_not_verified")
            result = party_choice(rows, party, self.target_index)
            if not result:
                return self._fail("cut_learner_party_cursor_unreadable")
            self.stage = "choose_learner"
            return {**result, "phase": "field_move_menu", "field_move_tactic": "choose_ivysaur_for_cut", "sources": SOURCES}
        if self._start_menu(rows) and self.stage == "start_menu":
            return _choose(rows, "ITEM", "open_hm01_bag")
        # 道具小選單會覆蓋在背包上；先處理它，避免把仍可見的 HM01 當成游標目標。
        if "USE" in compact and "TOSS" in compact and "CANCEL" in compact and self.stage == "hm_selected":
            return _choose(rows, "USE", "use_hm01")
        if (self.stage in {"start_menu", "bag", "hm_selected"}
                and any(rows[y][5] == "▶" for y in (4, 6, 8))):
            return self._verified_bag(rows, progress.get("inventory"))
        if self._bag_hm_visible(rows) and self.stage in {"start_menu", "bag", "hm_selected"}:
            result = _choose(rows, "HM01" if any("HM01" in row for row in rows) else "HM 01", "select_hm01")
            self.stage = "bag"
            if result.get("objective", "").startswith("Confirm"):
                self.stage = "hm_selected"
            return result
        return self._fail("cut_teaching_screen_unrecognized")

    def _verified_bag(self, rows, inventory):
        """只在實際背包版面、標籤、數量及唯讀順序一致時正常捲動。"""
        if (not isinstance(inventory, list) or not 1 <= len(inventory) <= 20
                or any(not isinstance(item, dict)
                       or type(item.get("item")) is not int or type(item.get("quantity")) is not int
                       or not 1 <= item["item"] <= 255 or not 1 <= item["quantity"] <= 99
                       for item in inventory)):
            return self._fail("cut_bag_inventory_unreadable")
        fingerprint = tuple((item["item"], item["quantity"]) for item in inventory)
        if len({item for item, _ in fingerprint}) != len(fingerprint):
            return self._fail("cut_bag_inventory_duplicate_item_ids")
        prior_inventory = getattr(self, "bag_inventory_fingerprint", None)
        if prior_inventory is not None and prior_inventory != fingerprint:
            return self._fail("cut_bag_inventory_changed_during_selection")
        self.bag_inventory_fingerprint = fingerprint
        hm_indices = [i for i, (item, _) in enumerate(fingerprint) if item == HM01]
        if len(hm_indices) != 1:
            return self._fail("cut_bag_hm01_not_verified")
        cursors = [(x, y) for y, row in enumerate(rows) for x, char in enumerate(row)
                   if char in {"▶", "▷"}]
        if len(cursors) != 1 or cursors[0][0] != 5 or cursors[0][1] not in (4, 6, 8):
            return self._fail("cut_bag_cursor_or_swap_marker_unverified")
        labels = _item_labels()
        visible, cancel_row = [], None
        for y in (4, 6, 8, 10):
            label = normalize(rows[y][6:19])
            if label == "CANCEL":
                cancel_row = y
                break
            matches = [(item, quantity) for item, quantity in fingerprint
                       if labels.get(item) == label and label]
            if len(matches) != 1:
                return self._fail("cut_bag_visible_item_label_unknown")
            item, quantity = matches[0]
            printed = rows[y+1][14:18].strip()
            if item in _KEY_ITEM_IDS:
                if printed:
                    return self._fail("cut_bag_key_item_quantity_layout_mismatch")
            else:
                number = re.fullmatch(r"×\s*(\d{1,2})", printed)
                if not number or int(number.group(1)) != quantity:
                    return self._fail("cut_bag_visible_quantity_mismatch")
            visible.append(item)
        if len(visible) < 2:
            return self._fail("cut_bag_too_few_verified_item_labels")
        offsets = [offset for offset in range(len(fingerprint)-len(visible)+1)
                   if [item for item, _ in fingerprint[offset:offset+len(visible)]] == visible
                   and (cancel_row is None or offset+len(visible) == len(fingerprint))]
        if len(offsets) != 1:
            return self._fail("cut_bag_visible_order_mismatch")
        offset = offsets[0]
        current_row = (cursors[0][1]-4)//2
        if current_row >= len(visible):
            return self._fail("cut_bag_cursor_not_on_item")
        current, target = offset+current_row, hm_indices[0]
        self.stage = "bag"
        evidence = {"bag_visible_item_ids": visible, "bag_visible_offset": offset,
                    "bag_cursor_inventory_index": current, "bag_hm01_inventory_index": target}
        if HM01 in visible:
            if current == target:
                self.stage = "hm_selected"
                return _hint("a", "select_verified_visible_hm01", menu_label="HM01", **evidence)
            if current > target:
                return _hint("up", "select_verified_visible_hm01", menu_label="HM01", **evidence)
        elif target <= offset+len(visible)-1:
            return self._fail("cut_bag_hm01_not_below_visible_page")
        # 不依任意未知頁猜方向；下個索引由上面的連續來源序列證明。
        previous = getattr(self, "bag_last_down_index", None)
        attempts = getattr(self, "bag_down_requests", 0)
        stagnant = getattr(self, "bag_stagnant_requests", 0)
        if previous is not None and current < previous:
            return self._fail("cut_bag_cursor_moved_backwards")
        stagnant = stagnant+1 if previous == current else 0
        if stagnant >= MAX_BAG_STAGNANT_REQUESTS:
            return self._fail("cut_bag_down_made_no_visible_progress")
        if attempts >= MAX_BAG_DOWN_REQUESTS:
            return self._fail("cut_bag_down_request_limit")
        self.bag_last_down_index, self.bag_down_requests = current, attempts+1
        self.bag_stagnant_requests = stagnant
        return _hint("down", "scroll_verified_bag_toward_hm01",
                     bag_down_requests=self.bag_down_requests,
                     bag_down_request_limit=MAX_BAG_DOWN_REQUESTS, **evidence)

    @staticmethod
    def _start_menu(rows):
        compact = normalize(" ".join(rows))
        return "POKEDEX" in compact and "POKEMON" in compact and "ITEM" in compact

    @staticmethod
    def _bag_hm_visible(rows):
        return any(re.search(r"(?:^|[ ▶▷])HM\s?01(?:[ ×x0-9]|$)", row) for row in rows)

    def _forget(self, rows, moves):
        labels = [move_key(move) for move in moves]
        if any(label is None for label in labels) or len(set(labels)) != 4:
            return self._fail("cut_forget_labels_unverifiable")
        matches = []
        for move, label in zip(moves, labels):
            found = [(x, y) for y, row in enumerate(rows) for x in range(len(row))
                     if normalize(row[x:].lstrip("▶▷ ")) == normalize(label.removesuffix("_M"))
                     and (x == 0 or row[x-1] not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ")]
            # 正常忘招選單使用固定 x=6，避免文字中同名招式或多個空白起點。
            found = [(6, y) for _, y in found if normalize(rows[y][6:]) == normalize(label.removesuffix("_M"))]
            found = list(set(found))
            if len(found) != 1:
                return self._fail("cut_forget_all_four_visible_moves_required")
            matches.append((move, found[0]))
        positions = [position for _, position in matches]
        # 固定 home/window.asm：BIT_DOUBLE_SPACED_MENU 設定時反而每項加一列；
        # learn_move.asm 設定此 bit，與 SINGLE_SPACED_LINES 的招式字串一致。
        if positions != [(6, 8+i) for i in range(4)]:
            return self._fail("cut_forget_move_order_or_layout_mismatch")
        cursors = [(x, y) for y, row in enumerate(rows) for x, char in enumerate(row) if char == "▶"]
        if len(cursors) != 1 or cursors[0][0] != 5 or cursors[0][1] not in range(8, 12):
            return self._fail("cut_forget_cursor_unreadable")
        target_y = next(position[1] for move, position in matches if move == GROWL)
        action = "a" if cursors[0][1] == target_y else "up" if cursors[0][1] > target_y else "down"
        if action == "a":
            self.stage = "forget_selected"
        return _hint(action, "forget_only_verified_growl", forgotten_move=GROWL, protected_move=VINE_WHIP)

    def _tree(self, location, grid):
        if not location or location.get("map_id") != self.intent["map_id"]:
            return None
        if not grid or grid.get("tileset_id") != self.intent.get('tileset_id',0) or grid.get("screen_cells_verified", 0) < 12:
            return None
        try:
            x, y = self.intent["tree_x"], self.intent["tree_y"]
            return grid["tiles"][y][x], grid["walkable"][y][x]
        except (IndexError, KeyError, TypeError):
            return None

    def _field_message(self):
        return _CUT_USERS[self.intent["species"]] + "HACKEDAWAYWITHCUT"

    def _field_party_choice(self, rows, party):
        """use_cut限定正常名字／來源槽位與單一active游標，不借同family成員。"""
        labels = [normalize(species_key(mon["species"])) for mon in party]
        if (len(set(labels)) != len(labels)
                or any(normalize(rows[2*i][3:13]) != label for i, label in enumerate(labels))
                or any(normalize(rows[2*i][3:13]) for i in range(len(party), 6))
                or any(sum(normalize(row[3:13]) == label for row in rows[:12]) != 1
                       for label in labels)):
            return self._fail("cut_field_party_names_or_slots_unverified")
        active = [(x, y) for y, row in enumerate(rows) for x, char in enumerate(row) if char == "▶"]
        inactive = [(x, y) for y, row in enumerate(rows) for x, char in enumerate(row) if char == "▷"]
        positions = {(0, y) for y in range(2*len(party))}
        if not active and len(inactive) == 1 and inactive[0] in positions:
            return self._bounded_wait("await_active_cut_party_cursor")
        if len(active) != 1 or active[0] not in positions or inactive:
            return self._fail("cut_field_party_cursor_unverified")
        current = active[0][1] // 2
        action = "a" if current == self.target_index else "up" if current > self.target_index else "down"
        if action == "a":
            self.field_user_confirmed = True
        return _hint(action, "choose_verified_cut_user", party_target_index=self.target_index,
                     cut_user_species=self.intent["species"], cut_user_name=_CUT_USERS[self.intent["species"]])

    def _field_cut_choice(self, rows):
        """兩種使用者都只有CUT這個已核對野外招；不確認CUTTER或錯誤選項。"""
        # start_sub_menus.asm：topY=12−2×一個field move；CUT在10，CANCEL固定16。
        labels = {"CUT": 10, "STATS": 12, "SWITCH": 14, "CANCEL": 16}
        if any(rows[y][13:].strip() != label
               or sum(bool(re.search(r"(?<![A-Z])" + label + r"(?![A-Z])", row)) for row in rows) != 1
               for label, y in labels.items()):
            return self._fail("cut_field_submenu_labels_unverified")
        active = [(x, y) for y, row in enumerate(rows) for x, char in enumerate(row) if char == "▶"]
        inactive = [(x, y) for y, row in enumerate(rows) for x, char in enumerate(row) if char == "▷"]
        positions = {(12, y) for y in labels.values()}
        # 四／六人隊子選單保留已選隊員HP列的靜態▷；六人後兩列的等級/HP被覆蓋。
        # 只接受已在真隊伍頁確認過的使用者與全部來源名字，其他游標位置仍拒絕。
        party_background = (self.field_user_confirmed is True and self.baseline is not None
            and len(self.baseline) in (4,6) and inactive==[(0,2*self.target_index+1)]
            and all(normalize(rows[2*i][3:13])==normalize(species_key(mon[0]))
                    for i,mon in enumerate(self.baseline)))
        if party_background and len(active)==1 and active[0] in positions:
            inactive=[]
        if not active and len(inactive) == 1 and inactive[0] in positions:
            return self._bounded_wait("await_active_cut_submenu_cursor")
        if len(active) != 1 or active[0] not in positions or inactive:
            return self._fail("cut_field_submenu_cursor_unverified")
        action = "a" if active[0][1] == labels["CUT"] else "up"
        self.stage = "cut_selected" if action == "a" else "cut_menu"
        return _hint(action, "select_party_cut", menu_label="CUT",
                     cut_user_species=self.intent["species"])

    def _use(self, rows, progress, moves, location, grid, overworld_ready):
        compact = normalize(" ".join(rows))
        before_tile,after_tile=_CUT_TILES[self.intent.get('tileset_id',0)]
        if CUT not in moves:
            return self._fail("cut_field_move_not_known")
        if not isinstance(progress.get("badges_raw"), int) or not progress["badges_raw"] & 2:
            return self._fail("cut_cascade_badge_not_verified")
        if moves != self.baseline[self.target_index][1]:
            return self._fail("cut_field_party_moves_changed")
        if self.stage == "initial":
            tree = self._tree(location, grid)
            if not overworld_ready or tree != (before_tile, 0):
                return self._fail("cut_tree_not_verified_in_overworld")
            dx, dy = self.intent["tree_x"]-location.get("x", -100), self.intent["tree_y"]-location.get("y", -100)
            direction = {(0, -1): "up", (0, 1): "down", (-1, 0): "left", (1, 0): "right"}.get((dx, dy))
            if direction is None or location.get("facing") != direction:
                return self._fail("cut_player_not_adjacent_and_facing_tree")
            self.start_location = {key: location[key] for key in ("map_id", "x", "y", "facing")}
            self.stage = "start_menu"
            return _hint("start", "open_party_for_cut")
        if "ANYTHINGTOCUT" in compact or "CANTUSE" in compact:
            return self._fail("cut_field_use_rejected")
        partial = self._partial_wait(rows, field=True) if not overworld_ready else None
        if partial:
            return partial
        if "HACKED" in compact and "AWAYWITHCUT" in compact:
            lower = normalize(" ".join(rows[12:18]))
            if self.stage not in {"cut_selected", "cut_animation"} or lower != self._field_message():
                return self._fail("cut_field_user_or_stage_unverified")
            if "!" not in " ".join(rows[12:18]):
                return self._bounded_wait("await_complete_cut_field_message")
            self.seen_used_cut = True
            self.stage = "cut_animation"
            return _hint("a", "advance_verified_cut_field_message")
        if self.stage == "cut_animation":
            if overworld_ready:
                tree = self._tree(location, grid)
                if any(location.get(key) != value for key, value in self.start_location.items()):
                    return self._fail("cut_verification_location_changed")
                if self.seen_used_cut and tree == (after_tile, 1):
                    return self._complete("use_cut", tree_removal_verified=True,
                                          tree_position=[self.intent["tree_x"], self.intent["tree_y"]],
                                          before_tile=before_tile, after_tile=tree[0],
                                          cut_user_species=self.intent["species"],
                                          cut_user_party_index=self.target_index)
                return self._fail("cut_tree_removal_not_verified")
            return self._fail("cut_field_animation_screen_unrecognized")
        if self._start_menu(rows) and self.stage == "start_menu":
            label = "POKÉMON" if any("POKÉMON" in row for row in rows) else "POKEMON"
            return _choose(rows, label, "open_party_for_cut")
        if "CUT" in compact and "STATS" in compact and "SWITCH" in compact and "CANCEL" in compact:
            if (self.stage not in {"choose_user", "cut_menu", "cut_selected"}
                    or not getattr(self, "field_user_confirmed", False)):
                return self._fail("cut_field_submenu_without_verified_user")
            return self._field_cut_choice(rows)
        if self.stage in {"start_menu", "choose_user"}:
            self.stage = "choose_user"
            return self._field_party_choice(rows, progress["party"])
        return self._fail("cut_field_screen_unrecognized")
