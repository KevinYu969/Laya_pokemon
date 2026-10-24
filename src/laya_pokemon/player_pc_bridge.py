"""將明確、可逆的兩種TM存物意圖接到原生PC；保留owner及原基線。"""
import importlib
import time
from . import player_pc_deposit
importlib.reload(player_pc_deposit)

MECHANIC='player_pc_deposit'
_CONTROLLERS=globals().get('_CONTROLLERS',{})
_BINDINGS=globals().get('_BINDINGS',{})
_COMPLETED=globals().get('_COMPLETED',set())


def _review(reason):
    return {'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
            'review_reason':reason}


def applies(step_id,step):
    return bool(set(_BINDINGS)-_COMPLETED) or step_id in _BINDINGS or bool(
        step and step.get('mechanic')==MECHANIC)


def context(pyboy,state,plan,step_id,text,grid,previous):
    active=set(_BINDINGS)-_COMPLETED
    if active and active!={step_id}:return _review('player_pc_owner_changed'),step_id
    step=next((s for s in plan.get('steps',[]) if s.get('id')==step_id),None)
    if not isinstance(step,dict) or step.get('mechanic')!=MECHANIC:
        return (_review('player_pc_intent_changed'),step_id) if active else None
    intent=step.get('pc_intent')
    expected={**player_pc_deposit.INTENT_BASE,'item':intent.get('item') if isinstance(intent,dict) else None}
    if (type(intent) is not dict or intent!=expected
            or any(type(intent.get(k)) is not type(v) for k,v in expected.items())
            or type(intent.get('item')) is not int or intent['item'] not in (234,221)
            or step.get('kind')!='interact' or type(step.get('map_id')) is not int
            or step['map_id']!=182 or step.get('target')!=[13,4] or step.get('face')!='up'
            or any(k in step for k in ('next_map','terminal','event','item','badge','await_script_event'))):
        return _review('player_pc_explicit_intent_unverified'),step_id
    binding=(MECHANIC,182,(13,4),'up',tuple(sorted(intent.items())))
    if step_id in _BINDINGS and _BINDINGS[step_id]!=binding:
        return _review('player_pc_intent_changed'),step_id
    loc=state.get('location')
    if loc!={'map_id':182,'x':13,'y':4}:
        return (_review('player_pc_location_changed'),step_id) if active else None
    from .campaign_transactions import ui_overworld_ready,verified_blank_transaction_world
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    signal=player_pc_deposit.read_player_pc(pyboy,observation_frame=state.get('frame'),
        expected_location=loc,constants=constants)
    controller=_CONTROLLERS.get(step_id)
    if controller is None:
        if not verified_blank_transaction_world(text,grid):
            return _review('player_pc_initial_closed_world_required'),step_id
        if signal.get('read_valid') is not True or signal.get('facing_raw')!=4:
            return _review('player_pc_initial_read_or_facing_unverified'),step_id
        controller=player_pc_deposit.PlayerPCDepositController(intent)
        _CONTROLLERS[step_id]=controller;_BINDINGS[step_id]=binding
    controller.__class__=player_pc_deposit.PlayerPCDepositController
    # 具名修補只補已成功TM34存物後的重畫及來源scroll箭頭閃爍，不能重存。
    revision=step.get('reviewed_pc_ui_revision')
    if revision is not None and getattr(controller,'_reviewed_pc_ui_revision',None)!=revision:
        base=getattr(controller,'baseline',{}) or {}
        contract={1:(1427457,'after_receipt','bag_viewport_or_quantity_unverified'),
                  2:(1427537,'after_receipt','bag_viewport_or_quantity_unverified'),
                  3:(1427617,'exit_player','player_menu_or_deposit_label_unverified')}.get(revision) if type(revision) is int else None
        reviewed_frame=contract[0] if contract else None
        if (contract is None or intent['item']!=234
                or revision>1 and getattr(controller,'_reviewed_pc_ui_revision',None)!=revision-1
                or controller.error!='player_pc_deposit_'+contract[2]
                or controller.stage!=contract[1] or controller.transferred is not True
                or controller.receipt_seen is not True or state.get('frame')!=reviewed_frame
                or controller.last_frame!=reviewed_frame or controller.pending is not None
                or state.get('progress',{}).get('inventory')!=base.get('bag_after')
                or signal.get('items')!=base.get('pc_after')
                or state.get('progress',{}).get('party')!=base.get('party')
                or state.get('progress',{}).get('money')!=base.get('money')):
            return _review('player_pc_named_redraw_review_unverified'),step_id
        now=time.monotonic()
        # 保留原60秒已花額度與calls/waits；只扣這次實際工程停檢時間。
        paused=max(0.,now-controller.last_now)
        controller.started+=paused
        controller.error=None;controller._reviewed_pc_ui_revision=revision
        controller.review_pause_adjustments=getattr(controller,'review_pause_adjustments',[])+[
            {'source_frame':reviewed_frame,'reason':{1:'native_post_receipt_list_redraw',2:'native_scroll_arrow_blink',3:'native_player_menu_redraw'}[revision],'seconds':paused}]
    result=controller.context(text,state.get('progress'),location=loc,
        battle_state=state.get('battle_state'),pc_signal=signal,frame=state.get('frame'),
        previous=previous,now=time.monotonic(),overworld_ready=ui_overworld_ready(text,grid))
    if result.get('pc_deposit_complete') is True:
        _COMPLETED.add(step_id)
        result={**result,'field_move_complete':True,'field_move_kind':'player-pc-deposit'}
        index=plan['steps'].index(step)+1
        return result,(plan['steps'][index]['id'] if index<len(plan['steps']) else 'complete')
    return result,step_id
