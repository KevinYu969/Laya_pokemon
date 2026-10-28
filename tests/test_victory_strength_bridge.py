"""Real frozen pure/getter integration only; no fake controller or getter substitutions."""
from copy import deepcopy
from pathlib import Path
import importlib.util
import pytest

HERE=Path(__file__).resolve().parent
if HERE.name=="staged-victory-strength-floors-20261025" and HERE.parent.name==".local":
    ROOT=HERE.parent.parent
    BRIDGE=ROOT/".local/staged-victory-strength-floors-20261025/victory_strength_bridge.py"
    PURE_TEST=ROOT/".local/staged-victory-strength-floors-20261025/test_victory_strength.py"
elif HERE.name=="tests":
    ROOT=HERE.parent
    BRIDGE=ROOT/"src/laya_pokemon/victory_strength_bridge.py"
    PURE_TEST=ROOT/"tests/test_victory_strength.py"
else:raise RuntimeError("Only exact staged or formal Strength bridge test path is supported")


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path.resolve(strict=True))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert Path(module.__file__).resolve()==path.resolve()
    return module


bridge=load("laya_pokemon._exact_victory_strength_bridge_tests",BRIDGE)
helper=load("laya_pokemon._exact_victory_strength_test_helpers",PURE_TEST)


def plan(key="1f_entry"):
    return dict(training_job="victory-strength-activation-20261025",steps=[dict(
        id="victory-strength",kind="interact",mechanic="victory_strength",map_id=bridge.victory_strength.INTENTS[key]["map_id"],
        target=[bridge.victory_strength.INTENTS[key]["player_x"],bridge.victory_strength.INTENTS[key]["player_y"]],strength_intent=deepcopy(bridge.victory_strength.INTENTS[key])),
        dict(id="after-strength",kind="move",map_id=108,target=[8,15])])


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for name,value in (("_CONTROLLERS",{}),("_BINDINGS",{}),("_COMPLETED",set())):
        monkeypatch.setattr(bridge,name,value)


class BridgeSession(helper.Session):
    """Only the native read surface is synthetic; source getter/controller/SDK stay real."""
    def __init__(self,key="1f_entry"):
        super().__init__(key);self.plan=plan(key);self.step_id="victory-strength"
        self.last_next=None;self.last_state=None;self.last_result=None
    def call(self,rows=None,*,window=True,ready=False,same=False,previous=None,
             signal_change=None,grid_change=None,text_change=None,location=None,state_change=None):
        assert signal_change is None
        if not same:self.pb.frame_count+=1;self.now+=.05
        loc=deepcopy(location or self.location)
        self.pb.memory.values.update({0xD35E:loc["map_id"],0xD361:loc["y"],0xD362:loc["x"]})
        text=helper.packet(rows,window)
        if text_change:text_change(text)
        g=helper.grid(self.pb.frame_count,self.key)
        if grid_change:grid_change(g)
        state=dict(frame=self.pb.frame_count,location=loc,progress=self.p,
            battle_state=dict(kind="none",active=False,raw=0,observation_frame=self.pb.frame_count))
        if state_change:state_change(state)
        self.last_state=deepcopy(state)
        result=bridge.context(self.pb,state,self.plan,self.step_id,text,g,
                              self.previous if previous is None else previous)
        if result is None:self.last_result=self.last_next=None;return None
        self.last_result,self.last_next=result
        if self.step_id in bridge._CONTROLLERS:self.c=bridge._CONTROLLERS[self.step_id]
        return self.last_result


def review(out,reason=None):
    helper.review(out)
    if reason:assert out["review_reason"]=="victory_strength_"+reason


def test_real_complete_activation_with_both_source_messages_and_two_fresh_world_frames():
    s=BridgeSession();before=deepcopy(s.p);s.confirm();c=s.c;baseline=c.baseline
    assert c.strength_selected and c.seen_used_full and not c.prompt_ack
    assert s.last_next=="victory-strength" and not bridge._COMPLETED
    out=s.finish()
    assert out["field_move_complete"] is True and out["field_move_kind"]=="victory-strength"
    assert s.last_next=="after-strength" and bridge._COMPLETED=={"victory-strength"}
    assert s.c is c and c.baseline is baseline and s.p==before
    assert s.pb.memory.reads.count(0xD728)>2


def test_real_automatic_first_page_can_be_unsampled_and_receipt_reports_that():
    s=BridgeSession();s.confirm(see_used=False);s.finish()
    assert not s.c.seen_used_full and s.c.seen_can_prompt and s.c.prompt_ack


def test_real_dynamic_snorlax_slot_injured_hp_bag_and_money_preserved():
    s=BridgeSession();s.p["party"][0],s.p["party"][1]=s.p["party"][1],s.p["party"][0]
    s.p["party"][0].update(level=50,hp=50,exp=125000)
    s.p["money"]=3;s.p["inventory"]=[];before=deepcopy(s.p)
    s.confirm();s.finish();assert s.c.target_index==0 and s.p==before


@pytest.mark.parametrize("key,value",[("event","got_hm04"),("item",199),("badge",8),
    ("terminal",False),("next_map",194),("await_script_event",False),("kind","move"),
    ("map_id",1),("map_id",True),("target",[8,17]),("target",[8,True])])
def test_no_generic_completion_or_changed_fixed_stance_can_bind(key,value):
    s=BridgeSession();s.plan["steps"][0][key]=value
    review(s.call(helper.canvas(),window=False,ready=True),"explicit_intent_unverified")
    assert not bridge._BINDINGS and not bridge._CONTROLLERS


@pytest.mark.parametrize("change",[
    lambda i:i.update(species=7),lambda i:i.update(move=57),lambda i:i.update(player_y=17),
    lambda i:i.update(map_id=True),lambda i:i.update(extra="foreign"),lambda i:i.pop("move"),
])
def test_fixed_strength_intent_cannot_be_generalized(change):
    s=BridgeSession();change(s.plan["steps"][0]["strength_intent"])
    review(s.call(helper.canvas(),window=False,ready=True),"explicit_intent_unverified")
    assert not bridge._CONTROLLERS


def test_unbound_navigation_or_a_different_floor_cannot_claim_activation():
    s=BridgeSession()
    assert s.call(helper.canvas(),window=False,ready=True,location=dict(map_id=108,x=8,y=17)) is None
    assert s.call(helper.canvas(),window=False,ready=True,location=dict(map_id=194,x=0,y=8)) is None
    assert not bridge._BINDINGS and not bridge._COMPLETED


def test_legacy_or_visible_menu_cannot_bind_initial_native_world():
    s=BridgeSession()
    review(s.call(helper.start(4)),"initial_closed_world_required")
    review(s.call(helper.canvas(),window=False,ready=True,text_change=lambda t:t.pop("profile")),"initial_closed_world_required")
    assert not bridge._CONTROLLERS


def test_real_unknown_flag_byte_never_binds_and_is_not_coerced_to_false():
    s=BridgeSession();s.pb.memory.values[0xD728]=False
    review(s.call(helper.canvas(),window=False,ready=True),"initial_signal_unverified")
    assert not bridge._BINDINGS


def test_real_already_active_source_flag_is_not_this_transaction_completion():
    s=BridgeSession();s.pb.memory.values[0xD728]=65
    review(s.call(helper.canvas(),window=False,ready=True),"initial_closed_victory_road_unverified")
    assert not bridge._COMPLETED and "field_move_complete" not in s.last_result


def test_active_owner_intercepts_other_step_and_removed_mechanic():
    s=BridgeSession();s.expect(helper.canvas(),"start",window=False,ready=True)
    assert bridge.applies("foreign-step",None)
    s.step_id="foreign-step";review(s.call(helper.canvas(),window=False),"owner_changed")
    s.step_id="victory-strength";s.plan["steps"][0].pop("mechanic")
    review(s.call(helper.canvas(),window=False),"intent_changed")


def test_canonical_job_or_step_binding_changes_do_not_refund_clock_or_calls():
    s=BridgeSession();s.expect(helper.canvas(),"start",window=False,ready=True)
    c=s.c;baseline=c.baseline;pending=c.pending;spent=(c.started,c.calls,c.waits)
    s.plan["training_job"]="different"
    review(s.call(helper.canvas(),window=False),"intent_or_owner_changed")
    assert s.c is c and c.baseline is baseline and c.pending is pending
    assert (c.started,c.calls,c.waits)==spent


def test_missing_original_controller_or_binding_cannot_restart_budget():
    s=BridgeSession();s.expect(helper.canvas(),"start",window=False,ready=True)
    c=bridge._CONTROLLERS.pop("victory-strength")
    review(s.call(helper.canvas(),window=False),"original_controller_missing")
    bridge._CONTROLLERS["victory-strength"]=c;bridge._BINDINGS.clear()
    review(s.call(helper.canvas(),window=False),"original_binding_missing")


def test_flag_true_and_closed_location_without_final_prompt_receipt_cannot_advance():
    s=BridgeSession();s.to_messages();s.pb.memory.values[0xD728]=65
    review(s.call(helper.canvas(),window=False,ready=True))
    assert not s.c.prompt_ack and not bridge._COMPLETED and "field_move_complete" not in s.last_result


def test_prompt_offer_needs_true_previous_and_wait_reoffers_same_pending():
    s=BridgeSession();s.confirm();c=s.c;pending=c.pending;baseline=c.baseline
    started=c.started;calls=c.calls;s.previous=["wait"]
    out=s.call(helper.message(s.p,"can",True))
    assert out["available_actions"]==["a","wait"] and not c.prompt_ack
    assert c.pending is pending and c.baseline is baseline and c.started==started and c.calls==calls+1
    s.previous=["a"];s.finish();assert bridge._COMPLETED=={"victory-strength"}


def test_final_prompt_offer_without_actual_a_then_blank_is_sticky_error():
    s=BridgeSession();s.confirm()
    review(s.call(helper.canvas(),window=False,ready=True,previous=["wait"]))
    error=s.c.error;started=s.c.started;calls=s.c.calls
    review(s.call(helper.canvas(),window=False,ready=True,previous=["a"]))
    assert s.c.error==error and s.c.started==started and s.c.calls==calls
    assert not bridge._COMPLETED


def test_hot_reload_keeps_original_pending_baseline_error_and_spent_budget():
    s=BridgeSession();s.confirm();c=s.c;baseline=c.baseline;pending=c.pending
    spent=(c.started,c.calls,c.waits)
    spec=importlib.util.spec_from_file_location(bridge.__name__,BRIDGE.resolve())
    spec.loader.exec_module(bridge)
    assert bridge._CONTROLLERS["victory-strength"] is c and c.baseline is baseline and c.pending is pending
    assert (c.started,c.calls,c.waits)==spent and c.error is None
    s.previous=["wait"]
    assert s.call(helper.message(s.p,"can",True))["available_actions"]==["a","wait"]
    assert s.c is c and c.pending is pending and c.started==spent[0]
    s.previous=["a"];s.finish()
    assert s.c is c and s.last_next=="after-strength"


def test_hot_reload_also_preserves_sticky_pure_error_without_reconstruction():
    s=BridgeSession();s.expect(helper.canvas(),"start",window=False,ready=True)
    review(s.call(helper.start(2),previous=[]));c=s.c;error=c.error;spent=(c.started,c.calls,c.waits)
    spec=importlib.util.spec_from_file_location(bridge.__name__,BRIDGE.resolve())
    spec.loader.exec_module(bridge)
    review(s.call(helper.start(2),previous=["start"]))
    assert s.c is c and c.error==error and (c.started,c.calls,c.waits)==spent


def test_clock_or_call_budget_exhaustion_cannot_be_recredited_by_bridge():
    s=BridgeSession();s.expect(helper.canvas(),"start",window=False,ready=True)
    c=s.c;c.calls=240;started=c.started
    review(s.call(helper.start(2)),"budget_exhausted")
    assert c.calls==241 and c.started==started and not bridge._COMPLETED


@pytest.mark.parametrize("key,value",[("frame",True),("frame",-1),("location",None)])
def test_malformed_outer_frame_or_location_rejects_before_getter_binding(key,value):
    s=BridgeSession();out=s.call(helper.canvas(),window=False,ready=True,state_change=lambda state:state.update({key:value}))
    review(out);assert not bridge._BINDINGS


def test_duplicate_plan_ids_or_nan_owner_are_rejected_before_native_action():
    s=BridgeSession();s.plan["steps"].append(deepcopy(s.plan["steps"][0]))
    review(s.call(helper.canvas(),window=False,ready=True),"plan_unverified")
    s.plan["steps"].pop();s.plan["training_job"]=float("nan")
    review(s.call(helper.canvas(),window=False,ready=True),"owner_unverified")
    assert not bridge._CONTROLLERS


def test_actual_pure_error_on_cross_floor_never_leaks_owner_or_completes():
    s=BridgeSession();s.confirm()
    review(s.call(helper.canvas(),window=False,ready=True,location=dict(map_id=194,x=0,y=8)))
    assert bridge.applies("foreign",None) and not bridge._COMPLETED


def test_every_bridge_nonwait_has_two_choices_and_no_input_io_occurs():
    s=BridgeSession();out=s.call(helper.canvas(),window=False,ready=True)
    assert out["available_actions"]==["start","wait"] and len(out["available_actions"])==2
    with pytest.raises(AssertionError):s.pb.tick()
    with pytest.raises(AssertionError):s.pb.memory[0xD728]=65


def test_exact_source_loader_uses_frozen_real_pure_and_getter_file():
    from hashlib import sha256
    file=Path(bridge.victory_strength.__file__).resolve()
    expected=(ROOT/"src/laya_pokemon/victory_strength.py" if HERE.name=="tests"
              else ROOT/".local/staged-victory-strength-floors-20261025/victory_strength.py").resolve()
    assert file==expected
    assert sha256(file.read_bytes()).hexdigest() in bridge.PURE_SHA256S
