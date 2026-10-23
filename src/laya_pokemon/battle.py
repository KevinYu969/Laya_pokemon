"""第一世代初期對戰／捕捉的唯讀選單提示；不是完整戰術模型。"""
from __future__ import annotations

from numbers import Integral
import re
import importlib
from . import levelup_control, levelup_moves
importlib.reload(levelup_control)
importlib.reload(levelup_moves)


# wram.asm: wIsInBattle、單 byte wPartyGainExpFlags、wCurOpponent；後者由 PyBoy 定位 D059。
BATTLE_STATE_ADDRESS = 0xD057
PLAYER_DISABLED_MOVE_ADDRESS = 0xD06D
PLAYER_BATTLE_SPECIES_ADDRESS = 0xD014
PLAYER_BATTLE_MOVES_ADDRESS = 0xD01C
PLAYER_PARTY_INDEX_ADDRESS = 0xCC2F
DISABLE_SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
DISABLE_SOURCE = f'https://github.com/pret/pokered/blob/{DISABLE_SOURCE_COMMIT}/engine/battle/effects.asm'
DISABLE_SOURCE_SHA256 = {
    'engine/battle/effects.asm': '6e7650408de33069aae9521473f62a1078697f7b539a3978daa49a0e6df825d3',
    'engine/battle/core.asm': '36d8ff785fe642d61f6917156e70b78c36fd7cde6c0b8fb582e02f6552e786d0',
    'ram/wram.asm': '00683cd430a9ef30794d2aeaee51f3a5440e4bb14dca13e9f9cb5fa88f130e34',
    'macros/ram.asm': 'cfb685afd3d00f3f4ee083014424e185f40250bf508579e007e686117a6b2a30',
}
SOURCE = "https://github.com/pret/pokered/blob/master/ram/wram.asm"
MENU_SOURCE = "https://github.com/pret/pokered/blob/master/engine/battle/core.asm"
_no_pp_switch = globals().get('_no_pp_switch')


def _read_player_disabled_move(pyboy):
    """唯讀玩家封招；D057錨點+固定wram排列、舊符號D06D獨立交叉核對。"""
    result = {'state': 'unknown', 'valid': False, 'address': PLAYER_DISABLED_MOVE_ADDRESS,
              'source': DISABLE_SOURCE, 'source_commit': DISABLE_SOURCE_COMMIT}
    def byte(address):
        value = pyboy.memory[address]
        if not isinstance(value, Integral) or isinstance(value, bool) or not 0 <= value <= 255:
            raise ValueError('not a byte')
        return int(value)
    try:
        packed = byte(PLAYER_DISABLED_MOVE_ADDRESS)
        result['raw'] = packed
        if packed == 0:
            return {**result, 'state': 'clear', 'valid': True, 'slot': None, 'turns_left': 0}
        slot, turns = packed >> 4, packed & 15
        if not 1 <= slot <= 4 or not 1 <= turns <= 8:
            return {**result, 'state': 'invalid', 'reason': 'disabled_move_bits_out_of_source_range'}
        species = byte(PLAYER_BATTLE_SPECIES_ADDRESS)
        moves = [byte(PLAYER_BATTLE_MOVES_ADDRESS + index) for index in range(4)]
        party_index = byte(PLAYER_PARTY_INDEX_ADDRESS)
        from .team_strategy import species_key
        if (species_key(species) is None or not 0 <= party_index <= 5
                or any(move > 165 for move in moves) or moves[slot - 1] == 0):
            return {**result, 'state': 'invalid', 'reason': 'disabled_move_owner_or_slot_not_verified'}
        return {**result, 'state': 'disabled', 'valid': True, 'slot': slot - 1,
                'turns_left': turns, 'move_id': moves[slot - 1], 'species': species,
                'party_index': party_index, 'battle_moves': moves}
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return {**result, 'reason': 'disabled_move_signal_unreadable'}


def _disabled_policy_party(party, signal):
    """只遮策略副本的PP，封招絕不外溢至其他隊員，不寫入SDK或遊戲。"""
    if signal is None:
        return party, None  # 舊合成呼叫沒有RAM訊號；真實read_battle_state總會附帶。
    if not isinstance(signal, dict):
        return None, 'player_disabled_move_signal_not_verified'
    if signal.get('valid') is not True or signal.get('state') not in {'clear', 'disabled'}:
        return None, 'player_disabled_move_signal_not_verified'
    if signal['state'] == 'clear':
        if type(signal.get('raw')) is not int or signal['raw'] != 0:
            return None, 'player_disabled_move_signal_inconsistent'
        return party, None
    index, slot = signal.get('party_index'), signal.get('slot')
    turns = signal.get('turns_left')
    if (type(index) is not int or type(slot) is not int or not 0 <= index < len(party)
            or not 0 <= slot < 4 or type(turns) is not int or not 1 <= turns <= 8
            or type(signal.get('raw')) is not int or signal['raw'] != ((slot + 1) << 4 | turns)):
        return None, 'player_disabled_move_signal_inconsistent'
    mon = party[index]
    moves = mon.get('moves')
    if (not isinstance(moves, list) or len(moves) != 4 or any(type(move) is not int or not 0 <= move <= 165 for move in moves)
            or mon.get('species') != signal.get('species') or moves != signal.get('battle_moves')
            or moves[slot] != signal.get('move_id')):
        return None, 'player_disabled_move_owner_disagrees_with_party'
    pp = mon.get('pp', [])
    if (not isinstance(pp, (list, tuple)) or len(pp) != 4 or any(not isinstance(value, Integral) or isinstance(value, bool)
                           or not 0 <= value <= 255 for value in pp)):
        return None, 'player_disabled_move_pp_unreadable'
    masked = list(party)
    masked_pp = list(pp)
    masked_pp[slot] = 0
    masked[index] = {**mon, 'pp': masked_pp}
    return masked, None


def _all_available_attacks_resisted(active, enemy):
    """只比較已知、可用的一般傷害招；未知或沒有攻擊候選不推論該逃跑。"""
    from .team_strategy import effective_power, move_key, species_key
    if not active or species_key(active.get('species')) is None or species_key(enemy) is None:
        return None
    moves, pp = active.get('moves'), active.get('pp')
    if not isinstance(moves, list) or not isinstance(pp, list) or len(moves) != 4 or len(pp) != 4:
        return None
    evidence = []
    for move, remaining in zip(moves, pp):
        if not isinstance(remaining, Integral) or isinstance(remaining, bool) or not 0 <= remaining <= 255:
            return None
        if not remaining & 63 or move == 0:
            continue
        if move_key(move) is None:
            return None
        base = effective_power(move, active['species'])
        if base <= 0:
            continue
        effective = effective_power(move, active['species'], enemy)
        if effective >= base:
            return None
        evidence.append({'move': move_key(move), 'base_effective_power': base, 'effective_power': effective})
    return evidence or None


def read_battle_state(pyboy) -> dict:
    """只讀旗標；未知值不當作非戰鬥，亦不從此旗標推論勝利。"""
    raw = pyboy.memory[BATTLE_STATE_ADDRESS]
    if not isinstance(raw, Integral) or isinstance(raw, bool) or not 0 <= raw <= 255:
        raise ValueError("戰鬥旗標不是 byte")
    raw = int(raw)
    opponent = None
    if raw in {1,2}:
        try:
            # wCurOpponent(D059)在自然戰鬥中可歸零；改讀實際在場結構wEnemyMonSpecies。
            value = pyboy.memory[0xCFE5]
            from .team_strategy import species_key
            if isinstance(value, Integral) and not isinstance(value, bool):
                opponent = species_key(int(value))
        except (KeyError, IndexError, TypeError, ValueError):
            pass
    return {"raw": raw, "active": raw in (1, 2) if raw in (0, 1, 2, 255) else None,
            "kind": {0: "none", 1: "wild", 2: "trainer", 255: "lost_transition"}.get(raw, "unknown"),
            "wild_opponent_species": opponent if raw==1 else None, "opponent_species":opponent,
            "opponent_source": "https://github.com/pret/pokered/blob/53ae0e93fad9f4c3eaef92f102b1eeb531e59d68/wram.asm#L641",
            "source": SOURCE, "victory_confirmed": None,
            "player_disabled_move": _read_player_disabled_move(pyboy) if raw in {1, 2}
                else {'state': 'not_in_battle', 'valid': True}}


def _label(rows, label):
    matches = [(row.index(label), y) for y, row in enumerate(rows[12:], 12) if label in row]
    return matches[0] if len(matches) == 1 else None


def _selection_hint(rows, target, menu):
    cursors = [(x, y) for y, row in enumerate(rows[12:], 12) for x, c in enumerate(row) if c == "▶"]
    if len(cursors) != 1:
        return {"phase": "battle_menu", "objective": "Wait for a readable menu cursor.",
                "available_actions": ["wait", "b"], "battle_menu": menu,
                "phase_source": "local battle cursor parser; unreadable cursor"}
    x, y = cursors[0]
    tx, ty = target
    if y != ty:
        objective = "Move UP." if y > ty else "Move DOWN."
    elif x + 1 != tx:
        objective = "Move LEFT." if x + 1 > tx else "Move RIGHT."
    else:
        objective = "Confirm the current selection."
    return {"phase": "battle_menu", "objective": objective,
            "available_actions": ["a", "b"] if objective.startswith("Confirm") else ["up", "down", "left", "right", "wait"],
            "battle_menu": menu, "battle_target_tile": list(target), "battle_cursor_tile": list(cursors[0]),
            "phase_source": "local visible battle menu parser; subgoal supplied by controller",
            "battle_strategy": "controller menu subgoal; chosen move or capture tactic logged separately", "source": MENU_SOURCE}


def battle_context(text, battle_state, party=(), inventory=None, *, capture_focus=False) -> dict | None:
    """僅對已核對 ROM 的實驗性路線提供局部提示；不執行按鍵。"""
    global _no_pp_switch
    if battle_state.get("kind")=="lost_transition":
        return {"phase":"strategy_review","objective":"Wait.","available_actions":["wait","b"],"review_reason":"battle_loss_requires_review","battle_loss_confirmed":True,"phase_source":"read-only wIsInBattle LOST_BATTLE=255; save and review before continuing"}
    if battle_state["active"] is not True:
        _no_pp_switch=None
        return None
    signal = battle_state.get('player_disabled_move')
    party, disabled_error = _disabled_policy_party(party, signal)
    if disabled_error:
        return {'phase': 'strategy_review', 'objective': 'Wait.', 'available_actions': ['wait'],
                'review_reason': disabled_error, 'player_disabled_move': signal}
    cells = text.get("cells", [])
    if len(cells) == 18 and all(len(row) == 20 for row in cells):
        rows = ["".join(row).upper() for row in cells]
        dialogue = " ".join(rows[12:])
        if 'THEMOVEISDISABLED' in re.sub(r'[^A-Z]', '', dialogue):
            if not signal or signal.get('state') != 'disabled':
                return {'phase': 'strategy_review', 'objective': 'Wait.', 'available_actions': ['wait'],
                        'review_reason': 'disabled_move_message_without_verified_signal'}
            return {'phase': 'battle_dialogue', 'objective': 'Confirm the current selection.',
                    'available_actions': ['a', 'wait'], 'battle_tactic': 'dismiss_verified_disabled_move_message',
                    'player_disabled_move': signal}
        if "CHANGE" in dialogue and ("POKÉMON" in dialogue or "POKEMON" in dialogue):
            return {"phase": "battle_menu", "objective": "Cancel to keep the current active Pokemon.",
                    "available_actions": ["b", "wait"], "battle_tactic": "keep_active",
                    "phase_source": "visible trainer replacement prompt; retain trained lead"}
        # 玩家 HP 顯示在右側 HUD；排除左下的招式 PP，亦避免使用可能落後的 party HP。
        health = []
        for row in rows[8:12]:
            match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", row[10:])
            if match:
                hp, maximum = map(int, match.groups())
                if 0 <= hp <= maximum and maximum > 0:
                    health.append({"hp": hp, "max_hp": maximum})
        retreat = (battle_state.get("kind") == "wild" and len(health) == 1
                   and health[0]["hp"] * 2 <= health[0]["max_hp"])
        from .team_strategy import reference, normalize, species_key, move_key, choose_damage_move, capture_plan
        names = reference()["species"]
        party_form = len(party)>1 and all(species_key(mon["species"]) and any(normalize(species_key(mon["species"])) in normalize(row) for row in rows[:12]) for mon in party)
        enemy_rows = [] if party_form else [normalize(row.strip()) for row in rows[:4]]
        enemy_matches = [key for key in names if normalize(key) in enemy_rows]
        enemy = next(iter(enemy_matches), None)
        ram_enemy = battle_state.get("opponent_species") or battle_state.get("wild_opponent_species")
        if enemy and ram_enemy and enemy != ram_enemy:
            return {"phase": "strategy_review", "review_reason": "visible_enemy_and_wild_opponent_signal_disagree"}
        if enemy is None:
            enemy = ram_enemy  # 背包可能蓋住 HUD；只在野生旗標下讀已核對的wEnemyMonSpecies。
        visible_names={normalize(row.strip()) for row in rows[6:10]}
        matches=[mon for mon in party if normalize(species_key(mon['species'])) in visible_names]
        active=matches[0] if len(matches)==1 else party[0] if len(party)==1 else None
        if _no_pp_switch and active and active['species']==_no_pp_switch['species']:_no_pp_switch=None
        if _no_pp_switch:
            from .party_control import party_choice,selection
            compact=normalize(' '.join(rows))
            if 'ALREADYOUT' in compact or 'CANTSWITCH' in compact:
                return {'phase':'strategy_review','review_reason':'no_pp_switch_rejected'}
            if 'SWITCH' in compact and 'STATS' in compact:
                return selection(rows,'SWITCH','battle_menu') or {'phase':'strategy_review','review_reason':'switch_submenu_unreadable'}
            target=next((i for i,m in enumerate(party) if m['species']==_no_pp_switch['species'] and m['hp']>0),None)
            if target is not None:
                hint=party_choice(rows,party,target)
                if hint:return {**hint,'phase':'battle_menu','battle_tactic':'switch_no_attack_pp'}
        # 強制換人／戰鬥隊伍頁：名字每三列、游標在HP列，不把FNT主力反覆選入。
        if "NOWILLTOFIGHT" in normalize(" ".join(rows)):
            return {"phase":"battle_menu","objective":"Confirm the current selection.","available_actions":["a","b"],"battle_tactic":"dismiss_fainted_message"}
        party_names=[(index,mon,y) for index,mon in enumerate(party) for y,row in enumerate(rows[:12]) if species_key(mon['species']) and normalize(species_key(mon['species'])) in normalize(row)]
        party_cursors=[(x,y) for y,row in enumerate(rows[:12]) for x,c in enumerate(row[:2]) if c in {'▶','▷'}]
        if len(party_names)==len(party) and len(party)>1 and len(party_cursors)==1:
            healthy=[(index,mon) for index,mon in enumerate(party) if mon['hp']>0]
            if healthy:
                from .team_strategy import effective_power
                target=max(healthy,key=lambda item:(max((effective_power(move,item[1]['species'],enemy) for move,pp in zip(item[1].get('moves',[]),item[1].get('pp',[])) if pp&63),default=0)*item[1]['level'],item[1]['hp']))[0]
                current=next((index for index,mon,y in party_names if y<=party_cursors[0][1]<=y+1),None)
                if current is None:return {'phase':'strategy_review','review_reason':'party_cursor_not_at_verified_member'}
                objective='Confirm the current selection.' if current==target else 'Move DOWN.' if current<target else 'Move UP.'
                return {'phase':'battle_menu','objective':objective,'available_actions':['a','b'] if current==target else ['up','down','wait'],'battle_tactic':'select_healthy_party','party_target_index':target,'enemy_species':enemy,'controller_menu_verified':True}
        owned = [mon["species"] for mon in party]
        balls = sum(item["quantity"] for item in inventory or [] if item["item"] == 4)
        capture = capture_plan(enemy, owned, balls, wild=battle_state.get("kind") == "wild", party_count=len(party))
        catch = capture["tactic"] == "throw_ball"
        skip_non_target = capture_focus and enemy is not None and battle_state.get("kind") == "wild" and capture["tactic"] == "not_capture"
        retreat = retreat or skip_non_target
        resisted_retreat = {}
        if (not retreat and not catch and capture['tactic'] == 'not_capture'
                and battle_state.get('kind') == 'wild' and len(enemy_matches) == 1 and len(matches) == 1):
            resisted = _all_available_attacks_resisted(active, enemy)
            if resisted:
                retreat = True
                resisted_retreat = {'retreat_reason': 'all_available_damage_moves_resisted',
                                    'resisted_attacks': resisted, 'enemy_species': enemy}
        fight, item, run = (_label(rows, word) for word in ("FIGHT", "ITEM", "RUN"))
        if fight and item and run:
            if resisted_retreat:
                result = _selection_hint(rows, run, 'command')
                result.update(battle_tactic='retreat', **resisted_retreat)
                return result
            if _no_pp_switch:
                result=_selection_hint(rows,(run[0],fight[1]),'command')
                result.update(battle_tactic='switch_pending_party',party_target_species=_no_pp_switch['species'],enemy_species=enemy)
                return result
            # 岩系等明顯抗性對手改派有效隊員；不為練等反覆用弱效招硬打。
            if active and enemy and battle_state.get('kind')=='trainer' and not _no_pp_switch:
                from .team_strategy import effective_power
                def attack_score(mon):
                    return max((effective_power(move,mon['species'],enemy) for move,pp in zip(mon.get('moves',[]),mon.get('pp',[])) if pp&63),default=0)*mon.get('level',1)
                supports=[mon for mon in party if mon['species']!=active['species'] and mon['hp']*2>mon['max_hp'] and attack_score(mon)>0]
                target=max(supports,key=attack_score,default=None)
                low_hp=active['hp']*3<=active['max_hp']
                if target and (attack_score(target)>max(1,attack_score(active))*2.5 or low_hp and attack_score(target)>=attack_score(active)*.75):
                    _no_pp_switch={'species':target['species']}
                    result=_selection_hint(rows,(run[0],fight[1]),'command')
                    result.update(battle_tactic='switch_low_hp_support' if low_hp else 'switch_type_advantage',party_target_species=target['species'],enemy_species=enemy)
                    return result
            if active and 'moves' in active and 'pp' in active and choose_damage_move(active['species'],active['moves'],active['pp'],enemy) is None:
                from .team_strategy import effective_power
                candidates=[m for m in party if m['species']!=active['species'] and m['hp']>0 and choose_damage_move(m['species'],m.get('moves',[]),m.get('pp',[]),enemy)]
                if not candidates:return {'phase':'strategy_review','review_reason':'no_healthy_attacking_support'}
                target=max(candidates,key=lambda m:max((effective_power(move,m['species'],enemy) for move,pp in zip(m['moves'],m['pp']) if pp&63),default=0)*m.get('level',1))
                _no_pp_switch={'species':target['species']}
                result=_selection_hint(rows,(run[0],fight[1]),'command');result['battle_tactic']='switch_no_attack_pp';return result
            if capture["tactic"] == "review":
                return {"phase": "strategy_review", "objective": "Wait.", "available_actions": ["wait", "b"],
                        "capture_plan": capture, "review_reason": capture["reason"]}
            result = _selection_hint(rows, run if retreat else item if catch else fight, "command")
            result.update(battle_tactic="retreat" if retreat else "capture" if catch else "damage",
                          visible_player_hp=health, capture_plan=capture, enemy_species=enemy)
            return result
        # 道具選單只信任標籤前一格游標，避免對手圖像被誤解為游標。
        if catch and not retreat:
            for y, row in enumerate(rows[:13]):
                match = re.search(r"POK[ÉE] BALL", row)
                if match and match.start() > 0:
                    target_x = match.start()
                    cursors = [(target_x - 1, cy) for cy, candidate in enumerate(rows[:13])
                               if candidate[target_x - 1] == "▶"]
                    if len(cursors) == 1:
                        direction = "UP" if cursors[0][1] > y else "DOWN"
                        return {"phase": "battle_bag", "objective": "Confirm the current selection." if cursors[0][1] == y else f"Move {direction}.",
                                "available_actions": ["a", "b"] if cursors[0][1] == y else ["up", "down", "wait"],
                                "capture_plan": capture, "phase_source": "visible POKE BALL bag cursor; controller capture subgoal"}
        # 讀目前在場寶可夢：目前一隻時唯一；多隻必須有唯一可見名稱配對。
        active = party[0] if len(party) == 1 else None
        if len(party) > 1:
            visible_names = {normalize(row.strip()) for row in rows[6:10]}
            matches = [mon for mon in party if species_key(mon["species"]) and normalize(species_key(mon["species"])) in visible_names]
            if len(matches) == 1:
                active = matches[0]
        if active and "moves" in active and "pp" in active:
            labels = {move_key(move): (len(row) - len(row.lstrip(" ▶")), y) for move in active["moves"] if move and move_key(move)
                      for y, row in enumerate(rows[12:], 12)
                      if normalize(row[5:]) == normalize(move_key(move).removesuffix("_M"))}
            cursor_rows = [y for y, row in enumerate(rows[12:], 12) if "▶" in row]
            if labels and len(cursor_rows) == 1 and cursor_rows[0] in {pos[1] for pos in labels.values()}:
                if retreat or catch:
                    return {"phase": "battle_menu", "objective": "Cancel and return to the battle command menu.",
                            "available_actions": ["b", "wait"], "battle_tactic": "retreat" if retreat else "capture",
                            **resisted_retreat}
                selected = choose_damage_move(active["species"], active["moves"], active["pp"], enemy)
                if selected in labels:
                    result = _selection_hint(rows, labels[selected], "moves")
                    result.update(chosen_move=selected, enemy_species=enemy,
                                  battle_strategy="Gen I power/accuracy/STAB/type heuristic; not full damage simulation",
                                  player_disabled_move=signal)
                    return result
                if any(m['species']!=active['species'] and m['hp']>0 and choose_damage_move(m['species'],m.get('moves',[]),m.get('pp',[]),enemy) for m in party):
                    return {'phase':'battle_menu','objective':'Cancel and return to the battle command menu.','available_actions':['b','wait'],'battle_tactic':'return_for_no_pp_switch'}
                return {"phase": "strategy_review", "objective": "Wait.", "available_actions": ["wait", "b"],"review_reason": "no_verified_damaging_move_with_pp"}
        tackle, growl = (_label(rows, word) for word in ("TACKLE", "GROWL"))
        if tackle and growl and tackle[0] == growl[0] and tackle[1] != growl[1]:
            if retreat:
                return {"phase": "battle_menu", "objective": "Cancel and return to the battle command menu.",
                        "available_actions": ["b", "wait"], "battle_tactic": "retreat",
                        "visible_player_hp": health, "phase_source": "visible wild-battle HP at or below half; controller retreat rule"}
            return _selection_hint(rows, tackle, "moves")
    if any(y >= 12 for y in text.get("line_rows", [])):
        return {"phase": "battle_dialogue", "objective": "Advance the visible dialogue with the confirm button.",
                "available_actions": ["a", "wait"], "phase_source": "battle flag and visible lower dialogue"}
    return {"phase": "battle_animation", "objective": "Wait.", "available_actions": ["wait", "a"],
            "phase_source": "battle flag; no readable lower dialogue"}


_skip_poison_session = globals().get('_skip_poison_session')


def poisonpowder_skip_context(text,party):
    """妙蛙草22級毒粉略過的實驗流程；分頁狀態鎖與異常刪招停機。"""
    global _skip_poison_session
    from .team_strategy import normalize,learn_move_plan
    from .party_control import command,selection
    upper=' '.join(text.get('lines',[])).upper();compact=normalize(upper)
    learner=next((m for m in party if m['species']==9 and m['level']==22 and m.get('moves')==[33,45,73,22]),None)
    if _skip_poison_session is None:
        if not learner or 'IVYSAUR' not in compact or 'TRYINGTOLEARN' not in compact:return None
        plan=learn_move_plan(9,learner['moves'],'POISONPOWDER',level=22)
        if plan['decision']!='skip':return None
        _skip_poison_session={'confirmed_move':False,'plan':plan,'phase':'intro'}
    if learner is None:
        _skip_poison_session=None
        return {'phase':'strategy_review','review_reason':'learning_party_changed_unexpectedly'}
    if 'DIDNOTLEARN' in compact:
        _skip_poison_session=None
        return command('a','learning_menu',{'learning_tactic':'skip_confirmed'})
    if 'POISONPOWDER' in compact:_skip_poison_session['confirmed_move']=True
    if any(phrase in compact for phrase in ['WHICHMOVESHOULD','BEFORGOTTEN','FORGOT','12AND']):
        return {'phase':'strategy_review','review_reason':'unexpected_forget_menu_during_skip'}
    if 'DELETE' in compact:_skip_poison_session['phase']='delete_decision'
    if 'STOPLEARNING' in compact:_skip_poison_session['phase']='stop_decision'
    question=_skip_poison_session.get('phase') in {'delete_decision','stop_decision'}
    if question:
        if not _skip_poison_session['confirmed_move']:
            return {'phase':'strategy_review','review_reason':'learning_move_not_visually_confirmed'}
        cells=text.get('cells',[]);rows=[''.join(row).upper() for row in cells]
        target='YES' if _skip_poison_session['phase']=='stop_decision' else 'NO'
        result=selection(rows,target,'learning_menu') if 'YES' in compact and 'NO' in compact else None
        if result:return {**result,'learning_tactic':'skip_poisonpowder','learn_move_plan':_skip_poison_session['plan']}
        if '▼' in upper:return command('a','learning_menu',{'learning_tactic':'advance_wrapped_learning_question'})
        return {'phase':'learning_menu','objective':'Wait.','available_actions':['wait','b'],'learning_tactic':'await_learning_choices'}
    if 'YES' in compact and 'NO' in compact:
        return {'phase':'strategy_review','review_reason':'learning_question_not_confirmed'}
    return command('a','learning_menu',{'learning_tactic':'advance_poisonpowder_intro'})


def learning_context(text, party, progress=None):
    """有四招的學招流程暫停並留下計畫；待真實忘招畫面校準後才能執行。"""
    from .team_strategy import normalize, reference, learn_move_plan
    specific=levelup_control.skip_context(text,party)
    if specific:return specific
    skip=poisonpowder_skip_context(text,party)
    if skip:return skip
    if progress is not None:
        if progress.get('party') != party:
            return {'phase':'strategy_review','objective':'Wait.','available_actions':['wait'],
                    'review_reason':'natural_learning_progress_party_mismatch'}
        natural=levelup_moves.context(text,progress)
        if natural:return natural
    upper = " ".join(text.get("lines", [])).upper()
    compact = normalize(upper)
    if not any(normalize(phrase) in compact for phrase in
               ("TRYING TO LEARN", "DELETE A MOVE", "DELETE AN OLDER", "MOVE TO MAKE ROOM",
                "FORGET WHICH MOVE", "WHICH MOVE SHOULD", "BE FORGOTTEN", "STOP LEARNING",
                "ABANDON LEARNING", "FORGOT", "POOF")):
        return None
    if len(party) != 1 or len([move for move in party[0].get("moves", []) if move]) == 4:
        new_moves = [key for key in reference()["moves"]
                     if normalize(key.removesuffix("_M")) in compact and len(normalize(key)) >= 4]
        plan = learn_move_plan(party[0]["species"], party[0].get("moves", []), new_moves[0], level=party[0]["level"]) \
            if len(party) == 1 and len(new_moves) == 1 else {"decision": "review", "reason": "learning_context_ambiguous"}
        return {"phase": "strategy_review", "objective": "Wait.", "available_actions": ["wait", "b"],
                "review_reason": "forget_move_menu_requires_live_calibration", "learn_move_plan": plan}
    return None
