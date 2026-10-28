"""Six focused policy checks. Pure AST harness; no live/module initialization.
Snapshot-byte provenance is a harness boundary; original party/calibration,
EOF receipt, continuity, budget and history validators execute unchanged.
"""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

STAGE=Path(__file__).resolve().parent
ROOT=STAGE.parent

def harness():
    tree=ast.parse((ROOT/'src/laya_pokemon/league_training_supervisor.py').read_text(encoding='utf-8'))
    names={'SOURCE_COMMIT','ROUTE_SHA','BATCH_RECEIPT_SHA','BATCH_PURE_SHA','BATCH_BRIDGE_SHA',
           'PROOF_PROFILE','MAX_SECONDS','MAX_OUTINGS','TARGET','BUDGET_KEY','ROSTER','NAMES',
           'BATCH_INTENT','JOB','PLAN_SHARE_REVIEW_SHA256','GAME_REL','PLAN_REL'}
    def selected(node):
        if isinstance(node,(ast.Import,ast.ImportFrom,ast.FunctionDef,ast.ClassDef)):return True
        if isinstance(node,ast.Assign):
            targets=[n.id for target in node.targets for n in ast.walk(target) if isinstance(n,ast.Name)]
            return bool(targets) and all(name in names for name in targets)
        return False
    namespace={'__name__':'private_policy_harness'}
    exec(compile(ast.Module(body=[n for n in tree.body if selected(n)],type_ignores=[]),str(ROOT/'src/laya_pokemon/league_training_supervisor.py'),'exec'),namespace)
    namespace['MOVES']={33:(35,40)}
    segments=['lobby_nurse_to_left_exit','city_landing_to_south_edge','route_north_edge_to_east_cave_door',
              'route_closed_cave_exit_to_north_edge','city_south_edge_to_center_left_door','lobby_raw_left_entry_to_nurse']
    namespace['ROUTE']={'segments':{name:{'coordinates':[[0,0],[1,1]]} for name in segments}}
    training=ModuleType('laya_pokemon.league_training_batch')
    t=training.__dict__
    t.update(deepcopy=deepcopy,ROSTER=namespace['ROSTER'],SPECIES_NAMES=namespace['NAMES'],MOVE_DATA={33:(35,40)},
             _inventory=lambda value: [] if value==[] else None)
    tree=ast.parse((ROOT/'src/laya_pokemon/league_training_batch.py').read_text(encoding='utf-8-sig'))
    selected_nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('integer','resources','needs_center')]
    exec(compile(ast.Module(body=selected_nodes,type_ignores=[]),'private_training_functions','exec'),t)
    package=ModuleType('laya_pokemon');package.league_training_batch=training
    return namespace,package,training

class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.g,self.package,self.training=harness()
        self.import_patch=patch.dict(sys.modules,{'laya_pokemon':self.package,'laya_pokemon.league_training_batch':self.training})
        self.import_patch.start()
        self.addCleanup(self.import_patch.stop)

    def fixture(self,*,tile=8,hp=80,pp=34,status=0,needs=False,outcome='complete_single_wild',phase='outbound_batch'):
        g=self.g
        progress=dict(profile='gen1-wrapper-ram-progress-v1-unvalidated',initialization_candidate=True,party_read_valid=True,
            party_count=6,player_name_raw='KEVIN',badges_raw=255,money=1000,inventory=[],party=[])
        for species in (19,132,102,154,35,7):
            progress['party'].append(dict(species=species,species_name=g['NAMES'][species],level=43 if species==7 else 44,
                exp=1000,max_hp=100,hp=hp,status=status,moves=[33,0,0,0],pp=[pp,0,0,0]))
        budget=g['budget_start'](100.,'a'*64,'b'*64,'c'*64)
        budget.update(outings=1,appends=1 if phase=='outbound_batch' else 2,phase=phase,last_frame=10,
            last_review_stamp=100.,last_progress=deepcopy(progress))
        loc=dict(map_id=194,x=28,y=tile) if phase=='outbound_batch' else dict(map_id=174,x=7,y=7)
        step=dict(id=g['JOB']+'-001-000',kind='interact',mechanic='league_training_batch',map_id=194,target=[28,7],training_intent=deepcopy(g['BATCH_INTENT']))
        plan=dict(mode='league_campaign',source_commit=g['SOURCE_COMMIT'],training_supervisor='vr2-east-balanced45-v1',
            training_job=g['JOB'],resume_revision=1,steps=[step])
        state=dict(frame=22,location=loc,progress=progress,training_world_proof=dict(closed_frames=[21,22],full_party_healed=hp==100 and pp==35 and status==0))
        receipt=dict(closed_frames=[18,19],needs_center=needs,wild_count=0 if outcome=='complete_no_encounter' else 1,
            total_exp_gain=0 if outcome=='complete_no_encounter' else 100,total_pp_spent=1)
        stored=dict(job=g['JOB'],owner_step=step['id'],outcome=outcome,displacements=32 if outcome=='complete_no_encounter' else 1,
            source_commit=g['SOURCE_COMMIT'],closed_frames=[18,19],location=deepcopy(loc),progress_sha256=g['canonical_sha'](progress),
            step_sha256=g['canonical_sha'](step),batch_receipt=receipt,batch_receipt_sha256=g['canonical_sha'](receipt))
        state['training_batch_proof']=stored
        snapshot=dict(plan=plan,review={'state':state},stamp=200.,raw=[])
        def sync():
            plan[g['BUDGET_KEY']]=g['plan_budget'](budget)
            raw=[g['encode'](plan),b'{}',g['encode']({'state':state}),b'{"active":true}']
            budget['expected_plan_sha256']=g['digest'](raw[0]);budget['active_sha256']=g['digest'](raw[3])
            snapshot['raw']=raw
        sync()
        g['snapshot_from_bytes']=lambda raw:snapshot
        calibration=dict(profile='league-training-calibration-v1',approved_by='root',game=g['GAME_REL'],source_commit=g['SOURCE_COMMIT'],
            route_audit_sha256=g['ROUTE_SHA'],batch_receipt_sha256=g['BATCH_RECEIPT_SHA'],batch_pure_sha256=g['BATCH_PURE_SHA'],
            batch_bridge_sha256=g['BATCH_BRIDGE_SHA'],round_trip_verified=True,single_wild_verified=True,normal_nurse_verified=True,
            proof_profile=g['PROOF_PROFILE'],single_plan_writer='root-supervisor-exclusive')
        return snapshot,budget,calibration,sync

    def run_propose(self,fixture,now=201.):
        snapshot,budget,calibration,_=fixture
        return self.g['propose'](snapshot,budget,calibration,now)

    def test_healthy_continues_at_either_current_tile_with_zero_anchor(self):
        for tile in (7,8):
            fixture=self.fixture(tile=tile);before=deepcopy(fixture[0]['plan']);budget=deepcopy(fixture[1])
            result=self.run_propose(fixture);steps=result['plan']['steps'][-2:]
            self.assertEqual([s['target'] for s in steps],[[28,tile],[28,tile]])
            self.assertEqual(steps[0]['kind'],'move');self.assertNotIn('mechanic',steps[0])
            self.assertEqual(steps[1]['mechanic'],'league_training_batch')
            self.assertEqual(steps[1]['training_intent'],self.g['BATCH_INTENT'])
            self.assertEqual(result['budget']['phase'],'outbound_batch')
            self.assertEqual((result['budget']['outings'],result['budget']['appends']),(2,2))
            self.assertEqual(result['plan']['lead_species'],7)
            self.assertEqual(fixture[0]['plan'],before);self.assertEqual(fixture[1],budget)
            self.assertEqual(result['budget']['deadline_wall'],budget['deadline_wall'])
            self.g['validate_budget'](result['budget'],201.)

    def test_no_encounter_zero_exp_still_consumes_new_attempt(self):
        result=self.run_propose(self.fixture(outcome='complete_no_encounter'))
        self.assertEqual((result['budget']['outings'],result['budget']['appends']),(2,2))
        self.assertEqual(result['budget']['phase'],'outbound_batch')

    def test_real_center_requirement_recovers_and_committed_return_finishes_normally(self):
        for values in [dict(hp=66),dict(status=8),dict(pp=2)]:
            result=self.run_propose(self.fixture(needs=True,**values))
            self.assertEqual((result['budget']['phase'],result['budget']['outings'],result['budget']['appends']),('returning',1,2))
            self.assertEqual(result['plan']['steps'][-1]['kind'],'heal')
        result=self.run_propose(self.fixture(phase='returning',hp=100,pp=35))
        self.assertEqual((result['budget']['phase'],result['budget']['outings'],result['budget']['appends']),('outbound_batch',2,3))

    def test_disagreement_invalid_receipt_and_continuity_fail_closed(self):
        for flag in (False,0,None):
            with self.assertRaises(self.g['ReviewRequired']):self.run_propose(self.fixture(hp=60,needs=flag))
        fixture=self.fixture();fixture[0]['review']['state']['training_batch_proof']['progress_sha256']='0'*64
        with self.assertRaises(self.g['ReviewRequired']):self.run_propose(fixture)
        fixture=self.fixture();fixture[1]['last_progress']['money']+=1
        with self.assertRaises(self.g['ReviewRequired']):self.run_propose(fixture)

    def test_legacy_then_continuous_ledger_keeps_original_seed_and_no_refund(self):
        g=self.g;seed=g['budget_start'](100.,'a'*64,'b'*64,'c'*64);rows=[dict(kind='seed',job=g['JOB'],budget=seed)]
        prior=seed
        for index,(outings,appends,phase) in enumerate([(1,1,'outbound_batch'),(1,2,'returning'),(2,3,'outbound_batch'),(3,4,'outbound_batch'),(3,5,'returning')],1):
            current=deepcopy(prior);current.update(outings=outings,appends=appends,phase=phase,last_frame=index,last_wall=100.+index,expected_plan_sha256=str(index)*64)
            rows.extend([dict(kind='reserve',job=g['JOB'],plan_sha256=current['expected_plan_sha256']),dict(kind='commit',job=g['JOB'],budget=current)]);prior=current
        self.assertEqual(g['history_budget'](rows,201.),prior)
        bad=deepcopy(rows);bad[-1]['budget']['outings']=2
        with self.assertRaises(g['ReviewRequired']):g['history_budget'](bad,201.)
        bad=deepcopy(rows);bad[-1]['budget']['started_wall']+=1;bad[-1]['budget']['deadline_wall']+=1
        with self.assertRaises(g['ReviewRequired']):g['history_budget'](bad,201.)

    def test_attempt_deadline_limits_and_level45_checkpoint_unchanged(self):
        fixture=self.fixture();fixture[1].update(outings=1000,appends=1999);fixture[3]()
        with self.assertRaises(self.g['ReviewRequired']):self.run_propose(fixture)
        fixture=self.fixture()
        with self.assertRaises(self.g['ReviewRequired']):self.run_propose(fixture,now=fixture[1]['deadline_wall'])
        fixture=self.fixture();state=fixture[0]['review']['state']
        for mon in state['progress']['party']:mon['level']=45
        state['training_batch_proof']['progress_sha256']=self.g['canonical_sha'](state['progress']);fixture[3]()
        result=self.run_propose(fixture)
        self.assertEqual(result['status'],'all_six_45_checkpoint_review');self.assertIsNone(result['plan'])
        self.assertEqual(result['budget']['outings'],1)

if __name__=='__main__':unittest.main(verbosity=2)
