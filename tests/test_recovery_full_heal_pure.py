"""Real SDK/getter + synthetic field UI; no emulator, ROM, state or input."""
from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path
import sys
import pytest
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def load(name,path):
    spec=importlib.util.spec_from_file_location('laya_pokemon._recovery_full_heal_'+name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert Path(module.__file__).resolve()==path.resolve()
    assert module.__name__ not in sys.modules
    return module

m=importlib.import_module('laya_pokemon.overworld_hyper')
h=importlib.import_module('test_overworld_hyper')
assert Path(m.__file__).resolve()==ROOT/'src/laya_pokemon/overworld_hyper.py'
assert Path(h.__file__).resolve()==ROOT/'tests/test_overworld_hyper.py'

def intent():
    return dict(kind='recovery_full_heal',map_id=198,target=[11,13],item=52,quantity=1,
        target_species=35,status_before=8,status_after=0,reviewed_fainted_bench=[7],
        owner_step_id='league28-fnt-recovery-00',capsule_sha256='a'*64)

def authority(v):
    return dict(kind=v['kind'],owner_step_id=v['owner_step_id'],capsule_sha256=v['capsule_sha256'],
        location=m._location(v),reviewed_fainted_bench=[7],status_before=8,status_after=0)

def party(mons,cursor=None,marker='▶',receipt=False):
    cells=h.party(mons,cursor,marker)
    for i,mon in enumerate(mons):
        if mon['hp']==0:h.put(cells,17,2*i,'FNT')
        elif mon['status']==8:h.put(cells,17,2*i,'PSN')
    if receipt:
        cells[14]=[' ']*20;cells[16]=[' ']*20
        h.put(cells,1,14,'FEAROW');cells[14][7]="'s"
        h.put(cells,1,16,'health returned!')
    return cells

class Session(h.Session):
    def __init__(self,quantity=10):
        super().__init__(m)
        self.intent=intent();self.auth=authority(self.intent);self.target=4
        for mon in self.mons:mon.update(hp=mon['max_hp'],status=0)
        self.mons[4].update(level=38,hp=117,max_hp=117,status=8)
        self.mons[5].update(level=37,hp=0,max_hp=125,status=0)
        self.items[3]['quantity']=5;self.items[4]['quantity']=quantity
        self.game.memory.update({0xD35E:198,0xD362:11,0xD361:13})
        self.location=dict(map_id=198,x=11,y=13)
        self.c=m.OverworldHyperController(self.intent,owner=self.game,owned_authority=self.auth)
    def world_grid(self):
        cells=[[x,13] for x in range(12)]
        return dict(walkable=[[1]*30 for _ in range(18)],observation_frame=self.game.frame_count,
            verified_location=[198,11,13],screen_cells_verified=len(cells),visible_verified_cells=cells,
            source='wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM')
    def prepare(self,cells=None,*,world=False,frames=40,same=False):
        if self.kw is not None and not same:self.game.frame_count+=frames;self.now+=frames/60
        self.game.cells=h.blank() if cells is None else deepcopy(cells)
        self.game.memory[0xFF40]=0x91 if world else 0xB1
        text=h.read_visible_text(self.game);assert text['read_valid'],text
        signal=m.read_observation(self.game,self.game.frame_count,sdk,map_id=self.location['map_id']);assert signal['read_valid'],signal
        state=dict(frame=self.game.frame_count,phase='unclassified',location=deepcopy(self.location),
            progress=deepcopy(signal['progress']),battle_state=dict(raw=0,kind='none',active=False,
                observation_frame=self.game.frame_count))
        self.kw=dict(state=state,text=text,grid=self.world_grid() if world else None,signal=signal,
            previous=list(self.previous),owner=self.game,now=self.now)
        if self.before is None:self.before=deepcopy(state['progress'])
        return self
    def select(self,toss=False):
        self.expect(h.blank(),'start',world=True);self.expect(h.start(6),'a')
        for i in range(5):self.expect(h.bag(m,self.items,max(0,i-2),min(2,i)),'a' if i==4 else 'down')
        if toss:self.expect(h.use(m,self.items,2,2,13),'up')
        self.expect(h.use(m,self.items,2,2),'a')
        for i in range(5):self.expect(party(self.mons,i),'a' if i==4 else 'down')
        return self
    def effect(self):
        self.mons[4]['status']=0;self.items[4]['quantity']-=1
        if self.items[4]['quantity']==0:self.items.pop(4)
    def receipt(self):return party(self.mons,receipt=True)
    def finish(self):
        self.effect();out=self.prepare(self.receipt()).call();assert out['available_actions']==['wait'],out
        out=self.prepare(self.receipt(),frames=53).call();assert out['available_actions']==['wait'],out
        self.expect(self.receipt(),'a',frames=1)
        assert self.c.context(**self.kw)['available_actions']==['wait']
        self.expect(h.bag(m,self.items,2,2),'b');self.expect(h.start(6),'b')
        assert self.prepare(world=True).call()['available_actions']==['wait']
        out=self.prepare(world=True).call();assert out['overworld_medicine_complete'],out
        return out

@pytest.mark.parametrize('quantity',[10,1])
def test_exact_full_heal_normal_ui_closes_once_and_preserves_fnt_hp_pp_exp_order(quantity):
    s=Session(quantity).select(toss=True);before=deepcopy(s.before);out=s.finish()
    expected=deepcopy(before);expected['party'][4]['status']=0
    expected['inventory'][4]['quantity']-=1
    if expected['inventory'][4]['quantity']==0:expected['inventory'].pop(4)
    assert s.kw['state']['progress']==expected==s.c.after
    assert out['medicine_receipt']['item']==52 and out['medicine_receipt']['status_before']==8
    assert out['medicine_receipt']['status_after']==0 and out['medicine_receipt']['reviewed_fainted_bench']==[7]
    assert s.c.baseline==before and s.c.pending is None and s.c.receipt_ack and s.c.effect_selected
    assert before['party'][5]==expected['party'][5] and expected['party'][5]['hp']==0
    assert m.recovery_party(before) is before['party']
    assert s.c.closed_frame<s.game.frame_count

@pytest.mark.parametrize('field,value',[
    ('kind','overworld_full_heal'),('map_id',194),('map_id',True),('target',[12,13]),('target',[11,True]),
    ('item',18),('quantity',2),('quantity',True),('target_species',7),('status_before',64),('status_before',True),
    ('status_after',8),('reviewed_fainted_bench',[]),('reviewed_fainted_bench',[7.0]),
    ('owner_step_id','another'),('capsule_sha256','a'*63),('capsule_sha256','A'*64)])
def test_recovery_intent_is_exact_and_location_target_status_never_generalized(field,value):
    v=intent();v[field]=value;assert not m._RECOVERY_INTENT(v)
    with pytest.raises(ValueError):m.OverworldHyperController(v,owner=object(),owned_authority={})

def test_exact_authority_required_and_deepcopied_contract_detects_tamper():
    v=intent();a=authority(v)
    for bad in (None,{},dict(a,extra=True),dict(a,status_before=0),dict(a,reviewed_fainted_bench=[])):
        with pytest.raises(ValueError):m.OverworldHyperController(v,owner=object(),owned_authority=bad)
    s=Session();s.prepare(world=True);s.c.owned_authority['status_before']=0
    h.review(s.call(),'owner_intent_frame_clock_or_previous_unverified')

@pytest.mark.parametrize('mutate',[
    lambda s:s.mons[5].update(hp=1),lambda s:s.mons[5].update(status=8),lambda s:s.mons[0].update(hp=0),
    lambda s:s.mons[0].update(hp=s.mons[0]['max_hp']-1),lambda s:s.mons[1].update(status=64),
    lambda s:s.mons[4].update(hp=116),lambda s:s.mons[4].update(status=64),
    lambda s:s.mons[0].update(species=19.0),lambda s:s.mons[0].update(species_name='FEAROW'),
    lambda s:s.mons[5].update(hp=False),lambda s:s.mons[0]['moves'].__setitem__(0,0),
    lambda s:s.mons[0]['pp'].__setitem__(0,255)])
def test_reviewed_party_is_validated_without_forging_fnt_hp(mutate):
    s=Session();mutate(s);s.prepare(world=True)
    if 'species_name' in s.mons[0] and s.mons[0]['species_name']!=s.kw['state']['progress']['party'][0]['species_name']:
        for p in (s.kw['state']['progress'],s.kw['signal']['progress']):p['party'][0]['species_name']=s.mons[0]['species_name']
    original=deepcopy(s.kw['state']['progress'])
    assert m.recovery_party(original) is None
    h.review(s.call(),'recovery_resources_or_reviewed_bench_unverified')
    assert original==s.kw['state']['progress'] and s.c.pending is None

def test_already_healed_fearow_and_missing_full_heal_are_no_effect_before_start():
    s=Session();s.mons[4]['status']=0;s.prepare(world=True)
    h.review(s.call(),'exact_poisoned_fearow_required')
    s=Session();s.items[:]=[i for i in s.items if i['item']!=52];s.prepare(world=True)
    h.review(s.call(),'full_heal_missing')

@pytest.mark.parametrize('mutate',[
    lambda s:s.mons.reverse(),lambda s:s.mons[0].update(exp=s.mons[0]['exp']+1),
    lambda s:s.mons[1]['pp'].__setitem__(0,19),lambda s:s.items[0].update(quantity=5),
    lambda s:s.game.memory.__setitem__(sdk.PLAYER_MONEY_ADDRESS+2,1),
    lambda s:s.mons[5].update(hp=125),lambda s:s.mons[0].update(status=8)])
def test_unrelated_full_progress_change_is_sticky_without_repeated_use(mutate):
    s=Session().select();mutate(s);s.prepare(party(s.mons,s.target))
    out=s.call();h.review(out);error=out['review_reason']
    assert s.call()['review_reason']==error

@pytest.mark.parametrize('bad',['arrow','wrong_name','shifted_s','ascii_s','caller_private_s','pollution','metadata'])
def test_fullheal_receipt_is_exact_physical_actor_and_no_arrow(bad):
    s=Session().select();s.effect();cells=s.receipt()
    if bad=='arrow':cells[16][18]='▼'
    if bad=='wrong_name':h.put(cells,1,14,'LAPRAS')
    if bad=='shifted_s':cells[14][7]=' ';cells[14][8]="'s"
    if bad=='ascii_s':cells[14][7]="'";cells[14][8]='s'
    if bad=='caller_private_s':
        s.prepare(cells);s.kw['text']['cells'][14][7]=m.ui._S
    else:s.prepare(cells)
    if bad=='pollution':s.kw['text']['cells'][0][19]='X'
    if bad=='metadata':s.kw['text']['lines']=['invented']
    h.review(s.call())

def test_true_target_a_effect_and_item_consumption_required_before_receipt_ack():
    s=Session().select();s.previous=['wait'];s.effect();s.prepare(s.receipt())
    h.review(s.call(),'actual_pending_ack_required')
    s=Session().select();s.mons[4]['status']=0;s.prepare(s.receipt())
    h.review(s.call(),'unexpected_recovery_effect_or_resource_change')
    s=Session().select();fake=deepcopy(s.mons);fake[4]['status']=0;cells=party(fake,receipt=True);s.prepare(cells)
    h.review(s.call(),'fullheal_done_without_exact_status_and_item_consumption')

def test_fullheal_cannot_close_world_without_source_receipt_and_both_real_b():
    s=Session().select();s.effect();s.prepare(world=True)
    h.review(s.call(),'native_text_unverified')
    s=Session().select();s.effect();s.prepare(s.receipt()).call();s.expect(s.receipt(),'a',frames=54)
    s.previous=['b'];s.prepare(h.bag(m,s.items,2,2));h.review(s.call(),'actual_pending_ack_required')

def test_owned_source_map_script_owner_and_clock_stay_exact():
    for field,value in (('source_map_id',194),('script_address',0xD63F),('owner_id',0)):
        s=Session();s.prepare(world=True);s.kw['signal'][field]=value;h.review(s.call())
    s=Session();s.expect(h.blank(),'start',world=True);s.prepare(h.start(6))
    h.review(s.call(now=10),'true_frame_clock_required')

@pytest.mark.parametrize('species,quantity,maximum',[(19,8,None),(132,1,None),(19,2,320)])
def test_old_fixed_hyper_complete_regression(species,quantity,maximum):
    h.test_complete_normal_overworld_transaction_exact_target_once(m,species,quantity,maximum)

@pytest.mark.parametrize('name',[
    'test_full_hp_and_missing_medicine_never_spent','test_fresh_actual_previous_ack_required_and_same_frame_no_repeat',
    'test_same_frame_packet_conflict_clock_timeout_and_reload_preserve','test_real_reader_double_read_sdk_anchors_movement_and_full_progress',
    'test_missing_after_hp_done_text_and_unknown_pollution_never_spends_extra','test_pending_a_known_source_old_page_waits_no_repeat',
    'test_world_grid_unknown_cannot_open_menu','test_wrong_observation_owner_packet_and_ui_cursor_stop'])
def test_old_fixed_hyper_negative_regressions(name):
    m._spec=m.__spec__;getattr(h,name)(m)


class OwnedHyperSession(h.Session):
    prepare=Session.prepare
    def __init__(self,map_id=198):
        super().__init__(m)
        self.target=5;self.mons[self.target]['hp']=50
        self.location=dict(map_id=map_id,x=18,y=1)
        self.intent=dict(kind=m.OWNED_KIND,map_id=map_id,target=[18,1],item=18,quantity=1,
            target_species=7,owner_step_id='old-owned-step',case_key='3f_switch1' if map_id==198 else '2f_switch1',capsule_sha256='c'*64)
        self.auth=dict(owner_step_id='old-owned-step',case_key=self.intent['case_key'],
            capsule_sha256='c'*64,location=deepcopy(self.location))
        self.c=m.OverworldHyperController(self.intent,owner=self.game,owned_authority=self.auth)
        self.game.memory.update({0xD35E:map_id,0xD362:18,0xD361:1})
    def world_grid(self):
        cells=[[x,1] for x in range(12)]+[[18,1]]
        return dict(walkable=[[1]*30 for _ in range(18)],observation_frame=self.game.frame_count,
            verified_location=[self.location['map_id'],18,1],screen_cells_verified=len(cells),visible_verified_cells=cells,
            source='wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM')
    def select(self):
        self.expect(h.blank(),'start',world=True);self.expect(h.start(6),'a')
        for i in range(4):self.expect(h.bag(m,self.items,max(0,i-2),min(2,i)),'a' if i==3 else 'down')
        self.expect(h.use(m,self.items,1,2),'a')
        for i in range(6):self.expect(h.party(self.mons,i),'a' if i==5 else 'down')
        return self

@pytest.mark.parametrize('map_id',[194,198])
def test_old_owned_hyper_profile_still_completes_full_exact_hp_transaction(map_id):
    s=OwnedHyperSession(map_id).select();out=s.finish()
    assert out['medicine_receipt']['item']==18 and out['medicine_receipt']['target_species']==7
    assert 'status_after' not in out['medicine_receipt'] and s.c.after==s.kw['state']['progress']

def test_old_owned_hyper_profile_still_refuses_reviewed_fnt_and_poison():
    s=OwnedHyperSession();s.mons[5]['hp']=0;s.prepare(world=True)
    h.review(s.call(),'resources_or_fnt_status_unverified')
    s=OwnedHyperSession();s.mons[4]['status']=8;s.prepare(world=True)
    h.review(s.call(),'resources_or_fnt_status_unverified')
