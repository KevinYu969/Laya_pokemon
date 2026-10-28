"""Four fixed later Victory Road stone cases. Read-only getter + pure goals.

No inputs/ticks/memory writes, HM activation, runtime stone search or arbitrary RAM.
The static whitelist derives from fixed primary source; not live calibrated.
"""
from collections.abc import Mapping
from copy import deepcopy
import math
from laya_pokemon.hm_teaching import _rows
from laya_pokemon.mart_purchase import _party,_inventory
from laya_pokemon.team_strategy import reference,move_key,species_key,PROTECTED_HMS
from laya_pokemon.world_map import world_direction


def _int(v,lo=0,hi=255):return type(v) is int and lo<=v<=hi
def _get(obj,key):return obj.get(key) if isinstance(obj,Mapping) else getattr(obj,key,None)

SOURCE_COMMIT="a53671100ec22e5394ff26ec028d0812a238dae2"
PROFILE="red-en-victory-later-boulders-source-v1-unvalidated"
MAX_SECONDS,MAX_CALLS,MAX_STEP_SECONDS,MAX_STEP_WAITS,MAX_REQUESTS=900,2400,60,30,8
DELTAS=dict(up=(0,-1),down=(0,1),left=(-1,0),right=(1,0))
FACING=dict(down=0,up=4,left=8,right=12)
CASES={'2f_switch1': {'map_id': 194,
                'slot': 11,
                'object_count': 13,
                'start_player': [0, 9],
                'start_player_tile': 32,
                'start_stone': [4, 14],
                'goal_stone': [1, 16],
                'goal_stone_tile': 45,
                'event': {'id': 1336, 'address': 55278, 'bit': 0},
                'gate': {'block_xy': [3, 4],
                         'address': 51073,
                         'before': 55,
                         'after': 21,
                         'cells': [[7, 8, 36, 5], [7, 9, 36, 5]]},
                'source_all_c2_objects': [{'slot': 1, 'x': 12, 'y': 9},
                                          {'slot': 2, 'x': 21, 'y': 13},
                                          {'slot': 3, 'x': 19, 'y': 8},
                                          {'slot': 4, 'x': 4, 'y': 2},
                                          {'slot': 5, 'x': 26, 'y': 3},
                                          {'slot': 6, 'x': 11, 'y': 5},
                                          {'slot': 7, 'x': 27, 'y': 5},
                                          {'slot': 8, 'x': 18, 'y': 9},
                                          {'slot': 9, 'x': 9, 'y': 11},
                                          {'slot': 10, 'x': 11, 'y': 0},
                                          {'slot': 11, 'x': 4, 'y': 14},
                                          {'slot': 12, 'x': 5, 'y': 5},
                                          {'slot': 13, 'x': 23, 'y': 16}],
                'normal_warp_coords': [[0, 8], [1, 1], [23, 7], [25, 14], [27, 7], [29, 7], [29, 8]],
                'pushes': (('left', (5, 14), (4, 14), (3, 14)),
                           ('down', (3, 13), (3, 14), (3, 15)),
                           ('down', (3, 14), (3, 15), (3, 16)),
                           ('left', (4, 16), (3, 16), (2, 16)),
                           ('left', (3, 16), (2, 16), (1, 16))),
                'required_true': (),
                'gate_binding': {'gate1': 55, 'gate2': 37},
                'source_stones': {11: (4, 14), 12: (5, 5), 13: (23, 16)}},
 '3f_switch1': {'map_id': 198,
                'slot': 7,
                'object_count': 10,
                'start_player': [23, 8],
                'start_player_tile': 32,
                'start_stone': [22, 3],
                'goal_stone': [3, 5],
                'goal_stone_tile': 45,
                'event': {'id': 1632, 'address': 55315, 'bit': 0},
                'gate': {'block_xy': [3, 5],
                         'address': 51094,
                         'before': 37,
                         'after': 29,
                         'cells': [[7, 10, 36, 5]]},
                'source_all_c2_objects': [{'slot': 1, 'x': 28, 'y': 5},
                                          {'slot': 2, 'x': 7, 'y': 13},
                                          {'slot': 3, 'x': 6, 'y': 14},
                                          {'slot': 4, 'x': 13, 'y': 3},
                                          {'slot': 5, 'x': 26, 'y': 5},
                                          {'slot': 6, 'x': 7, 'y': 7},
                                          {'slot': 7, 'x': 22, 'y': 3},
                                          {'slot': 8, 'x': 13, 'y': 12},
                                          {'slot': 9, 'x': 24, 'y': 10},
                                          {'slot': 10, 'x': 22, 'y': 15}],
                'normal_warp_coords': [[2, 0], [23, 7], [26, 8], [27, 15]],
                'pushes': (('up', (22, 4), (22, 3), (22, 2)),
                           ('up', (22, 3), (22, 2), (22, 1)),
                           ('left', (23, 1), (22, 1), (21, 1)),
                           ('left', (22, 1), (21, 1), (20, 1)),
                           ('left', (21, 1), (20, 1), (19, 1)),
                           ('left', (20, 1), (19, 1), (18, 1)),
                           ('left', (19, 1), (18, 1), (17, 1)),
                           ('left', (18, 1), (17, 1), (16, 1)),
                           ('left', (17, 1), (16, 1), (15, 1)),
                           ('left', (16, 1), (15, 1), (14, 1)),
                           ('left', (15, 1), (14, 1), (13, 1)),
                           ('left', (14, 1), (13, 1), (12, 1)),
                           ('left', (13, 1), (12, 1), (11, 1)),
                           ('left', (12, 1), (11, 1), (10, 1)),
                           ('left', (11, 1), (10, 1), (9, 1)),
                           ('left', (10, 1), (9, 1), (8, 1)),
                           ('left', (9, 1), (8, 1), (7, 1)),
                           ('left', (8, 1), (7, 1), (6, 1)),
                           ('down', (6, 0), (6, 1), (6, 2)),
                           ('left', (7, 2), (6, 2), (5, 2)),
                           ('left', (6, 2), (5, 2), (4, 2)),
                           ('left', (5, 2), (4, 2), (3, 2)),
                           ('left', (4, 2), (3, 2), (2, 2)),
                           ('down', (2, 1), (2, 2), (2, 3)),
                           ('down', (2, 2), (2, 3), (2, 4)),
                           ('down', (2, 3), (2, 4), (2, 5)),
                           ('right', (1, 5), (2, 5), (3, 5))),
                'required_true': ('2f_switch1',),
                'gate_binding': {'gate1': 37},
                'source_stones': {7: (22, 3), 8: (13, 12), 9: (24, 10), 10: (22, 15)}},
 '3f_hole': {'map_id': 198,
             'slot': 10,
             'object_count': 10,
             'start_player': [21, 15],
             'start_player_tile': 42,
             'start_stone': [22, 15],
             'goal_stone': [23, 15],
             'goal_stone_tile': 34,
             'event': {'id': 1638, 'address': 55315, 'bit': 6},
             'gate': None,
             'source_all_c2_objects': [{'slot': 1, 'x': 28, 'y': 5},
                                       {'slot': 2, 'x': 7, 'y': 13},
                                       {'slot': 3, 'x': 6, 'y': 14},
                                       {'slot': 4, 'x': 13, 'y': 3},
                                       {'slot': 5, 'x': 26, 'y': 5},
                                       {'slot': 6, 'x': 7, 'y': 7},
                                       {'slot': 7, 'x': 3, 'y': 5},
                                       {'slot': 8, 'x': 13, 'y': 12},
                                       {'slot': 9, 'x': 24, 'y': 10},
                                       {'slot': 10, 'x': 22, 'y': 15}],
             'normal_warp_coords': [[2, 0], [23, 7], [26, 8], [27, 15]],
             'pushes': (('right', (21, 15), (22, 15), (23, 15)),),
             'required_true': ('2f_switch1', '3f_switch1'),
             'gate_binding': {'gate1': 29},
             'source_stones': {7: (3, 5), 8: (13, 12), 9: (24, 10), 10: (22, 15)}},
 '2f_switch2': {'map_id': 194,
                'slot': 13,
                'object_count': 13,
                'start_player': [22, 16],
                'start_player_tile': 42,
                'start_stone': [23, 16],
                'goal_stone': [9, 16],
                'goal_stone_tile': 45,
                'event': {'id': 1343, 'address': 55278, 'bit': 7},
                'gate': {'block_xy': [11, 7],
                         'address': 51144,
                         'before': 37,
                         'after': 29,
                         'cells': [[23, 14, 36, 5]]},
                'source_all_c2_objects': [{'slot': 1, 'x': 12, 'y': 9},
                                          {'slot': 2, 'x': 21, 'y': 13},
                                          {'slot': 3, 'x': 19, 'y': 8},
                                          {'slot': 4, 'x': 4, 'y': 2},
                                          {'slot': 5, 'x': 26, 'y': 3},
                                          {'slot': 6, 'x': 11, 'y': 5},
                                          {'slot': 7, 'x': 27, 'y': 5},
                                          {'slot': 8, 'x': 18, 'y': 9},
                                          {'slot': 9, 'x': 9, 'y': 11},
                                          {'slot': 10, 'x': 11, 'y': 0},
                                          {'slot': 11, 'x': 4, 'y': 14},
                                          {'slot': 12, 'x': 5, 'y': 5},
                                          {'slot': 13, 'x': 23, 'y': 16}],
                'normal_warp_coords': [[0, 8], [1, 1], [23, 7], [25, 14], [27, 7], [29, 7], [29, 8]],
                'pushes': (('left', (24, 16), (23, 16), (22, 16)),
                           ('left', (23, 16), (22, 16), (21, 16)),
                           ('left', (22, 16), (21, 16), (20, 16)),
                           ('left', (21, 16), (20, 16), (19, 16)),
                           ('left', (20, 16), (19, 16), (18, 16)),
                           ('left', (19, 16), (18, 16), (17, 16)),
                           ('left', (18, 16), (17, 16), (16, 16)),
                           ('left', (17, 16), (16, 16), (15, 16)),
                           ('left', (16, 16), (15, 16), (14, 16)),
                           ('left', (15, 16), (14, 16), (13, 16)),
                           ('left', (14, 16), (13, 16), (12, 16)),
                           ('left', (13, 16), (12, 16), (11, 16)),
                           ('left', (12, 16), (11, 16), (10, 16)),
                           ('left', (11, 16), (10, 16), (9, 16))),
                'required_true': ('2f_switch1', '3f_switch1', '3f_hole'),
                'gate_binding': {'gate1': 21, 'gate2': 37},
                'source_stones': {11: (4, 14), 12: (5, 5), 13: (23, 16)}}}
TOGGLE_TABLES={194: ((6, 91), (7, 92), (8, 93), (9, 94), (10, 95), (13, 96)), 198: ((5, 120), (6, 121), (10, 122))}

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


def _addresses(case_key):
    c=CASES[case_key]
    result=dict(map_id=0xD35E,y=0xD361,x=0xD362,facing_raw=0xC109,
        tileset=0xD367,height=0xD368,width=0xD369,object_count=0xD4E1,
        flags1=0xD728,flags3=0xD72D,flags5=0xD730,flags6=0xD732,flags7=0xD733,
        mode=0xD700,battle_raw=0xD057,misc=0xCD60,boulder_index=0xD718,
        collision_result=0xD71C,dungeon_destination=0xD71D,dungeon_which=0xD71E,
        joy_ignore=0xCD6B,walk_counter=0xCFC5,simulated=0xCD38,movement_flags=0xD736,
        event2f_raw=0xD7EE,event3f_raw=0xD813,gate1=0xC781 if c["map_id"]==194 else 0xC796)
    if c["map_id"]==194:result["gate2"]=0xC7C8
    return result


def _event(c,raw):
    return bool(raw["event2f_raw" if c["map_id"]==194 else "event3f_raw"]&(1<<c["event"]["bit"]))


def _hidden(flags,index):return bool(flags[index//8]&(1<<(index%8)))


def _native_state(a,stone):
    busy=bool(a["flags5"]&1 or a["misc"]&2 or stone["walk_counter"] or stone["movement_byte2"]==255)
    idle=(a["joy_ignore"]==a["walk_counter"]==a["simulated"]==0 and not busy
        and not a["movement_flags"]&0xFB and not a["flags5"]&0xA7
        and not a["flags3"]&0x18 and not a["flags6"]&0x5C and not a["flags7"]&4
        and a["mode"]==a["battle_raw"]==0 and stone["movement_byte1"]==255
        and stone["status"]&0x7F in (1,2))
    return busy,idle


def _anchors(constants):
    anchors=dict(STATUS_FLAGS3_ADDRESS=0xD72D,EVENT_FLAGS_ADDRESS=0xD747,OBTAINED_BADGES_ADDRESS=0xD356)
    maps,events=_get(constants,"MAPS"),_get(constants,"EVENT_FLAGS")
    if (any(type(_get(constants,k)) is not int or _get(constants,k)!=v for k,v in anchors.items())
            or not isinstance(maps,Mapping) or not isinstance(events,Mapping)):return False
    return (all(type(maps.get(k)) is int and maps[k]==v for k,v in (("victory_road_2f",194),("victory_road_3f",198)))
        and all(type(events.get(k)) is int and events[k]==v for k,v in (
            ("victory_road_2_boulder_on_switch1",0x538),("victory_road_2_boulder_on_switch2",0x53F),
            ("victory_road_3_boulder_on_switch1",0x660),("victory_road_3_boulder_on_switch2",0x666))))


def _unknown(frame,case_key,reason):
    return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,case_key=case_key,observation_frame=frame,
        read_valid=False,read_error=reason,location=None,stone=None,objects=None,raw=None,
        toggle_flags=None,toggle_table=None,idle=None,native_push_busy=None,event=None,live_calibrated=False)


def read_later_boulder_observation(pyboy,observation_frame,constants,*,case_key):
    """Only four built-in cases. Validate both snapshots before byte equality."""
    if type(case_key) is not str or case_key not in CASES:return _unknown(None,None,"case_unverified")
    if not _int(observation_frame,0,2**63-1):return _unknown(None,case_key,"frame_invalid")
    c=CASES[case_key];addresses=_addresses(case_key);slot=c["slot"]
    try:
        if not _anchors(constants):return _unknown(observation_frame,case_key,"sdk_source_anchors_unverified")
        if type(pyboy.frame_count) is not int or pyboy.frame_count!=observation_frame:
            return _unknown(observation_frame,case_key,"frame_not_current")
        def sample():
            a={k:pyboy.memory[v] for k,v in addresses.items()};objects=[]
            for s in range(1,c["object_count"]+1):
                p,q=0xC100+16*s,0xC200+16*s
                objects.append([pyboy.memory[p],pyboy.memory[p+1],pyboy.memory[q],pyboy.memory[q+4],
                    pyboy.memory[q+5],pyboy.memory[q+6],pyboy.memory[q+13],
                    pyboy.memory[0xD4E4+2*(s-1)],pyboy.memory[0xD4E5+2*(s-1)]])
            flags=[pyboy.memory[0xD5A6+i] for i in range(32)]
            table=[pyboy.memory[0xD5CE+i] for i in range(33)]
            return a,objects,flags,table
        first,second=sample(),sample();after=pyboy.frame_count
    except Exception:return _unknown(observation_frame,case_key,"getter_failed")
    expected=[v for pair in TOGGLE_TABLES[c["map_id"]] for v in pair]+[255]
    def valid(sampled):
        a,rows,flags,table=sampled
        return (all(_int(v) for v in a.values()) and all(_int(v) for r in rows for v in r)
            and all(_int(v) for v in flags+table) and table[:len(expected)]==expected
            and (a["map_id"],a["tileset"],a["height"],a["width"],a["object_count"])==(c["map_id"],17,9,15,c["object_count"])
            and _int(a["x"],0,29) and _int(a["y"],0,17)
            and all(4<=r[3]<=21 and 4<=r[4]<=33 for r in rows)
            and all(rows[s-1][0]==63 and rows[s-1][6]==0 and rows[s-1][8]==s for s in c["source_stones"])
            and rows[slot-1][7] in (16,255))
    if not valid(first) or not valid(second):return _unknown(observation_frame,case_key,"byte_slot_or_toggle_invalid")
    if type(after) is not int or after!=observation_frame or first!=second:
        return _unknown(observation_frame,case_key,"torn_frame_or_snapshot")
    a,rows,flags,table=first;toggle=dict(TOGGLE_TABLES[c["map_id"]])
    objects=[dict(slot=i+1,picture=r[0],status=r[1],walk_counter=r[2],y=r[3]-4,x=r[4]-4,
        movement_byte1=r[5],picture2=r[6],movement_byte2=r[7],text=r[8],
        hidden=_hidden(flags,toggle[i+1]) if i+1 in toggle else False) for i,r in enumerate(rows)]
    stone=objects[slot-1];busy,idle=_native_state(a,stone)
    return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,case_key=case_key,observation_frame=observation_frame,
        read_valid=True,read_error=None,location={k:a[k] for k in ("map_id","x","y")},stone=stone,
        objects=objects,raw=a,toggle_flags=flags,toggle_table=table,idle=idle,native_push_busy=busy,
        event=_event(c,a),live_calibrated=False)


def _grid(grid,c,player,frame):
    if (not isinstance(grid,dict) or type(grid.get("tileset_id")) is not int or grid["tileset_id"]!=17
            or type(grid.get("verified_location")) is not list or len(grid["verified_location"])!=3
            or any(type(v) is not int for v in grid["verified_location"])
            or grid.get("verified_location")!=[c["map_id"],*player]
            or type(grid.get("observation_frame")) is not int or grid["observation_frame"]!=frame
            or not _int(grid.get("screen_cells_verified"),12,540)):return False
    visible=grid.get("visible_verified_cells")
    if (not isinstance(visible,list) or len(visible)!=grid["screen_cells_verified"]
            or any(not isinstance(p,list) or len(p)!=2 or not _int(p[0],0,29) or not _int(p[1],0,17) for p in visible)
            or len(set(map(tuple,visible)))!=len(visible)):return False
    for key,high in (("tiles",255),("walkable",1)):
        cells=grid.get(key)
        if (not isinstance(cells,(list,tuple)) or len(cells)!=18 or any(not isinstance(r,(list,tuple))
                or len(r)!=30 or any(not _int(v,0,high) for v in r) for r in cells)):return False
    return grid["walkable"][player[1]][player[0]]==1


def _warps(c,p,action,tiles):
    if list(p) not in c["normal_warp_coords"]:return False
    if tiles[p[1]][p[0]] in (0x18,0x1A,0x22):return True
    return ((action=="down" and p[1]==17) or (action=="up" and p[1]==0)
            or (action=="left" and p[0]==0) or (action=="right" and p[0]==29))


def _bad_edges(c,grid):
    edges=set()
    for y in range(18):
        for x in range(30):
            for action,(dx,dy) in DELTAS.items():
                q=x+dx,y+dy
                if 0<=q[0]<30 and 0<=q[1]<18 and (_warps(c,q,action,grid["tiles"])
                        or c["map_id"]==198 and q==(23,15)):
                    edges.add(((x,y),q))
    return edges


def _other_objects(objects,slot):
    return tuple((o["slot"],o["x"],o["y"],o["picture"],o["text"],o["hidden"]) for o in objects if o["slot"]!=slot)


SOURCE_LAYOUT='source'
REVIEWED_HOLE_LAYOUT='reviewed_3f_hole_aux8_13_13_20261028'


def valid_source_layout(case_key,source_layout):
    return type(source_layout) is str and (source_layout==SOURCE_LAYOUT
        or case_key=='3f_hole' and source_layout==REVIEWED_HOLE_LAYOUT)


def initial_source_stones(case_key,source_layout):
    if not valid_source_layout(case_key,source_layout):return None
    # Fixed reviewed alternative only; CASES/contract/push geometry are immutable.
    if source_layout==REVIEWED_HOLE_LAYOUT:
        return {7:(3,5),8:(13,13),9:(24,10),10:(22,15)}
    return CASES[case_key]['source_stones']


class VictoryLaterBoulderController:
    def __init__(self,case_key,*,reviewed_fainted_bench=(),source_layout=SOURCE_LAYOUT):
        if type(reviewed_fainted_bench) is not tuple or any(type(v) is not int for v in reviewed_fainted_bench) or reviewed_fainted_bench not in ((),(7,)):
            raise ValueError('Only the explicitly reviewed Nidoking bench is supported')
        self.reviewed_fainted_bench=reviewed_fainted_bench
        if type(case_key) is not str or case_key not in CASES:raise ValueError("Only four fixed later-boulder case keys")
        if not valid_source_layout(case_key,source_layout):raise ValueError('Only one reviewed 3F-hole auxiliary layout')
        self.source_layout=self.source_layout_contract=source_layout
        self.case_key=case_key;self.case=deepcopy(CASES[case_key]);self.contract=deepcopy(self.case)
        self.pushes=self.case["pushes"];self.owner=None;self.started=self.last_now=self.step_started=None
        self.calls=self.waits=self.requests=0;self.last_frame=-1;self.last_packet=None;self.error=None
        self.push_index=0;self.pending=None;self.baseline=None;self.flags_baseline=None;self.object_baseline=None
        self.closed_frame=None;self.final_player=None;self.suspended=False;self.battle_returns=0
        self.contact_arm_seen=self.native_script_seen=self.dust_seen=False

    def _hint(self,action,tactic,complete=False,**extra):
        return dict(phase="victory_later_boulder_complete" if complete else "overworld",
            objective="Wait." if action=="wait" else "Move "+action.upper()+".",
            available_actions=["wait"] if action=="wait" else [action,"wait"],controller_menu_verified=action!="wait",
            later_boulder_complete=complete,later_boulder_case=self.case_key,later_boulder_tactic=tactic,
            later_boulder_push_index=self.push_index,suppress_navigation_stall=True,suppress_blocked_edge_learning=True,
            source_commit=SOURCE_COMMIT,contact_arm_seen=self.contact_arm_seen,native_script_seen=self.native_script_seen,
            dust_seen=self.dust_seen,**extra)
    def _fail(self,reason):
        self.error=self.error or "victory_later_boulder_"+reason
        return {**self._hint("wait","review"),"phase":"campaign_review","review_reason":self.error}
    def _wait(self,reason):
        self.waits+=1
        return self._fail("step_wait_budget_exhausted") if self.waits>MAX_STEP_WAITS else self._hint("wait",reason)
    def _reset_step(self,now):self.step_started=now;self.waits=self.requests=0;self.pending=None
    def _offer(self,kind,action,player,stone,frame):
        self.requests+=1
        if self.requests>MAX_REQUESTS:return self._fail("direction_request_budget_exhausted")
        dx,dy=DELTAS[action]
        self.pending=dict(kind=kind,action=action,player=player,stone=stone,frame=frame,executed=False,
            expected_player=(player[0]+dx,player[1]+dy) if kind=="walk" else player,
            expected_stone=(stone[0]+dx,stone[1]+dy) if kind=="push" else stone)
        return self._hint(action,"offer_"+kind)

    def context(self,state,*,text,grid,signal,previous,now,owner,overworld_ready=False):
        if self.error:return self._fail("sticky")
        c=self.case;frame=state.get("frame") if isinstance(state,dict) else None
        layout=getattr(self,'source_layout',SOURCE_LAYOUT)
        if (not valid_source_layout(self.case_key,layout)
                or layout!=getattr(self,'source_layout_contract',SOURCE_LAYOUT)
                or c!=self.contract or c!=CASES.get(self.case_key) or self.pushes!=c["pushes"]
                or not isinstance(owner,str) or not owner or self.owner is not None and owner!=self.owner
                or not _int(frame,0,2**63-1) or frame<self.last_frame or type(now) not in (int,float)
                or not math.isfinite(now) or now<0 or self.last_now is not None and now<self.last_now):
            return self._fail("case_owner_frame_or_clock_invalid")
        if self.started is None:self.started=self.step_started=now;self.owner=owner
        self.calls+=1;self.last_now=now
        if self.calls>MAX_CALLS or now-self.started>MAX_SECONDS or now-self.step_started>MAX_STEP_SECONDS:return self._fail("budget_exhausted")
        if type(previous) not in (list,tuple) or any(type(a) is not str or a not in ("wait","up","down","left","right","a","b","start") for a in previous):
            return self._fail("actual_previous_invalid")
        loc=state.get("location");battle=state.get("battle_state")
        if (not isinstance(loc,dict) or any(not _int(loc.get(k)) for k in ("map_id","x","y"))
                or loc["map_id"]!=c["map_id"] or not 0<=loc["x"]<30 or not 0<=loc["y"]<18
                or not isinstance(battle,dict) or type(battle.get("raw")) is not int
                or type(battle.get("observation_frame")) is not int or battle["observation_frame"]!=frame):
            return self._fail("location_or_battle_unverified")
        if type(overworld_ready) is not bool:return self._fail("world_ready_type_invalid")
        player=loc["x"],loc["y"]
        for observed in (loc,state.get("progress"),text):
            if isinstance(observed,dict) and "observation_frame" in observed and (
                    type(observed["observation_frame"]) is not int or observed["observation_frame"]!=frame):
                return self._fail("observation_frame_conflict")
        packet=deepcopy((state,text,grid,signal,previous,owner,overworld_ready))
        if frame==self.last_frame:
            if packet!=self.last_packet:return self._fail("same_frame_conflict")
            if self.suspended:return self._hint("wait","same_frame_owned_wild_handoff",later_boulder_battle_handoff=True)
            return self._wait("same_frame_no_resend")
        self.last_frame,self.last_packet=frame,packet
        field_receipt=(not self.suspended and ((battle["raw"]==0 and battle.get("kind")=="none" and battle.get("active") is False)
                       or (battle["raw"]==1 and battle.get("kind")=="wild" and battle.get("active") is True)))
        if field_receipt and self.pending and not self.pending["executed"] and frame>self.pending["frame"] and previous and previous[-1]==self.pending["action"]:
            self.pending["executed"]=True
        if battle["raw"]==1 and battle.get("kind")=="wild" and battle.get("active") is True:
            if self.baseline is None:return self._fail("battle_before_initial_binding")
            self.suspended=True;self.closed_frame=None
            return self._hint("wait","owned_wild_battle_handoff",later_boulder_battle_handoff=True)
        if battle["raw"]!=0 or battle.get("kind")!="none" or battle.get("active") is not False:
            return self._fail("only_raw1_wild_handoff_supported")
        if self.suspended and not overworld_ready:
            self.closed_frame=None
            return self._hint("wait","owned_wild_return_ui_handoff",later_boulder_battle_handoff=True)
        if (not isinstance(signal,dict) or signal.get("profile")!=PROFILE or signal.get("source_commit")!=SOURCE_COMMIT
                or signal.get("case_key")!=self.case_key or signal.get("read_valid") is not True or signal.get("read_error") is not None
                or type(signal.get("observation_frame")) is not int or signal["observation_frame"]!=frame
                or signal.get("location")!={"map_id":c["map_id"],"x":player[0],"y":player[1]}):
            return self._fail("source_signal_unverified")
        a=signal.get("raw");objects=signal.get("objects");stone_record=signal.get("stone")
        flags=signal.get("toggle_flags");table=signal.get("toggle_table")
        if (not isinstance(a,dict) or any(not _int(a.get(k)) for k in _addresses(self.case_key))
                or not isinstance(objects,list) or len(objects)!=c["object_count"]
                or any(not isinstance(o,dict) or type(o.get("slot")) is not int or o["slot"]!=i+1
                    or any(not _int(o.get(k)) for k in ("picture","status","walk_counter","movement_byte1","picture2","movement_byte2","text"))
                    or not _int(o.get("x"),0,29) or not _int(o.get("y"),0,17) or type(o.get("hidden")) is not bool for i,o in enumerate(objects))
                or type(flags) is not list or len(flags)!=32 or any(not _int(v) for v in flags)
                or type(table) is not list or len(table)!=33 or any(not _int(v) for v in table)
                or not isinstance(stone_record,dict) or stone_record!=objects[c["slot"]-1]
                or type(signal.get("idle")) is not bool or type(signal.get("native_push_busy")) is not bool
                or type(signal.get("event")) is not bool):return self._fail("source_signal_shape_unverified")
        expected=[v for pair in TOGGLE_TABLES[c["map_id"]] for v in pair]+[255];toggle=dict(TOGGLE_TABLES[c["map_id"]])
        if ((a["map_id"],a["x"],a["y"],a["tileset"],a["height"],a["width"],a["object_count"])!=(c["map_id"],*player,17,9,15,c["object_count"])
                or a["facing_raw"] not in FACING.values() or table[:len(expected)]!=expected
                or any(o["hidden"]!=(_hidden(flags,toggle[o["slot"]]) if o["slot"] in toggle else False) for o in objects)
                or any(objects[s-1]["picture"]!=63 or objects[s-1]["picture2"]!=0 or objects[s-1]["text"]!=s for s in c["source_stones"])
                or stone_record["movement_byte2"] not in (16,255)
                or _native_state(a,stone_record)!=(signal["native_push_busy"],signal["idle"])
                or signal["event"]!=_event(c,a)):
            return self._fail("source_signal_derivation_unverified")
        stone=stone_record["x"],stone_record["y"]
        if not a["flags1"]&1 or a["mode"]!=0 or a["battle_raw"]!=0:return self._fail("strength_or_native_world_mode_unverified")
        if a["movement_flags"]&4:return self._fail("unreviewed_warp_pad_state")
        if self.flags_baseline is not None and a["flags1"]&0xFE!=self.flags_baseline&0xFE:return self._fail("unrelated_flags1_changed")
        for key,other in CASES.items():
            if key!=self.case_key and _event(other,a)!=(key in c["required_true"]):return self._fail("ordered_source_puzzle_state_changed")
        final_native_transition=(self.push_index==len(self.pushes) or self.pending is not None
            and self.pending["executed"] and self.pending["kind"]=="push"
            and self.pending["expected_stone"]==tuple(c["goal_stone"]) and stone==tuple(c["goal_stone"]))
        if not final_native_transition:
            if signal["event"]:return self._fail("goal_opened_before_fixed_final_push")
        own_gate=("gate2" if self.case_key=="2f_switch2" else "gate1") if c["gate"] else None
        if any(a[k]!=v for k,v in c["gate_binding"].items() if not (final_native_transition and k==own_gate)):
            return self._fail("source_gate_binding_changed")
        if not (final_native_transition and self.case_key=="3f_hole"):
            if _hidden(flags,0x60)!=(self.case_key!="2f_switch2") or _hidden(flags,0x7A)!=(self.case_key=="2f_switch2"):
                return self._fail("puzzle_toggle_changed_before_hole_goal")
        current=_resources(state.get("progress"))
        if current is None:return self._fail("progress_unverified")
        if self.suspended:
            if not _wild_return(self.baseline,current):return self._fail("wild_return_resource_change_unverified")
        elif self.baseline is not None and current!=self.baseline:return self._fail("resources_changed_outside_owned_wild_battle")
        if any((m['hp']<=0 and m['species'] not in getattr(self,'reviewed_fainted_bench',())) or m['status']!=0 for m in current['party']):return self._fail('attrition_requires_owned_review')
        if self.object_baseline is not None and _other_objects(objects,c["slot"])!=self.object_baseline:
            return self._fail("other_bound_objects_changed")
        self.contact_arm_seen|=bool(a["misc"]&64);self.native_script_seen|=bool(a["flags5"]&1);self.dust_seen|=bool(a["misc"]&2)
        if self.pending and self.pending["executed"]:
            p=self.pending
            if signal["native_push_busy"]:
                if (p["kind"]!="push" or a["boulder_index"]!=c["slot"] or stone not in (p["stone"],p["expected_stone"])
                        or player not in (p["player"],p["stone"])):return self._fail("foreign_native_movement")
                self.closed_frame=None;return self._wait("native_owned_slot_movement_and_dust_only")
            if p["kind"]=="walk" and a["walk_counter"]:
                if stone!=p["stone"] or player not in (p["player"],p["expected_player"]):return self._fail("unexpected_walk_in_progress")
                self.closed_frame=None;return self._wait("native_player_walk_in_progress")
        rows=_rows(text)
        if rows is None or rows!=(" "*20,)*18 or text.get("window_visible") is not False or not overworld_ready:
            self.closed_frame=None;return self._wait("await_verified_world_without_sending_input")
        if not _grid(grid,c,player,frame):return self._fail("native_world_grid_unverified")
        if self.baseline is None:
            if (player!=tuple(c["start_player"]) or stone!=tuple(c["start_stone"]) or signal["event"] or not signal["idle"]
                    or grid["tiles"][player[1]][player[0]]!=c["start_player_tile"]
                    or any(a[k]!=v for k,v in c["gate_binding"].items())
                    or _hidden(flags,0x60)!=(self.case_key!="2f_switch2")
                    or _hidden(flags,0x7A)!=(self.case_key=="2f_switch2")
                    or any((objects[s-1]["x"],objects[s-1]["y"])!=p for s,p in initial_source_stones(self.case_key,layout).items())):
                return self._fail("initial_fixed_mechanism_unverified")
            self.baseline=current;self.flags_baseline=a["flags1"];self.object_baseline=_other_objects(objects,c["slot"])
        if self.suspended:self.baseline=current;self.suspended=False;self.battle_returns+=1
        if self.push_index==len(self.pushes):
            if player!=self.final_player:return self._fail("unowned_player_move_after_final_push")
            if stone!=tuple(c["goal_stone"]) or not signal["event"]:
                self.closed_frame=None;return self._wait("await_native_goal_event")
            if c["gate"]:
                gate=c["gate"];field="gate2" if self.case_key=="2f_switch2" else "gate1"
                physical=(a[field]==gate["after"] and all(grid["tiles"][y][x]==new for x,y,old,new in gate["cells"]))
            else:
                physical=(_hidden(flags,0x7A) and not _hidden(flags,0x60) and grid["tiles"][15][23]==0x22 and a["gate1"]==0x1D)
            if not physical:self.closed_frame=None;return self._wait("await_native_block_tiles_or_hole_toggle_pair")
            if not signal["idle"]:self.closed_frame=None;return self._wait("await_native_final_idle")
            if self.closed_frame is None:self.closed_frame=frame;return self._wait("first_closed_goal_frame")
            return self._hint("wait","verified_fixed_later_boulder",True)
        if self.pending:
            p=self.pending
            if p["kind"]=="push" and a["boulder_index"] not in (0,c["slot"]):return self._fail("wrong_contact_sprite")
            if not p["executed"]:
                if not signal["idle"]:return self._wait("unexecuted_direction_await_idle_without_resend")
                if player==p["player"] and stone==p["stone"]:
                    self.requests+=1
                    if self.requests>MAX_REQUESTS:return self._fail("direction_request_budget_exhausted")
                    return self._hint(p["action"],"retry_unexecuted_direction_same_pending")
                return self._fail("coordinate_change_without_true_previous")
            if not signal["idle"]:return self._wait("await_native_idle_before_next_direction")
            if p["kind"]=="walk":
                if stone!=p["stone"]:return self._fail("boulder_changed_during_walk")
                if player==p["expected_player"]:self._reset_step(now)
                elif player==p["player"]:return self._offer("walk",p["action"],player,stone,frame)
                else:return self._fail("unexpected_player_displacement")
            else:
                if stone==p["expected_stone"]:
                    if player not in (p["player"],p["stone"]):return self._fail("unexpected_player_follow")
                    self.push_index+=1;self._reset_step(now)
                    if self.push_index==len(self.pushes):
                        self.final_player=player;return self._wait("final_stone_moved_await_native_goal_receipt")
                elif stone==p["stone"] and player==p["player"]:return self._offer("push",p["action"],player,stone,frame)
                else:return self._fail("unexpected_boulder_displacement")
        if stone!=self.pushes[self.push_index][2]:return self._fail("stone_not_at_retained_sequence_position")
        if signal["event"] or any(a[k]!=v for k,v in c["gate_binding"].items()):return self._fail("goal_opened_before_fixed_final_push")
        if _hidden(flags,0x60)!=(self.case_key!="2f_switch2") or _hidden(flags,0x7A)!=(self.case_key=="2f_switch2"):
            return self._fail("puzzle_toggle_changed_before_hole_goal")
        if not signal["idle"]:return self._wait("await_normal_native_idle")
        action,stance,_,destination=self.pushes[self.push_index]
        if player==stance:
            # All current C2 records obstruct a stone, even when hidden/imageFF.
            if (grid["walkable"][destination[1]][destination[0]]!=1 or grid["tiles"][destination[1]][destination[0]]==0x15
                    or any((o["x"],o["y"])==destination for o in objects if o["slot"]!=c["slot"])):
                return self._fail("source_push_destination_blocked")
            pair=frozenset((grid["tiles"][player[1]][player[0]],grid["tiles"][destination[1]][destination[0]]))
            if pair in {frozenset(p) for p in ((0x20,5),(0x41,5),(0x2A,5),(5,0x21))} or _warps(c,player,action,grid["tiles"]):
                return self._fail("source_push_elevation_or_warp_blocked")
            return self._offer("push",action,player,stone,frame)
        blocked=[(o["x"],o["y"]) for o in objects if not o["hidden"]]
        if stance in blocked:return self._fail("fixed_stance_occupied")
        hint=world_direction(grid,{"map_id":c["map_id"],"x":player[0],"y":player[1]},
            {"x":stance[0],"y":stance[1]},blocked,_bad_edges(c,grid))
        if not hint:return self._fail("no_verified_normal_walk_to_fixed_stance")
        return self._offer("walk",hint["direction"],player,stone,frame)

