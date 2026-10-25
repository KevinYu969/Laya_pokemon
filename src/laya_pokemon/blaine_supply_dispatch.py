"""只在完整夏伯command決定固定補藥；對話仍走既有戰鬥控制器。"""
from . import battle_medicine_bridge as bridge,battle_medicine as bm
from . import blaine_supply_policy as policy,player_battle,trainer_opponent


def _review(reason,step_id):
    return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
                review_reason='blaine_supply_'+reason),step_id


def _reviewed_rapidash_finisher(state,step,text,player_snapshot,enemy_proof,frame):
    """限定父層已檢視的5HP收尾；保留會心五次火焰漩渦的3HP風險。"""
    if step.get('reviewed_rapidash_finisher') is not True:return None
    player=bm._player(player_snapshot,frame,policy.LOCATION)
    enemy=bm._enemy(enemy_proof,frame,policy.LOCATION)
    party=bm._party(state.get('progress'))
    if player is None or enemy is None or party is None:return None
    active=player_snapshot['active_party_index']
    if (enemy['species']!=164 or enemy['level']!=42 or enemy['status']!=0
            or enemy['max_hp']!=113 or not 1<=enemy['hp']<=5
            or enemy['moves']!=[39,23,45,83]
            or (enemy['attack'],enemy['special'])!=(96,78)
            or player['status']!=0 or player['max_hp']!=156
            or not 77<=player['hp']<=78 or player['special']!=88 or player['defense']!=88
            or (player['pp'][0]&63)<1
            or any(party[active][k]!=player[k] for k in ('species','hp','max_hp','status','moves','pp'))):
        return None
    rows=bm._rows(text)
    if rows is None:return None
    rows=bm._clean_art(rows)
    if not any(rows==bm._command_view(player,enemy,c) for c in bm._COMMAND):return None
    from .battle import _selection_hint
    return {**_selection_hint(rows,(10,14),'command'),
        'battle_tactic':'reviewed_rapidash_5hp_finisher',
        'finisher_risk':'FireSpin critical five-hit maximum80 exceeds77/78HP; normal gameplay risk accepted, FNT guard retained',
        'finisher_source_enemy_hp':enemy['hp'],'survival_approved':False}


def context(pyboy,state,plan,step_id,text,previous):
    steps=plan.get('steps') if isinstance(plan,dict) else None
    matches=[s for s in steps if isinstance(s,dict) and s.get('id')==step_id] if type(steps) is list else []
    if len(matches)!=1 or bridge._signature(step_id,matches[0]) is None:
        return _review('fixed_step_unverified',step_id)
    if bridge._active():
        return bridge.context(pyboy,state,plan,step_id,text,previous)
    battle=state.get('battle_state',{})
    if battle.get('kind')=='none' and battle.get('active') is False and type(battle.get('raw')) is int and battle['raw']==0:
        return None
    if (battle.get('kind')!='trainer' or battle.get('active') is not True
            or type(battle.get('raw')) is not int or battle['raw']!=2):
        return _review('trainer_unverified',step_id)
    # Native dialogues, faint/EXP, replacement prompts and victory are not item
    # decisions. In particular a zero-HP enemy is not an invalid medicine start.
    rows=bm._rows(text)
    if rows is None:
        return None
    rows=bm._clean_art(rows)
    if not all(rows[y][x:x+len(label)]==label for x,y,label in ((10,14,'FIGHT'),(10,16,'ITEM'),(16,16,'RUN'))):
        return None
    frame=state.get('frame');loc=state.get('location')
    if (not bm._int(frame) or not bm._exact(loc,policy.LOCATION)
            or type(battle.get('observation_frame')) is not int or battle['observation_frame']!=frame):
        return _review('command_frame_location_unverified',step_id)
    constants=bridge._sdk_constants()
    player=player_battle.read_player_battle(pyboy,observation_frame=frame,
        expected_location=loc,constants=constants,profile=player_battle.PROFILE)
    enemy=trainer_opponent.read_trainer_opponent(pyboy,observation_frame=frame,
        expected_location=loc,constants=constants,profile=trainer_opponent.PROFILE)
    if pyboy.frame_count!=frame:
        return _review('command_frame_changed',step_id)
    decision=policy.decide(text,state.get('progress'),player,enemy,frame)
    if decision.get('action')=='review':return _review(decision['reason'],step_id)
    if decision.get('action')=='none':
        finisher=_reviewed_rapidash_finisher(state,matches[0],text,player,enemy,frame)
        if finisher is not None:return finisher,step_id
        if decision.get('reason')=='full_native_command_not_ready':
            return _review('command_hud_requires_calibration',step_id)
        return None
    if decision.get('action')!='medicine':return _review('decision_unverified',step_id)
    # Completion is journaled without ticking. Obtain a genuinely fresh command
    # before asking the bridge for another owner on that same native menu.
    if any(bridge._BINDINGS[o].get('completed_frame')==frame for o in bridge._COMPLETED):
        return dict(phase='battle_medicine_wait',objective='Wait.',available_actions=['wait'],
                    battle_tactic='fresh_command_before_next_medicine'),step_id
    result=bridge.context(pyboy,state,plan,step_id,text,previous,intent=decision['intent'])
    if result is None:return _review('medicine_intent_not_claimed',step_id)
    hint,nxt=result
    return {**hint,'blaine_supply_decision':decision},nxt
