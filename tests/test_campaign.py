from types import SimpleNamespace
from pathlib import Path
import json
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
    journal=Journal(tmp_path,{'story_event_bits':{},'badges_raw':1})
    def save(name):p=tmp_path/name;p.write_bytes(b'synthetic-state');return p
    assert journal.observe(emulator,state,{'wall_seconds':30},save)==[]
    state['phase']='unclassified';records=journal.observe(emulator,state,{'wall_seconds':31},save)
    assert len(records)==1 and records[0]['id']=='misty' and '+08:00' in records[0]['completed_at_taipei']
    assert journal.observe(emulator,state,{'wall_seconds':32},save)==[]


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
