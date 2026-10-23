"""Route12 明確放棄卡比獸的純撤退候選；不執行按鍵、I/O或讀寫RAM。"""
from copy import deepcopy

from . import snorlax_switch as ui
from .player_battle import PROFILE as PLAYER_PROFILE

SOURCE_COMMIT = ui.SOURCE_COMMIT
INTENT = {'kind': 'escape_route12_snorlax_without_capture', 'map_id': 23, 'x': 10, 'y': 61,
          'species': 132, 'level': 30, 'acknowledge_loses_route12_snorlax': True,
          'no_attack': True, 'no_ball': True, 'no_switch': True, 'guaranteed_speed_only': True}
_PLAYER_KEYS = ('species', 'species_name', 'level', 'hp', 'max_hp', 'status', 'moves', 'pp')


def _intent(value):
    return (isinstance(value, dict) and value == INTENT and set(value) == set(INTENT)
            and all(type(value[k]) is type(v) for k, v in INTENT.items()))


def _frame(packet, frame):
    return (isinstance(packet, dict) and ('observation_frame' not in packet
            or type(packet['observation_frame']) is int and packet['observation_frame'] == frame))


def _stats(mon):
    return (isinstance(mon, dict) and all(ui._int(mon.get(k), 1, 999)
            for k in ('attack', 'defense', 'speed', 'special'))
            and isinstance(mon.get('dvs'), list) and len(mon['dvs']) == 2
            and all(ui._int(v, 0, 255) for v in mon['dvs'])
            and isinstance(mon.get('types'), list) and len(mon['types']) == 2
            and all(type(v) is int and v in {0,1,2,3,4,5,7,8,20,21,22,23,24,25,26}
                    for v in mon['types'])
            and all(isinstance(mon.get(k), list) and len(mon[k]) == 4
                    and all(ui._int(v, 0, cap) for v in mon[k])
                    for k, cap in (('moves',165),('pp',255)))
            and mon['moves'][0] != 0
            and all(m or not mon['pp'][i] and not any(mon['moves'][i+1:])
                    for i,m in enumerate(mon['moves']))
            and mon.get('pp_remaining') == [v & 63 for v in mon['pp']]
            and mon.get('pp_ups') == [v >> 6 for v in mon['pp']])


def _readers(enemy_snapshot, player_snapshot, frame, party, active):
    enemy = ui._enemy(enemy_snapshot, frame)
    if enemy is None or not _stats(enemy_snapshot.get('enemy')):
        return None
    p = player_snapshot
    if (not isinstance(p, dict) or p.get('profile') != PLAYER_PROFILE
            or p.get('source_commit') != SOURCE_COMMIT or p.get('read_valid') is not True
            or p.get('unknown_reason') is not None or p.get('battle_kind') != 'wild'
            or type(p.get('observation_frame')) is not int or p['observation_frame'] != frame
            or not ui._stance(p.get('location'),frame)
            or type(p.get('active_party_index')) is not int or p['active_party_index'] != active
            or not _stats(p.get('player'))):
        return None
    mon = p['player']; actual = party[active]
    if (any(type(mon.get(k)) is not type(actual[k]) or mon[k] != actual[k] for k in _PLAYER_KEYS)
            or type(mon.get('internal_id')) is not int or mon['internal_id'] != actual['species']
            or mon['speed'] < enemy_snapshot['enemy']['speed']):
        return None
    return deepcopy((enemy_snapshot['enemy'],mon))


def _battle(battle,frame):
    if not _frame(battle,frame):return None
    if ui._battle(battle,frame):return 'wild'
    if (type(battle.get('raw')) is int and battle['raw'] == 0 and battle.get('active') is False
            and battle.get('kind') == 'none'
            and all(battle.get(k) is None for k in ('opponent_species','wild_opponent_species'))):return 'none'
    return None


def _grid(grid,frame):
    if (not isinstance(grid,dict) or type(grid.get('observation_frame')) is not int
            or grid['observation_frame'] != frame or grid.get('verified_location') != [23,10,61]
            or not ui._int(grid.get('screen_cells_verified'),12,90)):return False
    cells=grid.get('visible_verified_cells')
    return (isinstance(cells,list) and len(cells)==grid['screen_cells_verified']
            and all(isinstance(c,list) and len(c)==2 and all(ui._int(v,0,255) for v in c) for c in cells)
            and len(set(map(tuple,cells)))==len(cells) and [10,61] in cells)


def _inactive(snapshot,profile,key,frame):
    return (snapshot is None or isinstance(snapshot,dict) and snapshot.get('profile')==profile
            and snapshot.get('source_commit')==SOURCE_COMMIT and snapshot.get('read_valid') is False
            and snapshot.get(key) is None and type(snapshot.get('observation_frame')) is int
            and snapshot['observation_frame']==frame and isinstance(snapshot.get('unknown_reason'),str))


def _native_blank(text,frame):
    if (not isinstance(text,dict) or text.get('profile')!=ui.TEXT_PROFILE
            or text.get('read_valid') is not False or text.get('alignment_verified') is not False
            or text.get('window_visible') is not True
            or text.get('read_error')!='visible_tile_alignment_incomplete' or not _frame(text,frame)):
        return False
    cells=text.get('cells')
    return (isinstance(cells,(list,tuple)) and len(cells)==18
            and all(isinstance(r,(list,tuple)) and len(r)==20 and all(c==' ' for c in r) for r in cells)
            and ('lines' not in text or text['lines']==[])
            and ('line_rows' not in text or text['line_rows']==[]))


class SnorlaxEscapeController:
    """只接受原生完整command基線與同幀兩reader；速度較慢一律拒絕。

    baseline恰含frame/now/text/progress/location/battle_state/enemy_snapshot/player_snapshot。
    context所有參數都是caller原觀測；禁止替未知HP、速度、profile或frame補值。
    """
    def __init__(self,baseline,intent,*,max_calls=120,max_seconds=60,max_waits=60):
        keys={'frame','now','text','progress','location','battle_state','enemy_snapshot','player_snapshot'}
        if (not _intent(intent) or not isinstance(baseline,dict) or set(baseline)!=keys
                or not ui._int(max_calls,1,120) or not ui._int(max_waits,1,60)
                or not ui._clock(max_seconds) or not 0<max_seconds<=60):
            raise ValueError('必須明確承認永久放棄Route12卡比獸，且不擴大60秒/120call/60wait')
        b=deepcopy(baseline);frame=b['frame'];p=b['progress']
        party=ui._party(p);rows=ui._rows(b['text'],frame);enemy=ui._enemy(b['enemy_snapshot'],frame)
        if (not ui._int(frame,0,2**63-1) or not ui._clock(b['now']) or party is None
                or rows is None or enemy is None or not ui._stance(b['location'],frame)
                or _battle(b['battle_state'],frame)!='wild' or not _frame(p,frame)
                or ui._inventory(p) is None or not ui._int(p.get('money'),0,999999)):
            raise ValueError('缺完整同步command/四人隊/背包/金錢/固定Route12野生卡比獸')
        command=ui._command(rows,party,enemy)
        readers=_readers(b['enemy_snapshot'],b['player_snapshot'],frame,party,command[0]) if command else None
        if command is None or readers is None:
            raise ValueError('必須完整HUD/Party/player-reader吻合且真實P>=E')
        self.baseline,self.intent=b,deepcopy(intent)
        self.before_party,self.before_items=deepcopy(party),ui._inventory(p)
        self.active_index,self.before_readers=command[0],readers
        self.upper=rows[:12]
        self.max_calls,self.max_seconds,self.max_waits=max_calls,max_seconds,max_waits
        self.calls=self.waits=0;self.stage='command';self.error=self.completion=None
        self.last_frame=self.last_packet=None;self.last_now=b['now']
        self.pending=None;self.run_requested=self.prompt_confirmed=False
        self.world_frame=None;self.seen_battle_none=False

    def _hint(self,action,tactic,**extra):
        objectives={'wait':'Wait.','a':'Confirm the current selection.','right':'Move RIGHT.','down':'Move DOWN.'}
        return {'phase':'snorlax_escape_menu','objective':objectives[action],
                'available_actions':['wait'] if action=='wait' else [action,'wait'],
                'controller_menu_verified':action!='wait','snorlax_escape_tactic':tactic,
                'escape_stage':self.stage,'escape_complete':False,'captured':False,
                'source_commit':SOURCE_COMMIT,**extra}

    def _fail(self,reason):
        self.error=reason
        return {**self._hint('wait','stop_for_review'),'phase':'campaign_review','review_reason':reason}

    def _wait(self,tactic):
        self.waits+=1
        return self._fail('snorlax_escape_wait_budget_exhausted') if self.waits>self.max_waits else self._hint('wait',tactic)

    def _page(self,rows):
        expected=[list(r) for r in self.upper]+[[' ']*20 for _ in range(6)]
        ui._put(expected,1,14,'GOT AWAY SAFELY!');expected[16][18]='▼'
        return ui._match(rows,tuple(''.join(r) for r in expected))

    def _command_partial(self,rows):
        for x,y in ui._COMMAND:
            t=[list(r) for r in self.upper]+[[' ']*20 for _ in range(6)]
            for tx,ty,word in ((10,14,'FIGHT'),(10,16,'ITEM'),(16,16,'RUN')):ui._put(t,tx,ty,word)
            t[y][x]='▶'
            if ui._match(rows,tuple(''.join(r) for r in t))!='invalid':return True
        return False

    def context(self,text,progress,*,location,battle_state,enemy_snapshot,player_snapshot,
                frame,now,overworld_ready=False,grid=None,intent=None):
        if self.completion is not None:return deepcopy(self.completion)
        if self.error:return self._fail(self.error)
        self.calls+=1
        if not _intent(self.intent) or intent is not None and not _intent(intent):
            return self._fail('snorlax_escape_intent_changed')
        if (not ui._int(frame,self.baseline['frame'],2**63-1) or not ui._clock(now)
                or now<self.last_now or self.last_frame is not None and frame<self.last_frame):
            return self._fail('snorlax_escape_clock_or_frame_invalid')
        if self.calls>self.max_calls or now-self.baseline['now']>self.max_seconds:
            return self._fail('snorlax_escape_transaction_budget_exhausted')
        self.last_now=now
        if (not ui._stance(location,frame) or not _frame(progress,frame) or type(overworld_ready) is not bool):
            return self._fail('snorlax_escape_location_or_frame_unknown')
        party=ui._party(progress);battle=_battle(battle_state,frame)
        if (party is None or party!=self.before_party or ui._inventory(progress)!=self.before_items
                or type(progress.get('money')) is not int or progress['money']!=self.baseline['progress']['money']):
            return self._fail('snorlax_escape_party_inventory_or_money_changed')
        if battle is None or battle=='none' and not self.prompt_confirmed or battle=='wild' and self.seen_battle_none:
            return self._fail('snorlax_escape_battle_sequence_unknown')
        if battle=='wild':
            readers=_readers(enemy_snapshot,player_snapshot,frame,party,self.active_index)
            if readers is None or readers!=self.before_readers:
                return self._fail('snorlax_escape_real_readers_or_guaranteed_speed_changed')
        elif (not _inactive(enemy_snapshot,ui.ENEMY_PROFILE,'enemy',frame)
              or not _inactive(player_snapshot,PLAYER_PROFILE,'player',frame)):
            return self._fail('snorlax_escape_inactive_readers_conflict')
        packet=deepcopy((text,progress,location,battle_state,enemy_snapshot,player_snapshot,overworld_ready,grid))
        if frame==self.last_frame:
            return self._wait('same_frame_no_resend') if packet==self.last_packet else self._fail('snorlax_escape_same_frame_changed_packet')
        self.last_frame,self.last_packet=frame,packet
        rows=ui._rows(text,frame)
        if rows is None:
            if self.run_requested and _native_blank(text,frame) and not overworld_ready:
                self.world_frame=None
                return self._wait('await_exact_native_blank_without_confirming')
            return self._fail('snorlax_escape_decoder_proof_required')
        if self.stage=='command':
            if overworld_ready:return self._fail('snorlax_escape_world_before_run')
            command=ui._command(rows,party,ui._enemy(enemy_snapshot,frame))
            if command is None:
                return self._wait('await_complete_known_command') if self._command_partial(rows) else self._fail('snorlax_escape_unknown_command')
            if command[0]!=self.active_index:return self._fail('snorlax_escape_active_member_changed')
            cursor=command[1]
            if self.pending:
                old,expected=self.pending
                if cursor==old:return self._wait('await_requested_cursor_without_resend')
                if cursor!=expected:return self._fail('snorlax_escape_unrequested_cursor')
                self.pending=None
            if cursor==(15,16):
                self.run_requested=True;self.stage='await_escape'
                return self._hint('a','select_only_verified_run_once',menu_label='RUN')
            action='down' if cursor[1]==14 else 'right'
            self.pending=(cursor,(cursor[0],16) if action=='down' else (15,16))
            return self._hint(action,'navigate_only_to_run')
        page=self._page(rows)
        if self.stage=='await_escape':
            if overworld_ready:return self._fail('snorlax_escape_world_before_success_prompt')
            if page=='full':
                self.prompt_confirmed=True;self.stage='closing'
                return self._hint('a','confirm_full_got_away_prompt_once')
            if page=='partial':return self._wait('await_complete_got_away_prompt')
            command=ui._command(rows,party,ui._enemy(enemy_snapshot,frame))
            if command==(self.active_index,(15,16)):return self._wait('await_run_result_without_reconfirming')
            return self._fail('snorlax_escape_failed_or_unknown_result')
        if self.stage!='closing':return self._fail('snorlax_escape_stage_unknown')
        if overworld_ready:
            if (battle!='none' or text['window_visible'] is not False or ''.join(rows).strip()
                    or not _grid(grid,frame)):
                return self._fail('snorlax_escape_world_proof_required')
            self.seen_battle_none=True
            if self.world_frame is None:
                self.world_frame=frame
                return self._wait('verify_second_distinct_closed_world_frame')
            self.stage='complete'
            self.completion={**self._hint('wait','escape_verified_on_two_world_frames'),
                'phase':'snorlax_escape_complete','escape_complete':True,'captured':False,
                'acknowledge_loses_route12_snorlax':True,'party_order_and_inventory_preserved':True,
                'first_world_observation_frame':self.world_frame,'completion_observation_frame':frame,
                'evidence_scope':'normal RUN and complete Got away safely prompt; not caught/result2/BEAT proof'}
            return deepcopy(self.completion)
        self.world_frame=None
        if battle=='none':self.seen_battle_none=True
        if not ''.join(rows).strip() or page!='invalid':return self._wait('await_native_battle_exit_without_resending_a')
        return self._fail('snorlax_escape_unknown_closing_ui')
