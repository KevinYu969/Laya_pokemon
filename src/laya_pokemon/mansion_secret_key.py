"""B1F固定Secret Key球的正常拾取候選；只回DOWN/A/WAIT，不操作遊戲。

固定pret/pokered a536711。pick_up_item.asm先GiveItem→HideObject，
再設wDoNotWaitForButtonPressAfterDisplayingText=1並印FoundItemText。
data/text/text_1.asm60–65是!@/text_end，沒有prompt；home/text_script.asm
87–103跳過WaitForTextScrollButtonPress，只等A釋放。因此收據絕不補A。
row14/16 x1來自普通PrintText與line；source-only版型仍待父層真packet校準。
"""
from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
import math
import re

from .mart_purchase import _party, _inventory
from .observation import PROFILE as TEXT_PROFILE
from .party_control import command
from .team_strategy import reference, move_key

SOURCE_COMMIT='a53671100ec22e5394ff26ec028d0812a238dae2'
PROFILE='red-en-mansion-secret-key-source-v1-unvalidated'
SECRET_KEY_INTENT=dict(kind='mansion_secret_key',map_id=216,player_x=5,player_y=12,
    facing='down',item=43,quantity=1,object_slot=8,object_index=194)
LOCATION=dict(map_id=216,x=5,y=12)
MAX_SECONDS,MAX_CALLS,MAX_WAITS=60,80,25
GRID_SOURCE='wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM'
ON_MATRIX_SHA='99b6be2491b2052755c67bc6f06617a1129b91e6da7362241a02d56b9123d472'
OBJECT_PAIRS=((3,190),(4,191),(5,192),(6,193),(8,194))
# D4E1 NumSprites；+1+1→D4E4 MapSpriteData[16*2]→D504 Extra[16*2]。
# slot8 offset(8-1)*2=14→D512/D513。MAX_OBJECT_EVENTS是16，不是15。
# C180 picture；C284/C285 MapY/MapX含4格邊界。ImageIndex=FF不證hidden。
ADDRESSES=dict(map_id=0xD35E,y=0xD361,x=0xD362,facing_raw=0xC109,
    object_count=0xD4E1,object_picture=0xC180,object_y_raw=0xC284,object_x_raw=0xC285,
    item_raw=0xD512,item_aux=0xD513,switch_raw=0xD796,mode=0xD700,
    joy_ignore=0xCD6B,simulated=0xCD38,walk_counter=0xCFC5,movement_flags=0xD736)
FLAG_ADDRESS,FLAG_LENGTH,TABLE_ADDRESS,TABLE_LENGTH=0xD5A6,32,0xD5CE,33
KEY_FLAG_OFFSET,KEY_MASK=24,4  # D5A6+194//8=D5BE，194%8=2。
# 原研究曾漏計UNUSED_MAP_F4的$02列，錯列193/bit1；此處保留校正原因。
# const_def從0起；const先賦值後+1。C2=194是zero-based，不作一基轉換。
SOURCES=[f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/{p}' for p in (
    'data/maps/objects/PokemonMansionB1F.asm','data/maps/toggleable_objects.asm',
    'constants/toggle_constants.asm','constants/map_data_constants.asm',
    'constants/sprite_constants.asm','engine/events/pick_up_item.asm',
    'engine/overworld/toggleable_objects.asm','data/text/text_1.asm',
    'data/items/names.asm','home/overworld_text.asm','home/text_script.asm','ram/wram.asm')]
SOURCE_BLOBS={'data/text/text_1.asm':'538396ebed012c2c8f095fb97d30fad442ae1c05',
    'home/text_script.asm':'36f6338b4c8d06cb134e7af705df5ea8666ab3f8',
    'data/items/names.asm':'f5c0f27ea3b6d3600f9a17c98525486ebad41cf4',
    'constants/sprite_constants.asm':'346ad0e49c90500faabe59b2780fd101f44346f4'}
NATIVE_ERRORS=frozenset(('visible_tile_alignment_incomplete','visible_display_disabled'))


def _int(v,lo=0,hi=255):return type(v) is int and lo<=v<=hi


def _get(obj,key):return obj.get(key) if isinstance(obj,Mapping) else getattr(obj,key,None)


def _intent(i):
    return (type(i) is dict and i==SECRET_KEY_INTENT and set(i)==set(SECRET_KEY_INTENT)
            and all(type(i[k]) is type(v) for k,v in SECRET_KEY_INTENT.items()))


def _invalid(frame,reason):
    return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,observation_frame=frame,
        read_valid=False,read_error=reason,location=None,item_hidden=None,flags=None,table=None,live_calibrated=False)


def _source_fields(a,flags,table):
    if (any(not _int(v) for v in a.values()) or type(flags) is not list or len(flags)!=32
            or type(table) is not list or len(table)!=33 or any(not _int(v) for v in flags+table)):
        return False
    expected={'map_id':216,'y':12,'x':5,'object_count':8,'object_picture':61,
              'object_y_raw':17,'object_x_raw':9,'item_raw':43,'item_aux':0,'mode':0}
    if (any(a.get(k)!=v for k,v in expected.items()) or a.get('facing_raw') not in (0,4,8,12)
            or a.get('joy_ignore') not in (0,0xFC,0xFF) or a.get('movement_flags',255)&0xB8
            or not a.get('switch_raw',0)&1):return False
    prefix=[v for pair in OBJECT_PAIRS for v in pair]+[255]
    return table[:11]==prefix


def read_mansion_secret_key(pyboy,observation_frame,constants):
    """getter-only同frame兩遍全部byte；沒有ROM讀取／按鍵／tick／setter。
    source全toggle表及slot8身份一起核；不是僅讀D5BE當物件存在證據。
    SDK只證固定基址／map／item；不把source推導冒稱本機ROM校準。
    """
    if not _int(observation_frame,0,2**63-1):return _invalid(None,'frame_invalid')
    try:
        maps,items,events=(_get(constants,k) for k in ('MAPS','ITEMS','EVENT_FLAGS'))
        anchors={'EVENT_FLAGS_ADDRESS':0xD747,'STATUS_FLAGS3_ADDRESS':0xD72D,
            'OBTAINED_BADGES_ADDRESS':0xD356,'BAG_ITEM_COUNT_ADDRESS':0xD31D,
            'BAG_ITEMS_ADDRESS':0xD31E,'BAG_ITEM_CAPACITY':20}
        if (any(type(_get(constants,k)) is not int or _get(constants,k)!=v for k,v in anchors.items())
                or any(not isinstance(v,Mapping) for v in (maps,items,events))
                or any(type(d.get(k)) is not int or d[k]!=v for d,k,v in (
                    (maps,'pokemon_mansion_b1f',216),(items,'SECRET_KEY',43),(events,'mansion_switch_on',0x278)))):
            return _invalid(observation_frame,'sdk_anchor_mismatch')
        before=pyboy.frame_count
        if type(before) is not int or before!=observation_frame:return _invalid(observation_frame,'frame_not_current')
        memory=pyboy.memory
        def sample():
            return ({k:memory[a] for k,a in ADDRESSES.items()},
                    [memory[FLAG_ADDRESS+i] for i in range(FLAG_LENGTH)],
                    [memory[TABLE_ADDRESS+i] for i in range(TABLE_LENGTH)])
        first,second=sample(),sample();after=pyboy.frame_count
    except Exception:return _invalid(observation_frame,'getter_failed')
    # Python把0==False==0.0視為相等；兩遍必須各自通過真byte/source驗證。
    if not _source_fields(*first) or not _source_fields(*second):
        return _invalid(observation_frame,'object_or_source_fields_invalid')
    if type(after) is not int or before!=after or first!=second:return _invalid(observation_frame,'torn_frame_or_snapshot')
    a,flags,table=first
    if not _source_fields(a,flags,table):return _invalid(observation_frame,'object_or_source_fields_invalid')
    return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,observation_frame=before,
        read_valid=True,read_error=None,location={k:a[k] for k in ('map_id','x','y')},
        flags=flags,table=table,item_hidden=bool(flags[KEY_FLAG_OFFSET]&KEY_MASK),
        live_calibrated=False,**{k:v for k,v in a.items() if k not in ('map_id','x','y')})


def _blank():return (' '*20,)*18


def _receipt():
    r=[list(row) for row in _blank()]
    r[14][1:12]=list('KEVIN FOUND');r[16][1:12]=list('SECRET KEY!')
    return tuple(''.join(row) for row in r)


RECEIPT=_receipt()


def _rows(text,*,native=False):
    if (not isinstance(text,dict) or text.get('profile')!=TEXT_PROFILE or type(text.get('window_visible')) is not bool
            or 'read_error' not in text):return None
    if native:
        if (text.get('read_valid') is not False or text.get('alignment_verified') is not False
                or text.get('read_error') not in NATIVE_ERRORS):return None
    elif (text.get('read_valid') is not True or text.get('alignment_verified') is not True
            or text['read_error'] is not None):return None
    cells=text.get('cells')
    if (type(cells) not in (list,tuple) or len(cells)!=18 or any(type(row) not in (list,tuple) or len(row)!=20
            or any(type(c) is not str or len(c)!=1 or not(c==' ' or c=='!' or c.isascii() and c.isalnum()) for c in row) for row in cells)):
        return None
    raw=[''.join(row) for row in cells]
    pairs=[(y,s.rstrip()) for y,s in enumerate(raw) if re.search(r'[A-Za-z0-9]{2,}',s)][:12]
    if not native and (text.get('lines')!=[s for _,s in pairs] or text.get('line_rows')!=[y for y,_ in pairs]):return None
    return tuple(row.upper() for row in raw)


def _partial(rows):return all(a==' ' or a==b for r,t in zip(rows,RECEIPT) for a,b in zip(r,t))


def _fingerprint(p):
    party=_party(p);bag=_inventory(p.get('inventory')) if isinstance(p,dict) else None
    if (party is None or len(party)!=6 or {m['species'] for m in party}!={19,132,7,102,154,35}
            or any(mon['hp']<=0 or mon['status']!=0 for mon in party) or bag is None
            or not _int(p.get('money'),0,999999) or not _int(p.get('badges_raw')) or p.get('player_name_raw')!='KEVIN'):
        return None
    ref=reference()
    if ref.get('source_commit')!=SOURCE_COMMIT:return None
    for mon in party:
        for move,pp in zip(mon['moves'],mon['pp']):
            key=move_key(move) if move else None
            if (not move and pp or move and (key not in ref['moves'] or (pp&63)>ref['moves'][key]['pp']*(5+(pp>>6))//5)):return None
    return deepcopy(dict(party=party,inventory=bag,money=p['money'],badges_raw=p['badges_raw'],player_name_raw=p['player_name_raw']))


def _grid(grid,frame):
    if not isinstance(grid,dict):return False
    if (grid.get('source')!=GRID_SOURCE or type(grid.get('tileset_id')) is not int or grid['tileset_id']!=22
            or type(grid.get('observation_frame')) is not int or grid['observation_frame']!=frame
            or grid.get('verified_location')!=[216,5,12] or any(type(v) is not int for v in grid['verified_location'])):return False
    tiles,walk=grid.get('tiles'),grid.get('walkable');coll={1,16,17,19,27,32,33,34,48,49,50,66,67,72,82,85,88,94}
    if any(type(a) is not list or len(a)!=28 or any(type(row) is not list or len(row)!=30 or any(not _int(v,0,high) for v in row) for row in a) for a,high in ((tiles,255),(walk,1))):return False
    cells=grid.get('visible_verified_cells');n=grid.get('screen_cells_verified')
    if (not _int(n,12,90) or type(cells) is not list or len(cells)!=n
            or any(type(p) is not list or len(p)!=2 or not _int(p[0],0,29) or not _int(p[1],0,27) for p in cells)
            or len({tuple(p) for p in cells})!=n or [5,12] not in cells or [5,13] not in cells):return False
    return (hashlib.sha256(json.dumps(tiles,separators=(',',':')).encode()).hexdigest()==ON_MATRIX_SHA
            and all(w==int(t in coll) for ts,ws in zip(tiles,walk) for t,w in zip(ts,ws))
            and tiles[12][5]==tiles[13][5]==1 and walk[12][5]==walk[13][5]==1)


class MansionSecretKeyController:
    """同一實例綁定原19項袋、六隊與slot8；收據只WAIT，無任何第二次檢查球A。"""
    def __init__(self,intent=SECRET_KEY_INTENT):
        if not _intent(intent):raise ValueError('只允許固定B1F Secret Key拾取')
        self.intent=deepcopy(intent);self.binding=deepcopy(intent);self.baseline=None
        self.stage='initial';self.error=None;self.pending=None;self.started=self.last_now=None
        self.last_frame=-1;self.last_packet=None;self.calls=self.waits=0
        self.original_flags=self.original_switch=None;self.pickup_executed=False
        self.seen_receipt=False;self.closed_frames=[]

    def _fail(self,reason):
        self.error='mansion_secret_key_'+reason.removeprefix('mansion_secret_key_')
        return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],review_reason=self.error)

    def _wait(self,reason,complete=False):
        if not complete:
            self.waits+=1
            if self.waits>MAX_WAITS:return self._fail('wait_budget_exhausted')
        return dict(phase='mansion_secret_key',objective='Wait.',available_actions=['wait'],
            mansion_secret_key_tactic=reason,mansion_secret_key_complete=complete)

    def _offer(self,action,stage,view):
        self.pending=dict(action=action,stage=stage,view=deepcopy(view),frame=self.last_frame,executed=False)
        return command(action,'mansion_secret_key',dict(mansion_secret_key_tactic='offer_'+stage,source_commit=SOURCE_COMMIT))

    def context(self,text,progress,*,location,battle_state,grid,signal,frame,previous,now,overworld_ready=False):
        if self.error:return self._fail(self.error)
        if not _intent(self.intent) or self.intent!=self.binding:return self._fail('intent_changed')
        self.calls+=1
        if (not _int(frame,0,2**63-1) or type(now) not in (int,float) or not math.isfinite(now)
                or now<0 or self.last_now is not None and now<self.last_now or frame<self.last_frame):return self._fail('clock_or_frame_invalid')
        if self.started is None:self.started=now
        if now-self.started>MAX_SECONDS or self.calls>MAX_CALLS:return self._fail('budget_exhausted')
        self.last_now=now
        if (type(location) is not dict or location!=LOCATION or any(type(v) is not int for v in location.values())
                or type(previous) not in (list,tuple) or any(type(a) is not str or a not in ('a','b','up','down','left','right','start','wait') for a in previous)):
            return self._fail('location_or_previous_invalid')
        if any(isinstance(p,dict) and 'observation_frame' in p and (
                type(p['observation_frame']) is not int or p['observation_frame']!=frame)
                for p in (text,progress)):
            return self._fail('packet_frame_conflict')
        if (not isinstance(battle_state,dict) or battle_state.get('kind')!='none' or battle_state.get('active') is not False
                or type(battle_state.get('raw')) is not int or battle_state['raw']!=0
                or type(battle_state.get('observation_frame')) is not int or battle_state['observation_frame']!=frame):return self._fail('battle_unverified')
        if (not isinstance(signal,dict) or signal.get('profile')!=PROFILE or signal.get('source_commit')!=SOURCE_COMMIT
                or signal.get('read_valid') is not True or 'read_error' not in signal or signal['read_error'] is not None
                or type(signal.get('observation_frame')) is not int or signal['observation_frame']!=frame or signal.get('location')!=LOCATION
                or type(signal.get('item_hidden')) is not bool):return self._fail('source_signal_unverified')
        a={**LOCATION,**{k:signal.get(k) for k in ADDRESSES if k not in LOCATION}}
        flags,table=signal.get('flags'),signal.get('table')
        if (not _source_fields(a,flags,table) or signal['item_hidden'] is not bool(flags[24]&KEY_MASK)
                or any(signal[k]!=0 for k in ('simulated','walk_counter','movement_flags'))):return self._fail('object_source_or_movement_unverified')
        fp=_fingerprint(progress)
        if fp is None:return self._fail('party_bag_money_unverified')
        rows=_rows(text);native=_rows(text,native=True) if rows is None else None
        if rows is None and (native is None or not _partial(native)):return self._fail('text_unverified')
        if self.baseline is not None:
            if any(fp[k]!=self.baseline[k] for k in fp if k!='inventory'):return self._fail('party_identity_or_money_changed')
            after=self.baseline['inventory']+[dict(item=43,quantity=1)]
            bag_state=0 if fp['inventory']==self.baseline['inventory'] else 1 if fp['inventory']==after else None
            if bag_state is None:return self._fail('inventory_unexpected_change')
            expected=list(self.original_flags);expected[24]|=KEY_MASK
            if flags not in (self.original_flags,expected) or signal['switch_raw']!=self.original_switch:return self._fail('other_source_flags_changed')
        else:bag_state=0
        packet=deepcopy((text,progress,location,battle_state,grid,signal,previous,overworld_ready))
        if frame==self.last_frame:
            return self._wait('same_frame_no_action') if packet==self.last_packet else self._fail('same_frame_conflict')
        self.last_frame=frame;self.last_packet=packet
        view=deepcopy((rows if rows is not None else native,signal['facing_raw'],signal['item_hidden'],bag_state))
        idle=all(signal[k]==0 for k in ('joy_ignore','simulated','walk_counter','movement_flags'))
        grid_ok=_grid(grid,frame)
        closed=(rows==_blank() and text['window_visible'] is False and overworld_ready is True and idle and grid_ok)
        if self.stage=='initial' and self.baseline is None:
            if (not closed or native is not None or signal['item_hidden'] is not False or len(fp['inventory'])!=19
                    or any(i['item']==43 for i in fp['inventory'])):return self._fail('initial_world_space_or_object_unverified')
            self.baseline=fp;self.original_flags=deepcopy(flags);self.original_switch=signal['switch_raw']
            return self._offer('down' if signal['facing_raw']!=0 else 'a','facing' if signal['facing_raw']!=0 else 'pickup',view)
        if self.pending:
            p=self.pending
            if not p['executed']:
                if frame>p['frame'] and previous and previous[-1]==p['action']:
                    p['executed']=True;self.stage=p['stage']
                    if self.stage=='pickup':self.pickup_executed=True
                elif view==p['view']:return self._wait('await_actual_previous')
                else:return self._fail('changed_without_actual_previous')
            if view==p['view']:return self._wait('executed_offer_not_resent')
            self.pending=None
        if self.stage=='facing':
            if not closed or signal['facing_raw']!=0 or signal['item_hidden'] or bag_state:return self._fail('facing_or_object_not_confirmed')
            return self._offer('a','pickup',view)
        if not self.pickup_executed:return self._fail('pickup_not_executed')
        if signal['facing_raw']!=0:return self._fail('facing_changed')
        if signal['item_hidden'] and bag_state!=1:return self._fail('hidden_without_item')
        if native is not None:
            self.closed_frames=[]
            return self._wait('known_native_decoder_transition')
        if not grid_ok:return self._fail('source_grid_unverified')
        if rows==RECEIPT:
            if bag_state!=1 or signal['item_hidden'] is not True:return self._fail('receipt_without_item_and_hidden')
            self.seen_receipt=True;self.stage='closing';self.closed_frames=[]
            return self._wait('native_found_receipt_no_prompt_no_a')
        if closed and bag_state==1 and signal['item_hidden'] is True:
            if not self.seen_receipt:return self._fail('native_receipt_not_observed')
            self.closed_frames.append(frame)
            if len(self.closed_frames)>=2:self.stage='complete';return self._wait('verified_key_closed',True)
            return self._wait('first_closed_frame')
        if self.stage=='complete':return self._fail('completed_state_changed')
        self.closed_frames=[]
        if _partial(rows):return self._wait('known_partial_or_native_close')
        return self._fail('unknown_page')
