"""四個明確Victory Road站位的原生Strength來源候選；不推石、不按鍵。

第一段used/STRENGTH.@自動播放cry；僅第二段can/move boulders.<PROMPT>
完整▼才提出A，且只有真previous可證該A已執行。尚未實機校準。
"""
from collections.abc import Mapping
from copy import deepcopy
import math

from laya_pokemon.hm_teaching import _rows
from laya_pokemon.mart_purchase import _party, _inventory
from laya_pokemon.team_strategy import reference, move_key

SOURCE_COMMIT = "a53671100ec22e5394ff26ec028d0812a238dae2"
PROFILE = "red-en-victory-strength-source-v2-floors-unvalidated"
INTENT = dict(kind="victory_strength", map_id=108, player_x=8, player_y=16,
              species=132, move=70)
START = dict(map_id=108, x=8, y=16)
MAX_SECONDS, MAX_CALLS, MAX_WAITS = 60, 240, 30
FLAG_ADDRESS, FLAG_MASK = 0xD728, 1
# wStatusFlags1 = SDK StatusFlags3 D72D - 5; source wram.asm2105..2111.
ADDRESSES = dict(flags1=FLAG_ADDRESS, map_id=0xD35E, y=0xD361, x=0xD362,
    badges_raw=0xD356, party_count=0xD163, battle_raw=0xD057, mode=0xD700,
    joy_ignore=0xCD6B, walk_counter=0xCFC5, simulated=0xCD38,
    movement_flags=0xD736, flags3=0xD72D, flags5=0xD730,
    flags6=0xD732, flags7=0xD733, tileset=0xD367, height=0xD368, width=0xD369,
    player_y_pixels=0xC104, player_x_pixels=0xC106)
STANCES = {'1f_entry': {'start': {'map_id': 108, 'x': 8, 'y': 16},
              'tile': 32,
              'width': 20,
              'height': 18,
              'block_address': 51103,
              'block_id': 36,
              'block_index': 84,
              'bst_offset': 580,
              'intent': {'kind': 'victory_strength',
                         'map_id': 108,
                         'player_x': 8,
                         'player_y': 16,
                         'species': 132,
                         'move': 70}},
 '2f_entry': {'start': {'map_id': 194, 'x': 0, 'y': 9},
              'tile': 32,
              'width': 30,
              'height': 18,
              'block_address': 51070,
              'block_id': 35,
              'block_index': 60,
              'bst_offset': 572,
              'intent': {'kind': 'victory_strength',
                         'map_id': 194,
                         'player_x': 0,
                         'player_y': 9,
                         'species': 132,
                         'move': 70}},
 '3f_entry': {'start': {'map_id': 198, 'x': 23, 'y': 8},
              'tile': 32,
              'width': 30,
              'height': 18,
              'block_address': 51081,
              'block_id': 4,
              'block_index': 71,
              'bst_offset': 70,
              'intent': {'kind': 'victory_strength',
                         'map_id': 198,
                         'player_x': 23,
                         'player_y': 8,
                         'species': 132,
                         'move': 70}},
 '2f_after_fall': {'start': {'map_id': 194, 'x': 22, 'y': 16},
                   'tile': 42,
                   'width': 30,
                   'height': 18,
                   'block_address': 51165,
                   'block_id': 96,
                   'block_index': 131,
                   'bst_offset': 1540,
                   'intent': {'kind': 'victory_strength',
                              'map_id': 194,
                              'player_x': 22,
                              'player_y': 16,
                              'species': 132,
                              'move': 70}}}
INTENTS = {key:deepcopy(c["intent"]) for key,c in STANCES.items()}
FIELD_MOVES = frozenset({15, 19, 57, 70, 148, 91, 100, 135})


def _int(value, low=0, high=255):
    return type(value) is int and low <= value <= high


def _get(obj, key):
    return obj.get(key) if isinstance(obj, Mapping) else getattr(obj, key, None)


def _anchors(constants):
    anchors = dict(STATUS_FLAGS3_ADDRESS=0xD72D, EVENT_FLAGS_ADDRESS=0xD747,
                   OBTAINED_BADGES_ADDRESS=0xD356, PARTY_COUNT_ADDRESS=0xD163)
    maps, badges = _get(constants,"MAPS"), _get(constants,"BADGES")
    return (all(type(_get(constants,k)) is int and _get(constants,k)==v for k,v in anchors.items())
            and isinstance(maps,Mapping) and type(maps.get("victory_road_1f")) is int
            and all(type(maps.get(k)) is int and maps[k]==v for k,v in (("victory_road_1f",108),("victory_road_2f",194),("victory_road_3f",198))) and isinstance(badges,Mapping)
            and type(badges.get("rainbow")) is int and badges["rainbow"]==3)


def _unknown(frame, reason):
    return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,observation_frame=frame,
        read_valid=False,read_error=reason,location=None,raw_flags=None,
        strength_active=None,idle=None,source_case=None,source_block=None,live_calibrated=False,
        **{key:None for key in ADDRESSES if key not in {"flags1","map_id","x","y"}})


def _intent_key(intent):
    if type(intent) is not dict:return None
    for key,c in STANCES.items():
        expected=c["intent"]
        if (intent==expected and set(intent)==set(expected)
                and all(type(intent[k]) is type(v) for k,v in expected.items())):return key
    return None


def _native_idle(a):
    return (a["joy_ignore"]==a["walk_counter"]==a["simulated"]==0
        and a["battle_raw"]==a["mode"]==0
        and a["player_y_pixels"]==0x3C and a["player_x_pixels"]==0x40
        and not a["movement_flags"]&0xC7 and not a["flags5"]&0xA7
        and not a["flags3"]&0x18 and not a["flags6"]&0x5C and not a["flags7"]&4)


def _position_key(a):
    return next((key for key,c in STANCES.items()
                 if (a["map_id"],a["x"],a["y"])==(c["start"]["map_id"],c["start"]["x"],c["start"]["y"])),None)


def read_strength_observation(pyboy,observation_frame,constants):
    """Double-read bytes at one of four fixed positions; never accept caller RAM."""
    if not _int(observation_frame,0,2**63-1):return _unknown(None,"frame_invalid")
    try:
        if not _anchors(constants):return _unknown(observation_frame,"sdk_source_anchors_unverified")
        before=pyboy.frame_count
        if type(before) is not int or before!=observation_frame:return _unknown(observation_frame,"frame_not_current")
        def sample():
            a={k:pyboy.memory[address] for k,address in ADDRESSES.items()}
            key=_position_key(a)
            block=pyboy.memory[STANCES[key]["block_address"]] if key is not None else None
            return a,key,block
        first,second=sample(),sample();after=pyboy.frame_count
    except Exception:return _unknown(observation_frame,"getter_failed")
    def valid(s):
        a,key,block=s
        if key not in STANCES or any(not _int(v) for v in a.values()) or not _int(block):return False
        c=STANCES[key]
        return (a["tileset"],a["height"],a["width"],block)==(17,9,c["width"]//2,c["block_id"])
    if not valid(first) or not valid(second):return _unknown(observation_frame,"source_position_header_or_byte_unverified")
    if type(after) is not int or after!=before or first!=second:return _unknown(observation_frame,"torn_frame_or_snapshot")
    a,key,block=first
    if a["movement_flags"]&0x38:return _unknown(observation_frame,"unused_movement_flags_set")
    return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,observation_frame=before,
        read_valid=True,read_error=None,live_calibrated=False,source_case=key,source_block=block,
        location={k:a[k] for k in ("map_id","x","y")},raw_flags=a["flags1"],
        strength_active=bool(a["flags1"]&FLAG_MASK),idle=_native_idle(a),
        **{k:v for k,v in a.items() if k not in {"flags1","map_id","x","y"}})


def _source_signal_valid(signal,intent):
    key=_intent_key(intent)
    if key is None or not isinstance(signal,dict):return False
    c=STANCES[key]
    loc=signal.get("location")
    return (isinstance(loc,dict) and all(_int(loc.get(k)) for k in ("map_id","x","y"))
        and {k:loc[k] for k in ("map_id","x","y")}==c["start"]
        and signal.get("source_case")==key and _int(signal.get("source_block")) and signal["source_block"]==c["block_id"]
        and all(_int(signal.get(k)) for k in ADDRESSES if k not in {"flags1","map_id","x","y"})
        and (signal["tileset"],signal["height"],signal["width"])==(17,9,c["width"]//2)
        and not signal["movement_flags"]&0x38 and type(signal.get("idle")) is bool
        and signal["idle"]==_native_idle(signal))


def _blank():
    return (" "*20,)*18


def _put(rows,x,y,label):
    rows[y][x:x+len(label)]=list(label.upper())


def _serial(rows):
    return tuple("".join(row) for row in rows)


def _world(grid,frame,intent=INTENT):
    key=_intent_key(intent)
    if key is None:return False
    c=STANCES[key];start=c["start"];width=c["width"]
    if (not isinstance(grid,dict) or type(grid.get("tileset_id")) is not int or grid["tileset_id"]!=17
            or type(grid.get("observation_frame")) is not int or grid["observation_frame"]!=frame
            or type(grid.get("verified_location")) is not list or any(type(v) is not int for v in grid["verified_location"])
            or grid["verified_location"]!=[start["map_id"],start["x"],start["y"]]
            or not _int(grid.get("screen_cells_verified"),12,width*18)):return False
    visible=grid.get("visible_verified_cells")
    if (not isinstance(visible,list) or len(visible)!=grid["screen_cells_verified"]
            or any(not isinstance(p,list) or len(p)!=2 or not _int(p[0],0,width-1) or not _int(p[1],0,17) for p in visible)
            or len(set(map(tuple,visible)))!=len(visible)):return False
    for field,maximum in (("tiles",255),("walkable",1)):
        cells=grid.get(field)
        if (not isinstance(cells,(list,tuple)) or len(cells)!=18
                or any(not isinstance(row,(list,tuple)) or len(row)!=width
                    or any(not _int(v,0,maximum) for v in row) for row in cells)):return False
    return grid["tiles"][start["y"]][start["x"]]==c["tile"] and grid["walkable"][start["y"]][start["x"]]==1


class VictoryStrengthController:
    def __init__(self,intent=INTENT,*,reviewed_fainted_bench=()):
        if type(reviewed_fainted_bench) is not tuple or any(type(v) is not int for v in reviewed_fainted_bench) or reviewed_fainted_bench not in ((),(7,)):
            raise ValueError('Only the explicitly reviewed Nidoking bench is supported')
        self.reviewed_fainted_bench=reviewed_fainted_bench
        if _intent_key(intent) is None:
            raise ValueError("Only four fixed Victory Road Snorlax Strength stances")
        self.intent=deepcopy(intent);self.contract=deepcopy(intent)
        self.stage,self.error="initial",None
        self.started=self.last_now=None;self.last_frame=-1;self.last_packet=None
        self.calls=self.waits=0;self.baseline=None;self.target_index=None
        self.pending=self.expected=None;self.flags_baseline=None
        self.selected_user=self.strength_selected=self.prompt_ack=False
        self.seen_used_full=self.seen_can_prompt=False;self.closed_frame=None

    @property
    def start(self):
        key=_intent_key(self.intent)
        return deepcopy(STANCES[key]["start"]) if key is not None else None

    def _hint(self,action,tactic,complete=False):
        goals=dict(wait="Wait.",start="Press START.",a="Press A.",up="Move UP.",down="Move DOWN.")
        return dict(phase="victory_strength_complete" if complete else "victory_strength_menu",
            objective=goals[action],available_actions=["wait"] if action=="wait" else [action,"wait"],
            controller_menu_verified=action!="wait",victory_strength_complete=complete,
            victory_strength_stage=self.stage,victory_strength_tactic=tactic,
            source_commit=SOURCE_COMMIT,victory_strength_case=_intent_key(self.intent),seen_used_full=self.seen_used_full,
            seen_can_prompt=self.seen_can_prompt,prompt_ack=self.prompt_ack)

    def _fail(self,reason):
        self.error=self.error or "victory_strength_"+reason
        return {**self._hint("wait","review"),"phase":"campaign_review","review_reason":self.error}

    def _wait(self,reason):
        self.waits+=1
        return self._fail("wait_budget_exhausted") if self.waits>MAX_WAITS else self._hint("wait",reason)

    def _offer(self,action,stage,view,expected=None):
        self.pending=dict(action=action,stage=stage,frame=self.last_frame,
                          view=deepcopy(view),expected=expected,executed=False)
        return self._hint(action,"offer_"+stage)

    def _progress(self,p):
        party=_party(p);inv=_inventory(p.get("inventory")) if isinstance(p,dict) else None
        if (party is None or len(party)!=6 or len({m["species"] for m in party})!=6
                or any((m['hp']<=0 and m['species'] not in getattr(self,'reviewed_fainted_bench',())) or m['status']!=0 for m in party) or inv is None
                or not _int(p.get("money"),0,999999) or p.get("player_name_raw")!="KEVIN"
                or not _int(p.get("badges_raw")) or not p["badges_raw"] & 8):
            return None
        ref=reference()
        if ref.get("source_commit")!=SOURCE_COMMIT:return None
        for mon in party:
            for move,pp in zip(mon["moves"],mon["pp"]):
                key=move_key(move) if move else None
                if (not move and pp or move and (key not in ref["moves"]
                        or (pp&63)>ref["moves"][key]["pp"]*(5+(pp>>6))//5)):
                    return None
        targets=[i for i,m in enumerate(party) if 70 in m["moves"]]
        if len(targets)!=1 or party[targets[0]]["species"]!=132:return None
        fields=[]
        for move in party[targets[0]]["moves"]:
            if not move:break
            if move in FIELD_MOVES:fields.append(move)
        if fields!=[70]:return None
        return deepcopy(dict(party=party,inventory=inv,money=p["money"],badges_raw=p["badges_raw"],
                             player_name_raw=p["player_name_raw"]))

    def _start(self,y,marker="▶"):
        r=[list(row) for row in _blank()]
        for yy,label in ((2,"POKÉDEX"),(4,"POKÉMON"),(6,"ITEM"),(8,"KEVIN"),(10,"SAVE"),(12,"OPTION"),(14,"EXIT")):
            _put(r,12,yy,label)
        _put(r,11,y,marker);return _serial(r)

    def _party(self,index,marker="▶"):
        r=[list(row) for row in _blank()]
        for i,m in enumerate(self.baseline["party"]):
            _put(r,3,2*i,m["species_name"]);_put(r,13,2*i,f'{m["level"]:3}')
            if m['hp']==0:_put(r,17,2*i,'FNT')
            _put(r,13,2*i+1,f'{m["hp"]:3}/{m["max_hp"]:3}')
        _put(r,0,2*index+1,marker);_put(r,1,14,"Choose a POKéMON.")
        return _serial(r)

    def _field(self,y,marker="▶"):
        r=[list(row) for row in self._party(self.target_index,"▷")]
        for yy in range(8,18):r[yy][9:20]=[" "]*11
        for yy,label in ((10,"STRENGTH"),(12,"STATS"),(14,"SWITCH"),(16,"CANCEL")):
            _put(r,11,yy,label)
        _put(r,10,y,marker);return _serial(r)

    def _message(self,kind,arrow=False):
        r=[list(row) for row in self._party(self.target_index,"▷")[:12]]+[[" "]*20 for _ in range(6)]
        first,second=(("SNORLAX USED","STRENGTH.") if kind=="used" else ("SNORLAX CAN","MOVE BOULDERS."))
        _put(r,1,14,first);_put(r,1,16,second)
        if arrow:_put(r,18,16,"▼")
        return _serial(r)

    def _known_printing(self,rows,kind):
        full=self._message(kind)
        fixed=list(rows);fixed[14]=fixed[16]=" "*20
        expected=list(full);expected[14]=expected[16]=" "*20
        if tuple(fixed)!=tuple(expected):return False
        if any(c!=" " for yy in (14,16) for xx,c in enumerate(rows[yy]) if xx not in range(1,19)):
            return False
        a,b=rows[14][1:19].rstrip(),rows[16][1:19].rstrip()
        aa,bb=full[14][1:19].rstrip(),full[16][1:19].rstrip()
        return aa.startswith(a) and (not b or a==aa and bb.startswith(b))

    def _selection(self,kind,index):
        if self.expected is not None and self.expected!=(kind,index):return False
        self.expected=None;return True

    def context(self,text,progress,*,location,battle_state,grid,signal,frame,previous,now,overworld_ready=False):
        if self.error:return self._fail("sticky")
        self.calls+=1
        if (self.intent!=self.contract or _intent_key(self.intent) is None or not _int(frame,0,2**63-1) or frame<self.last_frame
                or type(now) not in (int,float) or not math.isfinite(now) or now<0
                or self.last_now is not None and now<self.last_now):return self._fail("owner_frame_or_clock_invalid")
        if self.started is None:self.started=now
        self.last_now=now
        if self.calls>MAX_CALLS or now-self.started>MAX_SECONDS:return self._fail("budget_exhausted")
        if (not isinstance(location,dict) or any(not _int(location.get(k)) for k in ("map_id","x","y"))
                or {k:location[k] for k in ("map_id","x","y")}!=self.start
                or type(previous) not in (list,tuple) or any(type(a) is not str or a not in
                    ("a","b","start","up","down","left","right","wait") for a in previous)
                or type(overworld_ready) is not bool):return self._fail("location_or_actual_previous_invalid")
        for packet in (text,progress,location):
            if isinstance(packet,dict) and "observation_frame" in packet and (
                    type(packet["observation_frame"]) is not int or packet["observation_frame"]!=frame):
                return self._fail("observation_frame_conflict")
        if (not isinstance(battle_state,dict) or battle_state.get("kind")!="none" or battle_state.get("active") is not False
                or type(battle_state.get("raw")) is not int or battle_state["raw"]!=0
                or type(battle_state.get("observation_frame")) is not int or battle_state["observation_frame"]!=frame):
            return self._fail("battle_not_verified_none")
        if (not isinstance(signal,dict) or signal.get("profile")!=PROFILE or signal.get("source_commit")!=SOURCE_COMMIT
                or signal.get("read_valid") is not True or signal.get("read_error") is not None
                or type(signal.get("observation_frame")) is not int or signal["observation_frame"]!=frame
                or signal.get("location")!=self.start or not _int(signal.get("raw_flags"))
                or type(signal.get("strength_active")) is not bool or signal["strength_active"]!=bool(signal["raw_flags"]&1)
                or type(signal.get("idle")) is not bool or not _source_signal_valid(signal,self.intent) or signal.get("battle_raw")!=0
                or type(signal.get("battle_raw")) is not int or signal.get("mode")!=0 or type(signal.get("mode")) is not int
                or signal.get("party_count")!=6 or type(signal.get("party_count")) is not int):
            return self._fail("source_signal_unverified")
        current=self._progress(progress)
        if (current is None or signal.get("badges_raw")!=current["badges_raw"]
                or type(signal.get("badges_raw")) is not int
                or self.baseline is not None and current!=self.baseline):return self._fail("party_bag_money_or_pp_changed")
        if self.flags_baseline is not None and signal["raw_flags"]&0xFE!=self.flags_baseline&0xFE:
            return self._fail("unrelated_flags1_changed")
        rows=_rows(text)
        if rows is None:return self._fail("native_decoder_unverified")
        packet=deepcopy((text,progress,location,battle_state,grid,signal,previous,overworld_ready))
        view=(rows,signal["raw_flags"])
        if frame==self.last_frame:
            return self._fail("same_frame_conflict") if packet!=self.last_packet else self._wait("same_frame_no_resend")
        self.last_frame,self.last_packet=frame,packet
        if self.baseline is None:
            if (rows!=_blank() or text["window_visible"] is not False or not overworld_ready
                    or signal["strength_active"] is not False or signal["idle"] is not True or not _world(grid,frame,self.intent)):
                return self._fail("initial_closed_victory_road_unverified")
            self.baseline=current;self.flags_baseline=signal["raw_flags"]
            self.target_index=next(i for i,m in enumerate(current["party"]) if m["species"]==132)
            return self._offer("start","start",view)
        if self.pending:
            p=self.pending
            if not p["executed"]:
                if frame>p["frame"] and previous and previous[-1]==p["action"]:
                    p["executed"]=True;self.stage=p["stage"];self.expected=p["expected"]
                    if self.stage=="field":self.selected_user=True
                    if self.stage=="messages":self.strength_selected=True
                    if self.stage=="closing":self.prompt_ack=True
                elif view==p["view"]:
                    return self._hint(p["action"],"retry_unexecuted_candidate")
                else:return self._fail("changed_page_without_actual_previous")
            if view==p["view"]:return self._wait("await_actual_action_effect")
            self.pending=None
        if not self.strength_selected and signal["strength_active"]:
            return self._fail("active_flag_before_actual_strength_selection")
        if self.stage in ("closing","complete"):
            if not self.strength_selected or not self.prompt_ack or not signal["strength_active"]:
                return self._fail("native_activation_handoff_unverified")
            if rows in (self._message("can",True),self._message("can",False)) and text["window_visible"] is True:
                self.closed_frame=None;return self._wait("acknowledged_prompt_no_resend")
            if rows!=_blank() or text["window_visible"] is not False:
                self.closed_frame=None;return self._fail("unexpected_post_prompt_text")
            if signal["idle"] is True and overworld_ready and _world(grid,frame,self.intent):
                if self.closed_frame is None:
                    self.closed_frame=frame;return self._wait("first_closed_active_frame")
                if frame>self.closed_frame:
                    self.stage="complete";return self._hint("wait","verified_native_strength_active_here",True)
            self.closed_frame=None
            return self._fail("completed_world_changed") if self.stage=="complete" else self._wait("native_closing_only")
        if text["window_visible"] is not True:return self._fail("menu_window_unverified")
        if self.stage=="start":
            for y in (2,4,6,8,10,12,14):
                if rows==self._start(y):
                    if not self._selection("start",y):return self._fail("start_cursor_jump")
                    if y==4:return self._offer("a","party",view)
                    return self._offer("down" if y<4 else "up","start",view,("start",y+2 if y<4 else y-2))
                if rows==self._start(y,"▷"):return self._wait("inactive_start_cursor")
        elif self.stage=="party":
            if rows==self._start(4,"▷"):return self._wait("native_start_confirmation")
            for i in range(6):
                if rows==self._party(i):
                    if not self._selection("party",i):return self._fail("party_cursor_jump")
                    if i==self.target_index:return self._offer("a","field",view)
                    return self._offer("down" if i<self.target_index else "up","party",view,
                                       ("party",i+1 if i<self.target_index else i-1))
                if rows==self._party(i,"▷"):return self._wait("inactive_party_cursor")
        elif self.stage=="field":
            if not self.selected_user:return self._fail("user_not_actually_selected")
            if rows==self._party(self.target_index,"▷"):return self._wait("native_party_confirmation")
            for y in (10,12,14,16):
                if rows==self._field(y):
                    if not self._selection("field",y):return self._fail("field_cursor_jump")
                    return self._offer("a","messages",view) if y==10 else self._offer("up","field",view,("field",y-2))
                if rows==self._field(y,"▷"):return self._wait("inactive_field_cursor")
        elif self.stage=="messages":
            if not self.strength_selected:return self._fail("strength_not_actually_selected")
            if rows in (self._field(10),self._field(10,"▷"),self._party(self.target_index,"▷")):
                return self._wait("native_strength_confirmation")
            if not signal["strength_active"]:return self._fail("strength_text_without_active_flag")
            if rows==self._message("used"):
                self.seen_used_full=True;return self._wait("used_text_automatic_cry_no_a")
            if rows==self._message("can",True):
                self.seen_can_prompt=True;return self._offer("a","closing",view)
            if self._known_printing(rows,"used") or self._known_printing(rows,"can"):
                return self._wait("known_text_printing_or_prompt_blink")
        return self._fail("unknown_or_polluted_native_page")
