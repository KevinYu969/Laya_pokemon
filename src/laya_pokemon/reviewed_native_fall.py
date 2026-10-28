"""One source-bound native hole fall. Readonly observations; WAIT hints only.

The 600-frame / 20-fresh-WAIT limits are engineering caps, not source timing.
Root must call preflight before reading UI, before waypoint's next_map shortcut,
and before either field dispatcher. Never supplies or executes game input.
"""
from copy import deepcopy

KIND = 'reviewed_native_fall_198_194_20261028'
PROFILE = 'red-en-reviewed-native-fall-v1'
SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
GAME_ID = 'game29'
STEP_ID = 'league28-fnt-recovery-02'
HOLE_ID = 'league28-fnt-recovery-01'
NEXT_ID = 'league28-fnt-recovery-03'
CURSORS = frozenset((STEP_ID, NEXT_ID, 'league28-fnt-recovery-04'))
FRAME = 7513
LOCATION = dict(map_id=198, x=23, y=15)
LANDING = dict(map_id=194, x=22, y=16)
LAYOUT = 'reviewed_3f_hole_aux8_13_13_20261028'
MAX_FRAMES, MAX_WAITS = 600, 20
SOURCE_PROGRESS_SHA256 = '15bed7a5c90f0d9ec756e1c3a4428ef1f0c270fa9d8e78bdc276cae207bf1a0e'
EVIDENCE = dict(
    review_sha256='40bcfe4dcd399cb837dc05821484da4aa0f9df07579174e078529bf77f39cd0a',
    state_sha256='a49b27c4868ca9da561bb9610553fd1a8afdc47d38d02685e75cb2e4c3e795ad',
    preflight_sha256='858dc6a8ed19b9f29aec39ce30cebcc95983451cac1fa8532ceb291e094af0a4')
_KEYS = {'kind', 'game_id', 'source_frame', 'source_location', 'landing_location',
         'original_step_id', 'original_step_sha256', 'training_job_sha256',
         'steps_sha256', 'recovery_capsule_sha256', 'source_progress_sha256', 'evidence'}
_PRESERVED = ('owner', 'started', 'last_now', 'step_started', 'calls', 'waits',
              'requests', 'last_frame', 'push_index', 'pending', 'baseline',
              'flags_baseline', 'object_baseline', 'closed_frame', 'final_player',
              'suspended', 'battle_returns', 'contact_arm_seen', 'native_script_seen',
              'dust_seen', 'error', 'reviewed_fainted_bench', 'source_layout',
              'source_layout_contract')
_SESSIONS = globals().get('_SESSIONS', {})
_ERRORS = globals().get('_ERRORS', {})


def _active():
    """Own original step02 while waiting or sticky review; done retains history only."""
    if type(_SESSIONS) is not dict or type(_ERRORS) is not dict:
        return None
    if (any(k != (GAME_ID, STEP_ID) or type(v) is not dict or type(v.get('done')) is not bool
            for k, v in _SESSIONS.items())
            or any(k != (GAME_ID, STEP_ID) or type(v) is not str or not v for k, v in _ERRORS.items())):
        return None
    return {STEP_ID} if _ERRORS or any(not v['done'] for v in _SESSIONS.values()) else set()


def applies(plan, step_id):
    active = _active()
    if active is None or active:
        return True  # Active/unknown ownership cannot be bypassed by a new cursor.
    if (GAME_ID, STEP_ID) in _SESSIONS:
        return type(step_id) is str and step_id in CURSORS
    return (type(plan) is dict and 'reviewed_fnt_recovery' in plan
            and type(step_id) is str and step_id == STEP_ID)


def _fail(reason):
    if type(_ERRORS) is dict:
        reason = _ERRORS.setdefault((GAME_ID, STEP_ID), reason)
    return dict(phase='campaign_review', objective='Wait.', available_actions=['wait'],
                review_reason='reviewed_native_fall_' + reason), STEP_ID


def _wait():
    return dict(phase='overworld', objective='Wait.', available_actions=['wait'],
                native_fall_owner_step=STEP_ID, native_fall_kind=KIND,
                suppress_navigation_stall=True, suppress_blocked_edge_learning=True), STEP_ID


def _binding(plan, capsule, source_evidence, shared, recovery):
    if (not recovery.valid_plan(plan) or type(capsule) is not dict or set(capsule) != _KEYS
            or shared.canonical(source_evidence) != shared.canonical(EVIDENCE)
            or shared.canonical(capsule.get('evidence')) != shared.canonical(EVIDENCE)):
        return None
    fixed = dict(kind=KIND, game_id=GAME_ID, source_frame=FRAME, source_location=LOCATION,
                 landing_location=LANDING, original_step_id=STEP_ID,
                 source_progress_sha256=SOURCE_PROGRESS_SHA256)
    if any(shared.canonical(capsule.get(k)) != shared.canonical(v) for k, v in fixed.items()):
        return None
    step = next(s for s in plan['steps'] if s['id'] == STEP_ID)
    hashes = dict(original_step_sha256=shared.canonical_sha256(step),
                  training_job_sha256=shared.canonical_sha256(plan['training_job']),
                  steps_sha256=shared.canonical_sha256(plan['steps']),
                  recovery_capsule_sha256=shared.canonical_sha256(plan['reviewed_fnt_recovery']))
    if any(type(capsule.get(k)) is not str or capsule[k] != v for k, v in hashes.items()):
        return None
    return shared.canonical(capsule)


def _original(bridge, shared, pyboy, plan):
    """Recheck the real completed native bridge packet, not just its completed bit."""
    try:
        if bridge._active() != set() or HOLE_ID not in bridge._COMPLETED:
            return None
        c = bridge._CONTROLLERS[HOLE_ID]
        binding = bridge._BINDINGS[HOLE_ID]
        step = next(s for s in plan['steps'] if s['id'] == HOLE_ID)
        if (binding != (bridge.MECHANIC, bridge._canonical(step), bridge._canonical(plan['training_job']))
                or c.owner != HOLE_ID or c.case_key != '3f_hole'
                or c.case != bridge.boulder.CASES['3f_hole'] or c.contract != c.case
                or c.pushes != c.case['pushes'] or type(c.reviewed_fainted_bench) is not tuple
                or c.reviewed_fainted_bench != (7,) or type(c.reviewed_fainted_bench[0]) is not int
                or c.source_layout != LAYOUT or c.source_layout_contract != LAYOUT):
            return None
        if (not shared._clock(c.started) or not shared._clock(c.last_now) or not shared._clock(c.step_started)
                or c.last_now < c.started or c.last_now < c.step_started
                or c.last_now-c.started > bridge.boulder.MAX_SECONDS
                or c.last_now-c.step_started > bridge.boulder.MAX_STEP_SECONDS
                or not bridge.boulder._int(c.calls, 1, bridge.boulder.MAX_CALLS)
                or not bridge.boulder._int(c.waits, 0, bridge.boulder.MAX_STEP_WAITS)
                or not bridge.boulder._int(c.requests, 0, bridge.boulder.MAX_REQUESTS)):
            return None
        review = c.source_layout_review_record
        if (type(review) is not dict or review.get('native_owner') is not pyboy
                or review.get('original_controller') is not c or review.get('binding') is not binding
                or review.get('released') is not True or getattr(c, 'source_layout_review_error', None)
                or type(c.source_layout_review_history) is not list or not c.source_layout_review_history
                or shared.canonical_sha256(c.source_layout_review_history[-1]) != review.get('history_sha256')):
            return None
        packet = c.last_packet
        if type(packet) is not tuple or len(packet) != 7:
            return None
        state, text, grid, signal, previous, owner, ready = packet
        if (type(state) is not dict or type(state.get('frame')) is not int
                or state['frame'] != c.last_frame or not state['frame'] < FRAME
                or shared.canonical_sha256(state.get('progress')) != SOURCE_PROGRESS_SHA256
                or c.baseline != bridge.boulder._resources(state['progress'])
                or not bridge._completion('3f_hole', c.case, c, state.get('location'), signal,
                                          text, grid, state['frame'])):
            return None
        return c, binding, packet, {k: deepcopy(getattr(c, k)) for k in _PRESERVED}
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, StopIteration, RecursionError):
        return None


def preflight(pyboy, state, plan, step_id, **kwargs):
    """Fail closed even when an existing registry or bound packet is malformed."""
    try:
        return _preflight(pyboy, state, plan, step_id, **kwargs)
    except Exception:
        return _fail('preflight_identity_or_registry_unverified')


def _preflight(pyboy, state, plan, step_id, *, bridge, shared, recovery, native_owner,
              game_id, review_capsule, source_evidence, peer_owners):
    """Call before text/grid or native getters. A truthy result must be returned."""
    active = _active()
    if active is None:
        return _fail('registries_unverified')
    if _ERRORS:
        return _fail(next(iter(_ERRORS.values())))
    record = _SESSIONS.get((GAME_ID, STEP_ID))
    if not applies(plan, step_id):
        return None
    if (pyboy is None or native_owner is not pyboy or type(game_id) is not str or game_id != GAME_ID
            or type(state) is not dict or type(state.get('frame')) is not int
            or type(pyboy.frame_count) is not int or pyboy.frame_count != state['frame']):
        return _fail('native_frame_unverified')
    try:
        bound = _binding(plan, review_capsule, source_evidence, shared, recovery)
    except (KeyError, TypeError, ValueError, StopIteration, RecursionError):
        bound = None
    if bound is None:
        return _fail('exact_review_capsule_required')
    # Recheck original identities even when done, but allow a later genuine owner.
    if record is not None and (record.get('native_owner') is not pyboy
            or record.get('capsule_canonical') != bound
            or bridge._CONTROLLERS.get(HOLE_ID) is not record.get('controller')
            or bridge._BINDINGS.get(HOLE_ID) is not record.get('binding')
            or HOLE_ID not in bridge._COMPLETED
            or record['controller'].last_packet is not record.get('original_packet')
            or any(getattr(record['controller'], k, None) != v for k, v in record['preserved'].items())
            or shared.canonical(record['original_packet']) != record.get('original_packet_canonical')):
        return _fail('original_native_controller_or_receipt_changed')
    if record is not None and record['done']:
        if _original(bridge, shared, pyboy, plan) is None:
            return _fail('completed_original_native_receipt_changed')
        if type(record.get('completed_frame')) is not int or state['frame'] < record['completed_frame']:
            return _fail('completed_frame_changed')
        if (type(record.get('receipt')) is not dict
                or shared.canonical_sha256(record['receipt']) != record.get('receipt_sha256')):
            return _fail('closed_receipt_changed')
        return _wait() if state['frame'] == record['completed_frame'] else None
    if type(step_id) is not str or step_id not in CURSORS or record is None and step_id != STEP_ID:
        return _fail('fall_cursor_changed')
    if (type(peer_owners) is not dict or set(peer_owners) != shared.PEER_NAMES
            or any(type(v) is not set or v for v in peer_owners.values()) or shared._active() != set()):
        return _fail('complete_peer_mutex_required')
    original = _original(bridge, shared, pyboy, plan)
    if original is None:
        return _fail('genuine_completed_hole_receipt_required')
    if record is not None and (original[0] is not record['controller'] or original[1] is not record['binding']
                               or original[2] is not record['original_packet']):
        return _fail('original_owner_changed')
    frame = state['frame']
    if (frame < FRAME or frame - FRAME > MAX_FRAMES or record is None and frame != FRAME
            or record is not None and frame < record['last_frame']):
        return _fail('actual_frame_budget_exceeded_or_reversed')
    loc = state.get('location')
    if (type(loc) is not dict or set(loc) != {'map_id', 'x', 'y'}
            or any(type(v) is not int for v in loc.values()) or loc not in (LOCATION, LANDING)
            or record is None and loc != LOCATION or record is not None and record['landed'] and loc != LANDING):
        return _fail('only_source_and_landing_allowed')
    battle = state.get('battle_state')
    if (type(battle) is not dict or type(battle.get('raw')) is not int or battle['raw'] != 0
            or battle.get('kind') != 'none' or battle.get('active') is not False
            or type(battle.get('observation_frame')) is not int or battle['observation_frame'] != frame):
        return _fail('nonbattle_packet_required')
    reason = state.get('review_reason')
    if (state.get('phase') not in ('overworld', 'unclassified', 'campaign_review')
            or reason is not None and not (frame == FRAME and loc == LOCATION
                and state.get('phase') == 'campaign_review' and reason == 'victory_navigation_closed_world_required')
            or state.get('phase') == 'campaign_review' and reason is None):
        return _fail('unknown_review_or_ui_retained')
    if shared.canonical_sha256(state.get('progress')) != SOURCE_PROGRESS_SHA256:
        return _fail('full_progress_changed')
    return None


def read_observation(pyboy, frame, *, bridge, constants):
    """Fixed source getter addresses/SDK anchors; double read without ticks."""
    b = bridge.boulder
    try:
        if not b._anchors(constants) or type(frame) is not int or type(pyboy.frame_count) is not int or pyboy.frame_count != frame:
            return None
        addresses = b._addresses('3f_hole')
        def sample():
            return ({k: pyboy.memory[a] for k, a in addresses.items()},
                    [pyboy.memory[0xD5A6 + i] for i in range(32)])
        first, second = sample(), sample()
        if (first != second or type(pyboy.frame_count) is not int or pyboy.frame_count != frame
                or any(not b._int(v) for v in first[0].values())
                or any(not b._int(v) for v in first[1])):
            return None
        raw, flags = first
        loc = {k: raw[k] for k in ('map_id', 'x', 'y')}
        return dict(profile=PROFILE, source_commit=SOURCE_COMMIT, observation_frame=frame,
                    location=loc, raw=raw, toggle_flags=flags)
    except Exception:
        return None


def _blank_native_text(text, *, allow_disabled=False):
    from laya_pokemon.observation import PROFILE as TEXT_PROFILE
    if (type(text) is not dict or text.get('profile') != TEXT_PROFILE
            or text.get('lines') != [] or text.get('line_rows') != []):
        return False
    if (allow_disabled is True and text.get('cells') == []
            and text.get('read_valid') is False and text.get('alignment_verified') is False
            and text.get('window_visible') is None and text.get('read_error') == 'visible_display_disabled'):
        return True
    if (type(text.get('cells')) is not list or len(text['cells']) != 18
            or any(type(r) is not list or len(r) != 20 or any(type(c) is not str or c != ' ' for c in r)
                   for r in text['cells'])):
        return False
    return (text.get('read_valid') is True and text.get('alignment_verified') is True
            and text.get('window_visible') is False and text.get('read_error') is None)


def _landing_closed(pyboy, state, text, grid, bridge, sdk):
    from laya_pokemon.campaign_transactions import verified_blank_transaction_world
    b = bridge.boulder
    signal = b.read_later_boulder_observation(pyboy, state['frame'], sdk, case_key='2f_switch2')
    if (signal.get('read_valid') is not True or signal.get('read_error') is not None
            or signal.get('location') != LANDING or signal.get('idle') is not True
            or signal.get('native_push_busy') is not False or signal.get('event') is not False
            or signal['raw']['gate1'] != 21 or signal['raw']['gate2'] != 37
            or not all(b._event(b.CASES[k], signal['raw']) for k in ('2f_switch1', '3f_switch1', '3f_hole'))
            or not b._hidden(signal['toggle_flags'], 0x7A) or b._hidden(signal['toggle_flags'], 0x60)
            or any((signal['objects'][s - 1]['x'], signal['objects'][s - 1]['y']) != p
                   for s, p in b.CASES['2f_switch2']['source_stones'].items())
            or not verified_blank_transaction_world(text, grid)
            or not b._grid(grid, b.CASES['2f_switch2'], (22, 16), state['frame'])):
        return None
    return deepcopy(signal)


def context(pyboy, state, plan, step_id, text, grid, *, bridge, shared, recovery,
            native_owner, game_id, review_capsule, source_evidence, peer_owners):
    args = dict(bridge=bridge, shared=shared, recovery=recovery, native_owner=native_owner,
                game_id=game_id, review_capsule=review_capsule, source_evidence=source_evidence,
                peer_owners=peer_owners)
    gate = preflight(pyboy, state, plan, step_id, **args)
    if gate is not None:
        return gate
    if not applies(plan, step_id):
        return None
    record = _SESSIONS.get((GAME_ID, STEP_ID))
    if record is not None and record['done']:
        return None
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
    from laya_pokemon.progress import read_progress
    try:
        signal = read_observation(pyboy, state['frame'], bridge=bridge, constants=sdk)
        progress = read_progress(pyboy, sdk)
        if (signal is None or signal['location'] != state['location'] or pyboy.frame_count != state['frame']
                or shared.canonical_sha256(progress) != SOURCE_PROGRESS_SHA256
                or shared.canonical(progress) != shared.canonical(state['progress'])
                or recovery.admitted(plan, STEP_ID, progress) != (7,)):
            return _fail('fresh_native_full_progress_unverified')
        raw = signal['raw']
        if (raw['battle_raw'] != 0 or raw['mode'] != 0 or raw['simulated'] != 0
                or raw['walk_counter'] != 0 or raw['movement_flags'] != 0
                or raw['dungeon_destination'] != 194 or raw['dungeon_which'] != 2
                or (raw['height'], raw['width']) != (9, 15)
                or raw['tileset'] != 17 and not (record is not None and state['location'] == LANDING
                    and raw['tileset'] == 0 and raw['object_count'] == 10 and grid is None)
                or raw['object_count'] not in ((10,) if state['location'] == LOCATION else (10, 13))
                or raw['flags5'] != 0 or raw['flags7'] != 0
                or raw['joy_ignore'] not in (0, 255) or not raw['event3f_raw'] & 64
                or not bridge.boulder._hidden(signal['toggle_flags'], 0x7A)
                or bridge.boulder._hidden(signal['toggle_flags'], 0x60)
                or not _blank_native_text(text, allow_disabled=(record is not None
                    and state['location'] == LANDING and raw['joy_ignore'] == 255
                    and bool(raw['flags6'] & 16) and grid is None))):
            return _fail('only_proven_native_fall_transition_allowed')
        if record is None:
            source = bridge.boulder.read_later_boulder_observation(pyboy, state['frame'], sdk, case_key='3f_hole')
            if (source.get('read_valid') is not True or source.get('read_error') is not None
                    or source.get('location') != LOCATION or source.get('event') is not True
                    or source['stone']['slot'] != 10 or source['stone']['hidden'] is not True
                    or (source['stone']['x'], source['stone']['y']) != (23, 15)
                    or not raw['flags3'] & 16 or not raw['flags6'] & 16
                    or raw['flags3'] & ~16 or raw['flags6'] & (8 | 64)
                    or raw['dungeon_destination'] != 194 or raw['dungeon_which'] != 2
                    or raw['gate1'] != 29 or source['native_push_busy'] is not False):
                return _fail('native_hole_entry_not_proven')
            original = _original(bridge, shared, pyboy, plan)
            if original is None:
                return _fail('original_receipt_changed_during_getters')
            if (source['toggle_flags'] != original[2][3]['toggle_flags']
                    or bridge.boulder._other_objects(source['objects'], 10) != original[0].object_baseline
                    or raw['flags1'] & ~1 != original[0].flags_baseline & ~1
                    or not all(bridge.boulder._event(bridge.boulder.CASES[k], raw)
                               for k in ('2f_switch1', '3f_switch1'))
                    or bridge.boulder._event(bridge.boulder.CASES['2f_switch2'], raw)):
                return _fail('completed_hole_objects_or_flags_changed')
            record = dict(done=False, native_owner=pyboy, capsule_canonical=shared.canonical(review_capsule),
                          controller=original[0], binding=original[1], original_packet=original[2],
                          original_packet_canonical=shared.canonical(original[2]), preserved=original[3],
                          source_signal=deepcopy(source), baseline_progress=deepcopy(progress),
                          entry=deepcopy(signal), last_frame=FRAME, last_packet=None, waits=0,
                          landed=False, first_closed_frame=None, history=[])
            _SESSIONS[(GAME_ID, STEP_ID)] = record
        if (signal['toggle_flags'] != record['entry']['toggle_flags']
                or raw['event2f_raw'] != record['entry']['raw']['event2f_raw']
                or raw['event3f_raw'] != record['entry']['raw']['event3f_raw']):
            return _fail('hole_events_or_hidden_flags_changed')
        # Unknown native flags cannot be excused by blank pixels. Entry bits may
        # clear during the source-defined transfer; Strength may normally clear.
        if ((raw['flags1'] & ~1) != (record['entry']['raw']['flags1'] & ~1)
                or raw['flags3'] & ~16
                or (raw['flags6'] & ~0x14) != (record['entry']['raw']['flags6'] & ~0x14)
                or state['location'] == LOCATION and (record['landed'] or not raw['flags3'] & 16)):
            return _fail('foreign_native_transition')
        packet = shared.canonical((state, signal, text, grid))
        if state['frame'] == record['last_frame'] and record['last_packet'] is not None:
            return _wait() if packet == record['last_packet'] else _fail('same_frame_packet_changed')
        closed = None
        if state['location'] == LANDING:
            record['landed'] = True
            if not raw['flags3'] & 0x18 and not raw['flags6'] & 0x5C and raw['joy_ignore'] == 0:
                closed = _landing_closed(pyboy, state, text, grid, bridge, sdk)
                if grid is not None and closed is None:
                    return _fail('landing_source_geometry_unverified')
        record['last_frame'], record['last_packet'] = state['frame'], packet
        if closed is not None:
            if record['first_closed_frame'] is None:
                record['first_closed_frame'] = state['frame']
                record['first_closed_signal'] = closed
            elif state['frame'] > record['first_closed_frame']:
                receipt = dict(kind=KIND, original_step_id=STEP_ID, source_frame=FRAME,
                               source_location=deepcopy(LOCATION), landing_location=deepcopy(LANDING),
                               first_closed_frame=record['first_closed_frame'], completed_frame=state['frame'],
                               capsule=deepcopy(review_capsule), actual_entry=deepcopy(record['entry']),
                               source_hole=deepcopy(record['source_signal']), actual_closed=closed,
                               actual_progress=deepcopy(progress), full_progress_sha256=SOURCE_PROGRESS_SHA256,
                               fresh_waits=record['waits'], history=deepcopy(record['history']))
                record.update(done=True, completed_frame=state['frame'], receipt=receipt,
                              receipt_sha256=shared.canonical_sha256(receipt))
                return dict(phase='overworld', objective='Wait.', available_actions=['wait'],
                            field_move_complete=True, field_move_kind='reviewed-native-fall',
                            native_fall_complete=True, native_fall_receipt=deepcopy(receipt),
                            suppress_navigation_stall=True, suppress_blocked_edge_learning=True), NEXT_ID
        else:
            record['first_closed_frame'] = None
            record.pop('first_closed_signal', None)
        if record['waits'] >= MAX_WAITS:
            return _fail('fresh_wait_budget_exceeded')
        record['waits'] += 1
        record['history'].append(dict(frame=state['frame'], location=deepcopy(state['location']),
                                      native=deepcopy(signal), closed_world=closed is not None))
        return _wait()
    except Exception:
        return _fail('readonly_native_observation_failed')
