"""Self-contained synthetic UI/dispatch evidence; no ROM, emulator, model or keys."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest

ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/'src/laya_pokemon/levelup_moves.py'
NAME='laya_pokemon._eevee37_levelup_ui_test'
spec=importlib.util.spec_from_file_location(NAME,SOURCE)
c=importlib.util.module_from_spec(spec);sys.modules[NAME]=c;spec.loader.exec_module(c)
assert Path(c.__file__).resolve()==SOURCE.resolve()
p=c.eevee37_learning_proof

import pytest
@pytest.fixture(autouse=True)
def restore_shared_proof_state(monkeypatch):
    monkeypatch.setattr(p,'_ACTIVE',None);monkeypatch.setattr(p,'_DONE',{})
    monkeypatch.setattr(c,'_SESSION',None)
    monkeypatch.setattr(c.snorlax_harden_skip,'_SESSION',None)



def progress():
    values=[(102,'EEVEE',37,[33,28,98,39],[35,15,20,30]),
            (132,'SNORLAX',42,[70,133,156,34],[15,20,10,15]),
            (154,'VENUSAUR',36,[75,15,73,22],[25,30,10,10]),
            (35,'FEAROW',38,[64,65,19,31],[35,20,15,20]),
            (7,'NIDOKING',37,[61,57,30,40],[20,15,25,35]),
            (19,'LAPRAS',43,[57,34,58,85],[15,15,10,15])]
    return dict(profile='gen1-wrapper-ram-progress-v1-unvalidated',initialization_candidate=True,
        party_read_valid=True,party_count=6,player_name_raw='KEVIN',badges_raw=255,money=53245,
        inventory=[dict(item=4,quantity=5)],story_event_bits={'synthetic_fixed_bit':True},party=[
            dict(species=s,species_name=name,level=level,exp=50000+i,hp=90,max_hp=90,status=0,moves=moves,pp=pp)
            for i,(s,name,level,moves,pp) in enumerate(values)])


def text(frame,*entries,window=True):
    cells=[[' ']*20 for _ in range(18)]
    for x,y,value in entries:
        assert x+len(value)<=20
        cells[y][x:x+len(value)]=list(value)
    return from_cells(frame,cells,window=window)


def from_cells(frame,cells,*,window=True):
    raw=[''.join(row) for row in cells]
    selected=[(i,row.rstrip()) for i,row in enumerate(raw) if re.search('[A-Za-z0-9]{2,}',row)][:12]
    return dict(profile=c.snorlax_harden_skip.TEXT_PROFILE,read_valid=True,alignment_verified=True,
        read_error=None,window_visible=window,observation_frame=frame,cells=cells,
        lines=[v for _,v in selected],line_rows=[i for i,_ in selected])


def question(frame,*,selected='YES'):
    return text(frame,(15,8,'YES'),(15,10,'NO'),(14,8 if selected=='YES' else 10,'▶'),(1,14,'for BITE?'))


def forget(frame,row=8):
    return text(frame,(6,8,'TACKLE'),(6,9,'SAND-ATTACK'),(6,10,'QUICK ATTACK'),(6,11,'TAIL WHIP'),
                (5,row,'▶'),(0,3,'▷'),(1,14,'Which move should'),(1,16,'be forgotten?'))


class Run:
    def __init__(self):
        self.owner=object();self.frame=100;self.prog=progress();self.last=None
        self.fixed=dict(native_owner=self.owner,job=p.JOB,owner_step='synthetic-owned-batch-067',
            step_sha256='a'*64,batch_binding_sha256='b'*64,controller_source_sha256=p.CONTROLLER_SOURCE_SHA256)
    def binding(self,*,raw=1):
        return {**self.fixed,'frame':self.frame,'battle_state':dict(raw=raw,kind='wild' if raw==1 else 'none',
            active=raw==1,observation_frame=self.frame,opponent_species='GOLBAT',wild_opponent_species='GOLBAT')}
    def call(self,page=None,*,raw=1,advance=True,**binding_changes):
        if advance:self.frame+=40
        if page is None:page=text(self.frame,window=False)
        if callable(page):page=page(self.frame)
        binding={**self.binding(raw=raw),**binding_changes}
        old=deepcopy((page,self.prog))
        self.last=c.context(page,self.prog,learning_binding=binding)
        assert old==(page,self.prog)
        return self.last
    def ack(self,*,action=None,request_id=None,executed_frame=None,binding=None):
        return p.acknowledge_actual_execution(binding or self.binding(),request_id or self.last['learning_request_id'],
            action=action or self.last['available_actions'][0],executed_frame=executed_frame or self.frame+1)
    def step(self,page):
        result=self.call(page)
        if 'learning_request_id' in result:assert self.ack()
        return result
    def intro(self):
        return self.step(lambda f:text(f,(1,14,'EEVEE is'),(1,16,'trying to learn'),(18,16,'▼')))
    def to_question(self):
        self.intro()
        self.step(lambda f:text(f,(1,14,'trying to learn'),(1,16,'BITE!')))
        self.call(lambda f:text(f,(1,14,'But, EEVEE'),(1,16,"can't learn more")))
        self.step(lambda f:text(f,(1,14,'than 4 moves!')))
        self.step(lambda f:text(f,(1,14,'Delete an older'),(1,16,'move to make room'),(18,16,'▼')))
    def to_forget(self):
        self.to_question();return self.step(question)
    def to_and(self):
        self.to_forget();self.step(forget)
        self.step(lambda f:text(f,(1,14,'1, 2 and... Poof!')))
        self.step(lambda f:text(f,(1,14,'EEVEE forgot'),(1,16,'TACKLE!')))
        return self.call(lambda f:text(f,(1,14,'And...')))
    def learned(self):
        self.prog['party'][0]['moves'][0]=44;self.prog['party'][0]['pp'][0]=25
        return self.call(lambda f:text(f,(1,14,'EEVEE learned'),(1,16,'BITE!'),(18,16,'▼')))
    def complete(self):
        self.to_and();assert self.ack();self.learned();self.learned();assert self.ack()
        return self.call(raw=0)


class Eevee37Tests(unittest.TestCase):
    def setUp(self):
        p._ACTIVE=None;p._DONE={};c._SESSION=None;c.snorlax_harden_skip._SESSION=None
    def assertReview(self,result,reason=None):
        self.assertEqual(result['phase'],'strategy_review',result)
        self.assertEqual(result['available_actions'],['wait'])
        if reason:self.assertIn(reason,result['review_reason'])
    def test_explicit_source_plan_preserves_all_three_other_slots(self):
        plan=c.candidate_plan(102,37,[33,28,98,39])
        self.assertEqual((plan['decision'],plan['replace_index'],plan['new_move_id']),('replace',0,44))
        self.assertEqual(plan['forget'],'TACKLE')
        self.assertIn({'level':37,'move':'BITE'},c.reference()['species']['EEVEE']['level_moves'])
        self.assertEqual(c.candidate_plan(102,37,[33,28,98,15])['decision'],'review')
        self.assertEqual(c.candidate_plan(102.0,37,[33,28,98,39])['decision'],'review')
    def test_without_trusted_binding_first_event_stops_without_a(self):
        result=c.context(text(100,(1,14,'EEVEE is'),(1,16,'trying to learn'),(18,16,'▼')),progress())
        self.assertReview(result,'binding_missing');self.assertIsNone(c._SESSION)
    def test_complete_normal_ui_requires_two_fresh_learned_reads_and_actual_dismiss_ack(self):
        r=Run();r.to_and()
        self.assertFalse(c._SESSION['and_requested']);self.assertTrue(r.ack())
        first=r.learned();self.assertNotIn('learning_complete',first);self.assertNotIn('learning_request_id',first)
        second=r.learned();self.assertNotIn('learning_complete',second);self.assertIn('learning_request_id',second)
        self.assertTrue(r.ack());out=r.call(raw=0)
        self.assertTrue(out['learning_complete']);receipt=out['learning_receipt']
        self.assertEqual(receipt['after_moves'],[44,28,98,39]);self.assertEqual(receipt['bite_pp_reset'],dict(raw=25,pp_ups=0))
        self.assertLess(*receipt['observed_learned_frames'])
        self.assertLess(receipt['dismiss_ack']['executed_frame'],receipt['handoff_frame'])
        self.assertIsNone(c._SESSION);self.assertIsNone(p._ACTIVE)
        for ack in receipt['actual_dispatch_acks']:self.assertGreater(ack['executed_frame'],ack['requested_frame'])
    def test_no_ack_cannot_advance_delete_or_forget_or_and(self):
        r=Run();r.to_question();r.call(question)
        self.assertFalse(c._SESSION['delete_yes_requested'])
        self.assertReview(r.call(forget),'without_actual_dispatch_ack')
        self.setUp();r=Run();r.to_forget();r.call(forget)
        self.assertNotEqual(c._SESSION['stage'],'forget_selected')
        self.assertReview(r.call(lambda f:text(f,(1,14,'1, 2 and... Poof!'))),'without_actual_dispatch_ack')
        self.setUp();r=Run();r.to_and();self.assertFalse(c._SESSION['and_requested'])
        self.assertReview(r.learned(),'without_actual_and_ack')
    def test_navigation_ack_is_not_a_confirmation_ack(self):
        r=Run();r.to_question();r.call(lambda f:question(f,selected='NO'))
        self.assertEqual(r.last['available_actions'][0],'up');self.assertTrue(r.ack())
        self.assertFalse(c._SESSION['delete_yes_requested'])
        r.step(question);r.call(lambda f:forget(f,10));self.assertTrue(r.ack())
        self.assertNotEqual(c._SESSION['stage'],'forget_selected')
        r.step(lambda f:forget(f,9));r.call(forget)
        self.assertNotEqual(c._SESSION['stage'],'forget_selected');self.assertTrue(r.ack())
        self.assertEqual(c._SESSION['stage'],'forget_selected')
    def test_wrong_or_replayed_ack_is_sticky_review(self):
        for bad in ('action','request','frame','owner','step'):
            with self.subTest(bad=bad):
                self.setUp();r=Run();r.call(lambda f:text(f,(1,14,'EEVEE is'),(1,16,'trying to learn'),(18,16,'▼')))
                kw={'action':'wait'} if bad=='action' else {'request_id':'wrong'} if bad=='request' else {'executed_frame':r.frame} if bad=='frame' else {'binding':{**r.binding(),'native_owner':object()}} if bad=='owner' else {'binding':{**r.binding(),'owner_step':'foreign'}}
                self.assertFalse(r.ack(**kw));self.assertReview(r.call())
        self.setUp();r=Run();r.intro();self.assertFalse(r.ack());self.assertReview(r.call())
    def test_same_frame_never_reissues_a_or_counts_second_result(self):
        r=Run();page=text(140,(1,14,'EEVEE is'),(1,16,'trying to learn'),(18,16,'▼'))
        r.call(page);self.assertEqual(r.call(page,advance=False)['available_actions'],['wait'])
        other=deepcopy(page);other['cells'][0][0]='?'
        self.assertReview(r.call(other,advance=False),'same_frame_conflict')
    def test_wrong_frame_profile_decoder_or_native_boolean_never_binds(self):
        for bad in ('frame','profile','read_error','raw_bool','active_int'):
            with self.subTest(bad=bad):
                self.setUp();r=Run();page=text(140,(1,14,'EEVEE is'),(1,16,'trying to learn'),(18,16,'▼'))
                changes={}
                if bad=='frame':page['observation_frame']=139
                if bad=='profile':page['profile']='unknown'
                if bad=='read_error':page['read_error']=False
                if bad in ('raw_bool','active_int'):
                    native=r.binding()['battle_state'];native['observation_frame']=140
                    native['raw' if bad=='raw_bool' else 'active']=True if bad=='raw_bool' else 1
                    changes['battle_state']=native
                self.assertReview(r.call(page,**changes));self.assertIsNone(c._SESSION)
    def test_wrong_yes_no_or_four_move_cursor_geometry_stops(self):
        for bad in ('wrong_slot_order','double_cursor','inactive_cursor','wrong_yes_row'):
            with self.subTest(bad=bad):
                self.setUp();r=Run();r.to_question()
                page=question(r.frame+40) if bad=='wrong_yes_row' else forget(r.frame+40)
                if bad=='wrong_yes_row':page['cells'][8][15]=' ';page['cells'][9][15:18]=list('YES')
                else:
                    r.step(question);page=forget(r.frame+40)
                    if bad=='wrong_slot_order':page['cells'][8][6:12]=list('TAIL  ')
                    if bad=='double_cursor':page['cells'][9][5]='▶'
                    if bad=='inactive_cursor':page['cells'][8][5]='▷'
                page=from_cells(page['observation_frame'],page['cells'])
                self.assertReview(r.call(page))
    def test_wrong_pp_reset_or_any_peer_world_change_cannot_complete(self):
        for bad in ('pp','ppup','peer','bag','money','story'):
            with self.subTest(bad=bad):
                self.setUp();r=Run();r.to_and();r.ack()
                r.prog['party'][0]['moves'][0]=44;r.prog['party'][0]['pp'][0]=25
                if bad=='pp':r.prog['party'][0]['pp'][0]=24
                if bad=='ppup':r.prog['party'][0]['pp'][0]=89
                if bad=='peer':r.prog['party'][1]['hp']-=1
                if bad=='bag':r.prog['inventory'][0]['quantity']-=1
                if bad=='money':r.prog['money']-=1
                if bad=='story':r.prog['story_event_bits']['synthetic_fixed_bit']=False
                self.assertReview(r.call(lambda f:text(f,(1,14,'EEVEE learned'),(1,16,'BITE!'))))
    def test_early_moves_forged_learned_and_missing_forgot_are_rejected(self):
        r=Run();r.intro();self.assertReview(r.learned(),'without_actual_and_ack')
        self.setUp();r=Run();r.to_forget();r.step(forget)
        self.assertReview(r.call(lambda f:text(f,(1,14,'And...'))),'normal_core_review')
    def test_lost_original_controller_or_binding_change_stops(self):
        for bad in ('session','owner','step','batch','source'):
            with self.subTest(bad=bad):
                self.setUp();r=Run();r.intro();kw={}
                if bad=='session':c._SESSION=deepcopy(c._SESSION)
                if bad=='owner':kw['native_owner']=object()
                if bad=='step':kw['owner_step']='different-step'
                if bad=='batch':kw['batch_binding_sha256']='c'*64
                if bad=='source':kw['controller_source_sha256']='d'*64
                self.assertReview(r.call(**kw))
    def test_lost_proof_registry_does_not_fall_through_to_old_unacked_core(self):
        r=Run();r.intro();p._ACTIVE=None
        out=r.call(lambda f:text(f,(1,14,'trying to learn'),(1,16,'BITE!')))
        self.assertReview(out,'original_learning_proof_missing')
    def test_receipt_is_json_but_only_original_object_can_claim_once(self):
        r=Run();out=r.complete();proof=p.original_controller(r.binding(raw=0))
        receipt=json.loads(json.dumps(out['learning_receipt']))
        self.assertEqual(p.completed_receipt(r.binding(raw=0),controller=proof,consume=True),receipt)
        with self.assertRaises(ValueError):p.completed_receipt(r.binding(raw=0),controller=proof,consume=True)
        with self.assertRaises(ValueError):p.completed_receipt(r.binding(raw=0),controller=object())
        with self.assertRaises(ValueError):p.original_controller({**r.binding(raw=0),'native_owner':object()})
    def test_budgets_and_frame_regression_are_not_reset(self):
        r=Run();r.intro();r.frame=3741;self.assertReview(r.call(advance=False),'budget_exhausted')
        self.setUp();r=Run();r.intro();r.frame=99;self.assertReview(r.call(advance=False),'frame_regressed')
    def test_partial_intro_or_learned_text_does_not_approve(self):
        r=Run();out=r.call(lambda f:text(f,(1,14,'EEVEE is'),(1,16,'trying to learn')))
        self.assertEqual(out['available_actions'],['wait']);self.assertNotIn('learning_request_id',out)
        self.setUp();r=Run();r.to_and();r.ack();r.prog['party'][0]['moves'][0]=44;r.prog['party'][0]['pp'][0]=25
        out=r.call(lambda f:text(f,(1,14,'EEVEE learned'),(1,16,'BI')))
        self.assertNotIn('learning_complete',out);self.assertNotIn('learning_request_id',out)

    def test_second_learned_read_still_needs_full_source_marker(self):
        r=Run();r.to_and();r.ack();r.learned()
        out=r.call(lambda f:text(f,(1,14,'EEVEE learned'),(1,16,'BITE')))
        self.assertNotIn('learning_complete',out);self.assertNotIn('learning_request_id',out)
        self.assertEqual(len(p._ACTIVE.learned_frames),1)
        self.assertIn('learning_request_id',r.learned())

    def test_source_native_single_tile_cant_is_readable_without_promoting_partial_page(self):
        r=Run();r.intro();r.step(lambda f:text(f,(1,14,'trying to learn'),(1,16,'BITE!')))
        page=text(r.frame+40,(1,14,'But, EEVEE'))
        tokens=['c','a','n',"'t",' ','l','e','a','r','n',' ','m','o','r','e']
        page['cells'][16][1:1+len(tokens)]=tokens
        page=from_cells(r.frame+40,page['cells'])
        out=r.call(page)
        self.assertEqual(out['available_actions'],['wait']);self.assertNotEqual(out['phase'],'strategy_review')

    def test_same_wild_identity_and_receipt_hash_remain_bound(self):
        r=Run();r.intro();changed=r.binding()['battle_state']
        changed.update(opponent_species='GRAVELER',wild_opponent_species='GRAVELER',observation_frame=r.frame+40)
        self.assertReview(r.call(battle_state=changed),'wild_enemy_identity_changed')
        self.setUp();r=Run();r.complete();proof=p.original_controller(r.binding(raw=0))
        proof.receipt['new_move']=85
        with self.assertRaisesRegex(ValueError,'mutated'):
            p.completed_receipt(r.binding(raw=0),controller=proof)

    def test_dismiss_ack_does_not_waive_peer_hp_pp_moves_or_status(self):
        for bad in ('hp','pp','moves','status'):
            with self.subTest(bad=bad):
                self.setUp();r=Run();r.to_and();r.ack();r.learned();r.learned();r.ack()
                peer=r.prog['party'][1]
                if bad=='hp':peer['hp']=1
                if bad=='pp':peer['pp'][0]=0
                if bad=='moves':peer['moves'][0]=33
                if bad=='status':peer['status']=64
                self.assertReview(r.call(raw=0),'peer_')

    def test_dismiss_ack_prefix_or_partial_page_is_not_window_close(self):
        r=Run();r.to_and();r.ack();r.learned();r.learned();r.ack()
        out=r.call(lambda f:text(f,(1,14,'EEVEE learned'),(1,16,'BI')))
        self.assertNotIn('learning_complete',out);self.assertEqual(out['available_actions'],['wait'])
        self.assertFalse(p._ACTIVE.complete)
        self.assertTrue(r.call(raw=0)['learning_complete'])

    def test_after_dismiss_only_bounded_peer_exp_growth_is_admitted_at_closed_window(self):
        r=Run();r.to_and();r.ack();r.learned();r.learned();r.ack()
        peer=r.prog['party'][1];peer['exp']+=294;peer['level']+=1;peer['max_hp']+=3;peer['hp']+=3
        out=r.call(raw=0);self.assertTrue(out['learning_complete'])
        entry=out['learning_receipt']['peer_postlearn_exp_gains'][0]
        self.assertEqual(entry,dict(species=132,exp_gain=294,level_gain=1,max_hp_gain=3))
        self.assertTrue(out['learning_receipt']['handoff_text_window_closed'])

    def test_visible_unknown_postlearn_page_is_reviewed_not_auto_advanced(self):
        r=Run();r.to_and();r.ack();r.learned();r.learned();r.ack()
        out=r.call(lambda f:text(f,(1,14,'Unknown page!')))
        self.assertReview(out,'postlearn_visible_handoff_requires_source_review')

    def test_source_peer_exp_prompt_hands_back_without_pressing_a(self):
        r=Run();r.to_and();r.ack();r.learned();r.learned();r.ack()
        r.prog['party'][5]['exp']+=294
        partial=r.call(lambda f:text(f,(1,14,'LAPRAS gained'),(1,16,'294 EXP. P')))
        self.assertNotIn('learning_complete',partial);self.assertEqual(partial['available_actions'],['wait'])
        out=r.call(lambda f:text(f,(0,3,'▷'),(1,14,'LAPRAS gained'),(1,16,'294 EXP. Points!')))
        self.assertTrue(out['learning_complete']);self.assertEqual(out['available_actions'],['wait'])
        receipt=out['learning_receipt']
        self.assertEqual(receipt['handoff_kind'],'source_verified_peer_exp_prompt')
        self.assertFalse(receipt['handoff_text_window_closed'])
        self.assertEqual(receipt['peer_postlearn_exp_gains'][-1]['exp_gain'],294)

    def test_peer_exp_prompt_needs_matching_real_delta_name_and_complete_marker(self):
        for bad in ('delta','name','none','multiple','marker'):
            with self.subTest(bad=bad):
                self.setUp();r=Run();r.to_and();r.ack();r.learned();r.learned();r.ack()
                if bad!='none':r.prog['party'][5]['exp']+=294
                if bad=='multiple':r.prog['party'][1]['exp']+=294
                count=295 if bad=='delta' else 294;name='SNORLAX' if bad=='name' else 'LAPRAS'
                suffix='' if bad=='marker' else '!'
                out=r.call(lambda f:text(f,(1,14,name+' gained'),(1,16,str(count)+' EXP. Points'+suffix)))
                if bad=='marker':
                    self.assertNotIn('learning_complete',out);self.assertEqual(out['available_actions'],['wait'])
                else:self.assertReview(out,'postlearn_visible_handoff_requires_source_review')


if __name__=='__main__':unittest.main(verbosity=2)
