"""四天王普通走位後的窄互動候選；只提供動作，不送鍵或認證戰勝。"""
from copy import deepcopy
import math
from . import league_native_wait as native

SOURCE_COMMIT=native.SOURCE_COMMIT
PROFILE='red-en-e4-coordinate-source-v1-candidate'
NAMESPACE='_e4_coordinate_v1'
MAX_HANDSHAKE_CALLS=12
CONFIG={
    245:dict(origin=(5,5),target=(5,3),npc=(5,2),picture=59),
    246:dict(origin=(5,5),target=(5,3),npc=(5,2),picture=58),
    247:dict(origin=(5,5),target=(5,3),npc=(5,2),picture=57),
    113:dict(origin=(6,11),target=(6,2),npc=(6,1),picture=30),
}
ADDRESSES=dict(map_id=0xD35E,x=0xD362,y=0xD361,walk=0xCFC5,
    player_walk=0xC200,player_facing=0xC109,player_collision=0xC10C,
    object_count=0xD4E1,npc_picture=0xC110,npc_status=0xC111,
    npc_y_step=0xC113,npc_x_step=0xC115,npc_facing=0xC119,
    npc_walk=0xC210,npc_y=0xC214,npc_x=0xC215)


def _int(value,lo=0,hi=2**63-1):return type(value) is int and lo<=value<=hi
def _clock(value):return type(value) in (int,float) and math.isfinite(value) and value>=0
def _review(reason,step):
    return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
        review_reason='e4_coordinate_'+reason,route_step=step.get('id') if type(step) is dict else None,
        source_commit=SOURCE_COMMIT)


def read_interaction_signal(pyboy,*,observation_frame,constants):
    """同 frame 雙讀真實 facing/NPC；未讀 ROM，未假設來源姿態等於當前姿態。"""
    def invalid(reason):
        return dict(profile=PROFILE,read_valid=False,read_error=reason,observation_frame=observation_frame)
    if not _int(observation_frame):return invalid('frame_invalid')
    try:
        get=lambda k:constants.get(k) if isinstance(constants,dict) else getattr(constants,k,None)
        if (get('STATUS_FLAGS3_ADDRESS')!=0xD72D or type(get('STATUS_FLAGS3_ADDRESS')) is not int
                or get('OBTAINED_BADGES_ADDRESS')!=0xD356 or type(get('OBTAINED_BADGES_ADDRESS')) is not int):
            return invalid('sdk_anchors_unverified')
        before=pyboy.frame_count
        if not _int(before) or before!=observation_frame:return invalid('frame_not_current')
        first={k:pyboy.memory[a] for k,a in ADDRESSES.items()}
        second={k:pyboy.memory[a] for k,a in ADDRESSES.items()};after=pyboy.frame_count
        mid=first['map_id'];maps=get('MAPS')
        if mid not in CONFIG or not isinstance(maps,dict) or type(maps.get(native.CONFIG[mid]['map_name'])) is not int or maps[native.CONFIG[mid]['map_name']]!=mid:
            return invalid('sdk_map_unverified')
    except Exception:return invalid('getter_failed')
    if any(not _int(v,0,255) for sample in (first,second) for v in sample.values()):return invalid('byte_invalid')
    if not _int(after) or after!=before or first!=second:return invalid('torn_frame_or_snapshot')
    return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,read_valid=True,read_error=None,
        observation_frame=before,frame_before=before,frame_after=after,owner_id=id(pyboy),values=first)


def _base_error(c,owner,state,step,text,now):
    if owner is None or not isinstance(c,native.NativeWaitController) or c.owner is not owner:return 'owner_unverified'
    if native._signature(step)!=c.signature or c.step!=step:return 'bound_step_changed'
    if c.error is not None or getattr(c,'reviewed_recovery_error',None) is not None:return 'native_error_retained'
    if c.waiting is not False or c.intro_handoff is not False:return 'native_not_released'
    if not _clock(now) or not _clock(c.last_now) or now!=c.last_now:return 'native_clock_not_current'
    if not _int(c.calls) or not _clock(c.elapsed) or not _clock(c.started):return 'native_counters_unverified'
    if c.calls>native.MAX_CALLS or c.elapsed>native.MAX_SECONDS:return 'native_budget_exhausted'
    frame=state.get('frame') if type(state) is dict else None
    if not _int(frame) or c.last_frame!=frame or type(c.packet) not in (tuple,list) or len(c.packet)!=5:return 'native_frame_not_current'
    loc,runtime,p,packet_text,signal=c.packet
    if any(state.get(k)!=v for k,v in (('location',loc),('battle_state',runtime),('progress',p))) or packet_text!=text:return 'native_packet_disagrees'
    if (type(signal) is not dict or signal.get('profile')!=native.PROFILE or signal.get('source_commit')!=SOURCE_COMMIT
            or signal.get('read_valid') is not True or signal.get('read_error') is not None
            or type(signal.get('owner_id')) is not int or signal['owner_id']!=id(owner)
            or any(not _int(signal.get(k)) or signal[k]!=frame for k in ('observation_frame','frame_before','frame_after'))
            or signal.get('location')!=loc):return 'native_signal_unverified'
    v=signal.get('values');events=signal.get('events');mid=step['map_id'];cfg=native.CONFIG[mid]
    if (type(v) is not dict or type(events) is not dict
            or any(not _int(v.get(k),0,255) for k in ('script','battle_raw','battle_type','badges','simulated','ignored','status5'))
            or v['script']!=0 or v['battle_raw']!=0 or v['battle_type']!=0 or v['badges']!=255
            or v['simulated']!=0 or v['ignored']!=0 or v['status5']&1
            or runtime.get('raw')!=0 or type(runtime.get('raw')) is not int
            or runtime.get('kind')!='none' or runtime.get('active') is not False):return 'native_idle_unverified'
    if events.get(str(cfg['won'])) is not False:return 'unwon_source_event_required'
    if mid!=113 and events.get(str(cfg['auto'])) is not True:return 'native_autowalk_event_required'
    if native._text(text) is not True:return 'idle_text_unverified'
    return None


def _grid(grid,loc,frame,npc):
    if (type(grid) is not dict or grid.get('source')!='wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM'
            or type(grid.get('observation_frame')) is not int or grid['observation_frame']!=frame
            or grid.get('verified_location')!=[loc['map_id'],loc['x'],loc['y']]
            or not _int(grid.get('screen_cells_verified'),12,360)):return False
    cells=grid.get('visible_verified_cells');walk=grid.get('walkable')
    if (type(cells) is not list or len(cells)!=grid['screen_cells_verified']
            or any(type(p) is not list or len(p)!=2 or any(not _int(v,0,255) for v in p) for p in cells)
            or len(set(map(tuple,cells)))!=len(cells) or (loc['x'],loc['y']) not in set(map(tuple,cells)) or npc not in set(map(tuple,cells))):return False
    if (type(walk) is not list or not walk or any(type(row) is not list or len(row)!=len(walk[0]) or any(type(v) is not int or v not in (0,1) for v in row) for row in walk)):return False
    try:return walk[loc['y']][loc['x']]==1 and walk[npc[1]][npc[0]]==1
    except (IndexError,TypeError):return False


def context(owner,state,step,text,grid,previous,*,native_controller,now,signal=None):
    """在 native release 之後每 frame 呼叫；非目標回 None，留給普通 BFS。

    不在四個精確意圖時回 None；不清原 error，不建立替代 native owner。
    只在 endpoint 建立 namespace，且單調扣既有 60 calls／60 秒。
    """
    if type(step) is not dict or step.get('map_id') not in CONFIG:return None
    c=native_controller
    error=_base_error(c,owner,state,step,text,now)
    if error:
        record=getattr(c,NAMESPACE,None)
        if (isinstance(c,native.NativeWaitController) and c.owner is owner and c.step==step
                and type(record) is dict and record.get('step')==step):
            if record.get('error') is None:record['error']=error
            return _review(record['error'],step)
        return _review(error,step)
    frame=state['frame'];loc=state['location'];mid=step['map_id'];cfg=CONFIG[mid];point=(loc['x'],loc['y'])
    record=getattr(c,NAMESPACE,None)
    if record is not None and (type(record) is not dict or record.get('step')!=step
            or not _int(record.get('origin_frame')) or record.get('origin')!=list(cfg['origin'])
            or not _int(record.get('last_frame')) or record['origin_frame']>record['last_frame']
            or not _clock(record.get('last_now')) or not _clock(record.get('started'))
            or not _int(record.get('native_calls')) or not _clock(record.get('native_elapsed'))
            or not _int(record.get('calls')) or record.get('last_offer') not in (None,'up','a')
            or record.get('offered_frame') is not None and not _int(record['offered_frame'])
            or type(record.get('packet')) not in (list,tuple) or len(record['packet'])!=3
            or record.get('error') is not None and type(record['error']) is not str):return _review('namespace_unverified',step)
    if record is not None and record.get('error') is not None:return _review(record['error'],step)
    if record is None:
        if point!=cfg['origin']:
            return _review('native_endpoint_witness_required',step) if point==cfg['target'] else None
        record=dict(step=deepcopy(step),origin_frame=frame,origin=list(point),last_frame=frame,last_now=now,
            native_calls=c.calls,native_elapsed=c.elapsed,started=c.started,calls=0,last_offer=None,offered_frame=None,
            packet=deepcopy((state,text,signal)),error=None)
        setattr(c,NAMESPACE,record)
        return None
    def fail(reason):
        if record['error'] is None:record['error']=reason
        return _review(record['error'],step)
    if (not _int(record.get('last_frame')) or frame<record['last_frame'] or not _clock(record.get('last_now'))
            or now<record['last_now'] or c.started!=record.get('started')
            or not _int(record.get('native_calls')) or c.calls<record['native_calls']
            or not _clock(record.get('native_elapsed')) or c.elapsed<record['native_elapsed']):return fail('counter_clock_or_frame_regressed')
    if type(previous) not in (tuple,list) or any(type(a) is not str or a not in {'a','b','up','down','left','right','wait','start'} for a in previous):return fail('actual_previous_unverified')
    delta=now-record['last_now']
    if not math.isclose(delta,(frame-record['last_frame'])/60,rel_tol=1e-9,abs_tol=1e-9):return fail('emulator_clock_disagrees')
    if point!=cfg['target']:
        if record['last_offer'] is not None:return fail('coordinate_changed_after_offer')
        # 普通 BFS 時間不冒稱原生 WAIT，不重置上次 endpoint 或 spent budget。
        record.update(last_frame=frame,last_now=now,native_calls=c.calls,native_elapsed=c.elapsed,
            packet=deepcopy((state,text,signal)))
        return None
    if signal is None:return fail('interaction_signal_required')
    if (type(signal) is not dict or signal.get('profile')!=PROFILE or signal.get('source_commit')!=SOURCE_COMMIT
            or signal.get('read_valid') is not True or signal.get('read_error') is not None
            or type(signal.get('owner_id')) is not int or signal['owner_id']!=id(owner)
            or any(not _int(signal.get(k)) or signal[k]!=frame for k in ('observation_frame','frame_before','frame_after'))):return fail('interaction_signal_unverified')
    v=signal.get('values')
    if type(v) is not dict or any(not _int(v.get(k),0,255) for k in ADDRESSES):return fail('interaction_bytes_unverified')
    if (v['map_id'],v['x'],v['y'])!=(mid,*cfg['target']):return fail('interaction_location_disagrees')
    if (v['object_count']!=1 or v['npc_picture']!=cfg['picture'] or (v['npc_x']-4,v['npc_y']-4)!=cfg['npc']
            or v['npc_facing']!=0 or v['npc_status'] not in (1,2)
            or any(v[k]!=0 for k in ('npc_walk','npc_y_step','npc_x_step'))):return fail('source_npc_pose_unverified')
    if v['player_facing'] not in (0,4,8,12) or v['player_collision'] not in (0,8):return fail('source_facing_or_collision_unverified')
    if not _grid(grid,loc,frame,cfg['npc']):return fail('world_grid_unverified')
    packet=deepcopy((state,text,signal))
    if frame==record['last_frame']:
        if packet!=record['packet']:return fail('same_frame_packet_conflict')
        return _out(step,c,record,'wait','same_frame_no_repeat')
    # 只扣 native 尚未自然累計的真模擬時間；絕不降低原計數。
    c.elapsed+=max(0.,delta-(c.elapsed-record['native_elapsed']))
    c.calls+=1;record['calls']+=1
    record.update(last_frame=frame,last_now=now,native_calls=c.calls,native_elapsed=c.elapsed,packet=packet)
    if c.calls>native.MAX_CALLS or c.elapsed>native.MAX_SECONDS or record['calls']>MAX_HANDSHAKE_CALLS:return fail('budget_exhausted')
    if any(v[k]!=0 for k in ('walk','player_walk')):return _out(step,c,record,'wait','physical_movement_pending')
    if mid==113:return _out(step,c,record,'wait','lance_source_coordinate_autotrigger')
    if record['last_offer']=='a':
        if not previous or previous[-1] not in ('a','wait'):return fail('actual_a_ack_unverified')
        return _out(step,c,record,'wait','native_intro_pending_after_actual_a')
    if record['last_offer']=='up':
        if not previous or previous[-1]!='up':return fail('actual_up_ack_unverified')
        if v['player_facing']!=4:return fail('actual_up_facing_unverified')
        record.update(last_offer='a',offered_frame=frame)
        return _out(step,c,record,'a','source_npc_actual_up_confirmed')
    record.update(last_offer='up',offered_frame=frame)
    return _out(step,c,record,'up','source_npc_turn_up')


def _out(step,c,record,action,reason):
    return dict(phase='overworld',objective={'wait':'Wait.','up':'Move UP.','a':'Confirm the current selection.'}[action],
        available_actions=[action,'wait'] if action!='wait' else ['wait'],goal=step['id'],route_step=step['id'],
        source_e4_coordinate=True,source_commit=SOURCE_COMMIT,e4_coordinate_reason=reason,
        native_wait_calls=c.calls,native_wait_elapsed_seconds=c.elapsed,
        e4_origin_frame=record['origin_frame'],e4_coordinate_calls=record['calls'])


def at_target(owner,state,step,text,grid,previous,*,native_controller,now):
    """真 getter 接線；未到站不讀額外 sprite byte。呼叫前仍須先 native.context。"""
    signal=None
    if type(step) is dict and step.get('map_id') in CONFIG and state.get('location')==dict(map_id=step['map_id'],x=step['target'][0],y=step['target'][1]):
        from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
        signal=read_interaction_signal(owner,observation_frame=state.get('frame'),constants=sdk)
    return context(owner,state,step,text,grid,previous,native_controller=native_controller,now=now,signal=signal)
