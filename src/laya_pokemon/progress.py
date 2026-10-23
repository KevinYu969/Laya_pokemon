"""唯讀的 Gen I 進度訊號；數值一致性不等同已完成畫面校準。"""
from __future__ import annotations

from numbers import Integral


PROFILE = "gen1-wrapper-ram-progress-v1-unvalidated"
FULL_MISSION_OBJECTIVE = "培養並升級隊伍、完成必要劇情、取得八枚徽章、擊敗四天王與冠軍，並完成名人堂登錄。"
FULL_MISSION_MILESTONES = [
    {"id": "train_party", "label": "培養並升級隊伍", "status": "pending"},
    {"id": "required_story", "label": "完成必要劇情", "status": "pending"},
    {"id": "eight_badges", "label": "取得八枚徽章", "status": "pending"},
    {"id": "elite_four", "label": "擊敗四天王", "status": "pending"},
    {"id": "champion", "label": "擊敗冠軍", "status": "pending"},
    {"id": "hall_of_fame", "label": "完成名人堂登錄", "status": "pending"},
]
STORY_EVENT_NAMES = (
    "followed_oak_into_lab", "oak_asked_to_choose_mon", "battled_rival_in_oaks_lab",
    "got_starter", "got_pokedex", "got_oaks_parcel", "oak_got_parcel", "got_hm01", "got_hm03", "got_hm04", "got_poke_flute",
    "beat_silph_co_giovanni", "beat_brock", "beat_misty", "beat_lt_surge", "beat_erika", "beat_koga",
    "beat_sabrina", "beat_blaine", "beat_viridian_gym_giovanni", "beat_loreleis_room_trainer_0",
    "beat_brunos_room_trainer_0", "beat_agathas_room_trainer_0", "beat_lance", "beat_champion_rival",
    "hall_of_fame_dex_rating",
)


def _integer(value) -> bool:
    return isinstance(value, Integral) and not isinstance(value, bool)


def read_progress(pyboy, constants=None) -> dict:
    """讀取有限進度訊號，不寫記憶體、不推進遊戲，也不執行模型分類。

    有效非空隊伍僅是 ``initialization_candidate``；徽章與事件仍需實際畫面校準。
    ``constants`` 可注入合成測試資料，避免 CI 匯入 PyBoy。
    """
    if constants is None:
        from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    result = {
        "profile": PROFILE, "initialization_candidate": False, "party_read_valid": False,
        "party_count": None, "party": [], "badges_raw": None, "badges_observed": [], "badge_count": None,
        "story_event_bits": {}, "champion_observed": None, "hall_of_fame_confirmed": None,
        "player_name_raw": None,
        "warnings": ["進度依記憶體訊號讀取，尚未完全校準；原始事件位元不等同本次執行已達成里程碑。"],
    }
    cache = {}

    def read_byte(address):
        if address not in cache:
            try:
                value = pyboy.memory[address]
                if not _integer(value) or not 0 <= value <= 255:
                    raise ValueError("invalid byte")
                cache[address] = int(value)
            except (AttributeError, KeyError, IndexError, TypeError, ValueError) as error:
                cache[address] = None
                result["warnings"].append(f"進度位址 {address:#06x} 尚不可讀取：{type(error).__name__}")
        return cache[address]

    count = read_byte(constants.PARTY_COUNT_ADDRESS)
    result["party_count"] = count
    name_address = getattr(constants, "PLAYER_NAME_ADDRESS", None)
    decoding = getattr(constants, "POKEMON_TEXT_DECODING", {})
    if name_address is not None:
        name = []
        for offset in range(11):
            byte = read_byte(name_address + offset)
            if byte == 0x50:
                result["player_name_raw"] = "".join(name)
                break
            char = decoding.get(byte, "")
            if len(char) != 1 or not char.isascii() or not char.isalpha():
                break
            name.append(char)
    try:
        # property 只能讀一次；hasattr 也會觸發 property，因此不使用它。
        party = list(pyboy.game_wrapper.party)
        if count is None or not 0 <= count <= constants.PARTY_LENGTH or len(party) != count:
            raise ValueError("party count does not match")
        summary = []
        for mon in party:
            species, level, hp, max_hp = (mon[key] for key in ("species", "level", "hp", "max_hp"))
            if (not all(_integer(value) for value in (species, level, hp, max_hp))
                    or species not in constants.POKEMON_SPECIES_NAMES or species <= 0
                    or not 1 <= level <= 100 or max_hp <= 0 or not 0 <= hp <= max_hp):
                raise ValueError("invalid party record")
            row = {"species": int(species), "species_name": constants.POKEMON_SPECIES_NAMES[species],
                   "level": int(level), "hp": int(hp), "max_hp": int(max_hp)}
            if "exp" in mon and _integer(mon["exp"]) and mon["exp"] >= 0:
                row["exp"] = int(mon["exp"])
            summary.append(row)
        result.update(party_read_valid=True, party=summary, initialization_candidate=bool(summary))
    except (AttributeError, KeyError, IndexError, TypeError, ValueError) as error:
        result["warnings"].append(f"隊伍尚不可驗證：{type(error).__name__}")
    badges = read_byte(constants.OBTAINED_BADGES_ADDRESS)
    result["badges_raw"] = badges
    for name in STORY_EVENT_NAMES:
        event_id = constants.EVENT_FLAGS.get(name)
        if event_id is None:
            result["story_event_bits"][name] = None
            continue
        value = read_byte(constants.EVENT_FLAGS_ADDRESS + event_id // 8)
        result["story_event_bits"][name] = None if value is None else bool(value & (1 << (event_id % 8)))
    if result["initialization_candidate"]:
        if badges is not None:
            result["badges_observed"] = [name for name, bit in constants.BADGES.items() if badges & (1 << bit)]
            result["badge_count"] = badges.bit_count()
        result["champion_observed"] = result["story_event_bits"].get("beat_champion_rival")
    # hall_of_fame_dex_rating 的事件名稱不足以證明完成名人堂登錄。
    return result
