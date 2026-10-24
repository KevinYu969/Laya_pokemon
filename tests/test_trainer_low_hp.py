"""新reader明確啟用的半血trainer政策；只用合成字格/字典，不讀遊戲。"""
from copy import deepcopy
from types import SimpleNamespace
import re

import pytest

from laya_pokemon import battle
from tests.test_battle import text_at


PARTY = [
    {'species':7,'level':36,'hp':51,'max_hp':121,'status':0,
     'moves':[61,33,30,40],'pp':[0,35,14,35]},
    {'species':132,'level':35,'hp':168,'max_hp':168,'status':0,
     'moves':[29,133,156,34],'pp':[15,20,10,15]},
    {'species':102,'level':35,'hp':90,'max_hp':90,'status':0,
     'moves':[33,28,98,39],'pp':[35,15,30,30]},
    {'species':154,'level':35,'hp':111,'max_hp':111,'status':0,
     'moves':[75,15,73,22],'pp':[25,30,10,10]},
    {'species':35,'level':35,'hp':108,'max_hp':108,'status':0,
     'moves':[64,65,43,31],'pp':[35,20,30,20]},
]


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    monkeypatch.setattr(battle,'_no_pp_switch',None)
    monkeypatch.setattr(battle,'_fixed_damage_risk',None)


def verified(text):
    raw=[''.join(row) for row in text['cells']]
    selected=[(i,row.rstrip()) for i,row in enumerate(raw) if re.search(r'[A-Za-z0-9]{2,}',row)][:12]
    return {**text,'lines':[row for _,row in selected],'line_rows':[i for i,_ in selected],
            'profile':battle._VISIBLE_PROFILE,'read_valid':True,
            'alignment_verified':True,'window_visible':False,'read_error':None}


def state(**updates):
    return {'raw':2,'active':True,'kind':'trainer','opponent_species':'WEEZING',
            'trainer_half_hp_profile':battle.TRAINER_HALF_HP_PROFILE,
            'player_disabled_move':{'state':'clear','valid':True,'raw':0},**updates}


def command(party=None, *, cursor=(9,14), active=0, enemy='WEEZING'):
    party=PARTY if party is None else party
    mon=party[active]
    from laya_pokemon.team_strategy import species_key
    return verified(text_at((1,0,enemy),(4,1,'43'),(10,7,species_key(mon['species'])),
                            (14,8,str(mon['level'])),(10,10,f"{mon['hp']}/{mon['max_hp']}"),
                            (10,14,'FIGHT'),(10,16,'ITEM'),(16,16,'RUN'),(*cursor,'▶')))


def party_page(party=None,index=0,*,submenu=False,inactive=False):
    party=PARTY if party is None else party
    from laya_pokemon.team_strategy import species_key
    entries=[]
    for i,mon in enumerate(party):
        entries += [(3,i*2,species_key(mon['species'])),(14,i*2,str(mon['level'])),
                    (13,i*2+1,f"{mon['hp']:3}/{mon['max_hp']:3}")]
    text=text_at(*entries,(1,14,'CHOOSE A POKéMON.'),(0,index*2+1,'▷' if submenu or inactive else '▶'))
    if submenu:
        for y in range(11,18):text['cells'][y][11:20]=[' ']*9
        for y,label in ((12,'SWITCH'),(14,'STATS'),(16,'CANCEL')):
            text['cells'][y][13:13+len(label)]=label
        text['cells'][12][12]='▷' if inactive else '▶'
    return verified(text)


def start(party=None):
    party=deepcopy(PARTY) if party is None else party
    result=battle.battle_context(command(party),state(),party)
    assert result['battle_tactic']=='switch_trainer_half_hp' and result['party_target_species']==132
    return party,result


def assert_review(result):
    assert result['phase']=='strategy_review' and result['available_actions']==['wait']


def test_real_shaped_51_of_121_with_bubble_zero_and_horn_pp_requests_normal_pkmn():
    party=deepcopy(PARTY);before=deepcopy(party)
    _,result=start(party)
    assert result['objective']=='Move RIGHT.' and result['battle_target_tile']==[16,14]
    assert party==before and battle._no_pp_switch['reason']=='trainer_half_hp_support'
    assert battle._no_pp_switch['enemy_species']=='WEEZING'


@pytest.mark.parametrize('maximum,hp,expected',[(120,40,'switch_low_hp_support'),
    (120,41,'switch_trainer_half_hp'),(120,60,'switch_trainer_half_hp'),(120,61,'damage'),
    (121,40,'switch_low_hp_support'),(121,41,'switch_trainer_half_hp'),
    (121,60,'switch_trainer_half_hp'),(121,61,'damage')])
def test_inclusive_half_and_existing_third_boundaries(maximum,hp,expected):
    party=deepcopy(PARTY);party[0].update(hp=hp,max_hp=maximum)
    result=battle.battle_context(command(party),state(),party)
    assert result['battle_tactic']==expected


def test_legacy_packet_without_explicit_reader_opt_in_preserves_old_damage():
    flag=state();flag.pop('trainer_half_hp_profile')
    assert battle.battle_context(command(),flag,deepcopy(PARTY))['battle_tactic']=='damage'
    assert battle._no_pp_switch is None


@pytest.mark.parametrize('raw',[0,1,2,255,17])
def test_read_battle_state_marks_only_native_trainer_raw2(raw):
    result=battle.read_battle_state(SimpleNamespace(memory={0xD057:raw}))
    assert ('trainer_half_hp_profile' in result) is (raw==2)
    if raw==2:assert result['trainer_half_hp_profile']=='red-en-trainer-half-hp-v1'


@pytest.mark.parametrize('change',[
    {'trainer_half_hp_profile':'unknown'}, {'raw':None}, {'raw':True}, {'raw':1},
    {'active':None}, {'active':False}, {'kind':'unknown'}, {'kind':'wild'},
])
def test_opted_but_unknown_reader_packet_cannot_attack(change):
    assert_review(battle.battle_context(command(),state(**change),deepcopy(PARTY)))
    assert battle._no_pp_switch is None


def test_opted_missing_raw_cannot_be_misread_as_legacy():
    flag=state();flag.pop('raw')
    assert_review(battle.battle_context(command(),flag,deepcopy(PARTY)))


@pytest.mark.parametrize('change',[
    lambda t:t.update(profile='unknown'),lambda t:t.update(read_valid=False),
    lambda t:t.update(alignment_verified=False),lambda t:t.update(read_error='unknown'),
    lambda t:t.update(window_visible=None),
    lambda t:t['cells'][14].__setitem__(slice(10,15),list('FIGH ')),
    lambda t:t['cells'][10].__setitem__(slice(10,16),list('52/121')),
    lambda t:t['cells'][10].__setitem__(slice(10,16),list('      ')),
    lambda t:t['cells'][7].__setitem__(slice(10,18),list('        ')),
    lambda t:t['cells'][8].__setitem__(slice(14,16),list('35')),
    lambda t:t['cells'][13].__setitem__(9,'▶'),
    lambda t:t['cells'][2].__setitem__(slice(1,8),list('WEEZING')),
    lambda t:t['cells'][6].__setitem__(slice(10,18),list('NIDOKING')),
    lambda t:t['cells'][13].__setitem__(slice(1,4),list('YES')),
])
def test_unknown_or_partial_command_hud_enemy_friend_and_cursor_do_not_start(change):
    text=command();change(text)
    assert_review(battle.battle_context(text,state(),deepcopy(PARTY)))
    assert battle._no_pp_switch is None


def test_actual_enemy_is_required_not_only_visible_species():
    assert_review(battle.battle_context(command(),state(opponent_species='KOFFING'),deepcopy(PARTY)))


@pytest.mark.parametrize('change',[
    lambda p:p[0].update(hp=True),lambda p:p[0].update(max_hp=None),
    lambda p:p[0].update(pp=[0,35,True,35]),lambda p:p[1].pop('status'),
    lambda p:p.append(deepcopy(p[1])),lambda p:p[1].update(status=255),
])
def test_unknown_or_ambiguous_party_is_reviewed_before_any_new_intent(change):
    party=deepcopy(PARTY);change(party)
    assert_review(battle.battle_context(command(),state(),party))
    assert battle._no_pp_switch is None


@pytest.mark.parametrize('change',[
    lambda p:[m.update(hp=0) for m in p[1:]],
    lambda p:[m.update(hp=m['max_hp']//2) for m in p[1:]],
    lambda p:[m.update(status=8) for m in p[1:]],
    lambda p:[m.update(pp=[0,0,0,0]) for m in p[1:]],
    lambda p:[m.update(moves=[40,0,0,0],pp=[35,0,0,0]) for m in p[1:]],
])
def test_no_healthy_effective_or_strong_enough_support_reviews(change):
    party=deepcopy(PARTY);change(party)
    assert_review(battle.battle_context(command(party),state(),party))
    assert battle._no_pp_switch is None


def test_wild_retreat_and_replacement_yes_no_are_unchanged():
    flag=state(raw=1,kind='wild');flag.pop('trainer_half_hp_profile')
    assert battle.battle_context(command(),flag,deepcopy(PARTY))['battle_tactic']=='retreat'
    text=verified(text_at((10,7,'NIDOKING'),(1,14,'Will KEVIN'),(1,16,'change POKéMON?')))
    result=battle.battle_context(text,state(),deepcopy(PARTY))
    assert result['available_actions']==['b','wait'] and result['battle_tactic']=='keep_active'


def test_existing_no_pp_and_type_support_keep_priority():
    party=deepcopy(PARTY);party[0]['pp']=[0,0,0,0]
    # 舊type分支在no-PP前；沒健康過半支援時才落到原no-PP分支。
    for mon in party[1:]:mon['hp']=mon['max_hp']//2
    assert battle.battle_context(command(party),state(),party)['battle_tactic']=='switch_no_attack_pp'
    battle._no_pp_switch=None
    party=deepcopy(PARTY);party[0].update(moves=[40,0,0,0],pp=[35,0,0,0])
    assert battle.battle_context(command(party),state(),party)['battle_tactic']=='switch_type_advantage'


def test_existing_observed_dragon_rage_has_priority_over_new_half_band():
    from tests.test_fixed_damage_risk import learn,low_party,command as old_command,state as old_state
    learn();party=low_party();flag=old_state(raw=2,trainer_half_hp_profile=battle.TRAINER_HALF_HP_PROFILE)
    for mon in party:mon['status']=0
    result=battle.battle_context(verified(old_command()),flag,party)
    assert result['battle_tactic']=='switch_observed_fixed_damage'


def test_pending_normal_pkmn_party_switch_and_actual_target_completion_preserve_data():
    party,_=start();before=deepcopy(party)
    result=battle.battle_context(command(party,cursor=(15,14)),state(),party)
    assert result['objective']=='Confirm the current selection.'
    assert battle.battle_context(command(party,cursor=(15,14)),state(),party)['available_actions']==['wait']
    assert battle.battle_context(party_page(party,0),state(),party)['objective']=='Move DOWN.'
    assert battle.battle_context(party_page(party,1),state(),party)['objective']=='Confirm the current selection.'
    assert battle.battle_context(party_page(party,1),state(),party)['available_actions']==['wait']
    assert battle.battle_context(party_page(party,1,submenu=True),state(),party)['objective']=='Confirm the current selection.'
    assert battle.battle_context(party_page(party,1,submenu=True),state(),party)['available_actions']==['wait']
    result=battle.battle_context(command(party,active=1),state(),party)
    assert result['battle_tactic']=='damage' and battle._no_pp_switch is None and party==before


@pytest.mark.parametrize('change',[
    lambda p:p[1].update(hp=80),lambda p:p[1].update(status=8),
    lambda p:p[1].update(pp=[0,0,0,0]),lambda p:p.append(deepcopy(p[1])),
])
def test_pending_target_health_status_pp_and_uniqueness_are_rechecked(change):
    party,_=start();change(party)
    assert_review(battle.battle_context(party_page(PARTY,0),state(),party))


def test_pending_enemy_changed_unknown_decoder_and_switch_cancellation_review_only():
    party,_=start()
    assert_review(battle.battle_context(party_page(party),state(opponent_species='KOFFING'),party))
    text=party_page(party);text['read_valid']=False
    assert_review(battle.battle_context(text,state(),party))
    text=party_page(party,1,submenu=True);text['cells'][12][12]=' ';text['cells'][16][12]='▶'
    assert_review(battle.battle_context(text,state(),party))


def test_pending_partial_party_and_unknown_switch_labels_never_confirm():
    party,_=start();text=party_page(party,1);text['cells'][8][3:9]=list('      ')
    assert_review(battle.battle_context(text,state(),party))
    text=party_page(party,1,submenu=True);text['cells'][16][13:19]=list('TOSS  ')
    assert_review(battle.battle_context(text,state(),party))


def test_pending_completion_cannot_accept_wrong_visible_enemy_or_polluted_command():
    party,_=start()
    battle.battle_context(command(party,cursor=(15,14)),state(),party)
    battle.battle_context(party_page(party,1),state(),party)
    battle.battle_context(party_page(party,1,submenu=True),state(),party)
    assert_review(battle.battle_context(command(party,active=1,enemy='KOFFING'),state(),party))
    text=command(party,active=1);text['cells'][13][1:4]=list('YES');text=verified(text)
    assert_review(battle.battle_context(text,state(),party))
    assert battle._no_pp_switch is not None


def test_pending_lost_reader_opt_in_cannot_fall_back_to_legacy_switch():
    party,_=start();flag=state();flag.pop('trainer_half_hp_profile')
    assert_review(battle.battle_context(party_page(party),flag,party))


def test_pending_inactive_submenu_and_known_blank_wait_are_bounded():
    party,_=start()
    battle.battle_context(command(party,cursor=(15,14)),state(),party)
    battle.battle_context(party_page(party,1),state(),party)
    battle.battle_context(party_page(party,1,submenu=True),state(),party)
    result=battle.battle_context(party_page(party,1,submenu=True,inactive=True),state(),party)
    assert result['available_actions']==['wait']
    for _ in range(24):assert battle.battle_context(verified(text_at()),state(),party)['available_actions']==['wait']
    assert_review(battle.battle_context(verified(text_at()),state(),party))


@pytest.mark.parametrize('text',[None,{}, {'cells':None},{'cells':[None]*18}])
def test_opted_malformed_text_packet_is_reviewed(text):
    assert_review(battle.battle_context(text,state(),deepcopy(PARTY)))


def native_getm_pending(*,old_hud=False):
    """Literal physical cells from the no-input clone, not an ASCII fixture."""
    party=[deepcopy(PARTY[i]) for i in (1,0,2,3,4)]
    party[0].update(level=36,hp=82,max_hp=173)
    party[1].update(hp=121,pp=[20,15,25,35],moves=[61,57,30,40])
    battle._no_pp_switch={'reason':battle._TRAINER_HALF_REASON,'species':35,
        'active_species':132,'enemy_species':'HYPNO',
        'party_species':tuple(m['species'] for m in party),
        'party_open_requested':True,'member_selected':True,
        'confirm_requested':True,'switch_requested':True}
    mon=party[0 if old_hud else 4]
    from laya_pokemon.team_strategy import species_key
    text=text_at((1,0,'HYPNO'),(5,1,'28'),(10,7,species_key(mon['species'])),
                 (15,8,str(mon['level'])),(11,10,f"{mon['hp']:3}/{mon['max_hp']:3}"))
    for x,value in ((1,'G'),(2,'e'),(3,'t'),(4,"'m"),(5,'!')):text['cells'][14][x]=value
    text['cells'][14][7:14]=list('FEAROW!')
    return party,verified(text)


@pytest.mark.parametrize('old_hud',[False,True])
def test_exact_native_getm_waits_with_target_or_old_hud_and_keeps_pending(old_hud):
    party,text=native_getm_pending(old_hud=old_hud);before=deepcopy(party)
    record=battle._no_pp_switch
    assert battle._fixed_damage_rows(text) is None
    assert battle._trainer_half_rows(text) is None  # no unbound/new-start expansion
    result=battle.battle_context(text,state(opponent_species='HYPNO'),party)
    assert result['available_actions']==['wait'] and result['phase']=='battle_animation'
    assert battle._no_pp_switch is record and party==before
    result=battle.battle_context(command(party,active=4,enemy='HYPNO'),state(opponent_species='HYPNO'),party)
    assert result['battle_tactic']=='damage' and battle._no_pp_switch is None


@pytest.mark.parametrize('change',[
    lambda t:t['cells'][14].__setitem__(4,"'r"),
    lambda t:t['cells'][14].__setitem__(4,"'M"),
    lambda t:t['cells'][14].__setitem__(3,"'m"),
    lambda t:t['cells'][14].__setitem__(8,'X'),
    lambda t:t['cells'][14].__setitem__(13,' '),
    lambda t:t['cells'][16].__setitem__(18,'▼'),
    lambda t:t['cells'][13].__setitem__(1,'X'),
    lambda t:t['cells'][0].__setitem__(2,'X'),
    lambda t:t['cells'][7].__setitem__(11,'X'),
    lambda t:t['cells'][10].__setitem__(13,'7'),
    lambda t:t['cells'][8].__setitem__(16,'4'),
    lambda t:t['cells'][4].__setitem__(4,"'m"),
])
def test_native_getm_wrong_cell_character_hud_or_pollution_never_sends_a(change):
    party,text=native_getm_pending();change(text);text=verified(text)
    assert_review(battle.battle_context(text,state(opponent_species='HYPNO'),party))
    assert battle._no_pp_switch is not None


@pytest.mark.parametrize('change',[
    lambda t:t.update(profile='unknown'),lambda t:t.update(read_valid=False),
    lambda t:t.update(alignment_verified=False),lambda t:t.update(read_error='unknown'),
    lambda t:t.update(window_visible=None),lambda t:t.update(lines=['Getm! FEAROW!']),
    lambda t:t.update(line_rows=[14]),
])
def test_native_getm_requires_original_decoder_and_raw_summary_proofs(change):
    party,text=native_getm_pending();change(text)
    assert_review(battle.battle_context(text,state(opponent_species='HYPNO'),party))


@pytest.mark.parametrize('change,old_hud',[
    (lambda r:r.update(reason='switch_low_hp_support'),False),
    (lambda r:r.update(switch_requested=False),False),
    (lambda r:r.update(switch_requested=1),False),
    (lambda r:r.update(species=132),False),
    (lambda r:r.update(active_species=102),True),
    (lambda r:r.update(enemy_species='KOFFING'),False),
])
def test_native_getm_requires_exact_existing_owner_and_target(change,old_hud):
    party,text=native_getm_pending(old_hud=old_hud);change(battle._no_pp_switch)
    # The half helper cannot expand this cell in any other controller/intent.
    assert battle._trainer_half_rows(text,party=party) is None


def test_native_getm_unknown_enemy_or_target_party_change_reviews():
    party,text=native_getm_pending()
    assert_review(battle.battle_context(text,state(opponent_species='KOFFING'),party))
    party[4]['status']=8
    assert_review(battle.battle_context(text,state(opponent_species='HYPNO'),party))


def test_native_getm_wait_uses_existing_25_call_budget_without_clearing_pending():
    party,text=native_getm_pending();record=battle._no_pp_switch
    for _ in range(25):
        result=battle.battle_context(text,state(opponent_species='HYPNO'),party)
        assert result['phase']=='battle_animation' and result['available_actions']==['wait']
    assert_review(battle.battle_context(text,state(opponent_species='HYPNO'),party))
    assert battle._no_pp_switch is record and record['waits']==26
