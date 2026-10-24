"""秘密鑰匙橋接純測試；假getter不讀RAM，真constructor核格式。"""
from copy import deepcopy
from importlib import reload
from types import SimpleNamespace

import pytest

from laya_pokemon import mansion_secret_key_bridge as bridge


@pytest.fixture
def env(monkeypatch):
    for name, value in (('_CONTROLLERS', {}), ('_BINDINGS', {}), ('_COMPLETED', set())):
        monkeypatch.setattr(bridge, name, value)
    from laya_pokemon import campaign_transactions as tx
    monkeypatch.setattr(tx, 'verified_blank_transaction_world', lambda t, g: t.get('ready') is True)
    monkeypatch.setattr(tx, 'ui_overworld_ready', lambda t, g: t.get('ready') is True)
    real_controller = bridge.mansion_secret_key.MansionSecretKeyController

    class Controller:
        def __init__(self, intent):
            assert bridge.mansion_secret_key._intent(intent)
            self.intent = deepcopy(intent); self.baseline = {'original': 'six-party-bag-money'}
            self.pending = {'action': 'a', 'frame': 90}; self.calls = 0; self.waits = 9
            self.started = 4.; self.last_now = 5.; self.done = False; self.error = None
        def context(self, text, progress, **kwargs):
            self.text = text; self.progress = progress; self.args = kwargs; self.calls += 1
            if self.error:
                return dict(phase='campaign_review', review_reason=self.error, available_actions=['wait'])
            return dict(phase='overworld', objective='Wait.', available_actions=['wait'],
                        mansion_secret_key_complete=self.done)

    monkeypatch.setattr(bridge.mansion_secret_key, 'MansionSecretKeyController', Controller)
    signal = dict(profile=bridge.mansion_secret_key.PROFILE, source_commit=bridge.mansion_secret_key.SOURCE_COMMIT,
        read_valid=True, read_error=None, observation_frame=100, item_hidden=False,
        location=deepcopy(bridge.mansion_secret_key.LOCATION))
    reads = []
    def reader(game, frame, constants):
        reads.append((game, frame)); return deepcopy(signal)
    monkeypatch.setattr(bridge.mansion_secret_key, 'read_mansion_secret_key', reader)
    monkeypatch.setattr(bridge.time, 'monotonic', lambda: 10.)
    intent = deepcopy(bridge.mansion_secret_key.SECRET_KEY_INTENT)
    step = dict(id='mansion-key', kind='interact', mechanic='mansion_secret_key', map_id=216,
                target=[5, 12], key_intent=intent)
    state = dict(frame=100, location=deepcopy(bridge.mansion_secret_key.LOCATION),
                 progress={'original': 'progress'}, battle_state={'kind': 'none'})
    return SimpleNamespace(plan=dict(training_job='mansion-mainline', steps=[step]), step=step,
        state=state, signal=signal, reads=reads, game=SimpleNamespace(), Controller=Controller,
        RealController=real_controller, reader=reader)


def call(e, *, step_id='mansion-key', ready=True, previous=None, text=None, grid=None):
    return bridge.context(e.game, e.state, e.plan, step_id,
        {'ready': ready, 'original': 'full-text'} if text is None else text,
        {'original': 'grid'} if grid is None else grid, ['wait'] if previous is None else previous)


def review(result):
    assert result[0]['phase'] == 'campaign_review'
    assert result[0]['available_actions'] == ['wait'] and result[1] == 'mansion-key'


def test_true_constructor_contract_and_corrected_key194_bit2_match_bridge_intent(env):
    intent = env.step['key_intent']
    assert intent['object_index'] == 194 and bridge.mansion_secret_key.KEY_MASK == 4
    c = env.RealController(intent)
    assert c.intent == intent and c.binding == intent and c.baseline is None
    old = deepcopy(intent); old['object_index'] = 193
    with pytest.raises(ValueError): env.RealController(old)
    with pytest.raises(AssertionError): env.Controller(old)
    old = deepcopy(intent); old['player'] = [old.pop('player_x'), old.pop('player_y')]
    with pytest.raises(ValueError): env.RealController(old)
    assert call(env)[1] == 'mansion-key' and bridge._BINDINGS


def test_full_decoder_progress_actual_previous_grid_location_and_frame_are_forwarded_unchanged(env):
    text = {'ready': True, 'cells': [['native']], 'metadata': 'retained'}
    grid = {'original': 'same-grid'}; previous = ['down', 'a', 'wait']
    before = deepcopy((env.state, env.plan, text, grid, previous))
    call(env, text=text, grid=grid, previous=previous)
    c = bridge._CONTROLLERS['mansion-key']
    assert c.text is text and c.progress is env.state['progress']
    assert c.args['previous'] is previous and c.args['grid'] is grid
    assert c.args['location'] is env.state['location'] and c.args['battle_state'] is env.state['battle_state']
    assert c.args['frame'] == 100 and c.args['now'] == 10. and c.args['overworld_ready'] is True
    assert c.args['signal'] == env.signal and env.reads == [(env.game, 100)]
    assert (env.state, env.plan, text, grid, previous) == before


@pytest.mark.parametrize('key,value', [('next_map', 216), ('terminal', True), ('event', 'got_key'),
    ('item', 43), ('badge', 64), ('await_script_event', True), ('kind', 'move'),
    ('map_id', 215), ('map_id', 216.), ('target', [5, 13]), ('target', [5., 12])])
def test_generic_shortcuts_or_wrong_step_geometry_never_bind(env, key, value):
    env.step[key] = value
    review(call(env)); assert not bridge._CONTROLLERS and not bridge._BINDINGS and not env.reads


@pytest.mark.parametrize('key,value', [('object_index', 193), ('object_index', 194.), ('object_slot', 7),
    ('player_y', 13), ('facing', 'up'), ('quantity', True), ('item', 44), ('extra', 'unapproved')])
def test_wrong_key_schema_or_source_identity_never_reaches_constructor(env, key, value):
    env.step['key_intent'][key] = value
    review(call(env)); assert not bridge._BINDINGS and not env.reads


@pytest.mark.parametrize('change', ['closed', 'invalid', 'truthy', 'frame', 'profile', 'hidden', 'none'])
def test_unknown_initial_source_or_world_cannot_create_baseline(env, monkeypatch, change):
    kwargs = {}
    if change == 'closed': kwargs['ready'] = False
    if change == 'invalid': env.signal['read_valid'] = False
    if change == 'truthy': env.signal['read_valid'] = 1
    if change == 'frame': env.signal['observation_frame'] = 99
    if change == 'profile': env.signal['profile'] = 'unknown'
    if change == 'hidden': env.signal['item_hidden'] = True
    if change == 'none': monkeypatch.setattr(bridge.mansion_secret_key, 'read_mansion_secret_key', lambda *a: None)
    review(call(env, **kwargs)); assert not bridge._BINDINGS and not bridge._CONTROLLERS


def test_unbound_wrong_location_delegates_navigation_without_reading_or_claiming_done(env):
    env.state['location']['y'] = 11
    assert call(env) is None and not bridge._CONTROLLERS and not env.reads


def test_original_baseline_pending_error_and_used_budget_survive_same_owner_review_revision(env):
    call(env); c = bridge._CONTROLLERS['mansion-key']; base, pending = c.baseline, c.pending
    c.waits = 17; c.started = 1.25; c.last_now = 8.5; c.error = 'original_sticky_error'
    env.plan['resume_revision'] = 6; env.step['reviewed_revision'] = 3
    env.state['frame'] = 140; env.signal['observation_frame'] = 140
    review(call(env, ready=False))
    assert bridge._CONTROLLERS['mansion-key'] is c and c.baseline is base and c.pending is pending
    assert (c.calls, c.waits, c.started, c.last_now, c.error) == (2, 17, 1.25, 8.5, 'original_sticky_error')
    assert not bridge._COMPLETED


def test_owner_job_step_or_intent_change_cannot_replace_existing_instance(env):
    call(env); c = bridge._CONTROLLERS['mansion-key']
    assert call(env, step_id='other')[0]['review_reason'].endswith('owner_changed')
    env.plan['training_job'] = 'different-trip'; review(call(env))
    env.plan['training_job'] = 'mansion-mainline'
    env.step['key_intent']['quantity'] = 2; review(call(env))
    env.step['key_intent']['quantity'] = 1; env.step.pop('mechanic'); review(call(env))
    assert bridge._CONTROLLERS['mansion-key'] is c and c.calls == 1


def test_missing_original_instance_or_binding_is_never_silently_rebuilt(env):
    call(env); c = bridge._CONTROLLERS.pop('mansion-key')
    review(call(env)); assert not bridge._CONTROLLERS
    bridge._CONTROLLERS['mansion-key'] = c; bridge._BINDINGS.clear()
    review(call(env)); assert c.calls == 1


def test_reload_preserves_controller_baseline_pending_error_and_original_clock(env, monkeypatch):
    call(env); c = bridge._CONTROLLERS['mansion-key']; base, pending = c.baseline, c.pending
    bindings, completed = bridge._BINDINGS, bridge._COMPLETED
    c.waits = 21; c.started = 2.5; c.error = 'same_sticky_review'
    reload(bridge)
    monkeypatch.setattr(bridge.mansion_secret_key, 'MansionSecretKeyController', env.Controller)
    monkeypatch.setattr(bridge.mansion_secret_key, 'read_mansion_secret_key', env.reader)
    review(call(env))
    assert bridge._CONTROLLERS['mansion-key'] is c and c.baseline is base and c.pending is pending
    assert bridge._BINDINGS is bindings and bridge._COMPLETED is completed
    assert (c.calls, c.waits, c.started, c.error) == (2, 21, 2.5, 'same_sticky_review')
    assert bridge.applies('different-step', None)


def test_hidden_flag_or_new_location_without_complete_receipt_cannot_advance(env):
    call(env); c = bridge._CONTROLLERS['mansion-key']; env.signal['item_hidden'] = True
    assert call(env)[1] == 'mansion-key' and not bridge._COMPLETED
    env.state['location']['y'] = 13
    assert call(env)[1] == 'mansion-key' and not bridge._COMPLETED
    assert bridge._CONTROLLERS['mansion-key'] is c


def test_only_exact_complete_and_closed_source_receipt_advances_next_step(env):
    call(env); c = bridge._CONTROLLERS['mansion-key']; env.signal['item_hidden'] = True
    env.plan['steps'].append(dict(id='exit-mansion', kind='move'))
    c.done = 1
    assert call(env)[1] == 'mansion-key' and not bridge._COMPLETED
    c.done = True
    result, next_id = call(env)
    assert next_id == 'exit-mansion' and result['field_move_complete'] is True
    assert result['field_move_kind'] == 'mansion-secret-key' and bridge._COMPLETED == {'mansion-key'}


@pytest.mark.parametrize('change', ['hidden', 'closed', 'position', 'source'])
def test_complete_flag_never_bypasses_final_source_and_blank_world_guard(env, change):
    call(env); c = bridge._CONTROLLERS['mansion-key']; c.done = True; env.signal['item_hidden'] = True
    kwargs = {}
    if change == 'hidden': env.signal['item_hidden'] = False
    if change == 'closed': kwargs['ready'] = False
    if change == 'position': env.state['location']['x'] = 6
    if change == 'source': env.signal['read_valid'] = False
    review(call(env, **kwargs)); assert not bridge._COMPLETED


def test_other_alias_or_invalid_controller_result_cannot_skip(env, monkeypatch):
    call(env)
    monkeypatch.setattr(env.Controller, 'context', lambda *a, **kw:
        dict(field_move_complete=True, got_key=True, available_actions=['wait']))
    assert call(env)[1] == 'mansion-key' and not bridge._COMPLETED
    monkeypatch.setattr(env.Controller, 'context', lambda *a, **kw: None)
    review(call(env)); assert not bridge._COMPLETED


def test_removed_active_step_reviews_and_unrelated_unbound_step_is_ignored(env):
    env.step['mechanic'] = 'other'
    assert call(env) is None and not bridge.applies('mansion-key', env.step)
    env.step['mechanic'] = 'mansion_secret_key'; assert bridge.applies('mansion-key', env.step)
    call(env); env.plan['steps'] = []
    review(call(env)); assert bridge._CONTROLLERS['mansion-key'].calls == 1
