"""紅版野生百變怪變身的唯讀證據；不操作遊戲、不替換觀測或隊伍資料。"""
from collections.abc import Mapping

SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
PROFILE = 'red-en-ditto-transform-source-v1'
KO_PROFILE = 'red-en-ditto-zero-hp-faint-source-v1'
SDK_ANCHORS = {'CURRENT_OPPONENT_ADDRESS': 0xD059, 'BATTLE_TYPE_ADDRESS': 0xD05A,
               'TRAINER_NUMBER_ADDRESS': 0xD05D, 'PARTY_COUNT_ADDRESS': 0xD163,
               'PARTY_SPECIES_ADDRESS': 0xD164, 'NAME_LENGTH': 11}
# 固定wram布局：D059後16 byte為EnemyBattleStatus3；TRANSFORMED為bit3。
ENEMY_STATUS3 = 0xD069
ORIGINAL_SPECIES = 0xCFD8
ENEMY_NICK = 0xCFDA
ENEMY_SPECIES = 0xCFE5
ENEMY_TYPE1 = 0xCFEA
ENEMY_TYPE2 = 0xCFEB
_DITTO_NICK = (131, 136, 147, 147, 142, 80, 80, 80, 80, 80, 80)
_TYPES = {'NORMAL': 0, 'FIGHTING': 1, 'FLYING': 2, 'POISON': 3, 'GROUND': 4,
          'ROCK': 5, 'BUG': 7, 'GHOST': 8, 'FIRE': 20, 'WATER': 21,
          'GRASS': 22, 'ELECTRIC': 23, 'PSYCHIC': 24, 'ICE': 25, 'DRAGON': 26}


def _unknown(reason):
    return {'read_valid': False, 'unknown_reason': reason, 'profile': PROFILE,
            'source_commit': SOURCE_COMMIT, 'live_calibrated': False}


def _byte(value):
    if type(value) is not int or not 0 <= value <= 255:
        raise ValueError('byte_invalid')
    return value


def _species(reference_data, number):
    if (not isinstance(reference_data, Mapping) or reference_data.get('source_commit') != SOURCE_COMMIT
            or not isinstance(reference_data.get('species'), Mapping)):
        raise ValueError('reference_unverified')
    found = [(name, data) for name, data in reference_data['species'].items()
             if isinstance(data, Mapping) and type(data.get('id')) is int and data['id'] == number]
    if len(found) != 1 or not isinstance(found[0][0], str):
        raise ValueError('effective_species_unknown_or_ambiguous')
    name, data = found[0]
    types = data.get('types')
    if not isinstance(types, (list, tuple)) or not 1 <= len(types) <= 2 or any(t not in _TYPES for t in types):
        raise ValueError('reference_types_unknown')
    expected = [_TYPES[types[0]], _TYPES[types[-1]]]
    return name, list(types), expected


def _certificate(raw, reference_data, frame):
    if type(frame) is not int or frame < 0:
        raise ValueError('frame_invalid')
    if any(type(raw[k]) is not int for k in ('wild', 'battle_type', 'status3', 'original', 'effective', 'cur_opponent')):
        raise ValueError('signal_byte_invalid')
    for k in ('wild', 'battle_type', 'status3', 'original', 'effective', 'cur_opponent'):
        _byte(raw[k])
    if raw['wild'] != 1 or raw['battle_type'] != 0 or not raw['status3'] & 8 or raw['status3'] & 0xF0:
        raise ValueError('not_normal_transformed_wild')
    if raw['original'] != 76 or tuple(raw['nick']) != _DITTO_NICK:
        raise ValueError('original_ditto_identity_unverified')
    if any(type(x) is not int for x in raw['nick']):
        raise ValueError('nickname_byte_invalid')
    original_name, _, _ = _species(reference_data, 76)
    if original_name != 'DITTO':
        raise ValueError('original_reference_unverified')
    name, types, expected = _species(reference_data, raw['effective'])
    if (not isinstance(raw['types'], (list, tuple)) or len(raw['types']) != 2
            or any(type(x) is not int for x in raw['types']) or list(raw['types']) != expected):
        raise ValueError('copied_types_disagree_with_reference')
    party = raw['party']
    if (not isinstance(party, (list, tuple)) or not 1 <= len(party) <= 6
            or any(type(x) is not int for x in party) or party.count(raw['effective']) != 1):
        raise ValueError('copied_target_not_unique_in_same_frame_party')
    for number in party:
        _species(reference_data, number)
    return {'read_valid': True, 'unknown_reason': None, 'profile': PROFILE,
            'source_commit': SOURCE_COMMIT, 'live_calibrated': False, 'observation_frame': frame,
            'original_species': 76, 'original_name': 'DITTO', 'original_nickname_bytes': list(raw['nick']),
            'effective_species': raw['effective'], 'effective_name': name,
            'effective_type_bytes': list(raw['types']), 'effective_types': types,
            'party_species': list(party), 'transformed_bit': 3,
            'raw_flags': {'is_in_battle': raw['wild'], 'battle_type': raw['battle_type'],
                          'enemy_battle_status3': raw['status3'], 'cur_opponent': raw['cur_opponent']}}


def read_ditto_transform(pyboy, *, observation_frame, constants, reference_data):
    """同執行緒、無tick的雙讀證據；未知不給部分有效欄位。"""
    try:
        for key, expected in SDK_ANCHORS.items():
            value = constants.get(key) if isinstance(constants, Mapping) else getattr(constants, key, None)
            if type(value) is not int or value != expected:
                return _unknown('sdk_anchor_unverified')
        if type(observation_frame) is not int or observation_frame < 0:
            return _unknown('frame_invalid')
        before = pyboy.frame_count
        if type(before) is not int or before != observation_frame:
            return _unknown('observation_frame_disagrees')

        def snapshot():
            memory = pyboy.memory
            count = _byte(memory[SDK_ANCHORS['PARTY_COUNT_ADDRESS']])
            if not 1 <= count <= 6:
                raise ValueError('party_count_invalid')
            party = [_byte(memory[SDK_ANCHORS['PARTY_SPECIES_ADDRESS'] + i]) for i in range(count)]
            if _byte(memory[SDK_ANCHORS['PARTY_SPECIES_ADDRESS'] + count]) != 255:
                raise ValueError('party_terminator_unverified')
            return {'wild': _byte(memory[0xD057]), 'battle_type': _byte(memory[0xD05A]),
                    'status3': _byte(memory[ENEMY_STATUS3]), 'original': _byte(memory[ORIGINAL_SPECIES]),
                    'effective': _byte(memory[ENEMY_SPECIES]),
                    'cur_opponent': _byte(memory[SDK_ANCHORS['CURRENT_OPPONENT_ADDRESS']]),
                    'nick': [_byte(memory[ENEMY_NICK + i]) for i in range(11)],
                    'types': [_byte(memory[ENEMY_TYPE1]), _byte(memory[ENEMY_TYPE2])], 'party': party}

        first, second = snapshot(), snapshot()
        after = pyboy.frame_count
        if type(after) is not int or after != before:
            return _unknown('frame_changed_during_read')
        if first != second:
            return _unknown('bytes_changed_during_read')
        return _certificate(first, reference_data, before)
    except Exception as error:
        return _unknown(str(error) if isinstance(error, ValueError) else 'getter_failed')


def verified_effective_enemy(signal, *, visible_enemy, ram_enemy, party, observation_frame, reference_data):
    """只放行可見原名DITTO與同幀有效複製目標；不靠read_valid單一旗標。"""
    try:
        if (not isinstance(signal, dict) or signal.get('read_valid') is not True
                or visible_enemy != 'DITTO' or signal.get('effective_name') != ram_enemy
                or type(observation_frame) is not int or type(signal.get('observation_frame')) is not int
                or signal.get('observation_frame') != observation_frame
                or not isinstance(party, (list, tuple))
                or any(not isinstance(m, dict) or type(m.get('species')) is not int for m in party)
                or [m.get('species') for m in party] != signal.get('party_species')):
            return None
        flags = signal['raw_flags']
        raw = {'wild': flags['is_in_battle'], 'battle_type': flags['battle_type'],
               'status3': flags['enemy_battle_status3'], 'cur_opponent': flags['cur_opponent'],
               'original': signal['original_species'], 'effective': signal['effective_species'],
               'nick': signal['original_nickname_bytes'], 'types': signal['effective_type_bytes'],
               'party': signal['party_species']}
        if _certificate(raw, reference_data, observation_frame) != signal:
            return None
        return signal['effective_name']
    except Exception:
        return None


def _ko_certificate(raw, reference_data, frame):
    """獨立擊倒證據；不設定或合成存活變身位元。"""
    if type(frame) is not int or frame < 0:
        raise ValueError('frame_invalid')
    for key in ('wild', 'battle_type', 'status3', 'original', 'effective', 'cur_opponent', 'status'):
        _byte(raw[key])
    if raw['wild'] != 1 or raw['battle_type'] != 0 or raw['status3'] != 0:
        raise ValueError('not_normal_wild_cleared_faint_flags')
    if (raw['hp_bytes'] != [0, 0] or any(type(x) is not int for x in raw['hp_bytes'])
            or raw['status'] not in set(range(8)) | {8, 16, 32, 64}):
        raise ValueError('not_exact_zero_hp_faint_transition')
    if (raw['original'] != 76 or tuple(raw['nick']) != _DITTO_NICK
            or any(type(x) is not int for x in raw['nick'])):
        raise ValueError('original_ditto_identity_unverified')
    if _species(reference_data, 76)[0] != 'DITTO':
        raise ValueError('original_reference_unverified')
    name, types, expected = _species(reference_data, raw['effective'])
    if (not isinstance(raw['types'], (list, tuple)) or len(raw['types']) != 2
            or any(type(x) is not int for x in raw['types']) or list(raw['types']) != expected):
        raise ValueError('copied_types_disagree_with_reference')
    party = raw['party']
    if (not isinstance(party, (list, tuple)) or not 1 <= len(party) <= 6
            or any(type(x) is not int for x in party) or party.count(raw['effective']) != 1):
        raise ValueError('copied_target_not_unique_in_same_frame_party')
    for number in party:
        _species(reference_data, number)
    return {'read_valid': True, 'unknown_reason': None, 'profile': KO_PROFILE,
            'stage': 'enemy_zero_hp_faint_transition', 'source_commit': SOURCE_COMMIT,
            'live_calibrated': False, 'observation_frame': frame,
            'original_species': 76, 'original_name': 'DITTO', 'original_nickname_bytes': list(raw['nick']),
            'effective_species': raw['effective'], 'effective_name': name,
            'effective_type_bytes': list(raw['types']), 'effective_types': types,
            'party_species': list(party), 'enemy_hp': 0, 'enemy_hp_bytes': list(raw['hp_bytes']),
            'enemy_status': raw['status'],
            'raw_flags': {'is_in_battle': raw['wild'], 'battle_type': raw['battle_type'],
                          'enemy_battle_status3': raw['status3'], 'cur_opponent': raw['cur_opponent']}}


def read_ditto_ko_transition(pyboy, *, observation_frame, constants, reference_data):
    """同幀雙讀真實0HP與清除後flags；不讀寫外部檔案或操作遊戲。"""
    def unknown(reason):
        return {'read_valid': False, 'unknown_reason': reason, 'profile': KO_PROFILE,
                'source_commit': SOURCE_COMMIT, 'live_calibrated': False}
    try:
        for key, expected in SDK_ANCHORS.items():
            value = constants.get(key) if isinstance(constants, Mapping) else getattr(constants, key, None)
            if type(value) is not int or value != expected:
                return unknown('sdk_anchor_unverified')
        before = pyboy.frame_count
        if type(observation_frame) is not int or type(before) is not int or before != observation_frame or before < 0:
            return unknown('observation_frame_disagrees')
        def snapshot():
            memory = pyboy.memory
            count = _byte(memory[SDK_ANCHORS['PARTY_COUNT_ADDRESS']])
            if not 1 <= count <= 6:
                raise ValueError('party_count_invalid')
            party = [_byte(memory[SDK_ANCHORS['PARTY_SPECIES_ADDRESS'] + i]) for i in range(count)]
            if _byte(memory[SDK_ANCHORS['PARTY_SPECIES_ADDRESS'] + count]) != 255:
                raise ValueError('party_terminator_unverified')
            return {'wild': _byte(memory[0xD057]), 'battle_type': _byte(memory[0xD05A]),
                    'status3': _byte(memory[ENEMY_STATUS3]), 'original': _byte(memory[ORIGINAL_SPECIES]),
                    'effective': _byte(memory[ENEMY_SPECIES]), 'cur_opponent': _byte(memory[0xD059]),
                    'nick': [_byte(memory[ENEMY_NICK + i]) for i in range(11)],
                    'types': [_byte(memory[ENEMY_TYPE1]), _byte(memory[ENEMY_TYPE2])], 'party': party,
                    'hp_bytes': [_byte(memory[ENEMY_SPECIES + i]) for i in (1, 2)],
                    'status': _byte(memory[ENEMY_SPECIES + 4])}
        first, second = snapshot(), snapshot()
        after = pyboy.frame_count
        if type(after) is not int or after != before:
            return unknown('frame_changed_during_read')
        if first != second:
            return unknown('bytes_changed_during_read')
        return _ko_certificate(first, reference_data, before)
    except Exception as error:
        return unknown(str(error) if isinstance(error, ValueError) else 'getter_failed')


def verified_ko_transition(signal, *, ram_enemy, party, observation_frame, reference_data):
    """重驗獨立擊倒證書與原隊順序，不將read_valid本身當充分證據。"""
    try:
        if (not isinstance(signal, dict) or signal.get('read_valid') is not True
                or type(observation_frame) is not int or type(signal.get('observation_frame')) is not int
                or type(signal.get('enemy_hp')) is not int or signal.get('enemy_hp') != 0
                or signal.get('observation_frame') != observation_frame or signal.get('effective_name') != ram_enemy
                or not isinstance(party, (list, tuple))
                or any(not isinstance(mon, dict) or type(mon.get('species')) is not int for mon in party)
                or [mon['species'] for mon in party] != signal.get('party_species')):
            return None
        flags = signal['raw_flags']
        raw = {'wild': flags['is_in_battle'], 'battle_type': flags['battle_type'],
               'status3': flags['enemy_battle_status3'], 'cur_opponent': flags['cur_opponent'],
               'original': signal['original_species'], 'effective': signal['effective_species'],
               'nick': signal['original_nickname_bytes'], 'types': signal['effective_type_bytes'],
               'party': signal['party_species'], 'hp_bytes': signal['enemy_hp_bytes'], 'status': signal['enemy_status']}
        return signal if _ko_certificate(raw, reference_data, observation_frame) == signal else None
    except Exception:
        return None

