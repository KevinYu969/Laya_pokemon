"""純合成同幀水路／戰鬥交接，不建立PyBoy或讀ROM／state。"""
from copy import deepcopy
import importlib

import pytest

from laya_pokemon import route21_water as water
from laya_pokemon.observation import PROFILE as TEXT_PROFILE
from laya_pokemon.rocket_movement import MOVEMENT_PROFILE


def progress():
    return {'profile':'gen1-wrapper-ram-progress-v1-unvalidated','initialization_candidate':True,
            'party_read_valid':True,'party_count':6,'money':55372,
            'inventory':[{'item':197,'quantity':1},{'item':198,'quantity':1}],
            'party':[dict(species=s,species_name=n,level=35,exp=50000,hp=100,max_hp=100,
                status=0,moves=[57,0,0,0],pp=[15,0,0,0]) for s,n in
                [(7,'NIDOKING'),(132,'SNORLAX'),(102,'EEVEE'),(154,'VENUSAUR'),(35,'FEAROW'),(19,'LAPRAS')]]}


def packet(index,frame,p=None,active=False):
    node=water.PATH[index];mid,x,y,mode,_=node
    height={0:18,32:90,8:18}[mid]
    tiles=[[0x14]*20 for _ in range(height)];walk=[[0]*20 for _ in range(height)]
    for m,nx,ny,nmode,tile in water.PATH:
        if m==mid: tiles[ny][nx]=tile;walk[ny][nx]=int(nmode==0)
    visible=sorted(([vx,vy]for vy in range(height)for vx in range(20)),
                   key=lambda v:(abs(v[0]-x)+abs(v[1]-y),v[1],v[0]))[:12]
    loc={'map_id':mid,'x':x,'y':y}
    text={'profile':TEXT_PROFILE,'read_valid':True,'alignment_verified':True,'read_error':None,
          'window_visible':False,'cells':[[' ']*20 for _ in range(18)],'lines':[],'line_rows':[]}
    state={'frame':frame,'location':loc,'progress':deepcopy(progress()if p is None else p),'text':text,
           'battle_state':{'raw':1 if active else 0,'active':active,'kind':'wild'if active else'none',
                           'observation_frame':frame}}
    signal={'profile':water.SURF_PROFILE,'source_commit':water.SOURCE_COMMIT,'read_valid':True,
            'read_error':None,'observation_frame':frame,'mode':mode,'location':deepcopy(loc),
            'battle_raw':1 if active else 0}
    grid={'tileset_id':0,'tiles':tiles,'walkable':walk,'observation_frame':frame,
          'verified_location':[mid,x,y],'visible_verified_cells':visible,'screen_cells_verified':12}
    movement={'profile':MOVEMENT_PROFILE,'source_commit':water.SOURCE_COMMIT,'read_valid':True,
              'read_error':None,'observation_frame':frame,'spinning':False,'simulated_remaining':0,
              'joy_ignore':0,'walk_counter':0,'movement_flags':0}
    return state,grid,signal,movement


class Session:
    def __init__(self):
        self.c=water.Route21WaterController();self.p=progress();self.frame=0;self.now=0.
        self.last=None
    def call(self,index=0,previous=('wait',),*,active=False,same=False,now=None,data=None):
        if not same:self.frame+=1
        self.now=self.now+.05 if now is None else now
        state,grid,signal,movement=packet(index,self.frame,self.p,active)if data is None else data
        before=deepcopy((state,grid,signal,movement,previous))
        result=self.c.context(state,grid=grid,signal=signal,movement=movement,previous=previous,now=self.now)
        assert (state,grid,signal,movement,previous)==before
        self.last=result
        return result
    def to(self,index):
        result=self.call()
        for i in range(1,index+1):
            action=result['available_actions'][0]
            assert action in ('down','left','right')
            result=self.call(i,(action,))
        return result


def review(result):
    assert result['phase']=='campaign_review' and result['available_actions']==['wait'],result
    assert result['route21_water_complete']is False


def test_source_path_has_only_106_exact_edges_with_two_real_map_connections():
    assert len(water.PATH)==107
    assert water.PATH[0]==(0,4,14,2,0x32) and water.PATH[-1]==(8,4,10,0,0x39)
    transitions=[]
    for a,b in zip(water.PATH,water.PATH[1:]):
        if a[0]==b[0]:assert abs(a[1]-b[1])+abs(a[2]-b[2])==1
        else:transitions.append((a[:3],b[:3]))
        assert water._direction(a,b)in('down','left','right')
    assert transitions==[((0,4,17),(32,4,0)),((32,3,89),(8,3,0))]
    assert all(n[4]in(0x14,0x32)and n[3]==2 for n in water.PATH[:-1])


def test_complete_fixed_route_preserves_original_water_grid_and_needs_two_fresh_landfall_frames():
    s=Session();result=s.to(106)
    assert result['available_actions']==['wait'] and not result['route21_water_complete']
    # 同包同幀不算第二次到岸；same previous必須仍是真RIGHT。
    assert not s.call(106,('right',),same=True)['route21_water_complete']
    final=s.call(106)
    assert final['route21_water_complete']is True and final['available_actions']==['wait']
    assert s.c.index==106 and s.c.fingerprint[0]==s.p['party']


def test_candidate_wait_does_not_move_or_reset_step_budget_and_same_frame_never_reoffers_key():
    s=Session();first=s.call(now=0)
    assert first['available_actions']==['down','wait']
    assert s.call(same=True,now=.1)['available_actions']==['wait']
    assert s.call(now=59)['available_actions']==['down','wait']
    assert s.c.index==0 and s.c.step_started==0
    review(s.call(now=60.01))


def test_appearing_at_next_cell_without_actual_direction_is_not_an_input_receipt():
    s=Session();s.call()
    review(s.call(1,('wait',)))


def test_walking_only_waits_and_does_not_reissue_a_direction_before_native_step_finishes():
    s=Session();s.call()
    d=packet(1,s.frame+1,s.p);d[3]['walk_counter']=4
    assert s.call(1,('down',),data=d)['available_actions']==['wait']
    assert s.c.index==0 and s.c.pending['executed']is True
    result=s.call(1)
    assert s.c.index==1 and result['available_actions']==['down','wait']


@pytest.mark.parametrize('index', [4,95])
def test_each_map_boundary_accepts_only_the_exact_source_connection_landing(index):
    s=Session();s.to(index-1)
    result=s.call(index,('down',))
    assert s.c.index==index and result['available_actions']==['down','wait']


def test_new_map_with_old_coordinates_is_not_premature_boundary_completion():
    s=Session();s.to(3)
    d=packet(4,s.frame+1,s.p)
    d[0]['location']['y']=17;d[2]['location']['y']=17
    review(s.call(4,('down',),data=d))
    assert s.c.index==3


@pytest.mark.parametrize('bad', ['skip_cell','wrong_map','wrong_mode','signal_frame','text_frame'])
def test_wrong_position_mode_or_observation_never_sends_another_direction(bad):
    s=Session();s.call();d=packet(1,s.frame+1,s.p)
    if bad=='skip_cell':d[0]['location']['y']=16;d[2]['location']['y']=16
    elif bad=='wrong_map':d[0]['location']['map_id']=8;d[2]['location']['map_id']=8
    elif bad=='wrong_mode':d[2]['mode']=0
    elif bad=='signal_frame':d[2]['observation_frame']+=1
    else:d[0]['text']['observation_frame']=True
    review(s.call(1,('down',),data=d))


@pytest.mark.parametrize('bad', ['water_tile','land_walkable','missing_visible_next','text','faint'])
def test_unverified_initial_world_or_health_never_arms_water_navigation(bad):
    s=Session();d=packet(0,1,s.p)
    if bad=='water_tile':d[1]['tiles'][15][4]=0x14
    elif bad=='land_walkable':d[1]['walkable'][15][4]=1
    elif bad=='missing_visible_next':d[1]['visible_verified_cells']=[c for c in d[1]['visible_verified_cells']if c!=[4,15]]
    elif bad=='text':d[0]['text']['window_visible']=True
    else:d[0]['progress']['party'][1]['hp']=0
    review(s.call(data=d))


def test_actual_new_cell_resets_only_that_step_timer_not_the_whole_route():
    s=Session();s.call(now=0)
    s.call(1,('down',),now=59)
    assert s.c.step_started==59 and s.c.started==0 and s.c.waits==0
    assert s.call(1,now=118)['available_actions']==['down','wait']
    review(s.call(1,now=119.01))


def test_native_landfall_mode0_at_old_water_cell_only_waits_and_cannot_complete():
    s=Session();s.to(105)
    d=packet(105,s.frame+1,s.p);d[2]['mode']=0;d[3]['walk_counter']=2
    result=s.call(105,('right',),data=d)
    assert result['available_actions']==['wait'] and not result['route21_water_complete']
    assert s.c.index==105
    assert not s.call(106)['route21_water_complete']
    assert s.call(106)['route21_water_complete']


def test_first_wild_consumes_actual_pending_water_landing_without_grid_before_handoff():
    s=Session();s.call()
    d=packet(1,s.frame+1,s.p,True);d=(d[0],None,d[2],None)
    assert s.call(1,('down',),active=True,data=d)is None
    assert s.c.index==1 and s.c.in_battle and s.c.pending is None
    # 原生戰鬥改HP/PP/EXP後，後續A不得誤作新的水步回執。
    s.p['party'][0].update(hp=90,exp=50200);s.p['party'][0]['pp'][0]=14
    assert s.call(1,('a',),active=True)is None
    # none但尚有尾頁只WAIT，不跳出水路按A；真closed後重取正常戰後資料。
    d=packet(1,s.frame+1,s.p);d[0]['text']['window_visible']=True
    assert s.call(1,('a',),data=d)['available_actions']==['wait']
    assert s.call(1)['available_actions']==['down','wait']
    assert s.c.fingerprint[0][0]['exp']==50200 and s.c.fingerprint[0][0]['pp'][0]==14


def test_first_battle_cannot_accept_a_candidate_that_laya_did_not_execute():
    s=Session();s.call()
    d=packet(1,s.frame+1,s.p,True)
    review(s.call(1,('wait',),active=True,data=(d[0],None,d[2],None)))


def test_battle_location_or_mode_cannot_drift_while_delegated():
    s=Session();s.call();assert s.call(1,('down',),active=True)is None
    review(s.call(2,('a',),active=True))


def test_nonbattle_party_bag_or_money_changes_cannot_be_mislabelled_as_movement():
    s=Session();s.call();s.p['party'][0]['pp'][0]-=1
    review(s.call(1,('down',)))


def test_valid_active_wild_time_is_excluded_but_same_frame_engineering_gap_is_not_reset():
    s=Session();s.call(now=0);assert s.call(1,('down',),active=True,now=1)is None
    assert s.call(1,('a',),active=True,now=601)is None
    assert s.c.excluded==600
    assert s.call(1,now=602)['available_actions']==['down','wait']
    t=Session();t.call(now=0);assert t.call(1,('down',),active=True,now=1)is None
    # 即使仍是active的同包，沒有新frame可證明遊戲持續，不自動抹工程暫停。
    review(t.call(1,('down',),active=True,same=True,now=62))


def test_thirty_wait_limit_and_owner_budget_survive_reload():
    s=Session();s.call(now=0)
    for n in range(30):
        d=packet(0,s.frame+1,s.p);d[3]['walk_counter']=1
        assert s.call(0,('down',),data=d,now=n+.1)['available_actions']==['wait']
    original=s.c;importlib.reload(water);s.c.__class__=water.Route21WaterController
    assert s.c is original and s.c.waits==30 and s.c.step_started==0
    d=packet(0,s.frame+1,s.p);d[3]['walk_counter']=1
    review(s.call(0,('wait',),data=d,now=31))


def test_whole_route_clock_is_not_reset_by_successful_new_cells():
    s=Session();result=s.call(now=0)
    for i in range(1,101):result=s.call(i,(result['available_actions'][0],),now=i*9)
    assert s.c.started==0 and s.c.index==100
    review(s.call(101,(result['available_actions'][0],),now=909))


def test_goal_cannot_complete_without_closed_idle_grid_and_mutated_intent_stays_rejected():
    s=Session();s.to(105)
    d=packet(106,s.frame+1,s.p);d[0]['text']['window_visible']=True
    assert not s.call(106,('right',),data=d)['route21_water_complete']
    s.c.intent['goal']=[8,5,10]
    review(s.call(106))


def test_same_frame_packet_conflict_and_boolean_clock_frame_are_rejected():
    s=Session();s.call()
    d=packet(0,s.frame,s.p);d[2]['mode']=0
    review(s.call(same=True,data=d))
    t=Session();d=packet(0,True,t.p)
    review(t.call(data=d))
