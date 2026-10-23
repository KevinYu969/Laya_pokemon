"""完全使用合成位址與虛構種族；不讀取遊戲 ROM 或真實 RAM。"""
from collections import defaultdict
from types import SimpleNamespace

import pytest

from laya_pokemon.progress import FULL_MISSION_MILESTONES, FULL_MISSION_OBJECTIVE, STORY_EVENT_NAMES, read_progress


def synthetic_constants():
    events = {name: index + 32 for index, name in enumerate(STORY_EVENT_NAMES)}
    events.update(got_starter=0, got_pokedex=7, beat_champion_rival=8, hall_of_fame_dex_rating=17)
    return SimpleNamespace(PARTY_COUNT_ADDRESS=0x100, PARTY_LENGTH=6, OBTAINED_BADGES_ADDRESS=0x101,
                           EVENT_FLAGS_ADDRESS=0x200, EVENT_FLAGS=events,
                           POKEMON_SPECIES_NAMES={1: "SYNTHETIC MON"},
                           BADGES={f"synthetic_badge_{bit}": bit for bit in range(8)})


class Wrapper:
    def __init__(self, party, error=None):
        self.records, self.error, self.reads = party, error, 0

    @property
    def party(self):
        self.reads += 1
        if self.error:
            raise self.error
        return self.records


def emulator(party=None, count=None, error=None):
    party = [] if party is None else party
    memory = defaultdict(int)
    memory[0x100] = len(party) if count is None else count
    return SimpleNamespace(memory=memory, game_wrapper=Wrapper(party, error))


def valid_mon(**changes):
    return {"species": 1, "level": 5, "hp": 12, "max_hp": 20, "exp": 125, **changes}


def test_committed_player_name_stops_at_game_terminator_without_writing_memory():
    constants = synthetic_constants()
    constants.PLAYER_NAME_ADDRESS = 0x300
    constants.POKEMON_TEXT_DECODING = {i + 1: char for i, char in enumerate("KEVIN")}
    game = emulator()
    for offset, byte in enumerate([1, 2, 3, 4, 5, 0x50]):
        game.memory[0x300 + offset] = byte
    assert read_progress(game, constants)["player_name_raw"] == "KEVIN"
    assert game.memory[0x305] == 0x50


def test_empty_party_keeps_semantic_progress_unknown_but_preserves_raw_bits():
    game = emulator()
    game.memory[0x101], game.memory[0x201] = 255, 1
    result = read_progress(game, synthetic_constants())
    assert result["party_read_valid"] and not result["initialization_candidate"]
    assert result["badges_raw"] == 255 and result["story_event_bits"]["beat_champion_rival"] is True
    assert result["badge_count"] is None and result["champion_observed"] is None
    assert result["badges_observed"] == [] and result["hall_of_fame_confirmed"] is None
    assert game.game_wrapper.reads == 1


@pytest.mark.parametrize("mon", [valid_mon(species=999), valid_mon(level=0), valid_mon(level=101),
                                 valid_mon(hp=21), valid_mon(hp=-1), valid_mon(max_hp=0), valid_mon(level=True), {}])
def test_invalid_party_does_not_confirm_badges_or_champion(mon):
    game = emulator([mon])
    game.memory[0x101], game.memory[0x201] = 255, 1
    result = read_progress(game, synthetic_constants())
    assert not result["party_read_valid"] and not result["initialization_candidate"]
    assert result["party"] == [] and result["badge_count"] is None and result["champion_observed"] is None
    assert result["badges_raw"] == 255 and result["hall_of_fame_confirmed"] is None
    assert game.game_wrapper.reads == 1


@pytest.mark.parametrize("count", [0, 7, 255])
def test_mismatched_or_invalid_party_count_is_rejected(count):
    result = read_progress(emulator([valid_mon()], count=count), synthetic_constants())
    assert result["party_count"] == count and not result["initialization_candidate"]


def test_property_error_is_contained_and_property_is_read_once():
    game = emulator(error=ValueError("synthetic uninitialized party"))
    result = read_progress(game, synthetic_constants())
    assert not result["party_read_valid"] and game.game_wrapper.reads == 1
    assert len(result["warnings"]) == 2


def test_valid_nonempty_party_is_only_an_initialization_candidate():
    game = emulator([valid_mon(hp=0)])
    game.memory[0x101], game.memory[0x201] = 0b10000101, 1
    result = read_progress(game, synthetic_constants())
    assert result["initialization_candidate"] and result["party_read_valid"]
    assert result["party"] == [{"species": 1, "species_name": "SYNTHETIC MON", "level": 5,
                                "hp": 0, "max_hp": 20, "exp": 125}]
    assert result["badge_count"] == 3
    assert result["badges_observed"] == ["synthetic_badge_0", "synthetic_badge_2", "synthetic_badge_7"]
    assert result["champion_observed"] is True and result["hall_of_fame_confirmed"] is None


def test_event_byte_offsets_and_bit_positions_are_read_correctly():
    game = emulator([valid_mon()])
    game.memory[0x200], game.memory[0x201], game.memory[0x202] = 0b10000000, 1, 0b10
    result = read_progress(game, synthetic_constants())
    assert result["story_event_bits"]["got_starter"] is False
    assert result["story_event_bits"]["got_pokedex"] is True
    assert result["story_event_bits"]["beat_champion_rival"] is True
    assert result["story_event_bits"]["hall_of_fame_dex_rating"] is True
    assert result["hall_of_fame_confirmed"] is None


def test_unknown_flag_and_unreadable_badges_stay_unknown():
    constants = synthetic_constants()
    constants.EVENT_FLAGS.pop("beat_champion_rival")
    game = emulator([valid_mon()])
    game.memory[0x101] = "uninitialized"
    result = read_progress(game, constants)
    assert result["badges_raw"] is None and result["badge_count"] is None
    assert result["champion_observed"] is None and result["hall_of_fame_confirmed"] is None


def test_mission_metadata_is_traditional_chinese_and_all_pending():
    assert "八枚徽章" in FULL_MISSION_OBJECTIVE and "名人堂" in FULL_MISSION_OBJECTIVE
    assert [item["id"] for item in FULL_MISSION_MILESTONES] == [
        "train_party", "required_story", "eight_badges", "elite_four", "champion", "hall_of_fame"]
    assert all(item["status"] == "pending" for item in FULL_MISSION_MILESTONES)
