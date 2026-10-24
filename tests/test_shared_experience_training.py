"""六人shared EXP純分派：真原context＋合成字格，不建立遊戲／模型。"""
from copy import deepcopy
import importlib
from types import SimpleNamespace
import re

import pytest

from laya_pokemon import balanced_training as training
from laya_pokemon.battle import _trainer_half_party_view


PARTY=[
 dict(species=19,level=15,hp=66,max_hp=66,status=0,exp=4218,moves=[55,45,0,0],pp=[25,40,0,0]),
 dict(species=7,level=36,hp=121,max_hp=121,status=0,exp=40019,moves=[61,57,30,40],pp=[20,15,25,35]),
 dict(species=102,level=35,hp=90,max_hp=90,status=0,exp=43317,moves=[33,28,98,39],pp=[35,15,30,30]),
 dict(species=154,level=35,hp=111,max_hp=111,status=0,exp=36804,moves=[75,15,73,22],pp=[25,30,10,10]),
 dict(species=35,level=36,hp=111,max_hp=111,status=0,exp=47593,moves=[64,65,43,31],pp=[35,20,30,20]),
 dict(species=132,level=37,hp=177,max_hp=177,status=0,exp=66666,moves=[70,133,156,34],pp=[15,20,10,15]),
]
PLAN=dict(mode='league_campaign',training_job='six-team35-candidate',
          training_shared_experience=True,training_direct_from_level=25)


def packet(rows):
 raw=[list(r) for r in rows]
 selected=[(i,''.join(r).rstrip()) for i,r in enumerate(raw) if re.search(r'[A-Za-z0-9]{2,}',''.join(r))][:12]
 return dict(profile='gen1-visible-tile-text-candidates-v1-unvalidated',read_valid=True,
             alignment_verified=True,window_visible=False,read_error=None,cells=raw,
             lines=[r for _,r in selected],line_rows=[i for i,_ in selected])


def command(party,active=0,*,cursor=(9,14)):
 from laya_pokemon.team_strategy import species_key
 rows=[[' ']*20 for _ in range(18)]
 mon=party[active]
 for x,y,text in ((1,0,'PIDGEY'),(5,1,'26'),(10,7,species_key(mon['species'])),
                  (15,8,str(mon['level'])),(11,10,f"{mon['hp']:3}/{mon['max_hp']:3}"),
                  (10,14,'FIGHT'),(10,16,'ITEM'),(16,16,'RUN'),(*cursor,'▶')):
  rows[y][x:x+len(text)]=text
 return packet(rows)


class Harness:
 def __init__(self,monkeypatch):
  self.party=deepcopy(PARTY);self.plan=deepcopy(PLAN);self.frame=100;self.now=10.
  self.pyboy=SimpleNamespace(frame_count=self.frame);self.text=command(self.party)
  self.calls=[]
  self.state=dict(frame=self.frame,phase='battle_menu',battle_tactic='damage',
    location=dict(map_id=26,x=18,y=8),
    battle_state=dict(raw=1,active=True,kind='wild',observation_frame=self.frame,
                      opponent_species='PIDGEY',wild_opponent_species='PIDGEY'),
    progress=dict(profile='gen1-wrapper-ram-progress-v1-unvalidated',party_read_valid=True,
                  initialization_candidate=True,party_count=6,party=self.party))
  original=training.context
  def delegated(pyboy,state,plan,previous):
   assert pyboy is self.pyboy and state is self.state and plan is self.plan and previous==[]
   assert state['progress']['party'] is self.party
   self.calls.append((state,plan))
   return original(pyboy,state,plan,previous)
  monkeypatch.setattr(training,'context',delegated)
  monkeypatch.setattr(training,'read_visible_text',lambda p:self.text)
  monkeypatch.setattr(training,'_SHARED_EXPERIENCE_PENDING',None)
  monkeypatch.setattr('time.monotonic',lambda:self.now)

 def call(self,text=None,*,advance=True):
  if advance:self.frame+=4;self.now+=.1
  self.pyboy.frame_count=self.frame;self.state['frame']=self.frame
  self.state['battle_state']['observation_frame']=self.frame
  if text is not None:self.text=text
  before=deepcopy((self.state,self.plan,self.text))
  result=training.shared_experience_battle_context(self.pyboy,self.state,self.plan)
  assert (self.state,self.plan,self.text)==before
  return result


@pytest.fixture
def env(monkeypatch):return Harness(monkeypatch)


def test_full_six_normal_command_party_slot6_switch_and_strong_hud_stops_training_swap(env):
 out=env.call();assert out['training_tactic']=='switch_for_shared_experience'
 assert out['objective']=='Move RIGHT.' and out['training_support_species']==132
 pending=training._SHARED_EXPERIENCE_PENDING
 out=env.call(command(env.party,cursor=(15,14)))
 assert out['objective']=='Confirm the current selection.'
 for i in range(6):
  out=env.call(packet(_trainer_half_party_view(env.party,i)))
  assert out['objective']==('Move DOWN.' if i<5 else 'Confirm the current selection.')
  assert out['training_support_species']==132
 out=env.call(packet(_trainer_half_party_view(env.party,5,True)))
 assert out['available_actions']==['a','wait'] and out['menu_label']=='SWITCH'
 assert training._SHARED_EXPERIENCE_PENDING is pending
 before=len(env.calls)
 assert env.call(command(env.party,5)) is None and len(env.calls)==before
 assert training._SHARED_EXPERIENCE_PENDING is None


@pytest.mark.parametrize('change',[
 lambda p:p.update(mode='other'),lambda p:p.update(training_shared_experience=1),
 lambda p:p.update(training_shared_experience=False),lambda p:p.update(training_direct_from_level=True),
 lambda p:p.update(training_direct_from_level=24),lambda p:p.update(training_direct_from_level=25.),
 lambda p:p.pop('training_job'),lambda p:p.update(training_job=''),lambda p:p.update(training_job='x'*129),
])
def test_only_explicit_training_contract_can_delegate(env,change):
 change(env.plan);assert env.call() is None and not env.calls


@pytest.mark.parametrize('change',[
 lambda s:s.update(phase='strategy_review'),lambda s:s.update(phase='battle_animation'),
 lambda s:s.update(review_reason='unsupported'),lambda s:s.update(battle_tactic='retreat'),
 lambda s:s.update(battle_tactic='capture'),lambda s:s.update(capture_tactic='throw'),
 lambda s:s.update(capture_plan={'tactic':'review'}),lambda s:s.update(capture_plan={'tactic':'capture'}),
 lambda s:s['battle_state'].update(raw=2,kind='trainer'),lambda s:s['battle_state'].update(raw=True),
 lambda s:s['battle_state'].update(active=None),lambda s:s['battle_state'].update(kind='unknown'),
 lambda s:s['battle_state'].update(wild_opponent_species='RATTATA'),
 lambda s:s['progress'].update(party_read_valid=False),lambda s:s['progress'].update(party_count=True),
 lambda s:s['progress']['party'][2].update(hp=0),lambda s:s['progress']['party'][0].update(exp=True),
 lambda s:s['progress']['party'][4].update(species=19),lambda s:s['progress']['party'].pop(),
])
def test_review_capture_retreat_unknown_or_faint_never_gets_overridden(env,change):
 change(env.state);assert env.call() is None and not env.calls


@pytest.mark.parametrize('change',[
 lambda t:t.update(profile='unknown'),lambda t:t.update(read_valid=False),
 lambda t:t.update(alignment_verified=False),lambda t:t.update(window_visible=None),
 lambda t:t.update(read_error='partial'),lambda t:t.update(lines=['wrong']),
 lambda t:t['cells'][13].__setitem__(1,'X'),lambda t:t['cells'][7].__setitem__(11,'X'),
 lambda t:t['cells'][10].__setitem__(13,'5'),lambda t:t['cells'][0].__setitem__(1,'X'),
 lambda t:t['cells'][14].__setitem__(10,' '),
])
def test_unknown_partial_text_hud_enemy_or_command_cannot_create_pending(env,change):
 change(env.text);assert env.call() is None and not env.calls
 assert training._SHARED_EXPERIENCE_PENDING is None


@pytest.mark.parametrize('change',[
 lambda p:p[5].update(hp=118),lambda p:p[5].update(status=8),
 lambda p:p[5].update(pp=[2,20,10,2]),lambda p:p[5].update(moves=[133,156,0,0],pp=[20,10,0,0]),
])
def test_original_highest_level_selection_must_be_safe_no_filtering_to_second_best(env,change):
 change(env.party);out=env.call()
 assert out['phase']=='campaign_review' and out['available_actions']==['wait']
 assert not env.calls


def test_three_effective_attack_pp_and_just_over_two_thirds_is_enough(env):
 env.party[5].update(hp=119,pp=[3,20,10,0])
 assert env.call()['training_support_species']==132


@pytest.mark.parametrize('level',[25,26])
def test_at_or_above_threshold_keeps_original_direct_battle(env,level):
 env.party[0]['level']=level
 assert env.call(command(env.party)) is None and not env.calls


def test_low_wild_half_hp_does_not_replace_original_run_policy(env):
 env.party[0]['hp']=33
 assert env.call(command(env.party)) is None and not env.calls


def test_no_pending_party_page_cannot_start_new_swap(env):
 assert env.call(packet(_trainer_half_party_view(env.party,0))) is None and not env.calls


def test_inactive_known_menu_and_same_frame_only_wait_do_not_resend_a(env):
 env.call();n=len(env.calls)
 assert env.call(advance=False)['available_actions']==['wait'] and len(env.calls)==n
 assert env.call(packet(_trainer_half_party_view(env.party,5,inactive=True)))['available_actions']==['wait']
 assert env.call(packet(_trainer_half_party_view(env.party,5,True,inactive=True)))['available_actions']==['wait']
 assert len(env.calls)==n


def test_changed_job_or_support_does_not_reuse_pending(env):
 env.call();n=len(env.calls);env.plan['training_job']='other-job'
 assert env.call()['phase']=='campaign_review' and len(env.calls)==n


@pytest.mark.parametrize('change',[
 lambda p:p[5].update(hp=118),lambda p:p[5].update(status=8),
 lambda p:p[5].update(pp=[2,20,10,2]),
])
def test_existing_pending_rechecks_support_without_filtering_or_rebuilding(env,change):
 env.call();p=training._SHARED_EXPERIENCE_PENDING;n=len(env.calls);change(env.party)
 out=env.call(packet(_trainer_half_party_view(env.party,0)))
 assert out['phase']=='campaign_review' and len(env.calls)==n
 assert training._SHARED_EXPERIENCE_PENDING is p


def test_same_frame_conflict_and_frame_packet_disagreement_do_not_delegate(env):
 env.call();n=len(env.calls)
 env.text=packet(_trainer_half_party_view(env.party,0))
 assert env.call(advance=False)['phase']=='campaign_review' and len(env.calls)==n


def test_stale_battle_observation_frame_is_not_repaired(env):
 env.state['battle_state']['observation_frame']=0
 assert training.shared_experience_battle_context(env.pyboy,env.state,env.plan) is None
 assert not env.calls and env.state['battle_state']['observation_frame']==0


def test_real_frame_counter_mismatch_never_reads_or_delegates(env):
 env.pyboy.frame_count=True
 assert training.shared_experience_battle_context(env.pyboy,env.state,env.plan) is None
 assert not env.calls


def test_negative_monotonic_clock_is_reviewed_without_rebuilding_pending(env):
 env.call();p=training._SHARED_EXPERIENCE_PENDING;n=len(env.calls)
 env.now-=1
 assert env.call()['review_reason'].endswith('clock_or_frame_invalid') and len(env.calls)==n
 assert training._SHARED_EXPERIENCE_PENDING is p


def test_pending_25_calls_and_sixty_seconds_survive_hot_reload(env,monkeypatch):
 env.call();p=training._SHARED_EXPERIENCE_PENDING;started=p['started']
 delegate=training.context
 importlib.reload(training)
 monkeypatch.setattr(training,'read_visible_text',lambda _:env.text)
 monkeypatch.setattr(training,'context',delegate)
 assert training._SHARED_EXPERIENCE_PENDING is p and p['started']==started
 env.now+=61
 assert env.call()['review_reason'].endswith('budget_exhausted') and not len(env.calls)>1


def test_call_budget_never_resets_on_repeated_command_or_same_frame(env):
 env.call();p=training._SHARED_EXPERIENCE_PENDING
 for _ in range(24):assert env.call(advance=False)['available_actions']==['wait']
 assert env.call(advance=False)['review_reason'].endswith('budget_exhausted') and p['calls']==26
