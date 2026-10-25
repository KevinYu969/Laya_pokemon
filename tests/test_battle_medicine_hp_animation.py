"""Exact source-schema fixtures, never imported from ignored game outputs."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import laya_pokemon
import pytest

ROOT=Path(laya_pokemon.__file__).resolve().parents[2]
STAGE=ROOT/'.local/staged-medicine-hp-animation-20261025'


def source_for_test(path):
    p=Path(path).resolve()
    if p==STAGE/'test_battle_medicine_hp_animation.py':return STAGE/'battle_medicine.py'
    if p==ROOT/'tests/test_battle_medicine_hp_animation.py':return ROOT/'src/laya_pokemon/battle_medicine.py'
    raise RuntimeError('Only exact staged or formal test locations are supported')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


bm=load('medicine_hp_animation_candidate',source_for_test(__file__))
fx=load('medicine_source_schema_fixture',ROOT/'tests/test_battle_medicine.py')
fx.bm=bm  # isolated fixture module; execute the real candidate controller


def selected(item=18):
    s=fx.Session(item);s.p['party'][2].update(hp=77,max_hp=156)
    s.player=s.player_now();s.before=deepcopy(s.p)
    s.select();s.effect()
    if item==18:s.p['party'][2]['hp']=156
    s.player=s.player_now()
    return s


def animation(s,hp=101):
    view=fx.party(s.p['party'],s.c.active,'▷')
    fx.at(view,13,2*s.c.active+1,f'{hp:3}/{s.p["party"][s.c.active]["max_hp"]:3}')
    return view


def args(s,*,fresh=False):
    kw=deepcopy(s.kw)
    keep=('text','progress','player_snapshot','enemy_proof','frame','owner')
    result={k:kw[k] for k in keep}
    if fresh:
        result['frame']+=40
        result['player_snapshot']['observation_frame']=result['frame']
        for k in ('observation_frame','frame_before','frame_after'):result['enemy_proof'][k]=result['frame']
    return result


def failed_snapshot():
    s=selected();r=s.call(animation(s))
    assert r['available_actions']==['wait'] and s.c.error is None
    # Model only the saved named error from the previously reviewed version.
    # Live failure and no-input calibration remain root-owned evidence.
    s.c.error='medicine_receipt_unknown'
    return s


def test_exact_animation_waits_without_reuse_then_done_receipt_settles54_frames():
    s=selected();inventory=deepcopy(s.p['inventory'])
    for hp in (77,101,126,149,156):
        r=s.call(animation(s,hp))
        assert r['phase']=='battle_medicine_wait' and r['available_actions']==['wait']
        assert r['battle_medicine_tactic']=='known_hyper_potion_hp_animation'
        assert s.c.stage=='receipt' and s.c.error is None and not s.c.complete
        assert s.p['inventory']==inventory and s.c.pending is None
    delta=s.c.healed[2]['hp']-s.c.baseline['party'][2]['hp']
    receipt=fx.party(s.p['party'],None,receipt=('heal',delta),arrow=False)
    assert s.call(receipt)['available_actions']==['wait']
    assert receipt[16][18]==' ' and s.c.receipt_full_frame==s.frame
    assert s.call(receipt,advance=53)['available_actions']==['wait']
    assert s.call(receipt,advance=1)['available_actions'][0]=='a'
    assert s.call(receipt)['available_actions']==['wait']
    assert s.p['inventory']==inventory and s.c.stage=='retaliation'
    assert source_for_test(__file__)==Path(bm.__file__).resolve()
    assert source_for_test(ROOT/'tests/test_battle_medicine_hp_animation.py')==ROOT/'src/laya_pokemon/battle_medicine.py'
    with pytest.raises(RuntimeError):source_for_test(ROOT/'tests/copy/test_battle_medicine_hp_animation.py')


def test_explicit_named_repair_changes_only_error_and_preserves_original_budget():
    s=failed_snapshot();kw=args(s)
    # Existing live instances predate the new settling fields. Repair must not
    # synthesize or initialize them as a side effect of clearing the error.
    del s.c.receipt_full_frame;del s.c.receipt_full_rows
    before=deepcopy(s.c.__dict__);inputs=deepcopy(kw)
    assert s.c.reviewed_hp_animation_repair(**kw) is True
    after=deepcopy(s.c.__dict__);after['error']=before['error']
    assert after==before and kw==inputs
    assert s.c.reviewed_hp_animation_repair(**kw) is False


def test_context_never_automatically_clears_the_saved_error():
    s=failed_snapshot();before=deepcopy(s.c.__dict__)
    r=s.c.context(**s.kw)
    assert r['phase']=='strategy_review' and r['available_actions']==['wait']
    assert s.c.__dict__==before


@pytest.mark.parametrize('bad',['other_error','stage','owner','frame','readproof','inventory','party'])
def test_repair_refuses_every_nonmatching_review_contract_without_mutation(bad):
    s=failed_snapshot();kw=args(s,fresh=True)
    if bad=='other_error':s.c.error='call_or_time_budget_exhausted'
    elif bad=='stage':s.c.stage='retaliation'
    elif bad=='owner':kw['owner']='foreign'
    elif bad=='frame':kw['frame']=s.c.last_frame-1
    elif bad=='readproof':kw['enemy_proof']['frame_after']=False
    elif bad=='inventory':next(i for i in kw['progress']['inventory'] if i['item']==18)['quantity']-=1
    elif bad=='party':kw['progress']['party'][0]['hp']-=1
    before=deepcopy(s.c.__dict__);inputs=deepcopy(kw)
    assert s.c.reviewed_hp_animation_repair(**kw) is False
    assert s.c.__dict__==before and kw==inputs


def test_animation_allows_only_integer_hp_range_and_exact_other_cells():
    s=failed_snapshot()
    for bad in ('below','above','leading_zero','other_name','extra_arrow','art_pollution','partial','wrongmax','wrongcursor'):
        kw=args(s,fresh=True);cells=deepcopy(kw['text']['cells'])
        if bad=='below':fx.at(cells,13,5,' 76')
        elif bad=='above':fx.at(cells,13,5,'157')
        elif bad=='leading_zero':fx.at(cells,13,5,'099')
        elif bad=='other_name':cells[0][3]='X'
        elif bad=='extra_arrow':cells[16][18]='▼'
        elif bad=='art_pollution':cells[5][1]='#'
        elif bad=='wrongmax':fx.at(cells,17,5,'155')
        elif bad=='wrongcursor':cells[5][0]='▶'
        else:cells[14][1]=' '
        kw['text']=fx.text(cells);before=deepcopy(s.c.__dict__)
        assert s.c.reviewed_hp_animation_repair(**kw) is False
        assert s.c.__dict__==before


@pytest.mark.parametrize('budget',['call','time'])
def test_animation_and_explicit_repair_do_not_reset_budgets(budget):
    s=failed_snapshot();assert s.c.reviewed_hp_animation_repair(**args(s))
    started,calls,waits=s.c.started,s.c.calls,s.c.waits
    if budget=='call':s.c.max_calls=calls
    r=s.call(animation(s,126),now=started+61 if budget=='time' else s.now+.1)
    assert r['review_reason']=='battle_medicine_call_or_time_budget_exhausted'
    assert s.c.started==started and s.c.calls==calls+1 and s.c.waits==waits


def test_full_heal_done_page_uses_same54_frames_and_requires_cleared_status():
    s=selected(52);receipt=fx.party(s.p['party'],None,receipt=('cure',0),arrow=False)
    assert s.call(receipt)['available_actions']==['wait']
    assert s.call(receipt,advance=53)['available_actions']==['wait']
    assert s.call(receipt,advance=1)['available_actions'][0]=='a'
    assert s.call(receipt)['available_actions']==['wait']
    bad=selected(52);bad.p['party'][2]['status']=16;bad.player=bad.player_now()
    assert bad.call(receipt)['phase']=='strategy_review'


def test_receipt_settle_restarts_after_partial_and_never_accepts_extra_arrow():
    s=selected();receipt=fx.party(s.p['party'],None,receipt=('heal',79),arrow=False)
    assert s.call(receipt)['available_actions']==['wait']
    partial=deepcopy(receipt);partial[16][1]=' '
    assert s.call(partial,advance=53)['available_actions']==['wait']
    assert s.c.receipt_full_frame is None
    assert s.call(receipt,advance=1)['available_actions']==['wait']
    assert s.call(receipt,advance=53)['available_actions']==['wait']
    assert s.call(receipt,advance=1)['available_actions'][0]=='a'
    bad=selected();receipt[16][18]='▼'
    assert bad.call(receipt)['phase']=='strategy_review'
