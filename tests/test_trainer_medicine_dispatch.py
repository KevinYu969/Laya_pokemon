"""True frozen policy, bridge, pure, RAM readers, native decoder and PyBoy SDK.

Only RAM/frame/tiles/progress/clock are synthetic; no ROM, game or model runs.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import laya_pokemon
from laya_pokemon import battle
import pytest

ROOT=Path(laya_pokemon.__file__).resolve().parents[2]
STAGE=ROOT/'.local/staged-trainer-medicine-dispatch-20261025'
POLICY_STAGE=ROOT/'.local/staged-trainer-medicine-postreview-20261025'


def source_for_test(path,filename='trainer_medicine_dispatch.py'):
    p=Path(path).resolve()
    if p==STAGE/'test_trainer_medicine_dispatch.py':
        if filename=='trainer_medicine_dispatch.py':return STAGE/filename
        if filename=='trainer_medicine_policy.py':return POLICY_STAGE/filename
        return ROOT/'src/laya_pokemon'/filename
    if p==ROOT/'tests/test_trainer_medicine_dispatch.py':return ROOT/'src/laya_pokemon'/filename
    raise RuntimeError('Only exact staged/formal test source paths are supported')


def fixture_for_test(path):
    p=Path(path).resolve()
    if p==STAGE/'test_trainer_medicine_dispatch.py':return ROOT/'.local/staged-trainer-medicine-ui-bridge-20261025/test_trainer_medicine_ui_bridge.py'
    if p==ROOT/'tests/test_trainer_medicine_dispatch.py':return ROOT/'tests/test_trainer_medicine_ui_bridge.py'
    raise RuntimeError('Only exact staged/formal fixture paths are supported')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


fx=load('trainer_dispatch_fixture',fixture_for_test(__file__))


class Session(fx.Session):
    def player_now(self):
        player=super().player_now();player['speed']=79;return player
    def __init__(self,d,**kw):
        super().__init__(d.bridge,**kw);self.d=d
        self.p['party'][self.active]['moves']=[57,34,58,109]
        self.p['party'][self.active]['pp']=[11,15,10,10]
        if self.item==52:self.p['party'][self.active]['hp']=150
        self.player=self.player_now();self.player['speed']=79
        self.before=deepcopy(self.p)
    def call(self,cells=None,advance=40,*,same_frame=False,state_mutate=None,previous=None,step_id=None,**ignored):
        if self.kw is not None and not same_frame:self.game.frame_count+=advance;self.now+=.1
        self.frame=self.game.frame_count;self.sync()
        state=dict(frame=self.frame,location=deepcopy(self.loc),progress=deepcopy(self.p),
            battle_state=battle.read_battle_state(self.game))
        text=fx.native_text(cells if cells is not None else fx.fx.command(self.player,self.enemy))
        if state_mutate:state_mutate(state)
        prev=self.prev if previous is None else previous
        self.kw=dict(frame=self.frame);self.last_state,self.last_text=state,text
        self.last_reads_before_bridge=len(self.game.memory.reads)
        before=deepcopy((state,self.plan,text,prev,self.game.memory.values))
        result=self.d.context(self.game,state,self.plan,self.step['id'] if step_id is None else step_id,text,prev)
        assert before==(state,self.plan,text,prev,self.game.memory.values)
        if result is None:return None
        hint,nxt=result;assert nxt==(self.step['id'] if step_id is None else step_id)
        if 'medicine_ui_owner' in hint:self.c=self.b._CONTROLLERS[hint['medicine_ui_owner']]
        self.prev=[hint['available_actions'][0]];return hint


@pytest.fixture
def env(monkeypatch):
    # Actual formal bridge and UI, isolated registries per test. Stage policy is
    # explicitly injected until root installs it; no fake policy/controller.
    b=load('laya_pokemon._trainer_dispatch_bridge',source_for_test(__file__,'trainer_medicine_ui_bridge.py'))
    policy=load('laya_pokemon._trainer_dispatch_policy',source_for_test(__file__,'trainer_medicine_policy.py'))
    for name,module in (('trainer_medicine_ui_bridge',b),('trainer_medicine_policy',policy)):
        monkeypatch.setattr(laya_pokemon,name,module,raising=False)
        monkeypatch.setitem(sys.modules,'laya_pokemon.'+name,module)
    d=load('laya_pokemon._trainer_dispatch_test',source_for_test(__file__))
    class Env:
        current=None
        def make(self,**kwargs):self.current=Session(d,**kwargs);return self.current
    e=Env();e.d=d;e.b=b
    for name in d._PEERS:
        monkeypatch.setitem(sys.modules,'laya_pokemon.'+name,SimpleNamespace(_BINDINGS={},_CONTROLLERS={},_COMPLETED=set()))
    monkeypatch.setitem(sys.modules,'laya_pokemon.capture_transaction',SimpleNamespace(_SESSIONS={}))
    monkeypatch.setattr(b.time,'monotonic',lambda:e.current.now)
    return e


def test_source_path_is_exact():
    assert source_for_test(__file__).name=='trainer_medicine_dispatch.py'
    with pytest.raises(RuntimeError):source_for_test(STAGE/'unapproved.py')


@pytest.mark.parametrize('item',[18,52])
def test_both_real_medicine_flows_complete_ui_only_and_return_same_step(env,item):
    s=env.make(item=item);s.ack_offer();r=s.call(fx.fx.hud(s.player,s.enemy))
    assert r['medicine_ui_complete'] and r['medicine_handoff']=='existing_battle'
    assert r['enemy_turn_resolved'] is False and r['survival_approved'] is False
    assert not r.get('field_move_complete') and not r.get('battle_medicine_complete')
    assert s.c.intent['item']==item and not s.b._active()
    assert s.game.memory.reads.count(0xD014)>5 and s.game.memory.reads.count(0xCFE5)>5


@pytest.mark.parametrize('map_id',[45,245,246,247,113,120])
def test_whitelist_and_dynamic_current_opponent_use_true_policy_and_getters(env,map_id):
    s=env.make(map_id=map_id);r=s.call()
    assert r['trainer_medicine_decision']['intent']==s.intent
    assert s.c.last_packet[5]['current_opponent']==s.current_opponent


@pytest.mark.parametrize('page',['partial','dialogue','blank','native_invalid','bad_cursor','half_hud'])
def test_nonfull_command_never_reads_either_getter_or_creates_owner(env,page):
    s=env.make();cells=fx.fx.command(s.player,s.enemy)
    if page=='partial':cells[14][10]=' '
    elif page=='dialogue':cells=fx.fx.hud(s.player,s.enemy);fx.fx.put(cells,1,14,'Enemy RHYDON')
    elif page=='blank':cells=[[' ']*20 for _ in range(18)]
    elif page=='bad_cursor':cells[16][9]=' ';cells[13][9]='▶'
    elif page=='half_hud':cells[7][10]=' '
    if page=='native_invalid':
        s.sync();state=dict(frame=s.game.frame_count,location=s.loc,progress=s.p,battle_state=battle.read_battle_state(s.game))
        text=fx.native_text(cells);text['alignment_verified']=False;before=len(s.game.memory.reads)
        assert s.d.context(s.game,state,s.plan,s.step['id'],text,[]) is None
        assert len(s.game.memory.reads)==before
    else:
        assert s.call(cells) is None
        assert len(s.game.memory.reads)==s.last_reads_before_bridge
    assert not s.b._active()


def test_nonbattle_does_not_read_typed_getters(env):
    s=env.make();assert s.call(state_mutate=lambda state:state.update(battle_state=dict(kind='none',active=False,raw=0))) is None
    assert len(s.game.memory.reads)==s.last_reads_before_bridge


def test_healthy_none_preserves_default_battle_attack(env):
    s=env.make();s.p['party'][s.active]['hp']=150;s.player=s.player_now()
    assert s.call() is None and not s.b._active()


def test_finish_uses_existing_battle_command_hint_and_same_actor(env):
    s=env.make();s.enemy['hp']=4;s.player['speed']=s.enemy['speed']
    r=s.call();rows=s.d._command_rows(s.last_text,s.last_state['battle_state'])
    expected=battle._selection_hint(rows,(10,14),'command')
    assert all(r[k]==v for k,v in expected.items())
    assert r['trainer_medicine_decision']['action']=='finish' and r['trainer_medicine_decision']['move_key']=='SURF'
    assert r['survival_approved'] is False and not s.b._active()


def test_active_owner_continues_real_previous_on_noncommand_page(env):
    s=env.make();s.call();owner=s.c.owner;controller=s.c
    r=s.call(fx.fx.bag(s.player,s.enemy,s.p['inventory'],0,0))
    assert r['available_actions'][0]=='down' and s.c is controller and s.c.owner==owner
    assert 'trainer_medicine_decision' not in r
    r=s.call(step_id='foreign');assert r['available_actions']==['wait'] and 'owner_step_changed' in r['review_reason']


@pytest.mark.parametrize('bad',['foreign_frame','wrong_step','wrong_target','generic_item','missing_item','party_lag','hud_hp'])
def test_invalid_scope_and_typed_facts_review_without_medicine(env,bad):
    s=env.make();cells=None;mutate=None
    if bad=='foreign_frame':mutate=lambda state:state['battle_state'].update(observation_frame=state['frame']-1)
    elif bad=='wrong_step':s.step['event']='beat_blaine'
    elif bad=='wrong_target':s.step['target']=[3,2]
    elif bad=='generic_item':s.step['item']=18
    elif bad=='missing_item':s.p['inventory']=[i for i in s.p['inventory'] if i['item']!=18]
    elif bad=='party_lag':s.p['party'][s.active]['hp']-=1
    else:
        p=deepcopy(s.player);p['hp']+=1;cells=fx.fx.command(p,s.enemy)
    r=s.call(cells,state_mutate=mutate)
    assert r['phase']=='campaign_review' and r['available_actions']==['wait'] and not s.b._active()


@pytest.mark.parametrize('peer',['medicine','capture','safari','lost_controller'])
def test_peer_transaction_is_rejected_before_getters(env,peer):
    s=env.make()
    if peer=='medicine':sys.modules['laya_pokemon.battle_medicine_bridge']._BINDINGS['peer']={}
    elif peer=='capture':sys.modules['laya_pokemon.capture_transaction']._SESSIONS['peer']={'done':False}
    elif peer=='safari':sys.modules['laya_pokemon.safari_entry']._RUN_CONTROLLER=object()
    else:sys.modules['laya_pokemon.player_pc_bridge']._CONTROLLERS['peer']=object()
    r=s.call();assert r['review_reason'].endswith('other_transaction_active')
    assert len(s.game.memory.reads)==s.last_reads_before_bridge and not s.b._active()


def test_completed_same_frame_requires_wait_before_new_owner(env):
    s=env.make();s.ack_offer();r=s.call(fx.fx.hud(s.player,s.enemy));owner=r['medicine_ui_owner']
    s.p['party'][s.active]['hp']=65;s.player=s.player_now();s.player['speed']=79
    r=s.call(same_frame=True);assert r['available_actions']==['wait'] and r['battle_tactic']=='fresh_command_before_next_medicine'
    assert owner in s.b._COMPLETED and not s.b._active()
    r=s.call();assert r['medicine_ui_owner']!=owner and s.b._BINDINGS[owner]['receipt']['medicine_ui_complete']
