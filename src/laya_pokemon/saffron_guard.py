"""Route7守衛收單瓶清水的純候選；只讀來源訊號、回傳Laya子目標。"""
from copy import deepcopy
import math

from .observation import PROFILE as TEXT_PROFILE
from .party_control import command
from .mart_purchase import _inventory, _party

SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
SOURCE = f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/scripts/Route7Gate.asm'
PROFILE = 'red-en-route7-fresh-water-source-v1-unvalidated'
INTENT = {'kind':'saffron_guard_fresh_water','map_id':76,'trigger_from':[2,4],
          'trigger_at':[3,4],'drink_item':60}
SDK_ANCHORS = {'STATUS_FLAGS3_ADDRESS':0xD72D,'OBTAINED_BADGES_ADDRESS':0xD356}
_L = '\ue000'
# cont會把舊底列捲到上列；para則清框。頁面保持來源順序，不是通用對話。
PAGES = (
    ('Whoa, boy!',"I'm parched!"), ("I'm parched!",'...'),
    ('...','Huh? I can have'), ('Huh? I can have','this drink?'),
    ('this drink?','Gee, thanks!'), ('...','Glug glug...'),
    ('Glug glug...','...'), ('...','Gulp...'),
    ('Gulp...','If you want to go'), ('If you want to go','to SAFFRON CITY...'),
    ('to SAFFRON CITY...','...'), ('...','You can go on'),
    ('You can go on',"through. I'll"), ("through. I'll",'share this with'),
    ('share this with','the other guards!'),
)


def read_saffron_guard(pyboy, *, observation_frame, expected_location, constants, profile=PROFILE):
    """同幀雙讀D728與座標；SDK錨與公開WRAM差值不符時整包未知。"""
    unknown = {'profile':profile,'source_commit':SOURCE_COMMIT,'read_valid':False,
               'unknown_reason':'source_anchor_or_observation_unverified','live_calibrated':False}
    if (profile != PROFILE or type(observation_frame) is not int or observation_frame < 0
            or type(getattr(pyboy,'frame_count',None)) is not int or pyboy.frame_count != observation_frame
            or not isinstance(expected_location,dict)
            or set(expected_location) != {'map_id','x','y'}
            or any(type(expected_location[k]) is not int or not 0<=expected_location[k]<=255
                   for k in expected_location)
            or expected_location['map_id'] != 76
            or any(type(getattr(constants,k,None)) is not int or getattr(constants,k)!=v
                   for k,v in SDK_ANCHORS.items())
            or not isinstance(getattr(constants,'MAPS',None),dict)
            or type(constants.MAPS.get('route_7_gate')) is not int
            or constants.MAPS['route_7_gate'] != 76):
        return unknown
    # wStatusFlags1在StatusFlags3前5bytes；wCurMap在ObtainedBadges後8bytes，
    # 其後2-byte view pointer，再接Y/X；兩個錨都由已安裝SDK交叉驗證。
    addresses=(0xD728,0xD35E,0xD361,0xD362)
    try:
        first=tuple(pyboy.memory[a] for a in addresses)
        second=tuple(pyboy.memory[a] for a in addresses)
        frame_after=getattr(pyboy,'frame_count',None)
        if (first!=second or any(type(v) is not int or not 0<=v<=255 for v in first+second)
                or type(frame_after) is not int or frame_after!=observation_frame):
            return {**unknown,'unknown_reason':'read_torn_or_frame_changed'}
    except (AttributeError,IndexError,KeyError,TypeError,ValueError,RuntimeError):
        return {**unknown,'unknown_reason':'memory_unreadable'}
    flags,map_id,y,x=first
    location={'map_id':map_id,'x':x,'y':y}
    if location!=expected_location:
        return {**unknown,'unknown_reason':'location_disagrees'}
    return {**unknown,'read_valid':True,'unknown_reason':None,'observation_frame':observation_frame,
            'location':location,'raw_flags':flags,'gave_drink':bool(flags&64)}


def _rows(text):
    if (not isinstance(text,dict) or text.get('profile')!=TEXT_PROFILE
            or text.get('read_valid') is not True or text.get('alignment_verified') is not True
            or text.get('read_error') is not None or type(text.get('window_visible')) is not bool):
        return None
    cells=text.get('cells')
    if not isinstance(cells,(list,tuple)) or len(cells)!=18:
        return None
    rows=[]
    for y,row in enumerate(cells):
        if not isinstance(row,(list,tuple,str)) or len(row)!=20:return None
        line=[]
        for x,c in enumerate(row):
            if not isinstance(c,str) or c==_L:return None
            if len(c)==1:line.append(c.upper())
            elif c=="'l" and y in (14,16) and 1<=x<=18:line.append(_L)
            else:return None
        rows.append(''.join(line))
    return tuple(rows)


def _line(value):
    return value.replace("'l",_L).upper()


def _body(rows):
    """只有兩列原生對話及固定▼位置；拒絕所有外來字句／游標。"""
    if any(c!=' ' for y,row in enumerate(rows) for x,c in enumerate(row)
           if not (y in (14,16) and 1<=x<=18)):
        return None
    arrow=rows[16][18]=='▼'
    if any(c in '▶▷▼' for y,row in enumerate(rows) for x,c in enumerate(row)
           if not (arrow and (x,y)==(18,16))):return None
    return rows[14][1:19].rstrip(),rows[16][1:18 if arrow else 19].rstrip(),arrow


def _full(body,index):
    a,b,arrow=body;first,second=map(_line,PAGES[index])
    # 第18字會被▼及其閃爍空白遮蓋；不能把任意其它字丟掉。
    expected=second[:17] if arrow and len(second)==18 else second
    return a==first and (b==expected or not arrow and len(second)==18 and b==second[:17])


def _prefix(body,index):
    a,b,arrow=body;first,second=map(_line,PAGES[index])
    return not arrow and first.startswith(a) and (not b or a==first and second.startswith(b))


class SaffronGuardController:
    """明確意圖、完整基線、逐頁prompt及兩個新閉合幀的有界交易。"""
    def __init__(self,intent):
        self.intent=deepcopy(intent);self.baseline=None;self.stage='start';self.error=None
        self.started=None;self.last_now=None;self.last_frame=-1;self.last_packet=None
        self.calls=0;self.waits=0;self.actions=0;self.page=0;self.pending=None
        self.consumed=False;self.final_seen_frame=None;self.closed_frames=[]

    def fail(self,reason):
        self.error=reason
        return {'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],'review_reason':reason}

    def wait(self,reason):
        self.waits+=1
        if self.waits>120:return self.fail('saffron_guard_wait_budget_exhausted')
        return {'phase':'saffron_guard','objective':'Wait.','available_actions':['wait'],
                'saffron_guard_stage':reason,'source':SOURCE}

    def action(self,button,reason):
        self.actions+=1
        if self.actions>20:return self.fail('saffron_guard_action_budget_exhausted')
        if button=='right':
            return {'phase':'saffron_guard','objective':'Move RIGHT.','available_actions':['right','wait'],
                    'controller_menu_verified':True,'saffron_guard_stage':reason,'source':SOURCE}
        return command(button,'saffron_guard',{'saffron_guard_stage':reason,'source':SOURCE})

    def context(self,text,progress,*,location,battle_state,guard_signal,frame,now,overworld_ready=False):
        """呼叫端須在無tick同一觀測中取得text/progress/location/signal；每次僅一個子目標。"""
        if self.error:return self.fail(self.error)
        if (self.intent!=INTENT or type(self.intent.get('map_id')) is not int
                or type(self.intent.get('drink_item')) is not int
                or any(type(self.intent.get(k)) is not list or any(type(v) is not int for v in self.intent[k])
                       for k in ('trigger_from','trigger_at'))):return self.fail('saffron_guard_intent_changed')
        if (type(frame) is not int or frame<0 or type(now) not in (int,float)
                or not math.isfinite(now) or now<0 or self.last_now is not None and now<self.last_now):
            return self.fail('saffron_guard_clock_or_frame_unverified')
        self.started=now if self.started is None else self.started;self.last_now=now;self.calls+=1
        if self.calls>240 or now-self.started>60:return self.fail('saffron_guard_budget_exhausted')
        signal=guard_signal
        if (not isinstance(signal,dict) or signal.get('profile')!=PROFILE
                or signal.get('source_commit')!=SOURCE_COMMIT or signal.get('read_valid') is not True
                or type(signal.get('observation_frame')) is not int or signal['observation_frame']!=frame
                or type(signal.get('raw_flags')) is not int or not 0<=signal['raw_flags']<=255
                or type(signal.get('gave_drink')) is not bool
                or signal['gave_drink']!=bool(signal['raw_flags']&64)
                or type(location) is not dict or set(location)!={'map_id','x','y'}
                or any(type(v) is not int for v in location.values()) or signal.get('location')!=location
                or location not in ({'map_id':76,'x':2,'y':4},{'map_id':76,'x':3,'y':4})
                or not isinstance(battle_state,dict) or battle_state.get('kind')!='none'
                or battle_state.get('active') is not False or type(battle_state.get('raw')) is not int
                or battle_state['raw']!=0 or type(battle_state.get('observation_frame')) is not int
                or battle_state['observation_frame']!=frame):return self.fail('saffron_guard_source_or_location_unverified')
        party=_party(progress);bag=_inventory(progress.get('inventory')) if isinstance(progress,dict) else None
        if (party is None or bag is None or type(progress.get('money')) is not int
                or not 0<=progress['money']<=999999 or any(m['hp']==0 for m in party)):
            return self.fail('saffron_guard_progress_unverified')
        packet=deepcopy((text,progress,location,battle_state,guard_signal,overworld_ready))
        if frame<self.last_frame or frame==self.last_frame and packet!=self.last_packet:
            return self.fail('saffron_guard_same_frame_conflict')
        if frame==self.last_frame:return self.wait('same_observation_no_resend')
        self.last_frame,self.last_packet=frame,packet
        rows=_rows(text)
        if self.baseline is None:
            if (location!={'map_id':76,'x':2,'y':4} or rows is None or not overworld_ready
                    or text['window_visible'] is not False or ''.join(rows).strip() or signal['gave_drink']
                    or [i for i in bag if i['item'] in (60,61,62)]!=[{'item':60,'quantity':1}]):
                return self.fail('saffron_guard_initial_conditions_unverified')
            self.baseline=deepcopy({'party':party,'inventory':bag,'money':progress['money'],'flags':signal['raw_flags']})
            self.stage='dialogue'
            return self.action('right','trigger_only_once')
        base=self.baseline;removed=[i for i in base['inventory'] if i['item']!=60]
        if (party!=base['party'] or progress['money']!=base['money']
                or bag not in (base['inventory'],removed) or self.consumed and bag!=removed
                or signal['raw_flags'] not in (base['flags'],base['flags']|64)):
            return self.fail('saffron_guard_transaction_fingerprint_changed')
        if bag==removed:self.consumed=True
        if signal['gave_drink'] and self.stage not in ('closing','complete'):
            return self.fail('saffron_guard_flag_before_final_confirmation')
        if rows is None:
            self.closed_frames.clear()
            if (isinstance(text,dict) and text.get('profile')==TEXT_PROFILE
                    and text.get('read_error') in ('visible_display_disabled','visible_tile_alignment_incomplete')):
                return self.wait('known_native_transition_unreadable')
            return self.fail('saffron_guard_decoder_unverified')
        if location['x']==2:
            if self.consumed or signal['gave_drink'] or ''.join(rows).strip() or text['window_visible']:
                return self.fail('saffron_guard_trigger_position_disagrees')
            return self.wait('await_single_right_movement')
        body=_body(rows)
        if body is None:return self.fail('saffron_guard_unknown_or_polluted_page')
        blank=not ''.join(rows).strip()
        if self.stage in ('closing','complete') and blank and text['window_visible'] is False:
            if not self.consumed:return self.fail('saffron_guard_missing_drink_removal')
            if not signal['gave_drink'] or not overworld_ready:
                self.closed_frames.clear();return self.wait('await_source_flag_and_closed_world')
            self.closed_frames.append(frame)
            if len(self.closed_frames)<2:return self.wait('first_closed_overworld_frame')
            result=self.wait('complete')
            if self.error:return result
            self.stage='complete'
            return {**result,'saffron_guard_complete':True,'drink_consumed':60,'quantity_used':1}
        self.closed_frames.clear()
        if blank:return self.wait('native_blank_transition')
        if text['window_visible'] is not True or not self.consumed:
            return self.fail('saffron_guard_dialogue_before_drink_removal')
        if self.pending is not None and _full(body,self.pending):
            return self.wait('old_page_no_resend')
        if self.page>=len(PAGES):return self.fail('saffron_guard_unexpected_closing_page')
        if _full(body,self.page):
            if self.page<len(PAGES)-1:
                if not body[2]:return self.wait('await_complete_native_prompt')
                self.pending=self.page;self.page+=1
                return self.action('a','advance_exact_source_page')
            if body[2]:return self.fail('saffron_guard_unexpected_final_arrow')
            if self.final_seen_frame is None:self.final_seen_frame=frame
            if frame-self.final_seen_frame<8:return self.wait('stable_done_page_before_outer_prompt')
            self.pending=self.page;self.page+=1;self.stage='closing'
            return self.action('a','close_exact_done_outer_prompt')
        if _prefix(body,self.page):return self.wait('known_source_text_typing')
        return self.fail('saffron_guard_unknown_or_out_of_order_page')
