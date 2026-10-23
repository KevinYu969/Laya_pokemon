"""以合成唯讀進度驗證損耗閘門；不操作遊戲或儲存檔。"""
from copy import deepcopy

import pytest

from laya_pokemon.campaign_safety import attrition_context


def state():
    return {'phase': 'overworld', 'battle_state': {'active': False, 'kind': 'none'},
            'progress': {'party_read_valid': True, 'party_count': 3, 'party': [
                {'species': 9, 'hp': 80, 'max_hp': 80},
                {'species': 167, 'hp': 73, 'max_hp': 73},
                {'species': 35, 'hp': 60, 'max_hp': 60},
            ]}}


def plan(**step):
    return {'mode': 'league_campaign', 'steps': [{'id': 'next', 'kind': 'move', **step}]}


@pytest.mark.parametrize('index', [0, 1, 2])
def test_any_nonbattle_fainted_party_member_stops_before_navigation(index):
    current = state()
    current['progress']['party'][index]['hp'] = 0
    result = attrition_context(current, plan(), 'next')
    assert result['phase'] == 'campaign_review' and result['available_actions'] == ['wait']
    assert result['review_reason'] == 'party_attrition_requires_center'
    assert result['party_attrition']['fainted_party_indices'] == [index]


@pytest.mark.parametrize('hp,maximum,stops', [(60, 90, True), (59, 90, True), (61, 90, False),
                                           (48, 73, True), (49, 73, False)])
def test_lead_two_thirds_boundary_uses_exact_integer_comparison(hp, maximum, stops):
    current = state()
    current['progress']['party'][0].update(hp=hp, max_hp=maximum)
    result = attrition_context(current, plan(), 'next')
    assert (result is not None) is stops
    if stops:
        assert result['review_reason'] == 'party_attrition_requires_center'
        assert result['party_attrition']['lead_at_or_below_two_thirds']


def test_low_hp_support_without_faint_does_not_expand_the_requested_lead_threshold():
    current = state()
    current['progress']['party'][1]['hp'] = 1
    assert attrition_context(current, plan(), 'next') is None


def test_rock_tunnel_postbattle_attrition_stops_even_without_a_supported_heal_detour():
    current = state()
    current['location'] = {'map_id': 82}
    current['progress']['party'] = [
        {'species': 35, 'hp': 21, 'max_hp': 70},
        {'species': 167, 'hp': 29, 'max_hp': 76},
        {'species': 9, 'hp': 38, 'max_hp': 79},
    ]
    result = attrition_context(current, plan(), 'next')
    assert result['review_reason'] == 'party_attrition_requires_center'
    assert result['party_attrition']['fainted_party_indices'] == []
    current['progress']['party'][1]['hp'] = 0
    current['progress']['party'][2]['hp'] = 0
    assert attrition_context(current, plan(), 'next')['party_attrition']['fainted_party_indices'] == [1, 2]


@pytest.mark.parametrize('kind,active', [('trainer', True), ('wild', True), ('lost_transition', False)])
def test_still_in_battle_or_loss_transition_is_left_to_the_battle_loss_guard(kind, active):
    current = state()
    current['battle_state'] = {'kind': kind, 'active': active}
    for mon in current['progress']['party']:
        mon['hp'] = 0
    assert attrition_context(current, plan(), 'next') is None


@pytest.mark.parametrize('phase', ['battle_menu', 'battle_dialogue', 'dialogue', 'learning_menu', 'campaign_review'])
def test_only_overworld_or_unclassified_is_checked(phase):
    current = state()
    current['phase'] = phase
    current['progress']['party'][0]['hp'] = 0
    assert attrition_context(current, plan(), 'next') is None


def test_unclassified_overworld_with_known_nonbattle_is_also_guarded():
    current = state()
    current['phase'] = 'unclassified'
    current['progress']['party'][1]['hp'] = 0
    assert attrition_context(current, plan(), 'next')['review_reason'] == 'party_attrition_requires_center'


@pytest.mark.parametrize('mode', ['balanced_training', 'battle_recovery', None])
def test_other_campaign_modes_are_not_changed(mode):
    current = state()
    current['progress']['party'][1]['hp'] = 0
    configured = plan()
    configured['mode'] = mode
    assert attrition_context(current, configured, 'next') is None


def test_normal_center_healing_releases_the_gate_without_hidden_session_or_latch():
    current = state()
    current['progress']['party'][1]['hp'] = 0
    assert attrition_context(current, plan(), 'next') is not None
    current['progress']['party'][1]['hp'] = 73
    assert attrition_context(current, plan(), 'next') is None


@pytest.mark.parametrize('kind', ['move', 'heal'])
def test_explicit_current_recovery_move_or_heal_can_proceed(kind):
    current = state()
    current['progress']['party'][0]['hp'] = 1
    current['progress']['party'][1]['hp'] = 0
    assert attrition_context(current, plan(kind=kind, recovery_route=True), 'next') is None


@pytest.mark.parametrize('kind', ['interact', 'use_cut', 'teach_cut', 'useCut', 'wait', None])
def test_nonwhitelisted_actions_cannot_escape_by_setting_recovery_flag(kind):
    current = state()
    current['progress']['party'][1]['hp'] = 0
    result = attrition_context(current, plan(kind=kind, recovery_route=True), 'next')
    assert result['review_reason'] == 'party_attrition_requires_center'


@pytest.mark.parametrize('flag', [False, 1, 'true', None])
def test_recovery_flag_requires_literal_true(flag):
    current = state()
    current['progress']['party'][1]['hp'] = 0
    assert attrition_context(current, plan(recovery_route=flag), 'next')['review_reason'] == 'party_attrition_requires_center'


def test_recovery_permission_does_not_leak_from_other_or_duplicate_steps():
    current = state()
    current['progress']['party'][1]['hp'] = 0
    configured = plan()
    configured['steps'].append({'id': 'center', 'kind': 'move', 'recovery_route': True})
    assert attrition_context(current, configured, 'next')['review_reason'] == 'party_attrition_requires_center'
    configured['steps'].append({'id': 'next', 'kind': 'heal', 'recovery_route': True})
    assert attrition_context(current, configured, 'next')['review_reason'] == 'party_attrition_requires_center'
    assert attrition_context(current, configured, 'absent')['review_reason'] == 'party_attrition_requires_center'


@pytest.mark.parametrize('value', [None, -1, True, 1.5, '5', 81])
def test_unknown_or_invalid_hp_stops_even_if_the_step_is_marked_recovery(value):
    current = state()
    current['progress']['party'][0]['hp'] = value
    result = attrition_context(current, plan(recovery_route=True), 'next')
    assert result['review_reason'] == 'party_attrition_state_unverified'
    assert result['available_actions'] == ['wait']


@pytest.mark.parametrize('value', [None, 0, -1, True, 80.5, '80'])
def test_unknown_or_invalid_max_hp_requires_review(value):
    current = state()
    current['progress']['party'][2]['max_hp'] = value
    assert attrition_context(current, plan(), 'next')['review_reason'] == 'party_attrition_state_unverified'


@pytest.mark.parametrize('value', [False, None, 1, 'true'])
def test_party_read_must_be_verified_true(value):
    current = state()
    current['progress']['party_read_valid'] = value
    assert attrition_context(current, plan(recovery_route=True), 'next')['review_reason'] == 'party_attrition_state_unverified'


def test_empty_initial_roster_cannot_pass_the_gate():
    current = state()
    current['progress'].update(party=[], party_count=0)
    assert attrition_context(current, plan(recovery_route=True), 'next')['review_reason'] == 'party_attrition_state_unverified'


@pytest.mark.parametrize('signal', [None, {}, {'kind': 'unknown', 'active': None}, {'kind': 'none', 'active': None}])
def test_missing_or_unknown_nonbattle_signal_cannot_authorize_navigation(signal):
    current = state()
    current['battle_state'] = signal
    assert attrition_context(current, plan(), 'next')['review_reason'] == 'party_attrition_state_unverified'


def test_party_count_disagreement_and_nonmember_record_require_review():
    current = state()
    current['progress']['party_count'] = 2
    assert attrition_context(current, plan(), 'next')['party_attrition']['issue'] == 'party_count_mismatch'
    current['progress']['party_count'] = 3
    current['progress']['party'][1] = None
    assert attrition_context(current, plan(), 'next')['party_attrition']['issue'] == 'party_member_invalid'


def test_function_never_mutates_state_or_plan_including_fainted_recovery_case():
    current, configured = state(), plan(recovery_route=True)
    current['progress']['party'][1]['hp'] = 0
    before = deepcopy((current, configured))
    assert attrition_context(current, configured, 'next') is None
    assert (current, configured) == before
    configured['steps'][0]['kind'] = 'interact'
    before = deepcopy((current, configured))
    attrition_context(current, configured, 'next')
    assert (current, configured) == before
