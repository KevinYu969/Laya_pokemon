"""Source-scoped Route22/E4 native movement and blank-intro WAIT only.

No keys, ticks, RAM writes, battle/route completion or victory certification.
Caller keeps loss/health guards and existing battle/dialogue handling first.
"""
from copy import deepcopy
import math
import re
import time

from .mart_purchase import _party
from . import rocket_movement

SOURCE_COMMIT='a53671100ec22e5394ff26ec028d0812a238dae2'
PROFILE='red-en-route22-league-native-wait-v1-candidate'
TEXT_PROFILE='gen1-visible-tile-text-candidates-v1-unvalidated'
MAX_CALLS,MAX_SECONDS=60,60
# wWalkBikeSurf D700 = SDK D72D-45. Route23 +153 bytes reaches D700:
# db3 + ds78 + ds56 + hidden112/8 + coins16/8. Relative script block
# wram1953..2038 then gives the other addresses without guessed symbols.
CONFIG={
 33:dict(script=0xD60A,target=[29,4],face='left',event='beat_route22_rival_2nd_battle',
         won=0x526,auto=None,opponent=242,map_name='route_22',source='Route22'),
 245:dict(script=0xD64D,target=[5,3],face='up',event='beat_loreleis_room_trainer_0',
          won=0x8E1,auto=0x8E6,opponent=244,map_name='loreleis_room',source='LoreleisRoom'),
 246:dict(script=0xD64E,target=[5,3],face='up',event='beat_brunos_room_trainer_0',
          won=0x8E9,auto=0x8EE,opponent=233,map_name='brunos_room',source='BrunosRoom'),
 247:dict(script=0xD64F,target=[5,3],face='up',event='beat_agathas_room_trainer_0',
          won=0x8F1,auto=0x8F6,opponent=246,map_name='agathas_room',source='AgathasRoom'),
 113:dict(script=0xD653,target=[6,2],face='up',event='beat_lance',
          won=0x8FE,auto=None,opponent=247,map_name='lances_room',source='LancesRoom'),
 120:dict(script=0xD64C,target=[4,3],face='up',event='beat_champion_rival',
          won=0x901,auto=None,opponent=243,map_name='champions_room',source='ChampionsRoom'),
}
_WAITS=globals().get('_WAITS',{})


def _int(v,lo=0,hi=2**63-1):return type(v) is int and lo<=v<=hi
def _clock(v):return type(v) in (int,float) and math.isfinite(v) and v>=0
def _get(obj,key):return obj.get(key) if isinstance(obj,dict) else getattr(obj,key,None)


def _invalid(frame,reason):
    return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,observation_frame=frame,
        read_valid=False,read_error=reason,location=None,values=None,events=None)


def read_native_signal(pyboy,*,observation_frame,constants):
    """Same-frame double read with installed SDK/source anchors; never ticks."""
    if not _int(observation_frame):return _invalid(None,'frame_invalid')
    anchors=dict(STATUS_FLAGS3_ADDRESS=0xD72D,EVENT_FLAGS_ADDRESS=0xD747,
        OBTAINED_BADGES_ADDRESS=0xD356,CURRENT_OPPONENT_ADDRESS=0xD059,
        BATTLE_TYPE_ADDRESS=0xD05A,TRAINER_NUMBER_ADDRESS=0xD05D)
    try:
        if any(type(_get(constants,k)) is not int or _get(constants,k)!=v for k,v in anchors.items()):
            return _invalid(observation_frame,'sdk_source_anchors_unverified')
        before=pyboy.frame_count
        if not _int(before) or before!=observation_frame:return _invalid(observation_frame,'frame_not_current')
        map_id=pyboy.memory[0xD35E]
        if not _int(map_id,0,255) or map_id not in CONFIG:return _invalid(observation_frame,'map_outside_scope')
        cfg=CONFIG[map_id];maps=_get(constants,'MAPS')
        if not isinstance(maps,dict) or type(maps.get(cfg['map_name'])) is not int or maps[cfg['map_name']]!=map_id:
            return _invalid(observation_frame,'sdk_map_unverified')
        addresses=dict(map_id=0xD35E,x=0xD362,y=0xD361,battle_raw=0xD057,battle_type=0xD05A,
            current_opponent=0xD059,trainer_no=0xD05D,badges=0xD356,status5=0xD730,
            simulated=rocket_movement.SIMULATED_JOYPAD_INDEX_ADDRESS,
            ignored=rocket_movement.JOY_IGNORE_ADDRESS,script=cfg['script'])
        ids={cfg['won']}|({cfg['auto']} if cfg['auto'] is not None else set())
        if map_id==33:ids|={0x520,0x521,0x527}
        addresses.update({f'event_{i//8}':0xD747+i//8 for i in ids})
        first={k:pyboy.memory[a] for k,a in addresses.items()}
        second={k:pyboy.memory[a] for k,a in addresses.items()};after=pyboy.frame_count
    except Exception:return _invalid(observation_frame,'getter_failed')
    if any(not _int(v,0,255) for sample in (first,second) for v in sample.values()):return _invalid(observation_frame,'byte_invalid')
    if not _int(after) or after!=before or first!=second:return _invalid(observation_frame,'frame_or_bytes_changed')
    if first['map_id']!=map_id:return _invalid(observation_frame,'map_changed')
    events={str(i):bool(first[f'event_{i//8}']&(1<<(i%8))) for i in ids}
    return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,observation_frame=before,
        frame_before=before,frame_after=after,owner_id=id(pyboy),read_valid=True,read_error=None,
        location={k:first[k] for k in ('map_id','x','y')},values=first,events=events,live_calibrated=False)


def _signature(step):
    if (type(step) is not dict or type(step.get('id')) is not str
            or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',step['id']) is None
            or step.get('kind')!='interact' or type(step.get('map_id')) is not int
            or step['map_id'] not in CONFIG or step.get('await_script_event') is not True
            or any(k in step for k in ('item','badge','mechanic','terminal','next_map','nextmap'))):return None
    cfg=CONFIG[step['map_id']]
    if (type(step.get('target')) is not list or step['target']!=cfg['target']
            or any(type(v) is not int for v in step['target']) or step.get('face')!=cfg['face']
            or step.get('event')!=cfg['event']):return None
    return (step['id'],step['map_id'],tuple(step['target']),step['face'],step['event'])


def _text(text):
    if (type(text) is not dict or text.get('profile')!=TEXT_PROFILE or type(text.get('window_visible')) is not bool):return None
    cells=text.get('cells')
    if (type(cells) is not list or len(cells)!=18 or any(type(row) is not list or len(row)!=20
            or any(type(c) is not str or len(c)!=1 for c in row) for row in cells)):return None
    rows=[''.join(row) for row in cells]
    indices=[i for i,row in enumerate(rows) if re.search(r'[A-Za-z0-9]{2,}',row)][:12]
    if text.get('lines')!=[rows[i].rstrip() for i in indices] or text.get('line_rows')!=indices:return None
    blank=all(row==' '*20 for row in rows)
    valid=text.get('read_valid') is True and text.get('alignment_verified') is True and text.get('read_error') is None
    silhouette=(blank and text['window_visible'] is False and text.get('read_valid') is False
        and text.get('alignment_verified') is False and text.get('read_error')=='visible_tile_alignment_incomplete')
    return (blank and text['window_visible'] is False) if valid or silhouette else None


def _lance_path():
    x,y=24,16;out={(x,y)}
    for dx,dy,n in ((0,-1,12),(-1,0,12),(0,1,7),(-1,0,6)):
        for _ in range(n):x+=dx;y+=dy;out.add((x,y))
    return out


class NativeWaitController:
    def __init__(self,step,*,owner):
        signature=_signature(step)
        if signature is None or owner is None:raise ValueError('Exact parent-owned native wait step required')
        self.signature,self.step,self.owner=signature,deepcopy(step),owner
        self.started=self.last_now=None;self.last_frame=-1;self.packet=None
        self.calls=0;self.elapsed=0.;self.error=None;self.waiting=False;self.intro_handoff=False

    def _review(self,reason):
        if self.error is None:self.error=reason
        self.waiting=True
        return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
            review_reason='league_native_wait_'+self.error,source_commit=SOURCE_COMMIT)

    def context(self,state,step,text,signal,*,owner,now):
        if self.error is not None:return self._review(self.error)
        if owner is not self.owner:return self._review('owner_changed')
        if _signature(step)!=self.signature or step!=self.step:return self._review('bound_step_changed')
        if not _clock(now) or self.last_now is not None and now<self.last_now:return self._review('clock_regressed_or_invalid')
        frame=state.get('frame') if type(state) is dict else None
        if not _int(frame) or frame<self.last_frame:return self._review('frame_invalid_or_regressed')
        # A retained owner counts native WAIT time, not the existing battle's
        # dialogue/attacks. No counter or clock is reset at handoff/re-entry.
        if self.last_now is not None and self.waiting:self.elapsed+=now-self.last_now
        if self.started is None:self.started=now
        self.last_now=now
        if self.calls>MAX_CALLS or self.elapsed>MAX_SECONDS:return self._review('budget_exhausted')
        cfg=CONFIG[step['map_id']];loc=state.get('location');runtime=state.get('battle_state');p=state.get('progress')
        if (type(signal) is not dict or signal.get('profile')!=PROFILE or signal.get('source_commit')!=SOURCE_COMMIT
                or signal.get('read_valid') is not True or signal.get('read_error') is not None
                or type(signal.get('owner_id')) is not int or signal['owner_id']!=id(owner)
                or any(not _int(signal.get(k)) or signal[k]!=frame for k in ('observation_frame','frame_before','frame_after'))
                or type(loc) is not dict or any(not _int(loc.get(k),0,255) for k in ('map_id','x','y'))
                or {k:loc[k] for k in ('map_id','x','y')}!=signal.get('location') or loc['map_id']!=step['map_id']
                or type(runtime) is not dict or not _int(runtime.get('observation_frame')) or runtime['observation_frame']!=frame):
            return self._review('same_frame_signal_location_unverified')
        for packet in (p,loc,text):
            if type(packet) is not dict:return self._review('original_packet_required')
            if 'observation_frame' in packet and (not _int(packet['observation_frame']) or packet['observation_frame']!=frame):return self._review('packet_frame_disagrees')
        party=_party(p)
        if (party is None or len(party)!=6 or any(m['hp']<=0 for m in party)):
            return self._review('party_or_existing_loss_guard_required')
        values=signal.get('values');events=signal.get('events')
        if type(values) is not dict or type(events) is not dict:return self._review('native_packet_unverified')
        if any(not _int(values.get(k),0,255) for k in ('script','battle_raw','battle_type','current_opponent','trainer_no','badges','status5','simulated','ignored')):
            return self._review('typed_signal_values_unverified')
        if values['badges']!=255 or values['ignored'] not in (0,0xF0,0xFF):return self._review('badges_or_input_mask_unverified')
        required=[str(cfg['won'])]+([str(cfg['auto'])] if cfg['auto'] is not None else [])
        if step['map_id']==33:required+=['1312','1313','1319']
        if any(type(events.get(k)) is not bool for k in required):return self._review('native_events_unverified')
        if any(not _int(values.get('event_'+str(int(k)//8)),0,255)
                or events[k]!=bool(values['event_'+str(int(k)//8)]&(1<<(int(k)%8))) for k in required):
            return self._review('native_event_bytes_disagree')
        won=events[str(cfg['won'])]
        named=p.get('story_event_bits',{})
        if type(named) is not dict or cfg['event'] in named and named[cfg['event']] is not won:return self._review('event_packet_disagrees')
        packet=deepcopy((loc,runtime,p,text,signal))
        if self.last_frame==frame and packet!=self.packet:return self._review('same_frame_packet_conflict')
        self.last_frame,self.packet=frame,packet
        raw=values['battle_raw'];script=values['script'];point=(loc['x'],loc['y'])
        if type(runtime.get('raw')) is not int or runtime['raw']!=raw:return self._review('runtime_battle_disagrees')
        if raw==1:return self._review('wild_battle_outside_contract')
        if raw==2:
            allowed_scripts={5} if step['map_id']==33 else {3} if step['map_id']==120 else {1,2}
            if (point!=tuple(cfg['target']) or runtime.get('kind')!='trainer' or runtime.get('active') is not True
                    or script not in allowed_scripts
                    or values['battle_type']!=0 or values['current_opponent']!=cfg['opponent']
                    or not ((10<=values['trainer_no']<=12) if step['map_id']==33 else
                            (1<=values['trainer_no']<=(3 if step['map_id']==120 else 1)))):
                return self._review('trainer_intro_unverified')
            if step['map_id']==33 and (won or events['1312'] or not events['1313'] or not events['1319']):
                return self._review('route22_second_rival_events_or_script_unverified')
            if self.intro_handoff:
                self.waiting=False;return None  # Existing battle owns every later text/animation.
            blank=_text(text)
            if blank is None:return self._review('native_packet_unverified')
            if not blank:
                self.intro_handoff=True;self.waiting=False;return None
            return self._wait('blank_trainer_intro')
        if raw!=0 or runtime.get('kind')!='none' or runtime.get('active') is not False:return self._review('nonbattle_unverified')
        blank=_text(text)
        if blank is None:return self._review('native_packet_unverified')
        if step['map_id']==33:
            if point!=(29,4):return self._review('route22_trigger_changed')
            if script in (4,5) and blank is False and not text.get('lines'):
                return self._wait('empty_native_dialogue_window')
            if script==7 and won and not events['1313'] and not events['1319']:
                self.waiting=False;return None
            if script==6 and won:return self._wait('rival_native_exit')
            if script==5 and won:
                if blank:return self._wait('rival_native_postbattle')
                self.waiting=False;return None
            if script not in (0,4,5) or won or events['1312'] or not events['1313'] or not events['1319']:
                return self._review('route22_second_rival_events_or_script_unverified')
            if values['simulated']!=0:return self._review('route22_unexpected_player_autowalk')
            if script==4 and not values['status5']&1 and not blank:
                self.waiting=False;return None
            return self._wait('rival_native_approach_or_intro')
        if won:
            self.waiting=False;return None  # Event alone is never a completion receipt.
        if step['map_id'] in (245,246,247):
            if script==3 and point in {(x,y) for x in (4,5) for y in range(5,12)} and values['simulated']<=6:
                return self._wait('elite_native_six_up')
            if script==0 and point in {(4,11),(5,11)} and not events[str(cfg['auto'])] and values['simulated']==0:
                return self._wait('elite_native_entry_pending')
        elif step['map_id']==113:
            if script==3 and point in _lance_path() and values['simulated']<=37:return self._wait('lance_native_rle')
            if script==0 and point==(24,16) and values['simulated']==0:return self._wait('lance_native_entry_pending')
        elif step['map_id']==120:
            if script in (1,2) and point in {(3,7),(3,6),(4,6),(4,5),(4,4),(4,3)} and values['simulated']<=5:
                return self._wait('champion_native_entry')
        if script==0 and values['simulated']==0 and not values['status5']&1:
            self.waiting=False;return None
        if (script in (1,2) and point==tuple(cfg['target'])
                and values['simulated']==0 and not values['status5']&1):
            if blank:return self._wait('trainer_native_intro_pending')
            self.waiting=False;return None
        return self._review('native_script_or_position_unverified')

    def _wait(self,reason):
        self.calls+=1
        if self.calls>MAX_CALLS:return self._review('budget_exhausted')
        self.waiting=True
        cfg=CONFIG[self.signature[1]]
        return dict(phase='overworld',objective='Wait.',available_actions=['wait'],
            source_coordinate_script_wait=True,native_wait_reason=reason,native_wait_calls=self.calls,
            route_step=self.signature[0],source_commit=SOURCE_COMMIT,
            source=f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/scripts/{cfg["source"]}.asm',
            enemy_turn_resolved=False,survival_approved=False)


def context(pyboy,state,step,text,previous,*,now=None):
    """Route adapter. Retain controller, error, owner and budget across reloads."""
    signature=_signature(step)
    sid=step.get('id') if type(step) is dict else None
    active=[c for key,c in _WAITS.items() if c.waiting and key!=sid]
    if active:return active[0]._review('active_step_owner_changed')
    if signature is None:
        if type(sid) is str and sid in _WAITS:return _WAITS[sid]._review('bound_step_changed')
        return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],review_reason='league_native_wait_fixed_step_required')
    c=_WAITS.get(sid)
    if c is None:c=NativeWaitController(step,owner=pyboy);_WAITS[sid]=c
    c.__class__=NativeWaitController
    if type(previous) not in (list,tuple) or any(type(a) is not str or a not in {'a','b','up','down','left','right','start','wait'} for a in previous):return c._review('actual_previous_unverified')
    try:
        from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
        signal=read_native_signal(pyboy,observation_frame=state.get('frame') if type(state) is dict else None,constants=sdk)
    except Exception:return c._review('readonly_signal_failed')
    return c.context(state,step,text,signal,owner=pyboy,now=time.monotonic() if now is None else now)
