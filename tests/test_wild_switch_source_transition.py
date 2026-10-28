"""True strategy/menus + readonly source getter on a synthetic native; no ROM/input."""
from copy import deepcopy
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

b=importlib.import_module('laya_pokemon.battle')
h=importlib.import_module('test_wild_retreat_lesson')
ROOT=Path(__file__).resolve().parent.parent
assert Path(b.__file__).resolve()==(ROOT/'src/laya_pokemon/battle.py').resolve()
assert Path(h.__file__).resolve()==(ROOT/'tests/test_wild_retreat_lesson.py').resolve()


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for name in ('_no_pp_switch','_fixed_damage_risk','_wild_retreat_lesson','_wild_retreat_switch'):
        monkeypatch.setattr(b,name,None)


class Memory:
    def __init__(self,species=19,index=5):self.data={0xD057:1,0xD014:species,0xCC2F:index,0xCFE5:145};self.reads=[];self.hook=None
    def __getitem__(self,key):
        self.reads.append(key);value=self.data.get(key,0)
        return self.hook(key,value) if self.hook else value
    def __setitem__(self,*args):raise AssertionError('no native writes')


def native(frame=770673,**kw):return SimpleNamespace(frame_count=frame,memory=Memory(**kw))


def state(frame=770673,pb=None):
    signal=h.battle(frame,enemy='MAROWAK')
    signal['wild_switch_native']=b._read_wild_switch_native(pb or native(frame))
    return signal


def setup():
    mons=h.party();mons=[mons[i] for i in (0,1,3,4,2,5)]
    mons[0].update(hp=69,status=0);mons[5].update(level=44,hp=181,max_hp=181)
    out=h.call(b,mons,770185,command=True,enemy='MAROWAK',state=h.battle(770185,enemy='MAROWAK'))
    assert out['party_target_species']==19
    h.call(b,mons,770225,command=True,cursor=(15,14),enemy='MAROWAK',state=h.battle(770225,enemy='MAROWAK'))
    for i in range(6):
        frame=770265+40*i;rows=b._trainer_half_party_view(mons,i)
        h.call(b,mons,frame,text=h.from_cells(b,[list(r) for r in rows],frame),state=h.battle(frame,enemy='MAROWAK'))
    rows=b._trainer_half_party_view(mons,5,True)
    h.call(b,mons,770505,text=h.from_cells(b,[list(r) for r in rows],770505),state=h.battle(770505,enemy='MAROWAK'))
    h.call(b,mons,770545,lines=('NIDOKING good!',),enemy='MAROWAK',state=h.battle(770545,enemy='MAROWAK'))
    record=b._wild_retreat_switch
    assert record['calls']==10 and record['waits']==1 and record['last_frame']==770545
    return mons,record


def weak(mons,frame=770673,*,full=False,active=0):
    text=h.packet(b,mons,frame,enemy='MAROWAK',active=active)
    cells=text['cells']
    for y,value in [(14,"The enemy's weak!" if full else "The enemy's we"),(16,"Get'm! LAPRAS!" if full else '')]:
        x=1
        while value:
            token=next((v for v in ("'s","'m") if value.startswith(v)),value[0])
            cells[y][x]=token;x+=1;value=value[len(token):]
    return h.from_cells(b,cells,frame)


def failed_original():
    mons,record=setup();text=weak(mons);signal=state()
    # Reproduce exactly the prior decoder's early rejection, before counter/packet updates.
    b._wild_retreat_review('pending_observation_or_owner_changed')
    original=deepcopy(record);cap=dict(kind='reviewed_wild_switch770673_v1',game_id='game29',source_frame=770673,
        native_identity='original_training_batch_native_game29',switch_identity=id(record),original_error=record['error'],
        original_switch=original,original_switch_sha256=b._wild_switch_sha(original),party_sha256=b._wild_switch_sha(mons),
        text_sha256=b._wild_switch_sha({k:v for k,v in text.items() if k!='observation_frame'}),native_active_species=19,native_active_party_index=5,
        diagnostic_sha256='a'*64,source_evidence_sha256={'review':'b'*64})
    return mons,record,text,signal,cap


def test_readonly_native_getter_is_double_sampled_typed_and_exposed_only_for_requested_switch():
    pb=native();result=b._read_wild_switch_native(pb)
    assert result['read_valid'] and result['species']==19 and result['party_index']==5 and len(pb.memory.reads)==6
    pb.memory.data[0xCC2F]=True;assert not b._read_wild_switch_native(pb)['read_valid']
    pb=native();count=0
    def torn(key,value):
        nonlocal count
        if key==0xD014:count+=1;return 19 if count==1 else 7
        return value
    pb.memory.hook=torn;assert not b._read_wild_switch_native(pb)['read_valid']
    pb=native();assert 'wild_switch_native' not in b.read_battle_state(pb)
    setup();assert b.read_battle_state(pb)['wild_switch_native']['species']==19


def test_exact_native_contraction_prefix_waits_with_old_hud_then_full_target_hud_hands_off():
    mons,record=setup();out=h.call(b,mons,770673,text=weak(mons),state=state())
    assert out['available_actions']==['wait'] and out['battle_tactic']=='await_source_weak_enemy_sendout'
    assert b._wild_retreat_switch is record and record['calls']==11 and record['waits']==2
    out=h.call(b,mons,770801,text=weak(mons,770801,full=True),state=state(770801))
    assert out['available_actions']==['wait'] and b._wild_retreat_switch is record
    out=h.call(b,mons,770929,text=weak(mons,770929,full=True,active=5),state=state(770929))
    assert out['battle_tactic']=='verified_wild_switch_handoff' and b._wild_retreat_switch is None


def test_arbitrary_partial_pollution_wrong_native_or_wrong_index_still_review():
    for bad in ('unknown_partial','pollution','old_native','wrong_index'):
        b._wild_retreat_clear();mons,record=setup();text=weak(mons);signal=state()
        if bad=='unknown_partial':text=h.packet(b,mons,770673,enemy='MAROWAK',lines=("The enemy's wrong!",))
        if bad=='pollution':text['cells'][15][1]='X';text=h.from_cells(b,text['cells'],770673)
        if bad=='old_native':signal=state(pb=native(species=7,index=0))
        if bad=='wrong_index':signal=state(pb=native(index=0))
        out=h.call(b,mons,770673,text=text,state=signal)
        assert out['phase']=='strategy_review' and out['available_actions']==['wait'] and b._wild_retreat_switch is record


def test_changed_enemy_or_party_order_cannot_use_sendout_source_exception():
    for bad in ('enemy','party'):
        b._wild_retreat_clear();mons,record=setup();text=weak(mons);signal=state()
        if bad=='enemy':signal['opponent_species']=signal['wild_opponent_species']='GOLBAT'
        else:mons[1],mons[2]=mons[2],mons[1]
        out=h.call(b,mons,770673,text=text,state=signal)
        assert out['phase']=='strategy_review' and b._wild_retreat_switch is record


def test_named_review_preserves_original_record_packet_and_cost_then_requires_fresh_native_transition():
    mons,record,text,signal,cap=failed_original();packet=record['last_packet'];spent=(record['calls'],record['waits'],record['started_frame'],record['last_frame'])
    result=b.review_wild_switch770673(native(),text,signal,mons,cap,
        expected_capsule_sha256=b._wild_switch_sha(cap),original_pending=record)
    assert result['available_actions']==['wait'] and b._wild_retreat_switch is record and record['error'] is None
    assert record['last_packet'] is packet and (record['calls'],record['waits'],record['started_frame'],record['last_frame'])==spent
    assert record['reviewed_transition_history'][0]['old_error']=='pending_observation_or_owner_changed'
    out=h.call(b,mons,770801,text=weak(mons,770801,full=True,active=5),state=state(770801))
    assert out['battle_tactic']=='verified_wild_switch_handoff' and record['calls']==11


def test_bad_review_authority_or_reconstructed_pending_changes_nothing():
    mons,record,text,signal,cap=failed_original();before=deepcopy(record)
    assert b.review_wild_switch770673(native(),text,signal,mons,cap,
        expected_capsule_sha256='0'*64,original_pending=record) is None
    assert b.review_wild_switch770673(native(),text,signal,mons,cap,
        expected_capsule_sha256=b._wild_switch_sha(cap),original_pending=deepcopy(record)) is None
    assert record==before and record['error']=='pending_observation_or_owner_changed'


def test_same_frame_source_repeats_do_not_refund_or_count_as_another_transition():
    mons,record=setup();text=weak(mons);signal=state();h.call(b,mons,770673,text=text,state=signal)
    spent=(record['calls'],record['waits']);out=h.call(b,mons,770673,text=text,state=signal)
    assert out['available_actions']==['wait'] and (record['calls'],record['waits'])==spent and b._wild_retreat_switch is record


def test_existing_pending_calls_waits_and_frame_budgets_remain_enforced():
    for budget in ('calls','waits','frames'):
        b._wild_retreat_clear();mons,record=setup();frame=770673
        if budget=='calls':record['calls']=120
        if budget=='waits':record['waits']=25
        if budget=='frames':frame=774000
        out=h.call(b,mons,frame,text=weak(mons,frame),state=state(frame))
        assert out['phase']=='strategy_review' and out['available_actions']==['wait'] and b._wild_retreat_switch is record
