"""Actual native read packets against the postreview pure/bridge; no fake success."""
from pathlib import Path
import importlib.util
import pytest

HERE=Path(__file__).resolve().parent
if HERE.name=="staged-victory-first-boulder-postreview-20261025" and HERE.parent.name==".local":
    PURE_TEST=HERE/"test_victory_first_boulder.py";BRIDGE_TEST=HERE/"test_victory_first_boulder_bridge.py"
elif HERE.name=="tests":
    PURE_TEST=HERE/"test_victory_first_boulder.py";BRIDGE_TEST=HERE/"test_victory_first_boulder_bridge.py"
else:raise RuntimeError("Only exact first-boulder postreview stage/formal tests supported")

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path.resolve(strict=True));m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m);return m

h=load("laya_pokemon._postreview_first_pure_helpers",PURE_TEST)
bh=load("laya_pokemon._postreview_first_bridge_helpers",BRIDGE_TEST)

def test_existing_wild_and_return_ui_directions_cannot_ack_unexecuted_field_offer():
    s=h.Session();s.call();p=s.c.pending
    assert s.call(raw=1,previous=["wait"],no_grid=True)["first_boulder_battle_handoff"]
    assert not p["executed"]
    assert s.call(raw=1,previous=[p["action"]],no_grid=True)["first_boulder_battle_handoff"]
    assert not p["executed"]
    assert s.call(ready=False,window=True,no_grid=True,previous=[p["action"]])["first_boulder_battle_handoff"]
    assert not p["executed"]
    out=s.call(previous=[p["action"]])
    assert out["available_actions"]==[p["action"],"wait"] and s.c.pending is p and not p["executed"]

@pytest.mark.parametrize("raw,kind,active",[(2,"trainer",True),(2,"wild",True),(1,"trainer",True)])
def test_foreign_battle_packet_never_acks_before_its_sticky_review(raw,kind,active):
    s=h.Session();s.call();p=s.c.pending
    h.review(s.call(raw=raw,kind=kind,active=active,previous=[p["action"]],no_grid=True))
    assert not p["executed"] and s.c.push_index==0

def test_first_true_raw1_entry_can_ack_the_actual_field_walk_that_triggered_encounter():
    s=h.Session();s.call();p=s.c.pending
    s.place(player=p["expected_player"],action=p["action"])
    assert s.call(raw=1,previous=[p["action"]],no_grid=True)["first_boulder_battle_handoff"]
    assert p["executed"] and s.c.suspended
    out=s.call(previous=["wait"])
    assert out["phase"]!="campaign_review" and s.c.pending is not p and s.c.battle_returns==1

def test_postwild_coordinate_change_without_entry_field_receipt_is_not_repaired_by_battle_direction():
    s=h.Session();s.call();p=s.c.pending;s.call(raw=1,previous=["wait"],no_grid=True)
    s.place(player=p["expected_player"],action=p["action"])
    s.call(raw=1,previous=[p["action"]],no_grid=True)
    assert not p["executed"]
    h.review(s.call(previous=[p["action"]]));assert not p["executed"] and s.c.push_index==0

def test_real_bridge_keeps_owned_wild_phase_and_never_credits_its_direction_as_field_execution(monkeypatch):
    bridge=bh.bridge
    for name,value in (("_CONTROLLERS",{}),("_BINDINGS",{}),("_COMPLETED",set())):monkeypatch.setattr(bridge,name,value)
    s=bh.BridgeSession();s.call();p=s.c.pending
    out=s.call(raw=1,no_grid=True,previous=["wait"])
    assert out["phase"]=="battle_dialogue" and out["first_boulder_battle_delegate"]=="existing_battle"
    out=s.call(raw=1,no_grid=True,previous=[p["action"]])
    assert out["first_boulder_battle_handoff"] and not p["executed"] and bridge.applies("foreign",None)
    s.call(previous=["wait"])
    assert s.c.pending is p and not p["executed"]
