"""明確HM教學意圖與固定站位的正常選單橋接，不讀寫遊戲RAM。"""
import importlib
import time
from . import hm_teaching
importlib.reload(hm_teaching)

_CONTROLLERS=globals().get('_CONTROLLERS',{})
_BINDINGS=globals().get('_BINDINGS',{})
_COMPLETED=globals().get('_COMPLETED',set())
_INTENT_LOCATIONS={
    'teach_surf_nidoking':(hm_teaching.SURF_INTENT,155,(4,5)),
    'teach_strength_snorlax':(hm_teaching.STRENGTH_INTENT,155,(4,5)),
    'teach_fly_fearow':(hm_teaching.FLY_INTENT,188,(1,3)),
    'teach_surf_lapras':(hm_teaching.LAPRAS_SURF_INTENT,171,(3,4)),
}
MECHANICS=set(_INTENT_LOCATIONS)

def _review(reason):
    return {'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
            'review_reason':reason}

def applies(step_id,step):
    return bool(set(_BINDINGS)-_COMPLETED) or step_id in _BINDINGS or bool(
        step and step.get('mechanic') in MECHANICS)

def context(state,plan,step_id,text,grid):
    active=set(_BINDINGS)-_COMPLETED
    if active and active!={step_id}:return _review('hm_teaching_owner_changed'),step_id
    step=next((s for s in plan['steps'] if s['id']==step_id),None)
    if not step or step.get('mechanic') not in MECHANICS:
        return (_review('hm_teaching_intent_changed'),step_id) if step_id in _BINDINGS else None
    expected,map_id,target=_INTENT_LOCATIONS[step['mechanic']]
    if (step.get('kind')!='interact' or step.get('map_id')!=map_id or step.get('target')!=list(target)
            or type(step.get('map_id')) is not int
            or any(type(v) is not int for v in step['target'])
            or step.get('hm_intent')!=expected or any(type(step['hm_intent'].get(k)) is not type(v)
                                                    for k,v in expected.items())):
        return _review('hm_teaching_explicit_intent_unverified'),step_id
    binding=(step['kind'],step['map_id'],tuple(step['target']),tuple(sorted(expected.items())))
    if step_id in _BINDINGS and _BINDINGS[step_id]!=binding:
        return _review('hm_teaching_intent_changed'),step_id
    controller=_CONTROLLERS.get(step_id)
    if controller is None:
        if state.get('location')!={'map_id':map_id,'x':target[0],'y':target[1]}:return None
        controller=hm_teaching.HMTeachingController(expected)
        _CONTROLLERS[step_id]=controller;_BINDINGS[step_id]=binding
    controller.__class__=hm_teaching.HMTeachingController
    battle=state.get('battle_state',{})
    if (battle.get('kind')!='none' or battle.get('active') is not False
            or type(battle.get('raw')) is not int or battle['raw']!=0
            or type(battle.get('observation_frame')) is not int
            or battle['observation_frame']!=state.get('frame')):
        return _review('hm_teaching_battle_signal_unverified'),step_id
    revision=step.get('reviewed_hm_revision',0)
    if (type(revision) is int and revision>getattr(controller,'_reviewed_revision',0)
            and controller.error is not None and step.get('reviewed_hm_error')==controller.error):
        controller.error=None;controller.started=time.monotonic();controller.calls=controller.waits=0
        controller._reviewed_revision=revision
    from .campaign_transactions import ui_overworld_ready
    result=controller.context(text,state['progress'],location=state['location'],frame=state['frame'],
        now=time.monotonic(),overworld_ready=ui_overworld_ready(text,grid),battle_active=False)
    if result.get('hm_teaching_complete'):
        _COMPLETED.add(step_id)
        index=plan['steps'].index(step)+1
        return result,(plan['steps'][index]['id'] if index<len(plan['steps']) else 'complete')
    return result,step_id
