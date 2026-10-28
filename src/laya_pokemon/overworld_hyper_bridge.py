"""明示補藥 step 的新橋接候選；不修改舊 runtime／損耗閘門。"""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import re
from . import overworld_hyper as medicine

# formal 使用標準 reload；精確 stage loader 只重讀本候選，不搜尋別的來源。
if (Path(__file__).resolve().parent.name=='staged-overworld-hyper-20261028'
        and Path(medicine.__file__).resolve().parent==Path(__file__).resolve().parent):
    medicine.__spec__.loader.exec_module(medicine)
else:importlib.reload(medicine)

_CONTROLLERS=globals().get('_CONTROLLERS',{})
_BINDINGS=globals().get('_BINDINGS',{})
_OWNERS=globals().get('_OWNERS',{})
_COMPLETED=globals().get('_COMPLETED',set())
_REGISTRY_ERROR=globals().get('_REGISTRY_ERROR')
MECHANIC='overworld_hyper'


def _active():
    global _REGISTRY_ERROR
    if _REGISTRY_ERROR is not None:return None
    if (any(type(v) is not dict for v in (_CONTROLLERS,_BINDINGS,_OWNERS)) or type(_COMPLETED) is not set
            or any(type(k) is not str or not k for d in (_CONTROLLERS,_BINDINGS,_OWNERS,_COMPLETED) for k in d)
            or set(_CONTROLLERS)!=set(_BINDINGS) or set(_CONTROLLERS)!=set(_OWNERS)
            or not _COMPLETED<=set(_CONTROLLERS) or any(v is None for d in (_CONTROLLERS,_OWNERS) for v in d.values())
            or any(type(record) is not dict or set(record)!=set(('step','training_job','job_canonical','error'))
                or type(record.get('step')) is not dict or type(record.get('job_canonical')) is not str
                or record.get('error') is not None and type(record['error']) is not str for record in _BINDINGS.values())):
        _REGISTRY_ERROR='registry_shape_unverified';return None
    return (set(_CONTROLLERS)|set(_BINDINGS)|set(_OWNERS))-_COMPLETED
def _review(reason,step_id):
    record=_BINDINGS.get(step_id) if type(_BINDINGS) is dict else None
    if type(record) is dict:
        if record.get('error') is None:record['error']=reason
        reason=record['error']
    return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
        review_reason='overworld_hyper_bridge_'+reason,route_step=step_id),step_id


def applies(step_id,step):
    active=_active()
    return active is None or bool(active) or type(step) is dict and step.get('mechanic')=='overworld_hyper'


def _job(plan):
    if type(plan) is not dict:return None
    value=plan.get('training_job')
    if value is None or value in ('',{},[]):return None
    try:
        canonical=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
        if not medicine.ui._exact(json.loads(canonical),value):return None
        return deepcopy(value),canonical
    except (ValueError,TypeError,RecursionError):return None


def _step(plan,step_id):
    if type(plan) is not dict or plan.get('mode')!='league_campaign' or type(plan.get('steps')) is not list:return None
    matches=[s for s in plan['steps'] if type(s) is dict and s.get('id')==step_id]
    if len(matches)!=1:return None
    s=matches[0]
    if (set(s)!=set(('id','kind','map_id','target','mechanic','overworld_hyper_intent'))
            or type(step_id) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',step_id) is None
            or s['kind']!='interact' or type(s['map_id']) is not int
            or type(s['target']) is not list or any(type(v) is not int for v in s['target'])
            or s['mechanic']!='overworld_hyper' or not medicine._intent(s['overworld_hyper_intent'])
            or s['map_id']!=s['overworld_hyper_intent']['map_id']
            or s['target']!=s['overworld_hyper_intent']['target']):return None
    return s


def context(pyboy,state,plan,step_id,text,grid,previous,*,owned_authority=None,now=None):
    active=_active();step=_step(plan,step_id)
    if active is None:return _review(_REGISTRY_ERROR or 'registry_unverified',step_id)
    if not active and step is None:return None
    if pyboy is None:return _review('original_owner_required',step_id)
    if active and active!={step_id}:return _review('active_owner_step_changed',next(iter(active)))
    if step is None:return _review('exact_explicit_medicine_step_required',step_id)
    intent=step['overworld_hyper_intent']
    if not medicine._authority(intent,owned_authority):return _review('owned_authority_required',step_id)
    job=_job(plan)
    if job is None:return _review('explicit_canonical_training_job_required',step_id)
    if step_id in _COMPLETED:return _review('completed_step_reentered',step_id)
    record=_BINDINGS.get(step_id);c=_CONTROLLERS.get(step_id)
    if record is not None and type(record) is not dict:return _review('binding_shape_unverified',step_id)
    if record is not None and record.get('error') is not None:return _review(record['error'],step_id)
    if record is not None and (not medicine.ui._exact(record.get('training_job'),job[0]) or record.get('job_canonical')!=job[1]):
        return _review('bound_training_job_changed',step_id)
    if record is not None and (c is None or _OWNERS.get(step_id) is not pyboy or not medicine.ui._exact(record.get('step'),step)):
        return _review('original_controller_owner_or_step_changed',step_id)
    if c is not None and record is None:return _review('original_binding_missing',step_id)
    if c is not None and not medicine.ui._exact(getattr(c,'owned_authority',None),owned_authority):
        return _review('original_owned_authority_changed',step_id)
    if type(state) is not dict:return _review('state_unverified',step_id)
    if state.get('phase') in ('campaign_review','strategy_review','review'):
        return _review('preexisting_unknown_review_retained',step_id)
    frame=state.get('frame')
    if not medicine._int(frame):return _review('frame_unverified',step_id)
    if c is None:
        c=medicine.OverworldHyperController(intent,owner=pyboy,owned_authority=owned_authority)
        _CONTROLLERS[step_id]=c;_OWNERS[step_id]=pyboy
        record=dict(step=deepcopy(step),training_job=deepcopy(job[0]),job_canonical=job[1],error=None);_BINDINGS[step_id]=record
    c.__class__=medicine.OverworldHyperController
    if c.last_frame is None:actual_now=0.
    elif (not medicine._int(c.last_frame) or not medicine._clock(c.last_now) or frame<c.last_frame):return _review('original_clock_unverified',step_id)
    else:actual_now=c.last_now+(frame-c.last_frame)/60
    if now is None:now=actual_now
    elif not medicine._clock(now):return _review('explicit_clock_unverified',step_id)
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
    signal=medicine.read_observation(pyboy,frame,sdk,map_id=intent['map_id'])
    result=c.context(state,text=text,grid=grid,signal=signal,previous=previous,owner=pyboy,now=now)
    if result.get('overworld_medicine_complete') is True:
        if (c.error is not None or c.pending is not None or not c.complete or not c.receipt_ack or c.closed_frame is None
                or c.closed_frame>=frame or not medicine._closed_world(text,grid,frame,medicine._location(intent))
                or not medicine.ui._exact(state['progress'],c.after)):return _review('completion_receipt_unverified',step_id)
        _COMPLETED.add(step_id)
        ids=[s['id'] for s in plan['steps']];index=ids.index(step_id)+1
        return dict(result,field_move_complete=True,field_move_kind='overworld-hyper'),ids[index] if index<len(ids) else 'complete'
    return result,step_id


def pre_attrition_context(pyboy,state,plan,step_id,attrition,text,grid,previous):
    """只接既定補藥步驟的已知低血量；FNT／未知原 review 原樣留給父層。"""
    if (type(attrition) is not dict or attrition.get('review_reason')!='party_attrition_requires_center'
            or _step(plan,step_id) is None):return None
    party=medicine.ui._party(state.get('progress')) if type(state) is dict else None
    if party is None or len(party)!=6 or any(m['hp']<=0 or m['status']!=0 for m in party):return None
    details=attrition.get('party_attrition')
    if type(details) is not dict or details.get('fainted_party_indices')!=[]:return None
    return context(pyboy,state,plan,step_id,text,grid,previous)
