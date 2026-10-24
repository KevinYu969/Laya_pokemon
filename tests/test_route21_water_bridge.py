"""只用假getter與純controller核橋接，不啟動遊戲或讀取存檔。"""
from copy import deepcopy
from importlib import reload
from types import SimpleNamespace

import pytest

from laya_pokemon import route21_water_bridge as bridge
from laya_pokemon.rocket_movement import MOVEMENT_PROFILE


@pytest.fixture
def env(monkeypatch):
    for name, value in (('_CONTROLLERS', {}), ('_BINDINGS', {}), ('_COMPLETED', set())):
        monkeypatch.setattr(bridge, name, value)
    from laya_pokemon import campaign_transactions as tx
    monkeypatch.setattr(tx, 'verified_blank_transaction_world', lambda t, g: t.get('ready') is True)

    class Controller:
        def __init__(self, intent):
            self.intent = deepcopy(intent); self.fingerprint = {'original': True}
            self.pending = {'frame': 90, 'action': 'down'}; self.calls = self.waits = 0
            self.started = 4.; self.step_started = 5.; self.excluded = 3.
            self.result = dict(phase='overworld', objective='Wait.', available_actions=['wait'])
        def context(self, state, **kwargs):
            self.state = state; self.args = kwargs; self.calls += 1
            return deepcopy(self.result)

    monkeypatch.setattr(bridge.route21_water, 'Route21WaterController', Controller)
    loc = dict(map_id=0, x=4, y=14)
    signal = dict(profile=bridge.pallet_surf.PROFILE, source_commit=bridge.route21_water.SOURCE_COMMIT,
                  read_valid=True, read_error=None, observation_frame=100, mode=2,
                  location=deepcopy(loc), battle_raw=0)
    movement = dict(profile=MOVEMENT_PROFILE, source_commit=bridge.route21_water.SOURCE_COMMIT,
        read_valid=True, read_error=None, observation_frame=100, spinning=False,
        simulated_remaining=0, joy_ignore=0, walk_counter=0, movement_flags=0)
    reads = []
    def reader(game, frame, constants):
        reads.append(('surf', game, frame)); return deepcopy(signal)
    def movement_reader(game, *, observation_frame):
        reads.append(('movement', game, observation_frame)); return deepcopy(movement)
    monkeypatch.setattr(bridge.pallet_surf, 'read_surf_observation', reader)
    monkeypatch.setattr(bridge, 'read_rocket_movement', movement_reader)
    monkeypatch.setattr(bridge.time, 'monotonic', lambda: 10.)
    step = dict(id='route21', kind='interact', mechanic='route21_water', map_id=0,
                target=[4, 14], water_intent=deepcopy(bridge.route21_water.INTENT))
    state = dict(frame=100, location=deepcopy(loc), progress={'full': 'original-progress'},
                 battle_state=dict(raw=0, active=False, kind='none', observation_frame=100),
                 text={'old': 'must-not-overwrite'})
    return SimpleNamespace(plan=dict(training_job='route21-mainline', steps=[step]), step=step,
        state=state, signal=signal, movement=movement, reads=reads, fake=SimpleNamespace(),
        Controller=Controller, reader=reader, movement_reader=movement_reader)


def call(e, *, step_id='route21', ready=True, previous=None, text=None, grid=None):
    return bridge.context(e.fake, e.state, e.plan, step_id,
        {'ready': ready, 'full': 'decoder'} if text is None else text,
        {'full': 'grid'} if grid is None else grid, ['wait'] if previous is None else previous)


def review(result):
    assert result[0]['phase'] == 'campaign_review'
    assert result[0]['available_actions'] == ['wait'] and result[1] == 'route21'


def move(e, mid, x, y, mode, frame=140):
    e.state.update(frame=frame, location=dict(map_id=mid, x=x, y=y))
    e.state['battle_state']['observation_frame'] = frame
    e.signal.update(observation_frame=frame, location=deepcopy(e.state['location']), mode=mode)
    e.movement['observation_frame'] = frame


def test_full_decoder_and_actual_previous_are_forwarded_in_state_copy_without_mutation(env):
    original = deepcopy(env.state); previous = ['a', 'down']
    text = {'ready': True, 'cells': [['full-native-cell']], 'lines': ['native'], 'extra': 'retained'}
    grid = {'full': 'same-grid'}
    call(env, previous=previous, text=text, grid=grid)
    c = bridge._CONTROLLERS['route21']
    assert c.state is not env.state and c.state['text'] is text
    assert c.state['progress'] is env.state['progress'] and env.state == original
    assert c.args['previous'] is previous and c.args['grid'] is grid
    assert c.args['signal'] == env.signal and c.args['movement'] == env.movement
    assert c.args['now'] == 10.
    assert env.reads == [('surf', env.fake, 100), ('movement', env.fake, 100)]


def test_first_wild_returns_bare_none_and_preserves_original_instance_pending_and_budgets(env):
    call(env); c = bridge._CONTROLLERS['route21']; fp, pending = c.fingerprint, c.pending
    c.waits = 12; move(env, 0, 4, 15, 2)
    env.state['battle_state'].update(raw=1, active=True, kind='wild')
    env.signal['battle_raw'] = 1; c.result = None
    assert call(env, ready=False, previous=['down']) is None
    assert c.state['battle_state']['kind'] == 'wild' and c.args['previous'] == ['down']
    assert bridge._CONTROLLERS['route21'] is c and c.fingerprint is fp and c.pending is pending
    assert (c.waits, c.started, c.step_started, c.excluded) == (12, 4., 5., 3.)
    assert not bridge._COMPLETED
    env.state['battle_state'].update(raw=0, active=False, kind='none'); env.signal['battle_raw'] = 0
    c.result = dict(available_actions=['down', 'wait'])
    assert call(env)[1] == 'route21' and bridge._CONTROLLERS['route21'] is c


def test_bound_instance_survives_both_map_boundaries_and_requires_exact_goal_receipt(env):
    call(env); c = bridge._CONTROLLERS['route21']; original = c.fingerprint
    move(env, 32, 4, 0, 2); assert call(env)[1] == 'route21'
    move(env, 8, 3, 0, 2, 180); assert call(env)[1] == 'route21'
    move(env, 8, 4, 10, 0, 220); assert call(env)[1] == 'route21'
    assert not bridge._COMPLETED and c.fingerprint is original
    c.result['route21_water_complete'] = True
    env.plan['steps'].append(dict(id='cinnabar-center', kind='move'))
    hint, next_id = call(env)
    assert next_id == 'cinnabar-center' and hint['field_move_complete'] is True
    assert hint['field_move_kind'] == 'route21-water' and bridge._COMPLETED == {'route21'}


@pytest.mark.parametrize('key,value', [('next_map', 8), ('terminal', True), ('event', 'arrived'),
    ('item', 198), ('badge', 16), ('await_script_event', True), ('kind', 'move'),
    ('map_id', False), ('target', [4, 13]), ('target', [4., 14])])
def test_explicit_step_contract_rejects_generic_completion_and_mistyped_coordinates(env, key, value):
    env.step[key] = value
    review(call(env)); assert not bridge._BINDINGS and not bridge._CONTROLLERS and not env.reads


@pytest.mark.parametrize('key,value', [('start', [False, 4, 14]), ('goal', [8, 4., 10]),
                                      ('path_id', 'other'), ('extra', True)])
def test_water_intent_cannot_change_or_use_bool_float_coordinates(env, key, value):
    env.step['water_intent'][key] = value
    review(call(env)); assert not bridge._BINDINGS


def test_unbound_far_or_already_landed_never_creates_owner_or_claims_complete(env):
    move(env, 0, 4, 13, 0)
    assert call(env) is None
    move(env, 32, 4, 0, 2)
    assert call(env) is None
    move(env, 8, 4, 10, 0)
    assert call(env) is None and not bridge._BINDINGS and not env.reads


@pytest.mark.parametrize('change', ['window', 'mode', 'signal_frame', 'profile', 'moving', 'active', 'text_frame'])
def test_new_owner_requires_true_initial_closed_world_same_frame_water_and_idle(env, change):
    kwargs = {}
    if change == 'window': kwargs['ready'] = False
    if change == 'mode': env.signal['mode'] = 0
    if change == 'signal_frame': env.signal['observation_frame'] = 99
    if change == 'profile': env.signal['profile'] = 'unverified'
    if change == 'moving': env.movement['walk_counter'] = 2
    if change == 'active':
        env.state['battle_state'].update(raw=1, active=True, kind='wild'); env.signal['battle_raw'] = 1
    if change == 'text_frame': kwargs['text'] = {'ready': True, 'observation_frame': True}
    review(call(env, **kwargs)); assert not bridge._BINDINGS


@pytest.mark.parametrize('change', ['location', 'mode', 'signal_location', 'window', 'moving', 'signal_frame'])
def test_erroneous_complete_flag_cannot_bypass_native_landfall_evidence(env, change):
    call(env); c = bridge._CONTROLLERS['route21']; c.result['route21_water_complete'] = True
    move(env, 8, 4, 10, 0); kwargs = {}
    if change == 'location': move(env, 8, 3, 10, 0)
    if change == 'mode': env.signal['mode'] = 2
    if change == 'signal_location': env.signal['location']['x'] = 3
    if change == 'window': kwargs['ready'] = False
    if change == 'moving': env.movement['walk_counter'] = 1
    if change == 'signal_frame': env.signal['observation_frame'] = 100
    review(call(env, **kwargs)); assert not bridge._COMPLETED


def test_other_alias_or_truthy_complete_never_advances(env):
    call(env); c = bridge._CONTROLLERS['route21']; move(env, 8, 4, 10, 0)
    c.result.update(field_move_complete=True, surf_entry_complete=True, route21_water_complete=1)
    assert call(env)[1] == 'route21' and not bridge._COMPLETED


def test_active_owner_step_job_or_intent_change_is_rejected_before_context(env):
    call(env); c = bridge._CONTROLLERS['route21']
    assert call(env, step_id='another')[0]['review_reason'].endswith('owner_changed')
    env.plan['training_job'] = 'new-job'; review(call(env))
    env.plan['training_job'] = 'route21-mainline'; env.step.pop('mechanic'); review(call(env))
    assert c.calls == 1 and bridge.applies('another', None)


def test_missing_original_registry_parts_never_rebind_or_reset_budget(env):
    call(env); c = bridge._CONTROLLERS.pop('route21')
    review(call(env)); assert not bridge._CONTROLLERS
    bridge._CONTROLLERS['route21'] = c; bridge._BINDINGS.clear()
    review(call(env)); assert c.calls == 1


def test_reload_and_review_revision_preserve_original_controller_fingerprint_and_clocks(env, monkeypatch):
    call(env); c = bridge._CONTROLLERS['route21']; fp, pending = c.fingerprint, c.pending
    c.waits = 15; env.plan['resume_revision'] = 8
    env.step['reviewed_revision'] = 5
    bindings = bridge._BINDINGS; completed = bridge._COMPLETED
    reload(bridge)
    monkeypatch.setattr(bridge.route21_water, 'Route21WaterController', env.Controller)
    monkeypatch.setattr(bridge.pallet_surf, 'read_surf_observation', env.reader)
    monkeypatch.setattr(bridge, 'read_rocket_movement', env.movement_reader)
    call(env)
    assert bridge._CONTROLLERS['route21'] is c and c.fingerprint is fp and c.pending is pending
    assert bridge._BINDINGS is bindings and bridge._COMPLETED is completed
    assert (c.waits, c.started, c.step_started, c.excluded, c.calls) == (15, 4., 5., 3., 2)


def test_duplicate_id_or_removed_active_step_is_not_generic_fallback(env):
    env.plan['steps'].append(deepcopy(env.step)); review(call(env))
    env.plan['steps'].pop(); call(env); env.plan['steps'] = []
    review(call(env)); assert bridge._CONTROLLERS['route21'].calls == 1


def test_unrelated_step_is_ignored_without_an_owner(env):
    env.step['mechanic'] = 'unrelated'
    assert call(env) is None and not bridge.applies('route21', env.step)
    assert bridge.applies('route21', {'mechanic': 'route21_water'})
