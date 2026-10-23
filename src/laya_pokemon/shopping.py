"""常磐商店補球的可見選單子目標；只買單顆，背包數量作為持久進度。"""
import re


def ball_count(inventory):
    return None if inventory is None else sum(item["quantity"] for item in inventory if item["item"] == 4)


def shopping_context(text, inventory, money, target=8):
    balls = ball_count(inventory)
    if balls is None or money is None:
        return {"phase": "strategy_review", "review_reason": "inventory_or_money_unknown"}
    rows = ["".join(row).upper() for row in text.get("cells", [])]
    upper = " ".join(rows)

    def hint(objective, actions):
        return {"phase": "shop_menu", "objective": objective, "available_actions": actions,
                "ball_count": balls, "target_balls": target, "phase_source": "local visible shop parser; buy one POKE BALL at a time"}

    if balls >= target:
        return hint("Cancel and close this menu.", ["b", "a"]) if (
            any(word in upper for word in ("BUY", "SELL", "QUIT", "BALL", "YES", "HOW MANY"))
            or any(y >= 12 for y in text.get("line_rows", []))) else None
    if money < 200:
        return {"phase": "strategy_review", "review_reason": "insufficient_money_for_poke_ball"}
    if "SELL" in upper and "QUIT" in upper and "BUY" in upper:
        for y, row in enumerate(rows):
            if "BUY" in row:
                x = row.index("BUY")
                cursors = [cy for cy, candidate in enumerate(rows) if x > 0 and candidate[x - 1] == "▶"]
                if len(cursors) == 1:
                    return hint("Confirm the current selection." if cursors[0] == y else "Move UP.",
                                ["a", "b"] if cursors[0] == y else ["up", "down", "wait"])
        return hint("Wait for a readable menu cursor.", ["wait", "b"])
    # 只讀到數量 01 才確認，避免沿用上一筆意外大量購買。
    if "HOW MANY" in upper or "×" in upper and "BALL" in upper:
        if any(re.search(r"[×X]\s*0?1\b", row) for row in rows):
            return hint("Confirm the current selection.", ["a", "b"])
        return {"phase": "strategy_review", "review_reason": "purchase_quantity_not_verified_one"}
    if "YES" in upper and "NO" in upper:
        for y, row in enumerate(rows):
            if "YES" in row:
                x = row.index("YES")
                if x > 0 and row[x - 1] == "▶":
                    return hint("Confirm the current selection.", ["a", "b"])
        return hint("Move UP.", ["up", "down", "wait"])
    for y, row in enumerate(rows[:12]):
        match = re.search(r"POK[ÉE] BALL", row)
        if match:
            x = match.start()
            cursors = [cy for cy, candidate in enumerate(rows[:12]) if x > 0 and candidate[x - 1] == "▶"]
            if len(cursors) == 1:
                return hint("Confirm the current selection." if cursors[0] == y else "Move UP." if cursors[0] > y else "Move DOWN.",
                            ["a", "b"] if cursors[0] == y else ["up", "down", "wait"])
    return None  # 一般對話交原來的可見文字解析；不憑猜測切到其他商品。
