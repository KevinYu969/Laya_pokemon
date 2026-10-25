"""Parent-owned half-HP trainer supply policy; pure decisions, never keys.

The damage range is conditional normal non-critical damage, not a prediction
of survival, accuracy, Substitute, volatile execution state or a critical hit.
"""
from copy import deepcopy

from laya_pokemon import trainer_medicine_ui as medicine
from laya_pokemon.ditto_transform import _TYPES
from laya_pokemon.player_battle import decode_player_battle
from laya_pokemon.team_strategy import choose_damage_move,reference

PROFILE='red-en-trainer-half-hp-supply-policy-v1-candidate'
_TYPE_NAMES={value:('PSYCHIC_TYPE' if name=='PSYCHIC' else name) for name,value in _TYPES.items()}
_DIRECT_EFFECTS=frozenset(('NO_ADDITIONAL_EFFECT','BURN_SIDE_EFFECT1','BURN_SIDE_EFFECT2',
    'FREEZE_SIDE_EFFECT1','PARALYZE_SIDE_EFFECT1','PARALYZE_SIDE_EFFECT2',
    'POISON_SIDE_EFFECT1','POISON_SIDE_EFFECT2','FLINCH_SIDE_EFFECT1','FLINCH_SIDE_EFFECT2',
    'CONFUSION_SIDE_EFFECT','ATTACK_DOWN_SIDE_EFFECT','DEFENSE_DOWN_SIDE_EFFECT',
    'SPEED_DOWN_SIDE_EFFECT','SPECIAL_DOWN_SIDE_EFFECT'))
_NORMAL_RISKS=['conditional_on_hit_and_normal_noncritical_execution',
    'critical_hit_substitute_disable_invulnerability_not_guaranteed',
    'parent_strategy_risk_no_survival_guarantee']


def _result(action,reason,*,intent=None,move_key=None,estimate=None,risks=()):
    out=dict(action=action,reason=reason,risks=list(risks),profile=PROFILE,survival_approved=False)
    if intent is not None:out['intent']=deepcopy(intent)
    if move_key is not None:out['move_key']=move_key
    if estimate is not None:out['estimate']=deepcopy(estimate)
    return out


def _zero_player(snapshot,frame,location):
    if (type(snapshot) is not dict or snapshot.get('profile')!=medicine.ui.PLAYER_PROFILE
            or snapshot.get('source_commit')!=medicine.SOURCE_COMMIT or snapshot.get('read_valid') is not True
            or not medicine.ui._int(snapshot.get('observation_frame')) or snapshot['observation_frame']!=frame
            or snapshot.get('battle_kind')!='trainer' or not medicine.ui._exact(snapshot.get('location'),location)
            or not medicine.ui._int(snapshot.get('active_party_index'),0,5)):
        return False
    p=snapshot.get('player')
    zero=(type(p) is dict and type(p.get('hp')) is int and p['hp']==0
            and medicine.ui._int(p.get('species'),1,190) and p['species'] in medicine.ui.ROSTER
            and p.get('species_name')==medicine.ui._SPECIES[p['species']]
            and medicine.ui._int(p.get('max_hp'),1,999) and medicine.ui._int(p.get('level'),1,100))
    if not zero:return False
    try:
        raw=[p['species'],0,0,0,p['status'],*p['types'],0,*p['moves'],*p['dvs'],p['level'],*divmod(p['max_hp'],256)]
        for key in ('attack','defense','speed','special'):raw.extend(divmod(p[key],256))
        raw.extend(p['pp']);decoded=decode_player_battle(raw)
        return decoded['read_valid'] and medicine.ui._exact(p,decoded['player'])
    except (KeyError,TypeError,ValueError):return False


def _zero_enemy(snapshot,frame):
    # The real trainer reader deliberately withholds enemy/raw_record at0HP.
    return (type(snapshot) is dict and snapshot.get('profile')==medicine.ui.ENEMY_PROFILE
            and snapshot.get('source_commit')==medicine.SOURCE_COMMIT
            and snapshot.get('read_valid') is False and snapshot.get('enemy') is None
            and snapshot.get('raw_record') is None and snapshot.get('unknown_reason')=='enemy_zero_hp_transition'
            and all(medicine.ui._int(snapshot.get(k)) and snapshot[k]==frame
                    for k in ('observation_frame','frame_before','frame_after')))


def _direct(entry):
    return (type(entry) is dict and type(entry.get('power')) is int and 1<entry['power']<=255
            and type(entry.get('accuracy')) is int and 0<entry['accuracy']<=100
            and entry.get('effect') in _DIRECT_EFFECTS and entry.get('type') in _TYPE_NAMES.values())


def _types(mon):
    try:return tuple(_TYPE_NAMES[value] for value in mon['types'])
    except (KeyError,TypeError):return None


def _type_possible(entry,enemy,ref):
    targets=_types(enemy)
    if targets is None:return False
    return not any(attacker==entry['type'] and defender in targets and factor==0
                   for attacker,defender,factor in ref['type_matchups'])


def estimate_normal_damage(player,enemy,move_key):
    """Source normal range across no-screen/screen and RNG217..255, or None.

    Screens are not in the supplied snapshot, so both scenarios are included.
    Source byte scaling/rounding is retained; possible division-by-zero yields
    unknown rather than a fabricated lower bound. Fixed/OHKO/explosive and
    other special damage effects are not evaluated as normal damage.
    """
    ref=reference();entry=ref['moves'].get(move_key)
    if ref.get('source_commit')!=medicine.SOURCE_COMMIT or not _direct(entry):return None
    attack_types,target_types=_types(player),_types(enemy)
    if attack_types is None or target_types is None:return None
    special=next(code for code,name in _TYPE_NAMES.items() if name==entry['type'])>=20
    attack=player['special' if special else 'attack']
    defense=enemy['special' if special else 'defense']
    values=[]
    for screen in (1,2):
        a,d=attack,defense*screen
        if a>255 or d>255:
            a=max(1,a//4)&255;d=(d//4)&255
        if d==0:return None
        neutral=min(997,(((2*player['level']//5+2)*entry['power']*a)//d)//50)+2
        if entry['type'] in attack_types:neutral+=neutral//2
        for attacking,defending,factor in ref['type_matchups']:
            if attacking==entry['type'] and defending in target_types:
                numerator={0:0,0.5:5,1:10,2:20}.get(factor)
                if numerator is None:return None
                neutral=neutral*numerator//10
        values.extend(neutral if neutral<2 else neutral*rng//255 for rng in range(217,256))
    return dict(kind='conditional_normal_range',move_key=move_key,lower=min(values),upper=max(values),
        attack_stat='special' if special else 'attack',defense_stat='special' if special else 'defense',
        rng=[217,255],screen_scenarios=['absent','present'],damage_exact=False,
        conditions=list(_NORMAL_RISKS),survival_approved=False)


def decide(text,progress,player_snapshot,enemy_proof,frame,location):
    """Only none/medicine/finish/review; root retains battle/terminal ownership."""
    if not medicine.ui._int(frame):return _result('review','observation_frame_invalid')
    loc={k:location.get(k) for k in ('map_id','x','y')} if type(location) is dict else None
    if loc is None or any(not medicine.ui._int(loc[k],0,255) for k in loc):
        return _result('review','location_unverified')
    if loc['map_id'] not in medicine.MAPS:return _result('none','outside_trainer_policy_scope')
    if _zero_player(player_snapshot,frame,loc) or _zero_enemy(enemy_proof,frame):
        return _result('none','existing_faint_or_loss_guard')
    player,enemy=medicine._player(player_snapshot,frame,loc),medicine.ui._enemy(enemy_proof,frame,loc)
    if player is None or enemy is None:return _result('review','same_frame_typed_readers_unverified')
    for packet in (text,progress):
        if type(packet) is not dict:return _result('review','original_text_progress_required')
        if 'observation_frame' in packet and (not medicine.ui._int(packet['observation_frame']) or packet['observation_frame']!=frame):
            return _result('review','packet_frame_disagrees')
    rows=medicine._rows(text,player['species_name'])
    if rows is None:return _result('review','native_decoder_unverified')
    rows=medicine.ui._clean_art(rows)
    if not any(rows==medicine._command_view(player,enemy,c) for c in medicine.ui._COMMAND):
        return _result('none','full_native_command_not_ready')
    party=medicine.ui._party(progress);inventory=medicine.ui._inventory(progress.get('inventory'))
    if (party is None or {mon['species'] for mon in party}!=medicine.ui.ROSTER
            or inventory is None or any(medicine.ui._name(i['item']) in (None,'?????') for i in inventory)
            or not medicine.ui._int(progress.get('money'),0,999999)):
        return _result('review','party_inventory_money_unverified')
    active=player_snapshot['active_party_index']
    if ([i for i,p in enumerate(party) if p['species']==player['species']]!=[active]
            or any(not medicine.ui._exact(party[active].get(k),player.get(k)) for k in
                   ('species','species_name','level','hp','max_hp','status','moves','pp'))):
        return _result('review','unique_active_party_not_synchronized')
    ref=reference()
    if ref.get('source_commit')!=medicine.SOURCE_COMMIT:return _result('review','fixed_reference_unverified')
    chosen=choose_damage_move(player['species'],player['moves'],player['pp'],enemy['species'])
    if chosen is None:return _result('review','no_usable_damage_move')
    entry=ref['moves'].get(chosen)
    estimate=estimate_normal_damage(player,enemy,chosen)
    eligible=player['status'] in (0,16) and (player['speed']>=enemy['speed'] or player['hp']*2>player['max_hp'])
    if eligible and estimate is not None and enemy['hp']<=estimate['lower']:
        return _result('finish','conditional_normal_lower_finisher',move_key=chosen,estimate=estimate,risks=_NORMAL_RISKS)
    if (eligible and estimate is None and enemy['hp']<=4 and _direct(entry)
            and _type_possible(entry,enemy,ref)):
        heuristic=dict(kind='enemy_hp_at_most4_heuristic',lower=None,upper=None,move_key=chosen,
                       damage_exact=False,survival_approved=False)
        return _result('finish','enemy_hp_at_most4_heuristic_finisher',move_key=chosen,estimate=heuristic,
                       risks=[*_NORMAL_RISKS,'heuristic_not_a_damage_or_survival_guarantee'])
    if player['hp']*2<=player['max_hp']:
        if not any(i['item']==18 for i in inventory):return _result('review','required_hyper_potion_not_owned')
        return _result('medicine','hp_at_most_half_hyper_potion',intent=medicine.HYPER_POTION_INTENT,
                       risks=['medicine_spends_turn_enemy_can_act','parent_strategy_risk_no_survival_guarantee'])
    if player['status']!=0:
        if not any(i['item']==52 for i in inventory):return _result('review','required_full_heal_not_owned')
        return _result('medicine','above_half_status_full_heal',intent=medicine.FULL_HEAL_INTENT,
                       risks=['medicine_spends_turn_enemy_can_act','parent_strategy_risk_no_survival_guarantee'])
    return _result('none','healthy_above_half_existing_battle')
