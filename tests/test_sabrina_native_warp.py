"""純合成固定正向與返程配對；不載遊戲、tick、讀RAM或執行候選按鍵。"""
from copy import deepcopy
import importlib

import pytest

from laya_pokemon import sabrina_native_warp as control

PAIRS = [((11, 15), (19, 17), (18, 17), (11, 16), 'up', 'left'),
         ((15, 15), (19, 3), (18, 3), (15, 16), 'up', 'left'),
         ((15, 5), (1, 3), (1, 4), (16, 5), 'left', 'down'),
         ((1, 5), (11, 11), (10, 11), (1, 4), 'down', 'left')]
RECOVERY_PAIRS = [((11, 11), (1, 5), (1, 4), (10, 11), 'right', 'up'),
                  ((1, 3), (15, 5), (16, 5), (1, 4), 'up', 'right'),
                  ((19, 3), (15, 15), (15, 16), (18, 3), 'right', 'down'),
                  ((19, 17), (11, 15), (11, 16), (18, 17), 'right', 'down')]


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(control, '_SESSIONS', {})
    monkeypatch.setattr(control, '_OWNER', None)


def step(pair=PAIRS[0]):
    return {'id': 'sabrina-pad-test', 'kind': 'move', 'mechanic': 'sabrina_native_warp',
            'map_id': 178, 'target': list(pair[0]), 'landing': list(pair[1]), 'offpad': list(pair[2])}


def packet(pos, frame):
    p = {'profile': 'gen1-wrapper-ram-progress-v1-unvalidated', 'initialization_candidate': True,
         'party_read_valid': True, 'party_count': 6, 'money': 47056,
         'inventory': [{'item': 48, 'quantity': 1}], 'party': []}
    for species, name, moves, pp in [
        (7, 'NIDOKING', [61, 57, 30, 40], [20, 15, 25, 35]),
        (19, 'LAPRAS', [55, 34, 47, 54], [25, 15, 15, 30]),
        (102, 'EEVEE', [33, 28, 98, 39], [35, 15, 30, 30]),
        (154, 'VENUSAUR', [75, 15, 73, 22], [25, 30, 10, 10]),
        (35, 'FEAROW', [64, 65, 43, 31], [35, 20, 30, 20]),
        (132, 'SNORLAX', [70, 133, 156, 34], [15, 20, 10, 15])]:
        p['party'].append({'species': species, 'species_name': name, 'level': 35,
                           'hp': 100, 'max_hp': 100, 'exp': 50000, 'status': 0, 'moves': moves, 'pp': pp})
    state = {'frame': frame, 'location': {'map_id': 178, 'x': pos[0], 'y': pos[1]}, 'progress': p,
             'battle_state': {'raw': 0, 'active': False, 'kind': 'none', 'observation_frame': frame}}
    text = {'profile': control.TEXT_PROFILE, 'read_valid': True, 'alignment_verified': True,
            'window_visible': False, 'read_error': None, 'cells': [[' '] * 20 for _ in range(18)],
            'lines': [], 'line_rows': []}
    tiles = [[1] * 20 for _ in range(18)]
    for source, (landing, _) in control.PAIRS.items():
        for x, y in (source, landing): tiles[y][x] = 0x20
    visible = sorted(([x, y] for y in range(18) for x in range(20)),
                     key=lambda c: (abs(c[0] - pos[0]) + abs(c[1] - pos[1]), c[1], c[0]))[:12]
    grid = {'tileset_id': 22, 'observation_frame': frame, 'verified_location': [178, *pos],
            'tiles': tiles, 'walkable': [[1] * 20 for _ in range(18)],
            'screen_cells_verified': 12, 'visible_verified_cells': visible}
    movement = {'profile': control.MOVEMENT_PROFILE, 'source_commit': control.SOURCE_COMMIT,
                'read_valid': True, 'observation_frame': frame, 'spinning': False,
                'simulated_remaining': 0, 'joy_ignore': 0, 'walk_counter': 0, 'movement_flags': 0}
    return state, text, grid, movement


def call(pos, frame, previous=('wait',), pair=PAIRS[0], now=None, data=None, intent=None):
    data = packet(pos, frame) if data is None else data
    state, text, grid, movement = data
    before = deepcopy((data, previous))
    result = control.context(state, step(pair) if intent is None else intent, text, grid, movement,
                             previous, now=frame if now is None else now)
    assert (data, previous) == before
    return result


def review(result):
    assert result['phase'] == 'campaign_review' and result['available_actions'] == ['wait']
    assert not result.get('native_warp_complete')


def at_offpad_offer(pair=PAIRS[0]):
    source, landing, offpad, origin, enter, leave = pair
    call(origin, 10, pair=pair)
    call(source, 11, (enter,), pair)
    call(landing, 12, pair=pair)
    result = call(landing, 13, pair=pair)
    assert result['available_actions'] == [leave, 'wait']
    return offpad, leave


@pytest.mark.parametrize('pair', PAIRS)
def test_four_source_pairs_require_actual_entry_two_fresh_landings_and_actual_offpad(pair):
    source, landing, offpad, origin, enter, leave = pair
    assert call(origin, 10, pair=pair)['available_actions'] == [enter, 'wait']
    assert call(source, 11, (enter,), pair)['available_actions'] == ['wait']
    first = call(landing, 12, pair=pair)
    assert first['available_actions'] == ['wait']
    assert call(landing, 12, pair=pair) == first  # 同幀不能充作第二次落地。
    assert call(landing, 13, pair=pair)['available_actions'] == [leave, 'wait']
    result = call(offpad, 14, (leave,), pair)
    assert result['native_warp_complete'] is True and result['available_actions'] == ['wait']


def test_far_unbound_returns_none_and_source_without_actual_receipt_does_not_arm():
    assert call((9, 16), 1) is None and control._OWNER is None
    review(call(PAIRS[0][0], 2))


def test_fake_laya_wait_can_retry_source_direction_but_cannot_explain_movement():
    origin, source = PAIRS[0][3], PAIRS[0][0]
    assert call(origin, 10)['available_actions'] == ['up', 'wait']
    assert call(origin, 11, ('wait',))['available_actions'] == ['up', 'wait']
    assert control._SESSIONS[step()['id']]['stage'] == 'entry'
    review(call(source, 12, ('wait',)))


def test_actual_entry_can_already_be_at_landing_without_replaying_pad_direction():
    call(PAIRS[0][3], 10)
    result = call(PAIRS[0][1], 11, ('up',))
    assert result['available_actions'] == ['wait'] and not result['native_warp_complete']
    assert call(PAIRS[0][1], 12)['available_actions'] == ['left', 'wait']


def test_offpad_candidate_is_not_execution_and_no_receipt_cannot_complete():
    offpad, leave = at_offpad_offer()
    assert call(PAIRS[0][1], 14, ('wait',))['available_actions'] == [leave, 'wait']
    review(call(offpad, 15, ('wait',)))


def test_unknown_only_after_actual_entry_can_wait_and_invalid_landing_breaks_stable_pair():
    call(PAIRS[0][3], 10)
    state, text, _, _ = packet(PAIRS[0][0], 11)
    text['read_valid'] = False
    assert call(PAIRS[0][0], 11, ('up',), data=(state, text, None, None))['available_actions'] == ['wait']
    assert call(PAIRS[0][1], 12)['available_actions'] == ['wait']
    bad = packet(PAIRS[0][1], 13); bad[1]['alignment_verified'] = False
    assert call(PAIRS[0][1], 13, data=bad)['available_actions'] == ['wait']
    assert call(PAIRS[0][1], 14)['available_actions'] == ['wait']
    assert call(PAIRS[0][1], 15)['available_actions'] == ['left', 'wait']


@pytest.mark.parametrize('bad', ['text', 'movement', 'visible', 'collision', 'pad_tile', 'tileset'])
def test_before_entry_missing_closed_idle_visible_world_never_sends_direction(bad):
    d = packet(PAIRS[0][3], 10)
    if bad == 'text': d[1]['window_visible'] = True
    elif bad == 'movement': d[3]['walk_counter'] = 1
    elif bad == 'visible': d[2]['visible_verified_cells'][0] = d[2]['visible_verified_cells'][1].copy()
    elif bad == 'collision': d[2]['walkable'][15][11] = 0
    elif bad == 'pad_tile': d[2]['tiles'][15][11] = 1
    else: d[2]['tileset_id'] = 7
    review(call(PAIRS[0][3], 10, data=d))


@pytest.mark.parametrize('bad', ['faint', 'unreadable', 'money', 'bag'])
def test_full_six_party_inventory_money_cannot_drift_during_transition(bad):
    call(PAIRS[0][3], 10)
    d = packet(PAIRS[0][0], 11); p = d[0]['progress']
    if bad == 'faint': p['party'][4]['hp'] = 0
    elif bad == 'unreadable': p['party_read_valid'] = False
    elif bad == 'money': p['money'] -= 1
    else: p['inventory'][0]['quantity'] = 2
    review(call(PAIRS[0][0], 11, ('up',), data=d))


@pytest.mark.parametrize('key,value', [('landing', [19, 3]), ('offpad', [17, 17]),
    ('target', (11, 15)), ('map_id', True), ('next_map', 178), ('id', '')])
def test_only_four_typed_exact_intents_are_accepted(key, value):
    intent = step(); intent[key] = value
    review(call(PAIRS[0][3], 10, intent=intent))


def test_same_frame_changed_packet_and_owner_error_survive_reload_without_reset():
    call(PAIRS[0][3], 10)
    d = packet(PAIRS[0][3], 10); d[1]['window_visible'] = True
    result = call(PAIRS[0][3], 10, data=d)
    assert result['review_reason'] == 'sabrina_native_warp_same_frame_packet_conflict'
    owner = control._OWNER; record = control._SESSIONS[owner]
    importlib.reload(control)
    assert control._OWNER == owner and control._SESSIONS[owner] is record
    assert call(PAIRS[0][3], 11)['review_reason'] == result['review_reason']


def test_caller_mutating_bound_step_cannot_rebind_owner_or_destination():
    intent = step(); call(PAIRS[0][3], 10, intent=intent)
    intent['id'] = 'another-owner'
    review(call(PAIRS[0][3], 11, intent=intent))
    assert control._OWNER == 'sabrina-pad-test'
    assert control._SESSIONS[control._OWNER]['step']['id'] == 'sabrina-pad-test'


def test_unexpected_warp_destination_never_completes():
    call(PAIRS[0][3], 10)
    review(call((18, 16), 11, ('up',)))


def test_thirty_waits_and_sixty_second_budget_are_not_reset_by_reload():
    call(PAIRS[0][3], 1, now=0)
    for frame in range(2, 32):
        assert call(PAIRS[0][0], frame, ('up',), now=frame - 1)['available_actions'] == ['wait']
    importlib.reload(control)
    assert call(PAIRS[0][0], 32, now=31)['review_reason'] == 'sabrina_native_warp_wait_budget_exhausted'


def test_time_budget_expires_without_reissuing_entry_direction():
    call(PAIRS[0][3], 1, now=0)
    importlib.reload(control)
    result = call(PAIRS[0][3], 2, now=60.001)
    assert result['review_reason'] == 'sabrina_native_warp_time_budget_exhausted'


def test_mismatched_getter_frame_cannot_be_used_as_landing_or_completion():
    call(PAIRS[0][3], 10)
    d = packet(PAIRS[0][1], 11); d[2]['observation_frame'] = 10
    review(call(PAIRS[0][1], 11, ('up',), data=d))


@pytest.mark.parametrize('at_landing', [True, False])
def test_exact_coordinates_without_expected_real_pad_or_floor_tile_never_complete(at_landing):
    if at_landing:
        call(PAIRS[0][3], 10); call(PAIRS[0][0], 11, ('up',))
        pos, frame, previous = PAIRS[0][1], 12, ('wait',)
    else:
        pos, leave = at_offpad_offer()
        frame, previous = 14, (leave,)
    d = packet(pos, frame)
    d[2]['tiles'][pos[1]][pos[0]] = 1 if at_landing else 0x20
    review(call(pos, frame, previous, data=d))


def recovery_packet(pos, frame):
    data = packet(pos, frame)
    # 娜姿戰後保留真實倒下成員；Nidoking 是可正常護送返程的健康隊員。
    data[0]['progress']['party'][-1]['hp'] = 0
    return data


@pytest.mark.parametrize('pair', RECOVERY_PAIRS)
def test_four_inverse_recovery_pairs_preserve_faint_and_require_actual_actions(pair):
    source, landing, offpad, origin, enter, leave = pair
    intent = step(pair); intent['recovery_route'] = True
    def advance(pos, frame, previous=('wait',)):
        return call(pos, frame, previous, pair, data=recovery_packet(pos, frame), intent=intent)
    assert advance(origin, 10)['available_actions'] == [enter, 'wait']
    assert advance(source, 11, (enter,))['available_actions'] == ['wait']
    first = advance(landing, 12)
    assert first['available_actions'] == ['wait']
    assert advance(landing, 12) == first
    assert advance(landing, 13)['available_actions'] == [leave, 'wait']
    assert advance(offpad, 14, (leave,))['native_warp_complete'] is True
    assert control._SESSIONS[intent['id']]['baseline'][0][-1]['hp'] == 0


def test_forward_route_still_rejects_faint_and_even_healthy_recovery_flag():
    origin = PAIRS[0][3]
    review(call(origin, 10, data=recovery_packet(origin, 10)))
    assert control._OWNER is None
    intent = step(); intent['recovery_route'] = True
    review(call(origin, 11, intent=intent))
    assert control._OWNER is None


@pytest.mark.parametrize('flag', [None, False, 1])
def test_inverse_requires_explicit_true_recovery_and_exact_offpad(flag):
    pair = RECOVERY_PAIRS[0]; intent = step(pair)
    if flag is not None: intent['recovery_route'] = flag
    review(call(pair[3], 10, pair=pair, data=recovery_packet(pair[3], 10), intent=intent))
    assert control._OWNER is None


def test_inverse_recovery_cannot_choose_an_unreviewed_offpad():
    pair = RECOVERY_PAIRS[0]; intent = step(pair)
    intent.update(recovery_route=True, offpad=[2, 5])
    review(call(pair[3], 10, pair=pair, data=recovery_packet(pair[3], 10), intent=intent))
    assert control._OWNER is None


@pytest.mark.parametrize('bad', ['low_hp', 'status', 'pp', 'nonattack', 'ppup_not_remaining'])
def test_recovery_needs_a_healthy_escort_with_three_remaining_damaging_pp(bad):
    pair = RECOVERY_PAIRS[0]; intent = step(pair); intent['recovery_route'] = True
    data = recovery_packet(pair[3], 10); party = data[0]['progress']['party']
    for mon in party[1:-1]: mon['hp'] = 60
    escort = party[0]
    if bad == 'low_hp': escort['hp'] = 66
    elif bad == 'status': escort['status'] = 16
    elif bad == 'nonattack': escort.update(moves=[133, 0, 0, 0], pp=[20, 0, 0, 0])
    else: escort['pp'] = [66, 0, 0, 0] if bad == 'ppup_not_remaining' else [2, 0, 0, 0]
    review(call(pair[3], 10, pair=pair, data=data, intent=intent))
    assert control._OWNER is None


def test_recovery_escort_accepts_three_remaining_pp_with_ppup_bits():
    pair = RECOVERY_PAIRS[0]; intent = step(pair); intent['recovery_route'] = True
    data = recovery_packet(pair[3], 10); party = data[0]['progress']['party']
    for mon in party[1:-1]: mon['hp'] = 60
    party[0]['pp'] = [67, 0, 0, 0]  # 一次 PP Up、實際剩 3 PP 的 BubbleBeam。
    assert call(pair[3], 10, pair=pair, data=data, intent=intent)['available_actions'] == ['right', 'wait']


def test_recovery_flag_cannot_rebind_existing_owner_across_reload_or_erase_faint():
    pair = RECOVERY_PAIRS[0]; intent = step(pair); intent['recovery_route'] = True
    call(pair[3], 10, pair=pair, data=recovery_packet(pair[3], 10), intent=intent)
    owner = control._OWNER; record = control._SESSIONS[owner]
    snapshot = deepcopy(record)
    importlib.reload(control)
    changed = deepcopy(intent); changed['recovery_route'] = False
    review(call(pair[3], 11, pair=pair, data=recovery_packet(pair[3], 11), intent=changed))
    assert control._OWNER == owner and control._SESSIONS[owner] is record
    assert record['started'] == snapshot['started'] and record['waits'] == snapshot['waits']
    assert record['baseline'] == snapshot['baseline'] and record['baseline'][0][-1]['hp'] == 0
    assert call(pair[3], 12, pair=pair, data=recovery_packet(pair[3], 12), intent=intent)['phase'] == 'campaign_review'
