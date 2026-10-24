"""精確Rival7F座標WAIT的純輸入測試，沒有RAM／按鍵／模型呼叫。"""
from copy import deepcopy
import importlib
import pytest
from laya_pokemon import silph_rival_wait as mod

STEP=dict(id="silph7-rival-test",kind="move",map_id=212,target=[3,3],
          await_script_event=True,event="beat_silph_co_rival")


def state(frame=1):
    return dict(frame=frame,location=dict(map_id=212,x=3,y=3),
        battle_state=dict(kind="none",active=False,raw=0,observation_frame=frame),
        progress=dict(profile="gen1-wrapper-ram-progress-v1-unvalidated",
            initialization_candidate=True,party_read_valid=True,party_count=1,
            party=[dict(species=7,species_name="NIDOKING",level=35,exp=42875,hp=100,max_hp=121,
                        status=0,moves=[61,57,30,40],pp=[20,15,25,35])],
            inventory=[dict(item=48,quantity=1)],story_event_bits={"beat_silph_co_rival":False}))


@pytest.fixture(autouse=True)
def clear_test_budget():
    mod._RIVAL_WAITS.clear()
    yield
    mod._RIVAL_WAITS.clear()


def review(value):
    assert value["phase"]=="campaign_review" and value["available_actions"]==["wait"],value


def test_only_wait_at_exact_trigger_and_input_data_not_mutated_or_claimed_win():
    s=state();p=deepcopy(STEP);before=deepcopy((s,p))
    out=mod.silph_rival_script_wait(s,p,now=0)
    assert out["phase"]=="overworld" and out["available_actions"]==["wait"]
    assert out["route_step"]==p["id"] and out["goal"]==p["id"] and out["source_coordinate_script_wait"]
    assert out["choice_source"]=="silph_rival_coordinate_script_wait"
    assert "complete" not in out and "victory_confirmed" not in out
    assert (s,p)==before and s["progress"]["story_event_bits"]["beat_silph_co_rival"] is False


@pytest.mark.parametrize("field,value",[("kind","interact"),("map_id",211),("map_id",True),
    ("target",[3,2]),("target",[True,3]),("target",(3,3)),("await_script_event",1),
    ("event","beat_silph_co_giovanni"),("id",""),("id",True),("id","bad owner"),
    ("next_map",235),("terminal",True)])
def test_not_generic_coordinate_event_wait(field,value):
    p={**STEP,field:value};review(mod.silph_rival_script_wait(state(),p,now=0))
    assert not mod._RIVAL_WAITS


@pytest.mark.parametrize("change",["map","x","y","bool","frame","battleframe","progressframe","locationframe"])
def test_same_observation_stance_and_true_frame_required(change):
    s=state()
    if change=="map":s["location"]["map_id"]=208
    elif change=="x":s["location"]["x"]=2
    elif change=="y":s["location"]["y"]=2
    elif change=="bool":s["location"]["x"]=True
    elif change=="frame":s["frame"]=True
    elif change=="battleframe":s["battle_state"]["observation_frame"]=0
    elif change=="progressframe":s["progress"]["observation_frame"]=0
    else:s["location"]["observation_frame"]=0
    review(mod.silph_rival_script_wait(s,STEP,now=0));assert not mod._RIVAL_WAITS


@pytest.mark.parametrize("change",["missing","none","one","wrong_profile","invalid_party","init_bool",
                                 "bad_status","missing_key","key_quantity_bool","duplicate_key"])
def test_effective_party_original_key_and_exact_false_event_prerequisites(change):
    s=state();p=s["progress"]
    if change=="missing":p["story_event_bits"].clear()
    elif change=="none":p["story_event_bits"]["beat_silph_co_rival"]=None
    elif change=="one":p["story_event_bits"]["beat_silph_co_rival"]=1
    elif change=="wrong_profile":p["profile"]="unknown"
    elif change=="invalid_party":p["party_read_valid"]=False
    elif change=="init_bool":p["initialization_candidate"]=1
    elif change=="bad_status":p["party"][0]["status"]=255
    elif change=="missing_key":p["inventory"]=[]
    elif change=="key_quantity_bool":p["inventory"][0]["quantity"]=True
    else:p["inventory"].append(dict(item=48,quantity=1))
    review(mod.silph_rival_script_wait(s,STEP,now=0));assert not mod._RIVAL_WAITS


@pytest.mark.parametrize("battle",[
    dict(kind="none",active=False,raw=True),dict(kind="unknown",active=None,raw=3),
    dict(kind="lost_transition",active=False,raw=255),dict(kind="trainer",active=False,raw=2),
    dict(kind="none",active=None,raw=0)])
def test_unknown_or_inconsistent_battle_is_review_not_fallback_input(battle):
    s=state();s["battle_state"]={**battle,"observation_frame":1}
    review(mod.silph_rival_script_wait(s,STEP,now=0))


@pytest.mark.parametrize("kind,raw",[("trainer",2),("wild",1)])
def test_verified_active_battle_hands_off_without_budget_or_party_takeover(kind,raw):
    s=state();s["battle_state"].update(kind=kind,raw=raw,active=True)
    assert mod.silph_rival_script_wait(s,STEP,now=0) is None
    assert not mod._RIVAL_WAITS
    mod.silph_rival_script_wait(state(),STEP,now=0)
    old=deepcopy(mod._RIVAL_WAITS)
    s["frame"]=s["battle_state"]["observation_frame"]=2
    assert mod.silph_rival_script_wait(s,STEP,now=1) is None
    assert mod._RIVAL_WAITS==old


def test_true_event_hands_back_without_claiming_closed_ui_or_new_win():
    s=state();s["progress"]["story_event_bits"]["beat_silph_co_rival"]=True
    assert mod.silph_rival_script_wait(s,STEP,now=0) is None
    assert not mod._RIVAL_WAITS
    mod.silph_rival_script_wait(state(),STEP,now=0);old=deepcopy(mod._RIVAL_WAITS)
    s["frame"]=s["battle_state"]["observation_frame"]=2
    assert mod.silph_rival_script_wait(s,STEP,now=1) is None
    assert mod._RIVAL_WAITS==old


def test_twenty_five_calls_limit_is_cumulative_including_repeated_same_frame():
    for n in range(25):
        out=mod.silph_rival_script_wait(state(),STEP,now=n/10)
        assert out["available_actions"]==["wait"] and out["silph_rival_wait_calls"]==n+1
    review(mod.silph_rival_script_wait(state(),STEP,now=2.5))
    assert mod._RIVAL_WAITS[STEP["id"]]["calls"]==26
    review(mod.silph_rival_script_wait(state(),STEP,now=2.6))
    assert mod._RIVAL_WAITS[STEP["id"]]["calls"]==26


@pytest.mark.parametrize("now",[-1,True,float("nan"),float("inf"),"1"])
def test_invalid_clock_does_not_create_budget(now):
    review(mod.silph_rival_script_wait(state(),STEP,now=now));assert not mod._RIVAL_WAITS


def test_exact_sixty_seconds_allowed_beyond_reviews_without_reset():
    mod.silph_rival_script_wait(state(),STEP,now=0)
    assert mod.silph_rival_script_wait(state(2),STEP,now=60)["available_actions"]==["wait"]
    review(mod.silph_rival_script_wait(state(3),STEP,now=60.001))


@pytest.mark.parametrize("change",["clock","frame","sameframe_packet","step_owner"])
def test_existing_unique_step_cannot_reset_or_change_binding(change):
    mod.silph_rival_script_wait(state(2),STEP,now=2)
    s=state(3);p=deepcopy(STEP);now=3
    if change=="clock":now=1
    elif change=="frame":s=state(1)
    elif change=="sameframe_packet":s=state(2);s["progress"]["party"][0]["hp"]=99
    else:p["owner"]="other-job"
    review(mod.silph_rival_script_wait(s,p,now=now))
    record=mod._RIVAL_WAITS[STEP["id"]]
    assert record["calls"]==1 and record["started"]==2 and record["step"]==STEP
    assert record["error"] is not None


def test_reload_preserves_global_budget_and_sticky_review():
    mod.silph_rival_script_wait(state(),STEP,now=0);registry=mod._RIVAL_WAITS
    importlib.reload(mod)
    assert mod._RIVAL_WAITS is registry
    assert mod.silph_rival_script_wait(state(2),STEP,now=1)["silph_rival_wait_calls"]==2
    review(mod.silph_rival_script_wait(state(3),STEP,now=.5))
    importlib.reload(mod);review(mod.silph_rival_script_wait(state(4),STEP,now=2))
    assert mod._RIVAL_WAITS[STEP["id"]]["calls"]==2


def test_module_source_event_id_matches_installed_primary_sdk():
    from pyboy.plugins import game_wrapper_pokemon_gen1_constants as c
    assert c.EVENT_FLAGS["beat_silph_co_rival"]==1856==mod.EVENT_ID
    assert c.EVENT_FLAGS_ADDRESS+mod.EVENT_ID//8==mod.EVENT_ADDRESS==0xD82F
    assert mod.EVENT_ID%8==mod.EVENT_BIT==0

