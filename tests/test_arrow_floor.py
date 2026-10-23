"""純來源／合成觀測反例；不讀ROM、存檔或模擬器，不執行遊戲按鍵。"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from laya_pokemon.arrow_floor import (
    ArrowFloorController, SOURCE_COMMIT, MOVEMENT_PROFILE, source_hop,
)


CASES = [(200, (17, 11)), (200, (4, 11)), (200, (11, 14)), (200, (13, 18)),
         (200, (13, 22)), (200, (10, 25)), (200, (5, 14)), (200, (11, 16)),
         (201, (12, 11)), (201, (10, 13)), (201, (11, 18)), (201, (18, 16)), (201, (16, 13))]


def movement(frame, **overrides):
    return {'read_valid': True, 'profile': MOVEMENT_PROFILE, 'source_commit': SOURCE_COMMIT,
            'observation_frame': frame, 'spinning': False, 'simulated_remaining': 0,
            'joy_ignore': 0, 'walk_counter': 0, **overrides}


def observation(controller, point=None, frame=100):
    hop = controller.hop
    x, y = point or hop['from']
    location = {'map_id': hop['map_id'], 'x': x, 'y': y}
    tiles = [[1] * 30 for _ in range(28)]
    tx, ty = hop['trigger']
    sx, sy = hop['expected_landing']
    tiles[ty][tx], tiles[sy][sx] = hop['trigger_tile'], 0x5E
    # 合成可見核對證據含目前點和入口；正式呼叫端須由真正畫面比對產生。
    visible = {(x, y), (tx, ty)}
    for yy in range(max(0, y - 2), min(28, y + 3)):
        for xx in range(max(0, x - 2), min(30, x + 3)):
            visible.add((xx, yy))
    grid = {'tileset_id': 22, 'tiles': tiles, 'walkable': [[1] * 30 for _ in range(28)],
            'observation_frame': frame, 'verified_location': [hop['map_id'], x, y],
            'visible_verified_cells': [list(p) for p in sorted(visible)],
            'screen_cells_verified': len(visible)}
    return location, grid


def call(controller, point=None, *, frame=100, now=1.0, grid_override='default',
         overworld_ready=True, battle_active=False, movement_override=None):
    loc, grid = observation(controller, point, frame)
    if grid_override != 'default':
        grid = grid_override
    return controller.context(loc, grid, movement_override or movement(frame), frame=frame, now=now,
                              overworld_ready=overworld_ready, battle_active=battle_active)


def test_all_thirteen_cases_match_separately_recorded_fixed_source_rle_and_route_definitions():
    path = Path(__file__).parents[1] / 'outputs/research/rocket-hideout-20261023.json'
    research = json.loads(path.read_text(encoding='utf-8'))
    assert research['source_commit'] == SOURCE_COMMIT
    found = set()
    for route in research['source_movement_routes'].values():
        for op in route['operations']:
            if op['kind'] != 'spin_entry_and_wait':
                continue
            key = route['map_id'], tuple(op['trigger'])
            hop = source_hop(*key)
            assert hop['from'] == tuple(op['from']) and hop['entry_action'] == op['entry_action']
            assert hop['expected_landing'] == tuple(op['expected_landing'])
            assert len(op['chains']) == 1
            chain = op['chains'][0]
            assert hop['source_label'] == chain['source_label']
            assert hop['rle'] == tuple((r['direction'], r['count']) for r in chain['moves_in_actual_execution_order'])
            found.add(key)
    assert found == set(CASES)


@pytest.mark.parametrize('map_id,trigger', CASES)
def test_each_source_hop_sends_only_one_entry_direction_then_waits_and_verifies_stop(map_id, trigger):
    controller = ArrowFloorController(map_id, trigger)
    result = call(controller)
    assert result['available_actions'] == [controller.hop['entry_action'], 'wait']
    assert result['suppress_navigation_stall'] and result['suppress_blocked_edge_learning']
    # tick可能略過短滑行，不能捏造已看到每個中途座標；只驗實際落點。
    stop = controller.hop['expected_landing']
    result = call(controller, stop, frame=132, now=1.2)
    assert result['available_actions'] == ['wait'] and not result.get('arrow_floor_complete')
    result = call(controller, stop, frame=164, now=1.4)
    assert result['arrow_floor_complete'] and result['arrow_observed_landing'] == list(stop)
    assert result['available_actions'] == ['wait'] and result['phase'] != 'overworld'


def test_forced_motion_uses_only_wait_even_without_aligned_grid_and_never_publishes_next_direction():
    controller = ArrowFloorController(200, (17, 11))
    call(controller)
    for i, point in enumerate(((17, 11), (16, 11), (12, 9), (2, 9)), 1):
        frame = 100 + i * 8
        result = call(controller, point, frame=frame, now=1 + i / 10, grid_override=None,
                      movement_override=movement(frame, spinning=True, simulated_remaining=5, joy_ignore=255))
        assert result['available_actions'] == ['wait'] and not result.get('arrow_floor_complete')
        assert result['phase'] == 'arrow_floor'  # 既有nav_stall僅累計overworld。


def test_passive_arrow_wait_uses_existing_laya_zero_inference_branch():
    from laya_pokemon.policy import LayaPolicy
    controller = ArrowFloorController(201, (12, 11));call(controller)
    state = call(controller, frame=132)
    # 不呼叫__init__，不載權重；若choose嘗試推論，缺agent會直接失敗。
    policy = LayaPolicy.__new__(LayaPolicy)
    result = policy.choose(state)
    assert result['action'] == 'wait' and result['passive_wait'] and result['model_ms'] == 0


@pytest.mark.parametrize('field,value', [('spinning', True), ('simulated_remaining', 1),
                                        ('joy_ignore', 255), ('walk_counter', 1)])
def test_landing_coordinate_alone_does_not_complete_before_all_movement_is_idle(field, value):
    controller = ArrowFloorController(201, (18, 16))
    call(controller)
    result = call(controller, controller.hop['expected_landing'], frame=132,
                  movement_override=movement(132, **{field: value}))
    assert result['available_actions'] == ['wait'] and not result.get('arrow_floor_complete')
    assert controller.stable_samples == 0


def test_duplicate_frame_and_unknown_screen_do_not_count_as_stable_landing_samples():
    controller = ArrowFloorController(201, (18, 16))
    call(controller)
    stop = controller.hop['expected_landing']
    call(controller, stop, frame=132)
    assert not call(controller, stop, frame=132).get('arrow_floor_complete')
    call(controller, stop, frame=164, grid_override=None)
    assert controller.stable_samples == 0
    assert not call(controller, stop, frame=196).get('arrow_floor_complete')
    assert call(controller, stop, frame=228)['arrow_floor_complete']


def test_changed_landing_neighborhood_restarts_stability_proof():
    controller = ArrowFloorController(201, (18, 16))
    call(controller)
    stop = controller.hop['expected_landing']
    call(controller, stop, frame=132)
    _, grid = observation(controller, stop, 164)
    grid['tiles'][stop[1]][stop[0] - 1] = 2
    assert not call(controller, stop, frame=164, grid_override=grid).get('arrow_floor_complete')
    assert controller.stable_samples == 1


@pytest.mark.parametrize('change,reason', [
    ('tileset', 'arrow_grid_tileset_not_verified'),
    ('frame', 'arrow_grid_observation_not_current'),
    ('location', 'arrow_grid_observation_not_current'),
    ('shape', 'arrow_grid_shape_or_values_invalid'),
    ('tile_value', 'arrow_grid_shape_or_values_invalid'),
    ('walkable_value', 'arrow_grid_shape_or_values_invalid'),
    ('no_visible_coordinates', 'arrow_visible_cell_proof_missing'),
    ('duplicate_coordinates', 'arrow_visible_cell_proof_missing'),
    ('wrong_count', 'arrow_visible_cell_proof_missing'),
    ('entry_not_visible', 'arrow_entry_cells_not_visibly_verified'),
    ('wrong_entry_tile', 'arrow_entry_tiles_do_not_match_source'),
    ('blocked_entry', 'arrow_entry_tiles_do_not_match_source'),
])
def test_unverified_or_contradictory_grid_never_sends_an_entry_button(change, reason):
    controller = ArrowFloorController(201, (12, 11))
    loc, grid = observation(controller)
    if change == 'tileset': grid['tileset_id'] = 7
    elif change == 'frame': grid['observation_frame'] = 99
    elif change == 'location': grid['verified_location'][1] += 1
    elif change == 'shape': grid['tiles'].pop()
    elif change == 'tile_value': grid['tiles'][0][0] = -1
    elif change == 'walkable_value': grid['walkable'][0][0] = True
    elif change == 'no_visible_coordinates': grid.pop('visible_verified_cells')
    elif change == 'duplicate_coordinates': grid['visible_verified_cells'][-1] = grid['visible_verified_cells'][0]
    elif change == 'wrong_count': grid['screen_cells_verified'] += 1
    elif change == 'entry_not_visible':
        grid['visible_verified_cells'].remove(list(controller.hop['trigger']))
        grid['screen_cells_verified'] -= 1
    elif change == 'wrong_entry_tile': grid['tiles'][11][12] = 0x30
    else: grid['walkable'][11][12] = 0
    result = controller.context(loc, grid, movement(100), frame=100, now=1, overworld_ready=True)
    assert result['review_reason'] == reason and result['available_actions'] == ['wait']


@pytest.mark.parametrize('change,reason', [('not_visible', 'arrow_stop_cell_not_visibly_verified'),
                                        ('not_stop_tile', 'arrow_landing_is_not_source_stop_tile'),
                                        ('not_walkable', 'arrow_landing_is_not_source_stop_tile')])
def test_stop_requires_visible_source_stop_tile_and_walkability(change, reason):
    controller = ArrowFloorController(201, (12, 11));call(controller)
    stop = controller.hop['expected_landing']
    _, grid = observation(controller, stop, 132)
    if change == 'not_visible':
        grid['visible_verified_cells'].remove(list(stop));grid['screen_cells_verified'] -= 1
    elif change == 'not_stop_tile': grid['tiles'][stop[1]][stop[0]] = 1
    else: grid['walkable'][stop[1]][stop[0]] = 0
    result = call(controller, stop, frame=132, grid_override=grid)
    assert result['review_reason'] == reason and not result.get('arrow_floor_complete')


@pytest.mark.parametrize('mutation', [
    lambda m: m.update(read_valid=False), lambda m: m.update(profile='unknown'),
    lambda m: m.update(source_commit='other'), lambda m: m.update(observation_frame=99),
    lambda m: m.update(spinning=0), lambda m: m.update(simulated_remaining=True),
    lambda m: m.update(joy_ignore=-1), lambda m: m.pop('walk_counter'),
])
def test_unknown_stale_or_invalid_movement_read_only_reviews(mutation):
    controller = ArrowFloorController(201, (12, 11))
    m = movement(100);mutation(m)
    result = call(controller, movement_override=m)
    assert result['review_reason'] == 'arrow_movement_read_not_verified'
    assert result['available_actions'] == ['wait']


def test_other_script_input_mask_is_unknown_and_cannot_be_treated_as_arrow_motion():
    controller = ArrowFloorController(201, (12, 11));call(controller)
    result = call(controller, controller.hop['trigger'], frame=132,
                  movement_override=movement(132, spinning=True, simulated_remaining=2, joy_ignore=16))
    assert result['review_reason'] == 'arrow_input_ignore_mask_unknown'
    assert result['available_actions'] == ['wait']


@pytest.mark.parametrize('point,reason', [((13, 11), None), ((12, 11), None),
                                       ((11, 11), 'arrow_stopped_before_expected_stop'),
                                       ((20, 20), 'arrow_observed_outside_source_route')])
def test_stalled_entry_is_not_retried_and_unexpected_stops_or_positions_review(point, reason):
    controller = ArrowFloorController(201, (12, 11));call(controller)
    result = call(controller, point, frame=132)
    assert result['available_actions'] == ['wait']
    assert result.get('review_reason') == reason


def test_wait_call_and_wall_time_budgets_end_in_latched_review_without_resending():
    controller = ArrowFloorController(201, (12, 11), max_waits=2)
    call(controller)
    for frame in (132, 164): assert call(controller, frame=frame)['available_actions'] == ['wait']
    result = call(controller, frame=196)
    assert result['review_reason'] == 'arrow_wait_budget_exhausted'
    assert call(controller, controller.hop['expected_landing'], frame=228) == result
    controller = ArrowFloorController(201, (12, 11), max_calls=1);call(controller)
    assert call(controller, frame=132)['review_reason'] == 'arrow_operation_budget_exhausted'
    controller = ArrowFloorController(201, (12, 11));call(controller)
    assert call(controller, frame=132, now=61.1)['review_reason'] == 'arrow_operation_budget_exhausted'


@pytest.mark.parametrize('kwargs', [{'frame': 99}, {'now': 0.5}, {'frame': True}, {'now': float('nan')}])
def test_invalid_or_backwards_clock_and_frame_review(kwargs):
    controller = ArrowFloorController(201, (12, 11));call(controller)
    assert call(controller, **kwargs)['review_reason'] == 'arrow_clock_or_frame_invalid'


def test_no_early_complete_wrong_map_battle_and_unknown_overworld_claim_review():
    controller = ArrowFloorController(201, (12, 11))
    assert call(controller, controller.hop['expected_landing'])['review_reason'] == 'arrow_entry_stance_or_idle_not_verified'
    controller = ArrowFloorController(201, (12, 11));loc, grid = observation(controller)
    loc['map_id'] = 200
    assert controller.context(loc, grid, movement(100), frame=100, now=1, overworld_ready=True)['review_reason'] == 'arrow_location_unverified_or_wrong_map'
    assert call(ArrowFloorController(201, (12, 11)), battle_active=True)['review_reason'] == 'arrow_requires_verified_nonbattle'
    assert call(ArrowFloorController(201, (12, 11)), overworld_ready=1)['review_reason'] == 'arrow_requires_verified_nonbattle'


def test_inputs_and_pinned_source_spec_are_not_mutated():
    controller = ArrowFloorController(201, (12, 11));loc, grid = observation(controller);m = movement(100)
    before = deepcopy((loc, grid, m))
    controller.context(loc, grid, m, frame=100, now=1, overworld_ready=True)
    assert (loc, grid, m) == before
    spec = source_hop(201, (12, 11));spec['expected_landing'] = (0, 0)
    assert source_hop(201, (12, 11))['expected_landing'] == (10, 11)


@pytest.mark.parametrize('map_id,trigger', [(203, (1, 1)), (200, (0, 0)), (True, (12, 11)),
                                          (201, (True, 11)), (201, (12,)), (201, '12,11')])
def test_elevator_arbitrary_or_malformed_hops_are_not_supported(map_id, trigger):
    with pytest.raises(ValueError): ArrowFloorController(map_id, trigger)


@pytest.mark.parametrize('kwargs', [{'max_calls': 0}, {'max_waits': True}, {'max_calls': 1001},
                                   {'max_seconds': 61}, {'max_seconds': 0}, {'max_seconds': float('inf')}])
def test_operation_limits_must_remain_bounded(kwargs):
    with pytest.raises(ValueError): ArrowFloorController(201, (12, 11), **kwargs)
