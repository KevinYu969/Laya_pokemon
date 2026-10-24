"""來源限定洋館雕像交易橋接；不直接執行按鍵或寫入遊戲資料。"""
import importlib
import json
import time
from . import mansion_statue
importlib.reload(mansion_statue)
MECHANIC='mansion_statue'
_CONTROLLERS=globals().get('_CONTROLLERS',{})
_BINDINGS=globals().get('_BINDINGS',{})
_COMPLETED=globals().get('_COMPLETED',set())
_LOCATIONS={(215,(10,6)),(216,(18,26)),(216,(20,4))}


def _review(reason):
 return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],review_reason='mansion_statue_bridge_'+reason)


def applies(step_id,step):
 return bool(set(_BINDINGS)-_COMPLETED) or step_id in _BINDINGS or bool(step and step.get('mechanic')==MECHANIC)


def context(pyboy,state,plan,step_id,text,grid,previous):
 active=set(_BINDINGS)-_COMPLETED
 if active and active!={step_id}:return _review('owner_changed'),step_id
 matches=[s for s in plan.get('steps',[]) if s.get('id')==step_id]
 if len(matches)!=1:return (_review('step_unverified'),step_id) if active else None
 step=matches[0];intent=step.get('statue_intent')
 if step.get('mechanic')!=MECHANIC:
  return (_review('intent_changed'),step_id) if step_id in _BINDINGS else None
 if (not mansion_statue._intent(intent)
     or step.get('kind')!='interact' or type(step.get('map_id')) is not int
     or step['map_id']!=intent['map_id'] or step.get('target')!=[intent['player_x'],intent['player_y']]
     or any(type(v) is not int for v in step.get('target',[]))
     or any(k in step for k in ('next_map','terminal','event','item','badge','await_script_event'))):
  return _review('explicit_intent_unverified'),step_id
 try:binding=json.dumps([MECHANIC,intent,plan.get('training_job')],sort_keys=True,ensure_ascii=False,allow_nan=False)
 except (TypeError,ValueError):return _review('owner_unverified'),step_id
 if step_id in _BINDINGS and _BINDINGS[step_id]!=binding:return _review('intent_or_owner_changed'),step_id
 c=_CONTROLLERS.get(step_id)
 if step_id in _BINDINGS and c is None:return _review('original_controller_missing'),step_id
 if c is not None and step_id not in _BINDINGS:return _review('original_binding_missing'),step_id
 loc=state.get('location');expected=dict(map_id=intent['map_id'],x=intent['player_x'],y=intent['player_y'])
 if c is None and loc!=expected:return None
 from .campaign_transactions import verified_blank_transaction_world,ui_overworld_ready
 from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
 signal=mansion_statue.read_mansion_statue(pyboy,state.get('frame'),constants)
 if c is None:
  if not verified_blank_transaction_world(text,grid):return _review('initial_closed_world_required'),step_id
  if signal.get('read_valid') is not True:return _review('initial_source_unknown'),step_id
  c=mansion_statue.MansionStatueController(intent);_CONTROLLERS[step_id]=c;_BINDINGS[step_id]=binding
 c.__class__=mansion_statue.MansionStatueController
 result=c.context(text,state.get('progress'),location=loc,battle_state=state.get('battle_state'),grid=grid,
                  signal=signal,frame=state.get('frame'),previous=previous,now=time.monotonic(),
                  overworld_ready=ui_overworld_ready(text,grid))
 if result.get('mansion_statue_complete') is True:
  _COMPLETED.add(step_id);result={**result,'field_move_complete':True,'field_move_kind':'mansion-statue'}
  i=plan['steps'].index(step)+1;return result,(plan['steps'][i]['id'] if i<len(plan['steps']) else 'complete')
 return result,step_id
