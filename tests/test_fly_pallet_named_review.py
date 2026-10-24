from copy import deepcopy
import pytest
from laya_pokemon import fly_pallet_bridge as b
from laya_pokemon import fly_pallet as fly
from tests.test_fly_pallet import Session, MAP_ROWS
from tests.test_hm_teaching import packet


def migration():
 s=Session();s.to_destination()
 # The real complete raw map was visible through the window layer.
 s.call(MAP_ROWS,window=True,raw=list(fly.PALLET_RAW))
 c=s.c;c.error='fly_pallet_not_exact_initial_pallet_destination';c.stage='destination'
 c.last_frame=1442553;c.last_now=12.;c.started=10.;c.destination_frame=None
 c.pending=dict(executed=True,action='a',stage='destination')
 text=packet(MAP_ROWS,True)
 sig=fly.read_fly_observation(s.pb,s.pb.frame_count,__import__('tests.test_fly_pallet',fromlist=['CONSTANTS']).CONSTANTS)
 sig['observation_frame']=1442553
 state=dict(frame=1442553,location=deepcopy(fly.START),progress=s.p)
 return c,dict(reviewed_fly_ui_revision=1),state,text,sig


def test_review_preserves_baseline_pending_and_used_budget():
 c,step,state,t,sig=migration();base=c.baseline;pending=c.pending;calls=c.calls;waits=c.waits
 assert b._review_native_map_window(c,step,state,t,sig,112.)
 assert c.error is None and c.baseline is base and c.pending is pending
 assert c.started==110. and c.last_now==12. and c.calls==calls and c.waits==waits
 assert b._review_native_map_window(c,step,state,t,sig,113.) and c.started==110.


@pytest.mark.parametrize('kind',['frame','revision','location','error','stage','raw','window','party','executed'])
def test_named_review_rejects_any_other_pause_or_evidence(kind):
 c,step,state,t,sig=migration()
 if kind=='frame':state['frame']-=1
 elif kind=='revision':step['reviewed_fly_ui_revision']=True
 elif kind=='location':state['location']['x']+=1
 elif kind=='error':c.error='fly_pallet_other_failure'
 elif kind=='stage':c.stage='party'
 elif kind=='raw':sig['raw_bytes'][100]^=1
 elif kind=='window':sig['window_visible']=False
 elif kind=='party':state['progress']['party'][0]['hp']-=1
 elif kind=='executed':c.pending['executed']=False
 error=c.error;started=c.started
 assert not b._review_native_map_window(c,step,state,t,sig,112.)
 assert c.error==error and c.started==started
