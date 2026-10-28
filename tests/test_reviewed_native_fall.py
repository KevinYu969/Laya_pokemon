"""Real SDK/progress/getters and completed native owner; synthetic memory only."""
from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / 'src/laya_pokemon'
gate = importlib.import_module('laya_pokemon.reviewed_native_fall')
shared = importlib.import_module('laya_pokemon.owned_field_medicine')
layout = importlib.import_module('laya_pokemon.reviewed_hole_layout')
recovery = importlib.import_module('laya_pokemon.league_recovery')
progress_module = importlib.import_module('laya_pokemon.progress')
for module, filename in ((gate, 'reviewed_native_fall.py'), (shared, 'owned_field_medicine.py'),
                         (layout, 'reviewed_hole_layout.py'), (recovery, 'league_recovery.py')):
    assert Path(module.__file__).resolve() == (SOURCE / filename).resolve()


def load_bridge():
    path = (SOURCE / 'victory_later_boulders_bridge.py').resolve(strict=True)
    spec = importlib.util.spec_from_file_location('laya_pokemon._native_fall_formal_test_bridge', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert Path(module.__file__).resolve() == path
    return module


bridge = load_bridge()
bh = importlib.import_module('test_victory_later_boulders')
hh = importlib.import_module('test_overworld_hyper')
for module, filename in ((bh, 'test_victory_later_boulders.py'), (hh, 'test_overworld_hyper.py')):
    assert Path(module.__file__).resolve() == (ROOT / 'tests' / filename).resolve()
REAL_PROGRESS_AUTHORITY = gate.SOURCE_PROGRESS_SHA256


def synthetic_samples():
    """Artificial source fixture: no outputs, game state, saved proof, or emulator."""
    game = hh.Game()
    game.memory.update(bh.Memory('3f_hole').values)
    p = bh.progress()
    for mon in p['party']:
        mon.update(hp=mon['max_hp'], status=0)
    next(mon for mon in p['party'] if mon['species'] == 7)['hp'] = 0
    game.game_wrapper = SimpleNamespace(party=p['party'], inventory=p['inventory'], money=p['money'])
    game.memory.update({0xD356: 255, sdk.PARTY_COUNT_ADDRESS: 6,
        sdk.PLAYER_MONEY_ADDRESS: 0x05, sdk.PLAYER_MONEY_ADDRESS+1: 0x43,
        sdk.PLAYER_MONEY_ADDRESS+2: 0x21, 0xD813: 69, 0xD7EE: 5,
        0xD72D: 16, 0xD732: 21, 0xD71D: 194, 0xD71E: 2,
        0xD362: 23, 0xD361: 15, 0xD5B2: 0, 0xD5B5: 4,
        0xC200+16*8+4: 17, 0xC200+16*10+5: 27, 0xFF40: 0x91})
    enc = {v: k for k, v in sdk.POKEMON_TEXT_DECODING.items() if type(k) is int and 0 <= k <= 255}
    for i, ch in enumerate('KEVIN'):
        game.memory[sdk.PLAYER_NAME_ADDRESS+i] = enc[ch]
    game.memory[sdk.PLAYER_NAME_ADDRESS+5] = 0x50
    progress = progress_module.read_progress(game, sdk)
    source = bridge.boulder.read_later_boulder_observation(game, game.frame_count, sdk, case_key='3f_hole')
    assert source['read_valid']
    normal_text = hh.read_visible_text(game)
    samples, phases = [], []
    for t in (1, 2, 8, 16, 24, 32, 48, 64, 96, 128, 160, 192, 240):
        raw = deepcopy(source['raw'])
        location = deepcopy(gate.LOCATION if t <= 2 else gate.LANDING)
        raw.update(map_id=location['map_id'], x=location['x'], y=location['y'])
        if t > 2:
            raw.update(flags3=0, flags6=21 if t < 32 else 17 if t < 48 else 1,
                       tileset=0 if t < 32 else 17, object_count=10 if t < 32 else 13,
                       flags1=65 if t < 48 else 64, joy_ignore=255 if 32 <= t < 128 else 0)
        text = deepcopy(normal_text)
        if t == 32:
            text.update(cells=[], read_valid=False, alignment_verified=False,
                        window_visible=None, read_error='visible_display_disabled')
        grid = bh.grid('2f_switch2', t, (22, 16), bh.Memory('2f_switch2').values) if t >= 160 else None
        samples.append(dict(t=t, location=location, progress=deepcopy(progress),
                            boulder=deepcopy(source), raw={}))
        phases.append(dict(t=t, phase='overworld', text=text, grid=grid, signal=dict(raw=raw)))
    return samples, phases


SAMPLES, PHASES = synthetic_samples()


@pytest.fixture(autouse=True)
def clear(monkeypatch):
    monkeypatch.setattr(gate, 'SOURCE_PROGRESS_SHA256', shared.canonical_sha256(SAMPLES[0]['progress']))
    for module, values in ((bridge, {'_CONTROLLERS': {}, '_BINDINGS': {}, '_COMPLETED': set()}),
                           (shared, {'_SESSIONS': {}, '_ERRORS': {}, '_REGISTRY_ERROR': None}),
                           (gate, {'_SESSIONS': {}, '_ERRORS': {}})):
        for name, value in values.items():
            monkeypatch.setattr(module, name, value)


def plan():
    steps = recovery.expected_steps()
    return dict(mode='league_campaign', training_job=recovery.JOB, lead_species=35, steps=steps,
                reviewed_fnt_recovery=dict(kind=recovery.KIND, source_frame=32809,
                    source_location=dict(map_id=198, x=6, y=1), fainted_species=7,
                    steps_sha256=recovery.digest(steps), review_sha256=recovery.SOURCE_REVIEW_SHA256,
                    state_sha256=recovery.SOURCE_STATE_SHA256))


class Session:
    def __init__(self):
        self.game = hh.Game()
        self.plan = plan()
        self.original_plan = deepcopy(self.plan)
        p = deepcopy(SAMPLES[0]['progress'])
        self.game.game_wrapper = SimpleNamespace(party=p['party'], inventory=p['inventory'], money=p['money'])
        self.game.memory.update(bh.Memory('3f_hole').values)
        # Build synthetic RAM for the literal diagnostic packet through the real
        # SDK read_progress, without substituting a progress getter.
        for name, value in p['story_event_bits'].items():
            event = sdk.EVENT_FLAGS.get(progress_module.EVENT_FLAG_ALIASES.get(name, name))
            if type(event) is int:
                address, mask = sdk.EVENT_FLAGS_ADDRESS + event // 8, 1 << (event % 8)
                self.game.memory[address] = ((self.game.memory[address] | mask) if value
                                            else (self.game.memory[address] & ~mask))
        self.game.memory.update({0xD356: 255, sdk.PARTY_COUNT_ADDRESS: 6})
        digits = f"{p['money']:06d}"
        for i in range(3):
            self.game.memory[sdk.PLAYER_MONEY_ADDRESS + i] = int(digits[2*i:2*i+2], 16)
        enc = {v: k for k, v in sdk.POKEMON_TEXT_DECODING.items() if type(k) is int and 0 <= k <= 255}
        for i, ch in enumerate('KEVIN'):
            self.game.memory[sdk.PLAYER_NAME_ADDRESS + i] = enc[ch]
        self.game.memory[sdk.PLAYER_NAME_ADDRESS + 5] = 0x50
        raw = SAMPLES[0]['boulder']
        for i, value in enumerate(raw['toggle_flags']):
            self.game.memory[0xD5A6 + i] = value
        self.game.memory[0xD5B2] |= 1  # before actual native stone fall
        self.game.memory[0xD5B5] &= ~4
        for o in raw['objects']:
            s = o['slot']; a, b = 0xC100+16*s, 0xC200+16*s
            self.game.memory.update({a: o['picture'], a+1: o['status'], b: o['walk_counter'],
                b+4: o['y']+4, b+5: o['x']+4, b+6: o['movement_byte1'], b+13: o['picture2'],
                0xD4E4+2*(s-1): o['movement_byte2'], 0xD4E5+2*(s-1): o['text']})
        self.game.memory.update({0xD7EE: 5, 0xD813: 5, 0xD718: 0,
                                  0xC200+16*10+5: 26, 0xC109: 12})
        assert progress_module.read_progress(self.game, sdk) == p
        self.game.frame_count = 7233
        self.original_previous = ['down']
        self.prepare_hole()
        out, _ = self.hole_context()
        assert out['review_reason'] == layout.ERROR
        self.c = bridge._CONTROLLERS[gate.HOLE_ID]
        self.layout_cap = dict(kind=layout.KIND, game_id='game29', source_frame=7233,
            source_location=deepcopy(layout.LOCATION), original_step_id=gate.HOLE_ID,
            original_step_sha256=shared.canonical_sha256(self.plan['steps'][1]),
            training_job_sha256=shared.canonical_sha256(self.plan['training_job']),
            steps_sha256=shared.canonical_sha256(self.plan['steps']),
            recovery_capsule_sha256=shared.canonical_sha256(self.plan['reviewed_fnt_recovery']),
            source_progress_sha256=shared.canonical_sha256(p), source_layout=layout.LAYOUT,
            evidence=deepcopy(layout.EVIDENCE))
        assert self.layout_context()[0]['available_actions'] == ['wait']
        self.original_previous = ['wait']; self.prepare_hole(40)
        assert self.layout_context() is None
        out, _ = self.hole_context()
        assert out['available_actions'] == ['right', 'wait'] and not self.c.pending['executed']
        self.original_previous = ['right']
        self.game.memory[0xC200+16*10+5] = 27
        self.game.memory[0xD813] |= 64
        self.game.memory[0xD5B2] &= ~1
        self.game.memory[0xD5B5] |= 4
        self.game.memory[0xD718] = 10
        for _ in range(3):
            self.prepare_hole(40)
            out, _ = self.hole_context()
            self.original_previous = ['wait']
        assert out['field_move_complete'] and gate.HOLE_ID in bridge._COMPLETED
        self.original_c = self.c
        self.original_binding = bridge._BINDINGS[gate.HOLE_ID]
        self.original_packet = self.c.last_packet
        self.preserved = deepcopy({k: getattr(self.c, k) for k in gate._PRESERVED})
        self.cap = dict(kind=gate.KIND, game_id='game29', source_frame=gate.FRAME,
            source_location=deepcopy(gate.LOCATION), landing_location=deepcopy(gate.LANDING),
            original_step_id=gate.STEP_ID, original_step_sha256=shared.canonical_sha256(self.plan['steps'][2]),
            training_job_sha256=shared.canonical_sha256(self.plan['training_job']),
            steps_sha256=shared.canonical_sha256(self.plan['steps']),
            recovery_capsule_sha256=shared.canonical_sha256(self.plan['reviewed_fnt_recovery']),
            source_progress_sha256=gate.SOURCE_PROGRESS_SHA256, evidence=deepcopy(gate.EVIDENCE))
        self.step_id = gate.STEP_ID
        self.apply_sample(0, frame=gate.FRAME)

    def peers(self):
        return {k: set() for k in shared.PEER_NAMES}

    def kwargs(self):
        return dict(bridge=bridge, shared=shared, recovery=recovery, native_owner=self.game,
                    game_id='game29', review_capsule=self.cap, source_evidence=deepcopy(gate.EVIDENCE),
                    peer_owners=self.peers())

    def prepare_hole(self, frames=0):
        self.game.frame_count += frames
        self.game.cells = hh.blank(); self.game.memory[0xFF40] = 0x91
        f = self.game.frame_count
        self.text = hh.read_visible_text(self.game)
        self.grid = bh.grid('3f_hole', f, (21, 15), self.game.memory)
        self.state = dict(frame=f, phase='unclassified', location=deepcopy(layout.LOCATION),
            progress=progress_module.read_progress(self.game, sdk),
            battle_state=dict(raw=0, kind='none', active=False, observation_frame=f))

    def layout_context(self):
        return layout.context(self.game, self.state, self.plan, gate.HOLE_ID, self.text, self.grid,
            self.original_previous, bridge=bridge, shared=shared, recovery=recovery,
            native_owner=self.game, game_id='game29', review_capsule=self.layout_cap,
            source_evidence=deepcopy(layout.EVIDENCE), peer_owners={**self.peers(), 'victory_later_boulder': bridge._active()})

    def hole_context(self):
        source_layout = getattr(bridge._CONTROLLERS.get(gate.HOLE_ID), 'source_layout', 'source')
        return bridge.context(self.game, self.state, self.plan, gate.HOLE_ID, self.text, self.grid,
            self.original_previous, reviewed_fainted_bench=(7,), source_layout=source_layout,
            now=(self.game.frame_count-7233)/60+1)

    def apply_sample(self, index, *, frame=None):
        sample = deepcopy(SAMPLES[index])
        self.game.frame_count = gate.FRAME + sample['t'] if frame is None else frame
        f = self.game.frame_count
        if sample['location'] == gate.LANDING:
            # Real 2F source layout after native map-load, not old 3F C2 slots.
            fresh = bh.Memory('2f_switch2').values
            for address, value in fresh.items():
                if (0xC110 <= address < 0xC1E0 or 0xC210 <= address < 0xC2E0
                        or 0xD4E1 <= address < 0xD500 or 0xD5CE <= address < 0xD5EF):
                    self.game.memory[address] = value
            self.game.memory.update({0xD728: 64, 0xD732: 1, 0xD700: 0, 0xD7EE: 5, 0xD813: 69,
                                     0xC781: 21, 0xC7C8: 37, 0xD367: 17, 0xD368: 9, 0xD369: 15})
        else:
            for name, value in sample['boulder']['raw'].items():
                self.game.memory[bridge.boulder._addresses('3f_hole')[name]] = value
        for name, value in PHASES[index]['signal']['raw'].items():
            self.game.memory[bridge.boulder._addresses('3f_hole')[name]] = value
        for address, value in sample['raw'].items():
            self.game.memory[int(address, 16)] = value
        self.text = deepcopy(PHASES[index]['text']); self.grid = deepcopy(PHASES[index]['grid'])
        if self.grid is not None:
            self.grid['observation_frame'] = f
        self.state = dict(frame=f, phase=PHASES[index]['phase'], location=sample['location'],
            progress=progress_module.read_progress(self.game, sdk),
            battle_state=dict(raw=0, kind='none', active=False, observation_frame=f))
        assert self.state['progress'] == sample['progress']
        return self

    def call(self, **kwargs):
        args = self.kwargs(); args.update(kwargs)
        snapshot = deepcopy((dict(self.game.memory), self.state, self.text, self.grid, self.plan))
        result = gate.context(self.game, self.state, self.plan, self.step_id, self.text, self.grid, **args)
        assert snapshot == (dict(self.game.memory), self.state, self.text, self.grid, self.plan)
        assert self.c is self.original_c and self.c.last_packet is self.original_packet
        assert self.preserved == {k: getattr(self.c, k) for k in gate._PRESERVED}
        return result

    def finish(self):
        out, nxt = self.call()
        for index in range(1, 12):
            self.apply_sample(index)
            out, nxt = self.call()
        assert out['native_fall_complete'] is True and nxt == gate.NEXT_ID
        return out


def review(result):
    assert result[0]['phase'] == 'campaign_review', result
    assert result[0]['available_actions'] == ['wait']
    assert not result[0].get('field_move_complete')


def test_source_native_phases_replayed_through_real_getters_and_two_fresh_landing_worlds():
    s = Session()
    assert gate._active() == set()
    out, nxt = s.call()
    assert out['available_actions'] == ['wait'] and nxt == gate.STEP_ID and gate._active() == {gate.STEP_ID}
    for index in range(1, len(SAMPLES)):
        s.apply_sample(index)
        result = s.call()
        if index == 12:
            assert result is None
            continue
        out, nxt = result
        if index < 11:
            assert out['available_actions'] == ['wait'] and nxt == gate.STEP_ID
            assert not out.get('field_move_complete') and not out.get('field_move_kind')
        elif index == 11:
            assert out['native_fall_complete'] and nxt == gate.NEXT_ID
            assert gate._active() == set()


def test_completion_same_frame_wait_then_fresh_original_route_may_move_and_start_strength():
    s = Session(); out = s.finish()
    assert out['field_move_kind'] == 'reviewed-native-fall'
    record = gate._SESSIONS[('game29', gate.STEP_ID)]
    assert record['receipt']['full_progress_sha256'] == gate.SOURCE_PROGRESS_SHA256
    assert record['receipt']['actual_closed']['raw']['flags1'] & 1 == 0
    assert record['receipt']['actual_closed']['stone']['hidden'] is False
    s.step_id = 'league28-fnt-recovery-04'
    assert s.call()[0]['available_actions'] == ['wait']
    s.game.frame_count += 1; s.state['frame'] += 1
    s.state['battle_state']['observation_frame'] += 1
    s.state['location'] = dict(map_id=194, x=21, y=16)
    assert s.call() is None  # done no longer locks the original fall point
    assert not gate.applies(s.plan, 'league28-fnt-recovery-05') and gate._active() == set()


@pytest.mark.parametrize('cursor', [None, 'unknown', 'league28-fnt-recovery-05', 4])
def test_active_gate_cannot_be_bypassed_by_any_other_cursor(cursor):
    s = Session(); s.call(); s.apply_sample(2); s.step_id = cursor
    assert gate.applies(s.plan, cursor)
    review(s.call())


@pytest.mark.parametrize('cursor', ['league28-fnt-recovery-03', 'league28-fnt-recovery-04'])
def test_new_floor_early_next_map_skip_and_strength_are_held_until_closed(cursor):
    s = Session(); s.call(); s.step_id = cursor; s.apply_sample(2)
    out, nxt = s.call()
    assert out['available_actions'] == ['wait'] and nxt == gate.STEP_ID
    assert gate._active() == {gate.STEP_ID}


@pytest.mark.parametrize('bad', ['native', 'frame', 'peer', 'missing_peer', 'peer_unknown', 'capsule',
    'evidence', 'job', 'steps', 'recovery', 'progress', 'battle', 'phase', 'unknown_review',
    'source_coord', 'source_float', 'done_bit', 'original_packet', 'binding', 'controller',
    'original_pending', 'original_budget', 'native_record'])
def test_preflight_failures_are_sticky_and_happen_without_memory_or_ui_reads(bad):
    s = Session(); args = s.kwargs()
    if bad == 'native': args['native_owner'] = object()
    if bad == 'frame': s.state['frame'] += 1
    if bad == 'peer': args['peer_owners']['victory_strength'] = {'foreign'}
    if bad == 'missing_peer': args['peer_owners'].pop('tm24_teaching')
    if bad == 'peer_unknown': args['peer_owners']['victory_strength'] = None
    if bad == 'capsule': s.cap['source_frame'] = True
    if bad == 'evidence': args['source_evidence']['state_sha256'] = 'a'*64
    if bad == 'job': s.plan['training_job'] = 'foreign'
    if bad == 'steps': s.plan['steps'][2]['next_map'] = 198
    if bad == 'recovery': s.plan['reviewed_fnt_recovery']['fainted_species'] = 35
    if bad == 'progress': s.state['progress']['party'][0]['hp'] -= 1
    if bad == 'battle': s.state['battle_state']['raw'] = 1
    if bad == 'phase': s.state['phase'] = 'battle_dialogue'
    if bad == 'unknown_review': s.state.update(phase='campaign_review', review_reason='unrelated')
    if bad == 'source_coord': s.state['location']['x'] -= 1
    if bad == 'source_float': s.state['location']['x'] = 23.0
    if bad == 'done_bit': bridge._COMPLETED.clear()
    if bad == 'original_packet': s.c.last_packet[0]['progress']['party'][0]['hp'] -= 1
    if bad == 'binding': bridge._BINDINGS[gate.HOLE_ID] = ('foreign', 'step', 'job')
    if bad == 'controller': bridge._CONTROLLERS[gate.HOLE_ID] = object()
    if bad == 'original_pending': s.c.pending = {'action': 'right', 'executed': False}
    if bad == 'original_budget': s.c.last_now = None
    if bad == 'native_record': s.c.source_layout_review_record['native_owner'] = object()
    count = len(s.game.memory.reads)
    out = gate.preflight(s.game, s.state, s.plan, s.step_id, **args)
    review(out); assert len(s.game.memory.reads) == count
    assert gate._active() == {gate.STEP_ID}
    review(gate.preflight(s.game, s.state, s.plan, s.step_id, **s.kwargs()))


@pytest.mark.parametrize('address,value', [(0xD72D, 0), (0xD732, 1), (0xD71D, 198), (0xD71E, 1),
    (0xD057, 1), (0xD700, 1), (0xCD38, 1), (0xCFC5, 1), (0xD736, 1), (0xD730, 1),
    (0xD733, 4), (0xCD6B, 1), (0xD813, 5), (0xD5B5, 0), (0xD5B2, 1)])
def test_missing_entry_proof_or_foreign_native_motion_never_becomes_generic_blank_wait(address, value):
    s = Session(); s.game.memory[address] = value
    review(s.call())


@pytest.mark.parametrize('bad', ['text', 'window', 'unknown_text', 'unknown_profile', 'slot11',
    'slot13_hidden', 'foreign_floor', 'source_return', 'event', 'toggle', 'fresh_progress',
    'resource_state', 'sameframe'])
def test_transition_and_closed_world_tamper_is_never_released(bad):
    s = Session(); s.call(); s.apply_sample(10)
    if bad == 'text': s.text['cells'][4][2] = 'A'
    if bad == 'window': s.text['window_visible'] = True
    if bad == 'unknown_text': s.text.update(read_valid=False, alignment_verified=False, read_error='unknown')
    if bad == 'unknown_profile': s.text['profile'] = 'foreign'
    if bad == 'slot11': s.game.memory[0xC200+16*11+5] = 5
    if bad == 'slot13_hidden': s.game.memory[0xD5B2] |= 1
    if bad == 'foreign_floor': s.state['location']['map_id'] = 199
    if bad == 'source_return':
        s.call(); s.apply_sample(0, frame=gate.FRAME+200)
    if bad == 'event': s.game.memory[0xD7EE] ^= 1
    if bad == 'toggle': s.game.memory[0xD5A7] ^= 1
    if bad == 'fresh_progress': s.game.game_wrapper.party[0]['pp'][0] -= 1
    if bad == 'resource_state': s.state['progress']['party'][0]['exp'] += 1
    if bad == 'sameframe':
        s.call(); s.text['cells'][0][0] = 'X'
    result = s.call()
    review(result)


def test_same_frame_reentry_never_refunds_budget_or_claims_a_second_fresh_world():
    s = Session(); s.call()
    record = gate._SESSIONS[('game29', gate.STEP_ID)]
    for _ in range(30): assert s.call()[0]['available_actions'] == ['wait']
    assert record['waits'] == 1
    s.apply_sample(10); s.call()
    first = record['first_closed_frame']
    for _ in range(3): assert not s.call()[0].get('field_move_complete')
    assert record['first_closed_frame'] == first and record['waits'] == 2


@pytest.mark.parametrize('limit', ['frames', 'waits', 'reverse'])
def test_actual_budgets_and_frame_monotonicity_are_sticky(limit):
    s = Session(); s.call()
    if limit == 'frames': s.apply_sample(1, frame=gate.FRAME+601)
    elif limit == 'reverse': s.apply_sample(1, frame=gate.FRAME-1)
    else:
        for i in range(1, 20):
            s.apply_sample(1, frame=gate.FRAME+i)
            assert s.call()[0]['available_actions'] == ['wait']
        s.apply_sample(1, frame=gate.FRAME+20)
    review(s.call()); assert gate._active() == {gate.STEP_ID}


@pytest.mark.parametrize('bad', ['controller', 'binding', 'packet', 'receipt', 'native', 'native_record', 'case'])
def test_done_does_not_hide_replaced_owner_binding_or_closed_receipt(bad):
    s = Session(); s.finish()
    r = gate._SESSIONS[('game29', gate.STEP_ID)]
    if bad == 'controller': bridge._CONTROLLERS[gate.HOLE_ID] = object()
    if bad == 'binding': bridge._BINDINGS[gate.HOLE_ID] = tuple(list(s.original_binding))
    if bad == 'packet': s.c.last_packet[0]['frame'] -= 1
    if bad == 'receipt': r['receipt']['completed_frame'] -= 1
    if bad == 'native_record': s.c.source_layout_review_record['native_owner'] = object()
    if bad == 'case': s.c.case['goal_stone'][0] -= 1
    args = {'native_owner': object()} if bad == 'native' else {}
    s.game.frame_count += 1; s.state['frame'] += 1; s.state['battle_state']['observation_frame'] += 1
    review(s.call(**args))


def test_hot_reload_preserves_warm_gate_and_does_not_reconstruct_original_owner(monkeypatch):
    s = Session(); s.call(); record = gate._SESSIONS[('game29', gate.STEP_ID)]
    gate.__spec__.loader.exec_module(gate)
    monkeypatch.setattr(gate, 'SOURCE_PROGRESS_SHA256', shared.canonical_sha256(SAMPLES[0]['progress']))
    assert gate._SESSIONS[('game29', gate.STEP_ID)] is record
    s.apply_sample(2); assert s.call()[0]['available_actions'] == ['wait']


@pytest.mark.parametrize('step_id', [None, 'ordinary', gate.STEP_ID])
def test_unmarked_old_plans_keep_backwards_compatible_no_ownership(step_id):
    assert not gate.applies({'steps': []}, step_id)
    assert gate._active() == set()


def test_only_named_navigation_review_is_admitted_and_never_cleared_on_original_controller():
    s = Session(); s.state.update(phase='campaign_review', review_reason='victory_navigation_closed_world_required')
    out, nxt = s.call()
    assert out['available_actions'] == ['wait'] and nxt == gate.STEP_ID
    assert s.c.error is None and gate._active() == {gate.STEP_ID}
    assert s.call()[0]['available_actions'] == ['wait']
    assert gate._SESSIONS[('game29', gate.STEP_ID)]['waits'] == 1


@pytest.mark.parametrize('sample', [5, 10, 11])
@pytest.mark.parametrize('address,value', [(0xD71D, 198), (0xD71E, 1)])
def test_native_destination_and_warp_index_cannot_change_in_any_phase(sample, address, value):
    s = Session(); s.call(); s.apply_sample(sample)
    s.game.memory[address] = value
    review(s.call())


@pytest.mark.parametrize('bad', ['unbound', 'source', 'joy', 'dungeon', 'grid', 'error'])
def test_disabled_empty_cells_require_this_active_landing_animation(bad):
    s = Session()
    if bad != 'unbound': s.call()
    s.apply_sample(5)
    if bad == 'source':
        s.state['location'] = deepcopy(gate.LOCATION)
        s.game.memory.update({0xD35E: 198, 0xD362: 23, 0xD361: 15})
    if bad == 'joy': s.game.memory[0xCD6B] = 0
    if bad == 'dungeon': s.game.memory[0xD732] &= ~16
    if bad == 'grid': s.grid = {'unknown': True}
    if bad == 'error': s.text['read_error'] = 'unknown'
    review(s.call())


def test_real_authority_is_pinned_separately_from_synthetic_resource_fixture():
    assert REAL_PROGRESS_AUTHORITY == '15bed7a5c90f0d9ec756e1c3a4428ef1f0c270fa9d8e78bdc276cae207bf1a0e'
    assert gate.EVIDENCE == dict(
        review_sha256='40bcfe4dcd399cb837dc05821484da4aa0f9df07579174e078529bf77f39cd0a',
        state_sha256='a49b27c4868ca9da561bb9610553fd1a8afdc47d38d02685e75cb2e4c3e795ad',
        preflight_sha256='858dc6a8ed19b9f29aec39ce30cebcc95983451cac1fa8532ceb291e094af0a4')
