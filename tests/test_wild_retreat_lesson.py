"""Real strategy/controller, synthetic source-position UI; no game or input."""
from copy import deepcopy
import importlib
from pathlib import Path
import re

import pytest
from laya_pokemon.team_strategy import species_key

formal_battle=importlib.import_module('laya_pokemon.battle')
FORMAL_SOURCE=Path(formal_battle.__file__).resolve()
assert FORMAL_SOURCE.parent.name=='laya_pokemon' and FORMAL_SOURCE.parent.parent.name=='src'
assert FORMAL_SOURCE==(FORMAL_SOURCE.parent.parent.parent/'src/laya_pokemon/battle.py').resolve()


@pytest.fixture
def b(monkeypatch):
    module=importlib.import_module('laya_pokemon.battle')
    assert module is formal_battle and Path(module.__file__).resolve()==FORMAL_SOURCE
    for name in ('_no_pp_switch','_fixed_damage_risk','_wild_retreat_lesson','_wild_retreat_switch'):
        monkeypatch.setattr(module,name,None)
    return module


def party():
    values=[(7,37,62,125,64,[61,57,30,40],[20,3,25,35]),
            (132,42,203,203,0,[70,133,156,34],[13,20,10,13]),
            (102,35,90,90,0,[33,28,98,39],[35,15,30,30]),
            (154,35,111,111,0,[75,15,73,22],[25,30,10,10]),
            (35,37,114,114,0,[64,65,19,31],[35,20,15,20]),
            (19,43,177,177,0,[57,34,58,109],[0,12,8,10])]
    return [dict(species=s,species_name=species_key(s),level=lv,hp=hp,max_hp=mh,status=st,
                 exp=lv**3,moves=moves,pp=pp) for s,lv,hp,mh,st,moves,pp in values]


def put(cells,x,y,value):
    assert x+len(value)<=20
    cells[y][x:x+len(value)]=list(value)


def packet(b,mons,frame=100,*,enemy='VENOMOTH',active=0,command=False,lines=(),cursor=(9,14),
           native_s=False,native_t=False,arrow=False):
    cells=[[' ']*20 for _ in range(18)]
    mon=mons[active]
    put(cells,1,0,enemy);put(cells,5,1,'40')
    put(cells,10,7,species_key(mon['species']))
    status='PAR' if mon['status']==64 else 'SLP' if 0<mon['status']<8 else {0:'',8:'PSN',16:'BRN',32:'FRZ'}[mon['status']]
    put(cells,14,8,status or str(mon['level']))
    put(cells,11,10,f"{mon['hp']:3}/{mon['max_hp']:3}")
    if command:
        for x,y,label in ((10,14,'FIGHT'),(10,16,'ITEM'),(16,16,'RUN')):put(cells,x,y,label)
        cells[cursor[1]][cursor[0]]='▶'
    for y,line in zip((14,16),lines):put(cells,1,y,line)
    if native_s:
        # The source decoder treats apostrophe-s as one physical text tile.
        assert ''.join(cells[14]).strip()=="It's super"
        cells[14]=[' ']*20
        for x,token in enumerate(('I','t',"'s",' ','s','u','p','e','r'),1):cells[14][x]=token
    if native_t:
        cells[14]=[' ']*20
        for x,token in enumerate(('C','a','n',"'t",' ','e','s','c','a','p','e','!'),1):cells[14][x]=token
    if arrow:cells[16][18]='▼'
    return from_cells(b,cells,frame)


def from_cells(b,cells,frame):
    raw=[''.join(row) for row in cells]
    selected=[(i,row.rstrip()) for i,row in enumerate(raw) if re.search(r'[A-Za-z0-9]{2,}',row)][:12]
    return dict(profile=b._VISIBLE_PROFILE,read_valid=True,alignment_verified=True,read_error=None,
        window_visible=True,cells=cells,lines=[line for _,line in selected],line_rows=[i for i,_ in selected],
        observation_frame=frame)


def battle(frame=100,*,enemy='VENOMOTH',kind='wild',active=True):
    return dict(raw=1 if kind=='wild' else 2 if kind=='trainer' else 0,active=active,kind=kind,
        opponent_species=enemy,wild_opponent_species=enemy if kind=='wild' else None,
        observation_frame=frame,player_disabled_move=dict(valid=True,state='clear',raw=0))


def call(b,mons,frame=100,*,text=None,state=None,**kwargs):
    if text is None:text=packet(b,mons,frame,**kwargs)
    if state is None:state=battle(frame)
    before=deepcopy((text,state,mons))
    result=b.battle_context(text,state,mons,[])
    assert before==(text,state,mons)
    return result


def observe(b,mons,*,impairment='par',native_s=False):
    mons[0]['hp']=125
    mons[0]['status']=64 if impairment=='par' else 0
    call(b,mons,100,lines=('Enemy VENOMOTH','used PSYBEAM!'))
    mons[0]['hp']=78
    call(b,mons,140,lines=("It's super",'effective!'),native_s=native_s,arrow=True)
    if impairment=='confusion':
        call(b,mons,180,lines=('NIDOKING became','confused!'))
    if impairment=='failed_run':
        call(b,mons,180,lines=("Can't escape!",))
    mons[0]['hp']=62


def switched(result):
    assert result.get('battle_tactic')=='switch_observed_wild_danger',result
    assert result.get('party_target_species')==35,result
    assert result.get('battle_target_tile')==[16,14],result


def not_switch(result):
    assert result.get('battle_tactic')!='switch_observed_wild_danger',result


@pytest.mark.parametrize('impairment',['par','confusion','failed_run'])
def test_observed_super_effective_impairment_prefers_healthy_advantage_support(b,impairment):
    mons=party();observe(b,mons,impairment=impairment)
    switched(call(b,mons,220,command=True))


def test_native_apostrophe_s_source_page_proves_same_enemy_danger(b):
    mons=party();observe(b,mons,native_s=True)
    switched(call(b,mons,220,command=True))


def test_impaired_observed_danger_can_switch_before_hp_crosses_retreat_threshold(b):
    mons=party();observe(b,mons);mons[0]['hp']=78
    switched(call(b,mons,220,command=True))


def test_same_frame_conflicting_used_and_effect_pages_cannot_create_danger(b):
    mons=party();mons[0]['hp']=125
    call(b,mons,100,lines=('Enemy VENOMOTH','used PSYBEAM!'))
    mons[0]['hp']=78
    call(b,mons,100,lines=("It's super",'effective!'))
    mons[0]['hp']=62
    not_switch(call(b,mons,220,command=True))


@pytest.mark.parametrize('evidence',['none','super_without_used','player_used','wrong_enemy','unknown_move','incomplete_super'])
def test_missing_or_misattributed_enemy_evidence_does_not_disable_normal_retreat(b,evidence):
    mons=party()
    used={'player_used':('NIDOKING used','BUBBLEBEAM!'),
          'wrong_enemy':('Enemy GOLBAT','used PSYBEAM!'),
          'unknown_move':('Enemy VENOMOTH','used UNKNOWN!')}
    if evidence in used:call(b,mons,100,lines=used[evidence])
    elif evidence=='incomplete_super':call(b,mons,100,lines=('Enemy VENOMOTH','used PSYBEAM!'))
    if evidence!='none':call(b,mons,140,lines=("It's super",'effective!' if evidence!='incomplete_super' else ''))
    out=call(b,mons,220,command=True)
    assert out.get('battle_tactic')=='retreat' and out.get('battle_target_tile')==[16,16],out


def test_no_impairment_still_retreats_normally_even_after_observed_super_effective(b):
    mons=party();observe(b,mons,impairment='none')
    out=call(b,mons,220,command=True)
    assert out.get('battle_tactic')=='retreat',out


@pytest.mark.parametrize('bad',['status','faint','half_hp','zero_pp','no_advantage','unknown_pp'])
def test_unsafe_or_unverified_bench_never_selected(b,bad):
    mons=party();observe(b,mons)
    target=mons[4]
    if bad=='status':target['status']=64
    if bad=='faint':target['hp']=0
    if bad=='half_hp':target['hp']=target['max_hp']//2
    if bad=='zero_pp':target['pp']=[0]*4
    if bad=='no_advantage':target['moves']=[33,34,39,40];target['pp']=[35,15,30,35]
    if bad=='unknown_pp':target['pp'][0]=True
    not_switch(call(b,mons,220,command=True))


@pytest.mark.parametrize('bad',['read_invalid','alignment','frame','hud_hp','hud_status','enemy','extra_cursor','pollution'])
def test_new_switch_requires_complete_current_verified_command(b,bad):
    mons=party();observe(b,mons);text=packet(b,mons,220,command=True)
    if bad=='read_invalid':text['read_valid']=False
    if bad=='alignment':text['alignment_verified']=False
    if bad=='frame':text['observation_frame']=219
    if bad in ('hud_hp','hud_status','enemy','extra_cursor','pollution'):
        cells=deepcopy(text['cells'])
        if bad=='hud_hp':cells[10][13]='1'
        if bad=='hud_status':cells[8][14]='P';cells[8][15]='S';cells[8][16]='N'
        if bad=='enemy':cells[0]=[' ']*20;put(cells,1,0,'GOLBAT')
        if bad=='extra_cursor':cells[16][15]='▶'
        if bad=='pollution':cells[12][0]='X'
        text=from_cells(b,cells,220)
    out=call(b,mons,220,text=text)
    not_switch(out)
    assert b._wild_retreat_switch is None,out


def test_exact_normal_party_and_switch_pages_complete_target_handoff(b):
    mons=party();observe(b,mons);switched(call(b,mons,220,command=True))
    # The first offered PKMN direction has to reach its actual cursor first.
    out=call(b,mons,260,command=True,cursor=(15,14))
    assert 'a' in out['available_actions'],out
    for index in range(5):
        rows=b._trainer_half_party_view(mons,index)
        out=call(b,mons,300+index*40,text=from_cells(b,[list(row) for row in rows],300+index*40))
        assert out.get('party_target_species',35)==35,out
    assert 'a' in out['available_actions'],out
    rows=b._trainer_half_party_view(mons,4,True)
    out=call(b,mons,540,text=from_cells(b,[list(row) for row in rows],540))
    assert 'a' in out['available_actions'],out
    out=call(b,mons,580,active=4,lines=('Go! FEAROW!',))
    assert b._wild_retreat_switch is None,out


@pytest.mark.parametrize('bad',['unknown_dialogue','polluted_party','polluted_submenu','order_changed','target_status'])
def test_pending_unknown_or_changed_party_never_confirms(b,bad):
    mons=party();observe(b,mons);switched(call(b,mons,220,command=True))
    call(b,mons,260,command=True,cursor=(15,14))
    if bad=='unknown_dialogue':text=packet(b,mons,300,lines=('Unknown message!',))
    else:
        if bad=='order_changed':mons[1],mons[2]=mons[2],mons[1]
        if bad=='target_status':mons[4]['status']=8
        rows=b._trainer_half_party_view(mons,4,bad=='polluted_submenu')
        cells=[list(row) for row in rows]
        if bad in ('polluted_party','polluted_submenu'):cells[17][0]='X'
        text=from_cells(b,cells,300)
    out=call(b,mons,300,text=text)
    assert 'a' not in out.get('available_actions',[]),out
    assert out.get('phase') in ('strategy_review','battle_animation','campaign_review'),out


@pytest.mark.parametrize('change',['status','hp','pp'])
def test_pending_command_rechecks_target_before_confirming_pkmn(b,change):
    mons=party();observe(b,mons);switched(call(b,mons,220,command=True))
    if change=='status':mons[4]['status']=8
    if change=='hp':mons[4]['hp']=1
    if change=='pp':mons[4]['pp']=[0]*4
    out=call(b,mons,260,command=True,cursor=(15,14))
    assert 'a' not in out.get('available_actions',[]),out
    assert out.get('phase') in ('strategy_review','battle_animation','campaign_review'),out


def test_risk_and_pending_survive_source_reload_without_reconstruction(b):
    mons=party();observe(b,mons);risk=b._wild_retreat_lesson
    importlib.reload(b)
    assert b._wild_retreat_lesson is risk
    switched(call(b,mons,220,command=True));pending=b._wild_retreat_switch
    importlib.reload(b)
    assert b._wild_retreat_switch is pending
    out=call(b,mons,260,command=True,cursor=(15,14))
    assert out.get('battle_target_tile')==[16,14],out


@pytest.mark.parametrize('reset',['inactive','enemy_changed','active_changed'])
def test_wild_evidence_does_not_leak_into_new_enemy_or_active(b,reset):
    mons=party();observe(b,mons)
    if reset=='inactive':
        call(b,mons,180,state=battle(180,kind='none',active=False))
        out=call(b,mons,220,command=True)
    elif reset=='enemy_changed':
        out=call(b,mons,220,enemy='GOLBAT',command=True,state=battle(220,enemy='GOLBAT'))
    else:
        out=call(b,mons,220,active=4,command=True)
    not_switch(out)


def test_invalid_disable_signal_retains_existing_review_precedence(b):
    mons=party();observe(b,mons);state=battle(220)
    state['player_disabled_move']={'valid':False,'state':'unknown'}
    out=call(b,mons,220,command=True,state=state)
    assert out.get('review_reason')=='player_disabled_move_signal_not_verified',out
    assert b._wild_retreat_switch is None


def test_no_pp_retains_existing_support_switch_precedence(b):
    mons=party();observe(b,mons);mons[0]['pp']=[0]*4
    out=call(b,mons,220,command=True)
    assert out.get('battle_tactic')=='switch_no_attack_pp',out


def test_trainer_half_profile_and_fixed40_protection_do_not_use_wild_policy(b):
    mons=party();observe(b,mons)
    state=battle(220,kind='trainer');state['trainer_half_hp_profile']=b.TRAINER_HALF_HP_PROFILE
    out=call(b,mons,220,command=True,state=state)
    assert out.get('battle_tactic')!='switch_observed_wild_danger',out
    mons[0]['hp']=45;mons[0]['status']=0
    call(b,mons,260,lines=('Enemy VENOMOTH','used DRAGON RAGE!'),state=battle(260,kind='trainer'))
    out=call(b,mons,300,command=True,state=battle(300,kind='trainer'))
    assert out.get('battle_tactic')=='switch_observed_fixed_damage',out


def test_native_apostrophe_t_failed_escape_is_accepted_only_as_complete_literal(b):
    mons=party();observe(b,mons,impairment='none')
    out=call(b,mons,200,lines=("Can't escape!",),native_t=True)
    assert b._wild_retreat_lesson['escape_failed'] is True
    switched(call(b,mons,240,command=True))


def test_pending_same_frame_repeat_waits_and_conflict_remains_sticky(b):
    mons=party();observe(b,mons);text=packet(b,mons,220,command=True)
    switched(call(b,mons,220,text=text))
    out=call(b,mons,220,text=text)
    assert out['available_actions']==['wait']
    text=deepcopy(text);text['cells'][14][9]=' ';text['cells'][14][15]='▶'
    text=from_cells(b,text['cells'],220)
    out=call(b,mons,220,text=text)
    assert out['phase']=='strategy_review' and out['available_actions']==['wait']
    out=call(b,mons,260,command=True)
    assert out['review_reason']=='wild_retreat_pending_same_frame_conflict'


@pytest.mark.parametrize('budget',['calls','frames','waits'])
def test_pending_budgets_do_not_refund_or_create_a_switch_ack(b,budget):
    mons=party();observe(b,mons);switched(call(b,mons,220,command=True))
    record=b._wild_retreat_switch
    if budget=='calls':record['calls']=120
    if budget=='waits':record['waits']=25
    frame=3821 if budget=='frames' else 260
    cells=[list(r) for r in b._trainer_half_party_view(mons,0,inactive=True)]
    out=call(b,mons,frame,text=from_cells(b,cells,frame))
    assert out['phase']=='strategy_review' and out['available_actions']==['wait']
    assert record['switch_requested'] is False


def test_active_fixed40_risk_precedes_existing_wild_lesson_before_any_pending_owner(b,monkeypatch):
    mons=party();observe(b,mons);mons[0]['hp']=40
    # Existing fixed40 observation currently establishes trainer-only evidence.
    # Hold its already-valid risk across this observer call to test the precise
    # simultaneous-policy invariant, without manufacturing an existing switch.
    b._fixed_damage_risk=dict(enemy_species='VENOMOTH',move='DRAGON_RAGE',move_id=82,
        damage=40,source_commit=b.FIXED_DAMAGE_SOURCE_COMMIT,unreadable_waits=0)
    assert b._no_pp_switch is None and b._wild_retreat_switch is None
    monkeypatch.setattr(b,'_observe_fixed_damage',lambda text,state:False)
    out=call(b,mons,220,command=True)
    assert out['battle_tactic']=='switch_observed_fixed_damage',out
    assert b._wild_retreat_switch is None
    assert b._no_pp_switch['reason']=='observed_dragon_rage_risk'

