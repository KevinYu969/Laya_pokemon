"""固定紅版 EnemyMon 的唯讀候選；來源推導不是實機校準。

沒有檔案、網路、wrapper 匯入、tick 或按鍵；caller 在同一模擬器執行緒
完成一次觀測，並提供已載入 SDK constants、版本契約及本次位置/幀。
本模組既不判定可以投球，也不將捕獲後重建的 moves/PP/EXP 說成繼承。
"""
from types import MappingProxyType


SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
PROFILE = 'red-en-sdk-2.8.1-enemy-source-v1-unvalidated'
SDK_ANCHORS = MappingProxyType({
    'CURRENT_OPPONENT_ADDRESS': 0xD059, 'BATTLE_TYPE_ADDRESS': 0xD05A,
    'CURRENT_ENEMY_LEVEL_ADDRESS': 0xD127, 'PARTY_COUNT_ADDRESS': 0xD163,
    'PARTY_MONS_ADDRESS': 0xD16B, 'OBTAINED_BADGES_ADDRESS': 0xD356,
})
# wCurOpponent - wIsInBattle = db + flag_array(6) = 2。
IS_IN_BATTLE = SDK_ANCHORS['CURRENT_OPPONENT_ADDRESS'] - 2
# battle_struct29 + baseStats5 + catch1 + exp1 + nick11 + battle29
# + trainer1 + ds1 + ptr2 + ds1 + union(max(14,11)) + ds2 + money2
# + counter1 + ds1 + trainerName13 = 114；另推到玩家battleMon D014。
ENEMY_MON_SIZE = 29
ENEMY_MON_ADDRESS = IS_IN_BATTLE - 114
PLAYER_BATTLE_MON_CROSSCHECK = ENEMY_MON_ADDRESS + 29 + 5 + 1 + 1 + 11
CUR_MAP = SDK_ANCHORS['OBTAINED_BADGES_ADDRESS'] + 8
Y_COORD, X_COORD = CUR_MAP + 3, CUR_MAP + 4
_GUARD_ADDRESSES = (CUR_MAP, X_COORD, Y_COORD, IS_IN_BATTLE,
                    SDK_ANCHORS['BATTLE_TYPE_ADDRESS'],
                    SDK_ANCHORS['CURRENT_OPPONENT_ADDRESS'],
                    SDK_ANCHORS['CURRENT_ENEMY_LEVEL_ADDRESS'])
_STATUS = frozenset(range(8)) | {8, 16, 32, 64}
_TYPES = frozenset(range(9)) | frozenset(range(20, 27))

# 以下151個真實物種由固定 pokemon_constants.asm 產生；MissingNo/化石/幽靈排除。
_SPECIES = MappingProxyType({
    1: 'RHYDON', 2: 'KANGASKHAN', 3: 'NIDORAN_M', 4: 'CLEFAIRY',
    5: 'SPEAROW', 6: 'VOLTORB', 7: 'NIDOKING', 8: 'SLOWBRO',
    9: 'IVYSAUR', 10: 'EXEGGUTOR', 11: 'LICKITUNG', 12: 'EXEGGCUTE',
    13: 'GRIMER', 14: 'GENGAR', 15: 'NIDORAN_F', 16: 'NIDOQUEEN',
    17: 'CUBONE', 18: 'RHYHORN', 19: 'LAPRAS', 20: 'ARCANINE',
    21: 'MEW', 22: 'GYARADOS', 23: 'SHELLDER', 24: 'TENTACOOL',
    25: 'GASTLY', 26: 'SCYTHER', 27: 'STARYU', 28: 'BLASTOISE',
    29: 'PINSIR', 30: 'TANGELA', 33: 'GROWLITHE', 34: 'ONIX',
    35: 'FEAROW', 36: 'PIDGEY', 37: 'SLOWPOKE', 38: 'KADABRA',
    39: 'GRAVELER', 40: 'CHANSEY', 41: 'MACHOKE', 42: 'MR_MIME',
    43: 'HITMONLEE', 44: 'HITMONCHAN', 45: 'ARBOK', 46: 'PARASECT',
    47: 'PSYDUCK', 48: 'DROWZEE', 49: 'GOLEM', 51: 'MAGMAR',
    53: 'ELECTABUZZ', 54: 'MAGNETON', 55: 'KOFFING', 57: 'MANKEY',
    58: 'SEEL', 59: 'DIGLETT', 60: 'TAUROS', 64: 'FARFETCHD',
    65: 'VENONAT', 66: 'DRAGONITE', 70: 'DODUO', 71: 'POLIWAG',
    72: 'JYNX', 73: 'MOLTRES', 74: 'ARTICUNO', 75: 'ZAPDOS',
    76: 'DITTO', 77: 'MEOWTH', 78: 'KRABBY', 82: 'VULPIX',
    83: 'NINETALES', 84: 'PIKACHU', 85: 'RAICHU', 88: 'DRATINI',
    89: 'DRAGONAIR', 90: 'KABUTO', 91: 'KABUTOPS', 92: 'HORSEA',
    93: 'SEADRA', 96: 'SANDSHREW', 97: 'SANDSLASH', 98: 'OMANYTE',
    99: 'OMASTAR', 100: 'JIGGLYPUFF', 101: 'WIGGLYTUFF', 102: 'EEVEE',
    103: 'FLAREON', 104: 'JOLTEON', 105: 'VAPOREON', 106: 'MACHOP',
    107: 'ZUBAT', 108: 'EKANS', 109: 'PARAS', 110: 'POLIWHIRL',
    111: 'POLIWRATH', 112: 'WEEDLE', 113: 'KAKUNA', 114: 'BEEDRILL',
    116: 'DODRIO', 117: 'PRIMEAPE', 118: 'DUGTRIO', 119: 'VENOMOTH',
    120: 'DEWGONG', 123: 'CATERPIE', 124: 'METAPOD', 125: 'BUTTERFREE',
    126: 'MACHAMP', 128: 'GOLDUCK', 129: 'HYPNO', 130: 'GOLBAT',
    131: 'MEWTWO', 132: 'SNORLAX', 133: 'MAGIKARP', 136: 'MUK',
    138: 'KINGLER', 139: 'CLOYSTER', 141: 'ELECTRODE', 142: 'CLEFABLE',
    143: 'WEEZING', 144: 'PERSIAN', 145: 'MAROWAK', 147: 'HAUNTER',
    148: 'ABRA', 149: 'ALAKAZAM', 150: 'PIDGEOTTO', 151: 'PIDGEOT',
    152: 'STARMIE', 153: 'BULBASAUR', 154: 'VENUSAUR', 155: 'TENTACRUEL',
    157: 'GOLDEEN', 158: 'SEAKING', 163: 'PONYTA', 164: 'RAPIDASH',
    165: 'RATTATA', 166: 'RATICATE', 167: 'NIDORINO', 168: 'NIDORINA',
    169: 'GEODUDE', 170: 'PORYGON', 171: 'AERODACTYL', 173: 'MAGNEMITE',
    176: 'CHARMANDER', 177: 'SQUIRTLE', 178: 'CHARMELEON', 179: 'WARTORTLE',
    180: 'CHARIZARD', 185: 'ODDISH', 186: 'GLOOM', 187: 'VILEPLUME',
    188: 'BELLSPROUT', 189: 'WEEPINBELL', 190: 'VICTREEBEL',
})


def _byte(value):
    return type(value) is int and 0 <= value <= 255


def _unknown(reason):
    return {'read_valid': False, 'enemy': None, 'unknown_reason': reason}


def decode_enemy_mon(record):
    """純29-byte結構解析；0HP是捕獲/昏厥過渡，不能提供可用敵方快照。"""
    if not isinstance(record, (list, tuple)) or len(record) != ENEMY_MON_SIZE:
        return _unknown('enemy_structure_length_invalid')
    if not all(_byte(b) for b in record):
        return _unknown('enemy_structure_byte_invalid')
    species, level, status = record[0], record[14], record[4]
    if species not in _SPECIES:
        return _unknown('enemy_species_unknown')
    if not 1 <= level <= 100:
        return _unknown('enemy_level_invalid')
    word = lambda i: record[i] * 256 + record[i + 1]
    hp, max_hp = word(1), word(15)
    if not 1 <= max_hp <= 999 or not 0 <= hp <= max_hp:
        return _unknown('enemy_hp_invalid')
    if hp == 0:
        return _unknown('enemy_zero_hp_transition')
    if status not in _STATUS:
        return _unknown('enemy_status_invalid')
    if record[5] not in _TYPES or record[6] not in _TYPES:
        return _unknown('enemy_type_invalid')
    moves, pp = list(record[8:12]), list(record[25:29])
    # 正常四格招式連續，無招式的槽位PP也必須0；PP高兩bit保留為PP Up。
    if (moves[0] == 0 or any(m > 165 for m in moves)
            or any(m == 0 and (p != 0 or any(moves[i + 1:]))
                   for i, (m, p) in enumerate(zip(moves, pp)))):
        return _unknown('enemy_moves_or_pp_invalid')
    stats = {name: word(i) for name, i in
             (('attack', 17), ('defense', 19), ('speed', 21), ('special', 23))}
    if any(not 1 <= value <= 999 for value in stats.values()):
        return _unknown('enemy_stats_invalid')
    return {'read_valid': True, 'unknown_reason': None, 'enemy': {
        'species': species, 'internal_id': species, 'species_name': _SPECIES[species],
        'level': level, 'hp': hp, 'max_hp': max_hp, 'status': status,
        'moves': moves, 'pp': pp, 'pp_remaining': [p & 63 for p in pp],
        'pp_ups': [p >> 6 for p in pp], 'dvs': list(record[12:14]),
        'types': list(record[5:7]), 'catch_rate': record[7], **stats}}


def read_wild_opponent(pyboy, *, observation_frame, expected_location,
                       constants, profile):
    """同一觀測的純唯讀getter；所有未知都不提供部分enemy。

    明確profile只是caller的紅版契約，不能取代ROM身分驗證。caller不可同時
    tick/操作記憶體；前後幀與兩次全結構重讀是偵測，不是跨執行緒鎖。
    非一般野生戰（含Safari/OldMan）不接管。捕捉結果須另核可見收據與party。
    """
    result = {'profile': PROFILE, 'source_commit': SOURCE_COMMIT,
              'live_calibrated': False, 'observation_frame': observation_frame,
              'read_valid': False, 'enemy': None, 'location': None,
              'battle_kind': None, 'unknown_reason': None}

    def fail(reason):
        return {**result, 'unknown_reason': reason}

    if profile != PROFILE:
        return fail('wild_red_profile_required')
    if type(observation_frame) is not int or observation_frame < 0:
        return fail('wild_observation_frame_invalid')
    if (not isinstance(expected_location, dict)
            or not all(_byte(expected_location.get(k)) for k in ('map_id', 'x', 'y'))):
        return fail('wild_expected_location_invalid')
    location = tuple(expected_location[k] for k in ('map_id', 'x', 'y'))
    try:
        if any(type(getattr(constants, name)) is not int
               or getattr(constants, name) != address for name, address in SDK_ANCHORS.items()):
            return fail('wild_sdk_anchor_mismatch')
    except Exception:
        return fail('wild_sdk_anchor_unavailable')
    try:
        before = pyboy.frame_count
        if type(before) is not int or before != observation_frame:
            return fail('wild_frame_not_current')
        memory = pyboy.memory
        guard1 = tuple(memory[a] for a in _GUARD_ADDRESSES)
        record1 = tuple(memory[ENEMY_MON_ADDRESS + i] for i in range(ENEMY_MON_SIZE))
        record2 = tuple(memory[ENEMY_MON_ADDRESS + i] for i in range(ENEMY_MON_SIZE))
        guard2 = tuple(memory[a] for a in _GUARD_ADDRESSES)
        after = pyboy.frame_count
    except Exception:
        return fail('wild_memory_getter_failed')
    if type(after) is not int or after != before:
        return fail('wild_frame_changed_during_read')
    if not all(_byte(b) for b in (*guard1, *guard2, *record1, *record2)):
        return fail('wild_memory_byte_invalid')
    if guard1 != guard2 or record1 != record2:
        return fail('wild_snapshot_changed_during_read')
    if guard1[:3] != location:
        return fail('wild_location_does_not_match_observation')
    if guard1[3] != 1:
        return fail('wild_battle_not_active')
    if guard1[4] != 0:
        return fail('wild_normal_battle_required')
    decoded = decode_enemy_mon(record1)
    if not decoded['read_valid']:
        return fail(decoded['unknown_reason'])
    if guard1[6] != decoded['enemy']['level']:
        return fail('wild_enemy_level_identity_mismatch')
    if guard1[5] not in (0, decoded['enemy']['species']):
        return fail('wild_enemy_species_identity_mismatch')
    # wCurOpponent可在正常戰鬥變成0，不當成當前物種；species使用完整EnemyMon。
    return {**result, **decoded, 'location': dict(zip(('map_id', 'x', 'y'), location)),
            'battle_kind': 'wild'}


def capture_fingerprint(snapshot):
    """只擷取同觀測五欄，不宣告caught或HP/status已由新party繼承。"""
    if (not isinstance(snapshot, dict) or snapshot.get('read_valid') is not True
            or snapshot.get('profile') != PROFILE or snapshot.get('source_commit') != SOURCE_COMMIT
            or snapshot.get('battle_kind') != 'wild'):
        return None
    enemy = snapshot.get('enemy')
    if not isinstance(enemy, dict):
        return None
    values = {key: enemy.get(key) for key in ('species', 'level', 'hp', 'max_hp', 'status')}
    if (not all(type(v) is int for v in values.values()) or values['species'] not in _SPECIES
            or not 1 <= values['level'] <= 100 or not 1 <= values['hp'] <= values['max_hp'] <= 999
            or values['status'] not in _STATUS):
        return None
    return values
