"""Pure Eevee37 evidence wrapper; no dispatch, emulator, file I/O or batch exemptions.

Only the trusted normal dispatcher may call acknowledge_actual_execution after it
actually executes a matching offered request. JSON output is never that ACK.
"""
from copy import deepcopy
import hashlib
import json
import re

SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
CONTROLLER_SOURCE_SHA256 = 'fb5e201c98a2fa232db53429b517e317aaea99152782aaa7aeaefafb16699279'
JOB = 'league-six-party45-game29-20261028'
PROFILE = 'red-en-eevee37-bite-owned-normal-learning-v1'
HANDOFF_PRIMARY_BLOBS = {'data/text/text_2.asm':'917feb8953c9c2b688395dfb54459b1d04bf7a71',
                        'engine/battle/experience.asm':'f9f47f82573771b108df6db4dacecb634a156a24'}
BEFORE, AFTER = (33, 28, 98, 39), (44, 28, 98, 39)
NAMES = {102:'EEVEE',132:'SNORLAX',154:'VENUSAUR',35:'FEAROW',7:'NIDOKING',19:'LAPRAS'}
BASE_PP = {33:35,28:15,98:30,39:30,44:25,75:25,15:30,73:10,22:10,70:15,
           133:20,156:10,34:15,64:35,65:20,19:15,31:20,61:20,57:15,30:25,40:35,58:10,85:15}
_ACTIVE = globals().get('_ACTIVE')
_DONE = globals().get('_DONE', {})
MAX_CALLS, MAX_FRAMES, MAX_WAITS = 160, 3600, 30


def sha(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
        separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()


def integer(value, low=0, high=2**63-1):
    return type(value) is int and low <= value <= high


def compact(text):
    return re.sub('[^A-Z0-9]', '', text.upper())


def review(reason):
    if _ACTIVE is not None:
        _ACTIVE.error = _ACTIVE.error or reason
        reason = _ACTIVE.error
    return dict(phase='strategy_review',objective='Wait.',available_actions=['wait'],
                learning_controller=PROFILE,review_reason='eevee37_' + reason)


def wait(reason):
    return dict(phase='learning_menu',objective='Wait.',available_actions=['wait'],
                learning_controller=PROFILE,learning_tactic=reason)


def bounded_wait(proof,reason):
    proof.waits+=1
    closure=getattr(proof,'dismiss_review',None)
    if closure is not None:
        if not _dismiss_review_valid(proof):raise ValueError('reviewed_dismiss_metadata_unverified')
        closure['waits']+=1
        if closure['waits']>8:raise ValueError('reviewed_dismiss_wait_budget_exhausted')
    elif proof.waits>MAX_WAITS:raise ValueError('source_wait_budget_exhausted')
    return wait(reason)


def _dismiss_review_valid(proof):
    try:
        r=proof.dismiss_review;history=proof.dismiss_review_history;old=history[0]
        return (type(r) is dict and type(history) is list and len(history)==1
            and sha(old)==r['history_sha256'] and r['source_core'] is proof.core_session
            and sha(r['source_pending'])==sha(old['old_pending'])
            and sha(r['source_dismiss_ack'])==sha(old['old_dismiss_ack'])
            and proof.started==old['spent']['started'] and proof.calls>=old['spent']['calls']
            and proof.waits>=old['spent']['waits'] and type(r['requests']) is int and 0<=r['requests']<=2
            and type(r['waits']) is int and 0<=r['waits']<=9)
    except (TypeError,KeyError,AttributeError,IndexError,ValueError):return False


def review_ignored_early_dismiss(binding,review_capsule,*,expected_capsule_sha256,
                                original_proof,original_core_session,text,progress):
    """Root first pins the actual619401 evidence/native/plan; no I/O or dispatch.

    Only named migration may reopen closure. Invalid input changes nothing.
    The original error/pending/ACK/learned frames remain in receipt history;
    original proof, core, ACK list, calls, waits and started are preserved.
    """
    try:
        p=original_controller(binding);cap=review_capsule;frame=binding.get('frame')
        checked=dict(deepcopy(text),observation_frame=frame)
        if (type(expected_capsule_sha256) is not str or sha(cap)!=expected_capsule_sha256
                or cap.get('kind')!='reviewed_early_dismiss_ignored_619401_v1'
                or cap.get('job')!=JOB or cap.get('original_step_id')!=p.key[1]
                or type(cap.get('source_frame')) is not int or cap['source_frame']!=619401
                or frame!=619401 or type(frame) is not int or p.last_frame!=frame
                or p is not original_proof or p.core_session is not original_core_session
                or type(p.core_session) is not dict or p.core_session.get('stage')!='complete'
                or p.core_session.get('replacement_case')!=(102,37)
                or p.error!='source_wait_budget_exhausted' or cap.get('original_error')!=p.error
                or getattr(p,'dismiss_review',None) is not None or getattr(p,'dismiss_review_history',[])!=[]
                or p.complete or p.consumed or p.receipt is not None
                or type(p.calls) is not int or p.calls>=MAX_CALLS
                or type(p.waits) is not int or p.waits<=MAX_WAITS
                or not integer(p.started) or not 0<=frame-p.started<MAX_FRAMES
                or p.forget_ack is None or p.and_ack is None
                or type(p.pending) is not dict or p.pending.get('purpose')!='dismiss_learned'
                or p.pending.get('frame')!=618161 or p.pending.get('ack')!=p.dismiss_ack
                or p.dismiss_ack not in p.acks or p.dismiss_ack.get('action')!='a'
                or p.dismiss_ack.get('requested_frame')!=618161 or p.dismiss_ack.get('executed_frame')!=618201
                or p.learned_frames!=[618121,618161]
                or cap.get('closure_max_waits')!=8 or type(cap.get('closure_max_waits')) is not int
                or cap.get('closure_max_requests')!=2 or type(cap.get('closure_max_requests')) is not int
                or sha(progress)!=sha(cap.get('source_progress')) or snapshot(progress)!=p.after
                or sha((checked,progress,binding.get('battle_state')))!=sha(p.last_packet)):
            return None
        rows=rows_checked(checked,frame,'gen1-visible-tile-text-candidates-v1-unvalidated')
        if compact('\n'.join(rows[12:]))!='EEVEELEARNEDBITE':return None
        old=dict(kind=cap['kind'],capsule_sha256=expected_capsule_sha256,source_frame=frame,
            original_error=p.error,old_pending=deepcopy(p.pending),old_dismiss_ack=deepcopy(p.dismiss_ack),
            old_learned_frames=list(p.learned_frames),source_evidence_sha256=deepcopy(cap.get('source_evidence_sha256')),
            plan_sha256=cap.get('plan_sha256'),original_deadline=cap.get('original_deadline'),
            spent=dict(calls=p.calls,waits=p.waits,started=p.started))
        metadata=dict(source_core=p.core_session,source_pending=p.pending,source_dismiss_ack=p.dismiss_ack,
            history_sha256=sha(old),waits=0,requests=0,retry_history=[])
        p.dismiss_review_history=[old];p.dismiss_review=metadata
        p.error=None;p.pending=None;p.dismiss_ack=None;p.learned_frames=[]
        return wait('reviewed_dismiss_fresh_prompt_required')
    except (ValueError,TypeError,KeyError,AttributeError,IndexError):return None


def binding_parts(binding):
    if not isinstance(binding,dict):
        raise ValueError('trusted_dispatch_binding_missing')
    owner=binding.get('native_owner')
    if owner is None or type(owner) in (str,int,float,bool,list,tuple,dict,bytes):
        raise ValueError('native_owner_object_missing')
    for key in ('step_sha256','batch_binding_sha256'):
        value=binding.get(key)
        if type(value) is not str or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('binding_digest_unknown')
    if (binding.get('job') != JOB or type(binding.get('owner_step')) is not str
            or not binding['owner_step'] or binding.get('controller_source_sha256') != CONTROLLER_SOURCE_SHA256):
        raise ValueError('job_step_or_source_changed')
    return owner,(binding['job'],binding['owner_step'],binding['step_sha256'],binding['batch_binding_sha256'],
                  binding['controller_source_sha256'])


def snapshot(progress):
    if (not isinstance(progress,dict) or progress.get('profile')!='gen1-wrapper-ram-progress-v1-unvalidated'
            or progress.get('initialization_candidate') is not True or progress.get('party_read_valid') is not True
            or type(progress.get('party_count')) is not int or progress['party_count']!=6):
        raise ValueError('source_progress_unverified')
    mons=progress.get('party')
    if (not isinstance(mons,list) or len(mons)!=6 or any(not isinstance(m,dict) for m in mons)
            or any(type(m.get('species')) is not int for m in mons)
            or {m['species'] for m in mons}!=set(NAMES)):
        raise ValueError('six_unique_party_required')
    party=[]
    for m in mons:
        if (m.get('species_name')!=NAMES[m['species']] or not integer(m.get('level'),1,100)
                or not integer(m.get('exp'),0,0xffffff) or not integer(m.get('max_hp'),1,999)
                or not integer(m.get('hp'),1,m['max_hp']) or type(m.get('status')) is not int
                or m['status'] not in {*range(8),8,16,32,64}
                or any(not isinstance(m.get(k),list) or len(m[k])!=4 for k in ('moves','pp'))
                or any(type(v) is not int for v in m['moves']+m['pp'])
                or len(set(m['moves']))!=4 or any(v not in BASE_PP for v in m['moves'])):
            raise ValueError('party_values_unverified')
        for move,pp in zip(m['moves'],m['pp']):
            if not 0<=pp<=255 or (pp&63)>BASE_PP[move]*(5+(pp>>6))//5:
                raise ValueError('party_pp_unverified')
        party.append({k:deepcopy(m[k]) for k in ('species','species_name','level','exp','hp','max_hp','status','moves','pp')})
    if (progress.get('player_name_raw')!='KEVIN' or not integer(progress.get('money'),0,999999)
            or not integer(progress.get('badges_raw'),0,255) or not isinstance(progress.get('inventory'),list)
            or not isinstance(progress.get('story_event_bits'),dict)):
        raise ValueError('world_resources_unverified')
    inventory=progress['inventory']
    if (len(inventory)>20 or any(not isinstance(item,dict) or not integer(item.get('item'),1,255)
            or not integer(item.get('quantity'),1,99) for item in inventory)
            or len({item['item'] for item in inventory})!=len(inventory)):
        raise ValueError('inventory_values_unverified')
    result={k:deepcopy(progress[k]) for k in ('player_name_raw','money','badges_raw','inventory','story_event_bits')}
    result['party']=party
    sha(result)  # Reject non-JSON/non-finite resources rather than silently omit them.
    return result


def rows_checked(text,frame,profile):
    if (not isinstance(text,dict) or text.get('profile')!=profile or text.get('read_valid') is not True
            or text.get('alignment_verified') is not True or text.get('read_error') is not None
            or type(text.get('window_visible')) is not bool or type(text.get('observation_frame')) is not int
            or text['observation_frame']!=frame):
        raise ValueError('text_source_or_frame_unverified')
    cells=text.get('cells')
    if (not isinstance(cells,(list,tuple)) or len(cells)!=18
            or any(not isinstance(row,(list,tuple,str)) or len(row)!=20 for row in cells)
            or any(type(c) is not str or not (len(c)==1 or y in (14,16) and c=="'t")
                   for y,row in enumerate(cells) for c in row)):
        raise ValueError('physical_text_cells_unverified')
    raw=[''.join(row) for row in cells]
    selected=[(i,row.rstrip()) for i,row in enumerate(raw) if re.search('[A-Za-z0-9]{2,}',row)][:12]
    if text.get('lines')!=[v for _,v in selected] or text.get('line_rows')!=[i for i,_ in selected]:
        raise ValueError('text_projection_conflict')
    rows=[row.upper() for row in raw]
    if any(re.search('[A-Z0-9!?]',rows[y]) for y in (12,13,15,17)):
        raise ValueError('dialogue_geometry_unknown')
    if any(re.search('[A-Z0-9!?]',cells[y][x].upper()) for y in (14,16) for x in (0,19)):
        raise ValueError('dialogue_border_geometry_unknown')
    if any(c=='▼' and (x,y)!=(18,16) for y,row in enumerate(cells) for x,c in enumerate(row)):
        raise ValueError('continuation_arrow_geometry_unknown')
    if any(c=='▷' and (x,y)!=(0,3) for y,row in enumerate(cells) for x,c in enumerate(row)):
        raise ValueError('inactive_cursor_geometry_unknown')
    active=[(x,y) for y,row in enumerate(cells) for x,c in enumerate(row) if c=='▶']
    if len(active)>1:
        raise ValueError('multiple_active_cursors')
    labels={label:[(m.start(),y) for y,row in enumerate(rows)
                   for m in re.finditer(r'(?<![A-Z])'+label+r'(?![A-Z])',row)] for label in ('YES','NO')}
    if any(labels.values()):
        if (any(len(labels[label])!=1 for label in labels) or labels['YES'][0][0] not in (15,16)
                or labels['YES'][0][1]!=8 or labels['NO'][0]!=(labels['YES'][0][0],10)
                or len(active)!=1 or active[0] not in ((labels['YES'][0][0]-1,8),(labels['YES'][0][0]-1,10))):
            raise ValueError('source_yes_no_geometry_unknown')
    elif active:
        expected=('TACKLE','SANDATTACK','QUICKATTACK','TAILWHIP')
        if (tuple(compact(rows[y][6:]) for y in range(8,12))!=expected
                or active[0][0]!=5 or active[0][1] not in range(8,12)):
            raise ValueError('source_four_move_cursor_geometry_unknown')
    return rows


def original_controller(binding):
    owner,key=binding_parts(binding)
    proof=_ACTIVE if _ACTIVE is not None and _ACTIVE.key==key else _DONE.get(key)
    if proof is None or proof.owner is not owner:
        raise ValueError('original_learning_controller_missing')
    return proof


def acknowledge_actual_execution(binding,request_id,*,action,executed_frame):
    """Trusted normal-dispatch hook AFTER actual execution; never call for WAIT/hints."""
    try:
        proof=original_controller(binding)
        if proof.error or proof.complete or proof.pending is None:
            raise ValueError('ack_without_pending_original_request')
        p=proof.pending
        if (type(request_id) is not str or request_id!=p['request_id'] or p['ack'] is not None
                or type(action) is not str or action!=p['action'] or not integer(executed_frame)
                or executed_frame<=p['frame']):
            raise ValueError('dispatch_ack_mismatch_or_replay')
        p['ack']=dict(request_id=request_id,action=action,requested_frame=p['frame'],executed_frame=executed_frame,
                      owner_step=proof.key[1])
        proof.acks.append(deepcopy(p['ack']))
        s=proof.core_session
        if p['purpose']=='delete_yes':
            s['delete_yes_requested']=True;s['stage']='await_forget'
        elif p['purpose']=='forget_tackle':
            s['stage']='forget_selected';proof.forget_ack=deepcopy(p['ack'])
        elif p['purpose']=='advance_and':
            s['stage']='and_message';s['and_requested']=True;proof.and_ack=deepcopy(p['ack'])
        elif p['purpose']=='dismiss_learned':
            proof.dismiss_ack=deepcopy(p['ack'])
        return True
    except (ValueError,TypeError,KeyError) as exc:
        review(str(exc));return False


def completed_receipt(binding,*,controller,consume=False):
    proof=original_controller(binding)
    if proof is not controller or not proof.complete or proof.error or proof.receipt is None:
        raise ValueError('original_completed_learning_controller_required')
    if type(consume) is not bool or consume and proof.consumed:
        raise ValueError('learning_receipt_already_consumed')
    content=deepcopy(proof.receipt);expected=content.pop('receipt_sha256',None)
    if expected!=sha(content):raise ValueError('completed_learning_receipt_mutated')
    if consume:proof.consumed=True
    return deepcopy(proof.receipt)


class Proof:
    def __init__(self,owner,key,frame,before,battle):
        self.owner,self.key,self.started=owner,key,frame
        self.before=deepcopy(before);self.after=deepcopy(before)
        self.index=next(i for i,m in enumerate(before['party']) if m['species']==102)
        self.enemy=battle.get('opponent_species')
        if (type(self.enemy) is not str or not self.enemy
                or battle.get('wild_opponent_species',self.enemy)!=self.enemy):
            raise ValueError('same_wild_enemy_identity_required')
        learner=before['party'][self.index]
        if learner['level']!=37 or tuple(learner['moves'])!=BEFORE:
            raise ValueError('exact_eevee37_initial_moves_required')
        self.after['party'][self.index]['moves']=list(AFTER)
        self.after['party'][self.index]['pp'][0]=25
        self.core_session=None;self.error=None;self.calls=0;self.waits=0
        self.last_frame=None;self.last_packet=None;self.pending=None;self.sequence=0
        self.acks=[];self.forget_ack=None;self.and_ack=None;self.dismiss_ack=None
        self.learned_frames=[];self.ui_frames=[];self.complete=False;self.receipt=None;self.consumed=False
        self.dismiss_review=None;self.dismiss_review_history=[]


def guarded_context(text,progress,*,binding,core,get_session,clear_session,text_profile):
    global _ACTIVE
    raw=text.get('cells',[]) if isinstance(text,dict) else []
    try:lower=compact(''.join(''.join(row) for row in raw[12:])) if isinstance(raw,(list,tuple)) else ''
    except (TypeError,ValueError):lower=''
    start=lower.startswith('EEVEEIS') and 'TRYINGTOLEARN' in lower
    if _ACTIVE is None and not start:
        existing=get_session()
        if isinstance(existing,dict) and existing.get('replacement_case')==(102,37):
            return review('original_learning_proof_missing')
        return core(text,progress)
    try:
        owner,key=binding_parts(binding)
        frame=binding.get('frame');battle=binding.get('battle_state')
        if (not integer(frame) or not isinstance(battle,dict) or type(battle.get('observation_frame')) is not int
                or battle['observation_frame']!=frame or type(battle.get('raw')) is not int
                or type(battle.get('active')) is not bool or type(battle.get('kind')) is not str
                or (battle.get('raw'),battle.get('kind'),battle.get('active')) not in ((1,'wild',True),(0,'none',False))):
            raise ValueError('native_frame_or_single_wild_unverified')
        if 'observation_frame' in progress and (type(progress['observation_frame']) is not int or progress['observation_frame']!=frame):
            raise ValueError('progress_frame_conflict')
        rows=rows_checked(text,frame,text_profile);current=snapshot(progress)
        if _ACTIVE is None:
            if battle['raw']!=1:raise ValueError('new_learning_requires_owned_wild')
            if get_session() is not None:raise ValueError('another_learning_controller_active')
            _ACTIVE=Proof(owner,key,frame,current,battle)
        p=_ACTIVE
        if p.error:return review(p.error)
        if getattr(p,'dismiss_review',None) is not None and not _dismiss_review_valid(p):
            raise ValueError('reviewed_dismiss_metadata_unverified')
        if p.owner is not owner or p.key!=key:raise ValueError('native_owner_or_plan_binding_changed')
        if battle['raw']==1 and (battle.get('opponent_species')!=p.enemy
                or battle.get('wild_opponent_species',p.enemy)!=p.enemy):
            raise ValueError('wild_enemy_identity_changed')
        if p.core_session is not None and get_session() is not p.core_session:
            raise ValueError('original_replacement_controller_missing')
        p.calls+=1
        if p.calls>MAX_CALLS or frame-p.started>MAX_FRAMES:raise ValueError('frame_or_call_budget_exhausted')
        if p.last_frame is not None and frame<p.last_frame:raise ValueError('frame_regressed')
        packet=deepcopy((text,progress,battle))
        if frame==p.last_frame:
            if packet!=p.last_packet:raise ValueError('same_frame_conflict')
            return wait('same_frame_no_resend')
        p.last_frame,p.last_packet=frame,packet
        page=sha(text['cells'])
        if p.dismiss_ack is not None:
            if frame<=p.dismiss_ack['executed_frame']:return bounded_wait(p,'fresh_dismiss_ack_observation_required')
            if current['party'][p.index]!=p.after['party'][p.index]:
                raise ValueError('learner_changed_after_learning')
            if any(current[k]!=p.after[k] for k in current if k!='party'):
                raise ValueError('world_resources_changed_after_learning')
            peer_gains=[]
            for index,(old,new) in enumerate(zip(p.after['party'],current['party'])):
                if index==p.index:continue
                mutable={'exp','level','max_hp','hp'}
                if {k:v for k,v in old.items() if k not in mutable}!={k:v for k,v in new.items() if k not in mutable}:
                    raise ValueError('peer_immutable_resources_changed_after_learning')
                exp=new['exp']-old['exp'];level=new['level']-old['level'];growth=new['max_hp']-old['max_hp']
                if (not 0<=exp<=8192 or not 0<=level<=1 or not 0<=growth<=12
                        or level==0 and growth!=0 or level and exp==0 or new['hp']!=old['hp']+growth):
                    raise ValueError('peer_postlearn_exp_growth_unverified')
                peer_gains.append(dict(species=old['species'],exp_gain=exp,level_gain=level,max_hp_gain=growth))
            page_compact=compact('\n'.join(rows[12:]))
            learned='EEVEELEARNEDBITE'
            if (page_compact and (learned.startswith(page_compact) or 'LEARNED' in page_compact
                    or 'BITE'.startswith(page_compact))):
                closure=getattr(p,'dismiss_review',None)
                if (closure is not None and page_compact==learned and '▼' in '\n'.join(rows[12:])
                        and closure['requests']<2):
                    closure['retry_history'].append(dict(pending=deepcopy(p.pending),dismiss_ack=deepcopy(p.dismiss_ack),
                        learned_frames=list(p.learned_frames),still_visible_frame=frame))
                    p.pending=None;p.dismiss_ack=None;p.learned_frames=[]
                    return bounded_wait(p,'reviewed_dismiss_retry_fresh_prompt_required')
                return bounded_wait(p,'await_actual_learned_page_close')
            handoff_kind='closed_learning_text_window'
            if text['window_visible'] is True:
                if not page_compact:return bounded_wait(p,'await_native_learning_window_close')
                gained=[entry for entry in peer_gains if entry['exp_gain']>0]
                expected_exp=(NAMES[gained[0]['species']]+'GAINED'+str(gained[0]['exp_gain'])+'EXPPOINTS'
                              if len(gained)==1 else None)
                if (battle['raw']==1 and expected_exp is not None and expected_exp.startswith(page_compact)
                        and (page_compact!=expected_exp or '!' not in '\n'.join(rows[12:]))):
                    return bounded_wait(p,'await_complete_peer_exp_handoff_prompt')
                match=re.fullmatch('('+'|'.join(NAMES.values())+r')GAINED([0-9]+)EXPPOINTS',page_compact)
                if (battle['raw']!=1 or len(gained)!=1 or match is None
                        or match[1]!=NAMES[gained[0]['species']] or int(match[2])!=gained[0]['exp_gain']
                        or '!' not in '\n'.join(rows[12:])):
                    raise ValueError('postlearn_visible_handoff_requires_source_review')
                handoff_kind='source_verified_peer_exp_prompt'
            elif any(c!=' ' for row in text['cells'][12:] for c in row):
                raise ValueError('postlearn_closed_text_geometry_unverified')
            if any('▶' in row for row in rows):
                raise ValueError('postlearn_handoff_cursor_conflict')
            # Other real participants may receive EXP after Eevee's LearnMove returns.
            # This receipt proves Eevee's local transaction, never that later XP or the whole wild.
            receipt=dict(profile=PROFILE,source_commit=SOURCE_COMMIT,controller_source_sha256=CONTROLLER_SOURCE_SHA256,
                job=key[0],owner_step=key[1],step_sha256=key[2],batch_binding_sha256=key[3],species=102,
                natural_level=37,enemy_species=p.enemy,new_move=44,forgotten_move=33,replace_index=0,before_moves=list(BEFORE),after_moves=list(AFTER),
                before_resources=deepcopy(p.before),after_resources=deepcopy(p.after),before_resources_sha256=sha(p.before),
                after_resources_sha256=sha(p.after),bite_pp_reset=dict(raw=25,pp_ups=0),
                ui_frames=deepcopy(p.ui_frames),actual_dispatch_acks=deepcopy(p.acks),
                observed_learned_frames=list(p.learned_frames),dismiss_ack=deepcopy(p.dismiss_ack),handoff_frame=frame,
                handoff_progress_sha256=sha(current),peer_postlearn_exp_gains=peer_gains,
                handoff_kind=handoff_kind,handoff_text_window_closed=text['window_visible'] is False,
                handoff_primary_blobs=HANDOFF_PRIMARY_BLOBS.copy(),native_battle_at_handoff=deepcopy(battle),
                receipt_id=key[1]+':eevee37-bite:'+str(p.started)+'-'+str(frame))
            if getattr(p,'dismiss_review',None) is not None:
                receipt['reviewed_dismiss_history']=deepcopy(p.dismiss_review_history)
                receipt['reviewed_dismiss_closure']=dict(waits=p.dismiss_review['waits'],requests=p.dismiss_review['requests'],
                    retry_history=deepcopy(p.dismiss_review['retry_history']))
            receipt['receipt_sha256']=sha(receipt)
            p.complete=True;p.receipt=receipt;_DONE[key]=p;clear_session();_ACTIVE=None
            return dict(phase='learning_menu',objective='Wait.',available_actions=['wait'],learning_controller=PROFILE,
                        learning_complete=True,learning_result='verified_bite_for_tackle',learning_receipt=deepcopy(receipt))
        if current not in (p.before,p.after):raise ValueError('exact_learning_resource_delta_required')
        if current==p.after and p.and_ack is None:raise ValueError('moves_changed_without_actual_and_ack')
        if p.pending is not None:
            if p.pending['ack'] is None:
                if page!=p.pending['page']:
                    prompt_page=sha([[(' ' if c=='▼' else c) for c in row] for row in text['cells']])
                    if (p.pending.get('purpose')=='dismiss_learned' and prompt_page==p.pending.get('prompt_page')
                            and compact('\n'.join(rows[12:]))=='EEVEELEARNEDBITE'):
                        return bounded_wait(p,'await_native_learned_prompt')
                    raise ValueError('ui_changed_without_actual_dispatch_ack')
                if getattr(p,'dismiss_review',None) is not None:bounded_wait(p,'reviewed_dismiss_unexecuted_request')
                return {**p.pending['hint'],'learning_request_id':p.pending['request_id']}
            if frame<p.pending['ack']['executed_frame']:raise ValueError('observation_precedes_actual_ack')
            if page==p.pending['page']:
                if getattr(p,'dismiss_review',None) is not None:return bounded_wait(p,'actual_ack_await_new_source_page')
                p.waits+=1
                if p.waits>MAX_WAITS:raise ValueError('post_ack_transition_wait_exhausted')
                return wait('actual_ack_await_new_source_page')
            p.pending=None
        result=core(text,progress)
        if p.core_session is None:p.core_session=get_session()
        if p.core_session is None or p.core_session.get('replacement_case')!=(102,37):
            raise ValueError('exact_original_replacement_session_required')
        if not isinstance(result,dict) or result.get('review_reason'):
            raise ValueError('normal_core_review:' + str((result or {}).get('review_reason')))
        p.ui_frames.append(dict(frame=frame,page=compact('\n'.join(rows[12:])),resources_sha256=sha(current)))
        result=deepcopy(result);result.pop('learning_complete',None)
        tactic=result.get('learning_tactic');action=next((a for a in result.get('available_actions',[]) if a in ('a','up','down')),None)
        purpose={'accept_verified_tackle_replacement':'delete_yes','forget_only_verified_tackle':'forget_tackle',
                 'advance_verified_learning_and':'advance_and','verified_bite_learned':'dismiss_learned',
                 'dismiss_verified_bite_learned':'dismiss_learned'}.get(tactic,'advance_source_page')
        if action!='a' and purpose in ('delete_yes','forget_tackle','advance_and','dismiss_learned'):
            purpose='navigate_' + purpose
        if purpose=='dismiss_learned':
            if (p.forget_ack is None or p.and_ack is None or current!=p.after
                    or compact('\n'.join(rows[12:]))!='EEVEELEARNEDBITE'):
                raise ValueError('learned_result_without_verified_chain')
            if '▼' not in '\n'.join(rows[12:]):
                return bounded_wait(p,'await_native_learned_prompt')
            p.learned_frames.append(frame)
            if len(p.learned_frames)<2:return bounded_wait(p,'first_fresh_complete_learned_resources')
            if not p.learned_frames[0]<p.learned_frames[1]:raise ValueError('two_fresh_learned_frames_required')
            p.learned_frames=p.learned_frames[:2]
        if action is None:
            p.waits+=1
            if p.waits>MAX_WAITS:raise ValueError('source_wait_budget_exhausted')
            return result
        if getattr(p,'dismiss_review',None) is None:p.waits=0
        elif purpose=='dismiss_learned':
            if p.dismiss_review['requests']>=2:raise ValueError('reviewed_dismiss_request_budget_exhausted')
            p.dismiss_review['requests']+=1
        p.sequence+=1
        request_id=key[1]+':learn:'+str(p.sequence)
        p.pending=dict(request_id=request_id,frame=frame,action=action,purpose=purpose,page=page,hint=result,ack=None)
        if purpose=='dismiss_learned':
            p.pending['prompt_page']=sha([[(' ' if c=='▼' else c) for c in row] for row in text['cells']])
        return {**result,'learning_request_id':request_id,'learning_evidence_pending':True}
    except (ValueError,KeyError,TypeError,IndexError) as exc:
        return review(str(exc))
