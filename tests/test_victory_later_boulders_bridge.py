"""Frozen real four-case pure/getter/SDK integration; no gameplay or fake success."""
from copy import deepcopy
from pathlib import Path
import importlib.util
import pytest

HERE=Path(__file__).resolve().parent
if HERE.name=="staged-victory-later-boulders-bridge-20261025" and HERE.parent.name==".local":
    ROOT=HERE.parent.parent;BRIDGE=HERE/"victory_later_boulders_bridge.py"
    PURE_TEST=HERE/"test_victory_later_boulders.py"
elif HERE.name=="tests":
    ROOT=HERE.parent;BRIDGE=ROOT/"src/laya_pokemon/victory_later_boulders_bridge.py"
    PURE_TEST=ROOT/"tests/test_victory_later_boulders.py"
else:raise RuntimeError("Only exact later-boulder bridge stage or formal tests supported")

def load(name,path):
    path=path.resolve(strict=True);spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert Path(module.__file__).resolve()==path;return module

bridge=load("laya_pokemon._exact_later_boulder_bridge_tests",BRIDGE)
helper=load("laya_pokemon._exact_later_boulder_bridge_helpers",PURE_TEST)
ORDER=helper.ORDER

def plan(key):
    c=bridge.boulder.CASES[key]
    return dict(training_job="league-later-boulders-20261025",steps=[dict(id="later-"+key,
        kind="interact",mechanic="victory_later_boulder",map_id=c["map_id"],
        target=deepcopy(c["start_player"]),boulder_case=key),
        dict(id="after-"+key,kind="move",map_id=c["map_id"],target=deepcopy(c["start_player"]))])

@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for name,value in (("_CONTROLLERS",{}),("_BINDINGS",{}),("_COMPLETED",set())):
        monkeypatch.setattr(bridge,name,value)
    from laya_pokemon import battle
    for name in ("_no_pp_switch","_fixed_damage_risk"):monkeypatch.setattr(battle,name,None)

class BridgeSession(helper.Session):
    def __init__(self,key="2f_switch1"):
        super().__init__(key);self.plan=plan(key);self.step_id="later-"+key
        self.last_next=self.last_result=self.last_state=None
    def call(self,*,same=False,previous=None,raw=0,kind=None,active=None,ready=True,window=False,
             no_grid=False,signal_change=None,grid_change=None,text_change=None,now=None,
             state_change=None,battle_context=True):
        assert signal_change is None and now is None
        if not same:self.pb.frame_count+=1;self.now+=.05
        f=self.pb.frame_count;m=self.pb.memory.values;m[0xD057]=raw
        text=dict(profile=helper.TEXT_PROFILE,read_valid=True,alignment_verified=True,read_error=None,
            cells=[[" "]*20 for _ in range(18)],window_visible=window,observation_frame=f,lines=[],line_rows=[])
        if raw==1:
            line="LAPRAS used SURF!";text["cells"][14][1:1+len(line)]=list(line)
            text.update(window_visible=True,lines=[line],line_rows=[14])
        if text_change:text_change(text)
        g=helper.grid(self.key,f,self.player,m)
        if grid_change:grid_change(g)
        if no_grid:g=None
        native=dict(raw=raw,kind=("wild" if raw==1 else "none") if kind is None else kind,
                    active=(raw!=0) if active is None else active,observation_frame=f)
        state=dict(frame=f,location=dict(map_id=m[0xD35E],x=self.player[0],y=self.player[1]),
            progress=deepcopy(self.p),battle_state=native,phase="unclassified",objective="Continue the route.",
            available_actions=["left","right","wait"])
        if raw==1 and battle_context:
            from laya_pokemon.battle import battle_context as existing_battle_context
            state.update(existing_battle_context(text,native,self.p["party"],self.p["inventory"]))
        if state_change:state_change(state)
        self.last_state=deepcopy(state)
        result=bridge.context(self.pb,state,self.plan,self.step_id,text,g,
            self.previous if previous is None else previous)
        if result is None:self.last_result=self.last_next=None;return None
        self.last_result,self.last_next=result
        if self.step_id in bridge._CONTROLLERS:self.c=bridge._CONTROLLERS[self.step_id]
        return self.last_result

def review(out,reason=None):
    assert out["phase"]=="campaign_review" and out["available_actions"]==["wait"],out
    assert out.get("later_boulder_complete") is not True
    if reason:assert out["review_reason"]=="victory_later_boulder_"+reason,out

def reload_bridge():
    spec=importlib.util.spec_from_file_location(bridge.__name__,BRIDGE.resolve());spec.loader.exec_module(bridge)

@pytest.mark.parametrize("key",ORDER)
def test_all_four_complete_source_traces_true_contacts_no_follow_and_no_strength_or_floor_claim(key):
    s=BridgeSession(key);before=deepcopy(s.p);out=s.finish()
    assert s.trace==s.case["coordinate_trace"] and s.p==before
    assert out["field_move_complete"] and out["field_move_kind"]=="victory-later-boulder"
    assert out["later_boulder_case"]==key and s.last_next=="after-"+key
    assert bridge._COMPLETED=={s.step_id} and s.pb.memory.values[0xD35E]==s.case["map_id"]
    assert out["contact_arm_seen"] and out["native_script_seen"] and out["dust_seen"]
    assert "strength_complete" not in out and "player_fall_complete" not in out

def test_real_wild_battle_decision_survives_truthy_owner_handoff_and_full_route_return():
    s=BridgeSession();s.to_index(1);c=s.c;p=c.pending;base=c.baseline;clock=c.started
    out=s.call(raw=1,no_grid=True,previous=["wait"])
    assert out["later_boulder_battle_delegate"]=="existing_battle"
    assert out["phase"]==s.last_state["phase"]=="battle_dialogue" and out["available_actions"]==["a","wait"]
    assert s.last_next==s.step_id and bridge.applies("foreign",None) and c.pending is p and c.suspended
    s.p["party"][0]["hp"]-=4;s.p["party"][0]["exp"]+=100;s.p["party"][0]["pp"][0]-=1
    s.p["inventory"][0]["quantity"]-=1
    out=s.call(no_grid=True,window=True,previous=["a"],state_change=lambda st:st.update(
        phase="dialogue",objective="Advance the visible dialogue with the confirm button.",available_actions=["a","wait"]))
    assert out["later_boulder_battle_delegate"]=="existing_battle" and c.baseline is base
    s.call(previous=["wait"]);s.finish()
    assert s.c is c and c.started==clock and c.battle_returns==1 and s.trace==s.case["coordinate_trace"]

@pytest.mark.parametrize("key",ORDER)
def test_held_push_can_skip_middle_samples_without_inventing_seen_phases(key):
    s=BridgeSession(key);out=s.finish(phases=False)
    assert out["field_move_complete"] and not out["contact_arm_seen"] and not out["native_script_seen"] and not out["dust_seen"]

def test_hole_proves_only_hidden_stone_same_floor_and_actual_follow_can_be_observed():
    s=BridgeSession("3f_hole");s.finish(follow=True)
    assert s.player==(22,15) and s.stone==(23,15) and s.pb.memory.values[0xD35E]==198
    assert s.pb.memory.values[0xD5B5]&4 and not s.pb.memory.values[0xD5B2]&1

@pytest.mark.parametrize("key,value",[("event",1336),("item",199),("badge",8),("terminal",False),
    ("next_map",198),("await_script_event",False),("boulder_intent",{}),("slot",11),("event_id",1336),
    ("ram_address",0xD7EE),("kind","move"),("map_id",True),("target",[1,9]),("target",[False,9]),
    ("boulder_case","unknown"),("boulder_case",{}),("boulder_case",True)])
def test_step_and_case_cannot_be_generalized_or_use_shortcuts(key,value):
    s=BridgeSession();s.plan["steps"][0][key]=value
    review(s.call(),"explicit_case_unverified");assert not bridge._BINDINGS

@pytest.mark.parametrize("key",ORDER)
def test_unbound_navigation_yields_but_exact_stance_and_job_bind_once(key):
    s=BridgeSession(key);s.place(player=(s.player[0],s.player[1]+1))
    assert s.call() is None and not bridge._BINDINGS
    s.place(player=tuple(s.case["start_player"]));out=s.call()
    assert out["phase"]!="campaign_review" and s.c.owner==s.step_id and bridge._BINDINGS

def test_active_foreign_step_removed_mechanic_or_step_never_leaks_to_waypoint():
    s=BridgeSession();s.call();c=s.c;s.step_id="foreign"
    review(s.call(),"owner_changed");assert bridge.applies(None,None)
    s.step_id="later-2f_switch1";s.plan["steps"][0].pop("mechanic")
    review(s.call(),"intent_changed");s.plan["steps"].pop(0)
    review(s.call(),"step_unverified");assert s.c is c

def test_changing_to_another_valid_case_or_job_does_not_rebind_or_refund():
    s=BridgeSession();s.call();c=s.c;p=c.pending;clock=c.started;spent=c.calls
    other=bridge.boulder.CASES["3f_switch1"]
    s.plan["steps"][0].update(boulder_case="3f_switch1",map_id=other["map_id"],target=other["start_player"])
    review(s.call(),"case_or_owner_changed")
    assert s.c is c and c.pending is p and c.started==clock and c.calls==spent
    s.plan=plan("2f_switch1");s.plan["training_job"]="other";review(s.call(),"case_or_owner_changed")

def test_missing_original_controller_or_binding_is_owned_review_not_reconstruction():
    s=BridgeSession();s.call();c=bridge._CONTROLLERS.pop(s.step_id)
    review(s.call(),"original_controller_missing")
    bridge._CONTROLLERS[s.step_id]=c;bridge._BINDINGS.clear()
    review(s.call(),"original_binding_missing");assert bridge.applies("foreign",None)

@pytest.mark.parametrize("change",[lambda p:p.update(training_job=None),lambda p:p.pop("training_job"),
    lambda p:p.update(training_job=float("nan")),lambda p:p["steps"].append(deepcopy(p["steps"][0]))])
def test_malformed_job_or_plan_cannot_bind(change):
    s=BridgeSession();change(s.plan);review(s.call());assert not bridge._BINDINGS

def test_initial_ui_unknown_byte_and_missing_strength_do_not_create_fake_activation():
    s=BridgeSession();review(s.call(window=True),"initial_closed_world_required")
    s.pb.memory.values[0xD728]=False;review(s.call(),"initial_signal_unverified")
    s.pb.memory.values[0xD728]=64;review(s.call())
    assert not bridge._COMPLETED and s.last_next==s.step_id
    assert s.last_result["available_actions"]==["wait"] and "field_move_complete" not in s.last_result

def test_true_previous_and_sameframe_protection_precede_any_progress():
    s=BridgeSession();s.call();p=s.c.pending
    assert s.call(same=True)["available_actions"]==["wait"]
    review(s.call(same=True,previous=[p["action"]]));assert not p["executed"]
    bridge._BINDINGS.clear();bridge._CONTROLLERS.clear();s=BridgeSession();s.call();p=s.c.pending
    s.place(player=p["expected_player"]);review(s.call(previous=["wait"]))
    assert not p["executed"] and not bridge._COMPLETED

def test_battle_direction_never_retroactively_acks_the_field_offer():
    s=BridgeSession("3f_hole");s.call();p=s.c.pending
    assert s.call(raw=1,no_grid=True,previous=["wait"])["later_boulder_battle_handoff"]
    assert s.call(raw=1,no_grid=True,previous=[p["action"]])["later_boulder_battle_handoff"]
    assert not p["executed"]
    s.call(previous=["wait"]);assert not p["executed"] and s.c.pending is p

@pytest.mark.parametrize("raw,kind,active",[(2,"wild",True),(2,"trainer",True),(1,"trainer",True),(1,"wild",False)])
def test_raw2_or_bad_raw1_is_not_delegated(raw,kind,active):
    s=BridgeSession();s.call();review(s.call(raw=raw,kind=kind,active=active,battle_context=False,no_grid=True))
    assert not bridge._COMPLETED and bridge.applies("foreign",None)

def test_unclassified_return_remains_owned_wait_and_real_review_is_preserved():
    s=BridgeSession();s.call()
    out=s.call(raw=1,battle_context=False,no_grid=True)
    assert out["available_actions"]==["wait"] and out["phase"]!="unclassified"
    out=s.call(raw=1,no_grid=True,state_change=lambda st:st.update(phase="strategy_review",objective="Wait.",
        available_actions=["wait"],review_reason="native_battle_review"))
    assert out["phase"]=="strategy_review" and out["review_reason"]=="native_battle_review"

@pytest.mark.parametrize("key",ORDER)
def test_goal_event_alone_never_advances_without_physical_receipt(key):
    s=BridgeSession(key);s.to_index(len(s.case["fixed_pushes"]));s.set_goal_event()
    assert not s.call()["later_boulder_complete"] and not bridge._COMPLETED
    assert s.last_next==s.step_id

def test_hole_player_fall_before_same_floor_receipt_is_review_not_next_case():
    s=BridgeSession("3f_hole");s.call();s.pb.memory.values[0xD35E]=194
    review(s.call());assert s.last_next==s.step_id and not bridge._COMPLETED

def test_reload_keeps_pending_suspension_original_resources_clock_and_sequence():
    s=BridgeSession();s.to_index(1);s.call(raw=1,no_grid=True,previous=["wait"])
    c=s.c;p=c.pending;base=c.baseline;spent=(c.started,c.step_started,c.calls,c.push_index)
    reload_bridge()
    assert bridge._CONTROLLERS[s.step_id] is c and c.pending is p and c.baseline is base and c.suspended
    assert (c.started,c.step_started,c.calls,c.push_index)==spent
    s.call(previous=["wait"]);s.finish();assert s.c is c and s.last_next=="after-2f_switch1"

def test_reload_preserves_sticky_error_and_exhausted_call_budget():
    s=BridgeSession();s.call();c=s.c;c.calls=2400
    review(s.call());error=c.error;clock=c.started;calls=c.calls
    reload_bridge();review(s.call())
    assert s.c is c and c.error==error and c.started==clock and c.calls==calls and not bridge._COMPLETED

def test_completed_step_cannot_replay_native_success_and_last_step_returns_complete():
    s=BridgeSession("3f_hole");s.plan["steps"].pop();s.finish();assert s.last_next=="complete"
    review(s.call(),"completed_step_reentered")
    assert s.last_next==s.step_id

def test_exact_frozen_dependency_and_readonly_operations():
    from hashlib import sha256
    source=Path(bridge.boulder.__file__).resolve()
    expected=(ROOT/"src/laya_pokemon/victory_later_boulders.py" if HERE.name=="tests" else
              ROOT/".local/staged-victory-later-boulders-20261025/victory_later_boulders.py").resolve()
    assert source==expected and sha256(source.read_bytes()).hexdigest() in bridge.PURE_SHA256S
    s=BridgeSession("3f_hole");assert s.call()["available_actions"]==["right","wait"]
    with pytest.raises(AssertionError):s.pb.tick()
    with pytest.raises(AssertionError):s.pb.memory[0xD728]=1
