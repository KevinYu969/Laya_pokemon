"""洋館兩個固定門落點的有界原生WAIT；不送鍵、不tick、不寫RAM。

固定a536711：home/overworld.asm536–540,2374–2381；
home/npc_movement.asm14–48；engine/overworld/auto_movement.asm1–17。
原生出門joy_ignore=FC有別於箭頭地板，故此處有獨立唯讀profile。
同一job/step交易不可重建基線；熱載入保留owner、已花預算與sticky錯誤。
"""
from collections.abc import Mapping
from copy import deepcopy
import json
import hashlib
import math
import time

from .mart_purchase import _party, _inventory
from .observation import PROFILE as TEXT_PROFILE

SOURCE_COMMIT='a53671100ec22e5394ff26ec028d0812a238dae2'
PROFILE='red-en-mansion-native-landing-movement-v1-unvalidated'
MECHANIC='mansion_native_landing'
PAIRS={214:((5,10),(5,11)),215:((6,1),(6,2))}
MAX_SECONDS,MAX_WAITS,MAX_CALLS=60,20,80
ADDRESSES=dict(simulated_remaining=0xCD38,joy_ignore=0xCD6B,walk_counter=0xCFC5,
               movement_flags=0xD736,map_id=0xD35E,y=0xD361,x=0xD362)
SOURCES=[f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/{p}' for p in (
    'home/overworld.asm#L536-L540','home/overworld.asm#L2374-L2381',
    'home/npc_movement.asm#L14-L48','engine/overworld/auto_movement.asm#L1-L17',
    'constants/ram_constants.asm')]
_CONTROLLERS=globals().get('_CONTROLLERS',{})
_BINDINGS=globals().get('_BINDINGS',{})
_COMPLETED=globals().get('_COMPLETED',set())
# 固定1F OFF原圖840格：公開blk/bst並套四個script門block後的canonical JSON。
# 只有2F初始pad可把這個「尚未換完的前圖」視為WAIT證據，絕非完成。
_PRELOAD_1F_OFF='680b4ddf16ab264fd33ed218dfd2093a7204326ad37264a77b87fde24929f8c0'
_PRELOAD_2F_OFF='ff65d21f82fa38b097d1beb62e35a36ddace9a308992694b847a1e0dd6710525'
_PRELOAD_OFF={214:_PRELOAD_1F_OFF,215:_PRELOAD_2F_OFF}
_FACILITY_COLL={1,16,17,19,27,32,33,34,48,49,50,66,67,72,82,85,88,94}


def _int(v,lo=0,hi=255):
    return type(v) is int and lo<=v<=hi


def _get(obj,key):
    return obj.get(key) if isinstance(obj,Mapping) else getattr(obj,key,None)


def _invalid(frame,error):
    return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,observation_frame=frame,
        read_valid=False,read_error=error,location=None,simulated_remaining=None,
        joy_ignore=None,walk_counter=None,movement_flags=None,spinning=None)


def read_mansion_landing_movement(pyboy,*,observation_frame,constants):
    """來源四個movement bytes加map/xy守衛，兩遍同frame；未知不補零。"""
    if not _int(observation_frame,0,2**63-1):return _invalid(None,'frame_invalid')
    try:
        maps=_get(constants,'MAPS')
        if (any(type(_get(constants,k)) is not int or _get(constants,k)!=v for k,v in
                (('STATUS_FLAGS3_ADDRESS',0xD72D),('EVENT_FLAGS_ADDRESS',0xD747)))
                or not isinstance(maps,Mapping) or any(type(maps.get(k)) is not int or maps[k]!=v
                    for k,v in (('pokemon_mansion_2f',214),('pokemon_mansion_3f',215)))):
            return _invalid(observation_frame,'sdk_source_anchors_unverified')
        before=pyboy.frame_count
        if type(before) is not int or before!=observation_frame:return _invalid(observation_frame,'frame_not_current')
        memory=pyboy.memory
        first={k:memory[a] for k,a in ADDRESSES.items()}
        second={k:memory[a] for k,a in ADDRESSES.items()}
        after=pyboy.frame_count
    except Exception:return _invalid(observation_frame,'getter_failed')
    if any(not _int(v) for sample in (first,second) for v in sample.values()):
        return _invalid(observation_frame,'byte_invalid')
    if type(after) is not int or after!=before or first!=second:
        return _invalid(observation_frame,'torn_frame_or_snapshot')
    map_id=first['map_id'];pos=(first['x'],first['y'])
    if map_id not in PAIRS or pos not in PAIRS[map_id]:return _invalid(observation_frame,'location_out_of_scope')
    if first['joy_ignore'] not in (0,0xFC,0xFF) or first['movement_flags']&0x38:
        return _invalid(observation_frame,'unknown_movement_bits_or_mask')
    return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,observation_frame=before,
        read_valid=True,read_error=None,location={k:first[k] for k in ('map_id','x','y')},
        **{k:first[k] for k in ('simulated_remaining','joy_ignore','walk_counter','movement_flags')},
        spinning=bool(first['movement_flags']&128))


def _idle(movement,frame,loc):
    if (not isinstance(movement,dict) or movement.get('profile')!=PROFILE
            or movement.get('source_commit')!=SOURCE_COMMIT or movement.get('read_valid') is not True
            or movement.get('read_error') is not None or type(movement.get('observation_frame')) is not int
            or movement['observation_frame']!=frame or movement.get('location')!=loc
            or any(not _int(movement.get(k)) for k in
                ('simulated_remaining','joy_ignore','walk_counter','movement_flags'))
            or movement['joy_ignore'] not in (0,0xFC,0xFF) or movement['movement_flags']&0x38
            or type(movement.get('spinning')) is not bool
            or movement['spinning']!=bool(movement['movement_flags']&128)):
        return None
    # 原生standing/exiting/warp/spinning旗標都要清；僅sprite暫靜止不是出門完成。
    return all(movement[k]==0 for k in ('simulated_remaining','joy_ignore','walk_counter','movement_flags'))


def _review(reason,record=None):
    if record is not None:
        record['error']=record['error'] or reason
        reason=record['error']
    return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
                review_reason='mansion_native_landing_'+reason,source_commit=SOURCE_COMMIT)


def _hint(record,complete=False):
    return dict(phase='overworld',objective='Wait.',available_actions=['wait'],
        field_move_complete=complete,field_move_kind='mansion-native-landing',
        mansion_native_landing_complete=complete,source_commit=SOURCE_COMMIT,sources=SOURCES,
        mansion_landing_waits=record['waits'],mansion_landing_calls=record['calls'])


def _wait(record):
    record['waits']+=1
    return _review('wait_budget_exhausted',record) if record['waits']>MAX_WAITS else _hint(record)


def applies(step_id,step):
    return (bool(set(_BINDINGS)-_COMPLETED) or step_id in _BINDINGS
            or isinstance(step,dict) and step.get('mechanic')==MECHANIC)


def _grid(grid,frame,loc,pad,exit_pos):
    if grid is None:return None
    if (not isinstance(grid,dict) or type(grid.get('tileset_id')) is not int or grid['tileset_id']!=22
            or type(grid.get('observation_frame')) is not int or grid['observation_frame']!=frame
            or grid.get('verified_location')!=[loc[k] for k in ('map_id','x','y')]):return False
    try:
        tiles,walk=grid['tiles'],grid['walkable']
        if (type(tiles) is not list or not tiles or len(tiles)>256 or type(walk) is not list
                or len(walk)!=len(tiles) or type(tiles[0]) is not list or not tiles[0]
                or len(tiles[0])>256):return False
        width=len(tiles[0])
        if any(type(row) is not list or len(row)!=width or any(not _int(v,0,high) for v in row)
               for a,high in ((tiles,255),(walk,1)) for row in a):return False
        cells=grid.get('visible_verified_cells');count=grid.get('screen_cells_verified')
        if (type(cells) is not list or not _int(count,12,90) or len(cells)!=count
                or any(type(p) is not list or len(p)!=2 or not _int(p[0],0,width-1)
                       or not _int(p[1],0,len(tiles)-1) for p in cells)
                or len({tuple(p) for p in cells})!=count or [loc['x'],loc['y']] not in cells):return False
        return (tiles[pad[1]][pad[0]]==0x1B and walk[pad[1]][pad[0]]==1
                and tiles[exit_pos[1]][exit_pos[0]]==1 and walk[exit_pos[1]][exit_pos[0]]==1)
    except (KeyError,IndexError,TypeError):return False


def _text(text):
    if text is None:return None
    if not isinstance(text,dict) or text.get('profile')!=TEXT_PROFILE:return False
    if text.get('read_valid') is not True or text.get('alignment_verified') is not True or text.get('read_error') is not None:
        return None
    cells=text.get('cells')
    if (type(cells) is not list or len(cells)!=18 or any(type(row) is not list or len(row)!=20
            or any(type(c) is not str or c!=' ' for c in row) for row in cells)):
        return False
    return (text.get('window_visible') is False and text.get('lines')==[] and text.get('line_rows')==[])


def _known_preload(grid,frame,loc,progress):
    """2F map id已變但1F OFF整幅仍在；只容許精確來源840格與碰撞表。"""
    mid=loc.get('map_id') if isinstance(loc,dict) else None
    pad=PAIRS[mid][0] if type(mid) is int and mid in PAIRS else None
    events=progress.get('story_event_bits') if isinstance(progress,dict) else None
    if (pad is None or loc!=dict(map_id=mid,x=pad[0],y=pad[1]) or not isinstance(events,Mapping)
            or events.get('mansion_switch_on') is not False
            or not isinstance(grid,dict) or grid.get('observation_frame')!=frame
            or type(grid.get('observation_frame')) is not int or grid.get('tileset_id')!=22
            or type(grid.get('tileset_id')) is not int
            or grid.get('verified_location')!=[mid,*pad]
            or grid.get('source')!='wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM'):
        return False
    tiles,walk=grid.get('tiles'),grid.get('walkable')
    for matrix,high in ((tiles,255),(walk,1)):
        if (type(matrix) is not list or len(matrix)!=28
                or any(type(row) is not list or len(row)!=30
                       or any(not _int(v,0,high) for v in row) for row in matrix)):
            return False
    if hashlib.sha256(json.dumps(tiles,separators=(',',':')).encode()).hexdigest()!=_PRELOAD_OFF[mid]:
        return False
    if any(w!=int(t in _FACILITY_COLL) for ts,ws in zip(tiles,walk) for t,w in zip(ts,ws)):
        return False
    cells=grid.get('visible_verified_cells');count=grid.get('screen_cells_verified')
    return (type(cells) is list and _int(count,12,90) and len(cells)==count
            and all(type(p) is list and len(p)==2 and _int(p[0],0,29) and _int(p[1],0,27) for p in cells)
            and len({tuple(p) for p in cells})==count and list(pad) in cells)


def _scripted_initial_wait(state,plan,step,text,grid,movement):
    """3F已由原生接管(FC/exiting)且畫面捲動未齊；只在固定前序樓梯後WAIT。"""
    if (state.get('location')!=dict(map_id=215,x=6,y=1) or grid is not None
            or not isinstance(text,dict) or text.get('profile')!=TEXT_PROFILE
            or text.get('read_valid') is not False or text.get('alignment_verified') is not False
            or text.get('read_error')!='visible_tile_alignment_incomplete'
            or text.get('window_visible') is not False or text.get('lines')!=[] or text.get('line_rows')!=[]
            or text.get('cells')!=[[' ']*20 for _ in range(18)]
            or movement.get('joy_ignore')!=0xFC or movement.get('movement_flags')!=2
            or movement.get('simulated_remaining') not in (0,1)
            or not _int(movement.get('walk_counter'),1,8)):
        return False
    progress=state.get('progress')
    events=progress.get('story_event_bits') if isinstance(progress,Mapping) else None
    if not isinstance(events,Mapping) or events.get('mansion_switch_on') is not False:return False
    index=plan['steps'].index(step)
    if index<1:return False
    previous=plan['steps'][index-1]
    return (previous.get('kind')=='move' and type(previous.get('map_id')) is int
            and previous['map_id']==214 and previous.get('target')==[6,1]
            and all(type(v) is int for v in previous['target'])
            and type(previous.get('next_map')) is int and previous['next_map']==215
            and not any(k in previous for k in ('event','item','badge','mechanic','await_script_event')))


def context(pyboy,state,plan,step_id,text,grid):
    """只回WAIT／sticky review；兩fresh、真空白野外與idle出口才推下一step。"""
    record=_CONTROLLERS.get(step_id)
    active=set(_BINDINGS)-_COMPLETED
    if active and active!={step_id}:
        owner=next(iter(active));return _review('owner_changed',_CONTROLLERS.get(owner)),step_id
    if record is not None and record['error'] is not None:return _review(record['error'],record),step_id
    if not isinstance(plan,dict) or type(plan.get('steps')) is not list:
        return _review('plan_unverified',record),step_id
    matches=[s for s in plan['steps'] if isinstance(s,dict) and s.get('id')==step_id]
    if len(matches)!=1:return (_review('step_unverified',record),step_id) if record or matches else None
    step=matches[0]
    if step.get('mechanic')!=MECHANIC:
        return (_review('intent_changed',record),step_id) if step_id in _BINDINGS else None
    map_id=step.get('map_id');pair=PAIRS.get(map_id) if type(map_id) is int else None
    if (step.get('kind')!='interact' or pair is None or type(step.get('target')) is not list
            or type(step.get('landing_pad')) is not list or step['target']!=list(pair[1])
            or step['landing_pad']!=list(pair[0]) or any(type(v) is not int for k in ('target','landing_pad') for v in step[k])
            or any(k in step for k in ('next_map','terminal','event','item','badge','await_script_event'))):
        return _review('explicit_intent_unverified',record),step_id
    try:
        binding=(MECHANIC,map_id,pair,json.dumps(plan.get('training_job'),sort_keys=True,allow_nan=False))
    except (TypeError,ValueError):return _review('owner_unverified',record),step_id
    if step_id in _BINDINGS and _BINDINGS[step_id]!=binding:return _review('intent_or_job_changed',record),step_id
    if (record is None)!=(step_id not in _BINDINGS):return _review('original_owner_state_missing',record),step_id
    if not isinstance(state,dict):return _review('state_unverified',record),step_id
    frame,loc,battle,p=state.get('frame'),state.get('location'),state.get('battle_state'),state.get('progress')
    if (not _int(frame,0,2**63-1) or not isinstance(loc,dict)
            or any(not _int(loc.get(k)) for k in ('map_id','x','y'))
            or loc['map_id']!=map_id or (loc['x'],loc['y']) not in pair):
        return _review('location_or_frame_unverified',record),step_id
    pos={k:loc[k] for k in ('map_id','x','y')}
    if (not isinstance(battle,dict) or battle.get('kind')!='none' or battle.get('active') is not False
            or type(battle.get('raw')) is not int or battle['raw']!=0
            or type(battle.get('observation_frame')) is not int or battle['observation_frame']!=frame):
        return _review('nonbattle_unverified',record),step_id
    for packet in (p,loc,text):
        if isinstance(packet,dict) and 'observation_frame' in packet and (
                type(packet['observation_frame']) is not int or packet['observation_frame']!=frame):
            return _review('packet_frame_conflict',record),step_id
    party=_party(p);inventory=_inventory(p.get('inventory')) if isinstance(p,dict) else None
    if (party is None or len(party)!=6 or any(m['hp']<=0 or m['status']!=0 for m in party)
            or inventory is None or not _int(p.get('money'),0,999999)):
        return _review('healthy_party_bag_money_unverified',record),step_id
    baseline=deepcopy((party,inventory,p['money']))
    if record is not None and baseline!=record['baseline']:return _review('party_bag_money_changed',record),step_id
    now=time.monotonic()
    if (type(now) not in (int,float) or not math.isfinite(now) or now<0
            or record is not None and (now<record['last_now'] or frame<record['last_frame'])):
        return _review('clock_or_frame_regressed',record),step_id
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    movement=read_mansion_landing_movement(pyboy,observation_frame=frame,constants=constants)
    idle=_idle(movement,frame,pos)
    if idle is None:return _review('movement_getter_unverified',record),step_id
    grid_ok=_grid(grid,frame,pos,*pair);text_ok=_text(text)
    preload=_known_preload(grid,frame,pos,p)
    if preload:grid_ok=None  # 保持未知目標圖，不可拿前圖作完成證據。
    if grid_ok is False or text_ok is False:return _review('source_grid_or_visible_text_conflict',record),step_id
    from .campaign_transactions import verified_blank_transaction_world,ui_overworld_ready
    closed=bool(grid_ok is True and text_ok is True and verified_blank_transaction_world(text,grid)
                and ui_overworld_ready(text,grid))
    if record is None:
        scripted=_scripted_initial_wait(state,plan,step,text,grid,movement)
        if not closed and not (preload and text_ok is True) and not scripted:
            return _review('initial_full_source_world_required'),step_id
        record=dict(baseline=baseline,started=now,last_now=now,last_frame=-1,packet=None,
                    calls=0,waits=0,closed_frame=None,error=None)
        _CONTROLLERS[step_id]=record;_BINDINGS[step_id]=binding
    record['calls']+=1
    if record['calls']>MAX_CALLS or now-record['started']>MAX_SECONDS:return _review('budget_exhausted',record),step_id
    record['last_now']=now
    packet=deepcopy((state,text,grid,movement))
    if frame==record['last_frame']:
        if packet!=record['packet']:return _review('same_frame_packet_conflict',record),step_id
        return _wait(record),step_id
    record.update(last_frame=frame,packet=packet)
    if closed and idle and (loc['x'],loc['y'])==pair[1]:
        if record['closed_frame'] is not None:
            _COMPLETED.add(step_id)
            index=plan['steps'].index(step)+1
            return _hint(record,True),(plan['steps'][index]['id'] if index<len(plan['steps']) else 'complete')
        record['closed_frame']=frame
    else:record['closed_frame']=None
    return _wait(record),step_id
