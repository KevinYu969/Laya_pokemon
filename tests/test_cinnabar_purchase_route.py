"""正式route的純購藥分派測試；不替換受測switch／field分支。"""
from copy import deepcopy
import importlib
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import laya_pokemon


ROOT = Path(laya_pokemon.__file__).resolve().parents[2]
STAGE = ROOT / '.local/staged-cinnabar-route-tests-20261024'


def formal_route_source(test_file):
    """只允許指定staged或正式tests安裝點，兩者都測正式route。"""
    here = Path(test_file).resolve()
    if here not in (STAGE / 'test_cinnabar_purchase_route.py',
                    ROOT / 'tests/test_cinnabar_purchase_route.py'):
        raise RuntimeError('not an approved cinnabar route test installation')
    return ROOT / 'src/laya_pokemon/campaign_route.py'


route = importlib.import_module('laya_pokemon.campaign_route')
assert Path(route.__file__).resolve() == formal_route_source(__file__)
PEERS = ('mansion_secret_key_bridge', 'mansion_statue_bridge', 'mansion_transition_ready',
         'mansion_native_landing', 'route21_water_bridge', 'pallet_surf_bridge',
         'fly_pallet_bridge', 'safari_entry', 'hm_teaching_bridge', 'vending_bridge',
         'saffron_guard_bridge', 'silph_card_bridge', 'lapras_bridge', 'player_pc_bridge',
         'campaign_transactions', 'battle_medicine_bridge', 'fly_viridian_bridge',
         'trainer_medicine_ui_bridge')


def forbidden(*args, **kwargs):
    raise AssertionError('blocked route must not read UI or call a transaction')


@pytest.fixture
def env(monkeypatch):
    bridge = route.cinnabar_purchase_bridge
    assert Path(bridge.__file__).resolve() == ROOT / 'src/laya_pokemon/cinnabar_purchase_bridge.py'
    for name in PEERS:
        module = getattr(route, name)
        monkeypatch.setattr(module, '_BINDINGS', {})
        monkeypatch.setattr(module, '_COMPLETED', set())
    monkeypatch.setattr(route.safari_entry, '_RUN_CONTROLLER', None)
    monkeypatch.setattr(route.capture_transaction, '_SESSIONS', {})
    monkeypatch.setattr(route.battle_medicine_bridge, '_CONTROLLERS', {})
    monkeypatch.setattr(route.trainer_medicine_ui_bridge, '_CONTROLLERS', {})
    monkeypatch.setattr(route, '_GYM_CONTROLLERS', {})
    for name, value in (('_CONTROLLER', {}), ('_BINDINGS', {}), ('_COMPLETED', set())):
        monkeypatch.setattr(bridge, name, value)
    intent = deepcopy(bridge.cinnabar_purchase.HYPER_POTION_INTENT)
    step = dict(id='medicine', kind='interact', mechanic='cinnabar_purchase', map_id=172,
                target=[2, 5], face='left', purchase_intent=intent)
    plan = dict(training_job='synthetic-medicine-job', steps=[step, dict(id='after', kind='move')])
    state = dict(frame=400, location=dict(map_id=172, x=2, y=5),
                 progress={'unaltered': 'six-party-progress'},
                 battle_state=dict(raw=0, active=False, kind='none', observation_frame=400))
    game = object(); text = {'cells': [['full-source-text']], 'observation_frame': 400}
    grid = {'sentinel': 'actual-grid'}; reads = []; calls = []
    from laya_pokemon import observation
    def read_text(emulator):
        reads.append(('text', emulator)); return text
    def read_grid(emulator, location):
        reads.append(('grid', emulator, location)); return grid
    result = (dict(phase='mart_menu', objective='Wait.', available_actions=['wait']), 'medicine')
    original_context = bridge.context
    def delegated(*args):
        calls.append(args); return result
    monkeypatch.setattr(observation, 'read_visible_text', read_text)
    monkeypatch.setattr(route, 'read_world_grid', read_grid)
    monkeypatch.setattr(bridge, 'context', delegated)
    return SimpleNamespace(bridge=bridge, step=step, plan=plan, state=state, game=game,
                           text=text, grid=grid, reads=reads, calls=calls,
                           result=result, original_context=original_context)


def review(result):
    value, step_id = result
    assert step_id == 'medicine' and value['phase'] == 'campaign_review'
    assert value['review_reason'] == 'cinnabar_purchase_other_transaction_active'
    assert value['available_actions'] == ['wait']


def test_loader_allows_only_exact_stage_or_formal_test_and_always_targets_formal_route():
    assert formal_route_source(STAGE / 'test_cinnabar_purchase_route.py') == Path(route.__file__).resolve()
    assert formal_route_source(ROOT / 'tests/test_cinnabar_purchase_route.py') == Path(route.__file__).resolve()
    with pytest.raises(RuntimeError): formal_route_source(ROOT / 'unknown/test_cinnabar_purchase_route.py')


def test_peer_fixture_covers_every_other_imported_binding_registry(env):
    actual = {name for name, module in vars(route).items()
              if isinstance(module, ModuleType) and module is not env.bridge
              and hasattr(module, '_BINDINGS') and hasattr(module, '_COMPLETED')}
    assert actual == set(PEERS) and len(actual) == 18


@pytest.mark.parametrize('name', PEERS)
def test_each_active_peer_blocks_before_ui_or_purchase_dispatch(env, monkeypatch, name):
    peer = getattr(route, name)
    peer._BINDINGS['existing-owner'] = {'retained': True}
    from laya_pokemon import observation
    monkeypatch.setattr(observation, 'read_visible_text', forbidden)
    monkeypatch.setattr(route, 'read_world_grid', forbidden)
    monkeypatch.setattr(env.bridge, 'context', forbidden)
    before = deepcopy(peer._BINDINGS)
    result=route.switch_context(env.game, env.state, env.plan, 'medicine', ['left', 'wait'])
    if name=='trainer_medicine_ui_bridge':
        assert result[0]['phase']=='campaign_review' and result[0]['available_actions']==['wait']
        assert result[0]['review_reason']=='trainer_medicine_owner_changed'
    elif name=='battle_medicine_bridge':
        assert result[0]['phase']=='campaign_review' and result[0]['available_actions']==['wait']
        assert result[0]['review_reason']=='blaine_supply_fixed_step_unverified'
    elif name=='fly_viridian_bridge':
        assert result[0]['phase']=='campaign_review' and result[0]['available_actions']==['wait']
        assert result[0]['review_reason']=='fly_viridian_owner_changed'
    else:
        review(result)
    assert peer._BINDINGS == before and not env.calls and not env.reads


def test_completed_peers_and_finished_capture_do_not_block_new_purchase(env):
    for name in PEERS:
        peer = getattr(route, name)
        peer._BINDINGS['old'] = ('original',)
        peer._COMPLETED.add('old')
    route.capture_transaction._SESSIONS['old-capture'] = {'done': True}
    assert route.switch_context(env.game, env.state, env.plan, 'medicine', ['wait']) is env.result
    assert len(env.calls) == 1


def test_active_safari_run_blocks_even_without_safari_binding(env):
    route.safari_entry._RUN_CONTROLLER = object()
    review(route.switch_context(env.game, env.state, env.plan, 'medicine', ['wait']))
    assert not env.calls and not env.reads


@pytest.mark.parametrize('capture', [{'done': False}, {}, {'done': None}])
def test_not_finished_capture_blocks_before_ui(env, capture):
    route.capture_transaction._SESSIONS['capture'] = deepcopy(capture)
    review(route.switch_context(env.game, env.state, env.plan, 'medicine', ['wait']))
    assert not env.calls and not env.reads


@pytest.mark.parametrize('previous', [[], ['a', 'left', 'wait'], ('down', 'a')])
def test_switch_passes_exact_previous_full_text_grid_and_original_objects_once(env, previous):
    before = deepcopy((env.state, env.plan, env.text, env.grid, previous))
    result = route.switch_context(env.game, env.state, env.plan, 'medicine', previous)
    assert result is env.result
    assert len(env.calls) == 1
    args = env.calls[0]
    assert args[0] is env.game and args[1] is env.state and args[2] is env.plan
    assert args[3] == 'medicine' and args[4] is env.text and args[5] is env.grid and args[6] is previous
    assert env.reads == [('text', env.game), ('grid', env.game, env.state['location'])]
    assert (env.state, env.plan, env.text, env.grid, previous) == before


def test_field_defers_before_any_generic_or_peer_transaction_even_when_peer_is_active(env, monkeypatch):
    route.mansion_secret_key_bridge._BINDINGS['other'] = ('still-active',)
    monkeypatch.setattr(route.mansion_secret_key_bridge, 'applies', forbidden)
    from laya_pokemon import observation
    monkeypatch.setattr(observation, 'read_visible_text', forbidden)
    monkeypatch.setattr(route, 'read_world_grid', forbidden)
    assert route.field_context(env.game, env.state, env.plan, 'medicine') is None
    review(route.switch_context(env.game, env.state, env.plan, 'medicine', ['wait']))
    assert not env.calls and not env.reads


def test_retained_purchase_owner_still_bypasses_field_after_step_mechanic_removed(env, monkeypatch):
    env.bridge._BINDINGS['medicine'] = ('original-bound-intent',)
    env.step.pop('mechanic')
    assert route.field_context(env.game, env.state, env.plan, 'medicine') is None
    # 真bridge的owner／intent防守，不用spy假造成功結果。
    monkeypatch.setattr(env.bridge, 'context', env.original_context)
    result = route.switch_context(env.game, env.state, env.plan, 'medicine', ['wait'])
    assert result[0]['review_reason'] == 'cinnabar_purchase_bridge_intent_changed'
    assert result[0]['available_actions'] == ['wait'] and result[1] == 'medicine'


def test_different_active_purchase_owner_cannot_fall_back_to_generic_or_new_controller(env, monkeypatch):
    env.bridge._BINDINGS['original'] = ('same-original-owner',)
    monkeypatch.setattr(env.bridge, 'context', env.original_context)
    assert route.field_context(env.game, env.state, env.plan, 'medicine') is None
    result = route.switch_context(env.game, env.state, env.plan, 'medicine', ['a'])
    assert result[0]['review_reason'] == 'cinnabar_purchase_bridge_owner_changed'
    assert result[0]['available_actions'] == ['wait'] and not env.bridge._CONTROLLER


def test_unrelated_move_without_purchase_owner_is_not_claimed(env):
    env.step.pop('mechanic'); env.step['kind'] = 'move'
    assert route.switch_context(env.game, env.state, env.plan, 'medicine', ['wait']) is None
    assert not env.calls and not env.reads


def test_actual_route_reload_retains_real_purchase_controller_baseline_pending_and_budget(env):
    bridge = env.bridge
    controller = bridge.cinnabar_purchase.CinnabarPurchaseController(env.step['purchase_intent'])
    controller.baseline = {'original-six-party-bag-money': True}
    controller.pending = {'action': 'a', 'frame': 360, 'rows': ('original-source',)}
    controller.calls = 21; controller.waits = 17; controller.started = 3.5
    controller.last_now = 9.25; controller.error = 'existing_sticky_error'
    bridge._CONTROLLER['medicine'] = controller
    bridge._BINDINGS['medicine'] = ('retained-binding',)
    original_registry = bridge._CONTROLLER; original_bindings = bridge._BINDINGS
    original_completed = bridge._COMPLETED
    baseline, pending = controller.baseline, controller.pending
    original_values = deepcopy(vars(controller))
    importlib.reload(route)  # 真import/reload分支，沒有mock受測熱載入。
    assert route.cinnabar_purchase_bridge is bridge
    assert bridge._CONTROLLER is original_registry and bridge._CONTROLLER['medicine'] is controller
    assert bridge._BINDINGS is original_bindings and bridge._COMPLETED is original_completed
    assert controller.baseline is baseline and controller.pending is pending
    assert vars(controller) == original_values
    assert bridge.applies('other-step', None) is True
