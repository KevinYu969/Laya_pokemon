"""Exact-path wrapper tests plus complete real pure-controller integration; no game IO."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import pytest


TEST_DIR = Path(__file__).resolve().parent
if TEST_DIR.name == "staged-fly-viridian-bridge-20261025" and TEST_DIR.parent.name == ".local":
    ROOT = TEST_DIR.parent.parent
    BRIDGE = ROOT / ".local/staged-fly-viridian-bridge-20261025/fly_viridian_bridge.py"
    PURE_TEST = ROOT / ".local/staged-fly-viridian-20261025/test_fly_viridian.py"
elif TEST_DIR.name == "tests":
    ROOT = TEST_DIR.parent
    BRIDGE = ROOT / "src/laya_pokemon/fly_viridian_bridge.py"
    PURE_TEST = ROOT / "tests/test_fly_viridian.py"
else:
    raise RuntimeError("Only exact staged or formal bridge test path is supported")


def load(name, path):
    resolved = path.resolve(strict=True)
    spec = importlib.util.spec_from_file_location(name, resolved)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert Path(module.__file__).resolve() == resolved
    return module


bridge = load("laya_pokemon._bridge_exact_tests", BRIDGE)
helper = load("laya_pokemon._fly_viridian_pure_test_helpers", PURE_TEST)


def plan():
    return dict(training_job="fly-cinnabar-viridian-20261025", steps=[dict(
        id="fly-viridian", kind="interact", mechanic="fly_viridian", map_id=8,
        target=[18, 4], fly_intent=deepcopy(bridge.fly_viridian.FLY_VIRIDIAN_INTENT)),
        dict(id="after-flight", kind="move", map_id=1, target=[23,25])])


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for name, value in (("_CONTROLLERS", {}), ("_BINDINGS", {}), ("_COMPLETED", set())):
        monkeypatch.setattr(bridge, name, value)


@pytest.fixture
def stub(monkeypatch):
    class Controller:
        def __init__(self, intent):
            self.intent=deepcopy(intent);self.baseline={"untouched":True};self.pending={"true":True}
            self.started=5.;self.last_now=6.;self.calls=9;self.waits=4;self.error=None
            self.result=dict(phase="fly_viridian_menu",objective="Wait.",available_actions=["wait"],fly_viridian_complete=False)
            self.kwargs=None
        def context(self,text,progress,**kwargs):
            self.kwargs=kwargs
            return deepcopy(self.result)
    monkeypatch.setattr(bridge.fly_viridian,"FlyViridianController",Controller)
    source_plan=plan()
    state=dict(frame=1739000,location=dict(map_id=8,x=18,y=4),progress={},battle_state={})
    signal=dict(read_valid=True,ram_read_valid=True,observation_frame=state["frame"],location=deepcopy(state["location"]))
    monkeypatch.setattr(bridge.fly_viridian,"read_fly_observation",lambda *args:deepcopy(signal))
    return SimpleNamespace(plan=source_plan,state=state,signal=signal,pb=object(),step=source_plan["steps"][0])


def call(e,step="fly-viridian",previous=("a","wait"),window=False):
    return bridge.context(e.pb,e.state,e.plan,step,helper.packet(window=window),
                          helper.grid(e.state["location"],e.state["frame"]),previous)


def test_fixed_api_retains_owner_controller_and_true_previous_at_destination(stub):
    call(stub,previous=("down","a"))
    c=bridge._CONTROLLERS["fly-viridian"];baseline=c.baseline;pending=c.pending
    assert c.kwargs["previous"] == ("down","a") and c.kwargs["frame"]==1739000
    stub.state.update(frame=1739001,location=dict(map_id=1,x=23,y=26))
    stub.signal.update(observation_frame=1739001,location=deepcopy(stub.state["location"]))
    result,next_id=call(stub)
    assert next_id=="fly-viridian" and not bridge._COMPLETED
    assert bridge._CONTROLLERS["fly-viridian"] is c and c.baseline is baseline and c.pending is pending
    assert (c.started,c.calls,c.waits)==(5.,9,4)
    c.result["fly_viridian_complete"]=True
    result,next_id=call(stub)
    assert result["field_move_complete"] is True and result["field_move_kind"]=="fly-viridian"
    assert next_id=="after-flight" and bridge._COMPLETED=={"fly-viridian"}


@pytest.mark.parametrize("key,value",[("event","beat_blaine"),("item",197),("badge",64),
    ("terminal",False),("next_map",1),("await_script_event",False),("kind","move"),
    ("map_id",True),("map_id",1),("target",[18,True]),("target",[18,5])])
def test_explicit_source_rejects_all_generic_completion_fields(stub,key,value):
    stub.step[key]=value
    result,_=call(stub)
    assert result["review_reason"]=="fly_viridian_explicit_intent_unverified"
    assert not bridge._CONTROLLERS and not bridge._BINDINGS


@pytest.mark.parametrize("change",[
    lambda i:i.update(map_id=27),lambda i:i.update(destination_map=0),
    lambda i:i.update(species=True),lambda i:i.update(extra="foreign"),
    lambda i:i.pop("landing_x"),
])
def test_exact_intent_no_boolean_or_foreign_extra_keys(stub,change):
    change(stub.step["fly_intent"])
    assert call(stub)[0]["review_reason"]=="fly_viridian_explicit_intent_unverified"
    assert not bridge._CONTROLLERS


def test_initial_native_closed_world_and_signal_required_without_binding(stub):
    assert call(stub,window=True)[0]["review_reason"]=="fly_viridian_initial_closed_world_required"
    stub.signal["read_valid"]=False
    assert call(stub)[0]["review_reason"]=="fly_viridian_initial_signal_unverified"
    assert not bridge._BINDINGS


def test_unbound_normal_navigation_returns_none_and_does_not_claim_landing(stub):
    stub.state["location"]=dict(map_id=8,x=17,y=4)
    assert call(stub) is None and not bridge._CONTROLLERS
    stub.state["location"]=dict(map_id=1,x=23,y=26)
    assert call(stub) is None and not bridge._COMPLETED


def test_any_active_owner_keeps_applies_and_blocks_owner_change(stub):
    call(stub)
    assert bridge.applies("other",None)
    assert call(stub,step="other")[0]["review_reason"]=="fly_viridian_owner_changed"
    stub.step.pop("mechanic")
    assert call(stub)[0]["review_reason"]=="fly_viridian_intent_changed"


def test_job_or_step_binding_change_is_rejected_without_credit_reset(stub):
    call(stub);c=bridge._CONTROLLERS["fly-viridian"]
    stub.plan["training_job"]="other"
    assert call(stub)[0]["review_reason"]=="fly_viridian_intent_or_owner_changed"
    assert c.started==5. and c.calls==9 and c.waits==4


def test_missing_original_controller_or_binding_is_not_reconstructed(stub):
    call(stub);c=bridge._CONTROLLERS.pop("fly-viridian")
    assert call(stub)[0]["review_reason"]=="fly_viridian_original_controller_missing"
    bridge._CONTROLLERS["fly-viridian"]=c;bridge._BINDINGS.clear()
    assert call(stub)[0]["review_reason"]=="fly_viridian_original_binding_missing"


@pytest.mark.parametrize("value",[1,"true",None,False])
def test_only_boolean_true_controller_receipt_can_complete(stub,value):
    call(stub);bridge._CONTROLLERS["fly-viridian"].result["fly_viridian_complete"]=value
    result,next_id=call(stub)
    assert "field_move_complete" not in result and next_id=="fly-viridian" and not bridge._COMPLETED


@pytest.mark.parametrize("change",[
    lambda e:e.signal.update(read_valid=False),
    lambda e:e.signal.update(observation_frame=True),
    lambda e:e.signal.update(location=dict(map_id=1,x=23,y=25)),
])
def test_completion_receipt_still_requires_matching_native_landing_signal(stub,change):
    call(stub);bridge._CONTROLLERS["fly-viridian"].result["fly_viridian_complete"]=True
    stub.state["location"]=dict(map_id=1,x=23,y=26)
    stub.signal["location"]=deepcopy(stub.state["location"])
    change(stub)
    assert call(stub)[0]["review_reason"]=="fly_viridian_completion_location_or_signal_unverified"
    assert not bridge._COMPLETED


def test_false_completion_at_source_does_not_advance(stub):
    call(stub);bridge._CONTROLLERS["fly-viridian"].result["fly_viridian_complete"]=True
    assert call(stub)[0]["review_reason"]=="fly_viridian_completion_location_or_signal_unverified"
    assert not bridge._COMPLETED


def test_bad_plan_duplicate_step_or_nan_owner_fail_before_binding(stub):
    stub.plan["steps"].append(deepcopy(stub.step))
    assert call(stub)[0]["review_reason"]=="fly_viridian_plan_unverified"
    stub.plan["steps"].pop();stub.plan["training_job"]=float("nan")
    assert call(stub)[0]["review_reason"]=="fly_viridian_owner_unverified"
    assert not bridge._CONTROLLERS


class IntegratedSession(helper.Session):
    """Synthetic native pixels/progress, with actual pure controller/getter and real SDK anchors."""
    def __init__(self):
        super().__init__();self.plan=plan();self.last_next=None
    def call(self,rows=None,*,ready=False,window=True,raw=None,same=False,previous=None,
             location=None,signal_change=None,text_change=None,grid_change=None):
        assert signal_change is None  # Integration never substitutes the source getter/profile.
        if not same:self.pb.frame_count+=1;self.now+=.05
        loc=deepcopy(location or bridge.fly_viridian.START)
        self.pb.memory.values.update({0xD35E:loc["map_id"],0xD361:loc["y"],0xD362:loc["x"],0xFF40:0xa1 if window else 0x81})
        self.pb.screen.tilemap_position_list=[[0,0,0,0 if window else 144] for _ in range(144)]
        raw=[0x7f]*360 if raw is None else raw
        self.pb.tilemap_background.ids=[((b^128)-128)+256 for b in raw]
        text=helper.packet(rows,window)
        if text_change:text_change(text)
        g=helper.grid(loc,self.pb.frame_count)
        if grid_change:grid_change(g)
        state=dict(frame=self.pb.frame_count,location=loc,progress=self.p,
            battle_state=dict(kind="none",active=False,raw=0,observation_frame=self.pb.frame_count))
        result,self.last_next=bridge.context(self.pb,state,self.plan,"fly-viridian",text,g,
                                            self.previous if previous is None else previous)
        return result


def test_real_pure_full_ordered_flight_through_wrapper_and_hot_reload_preserves_owner():
    s=IntegratedSession();before=deepcopy(s.p)
    s.to_viridian()
    c=bridge._CONTROLLERS["fly-viridian"];baseline=c.baseline;pending=c.pending
    spent=(c.started,c.calls,c.waits)
    spec=importlib.util.spec_from_file_location(bridge.__name__,BRIDGE.resolve())
    spec.loader.exec_module(bridge)  # Same module dictionary, equivalent to hot reload retention.
    assert bridge._CONTROLLERS["fly-viridian"] is c and c.baseline is baseline and c.pending is pending
    assert (c.started,c.calls,c.waits)==spent
    rows=[list(r) for r in bridge.fly_viridian._MAP_ROWS]
    assert s.call(rows,raw=list(bridge.fly_viridian.VIRIDIAN_RAW))["available_actions"]==["wait"]
    s.previous=["wait"];s.expect(rows,"a",raw=list(bridge.fly_viridian.VIRIDIAN_RAW))
    s.finish()
    assert s.last_next=="after-flight" and bridge._COMPLETED=={"fly-viridian"}
    assert s.p==before and c.baseline is baseline and c.pending is not None
    assert s.pb.memory.reads.count(0xD70B)>2


def test_real_pure_error_stays_sticky_and_bridge_does_not_rebuild_or_refund():
    s=IntegratedSession();s.expect(helper.canvas(),"start",ready=True,window=False)
    c=bridge._CONTROLLERS["fly-viridian"];started=c.started
    result=s.call(helper.start(2),previous=[])
    assert result["phase"]=="campaign_review";error=c.error;calls=c.calls
    result=s.call(helper.start(2),previous=["start"])
    assert result["review_reason"]==error and c.error==error
    assert bridge._CONTROLLERS["fly-viridian"] is c and c.started==started and c.calls==calls
    assert not bridge._COMPLETED
