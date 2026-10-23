"""唯讀的 Gen I 進度訊號；數值一致性不等同已完成畫面校準。"""
from __future__ import annotations

from collections.abc import Mapping
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
    "got_tm06", "beat_fuchsia_gym_trainer_0", "beat_fuchsia_gym_trainer_1",
    "beat_fuchsia_gym_trainer_2", "beat_fuchsia_gym_trainer_3",
    "beat_fuchsia_gym_trainer_4", "beat_fuchsia_gym_trainer_5",
    "beat_sabrina", "beat_blaine", "beat_viridian_gym_giovanni", "beat_loreleis_room_trainer_0",
    "beat_brunos_room_trainer_0", "beat_agathas_room_trainer_0", "beat_lance", "beat_champion_rival",
    "hall_of_fame_dex_rating", "beat_cerulean_rival", "beat_cerulean_rocket_thief", "got_nugget", "beat_route24_rocket", "got_hm02", "got_hm05",
    "met_bill", "bill_said_use_cell_separator", "used_cell_separator_on_bill", "got_ss_ticket", "left_bills_house_after_helping",
    "beat_mt_moon_exit_super_nerd", "got_dome_fossil", "got_helix_fossil", "got_master_ball",
    "first_lock_opened", "second_lock_opened", "ss_anne_left",
)
EVENT_FLAG_ALIASES={'first_lock_opened':'1st_lock_opened','second_lock_opened':'2nd_lock_opened'}

# 固定 pret/pokered a53671100ec22e5394ff26ec028d0812a238dae2：
# constants/event_constants.asm:154-161；ram/wram.asm wEventFlags 基址 D747。
# https://github.com/pret/pokered/blob/a53671100ec22e5394ff26ec028d0812a238dae2/constants/event_constants.asm#L154
# 同一 D792 byte 的 bit0=TM06、bit1=Koga、bit2..7=館員0..5。
_FUCHSIA_EVENT_IDS = {
    "got_tm06": 0x258, "beat_koga": 0x259,
    "beat_fuchsia_gym_trainer_0": 0x25A, "beat_fuchsia_gym_trainer_1": 0x25B,
    "beat_fuchsia_gym_trainer_2": 0x25C, "beat_fuchsia_gym_trainer_3": 0x25D,
    "beat_fuchsia_gym_trainer_4": 0x25E, "beat_fuchsia_gym_trainer_5": 0x25F,
}


def _integer(value) -> bool:
    return isinstance(value, Integral) and not isinstance(value, bool)


def _fuchsia_events_supported(constants) -> bool:
    """新欄位須吻合固定紅版與官方SDK；不改既有Koga讀法或推論本輪勝利。"""
    base = getattr(constants, "EVENT_FLAGS_ADDRESS", None)
    events = getattr(constants, "EVENT_FLAGS", None)
    return (_integer(base) and base == 0xD747 and isinstance(events, Mapping)
            and all(_integer(events.get(name)) and events[name] == event_id
                    for name, event_id in _FUCHSIA_EVENT_IDS.items()))


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
            if "status" in mon and _integer(mon['status']) and 0<=mon['status']<=255:
                row['status']=int(mon['status'])
            for key, maximum in (("moves", 165), ("pp", 255)):
                values = mon.get(key)
                if (isinstance(values, (tuple, list)) and len(values) == 4
                        and all(_integer(value) and 0 <= value <= maximum for value in values)):
                    row[key] = list(map(int, values))
            summary.append(row)
        result.update(party_read_valid=True, party=summary, initialization_candidate=bool(summary))
    except (AttributeError, KeyError, IndexError, TypeError, ValueError) as error:
        result["warnings"].append(f"隊伍尚不可驗證：{type(error).__name__}")
    # 只呼叫 property getter；不使用 SDK 的 set_inventory/set_money/set_party。
    result.update(inventory=None, money=None)
    try:
        inventory = list(pyboy.game_wrapper.inventory)
        if len(inventory) > 20 or any(not _integer(item["item"]) or not 1 <= item["item"] <= 255
                                    or not _integer(item["quantity"]) or not 1 <= item["quantity"] <= 99
                                    for item in inventory):
            raise ValueError("invalid inventory")
        result["inventory"] = [{"item": int(item["item"]), "quantity": int(item["quantity"])} for item in inventory]
        money = pyboy.game_wrapper.money
        if _integer(money) and 0 <= money <= 999999:
            result["money"] = int(money)
    except (AttributeError, KeyError, IndexError, TypeError, ValueError):
        pass  # 較舊 wrapper 或合成測試沒有此 property；保持未知，不視為空背包。
    money_address = getattr(constants, 'PLAYER_MONEY_ADDRESS', None)
    if money_address is not None:
        # PyBoy 2.8.1 BCD helper會反轉多byte順序；自行唯讀解碼大端BCD。
        digits = [read_byte(money_address + i) for i in range(3)]
        result['money'] = None
        if all(b is not None and b >> 4 <= 9 and b & 15 <= 9 for b in digits):
            result['money'] = sum(((b >> 4)*10+(b & 15))*100**(2-i) for i,b in enumerate(digits))
    badges = read_byte(constants.OBTAINED_BADGES_ADDRESS)
    result["badges_raw"] = badges
    fuchsia_supported = _fuchsia_events_supported(constants)
    for name in STORY_EVENT_NAMES:
        if name in _FUCHSIA_EVENT_IDS and name != "beat_koga" and not fuchsia_supported:
            result["story_event_bits"][name] = None
            continue
        event_id = constants.EVENT_FLAGS.get(EVENT_FLAG_ALIASES.get(name,name))
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
    from .rocket_progress import read_rocket_progress
    rocket=read_rocket_progress(pyboy.memory,result,constants)
    result['story_event_bits'].update(rocket['story_event_bits'])
    result['rocket_item_presence']=rocket['item_presence']
    from .tower_progress import read_tower_progress
    tower=read_tower_progress(pyboy.memory,result,constants)
    result['story_event_bits'].update(tower['story_event_bits'])
    result['tower_item_presence']=tower['item_presence']
    return result
