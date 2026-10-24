"""洋館固定落穴／樓梯轉場，只以WAIT等完整目的圖；不操作遊戲。

pret/pokered a536711；完整ON矩陣由公開blk/bst與各樓層script重建。
來源路標的lineage不是畫面完成證明，未知渲染只有限WAIT。
"""
from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
import math
import time

from .mart_purchase import _party,_inventory
from .observation import PROFILE as TEXT_PROFILE

SOURCE_COMMIT='a53671100ec22e5394ff26ec028d0812a238dae2'
PROFILE='red-en-mansion-transition-movement-v1-unvalidated'
MECHANIC='mansion_transition_ready'
# key為目的map/玩家格；value為緊鄰前一步的來源map/target與目的tile。
REGISTRY={(165,16,14):(215,(16,14),0x01),
          (216,23,22):(165,(21,23),0x13),
          (165,21,24):(216,(23,22),0x01)}
# 返1F先在door1B(21,23)，只等原生DOWN至普通01(21,24)。
LANDING_PADS={(165,21,24):(21,23)}
ON_MATRIX_SHA={165:'14dca2732064da35a9e8f504f3570e859530311ed808d0a14724e790ce66abbb',
               216:'99b6be2491b2052755c67bc6f06617a1129b91e6da7362241a02d56b9123d472'}
FACILITY_COLL=frozenset((1,16,17,19,27,32,33,34,48,49,50,66,67,72,82,85,88,94))
ADDRESSES=dict(simulated_remaining=0xCD38,joy_ignore=0xCD6B,walk_counter=0xCFC5,
               movement_flags=0xD736,map_id=0xD35E,y=0xD361,x=0xD362,switch_raw=0xD796)
NATIVE_TEXT_ERRORS=frozenset(('visible_lcdc_getter_failed','visible_lcdc_invalid',
    'visible_display_disabled','visible_scanline_getter_failed','visible_scanline_positions_invalid',
    'visible_tile_getter_failed','visible_tile_alignment_incomplete'))
MAX_SECONDS,MAX_WAITS,MAX_CALLS=60,30,100
_CONTROLLERS=globals().get('_CONTROLLERS',{})
_BINDINGS=globals().get('_BINDINGS',{})
_COMPLETED=globals().get('_COMPLETED',set())


def _int(v,lo=0,hi=255):return type(v) is int and lo<=v<=hi


def _get(obj,key):return obj.get(key) if isinstance(obj,Mapping) else getattr(obj,key,None)


def _invalid(frame,error):
    return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,observation_frame=frame,
        read_valid=False,read_error=error,location=None,switch_on=None,switch_raw=None,
        simulated_remaining=None,joy_ignore=None,walk_counter=None,movement_flags=None)


def read_transition_movement(pyboy,*,observation_frame,constants):
    """同frame雙讀source movement/map/xy/開關；失敗不以零替代。"""
    if not _int(observation_frame,0,2**63-1):return _invalid(None,'frame_invalid')
    try:
        maps=_get(constants,'MAPS');events=_get(constants,'EVENT_FLAGS')
        if (any(type(_get(constants,k)) is not int or _get(constants,k)!=v for k,v in
                (('EVENT_FLAGS_ADDRESS',0xD747),('STATUS_FLAGS3_ADDRESS',0xD72D)))
                or not isinstance(maps,Mapping) or any(type(maps.get(k)) is not int or maps[k]!=v
                    for k,v in (('pokemon_mansion_1f',165),('pokemon_mansion_3f',215),('pokemon_mansion_b1f',216)))
                or not isinstance(events,Mapping) or type(events.get('mansion_switch_on')) is not int
                or events['mansion_switch_on']!=0x278):return _invalid(observation_frame,'sdk_anchors_unverified')
        before=pyboy.frame_count
        if type(before) is not int or before!=observation_frame:return _invalid(observation_frame,'frame_not_current')
        memory=pyboy.memory
        first={k:memory[a] for k,a in ADDRESSES.items()};second={k:memory[a] for k,a in ADDRESSES.items()}
        after=pyboy.frame_count
    except Exception:return _invalid(observation_frame,'getter_failed')
    if any(not _int(v) for sample in (first,second) for v in sample.values()):return _invalid(observation_frame,'byte_invalid')
    if type(after) is not int or after!=before or first!=second:return _invalid(observation_frame,'snapshot_changed')
    loc={k:first[k] for k in ('map_id','x','y')}
    if tuple(loc[k] for k in ('map_id','x','y')) not in (*REGISTRY,(165,21,23),(215,16,14)):
        return _invalid(observation_frame,'location_out_of_scope')
    if first['joy_ignore'] not in (0,0xFC,0xFF) or first['movement_flags']&0x38:
        return _invalid(observation_frame,'movement_mask_or_bits_unknown')
    return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,observation_frame=before,
        read_valid=True,read_error=None,location=loc,switch_on=bool(first['switch_raw']&1),
        **{k:first[k] for k in ('simulated_remaining','joy_ignore','walk_counter','movement_flags','switch_raw')})


def _review(reason,r=None):
    if r is not None:r['error']=r['error'] or reason;reason=r['error']
    return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
                review_reason='mansion_transition_'+reason,source_commit=SOURCE_COMMIT)


def _hint(r,complete=False):
    return dict(phase='overworld',objective='Wait.',available_actions=['wait'],source_commit=SOURCE_COMMIT,
        field_move_complete=complete,field_move_kind='mansion-transition-ready',
        mansion_transition_ready_complete=complete,transition_waits=r['waits'],transition_calls=r['calls'])


def _wait(r):
    r['waits']+=1
    return _review('wait_budget_exhausted',r) if r['waits']>MAX_WAITS else _hint(r)


def applies(step_id,step):
    return (bool(set(_BINDINGS)-_COMPLETED) or step_id in _BINDINGS
            or isinstance(step,dict) and step.get('mechanic')==MECHANIC)


def _text_status(text):
    if not isinstance(text,dict) or text.get('profile')!=TEXT_PROFILE:return False
    error=text.get('read_error')
    if error is not None:
        return None if type(error) is str and error in NATIVE_TEXT_ERRORS and text.get('read_valid') is False else False
    if (text.get('read_valid') is not True or text.get('alignment_verified') is not True
            or type(text.get('window_visible')) is not bool):return False
    cells=text.get('cells')
    if (type(cells) is not list or len(cells)!=18 or any(type(row) is not list or len(row)!=20
            or any(type(c) is not str or c!=' ' for c in row) for row in cells)):return False
    return text['window_visible'] is False and text.get('lines')==[] and text.get('line_rows')==[]


def _grid_status(grid,frame,loc,tile):
    if grid is None:return None
    if (not isinstance(grid,dict) or type(grid.get('observation_frame')) is not int or grid['observation_frame']!=frame
            or type(grid.get('tileset_id')) is not int or grid['tileset_id']!=22
            or grid.get('verified_location')!=[loc[k] for k in ('map_id','x','y')]
            or grid.get('source')!='wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM'):
        return False
    tiles,walk=grid.get('tiles'),grid.get('walkable')
    if any(type(a) is not list or len(a)!=28 or any(type(row) is not list or len(row)!=30
           or any(not _int(v,0,high) for v in row) for row in a) for a,high in ((tiles,255),(walk,1))):return False
    cells=grid.get('visible_verified_cells');count=grid.get('screen_cells_verified')
    if (type(cells) is not list or not _int(count,12,90) or len(cells)!=count
            or any(type(p) is not list or len(p)!=2 or not _int(p[0],0,29) or not _int(p[1],0,27) for p in cells)
            or len({tuple(p) for p in cells})!=count or [loc['x'],loc['y']] not in cells):return False
    if any(w!=int(t in FACILITY_COLL) for ts,ws in zip(tiles,walk) for t,w in zip(ts,ws)):return False
    digest=hashlib.sha256(json.dumps(tiles,separators=(',',':')).encode()).hexdigest()
    if digest!=ON_MATRIX_SHA[loc['map_id']]:return None  # 已改map、背景仍載入中；不能作ready。
    return tiles[loc['y']][loc['x']]==tile and walk[loc['y']][loc['x']]==1


def context(pyboy,state,plan,step_id,text,grid):
    """只等固定轉場；來源前序、完整ON目的圖及兩fresh幀各自查驗。"""
    r=_CONTROLLERS.get(step_id);active=set(_BINDINGS)-_COMPLETED
    if active and active!={step_id}:return _review('owner_changed',_CONTROLLERS.get(next(iter(active)))),step_id
    if r is not None and r['error'] is not None:return _review(r['error'],r),step_id
    if not isinstance(plan,dict) or type(plan.get('steps')) is not list:return _review('plan_unverified',r),step_id
    matches=[(i,s) for i,s in enumerate(plan['steps']) if isinstance(s,dict) and s.get('id')==step_id]
    if len(matches)!=1:return (_review('step_unverified',r),step_id) if r or matches else None
    index,step=matches[0]
    if step.get('mechanic')!=MECHANIC:return (_review('intent_changed',r),step_id) if step_id in _BINDINGS else None
    target=step.get('target');mid=step.get('map_id')
    key=(mid,*target) if type(mid) is int and type(target) is list and len(target)==2 and all(type(v) is int for v in target) else None
    if (key not in REGISTRY or step.get('kind')!='interact' or index==0
            or any(k in step for k in ('next_map','terminal','event','item','badge','await_script_event'))):
        return _review('explicit_intent_unverified',r),step_id
    pad=LANDING_PADS.get(key)
    if ((pad is not None and (step.get('landing_pad')!=list(pad) or type(step.get('landing_pad')) is not list
                             or any(type(v) is not int for v in step['landing_pad'])))
            or pad is None and 'landing_pad' in step):return _review('landing_pad_unverified',r),step_id
    smap,starget,tile=REGISTRY[key];prev=plan['steps'][index-1]
    if (not isinstance(prev,dict) or prev.get('kind')!='move' or type(prev.get('map_id')) is not int
            or prev['map_id']!=smap or type(prev.get('target')) is not list or prev['target']!=list(starget)
            or any(type(v) is not int for v in prev['target']) or type(prev.get('next_map')) is not int or prev['next_map']!=mid
            or any(k in prev for k in ('event','item','badge','mechanic','terminal','await_script_event'))):
        return _review('previous_native_source_lineage_unverified',r),step_id
    try:binding=(key,smap,starget,json.dumps(plan.get('training_job'),sort_keys=True,allow_nan=False))
    except (ValueError,TypeError):return _review('owner_unverified',r),step_id
    if step_id in _BINDINGS and _BINDINGS[step_id]!=binding:return _review('intent_or_job_changed',r),step_id
    if (r is None)!=(step_id not in _BINDINGS):return _review('original_owner_state_missing',r),step_id
    if not isinstance(state,dict):return _review('state_unverified',r),step_id
    frame,loc,battle,p=state.get('frame'),state.get('location'),state.get('battle_state'),state.get('progress')
    allowed=(key,) if pad is None else (key,(mid,*pad))
    if (not _int(frame,0,2**63-1) or not isinstance(loc,dict) or any(not _int(loc.get(k)) for k in ('map_id','x','y'))
            or tuple(loc[k] for k in ('map_id','x','y')) not in allowed):return _review('location_or_frame_unverified',r),step_id
    pos={k:loc[k] for k in ('map_id','x','y')}
    if (not isinstance(battle,dict) or battle.get('active') is not False or battle.get('kind')!='none'
            or type(battle.get('raw')) is not int or battle['raw']!=0
            or type(battle.get('observation_frame')) is not int or battle['observation_frame']!=frame):
        return _review('nonbattle_unverified',r),step_id
    for packet in (p,loc,text):
        if isinstance(packet,dict) and 'observation_frame' in packet and (
                type(packet['observation_frame']) is not int or packet['observation_frame']!=frame):return _review('packet_frame_conflict',r),step_id
    party=_party(p);bag=_inventory(p.get('inventory')) if isinstance(p,dict) else None
    events=p.get('story_event_bits') if isinstance(p,dict) else None
    if (party is None or len(party)!=6 or any(m['hp']<=0 or m['status']!=0 for m in party) or bag is None
            or not _int(p.get('money'),0,999999) or not isinstance(events,dict) or events.get('mansion_switch_on') is not True):
        return _review('healthy_party_bag_money_or_switch_unverified',r),step_id
    baseline=deepcopy((party,bag,p['money']))
    if r is not None and baseline!=r['baseline']:return _review('party_bag_money_changed',r),step_id
    now=time.monotonic()
    if (type(now) not in (int,float) or not math.isfinite(now) or now<0
            or r is not None and (now<r['last_now'] or frame<r['last_frame'])):return _review('clock_or_frame_regressed',r),step_id
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    movement=read_transition_movement(pyboy,observation_frame=frame,constants=constants)
    if (not isinstance(movement,dict) or movement.get('profile')!=PROFILE or movement.get('source_commit')!=SOURCE_COMMIT
            or movement.get('read_valid') is not True or movement.get('read_error') is not None
            or type(movement.get('observation_frame')) is not int or movement['observation_frame']!=frame
            or movement.get('location')!=pos or movement.get('switch_on') is not True
            or any(not _int(movement.get(k)) for k in ('simulated_remaining','joy_ignore','walk_counter','movement_flags','switch_raw'))
            or not movement['switch_raw']&1 or movement['joy_ignore'] not in (0,0xFC,0xFF) or movement['movement_flags']&0x38):
        return _review('movement_getter_unverified',r),step_id
    # a536711 constants/ram_constants.asm139–146：bit2=STANDING_ON_WARP，
    # home/overworld.asm410–418在warp格設置，並非出門／行走動作。
    # 僅B1普通13梯落點可保留4；1F門及落穴仍要求flags全0。
    flags_idle=(movement['movement_flags']==0 or
                key==(216,23,22) and tile==0x13 and movement['movement_flags']==4)
    idle=flags_idle and all(movement[k]==0 for k in ('simulated_remaining','joy_ignore','walk_counter'))
    at_exit=tuple(pos[k] for k in ('map_id','x','y'))==key
    text_ok=_text_status(text);grid_ok=_grid_status(grid,frame,pos,tile if at_exit else 0x1B)
    if text_ok is False or grid_ok is False:return _review('visible_or_source_grid_conflict',r),step_id
    if r is None:
        r=dict(baseline=baseline,started=now,last_now=now,last_frame=-1,packet=None,calls=0,waits=0,error=None,closed_frame=None)
        _CONTROLLERS[step_id]=r;_BINDINGS[step_id]=binding
    r['calls']+=1
    if r['calls']>MAX_CALLS or now-r['started']>MAX_SECONDS:return _review('budget_exhausted',r),step_id
    r['last_now']=now;packet=deepcopy((state,text,grid,movement))
    if frame==r['last_frame']:
        return (_review('same_frame_packet_conflict',r) if packet!=r['packet'] else _wait(r)),step_id
    r.update(last_frame=frame,packet=packet)
    from .campaign_transactions import verified_blank_transaction_world,ui_overworld_ready
    closed=(at_exit and text_ok is True and grid_ok is True and idle
            and verified_blank_transaction_world(text,grid) and ui_overworld_ready(text,grid))
    if closed:
        if r['closed_frame'] is not None:
            _COMPLETED.add(step_id)
            return _hint(r,True),(plan['steps'][index+1]['id'] if index+1<len(plan['steps']) else 'complete')
        r['closed_frame']=frame
    else:r['closed_frame']=None
    return _wait(r),step_id
