"""英文紅／藍版可見命名字格的純觀測解析；不產生按鍵。"""
from __future__ import annotations

import re


_ALPHABET_ROWS = ("ABCDEFGHI", "JKLMNOPQR", "STUVWXYZ ")


def naming_context(cells, player_name: str = "KEVIN") -> dict | None:
    """匹配命名標題、完整前三列字格與單一游標後才回傳子目標。

    座標皆為螢幕 tile 的零起算 ``[x, y]``；呼叫者仍須由本機模型選擇按鍵。
    """
    if not isinstance(player_name, str) or not re.fullmatch(r"[A-Z]{1,7}", player_name):
        raise ValueError("玩家名稱須為 1 至 7 個大寫英文字母")
    if (not isinstance(cells, (list, tuple)) or len(cells) != 18
            or any(not isinstance(row, (list, tuple)) or len(row) != 20 for row in cells)
            or any(not isinstance(cell, str) for row in cells for cell in row)):
        return None
    title = "".join(cells[1]).strip()
    if title == "YOUR NAME?":
        screen_type, target_name = "player_naming", player_name
    elif title == "RIVAL's NAME?":
        screen_type, target_name = "rival_naming", "BLUE"
    else:
        return None
    for row, expected in enumerate(_ALPHABET_ROWS):
        if "".join(cells[5 + row * 2][2 + column * 2] for column in range(9)) != expected:
            return None
    cursors = [(x, y) for y, row in enumerate(cells) for x, cell in enumerate(row) if cell == "▶"]
    if len(cursors) != 1:
        return None
    cursor_x, cursor_y = cursors[0]
    in_grid = cursor_y in (5, 7, 9, 11, 13) and cursor_x in range(1, 18, 2)
    on_case_switch = (cursor_x, cursor_y) == (1, 15) and "".join(cells[15][2:12]).strip() == "lower case"
    if not in_grid and not on_case_switch:
        return None
    entered_name = "".join(cells[2][10:17]).rstrip()
    context = {
        "screen_type": screen_type, "target_name": target_name, "entered_name": entered_name,
        "cursor_tile": [cursor_x, cursor_y], "selected_character": cells[cursor_y][cursor_x + 1],
        "next_target_character": None, "target_character_tile": None,
        "profile": "gen1-visible-naming-grid-v1", "mismatch": False,
    }
    if not target_name.startswith(entered_name):
        context.update(status="mismatch", mismatch=True,
                       objective=f"目前輸入 {entered_name!r} 不符合目標 {target_name}；刪除末字直到回復正確前綴。")
        return context
    if entered_name == target_name:
        context.update(status="ready_to_submit", objective=f"已完整輸入 {target_name}；提交這個名稱。")
        return context
    next_character = target_name[len(entered_name)]
    row, column = divmod(ord(next_character) - ord("A"), 9)
    target_tile = [2 + column * 2, 5 + row * 2]
    context.update(next_target_character=next_character, target_character_tile=target_tile)
    if [cursor_x + 1, cursor_y] == target_tile:
        context.update(status="ready_to_confirm", objective=f"游標已選中下一個字元 {next_character}；確認一次以加入名稱。")
    else:
        context.update(status="move_to_character",
                       objective=f"將游標移到下一個字元 {next_character} 的字格 {target_tile}，目前游標位於 {[cursor_x, cursor_y]}。")
    return context
