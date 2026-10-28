"""Four native Strength UI flows and source-only entry boundaries; no game input."""
from copy import deepcopy
from pathlib import Path
import importlib.util
import pytest

HERE=Path(__file__).resolve().parent
if not ((HERE.name=="staged-victory-strength-floors-20261025" and HERE.parent.name==".local") or HERE.name=="tests"):
    raise RuntimeError("Only exact Strength floors stage or formal tests directory supported")

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path.resolve(strict=True));m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m);return m

h=load("laya_pokemon._strength_floors_pure_helpers",HERE/"test_victory_strength.py")
bh=load("laya_pokemon._strength_floors_bridge_helpers",HERE/"test_victory_strength_bridge.py")
KEYS=("1f_entry","2f_entry","3f_entry","2f_after_fall")

@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for name,value in (("_CONTROLLERS",{}),("_BINDINGS",{}),("_COMPLETED",set())):
        monkeypatch.setattr(bh.bridge,name,value)

@pytest.mark.parametrize("key",KEYS)
def test_each_whitelisted_stance_runs_actual_two_page_ui_and_two_fresh_active_worlds(key):
    s=h.Session(key);before=deepcopy(s.p);s.confirm();out=s.finish()
    assert out["victory_strength_complete"] and out["victory_strength_case"]==key
    assert s.c.prompt_ack and s.c.strength_selected and s.c.seen_used_full and s.c.seen_can_prompt
    assert s.c.start==h.DATA["stances"][key]["start"] and s.p==before

@pytest.mark.parametrize("key",KEYS)
def test_each_real_bridge_advances_only_here_and_preserves_dynamic_party_and_resources(key):
    s=bh.BridgeSession(key);s.p["money"]=5;s.p["inventory"]=[]
    s.p["party"][0],s.p["party"][1]=s.p["party"][1],s.p["party"][0]
    s.p["party"][0].update(level=51,hp=60,exp=51**3)
    before=deepcopy(s.p);s.confirm();out=s.finish()
    assert s.last_next=="after-strength" and out["field_move_kind"]=="victory-strength"
    assert out["victory_strength_case"]==key and s.c.target_index==0 and s.p==before
    assert s.pb.memory.values[0xD35E]==h.DATA["stances"][key]["start"]["map_id"]
    assert "player_fall_complete" not in out and "later_boulder_complete" not in out

@pytest.mark.parametrize("key",KEYS)
def test_automatic_used_page_can_be_unsampled_but_exact_can_prompt_and_actual_a_are_still_required(key):
    s=h.Session(key);s.confirm(see_used=False)
    assert not s.c.seen_used_full and not s.c.prompt_ack
    out=s.call(h.message(s.p,"can",True),previous=["wait"])
    assert out["available_actions"]==["a","wait"] and not s.c.prompt_ack
    s.previous=["a"];s.finish()

@pytest.mark.parametrize("key",KEYS)
def test_already_active_flags_or_flag_only_blank_world_do_not_prove_a_new_activation(key):
    s=h.Session(key);s.pb.memory.values[0xD728]=65
    h.review(s.call(h.canvas(),window=False,ready=True))
    assert not s.c.prompt_ack and s.c.baseline is None

@pytest.mark.parametrize("key",KEYS)
def test_same_source_cell_header_and_loaded_block_are_required(key):
    for change in (lambda s:s.pb.memory.values.update({0xD367:0}),
                   lambda s:s.pb.memory.values.update({h.DATA["stances"][key]["block_address"]:0}),
                   lambda s:s.pb.memory.values.update({0xD369:1})):
        s=h.Session(key);change(s);h.review(s.call(h.canvas(),window=False,ready=True))
    s=h.Session(key);x,y=s.location["x"],s.location["y"]
    h.review(s.call(h.canvas(),window=False,ready=True,grid_change=lambda g:g["tiles"][y].__setitem__(x,5)))

@pytest.mark.parametrize("key",KEYS)
def test_cleared_warp_bits_with_unrestored_player_pixels_are_not_native_idle(key):
    s=h.Session(key);s.pb.memory.values[0xD72D]=0;s.pb.memory.values[0xD732]=1
    s.pb.memory.values[0xC104]=0xEC  # source delay50 after dungeon bit clears.
    signal=h.strength.read_strength_observation(s.pb,1,h.REAL_CONSTANTS)
    assert signal["read_valid"] and signal["idle"] is False
    h.review(s.call(h.canvas(),window=False,ready=True))
    assert s.c.baseline is None

@pytest.mark.parametrize("address",[0xD700,0xCD6B,0xD730,0xD736])
def test_second_snapshot_false_equals_zero_never_passes_byte_contract(address):
    s=h.Session("2f_after_fall")
    s.pb.memory.hook=lambda a,v:False if a==address and s.pb.memory.reads.count(a)==2 else v
    signal=h.strength.read_strength_observation(s.pb,1,h.REAL_CONSTANTS)
    assert not signal["read_valid"] and signal["strength_active"] is None

def test_getter_unknown_stance_is_not_generalized_to_any_victory_road_tile():
    s=h.Session("2f_entry");s.pb.memory.values[0xD362]=1
    assert not h.strength.read_strength_observation(s.pb,1,h.REAL_CONSTANTS)["read_valid"]
    intent=deepcopy(h.strength.INTENTS["2f_entry"]);intent["player_x"]=1
    with pytest.raises(ValueError):h.strength.VictoryStrengthController(intent)

def test_same_floor_entry_and_after_fall_intents_are_distinct_and_no_false_bool_alias():
    s=bh.BridgeSession("2f_entry");s.call(h.canvas(),window=False,ready=True);c=s.c;pending=c.pending
    s.plan["steps"][0]["strength_intent"]=deepcopy(bh.bridge.victory_strength.INTENTS["2f_after_fall"])
    s.plan["steps"][0]["target"]=[22,16]
    bh.review(s.call(h.canvas(),window=False),"intent_or_owner_changed")
    assert s.c is c and c.pending is pending
    intent=deepcopy(h.strength.INTENTS["2f_entry"]);intent["player_x"]=False
    with pytest.raises(ValueError):h.strength.VictoryStrengthController(intent)

@pytest.mark.parametrize("key",KEYS)
def test_hot_reload_retains_case_pending_flag_baseline_clock_and_actual_prompt_ack_boundary(key):
    s=bh.BridgeSession(key);s.confirm();c=s.c;p=c.pending;base=c.baseline;spent=(c.started,c.calls,c.waits)
    spec=importlib.util.spec_from_file_location(bh.bridge.__name__,bh.BRIDGE.resolve());spec.loader.exec_module(bh.bridge)
    assert bh.bridge._CONTROLLERS[s.step_id] is c and c.pending is p and c.baseline is base
    assert (c.started,c.calls,c.waits)==spent and not c.prompt_ack
    s.previous=["a"];s.finish();assert s.c is c and s.last_next=="after-strength"

def test_pure_recomputes_native_idle_and_fixed_case_instead_of_accepting_forged_labels():
    for change in (lambda o:o.update(source_case="1f_entry"),lambda o:o.update(player_y_pixels=0xEC),
                   lambda o:o.update(joy_ignore=255),lambda o:o.update(source_block=0)):
        s=h.Session("2f_after_fall")
        h.review(s.call(h.canvas(),window=False,ready=True,signal_change=change))

def test_source_fixture_pixels_and_blocks_match_fixed_primary_formulas():
    for key,c in h.DATA["stances"].items():
        x,y=c["start"]["x"],c["start"]["y"];width=c["width"]//2
        assert c["block_address"]==0xC6E8+(y//2+3)*(width+6)+(x//2+3)
        assert c["bst_offset"]==c["block_id"]*16+(y%2*2+1)*4+x%2*2
    assert h.DATA["stances"]["2f_after_fall"]["tile"]==42

@pytest.mark.parametrize("value",[False,0.0])
def test_pure_source_location_zero_requires_genuine_integer_not_equality_alias(value):
    s=h.Session("2f_entry")
    h.review(s.call(h.canvas(),window=False,ready=True,signal_change=lambda o:o["location"].update(x=value)))
    assert s.c.baseline is None and s.c.pending is None

def test_orphan_controller_with_removed_mechanic_never_returns_none_to_navigation():
    s=bh.BridgeSession("3f_entry");s.call(h.canvas(),window=False,ready=True)
    c=s.c;pending=c.pending;clock=c.started;calls=c.calls
    bh.bridge._BINDINGS.clear();s.plan["steps"][0].pop("mechanic")
    assert bh.bridge.applies(s.step_id,s.plan["steps"][0])
    out=s.call(h.canvas(),window=False)
    bh.review(out,"intent_changed")
    assert s.c is c and c.pending is pending and c.started==clock and c.calls==calls
