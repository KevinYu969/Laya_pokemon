"""拉普拉斯HM03固定資料擴充；六人完整UI合成，不載ROM或送遊戲鍵。"""
from copy import deepcopy
from importlib import reload
import inspect

import pytest

from laya_pokemon import hm_teaching as hm
from laya_pokemon import hm_teaching_bridge as bridge
from tests.test_hm_teaching import canvas,clear,packet,put,start
from tests.test_hm_fly_teaching import fly_progress,bag,use

LOCATION=dict(map_id=171,x=3,y=4)
BEFORE=[55,34,47,54]
AFTER=[57,34,47,54]
LABELS=['WATER GUN','BODY SLAM','SING','MIST']


def progress(lapras_index=5,hm_index=2):
    p=fly_progress()
    mon=p['party'].pop(0)
    mon.update(level=30,exp=27000)
    p['party'].insert(lapras_index,mon)
    fearow=next(m for m in p['party'] if m['species']==35)
    fearow.update(moves=[64,65,19,31],pp=[35,20,15,20])
    item=next(x for x in p['inventory'] if x['item']==198)
    p['inventory'].remove(item);p['inventory'].insert(hm_index,item)
    return p


def party(p,index=0,marker='▶'):
    r=canvas()
    for i,m in enumerate(p['party']):
        put(r,3,i*2,m['species_name']);put(r,13,i*2,f"{m['level']:3}")
        put(r,12,i*2+1,'ABLE' if m['species'] in (19,7,132) else 'NOT ABLE')
    put(r,0,index*2+1,marker);put(r,1,14,'Use TM on which')
    return put(r,1,16,'POKéMON?')


def plan():
    return dict(steps=[dict(id='lapras-surf',kind='interact',mechanic='teach_surf_lapras',
                           map_id=171,target=[3,4],hm_intent=deepcopy(hm.LAPRAS_SURF_INTENT)),
                       dict(id='next',kind='move',map_id=171,target=[3,5])])


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    for name,value in (('_CONTROLLERS',{}),('_BINDINGS',{}),('_COMPLETED',set())):
        monkeypatch.setattr(bridge,name,value)
    monkeypatch.setattr('laya_pokemon.campaign_transactions.ui_overworld_ready',
                        lambda t,g:t['window_visible'] is False and t['cells']==canvas())


class Session:
    def __init__(self,lapras_index=5,hm_index=2,via_bridge=False):
        self.p=progress(lapras_index,hm_index);self.target=lapras_index;self.hm_index=hm_index
        self.offset,self.cursor=max(0,hm_index-2),min(2,hm_index)
        self.frame=0;self.now=0.;self.via_bridge=via_bridge;self.plan=plan();self.next_step='lapras-surf'
        self.controller=None if via_bridge else hm.HMTeachingController(hm.LAPRAS_SURF_INTENT)

    @property
    def c(self):
        return bridge._CONTROLLERS['lapras-surf'] if self.via_bridge else self.controller

    def call(self,r=None,*,ready=False,same=False,window=True,p=None,text=None,location=None):
        if not same:self.frame+=1;self.now+=.05
        p=self.p if p is None else p;t=packet(r,window) if text is None else text
        location=deepcopy(LOCATION if location is None else location)
        if self.via_bridge:
            state=dict(frame=self.frame,location=location,progress=p,
                       battle_state=dict(kind='none',active=False,raw=0,observation_frame=self.frame))
            result=bridge.context(state,self.plan,'lapras-surf',t,object())
            assert result is not None
            out,self.next_step=result
            return out
        return self.c.context(t,p,location=location,frame=self.frame,now=self.now,
                              overworld_ready=ready,battle_active=False)

    def expected(self,r,action,**kw):
        out=self.call(r,**kw);assert out['available_actions']==[action,'wait'],out
        return out

    def dialog(self,lines,*,on_party=False,choose=False,y=8,arrow=None):
        r=party(self.p,self.target,'▷') if on_party else use(self.p,self.offset,self.cursor,marker='▷')
        clear(r,0,12,19,17)
        if choose:
            clear(r,14,7,19,12);put(r,16,8,'YES');put(r,16,10,'NO');put(r,15,y,'▶')
        for row,s in lines:put(r,1,row,s)
        if arrow is not None:put(r,18,arrow,'▼')
        return r

    def forget(self,y=8):
        r=clear(party(self.p,self.target,'▷'),4,7,19,12);clear(r,0,12,19,17)
        for i,s in enumerate(LABELS):put(r,6,8+i,s)
        put(r,5,y,'▶');put(r,1,14,'Which move should')
        return put(r,1,16,'be forgotten?')

    def to_party(self):
        self.expected(canvas(),'start',ready=True,window=False)
        self.expected(start(6),'a')
        for n in range(self.hm_index+1):
            self.expected(bag(self.p,max(0,n-2),min(2,n)), 'a' if n==self.hm_index else 'down')
        self.expected(use(self.p,self.offset,self.cursor),'a')
        self.expected(self.dialog([(14,'Booted up an HM!')],arrow=16),'a')
        self.expected(self.dialog([(14,'It contained'),(16,'SURF!')],arrow=16),'a')
        self.expected(self.dialog([(14,'Teach SURF'),(16,'to a POKéMON?')],choose=True),'a')

    def to_forget(self):
        self.to_party()
        for i in range(self.target+1):self.expected(party(self.p,i),'a' if i==self.target else 'down')
        for lines in ([(14,'LAPRAS is'),(16,'trying to learn')],
                      [(14,'trying to learn'),(16,'SURF!')],
                      [(14,'But, LAPRAS'),(16,"can't learn more")],
                      [(14,"can't learn more"),(16,'than 4 moves!')]):
            self.expected(self.dialog(lines,on_party=True),'a')
        self.expected(self.dialog([(13,'Delete an older'),(14,'move to make room'),
                                   (16,'for SURF?')],choose=True,on_party=True),'a')

    def to_receipt(self):
        self.to_forget()
        out=self.expected(self.forget(),'a');assert out['forgotten_move']==55

    def install(self):
        self.p['party'][self.target]['moves'][0]=57;self.p['party'][self.target]['pp'][0]=15

    def to_closing(self):
        self.to_receipt()
        self.expected(self.dialog([(14,'1, 2 and... Poof!')],on_party=True,arrow=16),'a')
        self.expected(self.dialog([(14,'LAPRAS forgot'),(16,'WATER GUN!')],on_party=True,arrow=16),'a')
        self.expected(self.dialog([(14,'And...')],on_party=True,arrow=16),'a')
        self.install()
        self.expected(self.dialog([(14,'LAPRAS learned'),(16,'SURF!')],on_party=True,arrow=16),'a')

    def finish(self):
        self.to_closing();self.expected(bag(self.p,self.offset,self.cursor),'b');self.expected(start(),'b')
        assert self.call(ready=True,window=False)['available_actions']==['wait']
        assert not self.call(ready=True,window=False,same=True).get('hm_teaching_complete')
        return self.call(ready=True,window=False)


def review(out):
    assert out['phase']=='campaign_review' and out['available_actions']==['wait'],out


@pytest.mark.parametrize('index,hmindex,via',[(5,2,False),(0,0,False),(3,5,False),(5,4,True)])
def test_complete_six_party_surf_replaces_only_water_gun_and_its_pp(index,hmindex,via):
    s=Session(index,hmindex,via);before=deepcopy(s.p)
    out=s.finish();expected=deepcopy(before)
    expected['party'][index]['moves'][0]=57;expected['party'][index]['pp'][0]=15
    assert s.p==expected and out['hm_teaching_complete'] is True
    assert out['hm_teaching_kind']=='teach_surf_lapras' and out['moves_verified']==AFTER
    assert out['hm_preserved']==198 and out['hm_quantity_used']==0
    assert s.c.baseline==before['party'] and s.c.inventory==[(x['item'],x['quantity']) for x in before['inventory']]
    if via:assert s.next_step=='next' and bridge._COMPLETED=={'lapras-surf'}


@pytest.mark.parametrize('key,value',[('species',7),('item',197),('move',70),('replace_move',34),
                                    ('replace_index',1),('replace_index',False),('move',57.0)])
def test_new_intent_is_exact_not_a_general_hm_permission(key,value):
    intent=deepcopy(hm.LAPRAS_SURF_INTENT);intent[key]=value
    with pytest.raises(ValueError):hm.HMTeachingController(intent)


@pytest.mark.parametrize('change',[
    lambda p:p['party'][-1].update(moves=AFTER,pp=[15,15,15,30]),
    lambda p:p['party'][-1].update(moves=[55,34,54,47]),
    lambda p:p['party'][-1].update(species=7,species_name='NIDOKING'),
    lambda p:p['party'][-1].update(status=8),
    lambda p:p['party'][-1]['pp'].__setitem__(0,255),
    lambda p:p['inventory'].__setitem__(2,dict(item=198,quantity=2)),
    lambda p:p['inventory'].pop(2),lambda p:p.update(party_read_valid=False),
])
def test_wrong_initial_learner_moves_hm_or_read_proof_never_opens_start(change):
    s=Session();change(s.p);review(s.call(ready=True,window=False));assert not s.c.actions


def test_wrong_reference_commit_or_incompatible_species_rejects(monkeypatch):
    original=hm.reference
    for commit,compatible in [('wrong',True),(hm.SOURCE_COMMIT,False)]:
        ref=deepcopy(original());ref['source_commit']=commit
        if not compatible:ref['species']['LAPRAS']['tmhm'].remove('SURF')
        monkeypatch.setattr(hm,'reference',lambda r=ref:r)
        s=Session();review(s.call(ready=True,window=False));assert not s.c.actions


@pytest.mark.parametrize('change',[
    lambda p:p['party'][-1]['moves'].__setitem__(1,57),
    lambda p:p['party'][-1]['pp'].__setitem__(1,14),
    lambda p:p['party'][0].update(hp=134),
    lambda p:p['party'][0]['pp'].__setitem__(0,24),
    lambda p:p['inventory'].reverse(),lambda p:p['inventory'].pop(2),
    lambda p:p.update(money=41065),lambda p:p['party'][-1].update(exp=27001),
])
def test_only_expected_slot_and_its_base_pp_may_change_after_selection(change):
    s=Session();s.to_receipt();s.install();change(s.p);review(s.call());assert not s.c.seen_learned


@pytest.mark.parametrize('wrong',['label','duplicate','foreign','wrong_receipt'])
def test_forget_page_and_receipt_pollution_never_confirms_another_move(wrong):
    s=Session();s.to_forget();r=s.forget()
    if wrong=='label':clear(r,6,8,19,8);put(r,6,8,'BODY SLAM')
    elif wrong=='duplicate':put(r,5,9,'▶')
    elif wrong=='foreign':put(r,0,0,'X')
    else:r=s.dialog([(14,'LAPRAS forgot'),(16,'MIST!')],on_party=True,arrow=16)
    review(s.call(r));assert not s.c.replacement_selected


def test_protected_slots_are_navigated_up_until_water_gun_without_confirming_them():
    s=Session();s.to_forget()
    for y in (11,10,9):
        s.expected(s.forget(y),'up');assert not s.c.replacement_selected
    assert s.call(s.forget(9),same=True)['available_actions']==['wait']
    s.expected(s.forget(8),'a');assert s.c.replacement_selected


def test_full_no_arrow_prompt_waits_and_old_prompt_or_sameframe_cannot_resend_a():
    s=Session();s.expected(canvas(),'start',ready=True,window=False);s.expected(start(),'a')
    for n in range(s.hm_index+1):s.expected(bag(s.p,0,n),'a' if n==s.hm_index else 'down')
    s.expected(use(s.p,s.offset,s.cursor),'a')
    r=s.dialog([(14,'Booted up an HM!')])
    assert s.call(r)['available_actions']==['wait']
    r=s.dialog([(14,'Booted up an HM!')],arrow=16)
    s.expected(r,'a')
    assert s.call(r,same=True)['available_actions']==['wait']
    assert s.call(r)['available_actions']==['wait']
    assert s.call()['available_actions']==['wait']
    assert 'previous' not in inspect.signature(hm.HMTeachingController.context).parameters


@pytest.mark.parametrize('key,value',[('map_id',155),('map_id',188),('map_id',171.0),
    ('target',[3,3]),('target',[3,True]),('kind','move'),('hm_intent',hm.SURF_INTENT)])
def test_bridge_accepts_only_new_exact_cinnabar_center_intent(key,value):
    s=Session(via_bridge=True);s.plan['steps'][0][key]=deepcopy(value)
    review(s.call(ready=True,window=False));assert not bridge._CONTROLLERS


def test_wrong_actual_location_defers_to_navigation_not_new_transaction():
    s=Session(via_bridge=True)
    state=dict(frame=1,location=dict(map_id=171,x=3,y=3),progress=s.p)
    assert bridge.context(state,s.plan,'lapras-surf',packet(window=False),object()) is None
    assert not bridge._CONTROLLERS


def test_completed_fly_owner_can_yield_to_new_lapras_step_without_rebuilding_fly():
    s=Session(via_bridge=True)
    old=hm.HMTeachingController(hm.FLY_INTENT);old.waits=8;old.stage='complete'
    bridge._CONTROLLERS['old-fly']=old;bridge._BINDINGS['old-fly']=('original',)
    bridge._COMPLETED.add('old-fly')
    s.expected(canvas(),'start',ready=True,window=False)
    assert bridge._CONTROLLERS['old-fly'] is old and old.waits==8
    assert bridge._CONTROLLERS['lapras-surf'] is not old
    s.plan['resume_revision']=3
    new=s.c;s.expected(start(),'a');assert s.c is new


def test_unfinished_fly_owner_still_blocks_new_surf_and_same_id_rebinding_is_rejected():
    s=Session(via_bridge=True)
    bridge._BINDINGS['old-fly']=('original',)
    out=s.call(ready=True,window=False);review(out);assert out['review_reason']=='hm_teaching_owner_changed'
    bridge._COMPLETED.add('old-fly')
    bridge._BINDINGS['lapras-surf']=('old-fly-intent',)
    out=s.call(ready=True,window=False);review(out);assert out['review_reason']=='hm_teaching_intent_changed'


@pytest.mark.parametrize('kind,map_id,target',[
    ('teach_surf_nidoking',155,(4,5)),('teach_strength_snorlax',155,(4,5)),
    ('teach_fly_fearow',188,(1,3))])
def test_legacy_three_intent_locations_are_unchanged(kind,map_id,target):
    assert bridge._INTENT_LOCATIONS[kind][1:]==(map_id,target)
    assert bridge._INTENT_LOCATIONS['teach_surf_lapras'][1:]==(171,(3,4))
