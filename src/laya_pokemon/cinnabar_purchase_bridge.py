"""紅蓮兩種固定購藥意圖橋接；只有唯讀站位getter與純子目標。"""
from collections.abc import Mapping
from copy import deepcopy
import importlib
import json
import time

from . import cinnabar_purchase
importlib.reload(cinnabar_purchase)

MECHANIC='cinnabar_purchase'
SOURCE_COMMIT='a53671100ec22e5394ff26ec028d0812a238dae2'
_CONTROLLER=globals().get('_CONTROLLER',{})
_BINDINGS=globals().get('_BINDINGS',{})
_COMPLETED=globals().get('_COMPLETED',set())
_ADDRESSES=(0xD35E,0xC109,0xD361,0xD362)


def _review(reason):
    return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
                review_reason='cinnabar_purchase_bridge_'+reason)


def _int(value,maximum=0x7fffffffffffffff):
    return type(value)is int and 0<=value<=maximum


def _sdk_constants():
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    return constants


def _read_stance(pyboy,frame,constants):
    """來源D35E/C109/D361/D362，同幀兩遍；False/float不等於byte0。"""
    unknown=dict(read_valid=False,read_error='source_or_frame_unverified',location=None)
    if not _int(frame):return unknown
    try:
        maps=getattr(constants,'MAPS',None)
        if not isinstance(maps,Mapping)or type(maps.get('cinnabar_mart'))is not int or maps['cinnabar_mart']!=172:
            return unknown
        before=pyboy.frame_count
        first=tuple(pyboy.memory[a]for a in _ADDRESSES)
        second=tuple(pyboy.memory[a]for a in _ADDRESSES)
        after=pyboy.frame_count
    except (AttributeError,KeyError,IndexError,TypeError,ValueError,RuntimeError,OSError):
        return {**unknown,'read_error':'getter_failed'}
    if (not _int(before)or not _int(after)or before!=frame or after!=before
            or any(not _int(v,255)for v in first+second)or first!=second):
        return {**unknown,'read_error':'torn_or_unknown_byte'}
    mid,facing,y,x=first
    if (mid,facing,y,x)!=(172,8,5,2):
        return {**unknown,'read_error':'stance_disagrees'}
    return dict(read_valid=True,read_error=None,observation_frame=frame,
                location=dict(map_id=mid,x=x,y=y,facing='left',facing_raw=facing))


def _fixed_intent(intent):
    if type(intent)is not dict:return None
    for expected in (cinnabar_purchase.HYPER_POTION_INTENT,cinnabar_purchase.FULL_HEAL_INTENT):
        if (type(expected)is dict and set(intent)==set(expected)
                and all(type(intent[k])is type(v)and intent[k]==v for k,v in expected.items())):
            return deepcopy(expected)
    return None


def _canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def applies(step_id,step):
    return bool(set(_BINDINGS)-_COMPLETED)or(type(step_id)is str and step_id in _BINDINGS)or bool(
        isinstance(step,dict)and step.get('mechanic')==MECHANIC)


def context(pyboy,state,plan,step_id,text,grid,previous):
    if type(step_id)is not str or not step_id:return _review('step_id_unverified'),step_id
    active=set(_BINDINGS)-_COMPLETED
    if active and active!={step_id}:return _review('owner_changed'),step_id
    if not isinstance(plan,dict)or type(plan.get('steps'))is not list:
        return _review('plan_unverified'),step_id
    matches=[s for s in plan['steps']if isinstance(s,dict)and s.get('id')==step_id]
    if len(matches)!=1:return _review('unique_step_required'),step_id
    step=matches[0]
    if step.get('mechanic')!=MECHANIC:
        return (_review('intent_changed'),step_id)if step_id in _BINDINGS or active else None
    expected=_fixed_intent(step.get('purchase_intent'))
    if (expected is None or step.get('kind')!='interact'or type(step.get('map_id'))is not int
            or step['map_id']!=172 or type(step.get('target'))is not list or step['target']!=[2,5]
            or any(type(v)is not int for v in step['target'])or type(step.get('face'))is not str or step['face']!='left'
            or any(k in step for k in ('event','item','next_map','terminal','badge','await_script_event'))):
        return _review('explicit_intent_unverified'),step_id
    binding=(MECHANIC,172,(2,5),'left',_canonical(expected))
    if step_id in _BINDINGS and _BINDINGS[step_id]!=binding:
        return _review('intent_changed'),step_id
    controller=_CONTROLLER.get(step_id)
    if ((controller is None)!=(step_id not in _BINDINGS)
            or step_id in _COMPLETED and controller is None):
        return _review('controller_or_binding_lost'),step_id
    if not isinstance(state,dict)or not _int(state.get('frame')):
        return _review('state_frame_unverified'),step_id
    loc=state.get('location')
    if (type(loc)is not dict or set(loc)!={'map_id','x','y'}or loc!={'map_id':172,'x':2,'y':5}
            or any(type(v)is not int for v in loc.values())):
        return _review('location_unverified'),step_id
    frame=state['frame'];battle=state.get('battle_state')
    if (not isinstance(battle,dict)or battle.get('kind')!='none'or battle.get('active')is not False
            or type(battle.get('raw'))is not int or battle['raw']!=0
            or type(battle.get('observation_frame'))is not int or battle['observation_frame']!=frame):
        return _review('battle_not_verified_none'),step_id
    if type(previous)not in (list,tuple)or any(type(a)is not str or a not in
        ('a','b','up','down','left','right','start','wait')for a in previous):
        return _review('actual_previous_unverified'),step_id
    for packet in (text,state.get('progress')):
        if isinstance(packet,dict)and 'observation_frame'in packet and (
            not _int(packet['observation_frame'])or packet['observation_frame']!=frame):
            return _review('packet_frame_disagrees'),step_id
    signal=_read_stance(pyboy,frame,_sdk_constants())
    if signal['read_valid']is not True:return _review(signal['read_error']),step_id
    from .campaign_transactions import verified_blank_transaction_world,ui_overworld_ready
    ready=ui_overworld_ready(text,grid)
    if type(ready)is not bool:return _review('ready_not_boolean'),step_id
    if controller is None:
        if not ready or verified_blank_transaction_world(text,grid)is not True:
            return _review('initial_closed_world_required'),step_id
        controller=cinnabar_purchase.CinnabarPurchaseController(expected,max_calls=240,max_seconds=60,max_waits=30)
        _CONTROLLER[step_id]=controller;_BINDINGS[step_id]=binding
    controller.__class__=cinnabar_purchase.CinnabarPurchaseController
    result=controller.context(text,state.get('progress'),location=signal['location'],battle_state=battle,
        frame=frame,now=time.monotonic(),previous=previous,overworld_ready=ready,intent=expected)
    if not isinstance(result,dict):return _review('controller_result_unverified'),step_id
    if result.get('cinnabar_purchase_complete')is True:
        _COMPLETED.add(step_id)
        result={**result,'field_move_complete':True,'field_move_kind':'cinnabar-purchase'}
        index=plan['steps'].index(step)+1
        return result,(plan['steps'][index]['id']if index<len(plan['steps'])else'complete')
    return result,step_id
