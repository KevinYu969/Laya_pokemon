"""僅橋接16號路已審站位的原生飛往真新鎮，使用主迴圈真previous。"""
import importlib
import json
import time
from . import fly_pallet
importlib.reload(fly_pallet)

MECHANIC='fly_pallet'
_CONTROLLERS=globals().get('_CONTROLLERS',{})
_BINDINGS=globals().get('_BINDINGS',{})
_COMPLETED=globals().get('_COMPLETED',set())


def _review(reason):
    return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],review_reason=reason)


def applies(step_id,step):
    return bool(set(_BINDINGS)-_COMPLETED) or step_id in _BINDINGS or bool(step and step.get('mechanic')==MECHANIC)


def _review_native_map_window(controller,step,state,text,signal,now):
    """只續接1442553已核真新鎮完整地圖；不清已用額度或重建交易。"""
    revision=step.get('reviewed_fly_ui_revision')
    if revision is None or getattr(controller,'_reviewed_fly_ui_revision',None)==revision:
        return True
    current=controller._progress(state.get('progress'))
    if (type(revision) is not int or revision!=1
            or state.get('frame')!=1442553 or controller.last_frame!=1442553
            or state.get('location')!=dict(map_id=27,x=7,y=6)
            or controller.error!='fly_pallet_not_exact_initial_pallet_destination'
            or controller.stage!='destination' or controller.selected_user is not True
            or controller.destination_confirmed is not False or controller.destination_frame is not None
            or controller.pending is None or controller.pending.get('executed') is not True
            or controller.pending.get('action')!='a' or controller.pending.get('stage')!='destination'
            or current is None or current!=controller.baseline
            or signal.get('observation_frame')!=1442553
            or not fly_pallet._screen_proof(signal) or signal.get('window_visible') is not True
            or signal.get('raw_bytes')!=list(fly_pallet.PALLET_RAW)
            or fly_pallet._rows(text)!=fly_pallet._MAP_ROWS):
        return False
    paused=max(0.,now-controller.last_now)
    controller.started+=paused
    controller.error=None
    controller._reviewed_fly_ui_revision=revision
    controller.review_pause_adjustments=getattr(controller,'review_pause_adjustments',[])+[
        dict(source_frame=1442553,reason='verified_native_town_map_window_layer',seconds=paused)]
    return True


def context(pyboy,state,plan,step_id,text,grid,previous):
    active=set(_BINDINGS)-_COMPLETED
    if active and active!={step_id}:return _review('fly_pallet_owner_changed'),step_id
    step=next((s for s in plan.get('steps',[]) if s.get('id')==step_id),None)
    if not step or step.get('mechanic')!=MECHANIC:
        return (_review('fly_pallet_intent_changed'),step_id) if active else None
    intent=step.get('fly_intent')
    canonical=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
    if (type(intent) is not dict or canonical(intent)!=canonical(fly_pallet.FLY_PALLET_INTENT)
            or step.get('kind')!='interact' or type(step.get('map_id')) is not int or step['map_id']!=27
            or step.get('target')!=[7,6]
            or any(k in step for k in ('next_map','terminal','event','item','badge','await_script_event'))):
        return _review('fly_pallet_explicit_intent_unverified'),step_id
    binding=(MECHANIC,27,(7,6),canonical(intent))
    if step_id in _BINDINGS and _BINDINGS[step_id]!=binding:
        return _review('fly_pallet_intent_changed'),step_id
    controller=_CONTROLLERS.get(step_id)
    if controller is None and state.get('location')!={'map_id':27,'x':7,'y':6}:return None
    from .campaign_transactions import verified_blank_transaction_world,ui_overworld_ready
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    signal=fly_pallet.read_fly_observation(pyboy,state.get('frame'),constants)
    if controller is None:
        if not verified_blank_transaction_world(text,grid):
            return _review('fly_pallet_initial_closed_world_required'),step_id
        if signal.get('read_valid') is not True:
            return _review('fly_pallet_initial_signal_unverified'),step_id
        controller=fly_pallet.FlyPalletController(intent)
        _CONTROLLERS[step_id]=controller;_BINDINGS[step_id]=binding
    controller.__class__=fly_pallet.FlyPalletController
    if not _review_native_map_window(controller,step,state,text,signal,time.monotonic()):
        return _review('fly_pallet_named_window_review_unverified'),step_id
    result=controller.context(text,state.get('progress'),location=state.get('location'),
        battle_state=state.get('battle_state'),grid=grid,signal=signal,frame=state.get('frame'),
        previous=previous,now=time.monotonic(),overworld_ready=ui_overworld_ready(text,grid))
    if result.get('fly_pallet_complete') is True:
        _COMPLETED.add(step_id)
        result={**result,'field_move_complete':True,'field_move_kind':'fly-pallet'}
        index=plan['steps'].index(step)+1
        return result,(plan['steps'][index]['id'] if index<len(plan['steps']) else 'complete')
    return result,step_id
