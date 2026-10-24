"""固定ON來源矩陣與純fake RAM；不讀outputs/ROM、不建模擬器或送鍵。"""
import base64
from copy import deepcopy
from importlib import reload
from types import SimpleNamespace
import zlib

import pytest

from laya_pokemon import mansion_transition_ready as ready
from tests.test_hm_fly_teaching import fly_progress
from tests.test_hm_teaching import packet,canvas,put

# 由固定a536711 blk/bst及ON分支替換後的840格，不讀ignored研究檔。
MATRICES={
165:'eJyFU0sOgjAQDWcwRhrj2sWsnRAbN0Qv0Psfxvl1WuqAQwKUl/eZKYXnQQFMBwWAiL5KfklhQwMRRu/0vD22KJCpoi9avT8DWrl0X36UoaaSMPYBWC+Tau5QUeF04O+chJWtcUneoZREfdN6KqWqL5xCm0RNtZZSahgZRY8mRj2ZabdUxoU2fsR5zroLldsyoU+y425UJ8+84XZDC7iZ5mUzG7hnKVVHHH0vUtLqjm/nHvgOaOAbc833GnNb6Y7u+f5HEfkvYjQPh0TRL5cCTss=',
216:'eJy9kTEOwyAMReUDZKqipANbpQx/rlQZZWs37n+e2g4EQgttlz4EsnjEIfkYNhhDApwAXDAIIeJACbGpSlsOC91siA21DVjpbEOsnr6Wtqy0vD9k8cy2RKxGPviGT3bvwkdweLZuEu04ks6GnSbS2bD9zn95r2RMJAFnW/xZzVgyCmb9PFf/GdUFf7SadcP6LeuGvewtTl3bvNXStevXX+T5lbz3BKopNCU='}
CONST=dict(EVENT_FLAGS_ADDRESS=0xD747,STATUS_FLAGS3_ADDRESS=0xD72D,
    MAPS={'pokemon_mansion_1f':165,'pokemon_mansion_3f':215,'pokemon_mansion_b1f':216},
    EVENT_FLAGS={'mansion_switch_on':0x278})
SOURCE_GRID='wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM'


class Memory:
    def __init__(self,loc=(165,16,14),values=None,change=None,error=None):
        self.values={a:0 for a in ready.ADDRESSES.values()}
        self.values.update({0xD35E:loc[0],0xD362:loc[1],0xD361:loc[2],0xD796:1})
        self.values.update(values or {});self.reads={};self.change=change;self.error=error
    def __getitem__(self,address):
        self.reads[address]=self.reads.get(address,0)+1
        if address==self.error:raise RuntimeError('synthetic getter')
        if address==self.change and self.reads[address]>1:return self.values[address]+1
        return self.values[address]
    def __setitem__(self,*args):raise AssertionError('read-only getter')


def read(memory=None,constants=None,game=None,frame=100):
    return ready.read_transition_movement(game or SimpleNamespace(memory=memory or Memory(),frame_count=frame),
        observation_frame=frame,constants=CONST if constants is None else constants)


@pytest.mark.parametrize('mask',[0,0xFC,0xFF])
def test_readonly_getter_known_door_masks_keep_exact_busy_bytes(mask):
    m=Memory(values={0xCD6B:mask});before=deepcopy(m.values);r=read(m)
    assert r['read_valid'] and r['joy_ignore']==mask and r['switch_on'] is True
    assert m.values==before and set(m.reads.values())=={2}


@pytest.mark.parametrize('a',list(ready.ADDRESSES.values()))
def test_getter_double_reads_and_exceptions_fail_unknown(a):
    for m in (Memory(change=a),Memory(error=a)):
        r=read(m);assert r['read_valid'] is False and r['location'] is None and r['joy_ignore'] is None


@pytest.mark.parametrize('value',[None,True,False,-1,256,0.0])
def test_getter_unknown_byte_never_becomes_idle(value):
    assert read(Memory(values={0xCD6B:value}))['read_valid'] is False


@pytest.mark.parametrize('mutation',[
    lambda c:c.update(EVENT_FLAGS_ADDRESS=True),lambda c:c.update(STATUS_FLAGS3_ADDRESS=0xD72E),
    lambda c:c['MAPS'].update(pokemon_mansion_1f=False),lambda c:c['MAPS'].pop('pokemon_mansion_3f'),
    lambda c:c['EVENT_FLAGS'].update(mansion_switch_on=0x279)])
def test_wrong_sdk_contract_is_not_a_valid_source_observation(mutation):
    c=deepcopy(CONST);mutation(c);assert not read(constants=c)['read_valid']


def test_getter_rejects_changed_frame_and_out_of_registry_map():
    class Torn:
        memory=Memory();n=0
        @property
        def frame_count(self):self.n+=1;return 100 if self.n==1 else 101
    assert not read(game=Torn())['read_valid']
    assert not read(Memory((214,5,10)))['read_valid']
    assert not read(Memory(values={0xCD6B:127}))['read_valid']


@pytest.fixture
def env(monkeypatch):
    for k,v in (('_CONTROLLERS',{}),('_BINDINGS',{}),('_COMPLETED',set())):monkeypatch.setattr(ready,k,v)
    e=SimpleNamespace(frame=100,now=10.,loc=(165,16,14),p=fly_progress(),memory=Memory())
    e.p['story_event_bits']={'mansion_switch_on':True}
    e.text=packet(window=False);e.text.update(lines=[],line_rows=[])
    e.prev=dict(id='hole',kind='move',map_id=215,target=[16,14],next_map=165)
    e.step=dict(id='settle',kind='interact',mechanic=ready.MECHANIC,map_id=165,target=[16,14])
    e.plan=dict(training_job='mansion-fixed',steps=[e.prev,e.step,dict(id='next',kind='move')])
    e.reader=ready.read_transition_movement
    monkeypatch.setattr(ready,'read_transition_movement',lambda game,*,observation_frame,constants:
        e.reader(game,observation_frame=observation_frame,constants=CONST))
    monkeypatch.setattr(ready.time,'monotonic',lambda:e.now)
    return e


def grid(e,frame):
    raw=zlib.decompress(base64.b64decode(MATRICES[e.loc[0]]));assert len(raw)==840
    tiles=[list(raw[y*30:(y+1)*30]) for y in range(28)]
    coll={1,16,17,19,27,32,33,34,48,49,50,66,67,72,82,85,88,94}
    cells=[[x,y] for y in range(max(0,e.loc[2]-2),min(28,e.loc[2]+3))
           for x in range(max(0,e.loc[1]-2),min(30,e.loc[1]+3))]
    return dict(source=SOURCE_GRID,tileset_id=22,observation_frame=frame,verified_location=list(e.loc),
                tiles=tiles,walkable=[[int(t in coll) for t in row] for row in tiles],
                screen_cells_verified=len(cells),visible_verified_cells=cells)


def call(e,*,advance=True,text='normal',g='normal',battle=None,step_id='settle'):
    if advance:e.frame+=40;e.now+=.1
    e.memory.values.update({0xD35E:e.loc[0],0xD362:e.loc[1],0xD361:e.loc[2]})
    b=dict(kind='none',active=False,raw=0,observation_frame=e.frame)
    if battle:b.update(battle)
    state=dict(frame=e.frame,location=dict(zip(('map_id','x','y'),e.loc)),progress=e.p,battle_state=b)
    game=SimpleNamespace(memory=e.memory,frame_count=e.frame)
    return ready.context(game,state,e.plan,step_id,e.text if text=='normal' else text,
                         grid(e,e.frame) if g=='normal' else g)


def review(result):
    assert result[0]['phase']=='campaign_review' and result[0]['available_actions']==['wait']
    assert not result[0].get('field_move_complete')


@pytest.mark.parametrize('dest,source,target,starget',[(165,215,[16,14],[16,14]),(216,165,[23,22],[21,23])])
def test_complete_only_two_fresh_full_on_source_world_samples(env,dest,source,target,starget):
    e=env;e.loc=(dest,*target);e.prev.update(map_id=source,target=starget,next_map=dest)
    e.step.update(map_id=dest,target=target)
    original=deepcopy(e.p)
    unknown=deepcopy(e.text);unknown.update(read_valid=False,alignment_verified=False,read_error='visible_display_disabled')
    first=call(e,text=unknown,g=None)
    assert first[0]['phase']=='overworld' and not first[0]['field_move_complete']
    assert not call(e)[0]['field_move_complete']
    assert not call(e,advance=False)[0]['field_move_complete']
    out,key=call(e);assert out['field_move_complete'] and key=='next'
    assert out['available_actions']==['wait'] and e.p==original


def test_registry_return_1f_tile_is_door_waits_native_down_then_two_fresh_exit_frames(env):
    e=env;e.loc=(165,21,23);e.prev.update(map_id=216,target=[23,22],next_map=165)
    e.step.update(map_id=165,target=[21,24],landing_pad=[21,23])
    assert grid(e,e.frame+40)['tiles'][23][21]==0x1B
    assert not call(e)[0]['field_move_complete']
    assert not call(e)[0]['field_move_complete']
    e.memory.values.update({0xCD6B:0xFC,0xCD38:1,0xD736:2})
    assert not call(e)[0]['field_move_complete']
    e.loc=(165,21,24);e.memory.values.update({0xCD6B:0,0xCD38:0,0xD736:0})
    assert grid(e,e.frame+40)['tiles'][24][21]==0x01
    assert not call(e)[0]['field_move_complete'];out,key=call(e)
    assert out['field_move_complete'] and out['available_actions']==['wait'] and key=='next'


def test_return_1f_original_door_target_or_missing_pad_is_not_a_completion_contract(env):
    e=env;e.loc=(165,21,23);e.prev.update(map_id=216,target=[23,22],next_map=165)
    e.step.update(map_id=165,target=[21,23])
    review(call(e));assert not ready._BINDINGS
    e.step['target']=[21,24]
    review(call(e));assert not ready._BINDINGS


@pytest.mark.parametrize('key,value',[('kind','interact'),('map_id',214),('target',[17,14]),
    ('next_map',216),('event','anything'),('mechanic','anything'),('item',43),('badge',64)])
def test_source_predecessor_must_be_immediately_adjacent_and_exact(env,key,value):
    env.prev[key]=value;review(call(env));assert not ready._BINDINGS


@pytest.mark.parametrize('key,value',[('next_map',165),('terminal',True),('event','x'),('item',43),
    ('badge',64),('await_script_event',True),('map_id',True),('target',[16,15])])
def test_destination_rejects_generic_shortcuts(env,key,value):
    env.step[key]=value;review(call(env));assert not ready._BINDINGS


def test_unknown_grid_never_completes_and_wrong_full_matrix_is_not_accepted_as_ready(env):
    e=env;call(e,g=None);r=ready._CONTROLLERS['settle'];base=r['baseline'];started=r['started']
    g=grid(e,e.frame+40);g['tiles'][0][0]=1;g['walkable'][0][0]=1
    assert not call(e,g=g)[0]['field_move_complete']
    assert r['closed_frame'] is None and r['baseline'] is base and r['started']==started
    assert not call(e)[0]['field_move_complete'];assert call(e)[0]['field_move_complete']


@pytest.mark.parametrize('error',sorted(ready.NATIVE_TEXT_ERRORS))
def test_only_actual_observation_errors_are_bounded_wait_not_completion(env,error):
    t=deepcopy(env.text);t.update(read_valid=False,read_error=error)
    out=call(env,text=t,g=None);assert out[0]['phase']=='overworld' and not out[0]['field_move_complete']


@pytest.mark.parametrize('fault',[dict(profile='wrong'),dict(read_valid=False,read_error='invented'),
    dict(read_valid=False,read_error=None),dict(read_valid=False,read_error=[]),dict(window_visible=True)])
def test_unknown_or_contradictory_decoder_metadata_never_becomes_ready(env,fault):
    t=deepcopy(env.text);t.update(fault);review(call(env,text=t))


def test_sameframe_conflict_does_not_count_two_ready_observations(env):
    call(env);t=deepcopy(env.text);t['warnings']=['changed']
    review(call(env,text=t,advance=False));assert not ready._COMPLETED


@pytest.mark.parametrize('mutation',[
    lambda e:e.p['party'][0].update(hp=134),lambda e:e.p['party'][0]['pp'].__setitem__(0,24),
    lambda e:e.p['inventory'].reverse(),lambda e:e.p.update(money=41065),
    lambda e:e.p.update(story_event_bits=None),lambda e:e.p['story_event_bits'].update(mansion_switch_on=False),
    lambda e:setattr(e,'loc',(165,16,15))])
def test_owner_baseline_switch_and_location_changes_are_sticky_review(env,mutation):
    call(env,g=None);mutation(env);review(call(env,g=None));r=ready._CONTROLLERS['settle']
    assert r['error'];review(call(env,g=None))


def test_ram_switch_or_getter_unknown_cannot_bind(env):
    env.memory.values[0xD796]=0;review(call(env,g=None));assert not ready._BINDINGS
    env.memory.values[0xD796]=1;env.memory.error=0xCD6B
    review(call(env,g=None));assert not ready._BINDINGS


def test_collision_mask_or_sourcegrid_metadata_must_match_full_source(env):
    g=grid(env,env.frame+40);g['walkable'][0][0]^=1;review(call(env,g=g));assert not ready._BINDINGS


def test_native_busy_wait_and_interrupted_closed_streak_preserve_budget(env):
    call(env);r=ready._CONTROLLERS['settle'];started=r['started']
    env.memory.values.update({0xCD6B:0xFC,0xCD38:1})
    assert not call(env)[0]['field_move_complete'] and r['closed_frame'] is None
    env.memory.values.update({0xCD6B:0,0xCD38:0})
    assert not call(env)[0]['field_move_complete'];assert call(env)[0]['field_move_complete']
    assert r['started']==started


def test_owner_or_job_cannot_be_rebound(env):
    call(env,g=None);r=ready._CONTROLLERS['settle'];base=r['baseline']
    env.plan['training_job']='other';review(call(env,g=None));assert r['baseline'] is base


def test_thirty_waits_reload_and_timeout_do_not_reset_original_record(env,monkeypatch):
    for _ in range(10):assert not call(env,g=None)[0]['field_move_complete']
    r=ready._CONTROLLERS['settle'];started=r['started'];base=r['baseline']
    reload(ready)
    monkeypatch.setattr(ready,'read_transition_movement',lambda game,*,observation_frame,constants:
        env.reader(game,observation_frame=observation_frame,constants=CONST))
    assert ready._CONTROLLERS['settle'] is r and r['waits']==10 and r['baseline'] is base
    env.plan['resume_revision']=3
    for _ in range(20):assert not call(env,g=None)[0]['field_move_complete']
    review(call(env,g=None));assert r['error']=='wait_budget_exhausted' and r['started']==started


def test_wall_clock_budget_and_sticky_error(env):
    call(env,g=None);r=ready._CONTROLLERS['settle'];env.now+=61
    review(call(env,g=None));assert r['error']=='budget_exhausted'
    review(call(env));assert not ready._COMPLETED


def basement(e):
    e.loc=(216,23,22);e.prev.update(map_id=165,target=[21,23],next_map=216)
    e.step.update(map_id=216,target=[23,22])


def test_b1_standing_warp_bit_is_not_motion_and_two_fresh_samples_complete_without_reset(env):
    e=env;basement(e)
    call(e,g=None);r=ready._CONTROLLERS['settle'];base=r['baseline'];started=r['started']
    e.memory.values[0xD736]=4
    assert not call(e)[0]['field_move_complete']
    assert r['waits']==2 and r['calls']==2 and r['error'] is None
    assert not call(e,advance=False)[0]['field_move_complete']
    out,key=call(e)
    assert out['field_move_complete'] and out['available_actions']==['wait'] and key=='next'
    assert r['started']==started and r['baseline'] is base and r['calls']==4 and r['waits']==3


@pytest.mark.parametrize('flags',[1,2,6,0x40,0x80])
def test_b1_other_known_movement_flags_cannot_become_ready(flags,env):
    basement(env);env.memory.values[0xD736]=flags
    assert not call(env)[0]['field_move_complete']
    assert not call(env)[0]['field_move_complete'] and not ready._COMPLETED


@pytest.mark.parametrize('which',['hole','return_door','return_exit'])
def test_standing_warp_exception_does_not_apply_to_other_registry_positions(env,which):
    e=env
    if which!='hole':
        e.prev.update(map_id=216,target=[23,22],next_map=165)
        e.step.update(map_id=165,target=[21,24],landing_pad=[21,23])
        e.loc=(165,21,23 if which=='return_door' else 24)
    e.memory.values[0xD736]=4
    assert not call(e)[0]['field_move_complete']
    assert not call(e)[0]['field_move_complete'] and not ready._COMPLETED


@pytest.mark.parametrize('address,value',[(0xCD38,1),(0xCD6B,0xFC),(0xCFC5,1)])
def test_b1_standing_warp_cannot_mask_other_three_busy_bytes(env,address,value):
    basement(env);env.memory.values.update({0xD736:4,address:value})
    assert not call(env)[0]['field_move_complete']
    assert not call(env)[0]['field_move_complete']


def test_b1_flags4_still_requires_full_source_matrix_and_true_decoder(env):
    basement(env);env.memory.values[0xD736]=4
    assert not call(env,g=None)[0]['field_move_complete']
    g=grid(env,env.frame+40);g['tiles'][0][0]=1;g['walkable'][0][0]=1
    assert not call(env,g=g)[0]['field_move_complete']
    assert ready._CONTROLLERS['settle']['closed_frame'] is None
    unknown=deepcopy(env.text);unknown.update(read_valid=False,read_error='visible_display_disabled')
    assert not call(env,text=unknown)[0]['field_move_complete']
    assert not call(env)[0]['field_move_complete'];assert call(env)[0]['field_move_complete']


@pytest.mark.parametrize('flags',[None,True,4.0,8])
def test_unknown_flag_or_invalid_type_still_reviews_without_completion(env,flags):
    basement(env);env.memory.values[0xD736]=flags
    review(call(env));assert not ready._COMPLETED


def test_flags4_fix_does_not_clear_existing_error_or_wall_budget(env):
    basement(env);call(env,g=None);r=ready._CONTROLLERS['settle'];started=r['started'];waits=r['waits']
    env.memory.values[0xD736]=4;env.now+=61
    review(call(env));assert r['error']=='budget_exhausted' and r['started']==started and r['waits']==waits
    review(call(env));assert r['error']=='budget_exhausted'
