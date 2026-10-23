"""第一道館任務：正常訓練→常磐森林→尼比市→小剛；沒有進度寫入。"""
from .navigation import _goal, _center_waypoint
from .capture_route import team_waypoint


SOURCES=['data/maps/objects/ViridianCity.asm','data/maps/objects/Route2.asm',
         'data/maps/objects/ViridianForest.asm','data/maps/objects/PewterCity.asm',
         'data/maps/objects/PewterGym.asm','scripts/PewterGym.asm']
BLOCKED={1:{(17,5),(17,9),(18,9),(6,23)},2:{(8,15),(17,25),(27,17)},
         47:{(3,2),(2,5)},50:{(8,4)},51:{(16,43),(30,33),(30,19),(2,18),(27,40),(25,11),(12,29),(1,31)},
         54:{(3,6),(7,10),(4,1)}}


def brock_waypoint(location,progress,previous_actions=(),grass_world=()):
    mid,x,y=(location[k] for k in ('map_id','x','y'))
    flags=progress['story_event_bits'];party=progress['party']
    def goal(name,target,objective='Move UP.',**kwargs):
        return _goal(name,objective,mid,target,SOURCES,**kwargs)
    if flags.get('beat_brock') is True and (progress.get('badges_raw') or 0)&1:
        return goal('first_gym_complete',None,'Wait.',waiting=True)
    if not progress['party_read_valid'] or not party:
        return goal('wait_for_valid_party',None,'Wait.',waiting=True)
    inventory=progress.get('inventory')
    balls=None if inventory is None else sum(i['quantity'] for i in inventory if i['item']==4)
    if party[0]['level']<13 and mid in {0,1,12,33,40,41,42}:
        return team_waypoint(location,flags,party,balls,previous_actions,grass_world,training=True)
    injured=any(m['hp']<m['max_hp'] or m.get('status',0) for m in party)
    low_pp=any(move and (mon.get('pp',[0]*4)[i]&63)<2 for mon in party[:1] for i,move in enumerate(mon.get('moves',[])) if move in {22,33})
    center=_center_waypoint(mid,x,y,injured or low_pp,previous_actions,SOURCES)
    if center:return center
    if mid==33:
        return goal('leave_route22_for_brock',(40,9),'Move RIGHT.')
    if mid==42:
        return goal('leave_mart_for_brock',(3,7 if y<7 else 8),'Move DOWN.')
    if mid==1:
        return goal('viridian_north_to_route2',(18,-1))
    if mid==13:
        if y>11:
            if (x,y)==(3,44):return goal('enter_forest_south_gate',(3,43))
            return goal('reach_forest_south_gate',(3,44))
        return goal('route2_north_to_pewter',(8,-1))
    if mid in {50,47}:
        # 兩格warp定義中x4上方仍是牆，實際門圖塊位於x5。
        if y>0:return goal('forest_gate_north',(5,0))
        return goal('step_out_forest_gate',(5,-1))
    if mid==51:
        if y==0 and x in {1,2}:
            return goal('step_out_forest',(x,-1))
        return goal('forest_north_exit',(1,0))
    if mid==2:
        if injured or low_pp:
            if (x,y)==(13,26):return goal('enter_pewter_center',(13,25))
            return goal('reach_pewter_center',(13,26))
        if (x,y)==(16,18):return goal('enter_pewter_gym',(16,17))
        return goal('reach_pewter_gym',(16,18))
    if mid==54:
        if (x,y)!=(4,2):return goal('reach_brock',(4,2))
        if not previous_actions or previous_actions[-1]!='up':
            return goal('face_brock',(4,1))
        return goal('challenge_brock',(4,1),'Interact using the confirm button.',interaction=True)
    return goal('unverified_brock_map',None,'Wait.',waiting=True)
