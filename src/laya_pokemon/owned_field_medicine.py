"""One normal Hyper transaction under one retained later-boulder owner.

Read-only controller coordination. No emulator construction, input, ticks, RAM
writes, plan edits, original owner recreation, or implicit attrition exception.
The root must pass its existing native instance and a complete owner inventory
before reading UI. All failures remain sticky across module reloads.
"""
from copy import deepcopy
from hashlib import sha256
import json
import math
import re

KIND = 'owned_later_boulder_hyper_v1'
PEER_NAMES = frozenset(('victory_later_boulder', 'overworld_hyper',
    'victory_strength', 'victory_first_boulder', 'route23', 'route23_land_guards',
    'league_training_batch', 'league_training_proof', 'battle_medicine',
    'trainer_medicine_ui', 'mansion_secret_key', 'mansion_statue',
    'mansion_transition_ready', 'mansion_native_landing', 'route21_water',
    'pallet_surf', 'fly_pallet', 'fly_viridian', 'safari_entry', 'hm_teaching',
    'vending', 'saffron_guard', 'silph_card', 'lapras', 'player_pc',
    'cinnabar_purchase', 'campaign_transactions', 'safari_run',
    'capture_transaction', 'native_wait', 'legacy_field', 'legacy_gym', 'tm24_teaching'))
_SESSIONS = globals().get('_SESSIONS', {})
_ERRORS = globals().get('_ERRORS', {})
_REGISTRY_ERROR = globals().get('_REGISTRY_ERROR')
_CAPSULE_KEYS = frozenset(('kind', 'original_game', 'original_step_id',
    'original_step_sha256', 'training_job_sha256', 'original_frame',
    'original_location', 'target_species', 'item', 'quantity', 'child_step_id',
    'evidence'))
_SHA = re.compile(r'[0-9a-f]{64}')
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}')


def _active():
    """Completed interrupts release; unresolved errors continue owning WAIT."""
    global _REGISTRY_ERROR
    if _REGISTRY_ERROR is not None:return None
    if (type(_SESSIONS) is not dict or type(_ERRORS) is not dict
            or any(type(k) is not str or not k for d in (_SESSIONS,_ERRORS) for k in d)
            or any(type(v) is not dict or type(v.get('done')) is not bool
                or v.get('error') is not None and type(v['error']) is not str for v in _SESSIONS.values())
            or any(type(v) is not str or not v for v in _ERRORS.values())):
        _REGISTRY_ERROR=_REGISTRY_ERROR or 'registry_unverified'
        return None
    return {k for k,v in _SESSIONS.items() if not v['done']}|set(_ERRORS)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False)


def canonical_sha256(value):
    return sha256(canonical(value).encode('utf-8')).hexdigest()


def _integer(v, lo=0, hi=2**63-1):
    return type(v) is int and lo <= v <= hi


def _clock(v):
    return type(v) in (float, int) and math.isfinite(v) and v >= 0


def _review(reason, step_id):
    global _REGISTRY_ERROR
    if type(_SESSIONS) is not dict or type(_ERRORS) is not dict:
        _REGISTRY_ERROR = _REGISTRY_ERROR or reason
    else:
        reason = _ERRORS.setdefault(step_id, reason)
        record = _SESSIONS.get(step_id)
        if type(record) is dict:
            record['error'] = record.get('error') or reason
            reason = record['error']
    return dict(phase='campaign_review', objective='Wait.', available_actions=['wait'],
        review_reason='owned_field_medicine_' + reason, route_step=step_id), step_id


def _wait(step_id, reason):
    return dict(phase='overworld_medicine_wait', objective='Wait.',
        available_actions=['wait'], owned_field_medicine_reason=reason,
        owned_field_medicine_owner_step=step_id, suppress_navigation_stall=True,
        suppress_blocked_edge_learning=True), step_id


def applies(plan, step_id):
    if type(step_id) is not str:
        return True
    marker=plan.get('field_medicine_interrupt') if type(plan) is dict else None
    return (_REGISTRY_ERROR is not None or type(_SESSIONS) is not dict
        or type(_ERRORS) is not dict or step_id in _ERRORS
        or any(type(v) is not dict or not v.get('done') for v in _SESSIONS.values())
        or step_id in _SESSIONS or type(plan) is dict and 'field_medicine_interrupt' in plan
        and (type(marker) is not dict or marker.get('original_step_id') == step_id))


def frame_clock(controller, frame):
    """No wall clock, refund, budget reset, or engineering pause time."""
    if (not _integer(frame) or not _integer(getattr(controller, 'last_frame', None))
            or frame < controller.last_frame or not _clock(getattr(controller, 'last_now', None))):
        return float('nan')
    return controller.last_now + (frame - controller.last_frame) / 60


def _capsule(plan, step_id, game_id, boulder):
    if type(plan) is not dict or plan.get('mode') != 'league_campaign' or type(plan.get('steps')) is not list:
        return None
    capsule = plan.get('field_medicine_interrupt')
    if type(capsule) is not dict or set(capsule) != _CAPSULE_KEYS:
        return None
    ids = [s.get('id') if type(s) is dict else None for s in plan['steps']]
    if any(type(i) is not str or not _ID.fullmatch(i) for i in ids) or len(set(ids)) != len(ids):
        return None
    matches = [s for s in plan['steps'] if s['id'] == step_id]
    if len(matches) != 1:
        return None
    step = matches[0]
    case_key=step.get('boulder_case')
    case = boulder.CASES.get(case_key) if type(case_key) is str else None
    if (capsule['kind'] != KIND or type(game_id) is not str or not game_id
            or capsule['original_game'] != game_id or capsule['original_step_id'] != step_id
            or type(capsule['child_step_id']) is not str or not _ID.fullmatch(capsule['child_step_id'])
            or capsule['child_step_id'] in ids or capsule['item'] != 18
            or type(capsule['item']) is not int or capsule['quantity'] != 1
            or type(capsule['quantity']) is not int or case is None
            or step.get('kind') != 'interact' or step.get('mechanic') != 'victory_later_boulder'
            or step.get('map_id') != case['map_id'] or step.get('target') != case['start_player']
            or not _integer(capsule['original_frame'])
            or type(capsule['target_species']) is not int
            or capsule['target_species'] not in (19,132,102,154,35,7)):
        return None
    loc = capsule['original_location']
    if (type(loc) is not dict or set(loc) != {'map_id','x','y'}
            or type(loc['map_id']) is not int or loc['map_id'] != case['map_id']
            or loc['map_id'] not in (194,198) or not _integer(loc['x'],0,29)
            or not _integer(loc['y'],0,17)):
        return None
    evidence = capsule['evidence']
    if (type(evidence) is not dict or set(evidence) != {'review_sha256','state_sha256'}
            or any(type(v) is not str or not _SHA.fullmatch(v) for v in evidence.values())):
        return None
    try:
        if (plan.get('training_job') in (None,'',{},[])
                or capsule['original_step_sha256'] != canonical_sha256(step)
                or capsule['training_job_sha256'] != canonical_sha256(plan['training_job'])):
            return None
        capsule_canonical = canonical(capsule)
    except (TypeError,ValueError,RecursionError):
        return None
    return capsule, capsule_canonical, step


def preflight(pyboy, state, plan, step_id, *, game_id, native_owner,
              later_bridge, hyper_bridge, peer_owners, attrition=None):
    """Root calls before UI/getters; None means admitted, never a key command."""
    if not applies(plan,step_id):
        return None
    if _REGISTRY_ERROR is not None or type(_SESSIONS) is not dict or type(_ERRORS) is not dict:
        return _review(_REGISTRY_ERROR or 'registry_unverified',step_id)
    if type(step_id) is not str or not step_id:
        return _review('step_id_unverified','unverified-step')
    if step_id in _ERRORS:
        return _review(_ERRORS[step_id],step_id)
    active = [k for k,v in _SESSIONS.items() if type(v) is not dict or not v.get('done')]
    if active and active != [step_id]:
        return _review('coordinator_owner_changed',step_id)
    record = _SESSIONS.get(step_id)
    if record is not None and type(record) is not dict:
        return _review('session_registry_unverified',step_id)
    if record is not None and record.get('error') is not None:
        return _review(record['error'],step_id)
    if pyboy is None or native_owner is not pyboy:
        return _review('original_native_instance_required',step_id)
    parsed = _capsule(plan,step_id,game_id,later_bridge.boulder)
    if parsed is None:
        return _review('exact_capsule_required',step_id)
    capsule, bound, step = parsed
    try:
        if (type(peer_owners) is not dict or set(peer_owners) != PEER_NAMES
                or any(type(v) is not set or any(type(k) is not str or not k for k in v)
                       for v in peer_owners.values())):
            return _review('complete_peer_inventory_required',step_id)
        allowed_hyper = {capsule['child_step_id']} if record and record.get('child_started') and not record.get('done') else set()
        allowed_later = set() if record and record.get('done') and step_id in later_bridge._COMPLETED else {step_id}
        if (peer_owners['victory_later_boulder'] != allowed_later
                or peer_owners['overworld_hyper'] != allowed_hyper
                or later_bridge._active() != allowed_later or hyper_bridge._active() != allowed_hyper
                or any(owners for name,owners in peer_owners.items()
                       if name not in ('victory_later_boulder','overworld_hyper'))):
            return _review('foreign_or_unknown_owner',step_id)
        c = later_bridge._CONTROLLERS.get(step_id)
        binding = later_bridge._BINDINGS.get(step_id)
        expected = (later_bridge.MECHANIC,later_bridge._canonical(step),later_bridge._canonical(plan['training_job']))
        if (c is None or binding != expected or c.owner != step_id or c.error is not None
                or c.case_key != step['boulder_case'] or c.started is None):
            return _review('original_boulder_owner_unverified',step_id)
        if record is not None and (record['native_owner'] is not pyboy or record['controller'] is not c
                or record['binding'] is not binding or record['capsule_canonical'] != bound):
            return _review('bound_instance_controller_or_capsule_changed',step_id)
        if type(state) is not dict or not _integer(state.get('frame')) or pyboy.frame_count != state['frame']:
            return _review('fresh_native_frame_required',step_id)
        if not (record and record.get('done')) and state.get('location') != capsule['original_location']:
            return _review('bound_location_changed',step_id)
        party = hyper_bridge.medicine.ui._party(state.get('progress'))
        if party is None or len(party) != 6 or any(m['hp'] <= 0 or m['status'] != 0 for m in party):
            return _review('fnt_status_or_party_unverified',step_id)
        if state.get('phase') in ('campaign_review','strategy_review','review'):
            if (record is not None or state.get('review_reason') != 'party_attrition_requires_center'
                    or type(attrition) is not dict or attrition.get('review_reason') != 'party_attrition_requires_center'
                    or attrition.get('party_attrition',{}).get('fainted_party_indices') != []):
                return _review('unknown_review_retained',step_id)
        if record is None:
            if (state['frame'] != capsule['original_frame'] or type(attrition) is not dict
                    or attrition.get('review_reason') != 'party_attrition_requires_center'
                    or attrition.get('party_attrition',{}).get('fainted_party_indices') != []):
                return _review('original_attrition_stop_required',step_id)
        elif not record.get('done') and record.get('frozen_parent') != c.__dict__:
            return _review('retained_parent_state_changed',step_id)
    except Exception:
        return _review('owner_preflight_failed',step_id)
    return None


def _proof_impl(signal, c, grid, text, frame, medicine, boulder):
    if (type(signal) is not dict or signal.get('read_valid') is not True
            or signal.get('read_error') is not None or signal.get('profile') != boulder.PROFILE
            or signal.get('source_commit') != boulder.SOURCE_COMMIT or signal.get('case_key') != c.case_key
            or signal.get('observation_frame') != frame or signal.get('idle') is not True
            or signal.get('native_push_busy') is not False or signal.get('location') is None):
        return None
    loc = signal['location']
    if not medicine._closed_world(text,grid,frame,location=loc):
        return None
    raw = signal.get('raw'); stone = signal.get('stone'); objects=signal.get('objects')
    if (type(raw) is not dict or type(stone) is not dict or type(objects) is not list
            or not raw.get('flags1',0)&1 or raw.get('mode') != 0 or raw.get('battle_raw') != 0
            or boulder._native_state(raw,stone) != (False,True)
            or not boulder._grid(grid,c.case,(loc['x'],loc['y']),frame)):
        return None
    keys = ('map_id','x','y','tileset','height','width','object_count','flags1',
            'event2f_raw','event3f_raw','gate1','gate2')
    return deepcopy(dict(location=loc,raw={k:raw[k] for k in keys if k in raw},
        stone=(stone.get('slot'),stone.get('x'),stone.get('y'),stone.get('movement_byte2')),
        objects=boulder._other_objects(objects,c.case['slot']),
        toggle_flags=signal.get('toggle_flags'),toggle_table=signal.get('toggle_table'),
        event=signal.get('event'),tiles=grid.get('tiles')))


def _proof(*args,**kwargs):
    try:return _proof_impl(*args,**kwargs)
    except Exception:return None


def context(pyboy, state, plan, step_id, text, grid, previous, *, game_id,
            native_owner, later_bridge, hyper_bridge, peer_owners, attrition=None):
    if not applies(plan,step_id):
        return None
    gate=preflight(pyboy,state,plan,step_id,game_id=game_id,native_owner=native_owner,
        later_bridge=later_bridge,hyper_bridge=hyper_bridge,peer_owners=peer_owners,attrition=attrition)
    if gate is not None:
        return gate
    capsule, bound, step = _capsule(plan,step_id,game_id,later_bridge.boulder)
    c=later_bridge._CONTROLLERS[step_id]; frame=state['frame']; record=_SESSIONS.get(step_id)
    if record and record.get('done'):
        return None if frame > record['completed_frame'] else _wait(step_id,'completion_frame_yields')
    if record is None:
        record=dict(native_owner=pyboy,controller=c,binding=later_bridge._BINDINGS[step_id],
            capsule_canonical=bound,error=None,done=False,child_started=False)
        _SESSIONS[step_id]=record
        # Real previous only here; later menu B is never passed to parent.
        result=later_bridge.context(pyboy,state,plan,step_id,text,grid,previous,now=frame_clock(c,frame))
        if (type(result) is not tuple or len(result)!=2 or type(result[0]) is not dict
                or result[1] != step_id or result[0].get('phase') == 'campaign_review'
                or result[0].get('later_boulder_battle_handoff') or c.error is not None
                or c.suspended or c.pending is None or c.pending.get('executed') is not False):
            return _review('true_wild_return_not_closed',step_id)
        record['prepared_frame']=frame
        record['pending']=c.pending
        record['frozen_parent']=deepcopy(c.__dict__)
        from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
        signal=later_bridge.boulder.read_later_boulder_observation(pyboy,frame,sdk,case_key=c.case_key)
        proof=_proof(signal,c,grid,text,frame,hyper_bridge.medicine,later_bridge.boulder)
        current=later_bridge.boulder._resources(state['progress'])
        if proof is None or current != c.baseline:
            return _review('prepared_world_or_baseline_unverified',step_id)
        record['proof']=proof; record['before']=deepcopy(state['progress'])
        record['old_baseline']=deepcopy(c.baseline)
        return _wait(step_id,'retained_parent_offer_not_executed')
    if frame <= record['prepared_frame']:
        return _wait(step_id,'fresh_frame_before_child_required')
    medicine=hyper_bridge.medicine
    authority=dict(owner_step_id=step_id,case_key=c.case_key,
        capsule_sha256=sha256(bound.encode('utf-8')).hexdigest(),location=deepcopy(capsule['original_location']))
    intent=dict(kind=KIND,map_id=capsule['original_location']['map_id'],
        target=[capsule['original_location']['x'],capsule['original_location']['y']],
        item=18,quantity=1,target_species=capsule['target_species'],
        owner_step_id=step_id,case_key=c.case_key,capsule_sha256=authority['capsule_sha256'])
    child=dict(id=capsule['child_step_id'],kind='interact',map_id=intent['map_id'],
        target=deepcopy(intent['target']),mechanic='overworld_hyper',overworld_hyper_intent=intent)
    child_plan=dict(mode='league_campaign',training_job=deepcopy(plan['training_job']),steps=[child])
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
    if not record['child_started']:
        signal=later_bridge.boulder.read_later_boulder_observation(pyboy,frame,sdk,case_key=c.case_key)
        if (_proof(signal,c,grid,text,frame,medicine,later_bridge.boulder) != record['proof']
                or not medicine.ui._exact(state['progress'],record['before'])):
            return _review('child_start_world_changed',step_id)
        record['child_started']=True
    result=hyper_bridge.context(pyboy,state,child_plan,child['id'],text,grid,previous,owned_authority=authority)
    if type(result) is not tuple or len(result)!=2 or type(result[0]) is not dict:
        return _review('child_context_unverified',step_id)
    out=result[0]
    if out.get('phase') == 'campaign_review':
        return _review('child_' + str(out.get('review_reason','unknown')),step_id)
    if not out.get('overworld_medicine_complete'):
        if out.get('field_move_complete') or out.get('field_move_kind'):
            return _review('premature_child_field_completion',step_id)
        return dict(out,owned_field_medicine_owner_step=step_id),step_id
    child_c=hyper_bridge._CONTROLLERS.get(child['id'])
    signal=later_bridge.boulder.read_later_boulder_observation(pyboy,frame,sdk,case_key=c.case_key)
    proof=_proof(signal,c,grid,text,frame,medicine,later_bridge.boulder)
    if (child_c is None or child_c.__class__ is not medicine.OverworldHyperController
            or hyper_bridge._OWNERS.get(child['id']) is not pyboy
            or child_c.error is not None or not child_c.complete or child_c.stage!='complete'
            or not child_c.effect_selected or child_c.last_frame!=frame
            or not medicine.ui._exact(child_c.contract,intent)
            or not medicine.ui._exact(child_c.owned_authority,authority)
            or not child_c.receipt_ack or child_c.pending is not None
            or child_c.closed_frame is None or child_c.closed_frame >= frame
            or type(child_c.receipt) is not dict or child_c.receipt != out.get('medicine_receipt')
            or child['id'] not in hyper_bridge._COMPLETED
            or proof is None or proof != record['proof']
            or not medicine.ui._exact(child_c.baseline,record['before'])
            or not medicine.ui._exact(child_c.after,state['progress'])
            or c.pending is not record['pending'] or c.pending.get('executed') is not False):
        return _review('closed_native_receipt_unverified',step_id)
    # Independently derive the only authorized delta, including inventory order.
    expected=deepcopy(record['before'])
    matches=[i for i,m in enumerate(expected['party']) if m['species']==capsule['target_species']]
    if len(matches) != 1:
        return _review('exact_target_required',step_id)
    i=matches[0]; target=expected['party'][i]
    target['hp']=min(target['hp']+200,target['max_hp'])
    for j,item in enumerate(expected['inventory']):
        if item['item']==18:
            item['quantity']-=1
            if item['quantity']==0:expected['inventory'].pop(j)
            break
    else:return _review('original_hyper_missing',step_id)
    if not medicine.ui._exact(expected,state['progress']):
        return _review('exact_hp_item_only_delta_required',step_id)
    new_baseline=later_bridge.boulder._resources(state['progress'])
    if new_baseline is None:
        return _review('after_resources_unverified',step_id)
    history=getattr(c,'medical_interruption_history',[])
    if type(history) is not list:
        return _review('history_unverified',step_id)
    receipt=dict(capsule=deepcopy(capsule),capsule_sha256=authority['capsule_sha256'],
        child_step=deepcopy(child),medicine_receipt=deepcopy(child_c.receipt),
        medicine_contract=deepcopy(child_c.contract),medicine_owned_authority=deepcopy(child_c.owned_authority),
        medicine_completion_context=deepcopy(out),medicine_target_a=child_c.effect_selected,
        medicine_complete=child_c.complete,
        medicine_baseline=deepcopy(child_c.baseline),medicine_after=deepcopy(child_c.after),
        medicine_started=child_c.started,medicine_last_now=child_c.last_now,
        medicine_calls=child_c.calls,medicine_closed_frame=child_c.closed_frame,
        receipt_ack=child_c.receipt_ack,old_baseline=deepcopy(c.baseline),
        new_baseline=deepcopy(new_baseline),proof_before=deepcopy(record['proof']),
        proof_after=deepcopy(proof),completed_frame=frame)
    c.medical_interruption_history=history+[receipt]
    c.baseline=new_baseline
    record['done']=True;record['completed_frame']=frame
    return dict(out,field_move_complete=True,field_move_kind='owned-overworld-hyper',
        owned_field_medicine_owner_step=step_id),step_id
