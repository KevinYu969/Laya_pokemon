"""真新鎮(4,13)正常選單使用衝浪；純子目標與唯讀getter，尚非實機校準。

固定 pret/pokered a536711；item_effects.asm669–748先設mode2才原生前進，
text_6.asm59–64的got on以prompt結尾。本類不執行任何按鍵或寫RAM。
呼叫端須保留同一實例跨reload，且序列化觀測/tick；不得重建基線續交易。
"""
from collections.abc import Mapping
from copy import deepcopy
import math
import re

from .mart_purchase import _party, _inventory
from .observation import PROFILE as TEXT_PROFILE
from .rocket_movement import MOVEMENT_PROFILE

SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
PROFILE = 'red-en-pallet-surf-source-v1-unvalidated'
PALLET_SURF_INTENT = dict(kind='pallet_surf', map_id=0, player_x=4, player_y=13,
                          facing='down', species=7, move=57, landing_x=4, landing_y=14)
START = dict(map_id=0, x=4, y=13)
LANDING = dict(map_id=0, x=4, y=14)
MAX_SECONDS, MAX_CALLS, MAX_WAITS = 60, 240, 30
# wWalkBikeSurfState = SDK D72D - 45 = SDK D747 - 71 = D700;
# ram/wram.asm2053–2141。map/y/x亦由既有badge D356+8/+11/+12交叉。
ADDRESSES = dict(mode=0xD700, map_id=0xD35E, y=0xD361, x=0xD362,
                 facing_raw=0xC109, battle_raw=0xD057, badges_raw=0xD356)


def _int(v, lo=0, hi=255):
    return type(v) is int and lo <= v <= hi


def _get(obj, name):
    return obj.get(name) if isinstance(obj, Mapping) else getattr(obj, name, None)


def _invalid(frame, reason):
    return dict(profile=PROFILE, source_commit=SOURCE_COMMIT, observation_frame=frame,
                read_valid=False, read_error=reason, mode=None, location=None,
                facing_raw=None, facing=None, battle_raw=None, badges_raw=None,
                live_calibrated=False)


def read_surf_observation(pyboy, observation_frame, constants):
    """同frame前後兩遍byte只讀；source推導不等同ROM版本或畫面認證。"""
    if not _int(observation_frame, 0, 2**63-1):
        return _invalid(None, 'frame_invalid')
    try:
        anchors = dict(STATUS_FLAGS3_ADDRESS=0xD72D, EVENT_FLAGS_ADDRESS=0xD747,
                       OBTAINED_BADGES_ADDRESS=0xD356)
        maps, badges = _get(constants, 'MAPS'), _get(constants, 'BADGES')
        if (any(type(_get(constants, k)) is not int or _get(constants, k) != v
                for k, v in anchors.items()) or not isinstance(maps, Mapping)
                or type(maps.get('pallet_town')) is not int or maps['pallet_town'] != 0
                or not isinstance(badges, Mapping) or type(badges.get('soul')) is not int
                or badges['soul'] != 4):
            return _invalid(observation_frame, 'sdk_source_anchors_unverified')
        before = pyboy.frame_count
        if type(before) is not int or before != observation_frame:
            return _invalid(observation_frame, 'frame_not_current')
        first = {k: pyboy.memory[a] for k, a in ADDRESSES.items()}
        second = {k: pyboy.memory[a] for k, a in ADDRESSES.items()}
        after = pyboy.frame_count
    except Exception:
        return _invalid(observation_frame, 'getter_failed')
    if any(not _int(v) for sample in (first, second) for v in sample.values()):
        return _invalid(observation_frame, 'byte_invalid')
    if type(after) is not int or after != before or first != second:
        return _invalid(observation_frame, 'torn_frame_or_snapshot')
    if first['mode'] not in (0, 1, 2) or first['facing_raw'] not in (0, 4, 8, 12):
        return _invalid(observation_frame, 'mode_or_facing_unknown')
    return dict(profile=PROFILE, source_commit=SOURCE_COMMIT, observation_frame=before,
                read_valid=True, read_error=None, mode=first['mode'],
                location={k:first[k] for k in ('map_id','x','y')},
                facing_raw=first['facing_raw'], facing={0:'down',4:'up',8:'left',12:'right'}[first['facing_raw']],
                battle_raw=first['battle_raw'], badges_raw=first['badges_raw'], live_calibrated=False)


def _blank():
    return (' '*20,)*18


def _put(rows, x, y, value):
    rows[y][x:x+len(value)] = list(value.upper())


def _serial(rows):
    return tuple(''.join(row) for row in rows)


def _rows(text):
    if (not isinstance(text, dict) or text.get('profile') != TEXT_PROFILE
            or text.get('read_valid') is not True or text.get('alignment_verified') is not True
            or text.get('read_error') is not None or type(text.get('window_visible')) is not bool
            or type(text.get('cells')) not in (list,tuple) or len(text['cells']) != 18):
        return None
    raw = []
    for row in text['cells']:
        if (type(row) not in (list,tuple) or len(row) != 20
                or any(type(c) is not str or len(c) != 1 or not (
                    c == ' ' or c in "éÉ'():;[]#?!.▷▶▼♂¥×/,-♀" or c.isascii() and c.isalnum()) for c in row)):
            return None
        raw.append(''.join(row))
    visible = [(y,row.rstrip()) for y,row in enumerate(raw) if re.search(r'[A-Za-z0-9]{2,}',row)][:12]
    if text.get('lines') != [s for _,s in visible] or text.get('line_rows') != [y for y,_ in visible]:
        return None
    return tuple(row.upper() for row in raw)


def _idle(movement, frame):
    if (not isinstance(movement,dict) or movement.get('profile') != MOVEMENT_PROFILE
            or movement.get('source_commit') != SOURCE_COMMIT or movement.get('read_valid') is not True
            or movement.get('read_error') is not None or type(movement.get('observation_frame')) is not int
            or movement['observation_frame'] != frame
            or any(not _int(movement.get(k)) for k in ('simulated_remaining','joy_ignore','walk_counter','movement_flags'))
            or movement['joy_ignore'] not in (0,255) or movement['movement_flags'] & 0x38
            or type(movement.get('spinning')) is not bool
            or movement['spinning'] != bool(movement['movement_flags'] & 128)):
        return None
    return (not movement['spinning'] and movement['simulated_remaining'] == 0
            and movement['joy_ignore'] == 0 and movement['walk_counter'] == 0)


def _world(grid, loc, frame):
    if (not isinstance(grid,dict) or type(grid.get('tileset_id')) is not int or grid['tileset_id'] != 0
            or not _int(grid.get('screen_cells_verified'),12,360)
            or type(grid.get('observation_frame')) is not int or grid['observation_frame'] != frame
            or grid.get('verified_location') != [loc['map_id'],loc['x'],loc['y']]):
        return False
    try:
        if any(type(grid[k]) is not list or len(grid[k]) != 18
               or any(type(row) is not list or len(row) != 20 for row in grid[k]) for k in ('tiles','walkable')):
            return False
        return (all(_int(v) for row in grid['tiles'] for v in row)
                and all(type(v) is int and v in (0,1) for row in grid['walkable'] for v in row)
                and (grid['tiles'][13][4],grid['walkable'][13][4]) == (0x23,1)
                and (grid['tiles'][14][4],grid['walkable'][14][4]) == (0x32,0))
    except (KeyError,TypeError,IndexError):
        return False


class PalletSurfController:
    """固定一次交易；同一owner實例的baseline/pending/預算必須跨熱載入保留。"""

    def __init__(self, intent=PALLET_SURF_INTENT):
        if (type(intent) is not dict or intent != PALLET_SURF_INTENT
                or any(type(v) is not int for k,v in intent.items() if k not in ('kind','facing'))):
            raise ValueError('僅允許Pallet(4,13)朝DOWN由Nidoking正常Surf至(4,14)')
        self.intent=deepcopy(intent); self.contract=deepcopy(intent)
        self.stage='initial'; self.error=None; self.baseline=None; self.target_index=None
        self.started=self.last_now=None; self.last_frame=-1; self.last_packet=None
        self.pending=self.expected=None; self.calls=self.waits=0
        self.surf_selected=self.prompt_ack=False; self.closed_frame=None

    def _hint(self, action, tactic, complete=False):
        return dict(phase='pallet_surf_complete' if complete else 'pallet_surf_menu',
                    objective={'wait':'Wait.','start':'Open the game menu with START.',
                               'a':'Confirm the current selection.','up':'Move UP.','down':'Move DOWN.'}[action],
                    available_actions=['wait'] if action=='wait' else [action,'wait'],
                    controller_menu_verified=action!='wait', pallet_surf_stage=self.stage,
                    pallet_surf_tactic=tactic, pallet_surf_complete=complete,
                    surf_entry_complete=complete, source_commit=SOURCE_COMMIT)

    def _fail(self, reason):
        self.error=self.error or 'pallet_surf_'+reason
        return {**self._hint('wait','review'),'phase':'campaign_review','review_reason':self.error}

    def _wait(self, reason):
        self.waits+=1
        return self._fail('wait_budget_exhausted') if self.waits>MAX_WAITS else self._hint('wait',reason)

    def _offer(self, action, stage, rows, expected=None):
        self.pending=dict(action=action, stage=stage, rows=rows, frame=self.last_frame,
                          executed=False, expected=expected)
        return self._hint(action,'offer_'+stage)

    def _start(self, cursor, marker='▶'):
        r=[list(row) for row in _blank()]
        for y,name in ((2,'POKÉDEX'),(4,'POKÉMON'),(6,'ITEM'),(8,'KEVIN'),(10,'SAVE'),(12,'OPTION'),(14,'EXIT')):
            _put(r,12,y,name)
        _put(r,11,cursor,marker)
        return _serial(r)

    def _party(self, index, marker='▶'):
        r=[list(row) for row in _blank()]
        for i,m in enumerate(self.baseline['party']):
            _put(r,3,2*i,m['species_name']); _put(r,13,2*i,f"{m['level']:3}")
            _put(r,13,2*i+1,f"{m['hp']:3}/{m['max_hp']:3}")
        _put(r,0,2*index+1,marker); _put(r,1,14,'Choose a POKéMON.')
        return _serial(r)

    def _field(self, cursor, marker='▶'):
        r=[list(row) for row in self._party(self.target_index,'▷')]
        for y in range(8,18): r[y][11:20]=[' ']*9
        for y,name in ((10,'SURF'),(12,'STATS'),(14,'SWITCH'),(16,'CANCEL')): _put(r,13,y,name)
        _put(r,12,cursor,marker)
        return _serial(r)

    def _prompt(self, arrow=False, party_background=False):
        # start_sub_menus: HandleMenuInput後先LoadScreenTilesFromBuffer1，
        # 再UseItem/PrintText；只接受原完整party或已重畫的空白背景。
        r=[list(row) for row in (self._party(self.target_index,'▷') if party_background else _blank())]
        for y in range(12,18): r[y]=[' ']*20
        _put(r,1,14,'KEVIN got on'); _put(r,1,16,'NIDOKING!')
        if arrow: _put(r,18,16,'▼')
        return _serial(r)

    def _selection(self, kind, index):
        good=self.expected is None or self.expected==(kind,index)
        if good: self.expected=None
        return good

    def context(self, text, progress, *, location, battle_state, grid, signal,
                movement, frame, previous, now, overworld_ready=False):
        if self.error: return self._fail('sticky')
        if (self.intent!=self.contract or not _int(frame,0,2**63-1) or frame<self.last_frame
                or type(now) not in (int,float) or not math.isfinite(now) or now<0
                or self.last_now is not None and now<self.last_now): return self._fail('owner_frame_or_clock_invalid')
        if self.started is None: self.started=now
        self.last_now=now; self.calls+=1
        if self.calls>MAX_CALLS or now-self.started>MAX_SECONDS: return self._fail('budget_exhausted')
        if (not isinstance(location,dict) or any(not _int(location.get(k)) for k in ('map_id','x','y'))
                or type(previous) not in (list,tuple) or any(type(a) is not str or a not in
                    ('a','b','up','down','left','right','start','wait') for a in previous)
                or type(overworld_ready) is not bool): return self._fail('location_or_actual_history_invalid')
        loc={k:location[k] for k in ('map_id','x','y')}
        if loc not in (START,LANDING): return self._fail('unexpected_location')
        for item in (text,progress,location):
            if isinstance(item,dict) and 'observation_frame' in item and (type(item['observation_frame']) is not int
                    or item['observation_frame']!=frame): return self._fail('observation_frame_conflict')
        if (not isinstance(battle_state,dict) or battle_state.get('kind')!='none' or battle_state.get('active') is not False
                or type(battle_state.get('raw')) is not int or battle_state['raw']!=0
                or type(battle_state.get('observation_frame')) is not int or battle_state['observation_frame']!=frame):
            return self._fail('battle_not_verified_none')
        if (not isinstance(signal,dict) or signal.get('profile')!=PROFILE or signal.get('source_commit')!=SOURCE_COMMIT
                or signal.get('read_valid') is not True or signal.get('read_error') is not None
                or type(signal.get('observation_frame')) is not int or signal['observation_frame']!=frame
                or signal.get('location')!=loc or signal.get('facing')!='down'
                or type(signal.get('facing_raw')) is not int or signal['facing_raw']!=0
                or type(signal.get('battle_raw')) is not int or signal['battle_raw']!=0
                or type(signal.get('mode')) is not int or signal['mode'] not in (0,2)):
            return self._fail('source_signal_unverified')
        idle=_idle(movement,frame)
        if idle is None: return self._fail('movement_unverified')
        party=_party(progress); bag=_inventory(progress.get('inventory')) if isinstance(progress,dict) else None
        if (party is None or len(party)!=6 or len({m['species'] for m in party})!=6
                or any(m['hp']<=0 or m['status']!=0 for m in party) or bag is None
                or not _int(progress.get('money'),0,999999) or progress.get('player_name_raw')!='KEVIN'
                or not _int(progress.get('badges_raw')) or not progress['badges_raw']&16
                or type(signal.get('badges_raw')) is not int or signal['badges_raw']!=progress['badges_raw']):
            return self._fail('progress_unverified')
        current=deepcopy(dict(party=party,inventory=bag,money=progress['money'],badges_raw=progress['badges_raw'],
                              player_name_raw=progress['player_name_raw']))
        if self.baseline is not None and current!=self.baseline: return self._fail('party_bag_money_or_pp_changed')
        rows=_rows(text)
        if rows is None: return self._fail('decoder_unverified')
        packet=deepcopy((text,progress,location,battle_state,grid,signal,movement,previous,overworld_ready))
        if frame==self.last_frame:
            return self._fail('same_frame_conflict') if packet!=self.last_packet else self._wait('same_frame_no_resend')
        self.last_frame,self.last_packet=frame,packet
        if self.baseline is None:
            targets=[i for i,m in enumerate(party) if m['species']==7 and m['moves']==[61,57,30,40]]
            if (len(targets)!=1 or loc!=START or not idle or signal['mode']!=0 or not overworld_ready
                    or text['window_visible'] is not False or rows!=_blank() or not _world(grid,loc,frame)):
                return self._fail('initial_closed_pallet_or_surf_user_unverified')
            self.baseline=current; self.target_index=targets[0]
            return self._offer('start','start',rows)
        if self.pending:
            p=self.pending
            if not p['executed']:
                if frame>p['frame'] and previous and previous[-1]==p['action']:
                    p['executed']=True; self.stage=p['stage']; self.expected=p['expected']
                    if self.stage=='got_on': self.surf_selected=True
                    if self.stage=='moving': self.prompt_ack=True
                elif rows==p['rows']: return self._hint(p['action'],'retry_unexecuted_candidate')
                else: return self._fail('changed_page_without_actual_previous')
            if rows==p['rows']: return self._wait('await_actual_action_effect')
            self.pending=None
        if self.stage in ('moving','complete'):
            if not self.prompt_ack or not self.surf_selected or signal['mode']!=2:
                return self._fail('native_surf_handoff_unverified')
            if (self.stage=='moving' and loc==START and text['window_visible'] is True
                    and any(rows==self._prompt(arrow,back) for arrow in (False,True) for back in (False,True))):
                self.closed_frame=None
                return self._wait('already_acknowledged_prompt_no_resend')
            if rows!=_blank() or text['window_visible'] is not False:
                self.closed_frame=None
                return self._fail('unexpected_post_prompt_text')
            if loc==LANDING and idle and overworld_ready and _world(grid,loc,frame):
                if self.closed_frame is None:
                    self.closed_frame=frame
                    return self._wait('first_closed_water_frame')
                self.stage='complete'
                return self._hint('wait','verified_native_pallet_surf',True)
            self.closed_frame=None
            if loc==LANDING and idle and overworld_ready: return self._fail('landing_water_grid_unverified')
            if self.stage=='complete': return self._fail('completed_water_landing_changed')
            return self._wait('native_forward_movement_only')
        if loc!=START: return self._fail('moved_before_prompt_ack')
        if text['window_visible'] is not True: return self._fail('menu_window_unverified')
        if self.stage!='got_on' and signal['mode']!=0: return self._fail('surf_mode_before_use')
        if self.stage=='start':
            for y in (2,4,6,8,10,12,14):
                if rows==self._start(y):
                    if not self._selection('start',y): return self._fail('start_cursor_jump')
                    if y==4: return self._offer('a','party',rows)
                    dy=2 if y<4 else -2
                    return self._offer('down' if dy>0 else 'up','start',rows,('start',y+dy))
                if rows==self._start(y,'▷'): return self._wait('inactive_start_cursor')
        elif self.stage=='party':
            if rows==self._start(4,'▷'): return self._wait('native_start_confirmation')
            for i in range(6):
                if rows==self._party(i):
                    if not self._selection('party',i): return self._fail('party_cursor_jump')
                    if i==self.target_index: return self._offer('a','field',rows)
                    di=1 if i<self.target_index else -1
                    return self._offer('down' if di>0 else 'up','party',rows,('party',i+di))
                if rows==self._party(i,'▷'): return self._wait('inactive_party_cursor')
        elif self.stage=='field':
            if rows==self._party(self.target_index,'▷'): return self._wait('native_party_confirmation')
            for y in (10,12,14,16):
                if rows==self._field(y):
                    if not self._selection('field',y): return self._fail('field_cursor_jump')
                    if y==10: return self._offer('a','got_on',rows)
                    return self._offer('up','field',rows,('field',y-2))
                if rows==self._field(y,'▷'): return self._wait('inactive_field_cursor')
        elif self.stage=='got_on':
            if not self.surf_selected: return self._fail('surf_not_actually_selected')
            if rows in (self._field(10,'▷'),self._party(self.target_index,'▷')):
                return self._wait('native_field_confirmation')
            if any(rows==self._prompt(True,back) for back in (False,True)) and signal['mode']==2:
                return self._offer('a','moving',rows)
            a,b=rows[14][1:19].rstrip(),rows[16][1:19].rstrip()
            clean=list(rows); clean[14]=clean[16]=' '*20
            backgrounds=[_blank(),tuple(list(self._party(self.target_index,'▷')[:12])+[' '*20]*6)]
            if (tuple(clean) in backgrounds and 'KEVIN GOT ON'.startswith(a)
                    and (not b or a=='KEVIN GOT ON' and 'NIDOKING!'.startswith(b))):
                return self._wait('known_got_on_printing_or_prompt_blink')
        return self._fail('unknown_or_polluted_native_page')
