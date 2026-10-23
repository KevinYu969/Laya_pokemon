"""獨立合成Safari入場測試；不讀ignored輸出、遊戲、ROM或存檔。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from laya_pokemon.observation import PROFILE
from laya_pokemon import safari_entry as entry
from laya_pokemon.safari_entry import (
    INTENT, PROFILE_SAFARI, SafariEntryController, read_safari_state,
)


NONE={'kind':'none','active':False,'raw':0}
START={'map_id':156,'x':3,'y':3}
GATE={'map_id':156,'x':4,'y':2}
ARRIVAL={'map_id':220,'x':14,'y':24}
WELCOME=('Welcome to the','SAFARI ZONE!')
OFFERS=[('For just ¥500,','you can catch all'),('you can catch all','the POKéMON you'),
        ('the POKéMON you','want in the park!')]
PAYMENT=[("That'll be ¥500",'please!'),('We only use a','special POKé BALL'),
         ('special POKé BALL','here.'),('KEVIN received','30 SAFARI BALLs!'),
         ("We'll call you on",'the PA when you'),('the PA when you','run out of time'),
         ('run out of time','or SAFARI BALLs!')]


def text_at(*entries,window=True):
    cells=[[' ']*20 for _ in range(18)]
    for x,y,word in entries:
        assert 0<=x and x+len(word)<=20
        cells[y][x:x+len(word)]=list(word)
    return {'profile':PROFILE,'read_valid':True,'alignment_verified':True,
            'read_error':None,'window_visible':window,'cells':cells}


def put(t,x,y,word):
    t['cells'][y][x:x+len(word)]=list(word)
    return t


def money(t,amount):
    return put(put(t,13,0,'MONEY'),12,1,f'¥{amount}'.rjust(7))


def page(words,prompt=True,amount=None):
    t=text_at((1,14,words[0]),(1,16,words[1]))
    if prompt:put(t,18,16,'▼')
    if amount is not None:money(t,amount)
    return t


def question(amount=41066,cursor=8):
    return money(text_at((1,14,'Would you like to'),(1,16,'join the hunt?'),
                         (16,8,'YES'),(16,10,'NO'),(15,cursor,'▶')),amount)


def progress():
    mons=[(7,'NIDOKING',36,121,[61,33,30,40],[20,35,25,35]),
          (132,'SNORLAX',35,168,[29,133,156,34],[15,20,10,15]),
          (102,'EEVEE',35,90,[33,28,98,39],[35,15,30,30]),
          (154,'VENUSAUR',35,111,[75,15,73,22],[25,30,10,10]),
          (35,'FEAROW',35,108,[64,65,43,31],[35,20,30,20])]
    return {'profile':'gen1-wrapper-ram-progress-v1-unvalidated','initialization_candidate':True,
            'party_read_valid':True,'party_count':5,'money':41066,'player_name_raw':'KEVIN','badges_raw':31,
            'inventory':[{'item':4,'quantity':6},{'item':3,'quantity':9}],
            'party':[{'species':i,'species_name':n,'level':l,'hp':hp,'max_hp':hp,'exp':50000,
                      'status':0,'moves':moves,'pp':pp} for i,n,l,hp,moves,pp in mons]}


def safari(frame,*,paid=False):
    return {'profile':PROFILE_SAFARI,'read_valid':True,'observation_frame':frame,
            'in_safari':paid,'game_over':False,'steps':502 if paid else 0,
            'balls':30 if paid else 0,'gate_script':3 if paid else 0}


def review(hint):
    assert hint['phase']=='campaign_review' and hint['available_actions']==['wait']
    assert not hint.get('safari_entry_complete')
    return hint['review_reason']


class Session:
    def __init__(self):
        self.c=SafariEntryController(deepcopy(INTENT));self.p=progress()
        self.frame=0;self.now=0;self.loc=deepcopy(START);self.paid=False

    def call(self,text=None,**kw):
        self.frame+=40;self.now+=.1
        frame=kw.pop('frame',self.frame)
        return self.c.context(text_at(window=False) if text is None else text,self.p,
                              location=kw.pop('location',self.loc),battle_state=kw.pop('battle_state',deepcopy(NONE)),
                              safari=kw.pop('safari',safari(frame,paid=self.paid)),frame=frame,
                              overworld_ready=kw.pop('overworld_ready',False),now=kw.pop('now',self.now),**kw)

    def to_offer(self):
        assert self.call(overworld_ready=True)['available_actions']==['up','wait']
        self.loc=deepcopy(GATE)
        assert self.call(page(WELCOME))['available_actions']==['a','wait']

    def to_question(self):
        self.to_offer()
        for words in OFFERS:
            assert self.call(page(words))['available_actions']==['a','wait']

    def approve(self):
        self.to_question()
        assert self.call(question())['available_actions']==['a','wait']

    def pay(self):
        self.p['money']-=500;self.paid=True

    def payments(self):
        self.pay()
        for words in PAYMENT:
            assert self.call(page(words,amount=self.p['money']))['available_actions']==['a','wait']

    def to_arrival(self):
        self.approve();self.payments();self.loc=deepcopy(ARRIVAL)


def test_complete_source_flow_exact_500_thirty_balls_and_two_closed_frames():
    s=Session();original=deepcopy(s.p);s.to_arrival()
    assert s.call(overworld_ready=True)['available_actions']==['wait']
    result=s.call(overworld_ready=True)
    assert result['safari_entry_complete'] is True
    assert result['safari_entry_fee_paid']==500 and result['safari_entry_balls']==30
    assert 498<=result['safari_entry_steps']<=502
    assert s.p['party']==original['party'] and s.p['inventory']==original['inventory']
    assert s.p['money']==original['money']-500


def test_source_no_selection_only_moves_up_then_confirms_yes_once():
    s=Session();s.to_question()
    assert s.call(question(cursor=10))['available_actions']==['up','wait']
    assert s.call(question())['available_actions']==['a','wait']
    assert s.call(question())['available_actions']==['wait']


@pytest.mark.parametrize('words',[('Welcome',''),('Welcome to the','SAFARI'),('For just ¥','')])
def test_known_partial_page_never_sends_a(words):
    s=Session()
    if words[0].startswith('For'):s.to_offer()
    else:s.call(overworld_ready=True);s.loc=deepcopy(GATE)
    assert s.call(page(words,prompt=False))['available_actions']==['wait']


@pytest.mark.parametrize('words',[('Delete',''),('For just ¥600,','you can catch all'),
                                 ('Leaving early?',''),('Please return any','SAFARI BALLs you')])
def test_unknown_or_other_safari_dialogue_is_review_not_a(words):
    s=Session();s.to_offer();review(s.call(page(words)))


@pytest.mark.parametrize('where',[(0,0),(5,5),(0,14),(19,16)])
@pytest.mark.parametrize('mark',['X','▶','▷'])
def test_foreign_marks_or_letters_outside_question_layout_rejected(where,mark):
    s=Session();s.to_question();t=question();put(t,*where,mark)
    review(s.call(t));assert s.c.stage!='payment'


@pytest.mark.parametrize('where',[(15,8),(15,10),(19,8),(19,10)])
def test_unknown_letters_in_yesno_border_cells_are_not_confirmation(where):
    s=Session();s.to_question();t=question();put(t,*where,'X')
    review(s.call(t));assert s.c.stage!='payment'


@pytest.mark.parametrize('edit',['missing_yes','missing_no','not_no','duplicate_yes','duplicate_no',
                                'wrong_cursor','inactive_cursor','double_cursor','money_off_by_one'])
def test_question_must_have_unique_complete_labels_cursor_and_money(edit):
    s=Session();s.to_question();t=question()
    if edit=='missing_yes':put(t,16,8,'   ')
    if edit=='missing_no':put(t,16,10,'  ')
    if edit=='not_no':put(t,16,10,'NOT')
    if edit=='duplicate_yes':put(t,1,4,'YES')
    if edit=='duplicate_no':put(t,1,4,'NO')
    if edit=='wrong_cursor':put(t,15,8,' ');put(t,14,8,'▶')
    if edit=='inactive_cursor':put(t,15,8,'▷')
    if edit=='double_cursor':put(t,15,10,'▶')
    if edit=='money_off_by_one':money(t,s.p['money']+1)
    review(s.call(t));assert s.c.stage!='payment'


@pytest.mark.parametrize('field,value',[('profile','wrong'),('read_valid',False),('alignment_verified',False),
                                       ('read_error','unknown'),('window_visible',None)])
def test_unknown_decoder_proof_cannot_confirm_fee(field,value):
    s=Session();s.to_question();t=question();t[field]=value;review(s.call(t))


@pytest.mark.parametrize('field,value',[('profile','unknown'),('read_valid',False),('observation_frame',1)])
def test_unknown_safari_proof_is_review_before_fee(field,value):
    s=Session();s.to_question();proof=safari(s.frame+40);proof[field]=value
    review(s.call(question(),safari=proof))


@pytest.mark.parametrize('delta',[-1000,-501,-499,1,500])
def test_unexpected_or_duplicate_payment_never_completes(delta):
    s=Session();s.approve();s.p['money']+=delta
    review(s.call(page(PAYMENT[0],amount=s.p['money'])))


def test_payment_before_yes_is_rejected():
    s=Session();s.to_question();s.pay();review(s.call(question(s.p['money'])))


@pytest.mark.parametrize('change',['hp','status','exp','pp','moves','order','inventory','quantity','money_type'])
def test_transaction_requires_original_party_and_inventory(change):
    s=Session();s.approve();s.pay()
    if change=='hp':s.p['party'][0]['hp']-=1
    if change=='status':s.p['party'][0]['status']=64
    if change=='exp':s.p['party'][0]['exp']+=1
    if change=='pp':s.p['party'][0]['pp'][0]-=1
    if change=='moves':s.p['party'][0]['moves'][0]=33
    if change=='order':s.p['party'].reverse()
    if change=='inventory':s.p['inventory'].append({'item':49,'quantity':1})
    if change=='quantity':s.p['inventory'][0]['quantity']+=1
    if change=='money_type':s.p['money']=float(s.p['money'])
    review(s.call(page(PAYMENT[0],amount=40566)))


@pytest.mark.parametrize('x,y',[(14,24),(15,24),(14,25),(15,25)])
@pytest.mark.parametrize('steps',[498,502])
def test_exact_normal_arrival_cells_and_source_step_bounds(x,y,steps):
    s=Session();s.to_arrival();s.loc={'map_id':220,'x':x,'y':y}
    def call():
        proof=safari(s.frame+40,paid=True);proof['steps']=steps
        return s.call(safari=proof,overworld_ready=True)
    assert not call().get('safari_entry_complete')
    assert call()['safari_entry_complete'] is True


@pytest.mark.parametrize('field,value',[('balls',29),('balls',31),('steps',497),('steps',503),
                                       ('in_safari',False),('game_over',True)])
def test_bad_arrival_accounting_is_not_completion(field,value):
    s=Session();s.to_arrival();proof=safari(s.frame+40,paid=True);proof[field]=value
    review(s.call(safari=proof,overworld_ready=True))


@pytest.mark.parametrize('location',[{'map_id':219,'x':14,'y':24},{'map_id':220,'x':13,'y':24},
                                     {'map_id':225,'x':14,'y':24}])
def test_wrong_map_or_arrival_cell_is_review(location):
    s=Session();s.to_arrival();review(s.call(location=location,overworld_ready=True))


def test_paid_known_display_transition_only_waits_without_more_a():
    s=Session();s.approve();s.pay()
    t=text_at();t['read_valid']=False;t['read_error']='visible_display_disabled'
    assert s.call(t)['available_actions']==['wait']


def test_replayed_frame_cannot_send_second_payment_or_complete():
    s=Session();s.to_question();frame=s.frame+40
    s.call(question(),frame=frame)
    review(s.call(question(),frame=frame))


@pytest.mark.parametrize('now',[60.2,61,100])
def test_wall_budget_is_bounded(now):
    s=Session();s.to_question();review(s.call(question(),now=now))


def test_call_budget_is_bounded_and_never_pays():
    s=Session();s.call(overworld_ready=True);s.loc=deepcopy(GATE)
    for _ in range(149):
        result=s.call(page(('Welcome',''),prompt=False))
        assert result['available_actions']==['wait']
    assert review(s.call(page(('Welcome',''),prompt=False)))=='safari_entry_budget_exhausted'


def test_error_is_sticky_after_unknown_page_even_if_fee_question_appears():
    s=Session();s.to_question();reason=review(s.call(page(('DELETE',''))))
    assert review(s.call(question()))==reason


@pytest.mark.parametrize('x,y,char',[(15,10,'!'),(18,10,'?'),(18,10,'★')])
def test_foreign_punctuation_inside_no_label_box_never_approves_500(x,y,char):
    s=Session();s.to_question();t=question();put(t,x,y,char)
    review(s.call(t));assert s.c.stage!='payment'


@pytest.mark.parametrize('now',[float('nan'),float('inf'),float('-inf'),True,'unknown'])
def test_unknown_or_nonfinite_clock_does_not_start_movement(now):
    s=Session();review(s.call(overworld_ready=True,now=now))


def test_clock_regression_cannot_confirm_fee():
    s=Session();s.to_question();review(s.call(question(),now=s.now-1))


def test_initial_empty_decoder_with_visible_window_is_not_closed_overworld():
    s=Session();review(s.call(text_at(window=True),overworld_ready=True))


def test_arrival_visible_empty_window_does_not_count_as_two_closed_frames():
    s=Session();s.to_arrival()
    for _ in range(2):
        result=s.call(text_at(window=True),overworld_ready=True)
        assert result['available_actions']==['wait'] and not result.get('safari_entry_complete')


def test_unclosed_arrival_resets_the_two_frame_evidence():
    s=Session();s.to_arrival()
    assert not s.call(overworld_ready=True).get('safari_entry_complete')
    assert not s.call(page(('unknown overlay','')),overworld_ready=False).get('safari_entry_complete')
    assert not s.call(overworld_ready=True).get('safari_entry_complete')
    assert s.call(overworld_ready=True)['safari_entry_complete']


def test_paid_gate_native_autowalk_is_wait_and_does_not_spend_twice():
    s=Session();s.approve();s.pay();before=deepcopy(s.p)
    assert s.call(overworld_ready=True)['available_actions']==['wait']
    assert s.call(overworld_ready=True)['available_actions']==['wait']
    assert s.p==before and s.c.stage=='payment'


@pytest.fixture
def bridge(monkeypatch):
    monkeypatch.setattr(entry,'_CONTROLLERS',{})
    monkeypatch.setattr(entry,'_BINDINGS',{})
    monkeypatch.setattr(entry,'_COMPLETED',set())
    monkeypatch.setattr(entry,'read_safari_state',lambda pyboy:safari(pyboy.frame_count,paid=pyboy.paid))
    from laya_pokemon import campaign_transactions
    monkeypatch.setattr(campaign_transactions,'ui_overworld_ready',
                        lambda text,grid:bool(grid and grid.get('ready')))
    step={'id':'enter-safari','kind':'interact','mechanic':'safari_entry','map_id':156,
          'target':[3,3],'safari_intent':deepcopy(INTENT)}
    plan={'mode':'league_campaign','steps':[step,{'id':'after-entry','kind':'move'}]}
    state={'frame':80,'location':deepcopy(START),'progress':progress(),'battle_state':deepcopy(NONE)}
    pyboy=SimpleNamespace(frame_count=80,paid=False)
    return pyboy,state,plan,step


def bridge_call(b,text=None,ready=True):
    pyboy,state,plan,step=b
    return entry.field_context(pyboy,state,plan,step['id'],text_at(window=False) if text is None else text,{'ready':ready})


def test_explicit_bridge_initial_claim_and_owner_binding(bridge):
    hint,ident=bridge_call(bridge)
    assert hint['available_actions']==['up','wait'] and ident=='enter-safari'
    assert set(entry._CONTROLLERS)==set(entry._BINDINGS)=={'enter-safari'}
    original=entry._CONTROLLERS['enter-safari']
    bridge[1]['frame']+=40;bridge[0].frame_count+=40;bridge[1]['location']=deepcopy(GATE)
    hint,ident=bridge_call(bridge,page(WELCOME),False)
    assert hint['available_actions']==['a','wait'] and entry._CONTROLLERS[ident] is original


@pytest.mark.parametrize('field,value',[('kind','move'),('map_id',157),('target',[4,3]),
                                       ('safari_intent',{'kind':'safari_entry','fee':500})])
def test_explicit_bridge_rejects_malformed_step_without_field_keys(bridge,field,value):
    bridge[3][field]=value
    result=entry.field_context(bridge[0],bridge[1],bridge[2],'enter-safari',text_at(window=False),{'ready':True})
    review(result[0]);assert not entry._CONTROLLERS


def test_bridge_does_not_claim_controller_before_initial_source_position(bridge):
    bridge[1]['location']['y']=4
    assert bridge_call(bridge) is None and not entry._CONTROLLERS


def test_active_bridge_rejects_step_owner_change(bridge):
    bridge_call(bridge)
    result=entry.field_context(bridge[0],bridge[1],bridge[2],'after-entry',text_at(window=False),{'ready':True})
    review(result[0]);assert set(entry._CONTROLLERS)=={'enter-safari'}


def test_active_bridge_rejects_same_owner_intent_mutation(bridge):
    bridge_call(bridge);bridge[3]['safari_intent']['fee']=1000
    review(bridge_call(bridge)[0])


@pytest.mark.parametrize('mid',range(217,226))
def test_safari_maps_guard_uses_only_true_source_maps(mid):
    assert entry.applies('plain',{'id':'plain','kind':'move'},{'location':{'map_id':mid}})


@pytest.mark.parametrize('mid',[156,216,226])
def test_non_safari_maps_do_not_get_implicit_capture_guard(mid):
    assert not entry.applies('plain',{'id':'plain','kind':'move'},{'location':{'map_id':mid}})


def test_safari_unknown_wild_is_review_before_ordinary_attack_can_run(bridge):
    bridge[1]['location']=deepcopy(ARRIVAL);bridge[1]['battle_state']={'kind':'wild','active':True,'raw':1}
    result=entry.field_context(bridge[0],bridge[1],bridge[2],'after-entry',text_at(),{'ready':False})
    assert review(result[0])=='safari_wild_requires_review'


def test_bridge_completion_advances_only_after_second_true_closed_arrival(bridge):
    pyboy,state,plan,step=bridge
    def call(t=None,ready=False):
        hint=bridge_call(bridge,t,ready)
        state['frame']+=40;pyboy.frame_count=state['frame']
        return hint
    call(ready=True);state['location']=deepcopy(GATE)
    call(page(WELCOME))
    for words in OFFERS:call(page(words))
    call(question());state['progress']['money']-=500;pyboy.paid=True
    for words in PAYMENT:call(page(words,amount=40566))
    state['location']=deepcopy(ARRIVAL)
    assert call(ready=True)[1]=='enter-safari'
    done,ident=call(ready=True)
    assert done['safari_entry_complete'] is True and ident=='after-entry'
    assert 'enter-safari' in entry._COMPLETED


def sdk(**overrides):
    d={'EVENT_FLAGS_ADDRESS':0xD747,'STATUS_FLAGS3_ADDRESS':0xD72D,
       'EVENT_FLAGS':{'in_safari_zone':0x24F,'safari_game_over':0x24E,'got_hm03':0x880,'got_hm04':0x238}}
    d.update(overrides)
    return SimpleNamespace(**d)


ADDRESSES=(0xD790,0xD70D,0xD70E,0xDA47,0xD61F)


class Memory:
    def __init__(self,values=None):
        self.values=dict(zip(ADDRESSES,(0,0,0,0,0))) if values is None else dict(values)
        self.reads=[];self.transform=None;self.pyboy=None

    def __getitem__(self,address):
        assert address in ADDRESSES,'reader只准讀固定五個來源位址'
        self.reads.append(address)
        value=self.values[address]
        return self.transform(address,value,self.reads.count(address)) if self.transform else value

    def __setitem__(self,address,value):
        raise AssertionError('測試禁止任何記憶體寫入')


def fake(values=None,frame=80):
    p=SimpleNamespace(memory=Memory(values),frame_count=frame)
    p.memory.pyboy=p
    return p


def unknown(result):
    assert result['profile']==PROFILE_SAFARI and result['read_valid'] is False
    assert not any(k in result for k in ('balls','steps','in_safari','game_over','gate_script'))


@pytest.mark.parametrize('flags,steps,balls,script',[(0,0,0,0),(128,502,30,3),(192,1,0,5)])
def test_reader_big_endian_bits_and_readonly_double_snapshot(flags,steps,balls,script):
    p=fake(dict(zip(ADDRESSES,(flags,steps>>8,steps&255,balls,script))))
    result=read_safari_state(p,sdk())
    assert result['read_valid'] is True and result['observation_frame']==80
    assert result['in_safari']==bool(flags&128) and result['game_over']==bool(flags&64)
    assert result['steps']==steps and result['balls']==balls and result['gate_script']==script
    assert p.memory.reads==list(ADDRESSES)*2


@pytest.mark.parametrize('events',[None,[],1,'unknown',{'in_safari_zone':True}])
def test_reader_bad_sdk_mapping_returns_unknown_without_reads(events):
    p=fake();unknown(read_safari_state(p,sdk(EVENT_FLAGS=events)));assert not p.memory.reads


@pytest.mark.parametrize('field,value',[('EVENT_FLAGS_ADDRESS',0xD748),('EVENT_FLAGS_ADDRESS',float(0xD747)),
                                       ('STATUS_FLAGS3_ADDRESS',0xD72E),('STATUS_FLAGS3_ADDRESS',None)])
def test_reader_requires_both_exact_sdk_anchors(field,value):
    p=fake();unknown(read_safari_state(p,sdk(**{field:value})));assert not p.memory.reads


@pytest.mark.parametrize('key',['in_safari_zone','safari_game_over','got_hm03','got_hm04'])
def test_reader_wrong_event_id_is_unknown(key):
    c=sdk();c.EVENT_FLAGS[key]+=1;unknown(read_safari_state(fake(),c))


@pytest.mark.parametrize('address',ADDRESSES)
@pytest.mark.parametrize('pass_number',[1,2])
@pytest.mark.parametrize('value',[None,-1,256,1.0,True])
def test_reader_every_byte_in_each_pass_requires_exact_byte_type(address,pass_number,value):
    # 所有原始byte為1，使第二讀True/1.0在Python數值比較中與1相等。
    p=fake(dict(zip(ADDRESSES,(1,1,1,1,1))))
    p.memory.transform=lambda a,v,n:value if a==address and n==pass_number else v
    unknown(read_safari_state(p,sdk()))


@pytest.mark.parametrize('address',ADDRESSES)
def test_reader_same_frame_changed_second_byte_is_unknown(address):
    p=fake();p.memory.transform=lambda a,v,n:v+1 if a==address and n==2 else v
    unknown(read_safari_state(p,sdk()))


def test_reader_frame_changes_during_snapshot_returns_unknown():
    p=fake()
    def mutate(a,v,n):
        if a==0xD70D and n==2:p.frame_count+=1
        return v
    p.memory.transform=mutate;unknown(read_safari_state(p,sdk()))


@pytest.mark.parametrize('frame',[None,True,1.0,-1])
def test_reader_bad_frame_is_unknown(frame):
    unknown(read_safari_state(fake(frame=frame),sdk()))


@pytest.mark.parametrize('error',[KeyError,IndexError,ValueError,TypeError,RuntimeError])
def test_reader_read_exception_returns_unknown(error):
    p=fake()
    def fail(a,v,n):raise error('synthetic getter failed')
    p.memory.transform=fail;unknown(read_safari_state(p,sdk()))


@pytest.mark.parametrize('values',[(0,1,247,0,0),(0,0,0,31,0),(0,0,0,0,7)])
def test_reader_out_of_source_range_is_unknown(values):
    unknown(read_safari_state(fake(dict(zip(ADDRESSES,values))),sdk()))


# 2026-10-24實機付款後停點的新回歸。以下全部合成，不讀pause-proof或game。
# 獨立clone的That'll prefix可正常解碼；原停點封包缺失，不能從此斷言根因。
def paid_before_balls():
    s=Session();s.approve()
    s.p['money']-=500
    # 正常源碼先扣錢、PrintText，付款文字結束後才發30球及設入場旗標。
    assert not s.paid
    return s


def incomplete_paid_text(field='read_valid',value=False):
    t=page(("That'll",''),prompt=False,amount=40566)
    t[field]=deepcopy(value)
    return t


@pytest.mark.parametrize('field,value',[
    ('read_valid',False),('alignment_verified',False),('cells',None),
    ('cells',[[' ']*20 for _ in range(17)]),('window_visible',None),
    ('read_error','visible_tile_alignment_incomplete'),('read_error','visible_display_disabled'),
])
def test_paid_known_profile_incomplete_decode_only_waits_without_a_or_mutation(field,value):
    s=paid_before_balls();before=deepcopy(s.p);baseline=deepcopy(s.c.baseline)
    result=s.call(incomplete_paid_text(field,value))
    assert result['phase']=='safari_entry' and result['available_actions']==['wait']
    assert not result.get('safari_entry_complete') and s.c.error is None
    assert s.c.stage=='payment' and s.p==before and s.c.baseline==baseline


def test_paid_decoder_wait_has_exact_25_call_limit_then_sticky_review():
    s=paid_before_balls();before=deepcopy(s.p);baseline=deepcopy(s.c.baseline)
    for _ in range(25):
        result=s.call(incomplete_paid_text())
        assert result['phase']=='safari_entry' and result['available_actions']==['wait']
    reason=review(s.call(incomplete_paid_text()))
    assert review(s.call(page(PAYMENT[0],amount=40566)))==reason
    assert s.c.stage=='payment' and s.p==before and s.c.baseline==baseline


def test_valid_prefix_between_invalid_packets_does_not_erase_25_wait_budget():
    s=paid_before_balls()
    for _ in range(25):
        assert s.call(incomplete_paid_text())['available_actions']==['wait']
        assert s.call(page(("That'll",''),prompt=False,amount=40566))['available_actions']==['wait']
    review(s.call(incomplete_paid_text()))


def test_paid_decode_recovers_to_strict_prefix_then_exact_full_payment_page():
    s=paid_before_balls();before=deepcopy(s.p)
    assert s.call(incomplete_paid_text())['available_actions']==['wait']
    assert s.call(page(("That'll",''),prompt=False,amount=40566))['available_actions']==['wait']
    result=s.call(page(PAYMENT[0],amount=40566))
    assert result['available_actions']==['a','wait']
    assert result['safari_entry_stage']=='advance_verified_payment'
    assert s.p==before and s.c.stage=='payment'


@pytest.mark.parametrize('point',['initial','welcome','offer','approved_but_not_deducted'])
@pytest.mark.parametrize('error',[None,'visible_tile_alignment_incomplete','visible_display_disabled'])
def test_unpaid_incomplete_decode_still_reviews(point,error):
    s=Session()
    if point=='welcome':s.call(overworld_ready=True);s.loc=deepcopy(GATE)
    elif point=='offer':s.to_offer()
    elif point=='approved_but_not_deducted':s.approve()
    t=incomplete_paid_text();t['read_error']=error
    review(s.call(t,overworld_ready=point=='initial'))
    assert s.p['money']==41066


@pytest.mark.parametrize('profile',[None,'unknown','other-gen-visible-text'])
def test_paid_unknown_profile_never_enters_decoder_wait_exception(profile):
    s=paid_before_balls();t=incomplete_paid_text();t['profile']=profile
    review(s.call(t))


@pytest.mark.parametrize('error',['unknown_decoder_error','memory_unavailable','read_failed'])
def test_paid_unknown_decode_error_is_review_not_tolerated(error):
    s=paid_before_balls();t=incomplete_paid_text();t['read_error']=error
    review(s.call(t))


@pytest.mark.parametrize('location',[{'map_id':156,'x':2,'y':2},{'map_id':156,'x':4,'y':4},
                                     {'map_id':157,'x':4,'y':2},{'map_id':220,'x':14,'y':24}])
def test_paid_incomplete_decode_wait_does_not_escape_source_gate_or_arrival_accounting(location):
    s=paid_before_balls();review(s.call(incomplete_paid_text(),location=location))


@pytest.mark.parametrize('change',['source_profile','source_invalid','other_frame','battle','party','bag','fee'])
def test_paid_incomplete_decode_wait_preserves_all_other_guards(change):
    s=paid_before_balls();proof=safari(s.frame+40);kwargs={'safari':proof}
    if change=='source_profile':proof['profile']='wrong'
    if change=='source_invalid':proof['read_valid']=False
    if change=='other_frame':proof['observation_frame']-=1
    if change=='battle':kwargs['battle_state']={'kind':'wild','active':True,'raw':1}
    if change=='party':s.p['party'][0]['hp']-=1
    if change=='bag':s.p['inventory'][0]['quantity']-=1
    if change=='fee':s.p['money']-=500
    review(s.call(incomplete_paid_text(),**kwargs))


def test_paid_decode_wait_cannot_bypass_existing_sixty_second_budget():
    s=paid_before_balls();review(s.call(incomplete_paid_text(),now=100))


def test_paid_decode_wait_cannot_bypass_replayed_frame_guard():
    s=paid_before_balls();frame=s.frame+40
    assert s.call(incomplete_paid_text(),frame=frame)['available_actions']==['wait']
    review(s.call(incomplete_paid_text(),frame=frame))


def test_paid_decode_wait_does_not_clear_unrelated_sticky_error():
    s=paid_before_balls();reason=review(s.call(page(('DELETE',''),amount=40566)))
    assert review(s.call(incomplete_paid_text()))==reason


def test_reappearing_fee_question_after_paid_wait_cannot_authorize_another_charge():
    s=paid_before_balls();baseline=deepcopy(s.c.baseline);before=deepcopy(s.p)
    assert s.call(incomplete_paid_text())['available_actions']==['wait']
    result=s.call(question(amount=40566))
    assert result['available_actions']==['wait'] and not result.get('safari_entry_complete')
    assert s.c.stage=='payment' and s.p==before and s.c.baseline==baseline


# 新來源回歸：SDK POKEMON_TEXT_DECODING[0xBC]及固定charmap.asm均為"'l"。
# charmap a536711 blob f096797827b30e28201826a1b61656c5adeaa41e。
# 一個token佔一個實體tile；只有語意比較才能展開，不得挪動錢框或游標。
def compressed_l_tokens(word):
    tokens=[];i=0
    while i<len(word):
        if word[i:i+2]=="'l":tokens.append("'l");i+=2
        else:tokens.append(word[i]);i+=1
    return tokens


def compressed_payment(words,prompt=True):
    t=money(text_at(),40566)
    for y,word in zip((14,16),words):
        tokens=compressed_l_tokens(word)
        assert len(tokens)<=18
        t['cells'][y][1:1+len(tokens)]=tokens
    if prompt:put(t,18,16,'▼')
    return t


@pytest.mark.parametrize('words,column',[(PAYMENT[0],5),(PAYMENT[4],3)])
def test_native_compressed_l_complete_payment_pages_advance_without_column_shift(words,column):
    s=paid_before_balls();t=compressed_payment(words);before=deepcopy(t);progress_before=deepcopy(s.p)
    assert t['cells'][14][column]=="'l"
    rows=entry._rows(t)
    assert len(rows)==18 and all(len(row)==20 for row in rows)
    assert len(rows[14][column])==1
    assert entry._positions(rows,'MONEY')==[(13,0)]
    assert entry._money(rows,40566)
    assert entry._marks(rows)=={(18,16,'▼')}
    assert entry._lower(rows)==''.join((words[0]+words[1]).upper().replace('É','E').split())
    result=s.call(t)
    assert result['available_actions']==['a','wait'] and result['safari_entry_stage']=='advance_verified_payment'
    assert s.c.stage=='payment' and s.p==progress_before and t==before


def test_complete_transaction_with_native_thatll_and_well_cells_only_spends_original_500():
    s=Session();before=deepcopy(s.p);s.approve();s.pay()
    for words in PAYMENT:
        assert s.call(compressed_payment(words))['available_actions']==['a','wait']
    s.loc=deepcopy(ARRIVAL)
    assert not s.call(overworld_ready=True).get('safari_entry_complete')
    assert s.call(overworld_ready=True)['safari_entry_complete']
    assert s.p['money']==before['money']-500
    assert s.p['party']==before['party'] and s.p['inventory']==before['inventory']


@pytest.mark.parametrize('word',["That'l","That'll","That'll be","We'll","We'll call"])
@pytest.mark.parametrize('prompt',[False,True])
def test_source_compressed_l_partial_typing_only_waits_even_with_visible_prompt(word,prompt):
    s=paid_before_balls();result=s.call(compressed_payment((word,''),prompt=prompt))
    assert result['available_actions']==['wait'] and not result.get('safari_entry_complete')


def test_compressed_l_in_wrapped_second_dialogue_row_keeps_physical_width_and_only_waits():
    s=paid_before_balls();t=compressed_payment(('',"We'll"),prompt=False)
    assert t['cells'][16][3]=="'l"
    rows=entry._rows(t)
    assert all(len(row)==20 for row in rows) and entry._lower(rows)=="WE'LL"
    assert s.call(t)['available_actions']==['wait']


@pytest.mark.parametrize('x,y',[(13,0),(12,1),(16,8),(15,8),(16,10),(15,10),
                              (0,14),(19,14),(0,16),(19,16),(5,13),(5,15),(5,17),(5,7)])
def test_compressed_l_outside_source_dialogue_or_on_borders_never_approves_fee(x,y):
    s=Session();s.to_question();t=question();t['cells'][y][x]="'l"
    result=s.call(t)
    assert result['available_actions']==['wait'] and not result.get('safari_entry_complete')
    assert s.c.stage!='payment'


@pytest.mark.parametrize('x,y',[(13,0),(12,1),(16,8),(15,10),(0,14),(19,16),(5,13),(5,15)])
def test_paid_l_token_in_wrong_physical_region_cannot_advance_payment(x,y):
    s=paid_before_balls();t=compressed_payment(PAYMENT[0]);t['cells'][y][x]="'l"
    result=s.call(t)
    assert result['available_actions']==['wait'] and not result.get('safari_entry_complete')


@pytest.mark.parametrize('glyph',["'L","'s","'t","'r","'ll",'<PLAYER>','Thatll','’l'])
def test_other_multichar_glyphs_do_not_inherit_the_l_exception(glyph):
    s=paid_before_balls();t=compressed_payment(PAYMENT[0]);t['cells'][14][5]=glyph
    assert entry._rows(t) is None
    result=s.call(t)
    assert result['available_actions']==['wait'] and not result.get('safari_entry_complete')


@pytest.mark.parametrize('second_token_position',[(6,14),(17,14),(17,16)])
def test_additional_compressed_l_pollution_cannot_become_a_known_full_page(second_token_position):
    s=paid_before_balls();t=compressed_payment(PAYMENT[0])
    x,y=second_token_position;t['cells'][y][x]="'l"
    assert s.call(t)['available_actions']==['wait']


def test_literal_private_sentinel_cannot_impersonate_native_compressed_sdk_token():
    t=compressed_payment(PAYMENT[0]);rows=entry._rows(t)
    sentinel=rows[14][5]
    assert len(sentinel)==1 and sentinel not in "'l"
    t['cells'][14][5]=sentinel
    s=paid_before_balls();result=s.call(t)
    assert result['available_actions']==['wait'] and not result.get('safari_entry_complete')


@pytest.mark.parametrize('shift',[-1,1])
def test_semantic_l_expansion_does_not_justify_shifted_money_box(shift):
    s=paid_before_balls();t=compressed_payment(PAYMENT[0])
    t['cells'][0]=[' ']*20;put(t,13+shift,0,'MONEY')
    result=s.call(t)
    assert result['available_actions']==['wait'] and not result.get('safari_entry_complete')


@pytest.mark.parametrize('shift',[-1,1])
def test_semantic_l_expansion_does_not_justify_shifted_prompt(shift):
    s=paid_before_balls();t=compressed_payment(PAYMENT[0]);put(t,18,16,' ');put(t,18+shift,16,'▼')
    assert s.call(t)['available_actions']==['wait']


@pytest.mark.parametrize('overflow',['column','row'])
def test_l_token_never_allows_a_nineteenth_row_or_twenty_first_column(overflow):
    s=paid_before_balls();t=compressed_payment(PAYMENT[0])
    if overflow=='column':t['cells'][14].append("'l")
    else:t['cells'].append([' ']*20)
    assert entry._rows(t) is None
    assert s.call(t)['available_actions']==['wait']


# 原生warp的map先更新、目的座標稍後更新；只驗證父層已觀測的220(4,0)。
MAPLOAD={'map_id':220,'x':4,'y':0}


def mapload_session():
    s=Session();s.to_arrival();s.loc=deepcopy(MAPLOAD)
    return s


def mapload_call(s,text=None,*,steps=500,**kw):
    proof=safari(s.frame+40,paid=True);proof['steps']=steps
    proof.update(kw.pop('source_changes',{}))
    return s.call(text,safari=proof,**kw)


@pytest.mark.parametrize('steps',[498,499,500,501,502])
@pytest.mark.parametrize('ready',[False,True])
def test_exact_paid_mapload_pose_only_waits_without_a_or_completion(steps,ready):
    s=mapload_session();before=deepcopy(s.p);baseline=deepcopy(s.c.baseline)
    hint=mapload_call(s,steps=steps,overworld_ready=ready)
    assert hint['available_actions']==['wait'] and hint['safari_entry_stage']=='paid_native_mapload'
    assert not hint.get('safari_entry_complete') and s.c.error is None
    assert s.p==before and s.c.baseline==baseline and s.c.stage=='payment'


def test_exact_paid_mapload_has_twenty_five_wait_limit_then_sticky_review():
    s=mapload_session();before=deepcopy(s.p);baseline=deepcopy(s.c.baseline)
    for _ in range(25):
        hint=mapload_call(s)
        assert hint['available_actions']==['wait'] and hint['phase']=='safari_entry'
    reason=review(mapload_call(s))
    assert reason=='safari_entry_arrival_wait_exhausted'
    s.loc=deepcopy(ARRIVAL)
    assert review(s.call(overworld_ready=True))==reason
    assert s.p==before and s.c.baseline==baseline


def test_native_mapload_then_correct_arrival_still_requires_two_closed_frames():
    s=mapload_session();before=deepcopy(s.p)
    for _ in range(3):assert mapload_call(s)['available_actions']==['wait']
    s.loc={'map_id':220,'x':15,'y':25}
    assert not s.call(overworld_ready=True).get('safari_entry_complete')
    assert s.call(overworld_ready=True)['safari_entry_complete']
    assert s.p==before


def test_return_to_mapload_pose_erases_prior_single_closed_arrival_frame():
    s=Session();s.to_arrival()
    assert not s.call(overworld_ready=True).get('safari_entry_complete')
    s.loc=deepcopy(MAPLOAD)
    assert mapload_call(s)['available_actions']==['wait']
    s.loc=deepcopy(ARRIVAL)
    assert not s.call(overworld_ready=True).get('safari_entry_complete')
    assert s.call(overworld_ready=True)['safari_entry_complete']


@pytest.mark.parametrize('location',[
    {'map_id':220,'x':3,'y':0},{'map_id':220,'x':5,'y':0},{'map_id':220,'x':4,'y':1},
    {'map_id':220,'x':14,'y':0},{'map_id':220,'x':4,'y':24},{'map_id':219,'x':4,'y':0},
    {'map_id':221,'x':4,'y':0},
])
def test_other_wrong_mapload_positions_do_not_inherit_the_wait_exception(location):
    s=mapload_session();review(mapload_call(s,location=location))


@pytest.mark.parametrize('field,value',[
    ('in_safari',False),('game_over',True),('balls',29),('balls',31),('steps',497),
    ('steps',503),('gate_script',0),('gate_script',4),('profile','wrong'),
    ('read_valid',False),('observation_frame',1),('balls',30.0),('steps',True),
])
def test_mapload_only_waits_with_exact_valid_paid_safari_source(field,value):
    s=mapload_session();review(mapload_call(s,source_changes={field:value}))


@pytest.mark.parametrize('field,value',[
    ('profile','unknown'),('read_valid',False),('alignment_verified',False),
    ('read_error','visible_display_disabled'),('read_error','visible_tile_alignment_incomplete'),
    ('cells',None),('window_visible',True),
])
def test_mapload_requires_complete_decoder_and_closed_window_not_general_paid_decode_fallback(field,value):
    s=mapload_session();t=text_at(window=False);t[field]=value
    review(mapload_call(s,t))


@pytest.mark.parametrize('word',['X','▶','▷','▼',"'l"])
def test_mapload_screen_must_be_completely_blank(word):
    s=mapload_session();t=text_at(window=False);t['cells'][14][5]=word
    review(mapload_call(s,t))


@pytest.mark.parametrize('change',['not_paid','paid_twice','party','inventory','active_battle'])
def test_mapload_cannot_bypass_payment_party_inventory_or_battle_guard(change):
    s=mapload_session();kwargs={}
    if change=='not_paid':s.p['money']+=500
    if change=='paid_twice':s.p['money']-=500
    if change=='party':s.p['party'][0]['hp']-=1
    if change=='inventory':s.p['inventory'][0]['quantity']-=1
    if change=='active_battle':kwargs['battle_state']={'kind':'wild','active':True,'raw':1}
    review(mapload_call(s,**kwargs))


def test_mapload_cannot_bypass_replayed_frame_or_wall_budget():
    s=mapload_session();frame=s.frame+40
    assert mapload_call(s,frame=frame)['available_actions']==['wait']
    review(mapload_call(s,frame=frame))
    s=mapload_session();review(mapload_call(s,now=100))
