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

ROOT=Path(laya_pokemon.__file__).resolve().parents[2]
STAGE=ROOT/'.local/staged-medicine-retaliation-animation-20261025'


def source_for_test(test_path,filename='battle_medicine_bridge.py'):
    p=Path(test_path).resolve()
    if p==STAGE/'test_battle_medicine_retaliation_animation.py':
        if filename=='trainer_opponent.py':return ROOT/'src/laya_pokemon'/filename
        return STAGE/filename
    if p==ROOT/'tests/test_battle_medicine_retaliation_animation.py':return ROOT/'src/laya_pokemon'/filename
    raise RuntimeError('Only exact staged or formal test locations are supported')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


fx=load('retaliation_schema_fixture',ROOT/'tests/test_battle_medicine.py')
bm=load('retaliation_pure_candidate',source_for_test(__file__,'battle_medicine.py'))
fx.bm=bm
progress,record,cmd,bag,party,dialog,blank=(getattr(fx,n) for n in ('progress','record','cmd','bag','party','dialog','blank'))


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
        assert text['read_valid'] or text['read_error']=='visible_tile_alignment_incomplete'
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


def shake_text(cells=None):
    game=Game();game.memory.values[0xFF40]=0xB1
    game.screen.tilemap_position_list=[(2,0,7,0)]*144
    game.show(cells if cells is not None else blank())
    t=observation.read_visible_text(game,game.decoding)
    assert t['read_error']=='visible_tile_alignment_incomplete' and t['cells']==blank()
    return t


def fired():
    s=fx.Session();s.p['party'][2].update(hp=77,max_hp=156)
    s.player=s.player_now();s.before=deepcopy(s.p);s.select();s.effect()
    s.p['party'][2]['hp']=156;s.player=s.player_now()
    receipt=fx.party(s.p['party'],None,receipt=('heal',79),arrow=False)
    assert s.call(receipt)['available_actions']==['wait']
    assert s.call(receipt,advance=54)['available_actions'][0]=='a'
    assert s.call(fx.dialog(s.player,s.enemy,'Enemy ARCANINE','used FIRE BLAST!'))['available_actions']==['wait']
    return s


def repair_args(s):
    return {k:deepcopy(s.kw[k]) for k in ('text','progress','player_snapshot','enemy_proof','frame','owner')}


def test_real_decoder_two_pixel_shake_only_waits_after_observed_fire_blast():
    s=fired();r=s.call(text=shake_text())
    assert r['battle_medicine_tactic']=='known_fire_blast_alignment_animation'
    assert r['available_actions']==['wait'] and not r.get('battle_medicine_complete')
    cells=blank();fx.at(cells,1,0,'ARCANINE')
    t=fx.text(cells);t.update(read_valid=False,alignment_verified=False,window_visible=True,
                            read_error='visible_tile_alignment_incomplete')
    assert s.call(text=t)['battle_medicine_tactic']=='known_fire_blast_alignment_animation'


def test_damage_bar_lags_real_battle_hp_and_party_then_critical_retains_true_prompt():
    s=fired();s.player['hp']=35
    inventory=deepcopy(s.p['inventory'])
    for hp in (143,117,94,69,43):
        rendered={**s.player,'hp':hp}
        r=s.call(fx.dialog(rendered,s.enemy,'Enemy ARCANINE','used FIRE BLAST!'))
        assert r['battle_medicine_tactic']=='known_fire_blast_damage_hp_bar' and r['available_actions']==['wait']
        assert s.kw['player_snapshot']['player']['hp']==35 and s.kw['progress']['party'][2]['hp']==156
        assert s.p['inventory']==inventory and not r.get('battle_medicine_complete')
    assert s.call(fx.dialog(s.player,s.enemy,'Critical hit!','',True))['available_actions'][0]=='a'
    s.p['party'][2]['hp']=35
    assert not s.call().get('battle_medicine_complete')
    assert s.call().get('battle_medicine_complete')


@pytest.mark.parametrize('bad',['unobserved','other_move','read_error','owner','inventory','other_party','player_frame'])
def test_alignment_wait_does_not_swallow_unknown_or_unbound_state(bad):
    s=fired();t=shake_text();override={}
    if bad=='unobserved':s.c.enemy_action=None
    elif bad=='other_move':s.c.enemy_action='EMBER'
    elif bad=='read_error':t['read_error']='visible_tile_getter_failed'
    elif bad=='owner':override['owner']='foreign'
    elif bad=='inventory':s.p['inventory'][3]['quantity']-=1
    elif bad=='other_party':s.p['party'][0]['hp']-=1
    else:
        override['player_snapshot']=deepcopy(s.kw['player_snapshot'])
        override['player_snapshot']['observation_frame']=False
    r=s.call(text=t,**override)
    assert r['phase']=='strategy_review' and r['available_actions']==['wait']
    assert not r.get('battle_medicine_complete')


def test_explicit_pure_repair_only_clears_named_alignment_error():
    s=fired();s.call(text=shake_text());s.c.error='native_decoder_not_verified'
    kw=repair_args(s);before=deepcopy(s.c.__dict__)
    assert s.c.context(**s.kw)['phase']=='strategy_review' and s.c.__dict__==before
    assert s.c.reviewed_retaliation_animation_repair(**kw)
    after=deepcopy(s.c.__dict__);after['error']=before['error'];assert after==before
    s.c.error='call_or_time_budget_exhausted';before=deepcopy(s.c.__dict__)
    assert not s.c.reviewed_retaliation_animation_repair(**kw) and s.c.__dict__==before


def test_hp_bar_range_max_cursor_and_party_lag_are_not_generalized():
    for bad in ('below','above','max','arrow','party_intermediate'):
        s=fired();s.player['hp']=35
        rendered={**s.player,'hp':34 if bad=='below' else 157 if bad=='above' else 143}
        cells=fx.dialog(rendered,s.enemy,'Enemy ARCANINE','used FIRE BLAST!')
        if bad=='max':fx.at(cells,15,10,'155')
        elif bad=='arrow':cells[16][18]='▼'
        elif bad=='party_intermediate':s.p['party'][2]['hp']=100
        r=s.call(cells)
        assert r['available_actions']==['wait'] and not r.get('battle_medicine_complete')
        assert r['battle_medicine_tactic']!='known_fire_blast_damage_hp_bar'


@pytest.mark.parametrize('budget',['wait','time'])
def test_known_shake_still_consumes_existing_budgets(budget):
    s=fired()
    if budget=='wait':s.c.max_waits=s.c.waits
    started=s.c.started
    r=s.call(text=shake_text(),now=started+61 if budget=='time' else s.now+.1)
    assert r['phase']=='strategy_review' and s.c.started==started


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
            monkeypatch.setitem(sys.modules,name,module);monkeypatch.setattr(laya_pokemon,short,module,raising=False)
        spec=importlib.util.spec_from_file_location('laya_pokemon._retaliation_bridge',source_for_test(__file__))
        b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
        yield SimpleNamespace(b=b,make=lambda:Session(b,monkeypatch),reload=lambda:spec.loader.exec_module(b),monkeypatch=monkeypatch)
    finally:sys.meta_path.remove(finder)


def bridge_paused(env):
    s=env.make();s.game.frame_count=14353;s.p['party'][2].update(hp=77,max_hp=156)
    s.before=deepcopy(s.p);s.sync();s.prepare_effect()
    cells=party(s.p['party'],2,marker='▷');cells[5][13:16]=list('101')
    assert s.call(cells)['available_actions']==['wait']
    c=s.controller();c.error='medicine_receipt_unknown';owner=next(iter(s.b._CONTROLLERS))
    s.step['reviewed_medicine_repair']=dict(kind='native_hp_bar_animation_v1',owner=owner,
        frame=s.game.frame_count,error='medicine_receipt_unknown')
    assert s.call(cells,same_frame=True,now=9999)['available_actions']==['wait']
    assert s.call(s.receipt())['available_actions']==['wait']
    assert s.call(s.receipt(),advance=54)['available_actions'][0]=='a'
    assert s.call(dialog(s.player,s.enemy,'Enemy ARCANINE','used FIRE BLAST!'))['available_actions']==['wait']
    s.game.memory.values[0xFF40]=0xB1;s.game.screen.tilemap_position_list=[(2,0,7,0)]*144
    assert s.call()['battle_medicine_tactic']=='known_fire_blast_alignment_animation'
    c.error='native_decoder_not_verified'
    s.step['reviewed_retaliation_animation']=dict(kind='native_fire_blast_alignment_v1',owner=owner,
        frame=s.game.frame_count,error='native_decoder_not_verified')
    return s,owner,c


def test_bridge_second_review_preserves_first_receipt_anchor_and_entire_controller(env):
    s,owner,c=bridge_paused(env);before=deepcopy(c.__dict__);record=s.b._BINDINGS[owner]
    anchor=deepcopy(record['reviewed_frame_clock']);first=deepcopy(record['reviewed_hp_animation_repair'])
    r=s.call(same_frame=True,now=999999)
    assert r['battle_medicine_tactic']=='reviewed_retaliation_animation_repair_recorded'
    after=deepcopy(c.__dict__);after['error']=before['error'];assert after==before
    assert record['reviewed_frame_clock']==anchor and record['reviewed_hp_animation_repair']==first
    assert record['reviewed_retaliation_animation_repair']['marker']==s.step['reviewed_retaliation_animation']
    env.reload();s.clock(env.monkeypatch)
    assert s.call(same_frame=True)['available_actions']==['wait']
    assert s.controller() is c and record['reviewed_frame_clock']==anchor


@pytest.mark.parametrize('bad',['owner','frame','error','clock','getter'])
def test_bridge_repair_marker_cannot_replace_other_errors_clock_or_getter_guard(env,bad):
    s,owner,c=bridge_paused(env);marker=s.step['reviewed_retaliation_animation']
    if bad=='owner':marker['owner']='foreign'
    elif bad=='frame':marker['frame']+=1
    elif bad=='error':c.error='wait_budget_exhausted'
    elif bad=='clock':s.b._BINDINGS[owner]['reviewed_frame_clock']['now']+=1
    else:s.game.memory.hook=lambda address,value:False if address==0xD014 else value
    before=deepcopy(c.__dict__);r=s.call(same_frame=True)
    assert r['phase']=='campaign_review' and c.__dict__==before
    assert s.b._BINDINGS[owner].get('reviewed_retaliation_animation_repair') is None


def test_exact_stage_and_formal_paths(env):
    assert Path(env.b.bm.__file__).resolve()==source_for_test(__file__,'battle_medicine.py')
    assert source_for_test(ROOT/'tests/test_battle_medicine_retaliation_animation.py')==ROOT/'src/laya_pokemon/battle_medicine_bridge.py'
    with pytest.raises(RuntimeError):source_for_test(ROOT/'tests/copy/test_battle_medicine_retaliation_animation.py')


