"""Route23兩筆明確交易的橋接候選；只讀真觀測與輸出Laya子目標。

保留controller/owner/error/baseline/pending/budget跨reload。全peer mutex、
戰敗/健康/捕捉/學招守門由parent在此橋接之前執行；此處另擋已載入peer。
"""
import importlib
import json
import sys
import time

from . import route23_surf as surf, route23_water as water
from .rocket_movement import read_rocket_movement

importlib.reload(surf)
importlib.reload(water)
MECHANICS={'route23_surf','route23_water'}
_CONTROLLERS=globals().get('_CONTROLLERS',{})
_BINDINGS=globals().get('_BINDINGS',{})
_COMPLETED=globals().get('_COMPLETED',set())
_FORBIDDEN={'event','item','badge','next_map','nextmap','terminal','await_script_event'}
_BATTLE_PHASES={'battle_menu','battle_bag','battle_animation','battle_dialogue','learning_menu','dialogue','strategy_review','campaign_review'}
_ACTIONS={'up','down','left','right','a','b','start','wait'}
_PEERS=('battle_medicine_bridge','trainer_medicine_ui_bridge','pallet_surf_bridge','route21_water_bridge',
        'fly_viridian_bridge','fly_pallet_bridge','player_pc_bridge','cinnabar_purchase_bridge',
        'victory_strength_bridge','victory_first_boulder_bridge','victory_later_boulders_bridge',
        'safari_entry','hm_teaching_bridge','vending_bridge','saffron_guard_bridge','silph_card_bridge',
        'lapras_bridge','mansion_native_landing','mansion_transition_ready','mansion_statue_bridge',
        'mansion_secret_key_bridge','campaign_transactions')


def _review(reason):return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],review_reason='route23_bridge_'+reason)


def _active():
    if type(_BINDINGS) is not dict or type(_CONTROLLERS) is not dict or type(_COMPLETED) is not set:return None
    return (set(_BINDINGS)|set(_CONTROLLERS))-_COMPLETED


def applies(step_id,step):
    active=_active()
    return active is None or bool(active) or step_id in _BINDINGS or isinstance(step,dict) and step.get('mechanic') in MECHANICS


def _canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def _peer_conflict():
    for name in _PEERS:
        module=sys.modules.get('laya_pokemon.'+name)
        if module is None:continue
        bindings=getattr(module,'_BINDINGS',{})
        controllers=getattr(module,'_CONTROLLERS',{})
        completed=getattr(module,'_COMPLETED',set())
        if type(bindings) is not dict or type(controllers) is not dict or type(completed) is not set:return name+'_registry_unknown'
        if (set(bindings)|set(controllers))-completed:return name+'_active'
    safari=sys.modules.get('laya_pokemon.safari_entry')
    if safari is not None and getattr(safari,'_RUN_CONTROLLER',None) is not None:return 'safari_run_active'
    capture=sys.modules.get('laya_pokemon.capture_transaction')
    if capture is not None:
        sessions=getattr(capture,'_SESSIONS',None)
        if type(sessions) is not dict:return 'capture_registry_unknown'
        if any(type(s) is not dict or s.get('done') is not True for s in sessions.values()):return 'capture_active'
    return None


def _explicit(step):
    kind=step.get('mechanic')
    if kind not in MECHANICS:return None
    entry=kind=='route23_surf';intent_key='surf_intent' if entry else 'water_intent'
    expected=surf.ROUTE23_SURF_INTENT if entry else water.INTENT
    start=surf.START if entry else dict(map_id=34,x=10,y=103)
    intent=step.get(intent_key)
    good=(step.get('kind')=='interact' and type(step.get('map_id')) is int and step['map_id']==34
          and type(step.get('target')) is list and step['target']==[start['x'],start['y']]
          and all(type(n) is int for n in step['target']) and not _FORBIDDEN.intersection(step)
          and type(intent) is dict and intent==expected and set(intent)==set(expected)
          and all(type(intent[k]) is type(v) for k,v in expected.items())
          and (entry or water._intent(intent)) and ('face' not in step or entry and step['face']=='up'))
    return (entry,start,intent) if good else None


def _handoff(state,result,step_id):
    phase=state.get('phase');choices=state.get('available_actions');objective=state.get('objective')
    valid=(type(phase) is str and phase in _BATTLE_PHASES and isinstance(objective,str) and bool(objective)
           and type(choices) is list and bool(choices) and all(type(a) is str and a in _ACTIONS for a in choices)
           and len(choices)==len(set(choices)) and (choices==['wait'] or len(choices)>=2))
    if not valid:return {**result,'route23_owner_step':step_id,'route23_battle_delegate':'await_existing_battle_context'}
    out={k:v for k,v in result.items() if k not in ('phase','objective','available_actions','controller_menu_verified')}
    out.update(phase=phase,objective=objective,available_actions=list(choices),route23_owner_step=step_id,route23_battle_delegate='existing_battle')
    for key in ('controller_menu_verified','review_reason'):
        if key in state:out[key]=state[key]
    return out


def context(pyboy,state,plan,step_id,text,grid,previous):
    active=_active()
    if active is None:return _review('registries_unknown'),step_id
    if type(step_id) is not str or not step_id:return _review('step_id_unverified'),step_id
    if active and active!={step_id}:return _review('owner_changed'),step_id
    if not isinstance(plan,dict) or type(plan.get('steps')) is not list:return _review('plan_unverified'),step_id
    ids=[s.get('id') if isinstance(s,dict) else None for s in plan['steps']]
    if any(type(i) is not str or not i for i in ids) or len(ids)!=len(set(ids)):return _review('plan_ids_unverified'),step_id
    if step_id not in ids:return (_review('step_missing'),step_id) if active or step_id in _BINDINGS else None
    step=plan['steps'][ids.index(step_id)]
    if step.get('mechanic') not in MECHANICS:return (_review('intent_changed'),step_id) if step_id in _BINDINGS else None
    contract=_explicit(step)
    if contract is None:return _review('explicit_intent_unverified'),step_id
    entry,start,intent=contract
    try:
        if 'training_job' not in plan or plan['training_job'] is None:raise ValueError('missing job')
        binding=(_canonical(step),_canonical(plan['training_job']))
    except(TypeError,ValueError):return _review('owner_unverified'),step_id
    if step_id in _BINDINGS and _BINDINGS[step_id]!=binding:return _review('intent_or_owner_changed'),step_id
    controller=_CONTROLLERS.get(step_id)
    if step_id in _BINDINGS and controller is None:return _review('original_controller_missing'),step_id
    if (controller is not None or step_id in _COMPLETED) and step_id not in _BINDINGS:return _review('original_binding_missing'),step_id
    if step_id in _COMPLETED:return _review('completed_step_reentered'),step_id
    if not isinstance(state,dict) or not isinstance(state.get('location'),dict):return _review('state_unverified'),step_id
    frame=state.get('frame');pos={k:state['location'].get(k) for k in ('map_id','x','y')}
    if type(frame) is not int or frame<0 or any(type(v) is not int or not 0<=v<=255 for v in pos.values()):return _review('frame_or_location_unverified'),step_id
    if controller is None and pos!=start:return None
    conflict=_peer_conflict()
    if conflict:return _review('peer_transaction_'+conflict),step_id
    from .campaign_transactions import verified_blank_transaction_world,ui_overworld_ready
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
    signal=surf.read_surf_observation(pyboy,frame,sdk)
    movement=read_rocket_movement(pyboy,observation_frame=frame)
    if controller is None:
        if not verified_blank_transaction_world(text,grid):return _review('initial_closed_world_required'),step_id
        if not isinstance(signal,dict) or signal.get('read_valid') is not True or not isinstance(movement,dict) or movement.get('read_valid') is not True:return _review('initial_getter_unverified'),step_id
        if (signal.get('profile')!=surf.PROFILE or signal.get('source_commit')!=surf.SOURCE_COMMIT
                or type(signal.get('observation_frame')) is not int or signal['observation_frame']!=frame
                or signal.get('location')!=pos or type(signal.get('mode')) is not int or signal['mode']!=(0 if entry else 2)
                or type(signal.get('battle_raw')) is not int or signal['battle_raw']!=0
                or not surf._source_signal(signal) or surf._idle(movement,frame) is not True
                or entry and (signal.get('facing')!='up' or type(signal.get('facing_raw')) is not int or signal['facing_raw']!=4)):
            return _review('initial_native_stance_unverified'),step_id
        controller=surf.Route23SurfController(intent) if entry else water.Route23WaterController(intent)
        _CONTROLLERS[step_id]=controller;_BINDINGS[step_id]=binding
    controller.__class__=surf.Route23SurfController if entry else water.Route23WaterController
    if entry:
        result=controller.context(text,state.get('progress'),location=state['location'],battle_state=state.get('battle_state'),
            grid=grid,signal=signal,movement=movement,frame=frame,previous=previous,now=time.monotonic(),overworld_ready=ui_overworld_ready(text,grid))
    else:
        result=controller.context({**state,'text':text},grid=grid,signal=signal,movement=movement,previous=previous,now=time.monotonic())
    if not isinstance(result,dict):return _review('controller_result_unverified'),step_id
    if result.get('route23_water_battle_handoff') is True:return _handoff(state,result,step_id),step_id
    completed=result.get('surf_entry_complete') is True if entry else result.get('route23_water_complete') is True
    if completed:
        expected=surf.LANDING if entry else dict(map_id=34,x=8,y=71)
        if (pos!=expected or signal.get('read_valid') is not True or signal.get('profile')!=surf.PROFILE
                or signal.get('source_commit')!=surf.SOURCE_COMMIT or signal.get('location')!=pos
                or type(signal.get('observation_frame')) is not int or signal['observation_frame']!=frame
                or type(signal.get('mode')) is not int or signal['mode']!=(2 if entry else 0)
                or not surf._source_signal(signal) or surf._idle(movement,frame) is not True
                or not verified_blank_transaction_world(text,grid) or controller.error is not None):return _review('completion_native_receipt_unverified'),step_id
        if not entry:
            goals=getattr(controller,'goal_frames',None)
            if (getattr(controller,'pending','unknown') is not None or getattr(controller,'in_battle',None) is not False
                    or getattr(controller,'guard','unknown') is not None or type(goals) is not list or len(goals)<2
                    or any(type(f) is not int for f in goals) or not goals[-2]<goals[-1]==frame
                    or getattr(controller,'index',None)!=len(water.PATH)-1 or signal['guard_flags']!=getattr(controller,'flags',None)
                    or getattr(controller,'stage',None)!='complete' or not water._grid(grid,water.PATH[-1],frame)
                    or water._fingerprint(state.get('progress'))!=getattr(controller,'fingerprint',None)):
                return _review('completion_water_owner_unverified'),step_id
        if entry and (type(getattr(controller,'closed_frame',None)) is not int or controller.closed_frame>=frame
                or getattr(controller,'prompt_ack',None) is not True or getattr(controller,'surf_selected',None) is not True
                or getattr(controller,'pending','unknown') is not None or getattr(controller,'stage',None)!='complete'
                or not surf._world(grid,pos,frame)):
            return _review('completion_surf_owner_unverified'),step_id
        _COMPLETED.add(step_id)
        result={**result,'field_move_complete':True,'field_move_kind':'route23-surf' if entry else 'route23-water'}
        index=ids.index(step_id)+1
        return result,ids[index] if index<len(ids) else 'complete'
    return {**result,'route23_owner_step':step_id},step_id
