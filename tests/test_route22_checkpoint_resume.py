"""New epoch from a source-bound checkpoint; no old instance/counter invented."""
from copy import deepcopy
import importlib.util
import inspect
from pathlib import Path
import laya_pokemon
import pytest

ROOT=Path(laya_pokemon.__file__).resolve().parents[2]
STAGE=ROOT/'.local/staged-route22-cold-resume-20261028'
HERE=Path(__file__).resolve()
if HERE==STAGE/'test_route22_checkpoint_resume.py':CANDIDATE=STAGE/'league_native_wait.py'
elif HERE==ROOT/'tests/test_route22_checkpoint_resume.py':CANDIDATE=ROOT/'src/laya_pokemon/league_native_wait.py'
else:raise RuntimeError('Only exact stage/formal checkpoint-resume test paths are supported')

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m,spec

fx,_=load('route22_checkpoint_fixtures',ROOT/'tests/test_league_native_wait.py')
hot,_=load('route22_retained_hot_regressions',ROOT/'tests/test_route22_reviewed_adoption.py')
hot.CANDIDATE=CANDIDATE
HOT_CASES=[(name,fn) for name,fn in vars(hot).items() if name.startswith('test_') and callable(fn)
           and list(inspect.signature(fn).parameters)==['env'] and not getattr(fn,'pytestmark',None)]

@pytest.fixture
def env():
    m,spec=load('laya_pokemon._route22_checkpoint_test',CANDIDATE)
    s=fx.Session(m);s.game.frame_count=1;s.values.update(script=4,status5=0,current=0)
    s.progress['badges_raw']=255;s.text=fx.dialogue_text(*fx.BEFORE[3]);s.sync();s.now=10.
    cap=dict(kind='route22_checkpoint_page3_resume_v1',source_frame=107929,initial_frame=1,page=3,
        names=dict(player='KEVIN',rival='BLUE'),location=dict(map_id=33,x=29,y=4),step_id=s.step['id'],
        source_checkpoint_sha256='a'*64,source_review_sha256='b'*64,
        source_progress_sha256=m.NativeWaitController.checkpoint_progress_sha256(s.progress))
    class Env:
        def __init__(self):self.m,self.s,self.cap,self.spec=m,s,cap,spec
        @property
        def c(self):return m._WAITS.get(s.step['id'])
        def call(self,*,fresh=False,previous=(),capsule=True,now=None,hot_cap=None):
            if fresh:s.game.frame_count+=40;s.now=(self.c.last_now if self.c else s.now)+40/60
            s.sync();before=deepcopy((s.state,s.step,s.text,s.game.memory.values))
            out=m.context(s.game,s.state,s.step,s.text,previous,now=s.now if now is None else now,
                checkpoint_resume_capsule=cap if capsule else None,review_capsule=hot_cap)
            assert before==(s.state,s.step,s.text,s.game.memory.values)
            return out
    return Env()

def bootstrap(e):
    out=e.call();assert out['available_actions']==['wait']
    assert out['native_wait_reason']=='checkpoint_resume_bootstrap_wait'
    c=e.c;h=out['checkpoint_resume_history']
    assert c.error is None and not hasattr(c,'reviewed_adoption')
    assert h['source_frame']==107929 and h['initial_frame']==h['observation_frame']==1
    assert h['epoch']=='new_controller_budget' and not h['old_instance_recovered']
    assert not h['older_spent_counters_recoverable'] and h['previous_review']=='native_packet_unverified'
    assert c.started==c.last_now==10. and c.last_frame==1 and c.calls==1 and c.elapsed==0
    assert c.packet is not None and not hasattr(c,'route22_dialogues')
    return out

def adopted(e):
    bootstrap(e);out=e.call(fresh=True,previous=['wait'])
    assert out['available_actions']==['a','wait'] and out['native_dialogue_page']==3
    assert out['checkpoint_resume_history']['adopted_page']==3
    assert e.c.error is None and e.c.calls==2 and e.c.elapsed==pytest.approx(40/60)
    return out

def test_new_epoch_bootstrap_and_actual_wait_are_distinct_from_old_hot_migration(env):
    e=env;bootstrap(e);c=e.c;owner=c.owner;packet=c.packet;h=c.checkpoint_resume_history
    out=e.call(previous=['wait']);assert out['available_actions']==['wait']
    assert not h['adopted'] and c.packet is packet and c.last_frame==1 and c.error is None
    out=e.call(fresh=True,previous=['wait'])
    assert out['available_actions']==['a','wait'] and e.c is c and c.owner is owner and c.checkpoint_resume_history is h
    assert c.started==10. and c.error is None and c.elapsed==pytest.approx(40/60)

@pytest.mark.parametrize('fault',['page','name','frame','flags','typed_byte','checkpoint_sha','review_sha','progress_sha','source_frame','initial_frame','money','metadata','nan','arrow','step'])
def test_wrong_initial_source_or_full_progress_fails_sticky_without_seeding(env,fault):
    e=env;s=e.s
    if fault=='page':s.text=fx.dialogue_text(*fx.BEFORE[2])
    elif fault=='name':
        reverse={v:k for k,v in fx.sdk.POKEMON_TEXT_DECODING.items() if type(k) is int and 0<=k<=255}
        s.game.memory.hook=lambda a,v:reverse['X'] if a==0xD158 else v
    elif fault=='frame':s.game.frame_count=2
    elif fault=='flags':s.events[0x527]=False
    elif fault=='typed_byte':s.game.memory.hook=lambda a,v:True if a==0xD356 else v
    elif fault in ('checkpoint_sha','review_sha','progress_sha'):e.cap['source_'+fault+'256']='x'*64
    elif fault=='source_frame':e.cap['source_frame']=107928
    elif fault=='initial_frame':e.cap['initial_frame']=True
    elif fault=='money':s.progress['money']+=1
    elif fault=='metadata':s.progress['extra_unhashed_fact']=1
    elif fault=='nan':s.progress['extra_unhashed_fact']=float('nan')
    elif fault=='arrow':s.text=fx.dialogue_text(*fx.BEFORE[3],arrow=False)
    elif fault=='step':s.step['face']='up'
    out=e.call();assert out['phase']=='campaign_review'
    if e.c is not None:
        assert e.c.error and not hasattr(e.c,'route22_dialogues')
        old=e.c.error;assert e.call(capsule=False)['review_reason'].endswith(old)

@pytest.mark.parametrize('fault',['previous','page','resource','flags','far_frame'])
def test_next_fresh_requires_actual_wait_same_page_and_canonical_progress(env,fault):
    e=env;bootstrap(e);prev=['wait']
    if fault=='previous':prev=['a']
    elif fault=='page':e.s.text=fx.dialogue_text(*fx.BEFORE[4])
    elif fault=='resource':e.s.progress['party'][0]['hp']-=1
    elif fault=='flags':e.s.events[0x526]=True
    elif fault=='far_frame':e.s.game.frame_count+=128
    out=e.call(fresh=True,previous=prev)
    assert out['phase']=='campaign_review' and not e.c.checkpoint_resume_history['adopted']
    assert not hasattr(e.c,'route22_dialogues') and e.c.error

def test_fresh_arrow_blink_waits_and_only_real_arrow_can_offer_a(env):
    e=env;bootstrap(e);e.s.text=fx.dialogue_text(*fx.BEFORE[3],arrow=False)
    out=e.call(fresh=True,previous=['wait'])
    assert out['available_actions']==['wait'] and out['native_wait_reason']=='native_dialogue_prompt_blink'
    assert e.c.checkpoint_resume_history['adopted'] and e.c.route22_dialogues['before']['pending'] is None
    e.s.text=fx.dialogue_text(*fx.BEFORE[3]);out=e.call(fresh=True,previous=['wait'])
    assert out['available_actions']==['a','wait'] and e.c.error is None

def test_same_frame_change_never_counts_as_fresh_arrow_blink(env):
    e=env;bootstrap(e);e.s.text=fx.dialogue_text(*fx.BEFORE[3],arrow=False)
    assert e.call()['review_reason'].endswith('checkpoint_resume_same_frame_packet_conflict')

def test_marker_changes_error_and_unknown_later_page_are_never_cleared(env):
    e=env;adopted(e);e.s.text=fx.dialogue_text('UNKNOWN PAGE','unexpected',arrow=True)
    out=e.call(fresh=True,previous=['a']);assert out['phase']=='campaign_review'
    old=e.c.error;e.s.text=fx.dialogue_text(*fx.BEFORE[3])
    assert e.call(fresh=True,previous=['wait'])['review_reason'].endswith(old)
    assert e.c.checkpoint_resume_history['previous_review']=='native_packet_unverified' and e.c.error!=e.c.checkpoint_resume_history['previous_review']

def test_checkpoint_hash_is_bound_after_bootstrap(env):
    e=env;bootstrap(e);e.cap['source_checkpoint_sha256']='c'*64
    assert e.call(fresh=True,previous=['wait'])['review_reason'].endswith('checkpoint_resume_capsule_changed')

def test_new_clock_is_bounded_and_cannot_be_reset_by_cold_capsule(env):
    e=env;bootstrap(e);out=e.call(now=100.)
    assert out['review_reason'].endswith('budget_exhausted') and e.c.started==10.
    assert e.call(now=100.)['review_reason'].endswith('budget_exhausted')

def test_cold_resume_cannot_be_used_as_a_hot_instance_repair(env):
    e=env;e.m._WAITS[e.s.step['id']]=e.m.NativeWaitController(e.s.step,owner=e.s.game)
    e.c.error='native_packet_unverified';e.c.calls=12;e.c.elapsed=5.
    out=e.call();assert out['review_reason'].endswith('native_packet_unverified')
    assert e.c.calls==12 and e.c.elapsed==5. and not hasattr(e.c,'checkpoint_resume_history')

def test_simultaneous_hot_and_cold_capsules_are_rejected(env):
    e=env;out=e.call(hot_cap={})
    assert out['review_reason'].endswith('checkpoint_resume_hot_capsule_conflict')
    assert e.c.error and not hasattr(e.c,'checkpoint_resume_history')

def test_reload_preserves_new_epoch_instance_history_pending_and_spent_clock(env):
    e=env;adopted(e);c=e.c;h=c.checkpoint_resume_history;pending=c.route22_dialogues['before']['pending']
    clock=(c.started,c.last_now,c.elapsed,c.calls)
    e.spec.loader.exec_module(e.m);assert e.m._WAITS[e.s.step['id']] is c
    assert c.checkpoint_resume_history is h and c.route22_dialogues['before']['pending'] is pending
    out=e.call(previous=['wait']);assert out['available_actions']==['wait']
    assert (c.started,c.last_now,c.elapsed)==clock[:3] and c.calls>=clock[3] and not pending['executed']

def test_remaining_source_pages_battle_and_five_after_pages_in_new_epoch(env):
    e=env;adopted(e)
    for i,pair in enumerate(fx.BEFORE[4:],4):
        e.s.text=fx.dialogue_text(*pair,arrow=i!=9);out=e.call(fresh=True,previous=['a'])
        if i==9:
            assert out['available_actions']==['wait'];out=e.call(fresh=True,previous=['wait'])
        assert out['available_actions']==['a','wait'] and out['native_dialogue_page']==i
    e.s.values.update(raw=2,script=5,current=242);e.s.text=fx.native_text()
    assert e.call(fresh=True,previous=['a'])['native_wait_reason']=='blank_trainer_intro'
    e.s.text=fx.native_text('BLUE wants',window=True);assert e.call(fresh=True) is None
    e.s.now=e.c.last_now+3600;e.s.game.frame_count+=40;e.s.text=fx.native_text();assert e.call() is None
    e.s.values.update(raw=0,script=5);e.s.events[0x526]=True;e.s.progress['party'][0]['exp']+=100
    for i,pair in enumerate(fx.AFTER):
        e.s.text=fx.dialogue_text(*pair,arrow=i!=4);out=e.call(fresh=True,previous=['a'] if i else ['wait'])
        if i==4:
            assert out['available_actions']==['wait'];out=e.call(fresh=True,previous=['wait'])
        assert out['available_actions']==['a','wait']
    e.s.values.update(script=6,status5=1);e.s.text=fx.native_text()
    assert e.call(fresh=True,previous=['a'])['native_wait_reason']=='rival_native_exit'
    e.s.values.update(script=7,status5=0);e.s.events[0x521]=e.s.events[0x527]=False
    assert e.call(fresh=True) is None
    assert e.c.error is None and e.c.calls<60 and e.c.elapsed<60

@pytest.mark.parametrize('name,fn',HOT_CASES,ids=[name for name,fn in HOT_CASES])
def test_existing_hot_recovery_nonparam_regressions_use_this_runtime(name,fn):
    original=hot.CANDIDATE;hot.CANDIDATE=CANDIDATE
    try:fn(hot.env.__wrapped__())
    finally:hot.CANDIDATE=original
