"""拒絕寫入的合成memory；不載入PyBoy、不讀真實ROM／RAM或啟動遊戲。"""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from laya_pokemon.rocket_progress import (
    read_rocket_progress, ROCKET_EVENT_IDS, ITEM_IDS, SOURCE_COMMIT,
    EVENT_FLAGS_ADDRESS, UPSTREAM_PROFILE,
)


class ReadOnlyMemory:
    def __init__(self, values=None):
        self.values, self.reads = dict(values or {}), []

    def __getitem__(self, address):
        self.reads.append(address)
        value = self.values.get(address, 0)
        if isinstance(value, Exception):
            raise value
        return value

    def __setitem__(self, address, value):
        raise AssertionError('候選不得寫memory')


def constants():
    return SimpleNamespace(EVENT_FLAGS_ADDRESS=EVENT_FLAGS_ADDRESS, EVENT_FLAGS=dict(ROCKET_EVENT_IDS))


def progress():
    return {'profile': UPSTREAM_PROFILE, 'initialization_candidate': True, 'party_read_valid': True,
            'party_count': 1, 'party': [{'species': 167, 'level': 25, 'hp': 76, 'max_hp': 76}],
            'inventory': []}


def test_all_event_ids_match_independent_pinned_research_and_no_invented_events():
    path = Path(__file__).parent / 'data/rocket-source-fixture.json'
    reference = json.loads(path.read_text(encoding='utf-8'))
    assert reference['source_commit'] == SOURCE_COMMIT
    assert dict(ROCKET_EVENT_IDS) == {key.removeprefix('EVENT_').lower(): value
                                    for key, value in reference['event_constants'].items()}
    assert dict(ITEM_IDS) == {'has_lift_key': reference['item_constants']['LIFT_KEY'],
                             'has_silph_scope': reference['item_constants']['SILPH_SCOPE']}
    assert not {'got_lift_key', 'got_silph_scope', 'beat_game_corner_rocket', 'entered_rocket_hideout'} & ROCKET_EVENT_IDS.keys()


@pytest.mark.parametrize('name,event_id', ROCKET_EVENT_IDS.items())
def test_each_fixed_event_address_and_bit_is_decoded_separately(name, event_id):
    address, bit = EVENT_FLAGS_ADDRESS + event_id // 8, event_id % 8
    memory = ReadOnlyMemory({address: 1 << bit})
    result = read_rocket_progress(memory, progress(), constants())
    assert result['story_event_bits'][name] is True
    assert [key for key, value in result['story_event_bits'].items() if value] == [name]
    assert result['event_locations'][name] == {'event_id': event_id, 'address': address, 'bit': bit}
    assert result['initialization_candidate'] and result['item_presence'] == {'has_lift_key': False, 'has_silph_scope': False}


def test_physical_b4f_byte_and_found_hideout_address_contracts():
    memory = ReadOnlyMemory({0xD77E: 0x02, 0xD81B: 0xFC})
    result = read_rocket_progress(memory, progress(), constants())
    assert result['story_event_bits']['found_rocket_hideout'] is True
    for name in ('beat_rocket_hideout_4_trainer_0', 'beat_rocket_hideout_4_trainer_1',
                 'beat_rocket_hideout_4_trainer_2', 'rocket_hideout_4_door_unlocked',
                 'rocket_dropped_lift_key', 'beat_rocket_hideout_giovanni'):
        assert result['story_event_bits'][name] is True
    assert len(memory.reads) == len(set(memory.reads)) == 5  # 同一byte只讀一次。
    assert result['item_presence'] == {'has_lift_key': False, 'has_silph_scope': False}


@pytest.mark.parametrize('mutation', [
    lambda p: p.update(profile='unknown'), lambda p: p.pop('profile'),
    lambda p: p.update(initialization_candidate=False), lambda p: p.update(party_read_valid=False),
    lambda p: p.update(party_count=0, party=[]), lambda p: p.update(party_count=2),
    lambda p: p.update(party_count=True), lambda p: p['party'][0].update(level=0),
    lambda p: p['party'][0].update(hp=77), lambda p: p['party'][0].update(species=True),
])
def test_uninitialized_or_unknown_party_never_reads_or_confirms_any_event_or_item(mutation):
    p = progress();mutation(p)
    memory = ReadOnlyMemory({0xD77E: 255, 0xD81B: 255})
    result = read_rocket_progress(memory, p, constants())
    assert not result['initialization_candidate'] and memory.reads == []
    assert all(value is None for value in result['story_event_bits'].values())
    assert all(value is None for value in result['item_presence'].values())


@pytest.mark.parametrize('c', [None, SimpleNamespace(),
                             SimpleNamespace(EVENT_FLAGS_ADDRESS=0x200, EVENT_FLAGS=dict(ROCKET_EVENT_IDS)),
                             SimpleNamespace(EVENT_FLAGS_ADDRESS=True, EVENT_FLAGS=dict(ROCKET_EVENT_IDS)),
                             SimpleNamespace(EVENT_FLAGS_ADDRESS=EVENT_FLAGS_ADDRESS, EVENT_FLAGS=None)])
def test_unknown_constant_contract_never_falls_back_or_reads_memory(c):
    memory = ReadOnlyMemory({0xD81B: 255})
    result = read_rocket_progress(memory, progress(), c)
    assert memory.reads == [] and all(value is None for value in result['story_event_bits'].values())


@pytest.mark.parametrize('bad', [None, True, 0x6A6, '1703', -1])
def test_missing_or_wrong_named_event_id_stays_unknown_without_borrowing_neighbor_flag(bad):
    c = constants();c.EVENT_FLAGS['beat_rocket_hideout_giovanni'] = bad
    result = read_rocket_progress(ReadOnlyMemory({0xD81B: 255}), progress(), c)
    assert result['story_event_bits']['beat_rocket_hideout_giovanni'] is None
    assert result['story_event_bits']['rocket_dropped_lift_key'] is True


@pytest.mark.parametrize('bad', [None, True, -1, 256, '255', KeyError('unknown'), RuntimeError('uninitialized')])
def test_unreadable_byte_is_unknown_for_all_six_b4f_flags_and_not_false(bad):
    memory = ReadOnlyMemory({0xD81B: bad, 0xD77E: 0x02})
    result = read_rocket_progress(memory, progress(), constants())
    assert all(value is None for name, value in result['story_event_bits'].items() if ROCKET_EVENT_IDS[name] // 8 == 0xD4)
    assert result['story_event_bits']['found_rocket_hideout'] is True
    assert memory.reads.count(0xD81B) == 1


@pytest.mark.parametrize('inventory,expected', [
    ([], {'has_lift_key': False, 'has_silph_scope': False}),
    ([{'item': 74, 'quantity': 1}], {'has_lift_key': True, 'has_silph_scope': False}),
    ([{'item': 72, 'quantity': 1}], {'has_lift_key': False, 'has_silph_scope': True}),
    ([{'item': 74, 'quantity': 1}, {'item': 72, 'quantity': 1}], {'has_lift_key': True, 'has_silph_scope': True}),
])
def test_item_possession_is_separate_from_story_flags_and_requires_valid_inventory(inventory, expected):
    p = progress();p['inventory'] = inventory
    result = read_rocket_progress(ReadOnlyMemory(), p, constants())
    assert result['item_presence'] == expected
    assert not any(result['story_event_bits'].values())
    assert 'got_lift_key' not in result['story_event_bits'] and 'got_silph_scope' not in result['story_event_bits']


@pytest.mark.parametrize('inventory', [None, {}, [{'item': 74, 'quantity': 0}],
                                      [{'item': 72, 'quantity': True}], [{'item': True, 'quantity': 1}],
                                      [{'item': 74, 'quantity': 1}] * 2, [{'item': 74, 'quantity': 1, 'unknown': 1}]])
def test_unknown_inventory_does_not_infer_item_possession_from_won_or_dropped_events(inventory):
    p = progress();p['inventory'] = inventory
    result = read_rocket_progress(ReadOnlyMemory({0xD81B: 0xFC}), p, constants())
    assert result['story_event_bits']['rocket_dropped_lift_key'] is True
    assert result['story_event_bits']['beat_rocket_hideout_giovanni'] is True
    assert result['item_presence'] == {'has_lift_key': None, 'has_silph_scope': None}


def test_no_baseline_milestone_or_state_mutation_and_only_expected_memory_addresses_are_read():
    p, c = progress(), constants()
    values = {address: 255 for address in (0xD77E, 0xD815, 0xD817, 0xD819, 0xD81B)}
    memory = ReadOnlyMemory(values)
    before = deepcopy((p, c.EVENT_FLAGS, memory.values))
    result = read_rocket_progress(memory, p, c)
    assert (p, c.EVENT_FLAGS, memory.values) == before
    assert set(memory.reads) == set(values)
    assert all(result['story_event_bits'].values())
    assert not any(key in result for key in ('milestones', 'champion_observed', 'hall_of_fame_confirmed', 'completed'))
    assert '首次為True不是本次新達成' in result['warnings'][0]
    assert dict(ITEM_IDS) == {'has_lift_key': 74, 'has_silph_scope': 72}
