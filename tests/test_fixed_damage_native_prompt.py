"""Real native glyph decoding; source prompts never fabricate Party HP sync."""
from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import laya_pokemon
import pytest
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
from laya_pokemon.observation import read_visible_text

ROOT=Path(laya_pokemon.__file__).resolve().parents[2]
STAGE=ROOT/'.local/staged-fixed-damage-visible-20261028'
HERE=Path(__file__).resolve()
if HERE==STAGE/'test_fixed_damage_native_prompt.py':CANDIDATE=STAGE/'battle.py'
elif HERE==ROOT/'tests/test_fixed_damage_native_prompt.py':CANDIDATE=ROOT/'src/laya_pokemon/battle.py'
else:raise RuntimeError('Only exact stage/formal source-bound prompt test paths are allowed')

@pytest.fixture
def m():
    spec=importlib.util.spec_from_file_location('laya_pokemon._fixed_damage_prompt_candidate',CANDIDATE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module._test_spec=spec
    return module

def party():
    names=[(19,'LAPRAS',41,139,169),(132,'SNORLAX',41,198,198),(102,'EEVEE',35,90,90),
           (154,'VENUSAUR',35,111,111),(35,'FEAROW',37,114,114),(7,'NIDOKING',36,121,121)]
    return [dict(species=s,species_name=n,level=lv,hp=hp,max_hp=mx,exp=92104 if i==0 else 50000,
        status=0,moves=[57,34,58,109],pp=[13,15,4,10]) for i,(s,n,lv,hp,mx) in enumerate(names)]

def state(**changes):
    return dict(active=True,kind='trainer',raw=2,opponent_species='GYARADOS',observation_frame=14161,
        player_disabled_move=dict(state='clear',valid=True,raw=0),**changes)

def native_text(first,second,*,arrow=True,hp=99,enemy='GYARADOS',extra=None):
    cells=[[' ']*20 for _ in range(18)]
    def put(x,y,s):cells[y][x:x+len(s)]=list(s)
    put(1,0,enemy);put(5,1,'47');put(10,7,'LAPRAS');put(15,8,'41');put(11,10,f'{hp:3}/169')
    for y,value in ((14,first),(16,second)):
        x=1
        while value:
            token="'s" if value.startswith("'s") else value[0]
            cells[y][x]=token;x+=1;value=value[len(token):]
    if arrow:cells[16][18]='▼'
    if extra:extra(cells)
    reverse={}
    for code,char in sdk.POKEMON_TEXT_DECODING.items():
        if type(code) is int and 0<=code<=255:reverse.setdefault(char,code)
    class Tiles:
        def __getitem__(self,xy):x,y=xy;return reverse[cells[y][x]]
    pb=SimpleNamespace(memory={0xFF40:0xB1},screen=SimpleNamespace(tilemap_position_list=[(0,0,0,0)]*144),
                       tilemap_background=Tiles(),tilemap_window=Tiles())
    text=read_visible_text(pb);assert text['read_valid'] and text['alignment_verified']
    return text

def arm(m):
    text=native_text('Enemy GYARADOS','used DRAGON RAGE!',hp=139)
    r=m.battle_context(text,state(),party())
    assert r['battle_tactic']=='observe_enemy_dragon_rage' and m._fixed_damage_risk['damage']==40
    m._fixed_damage_risk['unreadable_waits']=31
    return m._fixed_damage_risk

@pytest.mark.parametrize('first,second,kind',[("It's super",'effective!','super_effective'),
    ("It's not very",'effective...','not_very_effective'),("Enemy GYARADOS's",'attack missed!','enemy_attack_missed')])
def test_exact_source_native_s_prompts_offer_a_keep_risk_and_record_old31(m,first,second,kind):
    risk=arm(m);text=native_text(first,second);p=party();before=deepcopy((text,p))
    assert any(cell=="'s" for row in text['cells'] for cell in row)
    r=m.battle_context(text,state(),p)
    assert r['available_actions']==['a','wait'] and r['native_fixed_damage_prompt']==kind
    assert r['visible_player_hp']==dict(hp=99,max_hp=169) and r['party_player_hp']==139
    assert r['party_hp_rewritten'] is False and r['enemy_turn_resolved'] is False and r['survival_approved'] is False
    assert (text,p)==before and p[0]['hp']==139
    assert m._fixed_damage_risk is risk and risk['damage']==40 and risk['move_id']==82 and risk['unreadable_waits']==0
    assert risk['native_prompt_history'][-1]==dict(frame=14161,kind=kind,arrow=True,unreadable_waits_before=31)

def test_full_known_body_without_arrow_only_waits_then_true_arrow_offers_a(m):
    risk=arm(m);p=party();before=deepcopy(p)
    r=m.battle_context(native_text("It's super",'effective!',arrow=False),state(),p)
    assert r['available_actions']==['wait'] and r['battle_tactic']=='wait_source_fixed_damage_prompt_arrow'
    assert risk['unreadable_waits']==0 and risk['native_prompt_blink_waits']==1 and p==before
    r=m.battle_context(native_text("It's super",'effective!'),state(),p)
    assert r['available_actions']==['a','wait'] and risk['native_prompt_blink_waits']==0
    assert risk['native_prompt_history'][0]['unreadable_waits_before']==31

@pytest.mark.parametrize('fault',['partial','unknown','wrong_position','extra_s','wrong_enemy','read','alignment','error','lines','cursor'])
def test_unknown_or_partial_source_keeps_original_bounded_guard_and_never_a(m,fault):
    risk=arm(m);text=native_text("It's super",'effective!')
    if fault=='partial':text=native_text("It's su",'')
    elif fault=='unknown':text=native_text("It's super",'unexpected!')
    elif fault=='wrong_position':text['cells'][14][3]='s';text['cells'][14][4]="'s"
    elif fault=='extra_s':text['cells'][8][0]="'s"
    elif fault=='wrong_enemy':text=native_text("It's super",'effective!',enemy='PIDGEOT')
    elif fault=='read':text['read_valid']=False
    elif fault=='alignment':text['alignment_verified']=False
    elif fault=='error':text['read_error']='unknown'
    elif fault=='lines':text['lines'].append('forged')
    elif fault=='cursor':text['cells'][13][9]='▶'
    r=m.battle_context(text,state(),party())
    assert r['available_actions']==['wait'] and r['review_reason']=='fixed_damage_visible_wait_exhausted'
    assert m._fixed_damage_risk is risk and risk['unreadable_waits']==32 and risk['damage']==40

@pytest.mark.parametrize('fault',['zero_visible_hp','faint_party','missing_frame','wrong_frame','invalid_hp','invalid_party'])
def test_native_prompt_never_bypasses_zero_hp_unknown_party_or_frame(m,fault):
    arm(m);text=native_text("It's super",'effective!');p=party();bs=state()
    if fault=='zero_visible_hp':text=native_text("It's super",'effective!',hp=0)
    elif fault=='faint_party':p[1]['hp']=0
    elif fault=='missing_frame':bs.pop('observation_frame')
    elif fault=='wrong_frame':text['observation_frame']=14160
    elif fault=='invalid_hp':text['cells'][10][12]='X'
    elif fault=='invalid_party':p[0]['pp']=None
    r=m.battle_context(text,bs,p)
    assert r['phase']=='strategy_review' and r['available_actions']==['wait']

def test_blink_still_has_own_bound_and_does_not_clear_threat(m):
    risk=arm(m);t=native_text("It's super",'effective!',arrow=False)
    for _ in range(30):assert m.battle_context(t,state(),party())['available_actions']==['wait']
    r=m.battle_context(t,state(),party())
    assert r['review_reason']=='fixed_damage_native_prompt_blink_wait_exhausted'
    assert m._fixed_damage_risk is risk and risk['damage']==40

def test_real_valid_page_resets_only_consecutive_counter_not_risk_or_history(m):
    risk=arm(m);m.battle_context(native_text("It's super",'effective!'),state(),party())
    hist=risk['native_prompt_history'];m._test_spec.loader.exec_module(m)
    assert m._fixed_damage_risk is risk and risk['native_prompt_history'] is hist
    assert risk['native_prompt_history'][0]['unreadable_waits_before']==31 and risk['damage']==40

def test_later_real_command_retains_fixed40_switch_threshold_after_prompt_ack_hint(m):
    risk=arm(m);m.battle_context(native_text("It's super",'effective!'),state(),party())
    p=party();p[0]['hp']=40
    def command_cells(cells):
        for x,y,label in ((10,14,'FIGHT'),(10,16,'ITEM'),(16,16,'RUN')):
            cells[y][x:x+len(label)]=list(label)
        cells[14][9]='▶'
    t=native_text('','',arrow=False,hp=40,extra=command_cells)
    r=m.battle_context(t,state(),p)
    assert r['battle_tactic']=='switch_observed_fixed_damage'
    assert r['fixed_damage_hp_threshold']==57 and m._fixed_damage_risk is risk and risk['damage']==40
    assert risk['native_prompt_history'][0]['unreadable_waits_before']==31

@pytest.mark.parametrize('kind,raw,active',[('lost_transition',255,False),('wild',1,True),('none',0,False)])
def test_loss_wild_and_outside_battle_keep_original_gates(m,kind,raw,active):
    arm(m);bs=state();bs.update(kind=kind,raw=raw,active=active)
    r=m.battle_context(native_text("It's super",'effective!'),bs,party())
    assert m._fixed_damage_risk is None
    assert r is None or r.get('battle_tactic')!='dismiss_source_fixed_damage_native_prompt'
