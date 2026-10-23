"""固定公開來源與不可寫入 fake memory；不建立模擬器、不載 ROM／存檔。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from laya_pokemon import player_battle as p


LOCATION = {'map_id': 23, 'x': 10, 'y': 61}
CONSTANTS = SimpleNamespace(**p.SDK_ANCHORS)
FIXTURE = Path(__file__).parent / 'data' / 'player-battle-source-fixture.json'


def record():
    # 即時 Venusaur33 HP83/105；不假設 party105 已在此刻回寫。
    return [154, 0, 83, 33, 0, 22, 3, 45, 75, 15, 73, 22,
            0xAB, 0xCD, 33, 0, 105, 0, 75, 0, 70, 0, 65, 0, 90,
            25, 30, 10, 10]


class Memory:
    def __init__(self, values):
        self.values = values
        self.reads = []
        self.hook = None

    def __getitem__(self, address):
        assert type(address) is int
        self.reads.append(address)
        if self.hook:
            return self.hook(address, self.reads.count(address), self.values[address])
        return self.values[address]

    def __setitem__(self, address, value):
        raise AssertionError('禁止 RAM 寫入')


class Fake:
    def __init__(self):
        values = dict(zip(p._GUARD_ADDRESSES, (23, 10, 61, 1, 0, 0, 4)))
        values.update({p.BATTLE_MON_ADDRESS + i: b for i, b in enumerate(record())})
        self.memory = Memory(values)
        self.frames = [123, 123]

    @property
    def frame_count(self):
        value = self.frames.pop(0) if len(self.frames) > 1 else self.frames[0]
        if isinstance(value, Exception):
            raise value
        return value

    def __getattr__(self, name):
        raise AssertionError(f'禁止模擬器操作或額外 getter：{name}')


def read(fake=None, **changes):
    kwargs = {'observation_frame': 123, 'expected_location': deepcopy(LOCATION),
              'constants': CONSTANTS, 'profile': p.PROFILE}
    kwargs.update(changes)
    return p.read_player_battle(fake if fake is not None else Fake(), **kwargs)


def unknown(result, reason):
    assert result['read_valid'] is False
    assert result['unknown_reason'] == reason
    assert result['player'] is None and result['active_party_index'] is None
    assert result['location'] is None and result['battle_kind'] is None
    assert result['live_calibrated'] is False


def test_exact_read_preserves_original_memory_and_never_reads_or_rewrites_party_hp():
    fake = Fake()
    # 這只是額外的 fake party 欄位，getter 根本不該讀它。
    fake.memory.values[p.SDK_ANCHORS['PARTY_MONS_ADDRESS'] + 2] = 105
    before = deepcopy(fake.memory.values)
    result = read(fake)
    assert result['read_valid'] is True and result['active_party_index'] == 0
    assert result['location'] == LOCATION and result['battle_kind'] == 'wild'
    assert result['observation_frame'] == 123 and result['live_calibrated'] is False
    assert result['player'] == {
        'species': 154, 'internal_id': 154, 'species_name': 'VENUSAUR',
        'level': 33, 'hp': 83, 'max_hp': 105, 'status': 0,
        'moves': [75, 15, 73, 22], 'pp': [25, 30, 10, 10],
        'pp_remaining': [25, 30, 10, 10], 'pp_ups': [0, 0, 0, 0],
        'dvs': [171, 205], 'types': [22, 3],
        'attack': 75, 'defense': 70, 'speed': 65, 'special': 90}
    assert fake.memory.values == before
    assert fake.memory.reads == (list(p._GUARD_ADDRESSES)
                                + list(range(0xD014, 0xD014 + 29)) * 2
                                + list(p._GUARD_ADDRESSES))
    assert p.SDK_ANCHORS['PARTY_MONS_ADDRESS'] + 2 not in fake.memory.reads
    assert 'exp' not in result['player']


@pytest.mark.parametrize('active,count', [(0, 1), (0, 4), (3, 4), (5, 6)])
def test_active_index_is_zero_based_and_checked_against_current_party_count(active, count):
    fake = Fake()
    fake.memory.values.update({p.ACTIVE_PARTY_INDEX_ADDRESS: active,
                               p.SDK_ANCHORS['PARTY_COUNT_ADDRESS']: count})
    assert read(fake)['active_party_index'] == active


@pytest.mark.parametrize('active,count', [(4, 4), (6, 6), (0, 0), (0, 7), (255, 4)])
def test_invalid_party_count_or_index_has_no_partial_player(active, count):
    fake = Fake()
    fake.memory.values.update({p.ACTIVE_PARTY_INDEX_ADDRESS: active,
                               p.SDK_ANCHORS['PARTY_COUNT_ADDRESS']: count})
    unknown(read(fake), 'player_battle_active_party_index_invalid')


def test_normal_trainer_battle_can_be_read_without_claiming_capture_eligibility():
    fake = Fake()
    fake.memory.values[p.IS_IN_BATTLE] = 2
    assert read(fake)['battle_kind'] == 'trainer'


@pytest.mark.parametrize('value', [None, '', 'blue', True])
def test_explicit_source_profile_required_before_memory_access(value):
    fake = Fake()
    unknown(read(fake, profile=value), 'player_battle_red_profile_required')
    assert fake.memory.reads == []


@pytest.mark.parametrize('value', [None, True, -1, 1.5, '123'])
def test_invalid_observation_frame(value):
    unknown(read(observation_frame=value), 'player_battle_observation_frame_invalid')


@pytest.mark.parametrize('value', [None, {}, {'map_id': 23, 'x': 10},
                                  {'map_id': True, 'x': 10, 'y': 61},
                                  {'map_id': 23, 'x': -1, 'y': 61},
                                  {'map_id': 23, 'x': 10, 'y': 256}])
def test_invalid_expected_location(value):
    unknown(read(expected_location=value), 'player_battle_expected_location_invalid')


@pytest.mark.parametrize('name', p.SDK_ANCHORS)
@pytest.mark.parametrize('value', [None, True, -1, 0, 123, 'address'])
def test_sdk_anchor_mismatch_cannot_read_memory(name, value):
    fake = Fake()
    constants = dict(p.SDK_ANCHORS, **{name: value})
    unknown(read(fake, constants=SimpleNamespace(**constants)), 'player_battle_sdk_anchor_mismatch')
    assert fake.memory.reads == []


def test_sdk_anchor_missing_is_unknown():
    unknown(read(constants=SimpleNamespace()), 'player_battle_sdk_anchor_unavailable')


@pytest.mark.parametrize('address', list(p._GUARD_ADDRESSES) + list(range(0xD014, 0xD031)))
@pytest.mark.parametrize('value', [True, None, -1, 256])
def test_every_memory_byte_must_be_an_actual_byte(address, value):
    fake = Fake()
    fake.memory.values[address] = value
    unknown(read(fake), 'player_battle_memory_byte_invalid')


@pytest.mark.parametrize('address', list(p._GUARD_ADDRESSES) + list(range(0xD014, 0xD031)))
def test_each_guard_and_each_structure_byte_is_double_read(address):
    fake = Fake()
    fake.memory.hook = lambda a, n, v: v ^ 1 if a == address and n == 2 else v
    unknown(read(fake), 'player_battle_snapshot_changed_during_read')


@pytest.mark.parametrize('frames,reason', [
    ([122, 122], 'player_battle_frame_not_current'),
    ([True, True], 'player_battle_frame_not_current'),
    ([123, 124], 'player_battle_frame_changed_during_read'),
    ([123, True], 'player_battle_frame_changed_during_read'),
    ([RuntimeError('getter')], 'player_battle_memory_getter_failed'),
])
def test_frame_getter_boundaries(frames, reason):
    fake = Fake()
    fake.frames = frames
    unknown(read(fake), reason)


def test_memory_getter_exception_is_unknown():
    fake = Fake()
    fake.memory.values.pop(p.BATTLE_MON_ADDRESS + 12)
    unknown(read(fake), 'player_battle_memory_getter_failed')


@pytest.mark.parametrize('address', [p.CUR_MAP, p.X_COORD, p.Y_COORD])
def test_stable_but_wrong_location_is_not_accepted(address):
    fake = Fake()
    fake.memory.values[address] += 1
    unknown(read(fake), 'player_battle_location_does_not_match_observation')


@pytest.mark.parametrize('value', [0, 3, 255])
def test_outside_normal_active_battle_is_unknown(value):
    fake = Fake()
    fake.memory.values[p.IS_IN_BATTLE] = value
    unknown(read(fake), 'player_battle_not_active')


@pytest.mark.parametrize('value', [1, 2, 255])
def test_old_man_safari_and_unknown_battle_type_rejected(value):
    fake = Fake()
    fake.memory.values[p.SDK_ANCHORS['BATTLE_TYPE_ADDRESS']] = value
    unknown(read(fake), 'player_battle_normal_battle_required')


@pytest.mark.parametrize('index,value,reason', [
    (0, 0, 'species_unknown'), (0, 31, 'species_unknown'), (0, 255, 'species_unknown'),
    (14, 0, 'level_invalid'), (14, 101, 'level_invalid'),
    (2, 106, 'hp_invalid'), (15, 4, 'hp_invalid'), (16, 0, 'hp_invalid'),
    (4, 9, 'status_invalid'), (4, 128, 'status_invalid'),
    (5, 9, 'type_invalid'), (6, 255, 'type_invalid'),
    (8, 0, 'moves_or_pp_invalid'), (9, 166, 'moves_or_pp_invalid'),
    (10, 0, 'moves_or_pp_invalid'), (17, 4, 'stats_invalid'),
    (18, 0, 'stats_invalid'),
])
def test_malformed_complete_structure_is_unknown(index, value, reason):
    fake = Fake()
    fake.memory.values[0xD014 + index] = value
    unknown(read(fake), 'player_battle_' + reason)


def test_zero_hp_is_an_observed_faint_not_an_invented_healthy_party():
    fake = Fake()
    fake.memory.values[0xD015] = fake.memory.values[0xD016] = 0
    result = read(fake)
    assert result['read_valid'] is True and result['player']['hp'] == 0


def test_pp_ups_and_zero_pp_are_retained_without_permission_to_use_a_move():
    fake = Fake()
    fake.memory.values.update({0xD02D: 0xC0, 0xD02E: 0x85})
    player = read(fake)['player']
    assert player['pp'][:2] == [0xC0, 0x85]
    assert player['pp_remaining'][:2] == [0, 5] and player['pp_ups'][:2] == [3, 2]


@pytest.mark.parametrize('status', list(range(8)) + [8, 16, 32, 64])
def test_source_status_values_preserved(status):
    fake = Fake()
    fake.memory.values[0xD018] = status
    assert read(fake)['player']['status'] == status


def test_empty_tail_move_and_pp_slots_are_valid_and_return_fresh_lists():
    values = record()
    values[10:12] = [0, 0]
    values[27:29] = [0, 0]
    before = values.copy()
    decoded = p.decode_player_battle(values)
    assert decoded['read_valid'] is True
    decoded['player']['moves'][0] = 1
    assert values == before


@pytest.mark.parametrize('value', [None, [], [0] * 28, [0] * 30, 'x' * 29])
def test_pure_decoder_rejects_wrong_structure(value):
    assert p.decode_player_battle(value)['player'] is None


def test_fixed_public_source_fixture_derives_both_addresses_and_copy_boundary():
    f = json.loads(FIXTURE.read_text(encoding='utf-8'))
    assert f['commit'] == p.SOURCE_COMMIT
    assert f['sdk_anchors'] == dict(p.SDK_ANCHORS)
    for item in f['files'].values():
        assert hashlib.sha256(item['text'].encode('utf-8')).hexdigest() == item['sha256']
    for item in f['additional_source_excerpts'].values():
        assert re.fullmatch('[0-9a-f]{40}', item['git_blob_sha'])
        for excerpt in item['excerpts']:
            assert hashlib.sha256(excerpt['text'].encode('utf-8')).hexdigest() == excerpt['sha256']
    ram = f['files']['ram/wram.asm']['text']
    macros = f['files']['macros/ram.asm']['text']
    def macro_size(name, constants=None):
        block = re.search(r'MACRO ' + name + r'\n(.*?)ENDM', macros, re.S)[1]
        size = 0
        for op, arg in re.findall(r'(?:^|::)\s*(db|dw|ds)\b([^\n;]*)', block, re.M):
            size += 1 if op == 'db' else 2 if op == 'dw' else eval(arg.strip(), {'__builtins__': {}}, constants or {})
        return size
    assert macro_size('spritestatedata1') == macro_size('spritestatedata2') == 16
    assert macro_size('sprite_oam_struct') == 4
    assert macro_size('battle_struct', {'NUM_MOVES': 4}) == p.BATTLE_MON_SIZE == 29
    assert sum(f['active_index_source_derivation']) == p.ACTIVE_PARTY_INDEX_ADDRESS == 0xCC2F
    preamble = ram.split('SECTION "WRAM", WRAM0')[1].split('wPlayerMonNumber::')[0]
    sizes = re.findall(r'(?:^|::)\s*(db|dw|ds)\b([^\n;]*)', preamble, re.M)
    assert sum(1 if op == 'db' else 2 if op == 'dw' else eval(arg.strip(), {'__builtins__': {}}, {'SCREEN_WIDTH': 20}) for op, arg in sizes) == 51
    assert 0xC100 + 512 + 160 + 360 + 480 + 1300 + 51 == p.ACTIVE_PARTY_INDEX_ADDRESS
    assert p.SDK_ANCHORS['CURRENT_OPPONENT_ADDRESS'] - 2 - 67 == p.BATTLE_MON_ADDRESS == 0xD014
    assert f['active_index_direct_sdk_constant_available'] is False
    core = '\n'.join(e['text'] for e in f['additional_source_excerpts']['engine/battle/core.asm']['excerpts'])
    main = core.split('MainInBattleLoop:')[1].split('.selectEnemyMove')[0]
    assert main.index('call ReadPlayerMonCurHPAndStatus') < main.index('ld hl, wBattleMonHP')
    assert 'call DisplayBattleMenu ; show battle menu' in core
    assert 'ld hl, wBattleMonHP\n\tld bc, MON_STATUS + 1 - MON_HP' in core
    assert 'ld d, h\n\tld e, l\n\tld hl, wBattleMonHP' in core
    end = f['additional_source_excerpts']['engine/battle/end_of_battle.asm']['excerpts'][0]['text']
    assert 'ReadPlayerMonCurHPAndStatus' not in end and 'wBattleMonHP' not in end
