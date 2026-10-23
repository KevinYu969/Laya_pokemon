"""只橋接已審的玉虹屋頂單瓶購買，保留跨檢討交易基線。"""
import importlib
import time
from . import vending_water
importlib.reload(vending_water)

_CONTROLLERS=globals().get('_CONTROLLERS',{})
_BINDINGS=globals().get('_BINDINGS',{})
_COMPLETED=globals().get('_COMPLETED',set())
MECHANIC='buy_fresh_water'


def _review(reason):
    return {'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
            'review_reason':reason}


def applies(step_id,step):
    return bool(set(_BINDINGS)-_COMPLETED) or step_id in _BINDINGS or bool(
        step and step.get('mechanic')==MECHANIC)


def context(pyboy,state,plan,step_id,text,grid):
    active=set(_BINDINGS)-_COMPLETED
    if active and active!={step_id}:return _review('vending_owner_changed'),step_id
    step=next((s for s in plan['steps'] if s['id']==step_id),None)
    if not step or step.get('mechanic')!=MECHANIC:
        return (_review('vending_intent_changed'),step_id) if step_id in _BINDINGS else None
    intent=step.get('water_intent')
    if (step.get('kind')!='interact' or step.get('map_id')!=126 or step.get('target')!=[11,2]
            or intent!=vending_water.INTENT
            or any(type(intent.get(k)) is not type(v) for k,v in vending_water.INTENT.items())):
        return _review('vending_explicit_intent_unverified'),step_id
    binding=(MECHANIC,126,(11,2),tuple(sorted(intent.items())))
    if step_id in _BINDINGS and _BINDINGS[step_id]!=binding:
        return _review('vending_intent_changed'),step_id
    controller=_CONTROLLERS.get(step_id)
    if state.get('location')!={'map_id':126,'x':11,'y':2}:
        return (_review('vending_location_changed'),step_id) if step_id in _BINDINGS else None
    battle=state.get('battle_state',{})
    if (battle.get('kind')!='none' or battle.get('active') is not False
            or type(battle.get('raw')) is not int or battle['raw']!=0
            or type(battle.get('observation_frame')) is not int
            or battle['observation_frame']!=state.get('frame')):
        return _review('vending_battle_signal_unverified'),step_id
    try:facing_raw=pyboy.memory[0xC109]
    except (AttributeError,IndexError,KeyError,TypeError,ValueError,RuntimeError):
        return _review('vending_facing_unverified'),step_id
    if type(facing_raw) is not int or facing_raw not in {0,4,8,12}:
        return _review('vending_facing_unverified'),step_id
    from .campaign_transactions import ui_overworld_ready,verified_blank_transaction_world
    ready=ui_overworld_ready(text,grid)
    if controller is None:
        if not verified_blank_transaction_world(text,grid):
            return _review('vending_initial_closed_world_required'),step_id
        if facing_raw!=4:
            # 正常導航須先從11,3走到11,2；交易不另設未綁基線的轉向支線。
            return _review('vending_initial_up_facing_required'),step_id
        _BINDINGS[step_id]=binding
        controller=vending_water.VendingWaterController(intent)
        _CONTROLLERS[step_id]=controller
    controller.__class__=vending_water.VendingWaterController
    revision=step.get('reviewed_vending_revision',0)
    if (type(revision) is int and revision>getattr(controller,'_reviewed_revision',0)
            and controller.error is not None and step.get('reviewed_vending_error')==controller.error):
        controller.error=None;controller.started=time.monotonic();controller.calls=controller.waits=0
        controller._reviewed_revision=revision
    result=controller.context(text,state['progress'],
        location={**state['location'],'facing':{0:'down',4:'up',8:'left',12:'right'}[facing_raw],
                  'facing_raw':facing_raw},battle_state=battle,frame=state['frame'],now=time.monotonic(),
        overworld_ready=ready)
    if result.get('vending_water_complete'):
        _COMPLETED.add(step_id)
        index=plan['steps'].index(step)+1
        return result,(plan['steps'][index]['id'] if index<len(plan['steps']) else 'complete')
    return result,step_id
