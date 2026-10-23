from types import SimpleNamespace

from laya_pokemon.observation import PROFILE, read_visible_text
from laya_pokemon.observation import opening_context


def test_opening_context_uses_visible_layout_without_executing_buttons():
    assert opening_context({"lines": [" Hello there!"], "line_rows": [14]}, "Open adventure")["phase"] == "dialogue"
    # 姓名選單優先於底部仍留著的對話。
    assert opening_context({"lines": ["NEW NAME", "My name?"], "line_rows": [3, 14]}, "Open adventure")["phase"] == "menu"
    assert opening_context({"lines": [], "line_rows": []}, "Open adventure")["phase"] == "unclassified"


def test_main_menu_close_is_distinct_from_dialogue_confirmation():
    context = opening_context({"lines": ["POKéMON", "ITEM", "KEVIN", "SAVE", "OPTION", "EXIT"], "line_rows": [2, 4, 6, 8, 10, 12]}, "Leave house")
    assert context["objective"] == "Cancel and close this menu."
    assert set(context["available_actions"]) == {"b", "wait"}


def test_optional_nickname_prompt_does_not_decline_starter_choice():
    assert opening_context({"lines": ["Give a NICKNAME?", "YES", "NO"], "line_rows": [14, 6, 8]}, "Receive starter")["available_actions"] == ["b", "a"]
    assert opening_context({"lines": ["Want BULBASAUR?", "YES", "NO"], "line_rows": [14, 6, 8]}, "Receive starter")["objective"] == "Advance the visible dialogue with the confirm button."


DECODING = {1: "A", 2: "B", 3: "C", 4: "D", 5: "Q", 6: "R", 7: "▶", 8: " ", 9: "<PROMPT>"}


class Tilemap:
    def __init__(self):
        self.cells = {}
        self.reads = []

    def __getitem__(self, xy):
        self.reads.append(xy)
        return self.cells.get(xy, 999)


def emulator(*, lcdc=0x91, position=(0, 0, 0, 0)):
    return SimpleNamespace(memory={0xFF40: lcdc}, tilemap_background=Tilemap(), tilemap_window=Tilemap(),
                           screen=SimpleNamespace(tilemap_position_list=[list(position) for _ in range(144)]))


def test_disabled_window_does_not_leak_hidden_text():
    game = emulator()
    game.tilemap_background.cells.update({(0, 0): 1, (1, 0): 2})
    game.tilemap_window.cells.update({(0, 0): 3, (1, 0): 4})
    result = read_visible_text(game, DECODING)
    assert result["lines"] == ["AB"]
    assert game.tilemap_window.reads == []
    assert result["profile"] == PROFILE and result["warnings"]


def test_scroll_and_xy_indexing_use_visible_background_only():
    game = emulator(position=(8, 16, 0, 0))
    game.tilemap_background.cells.update({(1, 2): 1, (2, 2): 2, (1, 0): 3, (2, 0): 4})
    result = read_visible_text(game, DECODING)
    assert result["lines"] == ["AB"]
    assert (1, 2) in game.tilemap_background.reads
    assert (1, 0) not in game.tilemap_background.reads


def test_background_scroll_wraps_at_32_tiles():
    game = emulator(position=(248, 248, 0, 0))
    game.tilemap_background.cells.update({(31, 31): 1, (0, 31): 2})
    assert read_visible_text(game, DECODING)["lines"] == ["AB"]


def test_enabled_window_overrides_background_at_its_visible_position():
    game = emulator(lcdc=0xB1, position=(0, 0, 80, 112))
    game.tilemap_background.cells.update({(0, 0): 1, (1, 0): 2, (10, 14): 5, (11, 14): 6})
    game.tilemap_window.cells.update({(0, 0): 7, (1, 0): 3, (2, 0): 4})
    result = read_visible_text(game, DECODING)
    assert result["lines"] == ["AB", "          ▶CD"]
    assert (10, 14) not in game.tilemap_background.reads


def test_offscreen_window_is_never_read():
    game = emulator(lcdc=0xB1, position=(0, 0, 160, 0))
    game.tilemap_background.cells.update({(0, 0): 1, (1, 0): 2})
    game.tilemap_window.cells.update({(0, 0): 3, (1, 0): 4})
    assert read_visible_text(game, DECODING)["lines"] == ["AB"]
    assert game.tilemap_window.reads == []


def test_unaligned_scroll_is_skipped_with_warning():
    game = emulator(position=(4, 0, 0, 0))
    game.tilemap_background.cells.update({(0, 0): 1, (1, 0): 2})
    result = read_visible_text(game, DECODING)
    assert result["lines"] == []
    assert len(result["warnings"]) == 2


def test_mid_tile_window_boundary_does_not_decode_hidden_background():
    game = emulator(lcdc=0xB1, position=(0, 0, 4, 0))
    game.tilemap_background.cells.update({(0, 0): 1, (1, 0): 2})
    game.tilemap_window.cells.update({(0, 0): 3, (1, 0): 4})
    assert read_visible_text(game, DECODING)["lines"] == []


def test_lcd_or_background_disabled_does_not_decode_any_layer():
    for lcdc in (0x31, 0xB0):
        game = emulator(lcdc=lcdc)
        assert read_visible_text(game, DECODING)["lines"] == []
        assert game.tilemap_background.reads == game.tilemap_window.reads == []


def test_unknown_tiles_and_control_tokens_are_not_text_and_rows_are_bounded():
    game = emulator()
    for y in range(18):
        game.tilemap_background.cells.update({(0, y): 7, (1, y): 1, (2, y): 2, (3, y): 9})
    result = read_visible_text(game, DECODING)
    assert result["lines"] == ["▶AB"] * 12


def test_single_characters_do_not_count_as_text():
    game = emulator()
    game.tilemap_background.cells.update({(0, 0): 1, (2, 0): 2})
    assert read_visible_text(game, DECODING)["lines"] == []


def test_scanline_scroll_change_inside_tile_is_skipped():
    game = emulator()
    game.tilemap_background.cells.update({(0, 0): 1, (1, 0): 2})
    game.screen.tilemap_position_list[3][0] = 8
    assert read_visible_text(game, DECODING)["lines"] == []


def test_missing_scanline_positions_produces_warning():
    game = emulator()
    game.screen.tilemap_position_list = []
    result = read_visible_text(game, DECODING)
    assert result["lines"] == [] and len(result["warnings"]) == 2


def test_npc_wait_dialogue_is_data_and_only_dialogue_buttons_are_candidates():
    from laya_pokemon.observation import opening_context
    result=opening_context({'lines':[' Wait! Take this',' with you!'],'line_rows':[14,16]},'Play','KEVIN')
    assert result['phase']=='dialogue' and result['available_actions']==['a','b']
    assert result['objective']=='Advance the visible dialogue with the confirm button.'
