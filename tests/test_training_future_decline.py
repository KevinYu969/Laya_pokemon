"""Synthetic source-layout UI only; no game/model/private evidence."""
from copy import deepcopy
from pathlib import Path
import re
import unittest
import pytest
from laya_pokemon import training_future_decline as c
assert Path(c.__file__).resolve()==Path(__file__).resolve().parent.parent/'src/laya_pokemon/training_future_decline.py'

@pytest.fixture(autouse=True)
def isolate_future_decline(monkeypatch):
    monkeypatch.setattr(c,'_SESSION',None)


def progress(case):
    rows=[(154,'VENUSAUR',42,[75,15,73,22],[25,30,10,10]),(35,'FEAROW',42,[64,65,19,31],[35,20,15,20]),
          (102,'EEVEE',44,[44,28,98,39],[25,15,30,30]),(132,'SNORLAX',44,[70,133,156,34],[15,20,10,15]),
          (7,'NIDOKING',43,[61,57,30,40],[20,15,25,35]),(19,'LAPRAS',44,[57,34,58,85],[15,15,10,15])]
    return dict(profile='gen1-wrapper-ram-progress-v1-unvalidated',initialization_candidate=True,party_read_valid=True,
        party_count=6,player_name_raw='KEVIN',badges_raw=255,money=1000,inventory=[],story_event_bits={},party=[
            dict(species=s,species_name=n,level=case[1] if s==case[0] else lv,hp=100,max_hp=100,exp=100000,
                 status=0,moves=m,pp=p) for s,n,lv,m,p in rows])


def text(*items,window=True,native_t=False):
    cells=[[' ']*20 for _ in range(18)]
    for x,y,value in items:
        assert x+len(value)<=20;cells[y][x:x+len(value)]=list(value)
    if native_t:
        cells[16]=[' ']*20;tokens=['c','a','n',"'t",' ','l','e','a','r','n',' ','m','o','r','e']
        cells[16][1:1+len(tokens)]=tokens
    rows=[''.join(row) for row in cells];selected=[(i,row.rstrip()) for i,row in enumerate(rows) if re.search('[A-Za-z0-9]{2,}',row)][:12]
    return dict(profile=c.TEXT_PROFILE,read_valid=True,alignment_verified=True,read_error=None,window_visible=window,
        cells=cells,lines=[v for _,v in selected],line_rows=[i for i,_ in selected])


class Run:
    def __init__(self,case):
        self.case=case;self.p=progress(case);self.name=c.species_key(case[0]);self.new=c.CASES[case][0].replace('_',' ')
    def call(self,page):
        old=deepcopy((page,self.p));out=c.context(page,self.p['party'],self.p)
        assert old==(page,self.p);return out
    def question(self,kind,selected):
        words=((1,14,'for '+self.new+'?'),) if kind=='delete' else ((1,14,'Abandon learning'),(1,16,self.new+'?'))
        return text((15,8,'YES'),(15,10,'NO'),(14,8 if selected=='YES' else 10,'▶'),*words)
    def to_delete(self):
        self.call(text((1,14,self.name+' is'),(1,16,'trying to learn'),(18,16,'▼')))
        self.call(text((1,14,'trying to learn'),(1,16,self.new+'!')))
        self.call(text((1,14,'But, '+self.name),(1,16,"can't learn more"),native_t=True))
        self.call(text((1,14,'than 4 moves!')))
        return self.call(text((1,14,'Delete an older'),(1,16,'move to make room'),(18,16,'▼')))
    def to_result(self):
        self.to_delete();self.call(self.question('delete','NO'));self.call(self.question('abandon','YES'))
    def verify(self):
        self.to_result();self.call(text((1,14,self.name),(1,16,'did not learn'),(18,16,'▼')))
        return self.call(text((1,14,'did not learn'),(1,16,self.new+'!')))


class DeclineTests(unittest.TestCase):
    def setUp(self):c._SESSION=None
    def test_all_three_exact_full_move_cases_decline_normally_and_preserve_every_resource(self):
        for case in c.CASES:
            with self.subTest(case=case):
                self.setUp();r=Run(case);old=deepcopy(r.p);r.to_delete()
                self.assertEqual(r.call(r.question('delete','YES'))['available_actions'][0],'down')
                self.assertEqual(r.call(r.question('delete','NO'))['menu_label'],'NO')
                self.assertEqual(r.call(r.question('abandon','NO'))['available_actions'][0],'up')
                self.assertEqual(r.call(r.question('abandon','YES'))['menu_label'],'YES')
                r.call(text((1,14,r.name),(1,16,'did not learn'),(18,16,'▼')))
                out=r.call(text((1,14,'did not learn'),(1,16,r.new+'!')))
                self.assertTrue(out['learning_declined_verified']);self.assertTrue(out['learning_moves_unchanged'])
                self.assertNotIn('learning_receipt',out);self.assertEqual(r.p,old)
                self.assertIsNone(r.call(text(window=False)));self.assertIsNone(c._SESSION)
    def test_bite37_is_not_intercepted_and_empty_or_wrong_four_moves_are_not_authorized(self):
        r=Run((102,45));r.p['party'][2]['level']=37
        self.assertIsNone(r.call(text((1,14,'EEVEE is'),(1,16,'trying to learn'),(18,16,'▼'))))
        for move in (0,33):
            self.setUp();r=Run((102,45));r.p['party'][2]['moves'][0]=move
            out=r.call(text((1,14,'EEVEE is'),(1,16,'trying to learn'),(18,16,'▼')))
            self.assertEqual(out['available_actions'],['wait']);self.assertEqual(out['phase'],'strategy_review')
    def test_unknown_move_question_or_active_cursor_does_not_press_a(self):
        for bad in ('move','cursor','double_cursor','abandon_first'):
            self.setUp();r=Run((154,43));r.to_delete()
            page=r.question('delete','NO')
            if bad=='move':page=text((1,14,'for AGILITY?'),(15,8,'YES'),(15,10,'NO'),(14,10,'▶'))
            if bad=='cursor':page=text((1,14,'for GROWTH?'),(15,8,'YES'),(15,10,'NO'),(14,10,'▷'))
            if bad=='double_cursor':page=text((1,14,'for GROWTH?'),(15,8,'YES'),(15,10,'NO'),(14,8,'▶'),(14,10,'▶'))
            if bad=='abandon_first':page=r.question('abandon','YES')
            self.assertEqual(r.call(page)['available_actions'],['wait'])
    def test_partial_result_without_prefix_and_forged_learned_page_never_complete(self):
        r=Run((35,43));r.to_result()
        out=r.call(text((1,14,'did not learn'),(1,16,'AGILITY!')))
        self.assertNotIn('learning_declined_verified',out);self.assertEqual(out['available_actions'],['wait'])
        out=r.call(text((1,14,'FEAROW learned'),(1,16,'AGILITY!')))
        self.assertEqual(out['phase'],'strategy_review');self.assertEqual(out['available_actions'],['wait'])
    def test_mutated_resources_decoder_and_bounded_wait_fail_closed(self):
        for bad in ('move','pp','peer_hp','decoder'):
            self.setUp();r=Run((154,43));r.to_delete();page=r.question('delete','NO')
            if bad=='move':r.p['party'][0]['moves'][3]=74
            if bad=='pp':r.p['party'][0]['pp'][0]-=1
            if bad=='peer_hp':r.p['party'][1]['hp']-=1
            if bad=='decoder':page['read_error']=False
            self.assertEqual(r.call(page)['phase'],'strategy_review')
        self.setUp();r=Run((154,43))
        for _ in range(c.MAX_WAITS+1):out=r.call(text((1,14,'VENUSAUR is'),(1,16,'trying to learn')))
        self.assertEqual(out['phase'],'strategy_review')
    def test_only_matching_source_peer_exp_handoff_is_accepted_after_verified_decline(self):
        for correct in (True,False):
            self.setUp();r=Run((154,43));r.verify();r.p['party'][3]['exp']+=294
            out=r.call(text((1,14,'SNORLAX gained'),(1,16,('294' if correct else '295')+' EXP. Points!')))
            if correct:self.assertIsNone(out);self.assertIsNone(c._SESSION)
            else:self.assertEqual(out['phase'],'strategy_review')


if __name__=='__main__':unittest.main(verbosity=2)
