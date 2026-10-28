"""Source event order only; synthetic readonly observations, no game or API."""
from copy import deepcopy
import importlib
from pathlib import Path
import sys
import pytest
import laya_pokemon

HERE=Path(__file__).resolve().parent
if HERE.name=='staged-route23-water-order-20261028' and HERE.parent.name=='.local':
 ROOT=HERE.parent.parent
 laya_pokemon.__path__.insert(0,str(HERE))
 sys.path.insert(0,str(ROOT/'tests'))
elif HERE.name=='tests':ROOT=HERE.parent
else:raise RuntimeError('Only exact stage or formal tests may load this source contract')
from laya_pokemon import route23_water as water
importlib.reload(water)
from test_route23 import Water,guard_rows,review
assert Path(water.__file__).resolve()==(HERE/'route23_water.py' if HERE.name!='tests' else ROOT/'src/laya_pokemon/route23_water.py').resolve()

def begin_guard(point):
 s=Water();idx=next(i for i,n in enumerate(water.PATH) if n[1:3]==point)
 s.to(idx-1);bit,badge=water.GUARDS[point]
 r=s.call(idx,('up',),rows=guard_rows(badge,0));assert r['available_actions']==['a','wait']
 assert s.call(idx,('a',),rows=guard_rows(badge,1))['available_actions']==['a','wait']
 assert s.call(idx,('a',),rows=guard_rows(badge,2))['available_actions']==['a','wait']
 return s,idx,bit,badge

@pytest.mark.parametrize('point',tuple(water.GUARDS))
@pytest.mark.parametrize('script',(0,2))
def test_own_bit_before_final_offer_keeps_true_final_a_and_two_closed_worlds(point,script):
 s,idx,bit,badge=begin_guard(point);c=s.c;pending=c.pending;g=c.guard;started=c.started;oldflags=c.flags
 s.flags|=1<<bit
 r=s.call(idx,('a',),rows=guard_rows(badge,3,False),script=script)
 assert r['available_actions']==['wait'] and c.guard is g and c.pending is pending
 assert c.flags==oldflags and g['event_seen'] is True and not r['route23_water_complete']
 r=s.call(idx,rows=guard_rows(badge,3,False),script=script);assert r['available_actions']==['a','wait']
 offered=g['pending'];assert offered['executed'] is False
 assert s.call(idx,rows=guard_rows(badge,3,False),script=script)['available_actions']==['a','wait']
 assert g['pending'] is offered and offered['executed'] is False and c.flags==oldflags
 assert s.call(idx,('a',),script=2)['available_actions']==['wait']
 assert c.guard is g and c.pending is pending and g['closed_frame'] is None
 assert s.call(idx)['available_actions']==['wait'] and c.guard is g
 r=s.call(idx);assert c.guard is None and c.index==idx and c.flags==s.flags
 assert c.started==started and c.error is None and not r['route23_water_complete']

@pytest.mark.parametrize('point',tuple(water.GUARDS))
def test_known_done_prefix_with_native_event_waits_without_offering_a(point):
 s,idx,bit,badge=begin_guard(point);s.flags|=1<<bit
 rows=guard_rows(badge,3,False);rows[16][1:18]=list('go r'+' '*13)
 assert s.call(idx,('a',),rows=rows,script=2)['available_actions']==['wait']
 assert s.c.guard['page']==3 and s.c.guard['done_frame'] is None
 assert s.call(idx,rows=guard_rows(badge,3,False),script=2)['available_actions']==['wait']
 assert s.call(idx,rows=guard_rows(badge,3,False),script=2)['available_actions']==['a','wait']

@pytest.mark.parametrize('fault',('no_page2_a','foreign_bit','unknown_final','done_arrow','script2_no_event','blank_before_final_a','regression','changed_party','same_frame_event'))
def test_event_order_exception_never_hides_foreign_unknown_or_unexecuted_page(fault):
 s,idx,bit,badge=begin_guard((10,96));pending=s.c.pending;g=s.c.guard
 s.flags|=1<<bit;rows=guard_rows(badge,3,False);prev=('a',);script=2;changes={}
 if fault=='no_page2_a':prev=('wait',)
 elif fault=='foreign_bit':s.flags|=64
 elif fault=='unknown_final':rows[14][1]='X'
 elif fault=='done_arrow':rows=guard_rows(badge,3,True)
 elif fault=='script2_no_event':s.flags&=~(1<<bit)
 elif fault=='blank_before_final_a':rows=None
 elif fault=='regression':
  assert s.call(idx,prev,rows=rows,script=2)['available_actions']==['wait'];s.flags&=~(1<<bit)
 elif fault=='changed_party':s.p['party'][0]['hp']-=1
 elif fault=='same_frame_event':changes['same']=True
 r=s.call(idx,prev,rows=rows,script=script,**changes);review(r);reason=r['review_reason']
 assert s.c.pending is pending and s.c.guard is g and not r['route23_water_complete']
 r=s.call(idx,rows=guard_rows(badge,3,False),script=2);review(r);assert r['review_reason']==reason

@pytest.mark.parametrize('fault',('unknown','arrow','foreign','regression'))
def test_final_actual_a_does_not_hide_unknown_done_page_or_event_regression(fault):
 s,idx,bit,badge=begin_guard((10,96));s.flags|=1<<bit
 s.call(idx,('a',),rows=guard_rows(badge,3,False),script=2)
 s.call(idx,rows=guard_rows(badge,3,False),script=2)
 rows=guard_rows(badge,3,fault=='arrow')
 if fault=='unknown':rows[14][1]='X'
 elif fault=='foreign':s.flags|=64
 elif fault=='regression':s.flags&=~(1<<bit)
 review(s.call(idx,('a',),rows=rows,script=2))
 assert s.c.guard is not None and s.c.flags==7

def test_source_order_fix_preserves_step_budget_call_clock_pending_and_error_on_reload():
 s,idx,bit,badge=begin_guard((10,96));s.flags|=1<<bit
 s.call(idx,('a',),rows=guard_rows(badge,3,False),script=2)
 c=s.c;pending=c.pending;g=c.guard;before=(c.started,c.step_started,c.excluded,c.step_excluded,c.calls,c.last_now)
 importlib.reload(water);c.__class__=water.Route23WaterController
 assert s.c is c and c.pending is pending and c.guard is g
 assert (c.started,c.step_started,c.excluded,c.step_excluded,c.calls,c.last_now)==before
 r=s.call(idx,rows=guard_rows(badge,3,False),script=2,now=c.step_started+61)
 review(r);assert r['review_reason']=='route23_water_step_time_budget_exhausted'
 assert c.pending is pending and c.guard is g and c.started==before[0] and c.step_started==before[1]
 r=s.call(idx,rows=guard_rows(badge,3,False),script=2);review(r)
 assert r['review_reason']=='route23_water_step_time_budget_exhausted'
