"""捕捉橋接只串接純控制器和同幀唯讀snapshot，從不執行按鍵。"""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from laya_pokemon import capture_transaction as tx
from tests.test_snorlax_capture import progress,command,bag,dialogue,snapshot,LOCATION,WILD,F

@pytest.fixture(autouse=True)
def clean():
    tx._SESSIONS.clear();yield;tx._SESSIONS.clear()

def setup(monkeypatch):
    monkeypatch.setattr(tx.wild_opponent,'read_wild_opponent',lambda p,**kw:snapshot(kw['observation_frame']))
    state={'phase':'battle_menu','frame':40,'location':deepcopy(LOCATION),
           'battle_state':deepcopy(WILD),'progress':progress()}
    step={'id':'capture','kind':'interact','map_id':23,'target':[10,61],
          'mechanic':tx.MECHANIC,'capture_intent':deepcopy(tx.snorlax_capture.INTENT)}
    return SimpleNamespace(),state,{'steps':[step,{'id':'after'}]}

def call(a,t=None):return tx.context(*a,'capture',command(a[1]['progress']) if t is None else t,None)

def test_initial_true_snapshot_can_only_select_item_and_does_not_mutate_input(monkeypatch):
    a=setup(monkeypatch);before=deepcopy(a[1]);r,next_id=call(a)
    assert r['available_actions']==['a','wait'] and next_id=='capture'
    assert a[1]==before and r['wild_enemy_snapshot']['read_valid']

@pytest.mark.parametrize('mutate',[lambda s:s.update(target=[11,61]),
    lambda s:s['capture_intent'].update(ball_item=4),lambda s:s['capture_intent'].update(no_run=1)])
def test_explicit_capture_binding_rejects_changes(monkeypatch,mutate):
    a=setup(monkeypatch);mutate(a[2]['steps'][0])
    assert call(a)[0]['review_reason']=='capture_transaction_explicit_intent_unverified'
    assert not tx._SESSIONS

def test_live_transaction_cannot_be_dropped_for_different_step(monkeypatch):
    a=setup(monkeypatch);call(a)
    assert tx.context(*a,'after',command(a[1]['progress']),None)[0]['review_reason']=='capture_transaction_step_changed'

def test_caught_handoff_constructs_finalizer_from_original_last_throw_and_confirms_first_page(monkeypatch):
    a=setup(monkeypatch);call(a)
    a[1]['frame']=80;assert call(a,bag(a[1]['progress'],cursor=0))[0]['available_actions']==['down','wait']
    a[1]['frame']=120;assert call(a,bag(a[1]['progress'],cursor=1))[0]['available_actions']==['a','wait']
    capture=tx._SESSIONS['capture']['capture'];before=deepcopy(capture.last_throw)
    a[1]['frame']=160
    r,_=call(a,dialogue(a[1]['progress'],F['caught_first_page']))
    assert r['available_actions']==['a','wait'] and not r.get('capture_complete')
    c=tx._SESSIONS['capture']['completion']
    assert c is not None and c.baseline==before and capture.last_throw==before

def test_review_excludes_pause_clock_once_and_keeps_controller_baseline(monkeypatch):
    a=setup(monkeypatch);clock=iter([10.,20.,100.,101.]);monkeypatch.setattr(tx.time,'monotonic',lambda:next(clock))
    call(a);record=tx._SESSIONS['capture'];c=record['capture'];baseline=deepcopy(c.initial_items)
    a[1]['frame']=80
    wrong=command(a[1]['progress']);wrong['read_valid']=False
    reason=call(a,wrong)[0]['review_reason']
    a[2]['steps'][0].update(reviewed_controller_revision=1,reviewed_controller_error=reason)
    a[1]['frame']=120
    result,_=call(a,bag(a[1]['progress'],cursor=0))
    assert result['available_actions']==['down','wait']
    assert record['clock_offset']==80. and record['capture'] is c and c.initial_items==baseline
    a[1]['frame']=160;call(a,bag(a[1]['progress'],cursor=0))
    assert record['clock_offset']==80.


def reviewed_switch_session(monkeypatch):
    """Four genuine pure-controller throw requests; no fabricated capture baseline."""
    a=setup(monkeypatch);clock=[10.]
    monkeypatch.setattr(tx.time,'monotonic',lambda:clock[0])
    fp={'species':132,'level':30,'hp':140,'max_hp':140,'status':0}
    monkeypatch.setattr(tx.wild_opponent,'read_wild_opponent',
                        lambda p,**kw:snapshot(kw['observation_frame'],fp))
    def advance(t):
        a[1]['frame']+=40;clock[0]+=1.
        return call(a,t)[0]
    p=a[1]['progress']
    assert advance(command(p,enemy=fp))['available_actions']==['a','wait']
    for turn in range(4):
        assert advance(bag(p,cursor=0,enemy=fp))['available_actions']==['down','wait']
        assert advance(bag(p,cursor=1,enemy=fp))['available_actions']==['a','wait']
        assert advance(dialogue(p,F['failure_pages']['broke_free'],fp))['available_actions']==['a','wait']
        next(x for x in p['inventory'] if x['item']==3)['quantity']-=1
        if turn==3:p['party'][0]['hp']=56
        r=advance(command(p,enemy=fp))
        if turn<3:assert r['available_actions']==['a','wait']
    assert r['review_reason']==tx._SAFE_SWITCH_ERROR
    record=tx._SESSIONS['capture'];c=record['capture']
    assert c.throws==4 and c.stage=='enemy_turn' and c.party_hp==[56,70,80,90]
    return a,clock,advance,record,c


def request_switch(a,revision=1,target=7):
    a[2]['steps'][0].update(reviewed_switch_revision=revision,reviewed_switch_target_species=target)


def perform_switch(a,advance,revision=1):
    from tests import test_snorlax_switch as sw
    p=a[1]['progress']
    request_switch(a,revision)
    assert advance(sw.command(p,0,(9,16)))['available_actions']==['up','wait']
    assert advance(sw.command(p,0,(9,14)))['available_actions']==['right','wait']
    assert advance(sw.command(p,0,(15,14)))['available_actions']==['a','wait']
    for index in range(3):
        assert advance(sw.party_page(p,index))['available_actions']==['down','wait']
    assert advance(sw.party_page(p,3))['available_actions']==['a','wait']
    assert advance(sw.submenu(p,3))['available_actions']==['a','wait']
    assert advance(sw.dialogue(p,0,'VENUSAUR enough!','Come back!'))['available_actions']==['wait']
    assert advance(sw.dialogue(p,0,'Go! NIDOKING!'))['available_actions']==['wait']
    assert advance(sw.dialogue(p,3,'Enemy SNORLAX','used HEADBUTT!'))['available_actions']==['wait']
    p['party'][3]['hp']=82
    return advance(sw.command(p,3,(9,16)))


def test_real_four_throw_switch_preserves_capture_and_resumes_only_next_frame(monkeypatch):
    from tests import test_snorlax_switch as sw
    a,clock,advance,record,c=reviewed_switch_session(monkeypatch)
    last=c.last_throw;before={k:deepcopy(getattr(c,k)) for k in ('throws','initial_items','current_items','last_throw')}
    started=c.started_at;old_offset=record['clock_offset'];review_time=clock[0]
    clock[0]+=120. # Engineering review time is separate from the switch budget.
    result=perform_switch(a,advance)
    assert result['available_actions']==['wait'] and result['capture_resume_pending']
    assert not result['capture_complete'] and result['capture_controller_preserved']
    assert record['capture'] is c and c.last_throw is last and c.started_at==started
    assert all(getattr(c,k)==v for k,v in before.items())
    assert c.error is None and c.stage=='command' and c.active_index==3
    assert c.party_hp==[56,70,80,82] and record['switch'] is None
    assert record['last_switch_controller'].completion['snorlax_switch_complete']
    assert record['clock_offset']-old_offset==clock[0]-review_time
    assert c.command_pending is c.bag_pending is c.failure_pending is c.prompt_pending is None
    r=advance(sw.command(a[1]['progress'],3,(9,16)))
    assert r['available_actions']==['a','wait'] and c.throws==4
    assert c.current_items==tx.snorlax_capture._inventory(a[1]['progress'])
    assert c.last_throw is last and record['switch'] is None


@pytest.mark.parametrize('revision,target',[(True,7),(0,7),('1',7),(1,True),(1,6),(1,154)])
def test_invalid_or_active_target_never_clears_safe_error_or_creates_owner(monkeypatch,revision,target):
    from tests import test_snorlax_switch as sw
    a,_,advance,record,c=reviewed_switch_session(monkeypatch);before=deepcopy(c.__dict__)
    request_switch(a,revision,target);t=sw.command(a[1]['progress'],0,(9,16));r=advance(t)
    assert r['phase']=='campaign_review' and r['available_actions']==['wait']
    assert c.__dict__==before and record['switch'] is None and record['switch_revision']==0
    assert r['capture_text_snapshot']==t


@pytest.mark.parametrize('damage',['proof','hud','items','party','frame','enemy'])
def test_switch_baseline_requires_full_current_command_and_original_accounting(monkeypatch,damage):
    from tests import test_snorlax_switch as sw
    a,_,advance,record,c=reviewed_switch_session(monkeypatch);request_switch(a)
    t=sw.command(a[1]['progress'],0,(9,16))
    if damage=='proof':t['read_valid']=False
    elif damage=='hud':sw.put(t,11,10,' 55/105')
    elif damage=='items':a[1]['progress']['inventory'][1]['quantity']+=1
    elif damage=='party':a[1]['progress']['party'][1]['exp']+=1
    elif damage=='frame':a[1]['progress']['observation_frame']=a[1]['frame']
    elif damage=='enemy':monkeypatch.setattr(tx.wild_opponent,'read_wild_opponent',lambda p,**kw:{'read_valid':False})
    r=advance(t)
    assert r['phase']=='campaign_review' and r['available_actions']==['wait']
    assert c.error==tx._SAFE_SWITCH_ERROR and record['switch'] is None


def test_generic_review_cannot_acknowledge_safe_switch_without_explicit_request(monkeypatch):
    a,_,advance,record,c=reviewed_switch_session(monkeypatch)
    a[2]['steps'][0].update(reviewed_controller_revision=1,reviewed_controller_error=c.error,
                             reviewed_budget_reset=True)
    r=advance(command(a[1]['progress'],enemy={'species':132,'level':30,'hp':140,'max_hp':140,'status':0}))
    assert r['review_reason']==tx._SAFE_SWITCH_ERROR and c.error==tx._SAFE_SWITCH_ERROR
    assert record['reviewed_revision']==0 and record['switch'] is None


def test_switch_error_uses_existing_review_protocol_preserving_both_baselines_and_budgets(monkeypatch):
    from tests import test_snorlax_switch as sw
    a,clock,advance,record,c=reviewed_switch_session(monkeypatch);request_switch(a)
    assert advance(sw.command(a[1]['progress'],0,(9,16)))['available_actions']==['up','wait']
    s=record['switch'];before=deepcopy(record['switch_capture_preserved']);baseline=deepcopy(s.baseline)
    bad=sw.command(a[1]['progress'],0,(9,14));bad['read_valid']=False
    r=advance(bad);reason=r['review_reason'];old_calls=s.calls;old_started=s._baseline_now
    old_offset=record['clock_offset']
    assert c.error==tx._SAFE_SWITCH_ERROR and s.error==reason
    clock[0]+=120.
    a[2]['steps'][0].update(reviewed_controller_revision=1,reviewed_controller_error=reason,
                             reviewed_budget_reset=True)
    r=advance(sw.command(a[1]['progress'],0,(9,14)))
    assert r['available_actions']==['right','wait'] and record['switch'] is s and record['capture'] is c
    assert s.baseline==baseline and record['switch_capture_preserved']==before and s._baseline_now==old_started
    assert s.calls==old_calls+1 and c.error==tx._SAFE_SWITCH_ERROR
    assert record['reviewed_revision']==1 and record['clock_offset']==old_offset+121.


@pytest.mark.parametrize('change', ['owner','removed','revision','target','capture'])
def test_active_switch_owner_and_original_capture_cannot_be_replaced(monkeypatch,change):
    from tests import test_snorlax_switch as sw
    a,_,advance,record,c=reviewed_switch_session(monkeypatch);request_switch(a)
    advance(sw.command(a[1]['progress'],0,(9,16)));s=record['switch']
    if change=='owner':
        r=tx.context(*a,'after',sw.command(a[1]['progress']),None)[0]
    else:
        if change=='removed':a[2]['steps'][0].pop('reviewed_switch_revision');a[2]['steps'][0].pop('reviewed_switch_target_species')
        if change=='revision':a[2]['steps'][0]['reviewed_switch_revision']=2
        if change=='target':a[2]['steps'][0]['reviewed_switch_target_species']=35
        if change=='capture':c.throws+=1
        r=advance(sw.command(a[1]['progress'],0,(9,14)))
    assert r['phase']=='campaign_review' and r['available_actions']==['wait']
    assert record['switch'] is s and record['capture'] is c and c.error==tx._SAFE_SWITCH_ERROR


@pytest.mark.parametrize('revision,target',[(1,7),(1,35),(0,7)])
def test_consumed_revision_does_not_switch_again_and_changed_target_stops(monkeypatch,revision,target):
    from tests import test_snorlax_switch as sw
    a,_,advance,record,c=reviewed_switch_session(monkeypatch);perform_switch(a,advance)
    request_switch(a,revision,target);r=advance(sw.command(a[1]['progress'],3,(9,16)))
    assert record['switch'] is None and record['switch_revision']==1 and record['capture'] is c
    assert r['available_actions']==(['a','wait'] if (revision,target)==(1,7) else ['wait'])


def test_bridge_revalidates_actual_completion_before_clearing_capturer_error(monkeypatch):
    a,_,advance,record,c=reviewed_switch_session(monkeypatch)
    monkeypatch.setattr(tx,'_switch_completion_verified',lambda *args:None)
    before={k:deepcopy(getattr(c,k)) for k in tx._PRESERVED_CAPTURE}
    r=perform_switch(a,advance)
    assert r['review_reason']=='capture_switch_completion_not_verified'
    assert c.error==tx._SAFE_SWITCH_ERROR and record['switch'] is not None
    assert all(getattr(c,k)==v for k,v in before.items())


@pytest.mark.parametrize('target',[7,35])
def test_positive_but_regressed_revision_stops_without_any_capturer_action(monkeypatch,target):
    from tests import test_snorlax_switch as sw
    a,_,advance,record,c=reviewed_switch_session(monkeypatch);perform_switch(a,advance,revision=2)
    before=deepcopy(c.__dict__);request_switch(a,1,target)
    r=advance(sw.command(a[1]['progress'],3,(9,16)))
    assert r['review_reason']=='capture_switch_revision_regressed' and r['available_actions']==['wait']
    assert c.__dict__==before and record['switch'] is None and record['switch_revision']==2


def test_active_contract_review_latches_and_excludes_only_explicitly_acknowledged_pause(monkeypatch):
    from tests import test_snorlax_switch as sw
    a,clock,advance,record,c=reviewed_switch_session(monkeypatch);request_switch(a)
    advance(sw.command(a[1]['progress'],0,(9,16)));s=record['switch']
    a[2]['steps'][0]['reviewed_switch_target_species']=35
    r=advance(sw.command(a[1]['progress'],0,(9,14)));reason=r['review_reason']
    assert reason=='capture_switch_request_changed_while_active' and record['bridge_error']==reason
    clock[0]+=120.;a[2]['steps'][0]['reviewed_switch_target_species']=7
    assert advance(sw.command(a[1]['progress'],0,(9,14)))['review_reason']==reason
    a[2]['steps'][0].update(reviewed_controller_revision=1,reviewed_controller_error=reason)
    r=advance(sw.command(a[1]['progress'],0,(9,14)))
    assert r['available_actions']==['right','wait'] and record['switch'] is s
    assert c.error==tx._SAFE_SWITCH_ERROR and record['bridge_error'] is None


def test_switch_completion_same_frame_never_calls_capturer_or_reader_or_changes_clock(monkeypatch):
    from tests import test_snorlax_switch as sw
    a,clock,advance,record,c=reviewed_switch_session(monkeypatch)
    result=perform_switch(a,advance)
    assert result['available_actions']==['wait'] and record['last_switch_frame']==a[1]['frame']
    before=deepcopy(c.__dict__);offset=record['clock_offset']
    def forbidden(*args,**kwargs):raise AssertionError('same completion frame must not reach capture or enemy reader')
    monkeypatch.setattr(tx.snorlax_capture.SnorlaxCaptureController,'context',forbidden)
    monkeypatch.setattr(tx,'_enemy_snapshot',forbidden)
    for _ in range(3):
        clock[0]+=.1
        r,_=call(a,sw.command(a[1]['progress'],3,(9,16)))
        assert r['available_actions']==['wait'] and r['capture_resume_pending'] and not r['capture_complete']
    assert record['capture'] is c and c.__dict__==before and record['clock_offset']==offset


@pytest.mark.parametrize('frame',['regressed',True,None,2.5])
def test_switch_resume_invalid_or_regressed_frame_reviews_without_calling_capture(monkeypatch,frame):
    from tests import test_snorlax_switch as sw
    a,_,advance,record,c=reviewed_switch_session(monkeypatch);perform_switch(a,advance)
    before=deepcopy(c.__dict__);offset=record['clock_offset']
    a[1]['frame']=record['last_switch_frame']-1 if frame=='regressed' else frame
    def forbidden(*args,**kwargs):raise AssertionError('invalid resume frame must not reach capture')
    monkeypatch.setattr(tx.snorlax_capture.SnorlaxCaptureController,'context',forbidden)
    r,_=call(a,sw.command(a[1]['progress'],3,(9,16)))
    assert r['review_reason']=='capture_switch_resume_frame_invalid_or_regressed'
    assert r['available_actions']==['wait'] and c.__dict__==before and record['clock_offset']==offset


def test_old_hotload_record_without_frame_fence_remains_compatible(monkeypatch):
    from tests import test_snorlax_switch as sw
    a,_,advance,record,c=reviewed_switch_session(monkeypatch);perform_switch(a,advance)
    del record['last_switch_frame']
    r=advance(sw.command(a[1]['progress'],3,(9,16)))
    assert r['available_actions']==['a','wait'] and record['capture'] is c
    assert record['last_switch_frame'] is None and c.throws==4


def ten_throw_pre_switch_session(monkeypatch):
    """先真四投與正常換Nido，再六投失敗；不手改capturer的投球基線。"""
    from tests import test_snorlax_switch as sw
    a,clock,advance,record,c=reviewed_switch_session(monkeypatch)
    perform_switch(a,advance)
    p=a[1]['progress'];fp={'species':132,'level':30,'hp':140,'max_hp':140,'status':0}
    assert advance(sw.command(p,3,(9,16)))['available_actions']==['a','wait']
    for turn in range(6):
        assert advance(bag(p,cursor=0,enemy=fp))['available_actions']==['down','wait']
        assert advance(bag(p,cursor=1,enemy=fp))['available_actions']==['a','wait']
        failure=dialogue(p,F['failure_pages']['broke_free'],fp)
        failure['cells'][:12]=deepcopy(sw.hud(p,3)['cells'][:12])
        assert advance(failure)['available_actions']==['a','wait']
        next(x for x in p['inventory'] if x['item']==3)['quantity']-=1
        if turn==5:
            p['party'][3]['hp']=48
            result=advance(sw.dialogue(p,3,'Enemy SNORLAX','used HEADBUTT!'))
        else:
            result=advance(sw.command(p,3,(9,16)))
            assert result['available_actions']==['a','wait']
    assert result['review_reason']==tx._SAFE_SWITCH_ERROR and c.throws==10 and c.active_index==3
    assert next(x for x in p['inventory'] if x['item']==3)['quantity']==10
    return a,clock,advance,record,c


def begin_pre_switch(monkeypatch):
    from tests import test_snorlax_switch as sw
    a,clock,advance,record,c=ten_throw_pre_switch_session(monkeypatch)
    request_switch(a,2,35)
    t=sw.dialogue(a[1]['progress'],3,'Enemy SNORLAX','used HEADBUTT!')
    return a,clock,advance,record,c,t


def test_low_hp_headbutt_waits_for_real_command_then_normal_switch_keeps_ten_throws(monkeypatch):
    from tests import test_snorlax_switch as sw
    a,clock,advance,record,c,t=begin_pre_switch(monkeypatch)
    original=deepcopy(c.__dict__);last=c.last_throw;started=c.started_at;pause=clock[0]
    old_offset=record['clock_offset']
    clock[0]+=120.
    r=advance(t)
    assert r['phase']=='capture_pre_switch_wait' and r['available_actions']==['wait']
    assert record['switch'] is None and record['capture'] is c and c.__dict__==original
    pending_started=record['pre_switch']['started_now']
    assert advance(sw.hud(a[1]['progress'],3))['available_actions']==['wait']
    assert c.__dict__==original
    p=a[1]['progress']
    r=advance(sw.command(p,3,(9,16)))
    s=record['switch']
    assert r['available_actions']==['up','wait'] and record['pre_switch'] is None
    assert s.target_species==35 and s.baseline['now']==clock[0]-record['clock_offset']
    assert s.baseline['now']>pending_started and record['switch_start_now']==pending_started
    assert advance(sw.command(p,3,(9,14)))['available_actions']==['right','wait']
    assert advance(sw.command(p,3,(15,14)))['available_actions']==['a','wait']
    for i in range(2):assert advance(sw.party_page(p,i))['available_actions']==['down','wait']
    assert advance(sw.party_page(p,2))['available_actions']==['a','wait']
    assert advance(sw.submenu(p,2))['available_actions']==['a','wait']
    assert advance(sw.dialogue(p,3,'NIDOKING enough!','Come back!'))['available_actions']==['wait']
    assert advance(sw.dialogue(p,3,'Go! FEAROW!'))['available_actions']==['wait']
    assert advance(sw.dialogue(p,2,'Enemy SNORLAX','used HEADBUTT!'))['available_actions']==['wait']
    p['party'][2]['hp']=70
    result=advance(sw.command(p,2,(9,16)))
    assert result['capture_resume_pending'] and result['available_actions']==['wait']
    assert record['capture'] is c and c.throws==10 and c.last_throw is last and c.started_at==started
    assert c.initial_items==original['initial_items'] and c.current_items==original['current_items']
    assert c.error is None and c.active_index==2 and c.party_hp==[56,70,70,48]
    assert record['clock_offset']==old_offset+clock[0]-pause
    assert advance(sw.command(p,2,(9,16)))['available_actions']==['a','wait']
    assert c.throws==10 and next(x for x in p['inventory'] if x['item']==3)['quantity']==10


@pytest.mark.parametrize('empty_lower',[False,True])
def test_same_wait_contract_supports_other_throw_count_revision_and_healthy_target(monkeypatch,empty_lower):
    from tests import test_snorlax_switch as sw
    a,_,advance,record,c=reviewed_switch_session(monkeypatch)
    request_switch(a,3,102)
    before=deepcopy(c.__dict__)
    t=sw.hud(a[1]['progress'],0) if empty_lower else sw.dialogue(a[1]['progress'],0,'Enemy SNORLAX','used HEADBUTT!')
    r=advance(t)
    assert r['phase']=='capture_pre_switch_wait' and c.throws==4 and c.__dict__==before
    r=advance(sw.command(a[1]['progress'],0,(9,16)))
    assert r['available_actions']==['up','wait']
    assert record['switch'].target_species==102 and record['switch_revision']==3


@pytest.mark.parametrize('damage',['prompt','active_cursor','inactive_cursor','unknown','partial',
    'hp','missing_hp','other_active','proof','window','faint','enemy','ball','money','party','location','battle'])
def test_pre_switch_never_waits_on_unknown_or_changed_initial_observation(monkeypatch,damage):
    from tests import test_snorlax_switch as sw
    a,_,advance,record,c,t=begin_pre_switch(monkeypatch);before=deepcopy(c.__dict__)
    if damage=='prompt':sw.put(t,18,16,'▼')
    elif damage=='active_cursor':sw.put(t,0,0,'▶')
    elif damage=='inactive_cursor':sw.put(t,0,0,'▷')
    elif damage=='unknown':sw.put(t,1,14,'Delete')
    elif damage=='partial':sw.put(t,1,16,'used HEADBU  ')
    elif damage=='hp':sw.put(t,11,10,' 49/ 95')
    elif damage=='missing_hp':t['cells'][10]=[' ']*20
    elif damage=='other_active':t=sw.dialogue(a[1]['progress'],0,'Enemy SNORLAX','used HEADBUTT!')
    elif damage=='proof':t['alignment_verified']=False
    elif damage=='window':t['window_visible']=None
    elif damage=='faint':a[1]['progress']['party'][1]['hp']=0
    elif damage=='enemy':monkeypatch.setattr(tx,'_enemy_snapshot',lambda *args:snapshot(a[1]['frame'],{'species':132,'level':30,'hp':139,'max_hp':140,'status':0}))
    elif damage=='ball':a[1]['progress']['inventory'][1]['quantity']+=1
    elif damage=='money':a[1]['progress']['money']+=1
    elif damage=='party':a[1]['progress']['party'][1]['exp']+=1
    elif damage=='location':a[1]['location']['x']=11
    else:a[1]['battle_state']['raw']=0
    r=advance(t)
    assert r['phase']=='campaign_review' and r['available_actions']==['wait']
    assert record['pre_switch'] is None and record['switch'] is None and c.__dict__==before


@pytest.mark.parametrize('change',['revision','target','removed','capture','enemy','ball','healing','other_hp','money'])
def test_pending_contract_or_baseline_change_latches_review_and_never_clears_capture(monkeypatch,change):
    a,_,advance,record,c,t=begin_pre_switch(monkeypatch)
    advance(t);before=deepcopy(c.__dict__)
    if change=='revision':a[2]['steps'][0]['reviewed_switch_revision']=3
    elif change=='target':a[2]['steps'][0]['reviewed_switch_target_species']=102
    elif change=='removed':a[2]['steps'][0].pop('reviewed_switch_target_species')
    elif change=='capture':c.current_items=[]
    elif change=='enemy':monkeypatch.setattr(tx,'_enemy_snapshot',lambda *args:snapshot(a[1]['frame'],{'species':132,'level':30,'hp':139,'max_hp':140,'status':0}))
    elif change=='ball':a[1]['progress']['inventory'][1]['quantity']-=1
    elif change=='healing':a[1]['progress']['party'][3]['hp']+=1
    elif change=='other_hp':a[1]['progress']['party'][1]['hp']-=1
    else:a[1]['progress']['money']+=1
    r=advance(t)
    assert r['phase']=='campaign_review' and r['available_actions']==['wait']
    assert record['bridge_error']==r['review_reason'] and record['switch'] is None
    assert c.error==tx._SAFE_SWITCH_ERROR and (change=='capture' or c.__dict__==before)


def test_pending_same_frame_wait_is_bounded_and_changed_packet_reviewed(monkeypatch):
    from tests import test_snorlax_switch as sw
    a,_,advance,record,c,t=begin_pre_switch(monkeypatch);advance(t)
    before=deepcopy(c.__dict__)
    assert call(a,t)[0]['available_actions']==['wait']
    changed=sw.hud(a[1]['progress'],3)
    assert call(a,changed)[0]['review_reason']=='capture_pre_switch_same_frame_conflict'
    assert c.__dict__==before


def test_pending_twenty_five_wait_limit_stops_without_resetting_capture(monkeypatch):
    a,_,advance,record,c,t=begin_pre_switch(monkeypatch);before=deepcopy(c.__dict__)
    for _ in range(25):assert advance(t)['phase']=='capture_pre_switch_wait'
    r=advance(t)
    assert r['review_reason']=='capture_pre_switch_wait_budget_exhausted'
    assert record['pre_switch']['waits']==25 and c.__dict__==before and record['switch'] is None


def test_native_command_on_call_twenty_six_is_allowed_after_exactly_twenty_five_waits(monkeypatch):
    from tests import test_snorlax_switch as sw
    a,_,advance,record,c,t=begin_pre_switch(monkeypatch)
    for _ in range(25):assert advance(t)['phase']=='capture_pre_switch_wait'
    pending=record['pre_switch']
    r=advance(sw.command(a[1]['progress'],3,(9,16)))
    assert r['available_actions']==['up','wait'] and pending['calls']==26
    assert record['pre_switch'] is None and record['switch'].target_species==35 and c.throws==10


def test_pending_active_hp_may_decrease_but_capture_baseline_is_not_rewritten(monkeypatch):
    from tests import test_snorlax_switch as sw
    a,_,advance,record,c,t=begin_pre_switch(monkeypatch);advance(t)
    before=deepcopy(c.__dict__)
    a[1]['progress']['party'][3]['hp']=47
    assert advance(sw.dialogue(a[1]['progress'],3,'Enemy SNORLAX','used HEADBUTT!'))['phase']=='capture_pre_switch_wait'
    assert record['pre_switch']['party_hp'][3]==47 and c.__dict__==before
    assert advance(sw.command(a[1]['progress'],3,(9,16)))['available_actions']==['up','wait']
    assert record['switch'].baseline['progress']['party'][3]['hp']==47 and c.party_hp[3]==48


def test_pending_sixty_second_budget_does_not_include_initial_engineering_pause(monkeypatch):
    a,clock,advance,record,c,t=begin_pre_switch(monkeypatch);before=deepcopy(c.__dict__)
    clock[0]+=120.;assert advance(t)['phase']=='capture_pre_switch_wait'
    clock[0]+=60.
    r=advance(t)
    assert r['review_reason']=='capture_pre_switch_transaction_budget_exhausted'
    assert c.__dict__==before and record['switch'] is None


def test_pending_review_ack_preserves_safe_error_and_excludes_only_engineering_time(monkeypatch):
    from tests import test_snorlax_switch as sw
    a,clock,advance,record,c,t=begin_pre_switch(monkeypatch);advance(t)
    before=deepcopy(c.__dict__)
    bad=deepcopy(t);sw.put(bad,1,14,'Delete')
    reason=advance(bad)['review_reason'];clock[0]+=120.
    assert advance(t)['review_reason']==reason
    a[2]['steps'][0].update(reviewed_controller_revision=1,reviewed_controller_error=reason)
    r=advance(sw.command(a[1]['progress'],3,(9,16)))
    assert r['available_actions']==['up','wait'] and record['switch'].target_species==35
    assert c.error==tx._SAFE_SWITCH_ERROR and c.__dict__==before


@pytest.mark.parametrize('body',['command','headbutt'])
@pytest.mark.parametrize('damage',['old_frame','old_now'])
def test_first_new_switch_request_must_not_regress_original_capture_frame_or_clock(monkeypatch,body,damage):
    from tests import test_snorlax_switch as sw
    a,clock,_,record,c,t=begin_pre_switch(monkeypatch);before=deepcopy(c.__dict__)
    if damage=='old_frame':a[1]['frame']-=80
    else:clock[0]-=10.
    current=sw.command(a[1]['progress'],3,(9,16)) if body=='command' else t
    r=call(a,current)[0]
    assert r['review_reason']=='capture_switch_new_request_clock_or_frame_regressed'
    assert r['available_actions']==['wait'] and c.__dict__==before
    assert record['pre_switch'] is None and record['switch'] is None


@pytest.mark.parametrize('damage',['rows','progress','location','battle','enemy','window'])
def test_first_equal_frame_request_must_match_capturer_full_original_packet(monkeypatch,damage):
    from tests import test_snorlax_switch as sw
    a,_,_,record,c,t=begin_pre_switch(monkeypatch);before=deepcopy(c.__dict__)
    if damage=='rows':t=sw.command(a[1]['progress'],3,(9,16))
    elif damage=='progress':a[1]['progress']['money']+=1
    elif damage=='location':a[1]['location']['observation_frame']=a[1]['frame']
    elif damage=='battle':a[1]['battle_state']['observation_frame']=a[1]['frame']
    elif damage=='enemy':
        def changed(_p,frame,_loc):
            e=snapshot(frame,{'species':132,'level':30,'hp':140,'max_hp':140,'status':0})
            e['enemy']['pp'][0]-=1
            return e
        monkeypatch.setattr(tx,'_enemy_snapshot',changed)
    else:t['window_visible']=False
    r=call(a,t)[0]
    assert r['review_reason']=='capture_switch_new_request_same_frame_conflict'
    assert r['available_actions']==['wait'] and c.__dict__==before
    assert record['pre_switch'] is None and record['switch'] is None


def test_first_equal_frame_identical_headbutt_packet_can_only_start_bounded_wait(monkeypatch):
    a,_,_,record,c,t=begin_pre_switch(monkeypatch);before=deepcopy(c.__dict__)
    r=call(a,t)[0]
    assert r['phase']=='capture_pre_switch_wait' and r['available_actions']==['wait']
    assert record['switch'] is None and c.__dict__==before


@pytest.mark.parametrize('packet',[None,(),(None,)*6])
@pytest.mark.parametrize('body',['command','headbutt'])
def test_unknown_original_capture_packet_never_creates_new_action_or_owner(monkeypatch,packet,body):
    from tests import test_snorlax_switch as sw
    a,_,advance,record,c,t=begin_pre_switch(monkeypatch)
    c.last_packet=packet;before=deepcopy(c.__dict__)
    if body=='command':t=sw.command(a[1]['progress'],3,(9,16))
    r=advance(t)
    assert r['review_reason']=='capture_switch_prior_capture_packet_unverified'
    assert r['available_actions']==['wait'] and c.__dict__==before
    assert record['pre_switch'] is None and record['switch'] is None


@pytest.mark.parametrize('damage',['window','enemy_pp'])
def test_pending_same_frame_requires_full_raw_packet_not_only_rows_and_enemy_fingerprint(monkeypatch,damage):
    a,_,advance,record,c,t=begin_pre_switch(monkeypatch);advance(t)
    before=deepcopy(c.__dict__)
    if damage=='window':t['window_visible']=False
    else:
        def changed(_p,frame,_loc):
            e=snapshot(frame,{'species':132,'level':30,'hp':140,'max_hp':140,'status':0})
            e['enemy']['pp'][0]-=1
            return e
        monkeypatch.setattr(tx,'_enemy_snapshot',changed)
    r=call(a,t)[0]
    assert r['review_reason']=='capture_pre_switch_same_frame_conflict'
    assert r['available_actions']==['wait'] and record['switch'] is None and c.__dict__==before


def test_pending_same_frame_exact_raw_packet_only_waits_without_touching_capture(monkeypatch):
    a,_,advance,record,c,t=begin_pre_switch(monkeypatch);advance(t)
    before=deepcopy(c.__dict__);packet=deepcopy(record['pre_switch']['last_packet']['raw_packet'])
    assert call(a,t)[0]['phase']=='capture_pre_switch_wait'
    assert record['pre_switch']['last_packet']['raw_packet']==packet and c.__dict__==before


@pytest.mark.parametrize('damage',['window','enemy_pp'])
def test_pending_different_frame_does_not_require_raw_packet_equality(monkeypatch,damage):
    a,_,advance,record,c,t=begin_pre_switch(monkeypatch);advance(t)
    before=deepcopy(c.__dict__)
    if damage=='window':t['window_visible']=False
    else:
        def changed(_p,frame,_loc):
            e=snapshot(frame,{'species':132,'level':30,'hp':140,'max_hp':140,'status':0})
            e['enemy']['pp'][0]-=1
            return e
        monkeypatch.setattr(tx,'_enemy_snapshot',changed)
    r=advance(t)
    assert r['phase']=='capture_pre_switch_wait' and r['available_actions']==['wait']
    assert record['switch'] is None and c.__dict__==before
