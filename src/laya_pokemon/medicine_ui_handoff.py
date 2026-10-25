"""補藥UI閉合的狹窄交接；不宣稱敵回合已結算、不清原controller錯誤。"""
from copy import deepcopy
import re

MODE='verified_enemy_move_v1'


def _bound(bm,c,progress,player_packet,enemy_packet,frame,*,enemy_hp_may_change=False):
    if (c.stage!='retaliation' or c.complete or not isinstance(c.baseline,dict)
            or not bm._int(c.active,0,5) or not isinstance(c.healed,list)):
        return None
    b=c.baseline;loc=b['location'];active=c.active
    p=bm._player(player_packet,frame,loc);e=bm._enemy(enemy_packet,frame,loc)
    party=bm._party(progress);items=bm._inventory(progress.get('inventory'))
    varying=('pp','pp_remaining','hp') if enemy_hp_may_change else ('pp','pp_remaining')
    if (p is None or e is None or party is None or items is None
            or player_packet['active_party_index']!=active
            or not bm._exact(items,c.after_items) or progress.get('money')!=b['money']
            or not c._unchanged_player(p) or not c._party_allowed(party)
            or not 1<=p['hp']<=c.healed[active]['hp']
            or p['status']!=c.healed[active]['status']
            or party[active]['hp'] not in (p['hp'],c.healed[active]['hp'])
            or not 1<=e['hp']<=e['max_hp']
            or not bm._exact({k:v for k,v in e.items() if k not in varying},
                            {k:v for k,v in b['enemy'].items() if k not in varying})):
        return None
    expected=deepcopy(c.healed);expected[active]['hp']=party[active]['hp']
    return (p,e) if bm._exact(party,expected) else None


def after_acknowledged_done_hud(bm,c,text,progress,player,enemy,frame,previous,*,reviewed=False):
    """UseBagItem還原上方HUD就已離開item UI；NPC可在其後正常回血。"""
    bound=_bound(bm,c,progress,player,enemy,frame,enemy_hp_may_change=True)
    allowed_error='bound_state_changed' if reviewed else None
    if (bound is None or c.error!=allowed_error or not isinstance(c.pending,dict)
            or c.pending.get('action')!='a' or not bm._int(c.pending.get('frame'))
            or frame<=c.pending['frame'] or not previous or previous[-1]!='a'
            or not bm._int(getattr(c,'receipt_full_frame',None)) or frame-c.receipt_full_frame<54):
        return False
    p,e=bound
    if p['hp']!=c.healed[c.active]['hp'] or not bm._exact(progress['party'],c.healed):return False
    delta=c.healed[c.active]['hp']-c.baseline['party'][c.active]['hp']
    done=('LAPRAS',f'RECOVERED BY {delta}!') if c.contract['item']==18 else ('LAPRAS'+bm._S,'HEALTH RETURNED!')
    if c.sent_rows!=bm._party_view(c.healed,receipt=done):return False
    if reviewed and (c.last_frame!=frame or not isinstance(c.last_packet,tuple)
            or not bm._exact((text,progress,player,enemy),
                            (c.last_packet[0],c.last_packet[1],c.last_packet[4],c.last_packet[5]))):return False
    if (text.get('profile')!=bm.TEXT_PROFILE or text.get('read_valid') is not True
            or text.get('alignment_verified') is not True or text.get('read_error') is not None
            or type(text.get('window_visible')) is not bool):return False
    cells=text.get('cells')
    if (not isinstance(cells,list) or len(cells)!=18
            or any(not isinstance(row,list) or len(row)!=20 for row in cells)
            or any(not isinstance(ch,str) or len(ch)!=1 for row in cells[:12] for ch in row)):
        return False
    header=bm._clean_art(tuple(''.join(row).upper() for row in cells[:12]))
    return header==bm._freeze(bm._hud(p,e))[:12]


def after_verified_move(bm,c,text,progress,player,enemy,frame):
    """實際藥品A後的完整原生敵招頁，足以證明item UI已閉合。"""
    bound=_bound(bm,c,progress,player,enemy,frame)
    if (bound is None or c.error is not None or c.pending is not None or c.prompt_pages
            or c.enemy_action not in ('EMBER','FIRE BLAST','ROAR','TAKE DOWN')):
        return False
    p,e=bound
    if p['hp']!=c.healed[c.active]['hp'] or not bm._exact(progress['party'],c.healed):return False
    rows=bm._rows(text)
    if rows is None or bm._clean_art(rows)!=bm._dialog(p,e,'ENEMY '+e['species_name'],'USED '+c.enemy_action+'!'):
        return False
    delta=c.healed[c.active]['hp']-c.baseline['party'][c.active]['hp']
    receipt=('LAPRAS',f'RECOVERED BY {delta}!') if c.contract['item']==18 else ('LAPRAS'+bm._S,'HEALTH RETURNED!')
    return (c.sent_rows==bm._party_view(c.healed,receipt=receipt)
            and bm._int(getattr(c,'receipt_full_frame',None))
            and frame-c.receipt_full_frame>=54)


def reviewed_effectiveness(bm,c,text,progress,player,enemy,frame,previous):
    """只交接已確認critical後的來源NotVeryEffective頁；原error保留。"""
    bound=_bound(bm,c,progress,player,enemy,frame)
    if (bound is None or c.error!='native_decoder_not_verified' or c.enemy_action!='FIRE BLAST'
            or c.prompt_pages!={'critical'} or not isinstance(c.pending,dict)
            or c.pending.get('action')!='a' or not bm._int(c.pending.get('frame'))
            or c.pending['frame']>=frame or not previous or previous[-1]!='a'
            or c.last_frame!=frame or not isinstance(c.last_packet,tuple)
            or not bm._exact((text,progress,player,enemy),
                            (c.last_packet[0],c.last_packet[1],c.last_packet[4],c.last_packet[5]))):
        return False
    p,e=bound
    if c.sent_rows!=bm._dialog(p,e,'CRITICAL HIT!','',True):return False
    if (text.get('profile')!=bm.TEXT_PROFILE or text.get('read_valid') is not True
            or text.get('alignment_verified') is not True or text.get('read_error') is not None
            or type(text.get('window_visible')) is not bool):return False
    cells=text.get('cells')
    if (not isinstance(cells,list) or len(cells)!=18
            or any(not isinstance(row,list) or len(row)!=20 for row in cells)):return False
    native=[]
    for y,row in enumerate(cells):
        line=[]
        for x,ch in enumerate(row):
            if ch=="'s" and (x,y)==(3,14) and ''.join(row[1:3]).upper()=='IT':line.append(bm._S)
            elif not isinstance(ch,str) or len(ch)!=1 or ch==bm._S:return False
            else:line.append(ch.upper())
        native.append(''.join(line))
    summaries=[(''.join(row).rstrip(),y) for y,row in enumerate(cells)
               if re.search(r'[A-Za-z0-9]{2,}',''.join(row).rstrip())][:12]
    if text.get('lines')!=[s for s,y in summaries] or text.get('line_rows')!=[y for s,y in summaries]:return False
    rows=tuple(native)
    return (rows[14].startswith(' IT'+bm._S+' N')
            and bm._partial(rows,bm._dialog(p,e,'IT'+bm._S+' NOT VERY','EFFECTIVE...',True)))


def receipt(c,frame,*,reviewed=False):
    return dict(phase='battle_medicine_wait',objective='Wait.',available_actions=['wait'],
        medicine_ui_complete=True,medicine_handoff='existing_battle',
        enemy_turn_resolved=False,survival_approved=False,
        battle_medicine_owner=c.owner,battle_medicine_stage=c.stage,
        battle_medicine_tactic='verified_item_ui_handoff',handoff_frame=frame,
        reviewed_handoff=reviewed,retained_controller_error=c.error,
        field_move_complete=True,field_move_kind='battle-medicine-ui-handoff')
