"""固定紅版 toggleable objects 的唯讀快照候選；不按鍵、不步進、不寫 RAM。

read_valid 只證明 getter、範圍、表格及同 frame 契約；不是 ROM 身分或
地圖載入完成的證明。呼叫端需序列化模擬器存取、確認原生野外觀測有效，
並以固定公開來源校準 map-specific slot/index，再用 hidden=True 移除障礙。
未知快照回 objects=None，不得把它轉成空表或 hidden=False。
"""

SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
PROFILE = 'fixed-red-toggleable-object-snapshot-v1'
CURRENT_MAP_ADDRESS = 0xD35E
NUM_SPRITES_ADDRESS = 0xD4E1
TOGGLE_FLAGS_ADDRESS = 0xD5A6
TOGGLE_FLAGS_LENGTH = 32
TOGGLE_LIST_ADDRESS = 0xD5CE
TOGGLE_LIST_LENGTH = 33
MAX_MAP_SPRITES = 15
NUM_TOGGLEABLE_OBJECTS = 228  # 固定 constants/toggle_constants.asm 最末0xE3 + 1。
SOURCES = tuple(
    f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/{path}'
    for path in (
        'ram/wram.asm#L1910',
        'engine/overworld/toggleable_objects.asm#L99',
        'engine/overworld/movement.asm#L477',
        'constants/toggle_constants.asm#L394',
    )
)


class _InvalidSnapshot(Exception):
    pass


def _invalid(error):
    return {
        'read_valid': False, 'observed_frame': None, 'map': None,
        'sprite_count': None, 'objects': None, 'error': error,
        'profile': PROFILE, 'source_commit': SOURCE_COMMIT,
    }


def _byte(memory, address):
    value = memory[address]
    if type(value) is not int or not 0 <= value <= 255:
        raise _InvalidSnapshot('toggle_byte_invalid')
    return value


def read_toggleable_objects(pyboy, *, map_id, observation_frame):
    """只用 memory getter 與 frame_count 讀取固定地址的 toggle list／flags。

    list 為 (本圖slot, 全域index) 成對，到偶數offset的FF結束。所有32/33
    bytes均需有效；終止後的合法byte不要求清零。索引必須小於固定來源228。
    map/count在前後重讀，frame在前後均須等於 observation_frame。
    不讀 SpriteStateData ImageIndex：其FF也可能只是offscreen或文字遮擋。
    """
    if type(map_id) is not int or not 0 <= map_id <= 255:
        return _invalid('toggle_map_argument_invalid')
    if type(observation_frame) is not int or observation_frame < 0:
        return _invalid('toggle_frame_argument_invalid')
    try:
        before = pyboy.frame_count
        if type(before) is not int or before != observation_frame:
            return _invalid('toggle_frame_not_current')
        memory = pyboy.memory
        current_map = _byte(memory, CURRENT_MAP_ADDRESS)
        if current_map != map_id:
            return _invalid('toggle_map_mismatch')
        count = _byte(memory, NUM_SPRITES_ADDRESS)
        if count > MAX_MAP_SPRITES:
            return _invalid('toggle_sprite_count_invalid')
        flags = [_byte(memory, TOGGLE_FLAGS_ADDRESS + offset)
                 for offset in range(TOGGLE_FLAGS_LENGTH)]
        table = [_byte(memory, TOGGLE_LIST_ADDRESS + offset)
                 for offset in range(TOGGLE_LIST_LENGTH)]
        final_map = _byte(memory, CURRENT_MAP_ADDRESS)
        final_count = _byte(memory, NUM_SPRITES_ADDRESS)
        after = pyboy.frame_count
    except _InvalidSnapshot as error:
        return _invalid(str(error))
    except Exception:
        return _invalid('toggle_getter_failed')
    if type(after) is not int or after != before:
        return _invalid('toggle_frame_changed_during_read')
    if final_map != current_map:
        return _invalid('toggle_map_changed_during_read')
    if final_count != count:
        return _invalid('toggle_sprite_count_changed_during_read')
    end = next((offset for offset in range(0, TOGGLE_LIST_LENGTH, 2)
                if table[offset] == 0xFF), None)
    if end is None:
        return _invalid('toggle_table_terminator_missing')
    objects, slots, indices = [], set(), set()
    for offset in range(0, end, 2):
        slot, index = table[offset:offset + 2]
        if not 1 <= slot <= count:
            return _invalid('toggle_slot_out_of_bounds')
        if index >= NUM_TOGGLEABLE_OBJECTS:
            return _invalid('toggle_global_index_invalid')
        if slot in slots:
            return _invalid('toggle_duplicate_slot')
        if index in indices:
            return _invalid('toggle_duplicate_global_index')
        slots.add(slot)
        indices.add(index)
        objects.append({'slot': slot, 'index': index,
                        'hidden': bool(flags[index // 8] & (1 << (index % 8)))})
    return {
        'read_valid': True, 'observed_frame': observation_frame, 'map': current_map,
        'sprite_count': count, 'objects': objects, 'error': None,
        'profile': PROFILE, 'source_commit': SOURCE_COMMIT,
    }

