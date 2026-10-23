"""固定紅版 BattleMon 的唯讀快照；保留尚未回寫的 party 原始資料。

只讀同一觀測的記憶體 getter 與幀號；不匯入 SDK wrapper，不做 I/O、
tick、按鍵或 RAM 寫入。來源推導與防變動檢查不是實機身分校準或執行緒鎖。
"""
from types import MappingProxyType

from .wild_opponent import _SPECIES, _STATUS, _TYPES


SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
PROFILE = 'red-en-sdk-2.8.1-player-battle-source-v1-unvalidated'
SDK_ANCHORS = MappingProxyType({
    'CURRENT_OPPONENT_ADDRESS': 0xD059, 'BATTLE_TYPE_ADDRESS': 0xD05A,
    'CURRENT_ENEMY_LEVEL_ADDRESS': 0xD127, 'PARTY_COUNT_ADDRESS': 0xD163,
    'PARTY_SPECIES_ADDRESS': 0xD164, 'PARTY_MONS_ADDRESS': 0xD16B,
    'PARTY_MON_SIZE': 44, 'PARTY_LENGTH': 6, 'OBTAINED_BADGES_ADDRESS': 0xD356,
})
IS_IN_BATTLE = SDK_ANCHORS['CURRENT_OPPONENT_ADDRESS'] - 2
# 固定 wram：EnemyMon29+baseStats5+catch1+exp1+nick11 後即 BattleMon。
# BattleMon 至 wIsInBattle：29+1+1+2+1+max(14,11)+2+2+1+1+13 = 67。
BATTLE_MON_ADDRESS = IS_IN_BATTLE - 67
BATTLE_MON_SIZE = 29
# layout.link org C100：兩組16*16 sprite + OAM40*4 + tilemap360
# + union max(360,24*20,160,400) + overworld1300 + redraw40 + menu11。
ACTIVE_PARTY_INDEX_ADDRESS = 0xC100 + 512 + 160 + 360 + 480 + 1300 + 40 + 11
CUR_MAP = SDK_ANCHORS['OBTAINED_BADGES_ADDRESS'] + 8
Y_COORD, X_COORD = CUR_MAP + 3, CUR_MAP + 4
_GUARD_ADDRESSES = (CUR_MAP, X_COORD, Y_COORD, IS_IN_BATTLE,
                    SDK_ANCHORS['BATTLE_TYPE_ADDRESS'],
                    ACTIVE_PARTY_INDEX_ADDRESS, SDK_ANCHORS['PARTY_COUNT_ADDRESS'])


def _byte(value):
    return type(value) is int and 0 <= value <= 255


def decode_player_battle(record):
    """解析完整29 bytes；0HP保留為事實，不能據此允許繼續投球或換人。"""
    def fail(reason):
        return {'read_valid': False, 'player': None, 'unknown_reason': reason}

    if not isinstance(record, (list, tuple)) or len(record) != BATTLE_MON_SIZE:
        return fail('player_battle_structure_length_invalid')
    if not all(_byte(b) for b in record):
        return fail('player_battle_structure_byte_invalid')
    species, level, status = record[0], record[14], record[4]
    if species not in _SPECIES:
        return fail('player_battle_species_unknown')
    if not 1 <= level <= 100:
        return fail('player_battle_level_invalid')
    word = lambda i: record[i] * 256 + record[i + 1]
    hp, max_hp = word(1), word(15)
    if not 1 <= max_hp <= 999 or not 0 <= hp <= max_hp:
        return fail('player_battle_hp_invalid')
    if status not in _STATUS:
        return fail('player_battle_status_invalid')
    if record[5] not in _TYPES or record[6] not in _TYPES:
        return fail('player_battle_type_invalid')
    moves, pp = list(record[8:12]), list(record[25:29])
    if (moves[0] == 0 or any(m > 165 for m in moves)
            or any(m == 0 and (p != 0 or any(moves[i + 1:]))
                   for i, (m, p) in enumerate(zip(moves, pp)))):
        return fail('player_battle_moves_or_pp_invalid')
    stats = {name: word(i) for name, i in
             (('attack', 17), ('defense', 19), ('speed', 21), ('special', 23))}
    if any(not 1 <= v <= 999 for v in stats.values()):
        return fail('player_battle_stats_invalid')
    return {'read_valid': True, 'unknown_reason': None, 'player': {
        'species': species, 'internal_id': species, 'species_name': _SPECIES[species],
        'level': level, 'hp': hp, 'max_hp': max_hp, 'status': status,
        'moves': moves, 'pp': pp, 'pp_remaining': [p & 63 for p in pp],
        'pp_ups': [p >> 6 for p in pp], 'dvs': list(record[12:14]),
        'types': list(record[5:7]), **stats}}


def read_player_battle(pyboy, *, observation_frame, expected_location,
                       constants, profile):
    """同幀雙讀 BattleMon 與位置／戰鬥／active index guard，未知不給部分資料。

caller 須序列化同一模擬器的觀測，另核本快照與 progress party 的身份、
順序、實際 HUD 及 active index；本函式不改寫、合成或補正 party HP。
正常野生／訓練家戰都可讀；Safari、老人教學與戰鬥結束回未知。
"""
    result = {'profile': PROFILE, 'source_commit': SOURCE_COMMIT,
              'live_calibrated': False, 'observation_frame': observation_frame,
              'read_valid': False, 'player': None, 'active_party_index': None,
              'location': None, 'battle_kind': None, 'unknown_reason': None}

    def fail(reason):
        return {**result, 'unknown_reason': reason}

    if profile != PROFILE:
        return fail('player_battle_red_profile_required')
    if type(observation_frame) is not int or observation_frame < 0:
        return fail('player_battle_observation_frame_invalid')
    if (not isinstance(expected_location, dict)
            or not all(_byte(expected_location.get(k)) for k in ('map_id', 'x', 'y'))):
        return fail('player_battle_expected_location_invalid')
    location = tuple(expected_location[k] for k in ('map_id', 'x', 'y'))
    try:
        if any(type(getattr(constants, name)) is not int
               or getattr(constants, name) != address for name, address in SDK_ANCHORS.items()):
            return fail('player_battle_sdk_anchor_mismatch')
    except Exception:
        return fail('player_battle_sdk_anchor_unavailable')
    try:
        before = pyboy.frame_count
        if type(before) is not int or before != observation_frame:
            return fail('player_battle_frame_not_current')
        memory = pyboy.memory
        guard1 = tuple(memory[a] for a in _GUARD_ADDRESSES)
        record1 = tuple(memory[BATTLE_MON_ADDRESS + i] for i in range(BATTLE_MON_SIZE))
        record2 = tuple(memory[BATTLE_MON_ADDRESS + i] for i in range(BATTLE_MON_SIZE))
        guard2 = tuple(memory[a] for a in _GUARD_ADDRESSES)
        after = pyboy.frame_count
    except Exception:
        return fail('player_battle_memory_getter_failed')
    if type(after) is not int or after != before:
        return fail('player_battle_frame_changed_during_read')
    if not all(_byte(b) for b in (*guard1, *guard2, *record1, *record2)):
        return fail('player_battle_memory_byte_invalid')
    if guard1 != guard2 or record1 != record2:
        return fail('player_battle_snapshot_changed_during_read')
    if guard1[:3] != location:
        return fail('player_battle_location_does_not_match_observation')
    if guard1[3] not in (1, 2):
        return fail('player_battle_not_active')
    if guard1[4] != 0:
        return fail('player_battle_normal_battle_required')
    active, count = guard1[5:7]
    if not 1 <= count <= 6 or not 0 <= active < count:
        return fail('player_battle_active_party_index_invalid')
    decoded = decode_player_battle(record1)
    if not decoded['read_valid']:
        return fail(decoded['unknown_reason'])
    return {**result, **decoded, 'active_party_index': active,
            'location': dict(zip(('map_id', 'x', 'y'), location)),
            'battle_kind': 'wild' if guard1[3] == 1 else 'trainer'}
