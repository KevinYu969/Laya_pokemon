"""Canonical self-contained tests; no live plan, ledger, audit or temp access."""
from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/'src/laya_pokemon/league_training_supervisor.py'
spec=importlib.util.spec_from_file_location('_training_plan_share_retry_test',SOURCE)
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
assert Path(s.__file__).resolve()==SOURCE.resolve()
h=importlib.import_module('test_league_training_supervisor')
assert Path(h.__file__).resolve()==(ROOT/'tests/test_league_training_supervisor.py').resolve()


@pytest.fixture(autouse=True)
def fixture_module(monkeypatch):monkeypatch.setattr(h,'s',s)


class OwnedTemp:
    def __init__(self):self.data=b'exact owned proposal';self.reads=0
    def read_bytes(self):self.reads+=1;return self.data


def test_permission_retry_rechecks_owned_bytes_and_full_final_check_before_each_replace(monkeypatch):
    temp=OwnedTemp();events=[]
    def check():events.append('full-lock-snapshot-deadline-control-check')
    def replace(source,target):
        assert source is temp and target==s.PLAN
        events.append('replace')
        if events.count('replace')<3:raise PermissionError(5,'synthetic sharing violation')
    monkeypatch.setattr(s.os,'replace',replace);monkeypatch.setattr(s.time,'sleep',lambda seconds:events.append(('sleep',seconds)))
    s._replace_owned_plan(temp,temp.data,check)
    assert temp.reads==3 and events==['full-lock-snapshot-deadline-control-check','replace',('sleep',.05),
        'full-lock-snapshot-deadline-control-check','replace',('sleep',.05),
        'full-lock-snapshot-deadline-control-check','replace']


def test_eight_total_attempts_rethrow_same_original_permission_error_and_leave_temp(monkeypatch):
    temp=OwnedTemp();checks=[];attempts=[];sleeps=[];error=PermissionError(5,'same failure')
    def replace(*args):attempts.append(args);raise error
    monkeypatch.setattr(s.os,'replace',replace);monkeypatch.setattr(s.time,'sleep',sleeps.append)
    with pytest.raises(PermissionError) as caught:s._replace_owned_plan(temp,temp.data,lambda:checks.append(True))
    assert caught.value is error and len(attempts)==len(checks)==temp.reads==8 and sleeps==[.05]*7
    assert temp.data==b'exact owned proposal'


def test_only_replace_permission_error_is_retried(monkeypatch):
    temp=OwnedTemp();calls=[]
    monkeypatch.setattr(s.time,'sleep',lambda _:pytest.fail('must not retry'))
    def other_error(*args):calls.append(args);raise OSError(123,'not permission')
    monkeypatch.setattr(s.os,'replace',other_error)
    with pytest.raises(OSError,match='not permission'):s._replace_owned_plan(temp,temp.data,lambda:None)
    assert len(calls)==1
    def failed_check():raise PermissionError(5,'cannot reprove lock/snapshot')
    with pytest.raises(PermissionError,match='cannot reprove'):s._replace_owned_plan(temp,temp.data,failed_check)
    assert len(calls)==1


def test_changed_lock_snapshot_or_deadline_cancels_retry_before_second_replace(monkeypatch):
    temp=OwnedTemp();calls=[];checks=[]
    def replace(*args):calls.append(args);raise PermissionError(5,'sharing')
    def check():
        checks.append(True)
        if len(checks)>1:raise s.ReviewRequired('snapshot_or_deadline_changed')
    monkeypatch.setattr(s.os,'replace',replace);monkeypatch.setattr(s.time,'sleep',lambda _:None)
    with pytest.raises(s.ReviewRequired,match='snapshot_or_deadline'):s._replace_owned_plan(temp,temp.data,check)
    assert len(checks)==2 and len(calls)==temp.reads==1


def test_changed_owned_temp_bytes_cancel_retry_before_second_replace(monkeypatch):
    temp=OwnedTemp();original=temp.data;calls=[]
    def replace(*args):calls.append(args);temp.data=b'changed';raise PermissionError(5,'sharing')
    monkeypatch.setattr(s.os,'replace',replace);monkeypatch.setattr(s.time,'sleep',lambda _:None)
    with pytest.raises(s.ReviewRequired,match='owned_plan_temp_changed'):s._replace_owned_plan(temp,original,lambda:None)
    assert len(calls)==1 and temp.reads==2 and temp.data==b'changed'


def reviewed_rows(monkeypatch):
    snapshot,budget,cal=h.start();out=s.propose(snapshot,budget,cal,2001.)
    seed=dict(kind='seed',job=s.JOB,budget=deepcopy(budget))
    reserve=dict(kind='reserve',job=s.JOB,plan_sha256=out['budget']['expected_plan_sha256'])
    error=dict(kind='error',job=s.JOB,reason='[WinError 5] synthetic plan sharing violation')
    rows=[seed,reserve,error]
    review=dict(kind='reviewed_commit_after_plan_share_violation',job=s.JOB,winerror=5,
        error_sha256=s.canonical_sha(error),ledger_prefix_sha256=s.canonical_sha(rows),
        previous_budget_sha256=s.canonical_sha(budget),previous_expected_plan_sha256=budget['expected_plan_sha256'],
        reserve_plan_sha256=reserve['plan_sha256'],candidate_budget_sha256=s.canonical_sha(out['budget']),audit_sha256='a'*64)
    monkeypatch.setattr(s,'PLAN_SHARE_REVIEW_SHA256',s.canonical_sha(review))
    rows += [review,dict(kind='commit',job=s.JOB,budget=deepcopy(out['budget']))]
    return rows,out['budget']


def test_exact_root_review_keeps_error_and_completes_only_same_reserve_without_refund(monkeypatch):
    rows,candidate=reviewed_rows(monkeypatch);original=deepcopy(rows)
    restored=s.history_budget(rows,2100.)
    assert restored==candidate and rows==original and rows[2]['kind']=='error'
    seed=rows[0]['budget']
    assert restored['started_wall']==seed['started_wall'] and restored['deadline_wall']==seed['deadline_wall']
    assert restored['max_seconds']==14400 and restored['max_outings']==1000
    assert restored['appends']==seed['appends']+1 and restored['outings']==seed['outings']+1


def test_unreviewed_changed_error_wrong_pin_or_changed_candidate_remain_sticky(monkeypatch):
    rows,_=reviewed_rows(monkeypatch)
    for kind in ('no_review','reviewed_by_only','other_error','candidate','wrong_reserve'):
        bad=deepcopy(rows)
        if kind=='no_review':bad.pop(3)
        if kind=='reviewed_by_only':bad[3]={'kind':'reviewed_commit_after_plan_share_violation','job':s.JOB,'reviewed_by':'root'}
        if kind=='other_error':bad[2]['reason']='other error'
        if kind=='candidate':bad[4]['budget']['last_wall']+=1
        if kind=='wrong_reserve':bad[1]['plan_sha256']='e'*64
        with pytest.raises(s.ReviewRequired,match='sticky_job_error'):s.history_budget(bad,2100.)


def test_prefix_replay_incomplete_commit_and_standalone_review_are_rejected(monkeypatch):
    rows,_=reviewed_rows(monkeypatch)
    bad=deepcopy(rows);bad[0]['budget']['last_wall']+=.01
    with pytest.raises(s.ReviewRequired,match='sticky_job_error'):s.history_budget(bad,2100.)
    with pytest.raises(s.ReviewRequired,match='sticky_job_error'):s.history_budget(rows[:-1],2100.)
    with pytest.raises(s.ReviewRequired,match='unbound_plan_share_review'):s.history_budget([rows[0],rows[3]],2100.)
    with pytest.raises(s.ReviewRequired,match='unbound_plan_share_review'):s.history_budget(rows+[rows[3]],2100.)
