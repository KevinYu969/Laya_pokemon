"""固定公開事件fixture＋拒絕寫入的合成getter；無outputs／ROM／存檔依賴。"""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from laya_pokemon.tower_progress import (
    read_tower_progress, read_tower_observation, TOWER_EVENT_IDS, ITEM_IDS,
    SOURCE_COMMIT, EVENT_FLAGS_ADDRESS, UPSTREAM_PROFILE,
)


ADDRESSES = {0xD764, 0xD765, 0xD766, 0xD767, 0xD768, 0xD769, 0xD76C, 0xD7E0}


class ReadOnlyMemory:
    def __init__(self, values=None):
        self.values = {address: 0 for address in ADDRESSES}
        self.values.update(values or {})
        self.reads = []

    def __getitem__(self, address):
        self.reads.append(address)
        value = self.values[address]
        if isinstance(value, Exception):
            raise value
        return value

    def __setitem__(self, address, value):
        raise AssertionError('唯讀adapter不得寫RAM')


def constants():
    return SimpleNamespace(EVENT_FLAGS_ADDRESS=EVENT_FLAGS_ADDRESS, EVENT_FLAGS=dict(TOWER_EVENT_IDS))


def progress():
    return {'profile': UPSTREAM_PROFILE, 'initialization_candidate': True, 'party_read_valid': True,
            'party_count': 1, 'party': [{'species': 7, 'level': 28, 'hp': 95, 'max_hp': 95}],
            'inventory': []}


def test_all_twenty_two_events_match_independent_public_fixture_and_exact_whitelist():
    p = Path(__file__).parent / 'data/tower-event-source-fixture.json'
    fixture = json.loads(p.read_text(encoding='utf-8'))
    assert set(fixture) == {'source_commit', 'event_constants'}
    assert fixture['source_commit'] == SOURCE_COMMIT
    expected = {name.removeprefix('EVENT_').lower(): value for name, value in fixture['event_constants'].items()}
    assert dict(TOWER_EVENT_IDS) == expected and len(expected) == 22
    assert not {'got_silph_scope', 'got_scope', 'got_rare_candy', 'beat_tower',
                'entered_rocket_hideout', 'beat_rocket_hideout_1_trainer_4'} & expected.keys()
    assert dict(ITEM_IDS) == {'has_silph_scope': 72, 'has_poke_flute': 73}
    with pytest.raises(TypeError):
        TOWER_EVENT_IDS['got_poke_flute'] = 0


@pytest.mark.parametrize('name,event_id', TOWER_EVENT_IDS.items())
def test_each_event_decodes_only_its_fixed_address_and_bit(name, event_id):
    address, bit = EVENT_FLAGS_ADDRESS + event_id // 8, event_id % 8
    result = read_tower_progress(ReadOnlyMemory({address: 1 << bit}), progress(), constants())
    assert result['read_valid'] and result['initialization_candidate']
    assert [k for k, v in result['story_event_bits'].items() if v] == [name]
    assert result['event_locations'][name] == {'event_id': event_id, 'address': address, 'bit': bit}
    assert result['frame_checked'] is False and result['observation_frame'] is None


def test_physical_byte_locations_cache_each_byte_once_and_never_mutate_inputs():
    p, c = progress(), constants()
    memory = ReadOnlyMemory({address: 255 for address in ADDRESSES})
    before = deepcopy((p, c.EVENT_FLAGS, memory.values))
    result = read_tower_progress(memory, p, c)
    assert result['read_valid'] and all(result['story_event_bits'].values())
    assert set(memory.reads) == ADDRESSES and len(memory.reads) == 8
    assert (p, c.EVENT_FLAGS, memory.values) == before
    assert result['event_locations']['got_poke_flute'] == {'event_id': 296, 'address': 0xD76C, 'bit': 0}
    assert result['event_locations']['rescued_mr_fuji'] == {'event_id': 1231, 'address': 0xD7E0, 'bit': 7}
    assert result['event_locations']['beat_ghost_marowak'] == {'event_id': 271, 'address': 0xD768, 'bit': 7}
    assert not any(k in result for k in ('completed', 'milestones', 'hall_of_fame_confirmed', 'champion_observed'))
    assert '不是本次新達成' in result['warnings'][0]


@pytest.mark.parametrize('mutation', [
    lambda p: p.update(profile='other'), lambda p: p.pop('profile'),
    lambda p: p.update(initialization_candidate=False), lambda p: p.update(party_read_valid=False),
    lambda p: p.update(party_count=True), lambda p: p.update(party_count=0, party=[]),
    lambda p: p.update(party_count=2), lambda p: p['party'][0].update(species=True),
    lambda p: p['party'][0].update(level=0), lambda p: p['party'][0].update(hp=96),
])
def test_unverified_upstream_never_reads_any_memory_or_turns_unknown_into_false(mutation):
    p = progress(); mutation(p); memory = ReadOnlyMemory({a: 255 for a in ADDRESSES})
    result = read_tower_progress(memory, p, constants())
    assert not result['read_valid'] and not result['initialization_candidate']
    assert memory.reads == [] and all(v is None for v in result['story_event_bits'].values())
    assert all(v is None for v in result['item_presence'].values())


@pytest.mark.parametrize('c', [None, SimpleNamespace(),
    SimpleNamespace(EVENT_FLAGS_ADDRESS=0xD748, EVENT_FLAGS=dict(TOWER_EVENT_IDS)),
    SimpleNamespace(EVENT_FLAGS_ADDRESS=True, EVENT_FLAGS=dict(TOWER_EVENT_IDS)),
    SimpleNamespace(EVENT_FLAGS_ADDRESS=0xD747, EVENT_FLAGS=[]),
])
def test_unknown_global_sdk_contract_does_not_read_or_guess_event_memory(c):
    memory = ReadOnlyMemory({a: 255 for a in ADDRESSES})
    result = read_tower_progress(memory, progress(), c)
    assert not result['read_valid'] and memory.reads == []
    assert all(v is None for v in result['story_event_bits'].values())


@pytest.mark.parametrize('bad', [None, True, 272, '271', 271.0, -1])
def test_sdk_single_event_mismatch_does_not_borrow_neighbor_and_keeps_other_events(bad):
    c = constants(); c.EVENT_FLAGS['beat_ghost_marowak'] = bad
    result = read_tower_progress(ReadOnlyMemory({0xD768: 255}), progress(), c)
    assert not result['read_valid'] and result['story_event_bits']['beat_ghost_marowak'] is None
    assert result['story_event_bits']['beat_pokemontower_6_trainer_0'] is True


def test_missing_unique_event_id_never_reads_its_address_and_sdk_extras_are_ignored():
    c = constants(); del c.EVENT_FLAGS['rescued_mr_fuji']; c.EVENT_FLAGS['got_silph_scope'] = 1231
    memory = ReadOnlyMemory({a: 255 for a in ADDRESSES})
    result = read_tower_progress(memory, progress(), c)
    assert 0xD7E0 not in memory.reads and result['story_event_bits']['rescued_mr_fuji'] is None
    assert 'got_silph_scope' not in result['story_event_bits']


@pytest.mark.parametrize('bad', [None, True, False, -1, 256, '255', 255.0,
                              KeyError('missing'), RuntimeError('unknown'), OSError('unknown')])
def test_bad_byte_makes_every_shared_event_unknown_but_preserves_other_bytes(bad):
    memory = ReadOnlyMemory({0xD769: bad, 0xD76C: 1})
    result = read_tower_progress(memory, progress(), constants())
    shared = [name for name, value in TOWER_EVENT_IDS.items() if value // 8 == 0x22]
    assert len(shared) == 4 and all(result['story_event_bits'][name] is None for name in shared)
    assert result['story_event_bits']['got_poke_flute'] is True
    assert memory.reads.count(0xD769) == 1 and not result['read_valid']


@pytest.mark.parametrize('items,expected', [([], (False, False)),
    ([{'item': 72, 'quantity': 1}], (True, False)),
    ([{'item': 73, 'quantity': 1}], (False, True)),
    ([{'item': 72, 'quantity': 1}, {'item': 73, 'quantity': 1}], (True, True)),
])
def test_item_presence_is_actual_inventory_only_and_does_not_invent_event(items, expected):
    p = progress(); p['inventory'] = items
    result = read_tower_progress(ReadOnlyMemory(), p, constants())
    assert tuple(result['item_presence'].values()) == expected
    assert not any(result['story_event_bits'].values()) and result['read_valid']


@pytest.mark.parametrize('items', [None, {}, [{'item': 73, 'quantity': 0}],
    [{'item': 73, 'quantity': True}], [{'item': True, 'quantity': 1}],
    [{'item': 73, 'quantity': 1}] * 2, [{'item': 73, 'quantity': 1, 'extra': 1}],
])
def test_unknown_inventory_cannot_be_inferred_from_rescue_or_flute_event(items):
    p = progress(); p['inventory'] = items
    result = read_tower_progress(ReadOnlyMemory({0xD769: 128, 0xD7E0: 128, 0xD76C: 1}), p, constants())
    assert result['story_event_bits']['rescued_mr_fuji'] is True
    assert result['story_event_bits']['rescued_mr_fuji_2'] is True
    assert result['story_event_bits']['got_poke_flute'] is True
    assert all(v is None for v in result['item_presence'].values()) and not result['read_valid']


def test_transient_purified_zone_is_not_latched_as_completed_history():
    memory = ReadOnlyMemory({0xD767: 128})
    assert read_tower_progress(memory, progress(), constants())['story_event_bits']['in_purified_zone'] is True
    memory.values[0xD767] = 0
    assert read_tower_progress(memory, progress(), constants())['story_event_bits']['in_purified_zone'] is False


class PyBoyGetterOnly:
    def __init__(self, frames=(100, 100), memory=None):
        self._frames, self.frame_reads, self.memory_reads = iter(frames), 0, 0
        self._memory = memory if memory is not None else ReadOnlyMemory({a: 255 for a in ADDRESSES})

    @property
    def frame_count(self):
        self.frame_reads += 1
        return next(self._frames)

    @property
    def memory(self):
        self.memory_reads += 1
        return self._memory

    def __getattr__(self, name):
        raise AssertionError(f'不得存取其他模擬器介面：{name}')


def framed_progress(frame=100):
    p = progress(); p['observation_frame'] = frame
    p['inventory'] = [{'item': 72, 'quantity': 1}, {'item': 73, 'quantity': 1}]
    return p


def test_optional_observation_wrapper_only_getters_and_same_frame_contract():
    pyboy, p = PyBoyGetterOnly(), framed_progress()
    before = deepcopy(p)
    result = read_tower_observation(pyboy, p, constants(), observation_frame=100)
    assert result['read_valid'] and result['frame_checked'] and result['observation_frame'] == 100
    assert all(result['story_event_bits'].values()) and all(result['item_presence'].values())
    assert p == before and pyboy.frame_reads == 2 and pyboy.memory_reads == 1
    assert len(pyboy._memory.reads) == 8
    assert not any(w.startswith('裸memory') for w in result['warnings'])


@pytest.mark.parametrize('frame', [None, True, -1, 100.0, '100'])
def test_invalid_expected_frame_never_accesses_emulator(frame):
    pyboy = PyBoyGetterOnly()
    result = read_tower_observation(pyboy, framed_progress(), constants(), observation_frame=frame)
    assert pyboy.frame_reads == pyboy.memory_reads == 0 and not result['read_valid']
    assert all(v is None for v in result['story_event_bits'].values())


@pytest.mark.parametrize('upstream_frame', [None, 99, True, 100.0, '100'])
def test_progress_frame_missing_or_stale_cannot_be_forged_by_wrapper(upstream_frame):
    pyboy = PyBoyGetterOnly(); p = framed_progress(upstream_frame)
    if upstream_frame is None: del p['observation_frame']
    result = read_tower_observation(pyboy, p, constants(), observation_frame=100)
    assert not result['read_valid'] and pyboy.frame_reads == pyboy.memory_reads == 0
    assert all(v is None for v in result['item_presence'].values())


@pytest.mark.parametrize('before', [99, 101, True, 100.0, None])
def test_emulator_stale_before_read_never_reads_memory(before):
    pyboy = PyBoyGetterOnly(frames=(before, 100))
    result = read_tower_observation(pyboy, framed_progress(), constants(), observation_frame=100)
    assert not result['read_valid'] and pyboy.memory_reads == 0 and pyboy._memory.reads == []


@pytest.mark.parametrize('after', [99, 101, True, 100.0, None])
def test_cross_frame_discards_all_events_and_item_values_not_just_validity_flag(after):
    pyboy = PyBoyGetterOnly(frames=(100, after))
    result = read_tower_observation(pyboy, framed_progress(), constants(), observation_frame=100)
    assert not result['read_valid'] and not result['frame_checked']
    assert all(v is None for v in result['story_event_bits'].values())
    assert all(v is None for v in result['item_presence'].values())
    assert result['observation_frame'] is None


@pytest.mark.parametrize('frames', [(), (100,)])
def test_frame_getter_exception_fails_closed(frames):
    result = read_tower_observation(PyBoyGetterOnly(frames=frames), framed_progress(), constants(), observation_frame=100)
    assert not result['read_valid'] and all(v is None for v in result['story_event_bits'].values())


def test_same_frame_wrapper_does_not_replace_unknown_bytes_with_false():
    memory = ReadOnlyMemory({0xD76C: None})
    result = read_tower_observation(PyBoyGetterOnly(memory=memory), framed_progress(), constants(), observation_frame=100)
    assert result['frame_checked'] and not result['read_valid']
    assert result['story_event_bits']['got_poke_flute'] is None
    assert result['item_presence']['has_poke_flute'] is True  # 持有是另一個明確訊號，不補造event。
