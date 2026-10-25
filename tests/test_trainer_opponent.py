"""真候選＋唯讀 fake memory；不建立 PyBoy、不載 ROM、不送按鍵。"""
from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import laya_pokemon
import pytest


ROOT = Path(laya_pokemon.__file__).resolve().parents[2]
STAGE = ROOT / '.local/staged-medicine-final-20261025'


def source_for_test(test_path):
    path = Path(test_path).resolve()
    if path == STAGE / 'test_trainer_opponent.py':
        return STAGE / 'trainer_opponent.py'
    if path == ROOT / 'tests/test_trainer_opponent.py':
        return ROOT / 'src/laya_pokemon/trainer_opponent.py'
    raise RuntimeError('未知 trainer_opponent 測試位置')


SPEC = importlib.util.spec_from_file_location(
    'laya_pokemon._independent_trainer_opponent', source_for_test(__file__))
t = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(t)

FRAME = 1732097
LOCATION = {'map_id': 166, 'x': 4, 'y': 6}
# 獨立固定來源位址與 literal fixture，未依候選 guard 清單生成 RAM。
GUARDS = (0xD35E, 0xD362, 0xD361, 0xD057, 0xD05A, 0xD059, 0xD127)
RECORD = tuple(range(0xCFE5, 0xCFE5 + 29))
ADDRESSES = GUARDS + RECORD
SDK_VALUES = {
    'CURRENT_OPPONENT_ADDRESS': 0xD059, 'BATTLE_TYPE_ADDRESS': 0xD05A,
    'CURRENT_ENEMY_LEVEL_ADDRESS': 0xD127, 'PARTY_COUNT_ADDRESS': 0xD163,
    'PARTY_MONS_ADDRESS': 0xD16B, 'OBTAINED_BADGES_ADDRESS': 0xD356,
}


def record():
    # 合成 Ninetales36；current_opponent206 是 trainer code，與物種83不同。
    return [83, 0, 80, 0, 0, 20, 20, 75, 52, 39, 98, 109,
            0x98, 0x88, 36, 0, 105, 0, 70, 0, 65, 0, 85, 0, 80,
            20, 30, 25, 10]


class ReadOnlySDK:
    def __getattr__(self, name):
        try:
            return SDK_VALUES[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name, value):
        raise AssertionError('SDK writes forbidden')


class Memory:
    def __init__(self):
        self.values = {0xD35E: 166, 0xD362: 4, 0xD361: 6,
                       0xD057: 2, 0xD05A: 0, 0xD059: 206, 0xD127: 36}
        self.values.update(dict(zip(RECORD, record())))
        self.reads = []
        self.writes = []
        self.hook = None

    def __getitem__(self, address):
        assert type(address) is int
        self.reads.append(address)
        value = self.values[address]
        return self.hook(address, self.reads.count(address), value) if self.hook else value

    def __setitem__(self, address, value):
        self.writes.append((address, value))
        raise AssertionError('memory writes forbidden')


class Game:
    def __init__(self):
        self.memory = Memory()
        self.frames = [FRAME, FRAME]

    @property
    def frame_count(self):
        return self.frames.pop(0) if len(self.frames) > 1 else self.frames[0]

    def tick(self, *args, **kwargs):
        raise AssertionError('tick forbidden')

    def button(self, *args, **kwargs):
        raise AssertionError('buttons forbidden')


def read(game=None, **overrides):
    game = game or Game()
    args = dict(observation_frame=FRAME, expected_location=deepcopy(LOCATION),
                constants=ReadOnlySDK(), profile=t.PROFILE)
    args.update(overrides)
    snapshot = t.read_trainer_opponent(game, **args)
    assert game.memory.writes == []
    return snapshot


def unknown(snapshot, reason):
    assert snapshot['read_valid'] is False
    assert snapshot['enemy'] is None
    assert snapshot['raw_record'] is None
    assert snapshot['current_opponent'] is None
    assert snapshot['raw'] is None
    assert snapshot['unknown_reason'] == reason


def test_complete_trainer_snapshot_high_runtime_frame_readonly():
    game = Game()
    values = deepcopy(game.memory.values)
    snapshot = read(game)
    assert snapshot['read_valid'] is True
    assert snapshot['profile'] == 'red-en-sdk-2.8.1-trainer-enemy-source-v1-unvalidated'
    assert snapshot['source_commit'] == 'a53671100ec22e5394ff26ec028d0812a238dae2'
    assert snapshot['live_calibrated'] is False
    assert snapshot['frame_before'] == snapshot['frame_after'] == snapshot['observation_frame'] == FRAME
    assert snapshot['raw'] == 2 and snapshot['battle_type'] == 0
    assert snapshot['battle_kind'] == 'trainer'
    assert snapshot['current_opponent'] == 206
    assert snapshot['location'] == LOCATION
    assert snapshot['raw_record'] == record()
    assert snapshot['enemy'] == {
        'species': 83, 'internal_id': 83, 'species_name': 'NINETALES',
        'level': 36, 'hp': 80, 'max_hp': 105, 'status': 0,
        'moves': [52, 39, 98, 109], 'pp': [20, 30, 25, 10],
        'pp_remaining': [20, 30, 25, 10], 'pp_ups': [0, 0, 0, 0],
        'dvs': [152, 136], 'types': [20, 20], 'catch_rate': 75,
        'attack': 70, 'defense': 65, 'speed': 85, 'special': 80,
    }
    assert game.memory.values == values
    assert game.memory.reads == list(GUARDS + RECORD + RECORD + GUARDS)
    assert len(game.memory.reads) == 72
    assert not any(k in snapshot for k in ('can_heal', 'can_throw', 'capture_complete'))
    assert 'exp' not in snapshot['enemy']


@pytest.mark.parametrize('code', [0, 1, 83, 201, 247, 255])
def test_current_opponent_is_independent_raw_code_not_species_or_class_approval(code):
    game = Game()
    game.memory.values[0xD059] = code
    result = read(game)
    assert result['read_valid'] is True
    assert result['current_opponent'] == code
    assert result['enemy']['species'] == 83


def test_returned_lists_are_detached_from_ram_and_next_snapshot():
    game = Game()
    a = read(game)
    a['raw_record'][0] = 7
    a['enemy']['moves'][0] = 0
    a['location']['x'] = 99
    b = read(game)
    assert b['raw_record'] == record()
    assert b['enemy']['moves'] == [52, 39, 98, 109]
    assert b['location'] == LOCATION


@pytest.mark.parametrize('value', [None, '', True, 'red-en-sdk-2.8.1-enemy-source-v1-unvalidated'])
def test_explicit_trainer_profile_before_any_memory(value):
    game = Game()
    unknown(read(game, profile=value), 'trainer_red_profile_required')
    assert not game.memory.reads


@pytest.mark.parametrize('value', [None, False, 1732097.0, -1, '1732097'])
def test_invalid_frame_before_any_memory(value):
    game = Game()
    unknown(read(game, observation_frame=value), 'trainer_observation_frame_invalid')
    assert not game.memory.reads


@pytest.mark.parametrize('frames, reason', [
    ([FRAME - 1], 'trainer_frame_not_current'),
    ([False], 'trainer_frame_not_current'),
    ([float(FRAME)], 'trainer_frame_not_current'),
    ([FRAME, FRAME + 1], 'trainer_frame_changed_during_read'),
    ([FRAME, float(FRAME)], 'trainer_frame_changed_during_read'),
])
def test_before_after_actual_frames(frames, reason):
    game = Game()
    game.frames = frames
    unknown(read(game), reason)


@pytest.mark.parametrize('location', [None, {}, {'map_id': 166, 'x': 4},
    {'map_id': False, 'x': 4, 'y': 6}, {'map_id': 166, 'x': 4.0, 'y': 6},
    {'map_id': 166, 'x': 256, 'y': 6}])
def test_bad_expected_location(location):
    game = Game()
    unknown(read(game, expected_location=location), 'trainer_expected_location_invalid')
    assert not game.memory.reads


@pytest.mark.parametrize('anchor', list(SDK_VALUES))
@pytest.mark.parametrize('bad', [False, 0.0, 0xFFFF])
def test_every_sdk_anchor_must_be_exact_integer(anchor, bad):
    values = dict(SDK_VALUES)
    values[anchor] = bad
    game = Game()
    unknown(read(game, constants=SimpleNamespace(**values)), 'trainer_sdk_anchor_mismatch')
    assert not game.memory.reads


def test_missing_sdk_anchor_unknown():
    unknown(read(constants=SimpleNamespace()), 'trainer_sdk_anchor_unavailable')


def test_readonly_sdk_anchors_read_once_without_mutation():
    counts = {}
    class SDK(ReadOnlySDK):
        def __getattr__(self, name):
            counts[name] = counts.get(name, 0) + 1
            if counts[name] != 1:
                raise AssertionError('不可用不同 SDK 樣本分別核型別和值')
            return super().__getattr__(name)
    assert read(constants=SDK())['read_valid'] is True
    assert counts == {name: 1 for name in SDK_VALUES}


def test_never_calls_wild_reader_or_relabels_raw2_as_raw1(monkeypatch):
    from laya_pokemon import wild_opponent
    def forbidden(*args, **kwargs):
        raise AssertionError('不可呼叫 wild reader')
    monkeypatch.setattr(wild_opponent, 'read_wild_opponent', forbidden)
    game = Game()
    assert read(game)['raw'] == 2
    assert game.memory.values[0xD057] == 2


@pytest.mark.parametrize('raw', [0, 1, 3, 255])
def test_no_battle_wild_or_lost_never_coerced_to_trainer(raw):
    game = Game()
    game.memory.values[0xD057] = raw
    unknown(read(game), 'trainer_battle_not_active')


@pytest.mark.parametrize('battle_type', [1, 2, 255])
def test_old_man_safari_unknown_types_rejected(battle_type):
    game = Game()
    game.memory.values[0xD05A] = battle_type
    unknown(read(game), 'trainer_normal_battle_required')


@pytest.mark.parametrize('address', GUARDS[:3])
def test_ram_position_must_match_same_observation(address):
    game = Game()
    game.memory.values[address] += 1
    unknown(read(game), 'trainer_location_does_not_match_observation')


@pytest.mark.parametrize('address', ADDRESSES)
def test_each_guard_and_record_byte_is_read_twice_and_torn_snapshot_rejected(address):
    game = Game()
    game.memory.hook = lambda a, n, old: ((old + 1) % 256 if a == address and n == 2 else old)
    unknown(read(game), 'trainer_snapshot_changed_during_read')


@pytest.mark.parametrize('address', ADDRESSES)
def test_false_on_second_read_never_equals_a_valid_zero(address):
    game = Game()
    game.memory.hook = lambda a, n, old: (False if a == address and n == 2 else old)
    unknown(read(game), 'trainer_memory_byte_invalid')


@pytest.mark.parametrize('value', [True, False, None, -1, 256, 0.0])
@pytest.mark.parametrize('pass_number', [1, 2])
def test_overflow_and_nonbytes_in_either_structure_read(value, pass_number):
    game = Game()
    game.memory.hook = lambda a, n, old: (value if a == 0xCFE9 and n == pass_number else old)
    unknown(read(game), 'trainer_memory_byte_invalid')


@pytest.mark.parametrize('address', [GUARDS[0], GUARDS[-1], RECORD[0], RECORD[-1]])
@pytest.mark.parametrize('pass_number', [1, 2])
def test_read_exceptions_never_leak_partial_enemy_or_private_error(address, pass_number):
    game = Game()
    def hook(a, n, old):
        if a == address and n == pass_number:
            raise RuntimeError('private exception content')
        return old
    game.memory.hook = hook
    result = read(game)
    unknown(result, 'trainer_memory_getter_failed')
    assert 'private exception' not in repr(result)


@pytest.mark.parametrize('offset,value,reason', [
    (0, 31, 'enemy_species_unknown'), (14, 0, 'enemy_level_invalid'),
    (14, 101, 'enemy_level_invalid'), (1, 1, 'enemy_hp_invalid'),
    (2, 0, 'enemy_zero_hp_transition'), (4, 9, 'enemy_status_invalid'),
    (5, 255, 'enemy_type_invalid'), (8, 166, 'enemy_moves_or_pp_invalid'),
    (18, 0, 'enemy_stats_invalid'),
])
def test_shared_pure_decoder_rejects_invalid_enemy(offset, value, reason):
    game = Game()
    game.memory.values[0xCFE5 + offset] = value
    unknown(read(game), reason)


def test_level_guard_not_inferred_from_trainer_code():
    game = Game()
    game.memory.values[0xD127] = 37
    unknown(read(game), 'trainer_enemy_level_identity_mismatch')


@pytest.mark.parametrize('path,expected', [
    (STAGE / 'test_trainer_opponent.py', STAGE / 'trainer_opponent.py'),
    (ROOT / 'tests/test_trainer_opponent.py', ROOT / 'src/laya_pokemon/trainer_opponent.py'),
])
def test_explicit_stage_and_formal_loader(path, expected):
    assert source_for_test(path) == expected


def test_unknown_test_location_does_not_guess_or_fallback():
    with pytest.raises(RuntimeError, match='未知'):
        source_for_test(ROOT / 'outputs/test_trainer_opponent.py')
