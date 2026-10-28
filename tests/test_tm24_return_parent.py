"""復核入口須保原TM owner，排除其他owner後才讀新畫面。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from laya_pokemon import campaign_route as route, observation


class ReachedFreshRead(RuntimeError):
    pass


@pytest.mark.parametrize('foreign', [False, True])
def test_only_original_tm_owner_reaches_fresh_read(monkeypatch, foreign):
    b=route.tm24_teaching_bridge;h=route.owned_field_medicine.canonical_sha256
    sid='root-review-parent-fixture';step=dict(id=sid,kind='interact')
    plan=dict(training_job='fixture-job',steps=[step]);pb=SimpleNamespace(frame_count=19073)
    c=b.tm24_teaching.TM24TeachingController(deepcopy(b.tm24_teaching.INTENT))
    c.error='tm24_unknown_or_out_of_stage_source_page';c.last_frame=19073
    c.last_packet=(None,)*7;packet=c.last_packet
    cap=deepcopy(route._TM24_RETURN_REVIEW_CAPSULE)
    cap.update(original_step_id=sid,original_step_sha256=h(step),
               training_job_sha256=h(plan['training_job']))
    monkeypatch.setattr(route,'_TM24_RETURN_REVIEW_CAPSULE',cap)
    monkeypatch.setattr(route,'_TM24_RETURN_PLAN_CANONICAL_SHA256',h(plan))
    monkeypatch.setattr(b.tm24_teaching,'NATIVE_RETURN_REVIEW',deepcopy(cap))
    monkeypatch.setattr(b,'_CONTROLLERS',{sid:c})
    monkeypatch.setattr(b,'_OWNERS',{sid:dict(pyboy=pb,controller=c)})
    monkeypatch.setattr(b,'_BINDINGS',{sid:dict(step=step,job=plan['training_job'])})
    monkeypatch.setattr(b,'_registry_problem',lambda:None)
    monkeypatch.setattr(b,'_active',lambda:{sid})
    monkeypatch.setattr(b,'_known_controller',lambda obj:obj is c)
    monkeypatch.setattr(route,'_LEAGUE_FIELDS',(b,))
    monkeypatch.setattr(route.owned_field_medicine,'_active',lambda:set())
    peers={key:set() for key in route.owned_field_medicine.PEER_NAMES}
    peers['tm24_teaching']={sid}
    if foreign:peers['victory_later_boulder']={'other-owner'}
    monkeypatch.setattr(route,'_field_medicine_peers',lambda:peers)
    def fresh(_):raise ReachedFreshRead()
    monkeypatch.setattr(observation,'read_visible_text',fresh)
    state=dict(frame=19073,location=deepcopy(cap['source_location']))
    if foreign:
        result,_=route._tm24_return_review_context(pb,state,plan,sid,['a'])
        assert result['phase']=='campaign_review'
    else:
        with pytest.raises(ReachedFreshRead):
            route._tm24_return_review_context(pb,state,plan,sid,['a'])
    assert c.error=='tm24_unknown_or_out_of_stage_source_page'
    assert c.last_packet is packet and not hasattr(c,'native_return_review_history')
