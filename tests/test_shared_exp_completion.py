"""已核閉合的最小收尾；全為合成 packet，不開遊戲或模型。"""
from copy import deepcopy
import importlib

from test_shared_experience_training import Harness, command, packet
from laya_pokemon import balanced_training as training


def setup(monkeypatch):
    env=Harness(monkeypatch)
    monkeypatch.setattr(training,'_SHARED_EXPERIENCE_USED_REVIEWS',set())
    monkeypatch.setattr(training,'_SHARED_EXPERIENCE_LAST_COMPLETION',None)
    env.call()
    return env,training._SHARED_EXPERIENCE_PENDING


def closed(env,frame,x=18):
    state=deepcopy(env.state)
    state.update(frame=frame,phase='overworld',visible_text_candidates=[],screen_sha256='c'*64)
    state['location']['x']=x
    state['battle_state'].update(raw=0,active=False,kind='none',observation_frame=frame)
    state['world_path_hint']=dict(direction='left',ledge_jump=False,path_length=1,
        endpoint=[x-1,8],screen_cells_verified=90)
    return dict(step=1,at='2026-10-24T00:45:20+00:00',state=state,action='left')


def capsule(env,owner):
    sig=owner['signature']
    rows=[closed(env,120),closed(env,124,17)]
    cap=dict(schema='red-shared-experience-completed-review-v1',nonce='review-1',
        pending_signature=[sig[0],sig[1],list(sig[2]),sig[3],list(sig[4])],
        last_frame=owner['last_frame'],current_frame=140,closed_frames=[120,124],
        closed_row_sha256=['a'*64,'b'*64],parent_reviewed=True,ledger_closure_verified=True,
        closed_states=rows)
    env.plan['training_completed_battle_review']=cap
    return cap,rows


def test_whirlwind_without_target_command_closes_then_next_wild_gets_new_owner(monkeypatch):
    env,owner=setup(monkeypatch)
    env.state['phase']='battle_dialogue'
    assert env.call() is None and training._SHARED_EXPERIENCE_PENDING is owner
    env.state=closed(env,env.frame+4)['state']
    env.party=env.state['progress']['party']
    assert env.call(packet([' '*20]*18)) is None
    assert training._SHARED_EXPERIENCE_PENDING is None
    assert training._SHARED_EXPERIENCE_LAST_COMPLETION['training_tactic']=='shared_experience_native_battle_completed'
    env.state.update(phase='battle_menu')
    env.state['battle_state'].update(raw=1,active=True,kind='wild')
    out=env.call(command(env.party))
    assert out['objective']=='Move RIGHT.'
    assert training._SHARED_EXPERIENCE_PENDING is not owner


def test_stale_frame_or_sticky_error_does_not_clear_native_completion(monkeypatch):
    env,owner=setup(monkeypatch)
    env.state=closed(env,env.frame)['state']
    assert env.call(packet([' '*20]*18),advance=False) is None
    assert training._SHARED_EXPERIENCE_PENDING is owner
    owner['error']='same_frame_packet_conflict'
    assert env.call(packet([' '*20]*18)) is None
    assert training._SHARED_EXPERIENCE_PENDING is owner
    assert owner['error']=='same_frame_packet_conflict'


def test_unknown_decoder_raw_bool_or_review_cannot_close_native_owner(monkeypatch):
    env,owner=setup(monkeypatch)
    env.state=closed(env,env.frame+4)['state']
    blank=packet([' '*20]*18)
    for field,value in (('read_valid',False),('alignment_verified',False),('window_visible',True)):
        text=deepcopy(blank);text[field]=value
        assert env.call(text) is None and training._SHARED_EXPERIENCE_PENDING is owner
    env.state['battle_state']['raw']=False
    assert env.call(blank) is None and training._SHARED_EXPERIENCE_PENDING is owner
    env.state['battle_state']['raw']=0;env.state['review_reason']='keep_review'
    assert env.call(blank) is None and training._SHARED_EXPERIENCE_PENDING is owner


def test_historical_review_once_and_reload_cannot_clear_a_new_pending(monkeypatch):
    env,owner=setup(monkeypatch);cap,rows=capsule(env,owner)
    before=deepcopy((rows,env.plan))
    assert training.review_completed_shared_experience(rows,env.plan) is None
    assert training._SHARED_EXPERIENCE_PENDING is None
    assert (rows,env.plan)==before
    receipt=deepcopy(training._SHARED_EXPERIENCE_LAST_COMPLETION)
    training._SHARED_EXPERIENCE_PENDING=deepcopy(owner)
    new_owner=training._SHARED_EXPERIENCE_PENDING
    importlib.reload(training)
    assert training.review_completed_shared_experience(rows,env.plan) is None
    assert training._SHARED_EXPERIENCE_PENDING is new_owner
    assert training._SHARED_EXPERIENCE_LAST_COMPLETION==receipt


def test_review_binding_party_or_bad_closure_cannot_clear_owner(monkeypatch):
    env,owner=setup(monkeypatch);cap,rows=capsule(env,owner)
    for change in ('last_frame','party','path','attestation'):
        trial=deepcopy(cap);env.plan['training_completed_battle_review']=trial
        if change=='last_frame':trial['last_frame']-=1
        if change=='party':trial['closed_states'][0]['state']['progress']['party'][0]['exp']+=1
        if change=='path':trial['closed_states'][1]['state']['world_path_hint']['endpoint']=[99,99]
        if change=='attestation':trial['ledger_closure_verified']=False
        out=training.review_completed_shared_experience(trial['closed_states'],env.plan)
        assert out['available_actions']==['wait'] and out['phase']=='campaign_review'
        assert training._SHARED_EXPERIENCE_PENDING is owner
        assert cap['nonce'] not in training._SHARED_EXPERIENCE_USED_REVIEWS


def test_helper_capsule_emits_one_audit_wait_then_normal_next_wild(monkeypatch):
    env,owner=setup(monkeypatch);cap,rows=capsule(env,owner)
    env.frame=136
    out=env.call(command(env.party))
    assert out['available_actions']==['wait']
    assert out['training_tactic']=='shared_experience_reviewed_battle_completed'
    assert training._SHARED_EXPERIENCE_PENDING is None
    out=env.call(command(env.party))
    assert out['objective']=='Move RIGHT.'
    assert training._SHARED_EXPERIENCE_PENDING is not owner
