"""合成可見字格測試；不使用 ROM、模型、PyBoy 或真實畫面。"""
import pytest

from laya_pokemon.naming import naming_context
from laya_pokemon.observation import opening_context


def screen(*, title="YOUR NAME?", entered="", cursor=(1, 5)):
    cells = [[" "] * 20 for _ in range(18)]
    cells[1][:len(title)] = title
    for y, text in zip((5, 7, 9), ("ABCDEFGHI", "JKLMNOPQR", "STUVWXYZ ")):
        for column, char in enumerate(text):
            cells[y][2 + column * 2] = char
    cells[2][10:10 + len(entered)] = entered
    cells[15][2:12] = list("lower case")
    if cursor is not None:
        cells[cursor[1]][cursor[0]] = "▶"
    return cells


@pytest.mark.parametrize("cursor, word", [((1, 5), "right"), ((3, 5), "down"), ((5, 7), "left"), ((3, 9), "up")])
def test_keyboard_subgoal_uses_character_offset_and_keeps_multiple_choices(cursor, word):
    context = opening_context({"cells": screen(cursor=cursor), "lines": ["YOUR NAME?"], "line_rows": [1]}, "Open adventure")
    assert word.upper() in context["objective"]
    assert len(context["available_actions"]) > 1
    assert "start" not in context["available_actions"]


@pytest.mark.parametrize("entered, cursor, expected", [("", (3, 7), "a"), ("KEVIN", (1, 5), "start"), ("KEX", (1, 5), "b")])
def test_keyboard_confirm_submit_and_correction_keep_model_choice(entered, cursor, expected):
    context = opening_context({"cells": screen(entered=entered, cursor=cursor), "lines": ["YOUR NAME?"], "line_rows": [1]}, "Open adventure")
    assert expected in context["available_actions"] and len(context["available_actions"]) >= 2


def test_player_context_reads_visible_prefix_and_next_character_coordinates():
    context = naming_context(screen(entered="KE"))
    assert context["screen_type"] == "player_naming" and context["target_name"] == "KEVIN"
    assert context["entered_name"] == "KE" and context["next_target_character"] == "V"
    assert context["target_character_tile"] == [8, 9] and context["cursor_tile"] == [1, 5]
    assert context["selected_character"] == "A" and context["status"] == "move_to_character"


def test_rival_uses_blue_instead_of_player_name():
    context = naming_context(screen(title="RIVAL's NAME?", entered="BL"), player_name="KEVIN")
    assert context["screen_type"] == "rival_naming" and context["target_name"] == "BLUE"
    assert context["next_target_character"] == "U" and context["target_character_tile"] == [6, 9]


def test_selected_target_only_describes_confirmation_without_outputting_a_button():
    context = naming_context(screen(cursor=(3, 7)))
    assert context["selected_character"] == "K" and context["status"] == "ready_to_confirm"
    assert context["target_character_tile"] == [4, 7]
    assert "action" not in context and "button" not in context


def test_complete_target_is_ready_to_submit_and_does_not_add_another_letter():
    context = naming_context(screen(entered="KEVIN"))
    assert context["status"] == "ready_to_submit" and not context["mismatch"]
    assert context["next_target_character"] is context["target_character_tile"] is None


@pytest.mark.parametrize("entered", ["KEX", "BLUE", "KEVINX", "kevin"])
def test_wrong_prefix_is_reported_instead_of_hidden(entered):
    context = naming_context(screen(entered=entered))
    assert context["mismatch"] and context["status"] == "mismatch"
    assert context["entered_name"] == entered and entered in context["objective"]
    assert context["next_target_character"] is context["target_character_tile"] is None


def test_missing_multiple_or_outside_grid_cursors_are_rejected():
    assert naming_context(screen(cursor=None)) is None
    cells = screen()
    cells[7][1] = "▶"
    assert naming_context(cells) is None
    assert naming_context(screen(cursor=(0, 0))) is None


def test_case_switch_cursor_is_allowed_only_with_visible_case_switch_text():
    cells = screen(cursor=(1, 15))
    assert naming_context(cells)["status"] == "move_to_character"
    cells[15][2] = "?"
    assert naming_context(cells) is None


def test_matching_title_alone_is_not_a_naming_screen():
    cells = screen()
    cells[7][4] = "?"
    assert naming_context(cells) is None


@pytest.mark.parametrize("title", ["YOUR NAME", "YOUR NAME? OTHER", "RIVAL'S NAME?", "POKEMON"])
def test_unmatched_or_ambiguous_title_is_rejected(title):
    assert naming_context(screen(title=title)) is None


def test_custom_player_target_is_supported_without_affecting_rival():
    assert naming_context(screen(), "ASH")["target_name"] == "ASH"
    assert naming_context(screen(title="RIVAL's NAME?"), "ASH")["target_name"] == "BLUE"


@pytest.mark.parametrize("target", ["", "TOOLONGX", "Kevin", "A B", None])
def test_invalid_target_names_are_rejected(target):
    with pytest.raises(ValueError):
        naming_context(screen(), target)


@pytest.mark.parametrize("cells", [None, [], [[" "] * 19 for _ in range(18)], [[0] * 20 for _ in range(18)]])
def test_invalid_cell_shapes_are_not_naming_screens(cells):
    assert naming_context(cells) is None


def test_does_not_mutate_input_cells():
    cells = screen(entered="KE")
    before = [row[:] for row in cells]
    naming_context(cells)
    assert cells == before
