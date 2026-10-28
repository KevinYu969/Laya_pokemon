"""Synthetic normal UI/ACK -> owned batch -> JSON EOF learning receiver tests."""
from copy import deepcopy
import json
import re
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from laya_pokemon import league_training_batch as batch
from laya_pokemon import league_training_batch_bridge as bridge
from laya_pokemon import league_training_learning_receiver as receiver
from laya_pokemon import league_training_supervisor as sup
from laya_pokemon import levelup_moves as ui
learn=ui.eevee37_learning_proof



import hashlib
import inspect
from pathlib import Path
import pytest
import laya_pokemon

PURE_LF_SHA256 = '77520e26f3f016fd5893838ddfe061198b3a71e20757c7d60b1278e7fefaee18'
PURE_CRLF_SHA256 = '46147c7d6bb92bbd9dd7afd82e81774068310fdd5b8aa50820346186cc613082'


@pytest.fixture(autouse=True)
def isolate_receiver_runtime(monkeypatch):
    for name,value in (('_CONTROLLERS',{}),('_OWNERS',{}),('_BINDINGS',{}),('_COMPLETED',set()),
                       ('_ERRORS',{}),('_REVIEWED_ABORTS',{}),('_LEARNING',{})):
        monkeypatch.setattr(bridge,name,value)
    monkeypatch.setattr(learn,'_ACTIVE',None);monkeypatch.setattr(learn,'_DONE',{})
    monkeypatch.setattr(ui,'_SESSION',None);monkeypatch.setattr(ui.snorlax_harden_skip,'_SESSION',None)


@pytest.fixture(autouse=True)
def canonical_real_loader():
    """Exercise the unchanged production loader and its production byte pins."""
    package_dir = Path(laya_pokemon.__file__).resolve().parent
    pure_path = package_dir / 'league_training_batch.py'
    assert batch.__name__ == 'laya_pokemon.league_training_batch'
    assert bridge.__name__ == 'laya_pokemon.league_training_batch_bridge'
    assert receiver.__name__ == 'laya_pokemon.league_training_learning_receiver'
    assert Path(batch.__file__).resolve() == pure_path
    assert Path(bridge.__file__).resolve() == package_dir / 'league_training_batch_bridge.py'
    assert Path(receiver.__file__).resolve() == package_dir / 'league_training_learning_receiver.py'
    assert package_dir.name == 'laya_pokemon' and package_dir.parent.name == 'src'
    assert hashlib.sha256(pure_path.read_bytes()).hexdigest() in (PURE_LF_SHA256, PURE_CRLF_SHA256)
    assert hashlib.sha256(pure_path.read_bytes()).hexdigest() in bridge.PURE_SHA256S
    loaded = bridge._load_exact()  # Original path check, bytes hash check, and importlib loader.
    assert Path(loaded.__file__).resolve() == pure_path
    assert 'approved_learning' in inspect.signature(loaded.validate_wild_delta).parameters
    assert Path(bridge.batch.__file__).resolve() == pure_path
    assert 'approved_learning' in inspect.signature(bridge.batch.validate_wild_delta).parameters


def progress():
    rows=[(102,'EEVEE',36,93,[33,28,98,39],[35,15,30,30]),(132,'SNORLAX',42,100,[70,133,156,34],[15,20,10,15]),
          (154,'VENUSAUR',37,100,[75,15,73,22],[25,30,10,10]),(35,'FEAROW',39,100,[64,65,19,31],[35,20,15,20]),
          (7,'NIDOKING',37,100,[61,57,30,40],[20,15,25,35]),(19,'LAPRAS',44,181,[57,34,58,85],[15,15,10,15])]
    return dict(profile='gen1-wrapper-ram-progress-v1-unvalidated',initialization_candidate=True,party_read_valid=True,
        party_count=6,player_name_raw='KEVIN',badges_raw=255,money=1000,inventory=[],story_event_bits={},party=[
        dict(species=s,species_name=n,level=lv,hp=hp,max_hp=hp,exp=50638 if s==102 else 100000,status=0,moves=m,pp=p)
        for s,n,lv,hp,m,p in rows])


def text(frame,*items,window=True):
    cells=[[' ']*20 for _ in range(18)]
    for x,y,value in items:
        assert x+len(value)<=20;cells[y][x:x+len(value)]=list(value)
    raw=[''.join(row) for row in cells];selected=[(i,v.rstrip()) for i,v in enumerate(raw) if re.search('[A-Za-z0-9]{2,}',v)][:12]
    return dict(profile=ui.snorlax_harden_skip.TEXT_PROFILE,read_valid=True,alignment_verified=True,read_error=None,
        window_visible=window,observation_frame=frame,cells=cells,lines=[v for _,v in selected],line_rows=[i for i,_ in selected])


class Case:
    def __init__(self,*,zero=False,old_pp=35,pre_pp=None):
        self.native=SimpleNamespace(frame_count=140);self.frame=140;self.before=progress();self.before['party'][0]['pp'][0]=old_pp
        self.step=dict(id=receiver.JOB+'-071-067',kind='interact',mechanic='league_training_batch',map_id=194,target=[28,7],training_intent=deepcopy(batch.INTENT))
        self.key=self.step['id'];self.plan=dict(mode='league_campaign',training_job=receiver.JOB,steps=[self.step])
        self.binding=(bridge.MECHANIC,bridge._canonical(self.step),receiver.JOB)
        self.c=batch.TrainingBatch(batch.INTENT);c=self.c;c.owner=self.key;c.baseline=batch.resources(self.before)
        c.started=c.last_now=0.;c.last_frame=140;c.seen_wild=c.suspended=True;c.displacements=0 if zero else 1
        c.pending=dict(action='down',player=(28,7),expected=(28,8),frame=100,executed=True);c.pending_ack_frame=140
        e=dict(pending=c.pending,snapshot=deepcopy(c.pending),player=(28,7),frame=140,ack_frame=140,raw=1,kind='wild',active=True)
        c.wild_walk_evidence=e
        bridge._CONTROLLERS[self.key]=c;bridge._OWNERS[self.key]=self.native;bridge._BINDINGS[self.key]=self.binding
        if zero:c._zero_bridge_origin=dict(native=self.native,controller=c,binding=self.binding,
            ack=dict(pending=c.pending,snapshot=bridge._canonical(c.pending),frame=140,action='down'),
            wild=dict(pending=c.pending,evidence=e,snapshot=bridge._canonical(e),frame=140,
                location=dict(map_id=194,x=28,y=7),raw=1,kind='wild',active=True),closed=None)
        self.zero=zero;self.current=deepcopy(self.before);m=self.current['party'][0]
        m.update(level=37,exp=50932,max_hp=96,hp=96);m['pp'][0]=old_pp if pre_pp is None else pre_pp;m['pp'][2]=29
        self.proof=None;self.last=None
    def lb(self,raw=1):
        return dict(native_owner=self.native,job=receiver.JOB,owner_step=self.key,step_sha256=bridge._digest(self.step),
            batch_binding_sha256=bridge._digest(self.binding),controller_source_sha256=learn.CONTROLLER_SOURCE_SHA256,
            frame=self.frame,battle_state=dict(raw=raw,kind='wild' if raw==1 else 'none',active=raw==1,
                observation_frame=self.frame,opponent_species='GOLBAT',wild_opponent_species='GOLBAT'))
    def ui_call(self,items=(),*,raw=1,ack=True,closed=False):
        self.frame+=40;self.native.frame_count=self.frame
        self.last=ui.context(text(self.frame,*items,window=not closed),self.current,learning_binding=self.lb(raw))
        assert 'review_reason' not in self.last,self.last
        if ack and 'learning_request_id' in self.last:
            assert learn.acknowledge_actual_execution(self.lb(raw),self.last['learning_request_id'],
                action=self.last['available_actions'][0],executed_frame=self.frame+1)
        return self.last
    def finish_ui(self):
        for items in [((1,14,'EEVEE is'),(1,16,'trying to learn'),(18,16,'▼')),
                      ((1,14,'trying to learn'),(1,16,'BITE!')),
                      ((1,14,'than 4 moves!'),),
                      ((1,14,'Delete an older'),(1,16,'move to make room'),(18,16,'▼')),
                      ((15,8,'YES'),(15,10,'NO'),(14,8,'▶'),(1,14,'for BITE?')),
                      ((6,8,'TACKLE'),(6,9,'SAND-ATTACK'),(6,10,'QUICK ATTACK'),(6,11,'TAIL WHIP'),(5,8,'▶'),(1,14,'Which move should'),(1,16,'be forgotten?')),
                      ((1,14,'1, 2 and... Poof!'),),((1,14,'EEVEE forgot'),(1,16,'TACKLE!')),((1,14,'And...'),)]:self.ui_call(items)
        self.current['party'][0]['moves'][0]=44;self.current['party'][0]['pp'][0]=25
        self.ui_call(((1,14,'EEVEE learned'),(1,16,'BITE!'),(18,16,'▼')))
        self.ui_call(((1,14,'EEVEE learned'),(1,16,'BITE!'),(18,16,'▼')))
        out=self.ui_call(raw=0,closed=True);assert out.get('learning_complete') is True,out
        self.proof=learn.original_controller(self.lb(0));return out
    def approve(self,**changes):
        args=dict(original_controller=self.c,original_binding=self.binding,original_proof=self.proof,learning_binding=self.lb(0));args.update(changes)
        return bridge.consume_owned_eevee37_learning(self.native,self.plan,self.key,**args)
    def packet(self):
        self.frame+=40;self.native.frame_count=self.frame;y=7 if self.zero else 8;loc=dict(map_id=194,x=28,y=y)
        battle=dict(raw=0,kind='none',active=False,observation_frame=self.frame)
        raw={k:0 for k in batch.ADDRESSES};raw.update(map_id=194,x=28,y=y,tileset=17,height=9,width=15)
        state=dict(frame=self.frame,location=loc,battle_state=battle,progress=deepcopy(self.current))
        signal=dict(profile=batch.PROFILE,source_commit=batch.SOURCE_COMMIT,read_valid=True,read_error=None,
            observation_frame=self.frame,location=loc,battle=battle,raw=raw,idle=True,progress=deepcopy(self.current))
        return state,text(self.frame,window=False),dict(frame=self.frame),signal
    def close(self):
        result=None;state=None
        for _ in range(2):
            state,t,g,signal=self.packet()
            with patch.object(bridge.batch,'read_training_observation',return_value=signal),patch.object(bridge.batch,'closed_world',return_value=True):
                result,_=bridge.context(self.native,state,self.plan,self.key,t,g,['wait'],now=self.frame/60)
        return result,state


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        for k,v in (('_CONTROLLERS',{}),('_OWNERS',{}),('_BINDINGS',{}),('_COMPLETED',set()),('_ERRORS',{}),('_REVIEWED_ABORTS',{}),('_LEARNING',{})):setattr(bridge,k,v)
        learn._ACTIVE=None;learn._DONE={};ui._SESSION=None;ui.snorlax_harden_skip._SESSION=None
    def case(self,**kwargs):
        c=Case(**kwargs);c.finish_ui();return c
    def test_ordinary_no_learning_delta_remains_unchanged(self):
        old=batch.resources(progress());new=deepcopy(old);new['party'][0]['exp']+=294;new['party'][0]['pp'][2]-=1
        reason,r=batch.validate_wild_delta(old,new);self.assertIsNone(reason);self.assertEqual((r['total_exp_gain'],r['total_pp_spent']),(294,1));self.assertNotIn('learning',r)
    def test_exact_live_object_approval_reset_does_not_spend_ten_and_baseline_is_untouched(self):
        s=self.case();base=s.c.baseline;sha=bridge._digest(base);approval=s.approve();self.assertIsNotNone(approval)
        reason,r=batch.validate_wild_delta(base,batch.resources(s.current),approval)
        self.assertIsNone(reason);self.assertEqual((r['total_exp_gain'],r['total_pp_spent']),(294,1))
        self.assertEqual(r['learning']['tackle_bite_pp_spent'],dict(pre_learning=0,post_learning=0))
        self.assertIs(s.c.baseline,base);self.assertEqual(bridge._digest(base),sha)
    def test_low_old_pp_reset_and_post_bite_usage_are_split(self):
        s=self.case(old_pp=5,pre_pp=3);approval=s.approve();s.current['party'][0]['pp'][0]=24
        reason,r=batch.validate_wild_delta(s.c.baseline,batch.resources(s.current),approval)
        self.assertIsNone(reason);self.assertEqual(r['total_pp_spent'],4)
        self.assertEqual(r['learning']['tackle_bite_pp_spent'],dict(pre_learning=2,post_learning=1))
    def test_serialized_flags_or_receipt_do_not_create_an_approval(self):
        s=self.case();after=batch.resources(s.current)
        self.assertIsNotNone(batch.validate_wild_delta(s.c.baseline,after)[0])
        self.assertIsNotNone(batch.validate_wild_delta(s.c.baseline,after,deepcopy(s.proof.receipt))[0])
        self.assertFalse(s.proof.consumed)
    def test_public_mint_cannot_trust_an_arbitrary_callback(self):
        with self.assertRaisesRegex(ValueError,'only_canonical_bridge'):
            receiver.mint(controller=None,native=None,binding=None,baseline={},
                          proof=None,receipt={},verify_origin=lambda *a,**k:True)
    def test_foreign_original_objects_or_binding_cannot_consume(self):
        for bad in ('controller','binding','proof','native','step'):
            with self.subTest(bad=bad):
                self.setUp();s=self.case();args={}
                if bad=='controller':args['original_controller']=deepcopy(s.c)
                if bad=='binding':args['original_binding']=tuple(list(s.binding))
                if bad=='proof':args['original_proof']=deepcopy(s.proof)
                if bad=='native':args['learning_binding']={**s.lb(0),'native_owner':object()}
                if bad=='step':args['learning_binding']={**s.lb(0),'step_sha256':'a'*64}
                self.assertIsNone(s.approve(**args));self.assertFalse(s.proof.consumed)
    def test_one_consume_is_cached_and_registry_loss_or_error_revokes_it(self):
        s=self.case();original=learn.completed_receipt;consumes=[]
        def wrapped(*a,**kw):
            if kw.get('consume'):consumes.append(True)
            return original(*a,**kw)
        with patch.object(learn,'completed_receipt',side_effect=wrapped):
            approval=s.approve();self.assertIs(s.approve(),approval)
        self.assertEqual(len(consumes),1)
        bridge._LEARNING={};self.assertIsNotNone(batch.validate_wild_delta(s.c.baseline,batch.resources(s.current),approval)[0])
        self.setUp();s=self.case();s.c.error='league_training_batch_fainted_party_requires_review';self.assertIsNone(s.approve());self.assertFalse(s.proof.consumed)
    def test_pp_up_other_move_hp_and_whole_reward_bounds_are_not_relaxed(self):
        for bad in ('pp_up','other_move','faint','exp_total','pp_gain'):
            with self.subTest(bad=bad):
                self.setUp();s=self.case();a=s.approve();current=batch.resources(s.current)
                if bad=='pp_up':current['party'][0]['pp'][0]=89
                if bad=='other_move':current['party'][1]['moves'][0]=33
                if bad=='faint':current['party'][1]['hp']=0
                if bad=='exp_total':current['party'][1]['exp']+=8192
                if bad=='pp_gain':current['party'][0]['pp'][2]=30
                self.assertIsNotNone(batch.validate_wild_delta(s.c.baseline,current,a)[0])
    def test_positive_batch_projection_eof_and_outbound_continuity_require_the_original_approval(self):
        s=self.case();a=s.approve();result,state=s.close();self.assertTrue(result.get('training_batch_complete'),result)
        with self.assertRaises(Exception):sup.project_completed_batch(s.plan,result,state)
        projected=sup.project_completed_batch(s.plan,result,state,learning_authority=a)
        stored=json.loads(json.dumps(projected));eof={**state,'frame':state['frame']+80}
        self.assertEqual(sup.eof_batch_proof(s.plan,eof,stored),stored)
        with self.assertRaises(Exception):sup.continuity(s.before,eof['progress'],stored)
        permission=sup._learning_continuity_permit(s.before,eof['progress'],s.plan,eof,stored)
        sup.continuity(s.before,eof['progress'],permission)
        with self.assertRaises(Exception):sup.continuity(s.before,eof['progress'])
    def test_zero_displacement_learning_still_requires_the_original_native_walk_witness(self):
        s=self.case(zero=True);s.approve();result,state=s.close();self.assertTrue(result.get('training_batch_complete'),result)
        self.assertEqual(result['training_batch_displacements'],0);self.assertEqual(result['training_batch_receipt']['wild_count'],1)
        self.setUp();s=self.case(zero=True);s.approve();del s.c._zero_bridge_origin
        result,_=s.close();self.assertIn('zero_cancel_original_provenance_unverified',result.get('review_reason',''))
    def test_json_tamper_wrong_frame_and_legacy_projection_never_grant_move_change(self):
        s=self.case();a=s.approve();result,state=s.close();stored=sup.project_completed_batch(s.plan,result,state,a)
        eof={**state,'frame':state['frame']+80};bad=deepcopy(stored)
        bad['batch_receipt']['learning']['proof_receipt']['observed_learned_frames']=[1,1]
        bad['batch_receipt_sha256']=sup.canonical_sha(bad['batch_receipt'])
        with self.assertRaises(Exception):sup.eof_batch_proof(s.plan,eof,bad)
        legacy=deepcopy(stored);legacy.pop('batch_receipt');legacy.pop('batch_receipt_sha256')
        self.assertIsNone(sup._learning_continuity_permit(s.before,eof['progress'],s.plan,eof,legacy))
        with self.assertRaises(Exception):sup.continuity(s.before,eof['progress'])


# Run with pytest so the canonical loader fixture is mandatory.
