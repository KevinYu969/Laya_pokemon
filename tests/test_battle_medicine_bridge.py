"""真 staged bridge/pure/trainer＋正式 player/text/runtime readers 聯測。

Fake: RAM、frame、clock、screen tiles、party/inventory progress、plan、actual previous。
不載 ROM、不建立 PyBoy、不發按鍵；getter/controller/decoder 沒有 fake 替身。
"""
from copy import deepcopy
import importlib
import importlib.abc
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import laya_pokemon
from laya_pokemon import battle, observation, player_battle
import pytest

from test_battle_medicine import (progress, record, cmd, bag, party, dialog, blank,
                                 enemy_prompt)


ROOT=Path(laya_pokemon.__file__).resolve().parents[2]
STAGE=ROOT/'.local/staged-medicine-final-20261025'


def source_for_test(test_path,filename='battle_medicine_bridge.py'):
    p=Path(test_path).resolve()
    if p==STAGE/'test_battle_medicine_bridge.py':return STAGE/filename
    if p==ROOT/'tests/test_battle_medicine_bridge.py':return ROOT/'src/laya_pokemon'/filename
    raise RuntimeError('Only exact staged or formal test location is supported')


class Memory:
    def __init__(self):
        self.values={0xD35E:166,0xD362:3,0xD361:4,0xD057:2,0xD05A:0,
                     0xCC2F:2,0xD163:6,0xD059:247,0xD127:47,0xD06D:0,0xFF40:0x91}
        self.reads=[];self.hook=None
    def __getitem__(self,address):
        self.reads.append(address);value=self.values[address]
        return self.hook(address,value) if self.hook else value
    def __setitem__(self,*args):raise AssertionError('RAM write forbidden')


class Game:
    def __init__(self):
        self.frame_count=1730000;self.memory=Memory()
        self.screen=SimpleNamespace(tilemap_position_list=[(0,0,0,144)]*144)
        self.tiles={};self.decoding={}
        outer=self
        class Tiles:
            def __getitem__(self,xy):return outer.tiles[xy]
        self.tilemap_background=self.tilemap_window=Tiles()
    def show(self,cells):
        chars=sorted({v for row in cells for v in row})
        encoding={v:i for i,v in enumerate(chars)}
        self.decoding={i:v for v,i in encoding.items()}
        self.tiles={(x,y):encoding[v] for y,row in enumerate(cells) for x,v in enumerate(row)}
    def tick(self,*args,**kwargs):raise AssertionError('tick forbidden')
    def button(self,*args,**kwargs):raise AssertionError('button forbidden')
    def button_press(self,*args,**kwargs):raise AssertionError('button forbidden')


class Session:
    def __init__(self,b,monkeypatch,item=18):
        self.b=b;self.game=Game();self.item=item;self.now=0.;self.prev=[];self.started=False
        self.p=progress(item,status=16 if item==52 else 0);self.before=deepcopy(self.p)
        self.player=player_battle.decode_player_battle(self.player_record())['player']
        from laya_pokemon.wild_opponent import decode_enemy_mon
        self.enemy=decode_enemy_mon(record())['enemy']
        self.intent=deepcopy(b.bm.HYPER_POTION_INTENT if item==18 else b.bm.FULL_HEAL_INTENT)
        self.step=dict(id='blaine',kind='interact',map_id=166,target=[3,4],face='up',
                       event='beat_blaine',battle_supply=b.SUPPLY)
        self.plan=dict(steps=[self.step,dict(id='after',kind='move')]);self.state=None
        self.constants=SimpleNamespace(CURRENT_OPPONENT_ADDRESS=0xD059,BATTLE_TYPE_ADDRESS=0xD05A,
            CURRENT_ENEMY_LEVEL_ADDRESS=0xD127,PARTY_COUNT_ADDRESS=0xD163,PARTY_SPECIES_ADDRESS=0xD164,
            PARTY_MONS_ADDRESS=0xD16B,PARTY_MON_SIZE=44,PARTY_LENGTH=6,OBTAINED_BADGES_ADDRESS=0xD356)
        self.monkeypatch=monkeypatch;self.clock(monkeypatch)
    def clock(self,monkeypatch):
        monkeypatch.setattr(self.b,'_sdk_constants',lambda:self.constants)
        monkeypatch.setattr(self.b.time,'monotonic',lambda:self.now)
    def player_record(self):
        m=self.p['party'][2]
        return record(19,38,m['hp'],m['max_hp'],m['status'],m['moves'],m['pp'])
    def sync(self):
        # literal source addresses, independent of the candidate guard list
        m=self.game.memory.values
        m.update({0xD014+i:v for i,v in enumerate(self.player_record())})
        r=record(self.enemy['species'],self.enemy['level'],self.enemy['hp'],self.enemy['max_hp'],
                 self.enemy['status'],self.enemy['moves'],self.enemy['pp'])
        m.update({0xCFE5+i:v for i,v in enumerate(r)})
        self.player=player_battle.decode_player_battle(self.player_record())['player']
    def call(self,cells=None,*,intent=False,same_frame=False,now=None,state_mutate=None,previous=None):
        if self.started and not same_frame:self.game.frame_count+=40;self.now+=.1
        self.started=True
        if now is not None:self.now=now
        self.sync()
        # These readers are the real existing runtime implementations.
        self.state=dict(frame=self.game.frame_count,location=dict(map_id=166,x=3,y=4),
                        progress=deepcopy(self.p),battle_state=battle.read_battle_state(self.game))
        self.game.show(cells if cells is not None else cmd(self.player,self.enemy))
        text=observation.read_visible_text(self.game,self.game.decoding)
        assert text['read_valid'] and text['alignment_verified']
        if state_mutate is not None:state_mutate(self.state)
        before=deepcopy((self.state,self.plan,text,self.game.memory.values))
        out=self.b.context(self.game,self.state,self.plan,'blaine',text,
                           list(self.prev) if previous is None else previous,
                           intent=self.intent if intent else None)
        assert (self.state,self.plan,text,self.game.memory.values)==before
        if out is not None:self.prev=[out[0]['available_actions'][0]]
        return out[0] if out else None
    def use(self):
        assert self.call(intent=True)['available_actions'][0]=='a'
        assert self.state['battle_state']['opponent_species']=='ARCANINE'
        target=3 if self.item==18 else 4;off=cur=0
        for i in range(target+1):
            r=self.call(bag(self.player,self.enemy,self.p['inventory'],off,cur))
            assert r['available_actions'][0]==('a' if i==target else 'down'),r
            if cur<2:cur+=1
            else:off+=1
        assert self.call(party(self.p['party']))['available_actions'][0]=='a'
        if self.item==18:self.p['party'][2]['hp']=155
        else:self.p['party'][2]['status']=0
        next(i for i in self.p['inventory'] if i['item']==self.item)['quantity']-=1
        self.sync()
        receipt=party(self.p['party'],None,receipt=('heal',90) if self.item==18 else ('cure',0),arrow=False)
        assert self.call(receipt)['available_actions']==['wait']
        assert self.call(receipt)['available_actions']==['wait']  # 40 < native settling54
        assert self.call(receipt)['available_actions'][0]=='a'  # 80 fresh frames, one acknowledgement
    def controller(self):return next(iter(self.b._CONTROLLERS.values()))


@pytest.fixture
def env(monkeypatch):
    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname in ('laya_pokemon.battle_medicine','laya_pokemon.trainer_opponent'):
                filename=fullname.rsplit('.',1)[1]+'.py'
                return importlib.util.spec_from_file_location(fullname,source_for_test(__file__,filename))
            return None
    finder=Finder();sys.meta_path.insert(0,finder)
    try:
        for short in ('battle_medicine','trainer_opponent'):
            name='laya_pokemon.'+short
            spec=importlib.util.spec_from_file_location(name,source_for_test(__file__,short+'.py'))
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            monkeypatch.setitem(sys.modules,name,module)
            monkeypatch.setattr(laya_pokemon,short,module,raising=False)
        name='laya_pokemon._medicine_final_bridge'
        spec=importlib.util.spec_from_file_location(name,source_for_test(__file__))
        b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
        yield SimpleNamespace(b=b,make=lambda item=18:Session(b,monkeypatch,item),reload=lambda:spec.loader.exec_module(b))
    finally:sys.meta_path.remove(finder)


def test_exact_stage_and_formal_resolution(env):
    assert Path(env.b.__file__).resolve()==source_for_test(__file__)
    assert Path(env.b.bm.__file__).resolve()==source_for_test(__file__,'battle_medicine.py')
    assert Path(env.b.trainer_opponent.__file__).resolve()==source_for_test(__file__,'trainer_opponent.py')
    assert Path(env.b.player_battle.__file__).resolve()==ROOT/'src/laya_pokemon/player_battle.py'
    assert source_for_test(ROOT/'tests/test_battle_medicine_bridge.py')==ROOT/'src/laya_pokemon/battle_medicine_bridge.py'
    with pytest.raises(RuntimeError):source_for_test(ROOT/'tests/fallback/test_battle_medicine_bridge.py')


@pytest.mark.parametrize('item',[18,52])
@pytest.mark.parametrize('result',['ember','miss','recoil','take_down_miss'])
def test_real_pure_bridge_and_getters_full_transaction(env,item,result):
    s=env.make(item);s.use();move='TAKE DOWN' if result in ('recoil','take_down_miss') else 'EMBER'
    assert s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used '+move+'!'))['available_actions']==['wait']
    if result in ('miss','take_down_miss'):
        assert s.call(enemy_prompt(s,'attack missed!'))['available_actions'][0]=='a'
    else:
        s.p['party'][2]['hp']-=24;s.sync()
        if result=='recoil':
            s.enemy['hp']-=6
            assert s.call(enemy_prompt(s,'hit with recoil!'))['available_actions'][0]=='a'
    r=s.call();assert not r.get('battle_medicine_complete')
    r=s.call();assert r['battle_medicine_complete'] is True
    assert r['field_move_complete'] is True and r['field_move_kind']=='battle-medicine'
    assert r['survival_approved'] is False and s.controller().calls>5
    assert len(env.b._COMPLETED)==1
    assert next(iter(env.b._BINDINGS.values()))['receipt']['battle_medicine_complete']
    assert s.p['money']==s.before['money']
    assert next(i['quantity'] for i in s.p['inventory'] if i['item']==item)==9
    assert all(s.p['party'][j]==s.before['party'][j] for j in (0,1,3,4,5))
    assert s.call() is None


def test_bridge_does_not_autostart_without_explicit_intent(env):
    s=env.make();assert s.call() is None and not env.b._CONTROLLERS


def test_bridge_same_frame_timeout_real_controller(env):
    s=env.make();s.call(intent=True)
    assert s.call(same_frame=True,now=61)['review_reason']=='battle_medicine_call_or_time_budget_exhausted'
    assert not env.b._COMPLETED


def test_bridge_reload_preserves_started_budget_baseline_and_pending(env):
    s=env.make();s.call(intent=True);c=s.controller()
    before=deepcopy((c.started,c.calls,c.baseline,c.pending,c.owner))
    env.reload();s.clock(s.monkeypatch)
    r=s.call(same_frame=True,now=61)
    assert r['phase']=='strategy_review' and s.controller() is c
    assert (c.started,c.calls-1,c.baseline,c.pending,c.owner)==before


@pytest.mark.parametrize('field,value',[('opponent_species',20),('raw',True),('kind','wild')])
def test_bridge_rejects_wrong_runtime_schema_before_any_offer(env,field,value):
    s=env.make()
    r=s.call(intent=True,state_mutate=lambda state:state['battle_state'].__setitem__(field,value))
    assert r['phase']=='campaign_review' and r['available_actions']==['wait']
    assert not env.b._CONTROLLERS


def test_real_trainer_getter_memory_failure_cannot_offer_or_complete(env):
    s=env.make();s.call(intent=True)
    reads=0
    def bad(address,value):
        nonlocal reads
        if address==0xCFE5:
            reads+=1
            if reads>=2:return False  # real runtime reader sees first valid byte
        return value
    s.game.memory.hook=bad
    assert s.call()['review_reason']=='battle_medicine_bridge_trainer_snapshot_unverified'
    s.game.memory.hook=None
    assert s.call()['review_reason']=='battle_medicine_bridge_trainer_snapshot_unverified'


def test_bound_step_change_is_sticky_review(env):
    s=env.make();s.call(intent=True);s.step['target']=[4,4]
    assert s.call()['phase']=='campaign_review'
    s.step['target']=[3,4]
    assert s.call()['phase']=='campaign_review'


def test_real_player_getter_invalid_byte_is_sticky_review(env):
    s=env.make();s.call(intent=True)
    s.game.memory.hook=lambda address,value:False if address==0xD014 else value
    assert s.call()['review_reason']=='battle_medicine_bridge_player_snapshot_unverified'
    s.game.memory.hook=None
    assert s.call()['review_reason']=='battle_medicine_bridge_player_snapshot_unverified'


def test_bridge_actual_previous_is_bound_to_real_offer(env):
    s=env.make();s.call(intent=True)
    r=s.call(bag(s.player,s.enemy,s.p['inventory']),previous=['b'])
    assert r['review_reason']=='battle_medicine_actual_previous_does_not_match_offer'
    assert not env.b._COMPLETED


def test_completed_bridge_cannot_start_new_transaction_on_completed_frame(env):
    s=env.make();s.use();s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used EMBER!'))
    s.call();assert s.call()['battle_medicine_complete'] is True
    r=s.call(intent=True,same_frame=True)
    assert r['review_reason']=='battle_medicine_bridge_new_owner_requires_fresh_frame'


@pytest.mark.parametrize('bad',['ko','wrong_recoil','unknown_move'])
def test_bridge_unknown_or_recoil_ko_never_claims_completion(env,bad):
    s=env.make();s.use()
    if bad=='unknown_move':r=s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used BITE!'))
    else:
        s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used TAKE DOWN!'))
        s.p['party'][2]['hp']-=24;s.sync();s.enemy['hp']=0 if bad=='ko' else 142
        r=s.call(enemy_prompt(s,'hit with recoil!'))
    assert r['phase'] in ('strategy_review','campaign_review') and r['available_actions']==['wait']
    assert not env.b._COMPLETED and not r.get('field_move_complete')
