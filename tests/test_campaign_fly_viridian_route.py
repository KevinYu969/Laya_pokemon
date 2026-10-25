"""Fly接線的互斥與真previous傳遞；遊戲交易本身由真pure整合測試驗證。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from laya_pokemon import campaign_route as route
from laya_pokemon.fly_viridian import FLY_VIRIDIAN_INTENT

PEERS = ('battle_medicine_bridge', 'mansion_secret_key_bridge', 'mansion_statue_bridge',
         'mansion_transition_ready', 'mansion_native_landing', 'route21_water_bridge',
         'pallet_surf_bridge', 'fly_pallet_bridge', 'safari_entry', 'hm_teaching_bridge',
         'vending_bridge', 'saffron_guard_bridge', 'silph_card_bridge', 'lapras_bridge',
         'player_pc_bridge', 'cinnabar_purchase_bridge', 'campaign_transactions')


@pytest.fixture
def env(monkeypatch):
    for name in (*PEERS, 'fly_viridian_bridge'):
        module = getattr(route, name)
        for key, value in (('_BINDINGS', {}), ('_CONTROLLERS', {}), ('_COMPLETED', set())):
            if hasattr(module, key): monkeypatch.setattr(module, key, value)
    monkeypatch.setattr(route.safari_entry, '_RUN_CONTROLLER', None)
    monkeypatch.setattr(route.capture_transaction, '_SESSIONS', {})
    step = dict(id='fly-viridian-route', kind='interact', mechanic='fly_viridian',
                map_id=8, target=[18, 4], fly_intent=deepcopy(FLY_VIRIDIAN_INTENT))
    return SimpleNamespace(step=step, plan=dict(steps=[step], training_job='source-flight'),
        state=dict(frame=100, location=dict(map_id=8, x=18, y=4)), pb=object())


@pytest.mark.parametrize('peer', PEERS)
def test_all_existing_transaction_owners_block_fly_before_any_ui_read(env, monkeypatch, peer):
    getattr(route, peer)._BINDINGS['other'] = object()
    def forbidden(*args, **kwargs): raise AssertionError('must stop before UI/dispatch')
    monkeypatch.setattr(route.fly_viridian_bridge, 'context', forbidden)
    result, step_id = route.switch_context(env.pb, env.state, env.plan, env.step['id'], ['up'])
    assert result['review_reason'] == 'fly_viridian_other_transaction_active'
    assert result['available_actions'] == ['wait'] and step_id == env.step['id']


@pytest.mark.parametrize('other', ['capture', 'safari_run'])
def test_independent_running_transactions_also_block_fly(env, monkeypatch, other):
    if other == 'capture': route.capture_transaction._SESSIONS['other'] = dict(done=False)
    else: monkeypatch.setattr(route.safari_entry, '_RUN_CONTROLLER', object())
    result, _ = route.switch_context(env.pb, env.state, env.plan, env.step['id'], [])
    assert result['review_reason'] == 'fly_viridian_other_transaction_active'


def test_field_defers_and_switch_transmits_original_observations_and_previous(env, monkeypatch):
    import laya_pokemon.observation as observation
    text, grid, previous = object(), object(), ['up', 'wait', 'a']
    monkeypatch.setattr(observation, 'read_visible_text', lambda pb: text)
    monkeypatch.setattr(route, 'read_world_grid', lambda pb, loc: grid)
    seen = []
    def capture(*args):
        seen.append(args)
        return dict(phase='fly_viridian_menu', objective='Wait.', available_actions=['wait']), args[3]
    monkeypatch.setattr(route.fly_viridian_bridge, 'context', capture)
    assert route.field_context(env.pb, env.state, env.plan, env.step['id']) is None
    assert not seen
    route.switch_context(env.pb, env.state, env.plan, env.step['id'], previous)
    assert seen == [(env.pb, env.state, env.plan, env.step['id'], text, grid, previous)]
    assert seen[0][-1] is previous


def test_active_fly_owner_catches_foreign_step_before_old_branch(env, monkeypatch):
    route.fly_viridian_bridge._BINDINGS[env.step['id']] = object()
    foreign = dict(id='foreign-medicine', kind='interact', map_id=166, target=[3,4],
                   face='up', event='beat_blaine', battle_supply=route.battle_medicine_bridge.SUPPLY)
    env.plan['steps'].append(foreign)
    import laya_pokemon.observation as observation
    monkeypatch.setattr(observation, 'read_visible_text', lambda pb: {})
    monkeypatch.setattr(route, 'read_world_grid', lambda pb, loc: {})
    def forbidden(*args, **kwargs): raise AssertionError('foreign medicine must never run')
    monkeypatch.setattr(route.blaine_supply_dispatch, 'context', forbidden)
    assert route.field_context(env.pb, env.state, env.plan, foreign['id']) is None
    result, step_id = route.switch_context(env.pb, env.state, env.plan, foreign['id'], [])
    assert result['review_reason'] == 'fly_viridian_owner_changed' and step_id == foreign['id']
