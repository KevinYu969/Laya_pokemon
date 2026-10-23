"""只用合成畫面、公開來源版面與禁止寫入的fake getter；不載入模擬器。"""
from copy import deepcopy

import pytest

from laya_pokemon.rocket_elevator import (
    RocketElevatorController, floor_menu, read_elevator_animation,
    SOURCE_COMMIT, ANIMATION_PROFILE, MOVEMENT_PROFILE,
    SHADOW_SCY_ADDRESS, HARDWARE_SCY_ADDRESS, CHANNEL5_SOUND_ID_ADDRESS,
    INTENT, B1F_INTENT,
)


# 固定公開.blk/.bst左下碰撞格解碼；非ROM、存檔或本機outputs fixture。
SOURCE_TILES = [
    [93,93,93,93,93,93], [75,33,56,56,33,75], [75,69,20,20,69,75],
    [75,69,69,69,69,75], [75,69,69,69,69,75], [75,69,69,69,69,75],
    [75,69,69,69,69,75], [93,93,93,93,93,93],
]


def text_at(*entries):
    cells = [[' '] * 20 for _ in range(18)]
    for x, y, value in entries:
        assert x + len(value) <= 20
        cells[y][x:x+len(value)] = value
    return {'cells': cells}


def menu(index=0, marker='▶'):
    return text_at((1,14,'Which floor do'), (1,16,'you want?'), (6,4,'B1F'),
                   (6,6,'B2F'), (6,8,'B4F'), (6,10,'CANCEL'), (5,4+2*index,marker))


def inventory():
    return {'inventory': [{'item':4, 'quantity':8}, {'item':74, 'quantity':1}]}


def location(point=(1,2), mid=203, facing='up'):
    return {'map_id':mid, 'x':point[0], 'y':point[1], 'facing':facing}


def movement(frame, **extra):
    return {'read_valid':True, 'profile':MOVEMENT_PROFILE, 'source_commit':SOURCE_COMMIT,
            'observation_frame':frame, 'spinning':False, 'simulated_remaining':0,
            'joy_ignore':0, 'walk_counter':0, **extra}


def animation(frame, **extra):
    return {'read_valid':True, 'profile':ANIMATION_PROFILE, 'source_commit':SOURCE_COMMIT,
            'observation_frame':frame, 'shadow_scroll_y':40, 'hardware_scroll_y':40,
            'channel5_sound_id':0, **extra}


def grid(loc, frame):
    mid,x,y = loc['map_id'], loc['x'], loc['y']
    if mid == 203:
        tiles = deepcopy(SOURCE_TILES)
        walkable = [[int(tile in {0x14,0x17,0x1A,0x1C,0x20,0x38,0x45}) for tile in row] for row in tiles]
        visible = [[xx,yy] for yy in range(8) for xx in range(6)]
        tileset=18
    else:
        height,warp_y=(28,19) if mid==199 else (24,15)
        tiles = [[1]*30 for _ in range(height)];tiles[warp_y][25]=0x52
        walkable = [[1]*30 for _ in range(height)]
        visible = [[xx,yy] for yy in range(y-2,y+3) for xx in range(x-2,x+3)]
        tileset=22
    return {'tileset_id':tileset, 'tiles':tiles, 'walkable':walkable,
            'observation_frame':frame, 'verified_location':[mid,x,y],
            'visible_verified_cells':visible, 'screen_cells_verified':len(visible)}


def call(c, frame=100, *, text=None, loc=None, ready=True, grid_value='default',
         move=None, anim=None, progress=None, now=None, battle=False, cancel=False):
    loc=loc or location()
    return c.context(text or text_at(), progress or inventory(), loc,
                     grid(loc,frame) if grid_value == 'default' else grid_value,
                     move if move is not None else movement(frame),
                     anim if anim is not None else animation(frame),
                     frame=frame, now=frame/60 if now is None else now,
                     overworld_ready=ready, battle_active=battle, cancel=cancel)


def show_menu(c, frame, index=0, **kwargs):
    return call(c,frame,text=menu(index),ready=False,grid_value=None,**kwargs)


def selected(intent=None):
    c=RocketElevatorController(intent)
    assert call(c)['available_actions']==['a','wait']
    if c.target_floor=='B1F':
        assert show_menu(c,116,0)['available_actions']==['a','wait']
    else:
        assert show_menu(c,116,0)['available_actions']==['down','wait']
        assert show_menu(c,132,1)['available_actions']==['down','wait']
        assert show_menu(c,148,2)['available_actions']==['a','wait']
    assert c.stage=='settling'
    return c


def exiting(intent=None):
    c=selected(intent)
    assert call(c,364)['available_actions']==['wait']
    assert call(c,380)['available_actions']==['right','wait']
    return c


def test_whole_b4f_transaction_uses_feedback_and_actual_exit_only():
    c=RocketElevatorController()
    assert call(c)['available_actions']==['a','wait']
    partial=text_at((1,14,'Which floor d'))
    assert call(c,108,text=partial,ready=False,grid_value=None)['available_actions']==['wait']
    assert show_menu(c,116,0)['available_actions']==['down','wait']
    assert show_menu(c,124,0)['available_actions']==['wait']  # 不重送Down
    assert show_menu(c,132,1)['available_actions']==['down','wait']
    assert show_menu(c,148,2)['available_actions']==['a','wait']
    assert call(c,164,text=menu(2,'▷'),ready=False,grid_value=None)['available_actions']==['wait']
    # Source 100*2 frames以外還有延遲及PA音效；不能單靠座標／frame完成。
    assert call(c,348,anim=animation(348,channel5_sound_id=0x99))['available_actions']==['wait']
    assert call(c,364)['available_actions']==['wait']
    r=call(c,380)
    assert r['available_actions']==['right','wait'] and not r.get('rocket_elevator_complete')
    assert r['suppress_navigation_stall'] and r['suppress_blocked_edge_learning']
    assert call(c,396,loc=location((2,2),facing='right'))['available_actions']==['up','wait']
    assert call(c,412,loc=location((2,1)))['available_actions']==['wait']
    r=call(c,428,loc=location((25,15),202))
    assert r['rocket_elevator_complete'] and r['observed_destination']==[202,25,15]
    assert r['available_actions']==['wait']


def test_unknown_transition_text_clears_stability_and_never_navigates_or_completes():
    c=selected()
    assert call(c,364)['available_actions']==['wait']
    result=c.context({'cells':[]},inventory(),location(),None,movement(380),animation(380),
                     frame=380,now=380/60,overworld_ready=False,visible_text_verified=False)
    assert result['available_actions']==['wait'] and c.stable_count==0
    assert not result.get('rocket_elevator_complete')
    assert call(c,396)['available_actions']==['wait']
    assert call(c,412)['available_actions']==['right','wait']


def test_unknown_initial_text_and_conflicting_ready_cannot_interact():
    for ready in (False,True):
        c=RocketElevatorController()
        result=c.context({'cells':[]},inventory(),location(),None,movement(100),animation(100),
                         frame=100,now=0,overworld_ready=ready,visible_text_verified=False)
        assert result['phase']=='campaign_review' and result['available_actions']==['wait']


def test_real_exit_map_id_before_coordinates_only_waits_then_requires_true_landing():
    c=exiting()
    assert call(c,396,loc=location((2,2),facing='right'))['available_actions']==['up','wait']
    result=call(c,412,loc=location((2,1),202),ready=False,grid_value=None)
    assert result['available_actions']==['wait'] and not result.get('rocket_elevator_complete')
    assert call(c,428,loc=location((25,15),202))['rocket_elevator_complete']
    c=exiting()
    assert call(c,396,loc=location((2,1),202),ready=False,grid_value=None)['phase']=='campaign_review'


@pytest.mark.parametrize('index',[0,1,2])
def test_only_complete_unique_source_menu_gives_valid_active_index(index):
    assert floor_menu(menu(index))=={'status':'active','index':index}
    assert floor_menu(menu(index,'▷'))=={'status':'inactive','index':index}


@pytest.mark.parametrize('change',[
    lambda t:t['cells'][8].__setitem__(slice(6,9),list('B3F')),
    lambda t:t['cells'][8].__setitem__(slice(6,12),list('B4FNOT')),
    lambda t:t['cells'][6].__setitem__(slice(6,9),list('B1F')),
    lambda t:t['cells'][0].__setitem__(slice(0,3),list('B4F')),
    lambda t:t['cells'][4].__setitem__(slice(6,10),list(' B1F')),
    lambda t:t['cells'][10].__setitem__(slice(6,13),list('CANCELX')),
    lambda t:t['cells'][4].__setitem__(4,'▶'),
    lambda t:t['cells'][7].__setitem__(5,'▶'),
    lambda t:t['cells'][10].__setitem__(5,'▶'),
    lambda t:t['cells'][0].__setitem__(0,'▷'),
    lambda t:t['cells'][17].__setitem__(18,'▼'),
    lambda t:t['cells'][14].__setitem__(slice(1,14),list('Which floor x')),
    lambda t:t['cells'][16].__setitem__(slice(1,10),list('you want!')),
])
def test_malformed_labels_cursor_and_question_cannot_select_or_cancel(change):
    c=RocketElevatorController();call(c)
    t=menu();change(t)
    r=call(c,116,text=t,ready=False,grid_value=None,cancel=True)
    assert r['phase']=='campaign_review' and r['available_actions']==['wait']
    assert not c.cancel_requested


def test_partial_source_labels_without_cursor_only_wait_and_active_partial_reviews():
    c=RocketElevatorController();call(c)
    t=text_at((1,14,'Which floor do'),(1,16,'you want?'),(6,4,'B1F'),(6,6,'B'))
    assert floor_menu(t)['status']=='partial'
    assert call(c,116,text=t,ready=False,grid_value=None)['available_actions']==['wait']
    t['cells'][4][5]='▶'
    assert call(c,132,text=t,ready=False,grid_value=None)['phase']=='campaign_review'


def test_complete_labels_without_cursor_wait_but_cannot_select_or_cancel():
    c=RocketElevatorController(max_waits=1);call(c)
    t=menu();t['cells'][4][5]=' '
    assert call(c,116,text=t,ready=False,grid_value=None,cancel=True)['available_actions']==['wait']
    assert not c.cancel_requested
    assert call(c,132,text=t,ready=False,grid_value=None,cancel=True)['review_reason']=='elevator_wait_budget_exhausted'


@pytest.mark.parametrize('index',[1,2])
def test_initial_menu_must_really_start_at_source_first_floor(index):
    c=RocketElevatorController();call(c)
    assert show_menu(c,116,index)['review_reason']=='elevator_initial_cursor_not_source_first_floor'


def test_unexpected_cursor_jump_and_inactive_before_selection_review():
    c=RocketElevatorController();call(c);show_menu(c,116,0)
    assert show_menu(c,132,2)['review_reason']=='elevator_cursor_moved_unexpectedly'
    c=RocketElevatorController();call(c)
    assert call(c,116,text=menu(0,'▷'),ready=False,grid_value=None)['phase']=='campaign_review'


def test_same_frame_never_repeats_button_or_accepts_changed_menu():
    c=RocketElevatorController();call(c)
    assert call(c)['available_actions']==['wait']
    c=RocketElevatorController();call(c);show_menu(c,116,0)
    assert show_menu(c,116,0)['available_actions']==['wait']
    assert show_menu(c,116,1)['review_reason']=='elevator_same_frame_observation_conflict'


def test_known_cancel_sends_one_b_and_does_not_claim_b4f():
    c=RocketElevatorController();call(c)
    r=show_menu(c,116,0,cancel=True)
    assert r['available_actions']==['b','wait']
    assert show_menu(c,132,0)['available_actions']==['wait']
    r=call(c,148)
    assert r['rocket_elevator_cancelled'] and not r.get('rocket_elevator_complete')
    assert c.stage=='cancelled'


def test_cancel_unknown_initial_screen_and_unknown_floor_ui_never_send_b():
    assert call(RocketElevatorController(),cancel=True)['phase']=='campaign_review'
    c=RocketElevatorController();call(c)
    assert call(c,116,text=text_at((1,14,'It appears to'),(1,16,'need a key.')),
                ready=False,grid_value=None,cancel=True)['phase']=='campaign_review'


def test_ready_claim_does_not_authorize_unknown_top_menu_text_to_receive_a():
    r=call(RocketElevatorController(),text=text_at((1,1,'ITEM')))
    assert r['phase']=='campaign_review' and r['available_actions']==['wait']


def test_panel_facing_uses_normal_wall_direction_before_a_and_does_not_navigate_elsewhere():
    c=RocketElevatorController()
    assert call(c,loc=location(facing='left'))['available_actions']==['up','wait']
    assert call(c,116)['available_actions']==['a','wait']
    c=RocketElevatorController()
    assert call(c,loc=location((2,1)))['phase']=='campaign_review'


@pytest.mark.parametrize('point,mid', [((25,15),202),((25,14),202)])
def test_source_b4f_arrival_cells_only_complete_after_requested_normal_exit(point,mid):
    c=exiting();call(c,396,loc=location((2,2),facing='right'))
    assert call(c,412,loc=location(point,mid))['rocket_elevator_complete']
    c=selected()
    assert call(c,412,loc=location(point,mid))['phase']=='campaign_review'


@pytest.mark.parametrize('field,value', [('shadow_scroll_y',41),('hardware_scroll_y',39),('channel5_sound_id',0x99)])
def test_animation_scroll_or_tail_sound_prevents_exit_even_after_200_frames(field,value):
    c=selected()
    for f in [364,380,396]:
        r=call(c,f,anim=animation(f,**{field:value}))
        assert r['available_actions']==['wait'] and not r.get('rocket_elevator_complete')
    assert c.stable_count==0


def test_time_minimum_stable_frame_gap_and_grid_loss_each_prevent_animation_false_completion():
    c=selected()
    assert call(c,332)['available_actions']==['wait']  # selection148，尚未200
    assert c.stable_count==0
    assert call(c,364)['available_actions']==['wait']
    assert call(c,365)['available_actions']==['wait']  # 不同frame仍不足3frame間距
    assert call(c,380,grid_value=None,ready=False)['available_actions']==['wait']
    assert c.stable_count==0
    assert call(c,396)['available_actions']==['wait']
    assert call(c,412)['available_actions']==['right','wait']


def test_active_selected_menu_waits_without_second_a_and_conflicting_floor_reviews():
    c=selected()
    assert show_menu(c,364,2)['available_actions']==['wait']
    assert show_menu(c,380,1)['phase']=='campaign_review'


def test_exit_requests_each_sent_once_and_no_transition_is_treated_as_complete():
    c=exiting()
    assert call(c,396)['available_actions']==['wait']
    assert call(c,412,loc=location((2,2),facing='right'))['available_actions']==['up','wait']
    for f in (428,444):
        r=call(c,f,loc=location((2,2),facing='right'))
        assert r['available_actions']==['wait'] and not r.get('rocket_elevator_complete')


@pytest.mark.parametrize('mutation', [
    lambda g:g.update(tileset_id=22), lambda g:g.update(observation_frame=99),
    lambda g:g.update(verified_location=[203,2,1]), lambda g:g['tiles'].pop(),
    lambda g:g['tiles'][2].__setitem__(1,1), lambda g:g['walkable'][2].__setitem__(1,0),
    lambda g:g['visible_verified_cells'].pop(), lambda g:g.update(screen_cells_verified=True),
    lambda g:g['visible_verified_cells'].__setitem__(-1,[0,0]),
])
def test_wrong_source_grid_stale_or_incomplete_proof_cannot_interact(mutation):
    c=RocketElevatorController();loc=location();g=grid(loc,100);mutation(g)
    assert call(c,grid_value=g)['phase']=='campaign_review'


def test_destination_needs_actual_visible_matching_source_tile():
    c=exiting();call(c,396,loc=location((2,2),facing='right'))
    loc=location((25,15),202);g=grid(loc,412);g['tiles'][15][25]=1
    r=call(c,412,loc=loc,grid_value=g)
    assert r['review_reason']=='elevator_destination_tile_not_source_exit'
    assert not r.get('rocket_elevator_complete')


@pytest.mark.parametrize('progress', [
    {'inventory':None}, {'inventory':[]}, {'inventory':[{'item':74,'quantity':0}]},
    {'inventory':[{'item':True,'quantity':1}]}, {'inventory':[{'item':4,'quantity':1}]},
    {'inventory':[{'item':74,'quantity':1},{'item':74,'quantity':1}]},
])
def test_missing_unknown_or_duplicate_key_inventory_reviews(progress):
    r=call(RocketElevatorController(),progress=progress)
    assert r['review_reason']=='elevator_lift_key_inventory_not_verified'


def test_inventory_must_stay_unchanged_because_lift_key_is_not_consumed():
    c=RocketElevatorController();call(c)
    p=inventory();p['inventory'][0]['quantity']-=1
    assert show_menu(c,116,0,progress=p)['review_reason']=='elevator_inventory_changed'


@pytest.mark.parametrize('kind,change', [
    ('move',{'read_valid':False}), ('move',{'profile':'unknown'}),
    ('move',{'observation_frame':99}), ('move',{'spinning':0}),
    ('move',{'walk_counter':True}), ('move',{'joy_ignore':16}),
    ('anim',{'read_valid':False}), ('anim',{'source_commit':'unknown'}),
    ('anim',{'observation_frame':99}), ('anim',{'shadow_scroll_y':True}),
    ('anim',{'channel5_sound_id':256}),
])
def test_unknown_readonly_observations_never_cause_button(kind,change):
    kwargs={kind:movement(100,**change) if kind=='move' else animation(100,**change)}
    assert call(RocketElevatorController(),**kwargs)['phase']=='campaign_review'


@pytest.mark.parametrize('kwargs', [{'battle':True},{'ready':1},{'cancel':1},
                                   {'loc':location((1,2),200)}, {'loc':location((2,15),202)}])
def test_nonbattle_ui_and_location_must_be_verified(kwargs):
    assert call(RocketElevatorController(),**kwargs)['phase']=='campaign_review'


def test_timeout_failure_is_latched_and_does_not_repeat_action():
    c=RocketElevatorController(max_waits=1);call(c)
    assert call(c)['available_actions']==['wait']
    r=call(c)
    assert r['review_reason']=='elevator_wait_budget_exhausted'
    assert show_menu(c,116,0)==r
    c=RocketElevatorController(max_calls=1);call(c)
    assert show_menu(c,116,0)['review_reason']=='elevator_operation_budget_exhausted'
    c=RocketElevatorController();call(c)
    assert show_menu(c,116,0,now=62)['review_reason']=='elevator_operation_budget_exhausted'


@pytest.mark.parametrize('kwargs',[{'frame':99},{'now':0.1},{'now':float('nan')}])
def test_backwards_unknown_clocks_review(kwargs):
    c=RocketElevatorController();call(c)
    assert call(c,**kwargs)['review_reason']=='elevator_clock_or_frame_invalid'


def test_same_frame_passive_wait_still_updates_monotonic_clock_contract():
    c=RocketElevatorController();call(c,now=1)
    assert call(c,now=2)['available_actions']==['wait']
    assert call(c,116,now=1.5)['review_reason']=='elevator_clock_or_frame_invalid'


def test_input_objects_are_not_mutated_and_wait_does_not_infer_model():
    c=RocketElevatorController();t,p,loc=text_at(),inventory(),location()
    g,m,a=grid(loc,100),movement(100),animation(100)
    before=deepcopy((t,p,loc,g,m,a))
    c.context(t,p,loc,g,m,a,frame=100,now=1,overworld_ready=True)
    assert (t,p,loc,g,m,a)==before
    r=c.context(t,p,loc,g,m,a,frame=100,now=1,overworld_ready=True)
    from laya_pokemon.policy import LayaPolicy
    policy=LayaPolicy.__new__(LayaPolicy)
    result=policy.choose(r)
    assert result['action']=='wait' and result['passive_wait'] and result['model_ms']==0


class ReadOnlyMemory:
    def __init__(self,values=None):
        self.values={SHADOW_SCY_ADDRESS:40,HARDWARE_SCY_ADDRESS:40,CHANNEL5_SOUND_ID_ADDRESS:0}
        self.values.update(values or {});self.reads=[]
    def __getitem__(self,key):
        self.reads.append(key)
        return self.values[key]
    def __setitem__(self,*args):
        raise AssertionError('禁止寫入')


class FakePyBoy:
    def __init__(self,values=None):
        self.memory=ReadOnlyMemory(values);self.frame_count=100
    def tick(self,*args):raise AssertionError('禁止tick')
    def button_press(self,*args):raise AssertionError('禁止按鍵')


def test_adapter_reads_only_three_source_bytes_and_no_actions_or_writes():
    emulator=FakePyBoy()
    assert read_elevator_animation(emulator,observation_frame=100)==animation(100)
    assert emulator.memory.reads==[0xFFAF,0xFF42,0xC02A]


def test_source_allocation_includes_ten_byte_oam_dma_before_hram():
    # 固定layout.link先列OAM DMA再列HRAM；DMARoutine機器碼長度：
    # ld a,imm(2),ldh[imm],a(2),ld a,imm(2),dec a(1),jr nz(2),ret(1)。
    dma_size = 2+2+2+1+2+1
    # ram/hram.asm到hSCY前：softReset1，兩組UNION各4，tile1，priority1，
    # 巢狀UNION10，money3，BCD divisor3/buffer3，unused1，serial5，hSCX1。
    offset = 1+4+4+1+1+10+3+3+3+1+5+1
    assert SHADOW_SCY_ADDRESS == 0xFF80 + dma_size + offset == 0xFFAF
    assert CHANNEL5_SOUND_ID_ADDRESS == 0xC000 + 6 + 8*2 + 8*2 + 4 == 0xC02A


@pytest.mark.parametrize('value',[None,True,-1,256,'40'])
def test_adapter_unknown_bytes_never_become_zero_or_false_idle(value):
    r=read_elevator_animation(FakePyBoy({SHADOW_SCY_ADDRESS:value}),observation_frame=100)
    assert r['read_valid'] is False and r['shadow_scroll_y'] is None and r['channel5_sound_id'] is None


@pytest.mark.parametrize('frame',[None,True,-1,99])
def test_adapter_initial_frame_failure_does_not_read_memory(frame):
    emulator=FakePyBoy()
    r=read_elevator_animation(emulator,observation_frame=frame)
    assert not r['read_valid'] and not emulator.memory.reads


def test_adapter_frame_change_or_getter_exception_returns_unknown_entire_sample():
    emulator=FakePyBoy()
    class MovingMemory(ReadOnlyMemory):
        def __getitem__(self,key):
            value=super().__getitem__(key);emulator.frame_count+=1;return value
    emulator.memory=MovingMemory()
    r=read_elevator_animation(emulator,observation_frame=100)
    assert r['read_error']=='elevator_animation_frame_changed_during_read' and not r['read_valid']
    emulator=FakePyBoy();del emulator.memory.values[HARDWARE_SCY_ADDRESS]
    r=read_elevator_animation(emulator,observation_frame=100)
    assert r['read_error']=='elevator_animation_getter_failed' and not r['read_valid']


@pytest.mark.parametrize('kwargs',[{'intent':{'kind':'rocket_elevator','target_floor':'B2F'}},
                                   {'max_calls':True},{'max_waits':0},{'max_seconds':61},
                                   {'max_seconds':float('inf')}])
def test_unsupported_floor_intents_and_unbounded_limits_are_rejected(kwargs):
    with pytest.raises(ValueError):RocketElevatorController(**kwargs)


@pytest.mark.parametrize('point',[(25,19),(25,18)])
def test_explicit_b1f_whole_transaction_selects_zero_and_observes_source_arrival(point):
    intent=deepcopy(B1F_INTENT);c=RocketElevatorController(intent)
    before=deepcopy(intent)
    assert call(c)['available_actions']==['a','wait']
    r=show_menu(c,116,0)
    assert r['available_actions']==['a','wait'] and r['observed_cursor_index']==0
    assert r['rocket_elevator_target_floor']=='B1F' and r['rocket_elevator_destination_map']==199
    assert not r.get('rocket_elevator_complete')
    assert call(c,132,text=menu(0,'▷'),ready=False,grid_value=None)['available_actions']==['wait']
    assert call(c,300)['available_actions']==['wait']  # 還未到200frames
    assert call(c,364)['available_actions']==['wait']
    assert call(c,380)['available_actions']==['right','wait']
    assert call(c,396,loc=location((2,2),facing='right'))['available_actions']==['up','wait']
    r=call(c,412,loc=location((2,1),199),ready=False,grid_value=None)
    assert r['available_actions']==['wait'] and not r.get('rocket_elevator_complete')
    r=call(c,428,loc=location(point,199))
    assert r['rocket_elevator_complete'] and r['observed_destination']==[199,*point]
    assert r['available_actions']==['wait'] and intent==before


def test_default_and_legacy_instance_keep_verified_b4f_contract():
    assert RocketElevatorController().target_floor=='B4F'
    assert RocketElevatorController(INTENT).destination_spec==(202,2,((25,15),(25,14)))
    c=selected();del c.target_floor  # 父層保留已實測舊class實例的熱載入情境。
    assert call(c,364)['available_actions']==['wait']
    assert call(c,380)['available_actions']==['right','wait']
    assert call(c,396,loc=location((2,2),facing='right'))['available_actions']==['up','wait']
    r=call(c,412,loc=location((25,15),202))
    assert r['rocket_elevator_complete'] and r['rocket_elevator_target_floor']=='B4F'


@pytest.mark.parametrize('intent',[
    {'kind':'rocket_elevator','target_floor':'B2F'},
    {'kind':'rocket_elevator','target_floor':'1F'},
    {'kind':'rocket_elevator','target_floor':'B1F','destination_map':199},
    {'kind':'rocket_elevator','target_floor':'b1f'},
    {'kind':'rocket_elevator','target_floor':0},
    {'kind':'other','target_floor':'B1F'},
    {},'B1F', ['B1F'],
])
def test_b1f_requires_only_exact_bounded_return_intent(intent):
    with pytest.raises(ValueError):RocketElevatorController(intent)


@pytest.mark.parametrize('index',[1,2])
def test_b1f_wrong_initial_selected_option_never_gets_a(index):
    c=RocketElevatorController(B1F_INTENT);call(c)
    r=show_menu(c,116,index)
    assert r['review_reason']=='elevator_initial_cursor_not_source_first_floor'
    assert r['available_actions']==['wait'] and c.selection_frame is None


@pytest.mark.parametrize('index',[1,2])
def test_b1f_wrong_post_confirmation_option_cannot_be_treated_as_selected(index):
    c=selected(B1F_INTENT)
    r=show_menu(c,132,index)
    assert r['review_reason']=='elevator_selected_floor_cursor_conflict'
    assert r['available_actions']==['wait'] and not r.get('rocket_elevator_complete')


@pytest.mark.parametrize('change',[
    lambda t:t['cells'][4].__setitem__(slice(6,12),list('B1FNOT')),
    lambda t:t['cells'][0].__setitem__(slice(0,3),list('B1F')),
    lambda t:t['cells'][4].__setitem__(slice(6,9),list('B1 ')),
    lambda t:t['cells'][4].__setitem__(slice(6,10),list(' B1F')),
    lambda t:t['cells'][6].__setitem__(5,'▶'),
])
def test_b1f_incomplete_duplicate_or_misaligned_menu_cannot_confirm(change):
    c=RocketElevatorController(B1F_INTENT);call(c);t=menu();change(t)
    r=call(c,116,text=t,ready=False,grid_value=None)
    assert r['phase']=='campaign_review' and r['available_actions']==['wait']
    assert c.selection_frame is None


@pytest.mark.parametrize('point,mid',[
    ((25,15),202), ((25,14),202), ((25,19),200),
    ((25,15),199), ((24,19),199), ((25,20),199),
])
def test_b1f_wrong_map_or_non_source_exit_coordinates_cannot_complete(point,mid):
    c=exiting(B1F_INTENT);call(c,396,loc=location((2,2),facing='right'))
    r=call(c,412,loc=location(point,mid))
    assert r['phase']=='campaign_review' and r['available_actions']==['wait']
    assert not r.get('rocket_elevator_complete')


@pytest.mark.parametrize('kind',['dimensions','tileset','tile','blocked','stale','not_visible'])
def test_b1f_destination_requires_30x28_facility_visible_source_tile_and_walkable(kind):
    c=exiting(B1F_INTENT);call(c,396,loc=location((2,2),facing='right'))
    loc=location((25,19),199);g=grid(loc,412)
    if kind=='dimensions':g['tiles']=g['tiles'][:24];g['walkable']=g['walkable'][:24]
    elif kind=='tileset':g['tileset_id']=18
    elif kind=='tile':g['tiles'][19][25]=1
    elif kind=='blocked':g['walkable'][19][25]=0
    elif kind=='stale':g['observation_frame']=396
    else:g['visible_verified_cells'].remove([25,19]);g['screen_cells_verified']-=1
    r=call(c,412,loc=loc,grid_value=g)
    assert r['phase']=='campaign_review' and not r.get('rocket_elevator_complete')


def test_b1f_unknown_transition_text_resets_stable_and_never_infers_buttons():
    c=selected(B1F_INTENT)
    assert call(c,364)['available_actions']==['wait']
    r=c.context({'cells':[]},inventory(),location(),None,movement(380),animation(380),
                frame=380,now=380/60,overworld_ready=False,visible_text_verified=False)
    assert r['available_actions']==['wait'] and c.stable_count==0
    assert call(c,396)['available_actions']==['wait']
    assert call(c,412)['available_actions']==['right','wait']


def test_b1f_early_destination_without_exit_and_transition_timeout_never_complete():
    c=selected(B1F_INTENT)
    r=call(c,364,loc=location((25,19),199))
    assert r['phase']=='campaign_review' and not r.get('rocket_elevator_complete')
    c=exiting(B1F_INTENT);call(c,396,loc=location((2,2),facing='right'))
    c.max_waits=c.waits+1
    assert call(c,412,loc=location((2,1),199),ready=False,grid_value=None)['available_actions']==['wait']
    r=call(c,428,loc=location((2,1),199),ready=False,grid_value=None)
    assert r['review_reason']=='elevator_wait_budget_exhausted' and not r.get('rocket_elevator_complete')
