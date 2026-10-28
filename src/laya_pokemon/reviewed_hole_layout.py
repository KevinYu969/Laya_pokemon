"""One named review of the existing failed 3F-hole owner; no game writes."""
from copy import deepcopy
import re

KIND='reviewed_3f_hole_aux8_layout_v1'
LAYOUT='reviewed_3f_hole_aux8_13_13_20261028'
STEP_ID='league28-fnt-recovery-01'
ERROR='victory_later_boulder_initial_fixed_mechanism_unverified'
FRAME=7233
LOCATION={'map_id':198,'x':21,'y':15}
EVIDENCE=dict(review_sha256='1ca24415b4dd99a733047963b3b8df9f064d56f1bed5e7f293de1e275bb73abd',
    state_sha256='e2854324e82f59d2d8813712f2d759ce0ba9a4c2a22641785b31d79be23f0c75',
    preflight_sha256='48b19783531d936ea9bbe505cd44a424ec09e7a1de6a0d2c4ba00871402b28dd')
_KEYS={'kind','game_id','source_frame','source_location','original_step_id','original_step_sha256',
    'training_job_sha256','steps_sha256','recovery_capsule_sha256','source_progress_sha256','source_layout','evidence'}
_PRESERVED=('owner','started','last_now','step_started','calls','waits','requests','last_frame',
    'push_index','pending','baseline','flags_baseline','object_baseline','closed_frame','final_player',
    'suspended','battle_returns','contact_arm_seen','native_script_seen','dust_seen')


def applies(step_id,*,bridge):
    return (step_id==STEP_ID and type(bridge._CONTROLLERS) is dict
        and bridge._CONTROLLERS.get(step_id) is not None)


def _review(reason,step_id,c=None):
    if c is not None:
        previous=getattr(c,'source_layout_review_error',None)
        c.source_layout_review_error=previous or reason
        reason=c.source_layout_review_error
    return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
        review_reason='reviewed_hole_layout_'+reason),step_id


def _wait(step_id):
    return dict(phase='overworld',objective='Wait.',available_actions=['wait'],
        later_boulder_owner_step=step_id,source_layout_review=LAYOUT,
        suppress_navigation_stall=True,suppress_blocked_edge_learning=True),step_id


def _binding(plan,step_id,game_id,capsule,source_evidence,shared,recovery):
    if (game_id!='game29' or type(game_id) is not str or step_id!=STEP_ID
            or not recovery.valid_plan(plan) or type(capsule) is not dict or set(capsule)!=_KEYS
            or shared.canonical(source_evidence)!=shared.canonical(EVIDENCE)
            or shared.canonical(capsule.get('evidence'))!=shared.canonical(EVIDENCE)):
        return None
    expected=dict(kind=KIND,game_id='game29',source_frame=FRAME,source_location=LOCATION,
        original_step_id=STEP_ID,source_layout=LAYOUT)
    if any(shared.canonical(capsule.get(k))!=shared.canonical(v) for k,v in expected.items()):return None
    try:
        step=next(s for s in plan['steps'] if s['id']==STEP_ID)
        required=dict(original_step_sha256=shared.canonical_sha256(step),
            training_job_sha256=shared.canonical_sha256(plan['training_job']),
            steps_sha256=shared.canonical_sha256(plan['steps']),
            recovery_capsule_sha256=shared.canonical_sha256(plan['reviewed_fnt_recovery']))
        if any(type(capsule.get(k)) is not str or capsule[k]!=v for k,v in required.items()):return None
        if type(capsule.get('source_progress_sha256')) is not str or re.fullmatch('[0-9a-f]{64}',capsule['source_progress_sha256']) is None:return None
        return shared.canonical(capsule),step
    except (KeyError,TypeError,ValueError,StopIteration,RecursionError):return None


def preflight(pyboy,state,plan,step_id,*,bridge,shared,recovery,native_owner,
              game_id,review_capsule,source_evidence,peer_owners):
    """Root must call before UI/getters; never clears an error here."""
    if type(step_id) is not str:return _review('step_id_unverified','unverified-step')
    active=bridge._active();c=bridge._CONTROLLERS.get(step_id) if type(bridge._CONTROLLERS) is dict else None
    if (active!={STEP_ID} or c is None or step_id!=STEP_ID or shared._active()!=set()):
        return _review('original_unique_owner_required',step_id,c)
    if getattr(c,'source_layout_review_error',None):return _review(c.source_layout_review_error,step_id,c)
    if (pyboy is None or native_owner is not pyboy or type(state) is not dict
            or type(state.get('frame')) is not int or type(pyboy.frame_count) is not int or pyboy.frame_count!=state['frame']):
        return _review('native_frame_unverified',step_id,c)
    try:bound=_binding(plan,step_id,game_id,review_capsule,source_evidence,shared,recovery)
    except (TypeError,ValueError,RecursionError):bound=None
    if bound is None:return _review('exact_review_capsule_required',step_id,c)
    if (type(peer_owners) is not dict or set(peer_owners)!=shared.PEER_NAMES
            or any(type(v) is not set or any(type(k) is not str or not k for k in v) for v in peer_owners.values())
            or any(v!={STEP_ID} if k=='victory_later_boulder' else bool(v) for k,v in peer_owners.items())):
        return _review('complete_peer_mutex_required',step_id,c)
    expected=(bridge.MECHANIC,bridge._canonical(bound[1]),bridge._canonical(plan['training_job']))
    if (bridge._BINDINGS.get(step_id)!=expected or c.owner!=step_id or c.case_key!='3f_hole'
            or c.case!=bridge.boulder.CASES['3f_hole'] or c.contract!=c.case or c.pushes!=c.case['pushes']
            or type(getattr(c,'reviewed_fainted_bench',())) is not tuple
            or getattr(c,'reviewed_fainted_bench',())!=(7,)
            or any(type(v) is not int for v in c.reviewed_fainted_bench)):
        return _review('original_step_job_case_or_bench_changed',step_id,c)
    record=getattr(c,'source_layout_review_record',None)
    phase=state.get('phase');reason=state.get('review_reason')
    released=type(record) is dict and record.get('released') is True
    if (phase in ('campaign_review','strategy_review','review')
            and not (not released and phase=='campaign_review' and reason==ERROR)
            or reason is not None and reason!=ERROR):
        return _review('unknown_existing_review_retained',step_id,c)
    if not released:
        battle=state.get('battle_state')
        if (phase not in ('overworld','unclassified','campaign_review')
                or type(battle) is not dict or type(battle.get('raw')) is not int or battle['raw']!=0
                or battle.get('kind')!='none' or battle.get('active') is not False
                or type(battle.get('observation_frame')) is not int or battle['observation_frame']!=state['frame']):
            return _review('original_nonbattle_packet_unverified',step_id,c)
    if record is not None:
        if (type(record) is not dict or record.get('native_owner') is not pyboy or record.get('original_controller') is not c
                or record.get('binding') is not bridge._BINDINGS[step_id] or record.get('capsule_canonical')!=bound[0]
                or getattr(c,'source_layout','source')!=LAYOUT or getattr(c,'source_layout_contract','source')!=LAYOUT):
            return _review('review_owner_or_profile_changed',step_id,c)
        history=getattr(c,'source_layout_review_history',None)
        if (type(history) is not list or not history or shared.canonical_sha256(history[-1])!=record.get('history_sha256')):
            return _review('review_history_changed',step_id,c)
        return None
    if (c.error!=ERROR or c.baseline is not None or c.pending is not None or c.push_index!=0
            or c.flags_baseline is not None or c.object_baseline is not None or c.suspended
            or c.closed_frame is not None or c.final_player is not None
            or c.last_frame!=FRAME or state['frame']!=FRAME or state.get('location')!=LOCATION
            or not bridge.boulder._int(c.calls,1,bridge.boulder.MAX_CALLS)
            or not bridge.boulder._int(c.waits,0,bridge.boulder.MAX_STEP_WAITS)
            or not bridge.boulder._int(c.requests,0,bridge.boulder.MAX_REQUESTS)
            or not shared._clock(c.started) or not shared._clock(c.last_now) or not shared._clock(c.step_started)
            or c.last_now<c.started or c.last_now<c.step_started
            or c.last_now-c.started>bridge.boulder.MAX_SECONDS or c.last_now-c.step_started>bridge.boulder.MAX_STEP_SECONDS
            or getattr(c,'source_layout','source')!='source' or getattr(c,'source_layout_contract','source')!='source'
            or type(c.last_packet) is not tuple or len(c.last_packet)!=7):
        return _review('only_named_initial_failure_supported',step_id,c)
    old_state=c.last_packet[0]
    if (type(old_state) is not dict or old_state.get('frame')!=FRAME or old_state.get('location')!=LOCATION
            or shared.canonical_sha256(old_state.get('progress'))!=review_capsule['source_progress_sha256']):
        return _review('original_failure_packet_changed',step_id,c)
    return None


def _proof(signal,state,text,grid,bridge,recovery,plan,step_id):
    try:
        b=bridge.boulder;frame=state['frame'];a=signal['raw'];objects=signal['objects'];stone=signal['stone']
        c=b.CASES['3f_hole']
        if (signal.get('read_valid') is not True or signal.get('read_error') is not None
                or signal.get('profile')!=b.PROFILE or signal.get('source_commit')!=b.SOURCE_COMMIT
                or signal.get('case_key')!='3f_hole' or type(signal.get('observation_frame')) is not int
                or signal['observation_frame']!=frame or signal.get('location')!=LOCATION or state.get('location')!=LOCATION
                or signal.get('idle') is not True or signal.get('native_push_busy') is not False or signal.get('event') is not False
                or b._native_state(a,stone)!=(False,True) or not a['flags1']&1 or a['mode']!=0 or a['battle_raw']!=0
                or a['movement_flags']&4 or not b._grid(grid,c,(21,15),frame)
                or grid['tiles'][15][21]!=42 or any(a[k]!=v for k,v in c['gate_binding'].items())
                or not b._hidden(signal['toggle_flags'],0x60) or b._hidden(signal['toggle_flags'],0x7A)
                or any((objects[s-1]['x'],objects[s-1]['y'])!=p for s,p in b.initial_source_stones('3f_hole',LAYOUT).items())
                or any(b._event(other,a)!=(key in c['required_true']) for key,other in b.CASES.items() if key!='3f_hole')
                or recovery.admitted(plan,step_id,state['progress'])!=(7,) or b._resources(state['progress']) is None):return None
        from laya_pokemon.campaign_transactions import verified_blank_transaction_world
        if not verified_blank_transaction_world(text,grid):return None
        return deepcopy(dict(location=LOCATION,objects=b._other_objects(objects,10),
            stones=[(s,objects[s-1]['x'],objects[s-1]['y']) for s in (7,8,9,10)],
            flags={k:a[k] for k in ('flags1','event2f_raw','event3f_raw','gate1','mode','battle_raw')},
            toggle_flags=signal['toggle_flags'],toggle_table=signal['toggle_table'],tiles=grid['tiles']))
    except (KeyError,TypeError,ValueError,IndexError,AttributeError):return None


def context(pyboy,state,plan,step_id,text,grid,previous,*,bridge,shared,recovery,
            native_owner,game_id,review_capsule,source_evidence,peer_owners):
    gate=preflight(pyboy,state,plan,step_id,bridge=bridge,shared=shared,recovery=recovery,
        native_owner=native_owner,game_id=game_id,review_capsule=review_capsule,source_evidence=source_evidence,peer_owners=peer_owners)
    if gate is not None:return gate
    c=bridge._CONTROLLERS[step_id];record=getattr(c,'source_layout_review_record',None)
    if record is not None and record.get('released') is True:return None
    if (type(previous) not in (list,tuple) or any(type(a) is not str or a not in bridge._ACTIONS for a in previous)):
        return _review('actual_previous_unverified',step_id,c)
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
    from laya_pokemon.progress import read_progress
    signal=bridge.boulder.read_later_boulder_observation(pyboy,state['frame'],sdk,case_key='3f_hole')
    progress=read_progress(pyboy,sdk)
    if (pyboy.frame_count!=state['frame'] or shared.canonical_sha256(progress)!=review_capsule['source_progress_sha256']
            or shared.canonical(progress)!=shared.canonical(state.get('progress'))):
        return _review('fresh_full_progress_changed',step_id,c)
    proof=_proof(signal,state,text,grid,bridge,recovery,plan,step_id)
    if proof is None:return _review('fixed_reviewed_layout_not_proven',step_id,c)
    if record is None:
        if proof!=_proof(c.last_packet[3],c.last_packet[0],c.last_packet[1],c.last_packet[2],bridge,recovery,plan,step_id):
            return _review('original_native_failure_packet_changed',step_id,c)
        history=getattr(c,'source_layout_review_history',[])
        if type(history) is not list or history:return _review('review_history_not_empty',step_id,c)
        snapshot={k:deepcopy(getattr(c,k)) for k in _PRESERVED}
        entry=dict(kind=KIND,old_error=c.error,old_source_layout='source',source_layout=LAYOUT,
            capsule=deepcopy(review_capsule),source_progress_sha256=review_capsule['source_progress_sha256'],
            native_owner_id=id(pyboy),preserved=deepcopy(snapshot),actual_proof=deepcopy(proof),actual_previous=list(previous))
        c.source_layout_review_history=[entry]
        c.source_layout_review_record=dict(native_owner=pyboy,original_controller=c,binding=bridge._BINDINGS[step_id],
            capsule_canonical=shared.canonical(review_capsule),armed_frame=FRAME,released=False,
            original_packet=c.last_packet,preserved=snapshot,proof=proof,history_sha256=shared.canonical_sha256(entry))
        c.source_layout=c.source_layout_contract=LAYOUT
        c.error=None  # The sole authorized error, after the complete readonly proof.
        return _wait(step_id)
    if (c.error is not None or c.last_packet is not record['original_packet']
            or any(getattr(c,k)!=v for k,v in record['preserved'].items()) or proof!=record['proof']):
        return _review('original_pending_clock_or_mechanism_changed',step_id,c)
    if state['frame']<=record['armed_frame']:return _wait(step_id)
    if not previous or previous[-1]!='wait':return _review('fresh_actual_wait_receipt_required',step_id,c)
    record['released']=True
    return None
