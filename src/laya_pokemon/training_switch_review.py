"""One reviewed native sendout repair; preserve the original field active clock."""
from pathlib import Path
import hashlib
import json
import time
from . import owned_field_medicine as shared

STEP='league-six-party45-game29-20261028-145-067'
JOB='league-six-party45-game29-20261028'
CAP_BYTES='eb47b12200776aaa067cd85214ef32996842dcfa4ae428c40fcb90af1ad37243'
CAP_SHA='daa8d59a0e52f015a0b59b28a58625e611e5b6f2a89580cccc1932f6d822c63a'
_CLOCKS=globals().get('_CLOCKS',{})


def _sha(data):return hashlib.sha256(data).hexdigest()
def _canonical(value):return shared.canonical_sha256(value)


def _read_capsule():
    root=Path(__file__).resolve().parents[2]
    raw=(root/'.local/wildswitch770673-reviewed-source.json').read_bytes()
    if _sha(raw)!=CAP_BYTES:raise ValueError('capsule_bytes_changed')
    cap=json.loads(raw)
    if _canonical(cap)!=CAP_SHA:raise ValueError('capsule_content_changed')
    raw=(root/'.local/wildswitch770673-runtime-diagnostic.json').read_bytes()
    if _sha(raw)!=cap['diagnostic_sha256']:raise ValueError('original_diagnostic_changed')
    diagnostic=json.loads(raw)
    if (diagnostic['controller_id']!=cap['controller_identity']
            or diagnostic['switch_id']!=cap['switch_identity']
            or _canonical(diagnostic['original_switch'])!=cap['original_switch_sha256']
            or _canonical(diagnostic['progress'])!=cap['progress_sha256']
            or _canonical(diagnostic['text'])!=cap['text_sha256']):
        raise ValueError('original_diagnostic_binding_changed')
    for label,ext in (('plan','json'),('review','json'),('state','state'),('summary','json')):
        raw=(root/f'.local/gym-reviewed-history/wildswitch770673-before-diagnostic-{label}.{ext}').read_bytes()
        if _sha(raw)!=cap['source_evidence_sha256'][label]:raise ValueError('original_source_changed')
        if label=='plan':source_plan=json.loads(raw)
    if cap['plan_bytes_sha256']!=cap['source_evidence_sha256']['plan']:
        raise ValueError('original_plan_bytes_unbound')
    return cap,source_plan


def _review(reason):
    return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
                review_reason='training_switch_source_'+reason),None


def applies(state,step_id):
    record=_CLOCKS.get(step_id)
    return (type(record) is dict and record.get('done') is False
        or step_id==STEP and state.get('frame')==770673
        and state.get('phase')=='strategy_review'
        and state.get('review_reason')=='wild_retreat_pending_observation_or_owner_changed')


def context(native,state,plan,step_id,text,*,bridge,peers):
    """No keys: first migration returns WAIT without replaying the old field packet."""
    opening=(step_id==STEP and state.get('frame')==770673
        and state.get('phase')=='strategy_review'
        and state.get('review_reason')=='wild_retreat_pending_observation_or_owner_changed')
    record=_CLOCKS.get(step_id)
    if record is None and not opening:return None,None
    if type(record) is dict and record.get('done') is True:return None,None
    try:
        if (type(peers) is not dict or set(peers)!=shared.PEER_NAMES
                or any(type(v) is not set or v!=({step_id} if k=='league_training_batch' else set())
                       for k,v in peers.items()) or bridge._active()!={step_id}):
            raise ValueError('original_peers_unverified')
        c=bridge._CONTROLLERS.get(step_id);binding=bridge._BINDINGS.get(step_id)
        if (c is None or c.error is not None or c.complete is not False
                or bridge._OWNERS.get(step_id) is not native or plan.get('training_job')!=JOB
                or native.frame_count!=state.get('frame')):
            raise ValueError('original_field_owner_changed')
        if record is not None:
            if (type(record) is not dict or record['controller'] is not c or record['native'] is not native
                    or record['binding'] is not binding or record['baseline'] is not c.baseline
                    or _canonical(plan)!=record['plan_sha']):
                raise ValueError('original_clock_binding_changed')
            return None,shared.frame_clock(c,state['frame'])
        cap,source_plan=_read_capsule()
        source=cap['original_field']
        if (plan!=source_plan or step_id!=cap['original_step_id'] or id(c)!=cap['controller_identity']
                or state.get('location')!=cap['source_location']
                or _canonical(state.get('progress'))!=cap['progress_sha256']
                or _canonical(text)!=cap['text_sha256'] or time.time()>=cap['original_deadline']
                or binding!=(bridge.MECHANIC,bridge._canonical(plan['steps'][-1]),JOB)
                or c.calls>=bridge.batch.MAX_CALLS
                or not 0<=c.last_now-c.started<bridge.batch.MAX_SECONDS):
            raise ValueError('original_source_or_budget_changed')
        for key,value in source.items():
            if _canonical(getattr(c,key))!=_canonical(value):raise ValueError('original_spent_or_packet_changed')
        from . import battle
        pending=battle._wild_retreat_switch
        if id(pending)!=cap['switch_identity'] or _canonical(pending)!=cap['original_switch_sha256']:
            raise ValueError('original_switch_changed')
        # Prepare the tether before mutating the child.  Its wall-clock job keeps
        # charging engineering review; only the original field uses new frames.
        clock=dict(controller=c,native=native,binding=binding,baseline=c.baseline,
            original_switch=pending,plan_sha=_canonical(plan),source_spent=dict(source),done=False)
        hint=battle.review_wild_switch770673(native,text,state['battle_state'],state['progress']['party'],cap,
            expected_capsule_sha256=CAP_SHA,original_pending=pending)
        if hint is None:raise ValueError('named_switch_migration_rejected')
        _CLOCKS[step_id]=clock
        return hint,None
    except (OSError,KeyError,TypeError,ValueError,AttributeError,IndexError):
        return _review('evidence_or_handoff_unverified')


def finish(native,step_id,frame,*,bridge):
    record=_CLOCKS.get(step_id)
    if record is None:return True
    c=bridge._CONTROLLERS.get(step_id)
    if (type(record) is not dict or record['native'] is not native or record['controller'] is not c
            or record['baseline'] is not c.baseline or c.error is not None
            or c.complete is not True or step_id not in bridge._COMPLETED):return False
    record['done']=True;record['completed_frame']=frame
    record['final_spent']=dict(calls=c.calls,waits=c.waits,requests=c.requests,
        displacements=c.displacements,started=c.started,last_now=c.last_now)
    return True
