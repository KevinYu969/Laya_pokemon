"""紅／藍版通關與捕捉策略；純函式，不連網、不按鍵、不寫遊戲記憶體。

數值資料固定至 pret/pokered 的指定版本。評分是公開可檢查的啟發式，
不是完整傷害計算，也不宣稱存在一組適用所有限制的唯一最強隊伍。
"""
from functools import lru_cache
from importlib.resources import files
import json
import re


CORE_TEAM = ("VENUSAUR", "NIDOKING", "KADABRA", "LAPRAS", "SNORLAX", "ZAPDOS")
FAMILIES = (
    ("BULBASAUR", "IVYSAUR", "VENUSAUR"), ("NIDORAN_M", "NIDORINO", "NIDOKING"),
    ("ABRA", "KADABRA", "ALAKAZAM"), ("CATERPIE", "METAPOD", "BUTTERFREE"),
    ("SPEAROW", "FEAROW"), ("LAPRAS",), ("SNORLAX",), ("ZAPDOS",),
)
CAPTURE_PRIORITY = ("NIDORAN_M", "CATERPIE", "ABRA", "SPEAROW", "SNORLAX", "LAPRAS", "ZAPDOS")
TM_RESERVATIONS = {"THUNDERBOLT": "ZAPDOS", "EARTHQUAKE": "NIDOKING",
                   "ICE_BEAM": "NIDOKING", "ROCK_SLIDE": "NIDOKING"}
PROTECTED_HMS = {"CUT", "FLY", "SURF", "STRENGTH", "FLASH"}
# 只用於學招取捨；不是自動消耗 TM 的授權。
PREFERRED = {
    "VENUSAUR": ("RAZOR_LEAF", "SLEEP_POWDER", "LEECH_SEED", "GROWTH"),
    "NIDOKING": ("EARTHQUAKE", "ICE_BEAM", "ROCK_SLIDE", "BODY_SLAM"),
    "KADABRA": ("PSYCHIC_M", "RECOVER", "REFLECT", "THUNDER_WAVE"),
    "BUTTERFREE": ("SLEEP_POWDER", "PSYBEAM", "STUN_SPORE", "CONFUSION"),
    "LAPRAS": ("SURF", "ICE_BEAM", "BODY_SLAM", "CONFUSE_RAY"),
    "SNORLAX": ("BODY_SLAM", "AMNESIA", "REST", "STRENGTH"),
    "ZAPDOS": ("THUNDERBOLT", "DRILL_PECK", "THUNDER_WAVE", "FLY"),
}


@lru_cache(maxsize=1)
def reference():
    return json.loads(files("laya_pokemon").joinpath("data/gen1_reference.json").read_text(encoding="utf-8"))


def normalize(value):
    value = str(value).upper().replace("♂", "M").replace("♀", "F").replace("É", "E")
    return re.sub(r"[^A-Z0-9]", "", value)


def species_key(value):
    for key, entry in reference()["species"].items():
        if (isinstance(value, int) and not isinstance(value, bool) and entry["id"] == value
                or isinstance(value, str) and normalize(key) == normalize(value)):
            return key
    return None


def move_key(value):
    for key, entry in reference()["moves"].items():
        # PSYCHIC_M 是原始碼名稱；遊戲畫面顯示 PSYCHIC。
        if (isinstance(value, int) and not isinstance(value, bool) and entry["id"] == value
                or isinstance(value, str) and normalize(value) in {normalize(key), normalize(key.removesuffix("_M"))}):
            return key
    return None


def family(value):
    key = species_key(value)
    return next((group[0] for group in FAMILIES if key in group), key)


def desired_captures(owned):
    """owned 必須包含已知 PC 名單；目前實作只有隊伍，滿六隻時停止捕捉。"""
    families = {family(value) for value in owned}
    return [key for key in CAPTURE_PRIORITY if family(key) not in families]


def capture_plan(opponent, owned, balls, *, wild, party_count):
    key = species_key(opponent)
    if not wild or key is None or key not in reference()["species"]:
        return {"tactic": "not_capture", "reason": "not_verified_wild_target"}
    if family(key) not in {family(value) for value in desired_captures(owned)}:
        return {"tactic": "not_capture", "reason": "duplicate_or_outside_team_plan"}
    if party_count >= 6:
        return {"tactic": "review", "reason": "party_full_pc_roster_not_implemented"}
    if balls <= 0:
        return {"tactic": "resupply", "reason": "no_poke_balls"}
    if reference()["species"][key]["catch_rate"] >= 190 or key == "ABRA":
        return {"tactic": "throw_ball", "species": key,
                "reason": "high_base_catch_rate_or_abra_teleport; no guaranteed catch"}
    return {"tactic": "review", "species": key,
            "reason": "needs_verified_weaken_status_strategy_before_rare_capture"}


def effective_power(move, attacker, defender=None):
    """只近似威力×命中×STAB×屬性，未計能力值、會心、傷害亂數及狀態。"""
    key, attacker, defender = move_key(move), species_key(attacker), species_key(defender)
    if key is None:
        return 0.0
    entry = reference()["moves"][key]
    # 固定傷害、OHKO、Counter、Bide 等不能當一般 power 比較。
    if entry["power"] <= 1:
        return 0.0
    multiplier = 1.0
    if attacker and entry["type"] in reference()["species"][attacker]["types"]:
        multiplier *= 1.5
    if defender:
        for target_type in reference()["species"][defender]["types"]:
            multiplier *= next((factor for a, b, factor in reference()["type_matchups"]
                                if a == entry["type"] and b == target_type), 1)
    score = entry["power"] * entry["accuracy"] / 100 * multiplier
    if key in {"SOLARBEAM", "SKULL_BASH", "RAZOR_WIND", "SKY_ATTACK", "HYPER_BEAM"}:
        score *= .5
    if key in {"SELFDESTRUCT", "EXPLOSION"}:
        score = 0.0  # 不為普通練等犧牲唯一主力。
    return score


def choose_damage_move(attacker, moves, pp, defender=None):
    candidates = [(effective_power(move, attacker, defender), -index, move_key(move))
                  for index, move in enumerate(moves) if index < len(pp) and (pp[index] & 63) > 0]
    best = max(candidates, default=(0, 0, None))
    return best[2] if best[0] > 0 else None


def learn_move_plan(species, current, new_move, *, level):
    """提出學招計畫；未知合法性、HM 或唯一攻擊招都不盲目刪除。"""
    key, new = species_key(species), move_key(new_move)
    known = [move_key(move) for move in current if move not in (0, "NO_MOVE")]
    if key is None or new is None or None in known or len(known) > 4:
        return {"decision": "review", "reason": "unknown_species_or_move"}
    mon = reference()["species"][key]
    legal = new in mon["initial_moves"] or any(item["move"] == new and item["level"] <= level for item in mon["level_moves"])
    if not legal:
        return {"decision": "review", "reason": "not_verified_level_up_move"}
    if new in known:
        return {"decision": "skip", "reason": "already_known"}
    if len(known) < 4:
        return {"decision": "learn", "replace_index": None, "move": new, "reason": "free_slot"}
    final = next((member for member in CORE_TEAM + ("BUTTERFREE",) if family(member) == family(key)), key)
    preferred = PREFERRED.get(final, ())

    def utility(move):
        if move in preferred:
            return 300 - preferred.index(move) * 10
        # Lapras的SING保留低量捕獲用途；優先於MIST等0分狀態招，
        # 仍低於傷害招與既有preferred，僅影響學招取捨、不影響出招。
        if key == "LAPRAS" and move == "SING":
            return 1.0
        if move in {"VINE_WHIP", "CONFUSION", "PSYBEAM", "DOUBLE_KICK", "HORN_ATTACK"}:
            return 100 + effective_power(move, key) / 10
        return effective_power(move, key) / 10

    damaging = [move for move in known if effective_power(move, key) > 0]
    candidates = [index for index, move in enumerate(known) if move not in PROTECTED_HMS
                  and not (len(damaging) == 1 and move in damaging and effective_power(new, key) <= 0)]
    if not candidates:
        return {"decision": "skip", "reason": "protected_hm_or_only_attack"}
    replace = min(candidates, key=lambda index: (utility(known[index]), index))
    if utility(new) <= utility(known[replace]):
        return {"decision": "skip", "reason": "preserve_higher_priority_moves", "move": new}
    return {"decision": "replace", "replace_index": replace, "forget": known[replace], "move": new,
            "reason": "gen1_level_up_team_priority; requires_verified_forget_menu"}
