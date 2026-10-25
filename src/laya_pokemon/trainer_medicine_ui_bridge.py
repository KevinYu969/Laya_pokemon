"""Explicit parent-owned trainer medicine UI bridge; no strategy or game writes."""
from copy import deepcopy
import importlib
import math
import time

from laya_pokemon import trainer_medicine_ui as medicine,player_battle,trainer_opponent

importlib.reload(medicine)
SUPPLY='trainer-medicine-ui-v1'
SOURCE_COMMIT='a53671100ec22e5394ff26ec028d0812a238dae2'
TRAINERS={
    33:((29,4),'left','beat_route22_rival_2nd_battle'),
    45:((2,2),'up','beat_viridian_gym_giovanni'),
    245:((5,3),'up','beat_loreleis_room_trainer_0'),
    246:((5,3),'up','beat_brunos_room_trainer_0'),
    247:((5,3),'up','beat_agathas_room_trainer_0'),
    113:((6,2),'up','beat_lance'),
    120:((4,3),'up','beat_champion_rival'),
}
_CONTROLLERS=globals().get('_CONTROLLERS',{})
_BINDINGS=globals().get('_BINDINGS',{})
_COMPLETED=globals().get('_COMPLETED',set())
_ACTIONS={'a','b','up','down','left','right','start','wait'}


def _int(value):return type(value) is int and 0<=value<=0x7fffffffffffffff
def _clock(value):return type(value) in (int,float) and math.isfinite(value) and value>=0
def _exact(a,b):return medicine.ui._exact(a,b)
def _active():return (set(_CONTROLLERS)|set(_BINDINGS))-_COMPLETED


def _review(reason,step_id,owner=None):
    record=_BINDINGS.get(owner)
    if type(record) is dict:
        if record.get('bridge_error') is None:record['bridge_error']=reason
        reason=record['bridge_error']
    return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
                review_reason='trainer_medicine_ui_bridge_'+reason),step_id


def _sdk_constants():
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
    return sdk


def _fixed_intent(value):
    for expected in (medicine.HYPER_POTION_INTENT,medicine.FULL_HEAL_INTENT):
        if _exact(value,expected):return deepcopy(expected)
    return None


def _signature(step_id,step):
    if (type(step_id) is not str or not step_id or type(step) is not dict
            or step.get('kind')!='interact' or type(step.get('map_id')) is not int
            or step['map_id'] not in TRAINERS or step.get('battle_supply')!=SUPPLY
            or any(key in step for key in ('mechanic','item','badge','terminal','next_map','nextmap'))
            or 'await_script_event' in step and step['await_script_event'] is not True):
        return None
    target,face,event=TRAINERS[step['map_id']]
    if (type(step.get('target')) is not list or len(step['target'])!=2
            or any(type(v) is not int for v in step['target']) or tuple(step['target'])!=target
            or step.get('face')!=face or step.get('event')!=event):
        return None
    return (step_id,'interact',step['map_id'],target,face,event,SUPPLY,step.get('await_script_event') is True)


def applies(step_id,step):
    return bool(_active()) or bool(type(step) is dict and step.get('battle_supply')==SUPPLY)


def _proof(packet,module,frame,location,*,enemy=False):
    if (type(packet) is not dict or packet.get('read_valid') is not True
            or packet.get('profile')!=module.PROFILE or packet.get('source_commit')!=SOURCE_COMMIT
            or not _int(packet.get('observation_frame')) or packet['observation_frame']!=frame
            or packet.get('battle_kind')!='trainer' or not _exact(packet.get('location'),location)):
        return False
    if not enemy:return True
    return (all(_int(packet.get(k)) and packet[k]==frame for k in ('frame_before','frame_after'))
            and type(packet.get('raw')) is int and packet['raw']==2
            and type(packet.get('battle_type')) is int and packet['battle_type']==0
            and type(packet.get('current_opponent')) is int and 0<=packet['current_opponent']<=255
            and type(packet.get('raw_record')) is list and len(packet['raw_record'])==29
            and all(type(v) is int and 0<=v<=255 for v in packet['raw_record']))


def context(pyboy,state,plan,step_id,text,previous,*,intent=None):
    """Return (UI hint, unchanged trainer step_id), or None if no UI owner/start.

    medicine_ui_complete retires only this UI owner. It never completes the
    trainer step, resolves its enemy turn, or claims survival/victory.
    """
    active=_active()
    if not active and intent is None:return None
    if len(active)>1:return _review('multiple_active_owners',step_id)
    owner=next(iter(active),None);record=_BINDINGS.get(owner);controller=_CONTROLLERS.get(owner)
    if owner is not None and (type(record) is not dict or controller is None):
        return _review('controller_or_binding_lost',step_id,owner)
    if owner is not None and record.get('bridge_error') is not None:
        return _review(record['bridge_error'],step_id,owner)
    if type(step_id) is not str or not step_id:return _review('step_id_unverified',step_id,owner)
    if owner is not None and record['step_id']!=step_id:return _review('owner_step_changed',step_id,owner)
    if type(plan) is not dict or type(plan.get('steps')) is not list:return _review('plan_unverified',step_id,owner)
    matches=[step for step in plan['steps'] if type(step) is dict and step.get('id')==step_id]
    if len(matches)!=1:return _review('unique_step_required',step_id,owner)
    signature=_signature(step_id,matches[0])
    if signature is None:return _review('fixed_trainer_step_required',step_id,owner)
    if owner is not None and not _exact(signature,record['signature']):return _review('bound_step_changed',step_id,owner)
    requested=_fixed_intent(intent) if intent is not None else None
    if intent is not None and requested is None:return _review('explicit_intent_unverified',step_id,owner)
    if owner is not None:
        if requested is not None and not _exact(requested,record['intent']):return _review('active_intent_changed',step_id,owner)
        expected=record['intent']
    else:expected=requested
    if type(state) is not dict or not _int(state.get('frame')):return _review('state_frame_unverified',step_id,owner)
    frame=state['frame'];location=state.get('location');battle=state.get('battle_state')
    expected_location=dict(map_id=signature[2],x=signature[3][0],y=signature[3][1])
    if not _exact(location,expected_location):return _review('bound_trainer_location_required',step_id,owner)
    if (type(battle) is not dict or battle.get('kind')!='trainer' or battle.get('active') is not True
            or type(battle.get('raw')) is not int or battle['raw']!=2
            or not _int(battle.get('observation_frame')) or battle['observation_frame']!=frame
            or type(battle.get('opponent_species')) is not str or not battle['opponent_species'].strip()):
        return _review('runtime_trainer_packet_unverified',step_id,owner)
    if type(previous) not in (list,tuple) or any(type(a) is not str or a not in _ACTIONS for a in previous):
        return _review('actual_previous_unverified',step_id,owner)
    progress=state.get('progress')
    if type(text) is not dict or type(progress) is not dict:return _review('original_text_progress_required',step_id,owner)
    for packet in (text,progress):
        if 'observation_frame' in packet and (not _int(packet['observation_frame']) or packet['observation_frame']!=frame):
            return _review('packet_frame_disagrees',step_id,owner)
    if owner is None:
        owner=step_id+'-medicine-ui-'+str(frame)
        if len(owner)>128:return _review('owner_length_unverified',step_id)
        if owner in _CONTROLLERS or owner in _BINDINGS or owner in _COMPLETED:return _review('owner_already_used',step_id)
        completed_frames=[]
        for done in _COMPLETED:
            old=_BINDINGS.get(done)
            if (type(old) is not dict or done not in _CONTROLLERS
                    or not _int(old.get('completed_frame')) or type(old.get('receipt')) is not dict
                    or old['receipt'].get('medicine_ui_complete') is not True):
                return _review('completed_receipt_lost',step_id)
            completed_frames.append(old['completed_frame'])
        if completed_frames and frame<=max(completed_frames):return _review('new_owner_requires_fresh_frame',step_id)
    try:
        sdk=_sdk_constants();before=pyboy.frame_count
        player=player_battle.read_player_battle(pyboy,observation_frame=frame,
            expected_location=location,constants=sdk,profile=player_battle.PROFILE)
        enemy=trainer_opponent.read_trainer_opponent(pyboy,observation_frame=frame,
            expected_location=location,constants=sdk,profile=trainer_opponent.PROFILE)
        after=pyboy.frame_count
    except Exception:return _review('readonly_snapshot_failed',step_id,owner if record is not None else None)
    if not _int(before) or not _int(after) or before!=frame or after!=frame:
        return _review('snapshot_frame_changed',step_id,owner if record is not None else None)
    if not _proof(player,player_battle,frame,location):return _review('player_snapshot_unverified',step_id,owner if record is not None else None)
    if not _proof(enemy,trainer_opponent,frame,location,enemy=True):return _review('trainer_snapshot_unverified',step_id,owner if record is not None else None)
    now=time.monotonic()
    if not _clock(now):return _review('clock_unverified',step_id,owner if record is not None else None)
    if controller is None:
        try:controller=medicine.TrainerMedicineUIController(expected,owner=owner,max_calls=240,max_seconds=60,max_waits=30)
        except Exception:return _review('controller_constructor_failed',step_id)
        record=dict(step_id=step_id,signature=signature,intent=deepcopy(expected),initial_frame=frame,
                    bridge_error=None,receipt=None,completed_frame=None)
        _CONTROLLERS[owner],_BINDINGS[owner]=controller,record
    try:
        controller.__class__=medicine.TrainerMedicineUIController
        result=controller.context(text,progress,owner=owner,location=location,battle_state=battle,
            player_snapshot=player,enemy_proof=enemy,frame=frame,previous=previous,now=now)
    except Exception:return _review('controller_context_failed',step_id,owner)
    if type(result) is not dict:return _review('controller_result_unverified',step_id,owner)
    if result.get('medicine_ui_complete') is True:
        if (result.get('medicine_handoff')!='existing_battle' or result.get('enemy_turn_resolved') is not False
                or result.get('survival_approved') is not False or result.get('available_actions')!=['wait']
                or result.get('field_move_complete') is True or result.get('battle_medicine_complete') is True):
            return _review('ui_completion_receipt_unverified',step_id,owner)
        record['receipt'],record['completed_frame']=deepcopy(result),frame
        _COMPLETED.add(owner)
    elif result.get('field_move_complete') is True or result.get('battle_medicine_complete') is True:
        return _review('non_ui_completion_rejected',step_id,owner)
    return {**result,'medicine_ui_owner':owner},step_id
