"""Parent-scoped trainer medicine decisions; preserve existing battle ownership."""
import re
import sys

from . import battle,trainer_medicine_ui_bridge as bridge
from . import trainer_medicine_policy as policy,player_battle,trainer_opponent
from .team_strategy import reference,species_key

_PEERS=('battle_medicine_bridge','mansion_secret_key_bridge','mansion_statue_bridge',
    'mansion_transition_ready','mansion_native_landing','route21_water_bridge',
    'pallet_surf_bridge','fly_pallet_bridge','fly_viridian_bridge','safari_entry',
    'hm_teaching_bridge','vending_bridge','saffron_guard_bridge','silph_card_bridge',
    'lapras_bridge','player_pc_bridge','cinnabar_purchase_bridge','campaign_transactions')


def _review(reason,step_id):
    return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
        review_reason='trainer_medicine_dispatch_'+reason,survival_approved=False),step_id


def _peer_busy():
    # Only inspect canonical, already loaded registries. An active transaction
    # necessarily owns such a module; importing route here would reset clocks.
    for name in _PEERS:
        module=sys.modules.get('laya_pokemon.'+name)
        if module is None:continue
        bindings=getattr(module,'_BINDINGS',{})
        completed=getattr(module,'_COMPLETED',set())
        controllers=getattr(module,'_CONTROLLERS',{})
        if type(bindings) is not dict or type(completed) is not set or type(controllers) is not dict:return True
        if (set(bindings)|set(controllers))-completed:return True
        if name=='safari_entry' and getattr(module,'_RUN_CONTROLLER',None) is not None:return True
    capture=sys.modules.get('laya_pokemon.capture_transaction')
    if capture is not None:
        sessions=getattr(capture,'_SESSIONS',{})
        if type(sessions) is not dict or any(type(s) is not dict or s.get('done') is not True for s in sessions.values()):return True
    return False


def _display_status(token):
    if re.fullmatch(r'[1-9][0-9]?|100',token):return dict(level=int(token),status=0)
    status={'SLP':1,'PSN':8,'BRN':16,'FRZ':32,'PAR':64}.get(token)
    return None if status is None else dict(level=1,status=status)


def _command_rows(text,runtime):
    """Complete source command geometry before any BattleMon RAM reader.

    Displayed numbers are only layout evidence. The frozen policy checks their
    equality against both genuine typed reader packets before choosing anything.
    """
    medicine=bridge.medicine
    rows=medicine._rows(text,'')
    if rows is None:return None
    rows=medicine.ui._clean_art(rows)
    if not battle._trainer_half_command_layout(list(rows)):return None
    enemy_name=runtime.get('opponent_species') if type(runtime) is dict else None
    if type(enemy_name) is not str or enemy_name not in reference()['species']:return None
    names=[species_key(s) for s in medicine.ui.ROSTER]
    actors=[name for name in names if rows[7].strip()==name]
    if len(actors)!=1 or rows[0].strip()!=enemy_name:return None
    p=_display_status(rows[8].strip());e=_display_status(rows[1].strip())
    token=rows[10][11:18]
    if p is None or e is None or not re.fullmatch(r' {0,2}[0-9]{1,3}/ {0,2}[0-9]{1,3}',token):return None
    hp,max_hp=(int(v) for v in token.split('/'))
    if not 0<=hp<=max_hp<=999 or max_hp==0 or token!=f'{hp:3}/{max_hp:3}':return None
    p.update(species_name=actors[0],hp=hp,max_hp=max_hp);e.update(species_name=enemy_name)
    if not any(rows==medicine._command_view(p,e,c) for c in medicine.ui._COMMAND):return None
    return rows


def context(pyboy,state,plan,step_id,text,previous):
    """Return a hint and unchanged trainer step, or None for legacy battle."""
    active=bridge._active()
    steps=plan.get('steps') if type(plan) is dict else None
    matches=[s for s in steps if type(s) is dict and s.get('id')==step_id] if type(steps) is list else []
    marked=any(s.get('battle_supply')==bridge.SUPPLY for s in matches)
    if not active and not marked:return None
    if _peer_busy():return _review('other_transaction_active',step_id)
    if active:
        return bridge.context(pyboy,state,plan,step_id,text,previous)
    if len(matches)!=1 or bridge._signature(step_id,matches[0]) is None:
        return _review('fixed_step_unverified',step_id)
    runtime=state.get('battle_state') if type(state) is dict else None
    if type(runtime) is not dict:return _review('runtime_unverified',step_id)
    if runtime.get('kind')=='none' and runtime.get('active') is False and type(runtime.get('raw')) is int and runtime['raw']==0:return None
    rows=_command_rows(text,runtime)
    if rows is None:return None
    if runtime.get('kind')!='trainer' or runtime.get('active') is not True or type(runtime.get('raw')) is not int or runtime['raw']!=2:
        return _review('trainer_unverified',step_id)
    frame=state.get('frame');loc=state.get('location');signature=bridge._signature(step_id,matches[0])
    expected=dict(map_id=signature[2],x=signature[3][0],y=signature[3][1])
    if (not bridge._int(frame) or not bridge._exact(loc,expected)
            or not bridge._int(runtime.get('observation_frame')) or runtime['observation_frame']!=frame):
        return _review('command_frame_location_unverified',step_id)
    for packet in (text,state.get('progress')):
        if type(packet) is not dict:return _review('original_packet_unverified',step_id)
        if 'observation_frame' in packet and (not bridge._int(packet['observation_frame']) or packet['observation_frame']!=frame):
            return _review('packet_frame_disagrees',step_id)
    try:
        sdk=bridge._sdk_constants();before=pyboy.frame_count
        if not bridge._int(before) or before!=frame:return _review('command_frame_changed',step_id)
        player=player_battle.read_player_battle(pyboy,observation_frame=frame,
            expected_location=loc,constants=sdk,profile=player_battle.PROFILE)
        enemy=trainer_opponent.read_trainer_opponent(pyboy,observation_frame=frame,
            expected_location=loc,constants=sdk,profile=trainer_opponent.PROFILE)
        after=pyboy.frame_count
    except Exception:return _review('readonly_snapshot_failed',step_id)
    if not bridge._int(after) or after!=frame:return _review('command_frame_changed',step_id)
    decision=policy.decide(text,state.get('progress'),player,enemy,frame,loc)
    if type(decision) is not dict or decision.get('survival_approved') is not False:return _review('decision_unverified',step_id)
    action=decision.get('action')
    if action=='review':return _review(decision.get('reason','policy_review'),step_id)
    if action=='none':
        if decision.get('reason')=='full_native_command_not_ready':return _review('command_hud_requires_calibration',step_id)
        return None
    if action=='finish':
        return {**battle._selection_hint(rows,(10,14),'command'),
            'battle_tactic':'trainer_medicine_policy_finisher','trainer_medicine_decision':decision,
            'survival_approved':False},step_id
    if action!='medicine' or bridge._fixed_intent(decision.get('intent')) is None:return _review('decision_unverified',step_id)
    if any(type(bridge._BINDINGS.get(o)) is dict and bridge._BINDINGS[o].get('completed_frame')==frame for o in bridge._COMPLETED):
        return dict(phase='trainer_medicine_wait',objective='Wait.',available_actions=['wait'],
            battle_tactic='fresh_command_before_next_medicine',survival_approved=False),step_id
    result=bridge.context(pyboy,state,plan,step_id,text,previous,intent=decision['intent'])
    if result is None:return _review('medicine_intent_not_claimed',step_id)
    hint,nxt=result
    return {**hint,'trainer_medicine_decision':decision},nxt
