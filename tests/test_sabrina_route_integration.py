"""同圖傳送一定經專用觀測閘門，不能在來源墊當普通move提前完成。"""
from copy import deepcopy
import pytest
from laya_pokemon import campaign_route as route


def step():
    return dict(id='native-pad20',kind='move',map_id=178,target=[11,15],
                mechanic='sabrina_native_warp',landing=[19,17],offpad=[18,17])


def state(pos):
    return dict(frame=100,location=dict(map_id=178,x=pos[0],y=pos[1]),
                progress=dict(party=[],story_event_bits={}))


def test_source_pad_is_not_plain_move_complete(monkeypatch):
    seen=[];hint=dict(phase='campaign_review',available_actions=['wait'],review_reason='unarmed')
    monkeypatch.setattr(route,'native_warp_context',lambda *args:seen.append(args) or hint)
    s=state([11,15]);st=step();p=dict(steps=[st])
    result,sid=route.waypoint(None,s,p,st['id'],['wait'])
    assert result==hint and sid==st['id'] and seen[0][1:]==(s,st,['wait'])


def test_native_wait_stays_on_same_step(monkeypatch):
    hint=dict(phase='overworld',available_actions=['wait'],objective='Wait.',native_warp_complete=False)
    monkeypatch.setattr(route,'native_warp_context',lambda *args:hint)
    st=step();result,sid=route.waypoint(None,state([19,17]),dict(steps=[st]),st['id'],['up'])
    assert result==hint and sid==st['id']


def test_only_verified_offpad_completion_advances(monkeypatch):
    monkeypatch.setattr(route,'native_warp_context',lambda *args:dict(native_warp_complete=True))
    st=step();tail=dict(id='closed-checkpoint',kind='move',map_id=178,target=[18,17])
    result,sid=route.waypoint(None,state([18,17]),dict(steps=[st,tail]),st['id'],['left'])
    assert sid=='complete' and result['review_reason']=='route_extension_required'


def test_far_unbound_none_uses_existing_navigation_without_advancing(monkeypatch):
    monkeypatch.setattr(route,'native_warp_context',lambda *args:None)
    monkeypatch.setattr(route,'read_world_grid',lambda *args:{'walkable':[[1]]})
    monkeypatch.setattr(route.world_map,'read_npc_obstacles',lambda *args,**kwargs:None)
    monkeypatch.setattr(route,'world_direction',lambda *args:dict(direction='right'))
    st=step();before=deepcopy(st)
    result,sid=route.waypoint(None,state([8,16]),dict(steps=[st]),st['id'],[])
    assert result['objective']=='Move RIGHT.' and sid==st['id'] and st==before


@pytest.mark.parametrize('key,value',[('next_map',178),('terminal',True),('event','done'),
                                    ('item',1),('badge',1),('await_script_event',True)])
def test_generic_completion_never_skips_native_controller(key,value,monkeypatch):
    monkeypatch.setattr(route,'native_warp_context',lambda *args:pytest.fail('invalid intent must stop first'))
    st={**step(),key:value};s=state([8,16])
    s['progress'].update(story_event_bits={'done':True},inventory=[{'item':1}],badges_raw=1)
    result,sid=route.waypoint(None,s,dict(steps=[st]),st['id'],[])
    assert result['review_reason']=='sabrina_native_warp_generic_completion_forbidden' and sid==st['id']


def test_field_dispatch_defers_native_warp_without_using_generic_transaction(monkeypatch):
    monkeypatch.setattr(route.campaign_transactions,'applies',lambda *args:pytest.fail('native is not an interact transaction'))
    assert route.field_context(None,state([11,16]),dict(steps=[step()]),step()['id']) is None
