"""真 progress/text/rocket readers + 合成 RAM／畫面；不載入 ROM 或遊戲。"""
from collections import defaultdict
from copy import deepcopy
import importlib.util
import importlib
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
from laya_pokemon.observation import read_visible_text
from laya_pokemon.world_map import visible_map_proof

STAGE=Path(__file__).resolve().parent
SOURCE=STAGE.parent/'src/laya_pokemon' if STAGE.name=='tests' else STAGE


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);m._spec=spec;return m


@pytest.fixture
def m():
    if STAGE.name!='tests':raise RuntimeError('正式測試只載src；stage另保留原凍結測試')
    module=importlib.import_module('laya_pokemon.overworld_hyper')
    assert Path(module.__file__).resolve()==(SOURCE/'overworld_hyper.py').resolve()
    module._spec=module.__spec__
    return module


@pytest.fixture
def bridge(m):return load('laya_pokemon._overworld_hyper_bridge_test',SOURCE/'overworld_hyper_bridge.py')


def blank():return [[' ']*20 for _ in range(18)]
def put(c,x,y,s):c[y][x:x+len(s)]=list(s);return c


def start(y=6,marker='▶'):
    c=blank()
    for row,label in ((2,'POKéDEX'),(4,'POKéMON'),(6,'ITEM'),(8,'KEVIN'),(10,'SAVE'),(12,'OPTION'),(14,'EXIT')):put(c,12,row,label)
    return put(c,11,y,marker)


def bag(m,items,off=0,cur=0,marker='▶'):
    c=start()
    for y in range(2,13):c[y][4:20]=[' ']*16
    for n in range(4):
        index,y=off+n,4+2*n
        if index==len(items):put(c,6,y,'CANCEL');break
        if index>len(items):break
        i=items[index];put(c,6,y,m.ui._name(i['item']).replace('É','é'))
        if i['item'] not in m.ui._KEY_ITEMS:put(c,14,y+1,f"×{i['quantity']:2}")
    if off+3<len(items):c[11][18]='▼'
    return put(c,5,4+cur*2,marker)


def use(m,items,off,cur,y=11,marker='▶'):
    c=bag(m,items,off,cur,'▷')
    for row in range(10,16):c[row][13:20]=[' ']*7
    put(c,15,11,'USE');put(c,15,13,'TOSS');return put(c,14,y,marker)


def party(rows,cursor=None,marker='▶',receipt=None,shown_hp=None):
    c=blank()
    for i,p in enumerate(rows):
        put(c,3,2*i,sdk.POKEMON_SPECIES_NAMES[p['species']]);put(c,13 if p['level']==100 else 14,2*i,str(p['level']))
        hp=shown_hp if shown_hp is not None and i==cursor else p['hp']
        put(c,13,2*i+1,f"{hp:3}/{p['max_hp']:3}")
    if cursor is not None:put(c,0,2*cursor+1,marker)
    if receipt is None:put(c,1,14,'Use item on which');put(c,1,16,'POKéMON?')
    else:put(c,1,14,receipt[0]);put(c,1,16,f'recovered by {receipt[1]}!')
    return c


class Memory(defaultdict):
    def __init__(self):super().__init__(int);self.hook=None;self.reads=[]
    def __getitem__(self,k):
        self.reads.append(k);v=super().__getitem__(k)
        return self.hook(k,v) if self.hook else v


class Game:
    def __init__(self):
        self.frame_count=1000;self.memory=Memory();self.cells=blank()
        self.screen=SimpleNamespace(tilemap_position_list=[(0,0,0,0)]*144)
        self.game_wrapper=SimpleNamespace(party=[dict(species=species,level=42+i,hp=150,max_hp=150,status=0,
            exp=80000+i,moves=[33,34,58,109],pp=[20,15,10,10]) for i,species in enumerate((19,132,102,154,35,7))],
            inventory=[dict(item=i,quantity=q) for i,q in ((4,6),(197,1),(43,1),(18,8),(52,4),(238,1))],money=30000)
        self.game_wrapper.party[0].update(hp=39,max_hp=190)
        self.game_wrapper.party[1].update(hp=82,max_hp=230)
        self.memory.update({0xD35E:194,0xD362:20,0xD361:13,0xD356:255,sdk.PARTY_COUNT_ADDRESS:6,
            sdk.PLAYER_MONEY_ADDRESS:0x03,sdk.PLAYER_MONEY_ADDRESS+1:0,sdk.PLAYER_MONEY_ADDRESS+2:0})
        enc={v:k for k,v in sdk.POKEMON_TEXT_DECODING.items() if type(k) is int and 0<=k<=255}
        for i,ch in enumerate('KEVIN'):self.memory[sdk.PLAYER_NAME_ADDRESS+i]=enc[ch]
        self.memory[sdk.PLAYER_NAME_ADDRESS+5]=0x50
        game=self
        class Tiles:
            def __getitem__(self,xy):x,y=xy;return enc[game.cells[y][x].replace('É','é')]
        self.tilemap_background=self.tilemap_window=Tiles()
    def tick(self,*a,**kw):raise AssertionError('禁止 tick')
    def button(self,*a,**kw):raise AssertionError('禁止送鍵')


class Session:
    def __init__(self,m,species=19,quantity=8,maximum=None):
        self.m=m;self.game=Game();self.target=0 if species==19 else 1
        if maximum:self.game.game_wrapper.party[self.target]['max_hp']=maximum
        self.game.game_wrapper.inventory[3]['quantity']=quantity
        self.intent=deepcopy(m.INTENTS[0 if species==19 else 1]);self.c=m.OverworldHyperController(self.intent,owner=self.game)
        self.now=0.;self.previous=();self.kw=None;self.before=None
        self.step=dict(id='hyper-'+str(species),kind='interact',map_id=194,target=[20,13],mechanic='overworld_hyper',overworld_hyper_intent=self.intent)
        self.plan=dict(mode='league_campaign',training_job={'id':'synthetic-normal-hyper','location':[194,20,13]},
            steps=[self.step,dict(id='next',kind='move',map_id=194,target=[20,12])])
    @property
    def items(self):return self.game.game_wrapper.inventory
    @property
    def mons(self):return self.game.game_wrapper.party
    def world_grid(self):
        tiles=[[1]*32 for _ in range(30)]
        visible=visible_map_proof(tiles,[[1]*9 for _ in range(9)],16,9)
        return dict(walkable=tiles,observation_frame=self.game.frame_count,verified_location=[194,20,13],
            screen_cells_verified=len(visible),visible_verified_cells=visible,
            source='wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM')
    def prepare(self,cells=None,*,world=False,frames=40,same=False):
        if self.kw is not None and not same:self.game.frame_count+=frames;self.now+=frames/60
        self.game.cells=blank() if cells is None else deepcopy(cells);self.game.memory[0xFF40]=0x91 if world else 0xB1
        text=read_visible_text(self.game);assert text['read_valid']
        signal=self.m.read_observation(self.game,self.game.frame_count,sdk);assert signal['read_valid'],signal
        state=dict(frame=self.game.frame_count,phase='unclassified',location=deepcopy(self.m.LOCATION),progress=deepcopy(signal['progress']),
            battle_state=dict(raw=0,kind='none',active=False,observation_frame=self.game.frame_count))
        self.kw=dict(state=state,text=text,grid=self.world_grid() if world else None,signal=signal,
            previous=list(self.previous),owner=self.game,now=self.now)
        if self.before is None:self.before=deepcopy(state['progress'])
        return self
    def call(self,**kw):
        args=dict(self.kw);args.update(kw);before=deepcopy((args['state'],args['text'],args['grid'],args['signal'],dict(self.game.memory)))
        out=self.c.context(**args)
        assert before==(args['state'],args['text'],args['grid'],args['signal'],dict(self.game.memory))
        self.previous=[out['available_actions'][0]]
        assert not any(out.get(k) for k in ('victory_confirmed','champion_confirmed','hall_of_fame_complete'))
        return out
    def expect(self,cells,action,**kw):
        out=self.prepare(cells,**kw).call();assert out['available_actions']==[action,'wait'],out;return out
    def select(self,toss=False):
        self.expect(blank(),'start',world=True)
        self.expect(start(2),'down');self.expect(start(4),'down');self.expect(start(6),'a')
        for i in range(4):self.expect(bag(self.m,self.items,max(0,i-2),min(2,i)),'a' if i==3 else 'down')
        if toss:self.expect(use(self.m,self.items,1,2,13),'up')
        self.expect(use(self.m,self.items,1,2),'a')
        self.expect(party(self.mons,0),'a' if self.target==0 else 'down')
        if self.target:self.expect(party(self.mons,1),'a')
        return self
    def effect(self):
        target=self.mons[self.target];target['hp']=min(target['hp']+200,target['max_hp'])
        self.items[3]['quantity']-=1
        if self.items[3]['quantity']==0:self.items.pop(3)
    def receipt(self):return party(self.mons,receipt=(sdk.POKEMON_SPECIES_NAMES[self.intent['target_species']],self.mons[self.target]['hp']-self.before['party'][self.target]['hp']))
    def finish(self):
        self.effect();assert self.prepare(self.receipt()).call()['available_actions']==['wait']
        assert self.prepare(self.receipt(),frames=53).call()['available_actions']==['wait']
        self.expect(self.receipt(),'a',frames=1)
        self.expect(bag(self.m,self.items,1,2),'b');self.expect(start(),'b')
        assert self.prepare(world=True).call()['available_actions']==['wait']
        out=self.prepare(world=True).call();assert out['overworld_medicine_complete'] is True;return out


def review(out,reason=None):
    assert out['phase']=='campaign_review' and out['available_actions']==['wait'],out
    if reason:assert out['review_reason']=='overworld_hyper_'+reason,out


@pytest.mark.parametrize('species,quantity,maximum',[(19,8,None),(132,1,None),(19,2,320)])
def test_complete_normal_overworld_transaction_exact_target_once(m,species,quantity,maximum):
    s=Session(m,species,quantity,maximum).select(toss=True);out=s.finish()
    assert out['medicine_receipt']['hp_after']==min(out['medicine_receipt']['hp_before']+200,s.mons[s.target]['max_hp'])
    assert s.c.pending is None and s.c.receipt_ack and s.c.complete
    assert s.c.after==s.kw['state']['progress']


@pytest.mark.parametrize('field,value', [('hp',0),('status',8),('hp',True),('status',True)])
def test_fnt_status_unknown_never_bypassed(m,field,value):
    s=Session(m);s.mons[3][field]=value;s.prepare(world=True)
    review(s.call(),'resources_or_fnt_status_unverified')


def test_full_hp_and_missing_medicine_never_spent(m):
    s=Session(m);s.mons[0]['hp']=s.mons[0]['max_hp'];s.prepare(world=True);review(s.call(),'full_hp_no_waste')
    t=Session(m);t.items[:]=[x for x in t.items if x['item']!=18];t.prepare(world=True);review(t.call(),'hyper_potion_missing')


def test_fresh_actual_previous_ack_required_and_same_frame_no_repeat(m):
    s=Session(m);s.expect(blank(),'start',world=True);before=(s.c.calls,s.c.waits,s.c.started,s.c.last_now)
    assert s.call()['available_actions']==['wait'];assert before==(s.c.calls,s.c.waits,s.c.started,s.c.last_now)
    s.previous=['wait'];s.prepare(start(6));review(s.call(),'actual_pending_ack_required')
    s.kw['previous']=['start'];review(s.call(),'actual_pending_ack_required')


@pytest.mark.parametrize('mutate',[
    lambda s:s.mons.reverse(),lambda s:s.mons[2].update(level=50),lambda s:s.mons[1].update(hp=81),
    lambda s:s.mons[0]['moves'].__setitem__(0,39),lambda s:s.mons[0]['pp'].__setitem__(0,19),
    lambda s:s.mons[0].update(exp=80001),lambda s:s.items[0].update(quantity=5),
    lambda s:s.game.memory.__setitem__(sdk.PLAYER_MONEY_ADDRESS+2,1),
])
def test_unrelated_resource_changes_are_sticky(m,mutate):
    s=Session(m);s.expect(blank(),'start',world=True);mutate(s);s.prepare(start())
    review(s.call(),'premature_or_unrelated_resource_change')
    review(s.call(),'premature_or_unrelated_resource_change')


def test_effect_needs_exact_target_hp_and_item_minus_one(m):
    s=Session(m).select();s.effect();s.items[3]['quantity']+=1;s.prepare(s.receipt())
    review(s.call(),'unexpected_effect_or_resource_change')
    t=Session(m).select();t.effect();t.mons[1]['hp']+=1;t.prepare(t.receipt())
    review(t.call(),'unexpected_effect_or_resource_change')


def test_native_hp_animation_waits_never_acknowledges_partial_done(m):
    s=Session(m).select();s.effect()
    out=s.prepare(party(s.mons,s.target,'▷',shown_hp=75)).call()
    assert out['available_actions']==['wait'] and out['overworld_hyper_reason']=='native_hp_animation_no_input'
    assert s.c.receipt_ack is False


def test_done_has_no_arrow_and_requires_full_source_delay_then_real_a(m):
    s=Session(m).select();s.effect();out=s.prepare(s.receipt()).call();assert out['available_actions']==['wait']
    assert s.c.pending is None
    partial=s.receipt();partial[16][3]='X';s.prepare(partial);review(s.call(),'medicine_effect_page_unverified')
    t=Session(m).select();t.effect();t.prepare(t.receipt()).call();t.expect(t.receipt(),'a',frames=54)
    t.previous=['wait'];t.prepare(bag(m,t.items,1,2));review(t.call(),'actual_pending_ack_required')


def test_closed_world_requires_two_fresh_actual_readers(m):
    s=Session(m).select();s.effect();s.prepare(s.receipt()).call();s.expect(s.receipt(),'a',frames=54)
    s.expect(bag(m,s.items,1,2),'b');s.expect(start(),'b')
    assert not s.prepare(world=True).call().get('overworld_medicine_complete')
    assert not s.call().get('overworld_medicine_complete')
    assert s.prepare(world=True).call()['overworld_medicine_complete'] is True


def test_owner_step_intent_and_location_stay_bound(m):
    s=Session(m);s.prepare(world=True);review(s.call(owner=object()),'owner_intent_frame_clock_or_previous_unverified')
    t=Session(m);t.prepare(world=True);t.kw['state']['location']['x']=19;review(t.call(),'fixed_nonbattle_location_unverified')
    q=Session(m);q.prepare(world=True);q.c.intent['quantity']=2;review(q.call(),'owner_intent_frame_clock_or_previous_unverified')


def test_same_frame_packet_conflict_clock_timeout_and_reload_preserve(m):
    s=Session(m);s.expect(blank(),'start',world=True);c=s.c;pending=deepcopy(c.pending)
    m._spec.loader.exec_module(m);s.c.__class__=m.OverworldHyperController
    assert s.c is c and c.pending==pending and c.calls==1 and c.started==0
    s.kw['text']['cells'][0][0]='X';review(s.call(),'same_frame_packet_conflict')
    m._spec.loader.exec_module(m);s.c.__class__=m.OverworldHyperController;review(s.call(),'same_frame_packet_conflict')
    t=Session(m);t.expect(blank(),'start',world=True);t.prepare(start(),frames=3661);review(t.call(),'call_or_time_budget_exhausted')
    q=Session(m);q.expect(blank(),'start',world=True);q.prepare(start());review(q.call(now=10),'true_frame_clock_required')


def test_real_reader_double_read_sdk_anchors_movement_and_full_progress(m):
    s=Session(m);s.prepare(world=True);sig=s.kw['signal']
    assert sig['progress']['party_read_valid'] and sig['progress']['player_name_raw']=='KEVIN'
    assert sig['movement']['read_valid'] and sig['owner_id']==id(s.game)
    assert all(s.game.memory.reads.count(a)>=2 for a in m.ADDRESSES.values())
    s.game.memory.hook=lambda key,v: v+1 if key==0xD362 and s.game.memory.reads.count(key)%2 else v
    assert not m.read_observation(s.game,s.game.frame_count,sdk)['read_valid']
    assert not m.read_observation(s.game,s.game.frame_count+1,sdk)['read_valid']


def test_bridge_explicit_attrition_step_only_unknown_and_fnt_retained(m,bridge):
    s=Session(m);s.prepare(world=True)
    from laya_pokemon.campaign_safety import attrition_context
    attrition=attrition_context(s.kw['state'],s.plan,s.step['id']);assert attrition['review_reason']=='party_attrition_requires_center'
    result=bridge.pre_attrition_context(s.game,s.kw['state'],s.plan,s.step['id'],attrition,s.kw['text'],s.kw['grid'],[])
    assert result[0]['available_actions']==['start','wait']
    for bad in ({**attrition,'review_reason':'party_attrition_state_unverified'},
                {**attrition,'party_attrition':{'fainted_party_indices':[2]}}):
        assert bridge.pre_attrition_context(s.game,s.kw['state'],s.plan,s.step['id'],bad,s.kw['text'],s.kw['grid'],[]) is None
    before=bridge._CONTROLLERS[s.step['id']];record=bridge._BINDINGS[s.step['id']]
    bridge._spec.loader.exec_module(bridge)
    assert bridge._CONTROLLERS[s.step['id']] is before and bridge._BINDINGS[s.step['id']] is record
    changed=deepcopy(s.plan);changed['steps'][0]['overworld_hyper_intent']=deepcopy(m.INTENTS[1])
    out=bridge.context(s.game,s.kw['state'],changed,s.step['id'],s.kw['text'],s.kw['grid'],['start'])
    assert out[0]['available_actions']==['wait'] and 'owner_or_step_changed' in out[0]['review_reason']


def test_bridge_full_transaction_and_complete_once(m,bridge):
    s=Session(m,132)
    def call(**kw):
        assert not kw
        out,next_id=bridge.context(s.game,s.kw['state'],s.plan,s.step['id'],s.kw['text'],s.kw['grid'],s.kw['previous'])
        s.c=bridge._CONTROLLERS[s.step['id']];s.previous=[out['available_actions'][0]]
        if out.get('overworld_medicine_complete'):
            assert next_id=='next' and out['field_move_complete'] is True
            assert bridge._COMPLETED=={s.step['id']}
        else:assert next_id==s.step['id']
        return out
    s.call=call;s.select();s.finish()
    out,_=bridge.context(s.game,s.kw['state'],s.plan,s.step['id'],s.kw['text'],s.kw['grid'],['wait'])
    assert out['review_reason']=='overworld_hyper_bridge_completed_step_reentered'


@pytest.mark.parametrize('address,value,reason',[(0xD057,1,'fixed_nonbattle_location_unverified'),
    (0xD05A,1,'fixed_nonbattle_location_unverified'),(0xD356,127,'fixed_nonbattle_location_unverified'),
    (0xD700,1,'fixed_nonbattle_location_unverified'),(0xD730,1,'fixed_nonbattle_location_unverified'),
    (0xD63F,2,'fixed_nonbattle_location_unverified'),(0xCD38,1,'native_movement_not_idle'),
    (0xCD6B,255,'native_movement_not_idle'),(0xCFC5,1,'native_movement_not_idle'),
    (0xD736,128,'native_movement_not_idle')])
def test_true_raw_script_movement_unknown_prevent_menu_input(m,address,value,reason):
    s=Session(m);s.game.memory[address]=value;s.prepare(world=True);review(s.call(),reason)
    s.game.memory[address]=0;s.prepare(world=True);review(s.call(),reason)


def test_missing_after_hp_done_text_and_unknown_pollution_never_spends_extra(m):
    s=Session(m).select();old=deepcopy(s.mons)
    fake=party(old,receipt=('LAPRAS',151));s.prepare(fake)
    review(s.call(),'medicine_effect_page_unverified')
    t=Session(m).select();t.effect();polluted=t.receipt();polluted[0][19]='X';t.prepare(polluted)
    review(t.call(),'medicine_effect_page_unverified')


def test_pending_a_known_source_old_page_waits_no_repeat(m):
    s=Session(m).select();before=s.items[3]['quantity']
    out=s.prepare(party(s.mons,s.target)).call()
    assert out['available_actions']==['wait'] and s.items[3]['quantity']==before and s.c.pending is None


def test_world_grid_unknown_cannot_open_menu(m):
    s=Session(m);s.prepare(world=True);s.kw['grid']['verified_location']=[194,20,12]
    review(s.call(),'initial_closed_world_required')


def test_bridge_foreign_owner_and_unknown_review_do_not_rebuild(m,bridge):
    s=Session(m);s.prepare(world=True)
    bridge.context(s.game,s.kw['state'],s.plan,s.step['id'],s.kw['text'],s.kw['grid'],[])
    original=bridge._CONTROLLERS[s.step['id']]
    out,_=bridge.context(object(),s.kw['state'],s.plan,s.step['id'],s.kw['text'],s.kw['grid'],['start'])
    assert out['available_actions']==['wait'] and bridge._CONTROLLERS[s.step['id']] is original
    assert original.calls==1 and original.pending['action']=='start'


def test_wait_and_call_budgets_are_sticky_and_not_reset_on_reload(m):
    s=Session(m);s.expect(blank(),'start',world=True)
    s.prepare(start(6,'▷'));s.c.waits=m.MAX_WAITS
    review(s.call(),'wait_budget_exhausted')
    m._spec.loader.exec_module(m);s.c.__class__=m.OverworldHyperController
    assert s.c.waits==m.MAX_WAITS+1 and s.c.started==0
    review(s.call(),'wait_budget_exhausted')
    t=Session(m);t.expect(blank(),'start',world=True);t.prepare(start(6));t.c.calls=m.MAX_CALLS
    review(t.call(),'call_or_time_budget_exhausted');assert t.c.calls==m.MAX_CALLS+1


def test_wrong_observation_owner_packet_and_ui_cursor_stop(m):
    s=Session(m);s.prepare(world=True);s.kw['signal']['owner_id']=0
    review(s.call(),'same_frame_reader_unverified')
    t=Session(m);t.expect(blank(),'start',world=True);t.expect(start(2),'down')
    t.prepare(start(6));review(t.call(),'cursor_did_not_follow_actual_offer')
    q=Session(m);q.prepare(world=True);q.kw['signal']['progress']['money']+=1
    review(q.call(),'fixed_nonbattle_location_unverified')


def test_bridge_complete_job_is_deepcopied_immutable_and_counters_never_rebuilt(m,bridge):
    s=Session(m);s.prepare(world=True)
    bridge.context(s.game,s.kw['state'],s.plan,s.step['id'],s.kw['text'],s.kw['grid'],[])
    c=bridge._CONTROLLERS[s.step['id']];record=bridge._BINDINGS[s.step['id']];original=deepcopy(record)
    assert record['training_job'] is not s.plan['training_job']
    s.plan['training_job']['location'][0]=108
    out,_=bridge.context(s.game,s.kw['state'],s.plan,s.step['id'],s.kw['text'],s.kw['grid'],['start'])
    assert out['review_reason']=='overworld_hyper_bridge_bound_training_job_changed'
    assert record['training_job']==original['training_job'] and c.calls==1 and c.pending['action']=='start'
    s.plan['training_job']=original['training_job'];bridge._spec.loader.exec_module(bridge)
    out,_=bridge.context(s.game,s.kw['state'],s.plan,s.step['id'],s.kw['text'],s.kw['grid'],['start'])
    assert out['review_reason']=='overworld_hyper_bridge_bound_training_job_changed' and bridge._CONTROLLERS[s.step['id']] is c


@pytest.mark.parametrize('job',[None,'',{},[],float('nan'),{1:'non-string-key'}])
def test_bridge_requires_nonempty_canonical_job_before_creating_owner(m,bridge,job):
    s=Session(m);s.prepare(world=True);s.plan['training_job']=job
    out,_=bridge.context(s.game,s.kw['state'],s.plan,s.step['id'],s.kw['text'],s.kw['grid'],[])
    assert out['review_reason']=='overworld_hyper_bridge_explicit_canonical_training_job_required'
    assert bridge._CONTROLLERS=={} and bridge._BINDINGS=={}


@pytest.mark.parametrize('field,value',[('_BINDINGS',None),('_OWNERS',[]),('_CONTROLLERS',None),('_COMPLETED',{}),('_BINDINGS',{'unknown':[]})])
def test_registry_unknown_is_sticky_none_active_applies_true_and_no_raise(m,bridge,field,value):
    s=Session(m);s.prepare(world=True);setattr(bridge,field,value)
    assert bridge._active() is None and bridge.applies('unknown',None) is True
    out,_=bridge.context(s.game,s.kw['state'],s.plan,s.step['id'],s.kw['text'],s.kw['grid'],[])
    assert out['review_reason']=='overworld_hyper_bridge_registry_shape_unverified'
    setattr(bridge,field,set() if field=='_COMPLETED' else {})
    bridge._spec.loader.exec_module(bridge)
    assert bridge._active() is None and bridge.applies('unknown',None) is True


def test_bridge_future_source_reload_retains_same_controller_pending_budget(m,bridge):
    s=Session(m);s.prepare(world=True)
    bridge.context(s.game,s.kw['state'],s.plan,s.step['id'],s.kw['text'],s.kw['grid'],[])
    c=bridge._CONTROLLERS[s.step['id']];pending=deepcopy(c.pending);old_class=c.__class__
    bridge._spec.loader.exec_module(bridge)
    s.previous=['start'];s.prepare(start(6))
    out,_=bridge.context(s.game,s.kw['state'],s.plan,s.step['id'],s.kw['text'],s.kw['grid'],s.previous)
    assert bridge._CONTROLLERS[s.step['id']] is c and c.started==0 and c.calls==2
    assert c.__class__ is bridge.medicine.OverworldHyperController and c.__class__ is not old_class
    assert pending['action']=='start' and out['available_actions']==['a','wait']
