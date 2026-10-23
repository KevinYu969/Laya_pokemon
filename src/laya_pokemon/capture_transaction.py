"""固定Route12捕捉橋接：唯讀真觀測，所有按鍵仍交原離線Laya。

投球與收尾共用最後一投基線；工程review只排除暫停時鐘，不重建交易。
"""
from copy import deepcopy
import importlib
import time
from . import snorlax_capture,capture_completion,wild_opponent,snorlax_switch
importlib.reload(snorlax_capture)
importlib.reload(capture_completion)
importlib.reload(wild_opponent)
importlib.reload(snorlax_switch)
_SESSIONS=globals().get('_SESSIONS',{})
MECHANIC='route12_snorlax_capture'
_SAFE_SWITCH_ERROR='snorlax_capture_safe_switch_requires_review'
_SWITCH_SPECIES={7,9,154,35,102}
_PRESERVED_CAPTURE=('throws','initial_items','current_items','last_throw','party_identity','party_hp','active_index','stage')

def _review(reason):
    return {'phase':'campaign_review','objective':'Wait.','available_actions':['wait'],'review_reason':reason}

def applies(step_id,step):
    return any(not s.get('done') for s in _SESSIONS.values()) or bool(step and step.get('mechanic')==MECHANIC)


def _finish_review(record,result,text,real_now):
    if result.get('phase')=='campaign_review':
        if record['pause_wall'] is None:record['pause_wall']=real_now
        switch=record.get('switch')
        if (switch is not None and switch.error is None) or record.get('pre_switch') is not None:
            record['bridge_error']=result.get('review_reason')
        result={**result,'capture_text_snapshot':deepcopy(text)}
    return result


def _enemy_snapshot(pyboy,frame,loc):
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as constants
    return wild_opponent.read_wild_opponent(pyboy,observation_frame=frame,
        expected_location=loc,constants=constants,profile=wild_opponent.PROFILE)


def _switch_accounting(capture,progress):
    """原投球物件的基線只核對，不重建、不調整throws或背包。"""
    party=snorlax_capture._party(progress)
    items=snorlax_capture._inventory(progress)
    if (party is None or items is None or type(capture.throws) is not int
            or not 0<=capture.throws<20 or capture.initial_items is None
            or capture.party_identity is None or capture.party_hp is None):return None
    identity=[{k:deepcopy(v) for k,v in m.items() if k!='hp'} for m in party]
    expected=[(i,20-capture.throws if i==3 else q) for i,q in capture.initial_items]
    if identity!=capture.party_identity or items!=expected:return None
    return party


def _construct_switch(capture,target,text,progress,loc,battle,enemy,frame,now):
    party=_switch_accounting(capture,progress)
    if party is None or capture.handoff is not None:return None
    try:
        controller=snorlax_switch.SnorlaxSwitchController(
            {'frame':frame,'now':now,'text':text,'progress':progress,'location':loc,
             'battle_state':battle,'enemy_snapshot':enemy},target)
    except (ValueError,TypeError,KeyError):return None
    old=controller.original_active
    if (capture.active_index not in (None,old) or len(capture.party_hp)!=4
            or any(type(hp) is not int or m['hp']>hp or i!=old and m['hp']!=hp
                   for i,(m,hp) in enumerate(zip(party,capture.party_hp)))):return None
    return controller


def _pre_switch_observation(capture,target,text,progress,loc,battle,enemy,frame):
    """只辨正常回合收尾或完整command；不改原觀測、capturer或安全線。"""
    party=_switch_accounting(capture,progress)
    rows=snorlax_switch._rows(text,frame)
    observed=snorlax_switch._enemy(enemy,frame)
    if (capture.error!=_SAFE_SWITCH_ERROR or capture.stage!='enemy_turn' or capture.handoff is not None
            or not 1<=capture.throws<=19 or party is None or rows is None or observed is None
            or not snorlax_switch._stance(loc,frame) or not snorlax_switch._battle(battle,frame)
            or 'observation_frame' in progress and (type(progress['observation_frame']) is not int
                                                    or progress['observation_frame']!=frame)
            or any(m['hp']<=0 for m in party) or type(capture.active_index) is not int
            or not 0<=capture.active_index<4 or len(capture.party_hp)!=4
            or not isinstance(capture.last_throw,dict) or observed!=capture.last_throw.get('enemy')
            or progress.get('money')!=capture.last_throw.get('progress',{}).get('money')):
        return None
    active=capture.active_index
    targets=[i for i,m in enumerate(party) if m['species']==target]
    if (len(targets)!=1 or targets[0]==active or not snorlax_capture._safe(party[targets[0]])
            or any(type(hp) is not int or m['hp']>hp or i!=active and m['hp']!=hp
                   for i,(m,hp) in enumerate(zip(party,capture.party_hp)))
            or snorlax_switch._hud(rows,party,observed)!=active):
        return None
    raw_packet=deepcopy((text,progress,loc,battle,enemy))
    command=snorlax_switch._command(rows,party,observed)
    if command is not None:return {'party':party,'enemy':observed,'rows':rows,'command':True,'raw_packet':raw_packet}
    lower=[[' ']*20 for _ in range(6)]
    snorlax_switch._put(lower,1,2,'ENEMY SNORLAX')
    snorlax_switch._put(lower,1,4,'USED HEADBUTT!')
    if rows[12:] not in (tuple(''.join(r) for r in lower),(' '*20,)*6):return None
    if any(c in ''.join(rows) for c in '▶▷▼'):return None
    return {'party':party,'enemy':observed,'rows':rows,'command':False,'raw_packet':raw_packet}


def _pre_switch_wait(record,proof,frame,now):
    """最多25個WAIT；同幀重呼也計入預算，絕不送A或改capture。"""
    pending=record['pre_switch']
    if pending['waits']>=25:return _review('capture_pre_switch_wait_budget_exhausted')
    pending['waits']+=1
    pending['last_frame'],pending['last_now']=frame,now
    pending['last_packet']=deepcopy(proof)
    pending['party_hp']=[m['hp'] for m in proof['party']]
    return {'phase':'capture_pre_switch_wait','objective':'Wait.','available_actions':['wait'],
            'capture_complete':False,'capture_controller_preserved':True,
            'reviewed_switch_revision':pending['revision'],'target_species':pending['target'],
            'pre_switch_waits':pending['waits'],'controller_menu_verified':False}


def _advance_pre_switch(record,target,text,progress,loc,battle,enemy,frame,now):
    """待原生完整command才建立既有嚴格Switch；其now為這次真觀測。"""
    capture,pending=record['capture'],record['pre_switch']
    pending['calls']+=1
    if (not snorlax_switch._clock(now) or now<pending['last_now']
            or type(frame) is not int or frame<pending['last_frame']):
        return _review('capture_pre_switch_clock_or_frame_invalid')
    if pending['calls']>26 or now-pending['started_now']>60:
        return _review('capture_pre_switch_transaction_budget_exhausted')
    if any(getattr(capture,k)!=v for k,v in pending['capture_preserved'].items()):
        return _review('capture_pre_switch_original_capture_changed')
    proof=_pre_switch_observation(capture,target,text,progress,loc,battle,enemy,frame)
    if (proof is None or proof['enemy']!=pending['enemy']
            or progress.get('money')!=pending['money']
            or any(m['hp']>hp for m,hp in zip(proof['party'],pending['party_hp']))):
        return _review('capture_pre_switch_observation_unverified')
    if frame==pending['last_frame']:
        if proof!=pending['last_packet']:return _review('capture_pre_switch_same_frame_conflict')
        return _pre_switch_wait(record,proof,frame,now)
    if not proof['command']:return _pre_switch_wait(record,proof,frame,now)
    candidate=_construct_switch(capture,target,text,progress,loc,battle,enemy,frame,now)
    if candidate is None:return _review('capture_pre_switch_native_command_rejected')
    record['switch']=candidate
    record['switch_revision'],record['switch_target']=pending['revision'],target
    record['switch_start_now']=pending['started_now']
    record['switch_capture_preserved']=pending['capture_preserved']
    record['pre_switch']=None
    return None


def _switch_completion_verified(capture,switch,text,progress,loc,battle,enemy,frame):
    rows=snorlax_switch._rows(text,frame)
    party=_switch_accounting(capture,progress)
    observed_enemy=snorlax_switch._enemy(enemy,frame)
    if (rows is None or party is None or observed_enemy is None
            or not snorlax_switch._stance(loc,frame) or not snorlax_switch._battle(battle,frame)
            or 'observation_frame' in progress and (type(progress['observation_frame']) is not int
                                                   or progress['observation_frame']!=frame)):
        return None
    command=snorlax_switch._command(rows,party,observed_enemy)
    if (command is None or command[0]!=switch.target_index
            or party[command[0]]['species']!=switch.target_species
            or progress.get('money')!=switch.baseline['progress'].get('money')
            or snorlax_switch._inventory(progress)!=switch.before_items):return None
    if any(observed_enemy[k]!=switch.before_enemy[k] for k in ('species','level','hp','max_hp')):return None
    if observed_enemy['status']!=switch.last_enemy_status:return None
    for i,(m,old) in enumerate(zip(party,switch.before_party)):
        if ({k:v for k,v in m.items() if k!='hp'}!={k:v for k,v in old.items() if k!='hp'}
                or not 0<m['hp']<=old['hp'] or i!=switch.target_index and m['hp']!=old['hp']):return None
    return command[0],[m['hp'] for m in party]

def context(pyboy,state,plan,step_id,text,grid):
    active={key for key,s in _SESSIONS.items() if not s.get('done')}
    if active and active!={step_id}:return _review('capture_transaction_step_changed'),step_id
    step=next((s for s in plan['steps'] if s['id']==step_id),None)
    if (not step or step.get('kind')!='interact' or step.get('mechanic')!=MECHANIC
            or step.get('map_id')!=23 or step.get('target')!=[10,61]
            or step.get('capture_intent')!=snorlax_capture.INTENT
            or any(type(step['capture_intent'].get(k)) is not type(v) for k,v in snorlax_capture.INTENT.items())):
        return _review('capture_transaction_explicit_intent_unverified'),step_id
    loc=state.get('location')
    if not capture_completion._stance(loc):
        return (_review('capture_transaction_location_changed'),step_id) if active else None
    binding=(23,(10,61),tuple(sorted(step['capture_intent'].items())))
    record=_SESSIONS.get(step_id)
    if record is not None and record['binding']!=binding:
        return _review('capture_transaction_bound_intent_changed'),step_id
    if record is None:
        record={'binding':binding,'capture':snorlax_capture.SnorlaxCaptureController(step['capture_intent']),
                'completion':None,'done':False,'clock_offset':0.,'reviewed_revision':0,'pause_wall':None}
        _SESSIONS[step_id]=record
    for key,value in (('switch',None),('switch_revision',0),('switch_target',None),
                      ('switch_start_now',None),('switch_capture_preserved',None),
                      ('last_switch_frame',None),('pre_switch',None)):
        record.setdefault(key,value)
    capture=record['capture'];capture.__class__=snorlax_capture.SnorlaxCaptureController
    completion=record['completion']
    if completion is not None:completion.__class__=capture_completion.CaptureCompletionController
    switch=record['switch']
    if switch is not None:switch.__class__=snorlax_switch.SnorlaxSwitchController
    real_now=time.monotonic()
    progress,battle,frame=state.get('progress'),state.get('battle_state'),state.get('frame')
    switch_revision=step.get('reviewed_switch_revision',0)
    switch_requested='reviewed_switch_revision' in step or 'reviewed_switch_target_species' in step
    enemy=None
    pending=record['pre_switch']
    if pending is not None:
        target=step.get('reviewed_switch_target_species')
        if (completion is not None or switch is not None or not switch_requested
                or type(switch_revision) is not int or switch_revision!=pending['revision']
                or type(target) is not int or target!=pending['target']):
            return _finish_review(record,_review('capture_pre_switch_request_changed'),text,real_now),step_id
        # 工程review只解除bridge error，絕不解除原capturer的SAFE_SWITCH。
        revision=step.get('reviewed_controller_revision',0)
        if record.get('bridge_error'):
            if (type(revision) is int and revision>record['reviewed_revision']
                    and step.get('reviewed_controller_error')==record['bridge_error']
                    and record['pause_wall'] is not None):
                record['clock_offset']+=max(0.,real_now-record['pause_wall'])
                record['pause_wall']=None;record['reviewed_revision']=revision;record['bridge_error']=None
            else:
                return _finish_review(record,_review(record['bridge_error']),text,real_now),step_id
        enemy=_enemy_snapshot(pyboy,frame,loc)
        result=_advance_pre_switch(record,target,text,progress,loc,battle,enemy,frame,
                                   real_now-record['clock_offset'])
        if result is not None:return _finish_review(record,result,text,real_now),step_id
        switch=record['switch']
    # New switch requests never acknowledge/clear the capturer error first.
    # A completion owner remains first; no switch may steal its transaction.
    if completion is None and switch_requested:
        target=step.get('reviewed_switch_target_species')
        if (type(switch_revision) is not int or switch_revision<=0
                or type(target) is not int or target not in _SWITCH_SPECIES):
            return _finish_review(record,_review('capture_switch_explicit_review_required'),text,real_now),step_id
        if switch is not None:
            if switch_revision!=record['switch_revision'] or target!=record['switch_target']:
                return _finish_review(record,_review('capture_switch_request_changed_while_active'),text,real_now),step_id
        elif switch_revision>record['switch_revision']:
            if capture.error!=_SAFE_SWITCH_ERROR:
                return _finish_review(record,_review('capture_switch_requires_safe_switch_review'),text,real_now),step_id
            pause=max(0.,real_now-record['pause_wall']) if record['pause_wall'] is not None else 0.
            switch_now=real_now-record['clock_offset']-pause
            if (type(frame) is not int or type(capture.last_frame) is not int or frame<capture.last_frame
                    or not snorlax_switch._clock(switch_now) or not snorlax_switch._clock(capture.last_now)
                    or switch_now<capture.last_now):
                return _finish_review(record,_review('capture_switch_new_request_clock_or_frame_regressed'),text,real_now),step_id
            prior=capture.last_packet
            if (not isinstance(prior,tuple) or len(prior)!=6 or not isinstance(prior[0],tuple)
                    or len(prior[0])!=18 or any(not isinstance(r,str) or len(r)!=20 for r in prior[0])
                    or not all(isinstance(v,dict) for v in prior[1:5]) or type(prior[5]) is not bool):
                return _finish_review(record,_review('capture_switch_prior_capture_packet_unverified'),text,real_now),step_id
            enemy=_enemy_snapshot(pyboy,frame,loc)
            if frame==capture.last_frame:
                rows=snorlax_capture._capture_rows(text,frame)
                packet=(rows,deepcopy(progress),deepcopy(loc),deepcopy(battle),deepcopy(enemy),
                        text.get('window_visible') if isinstance(text,dict) else None)
                if rows is None or packet!=prior:
                    return _finish_review(record,_review('capture_switch_new_request_same_frame_conflict'),text,real_now),step_id
            candidate=_construct_switch(capture,target,text,progress,loc,battle,enemy,frame,switch_now)
            if candidate is None:
                proof=_pre_switch_observation(capture,target,text,progress,loc,battle,enemy,frame)
                if (proof is not None and not proof['command'] and snorlax_switch._clock(switch_now)
                        and (capture.last_now is None or switch_now>=capture.last_now)):
                    record['clock_offset']+=pause;record['pause_wall']=None
                    record['pre_switch']={'revision':switch_revision,'target':target,'started_now':switch_now,
                        'last_now':switch_now,'last_frame':frame,'last_packet':None,'calls':1,'waits':0,
                        'capture_preserved':{k:deepcopy(getattr(capture,k)) for k in _PRESERVED_CAPTURE},
                        'enemy':deepcopy(proof['enemy']),'money':progress.get('money'),'party_hp':None}
                    record['bridge_error']=None
                    return _pre_switch_wait(record,proof,frame,switch_now),step_id
                return _finish_review(record,_review('capture_switch_full_command_baseline_rejected'),text,real_now),step_id
            record['clock_offset']+=pause;record['pause_wall']=None
            record['switch']=switch=candidate
            record['switch_revision'],record['switch_target']=switch_revision,target
            record['switch_start_now']=switch_now
            record['switch_capture_preserved']={k:deepcopy(getattr(capture,k)) for k in _PRESERVED_CAPTURE}
            record['bridge_error']=None
        elif switch_revision<record['switch_revision']:
            return _finish_review(record,_review('capture_switch_revision_regressed'),text,real_now),step_id
        elif switch_revision==record['switch_revision'] and target!=record['switch_target']:
            return _finish_review(record,_review('capture_switch_stale_revision_target_changed'),text,real_now),step_id
    if completion is None and switch is not None and not switch_requested:
        return _finish_review(record,_review('capture_switch_request_removed_while_active'),text,real_now),step_id
    controller=completion if completion is not None else switch if switch is not None else capture
    revision=step.get('reviewed_controller_revision',0)
    current_error=controller.error or record.get('bridge_error')
    if (type(revision) is int and revision>record['reviewed_revision'] and current_error is not None
            and step.get('reviewed_controller_error')==current_error and record['pause_wall'] is not None
            and not (controller is capture and current_error==_SAFE_SWITCH_ERROR)):
        record['clock_offset']+=max(0.,real_now-record['pause_wall'])
        record['pause_wall']=None;record['reviewed_revision']=revision;controller.error=None;record['bridge_error']=None
        if step.get('reviewed_budget_reset') is True and controller is capture:
            controller.calls=controller.waits=0;controller.started_at=real_now-record['clock_offset']
    now=real_now-record['clock_offset']
    if completion is None and switch is not None:
        preserved=record['switch_capture_preserved']
        if (capture.error!=_SAFE_SWITCH_ERROR or preserved is None
                or any(getattr(capture,k)!=v for k,v in preserved.items())):
            result=_review('capture_switch_original_capture_changed_while_active')
        elif record.get('bridge_error'):
            result=_review(record['bridge_error'])
        else:
            if enemy is None:enemy=_enemy_snapshot(pyboy,frame,loc)
            result=switch.context(text,progress,location=loc,battle_state=battle,enemy_snapshot=enemy,
                                  frame=frame,now=now)
            if result.get('snorlax_switch_complete') is True:
                verified=_switch_completion_verified(capture,switch,text,progress,loc,battle,enemy,frame)
                if verified is None:
                    record['bridge_error']='capture_switch_completion_not_verified'
                    result=_review(record['bridge_error'])
                else:
                    active_index,party_hp=verified
                    # Exclude all active switch time, separately from already
                    # excluded engineering pauses. Keep the original capturer.
                    record['clock_offset']+=max(0.,now-record['switch_start_now'])
                    capture.active_index,capture.party_hp=active_index,party_hp
                    capture.error,capture.stage=None,'command'
                    capture.command_pending=capture.bag_pending=None
                    capture.failure_pending=capture.prompt_pending=None
                    record['last_switch_controller']=switch
                    record['last_switch_receipt']=deepcopy(result)
                    record['last_switch_frame']=frame
                    record['switch']=None;record['switch_start_now']=None
                    record['switch_capture_preserved']=None;record['pause_wall']=None
                    record['bridge_error']=None
                    result={**result,'phase':'capture_switch_handoff','objective':'Wait.',
                        'available_actions':['wait'],'capture_complete':False,'capture_resume_pending':True,
                        'capture_controller_preserved':True,'capture_throw_requests':capture.throws}
        return _finish_review(record,result,text,real_now),step_id
    if completion is None:
        switch_frame=record['last_switch_frame']
        if switch_frame is not None:
            if type(frame) is not int or type(switch_frame) is not int or frame<switch_frame:
                return _finish_review(record,_review('capture_switch_resume_frame_invalid_or_regressed'),text,real_now),step_id
            if frame==switch_frame:
                return {'phase':'capture_switch_handoff','objective':'Wait.','available_actions':['wait'],
                    'capture_complete':False,'capture_resume_pending':True,
                    'capture_controller_preserved':True,'capture_throw_requests':capture.throws},step_id
        if enemy is None:enemy=_enemy_snapshot(pyboy,frame,loc)
        result=capture.context(text,progress,location=loc,battle_state=battle,enemy_snapshot=enemy,
            frame=frame,now=now,intent=step['capture_intent'])
        if result.get('capture_completion_handoff') is True:
            try:
                completion=capture_completion.CaptureCompletionController(capture_completion.INTENT,
                    last_throw=result['last_throw'])
            except (ValueError,TypeError,KeyError):
                record['bridge_error']='capture_completion_baseline_rejected'
                if record['pause_wall'] is None:record['pause_wall']=real_now
                return _review('capture_completion_baseline_rejected'),step_id
            record['completion']=completion
        else:
            result={**result,'wild_enemy_snapshot':enemy}
    if completion is not None:
        from .campaign_transactions import ui_overworld_ready
        result=completion.context(text,progress,location=loc,battle_state=battle,frame=frame,now=now,
                                  overworld_ready=ui_overworld_ready(text,grid),grid=grid)
        result={**result,'last_throw_observation_frame':completion.baseline['frame']}
    result=_finish_review(record,result,text,real_now)
    if result.get('capture_complete') is True:
        record['done']=True
        result={**result,'field_move_complete':True,'field_move_kind':'snorlax_capture_verified'}
        index=plan['steps'].index(step)+1
        return result,plan['steps'][index]['id'] if index<len(plan['steps']) else 'complete'
    return result,step_id
