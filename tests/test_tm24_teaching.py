"""Portable tests: src + tests/fixtures only; no ignored-directory fallback.

Default source is cwd/src. For a staged candidate explicitly set
LAYA_TM24_SOURCE_ROOT to its exact src directory. Never open a ROM or state.
"""
from copy import deepcopy
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import types

import pytest
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk

SOURCE = Path(os.environ.get('LAYA_TM24_SOURCE_ROOT', str(Path.cwd() / 'src'))).resolve()
FORMAL_SRC = (Path.cwd() / 'src').resolve()
from laya_pokemon.observation import read_visible_text
from laya_pokemon.progress import read_progress
from laya_pokemon.rocket_movement import read_rocket_movement


def load(name, source=SOURCE):
    path = source / 'laya_pokemon' / (name + '.py')
    if not path.is_file():
        raise RuntimeError('Exact requested source is absent: ' + str(path))
    if source == FORMAL_SRC:
        module = importlib.import_module('laya_pokemon.' + name)
        assert Path(module.__file__).resolve() == path.resolve()
        return module
    if source == SOURCE:
        if os.environ.get('LAYA_TM24_STAGED_ISOLATED') != '1':
            raise RuntimeError('Staged sources require an explicitly isolated pytest process')
        module = importlib.import_module('_tm24_staged.' + name)
        assert Path(module.__file__).resolve() == path.resolve()
        return module
    # EOL tests use an unregistered private name; canonical modules remain intact.
    spec = importlib.util.spec_from_file_location('laya_pokemon._tm24_eol_candidate', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if SOURCE != FORMAL_SRC:
    if os.environ.get('LAYA_TM24_STAGED_ISOLATED') != '1':
        raise RuntimeError('Staged sources require an explicitly isolated pytest process')
    package = types.ModuleType('_tm24_staged')
    package.__path__ = [str(SOURCE / 'laya_pokemon'), str(FORMAL_SRC / 'laya_pokemon')]
    sys.modules['_tm24_staged'] = package
tm = load('tm24_teaching')
bridge = load('tm24_teaching_bridge')
FIXTURE = json.loads((Path(__file__).parent / 'fixtures/tm24_source_views.json').read_text(encoding='utf-8'))


class Memory:
    def __init__(self):
        self.values, self.reads, self.writes = {}, [], []
    def __getitem__(self, address):
        self.reads.append(address)
        return self.values.get(address, 0)
    def __setitem__(self, address, value):
        self.writes.append((address, value))
        raise AssertionError('Forbidden memory write')


class Wrapper:
    def __init__(self):
        self.party_value = deepcopy(FIXTURE['party'])
        self.inventory_value = deepcopy(FIXTURE['inventory'])
        self.calls = {'party': 0, 'inventory': 0, 'money': 0}
    @property
    def party(self):
        self.calls['party'] += 1
        return deepcopy(self.party_value)
    @property
    def inventory(self):
        self.calls['inventory'] += 1
        return deepcopy(self.inventory_value)
    @property
    def money(self):
        self.calls['money'] += 1
        return FIXTURE['money']


class Tilemap:
    def __init__(self, rows):
        self.rows = rows
        self.encoding = {v.upper(): k for k, v in sdk.POKEMON_TEXT_DECODING.items()
                         if isinstance(v, str) and len(v) == 1}
    def __getitem__(self, xy):
        x, y = xy
        row = self.rows[y]
        if row[max(0, x-3):x+1] == 'CANT':
            return next(k for k, v in sdk.POKEMON_TEXT_DECODING.items() if v == "'t")
        return self.encoding[row[x]]


class Fake:
    def __init__(self, view='blank', frame=100):
        self.frame_count = frame
        self.memory, self.game_wrapper = Memory(), Wrapper()
        self.screen = type('Screen', (), {'tilemap_position_list': [(0, 0, 0, 0)] * 144})()
        self.memory.values.update({0xFF40: 0x91, sdk.PARTY_COUNT_ADDRESS: 6})
        encoding = {v: k for k, v in sdk.POKEMON_TEXT_DECODING.items()}
        for n, ch in enumerate('KEVIN'):
            self.memory.values[sdk.PLAYER_NAME_ADDRESS+n] = encoding[ch]
        self.memory.values[sdk.PLAYER_NAME_ADDRESS+5] = 0x50
        for n, byte in enumerate((0x12, 0x34, 0x56)):
            self.memory.values[sdk.PLAYER_MONEY_ADDRESS+n] = byte
        self.view(view)
    def view(self, name):
        self.tilemap_background = Tilemap(FIXTURE['views'][name])
        self.tilemap_window = self.tilemap_background
    def packet(self):
        text = read_visible_text(self)
        progress = read_progress(self, sdk)
        assert text['read_valid'] and progress['party_read_valid']
        return dict(text=text, progress=progress,
            location=dict(map_id=174, x=7, y=7, observation_frame=self.frame_count),
            battle_state=dict(kind='none', active=False, raw=0, observation_frame=self.frame_count),
            movement=read_rocket_movement(self, observation_frame=self.frame_count),
            frame=self.frame_count, now=self.frame_count / 100,
            overworld_ready=all(not row.strip() for row in self.tilemap_background.rows))
    def apply_after(self):
        self.game_wrapper.party_value[0]['moves'] = [57, 34, 58, 85]
        self.game_wrapper.party_value[0]['pp'] = [12, 8, 7, 15]
    def consume(self):
        self.game_wrapper.inventory_value = [i for i in self.game_wrapper.inventory_value if i['item'] != 224]


def action(result):
    return result['available_actions'][0]


class Run:
    def __init__(self):
        self.fake, self.controller = Fake(), tm.TM24TeachingController(deepcopy(tm.INTENT))
        self.previous = []
    def call(self, view, previous=None, *, after=False, consume=False, advance=True):
        if advance:
            self.fake.frame_count += 40
        self.fake.view(view)
        if after:
            self.fake.apply_after()
        if consume:
            self.fake.consume()
        packet = self.fake.packet()
        result = self.controller.context(**packet, previous=self.previous if previous is None else previous)
        self.previous = (self.previous + [action(result)])[-8:]
        return result
    def until(self, stop):
        for event in FIXTURE['schedule']:
            result = self.call(event['view'], after=event['view'].startswith('learned'),
                               consume=event['view'] == 'postbag')
            assert result.get('review_reason') is None, result
            assert action(result) == event['action'], (event, result)
            if event['view'] == stop:
                return result
        raise AssertionError(stop)


def test_real_sdk_constants_and_only_getters_full_transaction():
    assert sdk.PARTY_COUNT_ADDRESS == 0xD163 and sdk.PARTY_LENGTH == 6
    assert sdk.POKEMON_SPECIES_NAMES[19] == 'LAPRAS'
    run = Run()
    run.until('postbag')
    assert run.controller.learned_acked is True and run.controller.consumed is True
    assert action(run.call('start6')) == 'b'
    assert not run.call('blank').get('tm24_complete')
    result = run.call('blank')
    assert result['tm24_complete'] and result['quantity_used'] == 1 and result['machine_kind'] == 'TM'
    assert result['moves_verified'] == [57, 34, 58, 85]
    assert run.fake.memory.writes == []
    assert run.fake.game_wrapper.calls['party'] == run.controller.calls
    assert run.fake.game_wrapper.party_value[1:] == FIXTURE['party'][1:]
    assert run.fake.game_wrapper.inventory_value == [x for x in FIXTURE['inventory'] if x['item'] != 224]


def test_offer_is_not_ack_and_initial_world_requires_two_fresh_frames():
    run = Run()
    assert action(run.call('blank')) == 'wait'
    offered = run.call('blank')
    assert action(offered) == 'start'
    assert run.controller.stage == 'preflight' and run.controller.pending['action'] == 'start'
    # Same frame cannot ACK or resend even when the prior real action was start.
    packet = run.fake.packet()
    packet['now'] += .01
    result = run.controller.context(**packet, previous=['wait'])
    assert action(result) == 'wait' and run.controller.pending is not None
    result = run.call('start2', previous=['wait'])
    assert result['review_reason'] == 'tm24_actual_previous_did_not_ack_start'
    assert run.call('start2', previous=['start'])['review_reason'] == result['review_reason']


def test_same_frame_changed_packet_is_sticky():
    run = Run(); run.call('blank')
    packet = run.fake.packet(); packet['progress']['money'] -= 1
    result = run.controller.context(**packet, previous=[])
    assert result['review_reason'] == 'tm24_same_frame_conflicting_packet'
    assert run.controller.pending is None


@pytest.mark.parametrize('stop,nextview', [('use','boot'),('contained','teach'),('party','intro0'),
    ('delete','forget8'),('forget11','poof_typing'),('forgot','and'),('learned','postbag')])
def test_every_critical_a_requires_actual_a(stop, nextview):
    run = Run(); run.until(stop)
    result = run.call(nextview, previous=['wait'], after=nextview == 'postbag', consume=nextview == 'postbag')
    assert result['review_reason'] == 'tm24_actual_previous_did_not_ack_a'
    assert run.controller.pending is not None


def test_early_consumption_and_early_move_mutation_stop():
    run = Run(); run.until('forget11')
    result = run.call('poof_typing', after=True)
    assert result['review_reason'] == 'tm24_unexpected_or_premature_move_pp_change'
    run = Run(); run.until('learned')
    # Candidate learned A still has not been performed, even on the same source frame.
    packet = run.fake.packet(); run.fake.consume(); packet['progress'] = read_progress(run.fake, sdk)
    packet['frame'] += 1; packet['now'] += .01
    for key in ('location','battle_state','movement'): packet[key]['observation_frame'] += 1
    result = run.controller.context(**packet, previous=['wait'])
    assert result['review_reason'] == 'tm24_actual_previous_did_not_ack_a'
    run = Run(); run.until('and')
    result = run.call('learned', after=True, consume=True)
    assert result['review_reason'] == 'tm24_tm_consumed_before_actual_learned_a'


@pytest.mark.parametrize('mutation', ['pp', 'hp', 'status', 'level', 'exp', 'other', 'order', 'money', 'bag_order', 'bag_quantity', 'roster'])
def test_resources_only_exact_allowed_difference(mutation):
    run = Run(); run.until('learned')
    run.fake.apply_after(); run.fake.consume()
    p = run.fake.packet()['progress']
    if mutation == 'pp': p['party'][0]['pp'][1] -= 1
    elif mutation in ('hp','status','level','exp'): p['party'][0][mutation] += 1 if mutation != 'hp' else -1
    elif mutation == 'other': p['party'][1]['exp'] += 1
    elif mutation == 'order': p['party'][1],p['party'][2] = p['party'][2],p['party'][1]
    elif mutation == 'money': p['money'] -= 1
    elif mutation == 'bag_order': p['inventory'].reverse()
    elif mutation == 'bag_quantity': p['inventory'][0]['quantity'] -= 1
    elif mutation == 'roster': p['party'][2]['species'] = 103
    run.fake.frame_count += 40; run.fake.view('postbag')
    packet = run.fake.packet(); packet['progress'] = p
    assert run.controller.context(**packet, previous=['a'])['phase'] == 'campaign_review'


def test_wrong_forget_slot_or_cursor_skip_cannot_act():
    run = Run(); run.until('forget8')
    result = run.call('forget10')
    assert result['review_reason'] == 'tm24_cursor_did_not_move_one_source_item'


def test_source_unknown_and_out_of_stage_pages_stop():
    run = Run(); run.until('use')
    assert run.call('learned', after=False)['review_reason'] == 'tm24_unknown_or_out_of_stage_source_page'
    run = Run(); run.until('use'); run.fake.frame_count += 40; run.fake.view('boot')
    packet = run.fake.packet(); packet['text']['cells'][14][1] = 'X'
    packet['text'].pop('lines'); packet['text'].pop('line_rows')
    assert run.controller.context(**packet, previous=['a'])['review_reason'] == 'tm24_unknown_or_out_of_stage_source_page'


def test_no_prompt_arrow_waits_without_committing_and_or_learned():
    run = Run(); run.until('and')
    result = run.call('learned_typing', after=True)
    assert action(result) == 'wait' and run.controller.and_acked and not run.controller.learned_acked
    assert run.controller.pending is None
    result = run.call('learned', after=True)
    assert action(result) == 'a' and not run.controller.learned_acked


def test_after_consumption_must_not_revert_and_must_close_bag_and_start():
    run = Run(); run.until('postbag')
    run.fake.game_wrapper.inventory_value = deepcopy(FIXTURE['inventory'])
    assert run.call('start6')['review_reason'] == 'tm24_inventory_difference_or_reversion'
    run = Run(); run.until('postbag')
    assert run.call('blank')['review_reason'] == 'tm24_world_closed_before_native_return_and_close'


def test_second_closed_frame_must_remain_stable_and_completion_revalidates():
    run = Run(); run.until('postbag'); run.call('start6'); run.call('blank')
    run.fake.frame_count += 40
    packet = run.fake.packet(); packet['overworld_ready'] = False
    assert run.controller.context(**packet, previous=['wait'])['review_reason'] == 'tm24_post_closed_world_not_stable'
    run = Run(); run.until('postbag'); run.call('start6'); run.call('blank')
    assert run.call('blank')['tm24_complete']
    run.fake.game_wrapper.party_value[0]['pp'][0] -= 1
    assert run.call('blank')['phase'] == 'campaign_review'


def test_forget_menu_cannot_replace_surf_or_any_other_slot():
    run = Run(); run.until('forget11')
    run.fake.frame_count += 40; run.fake.view('poof_typing')
    packet = run.fake.packet()
    packet['progress']['party'][0]['moves'] = [85,34,58,109]
    packet['progress']['party'][0]['pp'] = [15,8,7,9]
    assert run.controller.context(**packet, previous=['a'])['phase'] == 'campaign_review'


@pytest.mark.parametrize('field', ['clock','frame','idle','window','observation'])
def test_closed_world_and_budget_are_real_observation_guards(field):
    run = Run(); run.call('blank')
    packet = run.fake.packet(); packet['frame'] += 1; packet['now'] += .01
    for key in ('location','battle_state','movement'): packet[key]['observation_frame'] += 1
    if field == 'clock': packet['now'] += 61
    elif field == 'frame':
        packet['frame'] += 3601
        for key in ('location','battle_state','movement'): packet[key]['observation_frame'] += 3601
    elif field == 'idle': packet['movement']['walk_counter'] = 1
    elif field == 'window': packet['text']['window_visible'] = True
    elif field == 'observation': packet['battle_state']['observation_frame'] -= 1
    assert run.controller.context(**packet, previous=['wait'])['phase'] == 'campaign_review'


def plan():
    return dict(training_job=bridge.JOB, steps=[dict(id='tm24',kind='interact',mechanic='lapras_tm24',
        map_id=174,target=[7,7],teaching_intent=deepcopy(tm.INTENT)), dict(id='next',kind='stop')])


@pytest.fixture
def clean_bridge():
    for collection in (bridge._CONTROLLERS, bridge._BINDINGS, bridge._OWNERS, bridge._COMPLETED, bridge._ERRORS): collection.clear()
    yield
    for collection in (bridge._CONTROLLERS, bridge._BINDINGS, bridge._OWNERS, bridge._COMPLETED, bridge._ERRORS): collection.clear()


def grid(frame):
    return dict(observation_frame=frame,verified_location=[174,7,7],screen_cells_verified=12,
                visible_verified_cells=[[x,7] for x in range(12)],
                walkable=[[1] * 12 for _ in range(8)], tiles=[[0] * 12 for _ in range(8)],
                source=bridge.GRID_SOURCE)


def bridge_call(fake, task=None, previous=(), peers=()):
    packet = fake.packet()
    state = dict(frame=fake.frame_count,progress=packet['progress'],location=packet['location'],battle_state=packet['battle_state'])
    return bridge.context(fake,state,task or plan(),'tm24',packet['text'],grid(fake.frame_count),previous,
                          peer_owners=peers,now=fake.frame_count/100)


def test_bridge_complete_step_and_job_binding_reload_and_budgets(clean_bridge):
    fake = Fake(); bridge_call(fake)
    fake.frame_count += 40; assert action(bridge_call(fake,previous=['wait'])[0]) == 'start'
    controller = bridge._CONTROLLERS['tm24']
    pending, began, startframe = deepcopy(controller.pending), controller.started_at, controller.start_frame
    reloaded = importlib.reload(bridge)
    assert reloaded._CONTROLLERS['tm24'] is controller
    assert controller.pending == pending and controller.started_at == began and controller.start_frame == startframe
    task = plan(); task['steps'][0]['description'] = 'added metadata is still a full step edit'
    assert bridge_call(fake,task,previous=['wait'])[0]['phase'] == 'campaign_review'
    assert bridge._CONTROLLERS['tm24'].pending == pending
    assert bridge._active() == {'tm24'}


@pytest.mark.parametrize('case', ['job','peer','missing_peer','frame','grid','battle','location'])
def test_bridge_rejects_missing_peer_proof_and_bad_inputs(case, clean_bridge):
    fake = Fake(); task = plan(); packet = fake.packet(); peers = ()
    state = dict(frame=fake.frame_count,progress=packet['progress'],location=packet['location'],battle_state=packet['battle_state'])
    g = grid(fake.frame_count)
    if case == 'job': task['training_job'] += '-changed'
    elif case == 'peer': peers = ('hm-owner',)
    elif case == 'missing_peer': peers = None
    elif case == 'frame': fake.frame_count += 1
    elif case == 'grid': g['observation_frame'] += 1
    elif case == 'battle': state['battle_state']['raw'] = 1
    elif case == 'location': state['location']['map_id'] = 171
    result, owner = bridge.context(fake,state,task,'tm24',packet['text'],g,[],peer_owners=peers,now=1)
    assert result['phase'] == 'campaign_review' and owner == 'tm24'
    assert bridge._active() == {'tm24'}
    assert not fake.memory.writes


def test_bridge_owner_change_preserves_original_owner(clean_bridge):
    fake = Fake(); bridge_call(fake)
    packet = fake.packet(); state = dict(frame=fake.frame_count)
    result, owner = bridge.context(fake,state,plan(),'other',packet['text'],None,[],peer_owners=(),now=2)
    assert result['phase'] == 'campaign_review' and owner == 'tm24'
    assert bridge._active() == {'tm24'}


@pytest.mark.parametrize('newline', ['\n','\r\n'])
def test_explicit_source_path_accepts_lf_and_crlf_without_hash_bypass(tmp_path, newline):
    source = SOURCE / 'laya_pokemon/tm24_teaching.py'
    destination = tmp_path / 'laya_pokemon'; destination.mkdir()
    (destination/'tm24_teaching.py').write_bytes(source.read_text(encoding='utf-8').replace('\r\n','\n').replace('\n',newline).encode())
    loaded = load('tm24_teaching',tmp_path)
    assert loaded.INTENT == tm.INTENT
    run = Run(); run.controller = loaded.TM24TeachingController(deepcopy(loaded.INTENT))
    assert action(run.call('blank')) == 'wait'
    assert action(run.call('blank')) == 'start'


@pytest.mark.parametrize('registry', ['_BINDINGS','_CONTROLLERS','_OWNERS'])
def test_bound_registry_loss_never_recreates_controller_or_owner(registry, clean_bridge):
    fake = Fake(); bridge_call(fake)
    original = bridge._CONTROLLERS['tm24']
    collection = getattr(bridge, registry); removed = collection.pop('tm24')
    fake.frame_count += 40
    result, owner = bridge_call(fake,previous=['wait'])
    assert result['phase'] == 'campaign_review' and owner == 'tm24'
    assert 'tm24' not in collection
    assert bridge._active() == {'tm24'}
    if registry != '_CONTROLLERS': assert bridge._CONTROLLERS['tm24'] is original
    assert removed is not None


@pytest.mark.parametrize('registry', ['_CONTROLLERS','_OWNERS','_BINDINGS'])
def test_orphan_registry_is_active_and_stops_before_binding(registry, clean_bridge):
    original = tm.TM24TeachingController(deepcopy(tm.INTENT))
    value = (original if registry == '_CONTROLLERS' else
             dict(pyboy=Fake(),controller=original) if registry == '_OWNERS' else
             dict(step=plan()['steps'][0],job=bridge.JOB))
    getattr(bridge,registry)['tm24'] = value
    assert bridge.applies('other',None) and bridge._active() == {'tm24'}
    result, owner = bridge_call(Fake())
    assert result['phase'] == 'campaign_review' and owner == 'tm24'
    for other in {'_CONTROLLERS','_OWNERS','_BINDINGS'} - {registry}:
        assert 'tm24' not in getattr(bridge,other)


def test_completed_marker_cannot_hide_an_orphan_controller(clean_bridge):
    bridge._CONTROLLERS['tm24'] = tm.TM24TeachingController(deepcopy(tm.INTENT))
    bridge._COMPLETED.add('tm24')
    assert bridge._active() == {'tm24'} and bridge.applies('other',None)
    assert bridge_call(Fake())[0]['phase'] == 'campaign_review'


def test_pyboy_identity_and_controller_identity_cannot_be_replaced(clean_bridge):
    fake = Fake(); bridge_call(fake)
    fake.frame_count += 40; bridge_call(fake,previous=['wait'])
    original = bridge._CONTROLLERS['tm24']; pending = deepcopy(original.pending)
    replacement = Fake(frame=fake.frame_count)
    result, owner = bridge_call(replacement,previous=['start'])
    assert result['review_reason'] == 'tm24_bridge_original_pyboy_identity_changed'
    assert owner == 'tm24' and bridge._OWNERS['tm24']['pyboy'] is fake
    assert original.pending == pending


def test_replacement_controller_is_not_accepted_even_with_valid_type(clean_bridge):
    fake = Fake(); bridge_call(fake)
    original = bridge._CONTROLLERS['tm24']
    replacement = tm.TM24TeachingController(deepcopy(tm.INTENT))
    bridge._CONTROLLERS['tm24'] = replacement
    result, owner = bridge_call(fake)
    assert result['phase'] == 'campaign_review' and owner == 'tm24'
    assert bridge._OWNERS['tm24']['controller'] is original
    assert bridge._CONTROLLERS['tm24'] is replacement


@pytest.mark.parametrize('registry,bad', [('_BINDINGS',[]),('_CONTROLLERS',[]),('_OWNERS',[]),
    ('_ERRORS',[]),('_COMPLETED',{}),('_BINDINGS',{True:{}})])
def test_registry_container_types_fail_closed_without_raising(registry,bad,monkeypatch,clean_bridge):
    monkeypatch.setattr(bridge,registry,bad)
    assert bridge._active()
    assert bridge_call(Fake())[0]['phase'] == 'campaign_review'


@pytest.mark.parametrize('registry,bad', [('_BINDINGS',None),('_CONTROLLERS',object()),
    ('_OWNERS',None),('_ERRORS',None)])
def test_registry_record_types_fail_closed(registry,bad,clean_bridge):
    fake = Fake(); bridge_call(fake)
    getattr(bridge,registry)['tm24'] = bad
    result, owner = bridge_call(fake)
    assert result['phase'] == 'campaign_review' and owner == 'tm24'
    assert bridge._active() == {'tm24'}


def test_reload_with_corrupt_class_registry_stops_without_import_error(clean_bridge):
    original = bridge._CONTROLLER_TYPES
    try:
        bridge._CONTROLLER_TYPES = ({'invalid':'unhashable'},)
        importlib.reload(bridge)
        assert bridge_call(Fake())[0]['phase'] == 'campaign_review'
    finally:
        bridge._CONTROLLER_TYPES = original
        importlib.reload(bridge)


@pytest.mark.parametrize('extra', ['description','reviewed_revision','reviewed_hm_revision','done'])
def test_step_is_exact_six_keys_even_before_first_observation(extra,clean_bridge):
    fake = Fake(); task = plan(); task['steps'][0][extra] = 'unexpected'
    result, owner = bridge_call(fake,task)
    assert result['phase'] == 'campaign_review' and owner == 'tm24'
    assert bridge._CONTROLLERS == {} and bridge._OWNERS == {}


@pytest.mark.parametrize('case', ['player_not_visible','blocked','bool_walk','ragged_walk','ragged_tiles',
    'tile_unknown','source_missing','source_unknown','location_bool','cell_oob','cell_float'])
def test_world_proof_requires_visible_walkable_player_and_exact_source(case,clean_bridge):
    fake = Fake(); packet = fake.packet(); g = grid(fake.frame_count)
    state = dict(frame=fake.frame_count,progress=packet['progress'],location=packet['location'],battle_state=packet['battle_state'])
    if case == 'player_not_visible': g['visible_verified_cells'][7] = [7,6]
    elif case == 'blocked': g['walkable'][7][7] = 0
    elif case == 'bool_walk': g['walkable'][7][7] = True
    elif case == 'ragged_walk': g['walkable'][2].pop()
    elif case == 'ragged_tiles': g['tiles'][2].pop()
    elif case == 'tile_unknown': g['tiles'][7][7] = None
    elif case == 'source_missing': g.pop('source')
    elif case == 'source_unknown': g['source'] = 'unverified'
    elif case == 'location_bool': g['verified_location'][1] = True
    elif case == 'cell_oob': g['visible_verified_cells'][0] = [12,7]
    elif case == 'cell_float': g['visible_verified_cells'][0] = [0.0,7]
    result, owner = bridge.context(fake,state,plan(),'tm24',packet['text'],g,[],peer_owners=())
    assert result['phase'] == 'campaign_review' and owner == 'tm24'
    assert bridge._active() == {'tm24'}


def call_without_now(fake,previous=()):
    packet = fake.packet()
    state = dict(frame=fake.frame_count,progress=packet['progress'],location=packet['location'],battle_state=packet['battle_state'])
    return bridge.context(fake,state,plan(),'tm24',packet['text'],grid(fake.frame_count),previous,peer_owners=())


def test_default_clock_is_frame_delta_and_reload_keeps_all_budgets(clean_bridge):
    fake = Fake(); call_without_now(fake)
    controller = bridge._CONTROLLERS['tm24']
    assert controller.last_now == 0 and controller.started_at == 0
    assert controller.start_frame == 100 and controller.calls == 1
    importlib.reload(bridge)
    assert bridge._OWNERS['tm24']['pyboy'] is fake
    assert bridge._OWNERS['tm24']['controller'] is controller
    fake.frame_count += 120
    assert action(call_without_now(fake,previous=['wait'])[0]) == 'start'
    assert controller.last_now == 2 and controller.started_at == 0
    assert controller.start_frame == 100 and controller.calls == 2
    pending = deepcopy(controller.pending)
    importlib.reload(bridge)
    fake.frame_count += 3601
    result, _ = call_without_now(fake,previous=['start'])
    assert result['review_reason'] == 'tm24_transaction_budget_exhausted'
    assert controller.pending == pending and controller.started_at == 0 and controller.start_frame == 100


def through_bridge(stop_before_last=False):
    fake = Fake(); previous=[]
    schedule = FIXTURE['schedule'][:-1] if stop_before_last else FIXTURE['schedule']
    for event in schedule:
        fake.frame_count += 40; fake.view(event['view'])
        if event['view'].startswith('learned'): fake.apply_after()
        if event['view'] == 'postbag': fake.consume()
        result, owner = call_without_now(fake,previous)
        assert result.get('review_reason') is None, result
        assert action(result) == event['action']
        previous = (previous + [action(result)])[-8:]
    return fake, previous, result, owner


def test_bridge_emits_journal_field_receipt_only_after_independent_closed_check(clean_bridge):
    fake, previous, result, owner = through_bridge()
    assert result['tm24_complete'] is True and result['field_move_complete'] is True
    assert result['field_move_kind'] == 'lapras-tm24' and owner == 'next'
    assert bridge._COMPLETED == {'tm24'} and not bridge._active()
    assert bridge._CONTROLLERS['tm24'].pending is None and not fake.memory.writes


@pytest.mark.parametrize('case', ['closed_same_frame','pending_after','pending_before','error',
    'not_complete_stage','no_learned_ack','no_consumption','wrong_receipt_frame','wrong_quantity'])
def test_bridge_independently_rejects_forged_completion(case,clean_bridge):
    fake, previous, _, _ = through_bridge(stop_before_last=True)
    controller = bridge._CONTROLLERS['tm24']
    if case == 'pending_before': controller.pending = {'test':'original pending must not vanish'}
    def forged(*args, **kwargs):
        controller.stage = 'complete'; controller.last_frame = kwargs['frame']; controller.pending = None
        if case == 'closed_same_frame': controller.closed_frame = kwargs['frame']
        elif case == 'pending_after': controller.pending = {'test':'new pending'}
        elif case == 'error': controller.error = 'tm24_existing_error'
        elif case == 'not_complete_stage': controller.stage = 'close_start'
        elif case == 'no_learned_ack': controller.learned_acked = False
        elif case == 'no_consumption': controller.consumed = False
        result = controller._complete()
        if case == 'wrong_receipt_frame': result['closed_observation_frame'] -= 1
        elif case == 'wrong_quantity': result['quantity_used'] = True
        return result
    controller.context = forged
    fake.frame_count += 40
    result, owner = call_without_now(fake,previous)
    assert result['phase'] == 'campaign_review' and owner == 'tm24'
    assert not result.get('field_move_complete') and bridge._COMPLETED == set()


def test_loader_does_not_mutate_canonical_package_path_or_register_eol_modules(tmp_path):
    package = importlib.import_module('laya_pokemon')
    before_path, before_modules = tuple(package.__path__), set(sys.modules)
    destination = tmp_path/'laya_pokemon'; destination.mkdir()
    (destination/'tm24_teaching.py').write_bytes((SOURCE/'laya_pokemon/tm24_teaching.py').read_bytes())
    loaded = load('tm24_teaching',tmp_path)
    assert loaded.__name__ == 'laya_pokemon._tm24_eol_candidate'
    assert tuple(package.__path__) == before_path
    assert 'laya_pokemon._tm24_eol_candidate' not in set(sys.modules) - before_modules
    if SOURCE != FORMAL_SRC:
        assert tm.__name__ == '_tm24_staged.tm24_teaching'
        assert all(str(SOURCE) not in entry for entry in package.__path__)
