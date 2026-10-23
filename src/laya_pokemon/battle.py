"""第一場對戰的唯讀選單提示；不執行按鍵，也不是完整戰術模型。"""
from __future__ import annotations

from numbers import Integral
import re


# wram.asm: wIsInBattle、單 byte wPartyGainExpFlags、wCurOpponent；後者由 PyBoy 定位 D059。
BATTLE_STATE_ADDRESS = 0xD057
SOURCE = "https://github.com/pret/pokered/blob/master/ram/wram.asm"
MENU_SOURCE = "https://github.com/pret/pokered/blob/master/engine/battle/core.asm"


def read_battle_state(pyboy) -> dict:
    """只讀旗標；未知值不當作非戰鬥，亦不從此旗標推論勝利。"""
    raw = pyboy.memory[BATTLE_STATE_ADDRESS]
    if not isinstance(raw, Integral) or isinstance(raw, bool) or not 0 <= raw <= 255:
        raise ValueError("戰鬥旗標不是 byte")
    raw = int(raw)
    return {"raw": raw, "active": raw in (1, 2) if raw in (0, 1, 2, 255) else None,
            "kind": {0: "none", 1: "wild", 2: "trainer", 255: "lost_transition"}.get(raw, "unknown"),
            "source": SOURCE, "victory_confirmed": None}


def _label(rows, label):
    matches = [(row.index(label), y) for y, row in enumerate(rows[12:], 12) if label in row]
    return matches[0] if len(matches) == 1 else None


def _selection_hint(rows, target, menu):
    cursors = [(x, y) for y, row in enumerate(rows[12:], 12) for x, c in enumerate(row) if c == "▶"]
    if len(cursors) != 1:
        return {"phase": "battle_menu", "objective": "Wait for a readable menu cursor.",
                "available_actions": ["wait", "b"], "battle_menu": menu,
                "phase_source": "local battle cursor parser; unreadable cursor"}
    x, y = cursors[0]
    tx, ty = target
    if y != ty:
        objective = "Move UP." if y > ty else "Move DOWN."
    elif x + 1 != tx:
        objective = "Move LEFT." if x + 1 > tx else "Move RIGHT."
    else:
        objective = "Confirm the current selection."
    return {"phase": "battle_menu", "objective": objective,
            "available_actions": ["a", "b"] if objective.startswith("Confirm") else ["up", "down", "left", "right", "wait"],
            "battle_menu": menu, "battle_target_tile": list(target), "battle_cursor_tile": list(cursors[0]),
            "phase_source": "local visible battle menu parser; subgoal supplied by controller",
            "battle_strategy": "early-game FIGHT/TACKLE baseline with low-HP wild retreat; not a general battle strategy", "source": MENU_SOURCE}


def battle_context(text, battle_state) -> dict | None:
    """僅對已核對 ROM 的實驗性 lab_rival 階段提供局部提示。"""
    if battle_state["active"] is not True:
        return None
    cells = text.get("cells", [])
    if len(cells) == 18 and all(len(row) == 20 for row in cells):
        rows = ["".join(row).upper() for row in cells]
        # 玩家 HP 顯示在右側 HUD；排除左下的招式 PP，亦避免使用可能落後的 party HP。
        health = []
        for row in rows[8:12]:
            match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", row[10:])
            if match:
                hp, maximum = map(int, match.groups())
                if 0 <= hp <= maximum and maximum > 0:
                    health.append({"hp": hp, "max_hp": maximum})
        retreat = (battle_state.get("kind") == "wild" and len(health) == 1
                   and health[0]["hp"] * 2 <= health[0]["max_hp"])
        fight, item, run = (_label(rows, word) for word in ("FIGHT", "ITEM", "RUN"))
        if fight and item and run:
            result = _selection_hint(rows, run if retreat else fight, "command")
            result.update(battle_tactic="retreat" if retreat else "damage", visible_player_hp=health)
            return result
        tackle, growl = (_label(rows, word) for word in ("TACKLE", "GROWL"))
        if tackle and growl and tackle[0] == growl[0] and tackle[1] != growl[1]:
            if retreat:
                return {"phase": "battle_menu", "objective": "Cancel and return to the battle command menu.",
                        "available_actions": ["b", "wait"], "battle_tactic": "retreat",
                        "visible_player_hp": health, "phase_source": "visible wild-battle HP at or below half; controller retreat rule"}
            return _selection_hint(rows, tackle, "moves")
    if any(y >= 12 for y in text.get("line_rows", [])):
        return {"phase": "battle_dialogue", "objective": "Advance the visible dialogue with the confirm button.",
                "available_actions": ["a", "wait"], "phase_source": "battle flag and visible lower dialogue"}
    return {"phase": "battle_animation", "objective": "Wait.", "available_actions": ["wait", "a"],
            "phase_source": "battle flag; no readable lower dialogue"}
