"""One-event receiver semantics and opaque runtime approval. No I/O or dispatch."""
from copy import deepcopy
import hashlib
import json

SOURCE_COMMIT='a53671100ec22e5394ff26ec028d0812a238dae2'
JOB='league-six-party45-game29-20261028'
PROFILE='red-en-eevee37-bite-owned-normal-learning-v1'
OLD,NEW=[33,28,98,39],[44,28,98,39]
_MINT=object()


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def integer(v,lo=0,hi=2**63-1):return type(v) is int and lo<=v<=hi
def require(ok,message):
    if not ok:raise ValueError(message)


def resources(snapshot,normalize):
    require(type(snapshot) is dict and set(snapshot)=={'party','inventory','money','badges_raw','player_name_raw','story_event_bits'},
            'learning_resources_missing')
    result=normalize(dict(profile='gen1-wrapper-ram-progress-v1-unvalidated',initialization_candidate=True,
                          party_read_valid=True,party_count=6,**deepcopy(snapshot)))
    require(result is not None,'learning_resources_invalid')
    return result


def proof_semantics(proof,normalize,*,closed_frames=None,expected_owner=None,expected_step_sha=None,
                    expected_binding_sha=None,expected_controller_sha=None):
    require(type(proof) is dict and proof.get('profile')==PROFILE and proof.get('source_commit')==SOURCE_COMMIT
        and proof.get('job')==JOB,'learning_source_or_job_invalid')
    body=deepcopy(proof);sha=body.pop('receipt_sha256',None)
    require(type(sha) is str and digest(body)==sha,'learning_proof_digest_invalid')
    for key,value in (('species',102),('natural_level',37),('new_move',44),('forgotten_move',33),('replace_index',0)):
        require(type(proof.get(key)) is int and proof[key]==value,'learning_case_not_exact')
    require(proof.get('before_moves')==OLD and proof.get('after_moves')==NEW
        and all(type(v) is int for v in proof['before_moves']+proof['after_moves'])
        and type(proof.get('bite_pp_reset')) is dict and proof['bite_pp_reset']==dict(raw=25,pp_ups=0)
        and all(type(v) is int for v in proof['bite_pp_reset'].values()),'learning_moves_or_pp_reset_invalid')
    for key,expected in (('owner_step',expected_owner),('step_sha256',expected_step_sha),
                         ('batch_binding_sha256',expected_binding_sha),('controller_source_sha256',expected_controller_sha)):
        require(type(proof.get(key)) is str and bool(proof[key]) and (expected is None or proof[key]==expected),
                'learning_owner_or_source_binding_invalid')
    pre=resources(proof.get('before_resources'),normalize);post=resources(proof.get('after_resources'),normalize)
    require(digest(proof['before_resources'])==proof.get('before_resources_sha256')
        and digest(proof['after_resources'])==proof.get('after_resources_sha256'),'learning_resource_digest_invalid')
    indexes=[i for i,m in enumerate(pre['party']) if m['species']==102]
    require(len(indexes)==1,'learning_unique_eevee_required');index=indexes[0]
    require(pre['party'][index]['level']==37 and pre['party'][index]['moves']==OLD,'learning_pre_case_invalid')
    expected=deepcopy(pre);expected['party'][index]['moves']=list(NEW);expected['party'][index]['pp'][0]=25
    require(post==expected,'learning_not_exact_single_slot_reset')
    frames=proof.get('observed_learned_frames');acks=proof.get('actual_dispatch_acks');ui=proof.get('ui_frames')
    require(type(frames) is list and len(frames)==2 and all(integer(f) for f in frames) and frames[0]<frames[1]
        and type(acks) is list and bool(acks) and type(ui) is list,'learning_fresh_or_ack_chain_missing')
    ids=set();last=-1
    for ack in acks:
        require(type(ack) is dict and type(ack.get('request_id')) is str and ack['request_id'] not in ids
            and ack.get('owner_step')==proof['owner_step'] and ack.get('action') in ('a','up','down')
            and integer(ack.get('requested_frame')) and integer(ack.get('executed_frame'))
            and last<ack['executed_frame'] and ack['requested_frame']<ack['executed_frame'],
            'learning_actual_ack_chain_invalid')
        ids.add(ack['request_id']);last=ack['executed_frame']
    def actual_a(page):
        candidates=[ack for entry in ui if type(entry) is dict and entry.get('page')==page
                    for ack in acks if ack['action']=='a' and ack['requested_frame']==entry.get('frame')]
        require(bool(candidates),'learning_required_selection_ack_missing:'+page)
        return candidates[-1]
    forget=actual_a('WHICHMOVESHOULDBEFORGOTTEN');and_ack=actual_a('AND')
    require(forget['executed_frame']<and_ack['requested_frame']<and_ack['executed_frame']<=frames[0],
            'learning_selection_frame_order_invalid')
    require(all(any(type(entry) is dict and entry.get('frame')==f and entry.get('page')=='EEVEELEARNEDBITE'
                    for entry in ui) for f in frames),'learning_two_complete_learned_pages_missing')
    dismiss=proof.get('dismiss_ack');handoff=proof.get('handoff_frame')
    require(type(dismiss) is dict and dismiss in acks and dismiss.get('action')=='a'
        and dismiss.get('requested_frame')==frames[1] and integer(handoff)
        and frames[1]<dismiss['executed_frame']<handoff,'learning_dismiss_or_handoff_invalid')
    if closed_frames is not None:
        require(type(closed_frames) is list and len(closed_frames)==2
            and all(integer(f) for f in closed_frames) and handoff<=closed_frames[0]<closed_frames[1],
            'learning_after_batch_close')
    return pre,post,index


class ApprovedLearning:
    """Only a bridge-owned original-object record can pass verify(). Never JSON."""
    def __init__(self,key,*,controller,native,binding,baseline,proof,receipt,verify_origin):
        require(key is _MINT,'learning_approval_cannot_be_constructed_from_json')
        self.controller=controller;self.native=native;self.binding=binding;self.baseline=baseline
        self.proof=proof;self.receipt=deepcopy(receipt);self.receipt_sha=digest(receipt)
        self.baseline_sha=digest(baseline);self._verify_origin=verify_origin
    def verify(self,before):
        from laya_pokemon import league_training_batch_bridge as canonical_bridge
        require(type(self) is ApprovedLearning and before is self.baseline
            and self.controller.baseline is before and digest(before)==self.baseline_sha
            and digest(self.receipt)==self.receipt_sha and canonical_bridge._learning_origin_valid(self),
            'original_learning_approval_missing_or_changed')
    def projection_authorized(self,batch_receipt):
        from laya_pokemon import league_training_batch_bridge as canonical_bridge
        self.verify(self.baseline)
        require(self.controller.complete is True and self.controller.receipt==batch_receipt
            and canonical_bridge._learning_origin_valid(self,completed=True)
            and batch_receipt.get('learning',{}).get('proof_receipt')==self.receipt,
            'original_completed_batch_learning_required')


def mint(**kwargs):
    from laya_pokemon import league_training_batch_bridge as canonical_bridge
    require(kwargs.get('verify_origin') is canonical_bridge._learning_origin_valid,
            'only_canonical_bridge_may_mint_learning_approval')
    return ApprovedLearning(_MINT,**kwargs)


def calculate(before,after,proof,*,normalize,base_validator,needs_center,closed_frames=None):
    """Pure semantics only. Caller must first establish an opaque runtime approval."""
    pre,post,index=proof_semantics(proof,normalize,closed_frames=closed_frames)
    require(before['party'][index]['species']==102 and before['party'][index]['level']==36
        and before['party'][index]['moves']==OLD and after['party'][index]['level']==37
        and after['party'][index]['moves']==NEW,'learning_only_eevee36_to37_allowed')
    reason,_=base_validator(before,pre)
    require(reason is None,'learning_pre_wild_delta_invalid:'+str(reason))
    require(all(before[k]==pre[k]==post[k]==after[k] for k in before if k!='party'),
            'learning_world_resources_changed')
    require(len(before['party'])==len(after['party'])==6,'learning_roster_size_changed')
    gain=spent=0;mutable={'level','exp','hp','max_hp','status','pp'}
    pre_spent=post_spent=0
    for i,(old,new,p0,p1) in enumerate(zip(before['party'],after['party'],pre['party'],post['party'])):
        compare=deepcopy(new)
        if i==index:compare['moves'][0]=33
        require({k:v for k,v in old.items() if k not in mutable}=={k:v for k,v in compare.items() if k not in mutable},
                'party_or_moves_change_requires_review')
        level=new['level']-old['level'];exp=new['exp']-old['exp'];growth=new['max_hp']-old['max_hp']
        require(0<=level<=1 and 0<=exp<=8192 and 0<=growth<=12 and not (level==0 and growth)
            and not (level and exp==0) and 1<=new['hp']<=old['hp']+growth,'wild_level_exp_hp_delta_unverified')
        require(new['exp']>=p1['exp'] and new['level']>=p1['level'] and new['max_hp']>=p1['max_hp']
            and new['hp']<=p1['hp']+new['max_hp']-p1['max_hp'],'learning_post_resources_regressed_or_healed')
        gain+=exp
        for slot,(oldpp,newpp,prepp,postpp) in enumerate(zip(old['pp'],new['pp'],p0['pp'],p1['pp'])):
            if i==index and slot==0:
                require(oldpp>>6==prepp>>6==newpp>>6==0 and 0<=prepp<=oldpp<=35 and postpp==25 and 0<=newpp<=25,
                        'learning_tackle_bite_pp_delta_invalid')
                pre_spent=oldpp-prepp;post_spent=25-newpp;spent+=pre_spent+post_spent
            else:
                require(oldpp>>6==prepp>>6==postpp>>6==newpp>>6
                    and (newpp&63)<=(postpp&63)<=(prepp&63)<=(oldpp&63),'wild_pp_gain_unverified')
                spent+=(oldpp&63)-(newpp&63)
    require(0<gain<=8192 and 0<=spent<=128,'single_wild_reward_or_pp_bound_unverified')
    return dict(total_exp_gain=gain,total_pp_spent=spent,
        levels_before=[m['level'] for m in before['party']],levels_after=[m['level'] for m in after['party']],
        needs_center=bool(needs_center(after))),dict(pre_learning=pre_spent,post_learning=post_spent)


def approved_delta(before,after,approval,*,normalize,base_validator,needs_center):
    require(type(approval) is ApprovedLearning,'opaque_learning_approval_required')
    approval.verify(before)
    result,split=calculate(before,after,approval.receipt,normalize=normalize,base_validator=base_validator,needs_center=needs_center)
    result['learning']=dict(proof_receipt=deepcopy(approval.receipt),baseline_resources=deepcopy(before),
        final_resources=deepcopy(after),baseline_resources_sha256=digest(before),final_resources_sha256=digest(after),
        tackle_bite_pp_spent=split)
    return result


def validate_package(package,*,normalize,base_validator,needs_center,closed_frames=None,expected_owner=None,
                     expected_step_sha=None,expected_binding_sha=None,expected_controller_sha=None):
    require(type(package) is dict and set(package)=={'proof_receipt','baseline_resources','final_resources',
        'baseline_resources_sha256','final_resources_sha256','tackle_bite_pp_spent'},'learning_package_invalid')
    before=package['baseline_resources'];after=package['final_resources'];proof=package['proof_receipt']
    require(digest(before)==package['baseline_resources_sha256'] and digest(after)==package['final_resources_sha256'],
            'learning_package_resource_digest_invalid')
    # Re-run the ordinary source resource validator, without inventing a progress observation.
    before=resources(before,normalize);after=resources(after,normalize)
    proof_semantics(proof,normalize,closed_frames=closed_frames,expected_owner=expected_owner,
        expected_step_sha=expected_step_sha,expected_binding_sha=expected_binding_sha,expected_controller_sha=expected_controller_sha)
    result,split=calculate(before,after,proof,normalize=normalize,base_validator=base_validator,
                           needs_center=needs_center,closed_frames=closed_frames)
    require(type(package['tackle_bite_pp_spent']) is dict and package['tackle_bite_pp_spent']==split
            and all(type(v) is int for v in package['tackle_bite_pp_spent'].values()),
            'learning_split_pp_invalid')
    return result,before,after
