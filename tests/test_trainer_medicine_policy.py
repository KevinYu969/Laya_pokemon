"""True typed decoders and policy; original same-frame source-schema fixtures."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import laya_pokemon
from laya_pokemon.wild_opponent import decode_enemy_mon
from laya_pokemon.team_strategy import choose_damage_move
import pytest

ROOT=Path(laya_pokemon.__file__).resolve().parents[2]
STAGE=ROOT/'.local/staged-trainer-medicine-postreview-20261025'


def source_for_test(path,filename='trainer_medicine_policy.py'):
    p=Path(path).resolve()
    if p==STAGE/'test_trainer_medicine_policy.py':return STAGE/filename
    if p==ROOT/'tests/test_trainer_medicine_policy.py':return ROOT/'src/laya_pokemon'/filename
    raise RuntimeError('Only exact staged/formal test source paths are supported')


def fixture_for_test(path):
    p=Path(path).resolve()
    if p==STAGE/'test_trainer_medicine_policy.py':return STAGE/'test_trainer_medicine_ui.py'
    if p==ROOT/'tests/test_trainer_medicine_policy.py':return ROOT/'tests/test_trainer_medicine_ui.py'
    raise RuntimeError('Only exact staged/formal fixture paths are supported')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


fx=load('medicine_postreview_policy_fixture',fixture_for_test(__file__))
prior=getattr(laya_pokemon,'trainer_medicine_ui',None)
try:
    laya_pokemon.trainer_medicine_ui=fx.m
    policy=load('trainer_medicine_policy_candidate',source_for_test(__file__))
finally:
    if prior is None:del laya_pokemon.trainer_medicine_ui
    else:laya_pokemon.trainer_medicine_ui=prior


def inputs(hp=65,status=0,enemy_hp=190,speed=80,enemy_speed=80,max_hp=250,active=0,moves=None):
    s=fx.Session(active);s.p['party'][active].update(hp=hp,status=status,max_hp=max_hp)
    s.p['party'][active]['moves']=moves or [57,34,58,109]
    s.p['party'][active]['pp']=[11,15,10,10] if moves is None else [15,0,0,0]
    s.player=s.player_now();s.player['speed']=speed
    raw=fx.record(1,55,enemy_hp,190,0,[23,39,30,32],[20,30,25,5])
    raw[5:7]=[4,5];raw[21:23]=divmod(enemy_speed,256)
    s.enemy=decode_enemy_mon(raw)['enemy'];s.call()
    out={k:deepcopy(s.kw[k]) for k in ('text','progress','player_snapshot','enemy_proof','frame','location')}
    out['enemy_proof']['raw_record']=raw  # fixture helper otherwise hardcodes Water/Ice
    return out


def decide(kw):
    original=deepcopy(kw);r=policy.decide(**kw);assert kw==original
    assert r['action'] in ('none','medicine','finish','review') and type(r['reason']) is str
    assert r['survival_approved'] is False
    assert not any(key in r for key in ('available_actions','phase','field_move_complete','medicine_ui_complete'))
    return r


def enemy_update(kw,**updates):
    enemy=deepcopy(kw['enemy_proof']['enemy']);enemy.update(updates)
    raw=[enemy['species'],*divmod(enemy['hp'],256),0,enemy['status'],*enemy['types'],enemy['catch_rate'],
         *enemy['moves'],*enemy['dvs'],enemy['level'],*divmod(enemy['max_hp'],256)]
    for key in ('attack','defense','speed','special'):raw.extend(divmod(enemy[key],256))
    raw.extend(enemy['pp']);kw['enemy_proof']['raw_record']=raw
    kw['enemy_proof']['enemy']=decode_enemy_mon(raw)['enemy']


def test_source_normal_range_uses_current_special_actual_types_stab_screens_and_rng():
    kw=inputs();player=kw['player_snapshot']['player'];enemy=kw['enemy_proof']['enemy']
    estimate=policy.estimate_normal_damage(player,enemy,'SURF')
    # Source L48,Spc88/88,Surf95; neutral41 or21(screen), STAB61/31,
    # water hits actual ground/rock in source table order ->244/124; RNG217..255.
    assert (estimate['lower'],estimate['upper'])==(105,244)
    assert estimate['attack_stat']=='special' and estimate['rng']==[217,255]
    assert estimate['damage_exact'] is False and estimate['survival_approved'] is False


def test_physical_formula_uses_actual_burned_attack_without_halving_it_again():
    kw=inputs();player=deepcopy(kw['player_snapshot']['player']);enemy=deepcopy(kw['enemy_proof']['enemy'])
    player.update(level=50,attack=60,status=16,types=[0,0]);enemy.update(defense=85,types=[0,0])
    estimate=policy.estimate_normal_damage(player,enemy,'BODY_SLAM')
    assert (estimate['lower'],estimate['upper'])==(18,42) and estimate['attack_stat']=='attack'


def test_source_byte_scaling_and_psychic_type_alias_are_handled():
    kw=inputs();player=deepcopy(kw['player_snapshot']['player']);enemy=deepcopy(kw['enemy_proof']['enemy'])
    player.update(level=50,attack=401,types=[0,0]);enemy.update(defense=301,types=[0,0])
    assert tuple(policy.estimate_normal_damage(player,enemy,'BODY_SLAM')[k] for k in ('lower','upper'))==(33,76)
    player['types']=[24,24];enemy['types']=[3,3]
    assert policy.estimate_normal_damage(player,enemy,'PSYCHIC_M')['lower']>0


@pytest.mark.parametrize('move',['HORN_DRILL','SEISMIC_TOSS','EXPLOSION','COUNTER','FLY','SUPER_FANG'])
def test_fixed_ohko_explosive_or_special_effects_are_not_claimed_precise(move):
    kw=inputs()
    assert policy.estimate_normal_damage(kw['player_snapshot']['player'],kw['enemy_proof']['enemy'],move) is None


@pytest.mark.parametrize('hp,status,enemy_hp,speed,action,item',[
    (65,0,100,80,'finish',None),(65,16,100,80,'finish',None),
    (65,0,4,79,'medicine',18),(126,0,100,79,'finish',None),
    (125,0,190,80,'medicine',18),(126,0,190,80,'none',None),
    (126,16,190,80,'medicine',52),(65,64,190,80,'medicine',18),
    (126,64,190,80,'medicine',52),(65,16,190,80,'medicine',18)])
def test_root_finisher_priority_and_half_hp_policy(hp,status,enemy_hp,speed,action,item):
    kw=inputs(hp,status,enemy_hp,speed);r=decide(kw)
    assert r['action']==action
    if item:assert r['intent']['item']==item
    if action=='finish':
        p=kw['player_snapshot']['player'];e=kw['enemy_proof']['enemy']
        assert r['move_key']==choose_damage_move(p['species'],p['moves'],p['pp'],e['species'])
        assert r['estimate']['lower']>=e['hp']


def test_odd_max_hp_threshold_is_exact_half_not_the_old150_rule():
    assert decide(inputs(77,max_hp=155))['intent']['item']==18
    assert decide(inputs(78,max_hp=155))['action']=='none'
    assert decide(inputs(149,max_hp=250))['action']=='none'


def test_unavailable_normal_estimate_has_only_explicit_four_hp_heuristic():
    kw=inputs(enemy_hp=4);enemy_update(kw,special=512)
    assert policy.estimate_normal_damage(kw['player_snapshot']['player'],kw['enemy_proof']['enemy'],'SURF') is None
    r=decide(kw);assert r['action']=='finish' and r['estimate']['kind']=='enemy_hp_at_most4_heuristic'
    assert r['estimate']['lower'] is None and any('heuristic' in risk for risk in r['risks'])
    enemy_update(kw,hp=5);assert decide(kw)['intent']['item']==18
    kw=inputs(enemy_hp=4,speed=79);enemy_update(kw,special=512)
    assert decide(kw)['intent']['item']==18


def test_unsupported_special_move_does_not_enable_finisher_even_at_four_hp():
    assert decide(inputs(enemy_hp=4,active=4,moves=[19,0,0,0]))['intent']['item']==18


def test_actual_immunity_or_duplicate_defender_type_does_not_invent_damage():
    kw=inputs();p=deepcopy(kw['player_snapshot']['player']);enemy=deepcopy(kw['enemy_proof']['enemy'])
    p['types']=[0,0];enemy['types']=[8,8]
    assert policy.estimate_normal_damage(p,enemy,'BODY_SLAM')['lower']==0


@pytest.mark.parametrize('which',['hyper','full_heal'])
def test_missing_required_medicine_reviews_but_finisher_has_priority(which):
    kw=inputs() if which=='hyper' else inputs(150,16)
    item=18 if which=='hyper' else 52
    kw['progress']['inventory']=[i for i in kw['progress']['inventory'] if i['item']!=item]
    assert decide(kw)['action']=='review'
    if which=='hyper':
        enemy_update(kw,hp=4)
        assert decide(kw)['action']=='finish'


@pytest.mark.parametrize('bad',['player_frame','enemy_frame','duplicate_actor','party_lag','inventory','money','text_frame','pp_empty'])
def test_invalid_facts_or_active_sync_never_sends_a_medical_or_finish_intent(bad):
    kw=inputs()
    if bad=='player_frame':kw['player_snapshot']['observation_frame']=False
    elif bad=='enemy_frame':kw['enemy_proof']['frame_after']+=1
    elif bad=='duplicate_actor':kw['progress']['party'][1]=deepcopy(kw['progress']['party'][0])
    elif bad=='party_lag':kw['progress']['party'][0]['hp']-=1
    elif bad=='inventory':kw['progress']['inventory']=None
    elif bad=='money':kw['progress']['money']=False
    elif bad=='text_frame':kw['text']['observation_frame']=kw['frame']-1
    else:
        p=kw['player_snapshot']['player'];p['pp']=[0]*4;p['pp_remaining']=[0]*4
        kw['progress']['party'][0]['pp']=[0]*4
    assert decide(kw)['action']=='review'


def test_known_native_partial_or_used_page_is_none_not_a_policy_decision():
    kw=inputs();cells=deepcopy(kw['text']['cells']);cells[14][10]=' '
    kw['text']=fx.text(cells);assert decide(kw)['action']=='none'
    cells=fx.hud(kw['player_snapshot']['player'],kw['enemy_proof']['enemy'])
    fx.put(cells,1,14,'Enemy RHYDON');fx.put(cells,1,16,'used STOMP!')
    kw['text']=fx.text(cells);assert decide(kw)['action']=='none'


def test_player_zero_or_true_reader_enemy_zero_transition_stays_with_existing_guard():
    kw=inputs(hp=0);assert decide(kw)['action']=='none'
    kw=inputs();e=kw['enemy_proof']
    e.update(read_valid=False,enemy=None,raw_record=None,unknown_reason='enemy_zero_hp_transition',
             location=None,battle_kind=None,raw=None,battle_type=None,current_opponent=None)
    assert decide(kw)['reason']=='existing_faint_or_loss_guard'
    e['frame_after']=False;assert decide(kw)['action']=='review'


def test_nonwhitelist_map_remains_existing_battle_and_self_paths_are_exact():
    kw=inputs();kw['location']['map_id']=166
    assert decide(kw)['action']=='none'
    assert Path(policy.__file__).resolve()==source_for_test(__file__)
    assert source_for_test(ROOT/'tests/test_trainer_medicine_policy.py')==ROOT/'src/laya_pokemon/trainer_medicine_policy.py'
    with pytest.raises(RuntimeError):source_for_test(ROOT/'tests/copy/test_trainer_medicine_policy.py')


def test_malformed_zero_hp_packet_is_not_a_typed_faint_proof():
    kw=inputs(hp=0);kw['player_snapshot']['player']['pp'][0]=False
    assert decide(kw)['action']=='review'
