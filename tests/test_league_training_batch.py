"""可攜合成驗證：只造 RAM/tiles/frame/time，執行真正 SDK/readers/pure/bridge。

不初始化 PyBoy、不讀 ROM/state，不用假的成功controller。SDK Python getter來源與
已安裝套件同目錄；只將其真 getter 掛至沒有 setter 的測試 adapter。
"""
from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from pyboy.plugins import game_wrapper_pokemon_gen1 as compiled_sdk
from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
from laya_pokemon.observation import read_visible_text
from laya_pokemon.progress import read_progress
from laya_pokemon.battle import read_battle_state,battle_context
from laya_pokemon.world_map import read_world_grid

HERE=Path(__file__).resolve().parent
if HERE.name=="staged-league-training-runtime-20261028" and HERE.parent.name==".local":
    SOURCE=HERE
elif HERE.name=="tests":
    SOURCE=HERE.parent/"src/laya_pokemon"
else:raise RuntimeError("只能使用精確stage或formal tests目錄")


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path.resolve(strict=True))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert Path(module.__file__).resolve()==path.resolve()
    return module


bridge=load("laya_pokemon._training_batch_bridge_test",SOURCE/"league_training_batch_bridge.py")
b=bridge.batch
sdk_python=load("pyboy.plugins._training_readonly_sdk_source",
                Path(compiled_sdk.__file__).with_name("game_wrapper_pokemon_gen1.py"))
real=sdk_python.GameWrapperPokemonGen1


class Memory:
    def __init__(self):self.values={};self.reads=[];self.hook=None
    def __getitem__(self,key):
        if isinstance(key,slice):return [self[i] for i in range(key.start,key.stop,key.step or 1)]
        self.reads.append(key)
        if isinstance(key,tuple):
            bank,address=key
            value=(0x20 if address==0x3000 or 0x4000<=address<0x4010 else 255 if address==0x3001 else 0)
        else:value=self.values.get(key,0)
        return self.hook(key,value) if self.hook else value
    def __setitem__(self,*args):raise AssertionError("禁止測試對被測getter寫RAM")


class RealSDKGetters:
    _read_u16=real._read_u16
    _read_name=real._read_name
    _read_party_mon=real._read_party_mon
    party=real.party
    inventory=real.inventory
    money=real.money
    def __init__(self,pb):self.pyboy=pb
    def _get_screen_background_tilemap(self):
        # world_map的真正解碼器仍須比對完整可見背景；外邊界會由其排除。
        return np.full((36,40),0x20,dtype=np.uint16)


class FakeTilemap:
    def __init__(self):self.cells={}
    def __getitem__(self,point):return self.cells.get(point,0x7F)


class FakePyBoy:
    def __init__(self):
        self.frame_count=1;self.memory=Memory();self.game_wrapper=RealSDKGetters(self)
        self.tilemap_background=FakeTilemap();self.tilemap_window=FakeTilemap()
        self.screen=SimpleNamespace(tilemap_position_list=[(0,0,0,0)]*144)
        self.memory.values.update({0xD35E:194,0xD362:28,0xD361:7,0xD367:17,0xD368:9,0xD369:15,
            0xD52B:13,0xD52C:0,0xD52D:0x40,0xD530:0,0xD531:0x30,0xD535:255,
            0xFF40:0x91,sdk.PARTY_COUNT_ADDRESS:6,sdk.OBTAINED_BADGES_ADDRESS:255,
            0xCFE5:sdk.POKEMON_SPECIES["MACHOP"]})
        for index,byte in enumerate((1,0x23,0x45)):
            self.memory.values[sdk.PLAYER_MONEY_ADDRESS+index]=byte
        for index,ch in enumerate("KEVIN"):
            self.memory.values[sdk.PLAYER_NAME_ADDRESS+index]=sdk.POKEMON_TEXT_ENCODING[ch]
        self.memory.values[sdk.PLAYER_NAME_ADDRESS+5]=0x50
        mons=[(102,35,[33,28,98,39],[35,15,30,30]),(154,35,[75,15,73,22],[25,30,10,10]),
              (7,36,[61,57,30,40],[20,15,25,35]),(35,37,[64,65,19,31],[35,20,15,20]),
              (19,41,[57,34,58,109],[15,15,10,10]),(132,41,[70,133,156,34],[15,20,10,15])]
        for i,(species,level,moves,pps) in enumerate(mons):
            address=sdk.PARTY_MONS_ADDRESS+i*sdk.PARTY_MON_SIZE
            self.memory.values.update({address:species,address+0x21:level,address+1:0,address+2:120,
                                       address+0x22:0,address+0x23:120})
            for offset,value in enumerate(moves):self.memory.values[address+8+offset]=value
            for offset,value in enumerate(pps):self.memory.values[address+29+offset]=value
            self.experience(i,level**3)
    def experience(self,index,value):
        address=sdk.PARTY_MONS_ADDRESS+index*sdk.PARTY_MON_SIZE+14
        for offset,byte in enumerate(value.to_bytes(3,"big")):self.memory.values[address+offset]=byte
    def get_sprite(self,index):
        return SimpleNamespace(x=(self.memory.values[0xD362]-20)*16,
                               y=self.memory.values[0xD361]*16-4)
    def tick(self,*args):raise AssertionError("禁止tick")
    def button(self,*args):raise AssertionError("禁止按鍵")
    def save_state(self,*args):raise AssertionError("禁止存檔")
    def load_state(self,*args):raise AssertionError("禁止讀檔")


def plan():
    return dict(mode="league_campaign",training_job="league-six-party45-new-job-20261028",
        lead_species=102,steps=[dict(id="training-001",kind="interact",mechanic=bridge.MECHANIC,
        map_id=194,target=[28,7],training_intent=deepcopy(b.INTENT)),
        dict(id="after-001",kind="move",map_id=194,target=[28,7])])


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for key,value in (("_CONTROLLERS",{}),("_BINDINGS",{}),("_COMPLETED",set()),("_ERRORS",{}),("_OWNERS",{})):
        monkeypatch.setattr(bridge,key,value)
    from laya_pokemon import battle
    monkeypatch.setattr(battle,"_no_pp_switch",None);monkeypatch.setattr(battle,"_fixed_damage_risk",None)


class Session:
    def __init__(self):
        self.pb=FakePyBoy();self.plan=plan();self.step_id="training-001";self.previous=[];self.now=10.
        self.last_state=self.last_text=self.last_grid=None;self.next_id=None
    @property
    def c(self):return bridge._CONTROLLERS[self.step_id]
    @property
    def player(self):return self.pb.memory.values[0xD362],self.pb.memory.values[0xD361]
    def place(self,player):self.pb.memory.values[0xD362],self.pb.memory.values[0xD361]=player
    def call(self,*,same=False,raw=0,window=False,no_grid=False,previous=None,
             state_change=None,text_change=None,grid_change=None,pre_attrition=False):
        if not same:self.pb.frame_count+=1;self.now+=.05
        self.pb.memory.values[0xD057]=raw;self.pb.memory.values[0xFF40]=0xB1 if window else 0x91
        self.pb.tilemap_window.cells.clear()
        if window:
            for i,ch in enumerate("LAPRAS used SURF!"):
                self.pb.tilemap_window.cells[(i+1,14)]=sdk.POKEMON_TEXT_ENCODING[ch]
        text=read_visible_text(self.pb);text["observation_frame"]=self.pb.frame_count
        if text_change:text_change(text)
        loc=dict(map_id=self.pb.memory.values[0xD35E],x=self.player[0],y=self.player[1])
        grid=read_world_grid(self.pb,loc)
        if grid_change:grid_change(grid)
        if no_grid:grid=None
        progress=read_progress(self.pb,sdk);native=read_battle_state(self.pb)
        state=dict(frame=self.pb.frame_count,location=loc,progress=progress,battle_state=native,
                   phase="unclassified",objective="Continue route.",available_actions=["left","right","wait"])
        if raw==1:state.update(battle_context(text,native,progress["party"],progress["inventory"]))
        if state_change:state_change(state)
        self.last_state,self.last_text,self.last_grid=deepcopy(state),text,grid
        prior=self.previous if previous is None else previous
        oldclock=bridge.time
        bridge.time=SimpleNamespace(monotonic=lambda:self.now)
        try:
            result=(bridge.pre_attrition_closure_context(self.pb,state,self.plan,self.step_id,
                dict(review_reason="party_attrition_requires_center"),text,grid,prior)
                if pre_attrition else bridge.context(self.pb,state,self.plan,self.step_id,text,grid,prior))
        finally:bridge.time=oldclock
        if result is None:self.next_id=None;return None
        out,self.next_id=result
        return out
    def advance(self,*,wild=False,ack=True):
        pending=deepcopy(self.c.pending);assert pending
        self.place(pending["expected"]);self.previous=[pending["action"]] if ack else ["wait"]
        return self.call(raw=1 if wild else 0,window=wild,no_grid=wild)
    def reward(self):
        old=read_progress(self.pb,sdk)["party"][0]
        self.pb.experience(0,old["exp"]+120)
        address=sdk.PARTY_MONS_ADDRESS
        self.pb.memory.values[address+2]-=4;self.pb.memory.values[address+29]-=1
        self.previous=["a"]
    def finish_wild(self,**kwargs):
        self.call();self.advance(wild=True);self.reward()
        first=self.call(**kwargs);assert not first["training_batch_complete"]
        final=self.call(**kwargs);assert final["training_batch_complete"]
        return final


def review(out,fragment=None):
    assert out["phase"]=="campaign_review" and out["available_actions"]==["wait"],out
    if fragment:assert fragment in out["review_reason"],out


def reload_bridge():
    spec=importlib.util.spec_from_file_location(bridge.__name__,SOURCE/"league_training_batch_bridge.py")
    spec.loader.exec_module(bridge)


def test_true_readers_complete_first_wild_only_after_two_fresh_blank_worlds():
    s=Session();out=s.call();assert out["available_actions"]==["down","wait"]
    pending=s.c.pending;baseline=s.c.baseline
    out=s.advance(wild=True)
    assert out["training_batch_battle_delegate"]=="existing_battle"
    assert out["phase"]==s.last_state["phase"]=="battle_dialogue"
    assert out["objective"]==s.last_state["objective"] and out["available_actions"]==["a","wait"]
    assert s.c.pending is pending and pending["executed"] and s.c.baseline is baseline
    assert s.c.displacements==0 and s.next_id==s.step_id and bridge.applies("foreign",None)
    s.reward();first=s.call();frame=s.c.closed_frame
    assert not first["training_batch_complete"] and s.c.pending is pending
    assert not s.call(same=True)["training_batch_complete"] and s.c.closed_frame==frame
    final=s.call();assert final["field_move_complete"] and s.next_id=="after-001"
    assert final["training_batch_outcome"]=="complete_single_wild" and s.c.pending is None
    assert s.c.displacements==1 and final["training_batch_receipt"]["total_exp_gain"]==120
    assert final["training_batch_receipt"]["total_pp_spent"]==1


def test_32_actual_coordinate_displacements_without_encounter_close_separately():
    s=Session();s.call()
    for i in range(32):
        out=s.advance();assert s.c.displacements==i+1
        assert not out["training_batch_complete"]
    assert s.c.pending is None and s.c.closed_frame is not None
    out=s.call();assert out["training_batch_outcome"]=="complete_no_encounter"
    assert out["training_batch_receipt"]["wild_count"]==0 and s.c.displacements==32


def test_no_encounter_closure_never_swallows_an_unowned_33rd_displacement():
    s=Session();s.call()
    for _ in range(32):s.advance()
    s.place((28,8));review(s.call(),"unowned_displacement_after_walk_budget")
    assert s.c.displacements==32 and not bridge._COMPLETED


def test_second_native_wild_after_first_verified_return_cannot_count_as_one_battle():
    s=Session();s.call();s.advance(wild=True);s.reward();s.call()
    review(s.call(raw=1,window=True,no_grid=True),"second_wild_after_verified_return")
    assert not bridge._COMPLETED


def test_dialogue_between_closed_return_and_second_raw1_cannot_erase_return_history():
    s=Session();s.call();s.advance(wild=True);s.reward();s.call()
    s.call(window=True,no_grid=True,state_change=lambda st:st.update(
        phase="dialogue",objective="Confirm visible text.",available_actions=["a","wait"]))
    assert s.c.closed_frame is None and s.c.returned_world_seen
    review(s.call(raw=1,window=True,no_grid=True),"second_wild_after_verified_return")


def test_offers_alone_do_not_credit_steps_and_requests_are_bounded():
    s=Session();s.call();pending=s.c.pending
    for _ in range(b.MAX_REQUESTS):out=s.call()
    review(out,"request_budget");assert s.c.displacements==0 and s.c.pending is pending


def test_subsequent_battle_directions_never_ack_original_unexecuted_pending():
    s=Session();s.call();p=s.c.pending;s.advance(wild=True,ack=False)
    assert p["executed"] is False
    s.call(raw=1,window=True,no_grid=True,previous=[p["action"]])
    assert p["executed"] is False
    s.reward();review(s.call(),"displacement_without_true_previous")


def test_same_frame_conflict_and_frame_or_time_rollback_are_sticky():
    s=Session();s.call();pending=s.c.pending
    review(s.call(same=True,previous=["down"]),"same_frame_conflict")
    old=s.c.error;review(s.call());assert s.c.error==old and s.c.pending is pending


@pytest.mark.parametrize("clock",[-1.,float("nan"),float("inf"),False])
def test_invalid_native_clock_is_sticky(clock):
    s=Session();s.call();s.now=clock;review(s.call(),"owner_frame_or_time")


def test_frame_rollback_is_not_repaired_by_new_wallclock():
    s=Session();s.call();s.pb.frame_count=0;review(s.call(),"owner_frame_or_time")


def test_same_frame_is_never_a_second_closed_receipt():
    s=Session();s.call();s.advance(wild=True);s.reward();s.call()
    for _ in range(3):assert not s.call(same=True)["training_batch_complete"]
    assert s.call()["training_batch_complete"]


def test_return_dialogue_keeps_truthy_owner_and_resets_first_closed_receipt():
    s=Session();s.call();s.advance(wild=True);s.reward();s.call();assert s.c.closed_frame
    out=s.call(window=True,no_grid=True,state_change=lambda st:st.update(
        phase="dialogue",objective="Confirm visible text.",available_actions=["a","wait"]))
    assert out["training_batch_battle_delegate"]=="existing_battle" and s.c.closed_frame is None
    assert s.next_id==s.step_id and s.c.suspended
    assert not s.call()["training_batch_complete"]
    assert s.call()["training_batch_complete"]


def test_unknown_existing_battle_context_becomes_owned_wait_not_navigation():
    s=Session();s.call();out=s.advance(wild=True)
    out=s.call(raw=1,window=True,no_grid=True,state_change=lambda st:st.update(
        phase="unclassified",objective="Move left.",available_actions=["left","wait"]))
    assert out["training_batch_battle_delegate"]=="await_existing_battle_context"
    assert out["available_actions"]==["wait"] and s.next_id==s.step_id


def test_actual_existing_battle_review_is_preserved():
    s=Session();s.call();s.advance(wild=True)
    out=s.call(raw=1,window=True,no_grid=True,state_change=lambda st:st.update(
        phase="strategy_review",objective="Wait.",available_actions=["wait"],review_reason="existing_native_review"))
    assert out["phase"]=="strategy_review" and out["review_reason"]=="existing_native_review"


@pytest.mark.parametrize("raw",[2,3,255])
def test_trainer_loss_and_unknown_raw_never_delegate(raw):
    s=Session();s.call();review(s.call(raw=raw,no_grid=True),"only_native_raw1")


@pytest.mark.parametrize("position",[(27,7),(29,7),(29,8),(28,9)])
def test_stair_exit_or_third_tile_never_becomes_training(position):
    s=Session();s.call();s.place(position);review(s.call(),"location_or_battle")


@pytest.mark.parametrize("mutate,fragment",[
    (lambda s:s.pb.memory.values.update({sdk.PLAYER_MONEY_ADDRESS+2:0x46}),"bag_money"),
    (lambda s:s.pb.memory.values.update({sdk.BAG_ITEM_COUNT_ADDRESS:1,sdk.BAG_ITEMS_ADDRESS:20,sdk.BAG_ITEMS_ADDRESS+1:1}),"bag_money"),
    (lambda s:s.pb.memory.values.update({sdk.PARTY_MONS_ADDRESS+8:1}),"party_or_moves"),
    (lambda s:s.pb.memory.values.update({sdk.PARTY_MONS_ADDRESS+29:36}),"party_or_source_progress"),
    (lambda s:s.pb.memory.values.update({sdk.PARTY_MONS_ADDRESS+2:0}),"fainted_party"),
    (lambda s:s.pb.experience(0,1000000),"wild_level_exp_hp"),
])
def test_unreceipted_resource_or_faint_changes_require_sticky_review(mutate,fragment):
    s=Session();s.call();s.advance(wild=True);s.reward();mutate(s)
    review(s.call(),fragment);error=s.c.error;review(s.call());assert s.c.error==error


def test_raw1_then_escape_without_reward_is_not_reported_training_success():
    s=Session();s.call();s.advance(wild=True)
    review(s.call(),"reward_or_pp_bound");assert not bridge._COMPLETED


def test_low_hp_or_poison_can_only_close_owned_wild_via_wait_then_center_marker():
    s=Session();s.call();s.advance(wild=True);s.reward()
    s.pb.memory.values[sdk.PARTY_MONS_ADDRESS+2]=60
    s.pb.memory.values[sdk.PARTY_MONS_ADDRESS+4]=8
    first=s.call(pre_attrition=True);assert first["available_actions"]==["wait"]
    final=s.call(pre_attrition=True)
    assert final["training_batch_complete"] and final["training_batch_receipt"]["needs_center"] is True
    assert final["available_actions"]==["wait"] and s.next_id=="after-001"


def test_attrition_unknown_fainted_or_unowned_never_gets_exception():
    s=Session();assert s.call(pre_attrition=True) is None
    s.call();s.advance(wild=True);s.reward();s.pb.memory.values[sdk.PARTY_MONS_ADDRESS+2]=0
    assert s.call(pre_attrition=True) is None and s.c.suspended


def test_pending_baseline_job_budget_and_suspension_survive_reload():
    s=Session();s.call();s.advance(wild=True);c=s.c;p=c.pending;base=c.baseline
    spent=(c.started,c.calls,c.displacements,c.requests);reload_bridge()
    assert s.c is c and c.pending is p and c.baseline is base and c.suspended
    assert (c.started,c.calls,c.displacements,c.requests)==spent
    s.call(raw=1,window=True,no_grid=True,previous=["up"]);assert c.pending is p
    s.reward();s.call();assert s.call()["training_batch_complete"] and s.c is c


def test_reload_does_not_reset_exhausted_budget_or_sticky_failure():
    s=Session();s.call();c=s.c;c.calls=b.MAX_CALLS
    review(s.call(),"budget_exhausted");error=c.error;spent=(c.started,c.calls)
    reload_bridge();review(s.call());assert s.c is c and c.error==error and (c.started,c.calls)==spent


@pytest.mark.parametrize("mutate",[
    lambda s:s.plan.update(training_job="foreign"),
    lambda s:s.plan["steps"][0].update(label="new canonical step"),
    lambda s:s.plan["steps"][0].pop("mechanic"),
    lambda s:s.plan["steps"].pop(0),
])
def test_active_binding_changes_are_sticky_and_cannot_reconstruct_controller(mutate):
    s=Session();s.call();c=s.c;p=c.pending;mutate(s);review(s.call())
    assert s.c is c and c.pending is p and not bridge._COMPLETED


def test_foreign_owner_is_sticky_on_original_owner_after_return():
    s=Session();s.call();c=s.c;s.step_id="foreign";review(s.call(),"owner_changed")
    s.step_id="training-001";review(s.call(),"owner_changed");assert s.c is c


def test_native_session_identity_cannot_change_with_matching_synthetic_ram():
    s=Session();s.call();original=s.pb;foreign=FakePyBoy();foreign.frame_count=s.pb.frame_count
    s.pb=foreign;review(s.call(),"native_session_owner_changed")
    s.pb=original;review(s.call(),"native_session_owner_changed")


def test_missing_session_owner_never_rebinds_existing_pending():
    s=Session();s.call();pending=s.c.pending;bridge._OWNERS.clear()
    review(s.call(),"original_session_owner_missing");assert s.c.pending is pending


def test_unknown_native_facing_does_not_issue_a_direction():
    s=Session();s.pb.memory.values[0xC109]=255;review(s.call(),"source_derivation")


def test_invalid_registry_types_return_review_instead_of_crashing(monkeypatch):
    s=Session();monkeypatch.setattr(bridge,"_ERRORS",None)
    review(s.call(),"registries_unverified")


@pytest.mark.parametrize("field,value",[("kind","move"),("map_id",True),("target",[28,True]),
    ("recovery_route",True),("next_map",34),("event",1234)])
def test_explicit_intent_cannot_be_used_as_shortcut(field,value):
    s=Session();s.plan["steps"][0][field]=value;review(s.call(),"explicit_intent")
    assert not bridge._BINDINGS


def test_true_lowest_lead_required_before_start_and_all_six_45_checkpoint_stops():
    s=Session();s.plan["lead_species"]=19;review(s.call(),"true_lowest_lead")
    assert not bridge._BINDINGS
    s=Session()
    for i in range(6):s.pb.memory.values[sdk.PARTY_MONS_ADDRESS+i*sdk.PARTY_MON_SIZE+0x21]=45
    review(s.call(),"all_six_45_checkpoint")


def test_source_getter_double_reads_native_bytes_and_rejects_bool_or_torn_values():
    s=Session();o=b.read_training_observation(s.pb,s.pb.frame_count,sdk)
    assert o["read_valid"] and o["idle"] and o["location"]==dict(map_id=194,x=28,y=7)
    assert all(s.pb.memory.reads.count(address)>=2 for address in b.ADDRESSES.values())
    s.pb.memory.hook=lambda address,value:False if address==0xD700 else value
    assert not b.read_training_observation(s.pb,s.pb.frame_count,sdk)["read_valid"]


def test_real_source_grid_requires_both_tiles_in_visible_proof_and_tile20():
    s=Session();review(s.call(grid_change=lambda grid:grid["tiles"][8].__setitem__(28,5)),"initial_source_world")
    assert not bridge._BINDINGS
    s=Session();review(s.call(grid_change=lambda grid:grid["visible_verified_cells"].remove([28,8])),"initial_source_world")


def test_source_progress_cannot_be_replaced_by_caller_claim():
    s=Session();review(s.call(state_change=lambda st:st["progress"]["party"][0].update(exp=99)),"party_or_source_progress")


def test_sdk_readers_are_actual_source_functions_and_no_emulator_input_available():
    assert RealSDKGetters.party.fget is real.party.fget
    assert RealSDKGetters._read_party_mon is real._read_party_mon
    s=Session();s.call();assert s.last_text["read_valid"] and s.last_grid["screen_cells_verified"]>=12
    with pytest.raises(AssertionError):s.pb.tick()
    with pytest.raises(AssertionError):s.pb.button("a")
    with pytest.raises(AssertionError):s.pb.memory[0xD057]=0


def test_pure_import_frozen_package_data_matches_reference_without_context_io(monkeypatch):
    from hashlib import sha256
    from laya_pokemon import team_strategy
    ref=team_strategy.reference()
    reference_path=SOURCE/"data/gen1_reference.json" if HERE.name=="tests" else HERE.parent.parent/"src/laya_pokemon/data/gen1_reference.json"
    assert sha256(reference_path.read_bytes()).hexdigest() in (b.REFERENCE_SHA256,
        "d427fd277d23235bc25ef4da6fd68a20e5b1f4412f807815a496ef58d9e8b330")
    assert len(b.MOVE_DATA)==165
    assert all(b.MOVE_DATA[m["id"]]==(m["pp"],m["power"])
               for m in ref["moves"].values())
    with pytest.raises(TypeError):b.MOVE_DATA[33]=(99,99)
    s=Session();s.call();s.advance(wild=True);s.reward()
    s.pb.frame_count+=1;s.now+=.05;s.pb.memory.values.update({0xD057:0,0xFF40:0x91})
    loc=dict(map_id=194,x=s.player[0],y=s.player[1])
    text=read_visible_text(s.pb);text["observation_frame"]=s.pb.frame_count
    grid=read_world_grid(s.pb,loc)
    state=dict(frame=s.pb.frame_count,location=loc,progress=read_progress(s.pb,sdk),
               battle_state=read_battle_state(s.pb),phase="unclassified")
    # 真getter已取得fresh正常返場packet後，純context不能再靠reference或open讀檔。
    signal=b.read_training_observation(s.pb,s.pb.frame_count,sdk)
    def forbidden(*args,**kwargs):raise AssertionError("純controller不得讀檔")
    monkeypatch.setattr(team_strategy,"reference",forbidden)
    monkeypatch.setattr("builtins.open",forbidden)
    out=s.c.context(state,text=text,grid=grid,signal=signal,
                    previous=s.previous,now=s.now,owner=s.step_id)
    assert out["available_actions"]==["wait"] and out["phase"]!="campaign_review"
    assert out["training_batch_tactic"]=="first_closed_source_world"
