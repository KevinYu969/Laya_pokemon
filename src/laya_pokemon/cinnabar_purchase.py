"""固定紅蓮商店購買十份藥品的私人純候選，尚未接入實況。

a536711: marts.asm43-44, list_menu.asm41-52/98-104/177-195/338-424,
pokemart.asm139-198。七項商品，三個可選列；向下越第三列會scroll。
Full Heal index5為offset3/cursor2；買後offset保留、cursor歸0。
價格YES/NO框遮住第三列商品尾字；以完整先前選項與精確overlay驗證，
不得在確認頁要求不存在的完整商品字串。僅回子目標，不執行遊戲IO。
"""
from copy import deepcopy
import math

from laya_pokemon.observation import PROFILE as TEXT_PROFILE
from laya_pokemon.party_control import command
from laya_pokemon.mart_purchase import _party, _inventory, _rows, _money_field
from laya_pokemon.player_pc_deposit import _name

SOURCE_COMMIT = "a53671100ec22e5394ff26ec028d0812a238dae2"
PROFILE = "red-en-cinnabar-medicine-purchase-source-v1-candidate"
_COMMON = dict(map_id=172, player_x=2, player_y=5, facing="left", quantity=10)
HYPER_POTION_INTENT = dict(_COMMON, kind="buy_cinnabar_hyper_potion10",
                          item=18, unit_price=1500, total_price=15000)
FULL_HEAL_INTENT = dict(_COMMON, kind="buy_cinnabar_full_heal10",
                       item=52, unit_price=600, total_price=6000)
INTENTS = {18: HYPER_POTION_INTENT, 52: FULL_HEAL_INTENT}
# marts.asm43-44 / prices.asm: exact source order, not bag labels.
GOODS = ((2, "ULTRA BALL", 1200), (3, "GREAT BALL", 600),
         (18, "HYPER POTION", 1500), (57, "MAX REPEL", 700),
         (29, "ESCAPE ROPE", 550), (52, "FULL HEAL", 600),
         (53, "REVIVE", 1500))
ROSTER = {19, 132, 7, 102, 154, 35}
MINIMUM_REMAINING_MONEY = 5000
RESERVED_BAG_SLOTS = 1  # keep room for TM38, even after the second purchase
_ACTIONS = {"a", "b", "up", "down", "left", "right", "start", "wait"}


def _int(value, low=0, high=999999):
    return type(value) is int and low <= value <= high


def _intent(value):
    return (type(value) is dict and any(value == fixed and set(value) == set(fixed)
            and all(type(value[k]) is type(v) for k, v in fixed.items())
            for fixed in INTENTS.values()))


def purchase_expectation(progress, intent):
    """Only an expectation; never a substitute for an observed receipt."""
    if not _intent(intent):
        return None
    party = _party(progress)
    items = _inventory(progress.get("inventory")) if isinstance(progress, dict) else None
    money = progress.get("money") if isinstance(progress, dict) else None
    if (party is None or len(party) != 6 or {m["species"] for m in party} != ROSTER
            or any(m["hp"] <= 0 or m["status"] != 0 for m in party)
            or items is None or any(_name(i["item"]) in (None, "?????") for i in items)
            or not _int(money) or money - intent["total_price"] < MINIMUM_REMAINING_MONEY):
        return None
    after = deepcopy(items)
    existing = next((i for i in after if i["item"] == intent["item"]), None)
    if existing:
        if existing["quantity"] + 10 > 99:
            return None
        existing["quantity"] += 10
    else:
        after.append({"item": intent["item"], "quantity": 10})
    if len(after) > 20 - RESERVED_BAG_SLOTS:
        return None
    return {"party": deepcopy(party), "inventory": after,
            "money": money - intent["total_price"]}


def _view(money, layout="main", *, offset=0, cursor=0, active=True,
          quantity=10, unit=1500, dialogue="buying", label="HYPER POTION",
          arrow=False, yes=0):
    """Physical font cells; border glyphs are decoder blanks. Source only."""
    a = [[" "] * 20 for _ in range(18)]
    def put(x, y, value):
        a[y][x:x + len(value)] = list(value)
    def clear(x1, y1, x2, y2):
        for y in range(y1, y2 + 1):
            a[y][x1:x2 + 1] = [" "] * (x2 - x1 + 1)
    for y, text in ((1, "BUY"), (3, "SELL"), (5, "QUIT")):
        put(2, y, text)
    put(13, 0, "MONEY"); put(12, 1, _money_field(money))
    put(1, 1, "▶" if layout == "main" and active else "▷")
    if layout != "main":
        clear(4, 2, 19, 12)
        for row, (_, name, price) in enumerate(GOODS[offset:offset + 4]):
            put(6, 4 + row * 2, name)
            put(11, 5 + row * 2, _money_field(price))
        put(5, 4 + cursor * 2, "▶" if active and layout == "shop" else "▷")
        if arrow and layout == "shop":
            put(18, 11, "▼")
    if layout in ("quantity", "yesno"):
        clear(7, 9, 19, 11)
        put(8, 10, f"×{quantity:02}")
        put(12, 10, _money_field(quantity * unit))
    if layout == "yesno":
        clear(14, 7, 19, 11)
        put(16, 8, "YES"); put(16, 10, "NO")
        put(15, 8 + 2 * yes, "▶")
    words = {
        "greeting": ("HI THERE!", "MAY I HELP YOU?"),
        "buying": ("TAKE YOUR TIME.", ""),
        "prefix": (label + "?", "THAT WILL BE"),
        "tail": ("THAT WILL BE", f"¥{quantity * unit}. OK?"),
        "bought": ("HERE YOU ARE!", "THANK YOU!"),
        "else": ("IS THERE ANYTHING", "ELSE I CAN DO?"),
        "thanks": ("THANK YOU!", ""),
    }[dialogue]
    clear(0, 12, 19, 17)
    put(1, 14, words[0]); put(1, 16, words[1])
    if arrow and dialogue in ("prefix", "bought"):
        put(18, 16, "▼")
    return tuple("".join(row) for row in a)


def _partial(rows, expected):
    # No wildcard characters or movable arrows. Only source glyph or blank.
    return all(c == expected[y][x] or c == " "
               for y, row in enumerate(rows) for x, c in enumerate(row))


class CinnabarPurchaseController:
    """Two fixed ten-item intents; same owner must retain this instance.

    context(text,progress,*,location,battle_state,frame,now,previous,
            overworld_ready=False,intent=None). No RAM/buttons/model/IO.
    Shared _party may consult the existing public reference JSON cache.
    The wrapper must serialize these observations; optional packet frame fields,
    when supplied, must all match frame. This is not ROM authentication.
    """
    def __init__(self, intent, *, max_calls=240, max_seconds=60, max_waits=30):
        if not _intent(intent):
            raise ValueError("Only reviewed Cinnabar ten Hyper Potion / Full Heal intents")
        if (not _int(max_calls, 1, 240) or not _int(max_waits, 1, 30)
                or type(max_seconds) not in (int, float) or not math.isfinite(max_seconds)
                or not 0 < max_seconds <= 60):
            raise ValueError("Budget may only be reduced: 240 calls / 60 seconds / 30 waits")
        self.intent = deepcopy(intent)
        self.contract = deepcopy(intent)
        self._binding = tuple((k, type(v), v) for k, v in sorted(intent.items()))
        self.max_calls, self.max_seconds, self.max_waits = max_calls, max_seconds, max_waits
        self.stage, self.error, self.complete = "initial", None, False
        self.calls = self.waits = 0
        self.started = self.last_now = self.last_frame = self.last_packet = None
        self.baseline = self.expected = None
        self.pending = self.sent_rows = None
        self.selection = (0, 0)
        self.goods_expected = None
        self.selected_view = None
        self.quantity_last = 0
        self.quantity_expected = 1
        self.yes_issued = self.purchase_seen = self.receipt_seen = self.exit_seen = False
        self.thanks_start = self.world_start = None
        self.label = next(n for i, n, _ in GOODS if i == intent["item"])
        self.target = next(j for j, (i, _, _) in enumerate(GOODS) if i == intent["item"])

    def _hint(self, action, tactic, **extra):
        info = dict(cinnabar_purchase_profile=PROFILE, source_commit=SOURCE_COMMIT,
                    cinnabar_purchase_stage=self.stage, cinnabar_purchase_tactic=tactic,
                    candidate_only=True, **extra)
        if action == "wait":
            return dict(phase="mart_menu", objective="Wait.",
                        available_actions=["wait"], **info)
        return command(action, "mart_menu", info)

    def _fail(self, reason):
        if self.error is None:
            self.error = reason
        return dict(self._hint("wait", "review"), phase="campaign_review",
                    review_reason="cinnabar_purchase_" + self.error)

    def _wait(self, reason):
        self.waits += 1
        if self.waits > self.max_waits:
            return self._fail("wait_budget_exhausted")
        return self._hint("wait", reason)

    def _offer(self, action, rows, next_stage, reason):
        self.pending = {"action": action, "frame": self.last_frame, "rows": rows}
        self.sent_rows, self.stage = rows, next_stage
        return self._hint(action, reason)

    def _make(self, money, layout="main", **kw):
        return _view(money, layout, unit=self.contract["unit_price"], label=self.label, **kw)

    def _shop(self, money, selection, active=True, arrow=True):
        off, cur = selection
        return self._make(money, "shop", offset=off, cursor=cur, active=active, arrow=arrow)

    def _quantity(self, money, q, dialogue="buying", arrow=False, yes=None):
        off, cur = self.selected_view
        return self._make(money, "yesno" if yes is not None else "quantity",
                          offset=off, cursor=cur, active=False, quantity=q,
                          dialogue=dialogue, arrow=arrow, yes=0 if yes is None else yes)

    def _templates(self):
        b, a = self.baseline["money"], self.expected["money"]
        templates = []
        def add(view):
            templates.append(view)
        if self.stage == "initial":
            return [tuple(" " * 20 for _ in range(18))]
        if self.stage == "opening":
            for active in (False, True):
                add(self._make(b, dialogue="greeting", active=active))
        elif self.stage == "goods":
            add(self._make(b, dialogue="greeting", active=False))
            add(self._make(b, active=False))
            for sel in {self.selection, self.goods_expected} - {None}:
                for arrow in (False, True):
                    add(self._shop(b, sel, arrow=arrow))
        elif self.stage == "quantity":
            for q in {self.quantity_last, self.quantity_expected} - {0}:
                add(self._quantity(b, q))
        elif self.stage in ("prefix", "price"):
            add(self._quantity(b, 10))
            for arrow in (False, True):
                add(self._quantity(b, 10, "prefix", arrow))
            if self.stage == "price":
                add(self._quantity(b, 10, "tail"))
                for yes in (0, 1):
                    add(self._quantity(b, 10, "tail", yes=yes))
        elif self.stage == "receipt":
            for money in (b, a):
                for yes in (0, 1):
                    add(self._quantity(money, 10, "tail", yes=yes))
                for arrow in (False, True):
                    add(self._quantity(money, 10, "bought", arrow))
        elif self.stage == "post_receipt":
            for arrow in (False, True):
                add(self._quantity(a, 10, "bought", arrow))
                add(self._shop(a, (self.selected_view[0], 0), arrow=arrow))
            add(self._make(a, active=False))
        elif self.stage == "return_main":
            for arrow in (False, True):
                add(self._shop(a, (self.selected_view[0], 0), arrow=arrow))
            for active in (False, True):
                add(self._make(a, dialogue="else", active=active))
            add(self._make(a, active=False))
        elif self.stage in ("closing", "exit"):
            for active in (False, True):
                add(self._make(a, dialogue="else", active=active))
            add(self._make(a, dialogue="thanks", active=False))
            if self.stage == "exit":
                add(tuple(" " * 20 for _ in range(18)))
        return templates

    def context(self, text, progress, *, location, battle_state, frame, now, previous,
                overworld_ready=False, intent=None):
        if self.error:
            return self._fail(self.error)
        if self.complete:
            return dict(self._hint("wait", "latched_complete"), cinnabar_purchase_complete=True,
                        item=self.contract["item"], quantity_purchased=10,
                        money_spent=self.contract["total_price"],
                        evidence_scope="completed original transaction; later packets not revalidated")
        self.calls += 1
        if (not _intent(self.intent) or self.intent != self.contract
                or tuple((k, type(v), v) for k, v in sorted(self.contract.items())) != self._binding
                or intent is not None and (not _intent(intent) or intent != self.contract)):
            return self._fail("intent_changed")
        if (not _int(frame, 0, 0x7fffffffffffffff) or type(now) not in (int, float) or not math.isfinite(now) or now < 0
                or self.last_frame is not None and frame < self.last_frame
                or self.last_now is not None and now < self.last_now):
            return self._fail("clock_or_frame_invalid")
        if self.started is None:
            self.started = now
        if self.calls > self.max_calls or now - self.started > self.max_seconds:
            return self._fail("time_or_call_budget_exhausted")
        if (type(previous) not in (list, tuple) or any(type(p) is not str or p not in _ACTIONS for p in previous)
                or type(overworld_ready) is not bool):
            return self._fail("actual_previous_or_ready_unverified")
        rows = _rows(text)
        if (rows is None or text.get("profile") != TEXT_PROFILE or text.get("read_valid") is not True
                or text.get("alignment_verified") is not True or text.get("read_error") is not None
                or type(text.get("window_visible")) is not bool):
            return self._fail("decoder_proof_required")
        for packet in (text, progress, location, battle_state):
            if not isinstance(packet, dict) or ("observation_frame" in packet and
                    (type(packet["observation_frame"]) is not int or packet["observation_frame"] != frame)):
                return self._fail("same_frame_proof_required")
        if (any(type(location.get(k)) is not int or location[k] != v
                for k, v in (("map_id", 172), ("x", 2), ("y", 5), ("facing_raw", 8)))
                or location.get("facing") != "left"):
            return self._fail("stance_changed_or_unknown")
        if (battle_state.get("active") is not False or battle_state.get("kind") != "none"
                or type(battle_state.get("raw")) is not int or battle_state["raw"] != 0):
            return self._fail("known_nonbattle_required")
        party, items = _party(progress), _inventory(progress.get("inventory"))
        money = progress.get("money")
        if party is None or items is None or not _int(money):
            return self._fail("progress_invalid")
        packet = deepcopy((text, progress, location, battle_state, previous, overworld_ready))
        if frame == self.last_frame:
            if packet != self.last_packet:
                return self._fail("same_frame_conflict")
            self.last_now = now
            return self._wait("duplicate_frame_no_repeat")
        self.last_frame, self.last_now, self.last_packet = frame, now, packet
        if self.baseline is None:
            self.expected = purchase_expectation(progress, self.contract)
            if self.expected is None:
                return self._fail("baseline_money_bag_or_party_invalid")
            self.baseline = deepcopy({"party": party, "inventory": items, "money": money})
        if party != self.baseline["party"]:
            return self._fail("party_changed")
        before = items == self.baseline["inventory"] and money == self.baseline["money"]
        after = items == self.expected["inventory"] and money == self.expected["money"]
        intermediate = items == self.expected["inventory"] and money == self.baseline["money"]
        if not self.yes_issued and not before:
            return self._fail("data_changed_before_yes")
        if self.yes_issued and not (after or not self.purchase_seen and (before or intermediate)):
            return self._fail("transaction_delta_invalid")
        if self.yes_issued and after:
            self.purchase_seen = True
        if not any(_partial(rows, view) for view in self._templates()):
            return self._fail("unknown_viewport_or_polluted_page")
        if self.stage == "initial":
            if any(row.strip() for row in rows) or text["window_visible"] or not overworld_ready:
                return self._fail("initial_closed_world_required")
            return self._offer("a", rows, "opening", "talk_to_fixed_clerk")
        if self.pending:
            if not previous or previous[-1] != self.pending["action"]:
                if rows == self.pending["rows"] or not any(r.strip() for r in rows):
                    return self._wait("actual_action_receipt_pending")
                return self._fail("changed_page_without_actual_action")
            self.pending = None
        if rows == self.sent_rows:
            return self._wait("prior_page_no_repeat")
        b, a = self.baseline["money"], self.expected["money"]
        if self.stage == "opening":
            if rows == self._make(b, dialogue="greeting"):
                return self._offer("a", rows, "goods", "choose_only_buy")
        elif self.stage == "goods":
            matches = [sel for sel in {self.selection, self.goods_expected} - {None}
                       if any(rows == self._shop(b, sel, arrow=arrow) for arrow in (False, True))]
            if matches:
                sel = matches[0]
                if self.goods_expected is not None:
                    if sel == self.selection:
                        return self._wait("old_goods_after_direction")
                    self.selection, self.goods_expected = sel, None
                off, cur = self.selection
                if off + cur == self.target:
                    self.selected_view = self.selection
                    return self._offer("a", rows, "quantity", "select_only_verified_medicine")
                self.goods_expected = (off, cur + 1) if cur < 2 else (off + 1, cur)
                return self._offer("down", rows, "goods", "move_one_source_goods_entry")
        elif self.stage == "quantity":
            if rows == self._quantity(b, self.quantity_expected):
                self.quantity_last = self.quantity_expected
                if self.quantity_last == 10:
                    return self._offer("a", rows, "prefix", "confirm_exact_ten_and_total")
                self.quantity_expected += 1
                return self._offer("up", rows, "quantity", "increment_quantity_once")
            if self.quantity_last and rows == self._quantity(b, self.quantity_last):
                return self._wait("quantity_direction_pending")
        elif self.stage == "prefix":
            if rows == self._quantity(b, 10, "prefix", True):
                return self._offer("a", rows, "price", "ack_true_price_scroll_prompt")
        elif self.stage == "price":
            if rows == self._quantity(b, 10, "tail", yes=1):
                return self._offer("up", rows, "price", "select_price_yes")
            if rows == self._quantity(b, 10, "tail", yes=0):
                self.yes_issued = True
                return self._offer("a", rows, "receipt", "purchase_once_at_exact_total")
        elif self.stage == "receipt":
            if rows == self._quantity(a, 10, "bought", True) and after:
                self.receipt_seen = True
                return self._offer("a", rows, "post_receipt", "ack_true_bought_prompt")
        elif self.stage == "post_receipt":
            if any(rows == self._shop(a, (self.selected_view[0], 0), arrow=arrow) for arrow in (False, True)):
                if not after or not self.receipt_seen:
                    return self._fail("post_receipt_without_accounting")
                return self._offer("b", rows, "return_main", "leave_buy_list_once")
        elif self.stage == "return_main":
            if rows == self._make(a, dialogue="else"):
                return self._offer("b", rows, "closing", "quit_main_once")
        elif self.stage == "closing":
            if rows == self._make(a, dialogue="thanks", active=False):
                if self.thanks_start is None:
                    self.thanks_start = frame
                if frame - self.thanks_start >= 16:
                    self.exit_seen = True
                    return self._offer("a", rows, "exit", "close_stable_done_after_outer_wait")
                return self._wait("thanks_done_stable16")
            self.thanks_start = None
        elif self.stage == "exit":
            blank = not any(r.strip() for r in rows)
            if blank and text["window_visible"] is False and overworld_ready:
                if not (after and self.receipt_seen and self.exit_seen and self.purchase_seen):
                    return self._fail("closed_world_without_receipts")
                if self.world_start is None:
                    self.world_start = frame
                    return self._wait("second_fresh_closed_world_required")
                if frame - self.world_start >= 3:
                    self.complete, self.stage = True, "complete"
                    return dict(self._hint("wait", "purchase_complete_observed"),
                                cinnabar_purchase_complete=True, item=self.contract["item"],
                                quantity_purchased=10, money_spent=self.contract["total_price"],
                                money_after=a, receipt_observation_frame=frame)
            self.world_start = None
        return self._wait("known_source_printing_or_native_transition")

