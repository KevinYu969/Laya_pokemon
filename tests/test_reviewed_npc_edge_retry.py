from copy import deepcopy
import pytest
from laya_pokemon import campaign_route as route


@pytest.fixture
def env(monkeypatch):
    edge=((10,4),(10,3));other=((1,1),(1,2))
    monkeypatch.setattr(route,'_LEARNED_EDGES',{45:{edge,other}})
    monkeypatch.setattr(route,'_REVIEWED_NPC_EDGE_RETRIES',set())
    monkeypatch.setattr(route,'_LAST_ATTEMPT',None)
    state=dict(frame=68641,location=dict(map_id=45,x=10,y=4))
    step=dict(id='reviewed-source-walk',kind='move',map_id=45,
        reviewed_npc_edge_retry=dict(kind='trainer_reset_after_normal_exit_v1',frame=68641,**{'from':[10,4],'to':[10,3]}))
    grid=dict(observation_frame=68641,verified_location=[45,10,4],screen_cells_verified=90,walkable=[[1]*20 for _ in range(18)])
    npcs=dict(source_anchor_matches=11,positions=[(10,1),(13,5)])
    return state,step,grid,npcs,edge,other


def test_only_reviewed_transient_edge_is_retired_once_without_input_or_packet_changes(env):
    state,step,grid,npcs,edge,other=env;before=deepcopy((state,step,grid,npcs))
    assert route._reviewed_npc_edge_retry(state,step,grid,npcs,True) is None
    assert route._LEARNED_EDGES[45]=={other} and (state,step,grid,npcs)==before
    route._LEARNED_EDGES[45].add(edge)
    assert route._reviewed_npc_edge_retry(state,step,grid,npcs,True) is None
    assert edge in route._LEARNED_EDGES[45]  # no repeated automatic clearing


@pytest.mark.parametrize('fault',['frame','map','location','ready','gridframe','anchors','npc','reset','wall','shape','marker'])
def test_wrong_or_still_blocked_scene_preserves_entire_navigation_cache(env,fault):
    state,step,grid,npcs,edge,other=env;ready=True
    if fault=='frame':state['frame']+=1
    elif fault=='map':step['map_id']=166
    elif fault=='location':state['location']['x']=9
    elif fault=='ready':ready=False
    elif fault=='gridframe':grid['observation_frame']+=1
    elif fault=='anchors':npcs['source_anchor_matches']=8
    elif fault=='npc':npcs['positions'].append((10,3))
    elif fault=='reset':npcs['positions'].remove((10,1))
    elif fault=='wall':grid['walkable'][3][10]=0
    elif fault=='shape':grid['walkable']=[]
    else:step['reviewed_npc_edge_retry']['frame']=True
    before=deepcopy(route._LEARNED_EDGES)
    assert route._reviewed_npc_edge_retry(state,step,grid,npcs,ready) is not None
    assert route._LEARNED_EDGES==before and not route._REVIEWED_NPC_EDGE_RETRIES
