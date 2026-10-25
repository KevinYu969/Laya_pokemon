"""Bounded trainer medicine UI only; hands restored battle HUD to existing battle.

Fixed red source a536711: core UseBagItem2232-2286 restores buffer1 and both
HUDs after a successful UseItem. ItemEffects1226-1237 uses done + Delay50 +
button wait; party_menu191-215 adds Delay3. No enemy turn is resolved here.
"""
from copy import deepcopy
import re

from laya_pokemon import battle_medicine as ui
from laya_pokemon.player_battle import decode_player_battle

SOURCE_COMMIT=ui.SOURCE_COMMIT
PROFILE='red-en-trainer-active-medicine-ui-v1-candidate'
MAPS=frozenset((33,45,245,246,247,113,120))
HYPER_POTION_INTENT=dict(kind='trainer_battle_medicine_active',target='active',item=18,quantity=1)
FULL_HEAL_INTENT=dict(kind='trainer_battle_medicine_active',target='active',item=52,quantity=1)


def _intent(value):
    return any(ui._exact(value,i) for i in (HYPER_POTION_INTENT,FULL_HEAL_INTENT))


def _player(snapshot,frame,location):
    if (not isinstance(snapshot,dict) or snapshot.get('profile')!=ui.PLAYER_PROFILE
            or snapshot.get('source_commit')!=SOURCE_COMMIT or snapshot.get('read_valid') is not True
            or not ui._int(snapshot.get('observation_frame')) or snapshot['observation_frame']!=frame
            or snapshot.get('battle_kind')!='trainer' or not ui._exact(snapshot.get('location'),location)
            or not ui._int(snapshot.get('active_party_index'),0,5)):
        return None
    p=snapshot.get('player')
    if (not isinstance(p,dict) or not ui._int(p.get('species'),1,190)
            or p['species'] not in ui.ROSTER or not ui._int(p.get('hp'),1,999)
            or not ui._int(p.get('max_hp'),p['hp'],999) or not ui._int(p.get('level'),1,100)
            or type(p.get('status')) is not int or p['status'] not in ui._STATUS
            or any(not isinstance(p.get(k),list) or len(p[k])!=n for k,n in
                   (('moves',4),('pp',4),('dvs',2),('types',2)))
            or any(not ui._int(v,0,255) for k in ('moves','pp','dvs','types') for v in p[k])
            or any(not ui._int(p.get(k),1,999) for k in ('attack','defense','speed','special'))):
        return None
    raw=[0]*29;raw[0]=p['species'];raw[1:3]=divmod(p['hp'],256);raw[4]=p['status']
    raw[5:7]=p['types'];raw[8:12]=p['moves'];raw[12:14]=p['dvs'];raw[14]=p['level']
    raw[15:17]=divmod(p['max_hp'],256);raw[25:29]=p['pp']
    for key,offset in (('attack',17),('defense',19),('speed',21),('special',23)):
        raw[offset:offset+2]=divmod(p[key],256)
    decoded=decode_player_battle(raw)
    return p if decoded['read_valid'] and ui._exact(p,decoded['player']) else None


def _rows(text,player_name):
    if (not isinstance(text,dict) or text.get('profile')!=ui.TEXT_PROFILE
            or text.get('read_valid') is not True or text.get('alignment_verified') is not True
            or text.get('read_error') is not None or type(text.get('window_visible')) is not bool):
        return None
    cells=text.get('cells')
    if not isinstance(cells,(list,tuple)) or len(cells)!=18:
        return None
    rows=[]
    for y,row in enumerate(cells):
        if not isinstance(row,(list,tuple)) or len(row)!=20:return None
        out=[]
        for x,ch in enumerate(row):
            if ch=="'s" and y==14 and x==len(player_name)+1 and ''.join(row[1:x]).upper()==player_name:
                out.append(ui._S)
            elif not isinstance(ch,str) or len(ch)!=1 or ch==ui._S:return None
            else:out.append(ch.upper())
        rows.append(''.join(out))
    expected=[(''.join(row).rstrip(),y) for y,row in enumerate(cells)
              if re.search(r'[A-Za-z0-9]{2,}',''.join(row).rstrip())][:12]
    return tuple(rows) if (text.get('lines')==[s for s,y in expected]
                          and text.get('line_rows')==[y for s,y in expected]) else None


def _hud(player,enemy):
    cells=ui._canvas()
    for x,y,name in ((1,0,enemy['species_name']),(10,7,player['species_name'])):
        ui._put(cells,x+max(0,2-(len(name)-1)//2),y,name)
    for normal,hundred,y,mon in ((5,4,1,enemy),(15,14,8,player)):
        ui._put(cells,hundred if mon['status']==0 and mon['level']==100 else normal,y,
                ui._status(mon['status'],mon['level']))
    ui._put(cells,11,10,f"{player['hp']:3}/{player['max_hp']:3}")
    return cells


def _command_view(player,enemy,cursor=(9,16)):
    cells=_hud(player,enemy)
    for x,y,label in ((10,14,'FIGHT'),(10,16,'ITEM'),(16,16,'RUN')):ui._put(cells,x,y,label)
    cells[cursor[1]][cursor[0]]='▶'
    return ui._freeze(cells)


def _bag_view(player,enemy,items,offset,cursor,arrow):
    cells=_hud(player,enemy)
    for y in range(2,18):
        left=4 if y<12 else 0;cells[y][left:20]=[' ']*(20-left)
    printed=0
    for n in range(4):
        index,y=offset+n,4+2*n
        if index==len(items):ui._put(cells,6,y,'CANCEL');break
        if index>len(items):break
        item=items[index];ui._put(cells,6,y,ui._name(item['item']))
        if item['item'] not in ui._KEY_ITEMS:ui._put(cells,14,y+1,f"×{item['quantity']:2}")
        printed+=1
    cells[4+2*cursor][5]='▶'
    if arrow and printed==4:cells[11][18]='▼'
    return ui._freeze(cells)


class TrainerMedicineUIController:
    """Explicit active-target intent; original snapshots remain unmodified."""
    _wait=ui.BattleMedicineController._wait
    _offer=ui.BattleMedicineController._offer
    _party_allowed=ui.BattleMedicineController._party_allowed
    _unchanged_player=ui.BattleMedicineController._unchanged_player
    def __init__(self,intent,*,owner,max_calls=240,max_seconds=60,max_waits=30):
        if (not _intent(intent) or type(owner) is not str or not 1<=len(owner)<=128
                or not ui._int(max_calls,1,240) or not ui._int(max_waits,1,30)
                or not ui._clock(max_seconds) or not 0<max_seconds<=60):
            raise ValueError('Explicit active Hyper Potion/Full Heal and bounded owner required')
        self.intent=deepcopy(intent);self.contract=deepcopy(intent);self.owner=owner
        self.max_calls,self.max_seconds,self.max_waits=max_calls,max_seconds,max_waits
        self.stage,self.error,self.complete='command',None,False;self.calls=self.waits=0
        self.started=self.last_now=self.last_frame=self.last_packet=None
        self.baseline=self.healed=self.after_items=self.active=None
        self.pending=self.sent_rows=self.expected_cursor=self.expected_bag=None
        self.receipt_full_frame=self.receipt_full_rows=None
        self.receipt_acknowledged=False

    def _hint(self,action,tactic,**extra):
        return dict(phase='trainer_medicine_wait' if action=='wait' else 'trainer_medicine_menu',
            objective='Wait.' if action=='wait' else 'Confirm.' if action=='a' else 'Move '+action.upper()+'.',
            available_actions=['wait'] if action=='wait' else [action,'wait'],
            controller_menu_verified=action!='wait',medicine_ui_profile=PROFILE,
            medicine_ui_stage=self.stage,medicine_ui_tactic=tactic,candidate_only=True,
            survival_approved=False,**extra)

    def _fail(self,reason):
        if self.error is None:self.error=reason
        return {**self._hint('wait','review'),'phase':'strategy_review',
                'review_reason':'trainer_medicine_ui_'+self.error}

    def _hp_animation(self,rows,party,items,player):
        if not ui._exact(party,self.healed) or not ui._exact(items,self.after_items):return False
        h=self.healed[self.active]
        if (player['hp'],player['status'])!=(h['hp'],h['status']):return False
        y=2*self.active+1;token=rows[y][13:16]
        if not re.fullmatch(r' {0,2}[0-9]{1,3}',token):return False
        value=int(token);before=self.baseline['party'][self.active]['hp']
        if token!=f'{value:3}':return False
        if self.contract['item']==18:
            if not before<=value<=h['hp'] or before>=h['hp']:return False
        elif value!=h['hp']:return False
        expected=list(ui._party_view(self.healed,self.active,'▷'))
        expected[y]=expected[y][:13]+token+expected[y][16:]
        if rows[:12]!=tuple(expected[:12]):return False
        name=player['species_name'];delta=h['hp']-before
        message=(name,f'RECOVERED BY {delta}!') if self.contract['item']==18 else (name+ui._S,'HEALTH RETURNED!')
        done=ui._party_view(self.healed,receipt=message)
        # Native RedrawPartyMenu may retain the dim cursor while replacing the
        # old source prompt with the done message. Either known lower partial
        # remains autonomous UI: never A and never a completed transaction.
        return (ui._partial(rows[12:],tuple(expected[12:])) or ui._partial(rows[12:],done[12:]))

    def context(self,text,progress,*,owner,location,battle_state,player_snapshot,enemy_proof,frame,previous,now):
        if self.error:return self._fail(self.error)
        if (owner!=self.owner or not ui._exact(self.intent,self.contract) or not ui._int(frame)
                or not ui._clock(now) or not isinstance(previous,(list,tuple))
                or any(type(a) is not str or a not in ui._ACTIONS for a in previous)):
            return self._fail('owner_intent_frame_clock_or_previous_invalid')
        if self.last_now is not None and (now<self.last_now or frame<self.last_frame):
            return self._fail('clock_or_frame_regressed')
        if self.started is None:self.started=now
        self.calls+=1
        if self.calls>self.max_calls or now-self.started>self.max_seconds:return self._fail('call_or_time_budget_exhausted')
        self.last_now=now
        packet=deepcopy((text,progress,location,battle_state,player_snapshot,enemy_proof))
        if self.last_frame==frame:
            return self._fail('same_frame_observation_changed') if not ui._exact(packet,self.last_packet) else self._wait('same_frame_no_resend')
        self.last_frame,self.last_packet=frame,packet
        loc={k:location.get(k) for k in ('map_id','x','y')} if isinstance(location,dict) else None
        if (loc is None or not ui._int(loc['map_id'],0,255) or loc['map_id'] not in MAPS
                or any(not ui._int(loc[k],0,255) for k in ('x','y'))
                or not isinstance(battle_state,dict) or type(battle_state.get('raw')) is not int
                or battle_state['raw']!=2 or battle_state.get('kind')!='trainer' or battle_state.get('active') is not True
                or not ui._int(battle_state.get('observation_frame')) or battle_state['observation_frame']!=frame):
            return self._fail('verified_whitelisted_trainer_required')
        player,enemy=_player(player_snapshot,frame,loc),ui._enemy(enemy_proof,frame,loc)
        party=ui._party(progress);items=ui._inventory(progress.get('inventory')) if isinstance(progress,dict) else None
        if (player is None or enemy is None or party is None or {m['species'] for m in party}!=ui.ROSTER
                or items is None or any(ui._name(i['item']) in (None,'?????') for i in items)
                or not ui._int(progress.get('money'),0,999999)
                or type(battle_state.get('opponent_species')) is not str
                or battle_state['opponent_species']!=enemy['species_name']):
            return self._fail('party_inventory_or_typed_readers_unverified')
        for p in (text,progress):
            if isinstance(p,dict) and 'observation_frame' in p and (not ui._int(p['observation_frame']) or p['observation_frame']!=frame):
                return self._fail('packet_frame_mismatch')
        raw_rows=_rows(text,player['species_name'])
        if raw_rows is None:return self._fail('native_decoder_not_verified')
        rows=ui._clean_art(raw_rows);active=player_snapshot['active_party_index']
        if self.baseline is None:
            if not any(rows==_command_view(player,enemy,c) for c in ui._COMMAND):return self._fail('initial_full_command_required')
            if any(not ui._exact(party[active].get(k),player.get(k)) for k in ('species','species_name','level','hp','max_hp','status','moves','pp')):
                return self._fail('initial_active_party_not_synchronized')
            if not any(i['item']==self.contract['item'] for i in items):return self._fail('medicine_not_owned')
            if self.contract['item']==18 and player['hp']==player['max_hp'] or self.contract['item']==52 and player['status']==0:
                return self._fail('medicine_would_have_no_effect')
            self.active=active
            self.baseline=dict(party=deepcopy(party),player=deepcopy(player),enemy=deepcopy(enemy),
                               inventory=deepcopy(items),money=progress['money'],location=deepcopy(loc))
            self.healed=deepcopy(party)
            if self.contract['item']==18:self.healed[active]['hp']=min(player['max_hp'],player['hp']+200)
            else:self.healed[active]['status']=0
            self.after_items=deepcopy(items)
            for j,item in enumerate(self.after_items):
                if item['item']==self.contract['item']:
                    item['quantity']-=1
                    if item['quantity']==0:self.after_items.pop(j)
                    break
        b=self.baseline;h=self.healed[self.active]
        enemy_keys=('species','internal_id','species_name','level','max_hp','moves','dvs','types','catch_rate','pp_ups')
        if (active!=self.active or not ui._exact(loc,b['location']) or progress['money']!=b['money']
                or not self._party_allowed(party) or not self._unchanged_player(player)
                or any(not ui._exact(enemy[k],b['enemy'][k]) for k in enemy_keys)):
            return self._fail('bound_state_changed')
        if self.stage in ('command','bag','party'):
            if not ui._exact(party,b['party']) or not ui._exact(player,b['player']) or not ui._exact(items,b['inventory']) or not ui._exact(enemy,b['enemy']):
                return self._fail('premature_effect_or_unrelated_change')
        elif self.stage=='receipt':
            if self.contract['item']==18 and not ui._exact(
                    {k:v for k,v in player.items() if k!='hp'},
                    {k:v for k,v in b['player'].items() if k!='hp'}):
                return self._fail('hyper_potion_unrelated_battle_change')
            if (not (ui._exact(party,b['party']) or ui._exact(party,self.healed))
                    or not (ui._exact(items,b['inventory']) or ui._exact(items,self.after_items))
                    or (player['hp'],player['status']) not in ((b['player']['hp'],b['player']['status']),(h['hp'],h['status']))
                    or ui._exact(items,self.after_items) and (not ui._exact(party,self.healed) or (player['hp'],player['status'])!=(h['hp'],h['status']))
                    or not ui._exact(enemy,b['enemy'])):
                return self._fail('medicine_effect_order_or_delta_invalid')
        elif (not ui._exact(items,self.after_items) or party[active]['hp'] not in (h['hp'],player['hp'])
                or party[active]['status'] not in (h['status'],player['status'])):
            return self._fail('post_ack_state_unverified')
        if self.pending is not None:
            if not previous or previous[-1]!=self.pending['action']:
                if previous and previous[-1]!='wait':return self._fail('actual_previous_does_not_match_offer')
                return self._wait('await_actual_previous')
            if self.stage=='hud_restore':self.receipt_acknowledged=True
            self.pending=None
        if self.sent_rows is not None and rows==self.sent_rows:return self._wait('old_page_no_resend')
        if self.stage=='command':
            found=next((c for c in ui._COMMAND if rows==_command_view(player,enemy,c)),None)
            if found is None:return self._fail('full_command_unverified')
            if self.expected_cursor is not None and found!=self.expected_cursor:return self._fail('command_cursor_did_not_follow_offer')
            if found!=(9,16):
                action='left' if found[0]==15 else 'down'
                self.expected_cursor=(9,found[1]) if action=='left' else (9,16)
                return self._offer(action,rows,'command','navigate_item')
            return self._offer('a',rows,'bag','open_battle_item_direct')
        if self.stage=='bag':
            views=[(o,c,_bag_view(player,enemy,items,o,c,a)) for o in range(max(1,len(items)))
                   for c in range(3) if o+c<=len(items) for a in (False,True)]
            found={(o,c) for o,c,v in views if rows==v}
            if len(found)!=1:return self._wait('known_bag_partial') if any(ui._partial(rows,v) for o,c,v in views) else self._fail('bag_viewport_unverified')
            off,cur=next(iter(found))
            if self.expected_bag is not None and (off,cur)!=self.expected_bag:return self._fail('bag_cursor_did_not_follow_offer')
            target=next(i for i,item in enumerate(items) if item['item']==self.contract['item'])
            if off+cur==target:
                self.expected_bag=None;return self._offer('a',rows,'party','use_selected_medicine_no_toss')
            action='down' if off+cur<target else 'up'
            self.expected_bag=((off,cur+1) if cur<2 else (off+1,2)) if action=='down' else ((off,cur-1) if cur>0 else (max(0,off-1),0))
            return self._offer(action,rows,'bag','navigate_actual_bag')
        if self.stage=='party':
            found=next((i for i in range(6) if rows==ui._party_view(party,i)),None)
            if found is None:return self._wait('known_party_partial') if any(ui._partial(rows,ui._party_view(party,i)) for i in range(6)) else self._fail('party_page_unverified')
            if type(self.expected_cursor) is int and found!=self.expected_cursor:return self._fail('party_cursor_did_not_follow_offer')
            if found!=active:
                action='down' if found<active else 'up';self.expected_cursor=found+(1 if action=='down' else -1)
                return self._offer(action,rows,'party','select_actual_active_only')
            self.expected_cursor=None;return self._offer('a',rows,'receipt','apply_one_medicine')
        if self.stage=='receipt':
            name=player['species_name'];delta=h['hp']-b['party'][active]['hp']
            message=(name,f'RECOVERED BY {delta}!') if self.contract['item']==18 else (name+ui._S,'HEALTH RETURNED!')
            full=ui._party_view(self.healed,receipt=message)
            if raw_rows==full:
                if not ui._exact(items,self.after_items) or not ui._exact(party,self.healed) or (player['hp'],player['status'])!=(h['hp'],h['status']):
                    return self._fail('receipt_without_observed_effect_and_consumption')
                if self.receipt_full_frame is None or self.receipt_full_rows!=full:
                    self.receipt_full_frame,self.receipt_full_rows=frame,full
                    return self._wait('known_done_receipt_settling')
                if frame-self.receipt_full_frame<54:return self._wait('known_done_receipt_settling')
                return self._offer('a',rows,'hud_restore','ack_stable_done_receipt_once')
            self.receipt_full_frame=self.receipt_full_rows=None
            if self._hp_animation(raw_rows,party,items,player):return self._wait('known_active_hp_animation')
            if ui._partial(rows,full) or ui._partial(rows,ui._party_view(b['party'],active,'▷')):
                return self._wait('known_effect_or_receipt_partial')
            return self._fail('medicine_receipt_unknown')
        if not self.receipt_acknowledged:return self._fail('actual_receipt_ack_required')
        expected=ui._freeze(_hud(player,enemy))
        if raw_rows[:12]==expected[:12]:
            lower='|'.join(rows[12:])
            if any(token in lower for token in ('USE ITEM ON WHICH','RECOVERED BY','HEALTH RETURNED!')):
                return self._fail('medicine_page_not_closed')
            if any(token in lower for token in ('FAINTED','BLACKED OUT','FNT')):
                return self._fail('terminal_page_requires_existing_guard')
            self.complete,self.stage=True,'complete'
            return self._hint('wait','existing_battle_handoff',medicine_ui_complete=True,
                              medicine_handoff='existing_battle',enemy_turn_resolved=False)
        if ui._partial(raw_rows[:12],expected[:12]):return self._wait('known_hud_restore_partial')
        return self._fail('restored_battle_hud_unverified')
