"""Route7單瓶清水交易的實況橋接；無直接按鍵或遊戲資料寫入。"""
import importlib
import json
import time
from . import saffron_guard
importlib.reload(saffron_guard)
_CONTROLLERS=globals().get('_CONTROLLERS',{})
_BINDINGS=globals().get('_BINDINGS',{})
_COMPLETED=globals().get('_COMPLETED',set())
MECHANIC='saffron_guard_fresh_water'


def _review(reason):
    return {'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
            'review_reason':reason}


def applies(step_id,step):
    return bool(set(_BINDINGS)-_COMPLETED) or step_id in _BINDINGS or bool(
        step and step.get('mechanic')==MECHANIC)


def context(pyboy,state,plan,step_id,text,grid):
    active=set(_BINDINGS)-_COMPLETED
    if active and active!={step_id}:return _review('saffron_guard_owner_changed'),step_id
    step=next((s for s in plan['steps'] if s['id']==step_id),None)
    if not step or step.get('mechanic')!=MECHANIC:
        return (_review('saffron_guard_intent_changed'),step_id) if step_id in _BINDINGS else None
    intent=step.get('guard_intent')
    if (step.get('kind')!='interact' or step.get('map_id')!=76 or step.get('target')!=[2,4]
            or intent!=saffron_guard.INTENT
            or any(type(intent.get(k)) is not type(v) for k,v in saffron_guard.INTENT.items())
            or any(type(v) is not int for k in ('trigger_from','trigger_at') for v in intent[k])):
        return _review('saffron_guard_explicit_intent_unverified'),step_id
    binding=(MECHANIC,76,(2,4),json.dumps(intent,sort_keys=True,separators=(',',':')))
    if step_id in _BINDINGS and _BINDINGS[step_id]!=binding:
        return _review('saffron_guard_intent_changed'),step_id
    controller=_CONTROLLERS.get(step_id)
    if controller is None:
        if state.get('location')!={'map_id':76,'x':2,'y':4}:return None
        controller=saffron_guard.SaffronGuardController(intent)
        _CONTROLLERS[step_id]=controller;_BINDINGS[step_id]=binding
    controller.__class__=saffron_guard.SaffronGuardController
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    signal=saffron_guard.read_saffron_guard(pyboy,observation_frame=state.get('frame'),
                                         expected_location=state.get('location'),constants=constants)
    revision=step.get('reviewed_guard_revision',0)
    if (type(revision) is int and revision>getattr(controller,'_reviewed_revision',0)
            and controller.error is not None and step.get('reviewed_guard_error')==controller.error):
        controller.error=None;controller.started=time.monotonic();controller.calls=controller.waits=0
        controller._reviewed_revision=revision
    from .campaign_transactions import ui_overworld_ready
    result=controller.context(text,state['progress'],location=state['location'],
        battle_state=state.get('battle_state'),guard_signal=signal,frame=state.get('frame'),
        now=time.monotonic(),overworld_ready=ui_overworld_ready(text,grid))
    if result.get('saffron_guard_complete'):
        _COMPLETED.add(step_id)
        index=plan['steps'].index(step)+1
        return result,(plan['steps'][index]['id'] if index<len(plan['steps']) else 'complete')
    return result,step_id
