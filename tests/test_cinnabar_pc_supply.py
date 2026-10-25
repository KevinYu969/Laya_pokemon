"""指定暫存／正式tests雙路徑隔離loader；只核紅蓮固定單件存物。"""
from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import laya_pokemon
from tests import test_player_pc_deposit as old

ROOT=Path(laya_pokemon.__file__).resolve().parents[2]
STAGE=ROOT/'.local/staged-cinnabar-pc-supply-20261024'


def source_paths(test_path):
    path=Path(test_path).resolve()
    if path==STAGE/'test_cinnabar_pc_supply.py':
        return STAGE/'player_pc_deposit.py',STAGE/'player_pc_bridge.py'
    if path==ROOT/'tests/test_cinnabar_pc_supply.py':
        source=ROOT/'src/laya_pokemon'
        return source/'player_pc_deposit.py',source/'player_pc_bridge.py'
    raise RuntimeError('PC供應測試只允許指定staged目錄或本專案正式tests位置')


PC_PATH,BRIDGE_PATH=source_paths(__file__)
LOC=dict(map_id=171,x=13,y=4)
# 僅固定審核快照的道具資料；不在tests讀取私有review或真遊戲。
ACTUAL_BAG=[dict(item=i,quantity=q)for i,q in
    [(4,6),(42,1),(49,1),(63,1),(228,1),(196,1),(224,1),(74,1),(72,1),
     (40,1),(73,1),(3,9),(206,1),(198,1),(199,1),(48,1),(1,1),(197,1),(43,1)]]


def module(path,name,existing=None):
    spec=importlib.util.spec_from_file_location(name,path)
    m=existing or importlib.util.module_from_spec(spec)
    sys.modules[name]=m
    spec.loader.exec_module(m)
    return m


def load_bridge(pc,existing=None):
    """兩種位置均隔離載入；只阻止reload跳回package的另一個module。"""
    original=laya_pokemon.player_pc_deposit
    reload=importlib.reload
    try:
        laya_pokemon.player_pc_deposit=pc
        importlib.reload=lambda m:m if m is pc else reload(m)
        return module(BRIDGE_PATH,'laya_pokemon._isolated_pc_supply_bridge',existing)
    finally:
        importlib.reload=reload
        laya_pokemon.player_pc_deposit=original


@pytest.fixture
def modules(monkeypatch):
    pc=module(PC_PATH,'laya_pokemon._isolated_pc_supply_deposit')
    bridge=load_bridge(pc)
    monkeypatch.setattr(old,'pc',pc)
    def bag(p,offset=0,cursor=0,marker='▶'):
        c=old.blank()
        for y,word in ((2,'WI'),(4,'DE'),(6,'TO'),(8,'LO')):old.put(c,2,y,word)
        c[4][1]='▷';printed=0
        for n in range(4):
            index,y=offset+n,4+n*2
            if index==len(p['inventory']):old.put(c,6,y,'CANCEL');break
            if index>len(p['inventory']):break
            v=p['inventory'][index];old.put(c,6,y,pc._name(v['item']))
            if v['item']not in pc._KEY_ITEMS:old.put(c,14,y+1,f"×{v['quantity']:2}")
            printed+=1
        if printed==4:c[11][18]='▼'
        c[4+cursor*2][5]=marker
        return old.dialogue('What do you want','to deposit?',upper=c,arrow=False)
    monkeypatch.setattr(old,'bag',bag)
    return pc,bridge


class Session(old.Session):
    def __init__(self,pc,item,map_id=171,inventory=None,items=None):
        super().__init__()
        self.pc=pc;self.loc=dict(map_id=map_id,x=13,y=4)
        self.controller=pc.PlayerPCDepositController(deepcopy(pc.INTENTS[(map_id,item)]))
        if inventory is not None:self.p['inventory']=deepcopy(inventory)
        if items is not None:self.items=deepcopy(items)
    def call(self,*args,**kw):
        frame=self.frame+int(not kw.get('same',False))
        signal=dict(profile=self.pc.PROFILE,source_commit=self.pc.SOURCE_COMMIT,
            read_valid=True,read_error=None,observation_frame=frame,location=deepcopy(self.loc),
            facing='up',facing_raw=4,count=len(self.items),items=deepcopy(self.items))
        kw.setdefault('location',deepcopy(self.loc));kw.setdefault('signal',signal)
        return super().call(*args,**kw)


def complete(s):
    before=deepcopy(s.p);prior=deepcopy(s.items);item=s.controller.intent['item']
    q=s.to_quantity();s.expect(q,'a','a');s.transfer()
    s.expect(old.dialogue(s.pc._name(item)+' was','stored via PC.',upper=q),'a','a')
    s.expect(old.bag(s.p,s.offset,s.cursor),'b','a')
    s.expect(old.player(4),'b','b');s.expect(old.main(2),'b','b')
    assert not s.expect(old.blank(),'wait','b',ready=True,window=False)['pc_deposit_complete']
    assert not s.call(old.blank(),('b',),ready=True,window=False,same=True)['pc_deposit_complete']
    assert s.expect(old.blank(),'wait','wait',ready=True,window=False)['pc_deposit_complete']
    assert s.p['inventory']==[v for v in before['inventory']if v['item']!=item]
    assert s.items==prior+[dict(item=item,quantity=1)]
    assert s.p['party']==before['party'] and s.p['money']==before['money']
    return s


def test_exact_registry_and_source_tm_names(modules):
    pc,_=modules
    assert set(pc.INTENTS)=={(182,234),(182,221),(171,246),(171,228),(171,206),(171,238)}
    assert pc._name(228)=='TM28' and pc._name(206)=='TM06' and pc._name(238)=='TM38'
    for mid,item in pc.INTENTS:
        assert pc.INTENTS[(mid,item)]=={**pc.INTENT_BASE,'map_id':mid,'item':item}


@pytest.mark.parametrize('mid,item',[(171,228),(171,206),(171,246),(182,234),(182,221)])
def test_all_five_native_paths_complete_only_exact_transfer_and_two_fresh_closed(modules,mid,item):
    pc,_=modules
    inventory=deepcopy(ACTUAL_BAG)if item in (228,206)else old.progress()['inventory']
    if item==246:inventory=[dict(item=246,quantity=1),*deepcopy(ACTUAL_BAG)]
    s=complete(Session(pc,item,mid,inventory,[dict(item=20,quantity=1)]))
    assert len(s.p['inventory'])==len(inventory)-1


def test_two_new_sessions_preserve_pc_order_and_bag19_to17(modules):
    pc,_=modules
    prior=[dict(item=i,quantity=1)for i in (20,234,221,246)]
    a=complete(Session(pc,228,inventory=ACTUAL_BAG,items=prior))
    assert len(a.p['inventory'])==18
    b=Session(pc,206,inventory=a.p['inventory'],items=a.items)
    b.p['party']=deepcopy(a.p['party']);b.p['money']=a.p['money'];complete(b)
    assert len(b.p['inventory'])==17 and b.items==prior+[dict(item=228,quantity=1),dict(item=206,quantity=1)]
    assert b.p['party']==a.p['party']


def test_post_blaine_tm38_deposit_preserves_six_mon_level39_and_frees_one_slot(modules):
    from tests.test_battle_medicine import progress
    pc,_=modules
    inventory=[deepcopy(v) for v in ACTUAL_BAG if v['item'] not in (228,206)]
    inventory.extend([dict(item=52,quantity=10),dict(item=238,quantity=1)])
    assert len(inventory)==19
    s=Session(pc,238,inventory=inventory,items=[dict(item=i,quantity=1) for i in (20,234,221,246,228,206)])
    s.p['party']=progress()['party'];s.p['party'][2].update(level=39,hp=160,max_hp=160,exp=75193,status=0)
    complete(s)
    assert len(s.p['inventory'])==18 and s.items[-1]==dict(item=238,quantity=1)


@pytest.mark.parametrize('changes',[dict(map_id=182),dict(map_id=170),dict(item=197),dict(item=43),
    dict(item=234),dict(quantity=2),dict(quantity=True),dict(item=True),dict(map_id=True),
    dict(player_y=3),dict(facing='down'),dict(item=[]),dict(item={})])
def test_other_map_item_quantity_type_or_facing_never_constructs(modules,changes):
    pc,_=modules;intent={**pc.INTENTS[(171,228)],**changes}
    with pytest.raises(ValueError):pc.PlayerPCDepositController(intent)


@pytest.mark.parametrize('item',[228,206])
@pytest.mark.parametrize('fault',['other_party','money','bag','pc_quantity','wrong_receipt','partial_receipt'])
def test_new_items_preserve_full_ledgers_and_need_native_receipt(modules,item,fault):
    pc,_=modules;s=Session(pc,item,inventory=ACTUAL_BAG);q=s.to_quantity();s.expect(q,'a','a');s.transfer()
    if fault=='other_party':s.p['party'][1]['hp']-=1
    elif fault=='money':s.p['money']-=1
    elif fault=='bag':s.p['inventory'][-1]['quantity']+=1
    elif fault=='pc_quantity':s.items[-1]['quantity']=2
    name=pc._name(item if fault!='wrong_receipt'else(206 if item==228 else 228))
    r=s.call(old.dialogue(name+' was','stored via'if fault=='partial_receipt'else'stored via PC.',upper=q,arrow=fault!='partial_receipt'),('a',))
    if fault=='partial_receipt':assert r['available_actions']==['wait']and not s.controller.receipt_seen
    else:old.review(r)
    assert not r['pc_deposit_complete']


@pytest.mark.parametrize('item',[228,206])
def test_unexecuted_or_sameframe_candidate_cannot_transfer(modules,item):
    pc,_=modules;s=Session(pc,item,inventory=ACTUAL_BAG)
    first=s.call(old.blank(),ready=True,window=False);assert first['available_actions']==['a','wait']
    assert s.call(old.blank(),ready=True,window=False,same=True)['available_actions']==['wait']
    r=s.call(old.dialogue('KEVIN turned on','the PC.'),('wait',));old.review(r)
    assert not s.controller.transferred and s.controller.baseline['bag']==ACTUAL_BAG


class Memory:
    def __init__(self,pc):
        self.values={0xD35E:171,0xD361:4,0xD362:13,0xC109:4,pc.PC_COUNT:0}
        self.values.update({pc.PC_ITEMS+i:0 for i in range(101)});self.values[pc.PC_ITEMS]=255
        self.reads=[];self.hook=None
    def __getitem__(self,address):
        self.reads.append(address);v=self.values[address]
        return self.hook(address,v)if self.hook else v
    def __setitem__(self,*args):raise AssertionError('writes forbidden')


def read(pc,m):
    return pc.read_player_pc(SimpleNamespace(memory=m,frame_count=10),observation_frame=10,
        expected_location=LOC,constants=SimpleNamespace(**pc.SDK_ANCHORS,MAPS={'cinnabar_pokecenter':171}))


def test_original_complete_106_byte_double_getter_is_unchanged(modules):
    pc,_=modules;m=Memory(pc);assert read(pc,m)['read_valid']
    expected=[0xD35E,0xD361,0xD362,0xC109,*range(pc.PC_COUNT,pc.PC_ITEMS+101)]
    assert len(expected)==106 and m.reads==expected*2


@pytest.mark.parametrize('which',[0,4,105])
@pytest.mark.parametrize('bad',[False,0.0])
def test_second_sample_bad_type_does_not_become_safe_zero(modules,which,bad):
    pc,_=modules;m=Memory(pc);addresses=[0xD35E,0xD361,0xD362,0xC109,*range(pc.PC_COUNT,pc.PC_ITEMS+101)]
    m.hook=lambda a,v:bad if a==addresses[which]and len(m.reads)>106 else v
    assert read(pc,m)['read_valid']is False


@pytest.mark.parametrize('item',[228,206])
def test_staged_bridge_binds_only_new_exact_intent_and_preserves_previous_owner(modules,monkeypatch,item):
    pc,b=modules
    from laya_pokemon import campaign_transactions as tx
    monkeypatch.setattr(tx,'verified_blank_transaction_world',lambda *a:True)
    monkeypatch.setattr(tx,'ui_overworld_ready',lambda *a:True)
    monkeypatch.setattr(b.time,'monotonic',lambda:10.)
    m=Memory(pc);game=SimpleNamespace(memory=m,frame_count=10)
    step=dict(id='supply',kind='interact',mechanic=b.MECHANIC,map_id=171,target=[13,4],face='up',pc_intent=deepcopy(pc.INTENTS[(171,item)]))
    plan=dict(steps=[step]);p=old.progress();p['inventory']=deepcopy(ACTUAL_BAG)
    state=dict(frame=10,location=deepcopy(LOC),progress=p,battle_state=dict(kind='none',active=False,raw=0,observation_frame=10))
    out,_=b.context(game,state,plan,'supply',old.text(old.blank(),False),{},['left','up'])
    assert out['available_actions']==['a','wait'];c=b._CONTROLLERS['supply'];base=c.baseline
    assert c.last_packet[-2]==['left','up']
    b._COMPLETED.add('supply');step['pc_intent']=deepcopy(pc.INTENTS[(171,206 if item==228 else 228)])
    out,_=b.context(game,state,plan,'supply',old.text(old.blank(),False),{},['wait'])
    assert out['review_reason']=='player_pc_intent_changed'and b._CONTROLLERS['supply']is c and c.baseline is base


def test_staged_reload_keeps_controller_pending_clock_and_sticky_error(modules):
    pc,b=modules;c=pc.PlayerPCDepositController(pc.INTENTS[(171,228)])
    c.error='original';c.started=3.;c.calls=21;c.waits=7;c.pending={'action':'a'}
    b._CONTROLLERS['same']=c;b._BINDINGS['same']=('original',)
    again=load_bridge(pc,b)
    assert again is b and b._CONTROLLERS['same']is c and c.pending=={'action':'a'}
    assert (c.error,c.started,c.calls,c.waits)==('original',3.,21,7)


@pytest.mark.parametrize('where',['stage','formal','unknown'])
def test_explicit_source_paths_never_load_modules_from_an_unrecognized_test_location(where):
    if where=='stage':
        assert source_paths(STAGE/'test_cinnabar_pc_supply.py')==(STAGE/'player_pc_deposit.py',STAGE/'player_pc_bridge.py')
    elif where=='formal':
        source=ROOT/'src/laya_pokemon'
        assert source_paths(ROOT/'tests/test_cinnabar_pc_supply.py')==(source/'player_pc_deposit.py',source/'player_pc_bridge.py')
    else:
        with pytest.raises(RuntimeError):source_paths(ROOT/'tests/player_pc_deposit.py')
