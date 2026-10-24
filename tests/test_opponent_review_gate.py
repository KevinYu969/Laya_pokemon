from copy import deepcopy
import pytest
from laya_pokemon.opponent_review_gate import context,PROFILE

def packet(species='ARCANINE'):
    return dict(frame=1737977,location=dict(map_id=166,x=3,y=4),
        battle_state=dict(raw=2,active=True,kind='trainer',observation_frame=1737977,opponent_species=species))

def step():return dict(kind='interact',map_id=166,target=[3,4],face='up',event='beat_blaine',opponent_review=PROFILE)

def test_first_arcanine_pauses_before_any_fight_or_keep_action_without_mutation():
    s,p=packet(),step();old=deepcopy((s,p));r=context(s,p)
    assert r['review_reason']=='blaine_arcanine_medicine_calibration' and r['available_actions']==['wait']
    assert (s,p)==old

@pytest.mark.parametrize('species',['GROWLITHE','PONYTA','RAPIDASH'])
def test_three_source_opponents_use_existing_battle_and_attrition_guards(species):
    assert context(packet(species),step()) is None

def test_true_nonbattle_leaves_normal_talk_to_existing_controller():
    s=packet();s['battle_state'].update(raw=0,kind='none',active=False)
    assert context(s,step()) is None

@pytest.mark.parametrize('species',[None,20,False,'OTHER','arcanine'])
def test_unknown_identity_cannot_enter_attacks(species):
    assert context(packet(species),step())['available_actions']==['wait']

@pytest.mark.parametrize('field,value',[('raw',True),('raw',1),('active',1),('kind','wild'),('observation_frame',1737978)])
def test_unverified_or_other_battle_is_review(field,value):
    s=packet();s['battle_state'][field]=value
    assert context(s,step())['phase']=='campaign_review'

@pytest.mark.parametrize('field,value',[('map_id',True),('target',[3.0,4]),('event','beat_champion_rival'),('opponent_review','other')])
def test_foreign_step_never_authorizes_open_battle(field,value):
    p=step();p[field]=value
    assert context(packet(),p)['phase']=='campaign_review'

def test_unrequested_gate_leaves_existing_routes_unchanged():
    p=step();p.pop('opponent_review')
    assert context(packet(),p) is None
