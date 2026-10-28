"""可核對的正常遊戲行程；路線資料可熱更新，不寫遊戲記憶體。"""
import importlib
import json
import time
from . import team_strategy
importlib.reload(team_strategy)
from . import party_control,balanced_training
if 'waypoint' in globals():
    importlib.reload(party_control)
    importlib.reload(balanced_training)
from . import world_map
importlib.reload(world_map)
read_world_grid,world_direction=world_map.read_world_grid,world_map.world_direction
_LEARNED_EDGES=globals().get('_LEARNED_EDGES',{})
_LAST_ATTEMPT=globals().get('_LAST_ATTEMPT')
_FIELD_CONTROLLERS=globals().get('_FIELD_CONTROLLERS',{})
_GYM_CONTROLLERS=globals().get('_GYM_CONTROLLERS',{})
_SCRIPT_WAITS=globals().get('_SCRIPT_WAITS',{})
_VIA_PROGRESS=globals().get('_VIA_PROGRESS',{})
_REVIEWED_NPC_EDGE_RETRIES=globals().get('_REVIEWED_NPC_EDGE_RETRIES',set())
from . import field_moves as field_moves_module
importlib.reload(field_moves_module)
from . import gym_switches as gym_switches_module
importlib.reload(gym_switches_module)
from . import campaign_transactions
importlib.reload(campaign_transactions)
from . import capture_transaction
importlib.reload(capture_transaction)
from . import campaign_safety,capture_closing_gate
from . import safari_entry
importlib.reload(safari_entry)
from . import hm_teaching_bridge
importlib.reload(hm_teaching_bridge)
from . import vending_bridge
importlib.reload(vending_bridge)
from . import saffron_guard_bridge
importlib.reload(saffron_guard_bridge)
from . import silph_card_bridge
importlib.reload(silph_card_bridge)
from . import silph_rival_wait
importlib.reload(silph_rival_wait)
from . import silph_giovanni_wait
importlib.reload(silph_giovanni_wait)
from . import league_native_wait
importlib.reload(league_native_wait)
from . import e4_coordinate
importlib.reload(e4_coordinate)
from . import sabrina_native_warp
importlib.reload(sabrina_native_warp)
from . import lapras_bridge
importlib.reload(lapras_bridge)
from . import player_pc_bridge
importlib.reload(player_pc_bridge)
from . import cinnabar_purchase_bridge
importlib.reload(cinnabar_purchase_bridge)
from . import opponent_review_gate
importlib.reload(opponent_review_gate)
from . import battle_medicine_bridge,blaine_supply_policy,blaine_supply_dispatch
importlib.reload(battle_medicine_bridge)
importlib.reload(blaine_supply_policy)
importlib.reload(blaine_supply_dispatch)
from . import trainer_medicine_ui_bridge,trainer_medicine_policy,trainer_medicine_dispatch
importlib.reload(trainer_medicine_ui_bridge)
importlib.reload(trainer_medicine_policy)
importlib.reload(trainer_medicine_dispatch)
from . import fly_pallet_bridge
importlib.reload(fly_pallet_bridge)
from . import fly_viridian_bridge
importlib.reload(fly_viridian_bridge)
from . import pallet_surf_bridge
importlib.reload(pallet_surf_bridge)
from . import route21_water_bridge
importlib.reload(route21_water_bridge)
from . import mansion_native_landing
importlib.reload(mansion_native_landing)
from . import mansion_transition_ready
importlib.reload(mansion_transition_ready)
from . import mansion_statue_bridge
importlib.reload(mansion_statue_bridge)
from . import mansion_secret_key_bridge
importlib.reload(mansion_secret_key_bridge)
from . import (victory_strength_bridge,victory_first_boulder_bridge,
               victory_later_boulders_bridge,route23_bridge,route23_land_guards_bridge,
               league_training_batch_bridge)
_LEAGUE_FIELDS=(victory_strength_bridge,victory_first_boulder_bridge,
               victory_later_boulders_bridge,route23_bridge,route23_land_guards_bridge,
               league_training_batch_bridge)
for _bridge in _LEAGUE_FIELDS:importlib.reload(_bridge)
del _bridge
from . import league_training_supervisor,league_training_proof
importlib.reload(league_training_supervisor)
importlib.reload(league_training_proof)
_TRAINING_BATCH_PROOFS=globals().get('_TRAINING_BATCH_PROOFS',{})
importlib.reload(campaign_safety)
importlib.reload(capture_closing_gate)
for controller in _GYM_CONTROLLERS.values():controller._last_now=None


def _native_wait_clock(step_id,frame):
    """延續既有clock，只加入真正前進的模擬幀；工程停檢不退款或耗預算。"""
    c=league_native_wait._WAITS.get(step_id)
    if c is None:return None
    last_frame,last_now=getattr(c,'last_frame',None),getattr(c,'last_now',None)
    if (type(frame) is int and type(last_frame) is int and 0<=last_frame<=frame
            and league_native_wait._clock(last_now)):
        return last_now+(frame-last_frame)/60
    return float('nan')  # 交純controller拒絕；不得以新wall clock修復非法舊欄位。


def _league_field_context(pyboy,state,plan,step_id,step,previous):
    """新聯盟field共用入口；先保原owner及互斥，再讀UI，不代替各交易驗收。"""
    def review(reason):
        return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                 'review_reason':'league_field_'+reason},step_id)
    active=[]
    for bridge in _LEAGUE_FIELDS:
        owners=bridge._active()
        if owners is None:return review('registry_unverified')
        if owners:active.append((bridge,owners))
    if len(active)>1:return review('multiple_owners_active')
    if active and active[0][1]!={step_id}:return review('owner_changed')
    matches=[b for b in _LEAGUE_FIELDS if b.applies(step_id,step)]
    if not matches:return None
    if len(matches)!=1:return review('multiple_intents_or_owners')
    bridge=matches[0]
    legacy=(battle_medicine_bridge,trainer_medicine_ui_bridge,mansion_secret_key_bridge,
        mansion_statue_bridge,mansion_transition_ready,mansion_native_landing,
        route21_water_bridge,pallet_surf_bridge,fly_pallet_bridge,fly_viridian_bridge,
        safari_entry,hm_teaching_bridge,vending_bridge,saffron_guard_bridge,
        silph_card_bridge,lapras_bridge,player_pc_bridge,cinnabar_purchase_bridge,campaign_transactions)
    for peer in legacy:
        bindings=getattr(peer,'_BINDINGS',None);done=getattr(peer,'_COMPLETED',None)
        controllers=getattr(peer,'_CONTROLLERS',{})
        if type(bindings) is not dict or type(done) is not set or type(controllers) is not dict:
            return review('peer_registry_unverified')
        if (set(bindings)|set(controllers))-done:return review('other_transaction_active')
    if type(capture_transaction._SESSIONS) is not dict:return review('capture_registry_unverified')
    if (safari_entry._RUN_CONTROLLER is not None
            or any(type(s) is not dict or s.get('done') is not True for s in capture_transaction._SESSIONS.values())
            or any(c.waiting for c in league_native_wait._WAITS.values())):
        return review('other_transaction_active')
    from .observation import read_visible_text
    result=bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
        read_world_grid(pyboy,state['location']),previous)
    return _retain_training_batch_proof(state,plan,result)


def _retain_training_batch_proof(state,plan,result):
    """只在真bridge完成當輪投影；不在EOF回推，也保存attrition收尾的完成。"""
    if (result is None or plan.get('training_job')!=league_training_supervisor.JOB
            or plan.get('training_supervisor')!=league_training_proof.MARKER):return result
    context,next_id=result
    if context.get('field_move_kind')!='league-training-batch' or context.get('field_move_complete') is not True:return result
    try:
        projection=league_training_supervisor.project_completed_batch(plan,context,state)
        key=context['training_batch_owner_step']
        if key in _TRAINING_BATCH_PROOFS and _TRAINING_BATCH_PROOFS[key]!=projection:
            raise ValueError('original_batch_projection_changed')
        _TRAINING_BATCH_PROOFS[key]=projection
    except Exception:
        return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                 'review_reason':'league_training_true_batch_projection_unverified'},next_id)
    return result


def _training_proof_owner_guard(pyboy,plan):
    """已開EOF owner不可藉改marker、plan或tail開始另一段送鍵。"""
    active=league_training_proof._active()
    if active is None:return league_training_proof._review('registries_unknown'),'complete'
    if not active:return None
    key=next(iter(active));c=league_training_proof._SESSIONS.get(key)
    try:
        valid=(len(active)==1 and c is not None and league_training_proof._OWNERS.get(key) is pyboy
            and plan.get('training_supervisor')==league_training_proof.MARKER
            and plan.get('training_job')==league_training_proof.JOB
            and c.binding==league_training_proof.canonical(plan))
    except Exception:valid=False
    if not valid:return league_training_proof._fail(key,'active_owner_plan_or_session_changed'),'complete'
    if not _training_peers_clear():return league_training_proof._fail(key,'active_field_or_legacy_owner'),'complete'
    if c.error is not None:return league_training_proof._review(c.error),'complete'
    return None


def _training_peers_clear():
    peers=(battle_medicine_bridge,trainer_medicine_ui_bridge,mansion_secret_key_bridge,
        mansion_statue_bridge,mansion_transition_ready,mansion_native_landing,route21_water_bridge,
        pallet_surf_bridge,fly_pallet_bridge,fly_viridian_bridge,safari_entry,hm_teaching_bridge,
        vending_bridge,saffron_guard_bridge,silph_card_bridge,lapras_bridge,player_pc_bridge,
        cinnabar_purchase_bridge,campaign_transactions)
    try:
        if any(b._active() is None or bool(b._active()) for b in _LEAGUE_FIELDS):return False
        for b in peers:
            bindings=getattr(b,'_BINDINGS',None);done=getattr(b,'_COMPLETED',None);controllers=getattr(b,'_CONTROLLERS',{})
            if type(bindings) is not dict or type(done) is not set or type(controllers) is not dict:return False
            if (set(bindings)|set(controllers))-done:return False
        if (safari_entry._RUN_CONTROLLER is not None or type(capture_transaction._SESSIONS) is not dict
                or any(type(s) is not dict or s.get('done') is not True for s in capture_transaction._SESSIONS.values())
                or any(c.waiting for c in league_native_wait._WAITS.values())
                or any(c.stage!='complete' for c in _FIELD_CONTROLLERS.values())
                or any(c.state!='complete' for c in _GYM_CONTROLLERS.values())):return False
    except Exception:return False
    return True


def _training_eof_context(pyboy,state,plan):
    if not league_training_proof.applies(plan):return None
    from .observation import read_visible_text
    from .rocket_movement import read_rocket_movement
    step=plan.get('steps',[])[-1] if plan.get('steps') else {}
    key=(league_training_proof.JOB,step.get('id'))
    if not _training_peers_clear():return league_training_proof._fail(key,'active_field_or_legacy_owner')
    try:
        return league_training_proof.context(state,plan,text=read_visible_text(pyboy),
            grid=read_world_grid(pyboy,state['location']),
            movement=read_rocket_movement(pyboy,observation_frame=state.get('frame')),
            native_owner=pyboy,peers_clear=True,
            full_party_healed=healthy(state['progress'],require_full_pp=True),validation=league_training_supervisor,
            stored_batch_proof=_TRAINING_BATCH_PROOFS.get(step.get('id')))
    except Exception:
        return league_training_proof._fail(key,'readonly_world_getter_failed')


def _e4_coordinate_context(pyboy,state,step,text,previous):
    """接同frame已release的原生owner；保原生終點見證後才普通走近NPC。"""
    c=league_native_wait._WAITS.get(step.get('id'));point=state.get('location',{})
    at_target=[point.get('x'),point.get('y')]==step.get('target')
    grid=read_world_grid(pyboy,point) if at_target else None
    return e4_coordinate.at_target(pyboy,state,step,text,grid,previous,
        native_controller=c,now=getattr(c,'last_now',None))


def switch_context(pyboy,state,plan,step_id,previous):
    proof_guard=_training_proof_owner_guard(pyboy,plan)
    if proof_guard is not None:return proof_guard
    step=next((s for s in plan['steps'] if s['id']==step_id),None)
    league_field=_league_field_context(pyboy,state,plan,step_id,step,previous)
    if league_field is not None:return league_field
    active_medicine=trainer_medicine_ui_bridge._active()
    if active_medicine:
        bindings=trainer_medicine_ui_bridge._BINDINGS
        if (len(active_medicine)!=1 or any(type(bindings.get(owner)) is not dict
                or bindings[owner].get('step_id')!=step_id for owner in active_medicine)):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'trainer_medicine_owner_changed'},step_id)
        from .observation import read_visible_text
        return trainer_medicine_dispatch.context(pyboy,state,plan,step_id,read_visible_text(pyboy),previous)
    native_active=any(c.waiting for c in league_native_wait._WAITS.values())
    native_signature=league_native_wait._signature(step)
    native_location=state.get('location',{}) if isinstance(state,dict) else {}
    native_ready=(native_signature is not None and native_location.get('map_id')==step['map_id']
        and (step['map_id']!=33 or [native_location.get('x'),native_location.get('y')]==[29,4]
             or step_id in league_native_wait._WAITS))
    if native_active or native_ready:
        from .observation import read_visible_text
        native_text=read_visible_text(pyboy)
        native=league_native_wait.context(pyboy,state,step,native_text,previous,
            now=_native_wait_clock(step_id,state.get('frame')),
            review_capsule=plan.get('native_dialogue_review'),
            checkpoint_resume_capsule=plan.get('checkpoint_resume_capsule'),
            final_a_review_capsule=plan.get('native_final_a_review'))
        if native is not None:
            if native.get('phase')=='overworld' and native.get('available_actions')==['wait']:
                native={**native,'phase':'league_native_wait'}
            return native,step_id
        if step['map_id'] in e4_coordinate.CONFIG and not satisfied(step,state['progress']):
            coordinate=_e4_coordinate_context(pyboy,state,step,native_text,previous)
            if coordinate is not None:return coordinate,step_id
    if fly_viridian_bridge.applies(step_id,step):
        active_fly=set(fly_viridian_bridge._BINDINGS)-fly_viridian_bridge._COMPLETED
        if active_fly and active_fly!={step_id}:
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'fly_viridian_owner_changed'},step_id)
        bridges=(battle_medicine_bridge,mansion_secret_key_bridge,mansion_statue_bridge,
                 mansion_transition_ready,mansion_native_landing,route21_water_bridge,
                 pallet_surf_bridge,fly_pallet_bridge,safari_entry,hm_teaching_bridge,
                 vending_bridge,saffron_guard_bridge,silph_card_bridge,lapras_bridge,
                 player_pc_bridge,cinnabar_purchase_bridge,campaign_transactions)
        if (any(set(m._BINDINGS)-m._COMPLETED for m in bridges)
                or safari_entry._RUN_CONTROLLER is not None
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'fly_viridian_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return fly_viridian_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                          read_world_grid(pyboy,state['location']),previous)
    if battle_medicine_bridge.applies(step_id,step):
        if battle_medicine_bridge._signature(step_id,step) is None:
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'blaine_supply_fixed_step_unverified'},step_id)
        bridges=(mansion_secret_key_bridge,mansion_statue_bridge,mansion_transition_ready,
                 mansion_native_landing,route21_water_bridge,pallet_surf_bridge,
                 fly_pallet_bridge,safari_entry,hm_teaching_bridge,vending_bridge,
                 saffron_guard_bridge,silph_card_bridge,lapras_bridge,player_pc_bridge,
                 cinnabar_purchase_bridge,campaign_transactions)
        if (any(set(m._BINDINGS)-m._COMPLETED for m in bridges)
                or safari_entry._RUN_CONTROLLER is not None
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'blaine_supply_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return blaine_supply_dispatch.context(pyboy,state,plan,step_id,read_visible_text(pyboy),previous)
    if step and 'opponent_review' in step:
        from .observation import read_visible_text
        opponent_gate=opponent_review_gate.context(state,step,read_visible_text(pyboy),previous=previous,
            signal=opponent_review_gate.read_intro_signal(pyboy),owner=pyboy)
        if opponent_gate is not None:return opponent_gate,step_id
    if trainer_medicine_ui_bridge.applies(step_id,step):
        from .observation import read_visible_text
        medicine=trainer_medicine_dispatch.context(pyboy,state,plan,step_id,read_visible_text(pyboy),previous)
        if medicine is not None:return medicine
    if cinnabar_purchase_bridge.applies(step_id,step):
        bridges=(mansion_secret_key_bridge,mansion_statue_bridge,mansion_transition_ready,
                 mansion_native_landing,route21_water_bridge,pallet_surf_bridge,
                 fly_pallet_bridge,safari_entry,hm_teaching_bridge,vending_bridge,
                 saffron_guard_bridge,silph_card_bridge,lapras_bridge,player_pc_bridge,
                 campaign_transactions)
        if (any(set(m._BINDINGS)-m._COMPLETED for m in bridges)
                or safari_entry._RUN_CONTROLLER is not None
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'cinnabar_purchase_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return cinnabar_purchase_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                                read_world_grid(pyboy,state['location']),previous)
    if mansion_secret_key_bridge.applies(step_id,step):
        bridges=(mansion_statue_bridge,mansion_transition_ready,mansion_native_landing,
                 route21_water_bridge,pallet_surf_bridge,fly_pallet_bridge,safari_entry,
                 hm_teaching_bridge,vending_bridge,saffron_guard_bridge,silph_card_bridge,
                 lapras_bridge,player_pc_bridge,campaign_transactions)
        if (any(set(m._BINDINGS)-m._COMPLETED for m in bridges)
                or safari_entry._RUN_CONTROLLER is not None
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'mansion_secret_key_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return mansion_secret_key_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                                read_world_grid(pyboy,state['location']),previous)
    if mansion_statue_bridge.applies(step_id,step):
        bridges=(mansion_secret_key_bridge,mansion_transition_ready,mansion_native_landing,route21_water_bridge,pallet_surf_bridge,
                 fly_pallet_bridge,safari_entry,hm_teaching_bridge,vending_bridge,
                 saffron_guard_bridge,silph_card_bridge,lapras_bridge,player_pc_bridge,
                 campaign_transactions)
        if (any(set(m._BINDINGS)-m._COMPLETED for m in bridges)
                or safari_entry._RUN_CONTROLLER is not None
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'mansion_statue_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return mansion_statue_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                               read_world_grid(pyboy,state['location']),previous)
    if route21_water_bridge.applies(step_id,step):
        bridges=(pallet_surf_bridge,fly_pallet_bridge,safari_entry,hm_teaching_bridge,
                 vending_bridge,saffron_guard_bridge,silph_card_bridge,lapras_bridge,
                 player_pc_bridge,campaign_transactions)
        if (any(set(m._BINDINGS)-m._COMPLETED for m in bridges)
                or safari_entry._RUN_CONTROLLER is not None
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'route21_water_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return route21_water_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                            read_world_grid(pyboy,state['location']),previous)
    if pallet_surf_bridge.applies(step_id,step):
        if (set(fly_pallet_bridge._BINDINGS)-fly_pallet_bridge._COMPLETED
                or set(safari_entry._BINDINGS)-safari_entry._COMPLETED
                or safari_entry._RUN_CONTROLLER is not None
                or set(hm_teaching_bridge._BINDINGS)-hm_teaching_bridge._COMPLETED
                or set(vending_bridge._BINDINGS)-vending_bridge._COMPLETED
                or set(saffron_guard_bridge._BINDINGS)-saffron_guard_bridge._COMPLETED
                or set(silph_card_bridge._BINDINGS)-silph_card_bridge._COMPLETED
                or set(lapras_bridge._BINDINGS)-lapras_bridge._COMPLETED
                or set(player_pc_bridge._BINDINGS)-player_pc_bridge._COMPLETED
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())
                or set(campaign_transactions._BINDINGS)-campaign_transactions._COMPLETED):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'pallet_surf_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return pallet_surf_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                          read_world_grid(pyboy,state['location']),previous)
    if fly_pallet_bridge.applies(step_id,step):
        if (set(safari_entry._BINDINGS)-safari_entry._COMPLETED
                or safari_entry._RUN_CONTROLLER is not None
                or set(hm_teaching_bridge._BINDINGS)-hm_teaching_bridge._COMPLETED
                or set(vending_bridge._BINDINGS)-vending_bridge._COMPLETED
                or set(saffron_guard_bridge._BINDINGS)-saffron_guard_bridge._COMPLETED
                or set(silph_card_bridge._BINDINGS)-silph_card_bridge._COMPLETED
                or set(lapras_bridge._BINDINGS)-lapras_bridge._COMPLETED
                or set(player_pc_bridge._BINDINGS)-player_pc_bridge._COMPLETED
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())
                or set(campaign_transactions._BINDINGS)-campaign_transactions._COMPLETED):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'fly_pallet_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return fly_pallet_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                         read_world_grid(pyboy,state['location']),previous)
    if player_pc_bridge.applies(step_id,step):
        if (set(safari_entry._BINDINGS)-safari_entry._COMPLETED
                or safari_entry._RUN_CONTROLLER is not None
                or set(hm_teaching_bridge._BINDINGS)-hm_teaching_bridge._COMPLETED
                or set(vending_bridge._BINDINGS)-vending_bridge._COMPLETED
                or set(saffron_guard_bridge._BINDINGS)-saffron_guard_bridge._COMPLETED
                or set(silph_card_bridge._BINDINGS)-silph_card_bridge._COMPLETED
                or set(lapras_bridge._BINDINGS)-lapras_bridge._COMPLETED
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())
                or set(campaign_transactions._BINDINGS)-campaign_transactions._COMPLETED):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'player_pc_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return player_pc_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                        read_world_grid(pyboy,state['location']),previous)
    if not step or step['kind']!='gym_switches':return None
    GymSwitchController=gym_switches_module.GymSwitchController
    from .observation import read_visible_text
    loc=state['location'];grid=read_world_grid(pyboy,loc)
    blocked=[tuple(p) for p in plan.get('blocked',{}).get(str(loc['map_id']),[])]
    npcs=world_map.read_npc_obstacles(pyboy,grid,blocked) if grid else None
    if npcs:blocked=list(set(blocked)|set(npcs['positions']))
    controller=_GYM_CONTROLLERS.setdefault(step_id,GymSwitchController())
    controller.__class__=GymSwitchController
    revision=step.get('reviewed_controller_revision',0)
    if revision>getattr(controller,'_reviewed_revision',0) and controller._review_reason==step.get('reviewed_controller_error'):
        controller._review_reason=None;controller._reviewed_revision=revision
    context=controller.context(read_visible_text(pyboy),loc,state['progress'],grid,battle_state=state.get('battle_state'),previous=previous,blocked=blocked)
    if context is None:return None
    next_id=step_id
    if context.get('gym_switches_complete'):
        index=plan['steps'].index(step)+1
        next_id=plan['steps'][index]['id'] if index<len(plan['steps']) else 'complete'
    return context,next_id


def attrition_transition_context(pyboy,state,plan,step_id,attrition,previous=()):
    """只將已綁Lapras的來源命名未初始化過渡交專屬reader；其他損耗照常停。"""
    proof_guard=_training_proof_owner_guard(pyboy,plan)
    if proof_guard is not None:return proof_guard
    active_eof=league_training_proof._active()
    if active_eof:return league_training_proof._fail(next(iter(active_eof)),'attrition_during_eof'),'complete'
    if league_training_batch_bridge._active()=={step_id}:
        from .observation import read_visible_text
        closure=league_training_batch_bridge.pre_attrition_closure_context(pyboy,state,plan,step_id,attrition,
            read_visible_text(pyboy),read_world_grid(pyboy,state['location']),previous)
        if closure is not None:return _retain_training_batch_proof(state,plan,closure)
    if (not isinstance(attrition,dict)
            or attrition.get('review_reason')!='party_attrition_state_unverified'
            or attrition.get('party_attrition',{}).get('issue')!='party_read_not_verified'):
        return None
    from .observation import read_visible_text
    return lapras_bridge.pre_attrition_context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                              read_world_grid(pyboy,state['location']))


def field_context(pyboy,state,plan,step_id):
    """僅精確field步驟可接管HM UI；其他未知學招仍由主程序暫停。"""
    proof_guard=_training_proof_owner_guard(pyboy,plan)
    if proof_guard is not None:return proof_guard
    step=next((s for s in plan['steps'] if s['id']==step_id),None)
    if any(b.applies(step_id,step) for b in _LEAGUE_FIELDS):return None
    if (any(c.waiting for c in league_native_wait._WAITS.values())
            or league_native_wait._signature(step) is not None):
        return None  # 原生走位與intro只交有真previous的switch，不由field提早接管。
    if trainer_medicine_ui_bridge.applies(step_id,step):
        return None  # 真previous、補藥UI與後續既有battle只由switch_context接管。
    if fly_viridian_bridge.applies(step_id,step):
        return None  # 同一飛行交易與真previous只交switch_context。
    if battle_medicine_bridge.applies(step_id,step):
        return None  # 真previous與所有補藥／敵回合頁面由switch_context接管。
    if step and 'opponent_review' in step:
        return None  # 對戰intro必須接switch_context的真實previous。
    if cinnabar_purchase_bridge.applies(step_id,step):
        return None  # 固定購藥交易只由switch_context接主runner真previous。
    if mansion_secret_key_bridge.applies(step_id,step):
        return None  # 祕密鑰匙只由switch_context接主runner真previous。
    if mansion_transition_ready.applies(step_id,step):
        bridges=(mansion_secret_key_bridge,mansion_native_landing,mansion_statue_bridge,route21_water_bridge,
                 pallet_surf_bridge,fly_pallet_bridge,safari_entry,hm_teaching_bridge,
                 vending_bridge,saffron_guard_bridge,silph_card_bridge,lapras_bridge,
                 player_pc_bridge,campaign_transactions)
        if (any(set(m._BINDINGS)-m._COMPLETED for m in bridges)
                or safari_entry._RUN_CONTROLLER is not None
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'mansion_transition_other_transaction_active'},step_id)
        from .observation import read_visible_text
        text=read_visible_text(pyboy);grid=read_world_grid(pyboy,state['location'])
        reviewed=_review_mansion_standing_warp(pyboy,state,plan,step,text,grid)
        if reviewed is not None:
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':reviewed},step_id)
        return mansion_transition_ready.context(pyboy,state,plan,step_id,text,grid)
    if mansion_native_landing.applies(step_id,step):
        bridges=(mansion_secret_key_bridge,mansion_transition_ready,mansion_statue_bridge,route21_water_bridge,pallet_surf_bridge,fly_pallet_bridge,safari_entry,
                 hm_teaching_bridge,vending_bridge,saffron_guard_bridge,silph_card_bridge,
                 lapras_bridge,player_pc_bridge,campaign_transactions)
        if (any(set(m._BINDINGS)-m._COMPLETED for m in bridges)
                or safari_entry._RUN_CONTROLLER is not None
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'mansion_landing_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return mansion_native_landing.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                               read_world_grid(pyboy,state['location']))
    if mansion_statue_bridge.applies(step_id,step):
        return None  # 原生雕像提示必由switch_context接真previous。
    if route21_water_bridge.applies(step_id,step):
        return None  # 第一個野戰觀測也先接真previous，水步收據後才交battle。
    if pallet_surf_bridge.applies(step_id,step):
        return None  # 下水全程由switch_context接真previous。
    if fly_pallet_bridge.applies(step_id,step):
        return None  # 由switch_context接真previous，攔截完整飛行直到落地閉合。
    if player_pc_bridge.applies(step_id,step):
        return None  # switch_context收到主runner真previous後才可推進PC交易。
    if lapras_bridge.applies(step_id,step):
        from .observation import read_visible_text
        return lapras_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                     read_world_grid(pyboy,state['location']))
    if silph_card_bridge.applies(step_id,step):
        if (set(safari_entry._BINDINGS)-safari_entry._COMPLETED
                or safari_entry._RUN_CONTROLLER is not None
                or set(saffron_guard_bridge._BINDINGS)-saffron_guard_bridge._COMPLETED
                or set(vending_bridge._BINDINGS)-vending_bridge._COMPLETED
                or set(hm_teaching_bridge._BINDINGS)-hm_teaching_bridge._COMPLETED
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())
                or set(campaign_transactions._BINDINGS)-campaign_transactions._COMPLETED):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'silph_card_bridge_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return silph_card_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                        read_world_grid(pyboy,state['location']))
    if saffron_guard_bridge.applies(step_id,step):
        if (set(safari_entry._BINDINGS)-safari_entry._COMPLETED
                or safari_entry._RUN_CONTROLLER is not None
                or set(vending_bridge._BINDINGS)-vending_bridge._COMPLETED
                or set(hm_teaching_bridge._BINDINGS)-hm_teaching_bridge._COMPLETED
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())
                or set(campaign_transactions._BINDINGS)-campaign_transactions._COMPLETED):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'saffron_guard_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return saffron_guard_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                            read_world_grid(pyboy,state['location']))
    if vending_bridge.applies(step_id,step):
        if (set(safari_entry._BINDINGS)-safari_entry._COMPLETED
                or safari_entry._RUN_CONTROLLER is not None
                or set(hm_teaching_bridge._BINDINGS)-hm_teaching_bridge._COMPLETED
                or any(not s.get('done') for s in capture_transaction._SESSIONS.values())
                or set(campaign_transactions._BINDINGS)-campaign_transactions._COMPLETED):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'vending_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return vending_bridge.context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                      read_world_grid(pyboy,state['location']))
    if hm_teaching_bridge.applies(step_id,step):
        if (set(safari_entry._BINDINGS)-safari_entry._COMPLETED
                or safari_entry._RUN_CONTROLLER is not None
                or set(campaign_transactions._BINDINGS)-campaign_transactions._COMPLETED):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'hm_teaching_other_transaction_active'},step_id)
        from .observation import read_visible_text
        return hm_teaching_bridge.context(state,plan,step_id,read_visible_text(pyboy),
                                          read_world_grid(pyboy,state['location']))
    if safari_entry.applies(step_id,step,state):
        from .observation import read_visible_text
        return safari_entry.field_context(pyboy,state,plan,step_id,read_visible_text(pyboy),
                                         read_world_grid(pyboy,state['location']))
    if capture_transaction.applies(step_id,step):
        from .observation import read_visible_text
        closing=capture_closing_gate.eligible(state,plan,step_id)
        result=capture_transaction.context(pyboy,state,plan,step_id,read_visible_text(pyboy),read_world_grid(pyboy,state['location']))
        return capture_closing_gate.restrict(result) if closing else result
    if step and step.get('mechanic')=='sabrina_native_warp':
        if (set(campaign_transactions._BINDINGS)-campaign_transactions._COMPLETED
                or set(hm_teaching_bridge._BINDINGS)-hm_teaching_bridge._COMPLETED
                or set(silph_card_bridge._BINDINGS)-silph_card_bridge._COMPLETED
                or set(lapras_bridge._BINDINGS)-lapras_bridge._COMPLETED):
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'sabrina_native_warp_other_transaction_active'},step_id)
        return None  # 原生傳送由waypoint拿真previous動作序列；不交泛用interact交易。
    if campaign_transactions.applies(step_id,step):
        from .observation import read_visible_text
        return campaign_transactions.context(pyboy,state,plan,step_id,read_visible_text(pyboy),read_world_grid(pyboy,state['location']))
    if (step and step.get('kind')=='move' and plan.get('training_shared_experience') is True
            and plan.get('mode')=='league_campaign'):
        training=balanced_training.shared_experience_battle_context(pyboy,state,plan)
        if training is not None:return training,step_id
    if not step:return None
    if step['kind'] not in {'teach_cut','use_cut'}:return None
    if state.get('battle_state',{}).get('kind')!='none':return None
    loc=dict(state['location'])
    if loc['map_id']!=step['map_id'] or [loc['x'],loc['y']]!=step['target']:return None
    from .observation import read_visible_text
    CutController=field_moves_module.CutController
    loc['facing']={0:'down',4:'up',8:'left',12:'right'}.get(int(pyboy.memory[0xC109]))
    grid=read_world_grid(pyboy,loc)
    controller=_FIELD_CONTROLLERS.get(step_id)
    if controller is not None:
        controller.__class__=CutController
        revision=step.get('reviewed_controller_revision',0)
        if revision>getattr(controller,'_reviewed_revision',0) and controller.error==step.get('reviewed_controller_error'):
            controller.error=None;controller._reviewed_revision=revision
    if controller is None:
        if grid is None:return None
        if step['kind']=='use_cut' and loc['facing']!=step.get('face'):
            direction=step['face']
            return ({'phase':'field_move_menu','objective':f'Move {direction.upper()}.','available_actions':[direction,'wait'],'controller_menu_verified':True},step_id)
        candidates=[m['species'] for m in state['progress'].get('party',[])
                    if type(m.get('species')) is int and m['species'] in {9,154}
                    and (step['kind']=='teach_cut' or 15 in m.get('moves',[]))]
        if state['progress'].get('party_read_valid') is not True or len(candidates)!=1:
            return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                     'review_reason':'unique_current_cut_user_unverified'},step_id)
        intent={'kind':step['kind'],'species':candidates[0],'replace_move':45}
        if step['kind']=='use_cut':intent.update(map_id=step['map_id'],tree_x=step['tree'][0],tree_y=step['tree'][1],tileset_id=step.get('tileset_id',0))
        controller=CutController(intent);_FIELD_CONTROLLERS[step_id]=controller
    reviewed_cut=_review_cut_six_party(controller,step,state)
    if reviewed_cut is not None:
        return ({'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                 'review_reason':reviewed_cut},step_id)
    context=controller.context(read_visible_text(pyboy),state['progress'],location=loc,grid=grid,overworld_ready=grid is not None,battle_active=False)
    next_id=step_id
    if context.get('field_move_complete'):
        index=plan['steps'].index(step)+1
        next_id=plan['steps'][index]['id'] if index<len(plan['steps']) else 'complete'
    return context,next_id


def _review_cut_six_party(controller,step,state):
    """僅續接16號路已選妙蛙花的六人背景誤拒；不重建Cut基線或等待額度。"""
    revision=step.get('reviewed_cut_six_party_revision')
    if revision is None or getattr(controller,'_reviewed_cut_six_party_revision',None)==revision:return None
    party=state.get('progress',{}).get('party',[])
    baseline=[(m.get('species'),list(m.get('moves',[]))) for m in party]
    if (type(revision) is not int or revision!=1 or state.get('frame')!=1436457
            or state.get('location')!={'map_id':27,'x':34,'y':10}
            or step.get('id')!='route16-native-cut' or step.get('kind')!='use_cut'
            or step.get('tree')!=[34,9] or step.get('map_id')!=27
            or controller.error!='cut_field_submenu_cursor_unverified'
            or controller.stage!='choose_user' or controller.field_user_confirmed is not True
            or controller.target_index!=3 or len(party)!=6 or party[3].get('species')!=154
            or controller.baseline!=baseline
            or controller.start_location!={'map_id':27,'x':34,'y':10,'facing':'up'}):
        return 'cut_six_party_named_review_unverified'
    controller.error=None;controller._reviewed_cut_six_party_revision=revision
    return None


def _review_mansion_standing_warp(pyboy,state,plan,step,text,grid):
    """只扣除已固定工程停檢的牆鐘；保留原交易與已耗用的全部預算。"""
    revision=step.get('reviewed_standing_warp_revision')
    if revision is None:return None
    module=mansion_transition_ready;r=module._CONTROLLERS.get(step.get('id'))
    if r is not None and r.get('reviewed_standing_warp_revision')==revision:return None
    reason='mansion_standing_warp_named_review_unverified'
    expected_binding=((216,23,22),165,(21,23),json.dumps('mansion-basement-approach-20261024',sort_keys=True,allow_nan=False))
    if (type(revision) is not int or revision!=1 or step.get('id')!='mansion-basement-stairs-ready-20261024'
            or plan.get('training_job')!='mansion-basement-approach-20261024'
            or step.get('map_id')!=216 or step.get('target')!=[23,22]
            or state.get('frame')!=1466785 or state.get('location')!={'map_id':216,'x':23,'y':22}
            or r is None or r.get('error') is not None or r.get('last_frame')!=1466785
            or r.get('waits')!=26 or r.get('calls')!=26 or r.get('closed_frame') is not None
            or module._BINDINGS.get(step['id'])!=expected_binding
            or set(module._BINDINGS)-module._COMPLETED!={step['id']}):return reason
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    signal=module.read_transition_movement(pyboy,observation_frame=state['frame'],constants=constants)
    p=state.get('progress');battle=state.get('battle_state',{})
    if (not isinstance(p,dict) or module._party(p) is None
            or (module._party(p),module._inventory(p.get('inventory')),p.get('money'))!=r['baseline']
            or signal.get('read_valid') is not True or signal.get('switch_on') is not True
            or signal.get('location')!=state['location'] or signal.get('movement_flags')!=4
            or any(signal.get(k)!=0 for k in ('simulated_remaining','joy_ignore','walk_counter'))
            or battle.get('active') is not False or battle.get('kind')!='none' or battle.get('raw')!=0
            or battle.get('observation_frame')!=state['frame']
            or module._text_status(text) is not True
            or module._grid_status(grid,state['frame'],state['location'],0x13) is not True):return reason
    now=time.monotonic();started,last=r.get('started'),r.get('last_now')
    if (any(type(v) not in (int,float) for v in (started,last,now))
            or not 0<=started<=last<=now or last-started>module.MAX_SECONDS):return reason
    excluded=now-last
    r['started']+=excluded;r['last_now']=now
    r['review_excluded_seconds']=r.get('review_excluded_seconds',0)+excluded
    r['review_elapsed_preserved']=last-started
    r['reviewed_standing_warp_revision']=revision
    return None


def satisfied(step,progress):
    if 'event' in step:return progress['story_event_bits'].get(step['event']) is True
    if 'item' in step:return any(i['item']==step['item'] for i in progress.get('inventory') or [])
    if 'badge' in step:return bool((progress.get('badges_raw') or 0)&step['badge'])
    return False


def attack_pp(mon):
    from .team_strategy import effective_power
    return sum(pp&63 for move,pp in zip(mon.get('moves',[]),mon.get('pp',[])) if effective_power(move,mon.get('species'))>0)


def healthy(progress, *, require_full_pp=False):
    party=progress['party']
    if require_full_pp:
        from .team_strategy import reference,move_key
        for mon in party:
            moves,pp=mon.get('moves'),mon.get('pp')
            if (not isinstance(moves,(list,tuple)) or not isinstance(pp,(list,tuple))
                    or len(moves)!=4 or len(pp)!=4):return False
            for move,remaining in zip(moves,pp):
                if type(move) is not int or type(remaining) is not int:return False
                if move==0:
                    if remaining!=0:return False
                    continue
                key=move_key(move)
                base=reference()['moves'].get(key,{}).get('pp')
                if type(base) is not int or remaining!=base:return False
    return bool(party) and all(m['hp']==m['max_hp'] and not m.get('status',0) for m in party) and attack_pp(party[0])>=3


def coordinate_script_wait(state, step):
    """固定來源嘎啦嘎啦／Silph勁敵與坂木座標等待；不輸出方向或A。"""
    if step.get('map_id') == 235 or step.get('event') == 'beat_silph_co_giovanni':
        return silph_giovanni_wait.silph_giovanni_script_wait(state,step)
    if step.get('map_id') == 212 or step.get('event') == 'beat_silph_co_rival':
        return silph_rival_wait.silph_rival_script_wait(state,step)
    def review(reason):
        return {'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                'review_reason':reason,'route_step':step['id']}
    if (step.get('await_script_event') is not True or step.get('kind')!='move'
            or step.get('map_id')!=147 or step.get('target')!=[10,16]
            or step.get('event')!='beat_ghost_marowak'):
        return review('coordinate_script_intent_unverified')
    battle=state.get('battle_state',{});progress=state.get('progress',{})
    if (battle.get('kind')!='none' or battle.get('active') is not False
            or progress.get('party_read_valid') is not True
            or progress.get('story_event_bits',{}).get('beat_ghost_marowak') is not False
            or not any(i.get('item')==72 and type(i.get('quantity')) is int and i['quantity']>0
                       for i in progress.get('inventory') or [])):
        return review('coordinate_script_prerequisites_unverified')
    now=time.monotonic();record=_SCRIPT_WAITS.setdefault(step['id'],{'started':now,'calls':0})
    record['calls']+=1
    if record['calls']>25 or now-record['started']>60:
        return review('coordinate_script_wait_exhausted')
    return {'phase':'overworld','objective':'Wait.','available_actions':['wait'],
            'goal':step['id'],'route_step':step['id'],'source_coordinate_script_wait':True,
            'source_commit':'a53671100ec22e5394ff26ec028d0812a238dae2',
            'phase_source':'PokemonTower6F.asm:25-47；保留10,16，讓原生座標腳本啟動，不把到站當成戰勝。'}


def _via_target(plan,step,position):
    """只消費實際抵達的下一中繼點；暫停、戰鬥與熱載入不重設游標。"""
    via=step.get('via',[])
    if not via:return step.get('target',list(position))
    # 工程解除的resume_revision與blocked修正不是新旅程；幾何或job改變才另建進度。
    fields=('id','kind','map_id','target','via','next_map','terminal',
            'event','item','badge','await_script_event','face','require_full_pp',
            'mechanic','landing','offpad')
    geometry=[{key:s[key] for key in fields if key in s} for s in plan['steps']]
    canonical=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)
    job=plan.get('training_job')
    scope=('training_job',canonical(job)) if job not in (None,'',{},[]) else ('unscoped_route',)
    key=(scope,canonical(geometry),step['id'])
    following=_VIA_PROGRESS.get(key,0)
    while following<len(via) and tuple(via[following])==position:
        following+=1
    _VIA_PROGRESS[key]=following
    return via[following] if following<len(via) else step.get('target',list(position))


def native_warp_context(pyboy,state,step,previous):
    """全部getter在原模擬器同一frame；controller只給候選，不自行按鍵。"""
    from .observation import read_visible_text
    from .rocket_movement import read_rocket_movement
    grid=read_world_grid(pyboy,state['location'])
    return sabrina_native_warp.context(state,step,read_visible_text(pyboy),grid,
        read_rocket_movement(pyboy,observation_frame=state['frame']),previous)


def _reviewed_npc_edge_retry(state,step,grid,npcs,ready):
    """父層核正常出入館後，只撤銷該NPC曾擋住的一條導航快取。"""
    global _LAST_ATTEMPT
    marker=step.get('reviewed_npc_edge_retry')
    if marker is None:return None
    if (type(marker) is not dict or set(marker)!={'kind','frame','from','to'}
            or marker.get('kind')!='trainer_reset_after_normal_exit_v1'
            or type(marker.get('frame')) is not int or marker['frame']<0
            or marker.get('from')!=[10,4] or marker.get('to')!=[10,3]
            or any(type(v) is not int for k in ('from','to') for v in marker[k])):
        return 'npc_edge_retry_marker_unverified'
    key=(step['id'],json.dumps(marker,sort_keys=True))
    if key in _REVIEWED_NPC_EDGE_RETRIES:return None
    if (step.get('kind')!='move' or step.get('map_id')!=45
            or state.get('frame')!=marker['frame'] or type(state.get('frame')) is not int
            or state.get('location')!={'map_id':45,'x':10,'y':4} or ready is not True
            or not isinstance(grid,dict) or grid.get('observation_frame')!=marker['frame']
            or type(grid.get('observation_frame')) is not int
            or grid.get('verified_location')!=[45,10,4] or type(grid.get('screen_cells_verified')) is not int
            or grid['screen_cells_verified']<12 or not isinstance(npcs,dict)
            or type(npcs.get('source_anchor_matches')) is not int or npcs['source_anchor_matches']<9):
        return 'npc_edge_retry_closed_world_unverified'
    raw_positions=npcs.get('positions')
    if (not isinstance(raw_positions,(list,tuple))
            or any(not isinstance(p,(list,tuple)) or len(p)!=2
                   or any(type(v) is not int for v in p) for p in raw_positions)):
        return 'npc_edge_retry_trainer_reset_unverified'
    positions=set(map(tuple,raw_positions))
    try:free=grid['walkable'][4][10]==1 and grid['walkable'][3][10]==1
    except (KeyError,IndexError,TypeError):free=False
    edge=((10,4),(10,3))
    if not free or (10,3) in positions or not {(10,1),(13,5)}<=positions:
        return 'npc_edge_retry_trainer_reset_unverified'
    if edge not in _LEARNED_EDGES.get(45,set()):return 'npc_edge_retry_cached_edge_missing'
    _LEARNED_EDGES[45].discard(edge)
    if (_LAST_ATTEMPT and _LAST_ATTEMPT.get('key')==(45,10,4,step['id'])
            and _LAST_ATTEMPT.get('direction')=='up'):_LAST_ATTEMPT=None
    _REVIEWED_NPC_EDGE_RETRIES.add(key)
    return None


def waypoint(pyboy,state,plan,step_id,previous):
    global _LAST_ATTEMPT
    steps=plan['steps'];ids=[s['id'] for s in steps]
    if len(ids)!=len(set(ids)):raise ValueError('路線ID重複')
    invalid=next((s for s in steps if s.get('mechanic')=='sabrina_native_warp'
                  and any(k in s for k in ('next_map','terminal','event','item','badge','await_script_event'))),None)
    if invalid is not None:
        return {'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                'review_reason':'sabrina_native_warp_generic_completion_forbidden','route_step':invalid['id']},invalid['id']
    index=len(steps) if step_id=='complete' else ids.index(step_id) if step_id in ids else 0
    loc=state['location'];progress=state['progress'];mid=loc['map_id'];x,y=loc['x'],loc['y']
    # 先承認已完成的轉場，再判斷補血繞路，避免「進中心→繞路出門→再進中心」循環。
    while index<len(steps) and (satisfied(steps[index],progress) or steps[index].get('next_map')==mid):index+=1
    current=steps[index] if index<len(steps) else {}
    lead=progress['party'][0] if progress.get('party') else None
    needs_heal=lead is not None and (lead['hp']*3<=lead['max_hp']*2 or lead.get('status',0) or attack_pp(lead)<3)
    detour=None
    if not plan.get('_detour'):
        if mid in {58,68,64} and current.get('map_id')!=mid:
            detour={'id':'detour-center','map_id':mid,'target':[3,3] if not healthy(progress) else [3,8],'kind':'heal' if not healthy(progress) else 'move','face':'up','terminal':True}
        elif mid==14 and needs_heal:detour={'id':'detour-return-pewter','map_id':14,'target':[-1,9],'kind':'move','terminal':True}
        elif mid==2 and current.get('map_id')==14:detour={'id':'detour-city','map_id':2,'target':[13,25] if not healthy(progress) else [40,17],'kind':'move','terminal':True}
        elif mid==35 and needs_heal:detour={'id':'detour-bridge-center','map_id':35,'target':[10,36],'kind':'move','terminal':True}
        elif mid==36 and needs_heal:detour={'id':'detour-route25-center','map_id':36,'target':[-1,8],'kind':'move','terminal':True}
        elif mid==35 and current.get('map_id')==36:detour={'id':'detour-return-route25','map_id':35,'target':[20,8],'kind':'move','terminal':True}
        elif mid==3 and current.get('map_id') in {35,36,88}:
            detour={'id':'detour-cerulean-center','map_id':3,'target':[19,17] if not healthy(progress) else [20,-1],'kind':'move','terminal':True}
    if detour:
        context,_=waypoint(pyboy,state,{'steps':[detour],'blocked':plan.get('blocked',{}),'_detour':True},detour['id'],previous)
        return context,current.get('id',step_id)
    # 只由實際執行的行程記錄失敗邊；外層主線不能清掉補血繞路的嘗試。
    if pyboy is not None and _LAST_ATTEMPT:
        old=_LAST_ATTEMPT
        if (mid,x,y,current.get('id'))==old['key'] and previous and previous[-1]==old['direction']:
            old['misses']+=1
            if old['misses']>=3:
                dx,dy={'up':(0,-1),'down':(0,1),'left':(-1,0),'right':(1,0)}[old['direction']]
                _LEARNED_EDGES.setdefault(mid,set()).add(((x,y),(x+dx,y+dy)))
                _LAST_ATTEMPT=None
        else:_LAST_ATTEMPT=None
    while index<len(steps):
        step=steps[index]
        if satisfied(step,progress) or ('next_map' in step and mid==step['next_map']):index+=1;continue
        if mid!=step['map_id']:
            return {'phase':'campaign_review','review_reason':'unexpected_map','expected_map':step['map_id'],'route_step':step['id']},step['id']
        if step.get('mechanic')=='sabrina_native_warp':
            context=native_warp_context(pyboy,state,step,previous)
            if context is not None:
                if context.get('native_warp_complete') is True:
                    index+=1;continue
                return context,step['id']
        target=_via_target(plan,step,(x,y))
        target={'x':target[0],'y':target[1]}
        if 'await_script_event' in step and [x,y]==list(target.values()):
            if step['map_id'] in e4_coordinate.CONFIG:
                from .observation import read_visible_text
                coordinate=_e4_coordinate_context(pyboy,state,step,read_visible_text(pyboy),previous)
                if coordinate is None:
                    coordinate={'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                                'review_reason':'e4_coordinate_target_context_missing','route_step':step['id']}
                return coordinate,step['id']
            return coordinate_script_wait(state,step),step['id']
        if step['kind']=='heal' and healthy(progress,require_full_pp=step.get('require_full_pp') is True):index+=1;continue
        if step['kind']=='move' and [x,y]==list(target.values()) and 'next_map' not in step:index+=1;continue
        if (step['kind'] in {'teach_cut','use_cut','gym_switches'} or 'mechanic' in step) and [x,y]==list(target.values()):
            return {'phase':'overworld','objective':'Wait.','available_actions':['wait'],'goal':'field_transaction_pending'},step['id']
        if [x,y]==list(target.values()) and step['kind'] in {'interact','heal'}:
            direction=step.get('face','up')
            return {'phase':'overworld','objective':'Confirm the current selection.' if previous and previous[-1]==direction else f'Move {direction.upper()}.',
                    'available_actions':['a','b'] if previous and previous[-1]==direction else ['up','down','left','right','wait'],
                    'goal':step['id'],'route_step':step['id'],'controller_interaction':True},step['id']
        grid=read_world_grid(pyboy,loc)
        blocked=[tuple(p) for p in plan.get('blocked',{}).get(str(mid),[])]
        from .observation import read_visible_text
        ready=campaign_transactions.ui_overworld_ready(read_visible_text(pyboy),grid) if pyboy is not None and grid else False
        npcs=(world_map.read_npc_obstacles(pyboy,grid,blocked,overworld_ready=True) if ready
              else world_map.read_npc_obstacles(pyboy,grid,blocked)) if grid else None
        if npcs:
            hidden=npcs.get('hidden_source_positions',[]) if npcs.get('toggle_source_calibrated') is True else []
            blocked=list((set(blocked)-set(map(tuple,hidden)))|set(npcs['positions']))
        retry_error=_reviewed_npc_edge_retry(state,step,grid,npcs,ready)
        if retry_error:
            return {'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],
                    'review_reason':retry_error},step['id']
        cleared=[]
        if mid==3:
            if progress['story_event_bits'].get('got_ss_ticket'):cleared.append((27,12))
            if any(i['item']==228 for i in progress.get('inventory') or []):cleared.append((30,8))
        if mid==88 and progress['story_event_bits'].get('bill_said_use_cell_separator'):cleared.append((6,5))
        if mid==61:
            if progress['story_event_bits'].get('got_helix_fossil'):cleared.append((13,6))
            if progress['story_event_bits'].get('got_dome_fossil'):cleared.append((12,6))
        blocked=[p for p in blocked if p not in cleared]
        learned=_LEARNED_EDGES.get(mid,set())
        hint=world_direction(grid,loc,target,blocked,learned) if grid else None
        if not hint and abs(target['x']-x)+abs(target['y']-y)==1 and step.get('terminal') and ((x,y),(target['x'],target['y'])) not in learned:
            direction='up' if target['y']<y else 'down' if target['y']>y else 'left' if target['x']<x else 'right'
            hint={'direction':direction,'kind':'source_verified_terminal_step','path_length':1}
        if hint:
            if npcs:hint['npc_obstacles']=npcs
            if cleared:hint['cleared_story_objects']=cleared
            if learned:hint['observed_blocked_edges']=[list(edge) for edge in sorted(learned)]
            key=(mid,x,y,step['id'])
            if pyboy is not None and (_LAST_ATTEMPT is None or _LAST_ATTEMPT['key']!=key or _LAST_ATTEMPT['direction']!=hint['direction']):
                _LAST_ATTEMPT={'key':key,'direction':hint['direction'],'misses':0}
            return {'phase':'overworld','objective':f"Move {hint['direction'].upper()}.",'available_actions':['up','down','left','right','wait'],
                    'goal':step['id'],'route_step':step['id'],'world_path_hint':hint},step['id']
        return {'phase':'overworld','objective':'Wait.','available_actions':['wait','b'],'navigation_warning':'no_verified_path',
                'goal':step['id'],'route_step':step['id']},step['id']
    training_proof=_training_eof_context(pyboy,state,plan)
    if training_proof is not None:return training_proof,'complete'
    return {'phase':'campaign_review','review_reason':'route_extension_required','route_step':'complete'},'complete'
