"""單場訓練候選橋接；只讀，不送鍵／tick／寫plan；未實機驗證或批准。"""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import time

PURE_SHA256S = ('2d7aa3db864b8eca7347a02a4be7aac38516aec2c1a5186b4a7bb23ba6469507', '15e3a3335229e656a857cecdbee1b193f899c6cebf4d1b7742a2ed548c84174c')


def _load_exact():
    folder=Path(__file__).resolve().parent
    if not ((folder.name=="staged-league-training-runtime-20261028" and folder.parent.name==".local")
            or (folder.name=="laya_pokemon" and folder.parent.name=="src")):
        raise RuntimeError("只能使用精確stage或formal目錄")
    source=folder/"league_training_batch.py";resolved=source.resolve(strict=True)
    if resolved!=source.absolute() or sha256(resolved.read_bytes()).hexdigest() not in PURE_SHA256S:
        raise RuntimeError("訓練pure來源path/hash不符")
    spec=importlib.util.spec_from_file_location("laya_pokemon._league_training_batch_exact",resolved)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


batch=_load_exact()
MECHANIC="league_training_batch"
START=dict(map_id=194,x=28,y=7)
_CONTROLLERS=globals().get("_CONTROLLERS",{})
_BINDINGS=globals().get("_BINDINGS",{})
_COMPLETED=globals().get("_COMPLETED",set())
_ERRORS=globals().get("_ERRORS",{})
_OWNERS=globals().get("_OWNERS",{})
_REVIEWED_ABORTS=globals().get("_REVIEWED_ABORTS",{})
_FORBIDDEN={"event","item","badge","terminal","next_map","await_script_event","recovery_route"}
_BATTLE_PHASES={"battle_menu","battle_bag","battle_animation","battle_dialogue",
                "learning_menu","dialogue","strategy_review","campaign_review"}
_ACTIONS={"up","down","left","right","a","b","start","wait"}


def _active():
    if (type(_CONTROLLERS) is not dict or type(_BINDINGS) is not dict
            or type(_COMPLETED) is not set or type(_ERRORS) is not dict or type(_OWNERS) is not dict
            or type(_REVIEWED_ABORTS) is not dict):return None
    if any(not _abort_record_valid(k,r) for k,r in _REVIEWED_ABORTS.items()):return None
    return (set(_CONTROLLERS)|set(_BINDINGS)|set(_OWNERS))-_COMPLETED-{k for k,r in _REVIEWED_ABORTS.items() if r['done']}


def _review(reason,step_id):
    active=_active()
    if active:
        for owner in active:_ERRORS.setdefault(owner,"league_training_batch_"+reason)
    key=next(iter(active)) if active and len(active)==1 else step_id
    return dict(phase="campaign_review",objective="Wait.",available_actions=["wait"],
                review_reason=(_ERRORS if type(_ERRORS) is dict else {}).get(key,"league_training_batch_"+reason)),step_id


def applies(step_id,step):
    active=_active()
    return (active is None or bool(active) or isinstance(step_id,str) and step_id in _BINDINGS
            or isinstance(step,dict) and step.get("mechanic")==MECHANIC)


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)


_ABORT_ERROR="league_training_batch_single_wild_reward_or_pp_bound_unverified"
_ABORT_FIELDS=('owner','intent','contract','started','last_now','calls','waits','requests',
    'displacements','last_frame','error','pending','baseline','seen_wild','suspended',
    'returned_world_seen','closed_frame','closed_resources','closed_player','final_player',
    'complete','outcome','receipt','pending_ack_frame','wild_walk_evidence',
    'closed_cancelled_walk','cancelled_walk_history','cancelled_walk_closure_review',
    'cancelled_walk_review_history')


def _digest(value):
    return sha256(_canonical(value).encode('utf-8')).hexdigest()


def _abort_snapshot(c):
    return _canonical({k:getattr(c,k,None) for k in _ABORT_FIELDS})


def _abort_record_valid(step_id,r):
    if type(r) is dict and r.get('kind')=='reviewed_eevee_faint382449_to_indigo_v1':
        return _fnt_abort_record_valid(step_id,r)
    try:
        c=r['controller']
        return (type(step_id) is str and type(r) is dict
            and _CONTROLLERS.get(step_id) is c and _OWNERS.get(step_id) is r['native']
            and _BINDINGS.get(step_id) is r['binding'] and c.pending is r['pending']
            and c.last_packet is r['last_packet'] and c.baseline is r['baseline']
            and step_id not in _COMPLETED and c.complete is False and c.error==_ABORT_ERROR
            and _abort_snapshot(c)==r['snapshot'] and _digest(c.last_packet)==r['packet_sha256']
            and (step_id in _ERRORS,_ERRORS.get(step_id))==r['bridge_error']
            and _digest(r['capsule'])==r['capsule_sha256']
            and type(r['done']) is bool and type(r['closed_frames']) is list
            and len(r['closed_frames'])==(2 if r['done'] else 1)
            and all(type(f) is int for f in r['closed_frames'])
            and r['closed_frames'][0]==160497
            and (not r['done'] or 160497<r['closed_frames'][1]<=160577))
    except (KeyError,TypeError,ValueError,AttributeError,RecursionError):return False


def _abort_wait(step_id):
    if _REVIEWED_ABORTS[step_id].get('kind')=='reviewed_eevee_faint382449_to_indigo_v1':
        return _fnt_abort_wait(step_id)
    done=_REVIEWED_ABORTS[step_id]['done']
    out=dict(phase='campaign_review' if done else 'training_batch_owned',
        objective='Wait.',available_actions=['wait'],training_batch_aborted=done,
        training_batch_complete=False,training_batch_owner_step=step_id,
        training_batch_tactic='reviewed_abort_closed_world' if done else 'reviewed_abort_await_second_world',
        suppress_navigation_stall=True,suppress_blocked_edge_learning=True)
    if done:out['review_reason']='training_batch_reviewed_abort_ready_for_recovery'
    return out,step_id


def reviewed_abort(pyboy,state,plan,step_id,text,grid,capsule,*,expected_capsule_sha256,
                   original_controller,original_binding,original_pending,original_last_packet):
    """Root-authorized named retreat; preserve failure, never manufacture completion.

    Root first independently pins the capsule from actual RUN/escape, review and
    checkpoint evidence, proves all 33 peers (only this batch), native identity and
    full current plan. The digest is integrity, not evidence of an actual escape.
    No input, clock advancement, controller call, budget refund or EOF receipt.
    """
    try:
        if _active() is None:return _review('abort_registry_unverified',step_id)
        if (type(capsule) is dict and step_id!=capsule.get('step_id')
                and _REVIEWED_ABORTS.get(capsule.get('step_id'),{}).get('done') is True):return None
        prior=_REVIEWED_ABORTS.get(step_id)
        c=_CONTROLLERS.get(step_id)
        capkeys={'kind','game_id','source_frame','source_location','step_id','job','original_error',
            'original_plan','plan_bytes_sha256','plan_sha256','binding_sha256','baseline_sha256',
            'progress_sha256','packet_sha256','pending','pending_sha256','counters','counters_sha256',
            'baseline','controller_identity','native_identity','source_escape','original_review_sha256',
            'source_state_sha256','root_review'}
        if (type(capsule) is not dict or set(capsule)!=capkeys
                or type(expected_capsule_sha256) is not str or len(expected_capsule_sha256)!=64
                or _digest(capsule)!=expected_capsule_sha256
                or capsule['kind']!='reviewed_training_escape160497_v1' or capsule['game_id']!='game29'
                or type(capsule['source_frame']) is not int or capsule['source_frame']!=160497
                or type(step_id) is not str or not step_id or capsule['step_id']!=step_id
                or capsule['original_error']!=_ABORT_ERROR
                or type(capsule['controller_identity']) is not int or capsule['controller_identity']!=id(c)
                or type(capsule['native_identity']) is not int or capsule['native_identity']!=id(pyboy)
                or any(type(capsule.get(k)) is not str or len(capsule[k])!=64
                       or any(ch not in '0123456789abcdef' for ch in capsule[k])
                       for k in ('plan_bytes_sha256','original_review_sha256','source_state_sha256'))
                or _active()!=(set() if prior and prior['done'] else {step_id})
                or prior is not None and prior['capsule_sha256']!=expected_capsule_sha256
                or c is not original_controller or c is None
                or _OWNERS.get(step_id) is not pyboy or _BINDINGS.get(step_id) is not original_binding
                or c.pending is not original_pending or c.last_packet is not original_last_packet
                or c.owner!=step_id or c.error!=_ABORT_ERROR or c.complete is not False
                or c.seen_wild is not True or c.suspended is not True or c.returned_world_seen is not True
                or c.receipt is not None or c.outcome is not None or c.closed_frame is not None
                or c.closed_resources is not None or c.closed_player is not None
                or type(c.pending) is not dict or c.pending.get('executed') is not True
                or type(c.last_packet) is not tuple or len(c.last_packet)!=6):
            return _review('reviewed_abort_authority_or_identity_unverified',step_id)
        ids=[s.get('id') for s in plan['steps'] if type(s) is dict]
        matches=[s for s in plan['steps'] if type(s) is dict and s.get('id')==step_id]
        counters={k:getattr(c,k,None) for k in ('started','last_now','last_frame','calls','waits','requests','displacements')}
        loc={'map_id':194,'x':28,'y':8};frame=state.get('frame') if type(state) is dict else None
        if (plan.get('mode')!='league_campaign' or len(ids)!=len(plan['steps'])
                or any(type(i) is not str or not i for i in ids) or len(ids)!=len(set(ids))
                or len(matches)!=1 or not _explicit(matches[0]) or _digest(plan)!=capsule['plan_sha256']
                or _digest(capsule['original_plan'])!=capsule['plan_sha256']
                or type(plan.get('training_job')) is not str or not plan['training_job']
                or plan['training_job']!=capsule['job']
                or original_binding!=(MECHANIC,_canonical(matches[0]),plan['training_job'])
                or _digest(original_binding)!=capsule['binding_sha256']
                or _digest(c.baseline)!=capsule['baseline_sha256']
                or _digest(c.last_packet)!=capsule['packet_sha256']
                or _digest(capsule['baseline'])!=capsule['baseline_sha256']
                or _digest(c.pending)!=capsule['pending_sha256']
                or _digest(capsule['pending'])!=capsule['pending_sha256']
                or _digest(counters)!=capsule['counters_sha256']
                or type(capsule['counters']) is not dict or set(capsule['counters'])!=set(counters)
                or any(type(v) is not int or v<0 for k,v in capsule['counters'].items() if k not in ('started','last_now'))
                or any(type(capsule['counters'][k]) not in (int,float) for k in ('started','last_now'))
                or counters!=capsule['counters'] or c.last_frame!=160497
                or type(frame) is not int or not 160497<=frame<=160577
                or prior is None and frame!=160497
                or type(pyboy.frame_count) is not int or pyboy.frame_count!=frame
                or type(state) is not dict or type(state.get('frame')) is not int or state['frame']!=frame
                or state.get('location')!=loc or capsule['source_location']!=loc
                or any(type(v) is not int for v in capsule['source_location'].values())
                or _digest(state.get('progress'))!=capsule['progress_sha256']):
            return _review('reviewed_abort_binding_or_snapshot_unverified',step_id)
        escape=capsule['source_escape'];es=escape['record']['state'];eb=es['battle_state']
        if (type(escape.get('line_number')) is not int or escape['line_number']<=0
                or type(escape.get('line_sha256')) is not str or len(escape['line_sha256'])!=64
                or type(es.get('frame')) is not int or not 0<es['frame']<160497
                or es.get('location')!=loc or type(eb.get('raw')) is not int or eb['raw']!=1
                or eb.get('kind')!='wild' or eb.get('active') is not True
                or 'Got away safely!' not in [v.strip() for v in es.get('visible_text_candidates',[]) if type(v) is str]
                or capsule['root_review'].get('reward_exp')!=0
                or capsule['root_review'].get('pp_spent')!=3
                or capsule['root_review'].get('hp_lost')!=65
                or capsule['root_review'].get('original_counter_refund') is not False
                or capsule['root_review'].get('original_error_cleared') is not False
                or type(capsule['root_review'].get('source_frame_wait_limit')) is not int
                or capsule['root_review']['source_frame_wait_limit']!=80):
            return _review('reviewed_abort_escape_evidence_unverified',step_id)
        from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
        signal=batch.read_training_observation(pyboy,frame,sdk)
        current=batch.resources(state.get('progress'));native=signal.get('battle',{})
        oldstate,oldtext,oldgrid,oldsignal,previous,owner=c.last_packet
        if (signal.get('read_valid') is not True or signal.get('idle') is not True
                or signal.get('location')!=loc or signal.get('progress')!=state.get('progress')
                or type(native.get('raw')) is not int or native['raw']!=0
                or native.get('kind')!='none' or native.get('active') is not False
                or native.get('observation_frame')!=frame or state.get('battle_state')!=native
                or not batch.closed_world(text,grid,(28,8),frame)
                or current is None or any(m['hp']<=0 or m['status']!=0 for m in current['party'])
                or oldstate.get('frame')!=160497 or oldstate.get('location')!=loc
                or oldstate.get('progress')!=state.get('progress') or owner!=step_id
                or not batch.closed_world(oldtext,oldgrid,(28,8),160497)
                or oldsignal.get('read_valid') is not True or oldsignal.get('idle') is not True
                or oldsignal.get('progress')!=signal.get('progress')
                or batch.validate_wild_delta(c.baseline,current)[0]
                   !='single_wild_reward_or_pp_bound_unverified'):
            return _review('reviewed_abort_current_world_unverified',step_id)
        # This named abort admits exactly no reward, HP loss, and three used PP.
        before=c.baseline;spent=lost=0
        if any(before[k]!=current[k] for k in before if k!='party'):
            return _review('reviewed_abort_nonbattle_resources_changed',step_id)
        for old,new in zip(before['party'],current['party']):
            if ({k:v for k,v in old.items() if k not in ('hp','pp')}
                    !={k:v for k,v in new.items() if k not in ('hp','pp')}
                    or new['hp']>old['hp']):return _review('reviewed_abort_party_changed',step_id)
            lost+=old['hp']-new['hp']
            for a,b in zip(old['pp'],new['pp']):
                if a>>6!=b>>6 or (b&63)>(a&63):return _review('reviewed_abort_pp_gain',step_id)
                spent+=(a&63)-(b&63)
        if spent!=3 or lost!=65:
            return _review('reviewed_abort_retreat_delta_unverified',step_id)
        if prior is not None:
            if frame>prior['closed_frames'][-1] and not prior['done']:
                prior['closed_frames'].append(frame);prior['done']=True
            return _abort_wait(step_id)
        record=dict(controller=c,native=pyboy,binding=original_binding,pending=original_pending,
            last_packet=original_last_packet,baseline=c.baseline,snapshot=_abort_snapshot(c),
            packet_sha256=_digest(c.last_packet),bridge_error=(step_id in _ERRORS,_ERRORS.get(step_id)),
            capsule=deepcopy(capsule),capsule_sha256=expected_capsule_sha256,closed_frames=[frame],done=False)
        _REVIEWED_ABORTS[step_id]=record
        return _abort_wait(step_id)
    except (KeyError,TypeError,ValueError,AttributeError,IndexError,RecursionError):
        return _review('reviewed_abort_unverified',step_id)


def _explicit(step):
    intent=step.get("training_intent")
    return (step.get("kind")=="interact" and step.get("mechanic")==MECHANIC
        and type(step.get("map_id")) is int and step["map_id"]==194
        and type(step.get("target")) is list and tuple(step["target"]) in batch.TILES
        and all(type(n) is int for n in step["target"])
        and type(intent) is dict and intent==batch.INTENT and set(intent)==set(batch.INTENT)
        and all(type(intent[k]) is type(v) for k,v in batch.INTENT.items())
        and all(type(p) is list and len(p)==2 and all(type(n) is int for n in p) for p in intent["tiles"])
        and not _FORBIDDEN.intersection(step))


def _handoff(state,result,step_id):
    phase=state.get("phase");objective=state.get("objective");actions=state.get("available_actions")
    valid=(type(phase) is str and phase in _BATTLE_PHASES
        and isinstance(objective,str) and bool(objective) and type(actions) is list and bool(actions)
        and all(type(a) is str and a in _ACTIONS for a in actions)
        and len(actions)==len(set(actions)) and (actions==["wait"] or len(actions)>=2))
    if not valid:
        return {**result,"training_batch_owner_step":step_id,
                "training_batch_battle_delegate":"await_existing_battle_context"}
    out={k:v for k,v in result.items() if k not in ("phase","objective","available_actions","controller_menu_verified")}
    out.update(phase=phase,objective=objective,available_actions=list(actions),
               training_batch_owner_step=step_id,training_batch_battle_delegate="existing_battle")
    for key in ("controller_menu_verified","review_reason"):
        if key in state:out[key]=state[key]
    return out


def _remember_zero_source(controller,pyboy,step_id,signal,previous,pending,executed_before,seen_before,frame,state,text,grid,result):
    """Private original-object witnesses, captured only from the real bridge turn."""
    origin=getattr(controller,'_zero_bridge_origin',None)
    if (type(origin) is not dict or origin.get('native') is not pyboy
            or origin.get('controller') is not controller or origin.get('binding') is not _BINDINGS.get(step_id)):return
    if (seen_before is False and type(pending) is dict and executed_before is False and pending.get('executed') is True
            and type(previous) in (list,tuple) and previous and previous[-1]==pending.get('action')):
        origin['ack']=dict(pending=pending,snapshot=_canonical(pending),frame=frame,action=previous[-1])
    native=signal.get('battle') if type(signal) is dict else None
    if (seen_before is False and origin.get('wild') is None and controller.seen_wild is True and type(native) is dict
            and type(native.get('raw')) is int and native['raw']==1
            and native.get('kind')=='wild' and native.get('active') is True
            and type(native.get('observation_frame')) is int and native['observation_frame']==frame):
        evidence=getattr(controller,'wild_walk_evidence',None)
        origin['wild']=dict(pending=pending,evidence=evidence,snapshot=_canonical(evidence),
            frame=frame,location=dict(signal['location']),raw=native['raw'],kind=native['kind'],active=native['active'])
    if (controller.error is None and result.get('training_batch_complete') is False
            and controller.displacements==0 and controller.seen_wild is True and controller.suspended is True
            and controller.closed_frame==frame and controller.pending is pending and type(pending) is dict
            and signal.get('idle') is True and batch.closed_world(text,grid,(state['location']['x'],state['location']['y']),frame)
            and type(native) is dict and type(native.get('raw')) is int and native['raw']==0
            and native.get('kind')=='none' and native.get('active') is False):
        current=batch.resources(signal.get('progress'))
        if current is not None and current==controller.closed_resources:
            origin['closed']=dict(pending=pending,frame=frame,location=dict(signal['location']),
                resources=deepcopy(current),cancelled=deepcopy(getattr(controller,'closed_cancelled_walk',None)))


def _zero_completion_proven(controller,pyboy,step_id,step,job,state,signal,result,frame):
    """SHA cannot establish provenance; validate the original live object chain."""
    try:
        c=controller;r=c.receipt;e=getattr(c,'wild_walk_evidence',None)
        origin=getattr(c,'_zero_bridge_origin',None);history=getattr(c,'cancelled_walk_history',None)
        if (type(origin) is not dict or set(origin)!={'native','controller','binding','ack','wild','closed'}
                or origin['native'] is not pyboy or origin['controller'] is not c
                or origin['binding'] is not _BINDINGS.get(step_id)
                or origin['binding']!=(MECHANIC,_canonical(step),job) or _OWNERS.get(step_id) is not pyboy
                or _CONTROLLERS.get(step_id) is not c or c.owner!=step_id
                or type(c.displacements) is not int or c.displacements!=0
                or c.outcome!='complete_single_wild' or c.seen_wild is not True
                or c.returned_world_seen is not True or c.complete is not True
                or c.pending is not None or c.suspended is not False
                or getattr(c,'cancelled_walk_closure_review',None) is not None
                or type(r) is not dict or r.get('walk_resolution')!='cancelled_before_displacement'
                or r.get('displacement_occurred') is not False or type(r.get('wild_count')) is not int or r['wild_count']!=1
                or type(result.get('training_batch_displacements')) is not int or result['training_batch_displacements']!=0
                or result.get('training_batch_outcome')!=c.outcome
                or _canonical(result.get('training_batch_receipt'))!=_canonical(r)
                or type(history) is not list or len(history)!=1 or type(e) is not dict):return False
        ack,wild,closed=origin['ack'],origin['wild'],origin['closed'];p=e.get('pending');cancel=r.get('cancelled_walk');loc=state['location']
        start=getattr(c,'start',batch.TILES[0])
        if (type(start) is not tuple or len(start)!=2 or any(type(n) is not int for n in start)
                or start not in batch.TILES or start!=getattr(c,'start_contract',batch.TILES[0])
                or start!=tuple(step['target']) or type(p) is not dict
                or tuple(p.get('player',()))!=start):return False
        if (type(ack) is not dict or type(wild) is not dict or type(closed) is not dict or type(p) is not dict
                or set(p)!={'action','player','expected','frame','executed'}
                or set(e)!={'pending','snapshot','player','frame','ack_frame','raw','kind','active'}
                or wild.get('pending') is not p or ack.get('pending') is not p or wild.get('evidence') is not e
                or ack.get('snapshot')!=_canonical(p) or wild.get('snapshot')!=_canonical(e)
                or type(p['executed']) is not bool or p['executed'] is not True
                or any(type(v) not in (list,tuple) or len(v)!=2 or any(type(n) is not int for n in v)
                       or tuple(v) not in batch.TILES for v in (p['player'],p['expected'],e['player']))
                or tuple(p['expected'])==tuple(p['player']) or tuple(e['player'])!=tuple(p['player'])
                or p['action']!=('down' if tuple(p['player'])==batch.TILES[0] else 'up')
                or _canonical(e['snapshot'])!=_canonical(p)
                or type(e['raw']) is not int or e['raw']!=1 or e['kind']!='wild' or e['active'] is not True
                or any(type(v) is not int or v<0 for v in (p['frame'],e['ack_frame'],e['frame'],c.closed_frame,frame))
                or not p['frame']<e['ack_frame']<=e['frame']<c.closed_frame<frame
                or type(c.pending_ack_frame) is not int or c.pending_ack_frame!=e['ack_frame']
                or type(ack.get('frame')) is not int or type(wild.get('frame')) is not int
                or ack.get('frame')!=e['ack_frame'] or ack.get('action')!=p['action']
                or wild.get('frame')!=e['frame'] or type(wild.get('raw')) is not int or wild['raw']!=1
                or wild.get('kind')!='wild' or wild.get('active') is not True
                or type(wild.get('location')) is not dict or set(wild['location'])!={'map_id','x','y'}
                or any(type(v) is not int for v in wild['location'].values())
                or wild.get('location')!={'map_id':194,'x':p['player'][0],'y':p['player'][1]}
                or type(cancel) is not dict or cancel.get('kind')!='observed_turn_before_displacement'
                or _canonical(cancel)!=_canonical(history[0])
                or cancel.get('displacement_occurred') is not False
                or any(type(cancel.get(k)) is not int or cancel[k]!=0 for k in ('displacements_before','displacements_after'))
                or _canonical(cancel.get('pending'))!=_canonical(p)
                or _canonical(cancel.get('wild_player'))!=_canonical(p['player'])
                or type(cancel.get('actual_ack_frame')) is not int or cancel['actual_ack_frame']!=e['ack_frame']
                or type(cancel.get('wild_frame')) is not int or cancel['wild_frame']!=e['frame']
                or any(type(v) is not list or len(v)!=2 or any(type(n) is not int for n in v)
                       for v in (cancel.get('closed_frames'),r.get('closed_frames')))
                or cancel.get('closed_frames')!=[c.closed_frame,frame] or r.get('closed_frames')!=[c.closed_frame,frame]
                or type(c.closed_player) is not tuple or any(type(v) is not int for v in c.closed_player)
                or closed.get('pending') is not p or type(closed.get('frame')) is not int or closed['frame']!=c.closed_frame
                or closed.get('location')!=loc or _canonical(closed.get('cancelled'))!=_canonical(c.closed_cancelled_walk)
                or c.closed_player!=tuple(p['player']) or loc!={'map_id':194,'x':p['player'][0],'y':p['player'][1]}):return False
        current=batch.resources(state['progress']);source=batch.resources(signal.get('progress'))
        if current is None or current!=source or current!=c.closed_resources or current!=closed.get('resources'):return False
        reason,delta=batch.validate_wild_delta(c.baseline,current,approved_learning=_learning_evidence(c,pyboy,step_id))
        return (reason is None and all(_canonical(r.get(k))==_canonical(v) for k,v in delta.items())
                and type(r.get('total_exp_gain')) is int and r['total_exp_gain']>0)
    except (KeyError,TypeError,ValueError,AttributeError,IndexError):return False


def context(pyboy,state,plan,step_id,text,grid,previous,*,now=None):
    """真getter＋原生決策包；同owner/pending/baseline/clock/error跨reload保留。"""
    active=_active()
    if active is None:return _review("registries_unverified",step_id)
    if not isinstance(step_id,str) or not step_id:return _review("step_id_unverified",step_id)
    if active and active!={step_id}:return _review("owner_changed",step_id)
    if step_id in _REVIEWED_ABORTS:return _abort_wait(step_id)
    if step_id in _ERRORS:return _review("sticky_bridge_error",step_id)
    if (not isinstance(plan,dict) or plan.get("mode")!="league_campaign"
            or not isinstance(plan.get("steps"),list)):
        return _review("plan_unverified",step_id)
    ids=[s.get("id") if isinstance(s,dict) else None for s in plan["steps"]]
    if any(not isinstance(i,str) or not i for i in ids) or len(ids)!=len(set(ids)):
        return _review("plan_step_ids_unverified",step_id)
    matches=[s for s in plan["steps"] if s["id"]==step_id]
    if len(matches)!=1:return _review("step_missing",step_id) if active else None
    step=matches[0]
    if step.get("mechanic")!=MECHANIC:
        return _review("intent_changed",step_id) if active or step_id in _BINDINGS else None
    if not _explicit(step):return _review("explicit_intent_unverified",step_id)
    job=plan.get("training_job")
    if not isinstance(job,str) or not job.strip():return _review("job_unverified",step_id)
    try:binding=(MECHANIC,_canonical(step),job)
    except (TypeError,ValueError):return _review("binding_unverified",step_id)
    if step_id in _BINDINGS and _BINDINGS[step_id]!=binding:return _review("job_or_intent_changed",step_id)
    controller=_CONTROLLERS.get(step_id)
    if step_id in _BINDINGS and controller is None:return _review("original_controller_missing",step_id)
    if (controller is not None or step_id in _COMPLETED) and step_id not in _BINDINGS:
        return _review("original_binding_missing",step_id)
    if step_id in _BINDINGS and step_id not in _OWNERS:return _review("original_session_owner_missing",step_id)
    if step_id in _OWNERS and _OWNERS[step_id] is not pyboy:return _review("native_session_owner_changed",step_id)
    if step_id in _COMPLETED:return _review("completed_step_reentered",step_id)
    if not isinstance(state,dict) or not isinstance(state.get("location"),dict):
        return _review("state_unverified",step_id)
    loc=state["location"];frame=state.get("frame")
    if (not batch.integer(frame,0,2**63-1)
            or any(not batch.integer(loc.get(k)) for k in ("map_id","x","y"))):
        return _review("frame_or_location_unverified",step_id)
    position={k:loc[k] for k in ("map_id","x","y")}
    start=tuple(step['target'])
    if controller is not None and (getattr(controller,'start',batch.TILES[0])!=start
            or getattr(controller,'start_contract',batch.TILES[0])!=start):
        return _review("original_start_contract_changed",step_id)
    if controller is None and position!={'map_id':194,'x':start[0],'y':start[1]}:return None
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
    signal=batch.read_training_observation(pyboy,frame,sdk)
    if controller is None:
        current=batch.resources(signal.get("progress"))
        if (signal.get("read_valid") is not True or current is None
                or not batch.closed_world(text,grid,start,frame) or signal.get("idle") is not True):
            return _review("initial_source_world_unverified",step_id)
        weakest=min(current["party"],key=lambda m:(m["level"],m["exp"]))
        if (type(plan.get("lead_species")) is not int or plan["lead_species"]!=weakest["species"]
                or current["party"][0]["species"]!=weakest["species"]):
            return _review("true_lowest_lead_not_ready",step_id)
        if min(m["level"] for m in current["party"])>=45:return _review("all_six_45_checkpoint_review",step_id)
        controller=batch.TrainingBatch(step["training_intent"],start=start)
        _CONTROLLERS[step_id]=controller;_BINDINGS[step_id]=binding;_OWNERS[step_id]=pyboy
        controller._zero_bridge_origin=dict(native=pyboy,controller=controller,binding=_BINDINGS[step_id],ack=None,wild=None,closed=None)
    controller.__class__=batch.TrainingBatch
    if ((step_id in _LEARNING or getattr(controller,'approved_learning',None) is not None)
            and _learning_evidence(controller,pyboy,step_id) is None):
        return _review('original_learning_approval_changed_or_missing',step_id)
    pending_before=controller.pending
    executed_before=type(pending_before) is dict and pending_before.get('executed') is True
    seen_before=controller.seen_wild
    result=controller.context(state,text=text,grid=grid,signal=signal,previous=previous,
                              now=time.monotonic() if now is None else now,owner=step_id)
    if not isinstance(result,dict):return _review("controller_result_unverified",step_id)
    _remember_zero_source(controller,pyboy,step_id,signal,previous,pending_before,executed_before,seen_before,frame,state,text,grid,result)
    if result.get("training_batch_battle_handoff") is True:return _handoff(state,result,step_id),step_id
    if result.get("training_batch_complete") is True:
        if (controller.error or controller.pending is not None or controller.suspended
                or controller.closed_frame is None or controller.closed_frame>=frame
                or not batch.closed_world(text,grid,(loc["x"],loc["y"]),frame)
                or signal.get("idle") is not True or controller.receipt is None
                or result.get("training_batch_outcome") not in ("complete_single_wild","complete_no_encounter")):
            return _review("completion_receipt_unverified",step_id)
        if controller.displacements==0 or result.get('training_batch_displacements')==0:
            if not _zero_completion_proven(controller,pyboy,step_id,step,job,state,signal,result,frame):
                return _review('zero_cancel_original_provenance_unverified',step_id)
        cancelled=controller.receipt.get('walk_resolution')=='cancelled_before_displacement'
        if cancelled:
            history=getattr(controller,'cancelled_walk_history',None)
            if (not batch.integer(controller.displacements,0,batch.INTENT['max_displacements'])
                    or controller.receipt.get('displacement_occurred') is not False
                    or type(history) is not list or not history
                    or controller.receipt.get('cancelled_walk')!=history[-1]
                    or history[-1].get('displacements_before')!=controller.displacements
                    or history[-1].get('displacements_after')!=controller.displacements
                    or history[-1].get('closed_frames')!=controller.receipt.get('closed_frames')):
                return _review('cancelled_turn_completion_receipt_unverified',step_id)
        elif not batch.integer(controller.displacements,1,batch.INTENT['max_displacements']):
            return _review('completion_displacement_bound_unverified',step_id)
        _COMPLETED.add(step_id)
        result={**result,"field_move_complete":True,"field_move_kind":"league-training-batch",
                "training_batch_owner_step":step_id,"training_batch_job":job}
        index=ids.index(step_id)+1
        return result,ids[index] if index<len(ids) else "complete"
    return {**result,"training_batch_owner_step":step_id},step_id


def pre_attrition_closure_context(pyboy,state,plan,step_id,attrition,text,grid,previous,*,now=None):
    """只讓已綁wild owner做WAIT驗收；其他損耗、FNT、未知仍由原閘停。"""
    if (not isinstance(attrition,dict) or attrition.get("review_reason")!="party_attrition_requires_center"
            or _active()!={step_id}):return None
    controller=_CONTROLLERS.get(step_id)
    current=batch.resources(state.get("progress")) if isinstance(state,dict) else None
    if (controller is None or controller.error or not controller.seen_wild or not controller.suspended
            or current is None or any(m["hp"]<=0 for m in current["party"])):
        return None
    frame=state.get("frame");loc=state.get("location",{})
    if not batch.closed_world(text,grid,(loc.get("x"),loc.get("y")),frame):return None
    owned=context(pyboy,state,plan,step_id,text,grid,previous,now=now)
    if owned is None:return None
    out,next_id=owned
    if out.get("available_actions")!=["wait"]:
        return _review("attrition_closure_must_only_wait",step_id)
    return out,next_id


# Appended to the pinned bridge by build_candidate.py; no file/native mutations.
_FNT_KIND = 'reviewed_eevee_faint382449_to_indigo_v1'
_FNT_CAP_SHA = 'e6d1633738687c674bb5914ec78b8339499ad9a9fefcdab9c2e304f4c46d7c4e'
_FNT_STEP = 'league-six-party45-game29-20261028-069-067'
_FNT_ERRORS = (None, 'league_training_batch_fainted_party_requires_review')


def _fnt_review(reason,step_id):
    # A failed audit must not change c.error, _ERRORS or the original transaction.
    record=_REVIEWED_ABORTS.get(step_id) if type(_REVIEWED_ABORTS) is dict else None
    if type(record) is dict and record.get('kind')==_FNT_KIND:
        record['review_error']=record.get('review_error') or reason
        reason=record['review_error']
    return dict(phase='campaign_review',objective='Wait.',available_actions=['wait'],
        review_reason='training_batch_reviewed_fnt_abort_'+reason,
        training_batch_complete=False,training_batch_aborted=False),step_id


def _fnt_abort_record_valid(step_id,r):
    try:
        c=r['controller'];frames=r['closed_frames'];cap=r['capsule']
        return (step_id==_FNT_STEP and type(r) is dict and r.get('kind')==_FNT_KIND
            and _CONTROLLERS.get(step_id) is c and _OWNERS.get(step_id) is r['native']
            and _BINDINGS.get(step_id) is r['binding'] and c.pending is r['pending']
            and c.last_packet is r['last_packet'] and c.baseline is r['baseline']
            and step_id not in _COMPLETED and c.complete is False
            and c.error==r['retained_error'] and c.error in _FNT_ERRORS
            and _abort_snapshot(c)==r['snapshot'] and _digest(c.last_packet)==r['packet_sha256']
            and _digest(c.baseline)==cap['baseline_sha256']
            and (step_id in _ERRORS,_ERRORS.get(step_id))==r['bridge_error']
            and r['capsule_sha256']==_FNT_CAP_SHA and _digest(cap)==_FNT_CAP_SHA
            and type(r['done']) is bool and type(frames) is list
            and len(frames)==(2 if r['done'] else 1)
            and all(type(f) is int for f in frames) and frames[0]==382449
            and (not r['done'] or 382449<frames[1]<=382529)
            and r['abort_frame']==frames[-1] and type(r['abort_packet_sha256']) is str
            and len(r['abort_packet_sha256'])==64
            and (r.get('review_error') is None or type(r['review_error']) is str and bool(r['review_error']))
            and (not r['done'] or r.get('review_error') is None))
    except (KeyError,TypeError,ValueError,AttributeError,RecursionError):return False


def _fnt_abort_wait(step_id):
    r=_REVIEWED_ABORTS[step_id]
    if r.get('review_error'):return _fnt_review(r['review_error'],step_id)
    done=r['done']
    out=dict(phase='campaign_review' if done else 'training_batch_owned',objective='Wait.',
        available_actions=['wait'],training_batch_aborted=done,training_batch_complete=False,
        training_batch_owner_step=step_id,training_batch_abort_kind=_FNT_KIND,
        training_batch_retained_error=r['retained_error'],
        training_batch_tactic='reviewed_fnt_abort_closed_world' if done else 'reviewed_fnt_abort_await_second_world',
        suppress_navigation_stall=True,suppress_blocked_edge_learning=True)
    if done:out['review_reason']='training_batch_reviewed_fnt_abort_ready_for_recovery'
    return out,step_id


def _fnt_source_events_valid(cap):
    try:
        events=cap['source_events'];frames=[]
        for key in ('faint','enemy_ko','reward'):
            event=events[key];state=event['record']['state'];native=state['battle_state']
            if (type(event.get('line_number')) is not int or event['line_number']<=0
                    or type(event.get('line_sha256')) is not str or len(event['line_sha256'])!=64
                    or type(state.get('frame')) is not int or type(native.get('raw')) is not int
                    or native['raw']!=1 or native.get('kind')!='wild' or native.get('active') is not True
                    or native.get('opponent_species')!='MAROWAK'
                    or native.get('wild_opponent_species')!='MAROWAK'):return False
            frames.append(state['frame'])
        if frames!=[380721,382193,382321]:return False
        def visible(key):return ' '.join(str(v).strip() for v in events[key]['record']['state']['visible_text_candidates'])
        return ('EEVEE fainted!' in visible('faint') and 'Enemy MAROWAK fainted!' in visible('enemy_ko')
            and 'LAPRAS gained 708 EXP. Points!' in visible('reward'))
    except (KeyError,TypeError,ValueError,AttributeError):return False


def reviewed_fnt_abort(pyboy,state,plan,step_id,text,grid,capsule,*,expected_capsule_sha256,
                       original_controller,original_binding,original_pending,original_last_packet):
    """One root-reviewed named faint, not successful training or a cleared failure.

    Root first pins the complete cap, clears all peers except this original batch,
    and supplies the original registry objects. Only two fresh WAIT observations
    are admitted. This API never calls TrainingBatch.context or alters its state.
    Ordinary exact070 recovery/lead UI/ledger handling belongs to the parent.
    """
    try:
        prior=_REVIEWED_ABORTS.get(_FNT_STEP) if type(_REVIEWED_ABORTS) is dict else None
        if step_id!=_FNT_STEP and prior and prior.get('done') is True:return None
        active=_active()
        if active is None:return _fnt_review('original_registry_unverified',step_id)
        if (type(capsule) is not dict or expected_capsule_sha256!=_FNT_CAP_SHA or _digest(capsule)!=_FNT_CAP_SHA
                or capsule.get('kind')!=_FNT_KIND or capsule.get('game_id')!='game29'
                or type(step_id) is not str or step_id!=_FNT_STEP or capsule.get('step_id')!=step_id
                or type(capsule.get('source_frame')) is not int or capsule['source_frame']!=382449
                or capsule.get('source_location')!={'map_id':194,'x':28,'y':7}
                or capsule.get('fainted_species')!=102 or capsule.get('healthy_lead_species')!=19
                or capsule['root_review'].get('refund') is not False
                or capsule['root_review'].get('baseline_rewritten') is not False
                or capsule['root_review'].get('blackout') is not False
                or capsule['root_review'].get('faint_retained') is not True
                or not _fnt_source_events_valid(capsule)):
            return _fnt_review('root_cap_unverified',step_id)
        c=_CONTROLLERS.get(step_id);prior=_REVIEWED_ABORTS.get(step_id)
        if (active!=(set() if prior and prior['done'] else {step_id})
                or c is None or c is not original_controller or _OWNERS.get(step_id) is not pyboy
                or _BINDINGS.get(step_id) is not original_binding or c.pending is not original_pending
                or c.last_packet is not original_last_packet or c.owner!=step_id or c.error not in _FNT_ERRORS
                or c.complete is not False or c.seen_wild is not True or c.suspended is not True
                or c.returned_world_seen is not False or c.receipt is not None or c.outcome is not None
                or any(getattr(c,k) is not None for k in ('closed_frame','closed_resources','closed_player','final_player'))
                or type(c.pending) is not dict or c.pending.get('executed') is not True
                or type(c.last_packet) is not tuple or len(c.last_packet)!=6
                or type(c.last_frame) is not int or not 0<=c.last_frame<=382449):
            return _fnt_review('original_owner_or_controller_unverified',step_id)
        ids=[s.get('id') for s in plan['steps'] if type(s) is dict]
        matches=[s for s in plan['steps'] if type(s) is dict and s.get('id')==step_id]
        if (plan.get('mode')!='league_campaign' or len(ids)!=len(plan['steps']) or len(ids)!=len(set(ids))
                or len(matches)!=1 or not _explicit(matches[0]) or plan.get('training_job')!=capsule['job']
                or _digest(plan)!=capsule['plan_sha256'] or _digest(capsule['original_plan'])!=capsule['plan_sha256']
                or original_binding!=(MECHANIC,_canonical(matches[0]),capsule['job'])
                or _digest(original_binding)!=capsule['binding_sha256']
                or _digest(c.baseline)!=capsule['baseline_sha256']
                or _digest(capsule['baseline'])!=capsule['baseline_sha256']
                or _digest(capsule['recovery_steps'])!=capsule['recovery_steps_sha256']):
            return _fnt_review('original_plan_binding_or_baseline_unverified',step_id)
        frame=state.get('frame') if type(state) is dict else None
        loc={'map_id':194,'x':28,'y':7}
        if (type(frame) is not int or not 382449<=frame<=382529 or prior is None and frame!=382449
                or type(pyboy.frame_count) is not int or pyboy.frame_count!=frame
                or state.get('location')!=loc or _digest(state.get('progress'))!=capsule['progress_sha256']
                or any(type(v) is not int for v in state['location'].values())):
            return _fnt_review('fresh_frame_or_source_progress_unverified',step_id)
        from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
        signal=batch.read_training_observation(pyboy,frame,sdk)
        native=signal.get('battle',{});current=batch.resources(state.get('progress'))
        if (signal.get('read_valid') is not True or signal.get('idle') is not True
                or signal.get('observation_frame')!=frame or signal.get('location')!=loc
                or signal.get('progress')!=state.get('progress') or state.get('progress')!=capsule['progress']
                or type(native.get('raw')) is not int or native['raw']!=0 or native.get('kind')!='none'
                or native.get('active') is not False or type(native.get('observation_frame')) is not int
                or native['observation_frame']!=frame or state.get('battle_state')!=native
                or not batch.closed_world(text,grid,(28,7),frame) or current is None
                or len(current['party'])!=6 or {m['species'] for m in current['party']}!=batch.ROSTER
                or [m['species'] for m in current['party'] if m['hp']==0]!=[102]
                or any(m['status']!=0 or m['hp']<=0 and m['species']!=102 for m in current['party'])):
            return _fnt_review('closed_native_world_or_unique_faint_unverified',step_id)
        if prior is not None:
            if not _fnt_abort_record_valid(step_id,prior):return _fnt_review('frozen_record_changed',step_id)
            if prior.get('review_error'):return _fnt_review(prior['review_error'],step_id)
            if frame<prior['closed_frames'][-1]:return _fnt_review('fresh_frame_regressed',step_id)
            packet_sha=_digest((state,text,grid,signal))
            if frame==prior['abort_frame'] and packet_sha!=prior['abort_packet_sha256']:
                return _fnt_review('same_frame_observation_conflict',step_id)
            if not prior['done'] and frame>prior['closed_frames'][0]:
                prior['closed_frames'].append(frame);prior['done']=True
                prior['abort_frame']=frame;prior['abort_packet_sha256']=packet_sha
            return _fnt_abort_wait(step_id)
        record=dict(kind=_FNT_KIND,controller=c,native=pyboy,binding=original_binding,pending=original_pending,
            last_packet=original_last_packet,baseline=c.baseline,snapshot=_abort_snapshot(c),
            packet_sha256=_digest(c.last_packet),bridge_error=(step_id in _ERRORS,_ERRORS.get(step_id)),
            retained_error=c.error,capsule=deepcopy(capsule),capsule_sha256=_FNT_CAP_SHA,
            closed_frames=[frame],abort_frame=frame,abort_packet_sha256=_digest((state,text,grid,signal)),
            done=False,review_error=None)
        _REVIEWED_ABORTS[step_id]=record
        return _fnt_abort_wait(step_id)
    except (KeyError,TypeError,ValueError,AttributeError,IndexError,RecursionError):
        return _fnt_review('input_or_source_unverified',step_id)


# Appended to the original bridge; no dispatch or baseline rewriting.
_LEARNING=globals().get('_LEARNING',{})


def _learning_origin_valid(approval,*,completed=False):
    try:
        from laya_pokemon import eevee37_learning_proof as learning
        c=approval.controller;key=c.owner;r=_LEARNING[key]
        return (type(_LEARNING) is dict and r['approval'] is approval and r['controller'] is c
            and _CONTROLLERS.get(key) is c and _OWNERS.get(key) is r['native'] is approval.native
            and _BINDINGS.get(key) is r['binding'] is approval.binding
            and c.baseline is r['baseline'] is approval.baseline and _digest(c.baseline)==r['baseline_sha256']
            and getattr(c,'approved_learning',None) is approval and c.error is None and key not in _REVIEWED_ABORTS
            and approval.receipt==r['receipt'] and approval.receipt_sha==r['receipt_sha256']
            and c.intent==c.contract and r['binding']==(MECHANIC,_canonical(r['step']),r['job'])
            and (not completed or c.complete is True and key in _COMPLETED)
            and learning.original_controller(r['learning_binding']) is r['proof'] is approval.proof
            and r['proof'].consumed is True
            and learning.completed_receipt(r['learning_binding'],controller=r['proof'],consume=False)==r['receipt']
            and _digest(r['receipt'])==r['receipt_sha256'])
    except (KeyError,ValueError,TypeError,AttributeError):return False


def _learning_evidence(controller,pyboy,step_id):
    r=_LEARNING.get(step_id) if type(_LEARNING) is dict else None
    if r is None:return None
    approval=r.get('approval')
    return approval if (r.get('controller') is controller and r.get('native') is pyboy
                        and _learning_origin_valid(approval)) else None


def consume_owned_eevee37_learning(pyboy,plan,step_id,*,original_controller,original_binding,
                                    original_proof,learning_binding):
    """Only the trusted caller invokes this after the original UI controller completes."""
    try:
        from laya_pokemon import eevee37_learning_proof as learning
        from laya_pokemon import league_training_learning_receiver as receiver
        c=_CONTROLLERS.get(step_id);binding=_BINDINGS.get(step_id)
        matches=[s for s in plan['steps'] if type(s) is dict and s.get('id')==step_id]
        if (c is not original_controller or c is None or binding is not original_binding
                or _OWNERS.get(step_id) is not pyboy or c.owner!=step_id or c.error is not None
                or step_id in _ERRORS or step_id in _REVIEWED_ABORTS or plan.get('training_job')!=receiver.JOB
                or len(matches)!=1 or not _explicit(matches[0])
                or binding!=(MECHANIC,_canonical(matches[0]),receiver.JOB)
                or learning_binding.get('native_owner') is not pyboy
                or learning_binding.get('job')!=receiver.JOB or learning_binding.get('owner_step')!=step_id
                or learning_binding.get('step_sha256')!=_digest(matches[0])
                or learning_binding.get('batch_binding_sha256')!=_digest(binding)
                or learning_binding.get('controller_source_sha256')!=learning.CONTROLLER_SOURCE_SHA256
                or learning.original_controller(learning_binding) is not original_proof):return None
        if step_id in _LEARNING:return _learning_evidence(c,pyboy,step_id)
        if (c.complete is not False or c.seen_wild is not True or c.suspended is not True
                or c.closed_frame is not None or c.returned_world_seen is not False
                or type(c.baseline) is not dict or getattr(c,'approved_learning',None) is not None):return None
        peek=learning.completed_receipt(learning_binding,controller=original_proof,consume=False)
        receiver.proof_semantics(peek,batch.resources,expected_owner=step_id,expected_step_sha=_digest(matches[0]),
            expected_binding_sha=_digest(binding),expected_controller_sha=learning.CONTROLLER_SOURCE_SHA256)
        after=receiver.resources(peek['after_resources'],batch.resources)
        receiver.calculate(c.baseline,after,peek,normalize=batch.resources,base_validator=batch.validate_wild_delta,
                           needs_center=batch.needs_center)
        if (type(pyboy.frame_count) is not int or learning_binding.get('frame')!=pyboy.frame_count
                or pyboy.frame_count<peek['handoff_frame']):return None
        consumed=learning.completed_receipt(learning_binding,controller=original_proof,consume=True)
        if consumed!=peek:return None
        frozen_binding={**learning_binding,'battle_state':deepcopy(learning_binding.get('battle_state'))}
        r=dict(controller=c,native=pyboy,binding=binding,baseline=c.baseline,baseline_sha256=_digest(c.baseline),
            proof=original_proof,learning_binding=frozen_binding,receipt=deepcopy(consumed),
            receipt_sha256=_digest(consumed),step=deepcopy(matches[0]),job=receiver.JOB)
        approval=receiver.mint(controller=c,native=pyboy,binding=binding,baseline=c.baseline,
            proof=original_proof,receipt=consumed,verify_origin=_learning_origin_valid)
        r['approval']=approval;_LEARNING[step_id]=r;c.approved_learning=approval
        return _learning_evidence(c,pyboy,step_id)
    except (KeyError,ValueError,TypeError,AttributeError):return None


def completed_learning_authority(pyboy,step_id):
    c=_CONTROLLERS.get(step_id)
    return _learning_evidence(c,pyboy,step_id) if c is not None and c.complete is True else None
