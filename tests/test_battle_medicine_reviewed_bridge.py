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
STAGE=ROOT/'.local/staged-medicine-reviewed-bridge-20261025'
PURE_STAGE=ROOT/'.local/staged-medicine-hp-animation-20261025'


def source_for_test(test_path,filename='battle_medicine_bridge.py'):
    p=Path(test_path).resolve()
    if p==STAGE/'test_battle_medicine_reviewed_bridge.py':
        if filename=='battle_medicine.py':return PURE_STAGE/filename
        if filename=='trainer_opponent.py':return ROOT/'src/laya_pokemon'/filename
        return STAGE/filename
    if p==ROOT/'tests/test_battle_medicine_reviewed_bridge.py':return ROOT/'src/laya_pokemon'/filename
    raise RuntimeError('Only exact staged or formal test locations are supported')


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
        self.b=b;self.game=Game();self.item=item;self.now=0.;self.prev=[];self.started=False;self.last_text=None
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
    def call(self,cells=None,*,intent=False,same_frame=False,now=None,state_mutate=None,previous=None,advance=40):
        if self.started and not same_frame:self.game.frame_count+=advance;self.now+=.1
        self.started=True
        if now is not None:self.now=now
        self.sync()
        # These readers are the real existing runtime implementations.
        self.state=dict(frame=self.game.frame_count,location=dict(map_id=166,x=3,y=4),
                        progress=deepcopy(self.p),battle_state=battle.read_battle_state(self.game))
        self.game.show(cells if cells is not None else cmd(self.player,self.enemy))
        text=observation.read_visible_text(self.game,self.game.decoding)
        assert text['read_valid'] and text['alignment_verified']
        self.last_text=deepcopy(text)
        if state_mutate is not None:state_mutate(self.state)
        before=deepcopy((self.state,self.plan,text,self.game.memory.values))
        out=self.b.context(self.game,self.state,self.plan,'blaine',text,
                           list(self.prev) if previous is None else previous,
                           intent=self.intent if intent else None)
        assert (self.state,self.plan,text,self.game.memory.values)==before
        if out is not None:self.prev=[out[0]['available_actions'][0]]
        return out[0] if out else None
    def prepare_effect(self):
        assert self.call(intent=True)['available_actions'][0]=='a'
        assert self.state['battle_state']['opponent_species']=='ARCANINE'
        target=3 if self.item==18 else 4;off=cur=0
        for i in range(target+1):
            r=self.call(bag(self.player,self.enemy,self.p['inventory'],off,cur))
            assert r['available_actions'][0]==('a' if i==target else 'down'),r
            if cur<2:cur+=1
            else:off+=1
        assert self.call(party(self.p['party']))['available_actions'][0]=='a'
        if self.item==18:self.p['party'][2]['hp']=self.p['party'][2]['max_hp']
        else:self.p['party'][2]['status']=0
        next(i for i in self.p['inventory'] if i['item']==self.item)['quantity']-=1
        self.sync()
    def receipt(self):
        c=self.controller();delta=c.healed[c.active]['hp']-c.baseline['party'][c.active]['hp']
        return party(self.p['party'],None,receipt=('heal',delta) if self.item==18 else ('cure',0),arrow=False)
    def use(self):
        self.prepare_effect()
        assert self.call(self.receipt())['available_actions']==['wait']
        assert self.call(self.receipt(),advance=54)['available_actions'][0]=='a'
    def controller(self):return next(iter(self.b._CONTROLLERS.values()))


@pytest.fixture
def env(monkeypatch):
    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname in ('laya_pokemon.battle_medicine','laya_pokemon.trainer_opponent'):
                return importlib.util.spec_from_file_location(fullname,
                    source_for_test(__file__,fullname.rsplit('.',1)[1]+'.py'))
            return None
    finder=Finder();sys.meta_path.insert(0,finder)
    try:
        for short in ('battle_medicine','trainer_opponent'):
            name='laya_pokemon.'+short
            spec=importlib.util.spec_from_file_location(name,source_for_test(__file__,short+'.py'))
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            monkeypatch.setitem(sys.modules,name,module)
            monkeypatch.setattr(laya_pokemon,short,module,raising=False)
        spec=importlib.util.spec_from_file_location('laya_pokemon._reviewed_medicine_bridge',source_for_test(__file__))
        b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
        yield SimpleNamespace(b=b,make=lambda item=18:Session(b,monkeypatch,item),
                              reload=lambda:spec.loader.exec_module(b),monkeypatch=monkeypatch)
    finally:sys.meta_path.remove(finder)


def animation(s,hp=101):
    cells=party(s.p['party'],2,marker='▷')
    cells[5][13:16]=list(f'{hp:3}')
    return cells


def paused(env):
    s=env.make();s.game.frame_count=14353
    s.p['party'][2].update(hp=77,max_hp=156);s.before=deepcopy(s.p);s.sync()
    s.prepare_effect()
    assert s.call(animation(s))['available_actions']==['wait']
    assert s.game.frame_count==14593
    c=s.controller();assert c.error is None
    # Seed only the historical false-error journal; actual repair and readers
    # are executed below. CI does not load ignored game outputs.
    c.error='medicine_receipt_unknown'
    # Preserve a real old-instance shape/class: the bridge must rebind this
    # very object before asking it for the newly introduced repair method.
    legacy_spec=importlib.util.spec_from_file_location('legacy_medicine_instance_class',
        ROOT/'src/laya_pokemon/battle_medicine.py')
    legacy=importlib.util.module_from_spec(legacy_spec);legacy_spec.loader.exec_module(legacy)
    del c.receipt_full_frame;del c.receipt_full_rows
    c.__class__=legacy.BattleMedicineController
    owner=next(iter(s.b._CONTROLLERS))
    s.step['reviewed_medicine_repair']=dict(kind='native_hp_bar_animation_v1',owner=owner,
        frame=s.game.frame_count,error='medicine_receipt_unknown')
    return s,owner,c


def repair(s):
    return s.call(animation(s),same_frame=True,now=99999.)


def finish(s):
    assert s.call(s.receipt())['available_actions']==['wait']
    assert s.call(s.receipt(),advance=54)['available_actions'][0]=='a'
    assert s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used EMBER!'))['available_actions']==['wait']
    s.p['party'][2]['hp']-=20;s.sync()
    assert not s.call().get('battle_medicine_complete')
    assert s.call().get('battle_medicine_complete')


def test_real_repair_journals_once_and_preserves_entire_controller_except_error(env):
    s,owner,c=paused(env);before=deepcopy(c.__dict__)
    r=repair(s)
    assert r['available_actions']==['wait'] and r['battle_medicine_tactic']=='reviewed_hp_animation_repair_recorded'
    after=deepcopy(c.__dict__);after['error']=before['error'];assert after==before
    assert c.error is None and s.controller() is c
    assert type(c) is s.b.bm.BattleMedicineController
    record=s.b._BINDINGS[owner]
    assert record['reviewed_hp_animation_repair']['marker']==s.step['reviewed_medicine_repair']
    assert record['reviewed_frame_clock']==dict(owner=owner,frame=14593,now=before['last_now'])
    assert next(i['quantity'] for i in s.p['inventory'] if i['item']==18)==9


def test_active_frame_clock_excludes_engineering_pause_but_keeps_elapsed_budget(env):
    s,owner,c=paused(env);used=c.last_now-c.started;repair(s);anchor=c.last_now
    assert s.call(animation(s,126))['available_actions']==['wait']
    assert c.last_now==pytest.approx(anchor+40/60)
    assert c.last_now-c.started==pytest.approx(used+40/60)
    assert c.started==0. and c.calls>1
    s.step.pop('reviewed_medicine_repair')
    assert s.call(animation(s,149))['available_actions']==['wait']
    assert c.last_now==pytest.approx(anchor+80/60)


def test_same_consumed_marker_reload_does_not_repeat_repair_or_rebuild_controller(env):
    s,owner,c=paused(env);repair(s);receipt=deepcopy(s.b._BINDINGS[owner]['reviewed_hp_animation_repair'])
    count=c.calls;saved_started=c.started;env.reload();s.clock(env.monkeypatch)
    def forbidden(*args,**kwargs):raise AssertionError('consumed marker must not invoke repair again')
    env.monkeypatch.setattr(s.b.bm.BattleMedicineController,'reviewed_hp_animation_repair',forbidden)
    assert s.call(animation(s),same_frame=True)['available_actions']==['wait']
    assert s.controller() is c and c.calls==count+1 and c.started==saved_started
    assert s.b._BINDINGS[owner]['reviewed_hp_animation_repair']==receipt


def test_consumed_history_allows_new_owner_without_inheriting_frame_clock(env):
    s,old,c=paused(env);repair(s);finish(s)
    assert old in s.b._COMPLETED
    old_anchor=deepcopy(s.b._BINDINGS[old]['reviewed_frame_clock'])
    assert s.call(intent=True)['available_actions'][0]=='a'
    active=s.b._active();assert len(active)==1;new=next(iter(active))
    assert new!=old and s.b._CONTROLLERS[new] is not c
    assert s.b._CONTROLLERS[new].started==s.now
    assert s.b._BINDINGS[new].get('reviewed_frame_clock') is None
    assert s.b._BINDINGS[new].get('reviewed_hp_animation_repair') is None
    assert s.b._BINDINGS[old]['reviewed_frame_clock']==old_anchor


@pytest.mark.parametrize('bad',['kind','owner','bool_frame','foreign_frame','error','extra_key'])
def test_wrong_marker_reviews_without_clearing_error_or_touching_controller(env,bad):
    s,owner,c=paused(env);marker=s.step['reviewed_medicine_repair']
    if bad=='kind':marker['kind']='unknown'
    elif bad=='owner':marker['owner']='foreign'
    elif bad=='bool_frame':marker['frame']=True
    elif bad=='foreign_frame':marker['frame']+=1
    elif bad=='error':marker['error']='call_or_time_budget_exhausted'
    else:marker['reset_budget']=True
    before=deepcopy(c.__dict__);r=repair(s)
    assert r['phase']=='campaign_review' and c.__dict__==before
    assert 'reviewed_frame_clock' not in s.b._BINDINGS[owner]


@pytest.mark.parametrize('bad',['error','stage','cursor','getter'])
def test_actual_repair_preconditions_and_real_getters_cannot_be_bypassed(env,bad):
    s,owner,c=paused(env)
    if bad=='error':c.error='wait_budget_exhausted'
    elif bad=='stage':c.stage='retaliation'
    elif bad=='getter':s.game.memory.hook=lambda address,value:False if address==0xD014 else value
    cells=animation(s)
    if bad=='cursor':cells[5][0]='▶'
    before=deepcopy(c.__dict__);r=s.call(cells,same_frame=True,now=99999)
    assert r['phase']=='campaign_review' and c.__dict__==before
    assert s.b._BINDINGS[owner].get('reviewed_hp_animation_repair') is None


def test_after_repair_elapsed_active_frames_still_exhaust_existing_sixty_seconds(env):
    s,owner,c=paused(env);repair(s);started=c.started
    r=s.call(animation(s),advance=3601)
    assert r['review_reason']=='battle_medicine_call_or_time_budget_exhausted'
    assert c.started==started and c.error=='call_or_time_budget_exhausted'


def test_consumed_marker_cannot_clear_a_later_error_or_replace_anchor(env):
    s,owner,c=paused(env);repair(s);anchor=deepcopy(s.b._BINDINGS[owner]['reviewed_frame_clock'])
    c.error='owner_intent_frame_clock_or_previous_invalid'
    r=s.call(animation(s),same_frame=True)
    assert r['review_reason']=='battle_medicine_owner_intent_frame_clock_or_previous_invalid'
    assert c.error=='owner_intent_frame_clock_or_previous_invalid'
    assert s.b._BINDINGS[owner]['reviewed_frame_clock']==anchor


def test_unconsumed_marker_requires_an_existing_active_transaction(env):
    s=env.make();s.step['reviewed_medicine_repair']=dict(kind='native_hp_bar_animation_v1',
        owner='nonexistent',frame=s.game.frame_count,error='medicine_receipt_unknown')
    assert s.call(intent=True)['phase']=='campaign_review'
    assert not s.b._CONTROLLERS


def test_exact_stage_formal_paths_and_real_dependencies(env):
    assert Path(env.b.__file__).resolve()==source_for_test(__file__)
    assert Path(env.b.bm.__file__).resolve()==source_for_test(__file__,'battle_medicine.py')
    assert Path(env.b.trainer_opponent.__file__).resolve()==ROOT/'src/laya_pokemon/trainer_opponent.py'
    assert Path(env.b.player_battle.__file__).resolve()==ROOT/'src/laya_pokemon/player_battle.py'
    assert source_for_test(ROOT/'tests/test_battle_medicine_reviewed_bridge.py')==ROOT/'src/laya_pokemon/battle_medicine_bridge.py'
    with pytest.raises(RuntimeError):source_for_test(ROOT/'tests/copy/test_battle_medicine_reviewed_bridge.py')


