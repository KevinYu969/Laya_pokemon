"""Bounded pure Hyper extension: real SDK/readers, synthetic memory, no ROM or input.

Production modules use canonical imports from the formal src directory.
Only bridge registries receive a private, exact-formal-source module instance.
"""
from copy import deepcopy
from hashlib import sha256
import importlib
import importlib.util
import json
from pathlib import Path
import re
import sys

import pytest
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk

m=importlib.import_module('laya_pokemon.overworld_hyper')
SOURCE=Path(m.__file__).resolve().parent
assert SOURCE.name=='laya_pokemon' and SOURCE.parent.name=='src'
ROOT=SOURCE.parent.parent
assert Path(m.__file__).resolve()==(ROOT/'src/laya_pokemon/overworld_hyper.py').resolve()


def unique_load(name,path):
    assert name.startswith('laya_pokemon._owned_hyper_')
    assert path.resolve()==(SOURCE/'overworld_hyper_bridge.py').resolve()
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert Path(module.__file__).resolve()==path.resolve()
    return module


helper=importlib.import_module('test_overworld_hyper')
assert Path(helper.__file__).resolve()==(ROOT/'tests/test_overworld_hyper.py').resolve()


def intent(map_id=198,species=7,location=None):
    if location is None:location=[18,1] if map_id==198 else [10,12]
    return dict(kind=m.OWNED_KIND,map_id=map_id,target=location,item=18,quantity=1,target_species=species,
        owner_step_id='league28-victory3f-switch1' if map_id==198 else 'synthetic-2f-switch1',
        case_key='3f_switch1' if map_id==198 else '2f_switch1',capsule_sha256='a'*64)


def authority(value):
    return dict(owner_step_id=value['owner_step_id'],case_key=value['case_key'],
        capsule_sha256=value['capsule_sha256'],location=m._location(value))


class OwnedSession(helper.Session):
    def __init__(self,species=7,map_id=198):
        super().__init__(m)
        self.intent=intent(map_id,species);self.location=m._location(self.intent)
        self.auth=authority(self.intent)
        self.target=next(i for i,p in enumerate(self.mons) if p['species']==species)
        self.mons[self.target]['hp']=50
        self.c=m.OverworldHyperController(self.intent,owner=self.game,owned_authority=self.auth)
        self.game.memory.update({0xD35E:map_id,0xD362:self.location['x'],0xD361:self.location['y']})

    def world_grid(self):
        x,y=self.location['x'],self.location['y']
        cells=[[xx,y] for xx in range(12)]
        if [x,y] not in cells:cells.append([x,y])
        return dict(walkable=[[1]*30 for _ in range(18)],observation_frame=self.game.frame_count,
            verified_location=[self.location['map_id'],x,y],screen_cells_verified=len(cells),
            visible_verified_cells=cells,
            source='wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM')

    def prepare(self,cells=None,*,world=False,frames=40,same=False):
        if self.kw is not None and not same:self.game.frame_count+=frames;self.now+=frames/60
        self.game.cells=helper.blank() if cells is None else deepcopy(cells)
        self.game.memory[0xFF40]=0x91 if world else 0xB1
        text=helper.read_visible_text(self.game);assert text['read_valid']
        signal=m.read_observation(self.game,self.game.frame_count,sdk,map_id=self.location['map_id'])
        assert signal['read_valid'],signal
        state=dict(frame=self.game.frame_count,phase='unclassified',location=deepcopy(self.location),
            progress=deepcopy(signal['progress']),
            battle_state=dict(raw=0,kind='none',active=False,observation_frame=self.game.frame_count))
        self.kw=dict(state=state,text=text,grid=self.world_grid() if world else None,signal=signal,
            previous=list(self.previous),owner=self.game,now=self.now)
        if self.before is None:self.before=deepcopy(state['progress'])
        return self

    def select(self,toss=False):
        self.expect(helper.blank(),'start',world=True)
        self.expect(helper.start(6),'a')
        for i in range(4):
            self.expect(helper.bag(m,self.items,max(0,i-2),min(2,i)),'a' if i==3 else 'down')
        if toss:self.expect(helper.use(m,self.items,1,2,13),'up')
        self.expect(helper.use(m,self.items,1,2),'a')
        for i in range(self.target+1):
            self.expect(helper.party(self.mons,i),'a' if i==self.target else 'down')
        return self


@pytest.mark.parametrize('species',sorted(m.ui.ROSTER))
@pytest.mark.parametrize('map_id',[194,198])
def test_owned_roster_exactly_one_hyper_real_ui_closes(species,map_id):
    s=OwnedSession(species,map_id).select(toss=True)
    out=s.finish()
    assert out['overworld_medicine_complete'] is True
    assert out['medicine_receipt']['target_species']==species
    assert out['medicine_receipt']['hp_before']==50
    assert out['medicine_receipt']['hp_after']==s.before['party'][s.target]['max_hp']
    assert s.c.receipt_ack and s.c.pending is None and s.c.closed_frame<s.game.frame_count
    expected=deepcopy(s.before);expected['party'][s.target]['hp']=s.mons[s.target]['max_hp']
    expected['inventory'][3]['quantity']-=1
    assert s.kw['state']['progress']==expected
    assert s.c.owned_authority==s.auth and s.c.owned_authority is not s.auth


@pytest.mark.parametrize('key,value',[
    ('kind','arbitrary_hyper'),('map_id',108),('map_id',True),('target',[30,1]),('target',[18,18]),
    ('target',[False,1]),('target',[18]),('item',19),('quantity',2),('quantity',True),
    ('target_species',25),('target_species',True),('owner_step_id',''),('owner_step_id','../other'),
    ('case_key','2f_switch1'),('case_key','unknown'),('capsule_sha256','a'*63),('capsule_sha256','A'*64),
])
def test_owned_intent_is_exact_bounded_contract(key,value):
    v=intent();v[key]=value
    assert not m._intent(v)
    with pytest.raises(ValueError):m.OverworldHyperController(v,owner=object(),owned_authority={})


def test_owned_authority_required_exact_and_immutable():
    v=intent();o=object();a=authority(v)
    for bad in (None,{},dict(a,extra=True),dict(a,owner_step_id='foreign'),dict(a,location=dict(map_id=198,x=17,y=1))):
        with pytest.raises(ValueError):m.OverworldHyperController(v,owner=o,owned_authority=bad)
    with pytest.raises(ValueError):m.OverworldHyperController(dict(v,extra=True),owner=o,owned_authority=a)
    with pytest.raises(ValueError):m.OverworldHyperController(m.INTENTS[0],owner=o,owned_authority=a)
    s=OwnedSession();s.c.owned_authority['capsule_sha256']='b'*64;s.prepare(world=True)
    helper.review(s.call(),'owner_intent_frame_clock_or_previous_unverified')


def test_getter_reads_only_selected_source_script_and_rejects_unknown_map_before_memory():
    s=OwnedSession();g=s.game;g.memory.reads.clear()
    signal=m.read_observation(g,g.frame_count,sdk,map_id=198)
    assert signal['read_valid'] and signal['source_map_id']==198 and signal['script_address']==0xD640
    assert g.memory.reads.count(0xD640)==2 and 0xD63F not in g.memory.reads
    g.memory.reads.clear()
    for bad in (108,True,'198',None):
        assert not m.read_observation(g,g.frame_count,sdk,map_id=bad)['read_valid']
    assert not g.memory.reads
    g.memory.reads.clear();g.memory[0xD640]=9
    s.prepare(world=True);helper.review(s.call(),'fixed_nonbattle_location_unverified')


@pytest.mark.parametrize('field,value',[('source_map_id',194),('script_address',0xD63F),('script_address',True)])
def test_owned_reader_script_mapping_is_bound_to_case(field,value):
    s=OwnedSession();s.prepare(world=True);s.kw['signal'][field]=value
    helper.review(s.call(),'owned_script_reader_unverified')


def test_bound_world_rejects_different_position_without_input():
    s=OwnedSession();s.prepare(world=True);s.kw['grid']['verified_location']=[198,17,1]
    helper.review(s.call(),'initial_closed_world_required')
    assert s.c.pending is None
    q=OwnedSession();q.prepare(world=True);q.kw['state']['location']['x']=17
    helper.review(q.call(),'fixed_nonbattle_location_unverified')


@pytest.mark.parametrize('field,value',[('hp',0),('status',8),('hp',True),('status',True)])
def test_owned_fnt_status_unknown_stops_before_start(field,value):
    s=OwnedSession();s.mons[3][field]=value;s.prepare(world=True)
    helper.review(s.call(),'resources_or_fnt_status_unverified')
    assert s.c.pending is None


def test_closed_world_uses_exact_dynamic_bound_location():
    s=OwnedSession();s.prepare(world=True);kw=s.kw
    assert m._closed_world(kw['text'],kw['grid'],s.game.frame_count,s.location)
    assert not m._closed_world(kw['text'],kw['grid'],s.game.frame_count)
    assert not m._closed_world(kw['text'],kw['grid'],s.game.frame_count,dict(map_id=108,x=18,y=1))


@pytest.mark.parametrize('species,quantity,maximum',[(19,8,None),(132,1,None),(19,2,320)])
def test_existing_fixed_2f_normal_transaction_regression(species,quantity,maximum):
    helper.test_complete_normal_overworld_transaction_exact_target_once(m,species,quantity,maximum)


@pytest.mark.parametrize('name',[
    'test_full_hp_and_missing_medicine_never_spent',
    'test_fresh_actual_previous_ack_required_and_same_frame_no_repeat',
    'test_same_frame_packet_conflict_clock_timeout_and_reload_preserve',
    'test_real_reader_double_read_sdk_anchors_movement_and_full_progress',
    'test_missing_after_hp_done_text_and_unknown_pollution_never_spends_extra',
    'test_pending_a_known_source_old_page_waits_no_repeat',
    'test_world_grid_unknown_cannot_open_menu',
    'test_wrong_observation_owner_packet_and_ui_cursor_stop',
])
def test_existing_fixed_2f_pure_negative_regressions(name):
    m._spec=m.__spec__
    getattr(helper,name)(m)


def test_canonical_hyper_module_not_rebound():
    canonical=sys.modules.get('laya_pokemon.overworld_hyper')
    if canonical is not None:
        assert Path(canonical.__file__).resolve()==(ROOT/'src/laya_pokemon/overworld_hyper.py').resolve()
    assert m is importlib.import_module('laya_pokemon.overworld_hyper')
    assert m is sys.modules['laya_pokemon.overworld_hyper']


def test_source_script_mapping_derives_from_frozen_wram():
    fixture=json.loads((ROOT/'tests/data/player-battle-source-fixture.json').read_text(encoding='utf-8'))
    text=fixture['files']['ram/wram.asm']['text']
    assert fixture['commit']==m.SOURCE_COMMIT
    assert sha256(text.encode('utf-8')).hexdigest()=='00683cd430a9ef30794d2aeaee51f3a5440e4bb14dca13e9f9cb5fa88f130e34'
    address=0xD60A;found={}
    for line in text[text.index('wRoute22CurScript::'):].splitlines():
        for label,map_id in (('wVictoryRoad2FCurScript::',194),('wVictoryRoad3FCurScript::',198)):
            if line.startswith(label):found[map_id]=address
        if len(found)==2:break
        code=line.split(';')[0].strip()
        if re.search(r'\bdb$',code):address+=1
        elif re.fullmatch(r'ds [0-9]+',code):address+=int(code.split()[1])
    assert found==m.SCRIPT_ADDRESSES=={194:0xD63F,198:0xD640}


def fresh_bridge():
    # Separate registries, exact formal bridge source and canonical dependency.
    b=unique_load('laya_pokemon._owned_hyper_bridge_formal_test',SOURCE/'overworld_hyper_bridge.py')
    assert b.medicine is importlib.import_module('laya_pokemon.overworld_hyper')
    b._spec=b.__spec__
    return b


def child_plan(s):
    child=dict(id='medicine-child-1',kind='interact',map_id=s.intent['map_id'],target=s.intent['target'],
        mechanic='overworld_hyper',overworld_hyper_intent=s.intent)
    return dict(mode='league_campaign',training_job={'id':'same-original-job'},steps=[child,dict(id='next')])


def test_bridge_owned_dependency_smoke_and_full_closed_transaction():
    b=fresh_bridge();s=OwnedSession();plan=child_plan(s)
    def call(**kw):
        assert not kw
        out,next_id=b.context(s.game,s.kw['state'],plan,'medicine-child-1',s.kw['text'],s.kw['grid'],
            s.kw['previous'],owned_authority=s.auth,now=s.now)
        assert next_id==('next' if out.get('overworld_medicine_complete') else 'medicine-child-1')
        s.c=b._CONTROLLERS['medicine-child-1'];s.previous=[out['available_actions'][0]]
        return out
    s.call=call;s.select();result=s.finish()
    assert result['field_move_complete'] and result['field_move_kind']=='overworld-hyper'
    assert b._COMPLETED=={'medicine-child-1'} and b._OWNERS['medicine-child-1'] is s.game


def test_bridge_owned_authority_required_before_native_getter():
    b=fresh_bridge();s=OwnedSession();plan=child_plan(s);s.prepare(world=True);s.game.memory.reads.clear()
    out,next_id=b.context(s.game,s.kw['state'],plan,'medicine-child-1',s.kw['text'],s.kw['grid'],[])
    assert out['review_reason']=='overworld_hyper_bridge_owned_authority_required'
    assert next_id=='medicine-child-1' and not b._CONTROLLERS and not s.game.memory.reads


def test_bridge_preserves_owned_authority_native_identity_and_clock():
    b=fresh_bridge();s=OwnedSession();plan=child_plan(s);s.prepare(world=True)
    args=(s.game,s.kw['state'],plan,'medicine-child-1',s.kw['text'],s.kw['grid'],[])
    out,_=b.context(*args,owned_authority=s.auth,now=34.)
    assert out['available_actions']==['start','wait']
    c=b._CONTROLLERS['medicine-child-1'];assert c.started==c.last_now==34.
    b.__spec__.loader.exec_module(b)
    assert b._CONTROLLERS['medicine-child-1'] is c and c.pending['action']=='start'
    s.previous=['start'];s.prepare(helper.start(6))
    out,_=b.context(s.game,s.kw['state'],plan,'medicine-child-1',s.kw['text'],s.kw['grid'],['start'],
        owned_authority=s.auth)
    assert out['available_actions']==['a','wait']
    assert c.started==34. and c.last_now==34.+40/60 and c.calls==2
    out,_=b.context(object(),s.kw['state'],plan,'medicine-child-1',s.kw['text'],s.kw['grid'],['start'],
        owned_authority=s.auth)
    assert out['review_reason']=='overworld_hyper_bridge_original_controller_owner_or_step_changed'
    assert b._CONTROLLERS['medicine-child-1'] is c and c.calls==2


@pytest.mark.parametrize('name',[
    'test_bridge_explicit_attrition_step_only_unknown_and_fnt_retained',
    'test_bridge_full_transaction_and_complete_once',
    'test_bridge_foreign_owner_and_unknown_review_do_not_rebuild',
    'test_bridge_complete_job_is_deepcopied_immutable_and_counters_never_rebuilt',
])
def test_existing_fixed_2f_bridge_regressions(name):
    b=fresh_bridge()
    # Borrowed reload regression executes the actual formal bridge loader.
    getattr(helper,name)(m,b)
