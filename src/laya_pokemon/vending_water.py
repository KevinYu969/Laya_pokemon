"""玉虹屋頂只買一瓶FRESH WATER的純候選；不接遊戲或交易橋接。
固定pret/pokered a53671100ec22e5394ff26ec028d0812a238dae2。
來源GiveItem先加物品，至少120幀送貨後才扣200及重畫錢框；外層
AfterDisplayingTextID仍等一次按鍵。這些是來源契約，尚非實況校準。
"""
from copy import deepcopy
import math
import re

from .party_control import command
from .mart_purchase import _party, _inventory
from .team_strategy import reference, move_key

SOURCE_COMMIT = "a53671100ec22e5394ff26ec028d0812a238dae2"
TEXT_PROFILE = "gen1-visible-tile-text-candidates-v1-unvalidated"
INTENT = dict(kind="buy_fresh_water", map_id=126, player_x=11, player_y=2,
              facing="up", item=60, quantity=1, unit_price=200, total_price=200)
MAX_SECONDS, MAX_CALLS, MAX_WAITS, MIN_DELIVERY_FRAMES = 60, 240, 120, 120
_S = "\ue101"  # 原生單一's tile；只供來源HERE's/T(H)ERE's兩個字位。
_SOURCE_PATHS = (
    "engine/events/vending_machine.asm", "text/CeladonMartRoof.asm#L129",
    "scripts/CeladonMartRoof.asm", "data/maps/objects/CeladonMartRoof.asm",
    "data/items/vending_prices.asm", "home/give.asm", "engine/items/inventory.asm",
    "home/text_script.asm#L83", "engine/menus/text_box.asm#L130",
    "data/text_boxes.asm#L35", "home/print_bcd.asm",
)
SOURCES = [f"https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/{p}" for p in _SOURCE_PATHS]
_INTRO = ("A VENDING MACHINE!", "HERE'S THE MENU!")
_RECEIPT = ("FRESH WATER", "POPPED OUT!")
_FAILURES = (("OOPS, NOT ENOUGH", "MONEY!"), ("THERE'S NO MORE", "ROOM FOR STUFF!"),
             ("NOT THIRSTY!", ""))


def _integer(v, low, high):
    return type(v) is int and low <= v <= high


def _rows(text):
    if (not isinstance(text, dict) or text.get("profile") != TEXT_PROFILE
            or text.get("read_valid") is not True or text.get("alignment_verified") is not True
            or text.get("read_error") is not None or type(text.get("window_visible")) is not bool):
        return None
    cells = text.get("cells")
    if (not isinstance(cells, (list, tuple)) or len(cells) != 18
            or any(not isinstance(row, (list, tuple)) or len(row) != 20 for row in cells)):
        return None
    rows, contractions = [], []
    for y, row in enumerate(cells):
        value = []
        for x, cell in enumerate(row):
            if cell == "'s" and y in (14, 16):
                contractions.append((x, y))
                value.append(_S)
            elif (isinstance(cell, str) and len(cell) == 1 and cell != _S
                  and (cell == " " or cell in "éÉ'(),.!?¥▶▷▼"
                       or cell.isascii() and cell.isalnum())):
                value.append(cell.upper())
            else:
                return None
        rows.append("".join(value))
    for x, y in contractions:
        if rows[y][:x].strip() not in ("HERE", "THERE"):
            return None
    native_rows = ["".join(row).rstrip() for row in cells]
    pairs = [(i, r) for i, r in enumerate(native_rows) if re.search(r"[A-Za-z0-9]{2,}", r)][:12]
    if ("lines" in text and text["lines"] != [r for _, r in pairs]
            or "line_rows" in text and text["line_rows"] != [i for i, _ in pairs]):
        return None
    return tuple(rows)


def _screen():
    return [[" "] * 20 for _ in range(18)]


def _put(r, x, y, label):
    value = label.upper().replace("'S", _S)
    if x + len(value) > 20:
        raise ValueError("source row overflow")
    r[y][x:x + len(value)] = list(value)


def _serialized(r):
    return tuple("".join(row) for row in r)


def _money(r, value):
    _put(r, 13, 0, "MONEY")
    _put(r, 12, 1, f"¥{value}".rjust(7))


def _dialog(lines, *, menu=None, money=None, arrow=None):
    r = _screen()
    if money is not None:
        _money(r, money)
    if menu is not None:
        for y, label in ((5, "FRESH WATER"), (7, "SODA POP"), (9, "LEMONADE"), (11, "CANCEL")):
            _put(r, 2, y, label)
        for y, price in ((6, 200), (8, 300), (10, 350)):
            _put(r, 9, y, f"¥{price}")
        _put(r, 1, menu, "▶")
    _put(r, 1, 14, lines[0])
    _put(r, 1, 16, lines[1])
    if arrow is not None:
        _put(r, 18, arrow, "▼")
    return _serialized(r)


def _subset(rows, template):
    return all(a == " " or a == b for line, want in zip(rows, template) for a, b in zip(line, want))


def _valid_party(p):
    party = _party(p)
    if party is None or len({m["species"] for m in party}) != len(party):
        return None
    ref = reference()
    if ref.get("source_commit") != SOURCE_COMMIT:
        return None
    for mon in party:
        if mon["status"] not in (*range(8), 8, 16, 32, 64):
            return None
        for move, pp in zip(mon["moves"], mon["pp"]):
            name = move_key(move) if move else None
            if (not move and pp or move and
                    (name is None or (pp & 63) > ref["moves"][name]["pp"] * (5 + (pp >> 6)) // 5)):
                return None
    return party


def water_expectation(progress):
    """只算來源預期差異，不把預期字典冒充真實購買結果。"""
    if _valid_party(progress) is None or _inventory(progress.get("inventory")) is None:
        return None
    money = progress.get("money")
    if not _integer(money, 200, 999999):
        return None
    items = deepcopy(progress["inventory"])
    water = next((v for v in items if v["item"] == 60), None)
    if water:
        if water["quantity"] == 99:
            return None  # 來源可能拆stack，這個一瓶契約不支援。
        water["quantity"] += 1
    elif len(items) == 20:
        return None
    else:
        items.append({"item": 60, "quantity": 1})
    return dict(party=deepcopy(progress["party"]), inventory=items, money=money - 200)


class VendingWaterController:
    """每個明確意圖只建一次；不得因檢討而重建基線重新購買。

    context(text, progress, *, location, battle_state, frame, now,
            overworld_ready=False)。location必含126/11/2/facing=up，
    optional facing_raw若有須4；frame為真遊戲觀測幀，不是action計數。
    只回Laya子目標，不發按鍵／讀寫RAM／呼叫模型。公開reference helper
    只讀既有封裝參考資料，不讀遊戲。需由父層獨審後另接bridge。
    """

    def __init__(self, intent):
        if (not isinstance(intent, dict) or intent != INTENT
                or any(type(intent.get(k)) is not type(v) for k, v in INTENT.items())):
            raise ValueError("僅允許map126固定站位買一瓶FreshWater60／200")
        self.intent = deepcopy(intent)
        self.stage, self.error, self.baseline, self.expected = "initial", None, None, None
        self.started = self.last_now = self.last_frame = self.last_packet = None
        self.calls = self.waits = 0
        self.intro_ack = self.purchase_issued = self.delivery_observed = self.paid_observed = False
        self.receipt_ack = False
        self.purchase_frame = self.closed_frame = None
        self.pending_cursor = None

    def _fail(self, reason):
        self.error = "vending_water_" + reason.removeprefix("vending_water_")
        return {"phase": "campaign_review", "objective": "Wait.", "available_actions": ["wait"],
                "review_reason": self.error, "vending_water_stage": self.stage,
                "vending_water_purchase_issued": self.purchase_issued,
                "vending_water_delivery_observed": self.delivery_observed,
                "vending_water_paid_observed": self.paid_observed,
                "source_commit": SOURCE_COMMIT, "sources": SOURCES}

    def _wait(self, reason):
        self.waits += 1
        if self.waits > MAX_WAITS:
            return self._fail("source_wait_budget_exhausted")
        return {"phase": "vending_water", "objective": "Wait.", "available_actions": ["wait"],
                "vending_water_tactic": reason, "source_waits": self.waits,
                "source_commit": SOURCE_COMMIT}

    def _send(self, action, reason):
        return command(action, "vending_water", {
            "vending_water_tactic": reason, "source_commit": SOURCE_COMMIT, "sources": SOURCES})

    def _progress(self, p):
        party, inv = _valid_party(p), _inventory(p.get("inventory"))
        if party is None or inv is None or not _integer(p.get("money"), 0, 999999):
            return "upstream_fingerprint_invalid"
        identity = {k: deepcopy(p[k]) for k in ("player_name_raw", "badges_raw", "party_count") if k in p}
        if ("badges_raw" in identity and not _integer(identity["badges_raw"], 0, 255)
                or "player_name_raw" in identity and not isinstance(identity["player_name_raw"], str)):
            return "identity_invalid"
        if self.baseline is None:
            expected = water_expectation(p)
            if expected is None:
                return "insufficient_money_full_bag_or_water_stack99"
            self.baseline = deepcopy(dict(party=party, inventory=inv, money=p["money"], identity=identity))
            self.expected = expected
        base = self.baseline
        if party != base["party"] or identity != base["identity"]:
            return "party_or_identity_changed"
        same = inv == base["inventory"] and p["money"] == base["money"]
        delivered = inv == self.expected["inventory"] and p["money"] == base["money"]
        paid = inv == self.expected["inventory"] and p["money"] == self.expected["money"]
        if not self.purchase_issued:
            if not same:
                return "change_before_single_purchase"
        else:
            if not (same or delivered or paid):
                return "inventory_or_price_not_exactly_one_water"
            if self.delivery_observed and same:
                return "delivered_water_reverted"
            if self.paid_observed and not paid:
                return "paid_transaction_reverted_or_refunded"
            if delivered or paid:
                self.delivery_observed = True
            if paid:
                self.paid_observed = True
        return None

    def context(self, text, progress, *, location, battle_state, frame, now, overworld_ready=False):
        if self.error:
            return self._fail(self.error)
        self.calls += 1
        if self.intent != INTENT or any(type(self.intent.get(k)) is not type(v) for k, v in INTENT.items()):
            return self._fail("intent_changed")
        if (type(now) not in (int, float) or not math.isfinite(now) or now < 0
                or self.last_now is not None and now < self.last_now):
            return self._fail("clock_invalid")
        if self.started is None:
            self.started = now
        if self.calls > MAX_CALLS or now - self.started > MAX_SECONDS:
            return self._fail("transaction_budget_exhausted")
        self.last_now = now
        if (not _integer(frame, 0, 0x7FFFFFFFFFFFFFFF)
                or self.last_frame is not None and frame < self.last_frame):
            return self._fail("frame_invalid_or_regressed")
        if (not isinstance(progress, dict) or not isinstance(location, dict)
                or type(overworld_ready) is not bool
                or any(type(location.get(k)) is not int for k in ("map_id", "x", "y"))
                or (location["map_id"], location["x"], location["y"], location.get("facing")) != (126, 11, 2, "up")
                or "facing_raw" in location and (type(location["facing_raw"]) is not int or location["facing_raw"] != 4)):
            return self._fail("fixed_stance_or_facing_unverified")
        if (not isinstance(battle_state, dict) or battle_state.get("kind") != "none"
                or battle_state.get("active") is not False
                or type(battle_state.get("raw")) is not int or battle_state["raw"] != 0):
            return self._fail("nonbattle_not_verified")
        for packet in (text, progress, location, battle_state):
            if not isinstance(packet, dict) or ("observation_frame" in packet and
                    (type(packet["observation_frame"]) is not int or packet["observation_frame"] != frame)):
                return self._fail("observation_frame_conflict")
        rows = _rows(text)
        if rows is None:
            return self._fail("full_native_decoder_required")
        error = self._progress(progress)
        if error:
            return self._fail(error)
        packet = deepcopy((text, progress, location, battle_state, overworld_ready))
        if self.last_frame == frame:
            if packet != self.last_packet:
                return self._fail("same_frame_packet_conflict")
            return self._wait("same_frame_no_resend")
        self.last_frame, self.last_packet = frame, packet
        blank = rows == (" " * 20,) * 18
        if self.stage == "initial":
            if not overworld_ready or text["window_visible"] or not blank:
                return self._fail("initial_canonical_closed_world_required")
            self.stage = "intro"
            return self._send("a", "inspect_verified_vending_bg")
        if blank:
            if self.receipt_ack and overworld_ready and text["window_visible"] is False:
                if not self.paid_observed:
                    return self._fail("world_without_paid_receipt")
                if self.closed_frame is None:
                    self.closed_frame = frame
                    return self._wait("first_closed_world_frame")
                if frame > self.closed_frame:
                    self.stage = "complete"
                    return self._complete()
            if overworld_ready:
                return self._fail("premature_world_or_unpaid_exit")
            self.closed_frame = None
            return self._wait("source_canonical_transition_blank")
        self.closed_frame = None
        if overworld_ready:
            return self._fail("world_assertion_conflicts_with_text")
        if self.stage == "complete":
            return self._fail("complete_screen_changed")
        old_money = self.baseline["money"]
        new_money = self.expected["money"]
        # 完整錯誤頁一律檢討，沒有「退款」或自動重新購買分支。
        failure_templates = [
            _dialog(lines, menu=5 if self.intro_ack else None,
                    money=old_money if self.intro_ack else None, arrow=arrow)
            for lines in _FAILURES for arrow in (None, 16, 17)]
        if rows in failure_templates:
            return self._fail("source_purchase_failure_or_cancel")
        intro_templates = [_dialog(_INTRO, arrow=a) for a in (None, 16, 17)]
        if rows in intro_templates:
            if self.stage != "intro":
                return self._wait("prior_intro_no_resend")
            if self.intro_ack:
                return self._wait("intro_ack_pending")
            # 此頁是prompt：全文可先於真正提示箭頭印完；早A可能只加速文字。
            # 不以全文或錯列17冒充WaitForTextScrollButtonPress已可接收。
            if rows != _dialog(_INTRO, arrow=16):
                return self._wait("await_intro_real_prompt_arrow")
            self.intro_ack, self.stage = True, "menu"
            return self._send("a", "advance_full_vending_intro_once")
        menus = [(y, _dialog(_INTRO, menu=y, money=old_money, arrow=a))
                 for y in (5, 7, 9, 11) for a in (None, 16, 17)]
        match = next((y for y, template in menus if rows == template), None)
        if match is not None:
            if not self.intro_ack:
                return self._fail("menu_without_own_intro_baseline")
            if self.purchase_issued:
                if match != 5 or self.paid_observed:
                    return self._fail("old_menu_changed_after_purchase")
                return self._wait("single_purchase_delivery_no_resend")
            if self.stage != "menu":
                return self._fail("unexpected_menu")
            if self.pending_cursor is not None:
                previous, expected = self.pending_cursor
                if match == previous:
                    return self._wait("direction_pending_no_resend")
                if match != expected:
                    return self._fail("cursor_did_not_move_one_source_row")
                self.pending_cursor = None
            if match != 5:
                self.pending_cursor = (match, match - 2)
                return self._send("up", "move_only_toward_fresh_water")
            self.purchase_issued, self.purchase_frame, self.stage = True, frame, "delivery"
            return self._send("a", "purchase_single_fresh_water_once")
        receipts = [(money, _dialog(_RECEIPT, menu=5, money=money, arrow=a))
                    for money in (old_money, new_money) for a in (None, 16, 17)]
        receipt_money = next((money for money, template in receipts if rows == template), None)
        if receipt_money is not None:
            if not self.purchase_issued or not self.delivery_observed:
                return self._fail("receipt_without_own_delivery")
            if frame - self.purchase_frame < MIN_DELIVERY_FRAMES:
                return self._fail("receipt_before_source_delivery_minimum")
            if self.receipt_ack:
                return self._wait("outer_receipt_ack_pending_no_resend")
            if not self.paid_observed or receipt_money != new_money:
                return self._wait("await_source_debit_and_money_redraw")
            self.receipt_ack, self.stage = True, "closing"
            # text5內done自動回返，但外層AfterDisplayingTextID仍WaitForTextScrollButtonPress。
            return self._send("a", "close_paid_full_popped_out_once")
        # 部分頁只可出現在精確來源遮罩，且永遠不確認。
        allowed = []
        if self.stage in {"intro", "menu"}:
            allowed += intro_templates
            if self.intro_ack:
                allowed += [t for _, t in menus]
                allowed += [_dialog(_INTRO, money=old_money)]
        if self.stage == "delivery":
            allowed += [t for y, t in menus if y == 5 and not self.paid_observed]
            allowed += [t for _, t in receipts]
        if self.stage == "closing":
            allowed += [t for _, t in receipts]
        if any(_subset(rows, template) for template in allowed):
            return self._wait("source_partial_no_input")
        return self._fail("unknown_or_polluted_source_page")

    def _complete(self):
        return {"phase": "vending_water_complete", "objective": "Wait.", "available_actions": ["wait"],
                "vending_water_complete": True, "item_purchased": 60, "quantity_purchased": 1,
                "money_spent": 200, "purchase_frame": self.purchase_frame,
                "first_closed_frame": self.closed_frame, "closed_observation_frame": self.last_frame,
                "source_commit": SOURCE_COMMIT, "sources": SOURCES}

