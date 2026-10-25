"""Real UI pure, real RAM getters, real decoder and installed PyBoy SDK constants.

Only RAM/frame/tile backing values, progress and wall clock are synthetic.
No PyBoy instance, ROM, model, game input, fake successful getter or controller.
"""
from copy import deepcopy
import importlib
import importlib.abc
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import laya_pokemon
from laya_pokemon import battle,observation
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as installed_sdk
import pytest

ROOT=Path(laya_pokemon.__file__).resolve().parents[2]
STAGE=ROOT/'.local/staged-trainer-medicine-ui-bridge-20261025'
PURE_STAGE=ROOT/'.local/staged-trainer-medicine-ui-20261025'


def source_for_test(path,filename='trainer_medicine_ui_bridge.py'):
    p=Path(path).resolve()
    if p==STAGE/'test_trainer_medicine_ui_bridge.py':
        return (PURE_STAGE if filename=='trainer_medicine_ui.py' else STAGE)/filename
    if p==ROOT/'tests/test_trainer_medicine_ui_bridge.py':return ROOT/'src/laya_pokemon'/filename
    raise RuntimeError('Only exact staged/formal test paths are supported')


def fixture_for_test(path):
    p=Path(path).resolve()
    if p==STAGE/'test_trainer_medicine_ui_bridge.py':return PURE_STAGE/'test_trainer_medicine_ui.py'
    if p==ROOT/'tests/test_trainer_medicine_ui_bridge.py':return ROOT/'tests/test_trainer_medicine_ui.py'
    raise RuntimeError('Only exact staged/formal fixture paths are supported')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


fx=load('trainer_ui_schema_fixture',fixture_for_test(__file__))


def native_text(cells):
    # The fixture contains real SDK glyph IDs, not a substitute decoding map.
    reverse={}
    for code,char in installed_sdk.POKEMON_TEXT_DECODING.items():
        if type(code) is int and 0<=code<=255:reverse.setdefault(char,code)
    class Tiles:
        def __getitem__(self,xy):x,y=xy;return reverse[cells[y][x]]
    game=SimpleNamespace(memory={0xFF40:0xB1},screen=SimpleNamespace(tilemap_position_list=[(0,0,0,0)]*144),
                         tilemap_background=Tiles(),tilemap_window=Tiles())
    result=observation.read_visible_text(game)
    assert result['read_valid'] and result['alignment_verified']
    return result


class Memory:
    def __init__(self):self.values={};self.reads=[];self.hook=None
    def __getitem__(self,address):
        self.reads.append(address);value=self.values[address]
        return self.hook(address,value) if self.hook else value
    def __setitem__(self,*args):raise AssertionError('RAM writes forbidden')


class Game:
    def __init__(self):self.frame_count=100000;self.memory=Memory()
    def tick(self,*args,**kwargs):raise AssertionError('tick forbidden')
    def button(self,*args,**kwargs):raise AssertionError('button forbidden')
    def button_press(self,*args,**kwargs):raise AssertionError('button forbidden')


def raw(mon):
    r=[mon['species'],*divmod(mon['hp'],256),0,mon['status'],*mon['types'],mon.get('catch_rate',75),
       *mon['moves'],*mon['dvs'],mon['level'],*divmod(mon['max_hp'],256)]
    for k in ('attack','defense','speed','special'):r.extend(divmod(mon[k],256))
    return r+mon['pp']


class Session(fx.Session):
    def __init__(self,b,active=0,item=18,map_id=45):
        super().__init__(active,item,map_id=map_id)
        self.b=b;self.c=None;self.game=Game();self.last_state=self.last_text=None
        self.current_opponent={45:201,245:244,246:245,247:246,113:247,120:243}[map_id]
        target,face,event=b.TRAINERS[map_id];self.loc=dict(map_id=map_id,x=target[0],y=target[1])
        self.step=dict(id='trainer-'+str(map_id),kind='interact',map_id=map_id,target=list(target),
                       face=face,event=event,battle_supply=b.SUPPLY)
        self.plan=dict(steps=[self.step,dict(id='after',kind='move')]);self.last_reads_before_bridge=0
    def sync(self):
        values=self.game.memory.values
        values.update({0xD35E:self.loc['map_id'],0xD362:self.loc['x'],0xD361:self.loc['y'],0xD057:2,
            0xD05A:0,0xD059:self.current_opponent,0xD127:self.enemy['level'],0xCC2F:self.active,
            0xD163:6,0xD06D:0})
        values.update({0xD014+i:v for i,v in enumerate(raw(self.player))})
        values.update({0xCFE5+i:v for i,v in enumerate(raw(self.enemy))})
    def call(self,cells=None,advance=40,*,start=None,same_frame=False,now=None,state_mutate=None,previous=None,step_id=None,intent=None):
        first=self.kw is None
        if not first and not same_frame:self.game.frame_count+=advance;self.now+=.1
        self.frame=self.game.frame_count
        if now is not None:self.now=now
        self.sync()
        state=dict(frame=self.frame,location=deepcopy(self.loc),progress=deepcopy(self.p),
                   battle_state=battle.read_battle_state(self.game))
        t=native_text(cells if cells is not None else fx.command(self.player,self.enemy))
        if state_mutate is not None:state_mutate(state)
        prev=list(self.prev) if previous is None else previous
        requested=intent if intent is not None else self.intent if (first and start is not False or start is True) else None
        self.last_state,self.last_text=state,t;self.kw=dict(frame=self.frame)
        before=deepcopy((state,self.plan,t,prev,self.game.memory.values));self.last_reads_before_bridge=len(self.game.memory.reads)
        out=self.b.context(self.game,state,self.plan,self.step['id'] if step_id is None else step_id,t,prev,intent=requested)
        assert (state,self.plan,t,prev,self.game.memory.values)==before
        if out is None:return None
        hint,nxt=out;assert nxt==(self.step['id'] if step_id is None else step_id)
        if 'medicine_ui_owner' in hint:self.c=self.b._CONTROLLERS[hint['medicine_ui_owner']]
        self.prev=[hint['available_actions'][0]]
        return hint


@pytest.fixture
def env(monkeypatch):
    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname=='laya_pokemon.trainer_medicine_ui':
                return importlib.util.spec_from_file_location(fullname,source_for_test(__file__,'trainer_medicine_ui.py'))
            return None
    finder=Finder();sys.meta_path.insert(0,finder)
    try:
        name='laya_pokemon.trainer_medicine_ui'
        spec=importlib.util.spec_from_file_location(name,source_for_test(__file__,'trainer_medicine_ui.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        monkeypatch.setitem(sys.modules,name,module);monkeypatch.setattr(laya_pokemon,'trainer_medicine_ui',module,raising=False)
        spec=importlib.util.spec_from_file_location('laya_pokemon._trainer_ui_bridge_test',source_for_test(__file__))
        b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
        class Env:
            current=None
            def make(self,**kwargs):self.current=Session(b,**kwargs);return self.current
            def reload(self):spec.loader.exec_module(b)
        e=Env();e.b=b;monkeypatch.setattr(b.time,'monotonic',lambda:e.current.now)
        yield e
    finally:sys.meta_path.remove(finder)


@pytest.mark.parametrize('active',range(6))
@pytest.mark.parametrize('item',[18,52])
def test_two_medicines_six_active_members_use_true_pure_getters_and_sdk(env,active,item):
    s=env.make(active=active,item=item);s.ack_offer();r=s.call(fx.hud(s.player,s.enemy))
    assert r['medicine_ui_complete'] and r['medicine_handoff']=='existing_battle'
    assert r['enemy_turn_resolved'] is False and r['survival_approved'] is False
    assert 'field_move_complete' not in r and 'battle_medicine_complete' not in r
    owner=r['medicine_ui_owner'];assert owner in s.b._COMPLETED and not s.b._active()
    receipt=s.b._BINDINGS[owner]['receipt'];assert receipt['medicine_ui_complete'] and receipt['enemy_turn_resolved'] is False
    assert s.game.memory.reads.count(0xD014)>=2 and s.game.memory.reads.count(0xCFE5)>=3
    assert s.b._sdk_constants() is installed_sdk and s.current_opponent!=247
    assert all(s.p['party'][i]==s.before['party'][i] for i in range(6) if i!=active)
    assert s.call(start=False) is None


@pytest.mark.parametrize('map_id',[45,245,246,247,113,120])
def test_source_target_event_whitelist_with_real_nonfixed_current_opponent(env,map_id):
    s=env.make(map_id=map_id)
    assert s.call()['available_actions'][0]=='a'
    packet=s.c.last_packet[5]
    assert packet['current_opponent']==s.current_opponent and packet['raw']==2
    assert s.c.last_packet[3]['opponent_species']=='RHYDON'


def test_no_active_owner_and_no_explicit_intent_is_noop(env):
    s=env.make();assert s.call(start=False) is None and not s.b._CONTROLLERS
    assert len(s.game.memory.reads)==s.last_reads_before_bridge


def test_reload_preserves_same_controller_pending_baseline_budget_and_clock(env):
    s=env.make();s.call();c=s.c;before=deepcopy(c.__dict__);env.reload()
    assert s.call(same_frame=True)['available_actions']==['wait']
    assert s.c is c and type(c) is s.b.medicine.TrainerMedicineUIController
    for k in ('pending','baseline','started','last_now','error','max_calls','max_seconds','max_waits'):
        assert c.__dict__[k]==before[k]
    assert c.calls==before['calls']+1 and c.waits==before['waits']+1


def test_reload_does_not_clear_existing_controller_error(env):
    s=env.make();s.call();view=fx.bag(s.player,s.enemy,s.p['inventory'],0,0)
    assert s.call(view,previous=['b'])['phase']=='strategy_review'
    c=s.c;before=deepcopy(c.__dict__);env.reload()
    assert s.call(view,same_frame=True)['phase']=='strategy_review' and s.c is c
    assert c.__dict__==before and not s.b._COMPLETED


@pytest.mark.parametrize('bad',['item','badge','terminal','next_map','nextmap','mechanic','event','target','target_bool'])
def test_generic_or_foreign_trainer_step_cannot_start_or_read_getters(env,bad):
    s=env.make()
    if bad=='event':s.step['event']='beat_blaine'
    elif bad=='target':s.step['target'][0]+=1
    elif bad=='target_bool':s.step['target'][0]=True
    else:s.step[bad]=None
    assert s.call()['phase']=='campaign_review' and not s.b._CONTROLLERS
    assert len(s.game.memory.reads)==s.last_reads_before_bridge


def test_active_owner_foreign_step_is_sticky_and_cannot_fall_through(env):
    s=env.make();s.call();c=s.c;before=deepcopy(c.__dict__)
    assert s.call(step_id='foreign')['review_reason']=='trainer_medicine_ui_bridge_owner_step_changed'
    assert c.__dict__==before and s.b.applies('foreign',None)
    assert s.call()['phase']=='campaign_review' and not s.b._COMPLETED


def test_active_intent_cannot_be_changed_to_other_medicine(env):
    s=env.make();s.call();before=deepcopy(s.c.__dict__)
    assert s.call(intent=env.b.medicine.FULL_HEAL_INTENT)['phase']=='campaign_review'
    assert s.c.__dict__==before


@pytest.mark.parametrize('bad',['player_byte','enemy_zero_hp','runtime_species_int','foreign_frame','frame_during_getter'])
def test_unknown_real_readers_and_runtime_schema_never_claim_success(env,bad):
    s=env.make();mutate=None
    if bad=='player_byte':s.game.memory.hook=lambda address,value:False if address==0xD014 else value
    elif bad=='enemy_zero_hp':s.enemy['hp']=0
    elif bad=='runtime_species_int':mutate=lambda state:state['battle_state'].__setitem__('opponent_species',1)
    elif bad=='foreign_frame':mutate=lambda state:state['battle_state'].__setitem__('observation_frame',False)
    else:
        def change(address,value):
            if address==0xD014:s.game.frame_count+=1
            return value
        s.game.memory.hook=change
    r=s.call(state_mutate=mutate)
    assert r['phase']=='campaign_review' and not r.get('medicine_ui_complete') and not s.b._COMPLETED


def test_completed_history_retained_and_next_owner_requires_fresh_frame(env):
    s=env.make();s.ack_offer();first=s.call(fx.hud(s.player,s.enemy));old=first['medicine_ui_owner']
    journal=deepcopy(s.b._BINDINGS[old]);old_controller=s.c
    r=s.call(start=True,same_frame=True)
    assert r['review_reason']=='trainer_medicine_ui_bridge_new_owner_requires_fresh_frame'
    s.p['party'][s.active]['hp']=100;s.player=s.player_now()
    assert s.call(start=True)['available_actions'][0]=='a'
    assert s.c is not old_controller and len(s.b._CONTROLLERS)==2
    assert s.b._BINDINGS[old]==journal and old in s.b._COMPLETED
    assert s.c.started==s.now and s.c.error is None


def test_duplicate_frame_timeout_is_persistent_and_never_retires_owner(env):
    s=env.make();s.call();c=s.c;started=c.started
    r=s.call(same_frame=True,now=61)
    assert r['review_reason']=='trainer_medicine_ui_call_or_time_budget_exhausted'
    assert c.started==started and c.calls==2 and not s.b._COMPLETED


def test_exact_formal_and_stage_paths_use_real_dependency_modules(env):
    assert Path(env.b.__file__).resolve()==source_for_test(__file__)
    assert Path(env.b.medicine.__file__).resolve()==source_for_test(__file__,'trainer_medicine_ui.py')
    assert Path(env.b.player_battle.__file__).resolve()==ROOT/'src/laya_pokemon/player_battle.py'
    assert Path(env.b.trainer_opponent.__file__).resolve()==ROOT/'src/laya_pokemon/trainer_opponent.py'
    assert fixture_for_test(ROOT/'tests/test_trainer_medicine_ui_bridge.py')==ROOT/'tests/test_trainer_medicine_ui.py'
    with pytest.raises(RuntimeError):source_for_test(ROOT/'tests/copy/test_trainer_medicine_ui_bridge.py')


@pytest.mark.parametrize('annotation',[True,False,1,'beat_champion_rival'])
def test_existing_await_script_annotation_is_true_only_and_never_completion(env,annotation):
    s=env.make(map_id=245);s.step['await_script_event']=annotation;r=s.call()
    if annotation is True:
        assert r['available_actions'][0]=='a' and not r.get('medicine_ui_complete')
        assert not s.b._COMPLETED and s.b._BINDINGS[next(iter(s.b._BINDINGS))]['receipt'] is None
    else:assert r['phase']=='campaign_review' and not s.b._CONTROLLERS
