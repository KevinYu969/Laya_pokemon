"""Exact loaders: this staged path, or tests/test_opponent_intro_gate.py.



python -B -m pytest -p no:cacheprovider --confcutdir=.local/staged-opponent-intro-v2-20261025 \

    .local/staged-opponent-intro-v2-20261025/test_opponent_review_gate.py

"""

from copy import deepcopy

import importlib.util

from pathlib import Path

from types import SimpleNamespace



import pytest

import laya_pokemon



ROOT = Path(laya_pokemon.__file__).resolve().parents[2]

HERE = Path(__file__).resolve()

STAGE = ROOT / '.local/staged-opponent-intro-v2-20261025'

if HERE == STAGE / 'test_opponent_review_gate.py':

    SOURCE = STAGE / 'opponent_review_gate.py'

elif HERE == ROOT / 'tests/test_opponent_intro_gate.py':

    SOURCE = ROOT / 'src/laya_pokemon/opponent_review_gate.py'

else:

    raise RuntimeError('Unknown test installation path; source must be explicit.')





@pytest.fixture

def gate():

    spec = importlib.util.spec_from_file_location('explicit_opponent_gate_under_test', SOURCE)

    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)

    assert Path(module.__file__).resolve() == SOURCE.resolve()

    return module





def packet(species='KOFFING', frame=1):

    return dict(frame=frame, location=dict(map_id=166, x=3, y=4),

                battle_state=dict(raw=2, active=True, kind='trainer', observation_frame=frame,

                                  opponent_species=species, wild_opponent_species=None))





def step(gate):

    return dict(kind='interact', map_id=166, target=[3, 4], face='up', event='beat_blaine',

                opponent_review=gate.PROFILE)





def text(gate, row14='', row16='', silhouette=False):

    cells = [[' '] * 20 for _ in range(18)]

    for y, line in ((14, row14), (16, row16)):

        cells[y] = list(line.ljust(20))

    lines = [line for line in (row14, row16) if len(line.strip()) >= 2]

    rows = [y for y, line in ((14, row14), (16, row16)) if len(line.strip()) >= 2]

    return dict(profile=gate.VISIBLE_PROFILE, cells=cells, lines=lines, line_rows=rows,

                read_valid=not silhouette, alignment_verified=not silhouette,

                window_visible=not silhouette,

                read_error='visible_tile_alignment_incomplete' if silhouette else None)





def signal(gate, owner, frame=1):

    return dict(profile=gate.SIGNAL_PROFILE, read_valid=True, owner_id=id(owner),

                frame_before=frame, frame_after=frame, raw=2, battle_type=0)





def call(gate, owner, frame=1, species='KOFFING', ui=None, now=0, previous=()):

    return gate.context(packet(species, frame), step(gate), text(gate) if ui is None else ui,

                        signal=signal(gate, owner, frame), owner=owner, now=now, previous=previous)





def test_summary_profile_and_empty_lines_are_not_decoder_proof(gate):

    owner = object()

    state = packet('KOFFING', 1738913)

    state.update(observation_profile=gate.VISIBLE_PROFILE, visible_text_candidates=[])

    summary = dict(profile=gate.VISIBLE_PROFILE, lines=[])

    result = gate.context(state, step(gate), summary, signal=signal(gate, owner, 1738913), owner=owner, now=0, previous=())

    assert result['phase'] == 'campaign_review'

    assert result['available_actions'] == ['wait']





@pytest.mark.parametrize('frame', [0, 1, 1738913])

@pytest.mark.parametrize('species', [None, 'KOFFING', 'GROWLITHE'])

def test_intro_blank_wait_never_authorizes_a_and_does_not_mutate_inputs(gate, frame, species):

    owner = object()

    state, route, ui, sig = packet(species, frame), step(gate), text(gate), signal(gate, owner, frame)

    old = deepcopy((state, route, ui, sig))

    result = gate.context(state, route, ui, signal=sig, owner=owner, now=0, previous=())

    assert result['available_actions'] == ['wait'] and result['phase'] == 'battle_animation'

    assert (state, route, ui, sig) == old





def test_exact_real_probe_blank_partial_complete_sequence(gate):

    samples = [(1, text(gate, silhouette=True)), (41, text(gate, silhouette=True)),

               (161, text(gate, ' BLAINE wants', ' to figh')),

               (321, text(gate, ' BLAINE wants', ' to fight!        ▼'))]

    owner = object()

    for frame, ui in samples:

        state = packet('KOFFING', frame)

        result = gate.context(state, step(gate), ui, signal=signal(gate, owner, frame), owner=owner, now=frame / 60, previous=())

        assert result['available_actions'] == (['a', 'wait'] if frame == 321 else ['wait'])

    repeated = call(gate, owner, frame=400, ui=samples[-1][1], now=7, previous=('a',))

    assert repeated['available_actions'] == ['wait']

    assert gate._INTRO['acknowledged'] is True





@pytest.mark.parametrize('row14,row16', [(' BLAINE wants', ' to figh'), (' BLAINE', ''), (' BLAINE wants', ' to fight!')])

def test_partial_source_intro_only_waits(gate, row14, row16):

    assert call(gate, object(), ui=text(gate, row14, row16))['available_actions'] == ['wait']





@pytest.mark.parametrize('row14,row16', [(' KOGA wants', ' to fight!        ▼'), (' BLAINE wants', ' to fight!        ▶'), (' BLAINE wants', ' to fight?        ▼'), (' FIGHT', ' ITEM')])

def test_arbitrary_text_never_authorizes_a(gate, row14, row16):

    result = call(gate, object(), ui=text(gate, row14, row16))

    assert result['phase'] == 'campaign_review' and result['available_actions'] == ['wait']





@pytest.mark.parametrize('key,value', [('read_valid', False), ('alignment_verified', False), ('read_error', 'other'), ('profile', 'other'), ('window_visible', None)])

def test_full_intro_a_requires_complete_decoder_proof(gate, key, value):

    ui = text(gate, ' BLAINE wants', ' to fight!        ▼')

    ui[key] = value

    assert call(gate, object(), ui=ui)['phase'] == 'campaign_review'





def test_stale_visible_lines_cannot_replace_cell_proof(gate):

    ui = text(gate)

    ui['lines'] = [' BLAINE wants', ' to fight!        ▼']

    assert call(gate, object(), ui=ui)['phase'] == 'campaign_review'

    state = packet()

    state['visible_text_candidates'] = []

    assert gate.context(state, step(gate))['phase'] == 'campaign_review'





@pytest.mark.parametrize('key,value', [('raw', True), ('raw', 1), ('battle_type', True), ('battle_type', 2), ('frame_after', 2), ('read_valid', False), ('owner_id', 123)])

def test_raw_type_or_same_frame_or_owner_mismatch_reviews(gate, key, value):

    owner = object()

    sig = signal(gate, owner)

    sig[key] = value

    assert gate.context(packet(), step(gate), text(gate), signal=sig, owner=owner, now=0, previous=())['phase'] == 'campaign_review'





def test_budget_30_waits_then_sticky_review(gate):

    owner = object()

    for i in range(30):

        assert call(gate, owner, frame=i, now=i / 10)['available_actions'] == ['wait']

    result = call(gate, owner, frame=30, now=3)

    assert result['review_reason'] == 'opponent_review_intro_wait_exhausted'

    assert call(gate, owner, frame=31, now=4)['phase'] == 'campaign_review'





def test_60_real_seconds_and_owner_changes_never_reset(gate):

    owner = object()

    call(gate, owner, frame=1738913, now=10)

    assert call(gate, object(), frame=1738914, now=11)['review_reason'] == 'opponent_review_intro_owner_changed'

    assert call(gate, owner, frame=1738915, now=70)['review_reason'] == 'opponent_review_intro_time_exhausted'

    assert gate._INTRO['started'] == 10





@pytest.mark.parametrize('frame', [0, 1])

def test_nonprogressing_frame_is_sticky_review(gate, frame):

    owner = object()

    call(gate, owner, frame=1)

    assert call(gate, owner, frame=frame, now=1)['review_reason'] == 'opponent_review_intro_frame_not_progressing'





def test_clock_regression_reviews(gate):

    owner = object()

    call(gate, owner, now=10)

    assert call(gate, owner, frame=2, now=9)['review_reason'] == 'opponent_review_intro_clock_regressed'





@pytest.mark.parametrize('species', ['GROWLITHE', 'PONYTA', 'RAPIDASH'])

def test_initialized_visible_enemy_hands_back_then_unknown_cannot_reenter_intro(gate, species):

    owner = object()

    call(gate, owner)

    ui = text(gate)

    ui['cells'][0] = list(species.ljust(20)); ui['lines']=[species]; ui['line_rows']=[0]

    assert call(gate, owner, frame=2, species=species, ui=ui, now=1) is None

    assert call(gate, owner, frame=3, now=2)['review_reason'] == 'opponent_review_identity_unverified'





def test_arcanine_always_stops_even_blank_or_bad_proof(gate):

    result = gate.context(packet('ARCANINE'), step(gate))

    assert result['review_reason'] == 'blaine_arcanine_medicine_calibration'

    assert result['available_actions'] == ['wait']





def test_known_species_without_decoder_never_bootstraps(gate):

    assert gate.context(packet('GROWLITHE'), step(gate))['phase'] == 'campaign_review'





def test_initialized_regular_battle_keeps_existing_guards_without_new_clock_or_decoder(gate):

    owner = object()

    ui = text(gate)

    ui['cells'][0] = list('GROWLITHE'.ljust(20)); ui['lines']=['GROWLITHE']; ui['line_rows']=[0]

    assert call(gate, owner, species='GROWLITHE', ui=ui, now=0) is None

    assert gate.context(packet('RAPIDASH', 5000), step(gate), owner=owner, now=1000) is None

    assert gate.context(packet('ARCANINE', 5001), step(gate), owner=owner)['review_reason'] == 'blaine_arcanine_medicine_calibration'

    assert gate.context(packet('KOFFING', 5002), step(gate), owner=owner)['phase'] == 'campaign_review'





def test_other_owner_cannot_reset_initialized_gate(gate):

    owner = object()

    ui = text(gate)

    ui['cells'][0] = list('GROWLITHE'.ljust(20)); ui['lines']=['GROWLITHE']; ui['line_rows']=[0]

    assert call(gate, owner, species='GROWLITHE', ui=ui) is None

    assert gate.context(packet('GROWLITHE', 2), step(gate), owner=object())['review_reason'] == 'opponent_review_intro_owner_changed'





def test_reload_does_not_reset_owner_waits_or_single_a(gate):

    owner = object()

    ui = text(gate, ' BLAINE wants', ' to fight!        ▼')

    assert call(gate, owner, ui=ui)['available_actions'] == ['a', 'wait']

    before = gate._INTRO

    exec(compile(SOURCE.read_text(encoding='utf-8'), str(SOURCE), 'exec'), gate.__dict__)

    assert gate._INTRO is before and gate._INTRO['owner'] is owner

    assert call(gate, owner, frame=2, ui=ui, now=1, previous=('a',))['available_actions'] == ['wait']





def test_silhouette_is_only_exact_blank_named_alignment_failure(gate):

    owner = object()

    ui = text(gate, silhouette=True)

    assert call(gate, owner, ui=ui)['available_actions'] == ['wait']

    ui['cells'][0][0] = 'X'

    assert call(gate, owner, frame=2, ui=ui, now=1)['phase'] == 'campaign_review'





def test_only_acknowledged_exact_known_sendout_prefix_may_wait(gate):

    owner = object()

    wants = text(gate, ' BLAINE wants', ' to fight!        ▼')

    assert call(gate, owner, ui=wants)['available_actions'] == ['a', 'wait']

    for frame, first, second in ((2, ' BLAINE sent', ''), (3, ' BLAINE sent', ' out GRO'),

                                  (4, ' BLAINE sent', ' out GROWLITHE')):

        result = call(gate, owner, frame=frame, species='GROWLITHE', ui=text(gate, first, second), now=frame, previous=('a',) if frame == 2 else ('a',) + ('wait',) * (frame - 2))

        assert result['available_actions'] == ['wait'] and result['phase'] == 'battle_animation'

    assert call(gate, owner, frame=5, species='GROWLITHE', ui=text(gate, ' BLAINE sent', ' out GROWLITHE!'), now=5, previous=('a', 'wait', 'wait', 'wait'))['battle_tactic'] == 'observed_native_blaine_sendout'





def test_sendout_prefix_without_ack_or_wrong_ram_cannot_continue(gate):

    owner = object()

    ui = text(gate, ' BLAINE sent', ' out GRO')

    assert call(gate, owner, species='GROWLITHE', ui=ui)['phase'] == 'campaign_review'

    wants = text(gate, ' BLAINE wants', ' to fight!        ▼')

    assert call(gate, owner, frame=2, ui=wants, now=1)['available_actions'] == ['a', 'wait']

    assert call(gate, owner, frame=3, species='KOFFING', ui=ui, now=2)['phase'] == 'campaign_review'





def test_real_laya_policy_candidate_contract_without_model(gate):

    from laya_pokemon.policy import LayaPolicy

    owner = object()

    offered = call(gate, owner, ui=text(gate, ' BLAINE wants', ' to fight!        ▼'))

    policy = LayaPolicy.__new__(LayaPolicy)

    policy.cache_enabled = False

    seen = []

    def choose_options(state, instructions, criteria):

        seen.append(tuple(criteria))

        return dict(action='a', model_ms=0.0, raw={})

    policy.choose_options = choose_options

    assert policy.choose(offered)['action'] == 'a'

    assert set(seen[0]) == {'a', 'wait'}

    assert gate._INTRO['acknowledged'] is False





def test_wait_receipt_reoffers_then_actual_a_acknowledges_once(gate):

    owner = object(); ui = text(gate, ' BLAINE wants', ' to fight!        ▼')

    assert call(gate, owner, ui=ui)['available_actions'] == ['a', 'wait']

    assert gate._INTRO['acknowledged'] is False and gate._INTRO['pending_frame'] == 1

    for frame in (2, 3, 4):

        assert call(gate, owner, frame=frame, ui=ui, previous=['wait'] * (frame - 1), now=frame)['available_actions'] == ['a', 'wait']

        assert gate._INTRO['acknowledged'] is False

        assert gate._INTRO['started'] == 0 and gate._INTRO['waits'] == frame - 1

    result = call(gate, owner, frame=5, ui=ui, previous=['wait'] * 3 + ['a'], now=5)

    assert result['available_actions'] == ['wait'] and gate._INTRO['acknowledged'] is True

    assert call(gate, owner, frame=6, ui=ui, previous=['wait'] * 3 + ['a', 'wait'], now=6)['available_actions'] == ['wait']





@pytest.mark.parametrize('frame', [0, 1])

def test_old_or_same_frame_cannot_acknowledge_offered_a(gate, frame):

    owner = object(); ui = text(gate, ' BLAINE wants', ' to fight!        ▼')

    call(gate, owner, ui=ui)

    assert call(gate, owner, frame=frame, ui=ui, previous=['a'], now=1)['phase'] == 'campaign_review'

    assert gate._INTRO['acknowledged'] is False





def test_pending_offer_reload_wait_history_and_rolling_eight_receipt(gate):

    owner = object(); ui = text(gate, ' BLAINE wants', ' to fight!        ▼')

    history = ['wait'] * 8

    call(gate, owner, ui=ui, previous=history)

    saved = gate._INTRO

    exec(compile(SOURCE.read_text(encoding='utf-8'), str(SOURCE), 'exec'), gate.__dict__)

    assert gate._INTRO is saved and not saved['acknowledged']

    assert call(gate, owner, frame=2, ui=ui, previous=history, now=1)['available_actions'] == ['a', 'wait']

    assert call(gate, owner, frame=3, ui=ui, previous=history[-7:] + ['a'], now=2)['available_actions'] == ['wait']

    assert saved['acknowledged'] and saved['waits'] == 2





def test_reoffers_consume_real_wait_budget_without_reset(gate):

    owner = object(); ui = text(gate, ' BLAINE wants', ' to fight!        ▼')

    call(gate, owner, ui=ui)

    for frame in range(2, 31):

        assert call(gate, owner, frame=frame, ui=ui, previous=['wait'] * min(frame - 1, 8), now=frame / 10)['available_actions'] == ['a', 'wait']

    assert call(gate, owner, frame=31, ui=ui, previous=['wait'] * 8, now=4)['review_reason'] == 'opponent_review_intro_wait_exhausted'

    assert gate._INTRO['started'] == 0 and gate._INTRO['acknowledged'] is False





def test_offer_without_a_cannot_initialize_from_complete_sendout(gate):

    owner = object(); ui = text(gate, ' BLAINE wants', ' to fight!        ▼')

    call(gate, owner, ui=ui)

    result = call(gate, owner, frame=2, species='GROWLITHE', ui=text(gate, ' BLAINE sent', ' out GROWLITHE!'), previous=['wait'], now=1)

    assert result['available_actions'] == ['wait'] and not gate._INTRO['initialized']





@pytest.mark.parametrize('previous', [None, 'a', [False], ['wrong']])

def test_previous_requires_actual_action_sequence(gate, previous):

    owner = object(); ui = text(gate, ' BLAINE wants', ' to fight!        ▼')

    assert call(gate, owner, ui=ui, previous=previous)['review_reason'] == 'opponent_review_intro_previous_unverified'





def test_reader_has_no_tick_input_or_memory_write(gate):

    class ReadOnlyMemory:

        def __getitem__(self, address):

            return {0xD057: 2, 0xD05A: 0}[address]

        def __setitem__(self, address, value):

            raise AssertionError('memory write forbidden')

    owner = SimpleNamespace(frame_count=0, memory=ReadOnlyMemory())

    result = gate.read_intro_signal(owner)

    assert result['read_valid'] is True and result['raw'] == 2 and result['battle_type'] == 0

    assert result['frame_before'] == result['frame_after'] == 0





def test_reader_detects_frame_or_byte_change(gate):

    class ChangingFrame:

        memory = {0xD057: 2, 0xD05A: 0}

        count = 0

        @property

        def frame_count(self):

            self.count += 1

            return self.count

    assert gate.read_intro_signal(ChangingFrame())['read_valid'] is False

    class ChangingMemory:

        count = 0

        def __getitem__(self, address):

            self.count += 1

            return 2 if self.count == 1 else 0

    assert gate.read_intro_signal(SimpleNamespace(frame_count=1, memory=ChangingMemory()))['read_valid'] is False



def test_actual_sendout_receipt_after_engineering_pause_does_not_send_another_a(gate):
    owner=object()
    wants=text(gate, ' BLAINE wants', ' to fight!        ▼')
    assert call(gate,owner,ui=wants,previous=(),now=0)['available_actions']==['a','wait']
    result=call(gate,owner,frame=129,species='GROWLITHE',ui=text(gate,' BLAINE sent',' out GROWLITHE!'),previous=('a',),now=3600)
    assert result['available_actions']==['wait'] and gate._INTRO['initialized']
    assert gate._INTRO['started']==0 and gate._INTRO['acknowledged']
