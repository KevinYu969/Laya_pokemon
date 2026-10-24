"""第一世代初期對戰／捕捉的唯讀選單提示；不是完整戰術模型。"""
from __future__ import annotations

from numbers import Integral
import re
import importlib
from . import levelup_control, levelup_moves, ditto_transform
importlib.reload(levelup_control)
importlib.reload(levelup_moves)
importlib.reload(ditto_transform)


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
_fixed_damage_risk = globals().get('_fixed_damage_risk')
FIXED_DAMAGE_SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
FIXED_DAMAGE_SOURCES = {
    'constants/battle_constants.asm#L58': 'db511a861aa64c631e43810315c2ce684cc107dfc94a958d1a34d51e99eafeeb',
    'engine/battle/core.asm#L4773': '36d8ff785fe642d61f6917156e70b78c36fd7cde6c0b8fb582e02f6552e786d0',
    'constants/move_constants.asm#L90': 'e8ac9263abd68b85c1292893b7a55d0664005e52ffc832fe8f6abe2c9d48c74d',
}
_VISIBLE_PROFILE = 'gen1-visible-tile-text-candidates-v1-unvalidated'
TRAINER_HALF_HP_PROFILE = 'red-en-trainer-half-hp-v1'
_TRAINER_HALF_REASON = 'trainer_half_hp_support'


def _trainer_half_review(reason):
    return {'phase': 'strategy_review', 'objective': 'Wait.', 'available_actions': ['wait'],
            'review_reason': 'trainer_half_hp_' + reason}


def _trainer_half_rows(text, *, party=None):
    rows=_fixed_damage_rows(text)
    if rows is None:
        # a536711 common_text.asm:GetmText -> PlayerMon1Text(done): native
        # $e5 is ONE physical cell "'m". Only this already-requested switch
        # may read it; the general fixed-damage decoder remains unchanged.
        record=_no_pp_switch
        if (not isinstance(text,dict) or not isinstance(record,dict)
                or record.get('reason')!=_TRAINER_HALF_REASON
                or record.get('switch_requested') is not True
                or not _trainer_half_party_valid(party)
                or tuple(m['species'] for m in party)!=record.get('party_species')):
            return None
        cells=text.get('cells')
        if (not isinstance(cells,(list,tuple)) or len(cells)!=18
                or any(not isinstance(row,(list,tuple)) or len(row)!=20 for row in cells)
                or any(not isinstance(c,str) or (len(c)!=1 and (x,y,c)!=(4,14,"'m"))
                       for y,row in enumerate(cells) for x,c in enumerate(row))
                or cells[14][4]!="'m"):
            return None
        from .team_strategy import species_key
        target=species_key(record.get('species')); enemy=species_key(record.get('enemy_species'))
        if not target or not enemy:return None
        expected=[' ']*20
        for x,value in ((1,'Get'),(4,"'m"),(5,'!'),(7,target+'!')):
            expected[x:x+(1 if x==4 else len(value))]=[value] if x==4 else list(value)
        if [c.upper() for c in cells[14]]!=[c.upper() for c in expected]:return None
        native=[list(row) for row in cells];native[14][4]='m'
        rows=_fixed_damage_rows({**text,'cells':native})
        if rows is None:return None
        allowed=[m for m in party if m['species'] in (record.get('active_species'),record.get('species'))
                 and rows[7]==(' '*10+species_key(m['species'])).ljust(20)]
        if len(allowed)!=1:return None
        mon=allowed[0]
        if (mon['status']!=0 or mon['hp']<=0
                or rows[0]!=(' '+enemy).ljust(20)
                or rows[1][:5]!=' '*5 or rows[1][8:]!=' '*12
                or not rows[1][5:8].strip().isdigit()
                or not 1<=int(rows[1][5:8])<=100
                or rows[8][:14]!=' '*14 or rows[8][18:]!=' '*2
                or rows[8][14:18].strip()!=str(mon['level'])
                or rows[10]!=(' '*11+f"{mon['hp']:3}/{mon['max_hp']:3}").ljust(20)
                or any(rows[y]!=' '*20 for y in range(18) if y not in (0,1,7,8,10,14))):
            return None
        rows[14]=f" GET'M! {target}!".ljust(20)
    if 'lines' in text or 'line_rows' in text:
        raw=[''.join(row) for row in text['cells']]
        selected=[(i,row.rstrip()) for i,row in enumerate(raw) if re.search(r'[A-Za-z0-9]{2,}',row)][:12]
        if text.get('lines') != [row for _,row in selected] or text.get('line_rows') != [i for i,_ in selected]:
            return None
    return rows


def _trainer_half_party_valid(party):
    return (isinstance(party, (list, tuple)) and 1 <= len(party) <= 6
            and all(_fixed_damage_mon_valid(m) and type(m.get('status')) is int
                    and m['status'] in {*range(8),8,16,32,64} for m in party)
            and len({m['species'] for m in party}) == len(party))


def _trainer_half_score(mon, enemy):
    from .team_strategy import effective_power
    return max((effective_power(move, mon['species'], enemy) for move, pp in zip(mon['moves'], mon['pp'])
                if pp & 63), default=0) * mon['level']


def _trainer_half_support(mon, enemy):
    return (mon['hp'] * 2 > mon['max_hp'] and mon['status'] == 0
            and _trainer_half_score(mon, enemy) > 0)


def _trainer_half_status(mon):
    if mon['status']==0:return str(mon['level'])
    return 'SLP' if mon['status']<8 else {8:'PSN',16:'BRN',32:'FRZ',64:'PAR'}[mon['status']]


def _trainer_half_command_layout(rows):
    cursors=[(x,y) for y,row in enumerate(rows) for x,c in enumerate(row) if c=='▶']
    if len(cursors)!=1 or cursors[0] not in {(9,14),(15,14),(9,16),(15,16)}:
        return False
    expected=[[' ']*20 for _ in range(6)]
    for x,y,label in ((10,14,'FIGHT'),(10,16,'ITEM'),(16,16,'RUN')):
        expected[y-12][x:x+len(label)]=label
    x,y=cursors[0];expected[y-12][x]='▶'
    return rows[12:]==[''.join(row) for row in expected] and not any('▷' in row for row in rows)


def _trainer_half_party_view(party,index,submenu=False,*,inactive=False):
    """固定普通隊伍頁；保留原生一格level符號解碼空白，正常名字/HP/狀態可核。"""
    from .team_strategy import species_key
    cells=[[' ']*20 for _ in range(18)]
    def put(x,y,value):cells[y][x:x+len(value)]=value
    for i,mon in enumerate(party):
        y=i*2;put(3,y,species_key(mon['species']))
        put(13 if mon['level']==100 else 14,y,str(mon['level']))
        status='SLP' if 0<mon['status']<8 else {0:'',8:'PSN',16:'BRN',32:'FRZ',64:'PAR'}[mon['status']]
        put(17,y,status);put(13,y+1,f"{mon['hp']:3}/{mon['max_hp']:3}")
    put(1,14,'CHOOSE A POKÉMON.');put(0,index*2+1,'▷' if submenu or inactive else '▶')
    if submenu:
        for y in range(11,18):cells[y][11:20]=[' ']*9
        for y,label in ((12,'SWITCH'),(14,'STATS'),(16,'CANCEL')):put(13,y,label)
        put(12,12,'▷' if inactive else '▶')
    return [''.join(row) for row in cells]


def _trainer_half_command(text, rows, party, health):
    """只驗新1/3..1/2區間，不把reader opt-in當成UI證據或修改legacy策略。"""
    from .team_strategy import reference, normalize, choose_damage_move
    if not re.search(r'\b(?:FIGHT|ITEM|RUN)\b', ' '.join(rows[12:])):
        return None
    possible = (not _trainer_half_party_valid(party)
                or any(m['hp'] * 3 > m['max_hp'] and m['hp'] * 2 <= m['max_hp'] for m in party)
                or any(h['hp'] * 3 > h['max_hp'] and h['hp'] * 2 <= h['max_hp'] for h in health))
    if not possible:
        return None
    if _trainer_half_rows(text) is None or not _trainer_half_party_valid(party):
        return _trainer_half_review('command_or_party_unverified')
    names = reference()['species']
    enemies = [name for row in rows[:4] for name in names if normalize(row.strip()) == normalize(name)]
    active = [m for row in rows[6:10] for m in party
              if normalize(row.strip()) == normalize(next(k for k,v in names.items() if v['id']==m['species']))]
    cursors = [(x,y) for y,row in enumerate(rows) for x,c in enumerate(row) if c=='▶']
    if (len(enemies) != 1 or len(active) != 1 or len(health) != 1
            or health[0] != {'hp':active[0]['hp'], 'max_hp':active[0]['max_hp']}
            or active[0]['hp'] <= 0 or rows[8].strip()!=_trainer_half_status(active[0])
            or any('▷' in row or '▼' in row for row in rows)
            or (_label(rows,'FIGHT'),_label(rows,'ITEM'),_label(rows,'RUN')) != ((10,14),(10,16),(16,16))
            or not _trainer_half_command_layout(rows)):
        return _trainer_half_review('command_hud_or_identity_unverified')
    current = active[0]
    if not (current['hp'] * 3 > current['max_hp'] and current['hp'] * 2 <= current['max_hp']):
        return None
    # 全無攻擊PP仍由原有no-PP策略處理，這裡不改其優先序。
    if choose_damage_move(current['species'],current['moves'],current['pp'],enemies[0]) is None:
        return None
    return {'active':current, 'enemy':enemies[0]}


def _trainer_half_pending(text, battle_state, party):
    """新reason沿正常PKMN/party/SWITCH；未知不落入legacy的對話A。"""
    global _no_pp_switch
    from .team_strategy import species_key, normalize
    from .party_control import party_choice, selection
    record = _no_pp_switch
    rows = _trainer_half_rows(text,party=party)
    if (rows is None or not _trainer_half_party_valid(party)
            or tuple(m['species'] for m in party) != record['party_species']
            or species_key(battle_state.get('opponent_species')) != record['enemy_species']):
        return _trainer_half_review('pending_observation_or_enemy_changed')
    target = [m for m in party if m['species'] == record['species']]
    if len(target) != 1:
        return _trainer_half_review('pending_target_ambiguous')
    target = target[0]
    if text['cells'][14][4]=="'m":
        # SendOutMon immediately draws the new HUD/animation after this done
        # text; there is no outer prompt. A verified new HUD completes the
        # switch, but this observation still only WAITs. The old HUD stays
        # pending. The enemy consumes its turn before the next command page.
        if rows[7]==(' '*10+species_key(target['species'])).ljust(20):
            _no_pp_switch=None
            return {'phase':'battle_animation','objective':'Wait.','available_actions':['wait'],
                    'battle_tactic':'wait_trainer_half_hp_switch_handoff'}
        record['waits']=record.get('waits',0)+1
        if record['waits']>25:return _trainer_half_review('pending_transition_wait_exhausted')
        return {'phase':'battle_animation','objective':'Wait.','available_actions':['wait'],
                'battle_tactic':'wait_trainer_half_hp_switch'}
    if record.get('switch_requested') is True:
        # Sampling may miss Get'm entirely. Only the observed native DISABLE
        # retaliation page plus the complete new target HUD proves this
        # narrow handoff; no generic enemy text or early A is authorized.
        expected=[' '*20 for _ in range(18)]
        expected[0]=(' '+record['enemy_species']).ljust(20)
        expected[1]=rows[1]
        expected[7]=(' '*10+species_key(target['species'])).ljust(20)
        expected[8]=rows[8]
        expected[10]=(' '*11+f"{target['hp']:3}/{target['max_hp']:3}").ljust(20)
        expected[14]=(' ENEMY '+record['enemy_species']).ljust(20)
        expected[16]=' USED DISABLE!'.ljust(20)
        if (rows==expected and target['hp']>0 and target['status']==0
                and rows[1][:5]==' '*5 and rows[1][8:]==' '*12
                and rows[1][5:8].strip().isdigit() and 1<=int(rows[1][5:8])<=100
                and rows[8][:14]==' '*14 and rows[8][18:]==' '*2
                and rows[8][14:18].strip()==str(target['level'])):
            _no_pp_switch=None
            return {'phase':'battle_animation','objective':'Wait.','available_actions':['wait'],
                    'battle_tactic':'wait_trainer_half_hp_switch_handoff'}
    party_view = all(normalize(rows[i*2][3:13]) == normalize(species_key(m['species']))
                     for i,m in enumerate(party))
    lower = ' '.join(' '.join(rows[12:]).split())
    if not party_view:
        active = [m for row in rows[6:10] for m in party
                  if normalize(row.strip()) == normalize(species_key(m['species']))]
        hp = [tuple(map(int,match.groups())) for row in rows[8:12]
              if (match:=re.fullmatch(r'\s*(\d+)\s*/\s*(\d+)\s*',row[10:]))]
        command = all(_label(rows,label) for label in ('FIGHT','ITEM','RUN'))
        visible_enemies=[species_key(row.strip()) for row in rows[:4] if species_key(row.strip())]
        if command and visible_enemies != [record['enemy_species']]:
            return _trainer_half_review('pending_visible_enemy_changed')
        if (record.get('switch_requested') and len(active)==1 and active[0]['species']==target['species']
                and hp==[(target['hp'],target['max_hp'])] and target['hp']>0 and target['status']==0
                and rows[8].strip()==_trainer_half_status(target)):
            sent = [f'GO! {species_key(target["species"])}!',f'DO IT! {species_key(target["species"])}!',
                    f"GET'M! {species_key(target['species'])}!"]
            if command and _trainer_half_command_layout(rows) or lower in sent:
                _no_pp_switch=None
                return None
        if command and not record.get('party_open_requested'):
            checked = _trainer_half_command(text,rows,party,[{'hp':a,'max_hp':b} for a,b in hp])
            if checked is None or 'review_reason' in checked or checked['enemy']!=record['enemy_species']:
                return _trainer_half_review('pending_command_unverified')
            if not _trainer_half_support(target,record['enemy_species']):
                return _trainer_half_review('pending_support_unverified')
            hint=_selection_hint(rows,(16,14),'command')
            if hint['objective']=='Confirm the current selection.':record['party_open_requested']=True
            return {**hint,'battle_tactic':'switch_pending_party','party_target_species':target['species']}
        if record.get('switch_requested'):
            name=species_key(record['active_species']); wanted=species_key(target['species'])
            messages=[f'{name} ENOUGH! COME BACK!',f'{name} OK! COME BACK!',f'{name} GOOD! COME BACK!',
                      f'{name} COME BACK!',f'GO! {wanted}!',f'DO IT! {wanted}!',f"GET'M! {wanted}!"]
            if lower in messages:
                return {'phase':'battle_dialogue','objective':'Confirm the current selection.',
                        'available_actions':['a','wait'],'battle_tactic':'verified_switch_dialogue'}
            if lower and not any(message.startswith(lower) for message in messages):
                return _trainer_half_review('pending_ui_unverified')
        elif not command:
            return _trainer_half_review('pending_ui_unverified')
    else:
        if not _trainer_half_support(target,record['enemy_species']):
            return _trainer_half_review('pending_support_unverified')
        index=next(i for i,m in enumerate(party) if m['species']==target['species'])
        markers=[(x,y,c) for y,row in enumerate(rows) for x,c in enumerate(row) if c in {'▶','▷','▼'}]
        submenu=any('SWITCH' in row or 'STATS' in row or 'CANCEL' in row for row in rows[12:])
        if submenu:
            if rows != _trainer_half_party_view(party,index,True):
                if not (record.get('switch_requested') and rows == _trainer_half_party_view(party,index,True,inactive=True)):
                    return _trainer_half_review('pending_switch_menu_unverified')
            elif not record.get('switch_requested'):
                result=selection(rows,'SWITCH','battle_menu')
                if not result:return _trainer_half_review('pending_switch_menu_unverified')
                record['switch_requested']=True
                return {**result,'battle_tactic':'switch_trainer_half_hp'}
        elif (len(markers)==1 and markers[0][0]==0 and markers[0][1]%2==1
              and markers[0][1]//2<len(party) and markers[0][2] in {'▶','▷'}):
            cursor=markers[0][1]//2
            if rows != _trainer_half_party_view(party,cursor,inactive=markers[0][2]=='▷'):
                return _trainer_half_review('pending_party_menu_unverified')
            if not record.get('member_selected') and markers[0][2]=='▶':
                result=party_choice(rows,party,index)
                if not result:return _trainer_half_review('pending_party_menu_unverified')
                if result['objective']=='Confirm the current selection.':record['member_selected']=True
                return {**result,'phase':'battle_menu','battle_tactic':'switch_trainer_half_hp'}
        else:
            return _trainer_half_review('pending_party_menu_unverified')
    record['waits']=record.get('waits',0)+1
    if record['waits']>25:return _trainer_half_review('pending_transition_wait_exhausted')
    return {'phase':'battle_animation','objective':'Wait.','available_actions':['wait'],
            'battle_tactic':'wait_trainer_half_hp_switch'}


def _clear_fixed_damage_risk():
    global _fixed_damage_risk, _no_pp_switch
    _fixed_damage_risk = None
    if _no_pp_switch and _no_pp_switch.get('reason') == 'observed_dragon_rage_risk':
        _no_pp_switch = None


def _fixed_damage_rows(text):
    """一般warning不是失敗；必須有本次decoder完整讀取／對齊的明確證據。"""
    if (not isinstance(text, dict) or text.get('profile') != _VISIBLE_PROFILE
            or text.get('read_valid') is not True or text.get('alignment_verified') is not True
            or type(text.get('window_visible')) is not bool or text.get('read_error') is not None):
        return None
    cells = text.get('cells')
    if (not isinstance(cells, (list, tuple)) or len(cells) != 18
            or any(not isinstance(row, (str, list, tuple)) or len(row) != 20
                   or any(not isinstance(c, str) or len(c) != 1 for c in row) for row in cells)):
        return None
    return [''.join(row).upper() for row in cells]


def _observe_fixed_damage(text, battle_state):
    """只記本場完整可見敵方龍怒；不讀敵招RAM、不由HP差值推測招式。"""
    global _fixed_damage_risk
    from .team_strategy import species_key, reference, normalize
    enemy = species_key(battle_state.get('opponent_species'))
    if battle_state.get('active') is not True or battle_state.get('kind') != 'trainer' or enemy is None:
        _clear_fixed_damage_risk()
        return False
    if _fixed_damage_risk and _fixed_damage_risk['enemy_species'] != enemy:
        _clear_fixed_damage_risk()
    rows = _fixed_damage_rows(text)
    if rows is None:
        return False
    lower = ' '.join(row.strip() for row in rows[12:]).strip()
    fainted = re.fullmatch(r'ENEMY\s+(.+?)\s+FAINTED!\s*(?:▼\s*)?', lower)
    replacement = re.fullmatch(r'WILL\s+KEVIN\s+CHANGE\s+POK[ÉE]MON\?\s*(?:▼\s*)?', lower)
    if replacement or fainted and normalize(fainted[1]) == normalize(enemy):
        _clear_fixed_damage_risk()
        return False
    visible = [key for key in reference()['species']
               if normalize(key) in {normalize(row.strip()) for row in rows[:4]}]
    match = re.fullmatch(r'ENEMY\s+(.+?)\s+USED\s+DRAGON\s+RAGE!\s*(?:▼\s*)?', lower)
    if (visible != [enemy] or match is None or normalize(match[1]) != normalize(enemy)
            or any(c in ''.join(rows) for c in ('▶', '▷'))):
        return False
    _fixed_damage_risk = {'enemy_species': enemy, 'move': 'DRAGON_RAGE', 'move_id': 82,
                          'damage': 40, 'source_commit': FIXED_DAMAGE_SOURCE_COMMIT, 'unreadable_waits': 0}
    return True


def _fixed_damage_review(reason):
    return {'phase': 'strategy_review', 'objective': 'Wait.', 'available_actions': ['wait'],
            'review_reason': reason, 'observed_fixed_damage': dict(_fixed_damage_risk or {})}


def _fixed_damage_mon_valid(mon):
    from .team_strategy import species_key, move_key
    return (isinstance(mon, dict) and species_key(mon.get('species')) is not None
            and type(mon.get('level')) is int and 1 <= mon['level'] <= 100
            and type(mon.get('hp')) is int and type(mon.get('max_hp')) is int
            and 0 <= mon['hp'] <= mon['max_hp'] <= 999 and mon['max_hp'] > 0
            and isinstance(mon.get('moves'), (list, tuple)) and len(mon['moves']) == 4
            and isinstance(mon.get('pp'), (list, tuple)) and len(mon['pp']) == 4
            and all(type(move) is int and (move == 0 or move_key(move) is not None)
                    and type(pp) is int and 0 <= pp <= 255 and (move != 0 or pp == 0)
                    for move, pp in zip(mon['moves'], mon['pp'])))


def _fixed_damage_support(mon, enemy):
    from .team_strategy import effective_power
    return (_fixed_damage_mon_valid(mon) and mon['hp'] > 40 + (mon['max_hp'] + 9) // 10
            and mon['hp'] * 2 > mon['max_hp']
            and any(pp & 63 and effective_power(move, mon['species'], enemy) > 0
                    for move, pp in zip(mon['moves'], mon['pp'])))


def _fixed_damage_command(text, rows, party, matches, enemy, health, fight, item, run):
    """只在完整command頁提出既有PKMN換人，不在招式／文字動畫頁猜按鍵。"""
    global _no_pp_switch
    from .team_strategy import effective_power, species_key, normalize, reference
    if not _fixed_damage_risk:
        return None
    if (_fixed_damage_rows(text) is None or enemy != _fixed_damage_risk['enemy_species']
            or len(matches) != 1 or len(health) != 1 or not isinstance(party, (list, tuple))
            or not 1 <= len(party) <= 6 or not all(_fixed_damage_mon_valid(m) for m in party)):
        return _fixed_damage_review('fixed_damage_active_hp_or_party_not_verified')
    active = matches[0]
    visible_enemies = [key for key in reference()['species']
                       if normalize(key) in {normalize(row.strip()) for row in rows[:4]}]
    cursors = [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == '▶']
    if (visible_enemies != [enemy] or fight != (10, 14) or item != (10, 16) or run != (16, 16)
            or len(cursors) != 1 or cursors[0] not in {(9,14), (15,14), (9,16), (15,16)}
            or any('▷' in row for row in rows)
            or health[0] != {'hp': active['hp'], 'max_hp': active['max_hp']} or active['hp'] <= 0):
        return _fixed_damage_review('fixed_damage_command_or_hud_not_verified')
    threshold = 40 + (active['max_hp'] + 9) // 10
    if active['hp'] > threshold:
        return None
    supports = [m for m in party if species_key(m['species']) != species_key(active['species'])
                and _fixed_damage_support(m, enemy)]
    if not supports:
        return _fixed_damage_review('fixed_damage_no_safe_attacking_support')
    def score(mon):
        return max((effective_power(move, mon['species'], enemy) for move, pp in zip(mon['moves'], mon['pp'])
                    if pp & 63), default=0) * mon['level']
    target = max(supports, key=score)
    if sum(m['species'] == target['species'] for m in party) != 1:
        return _fixed_damage_review('fixed_damage_support_species_ambiguous')
    _no_pp_switch = {'species': target['species'], 'reason': 'observed_dragon_rage_risk',
                     'enemy_species': enemy}
    result = _selection_hint(rows, (16, 14), 'command')
    result.update(battle_tactic='switch_observed_fixed_damage', party_target_species=target['species'],
                  enemy_species=enemy, fixed_damage_hp_threshold=threshold,
                  observed_fixed_damage=dict(_fixed_damage_risk))
    return result


def _fixed_damage_moves(text, rows, party, matches, enemy, health):
    """漏看command而已在招式頁：低血只B返回，不在此頁直接換人或攻擊。"""
    if not _fixed_damage_risk:
        return None
    from .team_strategy import normalize, move_key, reference
    # 對話的「 used PECK!」也可能從第6欄開始招名，必須保留左側空白版面，
    # 不能只去標點後把完整攻擊文字當作招式選單。
    lower = {normalize(row[6:].strip()) for row in rows[13:17]
             if not row[:5].strip() and row[5] in {' ', '▶', '▷'}}
    known_moves = {normalize(key.removesuffix('_M')) for key in reference()['moves']}
    if not (lower & known_moves or any('▶' in row for row in rows[13:17])):
        return None
    if (_fixed_damage_rows(text) is None or len(matches) != 1 or len(health) != 1
            or enemy != _fixed_damage_risk['enemy_species']
            or not isinstance(party, (list, tuple)) or not all(_fixed_damage_mon_valid(m) for m in party)):
        return _fixed_damage_review('fixed_damage_moves_hp_or_party_not_verified')
    active = matches[0]
    cursors = [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == '▶']
    visible_enemies = [key for key in reference()['species']
                       if normalize(key) in {normalize(row.strip()) for row in rows[:4]}]
    if (visible_enemies != [enemy] or health[0] != {'hp':active['hp'], 'max_hp':active['max_hp']}
            or active['hp'] <= 0 or len(cursors) != 1 or cursors[0] not in {(5,y) for y in range(13,17)}
            or any('▷' in row for row in rows)
            or any(not move or normalize(rows[13+i][6:].strip()) != normalize(move_key(move).removesuffix('_M'))
                   for i,move in enumerate(active['moves']))):
        return _fixed_damage_review('fixed_damage_moves_layout_or_hud_not_verified')
    threshold = 40 + (active['max_hp'] + 9) // 10
    if active['hp'] > threshold:
        return None
    return {'phase':'battle_menu','objective':'Cancel and return to the battle command menu.',
            'available_actions':['b','wait'],'battle_tactic':'return_for_fixed_damage_switch',
            'fixed_damage_hp_threshold':threshold,'observed_fixed_damage':dict(_fixed_damage_risk)}


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
    transform = ko_transition = None
    battle_frame = getattr(pyboy, 'frame_count', None)
    if raw == 1:
        from pyboy.plugins import game_wrapper_pokemon_gen1_constants as sdk
        from .ditto_transform import read_ditto_transform, read_ditto_ko_transition
        from .team_strategy import reference
        transform = read_ditto_transform(pyboy, observation_frame=battle_frame,
                                         constants=sdk, reference_data=reference())
        ko_transition = read_ditto_ko_transition(pyboy, observation_frame=battle_frame,
                                                constants=sdk, reference_data=reference())
    result = {"raw": raw, "active": raw in (1, 2) if raw in (0, 1, 2, 255) else None,
            "kind": {0: "none", 1: "wild", 2: "trainer", 255: "lost_transition"}.get(raw, "unknown"),
            "wild_opponent_species": opponent if raw==1 else None, "opponent_species":opponent,
            "observation_frame": battle_frame, "ditto_transform": transform,
            "ditto_ko_transition": ko_transition,
            "opponent_source": "https://github.com/pret/pokered/blob/53ae0e93fad9f4c3eaef92f102b1eeb531e59d68/wram.asm#L641",
            "source": SOURCE, "victory_confirmed": None,
            "player_disabled_move": _read_player_disabled_move(pyboy) if raw in {1, 2}
                else {'state': 'not_in_battle', 'valid': True}}
    if raw == 2:
        # 真實唯讀reader明確啟用；legacy合成呼叫不帶此欄仍維持原政策。
        # 此marker不是UI／HP／敵人證據，battle_context仍須逐項驗證。
        result['trainer_half_hp_profile'] = TRAINER_HALF_HP_PROFILE
    return result


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


def _ditto_ko_context(text, battle_state, party):
    """只准已驗證0HP百變怪的正常收尾；舊攻擊頁絕不送A。"""
    signal = battle_state.get('ditto_ko_transition')
    if not isinstance(signal, dict) or signal.get('read_valid') is not True:
        return None
    from .team_strategy import reference, species_key, move_key
    from .ditto_transform import verified_ko_transition
    def review():
        return {'phase': 'strategy_review', 'objective': 'Wait.', 'available_actions': ['wait'],
                'review_reason': 'ditto_ko_transition_ui_not_verified'}
    if (type(battle_state.get('raw')) is not int or battle_state['raw'] != 1
            or battle_state.get('kind') != 'wild' or battle_state.get('active') is not True
            or not verified_ko_transition(signal, ram_enemy=battle_state.get('opponent_species'), party=party,
                observation_frame=battle_state.get('observation_frame'), reference_data=reference())):
        return review()
    rows = _fixed_damage_rows(text)
    if rows is None or any(marker in ''.join(rows) for marker in ('▶', '▷')):
        return review()
    upper_names = [row.strip() for row in rows[:4] if row.strip() in reference()['species']]
    if upper_names not in ([], ['DITTO']):
        return review()
    allowed_upper = {'DITTO', 'SLP', 'PSN', 'BRN', 'FRZ', 'PAR', 'ATTACK', 'DEFENSE', 'SPEED', 'SPECIAL'}
    allowed_upper.update(species_key(mon['species']) for mon in party)
    if (any(word not in allowed_upper for word in re.findall(r'[A-Z_]+', ' '.join(rows[:12])))
            or re.search(r'[^A-Z0-9_ /]', ''.join(rows[:12]))):
        return review()
    lower = ' '.join(' '.join(rows[12:]).split())
    markers = lower.count('▼')
    if markers > 1 or '▼' in ''.join(rows[:12]) or markers and not lower.endswith('▼'):
        return review()
    lower = lower.removesuffix('▼').strip()
    first = species_key(party[0]['species'])
    if not first:
        return review()
    member_names=[species_key(mon['species']) for mon in party]
    growth=[f"{species_key(mon['species'])} GREW TO LEVEL {mon['level']}!"
            for mon in party if type(mon.get('level')) is int]
    learned=[]
    ref=reference()
    for mon in party:
        name=species_key(mon['species']);species=ref['species'].get(name,{})
        for entry in species.get('level_moves',[]):
            move=ref['moves'].get(entry['move'],{})
            if entry['level']==mon.get('level') and move.get('id') in mon.get('moves',[]):
                slot=mon['moves'].index(move['id'])
                if mon.get('pp',[0]*4)[slot]==move['pp']:
                    learned.append(f"{name} LEARNED {entry['move'].replace('_',' ')}!")
    complete = (lower == 'ENEMY DITTO FAINTED!' or lower in growth+learned
                or any(re.fullmatch(re.escape(name)+r' GAINED [1-9][0-9]{0,3} EXP\. POINTS!',lower)
                       for name in member_names))
    details = {'ditto_ko_stage': 'enemy_zero_hp_faint_transition', 'battle_tactic': 'wait_ditto_faint_transition'}
    if complete:
        return {'phase': 'battle_dialogue', 'objective': 'Confirm the current selection.',
                'available_actions': ['a', 'wait'], **details}
    if markers:
        return review()
    # 正常逐字／空白動畫只等待；未核實的攻擊文字不視作收據。
    known = ['ENEMY DITTO FAINTED!', *growth, *learned]
    if upper_names == ['DITTO']:
        active_names = [row.strip() for row in rows[6:10] if row.strip() in reference()['species']]
        active = [mon for mon in party if species_key(mon['species']) in active_names]
        if len(active) == 1:
            name = species_key(active[0]['species'])
            known.extend(f"{name} USED {move_key(move).replace('_', ' ')}!"
                         for move in active[0].get('moves', []) if move_key(move))
    partial_exp=False
    for name in member_names:
        exp_prefix=f'{name} GAINED'
        partial_exp=partial_exp or exp_prefix.startswith(lower)
        if lower.startswith(exp_prefix+' '):
            match=re.fullmatch(r'([1-9][0-9]{0,3})(?: (.*))?',lower[len(exp_prefix)+1:])
            partial_exp=partial_exp or bool(match and 'EXP. POINTS!'.startswith(match[2] or ''))
    if not lower or any(message.startswith(lower) for message in known) or partial_exp:
        return {'phase': 'battle_animation', 'objective': 'Wait.', 'available_actions': ['wait'], **details}
    return review()


def battle_context(text, battle_state, party=(), inventory=None, *, capture_focus=False) -> dict | None:
    """僅對已核對 ROM 的實驗性路線提供局部提示；不執行按鍵。"""
    global _no_pp_switch
    half_opted = 'trainer_half_hp_profile' in battle_state
    if half_opted and (battle_state.get('trainer_half_hp_profile') != TRAINER_HALF_HP_PROFILE
                      or type(battle_state.get('raw')) is not int or battle_state['raw'] != 2
                      or battle_state.get('active') is not True or battle_state.get('kind') != 'trainer'):
        return _trainer_half_review('reader_contract_unverified')
    if half_opted and not isinstance(text,dict):return _trainer_half_review('text_packet_unverified')
    observed_fixed_move = _observe_fixed_damage(text, battle_state)
    if battle_state.get("kind")=="lost_transition":
        return {"phase":"strategy_review","objective":"Wait.","available_actions":["wait","b"],"review_reason":"battle_loss_requires_review","battle_loss_confirmed":True,"phase_source":"read-only wIsInBattle LOST_BATTLE=255; save and review before continuing"}
    if battle_state["active"] is not True:
        _no_pp_switch=None
        return None
    ko_context = _ditto_ko_context(text, battle_state, party)
    if ko_context is not None:
        return ko_context
    signal = battle_state.get('player_disabled_move')
    party, disabled_error = _disabled_policy_party(party, signal)
    if disabled_error:
        return {'phase': 'strategy_review', 'objective': 'Wait.', 'available_actions': ['wait'],
                'review_reason': disabled_error, 'player_disabled_move': signal}
    if _fixed_damage_risk:
        if _fixed_damage_rows(text) is None:
            _fixed_damage_risk['unreadable_waits'] += 1
            if _fixed_damage_risk['unreadable_waits'] > 30:
                return _fixed_damage_review('fixed_damage_visible_wait_exhausted')
            return {'phase': 'battle_animation', 'objective': 'Wait.', 'available_actions': ['wait'],
                    'battle_tactic': 'wait_verified_fixed_damage_ui',
                    'observed_fixed_damage': dict(_fixed_damage_risk)}
        _fixed_damage_risk['unreadable_waits'] = 0
    if observed_fixed_move:
        if _no_pp_switch and _no_pp_switch.get('reason') == _TRAINER_HALF_REASON:
            _no_pp_switch=None  # 已觀測固定40傷害的原有保護優先接管。
        return {'phase': 'battle_dialogue', 'objective': 'Confirm the current selection.',
                'available_actions': ['a', 'wait'], 'battle_tactic': 'observe_enemy_dragon_rage',
                'observed_fixed_damage': dict(_fixed_damage_risk)}
    if _no_pp_switch and _no_pp_switch.get('reason') == _TRAINER_HALF_REASON:
        if not half_opted:
            return _trainer_half_review('pending_reader_contract_missing')
        pending = _trainer_half_pending(text,battle_state,party)
        if pending is not None:
            return pending
    cells = text.get("cells", [])
    if half_opted and (not isinstance(cells,(list,tuple)) or len(cells)!=18
                      or any(not isinstance(row,(str,list,tuple)) or len(row)!=20 for row in cells)):
        return _trainer_half_review('text_cells_unverified')
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
        half_command = _trainer_half_command(text,rows,party,health) if half_opted and not _fixed_damage_risk else None
        if half_command and 'review_reason' in half_command:
            return half_command
        if half_command:
            from .team_strategy import species_key
            if species_key(battle_state.get('opponent_species')) != half_command['enemy']:
                return _trainer_half_review('actual_enemy_unverified')
        from .team_strategy import reference, normalize, species_key, move_key, choose_damage_move, capture_plan
        names = reference()["species"]
        party_form = len(party)>1 and all(species_key(mon["species"]) and any(normalize(species_key(mon["species"])) in normalize(row) for row in rows[:12]) for mon in party)
        enemy_rows = [] if party_form else [normalize(row.strip()) for row in rows[:4]]
        enemy_matches = [key for key in names if normalize(key) in enemy_rows]
        enemy = next(iter(enemy_matches), None)
        ram_enemy = battle_state.get("opponent_species") or battle_state.get("wild_opponent_species")
        if enemy and ram_enemy and enemy != ram_enemy:
            from .ditto_transform import verified_effective_enemy
            transformed = (verified_effective_enemy(battle_state.get('ditto_transform'),
                visible_enemy=enemy, ram_enemy=ram_enemy, party=party,
                observation_frame=battle_state.get('observation_frame'), reference_data=reference())
                if type(battle_state.get('raw')) is int and battle_state.get('raw') == 1
                and battle_state.get('kind') == 'wild' and battle_state.get('active') is True
                and len(enemy_matches) == 1
                and (text.get('profile') == _VISIBLE_PROFILE and text.get('read_valid') is True
                    and text.get('alignment_verified') is True and text.get('read_error') is None
                    and type(text.get('window_visible')) is bool) else None)
            if transformed is None:
                return {"phase": "strategy_review", "review_reason": "visible_enemy_and_wild_opponent_signal_disagree"}
            enemy = transformed
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
                if _no_pp_switch.get('reason') == 'observed_dragon_rage_risk':
                    return _fixed_damage_review('fixed_damage_switch_rejected')
                return {'phase':'strategy_review','review_reason':'no_pp_switch_rejected'}
            if _no_pp_switch.get('reason') == 'observed_dragon_rage_risk':
                candidates = [m for m in party if m.get('species') == _no_pp_switch['species']]
                if (not _fixed_damage_risk or _no_pp_switch.get('enemy_species') != enemy
                        or len(candidates) != 1 or not _fixed_damage_support(candidates[0], enemy)):
                    return _fixed_damage_review('fixed_damage_pending_support_not_verified')
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
        if _fixed_damage_risk and any((fight, item, run)) and not all((fight, item, run)):
            return _fixed_damage_review('fixed_damage_command_not_complete')
        if fight and item and run:
            if resisted_retreat:
                result = _selection_hint(rows, run, 'command')
                result.update(battle_tactic='retreat', **resisted_retreat)
                return result
            risk_context = _fixed_damage_command(text, rows, party, matches, enemy, health, fight, item, run)
            if risk_context:
                return risk_context
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
            if half_command:
                current=half_command['active']
                supports=[mon for mon in party if mon['species']!=current['species']
                          and _trainer_half_support(mon,enemy)
                          and _trainer_half_score(mon,enemy)>=_trainer_half_score(current,enemy)*.75]
                target=max(supports,key=lambda mon:_trainer_half_score(mon,enemy),default=None)
                if target is None:return _trainer_half_review('no_healthy_attacking_support')
                _no_pp_switch={'species':target['species'],'reason':_TRAINER_HALF_REASON,
                               'enemy_species':enemy,'active_species':current['species'],
                               'party_species':tuple(mon['species'] for mon in party)}
                result=_selection_hint(rows,(16,14),'command')
                if result['objective']=='Confirm the current selection.':
                    _no_pp_switch['party_open_requested']=True
                return {**result,'battle_tactic':'switch_trainer_half_hp',
                        'party_target_species':target['species'],'enemy_species':enemy}
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
        risk_moves = _fixed_damage_moves(text, rows, party, matches, enemy, health)
        if risk_moves:
            return risk_moves
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
    if _fixed_damage_risk:
        _fixed_damage_risk['unknown_ui_waits'] = _fixed_damage_risk.get('unknown_ui_waits', 0) + 1
        if _fixed_damage_risk['unknown_ui_waits'] > 30:
            return _fixed_damage_review('fixed_damage_unrecognized_ui_wait_exhausted')
        return {'phase': 'battle_animation', 'objective': 'Wait.', 'available_actions': ['wait'],
                'battle_tactic': 'wait_recognized_fixed_damage_ui',
                'observed_fixed_damage': dict(_fixed_damage_risk)}
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
