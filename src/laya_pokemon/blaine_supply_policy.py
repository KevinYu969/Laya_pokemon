"""Parent-owned single Blaine live-test policy; proposes intent, never presses keys.

Caller runs existing FNT/loss guards first and serializes the original text,
progress and two same-frame readers. Native text/progress have no frame field;
if a caller supplies one, it must agree. Profiles cannot authenticate a caller.
"""
from copy import deepcopy

from laya_pokemon import battle_medicine as bm


PROFILE='red-en-blaine-lapras38-parent-live-test-policy-v1-candidate'
LOCATION={'map_id':166,'x':3,'y':4}
LIVE_RISK='parent_authorized_live_test_not_guaranteed_survival'
FULL_HEAL_RISK='full_heal_critical_fire_blast_and_reburn_may_ko_at_hp142_150'


def _result(action,reason,*,intent=None,risks=()):
    result=dict(action=action,reason=reason,risks=list(risks),profile=PROFILE,
                survival_approved=False)
    if intent is not None:result['intent']=deepcopy(intent)
    return result


def _zero_hp_player(snapshot,frame):
    # Preserve the caller's existing terminal guard, without turning a zero-HP
    # record into a live-player proof or asking the medicine UI to revive it.
    if (not isinstance(snapshot,dict) or snapshot.get('profile')!=bm.PLAYER_PROFILE
            or snapshot.get('source_commit')!=bm.SOURCE_COMMIT
            or snapshot.get('read_valid') is not True
            or not bm._int(snapshot.get('observation_frame'))
            or snapshot['observation_frame']!=frame
            or snapshot.get('battle_kind')!='trainer'
            or not bm._exact(snapshot.get('location'),LOCATION)
            or not bm._int(snapshot.get('active_party_index'),0,5)):
        return False
    p=snapshot.get('player')
    return (isinstance(p,dict) and type(p.get('hp')) is int and p['hp']==0
            and type(p.get('species')) is int and p['species']==19
            and p.get('species_name')=='LAPRAS')


def decide(text,progress,player_snapshot,enemy_proof,frame):
    """Return only none/medicine/review. FNT/loss guards retain caller priority."""
    if not bm._int(frame):return _result('review','observation_frame_invalid')
    enemy=bm._enemy(enemy_proof,frame,LOCATION)
    if enemy is None:return _result('review','same_frame_trainer_enemy_unverified')
    # No extension to other opponents or the earlier Blaine roster.
    if enemy['species']!=20:return _result('none','non_arcanine_existing_guards')
    if _zero_hp_player(player_snapshot,frame):
        return _result('none','zero_hp_existing_loss_guard')
    player=bm._player(player_snapshot,frame,LOCATION)
    if player is None:return _result('review','same_frame_active_lapras_unverified')
    if not isinstance(progress,dict):return _result('review','original_progress_required')
    for packet in (text,progress):
        if (isinstance(packet,dict) and 'observation_frame' in packet
                and (not bm._int(packet['observation_frame']) or packet['observation_frame']!=frame)):
            return _result('review','text_or_progress_frame_disagrees')
    rows=bm._rows(text)
    if rows is None:return _result('review','native_text_decoder_unverified')
    rows=bm._clean_art(rows)
    if not any(rows==bm._command_view(player,enemy,cursor) for cursor in bm._COMMAND):
        return _result('none','full_native_command_not_ready')
    if enemy['level']!=47 or player['max_hp']!=156 or player['special']!=88:
        return _result('review','fixed_blaine_live_test_stats_required')
    party=bm._party(progress)
    if party is None:return _result('review','original_party_unverified')
    if not bm._int(progress.get('money'),0,999999):
        return _result('review','original_money_unverified')
    matches=[i for i,m in enumerate(party) if m['species']==19]
    active=player_snapshot['active_party_index']
    if matches!=[active]:return _result('review','unique_active_lapras_required')
    if {m['species'] for m in party}!=bm.ROSTER:
        return _result('review','fixed_party_required')
    if (any(not bm._exact(party[active].get(k),player.get(k)) for k in
            ('species','species_name','level','hp','max_hp','status','moves','pp'))
            or any(m['status']!=0 for i,m in enumerate(party) if i!=active)):
        return _result('review','party_and_battle_not_synchronized')
    if (not bm._exact(player.get('pp_remaining'),[v&63 for v in player['pp']])
            or not bm._exact(player.get('pp_ups'),[v>>6 for v in player['pp']])
            or (player['pp'][0]&63)==0):
        return _result('review','surf_pp_unverified_or_empty')
    hp,status=player['hp'],player['status']
    if status==0:
        if hp>150:return _result('none','healthy_hp_above150_existing_surf',risks=[LIVE_RISK])
        intent=bm.HYPER_POTION_INTENT;reason='healthy_hp_at_most150_hyper_potion'
    elif status==16:
        if hp<=141:
            intent=bm.HYPER_POTION_INTENT;reason='burned_hp_at_most141_hyper_potion'
        else:
            intent=bm.FULL_HEAL_INTENT;reason='burned_hp_above141_full_heal'
    else:return _result('review','unsupported_status')
    inventory=bm._inventory(progress.get('inventory'))
    if inventory is None or any(bm._name(i['item']) in (None,'?????') for i in inventory):
        return _result('review','medicine_inventory_unverified')
    if not any(i['item']==intent['item'] for i in inventory):
        return _result('review','selected_medicine_not_owned')
    if (intent['item']==18 and hp==player['max_hp'] or intent['item']==52 and status==0):
        return _result('review','selected_medicine_would_have_no_effect')
    risks=[LIVE_RISK]
    if intent['item']==52 and hp<=150:risks.append(FULL_HEAL_RISK)
    return _result('medicine',reason,intent=intent,risks=risks)
