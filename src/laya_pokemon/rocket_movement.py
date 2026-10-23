"""紅版 rev0 箭頭滑行的唯讀觀測候選；不步進、不按鍵、不寫入記憶體。

呼叫端先用既有流程核對紅版版本，再於單一模擬器執行緒中，傳入與其他
觀測相同的 frame。read_valid 只證明這四個 getter 值及 frame 契約有效，
不證明 ROM 身分、地圖、位置、畫面核對或已抵達箭頭終點。
位址推導及固定公開來源見 outputs/research/rocket-movement-addresses-20261023.md。
"""

SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
MOVEMENT_PROFILE = 'gen1-arrow-movement-source-v1'
SIMULATED_JOYPAD_INDEX_ADDRESS = 0xCD38
JOY_IGNORE_ADDRESS = 0xCD6B
WALK_COUNTER_ADDRESS = 0xCFC5
MOVEMENT_FLAGS_ADDRESS = 0xD736
SPINNING_MASK = 0x80
_UNUSED_MOVEMENT_FLAGS_MASK = 0x38  # 固定來源 bits 3..5 為 unused。


def _invalid(frame, reason):
    # 不能將未知讀值填成 0／False，否則會被誤判為遊戲已停止移動。
    return {'read_valid': False, 'profile': MOVEMENT_PROFILE, 'source_commit': SOURCE_COMMIT,
            'observation_frame': frame, 'spinning': None, 'simulated_remaining': None,
            'joy_ignore': None, 'walk_counter': None, 'movement_flags': None,
            'read_error': reason}


def read_rocket_movement(pyboy, *, observation_frame: int) -> dict:
    """只讀真實 pyboy.memory 的四個 byte，產生 ArrowFloorController 契約。

    不接受外部 profile、spinning 或 verified 開關。frame_count 必須在讀取
    前後皆等於 observation_frame；呼叫端仍須禁止另一執行緒同時 tick。
    失敗一律 read_valid=False，不以部分讀值判斷 idle。未知的輸入忽略 mask
    或來源標示未使用的 movement bits 也停下，交由上層 review。
    """
    if type(observation_frame) is not int or observation_frame < 0:
        return _invalid(None, 'movement_observation_frame_invalid')
    try:
        before = pyboy.frame_count
        if type(before) is not int or before != observation_frame:
            return _invalid(observation_frame, 'movement_frame_not_current')
        memory = pyboy.memory
        simulated = memory[SIMULATED_JOYPAD_INDEX_ADDRESS]
        ignored = memory[JOY_IGNORE_ADDRESS]
        walk = memory[WALK_COUNTER_ADDRESS]
        flags = memory[MOVEMENT_FLAGS_ADDRESS]
        after = pyboy.frame_count
    except Exception:
        return _invalid(observation_frame, 'movement_getter_failed')
    if type(after) is not int or after != before:
        return _invalid(observation_frame, 'movement_frame_changed_during_read')
    if any(type(value) is not int or not 0 <= value <= 255
           for value in (simulated, ignored, walk, flags)):
        return _invalid(observation_frame, 'movement_byte_invalid')
    if ignored not in (0x00, 0xFF):
        return _invalid(observation_frame, 'movement_input_ignore_mask_unknown')
    if flags & _UNUSED_MOVEMENT_FLAGS_MASK:
        return _invalid(observation_frame, 'movement_unused_flag_bits_set')
    return {'read_valid': True, 'profile': MOVEMENT_PROFILE, 'source_commit': SOURCE_COMMIT,
            'observation_frame': observation_frame, 'spinning': bool(flags & SPINNING_MASK),
            'simulated_remaining': simulated, 'joy_ignore': ignored, 'walk_counter': walk,
            'movement_flags': flags}
