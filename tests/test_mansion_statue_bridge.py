"""洋館雕像橋接的假getter／純控制器測試；不建立模擬器或操作實況。"""
from copy import deepcopy
from importlib import reload
from types import SimpleNamespace

import pytest

from laya_pokemon import mansion_statue_bridge as bridge


@pytest.fixture
def env(monkeypatch):
    for name, value in (('_CONTROLLERS', {}), ('_BINDINGS', {}), ('_COMPLETED', set())):
        monkeypatch.setattr(bridge, name, value)
    from laya_pokemon import campaign_transactions as tx
    monkeypatch.setattr(tx, 'verified_blank_transaction_world', lambda t, g: t.get('ready') is True)
    monkeypatch.setattr(tx, 'ui_overworld_ready', lambda t, g: t.get('ready') is True)
    real_controller = bridge.mansion_statue.MansionStatueController

    class Controller:
        def __init__(self, intent):
            assert bridge.mansion_statue._intent(intent), '假controller也必須符合真實意圖契約'
            self.intent = deepcopy(intent); self.baseline = {'original': 'six-party-bag-money'}
            self.pending = {'actual_frame': 90}; self.calls = 0; self.waits = 9
            self.started = 4.; self.last_now = 5.; self.done = False
        def context(self, text, progress, **kwargs):
            self.text = text; self.progress = progress; self.args = kwargs; self.calls += 1
            return dict(phase='overworld', objective='Wait.', available_actions=['wait'],
                        mansion_statue_complete=self.done)

    monkeypatch.setattr(bridge.mansion_statue, 'MansionStatueController', Controller)
    signal = dict(read_valid=True, observation_frame=100, switch_on=False)
    reads = []
    def reader(game, frame, constants):
        reads.append((game, frame)); return deepcopy(signal)
    monkeypatch.setattr(bridge.mansion_statue, 'read_mansion_statue', reader)
    monkeypatch.setattr(bridge.time, 'monotonic', lambda: 10.)
    intent = dict(kind='mansion_statue', map_id=215, player_x=10, player_y=6,
                  source_before=False, source_after=True)
    step = dict(id='statue-1f', kind='interact', mechanic='mansion_statue', map_id=215,
                target=[10, 6], statue_intent=intent)
    state = dict(frame=100, location=dict(map_id=215, x=10, y=6),
                 progress={'original': 'progress'}, battle_state={'kind': 'none'})
    return SimpleNamespace(plan=dict(training_job='mansion-mainline', steps=[step]), step=step,
        state=state, signal=signal, reads=reads, game=SimpleNamespace(), Controller=Controller,
        RealController=real_controller, reader=reader)


def call(e, *, step_id='statue-1f', ready=True, previous=None, text=None, grid=None):
    return bridge.context(e.game, e.state, e.plan, step_id,
        {'ready': ready, 'original': 'full-text'} if text is None else text,
        {'original': 'grid'} if grid is None else grid, ['wait'] if previous is None else previous)


def review(result):
    assert result[0]['phase'] == 'campaign_review'
    assert result[0]['available_actions'] == ['wait'] and result[1] == 'statue-1f'


@pytest.mark.parametrize('mid,player', [(215, [10, 6]), (216, [18, 26]), (216, [20, 4])])
@pytest.mark.parametrize('before,after', [(False, True), (True, False)])
def test_only_the_three_fixed_source_positions_accept_either_typed_boolean_toggle(env, mid, player, before, after):
    env.step.update(map_id=mid, target=deepcopy(player))
    env.step['statue_intent'].update(map_id=mid, player_x=player[0], player_y=player[1],
                                     source_before=before, source_after=after)
    env.state['location'] = dict(map_id=mid, x=player[0], y=player[1])
    assert call(env)[1] == 'statue-1f'
    assert bridge._CONTROLLERS['statue-1f'].intent == env.step['statue_intent']
    assert bridge._BINDINGS and not bridge._COMPLETED


def test_full_text_progress_actual_previous_grid_and_frame_are_forwarded_without_mutating_inputs(env):
    text = {'ready': True, 'cells': [['native-cell']], 'other_full_metadata': 'retained'}
    grid = {'original': 'same-grid'}; previous = ['a', 'up', 'wait']
    before = deepcopy((env.state, env.plan, text, grid, previous))
    call(env, text=text, grid=grid, previous=previous)
    c = bridge._CONTROLLERS['statue-1f']
    assert c.text is text and c.progress is env.state['progress']
    assert c.args['previous'] is previous and c.args['grid'] is grid
    assert c.args['location'] is env.state['location'] and c.args['battle_state'] is env.state['battle_state']
    assert c.args['frame'] == 100 and c.args['now'] == 10. and c.args['overworld_ready'] is True
    assert c.args['signal'] == env.signal and env.reads == [(env.game, 100)]
    assert (env.state, env.plan, text, grid, previous) == before


@pytest.mark.parametrize('key,value', [('next_map', 216), ('terminal', True), ('event', 'secret_switch'),
    ('item', 43), ('badge', 64), ('await_script_event', True), ('kind', 'move'),
    ('map_id', 216), ('map_id', 215.), ('target', [10, 7]), ('target', [10., 6])])
def test_generic_completion_shortcuts_or_wrong_step_geometry_never_bind(env, key, value):
    env.step[key] = value
    review(call(env)); assert not bridge._CONTROLLERS and not bridge._BINDINGS and not env.reads


@pytest.mark.parametrize('changes', [dict(map_id=214), dict(player_y=7), dict(player_x=10.),
    dict(kind='other'), dict(source_before=0), dict(source_after=1),
    dict(source_before=True, source_after=True), dict(source_before=False, source_after=False),
    dict(extra='unapproved')])
def test_changed_source_location_unknown_intent_or_non_boolean_toggle_never_binds(env, changes):
    env.step['statue_intent'].update(changes)
    review(call(env)); assert not bridge._BINDINGS and not env.reads


@pytest.mark.parametrize('mid,x,y', [(215, 10, 6), (216, 18, 26), (216, 20, 4)])
def test_real_constructor_accepts_bridge_xy_intent_and_rejects_obsolete_player_list(env, mid, x, y):
    for before in (False, True):
        intent = dict(kind='mansion_statue', map_id=mid, player_x=x, player_y=y,
                      source_before=before, source_after=not before)
        controller = env.RealController(intent)
        assert controller.intent == intent and controller.binding == intent
        assert controller.calls == controller.waits == 0 and controller.baseline is None
        old = deepcopy(intent); old.pop('player_x'); old.pop('player_y'); old['player'] = [x, y]
        with pytest.raises(ValueError): env.RealController(old)
        with pytest.raises(AssertionError): env.Controller(old)


def test_unknown_initial_closed_world_or_source_signal_does_not_bind(env):
    review(call(env, ready=False)); assert not bridge._BINDINGS and not bridge._CONTROLLERS
    env.signal['read_valid'] = False
    review(call(env)); assert not bridge._BINDINGS and not bridge._CONTROLLERS
    env.signal['read_valid'] = 1
    review(call(env)); assert not bridge._BINDINGS and not bridge._CONTROLLERS


def test_unbound_different_position_delegates_navigation_without_creating_owner(env):
    env.state['location']['y'] = 7
    assert call(env) is None and not bridge._CONTROLLERS and not env.reads


def test_original_instance_baseline_pending_and_used_budget_survive_context_and_review_revision(env):
    call(env); c = bridge._CONTROLLERS['statue-1f']; base, pending = c.baseline, c.pending
    c.waits = 17; c.started = 1.25; c.last_now = 8.5
    env.plan['resume_revision'] = 6; env.step['reviewed_revision'] = 3; env.state['frame'] = 140
    call(env, ready=False)
    assert bridge._CONTROLLERS['statue-1f'] is c and c.baseline is base and c.pending is pending
    assert (c.calls, c.waits, c.started, c.last_now) == (2, 17, 1.25, 8.5)
    assert not bridge._COMPLETED


def test_owner_job_step_and_intent_changes_cannot_replace_original_controller(env):
    call(env); c = bridge._CONTROLLERS['statue-1f']
    assert call(env, step_id='statue-2f')[0]['review_reason'].endswith('owner_changed')
    env.plan['training_job'] = 'another-trip'; review(call(env))
    env.plan['training_job'] = 'mansion-mainline'
    env.step['statue_intent'].update(source_before=True, source_after=False); review(call(env))
    env.step['statue_intent'].update(source_before=False, source_after=True)
    env.step.pop('mechanic'); review(call(env))
    assert bridge._CONTROLLERS['statue-1f'] is c and c.calls == 1


def test_missing_original_instance_or_binding_is_never_reconstructed(env):
    call(env); c = bridge._CONTROLLERS.pop('statue-1f')
    review(call(env)); assert not bridge._CONTROLLERS
    bridge._CONTROLLERS['statue-1f'] = c; bridge._BINDINGS.clear()
    review(call(env)); assert c.calls == 1


def test_reload_preserves_the_same_instance_registry_pending_baseline_and_used_budget(env, monkeypatch):
    call(env); c = bridge._CONTROLLERS['statue-1f']; base, pending = c.baseline, c.pending
    bindings, completed = bridge._BINDINGS, bridge._COMPLETED
    c.waits = 21; c.started = 2.5
    reload(bridge)
    monkeypatch.setattr(bridge.mansion_statue, 'MansionStatueController', env.Controller)
    monkeypatch.setattr(bridge.mansion_statue, 'read_mansion_statue', env.reader)
    call(env)
    assert bridge._CONTROLLERS['statue-1f'] is c and c.baseline is base and c.pending is pending
    assert bridge._BINDINGS is bindings and bridge._COMPLETED is completed
    assert (c.calls, c.waits, c.started) == (2, 21, 2.5) and bridge.applies('different-step', None)


def test_location_or_changed_source_flag_alone_cannot_claim_controller_completion(env):
    call(env); c = bridge._CONTROLLERS['statue-1f']
    env.signal['switch_on'] = True
    env.state['location'] = dict(map_id=216, x=20, y=4)
    assert call(env)[1] == 'statue-1f' and not bridge._COMPLETED
    assert bridge._CONTROLLERS['statue-1f'] is c


def test_only_exact_controller_complete_receipt_advances_and_marks_field_move(env):
    call(env); c = bridge._CONTROLLERS['statue-1f']
    env.plan['steps'].append(dict(id='next-room', kind='move'))
    c.done = 1
    assert call(env)[1] == 'statue-1f' and not bridge._COMPLETED
    c.done = True
    result, next_id = call(env)
    assert next_id == 'next-room' and result['field_move_complete'] is True
    assert result['field_move_kind'] == 'mansion-statue' and bridge._COMPLETED == {'statue-1f'}


def test_other_completion_alias_cannot_skip_statue_transaction(env, monkeypatch):
    call(env)
    monkeypatch.setattr(env.Controller, 'context', lambda *a, **kw:
        dict(field_move_complete=True, secret_switch_changed=True, available_actions=['wait']))
    assert call(env)[1] == 'statue-1f' and not bridge._COMPLETED


def test_removed_active_step_is_reviewed_and_unrelated_unbound_step_is_ignored(env):
    env.step['mechanic'] = 'other'
    assert call(env) is None and not bridge.applies('statue-1f', env.step)
    env.step['mechanic'] = 'mansion_statue'
    assert bridge.applies('statue-1f', env.step)
    call(env); env.plan['steps'] = []
    review(call(env)); assert bridge._CONTROLLERS['statue-1f'].calls == 1
