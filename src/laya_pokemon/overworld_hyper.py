"""固定 Victory2F 停點的正常野外 Hyper Potion 交易；不送鍵／tick／寫 RAM。"""
from copy import deepcopy
import math
import re
from . import battle_medicine as ui, hm_teaching as hm, progress as progress_reader, rocket_movement
from .team_strategy import reference,move_key

SOURCE_COMMIT=ui.SOURCE_COMMIT
PROFILE='red-en-overworld-hyper-victory2f-v1-candidate'
LOCATION=dict(map_id=194,x=20,y=13)
MAX_SECONDS,MAX_CALLS,MAX_WAITS=60,240,30
INTENTS=tuple(dict(kind='overworld_hyper_victory2f',map_id=194,target=[20,13],
    item=18,quantity=1,target_species=species) for species in (19,132))
ADDRESSES=dict(map_id=0xD35E,x=0xD362,y=0xD361,raw=0xD057,battle_type=0xD05A,
    badges=0xD356,mode=0xD700,status5=0xD730,script=0xD63F)
# 固定 wram.asm：Route22 D60A + 41 db + 12 ds = 2F D63F；下一 db = 3F D640。
# tests/data/player-battle-source-fixture.json / files[ram/wram.asm].text
# source SHA256 00683cd430a9ef30794d2aeaee51f3a5440e4bb14dca13e9f9cb5fa88f130e34
SCRIPT_ADDRESSES={194:0xD63F,198:0xD640}
OWNED_CASE_MAP={'2f_switch1':194,'2f_switch2':194,'3f_switch1':198,'3f_hole':198}
OWNED_KIND='owned_later_boulder_hyper_v1'


def _int(value,lo=0,hi=2**63-1):return type(value) is int and lo<=value<=hi
def _clock(value):return type(value) in (int,float) and math.isfinite(value) and value>=0


def _owned_intent(intent):
    return (type(intent) is dict and set(intent)==set(('kind','map_id','target','item','quantity',
            'target_species','owner_step_id','case_key','capsule_sha256'))
        and intent['kind']==OWNED_KIND and type(intent['map_id']) is int
        and type(intent['case_key']) is str and OWNED_CASE_MAP.get(intent['case_key'])==intent['map_id']
        and type(intent['target']) is list and len(intent['target'])==2
        and _int(intent['target'][0],0,29) and _int(intent['target'][1],0,17)
        and type(intent['item']) is int and intent['item']==18
        and type(intent['quantity']) is int and intent['quantity']==1
        and type(intent['target_species']) is int and intent['target_species'] in ui.ROSTER
        and type(intent['owner_step_id']) is str
        and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',intent['owner_step_id']) is not None
        and type(intent['capsule_sha256']) is str and re.fullmatch(r'[0-9a-f]{64}',intent['capsule_sha256']) is not None)


def _intent(intent):return any(ui._exact(intent,x) for x in INTENTS) or _owned_intent(intent)


def _location(intent):
    if not _intent(intent):return None
    return dict(map_id=intent['map_id'],x=intent['target'][0],y=intent['target'][1])


def _authority(intent,authority):
    if not _owned_intent(intent):return authority is None
    return ui._exact(authority,dict(owner_step_id=intent['owner_step_id'],case_key=intent['case_key'],
        capsule_sha256=intent['capsule_sha256'],location=_location(intent)))


def read_observation(pyboy,frame,constants,*,map_id=194):
    """真 SDK／progress／movement reader，同 frame 雙讀，不讀 ROM。"""
    def invalid(reason):return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,read_valid=False,
        read_error=reason,observation_frame=frame)
    if not _int(frame):return invalid('frame_invalid')
    if type(map_id) is not int or map_id not in SCRIPT_ADDRESSES:return invalid('source_map_unverified')
    addresses=dict(ADDRESSES,script=SCRIPT_ADDRESSES[map_id])
    try:
        if (getattr(constants,'OBTAINED_BADGES_ADDRESS',None)!=0xD356
                or type(getattr(constants,'OBTAINED_BADGES_ADDRESS',None)) is not int
                or getattr(constants,'STATUS_FLAGS3_ADDRESS',None)!=0xD72D
                or type(getattr(constants,'STATUS_FLAGS3_ADDRESS',None)) is not int
                or type(constants.MAPS.get('victory_road_2f')) is not int
                or constants.MAPS['victory_road_2f']!=194
                or map_id==198 and (type(constants.MAPS.get('victory_road_3f')) is not int
                    or constants.MAPS['victory_road_3f']!=198)):return invalid('sdk_anchors_unverified')
        before=pyboy.frame_count
        if not _int(before) or before!=frame:return invalid('frame_not_current')
        first={k:pyboy.memory[a] for k,a in addresses.items()}
        p=progress_reader.read_progress(pyboy,constants)
        movement=rocket_movement.read_rocket_movement(pyboy,observation_frame=frame)
        second={k:pyboy.memory[a] for k,a in addresses.items()};after=pyboy.frame_count
    except Exception:return invalid('getter_failed')
    if any(not _int(v,0,255) for values in (first,second) for v in values.values()):return invalid('byte_invalid')
    if not _int(after) or after!=frame or first!=second:return invalid('torn_frame_or_snapshot')
    return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,read_valid=True,read_error=None,
        observation_frame=frame,frame_before=before,frame_after=after,owner_id=id(pyboy),
        values=first,progress=p,movement=movement,source_map_id=map_id,script_address=addresses['script'])


def _closed_world(text,grid,frame,location=LOCATION):
    if (type(location) is not dict or set(location)!=set(('map_id','x','y'))
            or type(location['map_id']) is not int or location['map_id'] not in SCRIPT_ADDRESSES
            or not _int(location['x'],0,29) or not _int(location['y'],0,17)):return False
    x,y=location['x'],location['y']
    if (type(text) is not dict or text.get('profile')!=ui.TEXT_PROFILE or text.get('window_visible') is not False
            or text.get('cells')!=[[' ']*20 for _ in range(18)] or text.get('lines')!=[] or text.get('line_rows')!=[]):return False
    full=text.get('read_valid') is True and text.get('alignment_verified') is True and text.get('read_error') is None
    silhouette=(text.get('read_valid') is False and text.get('alignment_verified') is False
        and text.get('read_error')=='visible_tile_alignment_incomplete')
    if not (full or silhouette):return False
    if (type(grid) is not dict or grid.get('source')!='wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM'
            or not ui._exact(grid.get('verified_location'),[location['map_id'],x,y]) or not _int(grid.get('observation_frame')) or grid['observation_frame']!=frame
            or not _int(grid.get('screen_cells_verified'),12,360)):return False
    cells=grid.get('visible_verified_cells')
    if (type(cells) is not list or len(cells)!=grid['screen_cells_verified']
            or any(type(p) is not list or len(p)!=2 or any(not _int(v,0,255) for v in p) for p in cells)
            or len(set(map(tuple,cells)))!=len(cells) or [x,y] not in cells):return False
    try:return type(grid['walkable'][y][x]) is int and grid['walkable'][y][x]==1
    except (KeyError,IndexError,TypeError):return False


class _Views:
    _start=hm.HMTeachingController._start
    _bag=hm.HMTeachingController._bag
    _use=hm.HMTeachingController._use
    def __init__(self,name,items,offset=0,cursor=0):
        self.player_name=name;self.inventory=[(x['item'],x['quantity']) for x in items]
        self.bag_offset=offset;self.bag_cursor=cursor


class OverworldHyperController:
    def __init__(self,intent,*,owner,owned_authority=None):
        if not _intent(intent) or owner is None or not _authority(intent,owned_authority):
            raise ValueError('固定單次 Hyper Potion／原 owner 與 owned authority 必填')
        self.intent=deepcopy(intent);self.contract=deepcopy(intent);self.owner=owner
        self.owned_authority=deepcopy(owned_authority)
        self.stage='initial';self.error=None;self.complete=False
        self.calls=self.waits=0;self.started=self.last_now=self.last_frame=self.packet=None
        self.baseline=self.after=self.target_index=self.items=self.after_items=None
        self.pending=None;self.expected=None;self.bag_offset=self.bag_cursor=None
        self.receipt_full_frame=None;self.receipt_ack=False;self.effect_selected=False;self.closed_frame=None
        self.name=None;self.player_name=None;self.receipt=None

    def _hint(self,action,reason,**extra):
        meta=dict(overworld_hyper_profile=PROFILE,source_commit=SOURCE_COMMIT,
            overworld_hyper_stage=self.stage,overworld_hyper_reason=reason,
            overworld_hyper_calls=self.calls,overworld_hyper_elapsed_seconds=0 if self.started is None else self.last_now-self.started,
            candidate_only=True,**extra)
        if action=='wait':return dict(phase='overworld_medicine_wait',objective='Wait.',available_actions=['wait'],**meta)
        return hm.command(action,'item_menu',meta)

    def _fail(self,reason):
        if self.error is None:self.error=reason
        return dict(self._hint('wait','review'),phase='campaign_review',review_reason='overworld_hyper_'+self.error)

    def _wait(self,reason,*,count=True):
        if count:self.waits+=1
        if self.waits>MAX_WAITS:return self._fail('wait_budget_exhausted')
        return self._hint('wait',reason)

    def _offer(self,action,next_stage,reason,expected=None):
        self.pending=dict(action=action,frame=self.last_frame,receipt_ack=reason=='ack_source_done_once')
        self.stage=next_stage;self.expected=expected
        return self._hint(action,reason)

    def _resources(self,p):
        party=ui._party(p);items=ui._inventory(p.get('inventory')) if type(p) is dict else None
        if (party is None or len(party)!=6 or len({m['species'] for m in party})!=6 or {m['species'] for m in party}!=ui.ROSTER
                or any(m['hp']<=0 or type(m['status']) is not int or m['status']!=0 for m in party)
                or items is None or not _int(p.get('money'),0,999999)
                or type(p.get('player_name_raw')) is not str or re.fullmatch(r'[A-Z]{1,7}',p['player_name_raw']) is None
                or any(ui._name(i['item']) in (None,'?????') for i in items)):return 'resources_or_fnt_status_unverified'
        ref=reference()
        if ref.get('source_commit')!=SOURCE_COMMIT:return 'reference_source_unverified'
        for mon in party:
            for move,pp in zip(mon['moves'],mon['pp']):
                key=move_key(move) if move else None
                if move and (key is None or (pp&63)>ref['moves'][key]['pp']*(5+(pp>>6))//5):return 'party_pp_unverified'
        if self.baseline is None:
            targets=[i for i,m in enumerate(party) if m['species']==self.contract['target_species']]
            if len(targets)!=1:return 'unique_target_required'
            target=party[targets[0]]
            if target['hp']==target['max_hp']:return 'full_hp_no_waste'
            if not any(i['item']==18 for i in items):return 'hyper_potion_missing'
            self.target_index=targets[0];self.name=target['species_name'];self.player_name=p['player_name_raw']
            self.baseline=deepcopy(p);self.items=deepcopy(items);self.after=deepcopy(p)
            self.after['party'][self.target_index]['hp']=min(target['hp']+200,target['max_hp'])
            for i,item in enumerate(self.after['inventory']):
                if item['item']==18:
                    item['quantity']-=1
                    if item['quantity']==0:self.after['inventory'].pop(i)
                    break
            self.after_items=deepcopy(self.after['inventory'])
        if self.stage not in ('effect','closing_bag','closing_start','world','complete'):
            return None if ui._exact(p,self.baseline) else 'premature_or_unrelated_resource_change'
        if self.stage=='effect' and not self.effect_selected:return 'actual_target_a_required'
        if self.stage=='effect' and ui._exact(p,self.baseline):return None
        return None if ui._exact(p,self.after) else 'unexpected_effect_or_resource_change'

    def _views(self,items):
        views=[];v=_Views(self.player_name,items,self.bag_offset or 0,self.bag_cursor or 0)
        for y in (2,4,6,8,10,12,14):
            for marker in ('▶','▷'):
                c=v._start(y);c[y][11]=marker;views.append(('start',(y,marker),hm._serial(c)))
        for off in range(max(1,len(items))):
            for cur in range(min(3,len(items)-off+1)):
                if off+cur>len(items):continue
                for marker in ('▶','▷'):
                    c=v._bag(off,cur,marker);views.append(('bag',(off,cur,marker),hm._serial(c)))
                    if off+3<len(items):c[11][18]='▼';views.append(('bag',(off,cur,marker),hm._serial(c)))
        if self.bag_offset is not None:
            for y in (11,13):
                for marker in ('▶','▷'):views.append(('use',(y,marker),hm._serial(v._use(y,marker))))
        return views

    def _cursor(self,kind,value):
        if self.expected is None:return None
        expected_kind,old,new=self.expected
        if kind!=expected_kind:return self._fail('cursor_menu_changed')
        if value==old:return self._wait('actual_cursor_motion_pending')
        if value!=new:return self._fail('cursor_did_not_follow_actual_offer')
        self.expected=None;return None

    def context(self,state,*,text,grid,signal,previous,owner,now):
        if self.error is not None:return self._fail(self.error)
        location=_location(self.contract)
        frame=state.get('frame') if type(state) is dict else None
        if (owner is not self.owner or not ui._exact(self.intent,self.contract) or location is None
                or not _authority(self.contract,getattr(self,'owned_authority',None)) or not _int(frame) or not _clock(now)
                or type(previous) not in (list,tuple) or any(type(a) is not str or a not in ui._ACTIONS for a in previous)):
            return self._fail('owner_intent_frame_clock_or_previous_unverified')
        if self.last_frame is not None and (frame<self.last_frame or now<self.last_now):return self._fail('frame_or_clock_regressed')
        if self.last_frame is not None and not math.isclose(now-self.last_now,(frame-self.last_frame)/60,rel_tol=1e-9,abs_tol=1e-9):return self._fail('true_frame_clock_required')
        if (type(signal) is not dict or signal.get('profile')!=PROFILE or signal.get('source_commit')!=SOURCE_COMMIT
                or signal.get('read_valid') is not True or signal.get('read_error') is not None
                or type(signal.get('owner_id')) is not int or signal['owner_id']!=id(owner)
                or any(not _int(signal.get(k)) or signal[k]!=frame for k in ('observation_frame','frame_before','frame_after'))):return self._fail('same_frame_reader_unverified')
        if (_owned_intent(self.contract) and (type(signal.get('source_map_id')) is not int
                or signal['source_map_id']!=location['map_id'] or type(signal.get('script_address')) is not int
                or signal['script_address']!=SCRIPT_ADDRESSES[location['map_id']])):
            return self._fail('owned_script_reader_unverified')
        values=signal.get('values');movement=signal.get('movement');p=state.get('progress');battle=state.get('battle_state')
        if (not ui._exact(state.get('location'),location) or not ui._exact(p,signal.get('progress')) or type(values) is not dict
                or any(not _int(values.get(k),0,255) for k in ADDRESSES)
                or {k:values[k] for k in location}!=location or values['raw']!=0 or values['battle_type']!=0
                or values['badges']!=255 or values['mode']!=0 or values['status5']&1 or values['script']!=0
                or type(battle) is not dict or type(battle.get('raw')) is not int or battle['raw']!=0
                or battle.get('kind')!='none' or battle.get('active') is not False or battle.get('observation_frame')!=frame
                or type(battle.get('observation_frame')) is not int):return self._fail('fixed_nonbattle_location_unverified')
        if (type(movement) is not dict or movement.get('read_valid') is not True or movement.get('read_error') is not None
                or movement.get('profile')!=rocket_movement.MOVEMENT_PROFILE or movement.get('source_commit')!=SOURCE_COMMIT
                or type(movement.get('observation_frame')) is not int or movement['observation_frame']!=frame
                or movement.get('spinning') is not False or any(type(movement.get(k)) is not int or movement[k]!=0 for k in ('simulated_remaining','joy_ignore','walk_counter'))
                or type(movement.get('movement_flags')) is not int or movement['movement_flags']!=0):return self._fail('native_movement_not_idle')
        for packet in (p,text):
            if type(packet) is not dict:return self._fail('original_packets_required')
            if 'observation_frame' in packet and (not _int(packet['observation_frame']) or packet['observation_frame']!=frame):return self._fail('packet_frame_disagrees')
        packet=deepcopy((state,text,grid,signal))
        if frame==self.last_frame:
            if not ui._exact(packet,self.packet):return self._fail('same_frame_packet_conflict')
            return self._wait('same_frame_no_resend',count=False)
        if self.started is None:self.started=now
        self.last_frame,self.last_now,self.packet=frame,now,packet;self.calls+=1
        if self.calls>MAX_CALLS or now-self.started>MAX_SECONDS:return self._fail('call_or_time_budget_exhausted')
        if self.pending is not None:
            if not previous or previous[-1]!=self.pending['action']:return self._fail('actual_pending_ack_required')
            if self.pending['receipt_ack']:self.receipt_ack=True
            if self.stage=='effect' and self.pending['action']=='a':self.effect_selected=True
            self.pending=None
        error=self._resources(p)
        if error:return self._fail(error)
        world=_closed_world(text,grid,frame,location)
        rows=hm._rows(text)
        if self.stage=='initial':
            if not world:return self._fail('initial_closed_world_required')
            return self._offer('start','start','open_normal_start')
        if self.stage in ('world','complete') and world:
            if not self.receipt_ack:return self._fail('actual_receipt_ack_required')
            if self.closed_frame is None:self.closed_frame=frame;return self._wait('first_closed_world_frame')
            if frame<=self.closed_frame:return self._wait('second_fresh_world_required',count=False)
            self.complete=True;self.stage='complete'
            self.receipt=dict(item=18,quantity=1,target_species=self.contract['target_species'],target_index=self.target_index,
                hp_before=self.baseline['party'][self.target_index]['hp'],hp_after=self.after['party'][self.target_index]['hp'],closed_frame=frame)
            return self._hint('wait','closed_two_fresh_world',overworld_medicine_complete=True,medicine_receipt=deepcopy(self.receipt))
        if rows is None:return self._fail('native_text_unverified')
        if world:return self._fail('world_before_transaction_closed')
        if rows==(' '*20,)*18:return self._wait('bounded_source_transition_blank')
        items=self.after_items if self.stage in ('closing_bag','closing_start','world','complete') else self.items
        if self.stage=='effect':return self._effect(rows,p,frame)
        party_views=[('party',(i,marker),ui._party_view(p['party'],i,marker)) for i in range(6) for marker in ('▶','▷')]
        views=self._views(items)+(party_views if self.stage=='party' else [])
        matches=[(kind,key) for kind,key,view in views if rows==view]
        if len(matches)!=1:
            return self._wait('known_source_partial_no_input') if not matches and any(ui._partial(rows,v) for k,key,v in views) else self._fail('unknown_or_ambiguous_source_page')
        kind,key=matches[0]
        if kind=='start':
            y,marker=key
            if marker!='▶':return self._wait('inactive_start_cursor')
            if self.stage=='closing_start':
                if y!=6:return self._fail('closing_start_cursor_changed')
                return self._offer('b','world','close_start')
            if self.stage=='bag':return self._wait('bag_open_pending')
            if self.stage!='start':return self._fail('unexpected_start_page')
            pending=self._cursor('start',y)
            if pending:return pending
            if y==6:return self._offer('a','bag','select_normal_item_menu')
            return self._offer('down' if y<6 else 'up','start','navigate_start_item',('start',y,y+(2 if y<6 else -2)))
        if kind=='bag':
            off,cur,marker=key
            if marker!='▶':return self._wait('inactive_bag_cursor')
            if self.stage=='closing_bag':
                if not self.receipt_ack:return self._fail('actual_receipt_ack_required')
                return self._offer('b','closing_start','close_verified_after_bag')
            if self.stage=='use':return self._wait('use_menu_pending')
            if self.stage!='bag':return self._fail('unexpected_bag_page')
            current=off+cur;pending=self._cursor('bag',current)
            if pending:return pending
            wanted=next(i for i,item in enumerate(self.items) if item['item']==18)
            if current==wanted:
                self.bag_offset,self.bag_cursor=off,cur
                return self._offer('a','use','select_exact_hyper_potion')
            return self._offer('down' if current<wanted else 'up','bag','navigate_actual_hyper',('bag',current,current+(1 if current<wanted else -1)))
        if kind=='use':
            y,marker=key
            if marker!='▶':return self._wait('inactive_use_cursor')
            if self.stage=='party':return self._wait('party_open_pending')
            if self.stage!='use':return self._fail('unexpected_use_toss_page')
            pending=self._cursor('use',y)
            if pending:return pending
            if y==13:return self._offer('up','use','never_confirm_toss',('use',13,11))
            return self._offer('a','party','confirm_use_only')
        if kind=='party':
            index,marker=key
            if marker!='▶':return self._wait('inactive_party_cursor')
            pending=self._cursor('party',index)
            if pending:return pending
            if index==self.target_index:return self._offer('a','effect','apply_once_to_exact_species')
            return self._offer('down' if index<self.target_index else 'up','party','navigate_exact_target',('party',index,index+(1 if index<self.target_index else -1)))
        return self._fail('unexpected_source_page')

    def _effect(self,rows,p,frame):
        after=self.after['party'];old=self.baseline['party'];delta=after[self.target_index]['hp']-old[self.target_index]['hp']
        full=ui._party_view(after,receipt=(self.name,f'RECOVERED BY {delta}!'))
        if rows==full:
            if not ui._exact(p,self.after):return self._fail('done_without_exact_hp_and_item_consumption')
            if self.receipt_full_frame is None:self.receipt_full_frame=frame
            if frame-self.receipt_full_frame<54:return self._wait('source_done_delay50_plus_redraw')
            return self._offer('a','closing_bag','ack_source_done_once')
        self.receipt_full_frame=None
        if ui._exact(p,self.baseline) and rows==ui._party_view(old,self.target_index,'▶'):
            return self._wait('actual_use_input_native_processing')
        for party in (old,after):
            expected=ui._party_view(party,self.target_index,'▷')
            if ui._partial(rows,expected) or ui._partial(rows,full):return self._wait('source_effect_partial_no_input')
        if ui._exact(p,self.after):
            expected=list(ui._party_view(after,self.target_index,'▷'));y=self.target_index*2+1;token=rows[y][13:16]
            if re.fullmatch(r' {0,2}[0-9]{1,3}',token):
                value=int(token)
                if old[self.target_index]['hp']<=value<=after[self.target_index]['hp'] and token==f'{value:3}':
                    expected[y]=expected[y][:13]+token+expected[y][16:]
                    if rows[:12]==tuple(expected[:12]) and (ui._partial(rows[12:],tuple(expected[12:])) or ui._partial(rows[12:],full[12:])):
                        return self._wait('native_hp_animation_no_input')
        return self._fail('medicine_effect_page_unverified')
