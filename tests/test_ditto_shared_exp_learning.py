"""0HP百變怪收尾涵蓋真隊員分EXP及當級已學成的來源招式。"""
from copy import deepcopy
import pytest
from tests.test_ditto_transform import ko_memory,signal_state,ko_text,party
from laya_pokemon.battle import battle_context


def lapras_case():
    data=ko_memory();data[0xD164]=19
    members=party();members[0].update(species=19,level=16,moves=[55,45,47,0],pp=[25,40,15,0])
    return signal_state(data),members


def test_lapras_actual_level_sing_receipt_advances_and_partial_waits():
    state,members=lapras_case()
    text=ko_text((10,7,'SNORLAX '),(1,14,'LAPRAS learned'),(1,16,'SING!'),header=False)
    assert battle_context(text,state,members)['available_actions']==['a','wait']
    text=ko_text((10,7,'SNORLAX '),(1,14,'LAPRAS learned'),(1,16,'SI'),header=False)
    assert battle_context(text,state,members)['available_actions']==['wait']


def test_unknown_or_not_installed_move_still_reviews():
    state,members=lapras_case()
    members[0]['moves'][2]=0;members[0]['pp'][2]=0
    text=ko_text((10,7,'SNORLAX '),(1,14,'LAPRAS learned'),(1,16,'SING!'),header=False)
    assert battle_context(text,state,members)['review_reason']=='ditto_ko_transition_ui_not_verified'


def test_other_real_party_member_can_receive_shared_experience():
    text=ko_text((1,14,'SNORLAX gained'),(1,16,'111 EXP. Points!'),header=False)
    assert battle_context(text,signal_state(ko_memory()),party())['available_actions']==['a','wait']


@pytest.mark.parametrize('pp',[79,82])
def test_ppup_is_not_mistaken_for_fresh_natural_learning(pp):
    state,members=lapras_case();members[0]['pp'][2]=pp
    text=ko_text((10,7,'SNORLAX '),(1,14,'LAPRAS learned'),(1,16,'SING!'),header=False)
    assert battle_context(text,state,members)['review_reason']=='ditto_ko_transition_ui_not_verified'
