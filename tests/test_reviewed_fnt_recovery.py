"""已檢討Nido FNT的必要中心路線；來源真getter合成測試，不操作模擬器。"""
from copy import deepcopy
import importlib
import pytest
from laya_pokemon import league_recovery as r,campaign_safety

hs=importlib.import_module('test_victory_strength')
hb=importlib.import_module('test_victory_later_boulders')


def plan():
    steps=r.expected_steps()
    return dict(mode='league_campaign',training_job=r.JOB,lead_species=35,steps=steps,
        reviewed_fnt_recovery=dict(kind=r.KIND,source_frame=32809,source_location=dict(map_id=198,x=6,y=1),
            fainted_species=7,steps_sha256=r.digest(steps),review_sha256=r.SOURCE_REVIEW_SHA256,state_sha256=r.SOURCE_STATE_SHA256))


def progress():
    p=hs.progress();next(m for m in p['party'] if m['species']==7)['hp']=0
    return p


def state(p):
    return dict(frame=100,phase='unclassified',location=dict(map_id=198,x=6,y=1),progress=p,battle_state=dict(kind='none',active=False))


@pytest.mark.parametrize('i',range(19))
def test_every_move_heal_and_interact_retains_only_reviewed_bench(i):
    p=plan();g=progress();step=p['steps'][i]
    assert r.valid_plan(p) and r.admitted(p,step['id'],g)==(7,)
    assert campaign_safety.attrition_context(state(g),p,step['id']) is None
    assert r.allowance(p,step['id'],g)==((7,) if step['kind']=='interact' else ())


@pytest.mark.parametrize('i',range(19))
@pytest.mark.parametrize('fault',('second_fnt','status','invalid_capsule'))
def test_legacy_recovery_flag_never_bypasses_new_fnt_status_or_capsule(i,fault):
    p=plan();g=progress();step=p['steps'][i]
    if fault=='second_fnt':next(m for m in g['party'] if m['species']==35)['hp']=0
    if fault=='status':next(m for m in g['party'] if m['species']==35)['status']=64
    if fault=='invalid_capsule':p['reviewed_fnt_recovery']['review_sha256']='a'*64
    assert r.allowance(p,step['id'],g)==()
    out=campaign_safety.attrition_context(state(g),p,step['id'])
    assert out and out['phase']=='campaign_review'


@pytest.mark.parametrize('field,value',(('next_map',33),('terminal',False),('via',[[0,0]]),('recovery_route',False),('target',[1,1]),('id','changed')))
def test_recomputed_hash_cannot_change_source_bound_route(field,value):
    p=plan();p['steps'][6][field]=value;p['reviewed_fnt_recovery']['steps_sha256']=r.digest(p['steps'])
    assert not r.valid_plan(p)


@pytest.mark.parametrize('value',(None,[],False,0,'unknown'))
def test_unknown_plan_fails_closed(value):assert r.valid_plan(value) is False


@pytest.mark.parametrize('fault',('species_float','species_list','species_dict','count_float','badges_float','hp_bool','maxhp_float'))
def test_unknown_or_numeric_type_confusion_fails_closed(fault):
    p=plan();g=progress()
    if fault=='species_float':g['party'][0]['species']=19.0
    if fault=='species_list':g['party'][0]['species']=[]
    if fault=='species_dict':g['party'][0]['species']={}
    if fault=='count_float':g['party_count']=6.0
    if fault=='badges_float':g['badges_raw']=255.0
    if fault=='hp_bool':g['party'][0]['hp']=True
    if fault=='maxhp_float':g['party'][0]['max_hp']=180.0
    assert r.admitted(p,p['steps'][0]['id'],g)==()


@pytest.mark.parametrize('value',((7.0,),(True,),[7],(35,),(7,35),None))
def test_controller_permission_is_exact_typed_tuple(value):
    with pytest.raises(ValueError):hs.strength.VictoryStrengthController(reviewed_fainted_bench=value)
    with pytest.raises(ValueError):hb.b.VictoryLaterBoulderController('3f_hole',reviewed_fainted_bench=value)


def test_default_strength_still_rejects_fnt():
    s=hs.Session('2f_after_fall');s.p=progress()
    out=s.call(hs.canvas(),window=False,ready=True)
    assert out['phase']=='campaign_review'


def test_reviewed_strength_uses_alive_snorlax_and_actual_fnt_row(monkeypatch):
    s=hs.Session('2f_after_fall');s.p=progress()
    s.c=hs.strength.VictoryStrengthController(s.intent,reviewed_fainted_bench=(7,))
    original=hs.party
    def party(p,*args,**kwargs):
        rows=original(p,*args,**kwargs)
        for i,m in enumerate(p['party']):
            if m['hp']==0:hs.put(rows,17,2*i,'FNT')
        return rows
    monkeypatch.setattr(hs,'party',party)
    before=deepcopy(s.p);s.confirm();s.finish()
    assert s.p==before and s.p['party'][-1]['hp']==0
    assert s.c.baseline['party'][s.c.target_index]['species']==132


@pytest.mark.parametrize('case',('3f_hole','2f_switch2'))
@pytest.mark.parametrize('follow',(False,True))
def test_reviewed_boulder_preserves_dead_bench_and_real_geometry(case,follow):
    s=hb.Session(case);next(m for m in s.p['party'] if m['species']==7)['hp']=0
    s.c=hb.b.VictoryLaterBoulderController(case,reviewed_fainted_bench=(7,))
    before=deepcopy(s.p);s.finish(follow=follow)
    control=hb.Session(case);control.finish(follow=follow)
    assert s.p==before and s.trace==control.trace and s.player==control.player and s.stone==control.stone


@pytest.mark.parametrize('case',('3f_hole','2f_switch2'))
def test_default_boulder_still_rejects_same_fnt(case):
    s=hb.Session(case);next(m for m in s.p['party'] if m['species']==7)['hp']=0
    assert s.call()['phase']=='campaign_review'


def test_only_true_full_nurse_recovery_allows_tail():
    p=plan();s=state(progress());s['location']=dict(map_id=174,x=7,y=7)
    for m in s['progress']['party']:m['hp']=m['max_hp']
    assert r.healed_terminal(p,p['steps'][16]['id'],s,full_party_healed=True)
    assert not r.healed_terminal(p,p['steps'][0]['id'],s,full_party_healed=True)
    assert not r.healed_terminal(p,p['steps'][16]['id'],s,full_party_healed=False)
    s['location']['x']=7.0
    assert not r.healed_terminal(p,p['steps'][16]['id'],s,full_party_healed=True)


@pytest.mark.parametrize('fault',('species','count','name','badges','status_missing','status_bool','read_valid','pp_missing'))
def test_healed_terminal_never_hides_invalid_identity_or_unknown_pp(fault):
    from laya_pokemon.team_strategy import reference,move_key
    p=plan();s=state(hs.progress());s['location']=dict(map_id=174,x=7,y=7)
    for m in s['progress']['party']:
        m['hp']=m['max_hp'];m['pp']=[reference()['moves'][move_key(move)]['pp'] if move else 0 for move in m['moves']]
    g=s['progress']
    if fault=='species':g['party'][0]['species']=999
    if fault=='count':g['party_count']=5
    if fault=='name':g['player_name_raw']='OTHER'
    if fault=='badges':g['badges_raw']=254
    if fault=='status_missing':g['party'][0].pop('status')
    if fault=='status_bool':g['party'][0]['status']=False
    if fault=='read_valid':g['party_read_valid']=False
    if fault=='pp_missing':g['party'][0].pop('pp')
    out=campaign_safety.attrition_context(s,p,p['steps'][16]['id'])
    assert out and out['phase']=='campaign_review'
