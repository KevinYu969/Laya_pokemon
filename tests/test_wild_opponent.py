"""固定公開來源及禁止寫入的fake memory；不建立PyBoy、不載ROM/存檔。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from laya_pokemon import wild_opponent as w


LOCATION = {'map_id': 23, 'x': 8, 'y': 9}
CONSTANTS = SimpleNamespace(**w.SDK_ANCHORS)


def record():
    # Snorlax Lv30，當前42/140、睡眠2，四格來源招式與剩餘PP。
    return [132, 0, 42, 30, 2, 0, 0, 25, 29, 133, 156, 0,
            0xAB, 0xCD, 30, 0, 140, 0, 75, 0, 49, 0, 29, 0, 49,
            12, 20, 8, 0]


class Memory:
    def __init__(self, values):
        self.values = dict(values)
        self.reads = []
        self.writes = []
        self.hook = None

    def __getitem__(self, address):
        assert type(address) is int
        self.reads.append(address)
        if self.hook:
            value = self.hook(address, self.reads.count(address))
            if value is not None:
                return value
        return self.values[address]

    def __setitem__(self, address, value):
        self.writes.append((address, value))
        raise AssertionError('memory writes forbidden')


class Fake:
    def __init__(self):
        values = dict(zip(w._GUARD_ADDRESSES, (23, 8, 9, 1, 0, 132, 30)))
        values.update({w.ENEMY_MON_ADDRESS + i: b for i, b in enumerate(record())})
        self.memory = Memory(values)
        self.frames = [123, 123]
        self.actions = []

    @property
    def frame_count(self):
        return self.frames.pop(0) if len(self.frames) > 1 else self.frames[0]

    def tick(self, *args):
        raise AssertionError('tick forbidden')

    def button(self, *args):
        raise AssertionError('buttons forbidden')


def read(fake=None, **overrides):
    fake = fake or Fake()
    kwargs = dict(observation_frame=123, expected_location=deepcopy(LOCATION),
                  constants=CONSTANTS, profile=w.PROFILE)
    kwargs.update(overrides)
    result = w.read_wild_opponent(fake, **kwargs)
    assert fake.memory.writes == []
    assert fake.actions == []
    return result


def unknown(result, reason):
    assert result['read_valid'] is False
    assert result['enemy'] is None
    assert result['unknown_reason'] == reason
    assert w.capture_fingerprint(result) is None


def test_happy_full_read_and_capture_minimum():
    fake = Fake()
    before = deepcopy(fake.memory.values)
    result = read(fake)
    assert result['read_valid'] is True
    assert result['live_calibrated'] is False
    assert result['source_commit'] == w.SOURCE_COMMIT
    assert result['location'] == LOCATION
    assert result['observation_frame'] == 123
    assert result['enemy'] == {
        'species': 132, 'internal_id': 132, 'species_name': 'SNORLAX',
        'level': 30, 'hp': 42, 'max_hp': 140, 'status': 2,
        'moves': [29, 133, 156, 0], 'pp': [12, 20, 8, 0],
        'pp_remaining': [12, 20, 8, 0], 'pp_ups': [0, 0, 0, 0],
        'dvs': [171, 205], 'types': [0, 0], 'catch_rate': 25,
        'attack': 75, 'defense': 49, 'speed': 29, 'special': 49}
    assert 'exp' not in result['enemy']
    assert w.capture_fingerprint(result) == {
        'species': 132, 'level': 30, 'hp': 42, 'max_hp': 140, 'status': 2}
    assert fake.memory.values == before
    assert len(fake.memory.reads) == 2 * (7 + 29)


def test_cur_opponent_zero_is_not_assumed_to_mean_no_enemy():
    fake = Fake()
    fake.memory.values[w.SDK_ANCHORS['CURRENT_OPPONENT_ADDRESS']] = 0
    assert read(fake)['read_valid'] is True


@pytest.mark.parametrize('value', [None, '', 'blue', True])
def test_requires_explicit_red_profile(value):
    fake = Fake()
    unknown(read(fake, profile=value), 'wild_red_profile_required')
    assert not fake.memory.reads


@pytest.mark.parametrize('value', [None, True, -1, 1.5, '123'])
def test_frame_input_invalid(value):
    fake = Fake()
    unknown(read(fake, observation_frame=value), 'wild_observation_frame_invalid')
    assert not fake.memory.reads


@pytest.mark.parametrize('value', [None, {}, {'map_id': 1, 'x': 2},
                                   {'map_id': True, 'x': 2, 'y': 3},
                                   {'map_id': 256, 'x': 2, 'y': 3}])
def test_location_input_invalid(value):
    fake = Fake()
    unknown(read(fake, expected_location=value), 'wild_expected_location_invalid')
    assert not fake.memory.reads


@pytest.mark.parametrize('name', list(w.SDK_ANCHORS))
@pytest.mark.parametrize('bad', [None, True, 0, 12.0])
def test_anchor_mismatch_without_reading_memory(name, bad):
    fake = Fake()
    values = dict(w.SDK_ANCHORS)
    values[name] = bad
    unknown(read(fake, constants=SimpleNamespace(**values)), 'wild_sdk_anchor_mismatch')
    assert not fake.memory.reads


def test_missing_anchor_does_not_import_or_guess():
    fake = Fake()
    unknown(read(fake, constants=None), 'wild_sdk_anchor_unavailable')
    assert not fake.memory.reads


@pytest.mark.parametrize('frames,reason', [([122], 'wild_frame_not_current'),
                                         ([True], 'wild_frame_not_current'),
                                         ([123,124], 'wild_frame_changed_during_read'),
                                         ([123,123.0], 'wild_frame_changed_during_read')])
def test_actual_frame_guard(frames, reason):
    fake = Fake()
    fake.frames = frames
    unknown(read(fake), reason)


@pytest.mark.parametrize('address', list(w._GUARD_ADDRESSES) +
                         [w.ENEMY_MON_ADDRESS + i for i in range(29)])
def test_each_getter_exception_fails_without_partial_snapshot(address):
    fake = Fake()
    def fail(a, count):
        if a == address:
            raise RuntimeError('private details must not be copied')
    fake.memory.hook = fail
    unknown(read(fake), 'wild_memory_getter_failed')


@pytest.mark.parametrize('value', [True, False, None, -1, 256, 1.0, '1'])
@pytest.mark.parametrize('address', [w.CUR_MAP, w.ENEMY_MON_ADDRESS + 4])
def test_byte_values_are_exact_integer_bytes(address, value):
    fake = Fake()
    fake.memory.values[address] = value
    unknown(read(fake), 'wild_memory_byte_invalid')


@pytest.mark.parametrize('address,new', [(w.CUR_MAP,24), (w.X_COORD,9), (w.Y_COORD,8),
    (w.IS_IN_BATTLE,0), (w.SDK_ANCHORS['BATTLE_TYPE_ADDRESS'],1),
    (w.SDK_ANCHORS['CURRENT_OPPONENT_ADDRESS'],0),
    (w.SDK_ANCHORS['CURRENT_ENEMY_LEVEL_ADDRESS'],31),
    (w.ENEMY_MON_ADDRESS,133), (w.ENEMY_MON_ADDRESS + 2,41),
    (w.ENEMY_MON_ADDRESS + 4,0), (w.ENEMY_MON_ADDRESS + 8,33),
    (w.ENEMY_MON_ADDRESS + 12,0), (w.ENEMY_MON_ADDRESS + 14,31),
    (w.ENEMY_MON_ADDRESS + 28,1)])
def test_double_snapshot_detects_change_at_same_frame(address, new):
    fake = Fake()
    fake.memory.hook = lambda a,c: new if a == address and c == 2 else None
    unknown(read(fake), 'wild_snapshot_changed_during_read')


@pytest.mark.parametrize('address,new,reason', [
    (w.CUR_MAP,24,'wild_location_does_not_match_observation'),
    (w.X_COORD,9,'wild_location_does_not_match_observation'),
    (w.Y_COORD,8,'wild_location_does_not_match_observation'),
    (w.IS_IN_BATTLE,0,'wild_battle_not_active'),
    (w.IS_IN_BATTLE,2,'wild_battle_not_active'),
    (w.IS_IN_BATTLE,255,'wild_battle_not_active'),
    (w.SDK_ANCHORS['BATTLE_TYPE_ADDRESS'],1,'wild_normal_battle_required'),
    (w.SDK_ANCHORS['BATTLE_TYPE_ADDRESS'],2,'wild_normal_battle_required'),
    (w.SDK_ANCHORS['CURRENT_OPPONENT_ADDRESS'],133,'wild_enemy_species_identity_mismatch'),
    (w.SDK_ANCHORS['CURRENT_ENEMY_LEVEL_ADDRESS'],31,'wild_enemy_level_identity_mismatch')])
def test_static_contradictions_are_unknown(address, new, reason):
    fake = Fake()
    fake.memory.values[address] = new
    unknown(read(fake), reason)


@pytest.mark.parametrize('size', [0, 28, 30, 44])
def test_structure_exact_length(size):
    unknown(w.decode_enemy_mon(([0] * size)), 'enemy_structure_length_invalid')


@pytest.mark.parametrize('value', [None, {}, b'x' * 29, 'x' * 29])
def test_no_coercion_of_structures(value):
    unknown(w.decode_enemy_mon(value), 'enemy_structure_length_invalid')


@pytest.mark.parametrize('species', [0, 31, 32, 86, 181, 182, 183, 184, 191, 255])
def test_missingno_fossils_ghost_and_unknown_rejected(species):
    data = record()
    data[0] = species
    unknown(w.decode_enemy_mon(data), 'enemy_species_unknown')


@pytest.mark.parametrize('offset,value,reason', [
    (14,0,'enemy_level_invalid'), (14,101,'enemy_level_invalid'),
    (1,1,'enemy_hp_invalid'), (16,0,'enemy_hp_invalid'),
    (4,9,'enemy_status_invalid'), (4,128,'enemy_status_invalid'),
    (5,19,'enemy_type_invalid'), (6,255,'enemy_type_invalid'),
    (8,0,'enemy_moves_or_pp_invalid'), (8,166,'enemy_moves_or_pp_invalid'),
    (9,0,'enemy_moves_or_pp_invalid'), (28,1,'enemy_moves_or_pp_invalid'),
    (17,4,'enemy_stats_invalid'), (18,0,'enemy_stats_invalid')])
def test_invalid_structural_fields(offset, value, reason):
    data = record()
    data[offset] = value
    unknown(w.decode_enemy_mon(data), reason)


def test_zero_hp_is_transition_never_capture_baseline():
    fake = Fake()
    fake.memory.values[w.ENEMY_MON_ADDRESS + 2] = 0
    unknown(read(fake), 'enemy_zero_hp_transition')


@pytest.mark.parametrize('status', list(range(8)) + [8,16,32,64])
def test_all_normal_nonvolatile_status_values(status):
    data = record()
    data[4] = status
    assert w.decode_enemy_mon(data)['enemy']['status'] == status


def test_pp_mask_preserves_raw_byte_and_does_not_predict_capture_pp():
    data = record()
    data[25] = 0xCA
    result = w.decode_enemy_mon(data)
    assert result['enemy']['pp'][0] == 0xCA
    assert result['enemy']['pp_remaining'][0] == 10
    assert result['enemy']['pp_ups'][0] == 3


@pytest.mark.parametrize('species', sorted(w._SPECIES))
def test_every_real_internal_species_id_has_static_no_io_name(species):
    data = record()
    data[0] = species
    result = w.decode_enemy_mon(data)
    assert result['read_valid'] is True
    assert result['enemy']['internal_id'] == species


@pytest.mark.parametrize('value', [True, None, -1, 256, 1.0, '1'])
def test_decoder_never_coerces_invalid_bytes(value):
    data = record()
    data[12] = value
    unknown(w.decode_enemy_mon(data), 'enemy_structure_byte_invalid')


@pytest.mark.parametrize('level,hp', [(1,1), (100,999)])
def test_numeric_boundary_values(level, hp):
    data = record()
    data[14] = level
    data[1], data[2] = divmod(hp,256)
    data[15], data[16] = divmod(hp,256)
    assert w.decode_enemy_mon(data)['read_valid'] is True


@pytest.mark.parametrize('field,value', [('profile','other'), ('read_valid',False),
    ('source_commit','master'), ('battle_kind','trainer'), ('enemy',None)])
def test_capture_fingerprint_rejects_unverified_snapshot(field, value):
    snapshot = read()
    snapshot[field] = value
    assert w.capture_fingerprint(snapshot) is None


def test_returned_values_and_minimum_are_detached_copies():
    fake = Fake()
    snapshot = read(fake)
    minimum = w.capture_fingerprint(snapshot)
    minimum['hp'] = 1
    snapshot['enemy']['moves'][0] = 165
    assert fake.memory.values[w.ENEMY_MON_ADDRESS + 8] == 29
    assert snapshot['enemy']['hp'] == 42


def test_source_fixture_hashes_and_internal_ids():
    fixture = json.loads((Path(__file__).parent / 'data/wild-opponent-source-fixture.json').read_text(encoding='utf8'))
    assert fixture['commit'] == w.SOURCE_COMMIT
    for value in fixture['files'].values():
        assert hashlib.sha256(value['text'].encode()).hexdigest() == value['sha256']
        assert w.SOURCE_COMMIT in value['url']
    old = fixture['legacy_crosscheck']
    assert hashlib.sha256(old['text'].encode()).hexdigest() == old['sha256']
    assert 'wEnemyMon:: ; cfe5' in old['text']
    assert 'wBattleMon:: battle_struct wBattleMon ; d014' in old['text']
    names = {int(i,16): name for name,i in re.findall(
        r'^\s*const\s+(\w+)\s*;\s*\$(\w+)', fixture['files']['constants/pokemon_constants.asm']['text'], re.M)
        if name not in ('NO_MON','MON_GHOST') and not name.startswith('FOSSIL_')}
    assert dict(w._SPECIES) == names and len(names) == 151


def test_offsets_derived_from_fixed_source_and_sdk_anchors():
    # field count strictly展開macro；不可把party_struct44誤套EnemyMon。
    assert sum((1,2,1,1,2,1,4,2,1,10,4)) == w.ENEMY_MON_SIZE == 29
    offset = sum((29,5,1,1,11,29,1,1,2,1,max(14,11),2,2,1,1,13))
    assert offset == 114
    assert w.SDK_ANCHORS['CURRENT_OPPONENT_ADDRESS'] - (1 + (6+7)//8) == w.IS_IN_BATTLE
    assert w.IS_IN_BATTLE - offset == w.ENEMY_MON_ADDRESS == 0xCFE5
    assert w.PLAYER_BATTLE_MON_CROSSCHECK == 0xD014
    assert (w.CUR_MAP, w.Y_COORD, w.X_COORD) == (0xD35E,0xD361,0xD362)


def test_getter_has_no_file_io_or_model_import(monkeypatch):
    import builtins
    def forbidden(*args, **kwargs):
        raise AssertionError('file IO/import inside getter forbidden')
    monkeypatch.setattr(builtins, 'open', forbidden)
    monkeypatch.setattr(builtins, '__import__', forbidden)
    assert read()['read_valid'] is True
