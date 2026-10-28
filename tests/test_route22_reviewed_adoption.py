"""Retain a real old parser/controller, then adopt only the named page3 schema."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
from pathlib import Path
import pytest
import laya_pokemon

ROOT=Path(laya_pokemon.__file__).resolve().parents[2]
STAGE=ROOT/'.local/staged-route22-reviewed-adoption-20261028'
HERE=Path(__file__).resolve()
if HERE==STAGE/'test_reviewed_adoption.py':
    CANDIDATE=STAGE/'league_native_wait.py'
    LEGACY=STAGE/'legacy_native_wait_fixture.py'
    FIXTURES=STAGE/'test_league_native_wait.py'
elif HERE==ROOT/'tests/test_route22_reviewed_adoption.py':
    CANDIDATE=ROOT/'src/laya_pokemon/league_native_wait.py'
    LEGACY=ROOT/'tests/fixtures/route22_legacy_native_wait.py'
    FIXTURES=ROOT/'tests/test_league_native_wait.py'
else:raise RuntimeError('Only exact stage/formal reviewed-adoption test paths are supported')
assert sha256(LEGACY.read_bytes().replace(b'\r\n',b'\n')).hexdigest()=='62b4fa3720be31deca7204b1a98a25007f84ac02232a9fbfa66157784b69ea73'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m,spec

fx,_=load('route22_adoption_fixtures',FIXTURES)

@pytest.fixture
def env():
    old,_=load('laya_pokemon._route22_original_review',LEGACY)
    new,spec=load('laya_pokemon._route22_adoption_review',CANDIDATE)
    s=fx.Session(old);s.game.frame_count=107929;s.values.update(script=4,status5=0,current=0)
    s.text=fx.dialogue_text(*fx.BEFORE[3]);r=s.call()
    assert r['review_reason']=='league_native_wait_native_packet_unverified'
    c=old._WAITS[s.step['id']]
    c.calls=13;c.elapsed=7.;c.started=4.;c.last_now=12.5
    original_packet=c.packet
    new._WAITS[s.step['id']]=c;s.m=new;s.now=c.last_now
    capsule=dict(kind='route22_before_page3_schema_adoption_v1',source_frame=107929,
        expected_error='native_packet_unverified',step_id=s.step['id'],location=dict(map_id=33,x=29,y=4),
        names=dict(player='KEVIN',rival='BLUE'),page=3)
    class Env:
        def __init__(self):self.s,self.m,self.c,self.spec,self.cap=s,new,c,spec,capsule;self.old_packet=original_packet
        def call(self,*,fresh=False,previous=(),capsule=True,now=None):
            if fresh:
                s.game.frame_count+=40;s.now=c.last_now+40/60
            s.sync();before=deepcopy((s.state,s.step,s.text,s.game.memory.values))
            result=new.context(s.game,s.state,s.step,s.text,previous,now=s.now if now is None else now,
                review_capsule=self.cap if capsule else None)
            assert before==(s.state,s.step,s.text,s.game.memory.values)
            return result
    return Env()

def bootstrap(e):
    r=e.call();assert r['available_actions']==['wait']
    assert r['native_wait_reason']=='reviewed_adoption_bootstrap_wait'
    d=r['route22_reviewed_adoption']
    assert d['source_frame']==d['observation_frame']==107929
    assert d['source_calls']==13 and d['source_elapsed']==7.
    assert d['calls']==14 and d['elapsed']==7. and d['adopted_page'] is None
    assert d['historical_error']=='native_packet_unverified'
    return r

def adopted(e):
    bootstrap(e);r=e.call(fresh=True,previous=['wait'])
    assert r['available_actions']==['a','wait'] and r['native_dialogue_page']==3
    d=r['route22_reviewed_adoption'];assert d['adopted_page']==3 and d['observation_frame']==107969
    assert d['elapsed']==pytest.approx(7+40/60) and d['source_elapsed']==7.
    return r

def test_bootstrap_retains_original_error_packet_owner_clocks_and_spent_budget(env):
    e=env;c=e.c;owner=c.owner;step=c.step;baseline=(c.started,c.last_now,c.last_frame,c.elapsed,c.intro_handoff)
    bootstrap(e)
    assert (c.started,c.last_now,c.last_frame,c.elapsed,c.intro_handoff)==baseline
    assert c.owner is owner and c.step is step and c.packet is e.old_packet
    assert c.error=='native_packet_unverified' and c.reviewed_recovery_error is None
    assert c.calls==14 and not hasattr(c,'route22_dialogues')
    assert c.reviewed_adoption['source_packet'] is e.old_packet
    r=e.call();assert r['available_actions']==['wait'] and c.calls==15
    assert not c.reviewed_adoption['adopted'] and c.packet is e.old_packet
    r=e.call(fresh=True,previous=['wait'])
    assert r['available_actions']==['a','wait'] and c.reviewed_adoption['adopted']
    assert c.error=='native_packet_unverified' and c.reviewed_recovery_error is None
    assert c.elapsed==pytest.approx(7+40/60) and c.started==4.
    assert c.route22_dialogues['before']['page']==3 and c.owner is owner and c.step is step


def test_fresh_same_page_with_blinking_arrow_adopts_but_waits_for_real_prompt(env):
    e=env;bootstrap(e)
    e.s.text=fx.dialogue_text(*fx.BEFORE[3],arrow=False)
    r=e.call(fresh=True,previous=['wait'])
    assert r['available_actions']==['wait'] and e.c.reviewed_adoption['adopted']
    assert e.c.error=='native_packet_unverified' and e.c.reviewed_recovery_error is None
    assert e.c.route22_dialogues['before']['pending'] is None
    e.s.text=fx.dialogue_text(*fx.BEFORE[3])
    assert e.call(fresh=True,previous=['wait'])['available_actions']==['a','wait']

@pytest.mark.parametrize('fault',['page','name','actual_name','source_byte','frame','flag','source','owner','step','arrow','resource','old_error','old_packet'])
def test_wrong_reviewed_facts_never_unlock_original_error_or_seed_page(env,fault):
    e=env;s=e.s;c=e.c
    if fault=='page':s.text=fx.dialogue_text(*fx.BEFORE[2])
    elif fault=='name':
        e.cap['names']['player']='OTHER'
    elif fault=='actual_name':
        reverse={v:k for k,v in fx.sdk.POKEMON_TEXT_DECODING.items() if type(k) is int and 0<=k<=255}
        s.game.memory.hook=lambda address,value:reverse['X'] if address==0xD158 else value
    elif fault=='source_byte':s.game.memory.hook=lambda address,value:True if address==0xD356 else value
    elif fault=='frame':s.game.frame_count+=40
    elif fault=='flag':s.events[0x527]=False
    elif fault=='source':e.cap['source_frame']=107928
    elif fault=='owner':c.owner=object()
    elif fault=='step':s.step['face']='up'
    elif fault=='arrow':s.text=fx.dialogue_text(*fx.BEFORE[3],arrow=False)
    elif fault=='resource':s.progress['party'][0]['hp']-=1
    elif fault=='old_error':c.error='unrelated_existing_review'
    else:c.packet=None
    old_error=c.error;old_packet=c.packet
    r=e.call();assert r['phase']=='campaign_review' and c.error==old_error and c.packet is old_packet
    assert not hasattr(c,'route22_dialogues') and getattr(c,'reviewed_adoption',None) is None
    reason=r['review_reason'];assert e.call()['review_reason']==reason
    assert e.call(capsule=False)['review_reason']==reason

@pytest.mark.parametrize('spent',['calls','elapsed'])
def test_prior_spent_native_budget_is_never_refunded_for_bootstrap(env,spent):
    e=env
    if spent=='calls':e.c.calls=61
    else:e.c.elapsed=61.
    before=(e.c.calls,e.c.elapsed,e.c.started,e.c.last_now,e.c.packet)
    r=e.call();assert r['review_reason'].endswith('budget_exhausted')
    assert (e.c.calls,e.c.elapsed,e.c.started,e.c.last_now,e.c.packet)==before
    assert e.c.error=='native_packet_unverified' and getattr(e.c,'reviewed_adoption',None) is None

@pytest.mark.parametrize('fault',['previous','page','resource','flags','far_frame'])
def test_fresh_adoption_requires_real_wait_same_page_and_original_resources(env,fault):
    e=env;bootstrap(e);prev=['wait']
    if fault=='previous':prev=['a']
    elif fault=='page':e.s.text=fx.dialogue_text(*fx.BEFORE[4])
    elif fault=='resource':e.s.progress['party'][0]['hp']-=1
    elif fault=='flags':e.s.events[0x526]=True
    elif fault=='far_frame':e.s.game.frame_count+=128
    r=e.call(fresh=True,previous=prev)
    assert r['phase']=='campaign_review' and not e.c.reviewed_adoption['adopted']
    assert e.c.error=='native_packet_unverified' and e.c.reviewed_recovery_error
    assert not hasattr(e.c,'route22_dialogues')

def test_same_frame_after_adoption_cannot_repeat_a_and_new_error_sticks(env):
    e=env;adopted(e);pending=e.c.route22_dialogues['before']['pending']
    r=e.call(previous=['wait']);assert r['available_actions']==['wait']
    assert e.c.route22_dialogues['before']['pending'] is pending and not pending['executed']
    e.s.text=fx.dialogue_text(*fx.BEFORE[4]);r=e.call(fresh=True,previous=['wait'])
    assert r['review_reason'].endswith('native_page_changed_without_actual_a')
    assert e.c.error=='native_packet_unverified'
    sticky=e.c.reviewed_recovery_error
    e.s.text=fx.dialogue_text(*fx.BEFORE[3])
    assert e.call(fresh=True,previous=['a'])['review_reason'].endswith(sticky)

def test_hot_reload_keeps_original_instance_error_and_adoption_references(env):
    e=env;adopted(e);c=e.c;record=c.reviewed_adoption;packet=c.packet;d=c.route22_dialogues
    values=(c.calls,c.elapsed,c.started,c.last_now,c.error,c.reviewed_recovery_error)
    e.spec.loader.exec_module(e.m)
    assert e.m._WAITS[e.s.step['id']] is c
    assert c.reviewed_adoption is record and c.packet is packet and c.route22_dialogues is d
    r=e.call(previous=['wait']);assert r['available_actions']==['wait']
    assert c.reviewed_adoption is record and c.packet==packet and c.route22_dialogues is d
    assert (c.elapsed,c.started,c.last_now,c.error,c.reviewed_recovery_error)==values[1:]
    assert c.calls>=values[0]

def test_complete_remaining_seven_before_pages_real_battle_and_five_after_pages(env):
    e=env;adopted(e)
    for i,pair in enumerate(fx.BEFORE[4:],4):
        e.s.text=fx.dialogue_text(*pair,arrow=i!=9)
        r=e.call(fresh=True,previous=['a'])
        if i==9:
            assert r['available_actions']==['wait'];r=e.call(fresh=True,previous=['wait'])
        assert r['available_actions']==['a','wait'] and r['native_dialogue_page']==i
    e.s.values.update(raw=2,script=5,current=242)
    e.s.text=fx.native_text();assert e.call(fresh=True,previous=['a'])['native_wait_reason']=='blank_trainer_intro'
    e.s.text=fx.native_text('BLUE wants',window=True);assert e.call(fresh=True) is None
    e.s.now=e.c.last_now+3600;e.s.game.frame_count+=40
    e.s.text=fx.native_text();assert e.call() is None
    e.s.values.update(raw=0,script=5);e.s.events[0x526]=True
    e.s.progress['party'][0]['exp']+=500
    for i,pair in enumerate(fx.AFTER):
        e.s.text=fx.dialogue_text(*pair,arrow=i!=4)
        r=e.call(fresh=True,previous=['a'] if i else ['wait'])
        if i==4:
            assert r['available_actions']==['wait'];r=e.call(fresh=True,previous=['wait'])
        assert r['available_actions']==['a','wait'] and r['native_dialogue_page']==i
    e.s.values.update(script=6,status5=1);e.s.text=fx.native_text()
    assert e.call(fresh=True,previous=['a'])['native_wait_reason']=='rival_native_exit'
    e.s.values.update(script=7,status5=0);e.s.events[0x521]=e.s.events[0x527]=False
    assert e.call(fresh=True) is None
    assert e.c.error=='native_packet_unverified' and e.c.reviewed_recovery_error is None
    assert e.c.reviewed_adoption['adopted'] and e.c.elapsed<60 and e.c.calls<60
