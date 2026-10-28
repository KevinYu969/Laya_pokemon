"""Real SDK/getters/pure bridge over synthetic source RAM; no emulator/input."""
from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent

def load(name,path):
    spec=importlib.util.spec_from_file_location('laya_pokemon._hole_layout_'+name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

bridge=load('bridge',ROOT/'src/laya_pokemon/victory_later_boulders_bridge.py')
reviewer=importlib.import_module('laya_pokemon.reviewed_hole_layout')
assert Path(reviewer.__file__).resolve()==ROOT/'src/laya_pokemon/reviewed_hole_layout.py'
shared=load('shared',ROOT/'src/laya_pokemon/owned_field_medicine.py')
recovery=importlib.import_module('laya_pokemon.league_recovery')
bh=importlib.import_module('test_victory_later_boulders')
hh=importlib.import_module('test_overworld_hyper')
from laya_pokemon.progress import read_progress

@pytest.fixture(autouse=True)
def clear(monkeypatch):
    for name,value in (('_CONTROLLERS',{}),('_BINDINGS',{}),('_COMPLETED',set())):monkeypatch.setattr(bridge,name,value)
    for name,value in (('_SESSIONS',{}),('_ERRORS',{}),('_REGISTRY_ERROR',None)):monkeypatch.setattr(shared,name,value)

def plan():
    steps=recovery.expected_steps()
    return dict(mode='league_campaign',training_job=recovery.JOB,lead_species=35,steps=steps,
        reviewed_fnt_recovery=dict(kind=recovery.KIND,source_frame=32809,source_location=dict(map_id=198,x=6,y=1),
            fainted_species=7,steps_sha256=recovery.digest(steps),review_sha256=recovery.SOURCE_REVIEW_SHA256,
            state_sha256=recovery.SOURCE_STATE_SHA256))

class Session:
    def __init__(self):
        self.game=hh.Game();self.game.frame_count=7233
        self.game.memory.update(bh.Memory('3f_hole').values)
        p=bh.progress()
        for mon in p['party']:mon.update(hp=mon['max_hp'],status=0)
        next(mon for mon in p['party'] if mon['species']==7).update(level=37,hp=0,max_hp=125)
        next(mon for mon in p['party'] if mon['species']==35).update(level=38,hp=117,max_hp=117)
        p['party'].sort(key=lambda mon:[35,7,132,102,154,19].index(mon['species']))
        self.game.game_wrapper=SimpleNamespace(party=p['party'],inventory=p['inventory'],money=p['money'])
        self.game.memory.update({0xD356:255,sdk.PARTY_COUNT_ADDRESS:6,
            sdk.PLAYER_MONEY_ADDRESS:0x05,sdk.PLAYER_MONEY_ADDRESS+1:0x43,sdk.PLAYER_MONEY_ADDRESS+2:0x21})
        enc={v:k for k,v in sdk.POKEMON_TEXT_DECODING.items() if type(k) is int and 0<=k<=255}
        for i,ch in enumerate('KEVIN'):self.game.memory[sdk.PLAYER_NAME_ADDRESS+i]=enc[ch]
        self.game.memory[sdk.PLAYER_NAME_ADDRESS+5]=0x50
        self.game.memory[0xC200+16*8+4]=17  # synthetic source slot8 y=13+4.
        self.plan=plan();self.sid=self.plan['steps'][1]['id'];self.previous=['down'];self.kw=None
        self.prepare(same=True)
        out,_=bridge.context(self.game,self.kw['state'],self.plan,self.sid,self.kw['text'],self.kw['grid'],self.previous,
            reviewed_fainted_bench=(7,),now=1.)
        assert out['review_reason']==reviewer.ERROR
        self.c=bridge._CONTROLLERS[self.sid]
        # Represent an actual warm owner constructed before the additive profile.
        del self.c.source_layout;del self.c.source_layout_contract
        self.original_binding=bridge._BINDINGS[self.sid];self.original_packet=self.c.last_packet
        self.original_plan=deepcopy(self.plan);self.original=deepcopy({k:getattr(self.c,k) for k in reviewer._PRESERVED})
        self.cap=dict(kind=reviewer.KIND,game_id='game29',source_frame=7233,source_location=deepcopy(reviewer.LOCATION),
            original_step_id=self.sid,original_step_sha256=shared.canonical_sha256(self.plan['steps'][1]),
            training_job_sha256=shared.canonical_sha256(self.plan['training_job']),steps_sha256=shared.canonical_sha256(self.plan['steps']),
            recovery_capsule_sha256=shared.canonical_sha256(self.plan['reviewed_fnt_recovery']),
            source_progress_sha256=shared.canonical_sha256(self.kw['state']['progress']),source_layout=reviewer.LAYOUT,
            evidence=deepcopy(reviewer.EVIDENCE))
    def prepare(self,*,frames=40,same=False):
        if not same:self.game.frame_count+=frames
        self.game.cells=hh.blank();self.game.memory[0xFF40]=0x91
        f=self.game.frame_count
        text=hh.read_visible_text(self.game);assert text['read_valid']
        loc=dict(map_id=self.game.memory[0xD35E],x=self.game.memory[0xD362],y=self.game.memory[0xD361])
        state=dict(frame=f,phase='unclassified',location=loc,progress=read_progress(self.game,sdk),
            battle_state=dict(raw=0,kind='none',active=False,observation_frame=f))
        grid=bh.grid('3f_hole',f,(loc['x'],loc['y']),self.game.memory)
        self.kw=dict(state=state,text=text,grid=grid)
        return self
    def peers(self):
        p={k:set() for k in shared.PEER_NAMES};p['victory_later_boulder']=bridge._active();return p
    def call(self,**kwargs):
        params=dict(bridge=bridge,shared=shared,recovery=recovery,native_owner=self.game,game_id='game29',
            review_capsule=self.cap,source_evidence=deepcopy(reviewer.EVIDENCE),peer_owners=self.peers())
        params.update(kwargs)
        before=deepcopy((dict(self.game.memory),self.kw,self.plan))
        result=reviewer.context(self.game,self.kw['state'],self.plan,self.sid,self.kw['text'],self.kw['grid'],self.previous,**params)
        assert before==(dict(self.game.memory),self.kw,self.plan)
        return result
    def original_context(self):
        return bridge.context(self.game,self.kw['state'],self.plan,self.sid,self.kw['text'],self.kw['grid'],self.previous,
            reviewed_fainted_bench=(7,),source_layout=reviewer.LAYOUT,now=shared.frame_clock(self.c,self.game.frame_count))

def check_review(result):
    assert result[0]['phase']=='campaign_review' and result[0]['available_actions']==['wait'],result

def test_named_warm_error_review_wait_preserves_owner_clock_packet_then_true_hole_receipt():
    s=Session();c=s.c
    out,nxt=s.call();assert out['available_actions']==['wait'] and nxt==s.sid
    assert c.error is None and c.source_layout==reviewer.LAYOUT
    assert c is bridge._CONTROLLERS[s.sid] and bridge._BINDINGS[s.sid] is s.original_binding and c.last_packet is s.original_packet
    assert s.original=={k:getattr(c,k) for k in reviewer._PRESERVED}
    assert c.baseline is None and c.pending is None and c.push_index==0
    assert c.source_layout_review_history[0]['old_error']==reviewer.ERROR
    assert s.call()[0]['available_actions']==['wait'] and c.calls==s.original['calls']
    s.previous=['wait'];s.prepare();assert s.call() is None
    out,nxt=s.original_context();assert out['available_actions']==['right','wait'] and nxt==s.sid
    assert c.pending['executed'] is False and c.baseline==bridge.boulder._resources(s.kw['state']['progress'])
    assert c.calls==s.original['calls']+1 and c.started==s.original['started']
    assert c.last_now==s.original['last_now']+40/60
    assert next(o for o in c.object_baseline if o[0]==8)[1:3]==(13,13)
    # Only an actual RIGHT receipt moves the own stone and sets its native goal.
    s.previous=['right'];s.game.memory[0xC200+16*10+5]=27
    s.game.memory[0xD813]|=64;s.game.memory[0xD5B2]&=0xFE;s.game.memory[0xD5B5]|=4
    s.game.memory[0xD718]=10
    s.prepare();assert s.call() is None;out,nxt=s.original_context();assert out['available_actions']==['wait']
    s.previous=['wait'];s.prepare();assert s.call() is None;out,nxt=s.original_context();assert out['available_actions']==['wait']
    s.prepare();assert s.call() is None;out,nxt=s.original_context()
    assert out['field_move_kind']=='victory-later-boulder' and out['later_boulder_complete'] is True
    assert nxt==s.plan['steps'][2]['id'] and s.plan==s.original_plan
    assert s.game.memory[0xC200+16*8+4]==17 and c.push_index==1

@pytest.mark.parametrize('bad',['native','peer','unknown_peer','evidence','capsule','job','steps','recovery','unknown_error',
    'pending','baseline','push_index','slot8','slot9','gate','event','strength','progress','status','extra_fnt'])
def test_unknown_or_changed_review_never_clears_original_error(bad,monkeypatch):
    s=Session();params={}
    if bad=='native':params['native_owner']=object()
    if bad=='peer':p=s.peers();p['legacy_field']={'foreign'};params['peer_owners']=p
    if bad=='unknown_peer':p=s.peers();p['native_wait']=None;params['peer_owners']=p
    if bad=='evidence':params['source_evidence']=dict(reviewer.EVIDENCE,state_sha256='a'*64)
    if bad=='capsule':s.cap['source_layout']='arbitrary'
    if bad=='job':s.plan['training_job']='changed'
    if bad=='steps':s.plan['steps'][1]['target'][0]+=1
    if bad=='recovery':s.plan['reviewed_fnt_recovery']['fainted_species']=35
    if bad=='unknown_error':s.c.error='foreign_error'
    if bad=='pending':s.c.pending={'action':'right'}
    if bad=='baseline':s.c.baseline={}
    if bad=='push_index':s.c.push_index=1
    if bad=='slot8':s.game.memory[0xC200+16*8+4]+=1
    if bad=='slot9':s.game.memory[0xC200+16*9+5]+=1
    if bad=='gate':s.game.memory[0xC796]=0x25
    if bad=='event':s.game.memory[0xD813]|=64
    if bad=='strength':s.game.memory[0xD728]&=0xFE
    if bad=='progress':s.game.game_wrapper.party[0]['exp']+=1
    if bad=='status':s.game.game_wrapper.party[0]['status']=8
    if bad=='extra_fnt':s.game.game_wrapper.party[2]['hp']=0
    s.prepare(same=True);old_error=s.c.error;old_calls=s.c.calls;packet=s.c.last_packet
    check_review(s.call(**params));assert s.c.error==old_error and s.c.calls==old_calls and s.c.last_packet is packet
    check_review(s.call());assert s.c.error==old_error

def test_actual_fresh_wait_is_required_and_no_budget_is_refunded():
    s=Session();s.call();s.prepare();s.previous=['right']
    check_review(s.call());assert s.c.pending is None and s.c.baseline is None
    assert s.c.calls==s.original['calls'] and s.c.started==s.original['started']

@pytest.mark.parametrize('bad',['profile','contract','history','controller','binding'])
def test_review_cannot_be_rebound_after_arming(bad):
    s=Session();s.call()
    if bad=='profile':s.c.source_layout='source'
    if bad=='contract':s.c.source_layout_contract='source'
    if bad=='history':s.c.source_layout_review_history[0]['old_error']='changed'
    if bad=='controller':bridge._CONTROLLERS[s.sid]=bridge.boulder.VictoryLaterBoulderController('3f_hole',reviewed_fainted_bench=(7,))
    if bad=='binding':bridge._BINDINGS[s.sid]=tuple(list(bridge._BINDINGS[s.sid]))
    s.previous=['wait'];s.prepare();check_review(s.call())

@pytest.mark.parametrize('key',['2f_switch1','3f_switch1','2f_switch2'])
def test_layout_profile_is_not_available_to_other_cases(key):
    with pytest.raises(ValueError):bridge.boulder.VictoryLaterBoulderController(key,source_layout=reviewer.LAYOUT)

def test_default_source_profile_still_rejects_the_displaced_auxiliary_stone():
    s=Session();assert s.c.error==reviewer.ERROR
    out,_=bridge.context(s.game,s.kw['state'],s.plan,s.sid,s.kw['text'],s.kw['grid'],[],reviewed_fainted_bench=(7,),now=1.)
    assert out['review_reason']==reviewer.ERROR and s.c.baseline is None

@pytest.mark.parametrize('key',bh.ORDER)
def test_all_original_default_case_traces_still_close_using_candidate_pure(key,monkeypatch):
    monkeypatch.setattr(bh,'b',bridge.boulder)
    s=bh.Session(key);out=s.finish()
    assert out['later_boulder_complete'] is True and s.trace==s.case['coordinate_trace']

def test_source_case_whitelist_and_true_goal_contract_are_unchanged():
    assert bridge.boulder.CASES==bh.b.CASES
    assert bridge.boulder.CASES['3f_hole']['source_stones'][8]==(13,12)
    assert bridge.boulder.initial_source_stones('3f_hole',reviewer.LAYOUT)[8]==(13,13)
    assert bridge.boulder.CASES['3f_hole']['goal_stone']==[23,15]
    assert bridge.boulder.CASES['2f_switch2']['source_stones'][11]==(4,14)

@pytest.mark.parametrize('bad',['unknown_campaign_review','strategy_review','raw_review_reason','battle_raw','battle_kind','battle_frame'])
def test_other_review_or_inconsistent_nonbattle_packet_never_clears_named_error(bad):
    s=Session();state=s.kw['state']
    if bad=='unknown_campaign_review':state.update(phase='campaign_review',review_reason='unknown_separate_error')
    if bad=='strategy_review':state.update(phase='strategy_review',review_reason=reviewer.ERROR)
    if bad=='raw_review_reason':state['review_reason']='unknown_separate_error'
    if bad=='battle_raw':state['battle_state']['raw']=1
    if bad=='battle_kind':state['battle_state']['kind']='wild'
    if bad=='battle_frame':state['battle_state']['observation_frame']-=1
    check_review(s.call());assert s.c.error==reviewer.ERROR and s.c.pending is None

def test_only_the_exact_named_campaign_review_can_be_explicitly_reviewed():
    s=Session();s.kw['state'].update(phase='campaign_review',review_reason=reviewer.ERROR)
    out,_=s.call();assert out['available_actions']==['wait'] and s.c.error is None

def test_shallow_clone_of_the_entire_reviewed_owner_cannot_continue():
    s=Session();s.call();clone=object.__new__(s.c.__class__);clone.__dict__.update(s.c.__dict__)
    bridge._CONTROLLERS[s.sid]=clone;s.previous=['wait'];s.prepare()
    check_review(s.call());assert clone.source_layout_review_record['original_controller'] is s.c
    assert clone.source_layout_review_record['released'] is False

def test_review_survives_bridge_reload_with_same_owner_and_binding():
    s=Session();s.call();owner=s.c;binding=s.original_binding
    bridge.__spec__.loader.exec_module(bridge)
    s.previous=['wait'];s.prepare();assert s.call() is None
    out,_=s.original_context();assert out['available_actions']==['right','wait']
    assert bridge._CONTROLLERS[s.sid] is owner and bridge._BINDINGS[s.sid] is binding

def test_released_review_does_not_block_the_original_legal_wild_handoff():
    s=Session();s.call();s.previous=['wait'];s.prepare();assert s.call() is None;s.original_context()
    pending=s.c.pending;baseline=s.c.baseline
    s.prepare();s.game.memory[0xD057]=1
    s.kw['state'].update(phase='battle_dialogue',objective='Advance the visible dialogue.',available_actions=['a','wait'])
    s.kw['state']['battle_state'].update(raw=1,kind='wild',active=True)
    assert s.call() is None
    out,_=s.original_context()
    assert out['later_boulder_battle_delegate']=='existing_battle' and out['available_actions']==['a','wait']
    assert s.c.suspended and s.c.pending is pending and s.c.baseline is baseline
