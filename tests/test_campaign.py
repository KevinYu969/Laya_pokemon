from types import SimpleNamespace
from pathlib import Path
import json
import pytest
from laya_pokemon.campaign_journal import Journal,GYMS
from laya_pokemon.campaign_route import waypoint


def test_badge_layout_matches_installed_gen1_and_baseline_does_not_reaward_old_gym(tmp_path):
    from pyboy.plugins.game_wrapper_pokemon_gen1_constants import BADGES
    for name,label,bit in GYMS:
        key={'brock':'boulder','misty':'cascade','lt_surge':'thunder','erika':'rainbow','koga':'soul','sabrina':'marsh','blaine':'volcano','viridian_gym_giovanni':'earth'}[name]
        assert bit==1<<BADGES[key]
    j=Journal(tmp_path,{'story_event_bits':{'beat_brock':True},'badges_raw':1})
    assert j.seen_gyms=={'brock'}


def test_new_gym_requires_event_badge_and_closed_dialogue_before_recording(tmp_path):
    class Screenshot:
        def save(self,p):p.write_bytes(b'synthetic-frame')
    emulator=SimpleNamespace(screen=SimpleNamespace(image=Screenshot()))
    state={'phase':'dialogue','battle_state':{'kind':'none'},'location':{'map_id':65},'progress':{'story_event_bits':{'beat_misty':True},'badges_raw':3,'party':[]}}
    journal=Journal(tmp_path,{'story_event_bits':{'beat_misty':False},'badges_raw':1})
    def save(name):p=tmp_path/name;p.write_bytes(b'synthetic-state');return p
    assert journal.observe(emulator,state,{'wall_seconds':30},save)==[]
    state['phase']='unclassified';records=journal.observe(emulator,state,{'wall_seconds':31},save)
    assert len(records)==1 and records[0]['id']=='misty' and '+08:00' in records[0]['completed_at_taipei']
    assert journal.observe(emulator,state,{'wall_seconds':32},save)==[]


def test_newly_monitored_true_event_is_baseline_not_a_new_completion(tmp_path):
    journal=Journal(tmp_path,{'story_event_bits':{},'badges_raw':3})
    state={'phase':'unclassified','battle_state':{'kind':'none'},'progress':{'badges_raw':3,'story_event_bits':{'got_nugget':True}}}
    assert journal.observe(None,state,{},None)==[]
    assert 'got_nugget' in journal.seen_events


def test_unknown_story_signal_first_becoming_true_is_baseline_not_completion(tmp_path):
    journal=Journal(tmp_path,{'story_event_bits':{'got_ss_ticket':None},'badges_raw':3})
    state={'phase':'unclassified','battle_state':{'kind':'none'},'progress':{'badges_raw':3,'story_event_bits':{'got_ss_ticket':True}}}
    assert journal.observe(None,state,{},None)==[]
    assert 'got_ss_ticket' in journal.seen_events


def test_unknown_gym_signal_first_becoming_complete_has_no_invented_time(tmp_path):
    journal=Journal(tmp_path,{'story_event_bits':{'beat_erika':None},'badges_raw':None})
    state={'phase':'unclassified','battle_state':{'kind':'none'},'progress':{'badges_raw':15,'story_event_bits':{'beat_erika':True}}}
    assert journal.observe(None,state,{},None)==[]
    assert 'erika' in journal.seen_gyms


def test_route_advances_only_on_expected_map_transition_without_ram_writes(monkeypatch):
    import laya_pokemon.campaign_route as route
    monkeypatch.setattr(route,'read_world_grid',lambda *args:{'walkable':[[1]*10 for _ in range(10)],'screen_cells_verified':90})
    plan={'steps':[{'id':'exit','map_id':54,'target':[4,14],'next_map':2,'kind':'move'}, {'id':'city','map_id':2,'target':[5,5],'kind':'move'}]}
    state={'location':{'map_id':2,'x':4,'y':5},'progress':{'story_event_bits':{}}}
    context,step=waypoint(None,state,plan,'exit',[])
    assert step=='city' and context['objective']=='Move RIGHT.'
    state['location']['map_id']=3
    context,_=waypoint(None,state,plan,'city',[])
    assert context['phase']=='campaign_review' and context['review_reason']=='unexpected_map'


def test_fainted_party_message_is_dismissed_then_healthy_flying_member_selected():
    from laya_pokemon.battle import battle_context
    from tests.test_battle import text_at
    party=[{'species':9,'level':17,'hp':0,'max_hp':50,'moves':[33,45,73,22],'pp':[20,40,10,10]}, {'species':3,'level':3,'hp':16,'max_hp':16,'moves':[43,33,0,0],'pp':[30,35,0,0]}, {'species':5,'level':3,'hp':16,'max_hp':16,'moves':[64,45,0,0],'pp':[35,40,0,0]}]
    text=text_at((3,0,'IVYSAUR'),(0,1,'▷'),(3,3,'NIDORAN♂'),(3,6,'SPEAROW'),(1,14,"There's no will"),(1,16,'to fight!'))
    result=battle_context(text,{'active':True,'kind':'trainer','opponent_species':'WEEDLE'},party)
    assert result['battle_tactic']=='dismiss_fainted_message'
    text=text_at((3,0,'IVYSAUR'),(0,1,'▷'),(3,3,'NIDORAN♂'),(3,6,'SPEAROW'))
    result=battle_context(text,{'active':True,'kind':'trainer','opponent_species':'WEEDLE'},party)
    assert result['party_target_index']==2 and result['objective']=='Move DOWN.'


def test_confirmed_battle_loss_requires_review_even_when_no_battle_is_active():
    from laya_pokemon.battle import battle_context
    result=battle_context({'lines':[]},{'active':False,'kind':'lost_transition','raw':255})
    assert result['phase']=='strategy_review' and result['review_reason']=='battle_loss_requires_review'
    assert result['battle_loss_confirmed'] is True


def test_loss_guard_distinguishes_faint_from_loss_and_latches_until_recovery():
    from laya_pokemon.loss_review import LossGuard
    guard=LossGuard()
    def state(hps,kind='trainer',text=()):
        return {'battle_state':{'kind':kind,'active':kind=='trainer'},
                'progress':{'party':[{'hp':hp} for hp in hps]},'visible_text_candidates':list(text)}
    assert guard.observe(state([0,16,16])) is None
    assert guard.observe(state([0,0,0]))['signals']==['all_party_fainted']
    assert guard.observe(state([0,0,0],text=['KEVIN blacked','out!'])) is None
    assert guard.observe(state([50,16,16],'none')) is None
    assert guard.observe(state([0,0,0])) is not None


def test_loss_guard_can_detect_visible_blackout_when_ram_transition_was_skipped():
    from laya_pokemon.loss_review import LossGuard
    guard=LossGuard()
    guard.observe({'battle_state':{'active':True,'kind':'trainer'},'progress':{'party':[{'hp':1}]}})
    loss=guard.observe({'battle_state':{'active':False,'kind':'none'},'visible_text_candidates':['KEVIN blacked','out!'],'progress':{'party':[{'hp':30}]}})
    assert loss['signals']==['visible_blackout']


def test_loss_resume_requires_reason_evidence_adjustment_and_validation():
    from laya_pokemon.loss_review import parse_loss_review
    assert parse_loss_review('繼續') is None
    assert parse_loss_review(json.dumps({'cause':'unknown'})) is None
    assert parse_loss_review(json.dumps({key:'已核對' for key in ['cause','evidence','adjustments','validation']}))['cause']=='已核對'


def test_per_frame_loss_monitor_checks_entire_party_and_never_writes_memory():
    from laya_pokemon.loss_review import frame_loss_signal
    from collections import defaultdict
    memory=defaultdict(int,{0xD057:2,0xD163:2,0xD16B+44+2:16})
    assert frame_loss_signal(memory) is False
    memory[0xD16B+44+2]=0
    assert frame_loss_signal(memory) is True
    memory[0xD057]=0
    assert frame_loss_signal(memory) is False
    memory[0xD057]=255
    assert frame_loss_signal(memory) is True


def test_expected_center_entry_advances_before_healing_detours(monkeypatch):
    import laya_pokemon.campaign_route as route
    monkeypatch.setattr(route,'read_world_grid',lambda *args:{'walkable':[[1]*30 for _ in range(20)],'screen_cells_verified':90})
    steps=[{'id':'enter','map_id':15,'target':[11,5],'next_map':68,'kind':'move'},
           {'id':'heal','map_id':68,'target':[3,3],'kind':'heal'},
           {'id':'exit','map_id':68,'target':[3,8],'next_map':15,'kind':'move'},
           {'id':'cave','map_id':15,'target':[18,5],'next_map':59,'kind':'move'}]
    state={'location':{'map_id':68,'x':3,'y':7},'progress':{'story_event_bits':{},'party':[{'hp':5,'max_hp':10,'moves':[22],'pp':[10]}]}}
    result,step=route.waypoint(None,state,{'steps':steps},'enter',[])
    assert step=='heal'
    state['progress']['party'][0]['hp']=10
    result,step=route.waypoint(None,state,{'steps':steps},'heal',[])
    assert step=='exit'
    state['location']={'map_id':15,'x':11,'y':5}
    result,step=route.waypoint(None,state,{'steps':steps},'exit',[])
    assert step=='cave'


def test_healing_pp_counts_flying_and_horn_attacks_not_status_moves():
    from laya_pokemon.campaign_route import healthy,attack_pp
    spearow={'species':5,'hp':50,'max_hp':50,'moves':[64,45,43,31],'pp':[2,40,30,0]}
    assert attack_pp(spearow)==2
    assert not healthy({'party':[spearow]})
    spearow['pp'][3]=20
    assert healthy({'party':[spearow]})


def test_full_pp_heal_still_interacts_when_full_hp_and_only_completes_after_nurse():
    from laya_pokemon.campaign_route import healthy,waypoint
    mon={'species':132,'hp':147,'max_hp':147,'status':0,'moves':[29,133,156,0],'pp':[4,20,10,0]}
    state={'location':{'map_id':154,'x':3,'y':3},
           'progress':{'party':[mon],'story_event_bits':{}}}
    plan={'steps':[{'id':'heal','kind':'heal','map_id':154,'target':[3,3],'face':'up','require_full_pp':True}]}
    assert healthy(state['progress']) and not healthy(state['progress'],require_full_pp=True)
    context,step=waypoint(None,state,plan,'heal',['up'])
    assert step=='heal' and context['controller_interaction'] is True
    assert context['objective']=='Confirm the current selection.' and context['available_actions']==['a','b']
    mon['pp'][0]=15
    assert healthy(state['progress'],require_full_pp=True)
    context,step=waypoint(None,state,plan,'heal',[])
    assert step=='complete' and context['review_reason']=='route_extension_required'


def test_full_pp_requires_bench_status_moves_and_preserves_default_heal_behavior():
    from laya_pokemon.campaign_route import healthy,waypoint
    lead={'species':132,'hp':147,'max_hp':147,'moves':[29,133,156,0],'pp':[15,20,10,0]}
    bench={'species':35,'hp':102,'max_hp':102,'moves':[64,45,43,31],'pp':[35,39,30,20]}
    progress={'party':[lead,bench],'story_event_bits':{}}
    assert healthy(progress) and not healthy(progress,require_full_pp=True)
    state={'location':{'map_id':154,'x':3,'y':3},'progress':progress}
    step={'id':'heal','kind':'heal','map_id':154,'target':[3,3]}
    assert waypoint(None,state,{'steps':[step]},'heal',[])[1]=='complete'
    step['require_full_pp']=True
    assert waypoint(None,state,{'steps':[step]},'heal',[])[1]=='heal'
    bench['pp'][1]=40
    assert healthy(progress,require_full_pp=True)


@pytest.mark.parametrize('moves,pp', [([29,133,156,0],[15,20,10,1]),
                                    ([29,133,156,166],[15,20,10,5]),
                                    ([29,133,156,0],[79,20,10,0]),
                                    ([29,133,156,0],None),([29,133,156],[15,20,10]),
                                    ([29,133,156,False],[15,20,10,0])])
def test_full_pp_empty_unknown_malformed_or_ppup_values_are_not_full(moves,pp):
    from laya_pokemon.campaign_route import healthy
    mon={'species':132,'hp':147,'max_hp':147,'moves':moves,'pp':pp}
    assert healthy({'party':[mon]},require_full_pp=True) is False


def test_injured_bridge_lead_returns_to_cerulean_center(monkeypatch):
    import laya_pokemon.campaign_route as route
    monkeypatch.setattr(route,'read_world_grid',lambda *a:{'walkable':[[1]*20 for _ in range(36)],'screen_cells_verified':90})
    mon={'species':5,'hp':11,'max_hp':52,'moves':[64,31],'pp':[20,20]}
    state={'location':{'map_id':35,'x':10,'y':30},'progress':{'party':[mon],'story_event_bits':{}}}
    plan={'steps':[{'id':'bridge','map_id':35,'target':[10,15],'kind':'move'}]}
    result,step=route.waypoint(None,state,plan,'bridge',[])
    assert step=='bridge' and result['goal']=='detour-bridge-center'
    assert result['objective']=='Move DOWN.'


def test_bill_machine_dialogue_flag_is_available_in_installed_sdk():
    from pyboy.plugins.game_wrapper_pokemon_gen1_constants import EVENT_FLAGS
    from laya_pokemon.progress import STORY_EVENT_NAMES
    assert 'bill_said_use_cell_separator' in STORY_EVENT_NAMES
    assert EVENT_FLAGS['bill_said_use_cell_separator']==0x55e


def test_rock_trainer_switches_flying_trainee_to_healthy_grass_member(monkeypatch):
    import laya_pokemon.battle as battle
    from tests.test_battle import text_at
    monkeypatch.setattr(battle,'_no_pp_switch',None)
    party=[{'species':5,'level':19,'hp':34,'max_hp':52,'moves':[64,45,43,31],'pp':[33,40,30,20]},
           {'species':9,'level':24,'hp':68,'max_hp':68,'moves':[77,45,73,22],'pp':[35,40,10,10]}]
    text=text_at((0,1,'GEODUDE'),(10,7,'SPEAROW'),(10,11,'34/52'),(10,14,'FIGHT'),(10,16,'ITEM'),(16,16,'RUN'),(9,14,'▶'))
    result=battle.battle_context(text,{'active':True,'kind':'trainer','opponent_species':'GEODUDE'},party)
    assert result['battle_tactic']=='switch_type_advantage' and result['party_target_species']==9
    assert result['objective']=='Move RIGHT.'


def test_control_file_sharing_lock_is_retried_without_terminating_game(tmp_path,monkeypatch):
    from laya_pokemon.campaign import take_control_file
    path=tmp_path/'REVIEW';path.write_text('檢查補血',encoding='utf-8')
    original=Path.unlink
    with monkeypatch.context() as patch:
        def locked(self,*args,**kwargs):
            if self==path:raise PermissionError('sharing violation')
            return original(self,*args,**kwargs)
        patch.setattr(Path,'unlink',locked)
        assert take_control_file(path) is None
        assert path.read_text(encoding='utf-8')=='檢查補血'
    assert take_control_file(path)=='檢查補血'
    assert not path.exists()


def test_low_hp_trainee_switches_before_fainting_to_retain_shared_experience(monkeypatch):
    import laya_pokemon.battle as battle
    from tests.test_battle import text_at
    monkeypatch.setattr(battle,'_no_pp_switch',None)
    party=[{'species':5,'level':19,'hp':12,'max_hp':52,'moves':[64,31],'pp':[30,20]},
           {'species':167,'level':22,'hp':63,'max_hp':68,'moves':[30,33],'pp':[18,35]}]
    text=text_at((0,1,'DROWZEE'),(10,7,'SPEAROW'),(10,11,'12/52'),(10,14,'FIGHT'),(10,16,'ITEM'),(16,16,'RUN'),(9,14,'▶'))
    result=battle.battle_context(text,{'active':True,'kind':'trainer','opponent_species':'DROWZEE'},party)
    assert result['battle_tactic']=='switch_low_hp_support' and result['party_target_species']==167
    text=text_at((0,1,'DROWZEE'),(10,7,'SPEAROW'),(10,11,'12/52'),(10,14,'FIGHT'),(10,16,'ITEM'),(16,16,'RUN'),(15,14,'▶'))
    result=battle.battle_context(text,{'active':True,'kind':'trainer','opponent_species':'DROWZEE'},party)
    assert result['battle_tactic']=='switch_pending_party'
    assert result['objective']=='Confirm the current selection.'


def test_review_plan_hash_lock_stays_paused_until_actual_change(monkeypatch):
    import laya_pokemon.campaign as campaign
    responses = iter([PermissionError('sharing violation'), 'same', 'changed'])
    def read_hash(path):
        result = next(responses)
        if isinstance(result, Exception):raise result
        return result
    monkeypatch.setattr(campaign, 'sha256_file', read_hash)
    assert campaign.plan_changed(Path('plan.json'), 'same') is False
    assert campaign.plan_changed(Path('plan.json'), 'same') is False
    assert campaign.plan_changed(Path('plan.json'), 'same') is True


@pytest.mark.parametrize('locked_operation', ['load', 'hash'])
def test_plan_snapshot_lock_does_not_expose_candidate_until_full_success(monkeypatch, locked_operation):
    import laya_pokemon.campaign as campaign
    candidate = {'resume_revision': 2, 'resume_step': 'center', 'steps': []}
    calls = {'load': 0, 'hash': 0}
    def maybe_locked(operation, result):
        calls[operation] += 1
        if operation == locked_operation and calls[operation] == 1:
            raise PermissionError('sharing violation')
        return result
    monkeypatch.setattr(campaign, 'load_plan', lambda _:maybe_locked('load', candidate))
    monkeypatch.setattr(campaign, 'sha256_file', lambda _:maybe_locked('hash', 'new-hash'))
    assert campaign.load_plan_snapshot(Path('plan.json')) is None
    assert campaign.load_plan_snapshot(Path('plan.json')) == (candidate, 'new-hash')


def test_persistent_plan_lock_never_publishes_candidate_and_only_pumps_paused_ui(monkeypatch):
    import laya_pokemon.campaign as campaign
    calls, sleeps = [], []
    emulator = SimpleNamespace(send_input=lambda event:calls.append(event),
        tick=lambda *args:calls.append(('tick', *args)) or True)
    def locked(_):raise PermissionError('sharing violation')
    monkeypatch.setattr(campaign, 'load_plan', locked)
    monkeypatch.setattr(campaign.time, 'sleep', sleeps.append)
    for _ in range(3):
        snapshot = campaign.load_plan_snapshot(Path('plan.json'))
        assert snapshot is None
        campaign.wait_for_plan_read(emulator, SimpleNamespace(exists=lambda:False), 'PAUSE', 'UNPAUSE')
    assert calls == ['PAUSE', ('tick', 1, True, False), 'UNPAUSE'] * 3
    assert sleeps == [.05] * 3


@pytest.mark.parametrize('condition', ['stop', 'closed'])
def test_plan_lock_ui_wait_still_honors_stop_and_window_close(monkeypatch, condition):
    import laya_pokemon.campaign as campaign
    from laya_pokemon.game import WindowClosed
    calls = []
    emulator = SimpleNamespace(send_input=calls.append, tick=lambda *args:condition != 'closed')
    def no_sleep(_):raise AssertionError('STOP或關窗後不得繼續等鎖')
    monkeypatch.setattr(campaign.time, 'sleep', no_sleep)
    expected = KeyboardInterrupt if condition == 'stop' else WindowClosed
    with pytest.raises(expected):
        campaign.wait_for_plan_read(emulator, SimpleNamespace(exists=lambda:condition == 'stop'), 'PAUSE', 'UNPAUSE')
    assert calls == ['PAUSE', 'UNPAUSE']


@pytest.mark.parametrize('error', [FileNotFoundError('missing'), ValueError('bad hash'), UnicodeError('decode')])
def test_plan_hash_does_not_hide_nonpermission_errors(monkeypatch, error):
    import laya_pokemon.campaign as campaign
    def failed(_):raise error
    monkeypatch.setattr(campaign, 'sha256_file', failed)
    with pytest.raises(type(error)):
        campaign.plan_changed(Path('plan.json'), 'old')


@pytest.mark.parametrize('operation,error', [('load', ValueError('invalid plan')),
                                           ('load', UnicodeError('decode')),
                                           ('load', FileNotFoundError('missing')),
                                           ('hash', FileNotFoundError('missing'))])
def test_snapshot_preserves_existing_invalid_plan_and_other_error_handling(monkeypatch, operation, error):
    import laya_pokemon.campaign as campaign
    def failed(_):raise error
    monkeypatch.setattr(campaign, 'load_plan', failed if operation == 'load' else lambda _:{'steps': []})
    monkeypatch.setattr(campaign, 'sha256_file', failed if operation == 'hash' else lambda _:'hash')
    with pytest.raises(type(error)):
        campaign.load_plan_snapshot(Path('plan.json'))
