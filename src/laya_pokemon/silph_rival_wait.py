"""希魯夫7F勁敵座標腳本的有界WAIT；不整合runner、不讀寫遊戲。
只等原生腳本啟動，不按A/方向、不把到站或旗標當作本次獲勝回執。
"""
from copy import deepcopy
import math
import re
import time

from .mart_purchase import _party, _inventory

SOURCE_COMMIT = "a53671100ec22e5394ff26ec028d0812a238dae2"
SOURCE = f"https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/scripts/SilphCo7F.asm"
EVENT = "beat_silph_co_rival"
EVENT_ID, EVENT_ADDRESS, EVENT_BIT = 0x740, 0xD82F, 0
MAX_CALLS, MAX_SECONDS = 25, 60
# 熱載入保留同一budget/owner/錯誤，不以reload逃過等待上限。
_RIVAL_WAITS = globals().get("_RIVAL_WAITS", {})


def _int(v, low=0, high=0x7FFFFFFFFFFFFFFF):
    return type(v) is int and low <= v <= high


def _intent(step):
    return (isinstance(step, dict) and isinstance(step.get("id"), str)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", step["id"]) is not None
            and step.get("kind") == "move" and type(step.get("map_id")) is int
            and step["map_id"] == 212 and type(step.get("target")) is list
            and len(step["target"]) == 2 and all(type(v) is int for v in step["target"])
            and step["target"] == [3, 3] and step.get("await_script_event") is True
            and step.get("event") == EVENT and "next_map" not in step
            and step.get("terminal", False) is False)


def silph_rival_script_wait(state, step, *, now=None):
    """state為同次observe的frame/location/progress/battle_state；只動自己的budget。
    有效active battle回None讓caller交還既有戰鬥管線，不建立/消耗WAIT紀錄。
    其他未知只review。now預設單調時鐘，測試可明確注入同一時間域。
    """
    sid = step.get("id") if isinstance(step, dict) else None
    record = _RIVAL_WAITS.get(sid) if isinstance(sid, str) else None

    def review(reason):
        if record is not None:
            record["error"] = reason
        return dict(phase="campaign_review", objective="Wait.", available_actions=["wait"],
                    review_reason="silph_rival_wait_" + reason, route_step=sid,
                    source_commit=SOURCE_COMMIT, choice_source="silph_rival_coordinate_script_wait")

    if not _intent(step):
        return review("intent_unverified")
    if record is not None and record["step"] != step:
        return review("step_id_binding_changed")
    if not isinstance(state, dict):
        return review("observation_unverified")
    frame, loc, battle = state.get("frame"), state.get("location"), state.get("battle_state")
    if (not _int(frame) or not isinstance(loc, dict)
            or any(type(loc.get(k)) is not int for k in ("map_id", "x", "y"))
            or (loc["map_id"], loc["x"], loc["y"]) != (212, 3, 3)
            or not isinstance(battle, dict) or type(battle.get("observation_frame")) is not int
            or battle["observation_frame"] != frame or type(battle.get("raw")) is not int):
        return review("same_frame_location_or_battle_unverified")
    for p in (loc, state.get("progress")):
        if not isinstance(p, dict) or ("observation_frame" in p and
                (type(p["observation_frame"]) is not int or p["observation_frame"] != frame)):
            return review("packet_frame_disagrees")
    if (battle.get("active") is True and
            (battle.get("kind"), battle["raw"]) in (("wild", 1), ("trainer", 2))):
        return None
    if battle.get("kind") != "none" or battle.get("active") is not False or battle["raw"] != 0:
        return review("nonbattle_unverified")
    p = state["progress"]
    party = _party(p)
    inventory = _inventory(p.get("inventory"))
    if (p.get("initialization_candidate") is not True or party is None
            or any(m["status"] not in (*range(8), 8, 16, 32, 64) for m in party)
            or inventory is None or [i for i in inventory if i["item"] == 48] != [{"item":48,"quantity":1}]
            or not isinstance(p.get("story_event_bits"), dict)
            or type(p["story_event_bits"].get(EVENT)) is not bool):
        return review("key_party_or_false_event_unverified")
    if p["story_event_bits"][EVENT] is True:
        return None  # 交回既有對話/路線；原始位元不證本次勝利或UI已閉。
    now = time.monotonic() if now is None else now
    if (type(now) not in (int, float) or not math.isfinite(now) or now < 0
            or record is not None and (now < record["last_now"] or frame < record["last_frame"])):
        return review("clock_or_frame_regressed")
    if record is None:
        record = dict(step=deepcopy(step), started=now, last_now=now, last_frame=-1,
                      packet=None, calls=0, error=None)
        _RIVAL_WAITS[sid] = record
    if record["error"] is not None:
        return review(record["error"])
    packet = deepcopy((loc, p, battle))
    if record["last_frame"] == frame and record["packet"] != packet:
        return review("same_frame_packet_conflict")
    record["calls"] += 1
    record["last_now"], record["last_frame"], record["packet"] = now, frame, packet
    if record["calls"] > MAX_CALLS or now - record["started"] > MAX_SECONDS:
        return review("budget_exhausted")
    return dict(phase="overworld", objective="Wait.", available_actions=["wait"],
                goal=sid, route_step=sid, source_coordinate_script_wait=True,
                source_commit=SOURCE_COMMIT, source=SOURCE, silph_rival_wait_calls=record["calls"],
                choice_source="silph_rival_coordinate_script_wait",
                phase_source="SilphCo7F.asm:122–204；留在3,3等原生座標腳本，不把到站當成勝利。")

