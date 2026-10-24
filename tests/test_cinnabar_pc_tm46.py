"""紅蓮171玩家13,4 UP，僅TM46單件可逆存物；純原生格與fake getter。

fixed a536711 hidden_events327–330＋CheckIfCoordsInFrontOfPlayerMatch，
前方13,3需玩家Y=4；不改原金黃兩種意圖或共用parser。
"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from laya_pokemon import player_pc_deposit as pc, player_pc_bridge as bridge
from tests import test_player_pc_deposit as old
from tests import test_player_pc_bridge as oldbridge


LOC={'map_id':171,'x':13,'y':4}
INTENT={**pc.INTENT_BASE,'map_id':171,'item':246}


def bag(p,offset=0,cursor=0,marker='▶'):
    c=old.blank()
    for y,word in [(2,'WI'),(4,'DE'),(6,'TO'),(8,'LO')]:old.put(c,2,y,word)
    c[4][1]='▷';printed=0
    for n in range(4):
        index,y=offset+n,4+n*2
        if index==len(p['inventory']):old.put(c,6,y,'CANCEL');break
        if index>len(p['inventory']):break
        entry=p['inventory'][index];old.put(c,6,y,pc._name(entry['item']))
        if entry['item'] not in pc._KEY_ITEMS:old.put(c,14,y+1,f"×{entry['quantity']:2}")
        printed+=1
    if printed==4:c[11][18]='▼'
    c[4+cursor*2][5]=marker
    return old.dialogue('What do you want','to deposit?',upper=c,arrow=False)


def quantity(p,offset,cursor):
    c=bag(p,offset,cursor,'▷')
    for y in range(9,12):
        for x in range(15,20):c[y][x]=' '
    old.put(c,16,10,'×01')
    return old.dialogue('How many?',upper=c,arrow=False)


class Session(old.Session):
    def __init__(self):
        super().__init__()
        self.controller=pc.PlayerPCDepositController(INTENT)
        ids=[4,246,43,198,199,197,196,48,72,73,74,63,45,6,49,42,211,228,201,202]
        self.p['inventory']=[dict(item=i,quantity=6 if i==4 else 1) for i in ids]
        self.items=[dict(item=234,quantity=1),dict(item=221,quantity=1)]
    def call(self,*args,**kw):
        frame=self.frame+int(not kw.get('same',False))
        signal=dict(profile=pc.PROFILE,source_commit=pc.SOURCE_COMMIT,read_valid=True,read_error=None,
            observation_frame=frame,location=deepcopy(LOC),facing='up',facing_raw=4,count=len(self.items),items=deepcopy(self.items))
        kw.setdefault('location',deepcopy(LOC));kw.setdefault('signal',signal)
        return super().call(*args,**kw)
    def to_quantity(self):
        self.to_bag()
        self.expect(bag(self.p,0,0),'down','a')
        self.expect(bag(self.p,0,1),'a','down')
        return quantity(self.p,0,1)


def test_full_twenty_to_nineteen_native_tm46_transfer_and_two_closed_frames():
    s=Session();before=deepcopy(s.p);original_pc=deepcopy(s.items)
    q=s.to_quantity();s.expect(q,'a','a');s.transfer()
    s.expect(old.dialogue('TM46 was','stored via PC.',upper=q),'a','a')
    s.expect(bag(s.p),'b','a');s.expect(old.player(4),'b','b');s.expect(old.main(2),'b','b')
    assert not s.expect(old.blank(),'wait','b',ready=True,window=False)['pc_deposit_complete']
    assert not s.call(old.blank(),('b',),ready=True,window=False,same=True)['pc_deposit_complete']
    assert s.expect(old.blank(),'wait','wait',ready=True,window=False)['pc_deposit_complete']
    assert len(s.p['inventory'])==19 and s.p['inventory']==[i for i in before['inventory'] if i['item']!=246]
    assert s.items==original_pc+[dict(item=246,quantity=1)]
    assert s.p['party']==before['party'] and s.p['money']==before['money']


@pytest.mark.parametrize('bad',[{**INTENT,'map_id':182},{**INTENT,'map_id':170},
    {**INTENT,'item':234},{**INTENT,'item':221},{**INTENT,'item':197},
    {**INTENT,'item':43},{**INTENT,'quantity':2},{**INTENT,'player_y':3},
    {**INTENT,'item':True},{**INTENT,'quantity':True}])
def test_no_arbitrary_map_item_hm_key_quantity_or_pc_body(bad):
    with pytest.raises(ValueError):pc.PlayerPCDepositController(bad)


@pytest.mark.parametrize('fault',['bag','pc','party','money','quantity','partial_receipt'])
def test_tm46_transfer_cannot_claim_receipt_without_exact_original_ledgers(fault):
    s=Session();q=s.to_quantity();s.expect(q,'a','a');before=deepcopy(s.p);before_pc=deepcopy(s.items);s.transfer()
    if fault=='bag':s.p['inventory']=before['inventory']
    elif fault=='pc':s.items=before_pc
    elif fault=='party':s.p['party'][0]['hp']-=1
    elif fault=='money':s.p['money']-=1
    elif fault=='quantity':s.items[-1]['quantity']=2
    r=old.dialogue('TM46 was','stored via' if fault=='partial_receipt' else 'stored via PC.',upper=q,arrow=fault!='partial_receipt')
    out=s.call(r,('a',))
    if fault=='partial_receipt':assert out['available_actions']==['wait'] and not s.controller.receipt_seen
    else:old.review(out)
    assert not out.get('pc_deposit_complete')


def sdk():
    return SimpleNamespace(**pc.SDK_ANCHORS,MAPS={'cinnabar_pokecenter':171})


class Memory:
    def __init__(self,items=None):
        items=items if items is not None else [dict(item=234,quantity=1),dict(item=221,quantity=1)]
        self.values={0xD35E:171,0xD361:4,0xD362:13,0xC109:4,pc.PC_COUNT:len(items)}
        self.values.update({pc.PC_ITEMS+i:0 for i in range(101)})
        for n,i in enumerate(items):self.values[pc.PC_ITEMS+2*n]=i['item'];self.values[pc.PC_ITEMS+2*n+1]=i['quantity']
        self.values[pc.PC_ITEMS+2*len(items)]=255;self.reads=[];self.hook=None
    def __getitem__(self,a):
        self.reads.append(a);return self.hook(a,self.values[a]) if self.hook else self.values[a]
    def __setitem__(self,*args):raise AssertionError('no memory writes')


def read(mem=None,c=None):
    mem=mem or Memory()
    return pc.read_player_pc(SimpleNamespace(memory=mem,frame_count=10),observation_frame=10,expected_location=deepcopy(LOC),constants=c or sdk())


def test_new_reader_uses_only_correct_sdk_map_anchor_and_all_fifty_slots():
    mem=Memory();before=deepcopy(mem.values);out=read(mem)
    assert out['read_valid'] and out['location']==LOC and out['items']==[dict(item=234,quantity=1),dict(item=221,quantity=1)]
    expected=[0xD35E,0xD361,0xD362,0xC109,*range(pc.PC_COUNT,pc.PC_ITEMS+101)]
    assert mem.reads==expected*2 and mem.values==before
    assert not read(c=SimpleNamespace(**pc.SDK_ANCHORS,MAPS={'saffron_pokecenter':182}))['read_valid']


@pytest.mark.parametrize('count',[0,49,50])
def test_cinnabar_zero_fortynine_fifty_capacity_and_terminator(count):
    ids=[i for i in range(1,251) if pc._name(i) not in (None,'?????')][:count]
    mem=Memory([dict(item=i,quantity=1) for i in ids]);assert read(mem)['count']==count
    mem.values[pc.PC_ITEMS+2*count]=0;assert read(mem)['items'] is None


@pytest.mark.parametrize('region',[pc.PC_COUNT,pc.PC_ITEMS,pc.PC_ITEMS+100])
def test_second_sample_unknown_byte_torn_or_bool_is_never_empty_pc(region):
    mem=Memory();n=4+1+101
    mem.hook=lambda a,v:False if a==region and len(mem.reads)>n else v
    assert not read(mem)['read_valid']


def new_bridge(e):
    e.step.update(map_id=171,pc_intent=deepcopy(INTENT));e.state['location']=deepcopy(LOC)
    return e


def test_new_bridge_preserves_same_controller_budget_owner_and_actual_previous(monkeypatch):
    e=new_bridge(oldbridge.env.__wrapped__(monkeypatch));oldbridge.call(e,previous=('down','up'))
    c=bridge._CONTROLLERS['pc-tm34'];base=c.baseline
    c.started=1.;c.calls=19;c.waits=7
    oldbridge.call(e)
    assert bridge._CONTROLLERS['pc-tm34'] is c and c.baseline is base
    assert c.args['location']==LOC and c.args['previous']==('up',)
    assert (c.started,c.calls,c.waits)==(1.,19,7)


def test_old_completed_tm34_id_cannot_be_rebound_to_cinnabar_tm46(monkeypatch):
    e=oldbridge.env.__wrapped__(monkeypatch);oldbridge.call(e)
    c=bridge._CONTROLLERS['pc-tm34'];base=c.baseline;bridge._COMPLETED.add('pc-tm34')
    new_bridge(e)
    out,_=oldbridge.call(e)
    assert out['review_reason']=='player_pc_intent_changed' and bridge._CONTROLLERS['pc-tm34'] is c and c.baseline is base


@pytest.mark.parametrize('bad',[[],{},True,197,43,234,221])
def test_new_bridge_wrong_or_unhashable_intent_item_is_review_without_binding(monkeypatch,bad):
    e=new_bridge(oldbridge.env.__wrapped__(monkeypatch));e.step['pc_intent']['item']=bad
    assert oldbridge.call(e)[0]['review_reason']=='player_pc_explicit_intent_unverified'
    assert not bridge._BINDINGS
