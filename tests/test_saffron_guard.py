"""固定公開來源與fake context；不讀遊戲／ROM／state或操作模型。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from laya_pokemon import saffron_guard as sg


START={'map_id':76,'x':2,'y':4}
TRIGGER={'map_id':76,'x':3,'y':4}


def text(words=None, *, arrow=False, window=True):
    cells=[[' ']*20 for _ in range(18)]
    if words:
        for y,value in zip((14,16),words):
            if y==14 and value=='to SAFFRON CITY...':value=value[:17]
            # 模擬真字型'l兩字共用單一tile，不把觀測改造成普通字串。
            chars=list(value.replace("'l",'\ue100').replace("'m",'\ue101'))
            cells[y][1:1+len(chars)]=["'l" if c=='\ue100' else "'m" if c=='\ue101' else c for c in chars]
    if arrow:cells[16][18]='▼'
    return {'profile':sg.TEXT_PROFILE,'read_valid':True,'alignment_verified':True,
            'read_error':None,'window_visible':window,'cells':cells}


def progress():
    return {'profile':'gen1-wrapper-ram-progress-v1-unvalidated','initialization_candidate':True,
        'party_read_valid':True,'party_count':2,'money':40566,
        'inventory':[{'item':4,'quantity':6},{'item':60,'quantity':1},{'item':198,'quantity':1},{'item':199,'quantity':1}],
        'party':[{'species':132,'species_name':'SNORLAX','level':35,'hp':168,'max_hp':168,
                  'exp':56987,'status':0,'moves':[70,133,156,34],'pp':[15,20,10,15]},
                 {'species':7,'species_name':'NIDOKING','level':36,'hp':121,'max_hp':121,
                  'exp':40019,'status':0,'moves':[61,57,30,40],'pp':[20,15,25,35]}]}


def signal(frame,loc=START,flags=1):
    return {'profile':sg.PROFILE,'source_commit':sg.SOURCE_COMMIT,'read_valid':True,
        'observation_frame':frame,'location':deepcopy(loc),'raw_flags':flags,'gave_drink':bool(flags&64)}


def reviewed(result):
    assert result['phase']=='campaign_review' and result['available_actions']==['wait']
    assert not result.get('saffron_guard_complete')
    return result['review_reason']


class Session:
    def __init__(self):
        self.c=sg.SaffronGuardController(deepcopy(sg.INTENT));self.p=progress()
        self.loc=deepcopy(START);self.frame=0;self.now=0.;self.flags=1

    def call(self,t=None,**kw):
        self.frame+=40;self.now+=.1
        frame=kw.pop('frame',self.frame);loc=kw.pop('location',self.loc)
        return self.c.context(text(window=False) if t is None else t,self.p,
            location=loc,battle_state=kw.pop('battle_state',{'kind':'none','active':False,'raw':0,'observation_frame':frame}),
            guard_signal=kw.pop('guard_signal',signal(frame,loc,self.flags)),frame=frame,
            now=kw.pop('now',self.now),overworld_ready=kw.pop('overworld_ready',False),**kw)

    def start(self):
        assert self.call(overworld_ready=True)['available_actions']==['right','wait']

    def arrive(self):
        self.loc=deepcopy(TRIGGER);self.p['inventory']=[i for i in self.p['inventory'] if i['item']!=60]

    def dialogue(self):
        self.start();self.arrive()
        for page in sg.PAGES[:-1]:
            assert self.call(text(page,arrow=True))['available_actions']==['a','wait']
        assert self.call(text(sg.PAGES[-1]))['available_actions']==['wait']
        assert self.call(text(sg.PAGES[-1]))['available_actions']==['a','wait']


def test_complete_source_sequence_single_water_exact_ledger_and_two_new_closed_frames():
    s=Session();before=deepcopy(s.p);s.dialogue()
    assert s.c.actions==16 and s.c.stage=='closing'
    # 最後外層A才允許旗標變化；舊頁也不能再按A。
    assert s.call(text(sg.PAGES[-1]))['available_actions']==['wait']
    s.flags|=64
    first=s.call(overworld_ready=True);assert not first.get('saffron_guard_complete')
    done=s.call(overworld_ready=True);assert done['saffron_guard_complete']
    assert s.p['party']==before['party'] and s.p['money']==before['money']
    assert s.p['inventory']==[i for i in before['inventory'] if i['item']!=60]
    assert done['quantity_used']==1 and done['drink_consumed']==60


def test_source_contraction_and_arrow_mask_on_eighteenth_character():
    s=Session();s.start();s.arrive()
    for i,page in enumerate(sg.PAGES[:-1]):
        assert s.call(text(page,arrow=True))['available_actions']==['a','wait'],i
    assert "'l" in [c for row in text(sg.PAGES[12])['cells'] for c in row]
    assert len(sg.PAGES[9][1])==18


def test_real_first_dialogue_compressed_im_keeps_physical_cells_and_waits_for_prompt():
    s=Session();s.start();s.arrive()
    partial=text(('Whoa, boy!',"I'm p"))
    assert partial['cells'][16][2]=="'m" and len(partial['cells'][16])==20
    assert s.call(partial)['available_actions']==['wait']
    assert s.c.page==0 and s.c.actions==1
    assert s.call(text(sg.PAGES[0],arrow=True))['available_actions']==['a','wait']
    assert s.c.page==1 and s.c.actions==2


@pytest.mark.parametrize('location,token',[(3,"'m"),(2,"'M"),(2,'\ue001')])
def test_compressed_im_wrong_cell_unknown_case_or_injected_internal_token_rejected(location,token):
    s=Session();s.start();s.arrive();t=text(sg.PAGES[0],arrow=True)
    t['cells'][16][2]=' ';t['cells'][16][location]=token
    reviewed(s.call(t));assert s.c.actions==1


def test_compressed_im_requires_exact_i_prefix_and_native_row():
    s=Session();s.start();s.arrive();t=text(sg.PAGES[0],arrow=True)
    t['cells'][16][1]='X';reviewed(s.call(t));assert s.c.actions==1


def test_eighteenth_character_erased_by_prompt_then_scrolled_preserves_source_page():
    s=Session();s.start();s.arrive()
    for page in sg.PAGES[:10]:s.call(text(page,arrow=True))
    native=text(sg.PAGES[10],arrow=True)
    assert ''.join(native['cells'][14]).strip()=='to SAFFRON CITY..'
    assert native['cells'][14][18]==' '
    assert s.call(native)['available_actions']==['a','wait'] and s.c.page==11
    assert s.call(native)['available_actions']==['wait'] and s.c.actions==12


def test_scrolled_line_does_not_accept_other_truncations_or_ordinary_extra_characters():
    for changes in ({17:' '},{18:'.'},{17:'X'}):
        s=Session();s.start();s.arrive()
        for page in sg.PAGES[:10]:s.call(text(page,arrow=True))
        packet=text(sg.PAGES[10],arrow=True)
        for x,value in changes.items():packet['cells'][14][x]=value
        reviewed(s.call(packet));assert s.c.actions==11


def test_full_without_arrow_partial_and_blank_never_accelerate_typing():
    s=Session();s.start();s.arrive()
    for t in [text(),text(('Whoa, bo','')),text(sg.PAGES[0])]:
        assert s.call(t)['available_actions']==['wait']
    assert s.call(text(sg.PAGES[0],arrow=True))['available_actions']==['a','wait']


def test_old_page_after_blank_does_not_resend_a_or_right():
    s=Session();s.start()
    assert s.call(overworld_ready=True)['available_actions']==['wait']
    assert s.c.actions==1
    s.arrive();assert s.call(text(sg.PAGES[0],arrow=True))['available_actions']==['a','wait']
    assert s.call(text())['available_actions']==['wait']
    assert s.call(text(sg.PAGES[0],arrow=True))['available_actions']==['wait']
    assert s.call(text(sg.PAGES[1],arrow=True))['available_actions']==['a','wait']


@pytest.mark.parametrize('change',['water_missing','water_two','soda','lemonade','duplicate','flags_true','bad_profile','not_ready','faint','wrong_position','bool_intent'])
def test_initial_preconditions_prevent_trigger(change):
    s=Session();t=text(window=False);kw={'overworld_ready':True}
    if change=='water_missing':s.p['inventory']=[i for i in s.p['inventory'] if i['item']!=60]
    elif change=='water_two':s.p['inventory'][1]['quantity']=2
    elif change in ('soda','lemonade'):s.p['inventory'].append({'item':61 if change=='soda' else 62,'quantity':1})
    elif change=='duplicate':s.p['inventory'].append({'item':60,'quantity':1})
    elif change=='flags_true':s.flags=65
    elif change=='bad_profile':t['profile']='unknown'
    elif change=='not_ready':kw['overworld_ready']=False
    elif change=='faint':s.p['party'][1]['hp']=0
    elif change=='wrong_position':s.loc['y']=3
    else:s.c.intent['drink_item']=True
    reviewed(s.call(t,**kw));assert s.c.actions==0 and s.c.baseline is None


@pytest.mark.parametrize('change',['upper_yes','unknown','out_of_order','cursor','wrong_arrow','sentinel','multi_cell','profile','alignment','window_false','not_consumed'])
def test_unknown_or_polluted_page_cannot_press_a(change):
    s=Session();s.start();s.arrive();t=text(sg.PAGES[0],arrow=True)
    if change=='upper_yes':t['cells'][0][0:3]=list('YES')
    elif change=='unknown':t=text(('DELETE A MOVE?',''),arrow=True)
    elif change=='out_of_order':t=text(sg.PAGES[5],arrow=True)
    elif change=='cursor':t['cells'][10][1]='▶'
    elif change=='wrong_arrow':t['cells'][16][17]='▼'
    elif change=='sentinel':t['cells'][14][1]=sg._L
    elif change=='multi_cell':t['cells'][14][1]='YES'
    elif change=='profile':t['profile']=None
    elif change=='alignment':t['alignment_verified']=False
    elif change=='window_false':t['window_visible']=False
    else:s.p=progress()
    reviewed(s.call(t));assert s.c.actions==1


@pytest.mark.parametrize('change',['money','bench_hp','bench_pp','exp','order','bag_qty','bag_order','flags_other','flag_early','water_restored','signal_frame','signal_bool','battle'])
def test_fingerprints_are_checked_before_partial_or_animation_wait(change):
    s=Session();s.start();s.arrive();s.call(text(('Wh','')))
    kw={}
    if change=='money':s.p['money']-=1
    elif change=='bench_hp':s.p['party'][1]['hp']-=1
    elif change=='bench_pp':s.p['party'][1]['pp'][0]-=1
    elif change=='exp':s.p['party'][0]['exp']+=1
    elif change=='order':s.p['party'].reverse()
    elif change=='bag_qty':s.p['inventory'][0]['quantity']-=1
    elif change=='bag_order':s.p['inventory'].reverse()
    elif change=='flags_other':s.flags|=2
    elif change=='flag_early':s.flags|=64
    elif change=='water_restored':s.p=progress()
    elif change=='signal_frame':kw['guard_signal']=signal(s.frame,TRIGGER)
    elif change=='signal_bool':kw['guard_signal']=signal(s.frame+40,TRIGGER);kw['guard_signal']['raw_flags']=True
    else:kw['battle_state']={'kind':'wild','active':True,'raw':1,'observation_frame':s.frame+40}
    reviewed(s.call(text(('Whoa','')),**kw));assert s.c.actions==1


def test_same_frame_conflict_and_monotonic_clock_never_resend():
    s=Session();s.start();frame=s.frame
    assert s.call(frame=frame,overworld_ready=True)['available_actions']==['wait']
    t=text(window=False);t['cells'][0][0]='X'
    reviewed(s.call(t,frame=frame,overworld_ready=True));assert s.c.actions==1
    s=Session();s.start();reviewed(s.call(now=0.))


@pytest.mark.parametrize('target',['text','progress','ready'])
@pytest.mark.parametrize('bound',[False,True])
def test_all_explicit_observation_frames_and_ready_are_verified_before_any_action(target,bound):
    for invalid in (999,True):
        s=Session()
        if bound:s.start();s.arrive()
        t=text(sg.PAGES[0],arrow=True) if bound else text(window=False)
        kw={'overworld_ready':not bound}
        if target=='text':t['observation_frame']=invalid
        elif target=='progress':s.p['observation_frame']=invalid
        else:kw['overworld_ready']=1
        reviewed(s.call(t,**kw));assert s.c.actions==(1 if bound else 0)
        assert (s.c.baseline is not None)==bound


def test_final_requires_stability_flag_and_consecutive_closed_proof():
    s=Session();s.start();s.arrive()
    for page in sg.PAGES[:-1]:s.call(text(page,arrow=True))
    assert s.call(text(sg.PAGES[-1]))['available_actions']==['wait']
    assert s.call(text(sg.PAGES[-1]),frame=s.frame+1)['available_actions']==['wait']
    assert s.call(text(sg.PAGES[-1]))['available_actions']==['a','wait']
    assert not s.call(overworld_ready=True).get('saffron_guard_complete')
    s.flags|=64;assert not s.call(overworld_ready=True).get('saffron_guard_complete')
    unreadable=text(window=False);unreadable.update(read_valid=False,alignment_verified=False,read_error='visible_display_disabled')
    assert s.call(unreadable)['available_actions']==['wait']
    assert not s.call(overworld_ready=True).get('saffron_guard_complete')
    assert s.call(overworld_ready=True)['saffron_guard_complete']


@pytest.mark.parametrize('transition',['blank','decode'])
def test_final_stability_needs_sixteen_frames_and_restarts_after_transition(transition):
    s=Session();s.start();s.arrive()
    for page in sg.PAGES[:-1]:s.call(text(page,arrow=True))
    assert s.call(text(sg.PAGES[-1]))['available_actions']==['wait'];first=s.frame
    assert s.call(text(sg.PAGES[-1]),frame=first+8)['available_actions']==['wait']
    t=text()
    if transition=='decode':t.update(read_valid=False,alignment_verified=False,read_error='visible_display_disabled')
    assert s.call(t,frame=first+16)['available_actions']==['wait']
    assert s.c.final_seen_frame is None
    assert s.call(text(sg.PAGES[-1]),frame=first+40)['available_actions']==['wait']
    assert s.call(text(sg.PAGES[-1]),frame=first+48)['available_actions']==['wait']
    assert s.call(text(sg.PAGES[-1]),frame=first+56)['available_actions']==['a','wait']


@pytest.mark.parametrize('kind',['wait','clock','calls','final_wait'])
def test_bounds_latch_review_and_never_attach_complete_to_review(kind):
    s=Session();s.start()
    if kind=='wait':s.c.waits=120;reviewed(s.call())
    elif kind=='clock':reviewed(s.call(now=60.101))
    elif kind=='calls':s.c.calls=240;reviewed(s.call())
    else:
        s.arrive()
        for p in sg.PAGES[:-1]:s.call(text(p,arrow=True))
        s.call(text(sg.PAGES[-1]));s.call(text(sg.PAGES[-1]));s.flags|=64
        s.call(overworld_ready=True);s.c.waits=120;reviewed(s.call(overworld_ready=True))
    reviewed(s.call());assert s.c.error


def sdk():return SimpleNamespace(**sg.SDK_ANCHORS,MAPS={'route_7_gate':76})


def test_reader_derived_addresses_readonly_stable_and_sdk_crosscheck():
    class ReadOnly(dict):
        def __setitem__(self,*a):raise AssertionError('No writes')
    memory=ReadOnly({0xD728:1,0xD35E:76,0xD361:4,0xD362:2})
    p=SimpleNamespace(memory=memory,frame_count=40)
    r=sg.read_saffron_guard(p,observation_frame=40,expected_location=START,constants=sdk())
    assert r['read_valid'] and r['raw_flags']==1 and r['gave_drink'] is False and not r['live_calibrated']
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    assert sg.read_saffron_guard(p,observation_frame=40,expected_location=START,constants=constants)['read_valid']


@pytest.mark.parametrize('change',['sdk','sdk_bool','map','frame','byte_bool','byte_missing','location','profile','torn','frame_changed'])
def test_reader_unknown_is_not_partial_evidence(change):
    mem={0xD728:1,0xD35E:76,0xD361:4,0xD362:2};c=sdk();loc=deepcopy(START);f=40;profile=sg.PROFILE
    if change=='sdk':c.STATUS_FLAGS3_ADDRESS+=1
    elif change=='sdk_bool':c.OBTAINED_BADGES_ADDRESS=True
    elif change=='map':c.MAPS={}
    elif change=='frame':f=True
    elif change=='byte_bool':mem[0xD728]=True
    elif change=='byte_missing':del mem[0xD728]
    elif change=='location':loc['x']=3
    elif change=='profile':profile='unknown'
    elif change=='torn':
        class Torn(dict):
            reads=0
            def __getitem__(self,key):
                self.reads+=1
                return 65 if self.reads>4 and key==0xD728 else super().__getitem__(key)
        mem=Torn(mem)
    p=SimpleNamespace(memory=mem,frame_count=40)
    if change=='frame_changed':
        class Frames:
            memory=mem;reads=0
            @property
            def frame_count(self):
                self.reads+=1
                return 40 if self.reads<=2 else 41
        p=Frames()
    r=sg.read_saffron_guard(p,observation_frame=f,expected_location=loc,constants=c,profile=profile)
    assert r['read_valid'] is False and 'raw_flags' not in r and 'gave_drink' not in r
