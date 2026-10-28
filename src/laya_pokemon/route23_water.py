"""Route23來源固定水路：保留真實水步、徽章對話與野戰owner；尚未實機校準。

只回傳Laya子目標，不執行按鍵／tick／RAM寫入。未知頁或NPC/腳本停檢。
caller必須先執行既有戰敗／健康守門，並序列化所有同幀getter。
"""
from copy import deepcopy
import math

from .mart_purchase import _inventory, _party
from . import route23_surf as surf

SOURCE_COMMIT = surf.SOURCE_COMMIT
INTENT = {'kind':'route23_water','start':[34,10,103],'goal':[34,8,71],
          'path_id':'route23-source-water-north-v1','surf_user':19}
PATH = (tuple((34,10,y,2,0x32 if y in (91,90) else 0x14) for y in range(103,83,-1))
        + tuple((34,x,84,2,0x14) for x in (9,8,7))
        + tuple((34,7,y,2,0x14) for y in range(83,71,-1))
        + ((34,8,72,2,0x14),(34,8,71,0,0x2c)))
GUARDS = {(10,96):(3,'SOULBADGE'),(10,85):(4,'MARSHBADGE')}
MAX_STEP_SECONDS,MAX_STEP_WAITS,MAX_SECONDS,MAX_CALLS=60,30,900,1500


def _int(v,lo=0,hi=2**63-1): return type(v) is int and lo<=v<=hi


def _intent(v):
    return (type(v) is dict and v==INTENT and set(v)==set(INTENT)
            and all(type(v[k]) is list and all(type(n) is int for n in v[k]) for k in ('start','goal'))
            and type(v['surf_user']) is int)


def _position(v):
    return tuple(v[k] for k in ('map_id','x','y')) if isinstance(v,dict) and all(_int(v.get(k),0,255) for k in ('map_id','x','y')) else None


def _direction(a,b):
    return {(0,-1):'up',(0,1):'down',(-1,0):'left',(1,0):'right'}.get((b[1]-a[1],b[2]-a[2])) if a[0]==b[0] else None


def _fingerprint(progress):
    party=_party(progress);bag=_inventory(progress.get('inventory')) if isinstance(progress,dict) else None
    if (party is None or [m['species'] for m in party]!=[19,132,102,154,35,7]
            or any(m['hp']<=0 for m in party) or bag is None or not _int(progress.get('money'),0,999999)
            or type(progress.get('badges_raw')) is not int or progress['badges_raw']!=255
            or progress.get('player_name_raw')!='KEVIN'): return None
    return deepcopy((party,bag,progress['money'],progress['badges_raw'],progress['player_name_raw']))


def _battle_rebase(before,after):
    # 真野戰只開放HP/PP/EXP/level/stat-derived maxHP的變化；捕捉、學招、耗藥需caller另行停檢。
    if before is None or after is None or before[1:]!=after[1:]: return False
    for a,b in zip(before[0],after[0]):
        if (any(a[k]!=b[k] for k in ('species','species_name','moves')) or b['exp']<a['exp']
                or b['level']<a['level'] or b['max_hp']<a['max_hp']
                or any(np>op for np,op in zip(b['pp'],a['pp']))): return False
    return True


def _blank(text): return surf._rows(text)==surf._blank() and text.get('window_visible') is False


def _grid(grid,node,frame,next_node=None):
    if (not isinstance(grid,dict) or type(grid.get('tileset_id')) is not int or grid['tileset_id']!=23
            or type(grid.get('observation_frame')) is not int or grid['observation_frame']!=frame
            or type(grid.get('verified_location')) is not list or any(type(v) is not int for v in grid['verified_location'])
            or grid['verified_location']!=list(node[:3])): return False
    for key,high in (('tiles',255),('walkable',1)):
        matrix=grid.get(key)
        if (type(matrix) is not list or len(matrix)!=144 or any(type(row) is not list or len(row)!=20
                or any(not _int(v,0,high) for v in row) for row in matrix)): return False
    cells=grid.get('visible_verified_cells')
    if (type(cells) is not list or not _int(grid.get('screen_cells_verified'),12,90)
            or len(cells)!=grid['screen_cells_verified'] or any(type(c) is not list or len(c)!=2
                or not _int(c[0],0,19) or not _int(c[1],0,143) for c in cells)): return False
    visible={tuple(c) for c in cells}
    required=[node]+([next_node] if next_node is not None else [])
    return len(visible)==len(cells) and all((n[1],n[2]) in visible
        and grid['tiles'][n[2]][n[1]]==n[4] and grid['walkable'][n[2]][n[1]]==int(n[3]==0) for n in required)


def _guard_page(rows,badge,page):
    pairs=(('YOU CAN PASS HERE','ONLY IF YOU HAVE'),('ONLY IF YOU HAVE','THE '+badge+'!'),
           ('OH! THAT IS THE',badge+'!'),('OK THEN! PLEASE,','GO RIGHT AHEAD!'))
    a,b=pairs[page]
    clean=list(rows);one=clean[14][1:19].rstrip();two=clean[16][1:18].rstrip();mark=clean[16][18]
    clean[14]=clean[16]=' '*20
    if tuple(clean)!=surf._blank() or rows[14][0]!=' ' or rows[14][19]!=' ' or rows[16][0]!=' ' or rows[16][19]!=' ' or mark not in (' ','▼'):
        return None
    # 每個來源行完整後才允許下一行開始，不把任意substring當原生頁。
    if not a.startswith(one) or two and (one!=a or not b.startswith(two)): return None
    full=one==a and two==b
    return {'full':full,'arrow':mark=='▼'} if not mark.strip() or full else None


class Route23WaterController:
    def __init__(self,intent=INTENT):
        if not _intent(intent): raise ValueError('僅允許Route23固定北行水路與Lapras19')
        self.intent,self.contract=deepcopy(intent),deepcopy(intent)
        self.index=0;self.pending=None;self.error=None;self.stage='initial'
        self.started=self.step_started=self.last_now=None;self.last_frame=-1;self.last_packet=None
        self.calls=self.waits=0;self.excluded=self.step_excluded=0.;self.last_active=False
        self.fingerprint=None;self.flags=None;self.in_battle=False;self.return_frame=None
        self.guard=None;self.goal_frames=[]

    def _hint(self,action,tactic,complete=False,handoff=False):
        return dict(phase='overworld',objective='Wait.' if action=='wait' else ('Confirm the current selection.' if action=='a' else f'Move {action.upper()}.'),
                    available_actions=['wait'] if action=='wait' else [action,'wait'],controller_menu_verified=action!='wait',
                    route23_water_complete=complete,route23_water_index=self.index,route23_water_stage=self.stage,
                    route23_water_tactic=tactic,route23_water_battle_handoff=handoff,source_commit=SOURCE_COMMIT)

    def _fail(self,reason):
        self.error=self.error or 'route23_water_'+reason
        return {**self._hint('wait','review'),'phase':'campaign_review','review_reason':self.error}

    def _wait(self,reason,handoff=False):
        self.waits+=1
        return self._fail('step_wait_budget_exhausted') if self.waits>MAX_STEP_WAITS else self._hint('wait',reason,handoff=handoff)

    def _advance(self,now):
        self.index+=1;self.pending=None;self.step_started=now;self.step_excluded=0.;self.waits=0;self.goal_frames=[]

    def _offer(self,frame):
        action=_direction(PATH[self.index],PATH[self.index+1])
        self.pending={'frame':frame,'action':action,'from':self.index,'to':self.index+1,'executed':False}
        self.stage='walking'
        return self._hint(action,'verified_next_source_cell')

    def _guard_event_order(self,rows,text,signal,g):
        """PrintText(done) returns before own bit/script2; outer text display still needs A."""
        expected=self.flags|(1<<g['bit']);flags=signal['guard_flags']
        if flags not in (self.flags,expected):return self._fail('guard_foreign_event_changed')
        if g.get('event_seen') is True and flags!=expected:return self._fail('guard_own_event_regressed')
        pending=g.get('pending')
        entered_done=(g['page']==3 or g['page']==2 and pending is not None and pending.get('executed') is True)
        done=_guard_page(rows,g['badge'],3) if text.get('window_visible') is True else None
        if flags==expected:
            if not entered_done or done is None or done['arrow']:
                return self._fail('guard_event_before_source_done_page')
            g['event_seen']=True
        if signal['route23_script']==2:
            if flags!=expected or not entered_done or done is None or done['arrow']:
                return self._fail('guard_reset_before_source_done_event')
            g['script2_seen']=True
        return None

    def _guard_context(self,text,signal,previous,frame,now):
        g=self.guard;rows=surf._rows(text)
        if rows is None or text.get('window_visible') is not True:return self._fail('guard_decoder_or_window_unverified')
        if g['pending'] is not None:
            p=g['pending']
            if not p['executed']:
                if frame>p['frame'] and previous and previous[-1]=='a':p['executed']=True
                elif rows==p['rows']:
                    order_error=self._guard_event_order(rows,text,signal,g)
                    if order_error is not None:return order_error
                    return self._hint('a','retry_unexecuted_guard_candidate')
                else:return self._fail('guard_page_changed_without_actual_a')
            order_error=self._guard_event_order(rows,text,signal,g)
            if order_error is not None:return order_error
            if rows==p['rows'] or _guard_page(rows,g['badge'],g['page']) is not None:
                return self._wait('await_native_guard_page_after_actual_a')
            g['page']+=1;g['pending']=None;g['done_frame']=None
        order_error=self._guard_event_order(rows,text,signal,g)
        if order_error is not None:return order_error
        if g['page']>3:return self._fail('guard_unknown_extra_page')
        page=_guard_page(rows,g['badge'],g['page'])
        if page is None:return self._fail('unknown_or_polluted_guard_page')
        if not page['full']:g['done_frame']=None;return self._wait('known_guard_printing')
        if g['page']<3:
            if not page['arrow']:return self._wait('guard_prompt_arrow_blink')
        else:
            if page['arrow']:return self._fail('guard_done_unexpected_prompt_arrow')
            if g['done_frame'] is None:g['done_frame']=frame;return self._wait('first_full_guard_done_frame')
        g['pending']={'frame':frame,'rows':rows,'executed':False}
        return self._hint('a','verified_source_guard_page')

    def context(self,state,*,grid,signal,movement,previous,now):
        if self.error:return self._fail('sticky')
        frame=state.get('frame') if isinstance(state,dict) else None
        if (not _intent(self.intent) or self.intent!=self.contract or not _int(frame) or frame<self.last_frame
                or type(now) not in (int,float) or not math.isfinite(now) or now<0
                or self.last_now is not None and now<self.last_now):return self._fail('intent_clock_or_frame_unverified')
        self.calls+=1
        if self.calls>MAX_CALLS:return self._fail('whole_call_budget_exhausted')
        pos=_position(state.get('location'));battle=state.get('battle_state');text=state.get('text')
        if (pos is None or pos[0]!=34 or not isinstance(battle,dict) or type(battle.get('raw')) is not int
                or type(battle.get('observation_frame')) is not int or battle['observation_frame']!=frame):return self._fail('location_or_battle_unverified')
        active=battle['raw']==1 and battle.get('active') is True and battle.get('kind')=='wild'
        none=battle['raw']==0 and battle.get('active') is False and battle.get('kind')=='none'
        if not(active or none):return self._fail('only_verified_wild_or_none_supported')
        if (not isinstance(signal,dict) or signal.get('profile')!=surf.PROFILE or signal.get('source_commit')!=SOURCE_COMMIT
                or signal.get('read_valid') is not True or signal.get('read_error') is not None
                or type(signal.get('observation_frame')) is not int or signal['observation_frame']!=frame
                or _position(signal.get('location'))!=pos or type(signal.get('mode')) is not int or signal['mode'] not in (0,2)
                or type(signal.get('battle_raw')) is not int or signal['battle_raw']!=battle['raw']
                or type(signal.get('badges_raw')) is not int or signal['badges_raw']!=255
                or type(signal.get('guard_flags')) is not int or not 0<=signal['guard_flags']<128
                or signal['guard_flags']&7!=7 or type(signal.get('route23_script')) is not int
                or signal['route23_script'] not in (0,2)
                or not surf._npc_source(signal.get('npc_positions'))):return self._fail('route23_source_signal_unverified')
        for packet in (state.get('location'),state.get('progress'),text,grid,movement):
            if isinstance(packet,dict) and 'observation_frame' in packet and (type(packet['observation_frame']) is not int or packet['observation_frame']!=frame):return self._fail('packet_frame_conflict')
        if type(previous) not in (list,tuple) or any(type(a) is not str or a not in ('up','down','left','right','a','b','start','wait') for a in previous):return self._fail('actual_previous_unverified')
        packet=deepcopy((state,grid,signal,movement,previous));same=frame==self.last_frame
        if same and packet!=self.last_packet:return self._fail('same_frame_conflict')
        if self.started is not None:
            if frame>self.last_frame and self.last_active and active:
                delta=now-self.last_now;self.excluded+=delta;self.step_excluded+=delta
            if now-self.started-self.excluded>MAX_SECONDS:return self._fail('whole_time_budget_exhausted')
            if now-self.step_started-self.step_excluded>MAX_STEP_SECONDS:return self._fail('step_time_budget_exhausted')
        was_active=self.last_active;self.last_now,self.last_active=now,active
        if same:return self._hint('wait','same_frame_no_action',handoff=self.in_battle and active)
        self.last_frame,self.last_packet=frame,packet
        current=PATH[self.index];mode=signal['mode']
        if self.stage=='initial':
            fp=_fingerprint(state.get('progress'))
            if (pos!=PATH[0][:3] or mode!=2 or active or fp is None or any(m['status']!=0 for m in fp[0])
                    or fp[0][0]['hp']*3<=fp[0][0]['max_hp']*2 or signal['route23_script']!=0
                    or not _blank(text) or surf._idle(movement,frame) is not True or not _grid(grid,current,frame,PATH[1])):return self._fail('initial_health_or_closed_water_unverified')
            self.fingerprint=fp;self.flags=signal['guard_flags'];self.started=self.step_started=now
            return self._offer(frame)
        target=PATH[self.pending['to']] if self.pending else current
        if self.pending and not self.pending['executed']:
            # 只由送出水步後首次none/野戰入口ACK；後續戰鬥同方向鍵不能補假收據。
            if not self.in_battle and not was_active and previous and previous[-1]==self.pending['action']:
                self.pending['executed']=True
        if pos not in (current[:3],target[:3]):return self._fail('unexpected_step_position')
        if active:
            if self.guard:return self._fail('wild_during_badge_script')
            if signal['guard_flags']!=self.flags or signal['route23_script']!=0:return self._fail('wild_source_state_changed')
            if not self.in_battle:
                if self.pending is None or not self.pending['executed'] or pos!=target[:3] or mode!=2:return self._fail('wild_without_actual_water_step_receipt')
                self.in_battle=True;self.stage='battle'
            elif pos!=target[:3] or mode!=2:return self._fail('wild_position_or_mode_changed')
            return self._hint('wait','delegate_existing_wild',handoff=True)
        if self.in_battle:
            if pos!=target[:3] or mode!=2 or signal['guard_flags']!=self.flags or signal['route23_script']!=0:return self._fail('wild_return_location_mode_or_flags_changed')
            if not _blank(text) or surf._idle(movement,frame) is not True or not _grid(grid,target,frame):
                self.return_frame=None;return self._wait('await_existing_wild_tail_and_world',handoff=True)
            after=_fingerprint(state.get('progress'))
            if not _battle_rebase(self.fingerprint,after):return self._fail('wild_return_progress_needs_review')
            if self.return_frame is None:self.return_frame=frame;return self._wait('first_closed_wild_return_frame')
            self.fingerprint=after;self.in_battle=False;self.return_frame=None;self.stage='walking'
        fp=_fingerprint(state.get('progress'))
        if fp is None or fp!=self.fingerprint:return self._fail('nonbattle_party_inventory_or_money_changed')
        if self.guard:
            g=self.guard;last=g.get('pending');expected=self.flags|(1<<g['bit'])
            # PrintText(done)返回先設bit/script2；外層DisplayTextID終頁仍等真A。
            # 事件提前不是閉合；同原guard/water pending，真A後兩fresh world才前進。
            if signal['guard_flags'] not in (self.flags,expected):return self._fail('guard_foreign_event_changed')
            if g.get('event_seen') is True and signal['guard_flags']!=expected:return self._fail('guard_own_event_regressed')
            if last and g['page']==3 and not last['executed'] and previous and previous[-1]=='a' and frame>last['frame']:last['executed']=True
            if signal['guard_flags']==expected and last and g['page']==3 and last['executed']:
                if pos!=target[:3] or mode!=2:return self._fail('guard_exit_position_or_mode_changed')
                rows=surf._rows(text)
                done=_guard_page(rows,g['badge'],3) if rows is not None and rows!=surf._blank() else None
                if rows is None or rows!=surf._blank() and (done is None or done['arrow']):
                    return self._fail('guard_unknown_page_after_final_actual_a')
                g['event_seen']=True
                if signal['route23_script']==2:g['script2_seen']=True
                if (signal['route23_script']!=0 or not _blank(text) or surf._idle(movement,frame) is not True
                        or not _grid(grid,target,frame)):
                    g['closed_frame']=None;return self._wait('native_guard_script_finishing')
                if g['closed_frame'] is None:g['closed_frame']=frame;return self._wait('first_closed_guard_frame')
                self.flags=expected;self.guard=None
            else:return self._guard_context(text,signal,previous,frame,now)
        if signal['guard_flags']!=self.flags or signal['route23_script']!=0:return self._fail('unexpected_event_or_script_change')
        if self.pending:
            expected_mode=target[3] if pos==target[:3] else current[3]
            if self.pending['executed'] and target==PATH[-1] and pos==current[:3] and mode==0:return self._wait('native_mode0_before_landfall')
            if mode!=expected_mode:return self._fail('water_step_mode_disagrees')
            if not self.pending['executed'] and pos!=current[:3]:return self._fail('water_step_without_actual_direction')
            if pos==target[:3] and (pos[1],pos[2]) in GUARDS and not self.flags&(1<<GUARDS[pos[1:]][0]):
                if not self.pending['executed'] or _blank(text):return self._wait('await_native_guard_intro')
                bit,badge=GUARDS[pos[1:]];self.guard={'bit':bit,'badge':badge,'page':0,'pending':None,'done_frame':None,'closed_frame':None}
                self.stage='guard';return self._guard_context(text,signal,previous,frame,now)
            if not _blank(text) or surf._idle(movement,frame) is not True:
                if surf._rows(text) is not None and text.get('window_visible') is True and surf._rows(text)!=surf._blank():
                    return self._fail('unexpected_native_dialogue_outside_known_guard')
                return self._wait('await_native_water_step') if self.pending['executed'] else self._fail('unarmed_world_unverified')
            node=target if pos==target[:3] else current
            if not _grid(grid,node,frame,target if node==current else None):return self._wait('await_verified_native_grid') if self.pending['executed'] else self._fail('unarmed_grid_unverified')
            if not self.pending['executed']:return self._offer(frame)
            if pos==current[:3]:return self._wait('await_actual_next_cell')
            self._advance(now);current=PATH[self.index]
        if mode!=current[3] or pos!=current[:3]:return self._fail('accepted_position_or_mode_disagrees')
        if self.index==len(PATH)-1:
            if not _blank(text) or surf._idle(movement,frame) is not True or not _grid(grid,current,frame):self.goal_frames=[];return self._wait('await_closed_landfall')
            self.goal_frames.append(frame)
            if len(self.goal_frames)<2:return self._wait('verify_second_fresh_landfall')
            self.stage='complete';return self._hint('wait','verified_route23_landfall',True)
        if not _grid(grid,current,frame,PATH[self.index+1]):return self._fail('next_source_cell_not_visible')
        return self._offer(frame)
