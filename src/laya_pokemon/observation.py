"""唯讀的 Gen I 可見 tile 文字候選；不執行任何遊戲操作。"""
from __future__ import annotations

import re
from collections.abc import Mapping


PROFILE = "gen1-visible-tile-text-candidates-v1-unvalidated"
_WORD = re.compile(r"[A-Za-z0-9]{2,}")
_PRINTABLE = re.compile(r"[A-Za-z0-9 é'():;\[\]#?!.▷▶▼♂¥×/,\-♀]+")


def _source_at(x: int, y: int, position, window_enabled: bool):
    scx, scy, wx, wy = map(int, position)
    if window_enabled and y >= wy and x >= wx and wy < 144 and wx < 160:
        return "window", x - wx, y - wy
    return "background", (x + scx) % 256, (y + scy) % 256


def read_visible_text(pyboy, decoding: Mapping[int, str] | None = None) -> dict:
    """解碼完整出現在 20×18 螢幕格的 tile，略過不對齊或跨層的格子。

    這是字碼候選而非 OCR：尚未核對字型外觀，也不重建 sprite 遮罩。
    read_valid／alignment_verified只證明本次完整格讀取與對齊，不能把略過的
    空白當作野外；window_visible另外記錄是否有任何可見Window像素。
    ``decoding`` 可供不載入 PyBoy 的合成測試使用。
    """
    result = {"lines": [], "line_rows": [], "cells": [], "warnings": [
        "文字候選依 tilemap 字碼推測，尚未完全校準；未核對字型外觀或 sprite 遮罩。"
    ], "profile": PROFILE, "read_valid": False, "alignment_verified": False,
        "window_visible": None, "read_error": None}
    try:
        lcdc = pyboy.memory[0xFF40]
    except Exception:
        result["read_error"] = "visible_lcdc_getter_failed"
        return result
    if type(lcdc) is not int or not 0 <= lcdc <= 255:
        result["read_error"] = "visible_lcdc_invalid"
        return result
    # 紅／藍版的 DMG 模式：bit 7 關閉 LCD；bit 0 關閉背景與視窗。
    if not lcdc & 0x80 or not lcdc & 0x01:
        result["read_error"] = "visible_display_disabled"
        return result
    if decoding is None:
        from pyboy.plugins.game_wrapper_pokemon_gen1_constants import POKEMON_TEXT_DECODING
        decoding = POKEMON_TEXT_DECODING
    try:
        positions = pyboy.screen.tilemap_position_list
    except Exception:
        result["read_error"] = "visible_scanline_getter_failed"
        return result
    # PyBoy提供SCX/SCY原始byte，以及WX-7/WY；不能用int()將未知值猜成座標。
    if (not isinstance(positions, (list, tuple)) or len(positions) < 144
            or any(not isinstance(line, (list, tuple)) or len(line) != 4
                   or any(type(value) is not int for value in line)
                   or not (0 <= line[0] <= 255 and 0 <= line[1] <= 255
                           and -7 <= line[2] <= 248 and 0 <= line[3] <= 255)
                   for line in positions[:144])):
        result["warnings"].append("掃描線位置資料不完整，已略過文字候選。")
        result["read_error"] = "visible_scanline_positions_invalid"
        return result
    positions = tuple(tuple(line) for line in positions[:144])
    window_enabled = bool(lcdc & 0x20)
    result["window_visible"] = window_enabled and any(
        y >= wy and wx < 160 and wy < 144 for y, (_, _, wx, wy) in enumerate(positions))
    skipped_alignment = False
    rows = []
    row_indices = []
    for row in range(18):
        chars = []
        for column in range(20):
            x, y = column * 8, row * 8
            layer, source_x, source_y = _source_at(x, y, positions[y], window_enabled)
            tile_x, tile_y = source_x // 8, source_y // 8
            aligned = source_x % 8 == 0 and source_y % 8 == 0
            # 八條掃描線及兩個水平端點必須來自同一個完整 tile。
            if aligned:
                for dy in range(8):
                    left = _source_at(x, y + dy, positions[y + dy], window_enabled)
                    right = _source_at(x + 7, y + dy, positions[y + dy], window_enabled)
                    if (left != (layer, source_x, source_y + dy)
                            or right != (layer, source_x + 7, source_y + dy)):
                        aligned = False
                        break
            if not aligned:
                skipped_alignment = True
                chars.append(" ")
                continue
            try:
                tilemap = pyboy.tilemap_window if layer == "window" else pyboy.tilemap_background
                char = decoding.get(int(tilemap[tile_x, tile_y]), " ")
            except Exception:
                result["read_error"] = "visible_tile_getter_failed"
                return result
            chars.append(char if isinstance(char, str) and _PRINTABLE.fullmatch(char) else " ")
        text = "".join(chars).rstrip()
        result["cells"].append(chars)
        if _WORD.search(text):
            rows.append(text)
            row_indices.append(row)
    result["lines"] = rows[:12]
    result["line_rows"] = row_indices[:12]
    if skipped_alignment:
        result["warnings"].append("已略過捲動、視窗邊界或掃描線變化造成的不完整 tile。")
        result["read_error"] = "visible_tile_alignment_incomplete"
    else:
        result["read_valid"] = result["alignment_verified"] = True
    return result


def opening_context(text: dict, fallback_objective: str, player_name: str = "KEVIN") -> dict:
    """本機 UI 解析提示；不替模型指定或執行動作，階段仍待全面校準。"""
    from .naming import naming_context

    naming = naming_context(text.get("cells", []), player_name)
    if naming:
        if naming["mismatch"]:
            objective, available = "Delete the last incorrect name character with the cancel button.", ["b", "wait"]
        elif naming["entered_name"] == naming["target_name"]:
            objective, available = "Submit the completed name with START.", ["start", "b", "wait"]
        elif naming["selected_character"] == naming["next_target_character"]:
            objective, available = "Confirm the current selection.", ["a", "b"]
        else:
            x, y = naming["cursor_tile"]
            tx, ty = naming["target_character_tile"]
            # 游標在字元左側一格；字格位置來自可見畫面，沒有寫入遊戲記憶體。
            direction = "right" if x + 1 < tx else "left" if x + 1 > tx else "down" if y < ty else "up"
            objective = f"Move {direction.upper()}."
            available = ["up", "down", "left", "right", "wait"]
        return {"phase": "menu", "objective": objective, "available_actions": available,
                "naming": naming, "phase_source": "local visible name-grid parser and keyboard subgoal planner"}
    upper = "\n".join(text["lines"]).upper()
    if all(word in upper for word in ("NICKNAME", "YES", "NO")):
        return {"phase": "menu", "objective": "Cancel the optional nickname prompt.",
                "available_actions": ["b", "a"], "phase_source": "visible optional nickname prompt"}
    if all(word in upper for word in ("ITEM", "SAVE", "OPTION", "EXIT")):
        return {"phase": "menu", "objective": "Cancel and close this menu.",
                "available_actions": ["b", "wait"], "phase_source": "visible main-menu parser"}
    if "NEW NAME" in upper:
        new_row = next(i for i, line in enumerate(text["lines"]) if "NEW NAME" in line.upper())
        cursor_rows = [i for i, line in enumerate(text["lines"]) if "▶" in line]
        if cursor_rows and cursor_rows[0] > new_row:
            objective = "Move the menu cursor up one item toward NEW NAME."
        elif cursor_rows and cursor_rows[0] < new_row:
            objective = "Move the menu cursor down one item toward NEW NAME."
        else:
            objective = "Confirm the selected NEW NAME option with the confirm button."
        return {"phase": "menu", "objective": objective, "phase_source": "visible name-menu parser",
                "available_actions": ["up", "down", "a", "b"]}
    elif "NEW GAME" in upper or "CONTINUE" in upper:
        phase, objective = "title", "Begin or continue the current adventure from the title menu."
    elif any(row >= 12 for row in text.get("line_rows", [])):
        return {"phase": "dialogue", "objective": "Advance the visible dialogue with the confirm button.",
                "available_actions": ["a", "b"], "phase_source": "visible lower dialogue; A/B advance text"}
    else:
        phase, objective = "unclassified", fallback_objective
    return {"phase": phase, "objective": objective, "phase_source": "visible_text_layout_heuristic"}
