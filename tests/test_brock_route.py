from laya_pokemon.brock_route import brock_waypoint
from laya_pokemon.world_map import world_direction
from laya_pokemon.local_planner import allowed_stages


def progress(level=13, hp=38, badge=0, beat=False):
    return {'party_read_valid':True,'party':[{'species':153,'level':level,'hp':hp,'max_hp':38,'moves':[33,45,73,22],'pp':[35,40,10,10]}], 'inventory':[{'item':4,'quantity':6}], 'story_event_bits':{'got_pokedex':True,'beat_brock':beat},'badges_raw':badge}


def test_brock_requires_both_defeat_and_boulder_badge():
    loc={'map_id':54,'x':4,'y':2}
    assert brock_waypoint(loc,progress(beat=True))['goal']!='first_gym_complete'
    assert brock_waypoint(loc,progress(badge=1))['goal']!='first_gym_complete'
    assert brock_waypoint(loc,progress(badge=1,beat=True))['goal']=='first_gym_complete'


def test_route_leaves_training_and_heals_before_gym():
    assert brock_waypoint({'map_id':33,'x':30,'y':9},progress())['controller_waypoint']['y']==9
    p=brock_waypoint({'map_id':2,'x':12,'y':24},progress(hp=37))
    assert p['goal']=='reach_pewter_center'
    assert brock_waypoint({'map_id':2,'x':12,'y':24},progress())['goal']=='reach_pewter_gym'


def test_world_bfs_goes_away_from_goal_to_escape_maze():
    grid={'walkable':[[1,0,1],[1,0,1],[1,1,1]],'screen_cells_verified':90}
    hint=world_direction(grid,{'x':0,'y':0},{'x':2,'y':0})
    assert hint['direction']=='down' and hint['path_length']==6
    assert world_direction(grid,{'x':2,'y':0},{'x':2,'y':-1})['direction']=='up'


def test_world_bfs_does_not_walk_through_npc():
    grid={'walkable':[[1,1,1],[1,1,1]],'screen_cells_verified':90}
    assert world_direction(grid,{'x':0,'y':0},{'x':2,'y':0},[(1,0)])['direction']=='down'


def test_mission_can_continue_through_forest_without_expanding_to_unknown_maps():
    snap={'party_valid':True,'party':[{'species':153,'level':13}], 'story':{'battled_rival_in_oaks_lab':True,'got_oaks_parcel':True,'got_pokedex':True}, 'battle':'none','location':{'map_id':51},'mission':'first_gym'}
    assert allowed_stages(snap)==['first_gym','review','stop']
    snap['location']['map_id']=255
    assert allowed_stages(snap)==['review','stop']


def test_gate_uses_walkable_right_hand_warp_column():
    waypoint=brock_waypoint({'map_id':50,'x':4,'y':1},progress())
    assert waypoint['controller_waypoint']=={'map_id':50,'x':5,'y':0}


def test_forest_exit_steps_beyond_border_after_reaching_warp():
    result=brock_waypoint({'map_id':51,'x':1,'y':0},progress())
    assert result['goal']=='step_out_forest' and result['controller_waypoint']['y']==-1


def test_route2_north_uses_open_border_instead_of_tree_column():
    waypoint=brock_waypoint({'map_id':13,'x':3,'y':2},progress())
    assert waypoint['controller_waypoint']=={'map_id':13,'x':8,'y':-1}
