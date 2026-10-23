"""使用純fake記憶體；第五館另交叉官方SDK公開常數，不讀ROM或真實RAM。"""
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


def test_money_decodes_big_endian_bcd_without_sdk_byte_reversal_or_ram_writes():
    constants=synthetic_constants();constants.PLAYER_MONEY_ADDRESS=0x400
    game=emulator([valid_mon()]);game.game_wrapper.inventory=[];game.game_wrapper.money=963000
    for offset,value in enumerate([0x00,0x30,0x96]):game.memory[0x400+offset]=value
    before=dict(game.memory)
    assert read_progress(game,constants)['money']==3096
    assert all(game.memory[k]==v for k,v in before.items())
    game.memory[0x401]=0xFA
    assert read_progress(game,constants)['money'] is None


# 固定來源 a53671100ec22e5394ff26ec028d0812a238dae2：
# constants/event_constants.asm:154-161 的獨立預期，不依 ignored outputs 研究檔。
FUCHSIA_EXPECTED = {
    "got_tm06": 0x258, "beat_koga": 0x259,
    "beat_fuchsia_gym_trainer_0": 0x25A, "beat_fuchsia_gym_trainer_1": 0x25B,
    "beat_fuchsia_gym_trainer_2": 0x25C, "beat_fuchsia_gym_trainer_3": 0x25D,
    "beat_fuchsia_gym_trainer_4": 0x25E, "beat_fuchsia_gym_trainer_5": 0x25F,
}
FUCHSIA_ADDED = set(FUCHSIA_EXPECTED) - {"beat_koga"}


class GetterOnlyMemory:
    def __init__(self, data):
        self.data, self.reads = dict(data), defaultdict(int)

    def __getitem__(self, address):
        self.reads[address] += 1
        value = self.data.get(address, 0)
        if isinstance(value, Exception):
            raise value
        return value

    def __setitem__(self, address, value):
        raise AssertionError("progress must never write fake memory")


def fuchsia_constants():
    # 只import已安裝官方常數，沒有建立PyBoy或載入遊戲。
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
    return SimpleNamespace(**{name: getattr(sdk, name) for name in (
        "PARTY_COUNT_ADDRESS", "PARTY_LENGTH", "OBTAINED_BADGES_ADDRESS",
        "EVENT_FLAGS_ADDRESS", "EVENT_FLAGS", "POKEMON_SPECIES_NAMES", "BADGES")})


def fuchsia_game(constants, event_byte, *, party=True):
    wrapper = Wrapper([valid_mon(species=7, level=35, hp=108, max_hp=108)] if party else [])
    wrapper.inventory, wrapper.money = [], 0
    return SimpleNamespace(memory=GetterOnlyMemory({constants.PARTY_COUNT_ADDRESS: int(party),
                           constants.OBTAINED_BADGES_ADDRESS: 15, 0xD792: event_byte}),
                           game_wrapper=wrapper)


def test_fuchsia_fixed_source_ids_and_byte_match_installed_official_sdk():
    constants = fuchsia_constants()
    assert constants.EVENT_FLAGS_ADDRESS == 0xD747
    assert {name: constants.EVENT_FLAGS[name] for name in FUCHSIA_EXPECTED} == FUCHSIA_EXPECTED
    assert {0xD747 + event_id // 8 for event_id in FUCHSIA_EXPECTED.values()} == {0xD792}
    assert {event_id % 8 for event_id in FUCHSIA_EXPECTED.values()} == set(range(8))
    assert all(name in STORY_EVENT_NAMES for name in FUCHSIA_EXPECTED)


@pytest.mark.parametrize("bit", range(8))
def test_fuchsia_each_real_bit_is_independent_and_cached_once_without_writes(bit):
    constants = fuchsia_constants()
    game = fuchsia_game(constants, 1 << bit)
    before = dict(game.memory.data)
    result = read_progress(game, constants)
    assert {name: result["story_event_bits"][name] for name in FUCHSIA_EXPECTED} == {
        name: (event_id % 8 == bit) for name, event_id in FUCHSIA_EXPECTED.items()}
    assert game.memory.reads[0xD792] == 1
    assert game.memory.data == before and game.game_wrapper.reads == 1
    # 原始館員/阿桔位元不會自動授予第五徽章或宣告冠軍／名人堂。
    assert result["badges_raw"] == 15 and result["badge_count"] == 4
    assert result["champion_observed"] is False and result["hall_of_fame_confirmed"] is None
    assert result["profile"] == "gen1-wrapper-ram-progress-v1-unvalidated"


@pytest.mark.parametrize("value", [None, True, False, -1, 256, 1.0, "255",
                                 ValueError("unknown byte"), KeyError(0xD792)])
def test_fuchsia_unknown_byte_keeps_all_eight_bits_unknown(value):
    constants = fuchsia_constants()
    result = read_progress(fuchsia_game(constants, value), constants)
    assert all(result["story_event_bits"][name] is None for name in FUCHSIA_EXPECTED)
    assert result["hall_of_fame_confirmed"] is None


@pytest.mark.parametrize("name", FUCHSIA_EXPECTED)
def test_fuchsia_missing_sdk_anchor_keeps_added_fields_unknown(name):
    constants = fuchsia_constants()
    constants.EVENT_FLAGS = dict(constants.EVENT_FLAGS)
    constants.EVENT_FLAGS.pop(name)
    result = read_progress(fuchsia_game(constants, 255), constants)
    assert all(result["story_event_bits"][event] is None for event in FUCHSIA_ADDED)
    assert result["story_event_bits"]["beat_koga"] is (None if name == "beat_koga" else True)


@pytest.mark.parametrize("change", ["shifted_id", "boolean_id", "other_event_base", "synthetic_profile"])
def test_fuchsia_unrecognized_source_contract_cannot_reinterpret_new_events(change):
    constants = fuchsia_constants()
    constants.EVENT_FLAGS = dict(constants.EVENT_FLAGS)
    if change == "shifted_id":
        constants.EVENT_FLAGS["beat_fuchsia_gym_trainer_0"] = 0x25B
    elif change == "boolean_id":
        constants.EVENT_FLAGS["got_tm06"] = True
    elif change == "other_event_base":
        constants.EVENT_FLAGS_ADDRESS = 0xD746
    else:
        constants = synthetic_constants()
    result = read_progress(fuchsia_game(constants, 255), constants)
    assert all(result["story_event_bits"][event] is None for event in FUCHSIA_ADDED)
    assert result["hall_of_fame_confirmed"] is None


def test_fuchsia_empty_party_preserves_only_raw_bits_without_confirming_mission():
    constants = fuchsia_constants()
    result = read_progress(fuchsia_game(constants, 255, party=False), constants)
    assert all(result["story_event_bits"][name] is True for name in FUCHSIA_EXPECTED)
    assert result["party_read_valid"] is True and result["initialization_candidate"] is False
    assert result["badge_count"] is None and result["champion_observed"] is None
    assert result["hall_of_fame_confirmed"] is None
