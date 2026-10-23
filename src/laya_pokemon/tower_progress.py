"""固定紅版寶可夢塔的唯讀進度候選；不讀ROM／檔案、不按鍵、不寫RAM。

主API與rocket_progress一致，僅索引memory getter及已提供的上游progress。
裸memory API無frame證明；可選包裝器另驗真實PyBoy前後frame及上游frame標記。
事件目前為True不代表本輪新完成，物品持有也不能取代取得交易證據。
"""
from collections.abc import Mapping
from numbers import Integral
from types import MappingProxyType

from .rocket_progress import _initialized, _inventory_ids


SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
SOURCE_ROOT = f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/'
SOURCES = tuple(SOURCE_ROOT + path for path in (
    'constants/event_constants.asm#L66', 'constants/event_constants.asm#L399',
    'constants/item_constants.asm', 'ram/wram.asm#L2141',
    'scripts/PokemonTower2F.asm', 'scripts/PokemonTower3F.asm',
    'scripts/PokemonTower4F.asm', 'scripts/PokemonTower5F.asm',
    'scripts/PokemonTower6F.asm', 'scripts/PokemonTower7F.asm', 'scripts/MrFujisHouse.asm'))
PROFILE = 'fixed-red-tower-progress-candidate-v1-unvalidated'
UPSTREAM_PROFILE = 'gen1-wrapper-ram-progress-v1-unvalidated'
EVENT_FLAGS_ADDRESS = 0xD747
TOWER_EVENT_IDS = MappingProxyType({
    'beat_pokemon_tower_rival': 0x0EF,
    'beat_pokemontower_3_trainer_0': 0x0F1,
    'beat_pokemontower_3_trainer_1': 0x0F2,
    'beat_pokemontower_3_trainer_2': 0x0F3,
    'beat_pokemontower_4_trainer_0': 0x0F9,
    'beat_pokemontower_4_trainer_1': 0x0FA,
    'beat_pokemontower_4_trainer_2': 0x0FB,
    'beat_pokemontower_5_trainer_0': 0x102,
    'beat_pokemontower_5_trainer_1': 0x103,
    'beat_pokemontower_5_trainer_2': 0x104,
    'beat_pokemontower_5_trainer_3': 0x105,
    'in_purified_zone': 0x107,
    'beat_pokemontower_6_trainer_0': 0x109,
    'beat_pokemontower_6_trainer_1': 0x10A,
    'beat_pokemontower_6_trainer_2': 0x10B,
    'beat_ghost_marowak': 0x10F,
    'beat_pokemontower_7_trainer_0': 0x111,
    'beat_pokemontower_7_trainer_1': 0x112,
    'beat_pokemontower_7_trainer_2': 0x113,
    'rescued_mr_fuji_2': 0x117,
    'got_poke_flute': 0x128,
    'rescued_mr_fuji': 0x4CF,
})
ITEM_IDS = MappingProxyType({'has_silph_scope': 72, 'has_poke_flute': 73})


def _integer(value):
    return isinstance(value, Integral) and not isinstance(value, bool)


def _empty():
    return {'profile': PROFILE, 'source_commit': SOURCE_COMMIT, 'sources': list(SOURCES),
            'initialization_candidate': False, 'read_valid': False,
            'frame_checked': False, 'observation_frame': None,
            'story_event_bits': {name: None for name in TOWER_EVENT_IDS},
            'item_presence': {name: None for name in ITEM_IDS},
            'event_locations': {name: {'event_id': value,
                                       'address': EVENT_FLAGS_ADDRESS + value // 8,
                                       'bit': value % 8} for name, value in TOWER_EVENT_IDS.items()},
            'warnings': ['目前事件值不是本次新達成的里程碑；仍需正常戰鬥、文字與交易證據。']}


def read_tower_progress(memory, progress, constants=None):
    """相容rocket API；不自動載SDK，不宣稱裸getter能驗證同一frame。

    constants須提供官方EVENT_FLAGS_ADDRESS與逐一相符的EVENT_FLAGS。
    未知／錯誤byte使同byte各事件為None；SDK單項矛盾只令該事件未知。
    read_valid表示這次事件及背包值完整，不等於frame／ROM／畫面已驗證。
    呼叫端須在同一main observation且不tick期間採樣，或使用下方嚴格包裝器。
    """
    result = _empty()
    result['warnings'].append('裸memory API未驗frame；呼叫端須保證同次觀測期間不步進。')
    if not _initialized(progress):
        result['warnings'].append('上游profile／初始化／有效非空隊伍未確認；事件與物品保持未知。')
        return result
    result['initialization_candidate'] = True
    inventory = _inventory_ids(progress.get('inventory'))
    if inventory is None:
        result['warnings'].append('背包未知；不從救援或戰勝事件推定持有Scope／Flute。')
    else:
        result['item_presence'] = {name: item_id in inventory for name, item_id in ITEM_IDS.items()}
    try:
        base = getattr(constants, 'EVENT_FLAGS_ADDRESS', None)
        event_flags = getattr(constants, 'EVENT_FLAGS', None)
    except Exception:
        base = event_flags = None
    if not _integer(base) or base != EVENT_FLAGS_ADDRESS or not isinstance(event_flags, Mapping):
        result['warnings'].append('事件常數基址／mapping不符固定紅版，未讀任何事件byte。')
        return result
    cache = {}
    for name, event_id in TOWER_EVENT_IDS.items():
        try:
            configured = event_flags.get(name)
        except Exception:
            configured = None
        if not _integer(configured) or configured != event_id:
            result['warnings'].append(f'事件 {name} 的SDK ID不符固定來源，保持未知。')
            continue
        address = EVENT_FLAGS_ADDRESS + event_id // 8
        if address not in cache:
            try:
                value = memory[address]
                if not _integer(value) or not 0 <= value <= 255:
                    raise ValueError('invalid byte')
                cache[address] = int(value)
            except Exception:
                cache[address] = None
                result['warnings'].append(f'事件byte {address:#06x} 未可讀，該byte各事件保持未知。')
        value = cache[address]
        result['story_event_bits'][name] = None if value is None else bool(value & (1 << (event_id % 8)))
    result['read_valid'] = inventory is not None and all(v is not None for v in result['story_event_bits'].values())
    return result


def read_tower_observation(pyboy, progress, constants=None, *, observation_frame):
    """可選同frame getter包裝；progress須另由呼叫端附同一observation_frame。

    不修改既有progress.py，也不自行替過期／無標記資料加上目前frame。
    前後frame或上游frame不符時，整包事件及物品均為None，不能保留跨frame True。
    此檢查仍不能代替單一模擬器執行緒／呼叫端同步。
    """
    def invalid(reason):
        result = _empty()
        result['warnings'].append(reason)
        return result

    if type(observation_frame) is not int or observation_frame < 0:
        return invalid('同觀測frame參數不合法，未讀事件。')
    if (not isinstance(progress, dict) or type(progress.get('observation_frame')) is not int
            or progress['observation_frame'] != observation_frame):
        return invalid('上游progress缺同frame標記或已過期；不能自行補造標記。')
    try:
        before = pyboy.frame_count
        if type(before) is not int or before != observation_frame:
            return invalid('PyBoy當前frame與觀測不符，未讀事件。')
        memory = pyboy.memory
        result = read_tower_progress(memory, progress, constants)
        after = pyboy.frame_count
    except Exception:
        return invalid('模擬器getter不可讀；事件與物品皆未知。')
    if type(after) is not int or after != before:
        return invalid('讀取期間frame改變；丟棄整包事件及物品。')
    result['frame_checked'], result['observation_frame'] = True, observation_frame
    result['warnings'] = [w for w in result['warnings'] if not w.startswith('裸memory API未驗frame')]
    return result
