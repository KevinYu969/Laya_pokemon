"""橋接只測假getter/純controller；不啟動遊戲，不改主流程接線。"""
from copy import deepcopy
from importlib import reload
from types import SimpleNamespace

import pytest

from laya_pokemon import pallet_surf_bridge as bridge


@pytest.fixture
def env(monkeypatch):
    for name, value in (('_CONTROLLERS', {}), ('_BINDINGS', {}), ('_COMPLETED', set())):
        monkeypatch.setattr(bridge, name, value)
    from laya_pokemon import campaign_transactions as tx
    monkeypatch.setattr(tx, 'verified_blank_transaction_world', lambda t, g: t.get('ready') is True)
    monkeypatch.setattr(tx, 'ui_overworld_ready', lambda t, g: t.get('ready') is True)
    class Controller:
        def __init__(self, intent):
            self.intent = deepcopy(intent); self.baseline = {'original': True}
            self.pending = {'original': True}; self.calls = self.waits = 0
            self.started = 4.0; self.done = False; self.args = None
        def context(self, text, progress, **kwargs):
            self.args = kwargs; self.text = text; self.progress = progress; self.calls += 1
            return dict(phase='pallet_surf_menu', objective='Wait.', available_actions=['wait'],
                        surf_entry_complete=self.done)
    monkeypatch.setattr(bridge.pallet_surf, 'PalletSurfController', Controller)
    signal = dict(read_valid=True, mode=0, location=dict(bridge.pallet_surf.START))
    movement = dict(read_valid=True)
    reads = []
    def reader(game, frame, constants):
        reads.append(('signal', game, frame))
        return deepcopy(signal)
    def movement_reader(game, *, observation_frame):
        reads.append(('movement', game, observation_frame))
        return deepcopy(movement)
    monkeypatch.setattr(bridge.pallet_surf, 'read_surf_observation', reader)
    monkeypatch.setattr(bridge, 'read_rocket_movement', movement_reader)
    monkeypatch.setattr(bridge.time, 'monotonic', lambda: 10.0)
    step = dict(id='surf-pallet', kind='interact', mechanic='pallet_surf', map_id=0,
                target=[4, 13], surf_intent=deepcopy(bridge.pallet_surf.PALLET_SURF_INTENT))
    state = dict(frame=100, location=dict(bridge.pallet_surf.START), progress={'full': 'progress'},
                 battle_state=dict(kind='none'))
    return SimpleNamespace(plan=dict(training_job='mainline-water', steps=[step]), step=step,
        state=state, signal=signal, movement=movement, reads=reads, fake=SimpleNamespace(),
        Controller=Controller, reader=reader, movement_reader=movement_reader)


def call(e, *, step_id='surf-pallet', ready=True, previous=None):
    return bridge.context(e.fake, e.state, e.plan, step_id, {'ready': ready, 'full': 'text'},
                          {'full': 'grid'}, ['wait'] if previous is None else previous)


def review(h):
    assert h[0]['phase'] == 'campaign_review' and h[0]['available_actions'] == ['wait']
    assert h[1] == 'surf-pallet'


def test_full_text_progress_actual_previous_and_same_frame_readers_are_forwarded(env):
    previous = ['down', 'start', 'a', 'wait']
    call(env, previous=previous)
    c = bridge._CONTROLLERS['surf-pallet']
    assert c.args['previous'] is previous and c.args['frame'] == 100
    assert c.args['now'] == 10 and c.args['overworld_ready'] is True
    assert c.text == {'ready': True, 'full': 'text'} and c.progress is env.state['progress']
    assert c.args['grid'] == {'full': 'grid'}
    assert env.reads == [('signal', env.fake, 100), ('movement', env.fake, 100)]


def test_original_owner_baseline_pending_and_budget_remain_until_verified_water_landing(env):
    call(env); c = bridge._CONTROLLERS['surf-pallet']; base, pending = c.baseline, c.pending
    c.waits = 9; c.started = 5.5
    env.state.update(frame=140, location=dict(bridge.pallet_surf.LANDING))
    env.signal.update(mode=2, location=dict(bridge.pallet_surf.LANDING))
    assert call(env, ready=False)[1] == 'surf-pallet'
    assert bridge._CONTROLLERS['surf-pallet'] is c and c.baseline is base and c.pending is pending
    assert c.waits == 9 and c.started == 5.5 and not bridge._COMPLETED
    env.plan['steps'].append(dict(id='water-route', kind='move'))
    c.done = True
    result, next_id = call(env)
    assert next_id == 'water-route' and result['field_move_complete']
    assert result['field_move_kind'] == 'pallet-surf' and bridge._COMPLETED == {'surf-pallet'}


@pytest.mark.parametrize('key,value', [('next_map', 32), ('terminal', True), ('event', 'anything'),
    ('item', 198), ('badge', 16), ('await_script_event', True), ('kind', 'move'), ('map_id', False),
    ('target', [4, 14]), ('target', [4.0, 13]), ('face', 'up')])
def test_explicit_intent_rejects_generic_shortcuts_and_mistyped_geometry_before_binding(env, key, value):
    env.step[key] = value
    review(call(env)); assert not bridge._BINDINGS and not bridge._CONTROLLERS and not env.reads


@pytest.mark.parametrize('key,value', [('species', 132), ('move', 57.0), ('map_id', False),
                                     ('facing', 'up'), ('kind', 'other')])
def test_changed_or_mistyped_surf_intent_is_not_accepted(env, key, value):
    env.step['surf_intent'][key] = value
    review(call(env)); assert not bridge._BINDINGS


def test_unknown_initial_world_signal_or_movement_never_creates_controller(env):
    review(call(env, ready=False)); assert not bridge._BINDINGS
    env.signal['read_valid'] = False
    review(call(env)); assert not bridge._BINDINGS
    env.signal['read_valid'] = True; env.movement['read_valid'] = False
    review(call(env)); assert not bridge._BINDINGS


def test_new_transaction_cannot_start_at_landing_or_changed_map_and_claim_completion(env):
    env.state['location'] = dict(bridge.pallet_surf.LANDING)
    assert call(env) is None and not bridge._BINDINGS
    env.state['location'] = dict(map_id=32, x=4, y=0)
    assert call(env) is None and not bridge._BINDINGS


@pytest.mark.parametrize('loc,mode', [(dict(map_id=32,x=4,y=0), 2),
    (dict(map_id=0,x=4,y=13), 2), (dict(map_id=0,x=4,y=14), 0)])
def test_changed_map_or_mode_cannot_steal_completion_even_with_erroneous_controller_flag(env, loc, mode):
    call(env); c = bridge._CONTROLLERS['surf-pallet']; c.done = True
    env.state['location'] = deepcopy(loc); env.signal.update(location=deepcopy(loc), mode=mode)
    review(call(env)); assert not bridge._COMPLETED and bridge._CONTROLLERS['surf-pallet'] is c


def test_active_owner_step_job_or_mechanic_cannot_be_changed(env):
    call(env); c = bridge._CONTROLLERS['surf-pallet']
    assert call(env, step_id='other')[0]['review_reason'] == 'pallet_surf_owner_changed'
    env.plan['training_job'] = 'new-journey'
    review(call(env)); assert bridge._CONTROLLERS['surf-pallet'] is c
    env.plan['training_job'] = 'mainline-water'; env.step.pop('mechanic')
    review(call(env)); assert c.calls == 1


def test_resume_revision_does_not_replace_original_controller_or_budget(env):
    call(env); c = bridge._CONTROLLERS['surf-pallet']; c.waits = 12
    env.step['reviewed_revision'] = 2; env.plan['resume_revision'] = 3
    call(env)
    assert bridge._CONTROLLERS['surf-pallet'] is c and c.waits == 12 and c.calls == 2


def test_reload_preserves_controller_binding_completion_and_original_baseline(env, monkeypatch):
    call(env); c = bridge._CONTROLLERS['surf-pallet']; binding = bridge._BINDINGS['surf-pallet']
    c.waits = 8; base = c.baseline; c.pending = {'actual': 'preserved'}
    reload(bridge)
    # reload也更新純controller class；此測試保留假class，不冒充真遊戲。
    monkeypatch.setattr(bridge.pallet_surf, 'PalletSurfController', env.Controller)
    monkeypatch.setattr(bridge.pallet_surf, 'read_surf_observation', env.reader)
    monkeypatch.setattr(bridge, 'read_rocket_movement', env.movement_reader)
    call(env)
    assert bridge._CONTROLLERS['surf-pallet'] is c and c.baseline is base
    assert c.waits == 8 and c.pending == {'actual': 'preserved'}
    assert bridge._BINDINGS['surf-pallet'] == binding
    assert bridge.applies('other', None)
    completed = bridge._COMPLETED
    completed.add('surf-pallet')
    reload(bridge)
    assert bridge._COMPLETED is completed and bridge._COMPLETED == {'surf-pallet'}
    assert bridge._CONTROLLERS['surf-pallet'] is c


def test_lost_original_controller_is_not_silently_recreated(env):
    call(env); bridge._CONTROLLERS.pop('surf-pallet')
    review(call(env)); assert not bridge._CONTROLLERS


def test_lost_original_binding_is_not_silently_reconstructed(env):
    call(env); bridge._BINDINGS.clear()
    review(call(env)); assert bridge._CONTROLLERS['surf-pallet'].calls == 1


def test_duplicate_step_ids_review_instead_of_selecting_arbitrary_owner(env):
    env.plan['steps'].append(deepcopy(env.step))
    review(call(env)); assert not bridge._BINDINGS


def test_unrelated_step_does_not_take_over_and_applies_is_explicit(env):
    env.step['mechanic'] = 'unrelated'
    assert call(env) is None
    assert not bridge.applies('surf-pallet', env.step)
    assert bridge.applies('surf-pallet', dict(mechanic='pallet_surf'))


def test_only_exact_surf_entry_flag_completes_not_other_field_alias(env, monkeypatch):
    call(env); c = bridge._CONTROLLERS['surf-pallet']
    monkeypatch.setattr(env.Controller, 'context', lambda self,*a,**k:
                        dict(pallet_surf_complete=True, field_move_complete=True, available_actions=['wait']))
    env.state['location'] = dict(bridge.pallet_surf.LANDING)
    env.signal.update(mode=2, location=dict(bridge.pallet_surf.LANDING))
    assert call(env)[1] == 'surf-pallet' and not bridge._COMPLETED

