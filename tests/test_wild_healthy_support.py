"""Synthetic pure inputs only; load the candidate, never an emulator or native process."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
NAME = 'laya_pokemon._reviewed_healthy_wild_candidate'
SPEC = importlib.util.spec_from_file_location(NAME, ROOT / 'src/laya_pokemon/battle.py')
b = importlib.util.module_from_spec(SPEC)
sys.modules[NAME] = b
SPEC.loader.exec_module(b)
from laya_pokemon.team_strategy import species_key


def party():
    values = [(102,35,25,90,[33,28,98,39],[35,15,27,30]),
              (132,42,203,203,[70,133,156,34],[15,20,10,15]),
              (154,36,114,114,[75,15,73,22],[25,30,10,10]),
              (35,38,117,117,[64,65,19,31],[35,20,15,20]),
              (7,37,125,125,[61,57,30,40],[20,15,25,35]),
              (19,43,177,177,[57,34,58,85],[15,15,10,15])]
    return [dict(species=s,species_name=species_key(s),level=lv,hp=hp,max_hp=mh,
                 status=0,moves=moves,pp=pp) for s,lv,hp,mh,moves,pp in values]


def from_cells(cells, frame):
    raw = [''.join(row) for row in cells]
    selected = [(i,row.rstrip()) for i,row in enumerate(raw) if re.search(r'[A-Za-z0-9]{2,}', row)][:12]
    return dict(profile=b._VISIBLE_PROFILE,read_valid=True,alignment_verified=True,read_error=None,
        window_visible=True,cells=cells,lines=[row for _,row in selected],
        line_rows=[i for i,_ in selected],observation_frame=frame)


def packet(mons, frame=100, *, enemy='GOLBAT', active=0, command=True, cursor=(9,14), lower=()):
    cells = [[' '] * 20 for _ in range(18)]
    def put(x,y,s):
        assert x+len(s)<=20
        cells[y][x:x+len(s)] = list(s)
    mon=mons[active]
    put(1,0,enemy);put(5,1,'40');put(10,7,species_key(mon['species']))
    put(14,8,b._trainer_half_status(mon));put(11,10,f"{mon['hp']:3}/{mon['max_hp']:3}")
    if command:
        for x,y,s in ((10,14,'FIGHT'),(10,16,'ITEM'),(16,16,'RUN')):put(x,y,s)
        cells[cursor[1]][cursor[0]]='▶'
    for y,s in zip((14,16),lower):put(1,y,s)
    return from_cells(cells,frame)


def state(frame=100, *, enemy='GOLBAT', kind='wild'):
    return dict(raw=1 if kind=='wild' else 2 if kind=='trainer' else 0,active=kind!='none',kind=kind,
        opponent_species=enemy,wild_opponent_species=enemy if kind=='wild' else None,
        observation_frame=frame,player_disabled_move=dict(valid=True,state='clear',raw=0))


def call(mons, frame=100, *, text=None, native=None, capture_focus=False, **kwargs):
    if text is None:text=packet(mons,frame,**kwargs)
    if native is None:native=state(frame,enemy=kwargs.get('enemy','GOLBAT'))
    old=deepcopy((text,native,mons))
    result=b.battle_context(text,native,mons,[],capture_focus=capture_focus)
    assert (text,native,mons)==old
    return result


class CandidateTests(unittest.TestCase):
    def setUp(self):
        for name in ('_wild_retreat_lesson','_wild_retreat_switch','_no_pp_switch','_fixed_damage_risk'):
            setattr(b,name,None)

    def test_actual_team_low_hp_prefers_lapras_without_invented_enemy_move(self):
        mons=party();out=call(mons)
        self.assertEqual(out['battle_tactic'],'switch_healthy_wild_support')
        self.assertEqual(out['party_target_species'],19)
        self.assertEqual(out['battle_target_tile'],[16,14])
        self.assertEqual(b._wild_retreat_switch['observed_move'],None)
        self.assertEqual(b._wild_retreat_switch['trigger'],'low_hp')
        self.assertEqual(out['wild_support_score'],12255)
        self.assertEqual(out['wild_active_score'],2100)

    def test_complete_party_submenu_and_actual_new_hud_handoff(self):
        mons=party();call(mons)
        for frame,index in ((140,0),(180,1),(220,2),(260,3),(300,4),(340,5)):
            text=from_cells([list(row) for row in b._trainer_half_party_view(mons,index)],frame)
            out=call(mons,frame,text=text)
            self.assertEqual(out['available_actions'][0],'a' if index==5 else 'down')
        text=from_cells([list(row) for row in b._trainer_half_party_view(mons,5,True)],380)
        out=call(mons,380,text=text)
        self.assertEqual(out['available_actions'][0],'a')
        out=call(mons,420,active=5)
        self.assertEqual(out['battle_tactic'],'verified_wild_switch_handoff')
        self.assertIsNone(b._wild_retreat_switch)

    def test_exact_same_frame_waits_and_conflicting_frame_sticks_review(self):
        mons=party();call(mons)
        out=call(mons)
        self.assertEqual(out['available_actions'],['wait'])
        out=call(mons,cursor=(15,14))
        self.assertEqual(out['review_reason'],'wild_retreat_pending_same_frame_conflict')
        self.assertEqual(call(mons,140)['available_actions'],['wait'])

    def test_already_strong_super_effective_active_does_not_switch(self):
        mons=party()
        self.assertEqual(call(mons,active=5)['battle_tactic'],'damage')
        self.assertIsNone(b._wild_retreat_switch)

    def test_full_hp_trainee_switches_for_clear_reliable_type_advantage(self):
        mons=party();mons[0]['hp']=90
        out=call(mons,enemy='MAROWAK')
        self.assertEqual(out['battle_tactic'],'switch_healthy_wild_support')
        self.assertEqual(out['party_target_species'],19)
        self.assertEqual(out['wild_support_trigger'],'clear_type_advantage')

    def test_48_of_93_hp_does_not_wait_to_cross_half_against_marowak(self):
        mons=party();mons[0].update(level=36,hp=48,max_hp=93)
        out=call(mons,enemy='MAROWAK')
        self.assertEqual(out['battle_tactic'],'switch_healthy_wild_support')
        self.assertEqual(out['party_target_species'],19)
        self.assertEqual(out['wild_support_trigger'],'low_hp')

    def test_low_hp_snorlax_can_switch_without_requiring_two_and_half_times_power(self):
        mons=party();mons[1]['hp']=100
        out=call(mons,enemy='MACHOKE',active=1)
        self.assertEqual(out['battle_tactic'],'switch_healthy_wild_support')
        self.assertEqual(out['party_target_species'],35)
        self.assertEqual(out['wild_support_trigger'],'low_hp')

    def test_resisted_full_hp_uses_healthy_super_effective_support(self):
        mons=party();mons[0]=deepcopy(mons[3]);mons.pop(3)
        self.assertEqual(call(mons,enemy='GRAVELER')['battle_tactic'],'switch_healthy_wild_support')
        self.assertEqual(b._wild_retreat_switch['trigger'],'all_attacks_resisted')

    def test_no_healthy_or_no_pp_or_statused_support_preserves_retreat(self):
        for update in (dict(hp=132),dict(status=8),dict(pp=[0,15,0,0])):
            with self.subTest(update=update):
                self.setUp();mons=party();mons[-1].update(update)
                self.assertEqual(call(mons)['battle_tactic'],'retreat')
                self.assertIsNone(b._wild_retreat_switch)

    def test_reliable_real_chooser_is_required_not_an_unselected_weak_move(self):
        mons=party();mons[-1].update(moves=[120,34,58,85],pp=[5,15,0,0])
        self.assertEqual(call(mons)['battle_tactic'],'retreat')
        self.assertIsNone(b._wild_retreat_switch)

    def test_low_accuracy_super_effective_support_is_not_selected(self):
        mons=party();mons[-1].update(moves=[57,34,87,0],pp=[15,15,10,0])
        self.assertEqual(call(mons)['battle_tactic'],'retreat')
        self.assertIsNone(b._wild_retreat_switch)

    def test_existing_observed_enemy_danger_policy_is_preserved(self):
        mons=party();mons[0],mons[4]=mons[4],mons[0]
        mons[0].update(hp=62,status=64)
        call(mons,100,enemy='VENOMOTH',command=False,lower=('Enemy VENOMOTH','used PSYBEAM!'))
        call(mons,140,enemy='VENOMOTH',command=False,lower=("It's super",'effective!'))
        out=call(mons,180,enemy='VENOMOTH')
        self.assertEqual(out['battle_tactic'],'switch_observed_wild_danger')
        self.assertEqual(out['party_target_species'],35)
        self.assertEqual(b._wild_retreat_switch['observed_move'],'PSYBEAM')
        self.assertNotIn('support_policy',b._wild_retreat_switch)

    def test_trainer_kind_does_not_enter_new_wild_policy(self):
        mons=party();text=packet(mons);native=state(kind='trainer')
        rows=[''.join(row).upper() for row in text['cells']]
        self.assertIsNone(b._healthy_wild_command(text,native,mons,rows,mons[0],'GOLBAT',
            capture_tactic='not_capture',capture_focus=False))
        self.assertIsNone(b._wild_retreat_switch)

    def test_capture_focus_non_target_keeps_run(self):
        mons=party();out=call(mons,capture_focus=True)
        self.assertEqual(out['battle_tactic'],'retreat')
        self.assertIsNone(b._wild_retreat_switch)

    def test_capture_target_is_not_claimed_as_support_switch(self):
        mons=party();text=packet(mons,enemy='CATERPIE')
        rows=[''.join(row).upper() for row in text['cells']]
        self.assertIsNone(b._healthy_wild_command(text,state(enemy='CATERPIE'),mons,rows,mons[0],'CATERPIE',
            capture_tactic='throw_ball',capture_focus=False))
        self.assertIsNone(b._healthy_wild_command(text,state(enemy='CATERPIE'),mons,rows,mons[0],'CATERPIE',
            capture_tactic='review',capture_focus=False))

    def test_fixed_damage_and_no_pp_owners_are_not_stolen(self):
        mons=party();text=packet(mons);rows=[''.join(row).upper() for row in text['cells']]
        for name in ('_fixed_damage_risk','_no_pp_switch'):
            with self.subTest(owner=name):
                self.setUp();setattr(b,name,{'synthetic_existing_owner':True})
                self.assertIsNone(b._healthy_wild_command(text,state(),mons,rows,mons[0],'GOLBAT',
                    capture_tactic='not_capture',capture_focus=False))

    def test_no_attack_pp_remains_owned_by_existing_policy(self):
        mons=party();mons[0]['pp']=[0,15,0,30]
        out=call(mons)
        self.assertNotEqual(out.get('battle_tactic'),'switch_healthy_wild_support')
        self.assertIsNone(b._wild_retreat_switch)

    def test_pending_capture_mode_change_stops_review(self):
        mons=party();call(mons)
        out=call(mons,140,capture_focus=True)
        self.assertEqual(out['review_reason'],'wild_retreat_healthy_support_priority_changed')

    def test_pending_wrong_enemy_or_party_order_stops_review(self):
        for mutation in ('enemy','party'):
            with self.subTest(mutation=mutation):
                self.setUp();mons=party();call(mons)
                if mutation=='party':mons[1],mons[2]=mons[2],mons[1]
                out=call(mons,140,enemy='VENOMOTH' if mutation=='enemy' else 'GOLBAT')
                self.assertEqual(out['review_reason'],'wild_retreat_pending_observation_or_owner_changed')

    def test_unknown_or_forged_hud_cannot_start_new_switch(self):
        for bad in ('hp','metadata','raw','frame','cursor'):
            with self.subTest(bad=bad):
                self.setUp();mons=party();text=packet(mons);native=state()
                if bad=='hp':text=packet([{**mons[0],'hp':24},*mons[1:]])
                if bad=='metadata':text['read_valid']=False
                if bad=='raw':native['raw']=True
                if bad=='frame':text['observation_frame']=99
                if bad=='cursor':text=packet(mons,cursor=(8,14))
                call(mons,text=text,native=native)
                self.assertIsNone(b._wild_retreat_switch)

    def test_pending_budget_is_not_reset_by_repeated_observations(self):
        mons=party();call(mons)
        out=call(mons,3741)
        self.assertEqual(out['review_reason'],'wild_retreat_pending_budget_exhausted')

    def test_confirm_hint_alone_does_not_claim_switch_complete(self):
        mons=party();call(mons)
        out=call(mons,140)
        self.assertNotEqual(out.get('battle_tactic'),'verified_wild_switch_handoff')
        self.assertIsNotNone(b._wild_retreat_switch)


if __name__ == '__main__':
    unittest.main(verbosity=2)
