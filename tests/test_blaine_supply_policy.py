"""True frozen pure helpers/readers; synthesized snapshots/UI, no game/model I/O."""
from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import laya_pokemon
from laya_pokemon.player_battle import decode_player_battle
from laya_pokemon.wild_opponent import decode_enemy_mon
from laya_pokemon.observation import read_visible_text
import pytest


ROOT=Path(laya_pokemon.__file__).resolve().parents[2]
STAGE=ROOT/'.local/staged-blaine-supply-policy-20261025'


def source_for_test(path):
    p=Path(path).resolve()
    if p==STAGE/'test_blaine_supply_policy.py':return STAGE/'blaine_supply_policy.py'
    if p==ROOT/'tests/test_blaine_supply_policy.py':return ROOT/'src/laya_pokemon/blaine_supply_policy.py'
    raise RuntimeError('Only exact staged or formal test locations are supported')


def pure_for_test(path):
    p=Path(path).resolve()
    if p==STAGE/'test_blaine_supply_policy.py':
        return ROOT/'.local/staged-medicine-final-20261025/battle_medicine.py'
    if p==ROOT/'tests/test_blaine_supply_policy.py':return ROOT/'src/laya_pokemon/battle_medicine.py'
    raise RuntimeError('Only exact staged or formal pure dependency is supported')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


bm=load('medicine_frozen_policy_dependency',pure_for_test(__file__))
prior=getattr(laya_pokemon,'battle_medicine',None)
try:
    laya_pokemon.battle_medicine=bm
    policy=load('blaine_supply_policy_stage',source_for_test(__file__))
finally:
    if prior is None:del laya_pokemon.battle_medicine
    else:laya_pokemon.battle_medicine=prior

FRAME=1735000
LOC={'map_id':166,'x':3,'y':4}


def record(species,hp,status=0,level=38,maxhp=156):
    r=[species,0,hp,0,status,21,25,75,57,34,58,109,152,136,level,0,maxhp,
       0,90,0,90,0,90,0,88,15,15,10,10]
    if species!=19:r[5:7]=[20,20];r[8:12]=[46,52,126,36];r[25:29]=[20,25,5,20]
    return r


def native_text(rows):
    # Run the real current decoder against a synthetic tilemap; no handmade
    # lines/line_rows normalization can conceal a native schema mismatch.
    cells=[list(row) for row in rows]
    chars=sorted({c for row in cells for c in row});encoding={c:i for i,c in enumerate(chars)}
    class Tiles:
        def __getitem__(self,xy):
            x,y=xy;return encoding[cells[y][x]]
    game=SimpleNamespace(memory={0xFF40:0x91},screen=SimpleNamespace(
        tilemap_position_list=[(0,0,0,144)]*144),tilemap_background=Tiles())
    result=read_visible_text(game,{i:c for c,i in encoding.items()})
    assert result['read_valid'] is True
    return result


def inputs(hp=150,status=0,enemy_species=20):
    player=decode_player_battle(record(19,hp,status))['player']
    raw=record(enemy_species,149,level=47,maxhp=149)
    enemy=decode_enemy_mon(raw)['enemy']
    ps=dict(profile=bm.PLAYER_PROFILE,source_commit=bm.SOURCE_COMMIT,read_valid=True,
        observation_frame=FRAME,battle_kind='trainer',location=deepcopy(LOC),active_party_index=2,
        player=player)
    es=dict(profile=bm.ENEMY_PROFILE,source_commit=bm.SOURCE_COMMIT,read_valid=True,
        observation_frame=FRAME,frame_before=FRAME,frame_after=FRAME,battle_kind='trainer',
        raw=2,battle_type=0,current_opponent=247,location=deepcopy(LOC),raw_record=raw,enemy=enemy)
    roster=[(132,'SNORLAX'),(7,'NIDOKING'),(19,'LAPRAS'),(102,'EEVEE'),(154,'VENUSAUR'),(35,'FEAROW')]
    party=[dict(species=s,species_name=n,level=38 if s==19 else 41,hp=hp if s==19 else 180,
        max_hp=156 if s==19 else 180,status=status if s==19 else 0,exp=60000,
        moves=[57,34,58,109] if s==19 else [33,0,0,0],
        pp=[15,15,10,10] if s==19 else [35,0,0,0]) for s,n in roster]
    progress=dict(profile='gen1-wrapper-ram-progress-v1-unvalidated',initialization_candidate=True,
        party_read_valid=True,party_count=6,party=party,money=48332,
        inventory=[dict(item=18,quantity=20),dict(item=52,quantity=10)])
    return dict(text=native_text(bm._command_view(player,enemy,(9,16))),progress=progress,
                player_snapshot=ps,enemy_proof=es,frame=FRAME)


def call(kw):
    original=deepcopy(kw);result=policy.decide(**kw)
    assert kw==original
    assert result['action'] in ('none','medicine','review')
    assert isinstance(result['risks'],list) and result['survival_approved'] is False
    assert not any(k in result for k in ('available_actions','phase','field_move_complete','battle_medicine_complete'))
    return result


@pytest.mark.parametrize('hp,status,item',[(1,0,18),(141,0,18),(150,0,18),
    (151,0,None),(156,0,None),(1,16,18),(141,16,18),(142,16,52),(150,16,52),(151,16,52),(156,16,52)])
def test_exact_parent_thresholds_only(hp,status,item):
    r=call(inputs(hp,status))
    assert r['action']==('medicine' if item else 'none')
    if item:assert r['intent']['item']==item and r['intent']['quantity']==1
    else:assert 'intent' not in r
    assert (policy.FULL_HEAL_RISK in r['risks'])==(status==16 and 142<=hp<=150)


@pytest.mark.parametrize('cursor',[(9,14),(15,14),(9,16),(15,16)])
def test_reuses_true_complete_command_view_at_all_four_cursors(cursor):
    kw=inputs();kw['text']=native_text(bm._command_view(kw['player_snapshot']['player'],
        kw['enemy_proof']['enemy'],cursor))
    assert call(kw)['action']=='medicine'


@pytest.mark.parametrize('ui',['partial','dialog','blank','extra_arrow'])
def test_partial_or_dialog_never_proposes_medicine(ui):
    kw=inputs();player=kw['player_snapshot']['player'];enemy=kw['enemy_proof']['enemy']
    if ui=='dialog':rows=bm._dialog(player,enemy,'ENEMY ARCANINE','USED FIRE BLAST!')
    elif ui=='blank':rows=tuple(' '*20 for _ in range(18))
    else:
        rows=[list(r) for r in bm._command_view(player,enemy,(9,16))]
        rows[14][10]=' ' if ui=='partial' else rows[14][10]
        if ui=='extra_arrow':rows[13][1]='▶'
        rows=tuple(''.join(r) for r in rows)
    kw['text']=native_text(rows)
    assert call(kw)['action']=='none'


@pytest.mark.parametrize('field',['read_valid','profile','source_commit','observation_frame','frame_before','raw','battle_type'])
def test_enemy_false_unknown_or_stale_proof_reviews(field):
    kw=inputs();kw['enemy_proof'][field]=False if field not in ('profile','source_commit') else 'unknown'
    assert call(kw)['action']=='review'


@pytest.mark.parametrize('field',['read_valid','profile','source_commit','observation_frame','active_party_index'])
def test_player_false_unknown_or_stale_proof_reviews(field):
    kw=inputs();kw['player_snapshot'][field]=False if field not in ('profile','source_commit') else 'unknown'
    assert call(kw)['action']=='review'


@pytest.mark.parametrize('bad',['moves','max_hp','special','money','status','surf_pp','duplicate_active','active_index',
                              'missing_item','bad_quantity','inventory_unknown','party_unsync','text_profile'])
def test_bounded_contract_failures_review(bad):
    kw=inputs();p=kw['player_snapshot']['player'];progress=kw['progress']
    if bad=='moves':p['moves'][0]=33
    elif bad in ('max_hp','special'):p[bad]-=1
    elif bad=='money':progress['money']=False
    elif bad=='status':p['status']=32;progress['party'][2]['status']=32
    elif bad=='surf_pp':p['pp'][0]=0;p['pp_remaining'][0]=0;progress['party'][2]['pp'][0]=0
    elif bad=='duplicate_active':progress['party'][0]=deepcopy(progress['party'][2])
    elif bad=='active_index':kw['player_snapshot']['active_party_index']=0
    elif bad=='missing_item':progress['inventory']=[dict(item=52,quantity=10)]
    elif bad=='bad_quantity':progress['inventory'][0]['quantity']=False
    elif bad=='inventory_unknown':progress['inventory']=None
    elif bad=='party_unsync':progress['party'][2]['hp']-=1
    else:kw['text']['profile']='unknown'
    if bad in ('status','max_hp','special','surf_pp'):
        kw['text']=native_text(bm._command_view(p,kw['enemy_proof']['enemy'],(9,16)))
    assert call(kw)['action']=='review'


@pytest.mark.parametrize('packet',['text','progress'])
@pytest.mark.parametrize('value',[False,1734999])
def test_optional_native_frame_annotations_must_agree(packet,value):
    kw=inputs();kw[packet]['observation_frame']=value
    assert call(kw)['action']=='review'


def test_native_text_progress_without_nonexistent_frame_fields_are_accepted():
    kw=inputs();assert 'observation_frame' not in kw['text'] and 'observation_frame' not in kw['progress']
    assert call(kw)['action']=='medicine'


def test_non_arcanine_does_not_extend_policy_or_override_existing_guards():
    kw=inputs(enemy_species=83);kw['player_snapshot']=None;kw['progress']=None;kw['text']=None
    assert call(kw)['action']=='none'


def test_zero_hp_preserves_existing_loss_guard_without_intent():
    kw=inputs();kw['player_snapshot']['player']['hp']=0;kw['progress']['party'][2]['hp']=0
    assert call(kw)['action']=='none'


def test_only_one_surf_pp_is_required_and_returned_intent_is_independent():
    kw=inputs();p=kw['player_snapshot']['player'];p['pp']=[1,0,0,0];p['pp_remaining']=[1,0,0,0]
    kw['progress']['party'][2]['pp']=[1,0,0,0]
    r=call(kw);assert r['action']=='medicine';r['intent']['item']=1
    assert bm.HYPER_POTION_INTENT['item']==18 and call(kw)['intent']['item']==18


def test_exact_source_resolution_has_no_exists_fallback():
    assert source_for_test(STAGE/'test_blaine_supply_policy.py')==STAGE/'blaine_supply_policy.py'
    assert source_for_test(ROOT/'tests/test_blaine_supply_policy.py')==ROOT/'src/laya_pokemon/blaine_supply_policy.py'
    with pytest.raises(RuntimeError):source_for_test(ROOT/'tests/copy/test_blaine_supply_policy.py')


@pytest.mark.parametrize('field',['location','level','frame_after'])
def test_fixed_enemy_location_level_and_all_frame_guards(field):
    kw=inputs();e=kw['enemy_proof']
    if field=='location':e['location']['x']=4
    elif field=='frame_after':e['frame_after']=FRAME+1
    else:
        e['raw_record'][14]=46;e['enemy']=decode_enemy_mon(e['raw_record'])['enemy']
        kw['text']=native_text(bm._command_view(kw['player_snapshot']['player'],e['enemy'],(9,16)))
    assert call(kw)['action']=='review'


@pytest.mark.parametrize('frame',[False,1735000.0,-1])
def test_false_or_non_integer_frame_is_never_proof(frame):
    kw=inputs();kw['frame']=frame
    assert call(kw)['action']=='review'


def test_full_heal_branch_without_full_heal_is_review():
    kw=inputs(142,16);kw['progress']['inventory']=[dict(item=18,quantity=20)]
    assert call(kw)['action']=='review'
