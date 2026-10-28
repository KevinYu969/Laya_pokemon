"""One source-bound Full Heal at game29's reviewed recovery stop.

All ownership/errors live in the injected owned_field_medicine registries.
No emulator creation, input, ticks, RAM/state/plan writes, or route advancement.
"""
from copy import deepcopy
import re

KIND='recovery_full_heal'
STEP_ID='league28-fnt-recovery-00'
LOCATION={'map_id':198,'x':11,'y':13}
FRAME=5353
_KEYS=frozenset(('kind','original_game','original_step_id','original_step_sha256',
    'training_job_sha256','steps_sha256','recovery_capsule_sha256','original_frame',
    'original_location','item','quantity','target_species','status_before','status_after',
    'reviewed_fainted_bench','child_step_id','evidence'))


def _record(shared,step_id):
    return shared._SESSIONS.get(step_id) if type(shared._SESSIONS) is dict and type(step_id) is str else None


def applies(plan,step_id,*,shared):
    marker_present=type(plan) is dict and 'recovery_field_medicine' in plan
    active_new_kind=type(shared._SESSIONS) is dict and any(type(r) is dict and r.get('kind')==KIND
        and not r.get('done') for r in shared._SESSIONS.values())
    if type(step_id) is not str:return marker_present or active_new_kind
    record=_record(shared,step_id)
    if type(record) is dict and record.get('kind')==KIND:return True
    if active_new_kind:return True
    marker=plan.get('recovery_field_medicine') if type(plan) is dict else None
    return marker_present and (
        type(marker) is not dict or marker.get('original_step_id')==step_id)


def _review(reason,step_id,shared):
    return shared._review('recovery_full_heal_'+reason,step_id)


def _wait(step_id,reason):
    return dict(phase='overworld_medicine_wait',objective='Wait.',available_actions=['wait'],
        recovery_full_heal_reason=reason,recovery_full_heal_owner_step=step_id,
        suppress_navigation_stall=True,suppress_blocked_edge_learning=True),step_id


def _binding(plan,step_id,game_id,evidence,shared,recovery,medicine):
    if (type(plan) is not dict or not recovery.valid_plan(plan) or step_id!=STEP_ID
            or game_id!='game29' or type(game_id) is not str):return None
    cap=plan.get('recovery_field_medicine')
    if type(cap) is not dict or set(cap)!=_KEYS:return None
    expected=dict(kind=KIND,original_game='game29',original_step_id=STEP_ID,
        original_frame=FRAME,original_location=LOCATION,item=52,quantity=1,target_species=35,
        status_before=8,status_after=0,reviewed_fainted_bench=[7])
    if any(not medicine.ui._exact(cap.get(k),v) for k,v in expected.items()):return None
    if (type(cap.get('child_step_id')) is not str
            or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',cap['child_step_id']) is None
            or cap['child_step_id'] in {s['id'] for s in plan['steps']}):return None
    if (type(evidence) is not dict or set(evidence)!={'review_sha256','state_sha256'}
            or any(type(v) is not str or re.fullmatch(r'[0-9a-f]{64}',v) is None for v in evidence.values())
            or not medicine.ui._exact(cap.get('evidence'),evidence)):return None
    try:
        step=next(s for s in plan['steps'] if s['id']==STEP_ID)
        hashes=dict(original_step_sha256=shared.canonical_sha256(step),
            training_job_sha256=shared.canonical_sha256(plan['training_job']),
            steps_sha256=shared.canonical_sha256(plan['steps']),
            recovery_capsule_sha256=shared.canonical_sha256(plan['reviewed_fnt_recovery']))
        if any(type(cap.get(k)) is not str or cap[k]!=v for k,v in hashes.items()):return None
        return cap,shared.canonical(cap),step
    except (TypeError,ValueError,StopIteration,RecursionError):return None


def _party(progress,medicine,*,initial):
    if (type(progress) is not dict or progress.get('party_read_valid') is not True
            or type(progress.get('party_count')) is not int or progress['party_count']!=6
            or type(progress.get('badges_raw')) is not int or progress['badges_raw']!=255
            or progress.get('player_name_raw')!='KEVIN'):return None
    party=medicine.recovery_party(progress)
    if (party is None or len(party)!=6 or {m['species'] for m in party}!=medicine.ui.ROSTER):return None
    for mon in party:
        if type(mon['status']) is not int:return None
        if mon['species']==7:
            if mon['hp']!=0 or mon['status']!=0:return None
        elif mon['species']==35:
            if mon['hp']!=mon['max_hp'] or mon['status'] not in ((8,) if initial else (8,0)):return None
        elif mon['hp']!=mon['max_hp'] or mon['status']!=0:return None
    return party


def _done_child_valid(record,cap,shared,hyper_bridge):
    """Completed releases navigation, while its original native receipt stays bound."""
    try:
        c=record['controller'];receipt=record['receipt'];exact=hyper_bridge.medicine.ui._exact
        return (record['child_started'] is True and cap['child_step_id'] in hyper_bridge._COMPLETED
            and type(receipt) is dict and shared.canonical_sha256(receipt)==record['receipt_sha256']
            and c.error is None and c.complete is True and c.stage=='complete' and c.pending is None
            and c.effect_selected is True and c.receipt_ack is True
            and exact(c.receipt,receipt['medicine_receipt'])
            and exact(c.intent,receipt['child_step']['overworld_hyper_intent'])
            and exact(c.contract,c.intent) and exact(c.owned_authority,receipt['owned_authority'])
            and exact(c.baseline,receipt['before']) and exact(c.after,receipt['after'])
            and exact(c.started,receipt['started']) and exact(c.last_now,receipt['last_now'])
            and exact(c.calls,receipt['calls']) and exact(c.closed_frame,receipt['closed_frame'])
            and c.last_frame==record['completed_frame']==receipt['completed_frame'])
    except (KeyError,TypeError,ValueError,AttributeError,RecursionError):return False


def preflight(pyboy,state,plan,step_id,*,game_id,native_owner,source_evidence,
              shared,hyper_bridge,recovery,peer_owners,attrition=None):
    """Call before reading UI. None admits observation, never an input."""
    if not applies(plan,step_id,shared=shared):return None
    if type(step_id) is not str or not step_id:return _review('step_unverified','unverified-step',shared)
    active=shared._active()
    if active is None:return _review('shared_registry_unverified',step_id,shared)
    if step_id in shared._ERRORS:return shared._review(shared._ERRORS[step_id],step_id)
    record=_record(shared,step_id)
    if record is not None and (type(record) is not dict or record.get('kind')!=KIND):
        return _review('shared_step_owner_conflict',step_id,shared)
    if record is not None and not {'child_started','native_owner','capsule_canonical','sessions_id','errors_id',
            'controller','child_binding','before','original_step','training_job','start_frame','receipt'}<=set(record):
        return _review('shared_session_shape_unverified',step_id,shared)
    if pyboy is None or native_owner is not pyboy:return _review('original_native_instance_required',step_id,shared)
    binding=_binding(plan,step_id,game_id,source_evidence,shared,recovery,hyper_bridge.medicine)
    if binding is None:return _review('exact_capsule_job_route_or_evidence_required',step_id,shared)
    cap,canonical,step=binding
    if active != ({step_id} if record and not record['done'] else set()):
        return _review('other_shared_owner_or_error',step_id,shared)
    expected_hyper={cap['child_step_id']} if record and record['child_started'] and not record['done'] else set()
    if (type(peer_owners) is not dict or set(peer_owners)!=shared.PEER_NAMES
            or any(type(v) is not set or any(type(k) is not str or not k for k in v) for v in peer_owners.values())
            or any(v!=expected_hyper if k=='overworld_hyper' else bool(v) for k,v in peer_owners.items())
            or hyper_bridge._active()!=expected_hyper):
        return _review('complete_empty_peer_inventory_required',step_id,shared)
    if (type(state) is not dict or not hyper_bridge.medicine._int(state.get('frame'))
            or pyboy.frame_count!=state['frame']):
        return _review('fresh_native_frame_required',step_id,shared)
    if record:
        if (record['native_owner'] is not pyboy or record['capsule_canonical']!=canonical
                or record['sessions_id']!=id(shared._SESSIONS) or record['errors_id']!=id(shared._ERRORS)):
            return _review('bound_owner_capsule_or_registries_changed',step_id,shared)
        if (hyper_bridge._CONTROLLERS.get(cap['child_step_id']) is not record['controller']
                or hyper_bridge._OWNERS.get(cap['child_step_id']) is not pyboy
                or hyper_bridge._BINDINGS.get(cap['child_step_id']) is not record['child_binding']):
            return _review('original_child_controller_or_binding_changed',step_id,shared)
        if record['done']:
            if not hyper_bridge.medicine._int(record.get('completed_frame')) or state['frame']<record['completed_frame']:
                return _review('completion_frame_regressed',step_id,shared)
            if not _done_child_valid(record,cap,shared,hyper_bridge):
                return _review('completed_child_or_receipt_changed',step_id,shared)
            return None
    if not hyper_bridge.medicine.ui._exact(state.get('location'),LOCATION):
        return _review('fresh_bound_native_frame_location_required',step_id,shared)
    if state.get('phase') in ('campaign_review','strategy_review','review'):
        return _review('unknown_review_retained_use_raw_observation',step_id,shared)
    battle=state.get('battle_state')
    if (type(battle) is not dict or type(battle.get('raw')) is not int or battle['raw']!=0
            or battle.get('kind')!='none' or battle.get('active') is not False
            or type(battle.get('observation_frame')) is not int or battle['observation_frame']!=state['frame']):
        return _review('nonbattle_frame_unverified',step_id,shared)
    party=_party(state.get('progress'),hyper_bridge.medicine,initial=record is None)
    if party is None:return _review('exact_reviewed_fnt_and_poison_party_required',step_id,shared)
    if record is None:
        indices=[i for i,m in enumerate(party) if m['hp']==0]
        if (state['frame']!=FRAME or type(attrition) is not dict
                or attrition.get('review_reason')!='party_attrition_requires_center'
                or type(attrition.get('party_attrition')) is not dict
                or attrition['party_attrition'].get('fainted_party_indices')!=indices):
            return _review('original_known_attrition_stop_required',step_id,shared)
    return None


def _fresh_closed_getter(signal,frame,pyboy,expected,medicine):
    if (type(signal) is not dict or signal.get('read_valid') is not True or signal.get('read_error') is not None
            or signal.get('profile')!=medicine.PROFILE or signal.get('source_commit')!=medicine.SOURCE_COMMIT
            or type(signal.get('owner_id')) is not int or signal['owner_id']!=id(pyboy)
            or any(type(signal.get(k)) is not int or signal[k]!=frame for k in ('observation_frame','frame_before','frame_after'))
            or type(signal.get('source_map_id')) is not int or signal['source_map_id']!=198
            or type(signal.get('script_address')) is not int or signal['script_address']!=0xD640
            or not medicine.ui._exact(signal.get('progress'),expected)):return False
    values=signal.get('values');movement=signal.get('movement')
    required=dict(LOCATION,raw=0,battle_type=0,badges=255,mode=0,script=0)
    if (type(values) is not dict or any(type(values.get(k)) is not int or values[k]!=v for k,v in required.items())
            or not medicine._int(values.get('status5'),0,255) or values['status5']&1):return False
    return (type(movement) is dict and movement.get('read_valid') is True and movement.get('read_error') is None
        and movement.get('profile')==medicine.rocket_movement.MOVEMENT_PROFILE
        and movement.get('source_commit')==medicine.SOURCE_COMMIT
        and type(movement.get('observation_frame')) is int and movement['observation_frame']==frame
        and movement.get('spinning') is False
        and all(type(movement.get(k)) is int and movement[k]==0
            for k in ('simulated_remaining','joy_ignore','walk_counter','movement_flags')))


def context(pyboy,state,plan,step_id,text,grid,previous,*,game_id,native_owner,
            source_evidence,shared,hyper_bridge,recovery,peer_owners,attrition=None):
    if not applies(plan,step_id,shared=shared):return None
    kwargs=dict(game_id=game_id,native_owner=native_owner,source_evidence=source_evidence,
        shared=shared,hyper_bridge=hyper_bridge,recovery=recovery,peer_owners=peer_owners,attrition=attrition)
    gate=preflight(pyboy,state,plan,step_id,**kwargs)
    if gate is not None:return gate
    cap,canonical,step=_binding(plan,step_id,game_id,source_evidence,shared,recovery,hyper_bridge.medicine)
    record=_record(shared,step_id);frame=state['frame'];medicine=hyper_bridge.medicine
    if record and record['done']:
        return None if frame>record['completed_frame'] else _wait(step_id,'completion_frame_yields')
    authority=dict(kind=KIND,owner_step_id=step_id,capsule_sha256=shared.canonical_sha256(cap),
        location=deepcopy(LOCATION),reviewed_fainted_bench=[7],status_before=8,status_after=0)
    intent=dict(kind=KIND,map_id=198,target=[11,13],item=52,quantity=1,target_species=35,
        status_before=8,status_after=0,reviewed_fainted_bench=[7],owner_step_id=step_id,
        capsule_sha256=authority['capsule_sha256'])
    child=dict(id=cap['child_step_id'],kind='interact',map_id=198,target=[11,13],
        mechanic='overworld_hyper',overworld_hyper_intent=intent)
    child_plan=dict(mode='league_campaign',training_job=deepcopy(plan['training_job']),steps=[child])
    if record is None:
        if not medicine._closed_world(text,grid,frame,LOCATION):return _review('initial_closed_world_required',step_id,shared)
        record=dict(kind=KIND,done=False,error=None,native_owner=pyboy,capsule_canonical=canonical,
            sessions_id=id(shared._SESSIONS),errors_id=id(shared._ERRORS),child_started=False,
            controller=None,child_binding=None,before=deepcopy(state['progress']),
            original_step=deepcopy(step),training_job=deepcopy(plan['training_job']),
            start_frame=frame,receipt=None)
        shared._SESSIONS[step_id]=record
    result=hyper_bridge.context(pyboy,state,child_plan,child['id'],text,grid,previous,owned_authority=authority)
    controller=hyper_bridge._CONTROLLERS.get(child['id'])
    if not record['child_started']:
        record['controller']=controller;record['child_binding']=hyper_bridge._BINDINGS.get(child['id'])
        record['child_started']=controller is not None
    if type(result) is not tuple or len(result)!=2 or type(result[0]) is not dict:
        return _review('child_context_unverified',step_id,shared)
    out=result[0]
    if out.get('phase')=='campaign_review':return _review('child_'+str(out.get('review_reason','unknown')),step_id,shared)
    if not out.get('overworld_medicine_complete'):
        if out.get('field_move_complete') or out.get('field_move_kind'):
            return _review('premature_child_field_completion',step_id,shared)
        return {**out,'recovery_full_heal_owner_step':step_id},step_id
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
    signal=medicine.read_observation(pyboy,frame,sdk,map_id=198)
    expected=deepcopy(record['before'])
    targets=[i for i,m in enumerate(expected['party']) if m['species']==35]
    if len(targets)!=1:return _review('unique_target_required',step_id,shared)
    expected['party'][targets[0]]['status']=0
    for i,item in enumerate(expected['inventory']):
        if item['item']==52:
            item['quantity']-=1
            if item['quantity']==0:expected['inventory'].pop(i)
            break
    else:return _review('original_full_heal_missing',step_id,shared)
    if (controller is None or controller.__class__ is not medicine.OverworldHyperController
            or controller is not record['controller'] or controller.error is not None
            or not controller.complete or controller.stage!='complete' or not controller.effect_selected
            or not controller.receipt_ack or controller.pending is not None or controller.last_frame!=frame
            or not medicine._int(controller.closed_frame) or controller.closed_frame>=frame
            or controller.receipt!=out.get('medicine_receipt') or child['id'] not in hyper_bridge._COMPLETED
            or not medicine.ui._exact(controller.contract,intent)
            or not medicine.ui._exact(controller.owned_authority,authority)
            or not medicine.ui._exact(controller.baseline,record['before'])
            or not medicine.ui._exact(controller.after,expected)
            or not medicine.ui._exact(state['progress'],expected)
            or not medicine._closed_world(text,grid,frame,LOCATION)
            or not _fresh_closed_getter(signal,frame,pyboy,expected,medicine)):
        return _review('genuine_closed_status_item_only_receipt_required',step_id,shared)
    record['receipt']=dict(capsule=deepcopy(cap),child_step=deepcopy(child),
        medicine_receipt=deepcopy(controller.receipt),completion_context=deepcopy(out),
        owned_authority=deepcopy(controller.owned_authority),
        before=deepcopy(record['before']),after=deepcopy(expected),
        receipt_ack=controller.receipt_ack,effect_selected=controller.effect_selected,
        started=controller.started,last_now=controller.last_now,calls=controller.calls,
        closed_frame=controller.closed_frame,completed_frame=frame)
    record['receipt_sha256']=shared.canonical_sha256(record['receipt'])
    record['done']=True;record['completed_frame']=frame
    return {**out,'field_move_complete':True,'field_move_kind':'recovery-full-heal',
        'recovery_full_heal_owner_step':step_id},step_id
