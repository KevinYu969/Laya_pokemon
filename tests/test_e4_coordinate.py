"""只用 synthetic RAM + 真 getter/native controller；未建立遊戲或讀 ROM。"""
from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
from laya_pokemon import league_native_wait as native

import laya_pokemon
ROOT=Path(laya_pokemon.__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
if HERE==ROOT/'tests':SOURCE=ROOT/'src/laya_pokemon'
elif HERE==ROOT/'.local/staged-e4-coordinate-20261028':SOURCE=HERE
else:raise RuntimeError('E4測試只能載精確stage/formal source')
fixture_spec=importlib.util.spec_from_file_location('_e4_native_fixture',ROOT/'tests/test_league_native_wait.py')
fixtures=importlib.util.module_from_spec(fixture_spec);fixture_spec.loader.exec_module(fixtures)


@pytest.fixture
def m():
    native._WAITS.clear()
    spec=importlib.util.spec_from_file_location('laya_pokemon._e4_stage',SOURCE/'e4_coordinate.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module._spec=spec
    yield module
    native._WAITS.clear()


class Session:
    def __init__(self,m,mid=245):
        self.m=m;self.s=fixtures.Session(native,mid);self.s.location.update(x=m.CONFIG[mid]['origin'][0],y=m.CONFIG[mid]['origin'][1])
        if mid!=113:self.s.events[native.CONFIG[mid]['auto']]=True
        self.now=0.;self.frame=1000;self.signal=None;self.previous=()
        mem=self.s.game.memory.values
        mem.update({address:0 for address in m.ADDRESSES.values()})
        npc=m.CONFIG[mid]
        mem.update({0xD4E1:1,0xC110:npc['picture'],0xC111:1,0xC119:0,
            0xC214:npc['npc'][1]+4,0xC215:npc['npc'][0]+4,0xC109:0,0xC10C:8})
        self.step=self.s.step

    @property
    def c(self):return native._WAITS.get(self.step['id'])
    @property
    def r(self):return getattr(self.c,self.m.NAMESPACE,None)
    def grid(self):
        points=[[x,y] for y in range(14) for x in range(10)]
        return dict(walkable=[[1]*30 for _ in range(40)],screen_cells_verified=len(points),
            visible_verified_cells=points,verified_location=[self.step['map_id'],self.s.location['x'],self.s.location['y']],
            observation_frame=self.frame,source='wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM')
    def prepare(self,point=None,previous=(),*,fresh=True,frames=40):
        if self.s.state is not None and fresh:self.frame+=frames;self.now+=frames/60
        self.previous=previous;self.s.game.frame_count=self.frame
        if point:self.s.location.update(x=point[0],y=point[1])
        self.s.sync()
        out=native.context(self.s.game,self.s.state,self.step,self.s.text,previous,now=self.now)
        assert out is None, out
        target=self.m.CONFIG[self.step['map_id']]['target']
        self.signal=self.m.read_interaction_signal(self.s.game,observation_frame=self.frame,constants=sdk) if (self.s.location['x'],self.s.location['y'])==target else None
        return self
    def call(self,**kw):
        args=dict(owner=self.s.game,state=self.s.state,step=self.step,text=self.s.text,grid=self.grid(),
            previous=self.previous,native_controller=self.c,now=self.now,signal=self.signal);args.update(kw)
        before=deepcopy((self.s.state,self.step,self.s.text,self.s.game.memory.values))
        out=self.m.context(**args)
        assert before==(self.s.state,self.step,self.s.text,self.s.game.memory.values)
        if out is not None:
            assert not any(out.get(k) for k in ('complete','victory_confirmed','battle_complete','league_complete'))
            assert set(out['available_actions'])<=set(('up','a','wait'))
        return out
    def origin(self):assert self.prepare().call() is None;return self
    def target(self,previous=()):return self.prepare(self.m.CONFIG[self.step['map_id']]['target'],previous)


def review(out,reason=None):
    assert out['phase']=='campaign_review' and out['available_actions']==['wait']
    if reason:assert out['review_reason']=='e4_coordinate_'+reason


@pytest.mark.parametrize('mid',[245,246,247])
def test_source_endpoint_ordinary_walk_real_up_then_single_a(m,mid):
    s=Session(m,mid).origin();assert s.r['origin']==[5,5]
    assert s.prepare((5,4),['up']).call() is None
    out=s.target(['up']).call();assert out['available_actions']==['up','wait']
    s.s.game.memory.values[0xC109]=4
    out=s.target(['up']).call();assert out['available_actions']==['a','wait']
    assert s.call()['available_actions']==['wait']
    assert s.prepare(previous=['a']).call()['available_actions']==['wait']
    assert s.c.error is None and s.r['last_offer']=='a'


def test_lance_source_coordinate_is_always_wait_never_a(m):
    s=Session(m,113).origin();assert s.r['origin']==[6,11]
    assert s.prepare((6,7),['up']).call() is None
    for _ in range(4):
        out=s.target(['up']).call();assert out['available_actions']==['wait']
        assert out['e4_coordinate_reason']=='lance_source_coordinate_autotrigger'
    assert s.r['last_offer'] is None


@pytest.mark.parametrize('mid',[33,120,147,999])
def test_other_maps_out_of_scope_no_manual_a(m,mid):
    assert m.context(None,{},dict(map_id=mid),{},None,(),native_controller=None,now=0) is None


def test_cannot_start_at_target_and_skip_native_endpoint(m):
    s=Session(m);s.target()
    review(s.call(),'native_endpoint_witness_required');assert s.r is None


def test_native_entry_flag_required_no_faked_autowalk(m):
    s=Session(m).origin();s.s.events[native.CONFIG[245]['auto']]=False;s.target()
    review(s.call(),'native_autowalk_event_required')
    s.s.events[native.CONFIG[245]['auto']]=True;s.target()
    review(s.call(),'native_autowalk_event_required')


@pytest.mark.parametrize('change,reason',[
    ({'waiting':True},'native_not_released'),({'intro_handoff':True},'native_not_released'),
    ({'error':'unknown_prior_error'},'native_error_retained'),({'last_frame':999},'native_frame_not_current'),
    ({'calls':61},'native_budget_exhausted'),({'elapsed':60.01},'native_budget_exhausted'),
    ({'last_now':float('nan')},'native_clock_not_current'),
])
def test_native_release_guards_and_original_error_retained(m,change,reason):
    s=Session(m).origin();s.target();s.c.__dict__.update(change)
    review(s.call(),reason)
    if 'error' in change:assert s.c.error==change['error']


def test_wrong_owner_or_full_step_never_approved(m):
    s=Session(m).origin();s.target()
    review(s.call(owner=object()),'owner_unverified')
    assert s.r['error'] is None
    for changed in ({**s.step,'id':'other'},{**s.step,'target':[5,4]},{**s.step,'new_unknown':True}):
        review(s.call(step=changed),'bound_step_changed')
    assert s.r['step']==s.step


def test_native_same_frame_original_progress_packet_required(m):
    s=Session(m).origin();s.target()
    changed=deepcopy(s.s.state);changed['progress']['money']+=1
    review(s.call(state=changed),'native_packet_disagrees')
    review(s.call(),'native_packet_disagrees')


@pytest.mark.parametrize('key,value',[('script',1),('battle_raw',2),('battle_type',1),
    ('badges',127),('simulated',1),('ignored',240),('status5',1)])
def test_native_raw_script_masks_must_still_be_exact_source_idle(m,key,value):
    s=Session(m).origin();s.target();s.c.packet[4]['values'][key]=value
    review(s.call(),'native_idle_unverified')
    s.c.packet[4]['values'][key]=0
    review(s.call(),'native_idle_unverified')


@pytest.mark.parametrize('key,value,reason',[
    ('npc_picture',57,'source_npc_pose_unverified'),('npc_x',10,'source_npc_pose_unverified'),
    ('npc_y',7,'source_npc_pose_unverified'),('npc_facing',4,'source_npc_pose_unverified'),
    ('npc_status',3,'source_npc_pose_unverified'),('npc_walk',1,'source_npc_pose_unverified'),
    ('npc_y_step',255,'source_npc_pose_unverified'),('object_count',2,'source_npc_pose_unverified'),
    ('player_facing',255,'source_facing_or_collision_unverified'),
    ('player_collision',1,'source_facing_or_collision_unverified'),
])
def test_real_npc_facing_location_collision_unknown_stop_sticky(m,key,value,reason):
    s=Session(m).origin();s.target();s.signal['values'][key]=value
    review(s.call(),reason)
    s.signal['values'][key]=0;review(s.call(),reason)


@pytest.mark.parametrize('mutate',[
    lambda g:g.update(observation_frame=0),lambda g:g.update(verified_location=[245,5,4]),
    lambda g:g.update(screen_cells_verified=0),lambda g:g.update(source='guessed'),
    lambda g:g['walkable'][3].__setitem__(5,0),lambda g:g['walkable'][2].__setitem__(5,0),
    lambda g:g.update(visible_verified_cells=[[0,0]]*g['screen_cells_verified']),
])
def test_grid_requires_actual_same_frame_source_and_npc_cells(m,mutate):
    s=Session(m).origin();s.target();g=s.grid();mutate(g)
    review(s.call(grid=g),'world_grid_unverified')


def test_up_ack_is_real_previous_and_real_facing(m):
    s=Session(m).origin();assert s.target().call()['available_actions']==['up','wait']
    s.target(['wait']);s.signal['values']['player_facing']=4
    review(s.call(),'actual_up_ack_unverified')


def test_previous_up_without_real_facing_never_a(m):
    s=Session(m).origin();s.target().call();s.target(['up'])
    review(s.call(),'actual_up_facing_unverified')


def test_same_frame_never_repeats_up_a_or_spends(m):
    s=Session(m).origin();out=s.target().call();before=(s.c.calls,s.c.elapsed,s.r['calls'])
    for _ in range(3):assert s.call()['available_actions']==['wait']
    assert before==(s.c.calls,s.c.elapsed,s.r['calls'])
    s.s.game.memory.values[0xC109]=4;s.target(['up']);assert s.call()['available_actions']==['a','wait']
    before=(s.c.calls,s.c.elapsed,s.r['calls'])
    assert s.call()['available_actions']==['wait'] and before==(s.c.calls,s.c.elapsed,s.r['calls'])


def test_same_frame_changed_packet_sticky_review(m):
    s=Session(m).origin();s.target().call();s.signal['values']['player_collision']=0
    review(s.call(),'same_frame_packet_conflict')
    s.signal['values']['player_collision']=8;review(s.call(),'same_frame_packet_conflict')


def test_native_counter_consumed_monotonically_no_second_budget(m):
    s=Session(m).origin();s.c.calls=59
    out=s.target().call();assert out['native_wait_calls']==60
    s.s.game.memory.values[0xC109]=4;s.target(['up'])
    review(s.call(),'budget_exhausted');assert s.c.calls==61


def test_original_native_elapsed_spend_not_refunded_or_double_counted(m):
    s=Session(m).origin();s.c.elapsed=10.;s.r['native_elapsed']=10.
    s.target();s.c.elapsed+=.25
    out=s.call();assert out['native_wait_elapsed_seconds']==pytest.approx(10+40/60)
    assert s.r['native_elapsed']==s.c.elapsed


@pytest.mark.parametrize('change',[
    lambda s:setattr(s.c,'calls',s.r['native_calls']-1),
    lambda s:setattr(s.c,'elapsed',s.r['native_elapsed']-.1),
    lambda s:setattr(s.c,'started',s.c.started+1),
])
def test_counter_refund_or_native_clock_rebuild_sticky(m,change):
    s=Session(m).origin();s.target().call();s.target(['up']);change(s)
    review(s.call(),'counter_clock_or_frame_regressed')


def test_refund_after_observed_ordinary_navigation_also_stops(m):
    s=Session(m).origin();s.prepare((5,4),['up']);s.c.calls=10;s.c.elapsed=2
    assert s.call() is None
    assert s.r['native_calls']==10 and s.r['native_elapsed']==2
    s.target(['up']);s.c.calls=9
    review(s.call(),'counter_clock_or_frame_regressed')


def test_new_controller_cannot_reuse_old_budget_or_endpoint(m):
    s=Session(m).origin();s.target().call();old=s.c
    new=native.NativeWaitController(s.step,owner=s.s.game)
    native._WAITS[s.step['id']]=new
    s.prepare(fresh=False)
    assert s.c is not old
    review(s.call(),'native_endpoint_witness_required')


def test_timeout_and_unknown_error_not_cleared(m):
    s=Session(m).origin();s.target();s.now+=61;s.c.last_now=s.now
    review(s.call(),'emulator_clock_disagrees')
    assert s.r['error']=='emulator_clock_disagrees'
    s.now-=61;s.c.last_now=s.now;review(s.call(),'emulator_clock_disagrees')
    other=Session(m,246).origin();other.c.elapsed=59.9;other.r['native_elapsed']=59.9;other.target()
    # Native already spent almost all budget; even one exact real-frame increment is rejected.
    review(other.call(),'budget_exhausted')


def test_physical_walk_pending_waits_no_up_or_a(m):
    s=Session(m).origin();s.target();s.signal['values']['walk']=1
    out=s.call();assert out['available_actions']==['wait'] and s.r['last_offer'] is None


def test_reload_preserves_owner_namespace_spend_and_sticky_error(m):
    s=Session(m).origin();s.target().call();record=s.r;original=s.c;spent=(s.c.calls,s.c.elapsed)
    m._spec.loader.exec_module(m)
    assert s.c is original and s.r is record and spent==(s.c.calls,s.c.elapsed)
    assert s.call()['available_actions']==['wait']
    s.target(['wait']);review(s.call(),'actual_up_ack_unverified')
    m._spec.loader.exec_module(m);review(s.call(),'actual_up_ack_unverified')


def test_getter_real_bytes_double_read_no_keys_no_tick(m):
    s=Session(m).origin();s.target();sig=s.signal
    assert sig['read_valid'] is True and sig['values']['npc_x']==9
    reads=s.s.game.memory.reads
    assert all(reads.count(a)>=2 for a in m.ADDRESSES.values())
    assert sig['owner_id']==id(s.s.game) and sig['frame_before']==sig['frame_after']==s.frame
    assert 0xD71C not in m.ADDRESSES.values()  # 推石 scratch 不是玩家碰撞。


@pytest.mark.parametrize('bad',[-1,True,float('nan')])
def test_getter_bad_frames(m,bad):
    s=Session(m)
    assert not m.read_interaction_signal(s.s.game,observation_frame=bad,constants=sdk)['read_valid']


def test_getter_torn_bytes_sdk_anchor_and_frame(m):
    s=Session(m).origin();s.target()
    s.s.game.memory.hook=lambda a,v:v+1 if a==0xC109 and len([r for r in s.s.game.memory.reads if r==a])%2 else v
    out=m.read_interaction_signal(s.s.game,observation_frame=s.frame,constants=sdk)
    assert out['read_valid'] is False and out['read_error']=='torn_frame_or_snapshot'
    s.s.game.memory.hook=None
    assert not m.read_interaction_signal(s.s.game,observation_frame=s.frame+1,constants=sdk)['read_valid']
    bad=SimpleNamespace(STATUS_FLAGS3_ADDRESS=0xD72E,OBTAINED_BADGES_ADDRESS=0xD356,MAPS=sdk.MAPS)
    assert not m.read_interaction_signal(s.s.game,observation_frame=s.frame,constants=bad)['read_valid']


def test_real_getter_wrapper_does_not_invent_endpoint_or_owner(m):
    s=Session(m).origin();s.target()
    before=deepcopy(s.s.game.memory.values)
    out=m.at_target(s.s.game,s.s.state,s.step,s.s.text,s.grid(),(),native_controller=s.c,now=s.now)
    assert out['available_actions']==['up','wait'] and before==s.s.game.memory.values
