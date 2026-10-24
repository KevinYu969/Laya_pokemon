"""真Lapras pure＋真raw getter的橋接合成測試；未建立模擬器。"""
from copy import deepcopy
import importlib
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

from laya_pokemon import lapras_bridge as bridge


_spec = spec_from_file_location('_lapras_source_fixtures', Path(__file__).with_name('test_lapras_gift.py'))
pure = module_from_spec(_spec)
_spec.loader.exec_module(pure)
REAL_FOREIGN_CHECK = bridge._foreign_owner_active


class Memory:
    def __init__(self):
        self.values = {}
        self.reads = []
        self.facing_reads = None
        self.hook = None

    def __getitem__(self, address):
        self.reads.append(address)
        if address == 0xC109 and self.facing_reads is not None:
            return next(self.facing_reads)
        if self.hook is not None:
            return self.hook(address, self.values[address], len(self.reads))
        return self.values[address]

    def __setitem__(self, *args):
        raise AssertionError('不得寫RAM')


class GetterOnly:
    def __init__(self):
        self.memory = Memory()
        self.frame_count = 0

    def __getattr__(self, name):
        raise AssertionError(f'不得操作模擬器：{name}')


class Harness:
    def __init__(self):
        self.fixture = pure.Session()
        self.frame = 0
        self.pyboy = GetterOnly()
        self.plan = {'steps': [dict(id='lapras', kind='interact', map_id=212, target=[2, 5],
                                   mechanic=bridge.MECHANIC,
                                   lapras_gift_intent=deepcopy(bridge.lapras_gift.INTENT)),
                               dict(id='after', kind='move', map_id=212, target=[3, 5])]}

    @property
    def controller(self):
        return bridge._CONTROLLERS['lapras']

    def sync(self):
        s = self.fixture.s
        values = {0xC109: 8, 0xD72E: s['raw_flags'], 0xD35E: 212,
                  0xD361: 5, 0xD362: 2, 0xD163: s['party_count']}
        species = s['party_species'] + [255]
        species += [0] * (7 - len(species))
        for start, raw in ((0xD164, species),
                (0xD16B, s['prefix_mons_raw'] + (s['new_mon_raw'] or [0] * 44)),
                (0xD273, s['prefix_ot_raw'] + (s['new_ot_raw'] or [0] * 11)),
                (0xD2B5, s['prefix_nicks_raw'] + (s['new_nickname_raw'] or [0] * 11))):
            values.update({start + i: byte for i, byte in enumerate(raw)})
        self.pyboy.memory.values = values
        self.pyboy.frame_count = self.frame

    def state(self):
        return dict(frame=self.frame, location=dict(map_id=212, x=2, y=5),
                    progress=self.fixture.p,
                    battle_state=dict(raw=0, kind='none', active=False, observation_frame=self.frame))

    def grid(self):
        visible = [[x, y] for y in range(4, 7) for x in range(5)]
        return dict(source=bridge.GRID_SOURCE, observation_frame=self.frame,
                    verified_location=[212, 2, 5], tiles=[[1] * 30 for _ in range(18)],
                    walkable=[[1] * 30 for _ in range(18)],
                    screen_cells_verified=15, visible_verified_cells=visible)

    def call(self, rows=None, *, ready=False, pre=False, step='lapras', text=None, grid=None):
        self.frame += 40
        self.sync()
        text = pure.packet(rows, window=not ready) if text is None else text
        if grid is None and ready:
            grid = self.grid()
        fn = bridge.pre_attrition_context if pre else bridge.context
        before = deepcopy((self.fixture.p, text, grid, self.pyboy.memory.values))
        result = fn(self.pyboy, self.state(), self.plan, step, text, grid)
        assert (self.fixture.p, text, grid, self.pyboy.memory.values) == before
        return result

    def intro_receipt(self):
        assert self.call(ready=True)[0]['available_actions'] == ['a', 'wait']
        for page in pure.INTRO:
            assert self.call(pure.cells(page, True))[0]['available_actions'] == ['a', 'wait']
        assert self.call(pure.cells(('KEVIN got', 'LAPRAS!')))[0]['available_actions'] == ['wait']

    def uninitialized_sixth(self):
        s = self.fixture.s
        s.update(party_count=6, party_species=s['party_species'] + [19], new_mon_raw=[0] * 44,
                 new_ot_raw=pure.native_name('KEVIN'), new_nickname_raw=[0] * 11)
        self.fixture.p.update(party_count=6, party_read_valid=False,
                              initialization_candidate=False, party=[])

    def at_no_transition(self):
        self.intro_receipt()
        self.uninitialized_sixth()
        assert self.call(pure.cells(pure.Q, True), pre=True)[0]['available_actions'] == ['a', 'wait']
        assert self.call(pure.cells(pure.N, cursor=8), pre=True)[0]['available_actions'] == ['down', 'wait']
        assert self.call(pure.cells(pure.N, cursor=10), pre=True)[0]['available_actions'] == ['a', 'wait']


@pytest.fixture
def env(monkeypatch):
    for name, value in (('_CONTROLLERS', {}), ('_BINDINGS', {}), ('_COMPLETED', set())):
        monkeypatch.setattr(bridge, name, value)
    monkeypatch.setattr(bridge, '_foreign_owner_active', lambda: False)
    return Harness()


def review(result):
    assert result[0]['phase'] == 'campaign_review' and result[0]['available_actions'] == ['wait']
    assert result[1] == 'lapras'


def test_real_getter_uninitialized_sixth_uses_original_controller_no_fabricated_progress(env):
    env.intro_receipt()
    c = env.controller
    original = deepcopy(c.baseline)
    env.uninitialized_sixth()
    out = env.call(pure.cells(pure.Q, True), pre=True)
    assert out[0]['available_actions'] == ['a', 'wait']
    assert out[0]['lapras_pre_attrition_transition'] is True and out[1] == 'lapras'
    assert env.controller is c and c.baseline == original and c.new_member is None
    assert env.fixture.p['party_read_valid'] is False and env.fixture.p['party'] == []
    assert not bridge._COMPLETED
    assert env.call(pure.cells(pure.N, cursor=8), pre=True)[0]['available_actions'] == ['down', 'wait']
    assert env.call(pre=True)[0]['available_actions'] == ['wait']
    assert env.call(pure.cells(pure.N, cursor=8), pre=True)[0]['available_actions'] == ['wait']
    assert env.call(pure.cells(pure.N, cursor=10), pre=True)[0]['available_actions'] == ['a', 'wait']
    assert env.call(pre=True)[0]['available_actions'] == ['wait']
    assert c.no_issued and c.new_member is None and env.fixture.p['party'] == []


def test_full_six_returns_to_safety_then_only_two_closed_complete_route(env):
    env.at_no_transition()
    env.fixture.fill_new()
    c = env.controller
    calls = c.calls
    assert env.call(pure.cells(pure.DESC[0], True), pre=True) is None
    assert c.calls == calls and c.stage == 'post_no' and not bridge._COMPLETED
    for page in pure.DESC[:-1]:
        assert env.call(pure.cells(page, True))[0]['available_actions'] == ['a', 'wait']
    env.fixture.s.update(got_lapras=True, raw_flags=0xA9)
    assert env.call(pure.cells(pure.DESC[-1]))[0]['available_actions'] == ['wait']
    assert env.call(pure.cells(pure.DESC[-1]))[0]['available_actions'] == ['a', 'wait']
    first = env.call(ready=True)
    assert first[1] == 'lapras' and first[0]['available_actions'] == ['wait']
    final = env.call(ready=True)
    assert final[0]['lapras_gift_complete'] is True and final[1] == 'after'
    assert final[0]['available_actions'] == ['wait']


def test_prehook_unbound_unknown_party_never_reads_or_constructs(env):
    env.uninitialized_sixth()
    assert env.call(pre=True) is None
    assert not bridge._CONTROLLERS and not env.pyboy.memory.reads


@pytest.mark.parametrize('change', [
    lambda e: e.fixture.s['prefix_mons_raw'].__setitem__(2, 0),
    lambda e: e.fixture.s['prefix_ot_raw'].__setitem__(0, 0x81),
    lambda e: e.fixture.s['prefix_nicks_raw'].__setitem__(0, 0x81),
    lambda e: e.fixture.s['party_species'].reverse(),
    lambda e: e.fixture.s.update(raw_flags=0xAA),
    lambda e: e.fixture.s.update(new_ot_raw=pure.native_name('RED')),
    lambda e: e.fixture.p.update(money=39999),
    lambda e: e.fixture.p.update(player_name_raw='RED'),
    lambda e: e.fixture.p.update(badges_raw=63),
    lambda e: e.fixture.p['inventory'].reverse(),
    lambda e: e.fixture.p.update(party_count=True),
    lambda e: e.fixture.p.update(initialization_candidate=True),
])
def test_prehook_one_field_wrong_does_not_grant_unknown_party_bypass(env, change):
    env.intro_receipt(); env.uninitialized_sixth()
    c = env.controller; calls = c.calls; baseline = deepcopy(c.baseline)
    change(env)
    result = env.call(pure.cells(pure.Q, True), pre=True)
    assert result is None or result[0]['phase'] == 'campaign_review'
    assert c.calls == calls and c.baseline == baseline and not bridge._COMPLETED


@pytest.mark.parametrize('bad', ['unknown', 'wrong_species', 'inactive_cursor', 'wrong_stage', 'no_receipt'])
def test_unknown_native_page_or_stage_keeps_original_attrition_review(env, bad):
    env.intro_receipt(); env.uninitialized_sixth()
    rows = pure.cells(pure.Q, True)
    if bad == 'unknown': rows[0][0:3] = list('YES')
    elif bad == 'wrong_species': rows = pure.cells(('give a nickname', 'to EEVEE?'))
    elif bad == 'inactive_cursor':
        env.call(pure.cells(pure.Q, True), pre=True)
        rows = pure.cells(pure.N, cursor=8); rows[8][15] = '▷'
    elif bad == 'wrong_stage': env.controller.stage = 'intro'
    else: env.controller.receipt_seen = False
    calls = env.controller.calls
    assert env.call(rows, pre=True) is None
    assert env.controller.calls == calls


def test_initialized_raw_but_invalid_progress_is_not_allowed_as_askname_transition(env):
    env.at_no_transition(); env.fixture.fill_new()
    env.fixture.p.update(party_read_valid=False, initialization_candidate=False, party=[])
    calls = env.controller.calls
    assert env.call(pre=True) is None and env.controller.calls == calls


def test_complete_sixth_struct_with_unknown_nickname_is_not_uninitialized_struct(env):
    env.intro_receipt(); env.uninitialized_sixth(); env.fixture.fill_new()
    env.fixture.s['new_nickname_raw'] = [0] * 11
    env.fixture.p.update(party_read_valid=False, initialization_candidate=False, party=[])
    assert env.call(pure.cells(pure.Q, True), pre=True) is None


def test_raw_prefix_torn_read_keeps_original_attrition_review_and_baseline(env):
    env.intro_receipt(); env.uninitialized_sixth()
    calls = env.controller.calls; baseline = deepcopy(env.controller.baseline)
    env.pyboy.memory.reads.clear()
    env.pyboy.memory.hook = lambda address, value, count: (
        value ^ 1 if address == 0xD16D and count > 410 else value)
    assert env.call(pure.cells(pure.Q, True), pre=True) is None
    assert env.controller.calls == calls and env.controller.baseline == baseline


def test_prehook_cannot_advance_even_if_pure_unexpectedly_claims_completion(env, monkeypatch):
    env.intro_receipt(); env.uninitialized_sixth()
    monkeypatch.setattr(bridge.lapras_gift.LaprasGiftController, 'context', lambda *a, **k: dict(
        phase='lapras_gift_complete', available_actions=['wait'], lapras_gift_complete=True))
    result = env.call(pure.cells(pure.Q, True), pre=True)
    review(result)
    assert result[0]['review_reason'] == 'lapras_bridge_pre_attrition_cannot_complete'
    assert not bridge._COMPLETED


@pytest.mark.parametrize('bad', ['faint', 'low_hp', 'normal'])
def test_valid_six_never_uses_prehook_even_when_health_needs_review(env, bad):
    env.at_no_transition(); env.fixture.fill_new()
    if bad == 'faint': env.fixture.p['party'][0]['hp'] = 0
    elif bad == 'low_hp': env.fixture.p['party'][0]['hp'] = 1
    calls = env.controller.calls
    assert env.call(pre=True) is None and env.controller.calls == calls


@pytest.mark.parametrize('bad', ['front_low', 'front_exact_two_thirds', 'bench_faint'])
def test_initial_true_party_health_must_be_safe_before_binding(env, bad):
    index, hp = (1, 0) if bad == 'bench_faint' else (0, 1 if bad == 'front_low' else 112)
    mon = env.fixture.p['party'][index]
    mon['hp'] = hp
    env.fixture.s['prefix_mons_raw'][index * 44 + 1:index * 44 + 3] = list(hp.to_bytes(2, 'big'))
    result = env.call(ready=True)
    review(result)
    assert result[0]['review_reason'] == 'lapras_bridge_initial_health_unverified'
    assert not bridge._CONTROLLERS and not bridge._BINDINGS


def test_initial_health_record_uses_real_party_without_requiring_full_hp_for_everyone(env):
    for index, hp in ((0, 113), (2, 1)):
        env.fixture.p['party'][index]['hp'] = hp
        env.fixture.s['prefix_mons_raw'][index * 44 + 1:index * 44 + 3] = list(hp.to_bytes(2, 'big'))
    assert env.call(ready=True)[0]['available_actions'] == ['a', 'wait']
    assert env.controller.initial_health_verified is True
    assert env.controller.initial_health_party == env.controller.baseline['party']
    assert env.controller.initial_health_party is not env.fixture.p['party']


@pytest.mark.parametrize('bad', ['missing', 'fingerprint'])
def test_prehook_requires_original_verified_health_record(env, bad):
    env.intro_receipt(); env.uninitialized_sixth()
    if bad == 'missing': del env.controller.initial_health_verified
    else: env.controller.initial_health_party[0]['hp'] -= 1
    assert env.call(pure.cells(pure.Q, True), pre=True) is None


@pytest.mark.parametrize('mutation', ['delete_mechanic', 'change_intent', 'change_kind', 'owner'])
def test_bound_owner_and_intent_changes_explicitly_review(env, mutation):
    env.intro_receipt(); c = env.controller
    if mutation == 'delete_mechanic': env.plan['steps'][0].pop('mechanic')
    elif mutation == 'change_intent': env.plan['steps'][0]['lapras_gift_intent']['level'] = 16
    elif mutation == 'change_kind': env.plan['steps'][0]['kind'] = 'move'
    result = env.call(pre=True, step='after' if mutation == 'owner' else 'lapras')
    assert result[0]['phase'] == 'campaign_review' and result[0]['available_actions'] == ['wait']
    assert env.controller is c and bridge.applies('lapras', env.plan['steps'][0])


@pytest.mark.parametrize('pair', [(8.0, 8), (8, 8.0), (8, 12), (12, 12), (8, None)])
def test_both_raw_facing_reads_are_true_int_left_without_preturn_keys(env, pair):
    env.pyboy.memory.facing_reads = iter(pair)
    review(env.call(ready=True))
    assert not bridge._CONTROLLERS and not bridge._BINDINGS


@pytest.mark.parametrize('frames', [(40.0, 40), (40, 40.0), (40, True), (40, 41)])
def test_frame_reads_around_raw_facing_are_real_int_and_current(env, frames):
    env.frame = 40; env.sync()
    class Emulator:
        memory = env.pyboy.memory
        values = iter(frames)
        @property
        def frame_count(self): return next(self.values)
    result = bridge.context(Emulator(), env.state(), env.plan, 'lapras',
                            pure.packet(window=False), env.grid())
    review(result)
    assert not bridge._CONTROLLERS


def test_provided_stale_grid_during_dialogue_cannot_be_ignored_to_send_a(env):
    env.intro_receipt(); calls = env.controller.calls
    g = env.grid()
    review(env.call(pure.cells(pure.Q, True), grid=g))
    assert env.controller.calls == calls


def test_unbound_movement_passes_but_bound_location_change_reviews(env):
    env.frame = 40; env.sync(); state = env.state(); state['location']['x'] = 3
    assert bridge.context(env.pyboy, state, env.plan, 'lapras', pure.packet(window=False), env.grid()) is None
    assert not bridge._BINDINGS
    env.intro_receipt()
    state = env.state(); state['location']['x'] = 3
    review(bridge.pre_attrition_context(env.pyboy, state, env.plan, 'lapras', pure.packet(), None))


@pytest.mark.parametrize('bad', ['empty', 'stale', 'missing_npc', 'count', 'bool_tile'])
def test_initial_closed_world_cannot_use_arbitrary_grid(env, bad):
    env.frame = 0
    env.sync(); g = env.grid(); g['observation_frame'] = 40
    if bad == 'empty': g = {}
    elif bad == 'stale': g['observation_frame'] = 39
    elif bad == 'missing_npc':
        g['visible_verified_cells'].remove([1, 5]); g['screen_cells_verified'] -= 1
    elif bad == 'count': g['screen_cells_verified'] = True
    else: g['tiles'][0][0] = True
    review(env.call(ready=True, grid=g))
    assert not bridge._BINDINGS and not bridge._CONTROLLERS


def test_hot_reload_retains_real_owner_baseline_clock_calls_and_budget(env, monkeypatch):
    env.intro_receipt(); c = env.controller
    baseline, started, calls = c.baseline, c.started, c.calls
    bindings, controllers = bridge._BINDINGS, bridge._CONTROLLERS
    importlib.reload(bridge)
    monkeypatch.setattr(bridge, '_foreign_owner_active', lambda: False)
    assert bridge._BINDINGS is bindings and bridge._CONTROLLERS is controllers
    env.uninitialized_sixth()
    assert env.call(pure.cells(pure.Q, True), pre=True)[0]['available_actions'] == ['a', 'wait']
    assert env.controller is c and c.baseline is baseline and c.started == started and c.calls == calls + 1
    c.started -= 61
    importlib.reload(bridge)
    monkeypatch.setattr(bridge, '_foreign_owner_active', lambda: False)
    review(env.call(pure.cells(pure.N, cursor=8), pre=True))
    assert 'budget' in c.error and c.baseline is baseline


@pytest.mark.parametrize('family', ['card', 'capture', 'campaign', 'safari', 'run', 'hm', 'vending', 'guard'])
def test_foreign_transaction_owner_rejects_before_game_reads(env, monkeypatch, family):
    from laya_pokemon import (campaign_transactions as tx, capture_transaction as cap,
        safari_entry as safari, hm_teaching_bridge as hm, vending_bridge as vending,
        saffron_guard_bridge as guard, silph_card_bridge as card)
    monkeypatch.setattr(bridge, '_foreign_owner_active', REAL_FOREIGN_CHECK)
    for module in (tx, safari, hm, vending, guard, card):
        monkeypatch.setattr(module, '_BINDINGS', {})
        monkeypatch.setattr(module, '_COMPLETED', set())
    monkeypatch.setattr(safari, '_RUN_CONTROLLER', None)
    monkeypatch.setattr(cap, '_SESSIONS', {})
    if family == 'capture': monkeypatch.setattr(cap, '_SESSIONS', {'other': {'done': False}})
    elif family == 'run': monkeypatch.setattr(safari, '_RUN_CONTROLLER', object())
    else:
        module = {'card': card, 'campaign': tx, 'safari': safari, 'hm': hm,
                  'vending': vending, 'guard': guard}[family]
        monkeypatch.setattr(module, '_BINDINGS', {'other': ()})
    result = env.call(ready=True)
    review(result)
    assert result[0]['review_reason'] == 'lapras_bridge_other_transaction_active'
    assert not env.pyboy.memory.reads and not bridge._CONTROLLERS
