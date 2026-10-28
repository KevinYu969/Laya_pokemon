"""Source-scoped Route22/E4 native movement and blank-intro WAIT only.

No keys, ticks, RAM writes, battle/route completion or victory certification.
Caller keeps loss/health guards and existing battle/dialogue handling first.
"""
from copy import deepcopy
import math
import hashlib
import json
import re
import time

from .mart_purchase import _party
from . import rocket_movement

SOURCE_COMMIT='a53671100ec22e5394ff26ec028d0812a238dae2'
PROFILE='red-en-route22-league-native-wait-v1-candidate'
TEXT_PROFILE='gen1-visible-tile-text-candidates-v1-unvalidated'
_CONTRACTIONS=("'d","'l","'s","'t","'v","'r","'m")
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


def _name(raw,decoding):
    if 0x50 not in raw:return None
    end=raw.index(0x50)
    if not 1<=end<=7:return None
    chars=[decoding.get(v,'') for v in raw[:end]]
    return ''.join(chars) if all(type(c) is str and len(c)==1 and c.isascii() and c.isalpha() for c in chars) else None


def _cells(value):
    """Source charmap greedy contractions; only source-generated positions pass."""
    value=value.replace('#','POKé');out=[]
    while value:
        token=next((s for s in _CONTRACTIONS if value.startswith(s)),None)
        if token is None:token=value[0]
        out.append(token.upper());value=value[len(token):]
    return tuple(out)


def route22_pages(names,kind):
    player,rival=names['player'],names['rival']
    pairs=([(rival+': What?',player+'! What a'),(player+'! What a','surprise to see'),
        ('surprise to see','you here!'),("So you're going to",'#MON LEAGUE?'),
        ('You collected all','the BADGEs too?'),('the BADGEs too?',"That's cool!"),
        ("Then I'll whip you",player+' as a'),(player+' as a','warm up for'),
        ('warm up for','#MON LEAGUE!'),('Come on!','')] if kind=='before' else
        [('That loosened me',"up! I'm ready for"),("up! I'm ready for",'#MON LEAGUE!'),
         (player+', you need','more practice!'),('But hey, you know',"that! I'm out of"),
         ("that! I'm out of",'here. Smell ya!')])
    return tuple((_cells(a),_cells(b)) for a,b in pairs)


def _route22_page(text,expected):
    if (type(text) is not dict or text.get('profile')!=TEXT_PROFILE
            or text.get('read_valid') is not True or text.get('alignment_verified') is not True
            or text.get('read_error') is not None or text.get('window_visible') is not True):return None
    cells=text.get('cells')
    if (type(cells) is not list or len(cells)!=18 or any(type(row) is not list or len(row)!=20
            or any(type(c) is not str for c in row) for row in cells)):return None
    rows=[''.join(r) for r in cells]
    indices=[i for i,row in enumerate(rows) if re.search(r'[A-Za-z0-9]{2,}',row)][:12]
    if text.get('line_rows')!=indices or text.get('lines')!=[rows[i].rstrip() for i in indices]:return None
    canvas=[[' ']*20 for _ in range(18)]
    for y,tokens in zip((14,16),expected):
        if len(tokens)>18:return None
        canvas[y][1:1+len(tokens)]=tokens
    normalized=tuple(tuple(c.upper() for c in row) for row in cells)
    arrow=cells[16][18]
    if arrow not in (' ','▼'):return None
    canvas[16][18]=arrow
    if any(ch not in (' ',canvas[y][x]) for y,row in enumerate(normalized) for x,ch in enumerate(row)):return None
    for y,tokens in zip((14,16),expected):
        actual=list(normalized[y][1:19 if y==14 else 18])
        while actual and actual[-1]==' ':actual.pop()
        if tuple(actual)!=tokens[:len(actual)]:return None
    first_full=normalized[14]==tuple(canvas[14])
    if any(ch!=' ' for ch in normalized[16][:18]) and not first_full:return None
    full=normalized==tuple(tuple(r) for r in canvas)
    if arrow=='▼' and not full:return None
    return dict(rows=normalized,full=full,arrow=arrow=='▼',empty=not any(c!=' ' for row in normalized for c in row))


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
        if map_id==33:
            ids|={0x520,0x521,0x527}
            if _get(constants,'PLAYER_NAME_ADDRESS')!=0xD158:return _invalid(observation_frame,'sdk_player_name_anchor_unverified')
            addresses.update({f'player_name_{i}':0xD158+i for i in range(11)})
            addresses.update({f'rival_name_{i}':0xD356-12+i for i in range(11)})
        addresses.update({f'event_{i//8}':0xD747+i//8 for i in ids})
        first={k:pyboy.memory[a] for k,a in addresses.items()}
        second={k:pyboy.memory[a] for k,a in addresses.items()};after=pyboy.frame_count
    except Exception:return _invalid(observation_frame,'getter_failed')
    if any(not _int(v,0,255) for sample in (first,second) for v in sample.values()):return _invalid(observation_frame,'byte_invalid')
    if not _int(after) or after!=before or first!=second:return _invalid(observation_frame,'frame_or_bytes_changed')
    if first['map_id']!=map_id:return _invalid(observation_frame,'map_changed')
    events={str(i):bool(first[f'event_{i//8}']&(1<<(i%8))) for i in ids}
    names=None
    if map_id==33:
        decoding=_get(constants,'POKEMON_TEXT_DECODING')
        if not isinstance(decoding,dict):return _invalid(observation_frame,'sdk_name_decoding_unverified')
        names={k:_name([first[f'{k}_name_{i}'] for i in range(11)],decoding) for k in ('player','rival')}
        if any(v is None for v in names.values()):return _invalid(observation_frame,'source_names_unverified')
    return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,observation_frame=before,
        frame_before=before,frame_after=after,owner_id=id(pyboy),read_valid=True,read_error=None,
        location={k:first[k] for k in ('map_id','x','y')},values=first,events=events,names=names,live_calibrated=False)


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
        if getattr(self,'reviewed_adoption',None) is not None:
            return self._reviewed_failure(reason)
        if self.error is None:self.error=reason
        self.waiting=True
        return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
            review_reason='league_native_wait_'+self.error,source_commit=SOURCE_COMMIT)

    def context(self,state,step,text,signal,*,owner,now,previous=(),review_capsule=None,checkpoint_resume_capsule=None):
        if checkpoint_resume_capsule is not None and review_capsule is not None:
            return self._review('checkpoint_resume_hot_capsule_conflict')
        if checkpoint_resume_capsule is not None or getattr(self,'checkpoint_resume_history',None) is not None:
            resumed=self._checkpoint_resume_context(state,step,text,signal,owner,now,previous,checkpoint_resume_capsule)
            if resumed is not None:return resumed
        if getattr(self,'reviewed_recovery_error',None) is not None:
            return self._reviewed_failure(self.reviewed_recovery_error)
        if review_capsule is not None or getattr(self,'reviewed_adoption',None) is not None:
            adopted=self._reviewed_adoption_context(state,step,text,signal,owner,now,previous,review_capsule)
            if adopted is not None:return adopted
        if self.error is not None and not (getattr(self,'reviewed_adoption',None) or {}).get('adopted'):
            return self._review(self.error)
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
        if (step['map_id']==33 and raw==0 and script==5 and point==(29,4) and not won
                and values['current_opponent']==242 and not events['1312'] and events['1313'] and events['1319']):
            self._route22_leave('before',frame,previous)  # 原生進場可延後raw2；即時保存最後真A。
        if raw==2:
            if step['map_id']==33 and not self._route22_leave('before',frame,previous):return self._review('native_dialogue_advanced_without_actual_a')
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
            if blank is False and not text.get('lines'):
                return self._wait('empty_trainer_intro_window')
            if not blank:
                self.intro_handoff=True;self.waiting=False;return None
            return self._wait('blank_trainer_intro')
        if raw!=0 or runtime.get('kind')!='none' or runtime.get('active') is not False:return self._review('nonbattle_unverified')
        if step['map_id']==33:
            if point!=(29,4):return self._review('route22_trigger_changed')
            if script==4 and not won and not events['1312'] and events['1313'] and events['1319'] and not values['status5']&1:
                return self._route22_dialogue('before',text,signal,frame,previous)
            if script==5 and won:
                return self._route22_dialogue('after',text,signal,frame,previous)
            if script in (6,7) and not self._route22_leave('after',frame,previous):return self._review('native_dialogue_advanced_without_actual_a')
            blank=_text(text)
            if blank is None:return self._review('native_packet_unverified')
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
        blank=_text(text)
        if blank is None:return self._review('native_packet_unverified')
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



    @staticmethod
    def checkpoint_progress_sha256(progress):
        if type(progress) is not dict:return None
        party=_party(progress)
        if party is None or len(party)!=6 or any(m['hp']<=0 for m in party):return None
        if 'badges_raw' in progress and (type(progress['badges_raw']) is not int or progress['badges_raw']!=255):return None
        try:raw=json.dumps(progress,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('utf-8')
        except (TypeError,ValueError,UnicodeError):return None
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _checkpoint_capsule_valid(capsule,step_id):
        return (type(capsule) is dict and set(capsule)=={
            'kind','source_frame','initial_frame','page','names','location','step_id',
            'source_checkpoint_sha256','source_review_sha256','source_progress_sha256'}
            and capsule.get('kind')=='route22_checkpoint_page3_resume_v1'
            and type(capsule.get('source_frame')) is int and capsule['source_frame']==107929
            and type(capsule.get('initial_frame')) is int and capsule['initial_frame']==1
            and type(capsule.get('page')) is int and capsule['page']==3
            and type(capsule.get('step_id')) is str and capsule['step_id']==step_id
            and capsule.get('names')=={'player':'KEVIN','rival':'BLUE'}
            and type(capsule.get('location')) is dict and capsule['location']=={'map_id':33,'x':29,'y':4}
            and all(type(v) is int for v in capsule['location'].values())
            and all(type(capsule.get(k)) is str and re.fullmatch('[0-9a-f]{64}',capsule[k]) is not None
                    for k in ('source_checkpoint_sha256','source_review_sha256','source_progress_sha256')))

    def _checkpoint_diagnostics(self):
        h=getattr(self,'checkpoint_resume_history',None)
        if h is None:return {}
        cap=h['capsule']
        return dict(checkpoint_resume_history=dict(kind=cap['kind'],source_frame=cap['source_frame'],
            initial_frame=cap['initial_frame'],observation_frame=self.last_frame,
            source_checkpoint_sha256=cap['source_checkpoint_sha256'],source_review_sha256=cap['source_review_sha256'],
            source_progress_sha256=cap['source_progress_sha256'],previous_review='native_packet_unverified',
            epoch='new_controller_budget',old_instance_recovered=False,older_spent_counters_recoverable=False,
            calls=self.calls,elapsed=self.elapsed,adopted_page=3 if h['adopted'] else None))

    def _checkpoint_resume_context(self,state,step,text,signal,owner,now,previous,capsule):
        if self.error is not None:return self._review(self.error)
        h=getattr(self,'checkpoint_resume_history',None)
        cap=h['capsule'] if h is not None and capsule is None else capsule
        if not self._checkpoint_capsule_valid(cap,self.signature[0]):return self._review('checkpoint_resume_capsule_unverified')
        if h is not None and cap!=h['capsule']:return self._review('checkpoint_resume_capsule_changed')
        if getattr(self,'reviewed_adoption',None) is not None or getattr(self,'reviewed_recovery_error',None) is not None:
            return self._review('checkpoint_resume_hot_instance_forbidden')
        if (owner is not self.owner or _signature(step)!=self.signature or step!=self.step
                or self.signature[1:]!=(33,(29,4),'left','beat_route22_rival_2nd_battle')):
            return self._review('checkpoint_resume_owner_or_step_changed')
        if not _clock(now) or self.last_now is not None and now<self.last_now:return self._review('checkpoint_resume_clock_invalid')
        if h is not None and h['adopted']:return None
        frame=state.get('frame') if type(state) is dict else None
        if type(frame) is not int or state.get('location')!=cap['location']:return self._review('checkpoint_resume_state_unverified')
        runtime=state.get('battle_state')
        if (type(runtime) is not dict or type(runtime.get('raw')) is not int or runtime['raw']!=0
                or runtime.get('kind')!='none' or runtime.get('active') is not False
                or type(runtime.get('observation_frame')) is not int or runtime['observation_frame']!=frame):
            return self._review('checkpoint_resume_runtime_unverified')
        if not self._adoption_signal_valid(signal,frame,names_required=True):return self._review('checkpoint_resume_source_unverified')
        progress=state.get('progress')
        if self.checkpoint_progress_sha256(progress)!=cap['source_progress_sha256']:return self._review('checkpoint_resume_progress_sha256_mismatch')
        page=_route22_page(text,route22_pages(cap['names'],'before')[3])
        if page is None or not page['full'] or h is None and not page['arrow']:return self._review('checkpoint_resume_page3_unverified')
        packet=deepcopy((state['location'],runtime,progress,text,signal))
        if h is None:
            if (frame!=1 or self.started is not None or self.last_now is not None or self.last_frame!=-1
                    or self.packet is not None or self.calls!=0 or self.elapsed!=0 or self.waiting is not False
                    or self.intro_handoff is not False or getattr(self,'route22_dialogues',None)):
                return self._review('checkpoint_resume_new_instance_required')
            self.started=self.last_now=now;self.last_frame=frame;self.packet=packet
            self.checkpoint_resume_history=dict(capsule=deepcopy(cap),bootstrap_frame=frame,adopted=False,
                previous_review='native_packet_unverified',epoch='new_controller_budget',
                old_instance_recovered=False,older_spent_counters_recoverable=False)
            return self._wait('checkpoint_resume_bootstrap_wait')
        if frame==h['bootstrap_frame']:
            if packet!=self.packet:return self._review('checkpoint_resume_same_frame_packet_conflict')
            if self.waiting:self.elapsed+=now-self.last_now
            self.last_now=now
            if self.elapsed>MAX_SECONDS:return self._review('budget_exhausted')
            return self._wait('checkpoint_resume_requires_true_fresh_frame')
        if frame<h['bootstrap_frame'] or frame-h['bootstrap_frame']>128:
            return self._review('checkpoint_resume_fresh_frame_unverified')
        if type(previous) not in (list,tuple) or not previous or previous[-1]!='wait':return self._review('checkpoint_resume_actual_wait_required')
        if getattr(self,'route22_dialogues',None):return self._review('checkpoint_resume_existing_dialogue_unverified')
        if not hasattr(self,'route22_dialogues'):self.route22_dialogues={}
        self.route22_dialogues['before']=dict(names=deepcopy(cap['names']),page=3,pending=None,done_frame=None)
        h['adopted']=True;h['adopted_frame']=frame
        return None  # Normal new-session context charges elapsed and observes arrow blink before any A.

    def _reviewed_diagnostics(self):
        record=getattr(self,'reviewed_adoption',None)
        if record is None:return {}
        return dict(route22_reviewed_adoption=dict(kind=record['capsule']['kind'],
            source_frame=record['issued_frame'],observation_frame=self.last_frame,
            source_calls=record['source_calls'],source_elapsed=record['source_elapsed'],
            calls=self.calls,elapsed=self.elapsed,historical_error=self.error,
            adopted_page=3 if record['adopted'] else None))

    def _reviewed_failure(self,reason):
        if getattr(self,'reviewed_recovery_error',None) is None:self.reviewed_recovery_error=reason
        self.waiting=True
        return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
            review_reason='league_native_wait_'+self.reviewed_recovery_error,
            historical_review_error=self.error,source_commit=SOURCE_COMMIT)

    @staticmethod
    def _adoption_capsule_valid(capsule,step_id):
        return (type(capsule) is dict
            and set(capsule)=={'kind','source_frame','expected_error','step_id','location','names','page'}
            and capsule.get('kind')=='route22_before_page3_schema_adoption_v1'
            and type(capsule.get('source_frame')) is int and capsule['source_frame']==107929
            and capsule.get('expected_error')=='native_packet_unverified'
            and type(capsule.get('step_id')) is str and capsule['step_id']==step_id
            and type(capsule.get('page')) is int and capsule['page']==3
            and type(capsule.get('location')) is dict and capsule['location']=={'map_id':33,'x':29,'y':4}
            and all(type(v) is int for v in capsule['location'].values())
            and capsule.get('names')=={'player':'KEVIN','rival':'BLUE'})

    def _adoption_signal_valid(self,signal,frame,*,names_required):
        if (type(signal) is not dict or signal.get('profile')!=PROFILE
                or signal.get('source_commit')!=SOURCE_COMMIT or signal.get('read_valid') is not True
                or signal.get('read_error') is not None or signal.get('owner_id')!=id(self.owner)
                or type(signal.get('owner_id')) is not int
                or any(type(signal.get(k)) is not int or signal[k]!=frame
                       for k in ('observation_frame','frame_before','frame_after'))
                or signal.get('location')!={'map_id':33,'x':29,'y':4}):return False
        values,events=signal.get('values'),signal.get('events')
        expected=dict(map_id=33,x=29,y=4,battle_raw=0,battle_type=0,badges=255,
                      status5=0,simulated=0,ignored=0,script=4,event_164=130)
        if (type(values) is not dict or any(type(values.get(k)) is not int or values[k]!=v for k,v in expected.items())
                or type(events) is not dict
                or any(type(events.get(k)) is not bool or events[k] is not v for k,v in
                       {'1312':False,'1313':True,'1318':False,'1319':True}.items())):return False
        if names_required and signal.get('names')!={'player':'KEVIN','rival':'BLUE'}:return False
        return True

    @staticmethod
    def _adoption_progress(progress):
        if type(progress) is not dict:return None
        party=_party(progress)
        if party is None or len(party)!=6 or any(m['hp']<=0 for m in party):return None
        if 'badges_raw' in progress and (type(progress['badges_raw']) is not int or progress['badges_raw']!=255):return None
        return {k:v for k,v in progress.items() if k!='observation_frame'}

    def _reviewed_adoption_context(self,state,step,text,signal,owner,now,previous,capsule):
        prior=getattr(self,'reviewed_adoption',None)
        if getattr(self,'reviewed_recovery_error',None) is not None:
            return self._reviewed_failure(self.reviewed_recovery_error)
        expected=prior['capsule'] if prior is not None and capsule is None else capsule
        if not self._adoption_capsule_valid(expected,self.signature[0]):return self._reviewed_failure('reviewed_adoption_capsule_unverified')
        if prior is not None and expected!=prior['capsule']:return self._reviewed_failure('reviewed_adoption_capsule_changed')
        if (owner is not self.owner or _signature(step)!=self.signature or step!=self.step
                or self.signature[1:]!=(33,(29,4),'left','beat_route22_rival_2nd_battle')):
            return self._reviewed_failure('reviewed_adoption_owner_or_step_changed')
        if not _clock(now) or self.last_now is not None and now<self.last_now:
            return self._reviewed_failure('reviewed_adoption_clock_invalid')
        if prior is not None and self.error!=prior['capsule']['expected_error']:
            return self._reviewed_failure('reviewed_adoption_historical_error_changed')
        if prior is not None and prior['adopted']:
            return None  # The unchanged source controller owns all subsequent pages/battle.
        if self.error!='native_packet_unverified' or self.intro_handoff is not False:
            return self._reviewed_failure('reviewed_adoption_historical_error_unverified')
        if (type(state) is not dict or type(state.get('frame')) is not int
                or state.get('location')!={'map_id':33,'x':29,'y':4}):
            return self._reviewed_failure('reviewed_adoption_state_unverified')
        frame=state['frame'];runtime=state.get('battle_state')
        if (type(runtime) is not dict or runtime.get('raw')!=0 or type(runtime.get('raw')) is not int
                or runtime.get('kind')!='none' or runtime.get('active') is not False
                or type(runtime.get('observation_frame')) is not int or runtime['observation_frame']!=frame):
            return self._reviewed_failure('reviewed_adoption_runtime_unverified')
        if not self._adoption_signal_valid(signal,frame,names_required=True):return self._reviewed_failure('reviewed_adoption_source_unverified')
        page=_route22_page(text,route22_pages(expected['names'],'before')[3])
        if page is None or page['full'] is not True or prior is None and page['arrow'] is not True:
            return self._reviewed_failure('reviewed_adoption_page3_unverified')
        packet=self.packet if prior is None else prior['source_packet']
        if (self.last_frame!=107929 or type(packet) is not tuple or len(packet)!=5
                or packet[0]!={'map_id':33,'x':29,'y':4}
                or type(packet[1]) is not dict or packet[1].get('raw')!=0
                or packet[1].get('observation_frame')!=107929
                or not self._adoption_signal_valid(packet[4],107929,names_required=False)):
            return self._reviewed_failure('reviewed_adoption_original_packet_unverified')
        old_page=_route22_page(packet[3],route22_pages(expected['names'],'before')[3])
        if old_page is None or not old_page['full'] or not old_page['arrow']:
            return self._reviewed_failure('reviewed_adoption_original_page_unverified')
        before=self._adoption_progress(packet[2]);current=self._adoption_progress(state.get('progress'))
        if before is None or current is None or before!=current:return self._reviewed_failure('reviewed_adoption_resources_changed')
        if self.calls>MAX_CALLS or self.elapsed>MAX_SECONDS:return self._reviewed_failure('budget_exhausted')
        if prior is None:
            if frame!=107929:return self._reviewed_failure('reviewed_adoption_source_frame_unverified')
            if getattr(self,'route22_dialogues',None):return self._reviewed_failure('reviewed_adoption_existing_dialogue_unverified')
            self.reviewed_adoption=dict(capsule=deepcopy(expected),issued=True,issued_frame=frame,adopted=False,
                source_packet=packet,source_calls=self.calls,source_elapsed=self.elapsed,source_started=self.started,
                source_last_now=self.last_now,source_intro_handoff=self.intro_handoff)
            self.reviewed_recovery_error=None
            return self._wait('reviewed_adoption_bootstrap_wait')
        if frame==prior['issued_frame']:return self._wait('reviewed_adoption_requires_true_fresh_frame')
        if frame<=prior['issued_frame'] or frame-prior['issued_frame']>128:
            return self._reviewed_failure('reviewed_adoption_fresh_frame_unverified')
        if type(previous) not in (list,tuple) or not previous or previous[-1]!='wait':
            return self._reviewed_failure('reviewed_adoption_actual_wait_required')
        if not hasattr(self,'route22_dialogues'):self.route22_dialogues={}
        if self.route22_dialogues:return self._reviewed_failure('reviewed_adoption_existing_dialogue_unverified')
        self.route22_dialogues['before']=dict(names=deepcopy(expected['names']),page=3,pending=None,done_frame=None)
        prior['adopted']=True;prior['adopted_frame']=frame
        return None  # Normal context now charges the retained clock and offers the real page3 A.

    def _route22_leave(self,kind,frame,previous):
        d=getattr(self,'route22_dialogues',{}).get(kind)
        if d is None:return True  # Genuine battle can predate this UI candidate.
        pending=d['pending']
        if pending is not None and pending['final'] and frame>pending['frame'] and previous and previous[-1]=='a':pending['executed']=True
        return pending is not None and pending['final'] and pending['executed']

    def _route22_dialogue(self,kind,text,signal,frame,previous):
        names=signal.get('names')
        if (type(names) is not dict or set(names)!={'player','rival'}
                or any(type(v) is not str or re.fullmatch(r'[A-Za-z]{1,7}',v) is None for v in names.values())):
            return self._review('source_names_unverified')
        if not hasattr(self,'route22_dialogues'):self.route22_dialogues={}
        pages=route22_pages(names,kind);d=self.route22_dialogues.get(kind)
        if d is None:
            d=dict(names=deepcopy(names),page=0,pending=None,done_frame=None);self.route22_dialogues[kind]=d
        if d['names']!=names:return self._review('source_names_changed')
        page=_route22_page(text,pages[d['page']]);pending=d['pending']
        if pending is not None:
            if frame==pending['frame']:return self._wait('native_dialogue_same_frame_no_action')
            if not pending['executed'] and frame>pending['frame'] and previous and previous[-1]=='a':pending['executed']=True
            if not pending['executed']:
                if page is None:return self._review('native_page_changed_without_actual_a')
                if not page['full'] or not page['arrow'] and not pending['final']:return self._wait('native_dialogue_prompt_blink')
                return self._route22_offer(kind,d,frame,page)
            if page is not None:return self._wait('native_dialogue_after_actual_a')
            if pending['final']:return self._review('native_dialogue_unknown_after_done')
            d['page']+=1;d['pending']=None;d['done_frame']=None
            page=_route22_page(text,pages[d['page']])
        if page is None:return self._review('native_dialogue_page_unverified')
        if not page['full']:
            d['done_frame']=None;return self._wait('native_dialogue_printing')
        final=d['page']==len(pages)-1
        if final:
            if page['arrow']:return self._review('native_done_unexpected_arrow')
            if d['done_frame'] is None:d['done_frame']=frame;return self._wait('native_done_first_full_frame')
            if frame<=d['done_frame']:return self._wait('native_done_requires_fresh_frame')
        elif not page['arrow']:return self._wait('native_dialogue_prompt_blink')
        return self._route22_offer(kind,d,frame,page)

    def _route22_offer(self,kind,d,frame,page):
        self.calls+=1
        if self.calls>MAX_CALLS:return self._review('budget_exhausted')
        self.waiting=True
        final=d['page']==len(route22_pages(d['names'],kind))-1
        d['pending']=dict(frame=frame,rows=page['rows'],executed=False,final=final)
        return dict(phase='dialogue',objective='Confirm the current selection.',available_actions=['a','wait'],
            controller_menu_verified=True,source_native_dialogue=True,native_dialogue_kind=kind,
            native_dialogue_page=d['page'],native_dialogue_final_done=final,source_commit=SOURCE_COMMIT,
            enemy_turn_resolved=False,survival_approved=False,**self._reviewed_diagnostics(),**self._checkpoint_diagnostics())

    def _wait(self,reason):
        self.calls+=1
        if self.calls>MAX_CALLS:return self._review('budget_exhausted')
        self.waiting=True
        cfg=CONFIG[self.signature[1]]
        return dict(phase='overworld',objective='Wait.',available_actions=['wait'],
            source_coordinate_script_wait=True,native_wait_reason=reason,native_wait_calls=self.calls,
            route_step=self.signature[0],source_commit=SOURCE_COMMIT,
            source=f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/scripts/{cfg["source"]}.asm',
            enemy_turn_resolved=False,survival_approved=False,**self._reviewed_diagnostics(),**self._checkpoint_diagnostics())


def restore_reviewed_final_a(c,state,step,signal,capsule):
    """只採父層已核ledger的929→1057收據；未知review不解鎖、不退款。"""
    if capsule is None:return None
    applied=getattr(c,'reviewed_final_a_receipt',None)
    if applied is not None:
        return None if capsule==applied else c._review('final_a_review_capsule_changed')
    keys={'kind','source_frame','offer_frame','ack_frame','step_id','source_steps_sha256','source_review_sha256'}
    if (type(capsule) is not dict or set(capsule)!=keys
            or capsule.get('kind')!='route22_before_final_a_receipt_v1'
            or any(type(capsule.get(k)) is not int or capsule[k]!=v for k,v in
                   {'source_frame':1177,'offer_frame':929,'ack_frame':1057}.items())
            or capsule.get('step_id')!=step.get('id')
            or any(type(capsule.get(k)) is not str or re.fullmatch(r'[a-f0-9]{64}',capsule[k]) is None
                   for k in ('source_steps_sha256','source_review_sha256'))):
        return c._review('final_a_review_capsule_unverified')
    h=getattr(c,'checkpoint_resume_history',None);v=signal.get('values',{});events=signal.get('events',{})
    d=getattr(c,'route22_dialogues',{}).get('before',{});pending=d.get('pending')
    if (c.error!='native_dialogue_advanced_without_actual_a' or type(h) is not dict or h.get('adopted') is not True
            or _signature(step)!=c.signature or step!=c.step or state.get('frame')!=1177 or c.last_frame!=1177
            or state.get('location')!={'map_id':33,'x':29,'y':4} or type(c.packet) is not tuple
            or c.packet[4]!=signal or state.get('progress')!=c.packet[2]
            or signal.get('read_valid') is not True or signal.get('profile')!=PROFILE
            or signal.get('source_commit')!=SOURCE_COMMIT or signal.get('owner_id')!=id(c.owner)
            or any(type(signal.get(k)) is not int or signal[k]!=1177 for k in ('observation_frame','frame_before','frame_after'))
            or signal.get('names')!={'player':'KEVIN','rival':'BLUE'}
            or any(type(v.get(k)) is not int or v[k]!=n for k,n in
                   {'map_id':33,'x':29,'y':4,'battle_raw':2,'battle_type':0,'current_opponent':242,'badges':255,'script':5,'event_164':130}.items())
            or type(v.get('trainer_no')) is not int or not 10<=v['trainer_no']<=12
            or any(type(events.get(k)) is not bool or events[k] is not n for k,n in
                   {'1312':False,'1313':True,'1318':False,'1319':True}.items())
            or d.get('page')!=9 or d.get('names')!={'player':'KEVIN','rival':'BLUE'}
            or type(pending) is not dict or pending.get('frame')!=929 or pending.get('final') is not True
            or pending.get('executed') is not False):
        return c._review('final_a_review_state_unverified')
    expected=[[' ']*20 for _ in range(18)]
    for y,tokens in zip((14,16),route22_pages(d['names'],'before')[9]):expected[y][1:1+len(tokens)]=tokens
    if pending.get('rows')!=tuple(tuple(row) for row in expected):return c._review('final_a_review_source_page_unverified')
    history=getattr(c,'reviewed_error_history',[])
    history.append(dict(error=c.error,source_frame=1177,offer_frame=929,ack_frame=1057,calls=c.calls,elapsed=c.elapsed,
        source_steps_sha256=capsule['source_steps_sha256'],source_review_sha256=capsule['source_review_sha256']))
    c.reviewed_error_history=history;c.reviewed_final_a_receipt=deepcopy(capsule)
    pending['executed']=True;c.error=None
    return None


def context(pyboy,state,step,text,previous,*,now=None,review_capsule=None,checkpoint_resume_capsule=None,final_a_review_capsule=None):
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
    restored=restore_reviewed_final_a(c,state,step,signal,final_a_review_capsule)
    if restored is not None:return restored
    return c.context(state,step,text,signal,owner=pyboy,now=time.monotonic() if now is None else now,previous=previous,review_capsule=review_capsule,checkpoint_resume_capsule=checkpoint_resume_capsule)
