"""兩個固定洋館門落點：fake getter/格網/時間；不開模擬器或送鍵。"""
from copy import deepcopy
from importlib import reload
from types import SimpleNamespace

import pytest

from laya_pokemon import mansion_native_landing as land
from tests.test_hm_fly_teaching import fly_progress
from tests.test_hm_teaching import packet,canvas,put


CONSTANTS=dict(STATUS_FLAGS3_ADDRESS=0xD72D,EVENT_FLAGS_ADDRESS=0xD747,
               MAPS={'pokemon_mansion_2f':214,'pokemon_mansion_3f':215})


class Memory:
    def __init__(self,map_id=214,pos=(5,10),values=None,change=None,error=None):
        self.values={a:0 for a in land.ADDRESSES.values()}
        self.values.update({0xD35E:map_id,0xD362:pos[0],0xD361:pos[1]})
        self.values.update(values or {});self.reads={};self.change=change;self.error=error
    def __getitem__(self,a):
        self.reads[a]=self.reads.get(a,0)+1
        if a==self.error:raise RuntimeError('getter')
        if a==self.change and self.reads[a]>1:return self.values[a]+1
        return self.values[a]
    def __setitem__(self,a,v):raise AssertionError('no memory writes')


def read(memory=None,frame=100,constants=None,game=None):
    return land.read_mansion_landing_movement(game or SimpleNamespace(memory=memory or Memory(),frame_count=frame),
        observation_frame=frame,constants=CONSTANTS if constants is None else constants)


@pytest.mark.parametrize('mask,idle',[(0,True),(0xFC,False),(0xFF,False)])
def test_source_door_mask_fc_is_valid_busy_without_widening_other_profiles(mask,idle):
    result=read(Memory(values={0xCD6B:mask}))
    assert result['read_valid'] and result['joy_ignore']==mask
    assert land._idle(result,100,dict(map_id=214,x=5,y=10)) is idle


@pytest.mark.parametrize('map_id,pad,exit_pos',[(214,(5,10),(5,11)),(215,(6,1),(6,2))])
def test_readonly_reader_is_limited_to_the_two_source_pairs(map_id,pad,exit_pos):
    for pos in (pad,exit_pos):
        m=Memory(map_id,pos);before=deepcopy(m.values);result=read(m)
        assert result['read_valid'] and result['location']==dict(map_id=map_id,x=pos[0],y=pos[1])
        assert m.values==before and set(m.reads.values())=={2}


@pytest.mark.parametrize('address',list(land.ADDRESSES.values()))
def test_second_read_change_or_getter_exception_never_becomes_idle(address):
    for m in (Memory(change=address),Memory(error=address)):
        out=read(m);assert not out['read_valid']
        assert out['joy_ignore'] is None and out['movement_flags'] is None


@pytest.mark.parametrize('value',[None,True,False,-1,256,0.0])
def test_invalid_byte_type_is_unknown(value):
    result=read(Memory(values={0xCD6B:value}))
    assert not result['read_valid'] and result['joy_ignore'] is None


@pytest.mark.parametrize('mask',[1,16,127,254])
def test_other_input_ignore_masks_remain_unknown(mask):
    assert not read(Memory(values={0xCD6B:mask}))['read_valid']


@pytest.mark.parametrize('mutation',[
    lambda c:c.update(STATUS_FLAGS3_ADDRESS=True),lambda c:c.update(EVENT_FLAGS_ADDRESS=0xD748),
    lambda c:c['MAPS'].update(pokemon_mansion_2f=215),lambda c:c['MAPS'].pop('pokemon_mansion_3f')])
def test_fixed_sdk_anchors_are_required(mutation):
    c=deepcopy(CONSTANTS);mutation(c)
    assert read(constants=c)['read_valid'] is False


def test_reader_snapshot_frame_or_location_is_never_guessed():
    class ChangingFrame:
        memory=Memory();calls=0
        @property
        def frame_count(self):
            self.calls+=1;return 100 if self.calls==1 else 101
    assert not read(game=ChangingFrame())['read_valid']
    for map_id,pos in ((213,(5,10)),(214,(5,9)),(215,(6,3))):
        assert read(Memory(map_id,pos))['location'] is None


@pytest.fixture
def env(monkeypatch):
    for name,value in (('_CONTROLLERS',{}),('_BINDINGS',{}),('_COMPLETED',set())):
        monkeypatch.setattr(land,name,value)
    e=SimpleNamespace(now=10.,frame=100,map_id=214,pos=(5,10),p=fly_progress(),
                      memory=Memory(),text=packet(window=False),grid_unknown=False)
    e.text.update(lines=[],line_rows=[])
    monkeypatch.setattr(land.time,'monotonic',lambda:e.now)
    e.reader=land.read_mansion_landing_movement
    monkeypatch.setattr(land,'read_mansion_landing_movement',lambda game,*,observation_frame,constants:
        e.reader(game,observation_frame=observation_frame,constants=CONSTANTS))
    e.step=dict(id='native2',kind='interact',mechanic=land.MECHANIC,map_id=214,
                target=[5,11],landing_pad=[5,10])
    e.plan=dict(training_job='mansion-mainline',steps=[e.step,dict(id='next',kind='move')])
    return e


def call(e,*,advance=True,text='default',grid='default',step_id='native2',battle=None):
    if advance:e.frame+=40;e.now+=.1
    loc=dict(map_id=e.map_id,x=e.pos[0],y=e.pos[1])
    m=e.memory;m.values.update({0xD35E:e.map_id,0xD362:e.pos[0],0xD361:e.pos[1]})
    game=SimpleNamespace(memory=m,frame_count=e.frame)
    tiles=[[1]*14 for _ in range(14)];walk=[[1]*14 for _ in range(14)]
    if e.map_id in land.PAIRS:
        pad,exit_pos=land.PAIRS[e.map_id];tiles[pad[1]][pad[0]]=0x1B
    cells=[[x,y] for y in range(max(0,e.pos[1]-2),min(14,e.pos[1]+3)) for x in range(max(0,e.pos[0]-2),min(14,e.pos[0]+3))]
    g=dict(tileset_id=22,observation_frame=e.frame,verified_location=[e.map_id,*e.pos],
           tiles=tiles,walkable=walk,screen_cells_verified=len(cells),visible_verified_cells=cells)
    b=dict(kind='none',active=False,raw=0,observation_frame=e.frame)
    if battle:b.update(battle)
    state=dict(frame=e.frame,location=loc,progress=e.p,battle_state=b)
    return land.context(game,state,e.plan,step_id,e.text if text=='default' else text,
                        g if grid=='default' else grid)


def review(result):
    assert result[0]['phase']=='campaign_review' and result[0]['available_actions']==['wait']
    assert not result[0].get('field_move_complete')


def test_native_pending_pad_unknown_transition_then_two_fresh_exit_frames_complete(env):
    e=env;e.memory.values.update({0xCD6B:0xFC,0xCD38:1,0xD736:2})
    assert call(e)[0]['available_actions']==['wait']
    c=land._CONTROLLERS['native2'];base=deepcopy(c['baseline'])
    unknown=packet(window=False);unknown.update(read_valid=False,read_error='visible_display_disabled')
    assert call(e,text=unknown,grid=None)[0]['available_actions']==['wait']
    e.pos=(5,11);e.memory.values.update({0xCD6B:0,0xCD38:0,0xD736:0})
    first=call(e);assert not first[0]['field_move_complete']
    same=call(e,advance=False);assert not same[0]['field_move_complete']
    result,next_id=call(e)
    assert result['field_move_complete'] is True and next_id=='next'
    assert c['baseline']==base and land._COMPLETED=={'native2'}
    assert all(r[0]['available_actions']==['wait'] for r in (first,same,(result,next_id)))


def test_temporarily_idle_on_pad_is_not_exit_even_across_multiple_frames(env):
    for _ in range(3):assert not call(env)[0]['field_move_complete']
    assert not land._COMPLETED


def test_second_fixed_intent_may_bind_at_exit_but_needs_two_fresh_closed_samples(env):
    e=env;e.map_id=215;e.pos=(6,2);e.step.update(map_id=215,target=[6,2],landing_pad=[6,1])
    assert not call(e)[0]['field_move_complete']
    assert call(e)[0]['field_move_complete']


def test_unknown_text_or_grid_cannot_create_first_baseline(env):
    review(call(env,grid=None));assert not land._BINDINGS
    t=packet(window=False);t['read_valid']=False
    review(call(env,text=t));assert not land._BINDINGS


@pytest.mark.parametrize('change',[
    lambda e:setattr(e,'map_id',215),lambda e:setattr(e,'pos',(5,9)),
    lambda e:e.p['party'][0].update(hp=134),lambda e:e.p['party'][0].update(status=8),
    lambda e:e.p['party'][0]['pp'].__setitem__(0,24),lambda e:e.p['inventory'].reverse(),
    lambda e:e.p.update(money=41065),lambda e:e.p.update(party_read_valid=False)])
def test_bound_location_party_bag_and_money_changes_sticky_review(env,change):
    call(env);change(env);review(call(env));error=land._CONTROLLERS['native2']['error']
    assert error is not None
    review(call(env));assert land._CONTROLLERS['native2']['error']==error


@pytest.mark.parametrize('battle',[dict(active=True,kind='wild',raw=1),dict(raw=None),dict(raw=True)])
def test_battle_or_unknown_battle_never_receives_field_completion(env,battle):
    call(env);review(call(env,battle=battle))


def test_unknown_movement_getter_stops_without_clearing_original_budget(env):
    call(env);record=land._CONTROLLERS['native2'];started=record['started']
    env.memory.error=0xCD6B
    review(call(env));assert record['started']==started and record['error']


def test_same_frame_conflicting_decoder_packet_is_not_second_closed_frame(env):
    env.pos=(5,11);call(env)
    t=packet(window=False);t['read_valid']=False
    review(call(env,advance=False,text=t));assert not land._COMPLETED


def test_busy_or_unknown_interruption_clears_first_exit_sample(env):
    env.pos=(5,11);call(env)
    call(env,grid=None)
    assert not call(env)[0]['field_move_complete']
    assert call(env)[0]['field_move_complete']


@pytest.mark.parametrize('key,value',[('next_map',214),('terminal',True),('event','anything'),
    ('item',43),('badge',64),('await_script_event',True),('kind','move'),('map_id',True),
    ('landing_pad',[5,11]),('target',[5,12])])
def test_explicit_two_source_pairs_reject_generic_shortcuts(env,key,value):
    env.step[key]=value;review(call(env));assert not land._BINDINGS


def test_owner_or_training_job_change_cannot_rebind_original_transaction(env):
    call(env);review(call(env,step_id='other'));assert land._CONTROLLERS['native2']['error']=='owner_changed'


def test_job_changes_review_but_resume_revision_keeps_budget(env):
    call(env);record=land._CONTROLLERS['native2'];started=record['started']
    env.plan['resume_revision']=2;call(env);assert record['started']==started
    env.plan['training_job']='other';review(call(env));assert record['baseline']


def test_reload_preserves_owner_waits_started_and_sticky_error(env,monkeypatch):
    call(env);record=land._CONTROLLERS['native2'];started=record['started'];waits=record['waits']
    reload(land)
    monkeypatch.setattr(land,'read_mansion_landing_movement',lambda game,*,observation_frame,constants:
        env.reader(game,observation_frame=observation_frame,constants=CONSTANTS))
    assert land._CONTROLLERS['native2'] is record and record['started']==started and record['waits']==waits
    env.now+=61;review(call(env));assert record['error']=='budget_exhausted'
    reload(land);assert land._CONTROLLERS['native2'] is record and record['error']=='budget_exhausted'


def test_twenty_wait_limit_and_negative_or_regressed_clock_stay_review(env):
    for _ in range(20):assert call(env)[0]['available_actions']==['wait']
    review(call(env));assert land._CONTROLLERS['native2']['error']=='wait_budget_exhausted'


@pytest.mark.parametrize('loc_key,bad',[('tileset_id',0),('observation_frame',0),('verified_location',[214,5,9])])
def test_source_grid_conflicts_are_not_treated_as_transitional_unknown(env,loc_key,bad):
    # 最小錯字典故意不補其他格，任何明確不符不得構造baseline。
    review(call(env,grid={loc_key:bad}));assert not land._BINDINGS


def test_active_menu_or_unknown_profile_cannot_be_accepted_as_blank_world(env):
    call(env)
    t=packet(put(canvas(),1,14,'YES'),window=True)
    review(call(env,text=t));assert not land._COMPLETED
