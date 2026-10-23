"""固定紅版沙湖付費入口：只產生離線Laya子目標，不寫記憶體或發按鍵。"""
from copy import deepcopy
from collections.abc import Mapping
import time
import math
import importlib
from . import safari_battle as safari_battle_module
importlib.reload(safari_battle_module)

from .observation import PROFILE
from .party_control import command
from .mart_purchase import _lower as _single_cell_lower, _marks, _money, _positions, _party, _inventory

SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
SOURCE = f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/scripts/SafariZoneGate.asm'
INTENT = {'kind':'safari_entry','map_id':156,'player_x':3,'player_y':3,'fee':500,'balls':30}
PROFILE_SAFARI = 'red-en-safari-source-v1'
_L_CONTRACTION='\ue000'
_PAGES = {
    'welcome': [('WELCOME TO THE','SAFARI ZONE!')],
    'offer': [('FOR JUST ¥500,','YOU CAN CATCH ALL'),
              ('YOU CAN CATCH ALL','THE POKéMON YOU'),
              ('THE POKéMON YOU','WANT IN THE PARK!')],
    'payment': [("THAT'LL BE ¥500",'PLEASE!'),('WE ONLY USE A','SPECIAL POKé BALL'),
                ('SPECIAL POKé BALL','HERE.'),('KEVIN RECEIVED','30 SAFARI BALLS!'),
                ("WE'LL CALL YOU ON",'THE PA WHEN YOU'),('THE PA WHEN YOU','RUN OUT OF TIME'),
                ('RUN OUT OF TIME','OR SAFARI BALLS!')],
    'question': [('WOULD YOU LIKE TO','JOIN THE HUNT?')],
}


def _compact(value):
    return ''.join(value.upper().replace('É','E').split())


def _rows(text):
    """維持20個實體tile；只有付款來源對話中的壓縮'l可用一格表示。"""
    cells=text.get('cells') if isinstance(text,dict) else None
    if (not isinstance(cells,(list,tuple)) or len(cells)!=18
            or any(not isinstance(row,(list,tuple,str)) or len(row)!=20 for row in cells)):
        return None
    rows=[]
    for y,row in enumerate(cells):
        mapped=[]
        for c in row:
            if not isinstance(c,str):return None
            if len(c)==1 and c!=_L_CONTRACTION:mapped.append(c)
            elif y in {14,16} and c=="'l":mapped.append(_L_CONTRACTION)
            else:return None
        rows.append(''.join(mapped).upper())
    return tuple(rows)


def _lower(rows):
    # 語意展開只用於來源頁比對；選單、錢框、游標始終保留實體tile座標。
    value=_single_cell_lower(rows)
    return value.replace(_L_CONTRACTION,"'L") if value is not None else None


def _review(reason):
    return {'phase':'campaign_review','review_reason':reason,'objective':'Wait.','available_actions':['wait']}


def _wait(reason):
    return {'phase':'safari_entry','objective':'Wait.','available_actions':['wait'],
            'safari_entry_stage':reason,'source':SOURCE}


def read_safari_state(pyboy, constants=None):
    """同幀雙讀固定來源欄位；無SDK錨點、未知byte或不一致時保留未知。"""
    result={'profile':PROFILE_SAFARI,'read_valid':False,'observation_frame':getattr(pyboy,'frame_count',None)}
    if constants is None:
        from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    events=getattr(constants,'EVENT_FLAGS',None)
    anchors={'in_safari_zone':0x24F,'safari_game_over':0x24E,'got_hm03':0x880,'got_hm04':0x238}
    if (type(getattr(constants,'EVENT_FLAGS_ADDRESS',None)) is not int
            or constants.EVENT_FLAGS_ADDRESS!=0xD747
            or type(getattr(constants,'STATUS_FLAGS3_ADDRESS',None)) is not int
            or constants.STATUS_FLAGS3_ADDRESS!=0xD72D
            or not isinstance(events,Mapping)
            or any(type(events.get(k)) is not int or events[k]!=v for k,v in anchors.items())
            or type(result['observation_frame']) is not int or result['observation_frame']<0):
        return result
    addresses=(0xD790,0xD70D,0xD70E,0xDA47,0xD61F)
    try:
        before=tuple(pyboy.memory[a] for a in addresses)
        after=tuple(pyboy.memory[a] for a in addresses)
        end_frame=getattr(pyboy,'frame_count',None)
        if (before!=after or type(end_frame) is not int or end_frame!=result['observation_frame']
                or any(type(v) is not int or not 0<=v<=255 for v in before+after)):return result
        flags,hi,lo,balls,script=before
        if balls>30 or (hi<<8|lo)>502 or script>6:return result
    except (AttributeError,IndexError,KeyError,TypeError,ValueError,RuntimeError):return result
    return {**result,'read_valid':True,'in_safari':bool(flags&128),'game_over':bool(flags&64),
            'steps':hi<<8|lo,'balls':balls,'gate_script':script}


def _text_valid(text):
    return (isinstance(text,dict) and text.get('profile')==PROFILE and text.get('read_valid') is True
            and text.get('alignment_verified') is True and text.get('read_error') is None
            and type(text.get('window_visible')) is bool and _rows(text) is not None)


def _safari_valid(safari,frame):
    return (isinstance(safari,dict) and safari.get('profile')==PROFILE_SAFARI
            and safari.get('read_valid') is True
            and type(safari.get('observation_frame')) is int and safari['observation_frame']==frame
            and all(type(safari.get(k)) is bool for k in ('in_safari','game_over'))
            and all(type(safari.get(k)) is int and 0<=safari[k]<=maximum
                    for k,maximum in (('steps',502),('balls',30),('gate_script',6))))


def _page(rows, group):
    return any(_lower(rows)==_compact(a+b) for a,b in _PAGES[group])


def _prefix(rows, group):
    lower=_lower(rows)
    return lower is not None and any(_compact(a+b).startswith(lower) for a,b in _PAGES[group])


def _outside_verified(rows, *, money=None, yesno=False):
    """不允許來源版面外的文字／游標；下方兩行由完整頁白名單另核。"""
    allowed=set((x,y) for y in (14,16) for x in range(1,19))
    if money is not None:
        if not _money(rows,money):return False
        allowed|={(x,0) for x in range(13,18)}|{(x,1) for x in range(12,19)}
    if yesno:
        if _positions(rows,'YES')!=[(16,8)] or _positions(rows,'NO')!=[(16,10)]:return False
        if (rows[8][16:19]!='YES' or rows[10][16:19]!='NO '
                or rows[8][15] not in {' ','▶'} or rows[10][15] not in {' ','▶'}):return False
        allowed|={(x,y) for y in (8,10) for x in range(15,19)}
    return all(c==' ' or (x,y) in allowed for y,row in enumerate(rows) for x,c in enumerate(row))


class SafariEntryController:
    def __init__(self,intent):
        self.intent=deepcopy(intent);self.stage='start';self.baseline=None;self.error=None
        self.started=None;self.calls=0;self.last_frame=-1;self.closed_frames=[];self.last_now=None;self.decode_waits=0

    def fail(self,reason):
        self.error=reason
        return _review(reason)

    def context(self,text,progress,*,location,battle_state,safari,frame,overworld_ready,now=None):
        if self.error:return _review(self.error)
        now=time.monotonic() if now is None else now
        if self.intent!=INTENT or any(type(self.intent.get(k)) is not type(v) for k,v in INTENT.items()):
            return self.fail('safari_entry_intent_unverified')
        if (type(now) not in (int,float) or not math.isfinite(now) or now<0
                or self.last_now is not None and now<self.last_now):
            return self.fail('safari_entry_clock_unverified')
        self.last_now=now
        if self.started is None:self.started=now
        self.calls+=1
        if self.calls>150 or now-self.started>60:return self.fail('safari_entry_budget_exhausted')
        if type(frame) is not int or frame<=self.last_frame:return self.fail('safari_entry_frame_not_advanced')
        self.last_frame=frame
        if (not isinstance(battle_state,dict) or not isinstance(safari,dict)
                or not isinstance(progress,dict) or not isinstance(location,dict)
                or any(type(location.get(k)) is not int for k in ('map_id','x','y'))
                or battle_state.get('kind')!='none' or battle_state.get('active') is not False
                or not _safari_valid(safari,frame)):
            return self.fail('safari_entry_source_or_battle_unverified')
        if safari['game_over']:return self.fail('safari_entry_game_over_unexpected')
        party=_party(progress);inventory=_inventory(progress.get('inventory'))
        if party is None or inventory is None or type(progress.get('money')) is not int:
            return self.fail('safari_entry_progress_unverified')
        if progress.get('player_name_raw')!='KEVIN' or progress.get('badges_raw')!=31:
            return self.fail('safari_entry_player_or_badges_changed')
        if self.baseline is None:
            if (location!={'map_id':156,'x':3,'y':3} or not overworld_ready or not _text_valid(text)
                    or text.get('window_visible') is not False
                    or ''.join(_rows(text)).strip() or safari['in_safari'] or safari['game_over']
                    or safari['balls']!=0 or safari['steps']!=0 or safari['gate_script']!=0
                    or progress['money']<1000 or len(inventory)>18
                    or any(m['hp']!=m['max_hp'] or m['status']!=0 for m in party)):
                return self.fail('safari_entry_initial_conditions_unverified')
            self.baseline=deepcopy({'party':party,'inventory':inventory,'money':progress['money']})
            self.stage='welcome'
            return command('up','safari_entry',{'safari_entry_stage':'trigger_source_coordinate'})
        base=self.baseline;money=progress['money']
        if party!=base['party'] or inventory!=base['inventory']:
            return self.fail('safari_entry_party_or_inventory_changed')
        if money not in (base['money'],base['money']-500):return self.fail('safari_entry_unexpected_payment')
        if self.stage in {'welcome','offer'} and money!=base['money']:
            return self.fail('safari_entry_payment_before_confirmation')
        if self.stage=='payment' and money==base['money']-500:
            if location['map_id']==220:
                if (location['x'],location['y']) not in {(14,24),(15,24),(14,25),(15,25)}:
                    # native warp先更新map ID、再載入目的座標；只允許已觀測的原閘口4,0。
                    if (location['x'],location['y'])==(4,0) and (
                            safari['in_safari'] and not safari['game_over'] and safari['balls']==30
                            and 498<=safari['steps']<=502 and safari['gate_script']==3
                            and _text_valid(text) and text['window_visible'] is False
                            and not ''.join(_rows(text)).strip()):
                        self.closed_frames.clear()
                        self.arrival_waits=getattr(self,'arrival_waits',0)+1
                        if self.arrival_waits<=25:return _wait('paid_native_mapload')
                        return self.fail('safari_entry_arrival_wait_exhausted')
                    return self.fail('safari_entry_arrival_location_unverified')
                if not (safari['in_safari'] and not safari['game_over'] and safari['balls']==30
                        and 498<=safari['steps']<=502):return self.fail('safari_entry_arrival_not_paid')
                if (not _text_valid(text) or text.get('window_visible') is not False
                        or not overworld_ready or ''.join(_rows(text)).strip()):
                    self.closed_frames.clear()
                    return _wait('arrival_wait_for_closed_overworld')
                self.closed_frames.append(frame)
                if len(self.closed_frames)<2:return _wait('first_closed_arrival')
                self.stage='complete'
                return {**_wait('complete'),'safari_entry_complete':True,'safari_entry_fee_paid':500,
                        'safari_entry_balls':30,'safari_entry_steps':safari['steps']}
        if location['map_id']!=156 or location['x'] not in {3,4} or not 0<=location['y']<=3:
            return self.fail('safari_entry_location_unverified')
        if not _text_valid(text):
            if (self.stage=='payment' and money==base['money']-500
                    and isinstance(text,dict) and text.get('profile')==PROFILE and text.get('read_error') in
                    {None,'visible_tile_alignment_incomplete','visible_display_disabled'}):
                self.decode_waits=getattr(self,'decode_waits',0)+1
                if self.decode_waits>25:
                    result=self.fail('safari_entry_paid_decoder_wait_exhausted')
                    cells=text.get('cells',[])
                    result['safari_entry_decoder_diagnostic']={
                        'cell_container':type(cells).__name__,
                        'row_lengths':[len(row) if isinstance(row,(list,tuple,str)) else -1 for row in cells],
                        'invalid_cells':[(x,y,str(c)) for y,row in enumerate(cells) if isinstance(row,(list,tuple,str))
                                         for x,c in enumerate(row) if not isinstance(c,str) or len(c)!=1]}
                    return result
                return {**_wait('paid_native_text_or_autowalk_transition'),
                        'safari_entry_decoder_diagnostic':{
                            'read_valid':text.get('read_valid') is True,
                            'alignment_verified':text.get('alignment_verified') is True,
                            'read_error':text.get('read_error'),'rows_complete':_rows(text) is not None}}
            return self.fail('safari_entry_decoder_unverified')
        rows=_rows(text);marks=_marks(rows)
        if (self.stage=='payment' and money==base['money']-500 and safari['in_safari']
                and not safari['game_over'] and safari['balls']==30 and 498<=safari['steps']<=502
                and safari['gate_script'] in {3,4} and not ''.join(rows).strip()
                and text['window_visible'] is False and overworld_ready):
            return _wait('paid_native_autowalk')
        if self.stage=='welcome':
            if not _outside_verified(rows) or not marks<={(18,16,'▼')}:
                return self.fail('safari_entry_welcome_layout_unverified')
            if _page(rows,'welcome'):
                self.stage='offer';return command('a','safari_entry',{'safari_entry_stage':'welcome_confirmed'})
            if _prefix(rows,'welcome'):return _wait('welcome_typing')
        elif self.stage=='offer':
            if any('YES' in row or 'NO' in row for row in rows[:12]):
                if (not _outside_verified(rows,money=money,yesno=True) or not _page(rows,'question')
                        or marks not in ({(15,8,'▶')},{(15,10,'▶')})):
                    return self.fail('safari_entry_fee_question_unverified')
                if marks=={(15,10,'▶')}:return command('up','safari_entry',{'safari_entry_stage':'select_source_yes'})
                self.stage='payment'
                return command('a','safari_entry',{'safari_entry_stage':'approve_exact_500_fee'})
            if not _outside_verified(rows) or not marks<={(18,16,'▼')}:
                return self.fail('safari_entry_offer_layout_unverified')
            if _page(rows,'offer'):return command('a','safari_entry',{'safari_entry_stage':'advance_source_offer'})
            if _prefix(rows,'offer') or _prefix(rows,'question'):return _wait('offer_typing')
        elif self.stage=='payment':
            if money==base['money']:return _wait('confirmation_native_payment_pending')
            if not _outside_verified(rows,money=money) or not marks<={(18,16,'▼')}:
                return self.fail('safari_entry_payment_layout_unverified')
            if _page(rows,'payment'):return command('a','safari_entry',{'safari_entry_stage':'advance_verified_payment'})
            if _prefix(rows,'payment') or not ''.join(rows).strip():return _wait('payment_typing_or_autowalk')
        return self.fail('safari_entry_unknown_visible_page')


_CONTROLLERS=globals().get('_CONTROLLERS',{})
_BINDINGS=globals().get('_BINDINGS',{})
_COMPLETED=globals().get('_COMPLETED',set())
_RUN_CONTROLLER=globals().get('_RUN_CONTROLLER')
_RUN_OWNER=globals().get('_RUN_OWNER')
SAFARI_MAPS={217,218,219,220,221,222,223,224,225}


def applies(step_id,step,state):
    return (bool(set(_BINDINGS)-_COMPLETED) or step_id in _BINDINGS
            or bool(step and step.get('mechanic')=='safari_entry')
            or state.get('location',{}).get('map_id') in SAFARI_MAPS)


def field_context(pyboy,state,plan,step_id,text,grid):
    """入口付費與導航RUN分開認領；未知Safari戰鬥先停，禁止普通A誤投球。"""
    global _RUN_CONTROLLER,_RUN_OWNER
    safari=read_safari_state(pyboy)
    active=set(_BINDINGS)-_COMPLETED
    if state.get('location',{}).get('map_id') in SAFARI_MAPS:
        if safari.get('read_valid') is not True:
            return _review('safari_source_state_unverified'),step_id
        battle=state.get('battle_state',{})
        if _RUN_CONTROLLER is not None or battle.get('kind')!='none' or battle.get('active') is not False:
            if active:return _review('safari_battle_during_entry_unverified'),step_id
            from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
            signal=safari_battle_module.read_safari_battle_signal(pyboy,observation_frame=state['frame'],
                expected_location=state['location'],constants=sdk)
            if signal.get('read_valid') is not True:return _review('safari_wild_requires_review'),step_id
            if _RUN_CONTROLLER is None:
                if battle.get('kind')!='wild' or battle.get('active') is not True:
                    return _review('safari_wild_requires_review'),step_id
                _RUN_CONTROLLER=safari_battle_module.SafariRunController(safari_battle_module.INTENT)
                _RUN_OWNER=step_id
            if _RUN_OWNER!=step_id:return _review('safari_run_owner_changed'),step_id
            _RUN_CONTROLLER.__class__=safari_battle_module.SafariRunController
            step=next((s for s in plan['steps'] if s['id']==step_id),{})
            revision=step.get('reviewed_safari_run_revision',0)
            if (type(revision) is int and revision>getattr(_RUN_CONTROLLER,'_reviewed_revision',0)
                    and _RUN_CONTROLLER.error and step.get('reviewed_safari_run_error')==_RUN_CONTROLLER.error):
                _RUN_CONTROLLER.error=None;_RUN_CONTROLLER.started=time.monotonic()
                _RUN_CONTROLLER.calls=_RUN_CONTROLLER.waits=0;_RUN_CONTROLLER._reviewed_revision=revision
            from .campaign_transactions import ui_overworld_ready
            result=_RUN_CONTROLLER.context(text,location=state['location'],battle_state=battle,safari=safari,
                battle_signal=signal,frame=state['frame'],now=time.monotonic(),
                overworld_ready=ui_overworld_ready(text,grid))
            if result is None:return _review('safari_wild_requires_review'),step_id
            if result.get('safari_run_complete'):_RUN_CONTROLLER=None;_RUN_OWNER=None
            return result,step_id
    elif _RUN_CONTROLLER is not None:
        return _review('safari_run_location_changed'),step_id
    if active and active!={step_id}:return _review('safari_entry_owner_changed'),step_id
    step=next((s for s in plan['steps'] if s['id']==step_id),None)
    if not step or step.get('mechanic')!='safari_entry':
        if step_id in _BINDINGS and step_id not in _COMPLETED:
            return _review('safari_entry_intent_changed'),step_id
        return None
    if (step.get('kind')!='interact' or step.get('map_id')!=156 or step.get('target')!=[3,3]
            or step.get('safari_intent')!=INTENT):
        return _review('safari_entry_explicit_intent_unverified'),step_id
    binding=(step['kind'],step['map_id'],tuple(step['target']),tuple(sorted(step['safari_intent'].items())))
    if step_id in _BINDINGS and _BINDINGS[step_id]!=binding:
        return _review('safari_entry_intent_changed'),step_id
    controller=_CONTROLLERS.get(step_id)
    if controller is None:
        if state['location']!={'map_id':156,'x':3,'y':3}:return None
        controller=SafariEntryController(step['safari_intent']);_CONTROLLERS[step_id]=controller
        _BINDINGS[step_id]=binding
    controller.__class__=SafariEntryController
    revision=step.get('reviewed_revision',0)
    if (type(revision) is int and revision>getattr(controller,'_reviewed_revision',0)
            and controller.error is not None and step.get('reviewed_error')==controller.error):
        previous_error=controller.error
        controller.error=None;controller.started=time.monotonic();controller.calls=0;controller.last_frame=-1
        if (previous_error=='safari_entry_paid_decoder_wait_exhausted'
                and type(step.get('reviewed_decode_budget')) is int and step['reviewed_decode_budget']==25):
            controller.decode_waits=0
        controller._reviewed_revision=revision
    from .campaign_transactions import ui_overworld_ready
    result=controller.context(text,state['progress'],location=state['location'],battle_state=state['battle_state'],
        safari=safari,frame=state['frame'],overworld_ready=ui_overworld_ready(text,grid))
    if result.get('safari_entry_complete'):
        _COMPLETED.add(step_id)
        index=plan['steps'].index(step)+1
        return result,(plan['steps'][index]['id'] if index<len(plan['steps']) else 'complete')
    return result,step_id
