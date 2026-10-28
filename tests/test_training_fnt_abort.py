"""Portable synthetic reviewed-FNT tests. No private evidence, files or emulator."""
from copy import deepcopy
from types import SimpleNamespace

from laya_pokemon import league_training_batch_bridge as bridge


REAL_CAP_SHA = 'e6d1633738687c674bb5914ec78b8339499ad9a9fefcdab9c2e304f4c46d7c4e'


def synthetic_case(monkeypatch,error=None):
    for key,value in (('_CONTROLLERS',{}),('_BINDINGS',{}),('_OWNERS',{}),('_ERRORS',{}),
                      ('_COMPLETED',set()),('_REVIEWED_ABORTS',{})):
        monkeypatch.setattr(bridge,key,value)
    rows=[(102,'EEVEE',36,93,[33,28,98,39],[35,15,30,30]),
          (132,'SNORLAX',42,100,[70,133,156,34],[15,20,10,15]),
          (154,'VENUSAUR',37,100,[75,15,73,22],[25,30,10,10]),
          (35,'FEAROW',38,100,[64,65,19,31],[35,20,15,20]),
          (7,'NIDOKING',37,100,[61,57,30,40],[20,15,25,35]),
          (19,'LAPRAS',44,181,[57,34,58,85],[15,15,10,15])]
    progress=dict(profile='gen1-wrapper-ram-progress-v1-unvalidated',initialization_candidate=True,
        party_read_valid=True,party_count=6,player_name_raw='KEVIN',badges_raw=255,money=1000,
        inventory=[],story_event_bits={},party=[dict(species=s,species_name=name,level=lv,
            hp=hp,max_hp=hp,exp=50000,status=0,moves=moves,pp=pp)
            for s,name,lv,hp,moves,pp in rows])
    baseline=bridge.batch.resources(progress)
    current=deepcopy(progress);current['party'][0]['hp']=0;current['party'][0]['pp'][2]=29
    current['party'][-1]['exp']+=708;current['party'][-1]['pp'][0]=14
    key=bridge._FNT_STEP;job='league-six-party45-game29-20261028'
    step=dict(id=key,kind='interact',mechanic='league_training_batch',map_id=194,target=[28,7],
              training_intent=deepcopy(bridge.batch.INTENT))
    budget=dict(appends=69,outings=35,deadline_wall=9999999999.,phase='outbound_batch')
    plan=dict(mode='league_campaign',training_job=job,steps=[step],lead_species=102,
              league_training_supervisor_budget=budget)
    binding=(bridge.MECHANIC,bridge._canonical(step),job)
    def event(frame,lines):
        return dict(file='synthetic-fnt.jsonl',line_number=1,line_sha256='a'*64,
            record=dict(state=dict(frame=frame,battle_state=dict(raw=1,kind='wild',active=True,
                opponent_species='MAROWAK',wild_opponent_species='MAROWAK'),visible_text_candidates=lines)))
    cap=dict(kind=bridge._FNT_KIND,game_id='game29',source_frame=382449,
        source_location=dict(map_id=194,x=28,y=7),step_id=key,job=job,fainted_species=102,healthy_lead_species=19,
        baseline=deepcopy(baseline),baseline_sha256=bridge._digest(baseline),progress=deepcopy(current),
        progress_sha256=bridge._digest(current),original_plan=deepcopy(plan),plan_sha256=bridge._digest(plan),
        binding_sha256=bridge._digest(binding),recovery_steps=[],recovery_steps_sha256=bridge._digest([]),
        root_review=dict(refund=False,baseline_rewritten=False,blackout=False,faint_retained=True),
        source_events=dict(faint=event(380721,['EEVEE','fainted!']),
            enemy_ko=event(382193,['Enemy MAROWAK','fainted!']),
            reward=event(382321,['LAPRAS gained','708 EXP. Points!'])))
    # Test-only authority pin. Production is separately asserted and never widened.
    monkeypatch.setattr(bridge,'_FNT_CAP_SHA',bridge._digest(cap))
    native=SimpleNamespace(frame_count=382449)
    c=bridge.batch.TrainingBatch(bridge.batch.INTENT);c.owner=key;c.baseline=baseline
    c.started=10.;c.last_now=20.;c.calls=10;c.requests=2;c.last_frame=382321
    c.seen_wild=True;c.suspended=True;c.error=error
    c.pending=dict(action='up',player=(28,8),expected=(28,7),frame=380000,executed=True)
    c.last_packet=(dict(frame=382321),{}, {}, {},['a'],key)
    bridge._CONTROLLERS[key]=c;bridge._OWNERS[key]=native;bridge._BINDINGS[key]=binding
    def getter(owner,frame,sdk):
        assert owner is native
        return dict(read_valid=True,idle=True,observation_frame=frame,location=dict(map_id=194,x=28,y=7),
            progress=deepcopy(current),battle=dict(raw=0,kind='none',active=False,observation_frame=frame))
    monkeypatch.setattr(bridge.batch,'read_training_observation',getter)
    monkeypatch.setattr(bridge.batch,'closed_world',lambda text,grid,player,frame:
        text=={'closed':frame} and grid=={'closed':frame} and player==(28,7))
    args=dict(expected_capsule_sha256=bridge._FNT_CAP_SHA,original_controller=c,original_binding=binding,
              original_pending=c.pending,original_last_packet=c.last_packet)
    def packet(frame):
        native.frame_count=frame
        return (dict(frame=frame,location=dict(map_id=194,x=28,y=7),progress=deepcopy(current),
            battle_state=dict(raw=0,kind='none',active=False,observation_frame=frame)),{'closed':frame},{'closed':frame})
    def call(frame=382449,parts=None,**changes):
        state,text,grid=parts or packet(frame)
        return bridge.reviewed_fnt_abort(native,state,plan,key,text,grid,cap,**{**args,**changes})[0]
    return SimpleNamespace(c=c,native=native,key=key,cap=cap,plan=plan,binding=binding,
                           current=current,args=args,packet=packet,call=call)


def test_production_case_pin_is_fixed_and_has_no_synthetic_default():
    assert bridge._FNT_CAP_SHA==REAL_CAP_SHA
    assert bridge._FNT_KIND=='reviewed_eevee_faint382449_to_indigo_v1'


def test_two_fresh_abort_preserves_original_none_error_refs_and_budget(monkeypatch):
    s=synthetic_case(monkeypatch);before=bridge._abort_snapshot(s.c);plan=deepcopy(s.plan)
    refs=(s.c.baseline,s.c.pending,s.c.last_packet)
    assert s.call()['training_batch_aborted'] is False
    assert s.call()['training_batch_aborted'] is False
    out=s.call(382489)
    assert out['training_batch_aborted'] is True and out['training_batch_complete'] is False
    assert out['available_actions']==['wait'] and out['review_reason'].endswith('ready_for_recovery')
    assert not {'field_move_complete','training_batch_receipt'}&set(out)
    assert s.c.error is None and bridge._abort_snapshot(s.c)==before and s.plan==plan
    assert s.c.baseline is refs[0] and s.c.pending is refs[1] and s.c.last_packet is refs[2]
    assert bridge._active()==set() and not bridge._COMPLETED and not bridge._ERRORS


def test_known_fnt_error_is_retained_but_unrelated_error_is_not_admitted(monkeypatch):
    s=synthetic_case(monkeypatch,'league_training_batch_fainted_party_requires_review')
    before=bridge._abort_snapshot(s.c);s.call();out=s.call(382489)
    assert out['training_batch_retained_error']=='league_training_batch_fainted_party_requires_review'
    assert bridge._abort_snapshot(s.c)==before
    s=synthetic_case(monkeypatch,'unrelated_error')
    assert s.call()['training_batch_aborted'] is False and not bridge._REVIEWED_ABORTS
    assert s.c.error=='unrelated_error'


def test_json_cap_or_equal_copies_cannot_replace_original_authority(monkeypatch):
    for bad in ('cap','native','controller','binding','pending','packet'):
        s=synthetic_case(monkeypatch);before=bridge._abort_snapshot(s.c);changes={}
        if bad=='cap':s.cap['root_review']['refund']=True
        if bad=='native':bridge._OWNERS[s.key]=object()
        if bad=='controller':changes['original_controller']=deepcopy(s.c)
        if bad=='binding':changes['original_binding']=tuple(list(s.binding))
        if bad=='pending':changes['original_pending']=deepcopy(s.c.pending)
        if bad=='packet':changes['original_last_packet']=deepcopy(s.c.last_packet)
        assert s.call(**changes)['training_batch_aborted'] is False
        assert bridge._abort_snapshot(s.c)==before and not bridge._ERRORS and not bridge._COMPLETED


def test_conflicts_late_world_or_second_faint_never_finish_the_abort(monkeypatch):
    for bad in ('same_frame','late','battle','second_faint'):
        s=synthetic_case(monkeypatch);s.call();before=bridge._abort_snapshot(s.c)
        parts=s.packet(382449 if bad=='same_frame' else 382530 if bad=='late' else 382489)
        if bad=='same_frame':parts[0]['conflicting_observation']=True
        if bad=='battle':parts[0]['battle_state']['raw']=1
        if bad=='second_faint':s.current['party'][1]['hp']=0;parts=s.packet(382489)
        assert s.call(parts=parts)['training_batch_aborted'] is False
        assert bridge._abort_snapshot(s.c)==before and s.c.error is None and not bridge._ERRORS


def test_done_abort_does_not_hide_changed_original_controller(monkeypatch):
    for bad in ('baseline_ref','counter','error'):
        s=synthetic_case(monkeypatch);s.call();assert s.call(382489)['training_batch_aborted'] is True
        if bad=='baseline_ref':s.c.baseline=deepcopy(s.c.baseline)
        if bad=='counter':s.c.calls+=1
        if bad=='error':s.c.error='league_training_batch_fainted_party_requires_review'
        assert bridge._active() is None and not bridge._COMPLETED
