from copy import deepcopy
from hashlib import sha256
import importlib.util
from pathlib import Path
import pytest
from test_route23_land_guards import Guard,BridgeGuard,pure,bridge,page,partial,review,assert_action,bridge_env

HERE=Path(__file__).resolve().parent
if HERE.name=='staged-route23-guard-eventfix-20261028' and HERE.parent.name=='.local':
 LEGACY=HERE/'original-route23_land_guards.py'
elif HERE.name=='tests':LEGACY=HERE/'fixtures/route23_guard_event_legacy.py'
else:raise RuntimeError('Only exact source stage or formal test fixture path is allowed')
spec=importlib.util.spec_from_file_location('laya_pokemon._original_guard_event_order',LEGACY)
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)

def capsule():
 return dict(kind='route23_land_guard_event_order_resume_v1',step_id='league27-cascade-guard',case='cascade',source_frame=41073,
  source_commit=pure.SOURCE_COMMIT,source_review_sha256='a'*64,source_steps_sha256='b'*64,step_sha256='c'*64,job_sha256='d'*64)

def to_page2(s):
 assert_action(s.call(page(s.case,0)),'a')
 assert_action(s.call(page(s.case,1),('a',)),'a')
 assert_action(s.call(page(s.case,2),('a',)),'a')

@pytest.mark.parametrize('case',tuple(pure.CASES))
@pytest.mark.parametrize('script',(0,2))
def test_real_source_own_event_after_page2_a_before_done_offer_still_requires_true_final_a(case,script):
 s=Guard(case);to_page2(s);s.flags|=1<<s.spec['bit']
 assert_action(s.call(page(case,3),('a',),script=script),'wait')
 assert s.c.event_seen is True and s.c.flags != s.flags and s.c.final_ack is False
 assert_action(s.call(page(case,3),script=script),'a')
 pending=s.c.pending
 assert_action(s.call(page(case,3),script=script),'a')
 assert s.c.pending is pending and pending['executed'] is False
 assert_action(s.call(prev=('a',),script=0),'wait')
 assert s.call()['route23_land_guard_complete'] is True

@pytest.mark.parametrize('case',tuple(pure.CASES))
def test_event_during_source_done_prefix_waits_for_two_full_frames_and_never_auto_closes(case):
 s=Guard(case);to_page2(s);s.flags|=1<<s.spec['bit'];rows=page(case,3)
 rows[16][1:18]=list('GO R'+' '*13)
 assert_action(s.call(rows,('a',),script=2),'wait')
 assert s.c.page==3 and s.c.done_frame is None and s.c.final_ack is False
 assert_action(s.call(page(case,3),script=2),'wait')
 assert_action(s.call(page(case,3),script=2),'a')

@pytest.mark.parametrize('fault',('before_page2_a','foreign_bit','unknown','done_arrow','script2_no_event','event_regression'))
def test_source_event_exception_is_narrow_and_unknown_errors_stay_sticky(fault):
 s=Guard();to_page2(s);s.flags|=1;rows=page('cascade',3);prev=('a',);script=2
 if fault=='before_page2_a':prev=('wait',)
 elif fault=='foreign_bit':s.flags|=64
 elif fault=='unknown':rows[14][1]='X'
 elif fault=='done_arrow':rows=page('cascade',3,True)
 elif fault=='script2_no_event':s.flags=0
 elif fault=='event_regression':
  assert_action(s.call(rows,prev,script=2),'wait');s.flags=0
 reason=review(s.call(rows,prev,script=script))
 assert review(s.call(page('cascade',3),script=2))==reason

def stalled_legacy(s=None):
 s=Guard() if s is None else s;s.f=40513
 # Use only this original controller to reproduce the actual source page/frame path.
 if isinstance(s,BridgeGuard):
  s.step_id='league27-cascade-guard';s.step['id']=s.step_id
  s.c=legacy.Route23LandGuardController()
  bridge._CONTROLLERS[s.step_id]=s.c
  bridge._BINDINGS[s.step_id]=(bridge._canonical(s.step),bridge._canonical(s.plan['training_job']))
 else:s.c=legacy.Route23LandGuardController()
 def native(rows=None,prev=('wait',),script=0):
  if isinstance(s,BridgeGuard):
   # The live old bridge/pure both have the original class; avoid its automatic reload reassignment here.
   old_dispatch=s.dispatch;s.dispatch=lambda st,args,pb:s.c.context(st,**args)
   try:return s.call(rows,prev,script=script)
   finally:s.dispatch=old_dispatch
  return s.call(rows,prev,script=script)
 native();native(partial());native(partial())
 native(page('cascade',0));native(page('cascade',1,False),('a',));native(page('cascade',1))
 native(page('cascade',2,False),('a',));native(page('cascade',2,False));native(page('cascade',2,False));native(page('cascade',2,False))
 native(page('cascade',2))
 rows=page('cascade',3);rows[14]=list(' OK THEN'+' '*12);rows[16]=list(' '*20)
 native(rows,('a',))
 rows=page('cascade',3);rows[16][1:18]=list('GO R'+' '*13)
 native(rows);s.flags=1;r=native(page('cascade',3),script=2)
 assert s.f==41073 and r['review_reason']=='route23_land_guard_event_before_final_actual_a'
 if isinstance(s,BridgeGuard):bridge._ERRORS[s.step_id]=s.c.error
 return s

def restore(s,cap=None):
 s.c.__class__=pure.Route23LandGuardController
 st,args=deepcopy(s.last)
 return s.c.restore_reviewed_event_order(st,grid=args['grid'],signal=args['signal'],movement=args['movement'],previous=args['previous'],capsule=capsule() if cap is None else cap)

def test_named41073_repair_keeps_same_owner_baseline_clock_counters_and_error_history_then_real_closure():
 s=stalled_legacy();c=s.c;fp=c.fingerprint;packet=c.last_packet
 before=(c.calls,c.waits,c.started,c.last_now,c.last_frame,c.flags,c.expected_flags,c.pending)
 r=restore(s);assert r['available_actions']==['wait'] and c.error is None
 assert s.c is c and c.fingerprint is fp and c.last_packet is packet
 assert (c.calls,c.waits,c.started,c.last_now,c.last_frame,c.flags,c.expected_flags,c.pending)==before
 assert c.reviewed_error_history[0]['error']=='route23_land_guard_event_before_final_actual_a'
 assert c.reviewed_error_history[0]['final_a_fabricated'] is False and c.final_ack is False
 assert_action(s.call(page('cascade',3),script=2),'wait')
 assert_action(s.call(page('cascade',3),script=2),'a')
 assert_action(s.call(prev=('a',)),'wait')
 assert s.call()['route23_land_guard_complete']

@pytest.mark.parametrize('fault',('error','frame','case','step','commit','review_sha','steps_sha','pending','baseline','counter','clock','flags','foreign_signal','text','previous'))
def test_named_repair_rejects_every_other_error_capsule_owner_or_source_packet(fault):
 s=stalled_legacy();cap=capsule()
 if fault=='error':s.c.error='route23_land_guard_unknown'
 elif fault=='frame':cap['source_frame']-=40
 elif fault in ('case','step','commit'):cap[{'case':'case','step':'step_id','commit':'source_commit'}[fault]]='unknown'
 elif fault in ('review_sha','steps_sha'):cap['source_'+fault+'256']='invalid'
 elif fault=='pending':s.c.pending={'frame':41033,'executed':False}
 elif fault=='baseline':s.c.fingerprint['money']-=1
 elif fault=='counter':s.c.calls=241
 elif fault=='clock':s.c.last_now=s.c.started+61
 elif fault=='flags':s.c.flags=1
 elif fault=='foreign_signal':s.last[1]['signal']['guard_flags']=65
 elif fault=='text':s.last[0]['text']['cells'][14][1]='X'
 elif fault=='previous':s.last[1]['previous']=('a',)
 before=deepcopy(s.c.__dict__);assert restore(s,cap) is None;assert s.c.__dict__==before

def test_repair_capsule_cannot_clear_second_unknown_error_or_be_reused():
 s=stalled_legacy();assert restore(s) is not None
 s.c.error='route23_land_guard_unknown_second';before=deepcopy(s.c.__dict__)
 assert restore(s) is None and s.c.__dict__==before

def test_bridge_real_readers_validate_capsule_binding_repair_existing_owner_then_freshframes(bridge_env):
 s=stalled_legacy(BridgeGuard(bridge_env));c=s.c;cap=capsule()
 cap['step_sha256']=sha256(bridge._canonical(s.step).encode()).hexdigest()
 cap['job_sha256']=sha256(bridge._canonical(s.plan['training_job']).encode()).hexdigest()
 s.plan['route23_guard_event_review']=cap
 before=(c.calls,c.waits,c.started,c.last_now,c.last_frame)
 s.env.clock['now']=1000.0  # Long engineering pause is not a fresh controller budget.
 st,args=deepcopy(s.last);result,nextid=bridge.context(s.pb,st,s.plan,s.step_id,st['text'],args['grid'],args['previous'])
 assert result['available_actions']==['wait'] and nextid==s.step_id
 assert bridge._CONTROLLERS[s.step_id] is c and s.step_id not in bridge._ERRORS
 assert (c.calls,c.waits,c.started,c.last_now,c.last_frame)==before
 assert bridge._REVIEWED_ERRORS[s.step_id][0]['error']=='route23_land_guard_event_before_final_actual_a'
 assert_action(s.call(page('cascade',3),script=2),'wait')
 assert c.started==before[2] and c.calls==before[0]+1
 assert c.last_now==pytest.approx(before[3]+40/60) and c.last_frame==before[4]+40
 assert_action(s.call(page('cascade',3),script=2),'a')
 assert_action(s.call(prev=('a',)),'wait')
 r=s.call();assert r['field_move_complete'] is True and s.next_id=='after-guard'
