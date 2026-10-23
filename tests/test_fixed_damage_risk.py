"""本場已觀測龍怒的有界保護；合成輸入，不讀ROM／存檔／實況。"""
from copy import deepcopy

import pytest

from laya_pokemon import battle
from tests.test_battle import text_at


PARTY = [
    {'species':35,'level':29,'hp':81,'max_hp':90,'moves':[64,45,43,31],'pp':[30,40,30,20]},
    {'species':7,'level':29,'hp':99,'max_hp':99,'moves':[61,33,30,40],'pp':[20,35,25,35]},
    {'species':9,'level':31,'hp':86,'max_hp':86,'moves':[75,15,73,22],'pp':[25,30,10,10]},
    {'species':102,'level':25,'hp':63,'max_hp':63,'moves':[33,28,0,0],'pp':[35,15,0,0]},
]


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    monkeypatch.setattr(battle,'_no_pp_switch',None)
    monkeypatch.setattr(battle,'_fixed_damage_risk',None)


def verified(text):
    return {**text,'profile':battle._VISIBLE_PROFILE,'read_valid':True,
            'alignment_verified':True,'window_visible':False,'read_error':None,
            'warnings':['文字候選尚未完全校準；一般warning不代表讀取失敗。']}


def state(enemy='GYARADOS',**extra):
    return {'active':True,'kind':'trainer','opponent_species':enemy,
            'player_disabled_move':{'state':'clear','valid':True,'raw':0},**extra}


def dialogue(prefix='Enemy GYARADOS',move='used DRAGON RAGE!',enemy='GYARADOS'):
    return verified(text_at((0,1,enemy),(10,7,'FEAROW'),(10,10,'81/90'),
                            (1,14,prefix),(1,16,move)))


def command(hp=41,enemy='GYARADOS',player='FEAROW',maximum=90,cursor=(9,14)):
    return verified(text_at((0,1,enemy),(10,7,player),(10,10,f'{hp}/{maximum}'),
                            (10,14,'FIGHT'),(10,16,'ITEM'),(16,16,'RUN'),(*cursor,'▶')))


def learn():
    result=battle.battle_context(dialogue(),state(),deepcopy(PARTY))
    assert result['battle_tactic']=='observe_enemy_dragon_rage'
    assert result['observed_fixed_damage']['damage']==40


def low_party(hp=41):
    party=deepcopy(PARTY);party[0]['hp']=hp;return party


def test_original_1601_counterexample_switches_at_41_after_observed_81_hp_enemy_move():
    learn()
    party=low_party();before=deepcopy(party)
    result=battle.battle_context(command(),state(),party)
    assert result['battle_tactic']=='switch_observed_fixed_damage'
    assert result['party_target_species']==9 and result['objective']=='Move RIGHT.'
    assert result['fixed_damage_hp_threshold']==49 and party==before
    assert battle._no_pp_switch['reason']=='observed_dragon_rage_risk'


@pytest.mark.parametrize('hp,expected',[(81,'damage'),(50,'damage'),(49,'switch_observed_fixed_damage'),
                                       (41,'switch_observed_fixed_damage'),(1,'switch_observed_fixed_damage')])
def test_exact_fixed_40_plus_ceil_ten_percent_boundary(hp,expected):
    learn();r=battle.battle_context(command(hp),state(),low_party(hp))
    assert r['battle_tactic']==expected


@pytest.mark.parametrize('text',[
    dialogue(prefix='FEAROW'), dialogue(move='used DRAGON RAGE'), dialogue(move='used DRAGON RA'),
    dialogue(prefix='Enemy PIDGEOTTO'), dialogue(enemy='PIDGEOTTO'),
    {**dialogue(),'read_valid':False}, {**dialogue(),'alignment_verified':False},
    {**dialogue(),'window_visible':None}, {**dialogue(),'profile':'unknown'},
    {**dialogue(),'read_error':'unknown'}, {'cells':dialogue()['cells']},
])
def test_player_partial_wrong_enemy_or_unknown_decoder_never_learns(text):
    battle.battle_context(text,state(),deepcopy(PARTY))
    assert battle._fixed_damage_risk is None
    result=battle.battle_context(command(),state(),low_party())
    assert result.get('battle_tactic')=='damage'


def test_ambiguous_enemy_and_active_cursor_in_move_message_never_learn():
    text=dialogue();text['cells'][2][0:9]=list('PIDGEOTTO')
    battle.battle_context(text,state(),deepcopy(PARTY));assert battle._fixed_damage_risk is None
    text=dialogue();text['cells'][12][1]='▶'
    battle.battle_context(text,state(),deepcopy(PARTY));assert battle._fixed_damage_risk is None


@pytest.mark.parametrize('boundary',[
    {'active':False,'kind':'none'}, {'active':False,'kind':'lost_transition'},
    {'active':None,'kind':'unknown'}, {'active':True,'kind':'trainer','opponent_species':'KADABRA'},
])
def test_exit_loss_unknown_or_changed_enemy_clears_record_before_new_same_species_battle(boundary):
    learn();battle.battle_context(verified(text_at()),state(**boundary),deepcopy(PARTY))
    assert battle._fixed_damage_risk is None
    result=battle.battle_context(command(),state(),low_party())
    assert result.get('battle_tactic')=='damage'


@pytest.mark.parametrize('lower',[
    ((1,14,'Enemy GYARADOS'),(1,16,'fainted!')),
    ((1,14,'Will KEVIN'),(1,16,'change POKéMON?')),
    ((1,14,'Will KEVIN'),(1,16,'change POKéMON? ▼')),
])
def test_same_species_replacement_page_clears_risk(lower):
    learn();battle.battle_context(verified(text_at(*lower)),state(),deepcopy(PARTY))
    assert battle._fixed_damage_risk is None


@pytest.mark.parametrize('lower',[
    ((1,14,'Do not change'),(1,16,'POKéMON!')),
    ((1,14,'BLUE is'),(1,16,'about to use')),
    ((1,14,'about to use'),(1,16,'GYARADOS!')),
    ((1,14,'Will KEVIN'),(1,16,'change POKéMON')),
    ((1,14,'Will BLUE'),(1,16,'change POKéMON?')),
    ((1,14,'Enemy GYARADOS'),(1,16,'fainted')),
    ((1,14,'Enemy PIDGEOTTO'),(1,16,'fainted!')),
])
def test_unknown_change_or_partial_replacement_faint_page_retains_observed_risk(lower):
    learn();battle.battle_context(verified(text_at(*lower)),state(),deepcopy(PARTY))
    assert battle._fixed_damage_risk['enemy_species']=='GYARADOS'
    result=battle.battle_context(command(),state(),low_party())
    assert result['battle_tactic']=='switch_observed_fixed_damage'


@pytest.mark.parametrize('change',[
    lambda t:t['cells'][10].__setitem__(slice(10,15),list('     ')),
    lambda t:t['cells'][10].__setitem__(slice(10,15),list('42/90')),
    lambda t:t['cells'][7].__setitem__(slice(10,16),list('      ')),
    lambda t:t['cells'][13].__setitem__(9,'▶'),
    lambda t:t['cells'][14].__setitem__(slice(10,15),list('FIGH ')),
])
def test_unknown_hud_active_cursor_or_incomplete_command_cannot_send_a(change):
    learn();t=command();change(t)
    r=battle.battle_context(t,state(),low_party())
    assert r['phase']=='strategy_review' and r['available_actions']==['wait']


@pytest.mark.parametrize('change',[
    lambda p:p[0].update(hp=None),lambda p:p[0].update(pp=None),
    lambda p:p[2].update(pp=[None,30,10,10]),lambda p:p[2].update(hp='86'),
    lambda p:p[2].update(moves=[166,15,73,22]),lambda p:p[2].update(pp=[True,30,10,10]),
])
def test_unknown_party_hp_pp_and_moves_cannot_send_a(change):
    learn();p=low_party();change(p)
    r=battle.battle_context(command(),state(),p)
    assert r['phase']=='strategy_review' and r['available_actions']==['wait']


def test_no_support_above_fixed_damage_margin_and_half_hp_reviews_instead_of_attacking():
    learn();p=low_party()
    for mon in p[1:]:mon['hp']=40
    r=battle.battle_context(command(),state(),p)
    assert r['review_reason']=='fixed_damage_no_safe_attacking_support' and r['available_actions']==['wait']


def test_zero_pp_support_cannot_be_selected_and_disable_pp_copy_is_respected():
    learn();p=low_party()
    for mon in p[1:]:mon['pp']=[0,0,0,0]
    assert battle.battle_context(command(),state(),p)['review_reason']=='fixed_damage_no_safe_attacking_support'
    # 仍然健康且有其他有效PP的支援可以替補；不覆寫真實party PP。
    p=low_party();p[2]['pp']=[0,0,10,0]
    before=deepcopy(p)
    r=battle.battle_context(command(),state(),p)
    assert r['party_target_species']==7 and p==before


def test_pending_support_rechecked_and_cannot_switch_message_never_confirms_again():
    learn();p=low_party();battle.battle_context(command(),state(),p)
    p[2]['pp']=[0,0,0,0]
    t=verified(text_at((1,14,'Choose a POKéMON.')))
    assert battle.battle_context(t,state(),p)['review_reason']=='fixed_damage_pending_support_not_verified'
    p=low_party();t=verified(text_at((1,14,"Can't switch!")))
    r=battle.battle_context(t,state(),p)
    assert r['review_reason']=='fixed_damage_switch_rejected' and r['available_actions']==['wait']


def test_unreadable_known_risk_ui_only_passively_waits_with_bound():
    learn();t={**command(),'read_valid':False}
    for _ in range(30):assert battle.battle_context(t,state(),low_party())['available_actions']==['wait']
    r=battle.battle_context(t,state(),low_party())
    assert r['review_reason']=='fixed_damage_visible_wait_exhausted' and r['available_actions']==['wait']


def test_wild_capture_and_run_are_unchanged_and_do_not_learn_dragon_rage():
    battle.battle_context(dialogue(),state(kind='wild'),deepcopy(PARTY))
    assert battle._fixed_damage_risk is None
    t=command(20);p=low_party(20)
    assert battle.battle_context(t,state(kind='wild'),p)['battle_tactic']=='retreat'
    t=command(81,enemy='CATERPIE')
    assert battle.battle_context(t,state(enemy='CATERPIE',kind='wild'),deepcopy(PARTY),[{'item':4,'quantity':6}])['battle_tactic']=='capture'


@pytest.mark.parametrize('text',[verified(text_at()),verified(text_at((0,0,'UNKNOWN')))])
def test_armed_complete_decoder_blank_or_unrecognized_fallback_only_waits_with_bound(text):
    learn()
    for _ in range(30):
        r=battle.battle_context(text,state(),low_party())
        assert r['phase']=='battle_animation' and r['available_actions']==['wait']
    r=battle.battle_context(text,state(),low_party())
    assert r['review_reason']=='fixed_damage_unrecognized_ui_wait_exhausted'
    assert r['available_actions']==['wait']


def moves_page(hp=41):
    return verified(text_at((0,1,'GYARADOS'),(10,7,'FEAROW'),(10,10,f'{hp}/90'),
                            (6,13,'PECK'),(6,14,'GROWL'),(6,15,'LEER'),
                            (6,16,'FURY ATTACK'),(5,13,'▶')))


def test_low_hp_direct_moves_page_only_b_then_command_requests_pkmn():
    learn();p=low_party()
    r=battle.battle_context(moves_page(),state(),p)
    assert r['available_actions']==['b','wait'] and r['battle_tactic']=='return_for_fixed_damage_switch'
    assert battle._no_pp_switch is None
    r=battle.battle_context(command(),state(),p)
    assert r['battle_tactic']=='switch_observed_fixed_damage' and r['party_target_species']==9


@pytest.mark.parametrize('hp',[50,81])
def test_verified_high_hp_moves_selection_remains_peck(hp):
    learn();r=battle.battle_context(moves_page(hp),state(),low_party(hp))
    assert r['chosen_move']=='PECK' and r['objective']=='Confirm the current selection.'


@pytest.mark.parametrize('change',[
    lambda t:t['cells'][10].__setitem__(slice(10,15),list('     ')),
    lambda t:t['cells'][10].__setitem__(slice(10,15),list('42/90')),
    lambda t:t['cells'][7].__setitem__(slice(10,16),list('      ')),
    lambda t:t['cells'][13].__setitem__(5,' '),
    lambda t:t['cells'][13].__setitem__(5,'▷'),
    lambda t:t['cells'][15].__setitem__(5,'▶'),
    lambda t:t['cells'][13].__setitem__(slice(6,10),list('PEC ')),
    lambda t:t['cells'][16].__setitem__(slice(6,17),list('           ')),
])
def test_unknown_moves_hud_cursor_or_incomplete_labels_never_send_a(change):
    learn();t=moves_page();change(t)
    r=battle.battle_context(t,state(),low_party())
    assert r['phase']=='strategy_review' and r['available_actions']==['wait']


def test_unknown_moves_pp_reviews_before_iterating_or_attacking():
    learn();p=low_party();p[0]['pp']=None
    r=battle.battle_context(moves_page(),state(),p)
    assert r['phase']=='strategy_review' and r['available_actions']==['wait']


@pytest.mark.parametrize('actor,move',[('FEAROW','PECK'),('Enemy GYARADOS','BITE'),('IVYSAUR','RAZOR LEAF')])
def test_full_attack_dialogue_is_not_mistaken_for_moves_menu(actor,move):
    learn()
    text=verified(text_at((0,1,'GYARADOS'),(10,7,'FEAROW'),(10,10,'41/90'),
                          (1,14,actor),(1,16,'used '+move+'!')))
    r=battle.battle_context(text,state(),low_party())
    assert r['phase']=='battle_dialogue' and r['available_actions']==['a','wait']
