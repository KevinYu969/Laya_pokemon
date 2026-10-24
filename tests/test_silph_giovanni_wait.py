"""合成state驗11F座標腳本等待；不讀ROM、存檔或執行任何遊戲輸入。"""
from copy import deepcopy
import importlib

import pytest

from laya_pokemon import silph_giovanni_wait as control


@pytest.fixture(autouse=True)
def fresh_waits(monkeypatch):
    monkeypatch.setattr(control, '_GIOVANNI_WAITS', {})


def step(target=(6, 13)):
    return {'id': 'silph11-giovanni', 'kind': 'move', 'map_id': 235,
            'target': list(target), 'event': 'beat_silph_co_giovanni', 'await_script_event': True}


def state(target=(6, 13), frame=40):
    mons = [(7, 'NIDOKING', [61, 57, 30, 40], [20, 15, 25, 35]),
            (19, 'LAPRAS', [55, 34, 47, 54], [25, 15, 15, 30]),
            (102, 'EEVEE', [33, 28, 98, 39], [35, 15, 30, 30]),
            (154, 'VENUSAUR', [75, 15, 73, 22], [25, 30, 10, 10]),
            (35, 'FEAROW', [64, 65, 43, 31], [35, 20, 30, 20]),
            (132, 'SNORLAX', [70, 133, 156, 34], [15, 20, 10, 15])]
    return {'frame': frame, 'location': {'map_id': 235, 'x': target[0], 'y': target[1],
                                       'observation_frame': frame},
            'battle_state': {'raw': 0, 'active': False, 'kind': 'none', 'observation_frame': frame},
            'progress': {'profile': 'gen1-wrapper-ram-progress-v1-unvalidated',
                         'initialization_candidate': True, 'party_read_valid': True,
                         'party_count': 6, 'observation_frame': frame,
                         'party': [{'species': s, 'species_name': name, 'level': 40, 'exp': 70000,
                                    'hp': 100, 'max_hp': 100, 'status': 0, 'moves': moves, 'pp': pp}
                                   for s, name, moves, pp in mons],
                         'inventory': [{'item': 4, 'quantity': 6}, {'item': 48, 'quantity': 1}],
                         'story_event_bits': {'beat_silph_co_rival': True,
                                              'silph_co_11_unlocked_door': True,
                                              'beat_silph_co_giovanni': False}}}


def review(result):
    assert result['phase'] == 'campaign_review' and result['available_actions'] == ['wait']
    assert 'victory_confirmed' not in result and 'completed' not in result


@pytest.mark.parametrize('target', [(6, 13), (7, 12)])
def test_both_source_triggers_only_wait_without_mutating_inputs(target):
    s, intent = state(target), step(target)
    original = deepcopy((s, intent))
    result = control.silph_giovanni_script_wait(s, intent, now=0)
    assert result['phase'] == 'overworld' and result['objective'] == 'Wait.'
    assert result['available_actions'] == ['wait'] and result['silph_giovanni_wait_calls'] == 1
    assert result['source_commit'] == 'a53671100ec22e5394ff26ec028d0812a238dae2'
    assert (s, intent) == original


@pytest.mark.parametrize('raw,kind', [(1, 'wild'), (2, 'trainer')])
def test_valid_active_battle_is_returned_without_binding_or_consuming_budget(raw, kind):
    s = state(); s['battle_state'].update(raw=raw, kind=kind, active=True)
    assert control.silph_giovanni_script_wait(s, step(), now=0) is None
    assert control._GIOVANNI_WAITS == {}


def test_event_true_returns_none_without_claiming_victory_or_closed_ui():
    s = state(); s['progress']['story_event_bits'][control.EVENT] = True
    assert control.silph_giovanni_script_wait(s, step(), now=0) is None
    assert control._GIOVANNI_WAITS == {}


@pytest.mark.parametrize('key,value', [('kind', 'interact'), ('map_id', True), ('map_id', 212),
    ('target', (6, 13)), ('target', [6, 12]), ('target', [True, 13]), ('id', ''), ('id', 'a/b'),
    ('id', 'x' * 129), ('await_script_event', 1), ('await_script_event', False),
    ('event', 'beat_silph_co_rival'), ('next_map', None), ('terminal', True), ('terminal', False)])
def test_inexact_intent_never_waits_as_verified_source(key, value):
    intent = step(); intent[key] = value
    review(control.silph_giovanni_script_wait(state(), intent, now=0))
    assert control._GIOVANNI_WAITS == {}


@pytest.mark.parametrize('flag', ['beat_silph_co_rival', 'silph_co_11_unlocked_door'])
@pytest.mark.parametrize('value', [False, None, 1])
def test_prerequisites_require_true_boolean(flag, value):
    s = state(); s['progress']['story_event_bits'][flag] = value
    review(control.silph_giovanni_script_wait(s, step(), now=0))


@pytest.mark.parametrize('value', [None, 0, 1, 'false'])
def test_giovanni_unknown_or_integer_event_does_not_count_as_false_or_win(value):
    s = state(); s['progress']['story_event_bits'][control.EVENT] = value
    review(control.silph_giovanni_script_wait(s, step(), now=0))


@pytest.mark.parametrize('items', [[], [{'item': 48, 'quantity': 2}],
    [{'item': 48, 'quantity': 1}, {'item': 48, 'quantity': 1}], [{'item': 48, 'quantity': True}]])
def test_card_key_must_be_unique_quantity_one(items):
    s = state(); s['progress']['inventory'] = items
    review(control.silph_giovanni_script_wait(s, step(), now=0))


@pytest.mark.parametrize('bad', ['five', 'count', 'unreadable', 'init', 'faint', 'species',
                                 'name', 'status', 'moves', 'pp', 'empty_pp'])
def test_incomplete_or_illegal_party_and_faint_never_pass(bad):
    s = state(); p = s['progress']; mon = p['party'][0]
    if bad == 'five': p['party'].pop(); p['party_count'] = 5
    elif bad == 'count': p['party_count'] = True
    elif bad == 'unreadable': p['party_read_valid'] = False
    elif bad == 'init': p['initialization_candidate'] = 1
    elif bad == 'faint': mon['hp'] = 0
    elif bad == 'species': mon['species'] = True
    elif bad == 'name': mon['species_name'] = 'LAPRAS'
    elif bad == 'status': mon['status'] = 9
    elif bad == 'moves': mon['moves'] = [61, 57]
    elif bad == 'pp': mon['pp'][0] = True
    else: mon['moves'][0] = 0
    review(control.silph_giovanni_script_wait(s, step(), now=0))


@pytest.mark.parametrize('part', ['frame', 'location', 'progress', 'battle_state', 'raw', 'position'])
def test_same_frame_and_typed_location_battle_evidence_is_required(part):
    s = state()
    if part == 'frame': s['frame'] = True
    elif part in ('location', 'progress', 'battle_state'): s[part]['observation_frame'] = 41
    elif part == 'raw': s['battle_state']['raw'] = False
    else: s['location']['x'] = True
    review(control.silph_giovanni_script_wait(s, step(), now=0))


@pytest.mark.parametrize('raw,kind,active', [(1, 'trainer', True), (2, 'wild', True),
    (0, 'none', 0), (255, 'none', False), (1, 'wild', False), (0, 'trainer', False)])
def test_unknown_or_contradictory_battle_is_not_handed_off(raw, kind, active):
    s = state(); s['battle_state'].update(raw=raw, kind=kind, active=active)
    review(control.silph_giovanni_script_wait(s, step(), now=0))


@pytest.mark.parametrize('now', [True, -1, float('nan'), float('inf'), '1'])
def test_invalid_clock_cannot_bind(now):
    review(control.silph_giovanni_script_wait(state(), step(), now=now))
    assert control._GIOVANNI_WAITS == {}


def test_intent_deepcopy_and_error_stay_bound_across_reload():
    s, intent = state(), step()
    control.silph_giovanni_script_wait(s, intent, now=0)
    intent['target'][:] = [7, 12]
    assert control._GIOVANNI_WAITS[intent['id']]['step']['target'] == [6, 13]
    result = control.silph_giovanni_script_wait(state((7, 12), 41), intent, now=1)
    review(result)
    importlib.reload(control)
    assert control.silph_giovanni_script_wait(state(frame=42), step(), now=2)['review_reason'] == result['review_reason']


def test_same_frame_identical_packet_can_only_wait_but_changed_packet_latches_error():
    s = state(); intent = step()
    control.silph_giovanni_script_wait(s, intent, now=0)
    assert control.silph_giovanni_script_wait(deepcopy(s), intent, now=1)['available_actions'] == ['wait']
    s['progress']['party'][0]['hp'] -= 1
    result = control.silph_giovanni_script_wait(s, intent, now=2)
    assert result['review_reason'] == 'silph_giovanni_wait_same_frame_packet_conflict'
    review(control.silph_giovanni_script_wait(state(frame=41), intent, now=3))


@pytest.mark.parametrize('bad', ['clock', 'frame', 'key'])
def test_pending_regression_or_key_change_is_sticky(bad):
    control.silph_giovanni_script_wait(state(), step(), now=10)
    s, now = state(frame=41), 11
    if bad == 'clock': now = 9
    elif bad == 'frame': s = state(frame=39)
    else: s['progress']['inventory'][-1]['quantity'] = 2
    review(control.silph_giovanni_script_wait(s, step(), now=now))
    s = state(frame=42); s['progress']['story_event_bits'][control.EVENT] = True
    review(control.silph_giovanni_script_wait(s, step(), now=12))


def test_calls_budget_is_not_reset_by_reload():
    for index in range(25):
        result = control.silph_giovanni_script_wait(state(frame=40 + index), step(), now=index)
        assert result['available_actions'] == ['wait'] and result['phase'] == 'overworld'
    record = control._GIOVANNI_WAITS[step()['id']]
    importlib.reload(control)
    assert control._GIOVANNI_WAITS[step()['id']] is record
    result = control.silph_giovanni_script_wait(state(frame=65), step(), now=25)
    assert result['review_reason'] == 'silph_giovanni_wait_budget_exhausted'


def test_seconds_budget_keeps_original_start_through_reload():
    control.silph_giovanni_script_wait(state(), step(), now=0)
    importlib.reload(control)
    assert control.silph_giovanni_script_wait(state(frame=41), step(), now=60)['phase'] == 'overworld'
    result = control.silph_giovanni_script_wait(state(frame=42), step(), now=60.001)
    assert result['review_reason'] == 'silph_giovanni_wait_budget_exhausted'
