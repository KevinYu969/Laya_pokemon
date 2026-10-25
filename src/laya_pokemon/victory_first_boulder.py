"""VR1 slot5 first-switch source candidate: fixed18 pushes, existing normal BFS walks.

Read-only getter and pure child goals. No input, tick, ROM/state or runtime box search.
Native contact/dust phases can be skipped by sampling; receipts report what was seen.
"""
from collections.abc import Mapping
from copy import deepcopy
import math
from laya_pokemon.hm_teaching import _rows
from laya_pokemon.mart_purchase import _party,_inventory
from laya_pokemon.team_strategy import reference,move_key,species_key,PROTECTED_HMS
from laya_pokemon.world_map import world_direction

SOURCE_COMMIT="a53671100ec22e5394ff26ec028d0812a238dae2"
PROFILE="red-en-victory-first-boulder-source-v1-unvalidated"
INTENT=dict(kind="victory_first_boulder",map_id=108,slot=5,start_player=[8,16],
            start_boulder=[5,15],goal_boulder=[17,13],event_id=0x917)
MAX_SECONDS,MAX_CALLS,MAX_STEP_SECONDS,MAX_STEP_WAITS,MAX_REQUESTS=900,2400,60,30,8
PUSHES=(
    ('down',(5,14),(5,15),(5,16)),('right',(4,16),(5,16),(6,16)),
    ('right',(5,16),(6,16),(7,16)),('right',(6,16),(7,16),(8,16)),
    ('right',(7,16),(8,16),(9,16)),('up',(9,17),(9,16),(9,15)),
    ('up',(9,16),(9,15),(9,14)),('right',(8,14),(9,14),(10,14)),
    ('right',(9,14),(10,14),(11,14)),('right',(10,14),(11,14),(12,14)),
    ('right',(11,14),(12,14),(13,14)),('right',(12,14),(13,14),(14,14)),
    ('right',(13,14),(14,14),(15,14)),('right',(14,14),(15,14),(16,14)),
    ('up',(16,15),(16,14),(16,13)),('up',(16,14),(16,13),(16,12)),
    ('right',(15,12),(16,12),(17,12)),('down',(17,11),(17,12),(17,13)))
DELTAS=dict(up=(0,-1),down=(0,1),left=(-1,0),right=(1,0))
FACING=dict(down=0,up=4,left=8,right=12)
BAD_EDGES=frozenset((((8,16),(8,17)),((9,16),(9,17))))
STATIC_POSITIONS=((7,5),(3,2),(11,0),(9,2),(5,15),(14,2),(2,10))
ADDRESSES=dict(map_id=0xD35E,y=0xD361,x=0xD362,facing_raw=0xC109,
    tileset=0xD367,height=0xD368,width=0xD369,object_count=0xD4E1,
    flags1=0xD728,flags3=0xD72D,flags5=0xD730,flags6=0xD732,flags7=0xD733,
    mode=0xD700,battle_raw=0xD057,misc=0xCD60,boulder_index=0xD718,
    collision_result=0xD71C,joy_ignore=0xCD6B,walk_counter=0xCFC5,simulated=0xCD38,
    movement_flags=0xD736,event_raw=0xD869,gate_block=0xC77F)


def _int(v,lo=0,hi=255):return type(v) is int and lo<=v<=hi
def _get(obj,key):return obj.get(key) if isinstance(obj,Mapping) else getattr(obj,key,None)
def _unknown(frame,reason):
    return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,observation_frame=frame,
        read_valid=False,read_error=reason,location=None,stone=None,objects=None,
        raw=None,idle=None,native_push_busy=None,event=None,live_calibrated=False)


def _anchors(constants):
    anchors=dict(STATUS_FLAGS3_ADDRESS=0xD72D,EVENT_FLAGS_ADDRESS=0xD747,OBTAINED_BADGES_ADDRESS=0xD356)
    maps,events=_get(constants,"MAPS"),_get(constants,"EVENT_FLAGS")
    return (all(type(_get(constants,k)) is int and _get(constants,k)==v for k,v in anchors.items())
        and isinstance(maps,Mapping) and type(maps.get("victory_road_1f")) is int and maps["victory_road_1f"]==108
        and isinstance(events,Mapping) and type(events.get("victory_road_1_boulder_on_switch")) is int
        and events["victory_road_1_boulder_on_switch"]==0x917)


def _native_state(a,stone):
    busy=bool(a["flags5"]&1 or a["misc"]&2 or stone["walk_counter"] or stone["movement_byte2"]==0xFF)
    idle=(a["joy_ignore"]==a["walk_counter"]==a["simulated"]==0 and not busy
        and not a["movement_flags"]&0xFB and not a["flags5"]&0xA7
        and not a["flags3"]&0x18 and not a["flags6"]&0x5C and not a["flags7"]&4
        and a["mode"]==a["battle_raw"]==0 and stone["movement_byte1"]==0xFF
        and stone["status"]&0x7F in (1,2))
    return busy,idle


def read_first_boulder_observation(pyboy,observation_frame,constants):
    """Double-read each real byte at one frame; validate BOTH snapshots before equality."""
    if not _int(observation_frame,0,2**63-1):return _unknown(None,"frame_invalid")
    try:
        if not _anchors(constants):return _unknown(observation_frame,"sdk_source_anchors_unverified")
        if type(pyboy.frame_count) is not int or pyboy.frame_count!=observation_frame:
            return _unknown(observation_frame,"frame_not_current")
        def sample():
            a={k:pyboy.memory[address] for k,address in ADDRESSES.items()};objects=[]
            for slot in range(1,8):
                b1,b2=0xC100+16*slot,0xC200+16*slot
                objects.append([pyboy.memory[b1],pyboy.memory[b1+1],pyboy.memory[b2],
                    pyboy.memory[b2+4],pyboy.memory[b2+5],pyboy.memory[b2+6],pyboy.memory[b2+13],
                    pyboy.memory[0xD4E4+2*(slot-1)],pyboy.memory[0xD4E5+2*(slot-1)]])
            return a,objects
        first,second=sample(),sample();after=pyboy.frame_count
    except Exception:return _unknown(observation_frame,"getter_failed")
    def valid(sampled):
        a,objects=sampled
        return (all(_int(v) for v in a.values()) and all(_int(v) for row in objects for v in row)
            and (a["map_id"],a["tileset"],a["height"],a["width"],a["object_count"])==(108,17,9,10,7)
            and objects[4][0]==0x3F and objects[4][6]==0 and objects[4][7] in (0x10,0xFF) and objects[4][8]==5
            and all(objects[i][0]==0x3F and objects[i][6]==0 and objects[i][8]==i+1 for i in (5,6)))
    if not valid(first) or not valid(second):return _unknown(observation_frame,"byte_or_slot_identity_invalid")
    if type(after) is not int or after!=observation_frame or first!=second:
        return _unknown(observation_frame,"torn_frame_or_snapshot")
    a,records=first
    objects=[dict(slot=i+1,picture=row[0],status=row[1],walk_counter=row[2],
        y=row[3]-4,x=row[4]-4,movement_byte1=row[5],picture2=row[6],movement_byte2=row[7],text=row[8])
        for i,row in enumerate(records)]
    stone=objects[4]
    busy,idle=_native_state(a,stone)
    return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,observation_frame=observation_frame,
        read_valid=True,read_error=None,location={k:a[k] for k in ("map_id","x","y")},
        stone=stone,objects=objects,raw=a,idle=idle,native_push_busy=busy,event=bool(a["event_raw"]&128),
        live_calibrated=False)


def _grid(grid,loc,frame):
    if (not isinstance(grid,dict) or type(grid.get("tileset_id")) is not int or grid["tileset_id"]!=17
            or grid.get("verified_location")!=[108,loc[0],loc[1]]
            or type(grid.get("observation_frame")) is not int or grid["observation_frame"]!=frame
            or not _int(grid.get("screen_cells_verified"),12,360)):return False
    visible=grid.get("visible_verified_cells")
    if (not isinstance(visible,list) or len(visible)!=grid["screen_cells_verified"]
            or any(not isinstance(p,list) or len(p)!=2 or not _int(p[0],0,19) or not _int(p[1],0,17) for p in visible)
            or len(set(map(tuple,visible)))!=len(visible)):return False
    for key,high in (("tiles",255),("walkable",1)):
        cells=grid.get(key)
        if (not isinstance(cells,(list,tuple)) or len(cells)!=18 or any(not isinstance(r,(list,tuple))
                or len(r)!=20 or any(not _int(v,0,high) for v in r) for r in cells)):return False
    return grid["walkable"][loc[1]][loc[0]]==1


def _resources(progress):
    party=_party(progress);bag=_inventory(progress.get("inventory")) if isinstance(progress,dict) else None
    if (party is None or len(party)!=6 or len({m["species"] for m in party})!=6 or bag is None
            or not _int(progress.get("money"),0,999999) or progress.get("player_name_raw")!="KEVIN"
            or not _int(progress.get("badges_raw")) or not progress["badges_raw"]&8):return None
    strength_users=[m for m in party if 70 in m["moves"]]
    if len(strength_users)!=1 or strength_users[0]["species"]!=132:return None
    ref=reference()
    if ref.get("source_commit")!=SOURCE_COMMIT:return None
    for mon in party:
        for move,pp in zip(mon["moves"],mon["pp"]):
            key=move_key(move) if move else None
            if (not move and pp or move and (key not in ref["moves"] or (pp&63)>ref["moves"][key]["pp"]*(5+(pp>>6))//5)):
                return None
    return deepcopy(dict(party=party,inventory=bag,money=progress["money"],badges_raw=progress["badges_raw"],
                          player_name_raw=progress["player_name_raw"]))


def _wild_return(before,after):
    if (before["money"]!=after["money"] or before["badges_raw"]!=after["badges_raw"]
            or before["player_name_raw"]!=after["player_name_raw"]
            or [m["species"] for m in before["party"]]!=[m["species"] for m in after["party"]]):return False
    oldbag={i["item"]:i["quantity"] for i in before["inventory"]}
    surviving=[i["item"] for i in before["inventory"] if any(j["item"]==i["item"] for j in after["inventory"])]
    if surviving!=[i["item"] for i in after["inventory"]] or any(i["item"] not in oldbag or i["quantity"]>oldbag[i["item"]] for i in after["inventory"]):
        return False
    ref=reference()
    for old,new in zip(before["party"],after["party"]):
        if new["level"]<old["level"] or new["exp"]<old["exp"]:return False
        mutable={"level","exp","hp","max_hp","status","moves","pp"}
        if ({k:v for k,v in old.items() if k not in mutable}!={k:v for k,v in new.items() if k not in mutable}
                or new["level"]==old["level"] and new["max_hp"]!=old["max_hp"]):return False
        for om,nm,op,np in zip(old["moves"],new["moves"],old["pp"],new["pp"]):
            if om!=nm:
                if move_key(om) in PROTECTED_HMS:return False
                legal={x["move"] for x in ref["species"][species_key(new["species"])]["level_moves"] if old["level"]<x["level"]<=new["level"]}
                if move_key(nm) not in legal or np>>6:return False
            elif (np>>6)!=(op>>6) or (np&63)>(op&63):return False
    return True


class VictoryFirstBoulderController:
    def __init__(self,intent=INTENT):
        if type(intent) is not dict or intent!=INTENT or set(intent)!=set(INTENT):raise ValueError("Only fixed VR1 slot5 first switch")
        if any(type(intent[k]) is not type(v) for k,v in INTENT.items()) or any(type(n) is not int for k in ("start_player","start_boulder","goal_boulder") for n in intent[k]):
            raise ValueError("Fixed intent requires genuine source coordinate integers")
        self.intent=deepcopy(intent);self.contract=deepcopy(intent);self.owner=None
        self.started=self.last_now=self.step_started=None;self.calls=self.waits=self.requests=0
        self.last_frame=-1;self.last_packet=None;self.error=None;self.push_index=0;self.pending=None
        self.baseline=None;self.flags_baseline=None;self.closed_frame=None;self.final_player=None;self.suspended=False
        self.battle_returns=0;self.contact_arm_seen=False;self.native_script_seen=False;self.dust_seen=False

    def _hint(self,action,tactic,complete=False,**extra):
        return dict(phase="victory_first_boulder_complete" if complete else "overworld",
            objective="Wait." if action=="wait" else "Move "+action.upper()+".",
            available_actions=["wait"] if action=="wait" else [action,"wait"],controller_menu_verified=action!="wait",
            first_boulder_complete=complete,first_boulder_tactic=tactic,first_boulder_push_index=self.push_index,
            suppress_navigation_stall=True,suppress_blocked_edge_learning=True,source_commit=SOURCE_COMMIT,
            contact_arm_seen=self.contact_arm_seen,native_script_seen=self.native_script_seen,dust_seen=self.dust_seen,**extra)
    def _fail(self,reason):
        self.error=self.error or "victory_first_boulder_"+reason
        return {**self._hint("wait","review"),"phase":"campaign_review","review_reason":self.error}
    def _wait(self,reason):
        self.waits+=1
        return self._fail("step_wait_budget_exhausted") if self.waits>MAX_STEP_WAITS else self._hint("wait",reason)
    def _reset_step(self,now):
        self.step_started=now;self.waits=self.requests=0;self.pending=None
    def _offer(self,kind,action,player,stone,frame,now):
        self.requests+=1
        if self.requests>MAX_REQUESTS:return self._fail("direction_request_budget_exhausted")
        delta=DELTAS[action]
        self.pending=dict(kind=kind,action=action,player=player,stone=stone,frame=frame,executed=False,
            expected_player=(player[0]+delta[0],player[1]+delta[1]) if kind=="walk" else player,
            expected_stone=(stone[0]+delta[0],stone[1]+delta[1]) if kind=="push" else stone)
        return self._hint(action,"offer_"+kind)

    def context(self,state,*,text,grid,signal,previous,now,owner,overworld_ready=False):
        if self.error:return self._fail("sticky")
        frame=state.get("frame") if isinstance(state,dict) else None
        if (self.intent!=self.contract or not isinstance(owner,str) or not owner or self.owner is not None and owner!=self.owner
                or not _int(frame,0,2**63-1) or frame<self.last_frame or type(now) not in (int,float)
                or not math.isfinite(now) or now<0 or self.last_now is not None and now<self.last_now):return self._fail("owner_frame_or_clock_invalid")
        if self.started is None:self.started=self.step_started=now;self.owner=owner
        self.calls+=1;self.last_now=now
        if self.calls>MAX_CALLS or now-self.started>MAX_SECONDS or now-self.step_started>MAX_STEP_SECONDS:return self._fail("budget_exhausted")
        if type(previous) not in (list,tuple) or any(type(a) is not str or a not in ("wait","up","down","left","right","a","b","start") for a in previous):
            return self._fail("actual_previous_invalid")
        loc=state.get("location");battle=state.get("battle_state")
        if (not isinstance(loc,dict) or any(not _int(loc.get(k)) for k in ("map_id","x","y")) or loc["map_id"]!=108
                or not 0<=loc["x"]<20 or not 0<=loc["y"]<18
                or not isinstance(battle,dict) or type(battle.get("raw")) is not int
                or type(battle.get("observation_frame")) is not int or battle["observation_frame"]!=frame):return self._fail("location_or_battle_unverified")
        player=(loc["x"],loc["y"])
        if type(overworld_ready) is not bool:return self._fail("world_ready_type_invalid")
        for observed in (loc,state.get("progress"),text):
            if isinstance(observed,dict) and "observation_frame" in observed and (
                    type(observed["observation_frame"]) is not int or observed["observation_frame"]!=frame):
                return self._fail("observation_frame_conflict")
        packet=deepcopy((state,text,grid,signal,previous,owner,overworld_ready))
        if frame==self.last_frame:
            if packet!=self.last_packet:return self._fail("same_frame_conflict")
            if self.suspended:
                return self._hint("wait","same_frame_owned_wild_handoff",first_boulder_battle_handoff=True)
            return self._wait("same_frame_no_resend")
        self.last_frame,self.last_packet=frame,packet
        field_receipt=(not self.suspended and ((battle["raw"]==0 and battle.get("kind")=="none" and battle.get("active") is False)
                       or (battle["raw"]==1 and battle.get("kind")=="wild" and battle.get("active") is True)))
        if field_receipt and self.pending and not self.pending["executed"] and frame>self.pending["frame"] and previous and previous[-1]==self.pending["action"]:
            self.pending["executed"]=True
        if battle["raw"]==1 and battle.get("kind")=="wild" and battle.get("active") is True:
            if self.baseline is None:return self._fail("battle_before_initial_binding")
            self.suspended=True;self.closed_frame=None
            return self._hint("wait","owned_wild_battle_handoff",first_boulder_battle_handoff=True)
        if battle["raw"]!=0 or battle.get("kind")!="none" or battle.get("active") is not False:return self._fail("only_raw1_wild_handoff_supported")
        if self.suspended and overworld_ready is not True:
            self.closed_frame=None
            return self._hint("wait","owned_wild_return_ui_handoff",first_boulder_battle_handoff=True)
        if (not isinstance(signal,dict) or signal.get("profile")!=PROFILE or signal.get("source_commit")!=SOURCE_COMMIT
                or signal.get("read_valid") is not True or signal.get("read_error") is not None
                or type(signal.get("observation_frame")) is not int or signal["observation_frame"]!=frame or signal.get("location")!={"map_id":108,"x":player[0],"y":player[1]}):
            return self._fail("source_signal_unverified")
        raw=signal.get("raw");objects=signal.get("objects");stone_record=signal.get("stone")
        if (not isinstance(raw,dict) or any(not _int(raw.get(key)) for key in ADDRESSES)
                or not isinstance(objects,list) or len(objects)!=7
                or any(not isinstance(o,dict) or type(o.get("slot")) is not int or o.get("slot")!=i+1
                       or any(not _int(o.get(k)) for k in ("picture","status","walk_counter","movement_byte1","picture2","movement_byte2","text"))
                       or not _int(o.get("x"),0,19) or not _int(o.get("y"),0,17) for i,o in enumerate(objects))
                or not isinstance(stone_record,dict) or stone_record!=objects[4]
                or type(signal.get("idle")) is not bool or type(signal.get("native_push_busy")) is not bool
                or type(signal.get("event")) is not bool or signal["event"]!=bool(raw["event_raw"]&128)):
            return self._fail("source_signal_shape_unverified")
        a=signal["raw"];stone=(signal["stone"]["x"],signal["stone"]["y"])
        if ((a["map_id"],a["x"],a["y"],a["tileset"],a["height"],a["width"],a["object_count"])!=(108,*player,17,9,10,7)
                or a["facing_raw"] not in FACING.values()
                or stone_record["picture"]!=0x3F or stone_record["picture2"]!=0
                or stone_record["movement_byte2"] not in (16,255) or stone_record["text"]!=5
                or any(o["picture"]!=0x3F or o["picture2"]!=0 or o["text"]!=i+1 for i,o in enumerate(objects) if i in (5,6))
                or _native_state(a,stone_record)!=(signal["native_push_busy"],signal["idle"])):
            return self._fail("source_signal_derivation_unverified")
        if not a["flags1"]&1 or a["mode"]!=0 or a["battle_raw"]!=0:return self._fail("strength_or_native_world_mode_unverified")
        if a["movement_flags"]&4 and (player not in ((8,17),(9,17)) or a["facing_raw"]==0):return self._fail("unreviewed_warp_pad_state")
        if self.flags_baseline is not None and a["flags1"]&0xFE!=self.flags_baseline&0xFE:return self._fail("unrelated_flags1_changed")
        current=_resources(state.get("progress"))
        if current is None:return self._fail("progress_unverified")
        if self.suspended:
            if not _wild_return(self.baseline,current):return self._fail("wild_return_resource_change_unverified")
        elif self.baseline is not None and current!=self.baseline:return self._fail("resources_changed_outside_owned_wild_battle")
        if any(m["hp"]<=0 or m["status"]!=0 for m in current["party"]):return self._fail("attrition_requires_owned_review")
        # A real accepted operation can outlive the visible-grid alignment.  Only
        # wait here: a fresh closed world is still mandatory before advancing.
        if self.pending and self.pending["executed"]:
            p=self.pending
            if signal["native_push_busy"]:
                if (p["kind"]!="push" or a["boulder_index"]!=5
                        or stone not in (p["stone"],p["expected_stone"])
                        or player not in (p["player"],p["stone"])):
                    return self._fail("foreign_native_movement")
                self.closed_frame=None
                self.contact_arm_seen|=bool(a["misc"]&64)
                self.native_script_seen|=bool(a["flags5"]&1);self.dust_seen|=bool(a["misc"]&2)
                return self._wait("native_slot5_movement_and_dust_only")
            if p["kind"]=="walk" and a["walk_counter"]:
                if stone!=p["stone"] or player not in (p["player"],p["expected_player"]):
                    return self._fail("unexpected_walk_in_progress")
                self.closed_frame=None
                return self._wait("native_player_walk_in_progress")
        rows=_rows(text)
        if rows is None or rows!=(" "*20,)*18 or text.get("window_visible") is not False or not overworld_ready:
            self.closed_frame=None
            return self._wait("await_verified_world_without_sending_input")
        if not _grid(grid,player,frame):return self._fail("native_world_grid_unverified")
        if any((obj["x"],obj["y"])!=STATIC_POSITIONS[obj["slot"]-1] for obj in signal["objects"] if obj["slot"]!=5):
            return self._fail("other_source_objects_changed")
        self.contact_arm_seen|=bool(a["misc"]&64);self.native_script_seen|=bool(a["flags5"]&1);self.dust_seen|=bool(a["misc"]&2)
        if self.baseline is None:
            if player!=(8,16) or stone!=(5,15) or signal["event"] or a["gate_block"]!=0x25 or signal["idle"] is not True:
                return self._fail("initial_fixed_mechanism_unverified")
            self.baseline=current;self.flags_baseline=a["flags1"]
        if self.suspended:
            self.baseline=current;self.suspended=False;self.battle_returns+=1
        if self.push_index==len(PUSHES):
            if player!=self.final_player:return self._fail("unowned_player_move_after_final_push")
            if stone!=(17,13) or not signal["event"] or a["gate_block"]!=0x1D or grid["tiles"][12][9]!=5:
                self.closed_frame=None;return self._wait("await_native_event_and_block_open")
            if signal["idle"] is not True:
                self.closed_frame=None;return self._wait("await_native_final_idle")
            if self.closed_frame is None:self.closed_frame=frame;return self._wait("first_closed_open_switch_frame")
            return self._hint("wait","verified_fixed_first_boulder_switch",True)
        if self.pending:
            pending=self.pending
            if pending["kind"]=="push" and a["boulder_index"] not in (0,5):
                return self._fail("wrong_contact_sprite")
            if not pending["executed"]:
                if signal["idle"] is not True:return self._wait("unexecuted_direction_await_idle_without_resend")
                if player==pending["player"] and stone==pending["stone"]:
                    self.requests+=1
                    if self.requests>MAX_REQUESTS:return self._fail("direction_request_budget_exhausted")
                    return self._hint(pending["action"],"retry_unexecuted_direction_same_pending")
                return self._fail("coordinate_change_without_true_previous")
            if signal["native_push_busy"]:
                if pending["kind"]!="push" or a["boulder_index"]!=5:return self._fail("foreign_native_movement")
                return self._wait("native_slot5_movement_and_dust_only")
            if signal["idle"] is not True:return self._wait("await_native_idle_before_next_direction")
            if pending["kind"]=="walk":
                if stone!=pending["stone"]:return self._fail("boulder_changed_during_walk")
                if player==pending["expected_player"]:self._reset_step(now)
                elif player==pending["player"]:
                    return self._offer("walk",pending["action"],player,stone,frame,now)
                else:return self._fail("unexpected_player_displacement")
            else:
                if stone==pending["expected_stone"]:
                    if player not in (pending["player"],pending["stone"]):return self._fail("unexpected_player_follow")
                    self.push_index+=1;self._reset_step(now)
                    if self.push_index==len(PUSHES):
                        self.final_player=player
                        return self._wait("final_stone_moved_await_native_gate_receipt")
                elif stone==pending["stone"] and player==pending["player"]:
                    if a["boulder_index"] not in (0,5):return self._fail("wrong_contact_sprite")
                    return self._offer("push",pending["action"],player,stone,frame,now)
                else:return self._fail("unexpected_boulder_displacement")
        if stone!=PUSHES[self.push_index][2]:return self._fail("stone_not_at_retained_sequence_position")
        if signal["event"] or a["gate_block"]!=0x25:return self._fail("switch_opened_before_fixed_final_push")
        action,stance,_,destination=PUSHES[self.push_index]
        if signal["idle"] is not True:return self._wait("await_normal_native_idle")
        if player==stance:
            if grid["walkable"][destination[1]][destination[0]]!=1 or grid["tiles"][destination[1]][destination[0]]==0x15:
                return self._fail("source_push_destination_blocked")
            # Push elevation compares player with two-steps-ahead destination, not adjacent rock tile.
            pair=frozenset((grid["tiles"][player[1]][player[0]],grid["tiles"][destination[1]][destination[0]]))
            if pair in {frozenset(p) for p in ((0x20,5),(0x41,5),(0x2A,5),(5,0x21))}:
                return self._fail("source_push_elevation_pair_blocked")
            return self._offer("push",action,player,stone,frame,now)
        blocked=[(o["x"],o["y"]) for o in signal["objects"]]+[(1,1)]
        hint=world_direction(grid,{"map_id":108,"x":player[0],"y":player[1]},
                             {"x":stance[0],"y":stance[1]},blocked,BAD_EDGES)
        if not hint:return self._fail("no_verified_normal_walk_to_fixed_stance")
        return self._offer("walk",hint["direction"],player,stone,frame,now)
