"""固定公開1F OFF 840格預載畫面反例；不需ROM、outputs或真按鍵。"""
import base64,zlib
from copy import deepcopy
import pytest
from laya_pokemon import mansion_native_landing as land
from tests.test_mansion_native_landing import env,call

# a536711 1F blk/bst + 四個OFF門替換，逐格對照真預載封包零差。
_DATA='eJyFU0sKgzAQxTOU0oTSdRez7kMa3Eh7gdz/MJ1PfsZoR1Dj431mYuh9UkTTSREBKCtfLi1UdCAi6JOfj9cWJTY1dOHV59uhmcv3eadMOZWGSR9Y0LnAqqFBVUXSUXmXJKKcGtfkDcpJzNevlxiz+iwprElYqjXGmMPoKFrUC1qSJe2aKnGpjl/QYLuQuTUTyiQb7kZ1Kpk33GZoA27gecke7H2vWqYO9L43LW31wLdxH/h26MB3zE2+9zG3lu3oke9/FJC/SNDQHRLAOeAH8QhPJw=='

def grid(e):
 raw=zlib.decompress(base64.b64decode(_DATA));assert len(raw)==840
 tiles=[list(raw[y*30:(y+1)*30]) for y in range(28)]
 cells=[[x,y] for y in range(8,13) for x in range(3,8)]
 return dict(source='wOverworldMap C6E8 / map header D368-D369 / tileset D52B-D535; fixed Red ROM',
   tileset_id=22,observation_frame=e.frame+40,verified_location=[214,5,10],tiles=tiles,
   walkable=[[int(t in land._FACILITY_COLL) for t in row] for row in tiles],
   screen_cells_verified=len(cells),visible_verified_cells=cells)


def test_exact_old_whole_map_can_only_wait_then_fresh_real_exit_completes(env):
 e=env;e.p.setdefault('story_event_bits',{})['mansion_switch_on']=False
 before=grid(e)
 first=call(e,grid=before);assert first[0]['phase']=='overworld' and not first[0]['field_move_complete']
 record=land._CONTROLLERS['native2'];base=record['baseline'];started=record['started']
 before['observation_frame']+=40
 second=call(e,grid=before);assert second[0]['phase']=='overworld' and not second[0]['field_move_complete']
 assert record['baseline'] is base and record['started']==started
 e.pos=(5,11)
 assert not call(e)[0]['field_move_complete']
 assert call(e)[0]['field_move_complete']


@pytest.mark.parametrize('what',['one_tile','one_walk','flag_true','flag_unknown','other_map','other_pos','oldframe','wrongsource','badcell'])
def test_old_map_whitelist_never_accepts_a_similar_or_unknown_handoff(env,what):
 e=env;e.p.setdefault('story_event_bits',{})['mansion_switch_on']=False
 g=grid(e);frame=e.frame+40;loc=dict(map_id=214,x=5,y=10)
 if what=='one_tile':g['tiles'][0][0]^=1
 elif what=='one_walk':g['walkable'][0][0]^=1
 elif what=='flag_true':e.p['story_event_bits']['mansion_switch_on']=True
 elif what=='flag_unknown':e.p['story_event_bits']['mansion_switch_on']=None
 elif what=='other_map':loc['map_id']=215
 elif what=='other_pos':loc['y']=11
 elif what=='oldframe':g['observation_frame']-=1
 elif what=='wrongsource':g['source']='unverified'
 elif what=='badcell':g['visible_verified_cells'][0]=[30,0]
 assert not land._known_preload(g,frame,loc,e.p)


def test_complete_source_2f_off_preload_at_3f_is_wait_only(env):
 e=env;e.map_id=215;e.pos=(6,1)
 e.step.update(map_id=215,target=[6,2],landing_pad=[6,1])
 e.p.setdefault('story_event_bits',{})['mansion_switch_on']=False
 g=grid(e);raw=zlib.decompress(base64.b64decode('eJylkk0KgzAQhXkHcCEiWoo7oYtZG4qhi4LusrD3v0zfmJhYU6HQJ85IvsxfjIxBsrN0RaFOjKoCBCpv6Zzj8kp367TdAFh+flC70WlGkFLsFTKHkCO146gmUpo7ny0KMZgbVnrhc05jxVo4ZdtqZj+2bKfBemik20LDRLgBV1TrYh1pyCd4pGqNuCP13sRmTihbUKodGD+6SMG/wTNTakyMNWsnIs45fKMpc5gdeJZluSTZnO6ldVlZ/Gll1KlwRtMpn1Pr35x2A29S7zfldJp5k/o/6v5Al+V1oHZMKjO9ATp9TOc='))
 g.update(verified_location=[215,6,1],tiles=[list(raw[y*30:(y+1)*30]) for y in range(28)])
 g['walkable']=[[int(t in land._FACILITY_COLL) for t in row] for row in g['tiles']]
 g['visible_verified_cells']=[[x,y] for y in range(5) for x in range(4,9)]
 out=call(e,grid=g);assert out[0]['phase']=='overworld' and not out[0]['field_move_complete']
 e.pos=(6,2)
 assert not call(e)[0]['field_move_complete']
 assert call(e)[0]['field_move_complete']


@pytest.mark.parametrize('container',[None,[],False,'unknown'])
def test_unknown_event_container_is_never_false_or_an_exception(env,container):
 e=env;e.p['story_event_bits']=container
 assert not land._known_preload(grid(e),e.frame+40,dict(map_id=214,x=5,y=10),e.p)


def scripted(e):
 e.map_id=215;e.pos=(6,1);e.step.update(map_id=215,target=[6,2],landing_pad=[6,1])
 e.plan['steps'].insert(0,dict(id='source-stair',kind='move',map_id=214,target=[6,1],next_map=215))
 e.p.setdefault('story_event_bits',{})['mansion_switch_on']=False
 e.memory.values.update({0xCD6B:0xFC,0xD736:2,0xCFC5:2})
 e.text.update(read_valid=False,alignment_verified=False,read_error='visible_tile_alignment_incomplete')
 return e


def test_initial_known_native_door_control_only_waits_for_unknown_display(env):
 e=scripted(env)
 out=call(e,grid=None);assert out[0]['phase']=='overworld' and not out[0]['field_move_complete']
 e.pos=(6,2);e.memory.values.update({0xCD6B:0,0xD736:0,0xCFC5:0})
 e.text.update(read_valid=True,alignment_verified=True,read_error=None)
 assert not call(e)[0]['field_move_complete']
 assert call(e)[0]['field_move_complete']


@pytest.mark.parametrize('change',['prior_map','prior_target','prior_missing','mask','exiting','counter','error','text','flag'])
def test_initial_unknown_display_without_exact_source_door_evidence_reviews(env,change):
 e=scripted(env)
 if change=='prior_map':e.plan['steps'][0]['map_id']=165
 elif change=='prior_target':e.plan['steps'][0]['target']=[7,10]
 elif change=='prior_missing':e.plan['steps'].pop(0)
 elif change=='mask':e.memory.values[0xCD6B]=0
 elif change=='exiting':e.memory.values[0xD736]=0
 elif change=='counter':e.memory.values[0xCFC5]=0
 elif change=='error':e.text['read_error']='other_unknown'
 elif change=='text':e.text['lines']=['unknown']
 elif change=='flag':e.p['story_event_bits']['mansion_switch_on']=None
 out=call(e,grid=None);assert out[0]['phase']=='campaign_review' and not land._BINDINGS
