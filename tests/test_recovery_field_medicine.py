"""Actual SDK/progress/text/movement readers with synthetic menu and RAM."""
from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path
import pytest
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent

def load(name,path):
    spec=importlib.util.spec_from_file_location('laya_pokemon._recovery_full_heal_'+name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert Path(module.__file__).resolve()==path.resolve()
    return module

m=importlib.import_module('laya_pokemon.overworld_hyper')
assert Path(m.__file__).resolve()==ROOT/'src/laya_pokemon/overworld_hyper.py'
bridge=load('bridge_test',ROOT/'src/laya_pokemon/overworld_hyper_bridge.py')
shared=load('shared_test',ROOT/'src/laya_pokemon/owned_field_medicine.py')
coordinator=importlib.import_module('laya_pokemon.recovery_field_medicine')
assert Path(coordinator.__file__).resolve()==ROOT/'src/laya_pokemon/recovery_field_medicine.py'
recovery=importlib.import_module('laya_pokemon.league_recovery')
helper=importlib.import_module('test_overworld_hyper')
assert Path(helper.__file__).resolve()==ROOT/'tests/test_overworld_hyper.py'

@pytest.fixture(autouse=True)
def clear(monkeypatch):
    for name,value in (('_CONTROLLERS',{}),('_BINDINGS',{}),('_OWNERS',{}),('_COMPLETED',set()),('_REGISTRY_ERROR',None)):
        monkeypatch.setattr(bridge,name,value)
    for name,value in (('_SESSIONS',{}),('_ERRORS',{}),('_REGISTRY_ERROR',None)):
        monkeypatch.setattr(shared,name,value)

def put(c,x,y,s):c[y][x:x+len(s)]=list(s)

def party(mons,cursor=None,marker='▶',receipt=False):
    c=helper.blank()
    for i,mon in enumerate(mons):
        put(c,3,2*i,sdk.POKEMON_SPECIES_NAMES[mon['species']])
        put(c,13 if mon['level']==100 else 14,2*i,str(mon['level']))
        if mon['hp']==0:put(c,17,2*i,'FNT')
        elif mon['status']==8:put(c,17,2*i,'PSN')
        put(c,13,2*i+1,f"{mon['hp']:3}/{mon['max_hp']:3}")
    if cursor is not None:c[2*cursor+1][0]=marker
    if receipt:
        put(c,1,14,'FEAROW');c[14][7]="'s";put(c,1,16,'health returned!')
    else:put(c,1,14,'Use item on which');put(c,1,16,'POKéMON?')
    return c

class Session:
    def __init__(self,quantity=10):
        self.game=helper.Game();self.game.frame_count=5353
        mons=self.game.game_wrapper.party
        for mon in mons:mon.update(hp=150,max_hp=150,status=0)
        next(mon for mon in mons if mon['species']==35).update(level=38,hp=117,max_hp=117,status=8)
        next(mon for mon in mons if mon['species']==7).update(level=37,hp=0,max_hp=125,status=0)
        mons.sort(key=lambda mon:[35,7,132,102,154,19].index(mon['species']))
        self.game.game_wrapper.inventory=[dict(item=i,quantity=q) for i,q in ((4,6),(42,1),(49,1),(63,1),(196,1),
            (224,1),(74,1),(72,1),(40,1),(73,1),(3,9),(198,1),(199,1),(48,1),(1,1),(197,1),(43,1),(52,quantity),(18,5))]
        self.game.memory.update({0xD35E:198,0xD362:11,0xD361:13})
        self.evidence={'review_sha256':'a'*64,'state_sha256':'b'*64}
        steps=recovery.expected_steps();self.sid=steps[0]['id'];self.child='game29-fearow-full-heal'
        self.plan=dict(mode='league_campaign',training_job=recovery.JOB,lead_species=35,steps=steps,
            reviewed_fnt_recovery=dict(kind=recovery.KIND,source_frame=32809,source_location=dict(map_id=198,x=6,y=1),
                fainted_species=7,steps_sha256=recovery.digest(steps),review_sha256=recovery.SOURCE_REVIEW_SHA256,
                state_sha256=recovery.SOURCE_STATE_SHA256))
        self.cap=dict(kind='recovery_full_heal',original_game='game29',original_step_id=self.sid,
            original_step_sha256=shared.canonical_sha256(steps[0]),training_job_sha256=shared.canonical_sha256(self.plan['training_job']),
            steps_sha256=shared.canonical_sha256(steps),recovery_capsule_sha256=shared.canonical_sha256(self.plan['reviewed_fnt_recovery']),
            original_frame=5353,original_location=dict(map_id=198,x=11,y=13),item=52,quantity=1,target_species=35,
            status_before=8,status_after=0,reviewed_fainted_bench=[7],child_step_id=self.child,evidence=deepcopy(self.evidence))
        self.plan['recovery_field_medicine']=self.cap
        self.previous=[];self.kw=None
        self.attrition=dict(review_reason='party_attrition_requires_center',party_attrition=dict(fainted_party_indices=[1],issue='reviewed_recovery_party_changed'))
        self.original_plan=deepcopy(self.plan)
        self.prepare(world=True)
    @property
    def mons(self):return self.game.game_wrapper.party
    @property
    def items(self):return self.game.game_wrapper.inventory
    def peers(self):
        p={name:set() for name in shared.PEER_NAMES};p['overworld_hyper']=bridge._active();return p
    def prepare(self,cells=None,*,world=False,frames=40,same=False):
        if self.kw is not None and not same:self.game.frame_count+=frames
        self.game.cells=helper.blank() if cells is None else deepcopy(cells)
        self.game.memory[0xFF40]=0x91 if world else 0xB1
        text=helper.read_visible_text(self.game);assert text['read_valid'],text
        sig=m.read_observation(self.game,self.game.frame_count,sdk,map_id=198);assert sig['read_valid'],sig
        state=dict(frame=self.game.frame_count,phase='unclassified',location=dict(map_id=198,x=11,y=13),
            progress=deepcopy(sig['progress']),battle_state=dict(raw=0,kind='none',active=False,observation_frame=self.game.frame_count))
        cells=[[x,13] for x in range(12)]
        grid=dict(source='wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM',
            walkable=[[1]*30 for _ in range(18)],observation_frame=self.game.frame_count,verified_location=[198,11,13],
            screen_cells_verified=len(cells),visible_verified_cells=cells)
        self.kw=dict(state=state,text=text,grid=grid if world else None)
        return self
    def call(self,**overrides):
        params=dict(game_id='game29',native_owner=self.game,source_evidence=self.evidence,shared=shared,
            hyper_bridge=bridge,recovery=recovery,peer_owners=self.peers(),attrition=self.attrition)
        params.update(overrides)
        snapshot=deepcopy((self.kw,self.plan,dict(self.game.memory)))
        out=coordinator.context(self.game,self.kw['state'],self.plan,self.sid,self.kw['text'],self.kw['grid'],self.previous,**params)
        assert snapshot==(self.kw,self.plan,dict(self.game.memory))
        if out:self.previous=[out[0]['available_actions'][0]]
        return out
    def expect(self,cells,action,**kw):
        out,nxt=self.prepare(cells,**kw).call();assert nxt==self.sid
        assert out['available_actions']==[action,'wait'],out
        return out
    def select(self):
        out,nxt=self.call();assert out['available_actions']==['start','wait'] and nxt==self.sid,out
        self.c=bridge._CONTROLLERS[self.child]
        self.expect(helper.start(6),'a')
        wanted=next(i for i,item in enumerate(self.items) if item['item']==52)
        for i in range(wanted+1):self.expect(helper.bag(m,self.items,max(0,i-2),min(2,i)),'a' if i==wanted else 'down')
        self.off,self.cur=max(0,wanted-2),min(2,wanted)
        self.expect(helper.use(m,self.items,self.off,self.cur),'a')
        self.expect(party(self.mons,0),'a')
        return self
    def effect(self):
        self.mons[0]['status']=0
        item=next(i for i in self.items if i['item']==52);item['quantity']-=1
        if not item['quantity']:self.items.remove(item)
    def finish(self):
        self.effect();out,_=self.prepare(party(self.mons,receipt=True)).call();assert out['available_actions']==['wait'],out
        out,_=self.prepare(party(self.mons,receipt=True),frames=53).call();assert out['available_actions']==['wait'],out
        self.expect(party(self.mons,receipt=True),'a',frames=1)
        self.expect(helper.bag(m,self.items,self.off,self.cur),'b');self.expect(helper.start(6),'b')
        out,_=self.prepare(world=True).call();assert out['available_actions']==['wait'],out
        return self.prepare(world=True).call()

def review(result):
    out,_=result;assert out['phase']=='campaign_review' and out['available_actions']==['wait'],out

@pytest.mark.parametrize('quantity',[1,10])
def test_full_heal_normal_source_ui_closes_preserves_fnt_and_original_recovery(quantity):
    s=Session(quantity);before=deepcopy(s.kw['state']['progress']);s.select();c=s.c;started=c.started
    out,nxt=s.finish()
    assert out['field_move_kind']=='recovery-full-heal' and nxt==s.sid
    expected=deepcopy(before);expected['party'][0]['status']=0
    item=next(i for i in expected['inventory'] if i['item']==52);item['quantity']-=1
    if not item['quantity']:expected['inventory'].remove(item)
    assert s.kw['state']['progress']==expected and s.mons[1]['hp']==0
    assert s.plan==s.original_plan and c is s.c and c.started==started
    assert shared._active()==set() and bridge._active()==set()
    rec=shared._SESSIONS[s.sid];assert rec['kind']=='recovery_full_heal' and rec['done'] and rec['receipt']['receipt_ack']
    assert s.call()[0]['available_actions']==['wait']
    s.prepare(world=True);assert s.call() is None
    s.kw['state']['location']['x']=12;assert s.call() is None
    assert not coordinator.applies(s.plan,s.plan['steps'][1]['id'],shared=shared)

@pytest.mark.parametrize('bad',['native','peer','missing_peer','unknown_peer','capsule','job','steps','recovery_capsule',
    'frame','location','review','extra_fnt','status','already_cured','bench_revived','target_hp','evidence'])
def test_preflight_refuses_before_getter_and_sticks(bad,monkeypatch):
    s=Session();params={}
    if bad=='native':params['native_owner']=object()
    if bad=='peer':p=s.peers();p['legacy_field']={'other'};params['peer_owners']=p
    if bad=='missing_peer':p=s.peers();p.pop('tm24_teaching');params['peer_owners']=p
    if bad=='unknown_peer':p=s.peers();p['native_wait']=None;params['peer_owners']=p
    if bad=='capsule':s.cap['quantity']=2
    if bad=='job':s.plan['training_job']='changed'
    if bad=='steps':s.plan['steps'][0]['target'][0]+=1
    if bad=='recovery_capsule':s.plan['reviewed_fnt_recovery']['state_sha256']='c'*64
    if bad=='frame':s.kw['state']['frame']+=1
    if bad=='location':s.kw['state']['location']['x']=10
    if bad=='review':s.kw['state'].update(phase='strategy_review',review_reason='unknown')
    if bad=='extra_fnt':s.kw['state']['progress']['party'][2]['hp']=0
    if bad=='status':s.kw['state']['progress']['party'][2]['status']=64
    if bad=='already_cured':s.kw['state']['progress']['party'][0]['status']=0
    if bad=='bench_revived':s.kw['state']['progress']['party'][1]['hp']=1
    if bad=='target_hp':s.kw['state']['progress']['party'][0]['hp']-=1
    if bad=='evidence':params['source_evidence']=dict(s.evidence,state_sha256='d'*64)
    def no_read(*a,**kw):raise AssertionError('must reject before native read')
    monkeypatch.setattr(m,'read_observation',no_read)
    result=s.call(**params);review(result);reason=result[0]['review_reason']
    result=s.call();review(result);assert result[0]['review_reason']==reason
    assert not bridge._CONTROLLERS and shared._active()=={s.sid}

@pytest.mark.parametrize('bad',['hp','pp','exp','money','bag_order','other_item','nido_revive','other_status'])
def test_unrelated_effect_delta_never_completes(bad):
    s=Session().select();s.effect()
    if bad=='hp':s.mons[0]['hp']-=1
    if bad=='pp':s.mons[2]['pp'][0]-=1
    if bad=='exp':s.mons[2]['exp']+=1
    if bad=='money':s.game.memory[sdk.PLAYER_MONEY_ADDRESS+2]=1
    if bad=='bag_order':s.items.reverse()
    if bad=='other_item':s.items[0]['quantity']-=1
    if bad=='nido_revive':s.mons[1]['hp']=1
    if bad=='other_status':s.mons[2]['status']=8
    review(s.prepare(party(s.mons,receipt=True)).call())
    assert not shared._SESSIONS[s.sid]['done']

def test_no_done_text_or_real_target_a_cannot_be_replaced_by_resource_change():
    s=Session().select();s.effect();review(s.prepare(world=True).call())
    assert not shared._SESSIONS[s.sid]['done']

def test_shared_registry_reload_preserves_same_child_pending_and_clock():
    s=Session().select();record=shared._SESSIONS[s.sid];c=s.c;pending=c.pending;started=c.started;calls=c.calls
    shared.__spec__.loader.exec_module(shared);coordinator.__spec__.loader.exec_module(coordinator)
    assert shared._SESSIONS[s.sid] is record and bridge._CONTROLLERS[s.child] is c and c.pending is pending
    assert c.calls==calls and c.started==started
    out,nxt=s.finish();assert out['field_move_kind']=='recovery-full-heal' and nxt==s.sid

def test_premature_field_completion_is_not_journaled(monkeypatch):
    s=Session()
    monkeypatch.setattr(bridge,'context',lambda *a,**kw:(dict(phase='item_menu',available_actions=['a','wait'],
        field_move_complete=True,field_move_kind='overworld-hyper'),'complete'))
    review(s.call());assert not shared._SESSIONS[s.sid]['done']

@pytest.mark.parametrize('key,value',[('source_map_id',198.0),('script_address',float(0xD640)),('status5',256)])
def test_fresh_completion_getter_rejects_nonexact_native_mapping(key,value):
    s=Session();signal=m.read_observation(s.game,s.game.frame_count,sdk,map_id=198)
    expected=deepcopy(signal['progress'])
    assert coordinator._fresh_closed_getter(signal,s.game.frame_count,s.game,expected,m)
    if key=='status5':signal['values'][key]=value
    else:signal[key]=value
    assert not coordinator._fresh_closed_getter(signal,s.game.frame_count,s.game,expected,m)

@pytest.mark.parametrize('tamper',['controller','binding','receipt'])
def test_done_does_not_mask_changed_original_child_or_receipt(tamper):
    s=Session().select();s.finish();s.prepare(world=True)
    if tamper=='controller':bridge._CONTROLLERS[s.child]=object()
    if tamper=='binding':bridge._BINDINGS[s.child]=deepcopy(bridge._BINDINGS[s.child])
    if tamper=='receipt':shared._SESSIONS[s.sid]['receipt']['medicine_receipt']['status_after']=8
    review(s.call())
    assert shared._active()=={s.sid}

def test_done_receipt_keeps_object_identity_across_pure_class_reload_and_location_change():
    s=Session().select();s.finish();c=s.c;old_class=c.__class__
    m.__spec__.loader.exec_module(m)
    assert c.__class__ is old_class and c.__class__ is not m.OverworldHyperController
    s.prepare(world=True);s.kw['state']['location']['x']=12
    assert s.call() is None and shared._active()==set()

def test_unmarked_old_plan_with_no_cursor_does_not_activate_recovery_profile():
    for plan in ({'mode':'league_campaign','steps':[]},
            {'mode':'league_campaign','steps':[{'id':'old','mechanic':'overworld_hyper','overworld_hyper_intent':m.INTENTS[0]}]}):
        assert coordinator.applies(plan,None,shared=shared) is False
    assert coordinator.applies({'recovery_field_medicine':{}},None,shared=shared) is True
