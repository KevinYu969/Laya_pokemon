"""Two fixed recovery ladders: bounded readonly buffer, never route completion."""
PAIRS = {'league28-fnt-recovery-07': (198, (25, 14), (27, 15), 13, 10),
         'league28-fnt-recovery-09': (194, (26, 8), (27, 7), 10, 13)}
MAX_FRAMES, MAX_WAITS = 240, 8
_WAITS = globals().get('_WAITS', {})
_ERROR = globals().get('_ERROR', None)
_ADDRESSES = (0xD35E, 0xD362, 0xD361, 0xD367, 0xD368, 0xD369, 0xD4E1,
              0xCD38, 0xCD6B, 0xCFC5, 0xD736, 0xD730, 0xD733, 0xD72D, 0xD057)


def _active():
    if (type(_WAITS) is not dict or any(k not in PAIRS or type(v) is not dict
            or type(v.get('done')) is not bool for k, v in _WAITS.items())
            or _ERROR is not None and type(_ERROR) is not str):
        return None
    return {'ladder-settle-error'} if _ERROR else {k for k, v in _WAITS.items() if not v['done']}


def applies(step_id, location):
    active = _active()
    if active is None or active:
        return True
    if type(step_id) is not str or step_id not in PAIRS or step_id in _WAITS:
        return False
    mid, source, landing, old_count, new_count = PAIRS[step_id]
    return location == dict(map_id=mid, x=source[0], y=source[1])


def _fail(reason, step_id):
    global _ERROR
    if _ERROR is not None and (type(_ERROR) is not str or not _ERROR):
        _ERROR = 'registry_unverified'
    elif _ERROR is None:
        _ERROR = reason if type(reason) is str and reason else 'registry_unverified'
    return dict(phase='campaign_review', objective='Wait.', available_actions=['wait'],
                review_reason='victory_ladder_settle_' + _ERROR), step_id


def _wait(step_id):
    return dict(phase='overworld', objective='Wait.', available_actions=['wait'],
                victory_ladder_settle=step_id, suppress_navigation_stall=True,
                suppress_blocked_edge_learning=True), step_id


def preflight(pyboy, state, plan, step_id, *, shared, recovery, native_owner, game_id, peer_owners):
    """No UI/native reads. Active waits intercept any changed/unknown cursor."""
    try:
        active = _active()
        if active is None or _ERROR:
            return _fail(_ERROR or 'registry_unverified', step_id)
        if not applies(step_id, state.get('location') if type(state) is dict else None):
            return None
        if (type(step_id) is not str or step_id not in PAIRS or active and active != {step_id}
                or not recovery.valid_plan(plan) or type(game_id) is not str or game_id != 'game29'
                or pyboy is None or native_owner is not pyboy or type(state) is not dict
                or type(state.get('frame')) is not int or type(pyboy.frame_count) is not int
                or state['frame'] != pyboy.frame_count):
            return _fail('original_step_job_or_native_changed', step_id)
        if (type(peer_owners) is not dict or set(peer_owners) != shared.PEER_NAMES
                or any(type(v) is not set or v for v in peer_owners.values()) or shared._active() != set()):
            return _fail('complete_peer_mutex_required', step_id)
        r = _WAITS.get(step_id)
        loc = state.get('location'); mid, source, landing, old_count, new_count = PAIRS[step_id]
        if (type(loc) is not dict or set(loc) != {'map_id', 'x', 'y'}
                or any(type(v) is not int for v in loc.values())
                or loc not in (dict(map_id=mid, x=source[0], y=source[1]), dict(map_id=mid, x=landing[0], y=landing[1]))
                or r is not None and r['landed'] and (loc['x'], loc['y']) != landing):
            return _fail('fixed_transfer_coordinates_required', step_id)
        battle = state.get('battle_state'); reason = state.get('review_reason')
        if (type(battle) is not dict or type(battle.get('raw')) is not int or battle['raw'] != 0
                or battle.get('active') is not False or battle.get('kind') != 'none'
                or type(battle.get('observation_frame')) is not int or battle['observation_frame'] != state['frame']
                or state.get('phase') not in ('overworld', 'unclassified', 'campaign_review')
                or reason is not None and not (state.get('phase') == 'campaign_review'
                    and reason == 'victory_navigation_native_header_or_objects_unverified'
                    and (r is None or state['frame'] == r['start_frame']))
                or state.get('phase') == 'campaign_review' and reason is None
                or recovery.admitted(plan, step_id, state.get('progress')) != (7,)):
            return _fail('nonbattle_or_review_unverified', step_id)
        if r is not None and (r['native_owner'] is not pyboy or r['plan'] != shared.canonical(plan)
                or r['progress'] != shared.canonical(state['progress']) or state['frame'] < r['last_frame']
                or state['frame']-r['start_frame'] > MAX_FRAMES):
            return _fail('baseline_or_actual_frame_budget_changed', step_id)
        return None
    except Exception:
        return _fail('preflight_unverified', step_id)


def context(pyboy, state, plan, step_id, text, grid, npcs, *, shared, recovery,
            native_owner, game_id, peer_owners):
    """Return WAIT/review, or None to let original navigation prove its own goal."""
    gate = preflight(pyboy, state, plan, step_id, shared=shared, recovery=recovery,
        native_owner=native_owner, game_id=game_id, peer_owners=peer_owners)
    if gate is not None:
        return gate
    if not applies(step_id, state.get('location')):
        return None
    try:
        from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
        from laya_pokemon.progress import read_progress
        from laya_pokemon.campaign_transactions import verified_blank_transaction_world
        from laya_pokemon.observation import PROFILE as TEXT_PROFILE
        from laya_pokemon import victory_road_navigation as nav, world_map, victory_later_boulders_bridge as later
        if (sdk.STATUS_FLAGS3_ADDRESS != 0xD72D or sdk.MAPS.get('victory_road_2f') != 194
                or sdk.MAPS.get('victory_road_3f') != 198):
            return _fail('sdk_source_anchors_unverified', step_id)
        first = tuple(pyboy.memory[a] for a in _ADDRESSES)
        second = tuple(pyboy.memory[a] for a in _ADDRESSES)
        if (first != second or pyboy.frame_count != state['frame']
                or any(type(v) is not int or not 0 <= v <= 255 for v in first)
                or shared.canonical(read_progress(pyboy, sdk)) != shared.canonical(state['progress'])):
            return _fail('fresh_native_or_full_progress_unverified', step_id)
        fresh_npcs = nav.read_victory_road_npcs(pyboy, grid, state['location'],
            world_map_module=world_map, boulder_module=later.boulder,
            overworld_ready=verified_blank_transaction_world(text, grid))
        if shared.canonical(fresh_npcs) != shared.canonical(npcs):
            return _fail('fresh_original_navigation_receipt_required', step_id)
        mid, x, y, tileset, height, width, count, simulated, joy, walk, movement, flags5, flags7, flags3, battle = first
        target_mid, source, landing, old_count, new_count = PAIRS[step_id]
        if (dict(map_id=mid, x=x, y=y) != state['location'] or (tileset, height, width) != (17, 9, 15)
                or count not in (old_count, new_count) or battle != 0 or flags3 != 0 or flags7 != 0
                or simulated != 0 or walk != 0 or joy not in (0, 255) or movement not in (0, 1)
                or flags5 not in (0, 0x24, 0x26)
                or type(text) is not dict or text.get('profile') != TEXT_PROFILE
                or not verified_blank_transaction_world(text, grid)):
            return _fail('only_known_ladder_load_allowed', step_id)
        r = _WAITS.get(step_id)
        if r is None:
            if (count != old_count or (x, y) != source or type(npcs) is not dict
                    or npcs.get('read_valid') is not False or npcs.get('read_error') != 'native_header_or_objects_unverified'):
                return _fail('old_floor_header_receipt_required', step_id)
            r = dict(done=False, native_owner=pyboy, plan=shared.canonical(plan),
                     progress=shared.canonical(state['progress']), start_frame=state['frame'],
                     last_frame=state['frame'], last_packet=None, waits=0, landed=False, history=[])
            _WAITS[step_id] = r
        packet = shared.canonical((state, first, text, grid, npcs))
        if state['frame'] == r['last_frame'] and r['last_packet'] is not None:
            return _wait(step_id) if packet == r['last_packet'] else _fail('same_frame_packet_changed', step_id)
        r['landed'] = r['landed'] or (x, y) == landing
        r['last_frame'], r['last_packet'] = state['frame'], packet
        if ((x, y) == landing and count == new_count and not any((simulated, joy, walk, movement, flags5))
                and type(npcs) is dict and npcs.get('read_valid') is True
                and type(npcs.get('observation_frame')) is int and npcs['observation_frame'] == state['frame']
                and npcs.get('fixed_floor') == target_mid):
            r.update(done=True, settled_frame=state['frame'])
            r['history'].append(dict(frame=state['frame'], raw=first, settled=True))
            return None
        if r['waits'] >= MAX_WAITS:
            return _fail('fresh_wait_budget_exceeded', step_id)
        r['waits'] += 1
        r['history'].append(dict(frame=state['frame'], raw=first, settled=False))
        return _wait(step_id)
    except Exception:
        return _fail('readonly_settle_getter_failed', step_id)
