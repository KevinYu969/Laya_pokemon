"""來源限定的單場野生訓練批次候選；只讀／純子目標，尚未實機驗證。

只允許 map194 的 (28,7)<->(28,8)，最多32次已觀測位移或第一場 wild。
不送按鍵、不 tick、不載入 ROM/state；既有 battle 決定所有戰鬥鍵。
module初始化一次凍結受信任package data；context沒有檔案I/O。
"""
from copy import deepcopy
from hashlib import sha256
import json
from types import MappingProxyType
from laya_pokemon.team_strategy import reference as _package_reference
import math
from laya_pokemon.hm_teaching import _rows
from laya_pokemon.mart_purchase import _inventory

SOURCE_COMMIT = "a53671100ec22e5394ff26ec028d0812a238dae2"
PROFILE = "red-en-vr2-east-single-wild-training-v1-source-only"
INTENT = dict(kind="vr2_east_single_wild", map_id=194,
              tiles=[[28,7],[28,8]], max_displacements=32, target_level=45)
ROSTER = frozenset((19,132,102,154,35,7))
SPECIES_NAMES = {19:"LAPRAS",132:"SNORLAX",102:"EEVEE",154:"VENUSAUR",35:"FEAROW",7:"NIDOKING"}
# 只在module初始化一次載入受信任package data；context不再讀檔或呼叫reference。
REFERENCE_SHA256 = "248c70e24eda08e57e818e8ace37877d3452dda417d0c04dbb21e0dc64b1941b"
_package_data = _package_reference()
if _package_data.get("source_commit") != SOURCE_COMMIT:
    raise RuntimeError("package招式來源commit不符")
MOVE_DATA = MappingProxyType({m["id"]:(m["pp"],m["power"]) for m in _package_data["moves"].values()})
del _package_data, _package_reference
TILES = ((28,7),(28,8))
MAX_SECONDS, MAX_CALLS, MAX_WAITS, MAX_REQUESTS = 600, 1800, 128, 128
MAX_EXP_GAIN, MAX_LEVEL_GAIN, MAX_HP_GROWTH, MAX_PP_SPEND = 8192, 1, 12, 128
ADDRESSES = dict(map_id=0xD35E, x=0xD362, y=0xD361, tileset=0xD367,
    height=0xD368, width=0xD369, facing=0xC109, battle_raw=0xD057,
    flags3=0xD72D, flags5=0xD730, flags6=0xD732, flags7=0xD733,
    mode=0xD700, misc=0xCD60, joy_ignore=0xCD6B, walk_counter=0xCFC5,
    simulated=0xCD38, movement_flags=0xD736)
_ACTIONS = frozenset(("up","down","left","right","a","b","start","wait"))

TURN_RETURN_REVIEW = {'kind': 'reviewed_training_turn_return30833_v1', 'game_id': 'game29', 'original_step_id': 'root-calibration-game29-20261028-out-067', 'plan_bytes_sha256': '432b4056ceeb469d62539d5b68659bc03357c467b2aef4f06f1a383582fc9f7e', 'binding_sha256': '93c365a277428572faa3ca72b2ef86c380938ebab0846653a94c2e98f3436080', 'baseline_sha256': '6689f9d51ce7ab8165e3179491a2dad02bbf205868d2dca5e99a7fa6ce393046', 'source_packet_sha256': '757bd2f50d6e129a47e7fedc7cddc903a34fada3f094f6df51306cd72573a2bf', 'source_progress_sha256': '727b0bec570b16b1c511fc7dc6103bfe8938904a940fadf9ec18538a9b9b498a', 'source_location': {'map_id': 194, 'x': 28, 'y': 7}, 'pending': {'action': 'down', 'player': [28, 7], 'expected': [28, 8], 'frame': 23673, 'executed': True}, 'actual_action_frame': 23673, 'first_wild_frame': 23713, 'historical_walk_sha256': '8b8d77cf6152da6f3690b4983d2e26c760a31b841af215c1fe56809975a678bf', 'historical_wild_sha256': 'cf08750b3fdf5ea37ea0a7f2ccd1f8b654d9b861748fedd133cfb05fa564011f', 'evidence': {'review_sha256': '447706ef6bb895538d1b23c49b1c1264deae1d70ad884f3af0208a24dbd7c6b6', 'state_sha256': 'e76501526abd833119eb32830f89613a6b5e82ee84bb28b0cc0983eb16317b14', 'preflight_sha256': 'e7f633c1021dc393419c18bc8c2ba31c1329fdbd85df48e0a432b524fb775123'}, 'last_frame': 30833, 'calls': 149, 'waits': 129, 'requests': 3, 'displacements': 2}
REVIEW_CLOSURE_FRAMES,REVIEW_CLOSURE_CALLS=240,4


def _review_sha(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
                             ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def integer(value, low=0, high=255):
    return type(value) is int and low <= value <= high


def _idle(raw):
    return (raw["joy_ignore"] == raw["walk_counter"] == raw["simulated"] == 0
        and not raw["movement_flags"] & 0xFB and not raw["flags5"] & 0xA7
        and not raw["flags3"] & 0x18 and not raw["flags6"] & 0x5C
        and not raw["flags7"] & 4 and not raw["misc"] & 2
        and raw["mode"] == raw["battle_raw"] == 0)


def read_training_observation(pyboy, frame, constants):
    """同 frame 雙讀來源 bytes 與既有真 progress/battle getters；不允許 caller RAM。"""
    unknown = dict(profile=PROFILE, source_commit=SOURCE_COMMIT, observation_frame=frame,
                   read_valid=False, read_error="source_getter_unverified", live_calibrated=False)
    try:
        from laya_pokemon.progress import read_progress
        from laya_pokemon.battle import read_battle_state
        if (not integer(frame,0,2**63-1) or type(pyboy.frame_count) is not int
                or pyboy.frame_count != frame or constants.MAPS.get("victory_road_2f") != 194
                or type(constants.MAPS.get("victory_road_2f")) is not int
                or constants.PARTY_COUNT_ADDRESS != 0xD163 or constants.PARTY_MON_SIZE != 44
                or constants.PARTY_MONS_ADDRESS != 0xD16B):
            return unknown
        def sample():
            raw = {key:pyboy.memory[address] for key,address in ADDRESSES.items()}
            return raw, read_progress(pyboy,constants), read_battle_state(pyboy)
        first, second = sample(), sample()
        if (type(pyboy.frame_count) is not int or pyboy.frame_count != frame or first != second
                or any(not integer(v) for packet in (first,second) for v in packet[0].values())):
            return unknown
        raw, progress, battle = first
        if (raw["map_id"],raw["tileset"],raw["height"],raw["width"]) != (194,17,9,15):
            return unknown
        return dict(profile=PROFILE,source_commit=SOURCE_COMMIT,observation_frame=frame,
            read_valid=True,read_error=None,raw=raw,progress=progress,battle=battle,
            location={k:raw[k] for k in ("map_id","x","y")},idle=_idle(raw),live_calibrated=False)
    except Exception:
        return unknown


def resources(progress):
    if (not isinstance(progress,dict) or progress.get("profile")!="gen1-wrapper-ram-progress-v1-unvalidated"
            or progress.get("initialization_candidate") is not True or progress.get("party_read_valid") is not True
            or type(progress.get("party_count")) is not int or progress["party_count"]!=6):
        return None
    party = progress.get("party")
    bag = _inventory(progress.get("inventory")) if isinstance(progress,dict) else None
    if (not isinstance(party,list) or len(party)!=6 or any(not isinstance(m,dict)
            or type(m.get("species")) is not int for m in party)
            or {m["species"] for m in party} != ROSTER
            or bag is None or not integer(progress.get("money"),0,999999)
            or progress.get("player_name_raw") != "KEVIN" or not integer(progress.get("badges_raw"))):
        return None
    for mon in party:
        if (mon.get("species_name")!=SPECIES_NAMES[mon["species"]]
                or not integer(mon.get("level"),1,100) or not integer(mon.get("exp"),0,0xFFFFFF)
                or not integer(mon.get("max_hp"),1,999) or not integer(mon.get("hp"),0,mon["max_hp"])
                or not integer(mon.get("status")) or mon["status"] not in set(range(8)) | {8,16,32,64}
                or any(not isinstance(mon.get(k),list) or len(mon[k])!=4
                       or any(not integer(v,0,high) for v in mon[k]) for k,high in (("moves",165),("pp",255)))):
            return None
        occupied = [m for m in mon["moves"] if m]
        if not occupied or len(occupied) != len(set(occupied)):
            return None
        for move, pp in zip(mon["moves"],mon["pp"]):
            if (not move and pp or move and (pp&63) > MOVE_DATA[move][0]*(5+(pp>>6))//5):
                return None
    return deepcopy(dict(party=party,inventory=bag,money=progress["money"],
        badges_raw=progress["badges_raw"],player_name_raw=progress["player_name_raw"],
        story_event_bits=progress.get("story_event_bits")))


def needs_center(current):
    return any(m["status"] or m["hp"]*3 <= m["max_hp"]*2
        or sum((p&63) for move,p in zip(m["moves"],m["pp"])
               if move and MOVE_DATA[move][1]>0) < 3
        for m in current["party"])


def validate_wild_delta(before,after,approved_learning=None):
    if approved_learning is not None:
        from laya_pokemon import league_training_learning_receiver as receiver
        try:
            return None,receiver.approved_delta(before,after,approved_learning,normalize=resources,
                base_validator=validate_wild_delta,needs_center=needs_center)
        except (ValueError,KeyError,TypeError,AttributeError) as exc:
            return 'learning_approval_or_delta_invalid:'+str(exc),None
    """明示保守收據：物品、金錢、招式／成員改變一律 review，無獎勵不冒稱成功。"""
    if any(before[k] != after[k] for k in before if k != "party"):
        return "bag_money_or_world_change_requires_review", None
    gain=spent=0; mutable={"level","exp","hp","max_hp","status","pp"}
    for old,new in zip(before["party"],after["party"]):
        if ({k:v for k,v in old.items() if k not in mutable}
                != {k:v for k,v in new.items() if k not in mutable}):
            return "party_or_moves_change_requires_review",None
        level,exp,growth = new["level"]-old["level"],new["exp"]-old["exp"],new["max_hp"]-old["max_hp"]
        if (not 0 <= level <= MAX_LEVEL_GAIN or not 0 <= exp <= MAX_EXP_GAIN
                or not 0 <= growth <= MAX_HP_GROWTH or level == 0 and growth != 0
                or level and exp == 0 or not 1 <= new["hp"] <= old["hp"]+growth):
            return "wild_level_exp_hp_delta_unverified",None
        gain += exp
        for oldpp,newpp in zip(old["pp"],new["pp"]):
            if oldpp>>6 != newpp>>6 or (newpp&63) > (oldpp&63):
                return "wild_pp_gain_unverified",None
            spent += (oldpp&63)-(newpp&63)
    if not 0 < gain <= MAX_EXP_GAIN or spent > MAX_PP_SPEND:
        return "single_wild_reward_or_pp_bound_unverified",None
    return None,dict(total_exp_gain=gain,total_pp_spent=spent,
        levels_before=[m["level"] for m in before["party"]],
        levels_after=[m["level"] for m in after["party"]],needs_center=bool(needs_center(after)))


def closed_world(text,grid,player,frame):
    from laya_pokemon.campaign_transactions import verified_blank_transaction_world
    if (not verified_blank_transaction_world(text,grid) or _rows(text) != (" "*20,)*18
            or not isinstance(grid,dict) or type(grid.get("tileset_id")) is not int
            or grid["tileset_id"] != 17 or grid.get("verified_location") != [194,*player]
            or type(grid.get("observation_frame")) is not int or grid["observation_frame"] != frame):
        return False
    visible=grid.get("visible_verified_cells");count=grid.get("screen_cells_verified")
    if (not integer(count,12,540) or not isinstance(visible,list) or len(visible) != count
            or any(not isinstance(p,list) or len(p)!=2 or not integer(p[0],0,29)
                   or not integer(p[1],0,17) for p in visible)
            or len(set(map(tuple,visible))) != count or not set(TILES) <= set(map(tuple,visible))):
        return False
    for key,high in (("tiles",255),("walkable",1)):
        cells=grid.get(key)
        if (not isinstance(cells,(list,tuple)) or len(cells)!=18
                or any(not isinstance(row,(list,tuple)) or len(row)!=30
                       or any(not integer(v,0,high) for v in row) for row in cells)):
            return False
    return all(grid["tiles"][y][x] == 0x20 and grid["walkable"][y][x] == 1 for x,y in TILES)


class TrainingBatch:
    def __init__(self,intent=INTENT):
        if (type(intent) is not dict or intent != INTENT or set(intent) != set(INTENT)
                or any(type(intent[k]) is not type(v) for k,v in INTENT.items())
                or any(type(n) is not int for p in intent["tiles"] for n in p)):
            raise ValueError("只接受固定194兩格、45級checkpoint的單場批次")
        self.intent=deepcopy(intent);self.contract=deepcopy(intent);self.owner=None
        self.started=self.last_now=None;self.calls=self.waits=self.requests=self.displacements=0
        self.last_frame=-1;self.last_packet=None;self.error=None;self.pending=None
        self.baseline=None;self.seen_wild=False;self.suspended=False;self.closed_frame=None
        self.returned_world_seen=False
        self.closed_resources=None;self.closed_player=None;self.final_player=None
        self.complete=False;self.outcome=None;self.receipt=None
        self.pending_ack_frame=None;self.wild_walk_evidence=None
        self.closed_cancelled_walk=None;self.cancelled_walk_history=[]
        self.cancelled_walk_closure_review=None;self.cancelled_walk_review_history=[]

    def hint(self,action="wait",tactic="wait",**extra):
        return dict(phase="training_batch_complete" if self.complete else "training_batch_owned",
            objective="Wait." if action=="wait" else "Move "+action.upper()+".",
            available_actions=["wait"] if action=="wait" else [action,"wait"],
            controller_menu_verified=action!="wait",training_batch_complete=self.complete,
            training_batch_outcome=self.outcome,training_batch_tactic=tactic,
            training_batch_displacements=self.displacements,training_batch_receipt=deepcopy(self.receipt),
            source_commit=SOURCE_COMMIT,live_calibrated=False,suppress_navigation_stall=True,
            suppress_blocked_edge_learning=True,**extra)

    def fail(self,reason):
        self.error=self.error or "league_training_batch_"+reason
        return {**self.hint(tactic="review"),"phase":"campaign_review","review_reason":self.error}

    def wait(self,reason,**extra):
        self.waits += 1
        review=getattr(self,'cancelled_walk_closure_review',None)
        if review is not None:
            if type(review) is not dict or not integer(review.get('waits'),0,REVIEW_CLOSURE_CALLS):
                return self.fail('review_closure_metadata_unverified')
            review['waits']+=1
            return (self.fail('review_closure_wait_budget_exhausted') if review['waits']>REVIEW_CLOSURE_CALLS
                    else self.hint(tactic=reason,**extra))
        return self.fail("wait_budget_exhausted") if self.waits>MAX_WAITS else self.hint(tactic=reason,**extra)

    def offer(self,player,frame):
        if getattr(self,'cancelled_walk_closure_review',None) is not None:
            return self.fail('review_closure_must_not_offer_walk')
        self.requests+=1
        if self.requests>MAX_REQUESTS:return self.fail("request_budget_exhausted")
        action="down" if player==TILES[0] else "up"
        expected=TILES[1] if player==TILES[0] else TILES[0]
        self.pending=dict(action=action,player=player,expected=expected,frame=frame,executed=False)
        self.pending_ack_frame=None
        return self.hint(action,"offer_fixed_tile_displacement")

    def review_cancelled_turn_return(self,*,review_capsule,source_evidence):
        """Only the named warm error; root first proves native/binding/full peers.

        No historical flag is fabricated. The independent pinned actual walk/wild
        logs remain reviewed historical evidence, distinct from new observations.
        Preserve original counters/clock/pending/packet; only closure may continue.
        """
        try:
            cap=TURN_RETURN_REVIEW
            if (_review_sha(review_capsule)!=_review_sha(cap)
                    or _review_sha(source_evidence)!=_review_sha(cap['evidence'])
                    or self.error!='league_training_batch_wait_budget_exhausted'
                    or self.owner!=cap['original_step_id'] or _review_sha(self.intent)!=_review_sha(INTENT)
                    or self.intent!=self.contract or self.seen_wild is not True or self.suspended is not True
                    or self.returned_world_seen is not False or self.complete is not False
                    or any(getattr(self,k) is not None for k in
                           ('closed_frame','closed_resources','closed_player','final_player','outcome','receipt'))
                    or _review_sha(self.pending)!=_review_sha(cap['pending'])
                    or type(self.last_packet) is not tuple or len(self.last_packet)!=6
                    or _review_sha(self.last_packet)!=cap['source_packet_sha256']
                    or _review_sha(self.baseline)!=cap['baseline_sha256']
                    or any(type(getattr(self,k)) is not int or getattr(self,k)!=cap[k]
                           for k in ('last_frame','calls','waits','requests','displacements'))
                    or any(type(v) not in (int,float) or not math.isfinite(v) or v<0
                           for v in (self.started,self.last_now))
                    or not 0<=self.last_now-self.started<=MAX_SECONDS or self.calls>=MAX_CALLS
                    or getattr(self,'cancelled_walk_closure_review',None) is not None
                    or getattr(self,'cancelled_walk_review_history',None) not in (None,[])
                    or getattr(self,'cancelled_walk_history',None) not in (None,[])):
                return self.fail('cancelled_turn_review_unverified')
            state,text,grid,signal,previous,owner=self.last_packet
            current=resources(state.get('progress'));source_current=resources(signal.get('progress'))
            raw=signal.get('raw');battle=state.get('battle_state')
            if (owner!=self.owner or state.get('frame')!=cap['last_frame']
                    or state.get('location')!=cap['source_location']
                    or _review_sha(state.get('progress'))!=cap['source_progress_sha256']
                    or current is None or current!=source_current
                    or not isinstance(raw,dict) or signal.get('idle') is not True or not _idle(raw)
                    or not isinstance(battle,dict) or battle.get('raw')!=0 or battle.get('kind')!='none'
                    or battle.get('active') is not False or battle.get('observation_frame')!=cap['last_frame']
                    or not closed_world(text,grid,tuple(self.pending['player']),cap['last_frame'])
                    or validate_wild_delta(self.baseline,current)[0] is not None):
                return self.fail('cancelled_turn_review_packet_unverified')
            preserved={k:deepcopy(getattr(self,k)) for k in
                ('owner','started','last_now','calls','waits','requests','displacements','last_frame','pending')}
            entry=dict(old_error=self.error,capsule=deepcopy(review_capsule),preserved=preserved,
                original_packet_sha256=_review_sha(self.last_packet),baseline_sha256=_review_sha(self.baseline))
            if getattr(self,'cancelled_walk_review_history',None) is None:self.cancelled_walk_review_history=[]
            self.cancelled_walk_review_history.append(entry)
            if getattr(self,'cancelled_walk_history',None) is None:self.cancelled_walk_history=[]
            self.cancelled_walk_closure_review=dict(capsule=deepcopy(review_capsule),pending=self.pending,
                snapshot=deepcopy(self.pending),source_frame=self.last_frame,calls=0,waits=0,
                history_sha256=_review_sha(entry),done=False)
            self.error=None
            return self.hint(tactic='reviewed_turn_return_closure_only')
        except (KeyError,TypeError,ValueError,AttributeError,IndexError,RecursionError):
            return self.fail('cancelled_turn_review_unverified')

    def _cancelled_turn_evidence(self):
        """First actual wild at the ACKed walk's source, never a battle-key ACK."""
        p=self.pending;e=getattr(self,'wild_walk_evidence',None)
        review=getattr(self,'cancelled_walk_closure_review',None)
        if review is not None:
            history=getattr(self,'cancelled_walk_review_history',None)
            if (type(review) is not dict or review.get('pending') is not p or review.get('snapshot')!=p
                    or type(history) is not list or len(history)!=1
                    or _review_sha(history[0])!=review.get('history_sha256')
                    or _review_sha(review.get('capsule'))!=_review_sha(TURN_RETURN_REVIEW)):
                return None
            cap=review['capsule']
            return dict(kind='reviewed_original_turn_before_displacement',wild_frame=cap['first_wild_frame'],
                actual_action_frame=cap['actual_action_frame'],actual_ack_frame=cap['first_wild_frame'],
                pending=deepcopy(p),wild_player=list(p['player']),displacement_occurred=False,
                historical_walk_sha256=cap['historical_walk_sha256'],historical_wild_sha256=cap['historical_wild_sha256'])
        if (not self.seen_wild or not self.suspended or type(p) is not dict or p.get('executed') is not True
                or type(e) is not dict or e.get('pending') is not p or e.get('snapshot')!=p
                or e.get('player')!=p.get('player') or e.get('raw')!=1 or e.get('active') is not True
                or e.get('kind')!='wild' or not integer(e.get('frame'),0,2**63-1)
                or not integer(e.get('ack_frame'),0,2**63-1)
                or not integer(p.get('frame'),0,2**63-1) or not p['frame']<e['ack_frame']<=e['frame']
                or p.get('player') not in TILES or p.get('expected') not in TILES
                or p['expected']==p['player']
                or p.get('action')!=('down' if p['player']==TILES[0] else 'up')):
            return None
        return dict(kind='observed_turn_before_displacement',wild_frame=e['frame'],
            actual_ack_frame=e['ack_frame'],pending=deepcopy(p),wild_player=list(e['player']),
            displacement_occurred=False)

    def context(self,state,*,text,grid,signal,previous,now,owner):
        if self.error:return self.fail("sticky")
        frame=state.get("frame") if isinstance(state,dict) else None
        if (self.intent!=self.contract or not isinstance(owner,str) or not owner
                or self.owner is not None and owner!=self.owner or not integer(frame,0,2**63-1)
                or frame<self.last_frame or type(now) not in (int,float) or not math.isfinite(now)
                or now<0 or self.last_now is not None and now<self.last_now):
            return self.fail("owner_frame_or_time_unverified")
        if self.started is None:self.started=now;self.owner=owner
        self.calls+=1;self.last_now=now
        if self.calls>MAX_CALLS or now-self.started>MAX_SECONDS:return self.fail("budget_exhausted")
        if (type(previous) not in (list,tuple)
                or any(type(a) is not str or a not in _ACTIONS for a in previous)):
            return self.fail("true_previous_unverified")
        loc=state.get("location");battle=state.get("battle_state")
        if (not isinstance(loc,dict) or any(not integer(loc.get(k)) for k in ("map_id","x","y"))
                or loc["map_id"]!=194 or (loc["x"],loc["y"]) not in TILES
                or not isinstance(battle,dict) or not integer(battle.get("raw"))
                or type(battle.get("observation_frame")) is not int or battle["observation_frame"]!=frame):
            return self.fail("location_or_battle_unverified")
        player=(loc["x"],loc["y"])
        if self.final_player is not None and player!=self.final_player:
            return self.fail("unowned_displacement_after_walk_budget")
        if (not isinstance(signal,dict) or signal.get("profile")!=PROFILE
                or signal.get("source_commit")!=SOURCE_COMMIT or signal.get("read_valid") is not True
                or signal.get("read_error") is not None or type(signal.get("observation_frame")) is not int
                or signal["observation_frame"]!=frame or signal.get("location")!={k:loc[k] for k in ("map_id","x","y")}):
            return self.fail("source_signal_unverified")
        raw=signal.get("raw");native=signal.get("battle")
        if (not isinstance(raw,dict) or any(not integer(raw.get(k)) for k in ADDRESSES)
                or (raw["map_id"],raw["x"],raw["y"],raw["tileset"],raw["height"],raw["width"])!=(194,*player,17,9,15)
                or raw["facing"] not in (0,4,8,12)
                or type(signal.get("idle")) is not bool or signal["idle"]!=_idle(raw)
                or not isinstance(native,dict) or any(native.get(k)!=battle.get(k) for k in ("raw","kind","active","observation_frame"))
                or raw["battle_raw"]!=battle["raw"]):
            return self.fail("source_derivation_or_native_state_conflict")
        for observed in (text,state.get("progress")):
            if isinstance(observed,dict) and "observation_frame" in observed and (
                    type(observed["observation_frame"]) is not int or observed["observation_frame"]!=frame):
                return self.fail("observation_frame_conflict")
        packet=deepcopy((state,text,grid,signal,previous,owner))
        if frame==self.last_frame:
            if packet!=self.last_packet:return self.fail("same_frame_conflict")
            return self.hint(tactic="same_frame_no_resend",training_batch_battle_handoff=self.suspended)
        self.last_frame,self.last_packet=frame,packet
        if self.complete:return self.fail("completed_batch_reentered")
        is_wild=(battle["raw"]==1 and battle.get("kind")=="wild" and battle.get("active") is True)
        is_world=(battle["raw"]==0 and battle.get("kind")=="none" and battle.get("active") is False)
        if not is_wild and not is_world:return self.fail("only_native_raw1_wild_supported")
        # 只在尚未見過 wild 的 field 邊界接受真 previous。後續戰鬥方向永遠不補 ACK。
        if (not self.seen_wild and self.pending and not self.pending["executed"]
                and frame>self.pending["frame"] and previous and previous[-1]==self.pending["action"]):
            self.pending["executed"]=True
            self.pending_ack_frame=frame
        if is_wild:
            if getattr(self,'cancelled_walk_closure_review',None) is not None:
                return self.fail('review_closure_new_battle_forbidden')
            if self.baseline is None or self.pending is None:return self.fail("wild_without_owned_walk")
            if self.returned_world_seen:return self.fail("second_wild_after_verified_return")
            if not self.seen_wild:
                self.wild_walk_evidence=dict(pending=self.pending,snapshot=deepcopy(self.pending),
                    player=player,frame=frame,ack_frame=getattr(self,'pending_ack_frame',None),
                    raw=battle['raw'],kind=battle['kind'],active=battle['active'])
            self.seen_wild=self.suspended=True;self.closed_frame=None;self.closed_resources=None;self.closed_player=None
            return self.hint(tactic="owned_single_wild",training_batch_battle_handoff=True)
        closed=signal["idle"] and closed_world(text,grid,player,frame)
        review=getattr(self,'cancelled_walk_closure_review',None)
        if review is not None:
            if (type(review) is not dict or review.get('done') is not False
                    or not integer(review.get('calls'),0,REVIEW_CLOSURE_CALLS)
                    or not integer(review.get('source_frame'),0,2**63-1)
                    or not 0<frame-review['source_frame']<=REVIEW_CLOSURE_FRAMES
                    or review['calls']>=REVIEW_CLOSURE_CALLS or not closed
                    or player!=tuple(TURN_RETURN_REVIEW['pending']['player'])
                    or _review_sha(state.get('progress'))!=TURN_RETURN_REVIEW['source_progress_sha256']):
                return self.fail('review_closure_only_world_or_budget_unverified')
            review['calls']+=1
        if self.suspended and not closed:
            self.closed_frame=None;self.closed_resources=None;self.closed_player=None
            return self.wait("owned_learning_dialogue_or_return",training_batch_battle_handoff=True)
        current=resources(state.get("progress"));source_current=resources(signal.get("progress"))
        if current is None or source_current is None or current!=source_current:
            return self.fail("party_or_source_progress_unverified")
        if any(m["hp"]==0 for m in current["party"]):return self.fail("fainted_party_requires_review")
        if self.baseline is None:
            if not closed:return self.fail("initial_blank_idle_source_world_required")
            if needs_center(current):return self.fail("initial_party_requires_center")
            self.baseline=current
            return self.offer(player,frame)
        if not self.suspended and current!=self.baseline:
            return self.fail("resource_change_outside_owned_wild")
        if not closed:
            self.closed_frame=None;self.closed_resources=None;self.closed_player=None
            return self.wait("await_blank_idle_source_world")
        cancelled=None
        if self.pending:
            pending=self.pending
            if not pending["executed"]:
                if player!=pending["player"]:return self.fail("displacement_without_true_previous")
                if self.suspended:return self.fail("wild_walk_execution_unverified")
                self.requests+=1
                if self.requests>MAX_REQUESTS:return self.fail("request_budget_exhausted")
                return self.hint(pending["action"],"retry_same_unexecuted_pending")
            if player!=pending["expected"]:
                if player!=pending["player"]:return self.fail("foreign_displacement")
                if self.suspended:
                    cancelled=self._cancelled_turn_evidence()
                    if cancelled is None:return self.fail('wild_source_return_without_turn_ack_proof')
                else:return self.wait("executed_walk_await_coordinate_receipt")
            if not self.suspended:
                self.displacements+=1;self.pending=None
                if self.displacements<INTENT["max_displacements"]:return self.offer(player,frame)
                self.final_player=player
        if self.suspended:
            self.returned_world_seen=True  # UI可重置雙frame候選，不能抹掉已返場的歷史。
            reason,receipt=validate_wild_delta(self.baseline,current,
                approved_learning=getattr(self,'approved_learning',None))
            if reason:return self.fail(reason)
        else:receipt=dict(total_exp_gain=0,total_pp_spent=0,needs_center=False)
        if self.closed_frame is None:
            self.closed_frame=frame;self.closed_resources=current;self.closed_player=player
            self.closed_cancelled_walk=deepcopy(cancelled)
            return self.wait("first_closed_source_world")
        if self.closed_player!=player:return self.fail("closed_world_position_changed")
        if self.closed_resources!=current:return self.fail("closed_world_resources_changed")
        if getattr(self,'closed_cancelled_walk',None)!=cancelled:return self.fail('closed_walk_resolution_changed')
        if frame<=self.closed_frame:return self.fail("fresh_closure_frame_required")
        if self.suspended:
            if cancelled is None:self.displacements+=1
            else:
                history=getattr(self,'cancelled_walk_history',None)
                if type(history) is not list:return self.fail('cancelled_walk_history_unverified')
                history.append(dict(cancelled,closed_frames=[self.closed_frame,frame],
                    displacements_before=self.displacements,displacements_after=self.displacements))
            self.pending=None;self.suspended=False
            self.outcome="complete_single_wild"
        else:self.outcome="complete_no_encounter"
        if not (0 if cancelled is not None else 1)<=self.displacements<=INTENT["max_displacements"]:
            return self.fail("displacement_bound_unverified")
        self.receipt={**receipt,"wild_count":int(self.seen_wild),"closed_frames":[self.closed_frame,frame]}
        if cancelled is not None:self.receipt.update(walk_resolution='cancelled_before_displacement',
            displacement_occurred=False,cancelled_walk=deepcopy(self.cancelled_walk_history[-1]))
        if getattr(self,'cancelled_walk_closure_review',None) is not None:
            self.cancelled_walk_closure_review['done']=True
        self.complete=True
        return self.hint(tactic="two_fresh_closed_source_worlds")
