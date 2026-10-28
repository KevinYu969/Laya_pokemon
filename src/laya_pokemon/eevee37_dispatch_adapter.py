"""Trusted caller/normal-dispatch evidence only; never dispatches or ticks itself."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import inspect
import json
from pathlib import Path
import types

JOB='league-six-party45-game29-20261028'
CONTROLLER_SHA='fb5e201c98a2fa232db53429b517e317aaea99152782aaa7aeaefafb16699279'
PROOF_SHA='f33f570c020cd69961f93189d81af080d5b042bedff3296576f430c780e9b509'
ADVANCE_SOURCE_SHA='2abb30c4b934d5ebac58ebc6b1a9f06160bfd32acb5ea6657a3f72508e466226'
_ORIGINAL_NAME='_eevee37_dispatch_original'
_CALLBACK_NAME='_eevee37_dispatch_callback'
_CONTEXT=globals().get('_CONTEXT')
_REQUEST=globals().get('_REQUEST')
_HOOK=globals().get('_HOOK')
_ERROR=globals().get('_ERROR')


def _sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
        ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()


def _fail(reason):
    global _ERROR,_REQUEST
    _ERROR=_ERROR if type(_ERROR) is str and _ERROR else 'eevee37_dispatch_'+reason
    _REQUEST=None
    return False


def review_context():
    if _ERROR is None:return None
    return dict(phase='strategy_review',objective='Wait.',available_actions=['wait'],
                review_reason=_ERROR if type(_ERROR) is str and _ERROR else 'eevee37_dispatch_registry_unverified')


def _validate_context():
    c=_CONTEXT
    if type(c) is not dict:raise ValueError('trusted_context_missing')
    b=c['bridge'];key=c['step_id'];controller=c['controller'];p=c['plan']
    if (type(controller).__name__!='TrainingBatch'
            or Path(type(controller).context.__code__.co_filename).resolve()!=Path(b.batch.__file__).resolve()
            or Path(b.__file__).resolve()!=Path(__file__).resolve().with_name('league_training_batch_bridge.py')
            or b._active()!={key} or b._CONTROLLERS.get(key) is not controller
            or b._OWNERS.get(key) is not c['native'] or b._BINDINGS.get(key) is not c['binding']
            or controller.owner!=key or controller.error is not None or controller.complete is not False
            or _sha(p)!=c['plan_sha'] or p.get('training_job')!=JOB or p.get('mode')!='league_campaign'
            or c['binding']!=('league_training_batch',b._canonical(c['step']),JOB)
            or c['step'] not in p['steps'] or _sha(c['step'])!=c['step_sha']):
        raise ValueError('original_batch_native_or_plan_changed')
    return c


def register_trusted_context(native,plan,step_id,*,batch_bridge,levelup_module,peer_owners):
    """Parent first proves actual batch/plan/native and complete 33-peer inventory."""
    global _CONTEXT
    if _ERROR is not None:return False
    try:
        from .owned_field_medicine import PEER_NAMES
        if (type(peer_owners) is not dict or set(peer_owners)!=set(PEER_NAMES)
                or any(type(v) is not set or v!=({step_id} if k=='league_training_batch' else set())
                       for k,v in peer_owners.items())
                or batch_bridge._active()!={step_id} or type(plan) is not dict
                or type(step_id) is not str or not step_id):raise ValueError('peer_inventory_unverified')
        step=[s for s in plan['steps'] if type(s) is dict and s.get('id')==step_id]
        if len(step)!=1 or not batch_bridge._explicit(step[0]):raise ValueError('exact_batch_step_missing')
        proof=levelup_module.eevee37_learning_proof
        folder=Path(__file__).resolve().parent
        if (Path(levelup_module.__file__).resolve()!=folder/'levelup_moves.py'
                or Path(proof.__file__).resolve()!=folder/'eevee37_learning_proof.py'
                or hashlib.sha256(Path(levelup_module.__file__).read_bytes()).hexdigest()!=CONTROLLER_SHA
                or hashlib.sha256(Path(proof.__file__).read_bytes()).hexdigest()!=PROOF_SHA
                or proof.CONTROLLER_SOURCE_SHA256!=CONTROLLER_SHA):raise ValueError('learning_source_unverified')
        new=dict(native=native,plan=plan,plan_sha=_sha(plan),step_id=step_id,step=step[0],step_sha=_sha(step[0]),
            bridge=batch_bridge,controller=batch_bridge._CONTROLLERS.get(step_id),
            binding=batch_bridge._BINDINGS.get(step_id),levelup=levelup_module,proof=proof,observation=None)
        if _CONTEXT is not None:
            old=_validate_context()
            if (old['native'] is not native or old['controller'] is not new['controller']
                    or old['binding'] is not new['binding'] or old['plan_sha']!=new['plan_sha']
                    or old['levelup'] is not levelup_module or old['proof'] is not proof):
                raise ValueError('explicit_closed_unregister_required')
            new['observation']=old['observation']
        _CONTEXT=new;_validate_context()
        return True
    except (ValueError,TypeError,KeyError,AttributeError,OSError):return _fail('trusted_registration_unverified')


def unregister_closed_context(native):
    """Only after batch EOF and no original learning session; never clears errors."""
    global _CONTEXT,_REQUEST
    if _ERROR is not None:return False
    if _CONTEXT is None:return True
    try:
        c=_CONTEXT
        if (c['native'] is not native or c['bridge']._active()!=set()
                or c['proof']._ACTIVE is not None or c['levelup']._SESSION is not None or _REQUEST is not None):
            raise ValueError('closed_unregister_unverified')
        _CONTEXT=None;_REQUEST=None;return True
    except (ValueError,TypeError,KeyError,AttributeError):return _fail('closed_unregister_unverified')


def current_binding(text,progress):
    """Double real getters at the actual native frame, before the learning parser."""
    if _ERROR is not None or _CONTEXT is None:return None
    try:
        c=_validate_context();native=c['native'];frame=native.frame_count
        if _HOOK is not None and not _hook_valid():raise ValueError('dispatch_hook_changed')
        if type(frame) is not int or frame<0:raise ValueError('native_frame_unknown')
        from .observation import read_visible_text
        from .progress import read_progress
        from .battle import read_battle_state
        def sample():return read_visible_text(native),read_progress(native),read_battle_state(native)
        first,second=sample(),sample()
        if native.frame_count!=frame or first!=second:raise ValueError('torn_native_observation')
        source_text,source_progress,battle=first
        supplied=deepcopy(text);supplied.pop('observation_frame',None)
        if (type(text) is not dict or text.get('observation_frame',frame)!=frame
                or supplied!=source_text or progress!=source_progress or battle.get('observation_frame')!=frame
                or type(battle.get('raw')) is not int or type(battle.get('active')) is not bool
                or (battle.get('raw'),battle.get('kind'),battle.get('active')) not in ((1,'wild',True),(0,'none',False))):
            raise ValueError('caller_and_native_observation_conflict')
        binding=dict(native_owner=native,frame=frame,battle_state=deepcopy(battle),job=JOB,owner_step=c['step_id'],
            step_sha256=c['step_sha'],batch_binding_sha256=_sha(c['binding']),controller_source_sha256=CONTROLLER_SHA)
        c['observation']=dict(binding=binding,text_sha=_sha(source_text['cells']),progress_sha=_sha(progress))
        return binding
    except (ValueError,TypeError,KeyError,AttributeError):_fail('current_native_binding_unverified');return None


def remember_learning_hint(binding,result):
    """Retain the original request actually returned to this normal decision turn."""
    global _REQUEST
    _REQUEST=None
    if binding is None or result is None or type(result) is dict and 'learning_request_id' not in result:return
    try:
        c=_validate_context();obs=c['observation'];proof=c['proof'].original_controller(binding);p=proof.pending
        if (obs['binding'] is not binding or proof.owner is not c['native'] or type(p) is not dict
                or p['request_id']!=result.get('learning_request_id') or p['ack'] is not None
                or p['action'] not in result.get('available_actions',[]) or p['action']=='wait'
                or p['page']!=obs['text_sha'] or p['frame']>binding['frame']
                or c['levelup']._SESSION is not proof.core_session):raise ValueError('original_offered_request_unverified')
        _REQUEST=dict(native=c['native'],proof=proof,pending=p,binding=binding,request_id=p['request_id'],
            action=p['action'],source_frame=binding['frame'])
    except (ValueError,TypeError,KeyError,AttributeError):_fail('offered_request_unverified')


def first_missing_binding_takeover(state,text,progress):
    """One same-frame handoff only; never repairs an existing controller or error."""
    if (type(state) is not dict or state.get('phase')!='strategy_review'
            or state.get('review_reason')!='eevee37_trusted_dispatch_binding_missing'):return None
    try:
        c=_validate_context();p=c['proof'];levelup=c['levelup'];frame=c['native'].frame_count
        if p._ACTIVE is not None or levelup._SESSION is not None:raise ValueError('existing_learning_not_repairable')
        binding=current_binding(text,progress)
        if binding is None:return review_context()
        checked=dict(deepcopy(text),observation_frame=frame)
        rows=p.rows_checked(checked,frame,levelup.snorlax_harden_skip.TEXT_PROFILE)
        current=p.snapshot(progress);eevee=next(m for m in current['party'] if m['species']==102)
        compact=p.compact(''.join(rows[12:]))
        if (not compact.startswith('EEVEEIS') or 'TRYINGTOLEARN' not in compact
                or eevee['level']!=37 or tuple(eevee['moves'])!=p.BEFORE):raise ValueError('exact_first_trying_required')
        result=levelup.context(checked,progress,learning_binding=binding)
        remember_learning_hint(binding,result)
        return review_context() or result
    except (ValueError,TypeError,KeyError,AttributeError):_fail('first_takeover_unverified');return review_context()


def _shape(code):
    return (code.co_argcount,code.co_posonlyargcount,code.co_kwonlyargcount,code.co_flags,code.co_freevars,code.co_cellvars)


def _hook_valid():
    from . import game
    h=_HOOK
    return (type(h) is dict and game.advance_action is h['function']
        and h['function'].__code__ is h['wrapper_code']
        and h['function'].__globals__ is game.__dict__ and h['original'].__globals__ is game.__dict__
        and game.__dict__.get(_ORIGINAL_NAME) is h['original'] and game.__dict__.get(_CALLBACK_NAME) is h['callback']
        and h['original'].__closure__ is None
        and hashlib.sha256(inspect.getsource(h['original']).encode('utf-8')).hexdigest()==ADVANCE_SOURCE_SHA)


class _ActualCallback:
    def __init__(self,native):self.native=native
    def __call__(self,native,action,source_frame,actual_frame):
        global _REQUEST
        request=_REQUEST
        if native is not self.native or action=='wait':return False
        if request is None:
            if type(_CONTEXT) is dict and _CONTEXT['proof']._ACTIVE is not None:
                return _fail('actual_action_without_learning_offer')
            return False
        try:
            c=_validate_context()
            if (_ERROR is not None or not _hook_valid() or _HOOK['callback'] is not self
                    or request['native'] is not native or action!=request['action']
                    or type(source_frame) is not int or source_frame!=request['source_frame']
                    or type(actual_frame) is not int or actual_frame<=source_frame or native.frame_count!=actual_frame
                    or c['proof'].original_controller(request['binding']) is not request['proof']
                    or request['proof'].pending is not request['pending']
                    or c['levelup']._SESSION is not request['proof'].core_session):raise ValueError('actual_dispatch_provenance_unverified')
            if not c['proof'].acknowledge_actual_execution(request['binding'],request['request_id'],
                    action=action,executed_frame=actual_frame):raise ValueError('actual_dispatch_ack_rejected')
            _REQUEST=None;return True
        except (ValueError,TypeError,KeyError,AttributeError):return _fail('actual_dispatch_unverified')


def _dispatch_wrapper(pyboy,action_key: str,hold_frames: int,settle_frames: int,on_frame=None) -> int:
    callback=_eevee37_dispatch_callback
    if pyboy is not callback.native or action_key=='wait':
        return _eevee37_dispatch_original(pyboy,action_key,hold_frames,settle_frames,on_frame)
    source_frame=pyboy.frame_count
    result=_eevee37_dispatch_original(pyboy,action_key,hold_frames,settle_frames,on_frame)
    callback(pyboy,action_key,source_frame,pyboy.frame_count)
    return result


def install_actual_dispatch_hook(native,function):
    """Preserve the exact already-referenced function object; no live call here."""
    global _HOOK
    try:
        from . import game
        if _ERROR is not None:return False
        if _HOOK is not None:
            if _hook_valid() and _HOOK['native'] is native and _HOOK['function'] is function:return True
            raise ValueError('unknown_or_other_native_hook')
        if (type(function) is not types.FunctionType or function is not game.advance_action
                or function.__globals__ is not game.__dict__ or function.__closure__ is not None
                or function.__code__.co_freevars or function.__code__.co_cellvars
                or _shape(function.__code__)!=_shape(_dispatch_wrapper.__code__)
                or function.__defaults__!=(None,) or function.__kwdefaults__ is not None
                or Path(function.__code__.co_filename).resolve()!=Path(game.__file__).resolve()
                or hashlib.sha256(inspect.getsource(function).encode('utf-8')).hexdigest()!=ADVANCE_SOURCE_SHA
                or _ORIGINAL_NAME in game.__dict__ or _CALLBACK_NAME in game.__dict__):raise ValueError('original_dispatch_function_unverified')
        c=_validate_context()
        if c['native'] is not native:raise ValueError('dispatch_native_changed')
        original=types.FunctionType(function.__code__,function.__globals__,function.__name__,function.__defaults__)
        original.__annotations__=dict(function.__annotations__)
        callback=_ActualCallback(native)
        record=dict(native=native,function=function,original=original,callback=callback,wrapper_code=_dispatch_wrapper.__code__)
        game.__dict__[_ORIGINAL_NAME]=original;game.__dict__[_CALLBACK_NAME]=callback
        function.__code__=record['wrapper_code'];_HOOK=record
        return True
    except (ValueError,TypeError,KeyError,AttributeError,OSError):return _fail('dispatch_install_unverified')
