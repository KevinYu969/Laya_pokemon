"""固定紅版一般訓練家 EnemyMon 的獨立唯讀候選；尚未實機校準。

僅讀 caller 所屬執行緒的 frame_count/memory；不做 I/O、tick、按鍵或寫入。
raw2 保持訓練家身分，絕不改成 raw1 或呼叫野生戰 reader。來源、SDK 錨點
及完整29-byte純解碼沿用既有 wild_opponent；這不是補藥或傷害安全批准。
"""
from laya_pokemon.wild_opponent import (
    SOURCE_COMMIT, SDK_ANCHORS, IS_IN_BATTLE, ENEMY_MON_ADDRESS,
    ENEMY_MON_SIZE, PLAYER_BATTLE_MON_CROSSCHECK, CUR_MAP, X_COORD, Y_COORD,
    decode_enemy_mon,
)


PROFILE = 'red-en-sdk-2.8.1-trainer-enemy-source-v1-unvalidated'
_GUARD_ADDRESSES = (
    CUR_MAP, X_COORD, Y_COORD, IS_IN_BATTLE,
    SDK_ANCHORS['BATTLE_TYPE_ADDRESS'],
    SDK_ANCHORS['CURRENT_OPPONENT_ADDRESS'],
    SDK_ANCHORS['CURRENT_ENEMY_LEVEL_ADDRESS'],
)


def _byte(value):
    return type(value) is int and 0 <= value <= 255


def read_trainer_opponent(pyboy, *, observation_frame, expected_location,
                          constants, profile):
    """同觀測兩遍 guards + 全29 bytes；未知不提供部分 enemy/raw_record。

    wCurOpponent 是 trainer class + OPP_ID_OFFSET，不是 EnemyMonSpecies。
    此版只保留其真 byte，不猜 class 範圍、特定館主或當前 UI；caller 須另核
    真紅版身分、trainer/HUD 與操作前提，並序列化所有觀測/tick。雙讀只是
    檢測撕裂，不能代替執行緒鎖，亦不能檢出同幀 A→B→A 的全部中間變化。
    """
    result = {
        'profile': PROFILE, 'source_commit': SOURCE_COMMIT,
        'live_calibrated': False, 'observation_frame': observation_frame,
        'frame_before': None, 'frame_after': None,
        'read_valid': False, 'enemy': None, 'raw_record': None,
        'location': None, 'battle_kind': None, 'raw': None,
        'battle_type': None, 'current_opponent': None, 'unknown_reason': None,
    }

    def fail(reason):
        return {**result, 'unknown_reason': reason}

    if profile != PROFILE:
        return fail('trainer_red_profile_required')
    if type(observation_frame) is not int or observation_frame < 0:
        return fail('trainer_observation_frame_invalid')
    if (not isinstance(expected_location, dict)
            or not all(_byte(expected_location.get(k)) for k in ('map_id', 'x', 'y'))):
        return fail('trainer_expected_location_invalid')
    location = tuple(expected_location[k] for k in ('map_id', 'x', 'y'))
    try:
        anchors = tuple((getattr(constants, name), address)
                        for name, address in SDK_ANCHORS.items())
        if any(type(value) is not int or value != address for value, address in anchors):
            return fail('trainer_sdk_anchor_mismatch')
    except Exception:
        return fail('trainer_sdk_anchor_unavailable')
    try:
        before = pyboy.frame_count
        if type(before) is not int or before != observation_frame:
            return fail('trainer_frame_not_current')
        result['frame_before'] = before
        memory = pyboy.memory
        guard1 = tuple(memory[a] for a in _GUARD_ADDRESSES)
        record1 = tuple(memory[ENEMY_MON_ADDRESS + i] for i in range(ENEMY_MON_SIZE))
        record2 = tuple(memory[ENEMY_MON_ADDRESS + i] for i in range(ENEMY_MON_SIZE))
        guard2 = tuple(memory[a] for a in _GUARD_ADDRESSES)
        after = pyboy.frame_count
    except Exception:
        return fail('trainer_memory_getter_failed')
    if type(after) is not int or after != before:
        return fail('trainer_frame_changed_during_read')
    result['frame_after'] = after
    # 兩遍都驗真 byte，先於 Python 相等比較，避免 False==0 / 0.0==0。
    if not all(_byte(b) for b in (*guard1, *guard2, *record1, *record2)):
        return fail('trainer_memory_byte_invalid')
    if guard1 != guard2 or record1 != record2:
        return fail('trainer_snapshot_changed_during_read')
    if guard1[:3] != location:
        return fail('trainer_location_does_not_match_observation')
    if guard1[3] != 2:
        return fail('trainer_battle_not_active')
    if guard1[4] != 0:
        return fail('trainer_normal_battle_required')
    decoded = decode_enemy_mon(record1)
    if not decoded['read_valid']:
        return fail(decoded['unknown_reason'])
    if guard1[6] != decoded['enemy']['level']:
        return fail('trainer_enemy_level_identity_mismatch')
    return {
        **result, **decoded,
        'location': dict(zip(('map_id', 'x', 'y'), location)),
        'battle_kind': 'trainer', 'raw': 2, 'battle_type': 0,
        'current_opponent': guard1[5], 'raw_record': list(record1),
    }
