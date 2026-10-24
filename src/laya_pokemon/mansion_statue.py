"""固定紅版洋館三個站位的正常雕像交易；純候選，不操作遊戲。

pret/pokered a536711：PrintText(Who wouldn't? prompt)返回後才toggle事件278。
sourcepad不是可控落點；呼叫端須已完成原生warp並保留本實例跨reload。
reader僅getter，同frame雙讀不等於ROM身分或畫面已實機校準。
"""
from collections.abc import Mapping
from copy import deepcopy
import math
import re

from .mart_purchase import _party, _inventory
from .observation import PROFILE as TEXT_PROFILE
from .party_control import command
from .team_strategy import reference, move_key

SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
PROFILE = 'red-en-mansion-statue-source-v1-unvalidated'
MAX_SECONDS, MAX_CALLS, MAX_WAITS = 60, 80, 25
GRID_SOURCE = 'wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM'
REGISTRY = {(215, 10, 6), (216, 18, 26), (216, 20, 4)}
ADDRESSES = dict(map_id=0xD35E, y=0xD361, x=0xD362, facing_raw=0xC109,
                 event_raw=0xD796, joy_ignore=0xCD6B, simulated=0xCD38,
                 walk_counter=0xCFC5, movement_flags=0xD736, mode=0xD700)
SOURCES = [f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/{p}' for p in (
    'scripts/PokemonMansion1F.asm', 'scripts/PokemonMansion3F.asm',
    'scripts/PokemonMansionB1F.asm', 'text/PokemonMansion1F.asm',
    'data/events/hidden_events.asm', 'home/yes_no.asm', 'home/text.asm',
    'engine/menus/text_box.asm', 'constants/event_constants.asm', 'ram/wram.asm')]
# Lower-left物理tile，由各floor block替換與FACILITY.bst解碼；不從遊戲讀答案。
DOOR_TILES = {
    215: {
        False: ((14,4,1),(15,4,1),(14,5,1),(15,5,1),(14,10,1),(15,10,36),(14,11,1),(15,11,36)),
        True: ((14,4,1),(15,4,36),(14,5,1),(15,5,36),(14,10,1),(15,10,1),(14,11,1),(15,11,1))},
    216: {
        False: ((26,16,1),(27,16,1),(26,17,1),(27,17,1),(12,22,1),(13,22,1),(12,23,1),(13,23,1),(8,6,1),(9,6,36),(8,7,1),(9,7,36),(16,16,24),(17,16,24),(16,17,1),(17,17,1)),
        True: ((26,16,1),(27,16,1),(26,17,24),(27,17,24),(12,22,1),(13,22,36),(12,23,1),(13,23,36),(8,6,1),(9,6,1),(8,7,1),(9,7,1),(16,16,1),(17,16,1),(16,17,1),(17,17,1))}}


def _int(v, lo=0, hi=255):
    return type(v) is int and lo <= v <= hi


def _get(obj, key):
    return obj.get(key) if isinstance(obj, Mapping) else getattr(obj, key, None)


def _intent(i):
    return (type(i) is dict and set(i) == {'kind','map_id','player_x','player_y','source_before','source_after'}
            and i['kind'] == 'mansion_statue'
            and all(_int(i[k]) for k in ('map_id','player_x','player_y'))
            and (i['map_id'],i['player_x'],i['player_y']) in REGISTRY
            and type(i['source_before']) is bool and type(i['source_after']) is bool
            and i['source_before'] is not i['source_after'])


def _invalid(frame, reason):
    return dict(profile=PROFILE, source_commit=SOURCE_COMMIT, observation_frame=frame,
                read_valid=False, read_error=reason, location=None, switch_on=None,
                live_calibrated=False)


def read_mansion_statue(pyboy, observation_frame, constants):
    """D747+278//8=D796 bit0；badge D356+8/+11/+12交叉map/y/x。
    movement位址沿固定source推導：CD38/CD6B/CFC5/D736；不呼tick或setter。
    FC是原生選擇/方向忽略mask；FF為全忽略。其他mask與未知byte一律未知。
    """
    if not _int(observation_frame, 0, 2**63-1):
        return _invalid(None, 'frame_invalid')
    try:
        events, maps = _get(constants,'EVENT_FLAGS'), _get(constants,'MAPS')
        anchors = {'EVENT_FLAGS_ADDRESS':0xD747,'OBTAINED_BADGES_ADDRESS':0xD356,
                   'STATUS_FLAGS3_ADDRESS':0xD72D}
        if (any(type(_get(constants,k)) is not int or _get(constants,k) != v for k,v in anchors.items())
                or not isinstance(events,Mapping) or type(events.get('mansion_switch_on')) is not int
                or events['mansion_switch_on'] != 0x278 or not isinstance(maps,Mapping)
                or any(type(maps.get(k)) is not int or maps[k] != v
                       for k,v in (('pokemon_mansion_3f',215),('pokemon_mansion_b1f',216)))):
            return _invalid(observation_frame,'sdk_source_anchor_mismatch')
        before = pyboy.frame_count
        if type(before) is not int or before != observation_frame:
            return _invalid(observation_frame,'frame_not_current')
        first = {k:pyboy.memory[a] for k,a in ADDRESSES.items()}
        second = {k:pyboy.memory[a] for k,a in ADDRESSES.items()}
        after = pyboy.frame_count
    except Exception:
        return _invalid(observation_frame,'getter_failed')
    if any(not _int(v) for sample in (first,second) for v in sample.values()):
        return _invalid(observation_frame,'byte_invalid')
    if type(after) is not int or after != before or first != second:
        return _invalid(observation_frame,'torn_frame_or_snapshot')
    if ((first['map_id'],first['x'],first['y']) not in REGISTRY or first['mode'] != 0
            or first['facing_raw'] not in (0,4,8,12) or first['joy_ignore'] not in (0,0xFC,0xFF)
            or first['movement_flags'] & 0xB8):
        return _invalid(observation_frame,'location_mode_or_movement_unknown')
    return dict(profile=PROFILE, source_commit=SOURCE_COMMIT, observation_frame=before,
                read_valid=True, read_error=None, live_calibrated=False,
                location={k:first[k] for k in ('map_id','x','y')},
                switch_on=bool(first['event_raw'] & 1), event_id=0x278,
                **{k:v for k,v in first.items() if k not in ('map_id','x','y')})


def _blank():
    return (' '*20,)*18


def _page(label, arrow=False):
    r=[list(v) for v in _blank()]
    r[14][1:1+len(label)]=list(label)
    if arrow:r[16][18]='▼'
    return tuple(''.join(v) for v in r)


FIRST = _page('A SECRET SWITCH!', True)
QUESTION = _page('PRESS IT?')
PRESSED = _page('WHO WOULDNT?', True)  # 一個 't cell→T，座標不展開。


def _menu(y=8, marker='▶'):
    r=[list(v) for v in QUESTION]
    r[8][16:19]=list('YES');r[10][16:18]=list('NO');r[y][15]=marker
    return tuple(''.join(v) for v in r)


def _rows(text):
    if (not isinstance(text,dict) or text.get('profile') != TEXT_PROFILE
            or text.get('read_valid') is not True or text.get('alignment_verified') is not True
            or 'read_error' not in text or text.get('read_error') is not None or type(text.get('window_visible')) is not bool
            or type(text.get('cells')) not in (list,tuple) or len(text['cells']) != 18):
        return None
    rows=[]; raw=[]
    for y,row in enumerate(text['cells']):
        if type(row) not in (list,tuple) or len(row) != 20:return None
        normalized=[]
        for x,c in enumerate(row):
            if c == "'t":
                if (x,y) != (11,14) or ''.join(row[1:11]).upper() != 'WHO WOULDN':return None
                normalized.append('T')
            elif type(c) is str and len(c) == 1 and (c == ' ' or c in '!?▼▶▷' or c.isascii() and c.isalnum()):
                normalized.append(c.upper())
            else:return None
        rows.append(''.join(normalized));raw.append(''.join(row))
    pairs=[(y,s.rstrip()) for y,s in enumerate(raw) if re.search(r'[A-Za-z0-9]{2,}',s)][:12]
    if text.get('lines') != [s for _,s in pairs] or text.get('line_rows') != [y for y,_ in pairs]:return None
    return tuple(rows)


def _partial(rows, template):
    return all(a == ' ' or a == b for r,t in zip(rows,template) for a,b in zip(r,t))


def _fingerprint(p):
    party=_party(p);bag=_inventory(p.get('inventory')) if isinstance(p,dict) else None
    if (party is None or len(party) != 6 or {m['species'] for m in party} != {19,132,7,102,154,35}
            or bag is None or not _int(p.get('money'),0,999999) or p.get('player_name_raw') != 'KEVIN'
            or not _int(p.get('badges_raw')) or any(m['status'] != 0 or m['hp']*3 <= m['max_hp']*2 for m in party)):
        return None
    ref=reference()
    if ref.get('source_commit') != SOURCE_COMMIT:return None
    for m in party:
        for move,pp in zip(m['moves'],m['pp']):
            key=move_key(move) if move else None
            if (not move and pp or move and (key not in ref['moves'] or (pp&63) > ref['moves'][key]['pp']*(5+(pp>>6))//5)):
                return None
    return deepcopy(dict(party=party,inventory=bag,money=p['money'],badges_raw=p['badges_raw'],player_name_raw=p['player_name_raw']))


def _grid(grid, loc, frame):
    if not isinstance(grid,dict):return None
    mid,x,y=loc['map_id'],loc['x'],loc['y'];height=18 if mid==215 else 28
    if (grid.get('source') != GRID_SOURCE or type(grid.get('observation_frame')) is not int
            or grid['observation_frame'] != frame or grid.get('verified_location') != [mid,x,y]
            or any(type(v) is not int for v in grid.get('verified_location',[]))
            or type(grid.get('tileset_id')) is not int or grid['tileset_id'] != 22):return None
    tiles,walk=grid.get('tiles'),grid.get('walkable')
    for matrix,hi in ((tiles,255),(walk,1)):
        if (type(matrix) not in (list,tuple) or len(matrix) != height
                or any(type(row) not in (list,tuple) or len(row)!=30 or any(not _int(v,0,hi) for v in row) for row in matrix)):
            return None
    visible=grid.get('visible_verified_cells')
    if (type(visible) is not list or type(grid.get('screen_cells_verified')) is not int
            or grid['screen_cells_verified'] != len(visible) or len(visible)<12
            or any(type(v) is not list or len(v)!=2 or not _int(v[0],0,29) or not _int(v[1],0,height-1) for v in visible)
            or len({tuple(v) for v in visible})!=len(visible) or [x,y] not in visible or [x,y-1] not in visible
            or tiles[y][x]!=1 or walk[y][x]!=1 or tiles[y-1][x]!=0x3D or walk[y-1][x]!=0):return None
    for state,points in DOOR_TILES[mid].items():
        if all(tiles[b][a]==tile and walk[b][a]==int(tile==1) for a,b,tile in points):return state
    return None


class MansionStatueController:
    """三位置／before→after明確意圖；每次交易獨立實例，跨reload保留所有狀態。"""
    def __init__(self,intent):
        if not _intent(intent):raise ValueError('僅支援三個已核雕像站位與反向bool事件')
        self.intent=deepcopy(intent);self.binding=deepcopy(intent);self.stage='initial';self.error=None
        self.baseline=self.pending=self.last_packet=self.started=self.last_now=None
        self.last_frame=-1;self.calls=self.waits=0;self.closed_frames=[]
        self.initial_raw=None;self.final_executed=False

    def _fail(self,reason):
        self.error='mansion_statue_'+reason.removeprefix('mansion_statue_')
        return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],review_reason=self.error)

    def _wait(self,reason,complete=False):
        if not complete:
            self.waits+=1
            if self.waits>MAX_WAITS:return self._fail('wait_budget_exhausted')
        return dict(phase='mansion_statue',objective='Wait.',available_actions=['wait'],
                    mansion_statue_tactic=reason,mansion_statue_complete=complete)

    def _offer(self,action,next_stage,view):
        self.pending=dict(action=action,frame=self.last_frame,view=deepcopy(view),next_stage=next_stage,executed=False)
        return command(action,'mansion_statue',dict(mansion_statue_tactic='offer_'+next_stage,source_commit=SOURCE_COMMIT))

    def context(self,text,progress,*,location,battle_state,grid,signal,frame,previous,now,overworld_ready=False):
        if self.error:return self._fail(self.error)
        if not _intent(self.intent) or self.intent!=self.binding:return self._fail('intent_changed')
        self.calls+=1
        if (not _int(frame,0,2**63-1) or type(now) not in (int,float) or not math.isfinite(now)
                or self.last_now is not None and now<self.last_now or frame<self.last_frame):return self._fail('clock_or_frame_invalid')
        if self.started is None:self.started=now
        if now-self.started>MAX_SECONDS or self.calls>MAX_CALLS:return self._fail('budget_exhausted')
        self.last_now=now
        i=self.intent;loc=dict(map_id=i['map_id'],x=i['player_x'],y=i['player_y'])
        if (type(location) is not dict or location!=loc or any(type(v) is not int for v in location.values())
                or type(previous) not in (list,tuple) or any(type(a) is not str or a not in ('a','b','up','down','left','right','start','wait') for a in previous)):
            return self._fail('location_or_previous_invalid')
        if (not isinstance(battle_state,dict) or battle_state.get('kind')!='none' or battle_state.get('active') is not False
                or type(battle_state.get('raw')) is not int or battle_state['raw']!=0
                or type(battle_state.get('observation_frame')) is not int or battle_state['observation_frame']!=frame):return self._fail('battle_unverified')
        if (not isinstance(signal,dict) or signal.get('profile')!=PROFILE or signal.get('source_commit')!=SOURCE_COMMIT
                or signal.get('read_valid') is not True or 'read_error' not in signal or signal.get('read_error') is not None
                or type(signal.get('observation_frame')) is not int or signal['observation_frame']!=frame or signal.get('location')!=loc
                or type(signal.get('switch_on')) is not bool or signal.get('event_id')!=0x278 or type(signal.get('event_id')) is not int
                or any(not _int(signal.get(k)) for k in ('event_raw','facing_raw','joy_ignore','simulated','walk_counter','movement_flags','mode'))
                or signal['switch_on'] is not bool(signal['event_raw']&1) or signal['facing_raw'] not in (0,4,8,12)
                or signal['joy_ignore'] not in (0,0xFC,0xFF) or signal['movement_flags']&0xB8 or signal['mode']!=0):return self._fail('source_signal_unverified')
        if any(signal[k] != 0 for k in ('simulated','walk_counter','movement_flags')):
            return self._fail('movement_not_stationary')
        fp=_fingerprint(progress);rows=_rows(text);state=_grid(grid,loc,frame)
        if fp is None or rows is None or state is None:return self._fail('party_text_or_grid_unverified')
        if self.baseline is not None and fp!=self.baseline:return self._fail('baseline_changed')
        if self.initial_raw is not None and (signal['event_raw']^self.initial_raw)&0xFE:return self._fail('other_event_bits_changed')
        view=deepcopy((rows,signal['facing_raw']))
        packet=deepcopy((text,progress,location,battle_state,grid,signal,previous,overworld_ready))
        if frame==self.last_frame:
            return self._wait('same_frame_no_action') if packet==self.last_packet else self._fail('same_frame_conflict')
        self.last_frame=frame;self.last_packet=packet
        idle=all(signal[k]==0 for k in ('joy_ignore','simulated','walk_counter','movement_flags'))
        closed=(rows==_blank() and text['window_visible'] is False and overworld_ready is True and idle)
        if self.stage=='initial' and self.baseline is None:
            if not closed or signal['switch_on'] is not i['source_before'] or state is not i['source_before']:
                return self._fail('initial_world_or_before_unverified')
            self.baseline=fp;self.initial_raw=signal['event_raw']
            if signal['facing_raw']!=4:return self._offer('up','facing',view)
            return self._offer('a','first',view)
        if self.pending:
            p=self.pending
            if not p['executed']:
                if frame>p['frame'] and previous and previous[-1]==p['action']:
                    p['executed']=True;self.stage=p['next_stage']
                    if self.stage=='closing':self.final_executed=True
                elif view==p['view']:return self._wait('await_actual_previous')
                else:return self._fail('page_changed_without_actual_previous')
            if view==p['view']:return self._wait('executed_offer_not_resent')
            if p['action']=='up' and p['next_stage']=='question' and rows!=_menu(8):
                if any(_partial(rows,t) for t in (_menu(8),_menu(10))):
                    return self._wait('direction_semantic_receipt_pending')
                return self._fail('direction_unknown_receipt')
            self.pending=None
        if not self.final_executed and signal['switch_on'] is not i['source_before']:return self._fail('event_changed_before_final_confirm')
        if not self.final_executed and state is not i['source_before']:return self._fail('door_changed_before_final_confirm')
        if self.stage=='facing':
            if not closed or signal['facing_raw']!=4:return self._fail('facing_not_confirmed')
            return self._offer('a','first',view)
        if signal['facing_raw']!=4:return self._fail('facing_changed')
        if self.stage=='closing':
            if closed and signal['switch_on'] is i['source_after'] and state is i['source_after']:
                self.closed_frames.append(frame)
                if len(self.closed_frames)>=2:self.stage='complete';return self._wait('verified_toggle_closed',True)
                return self._wait('first_closed_frame')
            self.closed_frames=[]
            if rows==_blank() or _partial(rows,PRESSED):return self._wait('native_toggle_or_redraw_pending')
            return self._fail('closing_unknown_page')
        if self.stage=='complete':
            return self._wait('verified_toggle_closed',True) if closed and signal['switch_on'] is i['source_after'] and state is i['source_after'] else self._fail('completed_state_changed')
        if self.stage=='first' and rows==FIRST:return self._offer('a','question',view)
        if self.stage=='question':
            if rows==_menu(8):return self._offer('a','pressed',view)
            if rows==_menu(10):return self._offer('up','question',view)
        if self.stage=='pressed' and rows==PRESSED:return self._offer('a','closing',view)
        allowed={'first':(FIRST,), 'question':(FIRST,QUESTION,_menu(8),_menu(10)),
                 'pressed':(QUESTION,_menu(8),_menu(8,'▷'),PRESSED)}.get(self.stage,())
        if any(_partial(rows,t) for t in allowed):return self._wait('known_partial_or_prompt_blink')
        return self._fail('unknown_page')
