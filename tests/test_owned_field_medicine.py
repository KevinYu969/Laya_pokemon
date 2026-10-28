"""Actual SDK + actual getters/controllers; synthetic memory/UI only."""
from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk

medicine=importlib.import_module('laya_pokemon.overworld_hyper')
coordinator=importlib.import_module('laya_pokemon.owned_field_medicine')
SOURCE=Path(medicine.__file__).resolve().parent
assert SOURCE.name=='laya_pokemon' and SOURCE.parent.name=='src'
ROOT=SOURCE.parent.parent
for module,filename in ((medicine,'overworld_hyper.py'),(coordinator,'owned_field_medicine.py')):
    assert Path(module.__file__).resolve()==(SOURCE/filename).resolve()

def load_bridge(name,path):
    assert path.resolve() in {(SOURCE/'victory_later_boulders_bridge.py').resolve(),
        (SOURCE/'overworld_hyper_bridge.py').resolve()}
    spec=importlib.util.spec_from_file_location('laya_pokemon._owned_medicine_'+name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

later=load_bridge('later_formal_test',SOURCE/'victory_later_boulders_bridge.py')
hyper=load_bridge('hyper_bridge_formal_test',SOURCE/'overworld_hyper_bridge.py')
assert hyper.medicine is medicine
bh=importlib.import_module('test_victory_later_boulders')
hh=importlib.import_module('test_overworld_hyper')
for helper,filename in ((bh,'test_victory_later_boulders.py'),(hh,'test_overworld_hyper.py')):
    assert Path(helper.__file__).resolve()==(ROOT/'tests'/filename).resolve()

@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for obj in (later,hyper):
        monkeypatch.setattr(obj,'_CONTROLLERS',{})
        monkeypatch.setattr(obj,'_BINDINGS',{})
        monkeypatch.setattr(obj,'_COMPLETED',set())
    monkeypatch.setattr(hyper,'_OWNERS',{})
    monkeypatch.setattr(hyper,'_REGISTRY_ERROR',None)
    monkeypatch.setattr(coordinator,'_SESSIONS',{})
    monkeypatch.setattr(coordinator,'_ERRORS',{})
    monkeypatch.setattr(coordinator,'_REGISTRY_ERROR',None)

class Session:
    def __init__(self,key='3f_switch1',species=7):
        self.key=key;self.case=later.boulder.CASES[key];self.game=hh.Game()
        self.game.memory.update(bh.Memory(key).values)
        p=bh.progress();p['inventory']=[i for i in p['inventory'] if i['item']!=7]
        self.game.game_wrapper=SimpleNamespace(party=p['party'],inventory=p['inventory'],money=p['money'])
        self.game.memory.update({sdk.PARTY_COUNT_ADDRESS:6,0xD356:255,
            sdk.PLAYER_MONEY_ADDRESS:0x05,sdk.PLAYER_MONEY_ADDRESS+1:0x43,sdk.PLAYER_MONEY_ADDRESS+2:0x21})
        enc={v:k for k,v in sdk.POKEMON_TEXT_DECODING.items() if type(k) is int and 0<=k<=255}
        for i,ch in enumerate('KEVIN'):self.game.memory[sdk.PLAYER_NAME_ADDRESS+i]=enc[ch]
        self.game.memory[sdk.PLAYER_NAME_ADDRESS+5]=0x50
        self.species=species;self.step_id='original-'+key;self.child_id='child-'+key
        self.step=dict(id=self.step_id,kind='interact',mechanic=later.MECHANIC,
            map_id=self.case['map_id'],target=deepcopy(self.case['start_player']),boulder_case=key)
        self.plan=dict(mode='league_campaign',training_job={'id':'synthetic-owned-medicine','deep':{'x':1}},steps=[self.step])
        self.previous=[];self.now=0.;self.prepare(world=True)
        out,_=later.context(self.game,self.state,self.plan,self.step_id,self.text,self.grid,[],now=0.)
        assert out['phase']!='campaign_review',out
        self.c=later._CONTROLLERS[self.step_id]
        pending=self.c.pending;assert pending
        if pending['kind']=='walk':self.game.memory[0xD362],self.game.memory[0xD361]=pending['expected_player']
        self.prepare(world=True,raw=1)
        out,_=later.context(self.game,self.state,self.plan,self.step_id,self.text,self.grid,[pending['action']],now=1/60)
        assert self.c.suspended and self.c.pending['executed']
        target=next(m for m in self.mons if m['species']==species)
        target['hp']-=30;target['exp']+=100;target['pp'][0]-=1
        self.prepare(world=True)
        self.capsule=dict(kind=coordinator.KIND,original_game='synthetic-game',original_step_id=self.step_id,
            original_step_sha256=coordinator.canonical_sha256(self.step),
            training_job_sha256=coordinator.canonical_sha256(self.plan['training_job']),
            original_frame=self.game.frame_count,original_location=deepcopy(self.state['location']),
            target_species=species,item=18,quantity=1,child_step_id=self.child_id,
            evidence={'review_sha256':'a'*64,'state_sha256':'b'*64})
        self.plan['field_medicine_interrupt']=self.capsule
        self.attrition={'review_reason':'party_attrition_requires_center','party_attrition':{'fainted_party_indices':[]}}
        self.before_parent=deepcopy(self.c.__dict__)
        self.parent_identity=self.c;self.binding_identity=later._BINDINGS[self.step_id]

    @property
    def mons(self):return self.game.game_wrapper.party
    @property
    def items(self):return self.game.game_wrapper.inventory
    def peers(self):
        p={k:set() for k in coordinator.PEER_NAMES}
        p['victory_later_boulder']=later._active();p['overworld_hyper']=hyper._active()
        return p
    def prepare(self,cells=None,*,world=False,frames=40,raw=0,same=False):
        if hasattr(self,'state') and not same:self.game.frame_count+=frames
        self.game.memory[0xD057]=raw
        self.game.cells=hh.blank() if cells is None else deepcopy(cells)
        self.game.memory[0xFF40]=0x91 if world else 0xB1
        self.text=hh.read_visible_text(self.game);assert self.text['read_valid']
        sig=medicine.read_observation(self.game,self.game.frame_count,sdk,map_id=self.case['map_id']);assert sig['read_valid']
        self.state=dict(frame=self.game.frame_count,phase='unclassified',
            location={k:self.game.memory[a] for k,a in [('map_id',0xD35E),('x',0xD362),('y',0xD361)]},
            progress=deepcopy(sig['progress']),battle_state=dict(raw=raw,kind='wild' if raw else 'none',active=bool(raw),observation_frame=self.game.frame_count))
        loc=self.state['location'];xy=(loc['x'],loc['y'])
        self.grid=bh.grid(self.key,self.game.frame_count,xy,self.game.memory)
        self.grid['source']='wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM'
        if [*xy] not in self.grid['visible_verified_cells']:self.grid['visible_verified_cells'].append([*xy])
        self.grid['screen_cells_verified']=len(self.grid['visible_verified_cells'])
        if not world:self.grid=None
        return self
    def call(self,**kwargs):
        params=dict(game_id='synthetic-game',native_owner=self.game,later_bridge=later,hyper_bridge=hyper,
            peer_owners=self.peers(),attrition=self.attrition)
        params.update(kwargs)
        before=deepcopy((dict(self.game.memory),self.state,self.plan,self.text,self.grid))
        result=coordinator.context(self.game,self.state,self.plan,self.step_id,self.text,self.grid,self.previous,**params)
        assert before==(dict(self.game.memory),self.state,self.plan,self.text,self.grid)
        if result:self.previous=[result[0]['available_actions'][0]]
        return result
    def expect(self,cells,action,**kwargs):
        self.prepare(cells,**kwargs);out,nxt=self.call();assert nxt==self.step_id
        assert out['available_actions']==[action,'wait'],out
        return out
    def start(self):
        out,nxt=self.call();assert out['available_actions']==['wait'] and nxt==self.step_id,out
        assert self.c is self.parent_identity and later._BINDINGS[self.step_id] is self.binding_identity
        assert not self.c.suspended and self.c.battle_returns==1
        self.parent_frozen=deepcopy(self.c.__dict__);self.pending=self.c.pending
        assert self.pending['executed'] is False
        self.expect(hh.blank(),'start',world=True)
        return self
    def select(self):
        self.start();self.expect(hh.start(6),'a')
        wanted=next(i for i,item in enumerate(self.items) if item['item']==18)
        for i in range(wanted+1):
            self.expect(hh.bag(medicine,self.items,max(0,i-2),min(2,i)),'a' if i==wanted else 'down')
        self.off,self.cur=max(0,wanted-2),min(2,wanted)
        self.expect(hh.use(medicine,self.items,self.off,self.cur),'a')
        self.target=next(i for i,m in enumerate(self.mons) if m['species']==self.species)
        for i in range(self.target+1):self.expect(hh.party(self.mons,i),'a' if i==self.target else 'down')
        return self
    def effect(self):
        m=self.mons[self.target];self.old_hp=m['hp'];m['hp']=min(m['hp']+200,m['max_hp'])
        item=next(i for i in self.items if i['item']==18);item['quantity']-=1
        if item['quantity']==0:self.items.remove(item)
    def receipt(self):
        return hh.party(self.mons,receipt=(sdk.POKEMON_SPECIES_NAMES[self.species],self.mons[self.target]['hp']-self.old_hp))
    def finish(self):
        self.effect();out,_=self.prepare(self.receipt()).call();assert out['available_actions']==['wait'],out
        self.expect(self.receipt(),'a',frames=54)
        self.expect(hh.bag(medicine,self.items,self.off,self.cur),'b')
        self.expect(hh.start(),'b')
        out,_=self.prepare(world=True).call();assert out['available_actions']==['wait'],out
        return self.prepare(world=True).call()

def review(result,reason=None):
    out,_=result;assert out['phase']=='campaign_review' and out['available_actions']==['wait'],out
    if reason:assert out['review_reason']=='owned_field_medicine_'+reason,out

@pytest.mark.parametrize('key',['2f_switch1','3f_switch1','3f_hole','2f_switch2'])
def test_genuine_child_receipt_rebases_once_keeps_parent_pending_and_real_clock(key):
    s=Session(key).select();c=s.c;old=deepcopy(c.baseline);frozen=deepcopy(c.__dict__)
    out,nxt=s.finish()
    assert out['field_move_kind']=='owned-overworld-hyper' and nxt==s.step_id
    assert c is s.parent_identity and c.pending is s.pending and c.pending['executed'] is False
    for k,v in frozen.items():
        if k!='baseline':assert c.__dict__[k]==v,k
    assert c.baseline!=old and c.baseline==later.boulder._resources(s.state['progress'])
    hist=c.medical_interruption_history;assert len(hist)==1 and hist[0]['old_baseline']==old
    assert coordinator._active()==set()
    assert hist[0]['new_baseline']==c.baseline and hist[0]['receipt_ack'] is True
    assert hist[0]['medicine_receipt']==out['medicine_receipt']
    assert coordinator.frame_clock(c,s.game.frame_count)==frozen['last_now']+(s.game.frame_count-frozen['last_frame'])/60
    assert s.call()[0]['available_actions']==['wait'] and len(c.medical_interruption_history)==1
    s.prepare(world=True);assert s.call() is None
    actual_now=coordinator.frame_clock(c,s.game.frame_count)
    out,_=later.context(s.game,s.state,s.plan,s.step_id,s.text,s.grid,['wait'],now=actual_now)
    assert out['phase']!='campaign_review' and c.pending is s.pending and not c.pending['executed']
    assert c.started==frozen['started'] and c.last_now==actual_now and c.calls==frozen['calls']+1
    assert coordinator.applies(s.plan,'some-next-step') is False

@pytest.mark.parametrize('bad',['native','peer','unknown_peer','step','job','evidence','fnt','status','review'])
def test_preflight_conflicts_sticky_before_child_and_getter(bad,monkeypatch):
    s=Session();kwargs={}
    if bad=='native':kwargs['native_owner']=object()
    if bad=='peer':p=s.peers();p['legacy_field']={'foreign'};kwargs['peer_owners']=p
    if bad=='unknown_peer':p=s.peers();p['legacy_field']=None;kwargs['peer_owners']=p
    if bad=='step':s.plan['steps'][0]['target'][0]+=1
    if bad=='job':s.plan['training_job']['deep']['x']=2
    if bad=='evidence':s.capsule['evidence']['review_sha256']='bad'
    if bad=='fnt':s.state['progress']['party'][0]['hp']=0
    if bad=='status':s.state['progress']['party'][0]['status']=8
    if bad=='review':s.state.update(phase='strategy_review',review_reason='unknown')
    def forbidden(*a,**kw):raise AssertionError('preflight may not read UI/getter')
    monkeypatch.setattr(later.boulder,'read_later_boulder_observation',forbidden)
    result=s.call(**kwargs);review(result);error=result[0]['review_reason']
    assert coordinator._active()=={s.step_id}
    s.capsule['evidence']['review_sha256']='a'*64
    result=s.call();review(result);assert result[0]['review_reason']==error
    assert not hyper._CONTROLLERS

@pytest.mark.parametrize('mutate',[
    lambda s:s.mons.reverse(),lambda s:s.mons[1]['pp'].__setitem__(0,12),
    lambda s:s.mons[2].update(exp=s.mons[2]['exp']+1),lambda s:s.mons[2].update(hp=s.mons[2]['hp']-1),
    lambda s:s.items.reverse(),lambda s:s.game.memory.__setitem__(sdk.PLAYER_MONEY_ADDRESS+2,0x22),
])
def test_unrelated_resources_stop_without_parent_rebase(mutate):
    s=Session().select();base=deepcopy(s.c.baseline);mutate(s)
    result=s.prepare(hh.party(s.mons,s.target)).call();review(result)
    assert s.c.baseline==base and not hasattr(s.c,'medical_interruption_history')

@pytest.mark.parametrize('kind',['stone','event','strength','object','toggle'])
def test_source_proof_change_at_child_start_stops(kind):
    s=Session();s.call();base=deepcopy(s.c.baseline);mem=s.game.memory
    if kind=='stone':mem[0xC200+16*s.case['slot']+5]+=1
    if kind=='event':mem[0xD813]^=1
    if kind=='strength':mem[0xD728]&=0xFE
    if kind=='object':mem[0xC215]+=1
    if kind=='toggle':mem[0xD5B2]^=1
    result=s.prepare(world=True).call();review(result,'child_start_world_changed')
    assert not hyper._CONTROLLERS and s.c.baseline==base

def test_retained_controller_mutation_or_forged_after_without_true_receipt_cannot_rebase():
    s=Session().start();base=deepcopy(s.c.baseline);s.c.pending['executed']=True
    review(s.prepare(hh.start()).call(),'retained_parent_state_changed')
    assert s.c.baseline==base and not hasattr(s.c,'medical_interruption_history')

def test_parent_hot_reload_and_pending_do_not_rebuild_during_child():
    s=Session().start();c=s.c;p=c.pending;started=c.started;calls=c.calls
    importlib.reload(coordinator)
    assert Path(coordinator.__file__).resolve()==(SOURCE/'owned_field_medicine.py').resolve()
    spec=importlib.util.spec_from_file_location(later.__name__,SOURCE/'victory_later_boulders_bridge.py')
    spec.loader.exec_module(later)
    s.expect(hh.start(6),'a')
    assert s.c is c and later._CONTROLLERS[s.step_id] is c and c.pending is p
    assert c.started==started and c.calls==calls and not p['executed']

def test_after_complete_parent_walks_and_two_actual_pushes_keep_original_capsule_and_owner():
    s=Session().select();out,nxt=s.finish();assert out['field_move_kind']=='owned-overworld-hyper'
    c=s.c;p=c.pending;started=c.started;baseline=deepcopy(c.baseline)
    s.prepare(world=True);assert s.call() is None
    # The final menu B cannot acknowledge the retained direction.
    out,_=later.context(s.game,s.state,s.plan,s.step_id,s.text,s.grid,['b'],now=coordinator.frame_clock(c,s.game.frame_count))
    assert out['phase']!='campaign_review' and c.pending is p and not p['executed']
    for _ in range(160):
        if c.push_index>=2:break
        pending=c.pending;assert pending and not pending['executed']
        if pending['kind']=='walk':
            s.game.memory[0xD362],s.game.memory[0xD361]=pending['expected_player']
        else:
            a=0xC200+16*s.case['slot']
            s.game.memory[a+5]=pending['expected_stone'][0]+4
            s.game.memory[a+4]=pending['expected_stone'][1]+4
            s.game.memory[0xD718]=s.case['slot']
        s.prepare(world=True);assert s.call() is None
        out,_=later.context(s.game,s.state,s.plan,s.step_id,s.text,s.grid,[pending['action']],
            now=coordinator.frame_clock(c,s.game.frame_count))
        assert out['phase']!='campaign_review',out
    assert c.push_index==2 and c.started==started and c.baseline==baseline
    assert c is s.parent_identity and len(c.medical_interruption_history)==1
    assert s.state['location']!=s.capsule['original_location']

def test_child_cannot_publish_field_completion_before_medicine_close(monkeypatch):
    s=Session();s.call();s.prepare(world=True)
    monkeypatch.setattr(hyper,'context',lambda *a,**kw:(dict(phase='item_menu',available_actions=['a','wait'],
        field_move_complete=True,field_move_kind='overworld-hyper'),'complete'))
    review(s.call(),'premature_child_field_completion')
    assert not hasattr(s.c,'medical_interruption_history')

def test_forged_actual_hp_and_item_without_ui_receipt_never_rebases():
    s=Session().select();base=deepcopy(s.c.baseline);s.effect()
    # The real resource effect alone is insufficient: source done and closure
    # still have to run through the child controller with real previous.
    result=s.prepare(world=True).call();review(result)
    assert s.c.baseline==base and not hasattr(s.c,'medical_interruption_history')

def test_public_active_releases_done_retains_sticky_and_typed_unknown(monkeypatch):
    assert coordinator._active()==set()
    s=Session();s.call();assert coordinator._active()=={s.step_id}
    monkeypatch.setattr(coordinator,'_SESSIONS',{'unknown':[]})
    assert coordinator._active() is None
    monkeypatch.setattr(coordinator,'_SESSIONS',{})
    assert coordinator._active() is None
