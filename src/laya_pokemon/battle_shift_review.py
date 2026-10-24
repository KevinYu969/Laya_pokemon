"""來源限定的 Gen1 免費換人候選；不讀 RAM、不按鍵、不改共同戰鬥策略。

API: BattleShiftReview.context(text, battle_state, progress, *, frame, now,
previous=()). previous[-1] 必須由 caller 的實際動作帳提供
{'frame': <動作前frame>, 'action': <真正選出的按鍵>}，不能填候選動作。
同一 controller 跨工程 pause/reload 保留；不可每幀重建。

None 只表示不適用（非訓練家／未進本流程）、已確認真正 B 保留現役，
或已在完整目標 command 驗證正常換人。已辨識的 partial/未知換人頁不
回落 generic A。caller 的 loss/review/capture 與既有 pending 必須先處理。

固定 a536711: core.asm 1310–1445，blob 7a5d617dc5ed080623bfb189f81d254c83ef4cc3；
text_2.asm 912–930/1275–1317/1361–1380，blob 917feb8953c9c2b688395dfb54459b1d04bf7a71；
party_menu.asm，blob 2a3086424d217093bcd8aa7100d4326f99894d2f；
text_box.asm 207–348，blob b8add148dc8cb44d4cedea42361f6a229796fed0。
SHIFT YES 直接 BATTLE_PARTY_MENU；沒有 SWITCH/STATS/CANCEL 子選單。
評分只用既有第一世代威力/屬性/PP與等級；不推定敵招、實際速度或急所。
"""
from copy import deepcopy
from math import isfinite
import re

from .observation import PROFILE
from .party_control import command
from .team_strategy import effective_power, move_key, normalize, reference, species_key

PROGRESS_PROFILE = 'gen1-wrapper-ram-progress-v1-unvalidated'
COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
_WORD = re.compile(r'[A-Za-z0-9]{2,}')


def _integer(x):
    return type(x) is int


def _party_valid(party):
    return (isinstance(party, (list, tuple)) and 1 <= len(party) <= 6
            and all(isinstance(m, dict) and species_key(m.get('species'))
                    and all(_integer(m.get(k)) for k in ('level', 'hp', 'max_hp', 'status'))
                    and 1 <= m['level'] <= 100 and 0 <= m['hp'] <= m['max_hp'] <= 999
                    and m['max_hp'] > 0 and m['status'] in {*range(8), 8, 16, 32, 64}
                    and isinstance(m.get('moves'), (list, tuple)) and len(m['moves']) == 4
                    and isinstance(m.get('pp'), (list, tuple)) and len(m['pp']) == 4
                    and all(_integer(move) and _integer(pp) and 0 <= pp <= 255
                            and (move_key(move) is not None if move else pp == 0)
                            for move, pp in zip(m['moves'], m['pp'])) for m in party)
            and len({m['species'] for m in party}) == len(party))


def _score(mon, enemy):
    return max((effective_power(move, mon['species'], enemy) * mon['level']
                for move, pp in zip(mon['moves'], mon['pp']) if pp & 63), default=0)


def _exposure(mon, enemy):
    """敵方各 STAB 屬性的最差倍率；不是猜測它已持有哪一招。"""
    ref = reference()
    factors = []
    for attack_type in ref['species'][enemy]['types']:
        factor = 1
        for defense_type in ref['species'][species_key(mon['species'])]['types']:
            factor *= next((v for a, b, v in ref['type_matchups']
                            if a == attack_type and b == defense_type), 1)
        factors.append(factor)
    return max(factors)


def shift_plan(party, active_index, next_enemy):
    """純策略：高風險且無可核替補就 review，低風險保留現役。"""
    if reference().get('source_commit') != COMMIT:
        return {'decision': 'review', 'reason': 'gen1_reference_contract_unverified'}
    if not _party_valid(party) or not _integer(active_index) or not 0 <= active_index < len(party):
        return {'decision': 'review', 'reason': 'party_or_active_unknown'}
    current = party[active_index]
    if not current['hp']:
        return {'decision': 'review', 'reason': 'active_fainted_not_shift_offer'}
    enemy = species_key(next_enemy)
    risky = current['status'] != 0 or current['hp'] * 3 <= current['max_hp'] * 2
    risky = risky or _score(current, None) == 0
    risky = risky or enemy is not None and _score(current, enemy) == 0
    if not risky:
        return {'decision': 'keep', 'reason': 'active_healthy_no_forced_switch'}
    if enemy is None:
        return {'decision': 'review', 'reason': 'risky_active_next_enemy_unverified'}
    current_score = _score(current, enemy)
    candidates = []
    for i, mon in enumerate(party):
        if (i == active_index or mon['status'] != 0 or mon['hp'] * 3 <= mon['max_hp'] * 2
                or mon['level'] * 4 < current['level'] * 3
                or _exposure(mon, enemy) > min(1, _exposure(current, enemy))):
            continue
        score = max((effective_power(move, mon['species'], enemy) * mon['level']
                     for move, pp in zip(mon['moves'], mon['pp']) if pp & 63 >= 3), default=0)
        if score > 0 and score >= current_score * .75:
            candidates.append((score, mon['hp'] / mon['max_hp'], -i, i))
    if not candidates:
        return {'decision': 'review', 'reason': 'risky_active_no_verified_healthy_support'}
    target = max(candidates)[-1]
    return {'decision': 'switch', 'reason': 'status_or_attrition_free_shift',
            'target_index': target, 'target_species': party[target]['species'], 'next_enemy': enemy,
            'heuristic_only': True, 'source_commit': COMMIT}


def _rows(text):
    if (not isinstance(text, dict) or text.get('profile') != PROFILE
            or text.get('read_valid') is not True or text.get('alignment_verified') is not True
            or 'read_error' not in text or text['read_error'] is not None
            or text.get('window_visible') is not False):
        return None
    cells = text.get('cells')
    if (not isinstance(cells, (list, tuple)) or len(cells) != 18
            or any(not isinstance(row, (str, list, tuple)) or len(row) != 20
                   or any(not isinstance(c, str) or len(c) != 1 for c in row) for row in cells)):
        return None
    raw = [''.join(row) for row in cells]
    selected = [(y, row.rstrip()) for y, row in enumerate(raw) if _WORD.search(row)][:12]
    if text.get('lines') != [row for _, row in selected] or text.get('line_rows') != [y for y, _ in selected]:
        return None
    return [row.upper() for row in raw]


def _put(rows, x, y, value):
    rows[y] = rows[y][:x] + value + rows[y][x + len(value):]


def _hud(mon):
    rows = [' ' * 20 for _ in range(18)]
    _put(rows, 10, 7, species_key(mon['species']))
    status = 'SLP' if 0 < mon['status'] < 8 else {0: f"{mon['level']:3}", 8: 'PSN', 16: 'BRN', 32: 'FRZ', 64: 'PAR'}[mon['status']]
    _put(rows, 15, 8, status)
    _put(rows, 11, 10, f"{mon['hp']:3}/{mon['max_hp']:3}")
    return rows


def _party_page(party, cursor, *, inactive=False):
    rows = [' ' * 20 for _ in range(18)]
    for i, mon in enumerate(party):
        _put(rows, 3, i * 2, species_key(mon['species']))
        _put(rows, 13 if mon['level'] == 100 else 14, i * 2, str(mon['level']))
        status = 'FNT' if mon['hp'] == 0 else 'SLP' if 0 < mon['status'] < 8 else {0: '', 8: 'PSN', 16: 'BRN', 32: 'FRZ', 64: 'PAR'}[mon['status']]
        _put(rows, 17, i * 2, status)
        _put(rows, 13, i * 2 + 1, f"{mon['hp']:3}/{mon['max_hp']:3}")
    _put(rows, 0, cursor * 2 + 1, '▷' if inactive else '▶')
    _put(rows, 1, 14, 'BRING OUT WHICH')
    _put(rows, 1, 16, 'POKÉMON?')
    return rows


class BattleShiftReview:
    """候選單次原生 SHIFT；保留同一物件，未知 sticky review。"""
    def __init__(self):
        self.stage = 'idle'
        self.error = None
        self.enemy = None
        self.trainer = None
        self.party = None
        self.active = None
        self.target = None
        self.started = None
        self.last_now = None
        self.last_frame = None
        self.last_packet = None
        self.candidate = None
        self.nav_expected = None
        self.yes_up_sent = False
        self.waits = 0
        self.calls = 0
        self.last_completed = None

    def _review(self, reason):
        self.error = self.error or reason
        return {'phase': 'strategy_review', 'objective': 'Wait.', 'available_actions': ['wait'],
                'review_reason': 'battle_shift_' + self.error}

    def _wait(self, reason):
        self.waits += 1
        if self.waits > 25:
            return self._review('wait_budget_exhausted')
        return {'phase': 'battle_animation', 'objective': 'Wait.', 'available_actions': ['wait'],
                'battle_tactic': 'wait_free_shift_' + reason}

    def _offer(self, action, frame, kind, *, cursor=None):
        self.candidate = {'frame': frame, 'action': action, 'kind': kind, 'cursor': cursor}
        return command(action, 'battle_menu', {'battle_tactic': 'free_shift_' + kind,
                       'party_target_species': self.party[self.target]['species'] if self.target is not None else None})

    def context(self, text, battle_state, progress, *, frame, now, previous=()):
        if self.error:
            return self._review(self.error)
        trainer = (isinstance(battle_state, dict) and type(battle_state.get('raw')) is int
                   and battle_state['raw'] == 2 and battle_state.get('active') is True
                   and battle_state.get('kind') == 'trainer')
        if not trainer:
            if self.stage != 'idle':
                return self._review('battle_ended_before_shift_verified')
            return None
        rows = _rows(text)
        words = normalize(' '.join(text.get('lines', []))) if isinstance(text, dict) else ''
        relevant = (self.stage != 'idle' or self.candidate is not None
                    or 'ABOUTTOUSE' in words or 'CHANGEPOKEMON' in words or 'WILLKEVIN' in words)
        if not relevant:
            return None
        if rows is None:
            return self._review('decoder_unverified')
        if (not _integer(frame) or frame < 0 or battle_state.get('observation_frame') != frame
                or type(battle_state.get('observation_frame')) is not int
                or type(now) not in (int, float) or not isfinite(now) or now < 0
                or self.last_now is not None and now < self.last_now):
            return self._review('frame_or_clock_unverified')
        if (not isinstance(progress, dict) or progress.get('profile') != PROGRESS_PROFILE
                or progress.get('initialization_candidate') is not True
                or progress.get('party_read_valid') is not True
                or not _party_valid(progress.get('party'))
                or type(progress.get('party_count')) is not int
                or progress['party_count'] != len(progress['party'])):
            return self._review('progress_unverified')
        if any('observation_frame' in packet and
               (type(packet['observation_frame']) is not int or packet['observation_frame'] != frame)
               for packet in (text, progress)):
            return self._review('explicit_observation_frame_disagrees')
        party = progress['party']
        packet = deepcopy((text, battle_state, progress))
        if self.last_frame is not None:
            if frame < self.last_frame:
                return self._review('frame_regressed')
            if frame == self.last_frame:
                return self._wait('same_frame') if packet == self.last_packet else self._review('same_frame_conflict')
        self.last_frame, self.last_packet, self.last_now = frame, packet, now
        self.calls += 1
        if self.started is None:
            self.started = now
        if now - self.started > 60 or self.calls > 80:
            return self._review('time_or_call_budget_exhausted')
        if self.party is not None and party != self.party:
            return self._review('party_fingerprint_changed')
        if self.enemy is not None and species_key(battle_state.get('opponent_species')) != self.enemy:
            return self._review('bound_next_enemy_changed')
        if self.candidate:
            candidate = self.candidate
            last = previous[-1] if isinstance(previous, (list, tuple)) and previous else None
            if (not isinstance(last, dict) or type(last.get('frame')) is not int
                    or last['frame'] != candidate['frame'] or last.get('action') not in (candidate['action'], 'wait')):
                return self._review('actual_action_receipt_missing_or_conflicting')
            self.candidate = None
            if last['action'] != 'wait':
                kind = candidate['kind']
                if kind == 'preface': self.stage = 'species'
                elif kind == 'next_species': self.stage = 'offer'
                elif kind == 'keep':
                    completed = {'decision': 'keep', 'frame': frame}
                    self.__init__()
                    self.last_completed = completed
                    return None
                elif kind == 'yes': self.stage = 'party'
                elif kind == 'yes_navigation': self.yes_up_sent = True
                elif kind == 'select_member': self.stage = 'handoff'
                elif kind == 'party_navigation':
                    self.nav_expected = candidate['cursor'] + (1 if candidate['action'] == 'down' else -1)
        # 唯一當前 HUD 與實際隊伍一致；不拿 party[0] 當作必然在場。
        matches = [i for i, mon in enumerate(party) if rows[7] == _hud(mon)[7]]
        if self.active is None:
            if len(matches) != 1:
                return self._review('active_hud_ambiguous')
            self.active = matches[0]
            self.party = deepcopy(party)
        base = _hud(party[self.active])
        # 原生來源前言／下一敵物種頁；兩頁各自必須真正 ▼ 才發 A。
        preface = rows[14][1:].strip()
        if self.stage in ('idle', 'species') and re.fullmatch(r'[A-Z. ]+ IS', preface):
            expected = base.copy(); expected[14] = rows[14]
            _put(expected, 1, 16, 'ABOUT TO USE'); _put(expected, 18, 16, '▼')
            if rows == expected:
                if self.stage == 'species': return self._wait('old_preface')
                self.trainer = preface[:-3]
                return self._offer('a', frame, 'preface')
            expected[16] = expected[16][:18] + '  '
            if rows == expected:
                return self._wait('preface_arrow_blink')
        if self.stage in ('idle', 'species', 'offer') and rows[14] == ' ABOUT TO USE'.ljust(20):
            tail = rows[16][1:18].strip()
            name = tail[:-1] if tail.endswith('!') else ''
            enemy = species_key(name)
            expected = base.copy(); expected[14] = rows[14]; expected[16] = rows[16]
            if rows != expected or rows[16][0] != ' ' or rows[16][19] != ' ':
                return self._review('next_species_layout_unverified')
            if enemy and rows[16][18] == '▼':
                if species_key(battle_state.get('opponent_species')) != enemy:
                    return self._review('next_species_ram_disagrees')
                if self.stage == 'offer': return self._wait('old_species')
                self.enemy = enemy
                return self._offer('a', frame, 'next_species')
            if rows[16][18] not in (' ', '▼') or any(c in ''.join(rows) for c in ('▶', '▷')):
                return self._review('next_species_marker_unverified')
            candidates = [normalize(k) + '!' for k in reference()['species']]
            partial = normalize(tail) + ('!' if tail.endswith('!') else '')
            if not partial or any(k.startswith(partial) for k in candidates):
                return self._wait('next_species_typing_or_blink')
            return self._review('next_species_unknown')
        if self.stage in ('idle', 'offer'):
            for cursor in (8, 10):
                expected = base.copy()
                _put(expected, 2, 8, 'YES'); _put(expected, 2, 10, 'NO'); _put(expected, 1, cursor, '▶')
                _put(expected, 1, 14, 'WILL KEVIN'); _put(expected, 1, 16, 'CHANGE POKÉMON?')
                if rows == expected:
                    if self.enemy and species_key(battle_state.get('opponent_species')) != self.enemy:
                        return self._review('offer_enemy_changed')
                    plan = shift_plan(party, self.active, self.enemy)
                    if plan['decision'] == 'review': return self._review(plan['reason'])
                    if plan['decision'] == 'keep': return self._offer('b', frame, 'keep')
                    self.target = plan['target_index']
                    if cursor == 10 and self.yes_up_sent:
                        return self._wait('yes_cursor_settling')
                    if cursor == 8: self.yes_up_sent = False
                    return self._offer('a' if cursor == 8 else 'up', frame, 'yes' if cursor == 8 else 'yes_navigation')
        if self.stage == 'party':
            for cursor in range(len(party)):
                if rows == _party_page(party, cursor, inactive=True):
                    return self._wait('inactive_party_cursor')
                if rows != _party_page(party, cursor): continue
                if self.nav_expected is not None:
                    if cursor != self.nav_expected: return self._wait('party_cursor_settling')
                    self.nav_expected = None
                action = 'a' if cursor == self.target else 'down' if cursor < self.target else 'up'
                return self._offer(action, frame, 'select_member' if action == 'a' else 'party_navigation', cursor=cursor)
            # 已確認 YES 後仍停留原題只等；不得重送 A 或改成普通 SWITCH。
            if 'WILLKEVINCHANGEPOKEMON' in normalize(''.join(rows[14:])):
                return self._wait('old_offer_after_yes')
            if not ''.join(rows).strip(): return self._wait('party_drawing')
            return self._review('party_page_unverified')
        if self.stage == 'handoff':
            target = party[self.target]
            expected = _hud(target)
            enemy_name = rows[0][1:].strip()
            if species_key(enemy_name) != self.enemy:
                # 原生自動過場可全空，但不能拿未知敵或菜單交回 generic A。
                if not ''.join(rows).strip(): return self._wait('native_transition')
            else:
                expected[0], expected[1] = rows[0], rows[1]
                valid_level = re.fullmatch(r' {5}[ 0-9]{3} {12}', rows[1]) and rows[1][5:8].strip().isdigit() and 1 <= int(rows[1][5:8]) <= 100
                for x, y, label in ((10, 14, 'FIGHT'), (10, 16, 'ITEM'), (16, 16, 'RUN')):
                    _put(expected, x, y, label)
                for x, y in ((9, 14), (15, 14), (9, 16), (15, 16)):
                    view = expected.copy(); _put(view, x, y, '▶')
                    if valid_level and rows == view:
                        completed = {'decision': 'switch', 'target_species': target['species'], 'enemy': self.enemy, 'frame': frame}
                        self.__init__()
                        self.last_completed = completed
                        return None
            if enemy_name and species_key(enemy_name) != self.enemy:
                return self._review('handoff_enemy_changed')
            if any(c in ''.join(rows) for c in ('▶', '▷', '▼')):
                return self._review('unexpected_handoff_menu_or_prompt')
            lower = ' '.join(' '.join(rows[12:]).split())
            # 所有這些都是 only-WAIT；未知仍停，不替新對手選攻擊。
            messages = [f"{self.trainer} SENT OUT {self.enemy.replace('_', ' ')}!" if self.trainer else '',
                        f"{species_key(party[self.active]['species'])} ENOUGH! COME BACK!",
                        f"{species_key(party[self.active]['species'])} COME BACK!",
                        f"GO! {species_key(target['species'])}!"]
            allowed_upper = (rows[:12] == _hud(party[self.active])[:12]
                             or rows[:12] == _hud(target)[:12])
            upper_without_enemy = rows[:12].copy(); upper_without_enemy[0] = upper_without_enemy[1] = ' ' * 20
            allowed_upper = allowed_upper or upper_without_enemy in (_hud(party[self.active])[:12], _hud(target)[:12])
            if allowed_upper and (not lower or any(m and m.startswith(lower) for m in messages)):
                return self._wait('native_sendout')
            return self._review('handoff_ui_unverified')
        if not ''.join(rows).strip():
            return self._wait('blank_native_transition')
        return self._review('unknown_or_partial_shift_page')
