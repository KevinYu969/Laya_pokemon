"""固定紅版火箭基地唯讀進度候選；尚未整合既有progress／journal。

只索引呼叫端提供的memory；不匯入PyBoy、不讀檔、不推進遊戲、不寫記憶體。
真正story event與目前持有道具分開，任何讀值皆不是本次新達成的里程碑。
"""
from collections.abc import Mapping
from numbers import Integral
from types import MappingProxyType


SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
SOURCE_ROOT = f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/'
SOURCES = [SOURCE_ROOT + path for path in (
    'constants/event_constants.asm', 'constants/item_constants.asm', 'ram/wram.asm',
    'scripts/GameCorner.asm', 'scripts/RocketHideoutB4F.asm',
    'constants/toggle_constants.asm', 'data/maps/objects/RocketHideoutB4F.asm')]
PROFILE = 'fixed-red-rocket-progress-candidate-v1-unvalidated'
UPSTREAM_PROFILE = 'gen1-wrapper-ram-progress-v1-unvalidated'
# PyBoy既有固定Gen1 constants的wEventFlags基址；呼叫端須傳入相同常數契約。
# 每個事件ID另與固定pret原始碼逐一核對，不以同名但不同ID靜默替代。
EVENT_FLAGS_ADDRESS = 0xD747
ROCKET_EVENT_IDS = MappingProxyType({
    'found_rocket_hideout': 0x1B9,
    'beat_rocket_hideout_1_trainer_0': 0x671,
    'beat_rocket_hideout_1_trainer_1': 0x672,
    'beat_rocket_hideout_1_trainer_2': 0x673,
    'beat_rocket_hideout_1_trainer_3': 0x674,
    'beat_rocket_hideout_1_trainer_4': 0x675,
    'beat_rocket_hideout_2_trainer_0': 0x681,
    'beat_rocket_hideout_3_trainer_0': 0x691,
    'beat_rocket_hideout_3_trainer_1': 0x692,
    'beat_rocket_hideout_4_trainer_0': 0x6A2,
    'beat_rocket_hideout_4_trainer_1': 0x6A3,
    'beat_rocket_hideout_4_trainer_2': 0x6A4,
    'rocket_hideout_4_door_unlocked': 0x6A5,
    'rocket_dropped_lift_key': 0x6A6,
    'beat_rocket_hideout_giovanni': 0x6A7,
})
ITEM_IDS = MappingProxyType({'has_lift_key': 74, 'has_silph_scope': 72})


def _integer(value):
    return isinstance(value, Integral) and not isinstance(value, bool)


def _initialized(progress):
    if (not isinstance(progress, dict) or progress.get('profile') != UPSTREAM_PROFILE
            or progress.get('party_read_valid') is not True
            or progress.get('initialization_candidate') is not True):
        return False
    party, count = progress.get('party'), progress.get('party_count')
    if (not isinstance(party, list) or not _integer(count) or not 1 <= count <= 6
            or len(party) != count):
        return False
    for mon in party:
        if (not isinstance(mon, dict)
                or not all(_integer(mon.get(key)) for key in ('species', 'level', 'hp', 'max_hp'))
                or not 1 <= mon['species'] <= 190 or not 1 <= mon['level'] <= 100
                or mon['max_hp'] <= 0 or not 0 <= mon['hp'] <= mon['max_hp']):
            return False
    return True


def _inventory_ids(inventory):
    if (not isinstance(inventory, list) or len(inventory) > 20
            or any(not isinstance(row, dict) or set(row) != {'item', 'quantity'}
                   or not _integer(row['item']) or not 1 <= row['item'] <= 255
                   or not _integer(row['quantity']) or not 1 <= row['quantity'] <= 99 for row in inventory)):
        return None
    ids = [row['item'] for row in inventory]
    return set(ids) if len(ids) == len(set(ids)) else None


def read_rocket_progress(memory, progress, constants=None):
    """以同一觀測的既有progress與常數契約解碼；未知維持None，不產生milestone。

    memory僅需__getitem__(address)，測試使用拒絕寫入的合成物件。
    constants必須明確提供EVENT_FLAGS_ADDRESS及EVENT_FLAGS；不自動載SDK或猜預設。
    只有正常有效的非空隊伍／profile才開始讀事件。道具訊號只表目前背包持有，
    不能用dropped-key或Giovanni事件推定已撿取，更不能加出不存在的got_* event。
    """
    result = {'profile': PROFILE, 'source_commit': SOURCE_COMMIT, 'sources': SOURCES,
              'initialization_candidate': False,
              'story_event_bits': {name: None for name in ROCKET_EVENT_IDS},
              'item_presence': {name: None for name in ITEM_IDS},
              'event_locations': {name: {'event_id': event_id,
                                         'address': EVENT_FLAGS_ADDRESS + event_id // 8,
                                         'bit': event_id % 8} for name, event_id in ROCKET_EVENT_IDS.items()},
              'warnings': ['這是目前觀測值；首次為True不是本次新達成的里程碑，仍須正常畫面／交易證據。']}
    if not _initialized(progress):
        result['warnings'].append('上游初始化／隊伍／profile未確認；火箭基地事件與道具保持未知。')
        return result
    result['initialization_candidate'] = True
    result['warnings'].append('有效上游非空隊伍僅是初始化候選，不等同畫面或ROM版本已校準。')
    inventory = _inventory_ids(progress.get('inventory'))
    if inventory is None:
        result['warnings'].append('背包尚不可驗證；道具持有保持未知。')
    else:
        result['item_presence'] = {name: item_id in inventory for name, item_id in ITEM_IDS.items()}
    base = getattr(constants, 'EVENT_FLAGS_ADDRESS', None)
    event_flags = getattr(constants, 'EVENT_FLAGS', None)
    if not _integer(base) or base != EVENT_FLAGS_ADDRESS or not isinstance(event_flags, Mapping):
        result['warnings'].append('事件基址／常數契約未符合固定紅版；不讀事件記憶體。')
        return result
    cache = {}
    for name, event_id in ROCKET_EVENT_IDS.items():
        configured = event_flags.get(name)
        if not _integer(configured) or configured != event_id:
            result['warnings'].append(f'事件 {name} 的固定來源ID尚不可確認；保持未知。')
            continue
        address = int(base) + event_id // 8
        if address not in cache:
            try:
                value = memory[address]
                if not _integer(value) or not 0 <= value <= 255:
                    raise ValueError('不是合法byte')
                cache[address] = int(value)
            except (AttributeError, KeyError, IndexError, TypeError, ValueError, RuntimeError):
                cache[address] = None
                result['warnings'].append(f'事件位址 {address:#06x} 尚不可讀；該byte保持未知。')
        value = cache[address]
        result['story_event_bits'][name] = None if value is None else bool(value & (1 << (event_id % 8)))
    return result
