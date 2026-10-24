"""高runtime frame的真pure＋真bridge合成聯測；不建立遊戲或模型。"""
from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import pytest
import laya_pokemon

ROOT=Path(laya_pokemon.__file__).resolve().parents[2]
STAGE=ROOT/'.local/staged-cinnabar-purchase-integration-20261024'


def sources(test_path):
    p=Path(test_path).resolve()
    if p not in (STAGE/'test_true_purchase_integration.py',ROOT/'tests/test_true_purchase_integration.py'):
        raise RuntimeError('未知integration測試位置')
    # 父層正式採用後的最新契約：兩種測試位置皆只載正式來源，不退回stage。
    return ROOT/'src/laya_pokemon/cinnabar_purchase.py',ROOT/'src/laya_pokemon/cinnabar_purchase_bridge.py'


PURE_PATH,BRIDGE_PATH=sources(__file__)


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
    return m


@pytest.fixture
def pair():
    cp=module(PURE_PATH,'laya_pokemon._integration_true_cinnabar_purchase')
    prior=getattr(laya_pokemon,'cinnabar_purchase',None);had=hasattr(laya_pokemon,'cinnabar_purchase')
    reload=importlib.reload
    try:
        laya_pokemon.cinnabar_purchase=cp
        importlib.reload=lambda m:m if m is cp else reload(m)
        b=module(BRIDGE_PATH,'laya_pokemon._integration_true_cinnabar_purchase_bridge')
    finally:
        importlib.reload=reload
        if had:laya_pokemon.cinnabar_purchase=prior
        else:del laya_pokemon.cinnabar_purchase
    assert b.cinnabar_purchase is cp
    return cp,b


STOCK=[('ULTRA BALL',1200),('GREAT BALL',600),('HYPER POTION',1500),
       ('MAX REPEL',700),('ESCAPE ROPE',550),('FULL HEAL',600),('REVIVE',1500)]


def native(money,*,view='main',offset=0,cursor=0,active=True,q=10,item=18,words='buying',arrow=False,yes=0):
    a=[[' ']*20 for _ in range(18)]
    def put(x,y,s):a[y][x:x+len(s)]=list(s)
    def clear(x1,y1,x2,y2):
        for y in range(y1,y2+1):a[y][x1:x2+1]=[' ']*(x2-x1+1)
    for label,y in [('BUY',1),('SELL',3),('QUIT',5)]:put(2,y,label)
    put(13,0,'MONEY');put(12,1,('¥'+str(money)).rjust(7));put(1,1,'▶'if view=='main'and active else'▷')
    if view!='main':
        clear(4,2,19,12)
        for j,(name,price)in enumerate(STOCK[offset:offset+4]):
            put(6,4+2*j,name);put(11,5+2*j,('¥'+str(price)).rjust(7))
        put(5,4+2*cursor,'▶'if view=='shop'and active else'▷')
        if view=='shop'and arrow:put(18,11,'▼')
    cost=1500 if item==18 else 600
    if view in ('quantity','yesno'):
        clear(7,9,19,11);put(8,10,'×'+str(q).zfill(2));put(12,10,('¥'+str(q*cost)).rjust(7))
    if view=='yesno':
        clear(14,7,19,11);put(16,8,'YES');put(16,10,'NO');put(15,8+2*yes,'▶')
    label='HYPER POTION'if item==18 else'FULL HEAL'
    text={'greeting':('HI THERE!','MAY I HELP YOU?'),'buying':('TAKE YOUR TIME.',''),
          'prefix':(label+'?','THAT WILL BE'),'tail':('THAT WILL BE','¥'+str(q*cost)+'. OK?'),
          'bought':('HERE YOU ARE!','THANK YOU!'),'else':('IS THERE ANYTHING','ELSE I CAN DO?'),
          'thanks':('THANK YOU!','')}
    clear(0,12,19,17);put(1,14,text[words][0]);put(1,16,text[words][1])
    if arrow and words in ('prefix','bought'):put(18,16,'▼')
    return a


def progress():
    names=[(19,'LAPRAS'),(132,'SNORLAX'),(7,'NIDOKING'),(102,'EEVEE'),(154,'VENUSAUR'),(35,'FEAROW')]
    ids=[(4,6),(42,1),(49,1),(63,1),(196,1),(224,1),(74,1),(72,1),(40,1),
         (73,1),(3,9),(198,1),(199,1),(48,1),(1,1),(197,1),(43,1)]
    return dict(profile='gen1-wrapper-ram-progress-v1-unvalidated',initialization_candidate=True,
        party_read_valid=True,party_count=6,money=69332,inventory=[dict(item=i,quantity=q)for i,q in ids],
        party=[dict(species=i,species_name=n,level=38,exp=60000,hp=150,max_hp=150,status=0,
                    moves=[33,0,0,0],pp=[35,0,0,0])for i,n in names])


class Memory:
    def __init__(self):self.values={0xD35E:172,0xC109:8,0xD361:5,0xD362:2};self.reads=[]
    def __getitem__(self,a):self.reads.append(a);return self.values[a]
    def __setitem__(self,*args):raise AssertionError('no memory writes')


class Session:
    def __init__(self,pair,which,progress_before=None):
        self.cp,self.b=pair;self.intent=deepcopy(getattr(self.cp,which));self.p=deepcopy(progress_before or progress())
        self.before=deepcopy(self.p);self.frame=1732097;self.prev=[];self.off=0 if self.intent['item']==18 else 3
        self.game=SimpleNamespace(memory=Memory(),frame_count=self.frame);self.history=[]
        self.step=dict(id=which,kind='interact',mechanic='cinnabar_purchase',map_id=172,target=[2,5],face='left',purchase_intent=deepcopy(self.intent))
        self.plan=dict(steps=[self.step,dict(id='after',kind='move',map_id=172,target=[3,5])])
    @property
    def c(self):return self.b._CONTROLLER[self.step['id']]
    def row(self,**kw):return native(self.p['money'],item=self.intent['item'],**kw)
    def call(self,cells=None,*,window=True,advance=40,fault=None):
        if self.history:self.frame+=advance
        self.game.frame_count=self.frame
        cells=deepcopy(cells if cells is not None else[[' ']*20 for _ in range(18)])
        visible=[(i,''.join(r).rstrip())for i,r in enumerate(cells)if re.search(r'[A-Za-z0-9]{2,}',''.join(r))][:12]
        text=dict(profile=self.cp.TEXT_PROFILE,read_valid=True,alignment_verified=True,read_error=None,
            window_visible=window,cells=cells,lines=[s for _,s in visible],line_rows=[i for i,_ in visible],observation_frame=self.frame)
        p=deepcopy(self.p);p['observation_frame']=self.frame
        state=dict(frame=self.frame,location=dict(map_id=172,x=2,y=5),progress=p,
            battle_state=dict(kind='none',raw=0,active=False,observation_frame=self.frame))
        grid=dict(tileset_id=2,observation_frame=self.frame,verified_location=[172,2,5],screen_cells_verified=90,
            tiles=[[0x11]*8 for _ in range(8)],walkable=[[1]*8 for _ in range(8)])
        if fault=='battle_frame':state['battle_state']['observation_frame']+=1
        if fault=='text_frame':text['observation_frame']+=1
        if fault=='no_previous':self.prev=['wait']
        original=deepcopy((state,text,grid,self.prev,self.plan,self.game.memory.values))
        out,next_id=self.b.context(self.game,state,self.plan,self.step['id'],text,grid,self.prev)
        assert (state,text,grid,self.prev,self.plan,self.game.memory.values)==original
        self.history.append(dict(frame=self.frame,result=deepcopy(out),next_id=next_id))
        self.prev=[out['available_actions'][0]]
        return out,next_id
    def expect(self,cells,action,**kw):
        out,sid=self.call(cells,**kw)
        assert out['phase']!='campaign_review',out
        assert out['available_actions'][0]==action,out
        return out,sid
    def confirm(self):
        self.expect(None,'a',window=False)
        assert type(self.c)is self.cp.CinnabarPurchaseController
        self.expect(self.row(words='greeting'),'a')
        off=cur=0;target=2 if self.intent['item']==18 else 5
        for index in range(target+1):
            self.expect(self.row(view='shop',offset=off,cursor=cur,arrow=True),'a'if index==target else'down')
            if index<target:
                if cur<2:cur+=1
                else:off+=1
        assert(off,cur)==(self.off,2)
        for q in range(1,11):self.expect(self.row(view='quantity',offset=self.off,cursor=2,q=q),'up'if q<10 else'a')
        self.expect(self.row(view='quantity',offset=self.off,cursor=2,words='prefix'),'wait')
        self.expect(self.row(view='quantity',offset=self.off,cursor=2,words='prefix',arrow=True),'a')
        self.expect(self.row(view='yesno',offset=self.off,cursor=2,words='tail',yes=1),'up')
        self.expect(self.row(view='yesno',offset=self.off,cursor=2,words='tail',yes=0),'a')
    def purchase_observation(self):
        self.p['inventory'].append(dict(item=self.intent['item'],quantity=10));self.p['money']-=self.intent['total_price']
    def close(self):
        self.expect(self.row(view='quantity',offset=self.off,cursor=2,words='bought',arrow=True),'a')
        self.expect(self.row(view='shop',offset=self.off,cursor=0,arrow=True),'b')
        self.expect(self.row(words='else'),'b')
        self.expect(self.row(words='thanks',active=False),'wait')
        self.expect(self.row(words='thanks',active=False),'a',advance=16)
        first,_=self.expect(None,'wait',window=False);assert not first.get('cinnabar_purchase_complete')
        final,sid=self.expect(None,'wait',window=False,advance=3)
        assert final['cinnabar_purchase_complete']is True and final['field_move_complete']is True and sid=='after'
        assert final['field_move_kind']=='cinnabar-purchase'
        assert self.p['party']==self.before['party'] and self.p['money']==self.before['money']-self.intent['total_price']
        assert self.p['inventory']==self.before['inventory']+[dict(item=self.intent['item'],quantity=10)]
        assert self.c.last_frame>1732097 and self.c.complete
        return final


@pytest.mark.parametrize('which',['HYPER_POTION_INTENT','FULL_HEAL_INTENT'])
def test_true_bridge_and_pure_full_high_frame_flow(pair,which):
    s=Session(pair,which);s.confirm();s.purchase_observation();out=s.close()
    assert out['quantity_purchased']==10 and out['money_spent']==s.intent['total_price']


def test_both_true_purchases_with_new_owners_keep17_to19_bag_slots_and_tm38_space(pair):
    a=Session(pair,'HYPER_POTION_INTENT');a.confirm();a.purchase_observation();a.close()
    b=Session(pair,'FULL_HEAL_INTENT',a.p);b.frame=a.frame+40
    b.confirm();b.purchase_observation();b.close()
    assert len(a.p['inventory'])==18 and len(b.p['inventory'])==19
    assert b.p['money']==69332-15000-6000 and b.p['party']==a.before['party']


@pytest.mark.parametrize('fault',['offset','cursor'])
def test_true_postbuy_fullheal_retains_offset3_resets_cursor0_or_sticky_review(pair,fault):
    s=Session(pair,'FULL_HEAL_INTENT');s.confirm();s.purchase_observation()
    s.expect(s.row(view='quantity',offset=3,cursor=2,words='bought',arrow=True),'a')
    out,sid=s.call(s.row(view='shop',offset=0 if fault=='offset'else 3,cursor=2 if fault=='cursor'else 0,arrow=True))
    assert out['phase']=='campaign_review'and sid==s.step['id']and s.c.error
    error=s.c.error;out,_=s.call(s.row(view='shop',offset=3,cursor=0,arrow=True))
    assert s.c.error==error and out['available_actions']==['wait']and not s.c.complete


@pytest.mark.parametrize('fault',['battle_frame','text_frame'])
def test_runtime_frame_mismatch_never_calls_pure_or_advances_existing_owner(pair,fault):
    s=Session(pair,'HYPER_POTION_INTENT');s.expect(None,'a',window=False)
    c=s.c;calls=c.calls;base=c.baseline
    out,sid=s.call(s.row(words='greeting'),fault=fault)
    assert out['phase']=='campaign_review'and sid==s.step['id']and c.calls==calls and c.baseline is base


def test_true_unknown_ui_is_sticky_not_recovered_by_later_valid_page(pair):
    s=Session(pair,'HYPER_POTION_INTENT');s.expect(None,'a',window=False)
    page=s.row(words='greeting');page[0][0]='X';out,_=s.call(page)
    assert out['phase']=='campaign_review'and s.c.error;error=s.c.error
    out,_=s.call(s.row(words='greeting'))
    assert out['available_actions']==['wait']and s.c.error==error and not s.c.yes_issued


@pytest.mark.parametrize('frame',[False,1732097.0,-1])
def test_true_pure_invalid_frame_types_still_reject_after_high_frame_fix(pair,frame):
    cp,_=pair;c=cp.CinnabarPurchaseController(cp.HYPER_POTION_INTENT)
    result=c.context(dict(profile=cp.TEXT_PROFILE,read_valid=True,alignment_verified=True,read_error=None,
        window_visible=False,cells=[[' ']*20 for _ in range(18)]),progress(),
        location=dict(map_id=172,x=2,y=5,facing='left',facing_raw=8),
        battle_state=dict(kind='none',raw=0,active=False),frame=frame,now=0.,previous=[],overworld_ready=True)
    assert result['phase']=='campaign_review'and result['available_actions']==['wait']and c.baseline is None


@pytest.mark.parametrize('where',['stage','formal','unknown'])
def test_loader_only_known_positions_and_always_formal_true_modules(where):
    if where=='unknown':
        with pytest.raises(RuntimeError):sources(ROOT/'tests/other.py')
    else:
        p=(STAGE if where=='stage'else ROOT/'tests')/'test_true_purchase_integration.py'
        assert sources(p)==(ROOT/'src/laya_pokemon/cinnabar_purchase.py',ROOT/'src/laya_pokemon/cinnabar_purchase_bridge.py')
