"""Frozen real pure/getter/SDK/BFS integration; no emulator or input operations."""
from copy import deepcopy
from pathlib import Path
import importlib.util
import pytest

HERE=Path(__file__).resolve().parent
if HERE.name=="staged-victory-first-boulder-postreview-20261025" and HERE.parent.name==".local":
    ROOT=HERE.parent.parent;BRIDGE=HERE/"victory_first_boulder_bridge.py"
    PURE_TEST=HERE/"test_victory_first_boulder.py"
elif HERE.name=="tests":
    ROOT=HERE.parent;BRIDGE=ROOT/"src/laya_pokemon/victory_first_boulder_bridge.py"
    PURE_TEST=ROOT/"tests/test_victory_first_boulder.py"
else:raise RuntimeError("Only exact first-boulder bridge stage or formal tests supported")

def load(name,path):
    path=path.resolve(strict=True);spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert Path(module.__file__).resolve()==path;return module

bridge=load("laya_pokemon._exact_first_boulder_bridge_tests",BRIDGE)
helper=load("laya_pokemon._exact_first_boulder_bridge_helpers",PURE_TEST)

def plan():
    return dict(training_job="league-first-boulder-20261025",steps=[dict(id="vr1-first-switch",
        kind="interact",mechanic="victory_first_boulder",map_id=108,target=[8,16],
        boulder_intent=deepcopy(bridge.boulder.INTENT)),
        dict(id="after-first-switch",kind="move",map_id=108,target=[9,12])])

@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for name,value in (("_CONTROLLERS",{}),("_BINDINGS",{}),("_COMPLETED",set())):
        monkeypatch.setattr(bridge,name,value)
    # Battle-context caches are unrelated to a new synthetic native encounter.
    from laya_pokemon import battle
    for name in ("_no_pp_switch","_fixed_damage_risk"):
        monkeypatch.setattr(battle,name,None)

class BridgeSession(helper.Session):
    def __init__(self):
        super().__init__();self.plan=plan();self.step_id="vr1-first-switch"
        self.last_next=self.last_result=self.last_state=None
    def call(self,*,same=False,previous=None,raw=0,kind=None,active=None,ready=True,
             window=False,no_grid=False,signal_change=None,grid_change=None,text_change=None,
             now=None,state_change=None,battle_context=True):
        assert signal_change is None and now is None  # Never replace the real getter/clock result.
        if not same:self.pb.frame_count+=1;self.now+=.05
        f=self.pb.frame_count;self.pb.memory.values[0xD057]=raw
        text=dict(profile=helper.TEXT_PROFILE,read_valid=True,alignment_verified=True,read_error=None,
            cells=[[" "]*20 for _ in range(18)],window_visible=window,observation_frame=f,
            lines=[],line_rows=[])
        if raw==1:
            line="LAPRAS used SURF!";text["cells"][14][1:1+len(line)]=list(line)
            text.update(window_visible=True,lines=[line],line_rows=[14])
        if text_change:text_change(text)
        g=helper.grid(f,self.player,self.pb.memory.values[0xC77F]==0x1D)
        if grid_change:grid_change(g)
        if no_grid:g=None
        native=dict(raw=raw,kind=("wild" if raw==1 else "none") if kind is None else kind,
                    active=(raw!=0) if active is None else active,observation_frame=f)
        state=dict(frame=f,location=dict(map_id=108,x=self.player[0],y=self.player[1]),progress=deepcopy(self.p),
                   battle_state=native,phase="unclassified",objective="Continue the route.",
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
    helper.review(out)
    if reason:assert out["review_reason"]=="victory_first_boulder_"+reason,out

def reload_bridge():
    spec=importlib.util.spec_from_file_location(bridge.__name__,BRIDGE.resolve())
    spec.loader.exec_module(bridge)

def test_complete_real_56_displacements_two_contacts_no_follow_and_owned_wild_return():
    s=BridgeSession();before=deepcopy(s.p);s.to_index(3)
    c=s.c;pending=c.pending;baseline=c.baseline;spent=(c.started,c.step_started,c.calls,c.push_index)
    out=s.call(raw=1,no_grid=True,previous=["wait"])
    assert out["first_boulder_battle_delegate"]=="existing_battle"
    assert out["phase"]==s.last_state["phase"]=="battle_dialogue"
    assert out["objective"]==s.last_state["objective"] and out["available_actions"]==["a","wait"]
    assert s.last_next==s.step_id and bridge.applies("foreign",None)
    assert c is s.c and c.pending is pending and c.baseline is baseline and c.push_index==3 and c.suspended
    assert (c.started,c.step_started)==spent[:2] and c.calls==spent[2]+1
    s.p["party"][0]["hp"]-=4;s.p["party"][0]["exp"]+=120;s.p["party"][0]["pp"][0]-=1
    s.p["inventory"][0]["quantity"]-=1
    out=s.call(ready=False,window=True,no_grid=True,previous=["a"],state_change=lambda st:st.update(
        phase="dialogue",objective="Advance the visible dialogue with the confirm button.",available_actions=["a","wait"]))
    assert out["first_boulder_battle_delegate"]=="existing_battle" and c.suspended and c.pending is pending
    s.call(previous=["wait"])
    assert c is s.c and c.battle_returns==1 and c.push_index==3 and not c.suspended
    out=s.finish()
    assert len(s.trace)==56 and sum(x[0]=="walk" for x in s.trace)==38 and sum(x[0]=="push" for x in s.trace)==18
    assert s.player==(17,11) and s.stone==(17,13)
    assert s.p["money"]==before["money"] and s.p["party"][0]["hp"]==before["party"][0]["hp"]-4
    assert out["field_move_complete"] is True and out["field_move_kind"]=="victory-first-boulder"
    assert out["contact_arm_seen"] and out["native_script_seen"] and out["dust_seen"]
    assert s.last_next=="after-first-switch" and bridge._COMPLETED=={s.step_id}

def test_real_held_contact_can_skip_middle_samples_without_fake_receipt_claims():
    s=BridgeSession();out=s.finish(sample_phases=False)
    assert out["field_move_complete"] and not out["contact_arm_seen"] and not out["native_script_seen"]
    assert not out["dust_seen"] and s.last_next=="after-first-switch"

def test_real_follow_is_observed_and_final_position_bound():
    s=BridgeSession();s.finish(follow=True)
    assert s.player==(17,12) and s.c.final_player==(17,12) and s.last_next=="after-first-switch"

@pytest.mark.parametrize("key,value",[("event",2327),("item",199),("badge",8),("terminal",False),
    ("next_map",194),("await_script_event",False),("kind","move"),("map_id",True),
    ("target",[9,16]),("target",[8,True])])
def test_explicit_step_rejects_shortcuts_or_changed_fixed_stance(key,value):
    s=BridgeSession();s.plan["steps"][0][key]=value
    review(s.call(),"explicit_intent_unverified");assert not bridge._BINDINGS

@pytest.mark.parametrize("change",[lambda i:i.update(slot=6),lambda i:i.update(slot=True),
    lambda i:i.update(start_player=[8,True]),lambda i:i.update(goal_boulder=[16,13]),
    lambda i:i.update(kind="all_boulders"),lambda i:i.update(event_id=0x918),
    lambda i:i.update(extra=True),lambda i:i.pop("slot")])
def test_intent_cannot_generalize_or_accept_bool_coordinate_alias(change):
    s=BridgeSession();change(s.plan["steps"][0]["boulder_intent"])
    review(s.call(),"explicit_intent_unverified");assert not bridge._CONTROLLERS

def test_unbound_normal_navigation_yields_then_exact_start_binds():
    s=BridgeSession();s.place(player=(8,17),action="up")
    assert s.call() is None and not bridge._BINDINGS
    s.place(player=(8,16));assert s.call()["available_actions"]==["left","wait"]
    assert bridge._BINDINGS and s.c.owner==s.step_id

def test_unbound_other_floor_yields_but_active_owner_never_yields_on_floor_change():
    s=BridgeSession()
    assert s.call(state_change=lambda st:st["location"].update(map_id=194)) is None
    s.call();c=s.c;s.pb.memory.values[0xD35E]=194
    review(s.call(state_change=lambda st:st["location"].update(map_id=194)))
    assert s.c is c and bridge.applies("foreign",None) and not bridge._COMPLETED

def test_initial_menu_unknown_byte_or_missing_decoder_proof_cannot_bind():
    s=BridgeSession();review(s.call(window=True),"initial_closed_world_required")
    review(s.call(text_change=lambda t:t.pop("profile")),"initial_closed_world_required")
    s.pb.memory.values[0xD728]=False
    review(s.call(),"initial_signal_unverified");assert not bridge._BINDINGS

def test_active_foreign_step_removed_step_or_mechanic_intercept_before_navigation():
    s=BridgeSession();s.call();c=s.c
    s.step_id="foreign";review(s.call(),"owner_changed")
    s.step_id="vr1-first-switch";s.plan["steps"][0].pop("mechanic")
    review(s.call(),"intent_changed");s.plan["steps"].pop(0)
    review(s.call(),"step_unverified");assert s.c is c and bridge.applies(None,None)

@pytest.mark.parametrize("change",[lambda p:p.update(training_job="foreign"),
    lambda p:p["steps"][0].update(label="changed"),lambda p:p["steps"][0].update(target=[8,15])])
def test_full_job_and_step_binding_changes_never_reconstruct_or_credit(change):
    s=BridgeSession();s.call();c=s.c;pending=c.pending;baseline=c.baseline;spent=(c.started,c.calls,c.waits)
    change(s.plan);review(s.call())
    assert s.c is c and c.pending is pending and c.baseline is baseline and (c.started,c.calls,c.waits)==spent

def test_missing_original_controller_or_binding_stays_owned_without_reset():
    s=BridgeSession();s.call();c=bridge._CONTROLLERS.pop(s.step_id)
    review(s.call(),"original_controller_missing")
    bridge._CONTROLLERS[s.step_id]=c;bridge._BINDINGS.clear()
    review(s.call(),"original_binding_missing");assert bridge.applies("foreign",None)

def test_true_previous_required_offer_cannot_move_coordinates_or_finish():
    s=BridgeSession();s.call();p=s.c.pending;s.place(player=p["expected_player"],action=p["action"])
    review(s.call(previous=["wait"]));assert not p["executed"] and not bridge._COMPLETED
    error=s.c.error;spent=s.c.calls
    review(s.call(previous=[p["action"]]));assert s.c.error==error and s.c.calls==spent

def test_same_frame_conflict_cannot_ack_while_identical_packet_only_waits():
    s=BridgeSession();s.call();p=s.c.pending
    assert s.call(same=True)["available_actions"]==["wait"]
    review(s.call(same=True,previous=[p["action"]]));assert not p["executed"]

def test_source_event_block_tile_without_actual_push_sequence_does_not_complete():
    s=BridgeSession();s.call();s.place(stone=(17,13));s.pb.memory.values.update({0xD869:128,0xC77F:0x1D})
    review(s.call(previous=["wait"]));assert not bridge._COMPLETED and s.last_next==s.step_id

def test_real_event_alone_and_missing_tile_and_interrupted_closed_pair_never_advance():
    s=BridgeSession();s.to_index(18);m=s.pb.memory.values;m[0xD869]=128
    assert not s.call()["first_boulder_complete"] and not bridge._COMPLETED
    m[0xC77F]=0x1D
    assert not s.call(grid_change=lambda g:g["tiles"][12].__setitem__(9,0x24))["first_boulder_complete"]
    assert not s.call()["first_boulder_complete"] and not bridge._COMPLETED
    m[0xCFC5]=8;assert not s.call()["first_boulder_complete"] and s.c.closed_frame is None
    m[0xCFC5]=0;assert not s.call()["first_boulder_complete"]
    assert s.call()["field_move_complete"] and s.last_next=="after-first-switch"

@pytest.mark.parametrize("raw,kind,active",[(2,"wild",True),(2,"trainer",True),(1,"trainer",True),(1,"wild",False)])
def test_raw2_or_mislabeled_raw1_is_never_battle_handoff(raw,kind,active):
    s=BridgeSession();s.call();review(s.call(raw=raw,kind=kind,active=active,battle_context=False,no_grid=True))
    assert s.last_next==s.step_id and bridge.applies("foreign",None) and not bridge._COMPLETED

def test_unclassified_wild_or_return_does_not_leak_navigation_choices():
    s=BridgeSession();s.call()
    out=s.call(raw=1,battle_context=False,no_grid=True)
    assert out["first_boulder_battle_delegate"]=="await_existing_battle_context" and out["available_actions"]==["wait"]
    assert out["phase"]!="unclassified" and bridge.applies("foreign",None)
    out=s.call(no_grid=True,window=True,previous=["a"])
    assert out["available_actions"]==["wait"] and s.c.suspended and s.last_next==s.step_id

def test_battle_handoff_preserves_native_review_instead_of_replacing_with_walk_or_a():
    s=BridgeSession();s.call()
    out=s.call(raw=1,no_grid=True,state_change=lambda st:st.update(phase="strategy_review",
        objective="Wait.",available_actions=["wait"],review_reason="existing_battle_review"))
    assert out["phase"]=="strategy_review" and out["review_reason"]=="existing_battle_review"
    assert out["available_actions"]==["wait"] and s.c.suspended and not bridge._COMPLETED

@pytest.mark.parametrize("change",[lambda p:p.update(money=p["money"]+1),
    lambda p:p["party"][0]["pp"].__setitem__(0,6),lambda p:p["party"].reverse()])
def test_unreceipted_wild_resource_gains_require_review_and_preserve_owner(change):
    s=BridgeSession();s.to_index(4);s.call(raw=1,no_grid=True);change(s.p)
    review(s.call());assert s.c.push_index==4 and s.c.suspended and bridge.applies("foreign",None)

def test_reload_preserves_exact_pending_baseline_owner_budget_and_raw1_suspension():
    s=BridgeSession();s.to_index(3);s.call(raw=1,no_grid=True)
    c=s.c;p=c.pending;base=c.baseline;spent=(c.started,c.step_started,c.calls,c.requests,c.push_index)
    reload_bridge()
    assert bridge._CONTROLLERS[s.step_id] is c and c.pending is p and c.baseline is base
    assert (c.started,c.step_started,c.calls,c.requests,c.push_index)==spent and c.suspended
    out=s.call(raw=1,no_grid=True,previous=["a"])
    assert out["first_boulder_battle_handoff"] and s.c is c and c.pending is p and c.started==spent[0]
    s.call(previous=["wait"]);s.finish();assert s.c is c and s.last_next=="after-first-switch"

def test_reload_keeps_sticky_error_and_exhausted_budget():
    s=BridgeSession();s.call();c=s.c;c.calls=2400;started=c.started
    review(s.call(),"budget_exhausted");error=c.error;calls=c.calls
    reload_bridge();review(s.call())
    assert s.c is c and c.error==error and c.started==started and c.calls==calls and not bridge._COMPLETED

@pytest.mark.parametrize("change",[lambda p:p["steps"].append(deepcopy(p["steps"][0])),
    lambda p:p.update(training_job=float("nan")),lambda p:p.pop("training_job"),lambda p:p.update(training_job=None)])
def test_bad_plan_or_unbound_job_rejected_before_binding(change):
    s=BridgeSession();change(s.plan);review(s.call());assert not bridge._BINDINGS

@pytest.mark.parametrize("change",[lambda s:s.update(frame=True),lambda s:s.update(frame=-1),
    lambda s:s.update(location=None),lambda s:s["location"].update(x=True)])
def test_malformed_outer_frame_or_location_is_not_read_as_navigation(change):
    s=BridgeSession();review(s.call(state_change=change));assert not bridge._BINDINGS

def test_completed_owner_cannot_replay_next_step_without_new_native_receipt():
    s=BridgeSession();s.finish();review(s.call(),"completed_step_reentered")
    assert s.last_next==s.step_id and bridge._COMPLETED=={s.step_id}
    s.step_id="after-first-switch";assert not bridge.applies(s.step_id,s.plan["steps"][1])

def test_final_step_returns_complete_only_after_true_native_completion():
    s=BridgeSession();s.plan["steps"].pop();s.finish();assert s.last_next=="complete"

def test_frozen_exact_loader_sha_real_sdk_and_getter_have_no_fake_escape():
    from hashlib import sha256
    source=Path(bridge.boulder.__file__).resolve()
    expected=(ROOT/"src/laya_pokemon/victory_first_boulder.py" if HERE.name=="tests" else
              ROOT/".local/staged-victory-first-boulder-postreview-20261025/victory_first_boulder.py").resolve()
    assert source==expected and sha256(source.read_bytes()).hexdigest() in bridge.PURE_SHA256S
    assert bridge.boulder.read_first_boulder_observation.__module__==bridge.boulder.__name__
    s=BridgeSession();out=s.call();assert out["available_actions"]==["left","wait"]
    with pytest.raises(AssertionError):s.pb.tick()
    with pytest.raises(AssertionError):s.pb.memory[0xD728]=65

@pytest.mark.parametrize("change",[lambda st:st.update(phase=[]),
    lambda st:st.update(available_actions=["a"]),lambda st:st.update(available_actions=["a","a"])])
def test_invalid_native_battle_decision_cannot_inject_actions_or_crash_handoff(change):
    s=BridgeSession();s.call();out=s.call(raw=1,no_grid=True,state_change=change)
    assert out["available_actions"]==["wait"] and out["first_boulder_battle_delegate"]=="await_existing_battle_context"
    assert bridge.applies("foreign",None) and not bridge._COMPLETED
