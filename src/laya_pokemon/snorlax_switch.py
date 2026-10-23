"""Route12 正常戰鬥換人的有界純候選；不讀檔、RAM或執行按鍵。"""
from copy import deepcopy
import math
import re

from .observation import PROFILE as TEXT_PROFILE

SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
ENEMY_PROFILE = 'red-en-sdk-2.8.1-enemy-source-v1-unvalidated'
NAMES = {7: 'NIDOKING', 9: 'IVYSAUR', 154: 'VENUSAUR', 35: 'FEAROW', 102: 'EEVEE'}
_STATUS = {*range(8), 8, 16, 32, 64}
_KEYS = {'species', 'species_name', 'level', 'exp', 'hp', 'max_hp', 'status', 'moves', 'pp'}
_COMMAND = {(9, 14), (15, 14), (9, 16), (15, 16)}
_SOURCES = ['engine/battle/core.asm#L2301', 'home/pokemon.asm#L181',
            'engine/menus/party_menu.asm#L14', 'data/text_boxes.asm#L33',
            'engine/pokemon/status_screen.asm#L7', 'engine/battle/common_text.asm#L97',
            'data/text/text_2.asm#L1275', 'data/text/text_2.asm#L996']
SOURCES = [f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/{p}' for p in _SOURCES]


def _int(value, low, high):
    return type(value) is int and low <= value <= high


def _clock(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _rows(text, frame):
    if (not isinstance(text, dict) or text.get('profile') != TEXT_PROFILE
            or text.get('read_valid') is not True or text.get('alignment_verified') is not True
            or type(text.get('window_visible')) is not bool or text.get('read_error') is not None
            or 'observation_frame' in text and (type(text['observation_frame']) is not int
                                                or text['observation_frame'] != frame)):
        return None
    cells = text.get('cells')
    if (not isinstance(cells, (list, tuple)) or len(cells) != 18
            or any(not isinstance(r, (str, list, tuple)) or len(r) != 20
                   or any(not isinstance(c, str) or len(c) != 1 for c in r) for r in cells)):
        return None
    raw = tuple(''.join(r) for r in cells)
    if 'lines' in text or 'line_rows' in text:
        visible = [(i, r.rstrip()) for i, r in enumerate(raw) if re.search(r'[A-Za-z0-9]{2,}', r)][:12]
        if text.get('lines') != [r for _, r in visible] or text.get('line_rows') != [i for i, _ in visible]:
            return None
    return tuple(r.upper() for r in raw)


def _party(p):
    if (not isinstance(p, dict) or p.get('profile') != 'gen1-wrapper-ram-progress-v1-unvalidated'
            or p.get('party_read_valid') is not True or p.get('initialization_candidate') is not True
            or type(p.get('party_count')) is not int or p['party_count'] != 4
            or not isinstance(p.get('party'), list) or len(p['party']) != 4
            or p.get('player_name_raw') != 'KEVIN'):
        return None
    party = p['party']
    for m in party:
        if (not isinstance(m, dict) or not _KEYS <= set(m)
                or type(m['species']) is not int or m['species'] not in NAMES
                or m['species_name'] != NAMES[m['species']]
                or 'nickname' in m and m['nickname'] != m['species_name']
                or not _int(m['level'], 1, 100) or not _int(m['exp'], 0, 0xFFFFFF)
                or not _int(m['max_hp'], 1, 999) or not _int(m['hp'], 1, m['max_hp'])
                or type(m['status']) is not int or m['status'] not in _STATUS
                or any(not isinstance(m[k], list) or len(m[k]) != 4
                       or any(not _int(v, 0, cap) for v in m[k]) for k, cap in (('moves', 165), ('pp', 255)))
                or not m['moves'][0]
                or any(v == 0 and (m['pp'][i] or any(m['moves'][i + 1:])) for i, v in enumerate(m['moves']))):
            return None
    return party if {m['species'] for m in party} in ({7, 9, 35, 102}, {7, 154, 35, 102}) else None


def _inventory(p):
    inv = p.get('inventory')
    if (not isinstance(inv, list) or len(inv) > 20
            or any(not isinstance(i, dict) or set(i) != {'item', 'quantity'}
                   or not _int(i['item'], 1, 250) or not _int(i['quantity'], 1, 99) for i in inv)):
        return None
    return deepcopy(inv) if len({i['item'] for i in inv}) == len(inv) else None


def _stance(location, frame):
    return (isinstance(location, dict) and all(type(location.get(k)) is int for k in ('map_id', 'x', 'y'))
            and (location['map_id'], location['x'], location['y']) == (23, 10, 61)
            and ('observation_frame' not in location or type(location['observation_frame']) is int
                 and location['observation_frame'] == frame))


def _battle(battle, frame):
    return (isinstance(battle, dict) and type(battle.get('raw')) is int and battle['raw'] == 1
            and battle.get('active') is True and battle.get('kind') == 'wild'
            and all(type(battle.get(k)) is int and battle[k] == 132 or type(battle.get(k)) is str
                    and battle[k] == 'SNORLAX' for k in ('opponent_species', 'wild_opponent_species'))
            and all(k not in battle or type(battle[k]) is int and battle[k] == 30
                    for k in ('level', 'enemy_level', 'opponent_level'))
            and ('observation_frame' not in battle or type(battle['observation_frame']) is int
                 and battle['observation_frame'] == frame))


def _enemy(snapshot, frame):
    if (not isinstance(snapshot, dict) or snapshot.get('profile') != ENEMY_PROFILE
            or snapshot.get('source_commit') != SOURCE_COMMIT or snapshot.get('read_valid') is not True
            or snapshot.get('unknown_reason') is not None or snapshot.get('battle_kind') != 'wild'
            or type(snapshot.get('observation_frame')) is not int or snapshot['observation_frame'] != frame
            or not _stance(snapshot.get('location'), frame)):
        return None
    e = snapshot.get('enemy')
    if (not isinstance(e, dict) or type(e.get('species')) is not int or e['species'] != 132
            or type(e.get('internal_id')) is not int or e['internal_id'] != 132 or e.get('species_name') != 'SNORLAX'
            or type(e.get('level')) is not int or e['level'] != 30
            or not _int(e.get('max_hp'), 136, 145) or not _int(e.get('hp'), 1, e['max_hp'])
            or type(e.get('status')) is not int or e['status'] not in _STATUS):
        return None
    return {k: e[k] for k in ('species', 'level', 'hp', 'max_hp', 'status')}


def _put(cells, x, y, word):
    cells[y][x:x + len(word)] = list(word)


def _marks(rows, char):
    return [(x, y) for y, r in enumerate(rows) for x, c in enumerate(r) if c == char]


def _status(value, level=None):
    return 'SLP' if value & 7 else {8: 'PSN', 16: 'BRN', 32: 'FRZ', 64: 'PAR'}.get(value, '' if level is None else str(level))


def _hud(rows, party, enemy, *, allow_hp_decrease_index=None):
    clean = [list(r) for r in rows[:12]]
    for y, row in enumerate(clean):
        for x, c in enumerate(row):
            if c == '#' and (x < 8 and 5 <= y < 12 or 12 <= x < 19 and y < 7):
                row[x] = ' '
    clean = [''.join(r) for r in clean]
    active = [i for i, m in enumerate(party) if clean[7].strip() == m['species_name']]
    if (len(active) != 1 or clean[0].strip() != 'SNORLAX'
            or clean[1].strip() != _status(enemy['status'], 30)
            or any(clean[y].strip() for y in (2, 3, 4, 5, 6, 9, 11))
            or any(c in ''.join(rows[:12]) for c in '▶▷▼')):
        return None
    i = active[0]; m = party[i]
    hp = re.fullmatch(r'\s*(\d+)\s*/\s*(\d+)\s*', clean[10])
    if hp is None or clean[8].strip() != _status(m['status'], m['level']):
        return None
    observed_hp, observed_max = map(int, hp.groups())
    if ((observed_hp, observed_max) != (m['hp'], m['max_hp'])
            and not (i == allow_hp_decrease_index and observed_max == m['max_hp']
                     and 1 <= observed_hp <= m['hp'])):
        return None
    return i


def _command(rows, party, enemy):
    active = _hud(rows, party, enemy)
    cursor = _marks(rows, '▶')
    if active is None or len(cursor) != 1 or cursor[0] not in _COMMAND or _marks(rows, '▷') or _marks(rows, '▼'):
        return None
    expected = [[' '] * 20 for _ in range(6)]
    for x, y, value in ((10, 2, 'FIGHT'), (10, 4, 'ITEM'), (16, 4, 'RUN')):
        _put(expected, x, y, value)
    # <PK><MN> are non-printable SDK tokens, hence blank in this decoder.
    x, y = cursor[0]; expected[y - 12][x] = '▶'
    return (active, cursor[0]) if rows[12:] == tuple(''.join(r) for r in expected) else None


def _party_view(party, cursor, *, submenu=False, sub_y=12):
    cells = [[' '] * 20 for _ in range(18)]
    for i, m in enumerate(party):
        y = i * 2
        _put(cells, 3, y, m['species_name'])
        _put(cells, 13 if m['level'] == 100 else 14, y, str(m['level']))
        _put(cells, 17, y, _status(m['status']))
        _put(cells, 13, y + 1, f"{m['hp']:3}/{m['max_hp']:3}")
    _put(cells, 1, 14, 'CHOOSE A POKÉMON.')
    cells[cursor * 2 + 1][0] = '▷' if submenu else '▶'
    if submenu:
        for y in range(11, 18):
            cells[y][11:20] = [' '] * 9
        for y, value in ((12, 'SWITCH'), (14, 'STATS'), (16, 'CANCEL')):
            _put(cells, 13, y, value)
        cells[sub_y][12] = '▶'
    return tuple(''.join(r) for r in cells)


def _match(rows, expected):
    if rows == expected:
        return 'full'
    return 'partial' if all(c in (' ', expected[y][x]) for y, r in enumerate(rows) for x, c in enumerate(r)) else 'invalid'


class SnorlaxSwitchController:
    """baseline須為本場完整command的原觀測；context不讀RAM、tick或按鍵。

    baseline keys: frame, now, text, progress, location, battle_state,
    enemy_snapshot。只支援唯一7/35/102及9或154；原順序完全保留。
    caller負責在同執行緒取得coherent觀測，禁止重寫progress來通過。
    """
    def __init__(self, baseline, target_species, *, max_calls=240, max_seconds=60, max_waits=120):
        if (not _int(max_calls, 1, 240) or not _int(max_waits, 1, 240)
                or not _clock(max_seconds) or not 0 < max_seconds <= 60):
            raise ValueError('上限240calls／240waits／60秒，可縮不可擴')
        keys = {'frame', 'now', 'text', 'progress', 'location', 'battle_state', 'enemy_snapshot'}
        if (not isinstance(baseline, dict) or set(baseline) != keys
                or not _int(baseline['frame'], 0, 2**63 - 1) or not _clock(baseline['now'])
                or type(target_species) is not int or target_species not in NAMES):
            raise ValueError('缺明確最後command基線／目標')
        b = deepcopy(baseline); frame = b['frame']; p = _party(b['progress'])
        rows = _rows(b['text'], frame); enemy = _enemy(b['enemy_snapshot'], frame)
        inv = _inventory(b['progress']) if isinstance(b['progress'], dict) else None
        if (p is None or rows is None or enemy is None or inv is None
                or not _stance(b['location'], frame) or not _battle(b['battle_state'], frame)
                or 'observation_frame' in b['progress'] and (type(b['progress']['observation_frame']) is not int
                                                           or b['progress']['observation_frame'] != frame)):
            raise ValueError('基線必須為完整同觀測四人／wild132 Lv30／位置與decoder')
        command = _command(rows, p, enemy)
        target = [i for i, m in enumerate(p) if m['species'] == target_species]
        if command is None or len(target) != 1 or command[0] == target[0]:
            raise ValueError('目標須唯一且非目前實際上場成員')
        m = p[target[0]]
        if m['hp'] < 60 or m['hp'] * 3 <= m['max_hp'] * 2:
            raise ValueError('換入目標須HP>=60且嚴格大於2/3')
        self.baseline, self.target_species = b, target_species
        self._target_contract, self._baseline_frame, self._baseline_now = target_species, b['frame'], b['now']
        self.target_index, self.original_active = target[0], command[0]
        self.before_party, self.before_items, self.before_enemy = deepcopy(p), inv, enemy
        self.original_upper = rows[:12]
        self.last_hp = [m['hp'] for m in p]
        self.last_enemy_status = enemy['status']
        self.max_calls, self.max_seconds, self.max_waits = max_calls, max_seconds, max_waits
        self.calls = self.waits = 0
        self.stage, self.error, self.completion = 'command', None, None
        self.last_frame = self.last_packet = None
        self.last_now = b['now']
        self.pending = None
        self.switch_requested = self.seen_sendout = self.seen_enemy_turn = False
        self.enemy_action = None
        self.prompt_pages = set()

    def _hint(self, action, tactic, **extra):
        objectives = {'wait': 'Wait.', 'a': 'Confirm the current selection.',
                      'up': 'Move UP.', 'down': 'Move DOWN.', 'left': 'Move LEFT.', 'right': 'Move RIGHT.'}
        return {'phase': 'snorlax_switch_menu', 'objective': objectives[action],
                'available_actions': ['wait'] if action == 'wait' else [action, 'wait'],
                'controller_menu_verified': True, 'snorlax_switch_tactic': tactic,
                'switch_stage': self.stage, 'target_species': self.target_species,
                'source_commit': SOURCE_COMMIT, 'sources': SOURCES,
                'snorlax_switch_complete': False, **extra}

    def _fail(self, reason):
        self.error = reason
        return {**self._hint('wait', 'stop_for_review'), 'phase': 'campaign_review',
                'controller_menu_verified': False, 'review_reason': reason}

    def _wait(self, reason):
        self.waits += 1
        return self._fail('snorlax_switch_wait_budget_exhausted') if self.waits > self.max_waits else self._hint('wait', reason)

    def _send(self, action, kind, old, expected, tactic):
        self.pending = (kind, old, expected)
        return self._hint(action, tactic)

    def _progress(self, progress):
        party = _party(progress)
        if party is None:
            return None, 'snorlax_switch_party_invalid_or_fainted'
        if _inventory(progress) != self.before_items or progress.get('money') != self.baseline['progress'].get('money'):
            return None, 'snorlax_switch_inventory_or_money_changed'
        for i, (m, before) in enumerate(zip(party, self.before_party)):
            if {k: v for k, v in m.items() if k != 'hp'} != {k: v for k, v in before.items() if k != 'hp'}:
                return None, 'snorlax_switch_identity_order_moves_pp_exp_or_status_changed'
            if (i != self.target_index or not self.switch_requested) and m['hp'] != before['hp']:
                return None, 'snorlax_switch_unexpected_party_hp_change'
            if m['hp'] > self.last_hp[i]:
                return None, 'snorlax_switch_hp_increased_or_snapshot_reverted'
        self.last_hp = [m['hp'] for m in party]
        return party, None

    def context(self, text, progress, *, location, battle_state, enemy_snapshot, frame, now):
        if self.completion is not None:
            return deepcopy(self.completion)
        if self.error:
            return self._fail(self.error)
        self.calls += 1
        if type(self.target_species) is not int or self.target_species != self._target_contract:
            return self._fail('snorlax_switch_target_contract_changed')
        if (not _int(frame, self._baseline_frame, 2**63 - 1) or not _clock(now) or now < self.last_now
                or self.last_frame is not None and frame < self.last_frame):
            return self._fail('snorlax_switch_clock_or_frame_invalid')
        if self.calls > self.max_calls or now - self._baseline_now > self.max_seconds:
            return self._fail('snorlax_switch_transaction_budget_exhausted')
        self.last_now = now
        rows = _rows(text, frame)
        if not _stance(location, frame) or not _battle(battle_state, frame):
            return self._fail('snorlax_switch_location_or_wild_identity_changed')
        if (not isinstance(progress, dict) or 'observation_frame' in progress
                and (type(progress['observation_frame']) is not int or progress['observation_frame'] != frame)):
            return self._fail('snorlax_switch_progress_frame_conflict')
        enemy = _enemy(enemy_snapshot, frame)
        if enemy is None:
            return self._fail('snorlax_switch_enemy_snapshot_unknown_or_zero_hp')
        if any(enemy[k] != self.before_enemy[k] for k in ('species', 'level', 'hp', 'max_hp')):
            return self._fail('snorlax_switch_enemy_hp_or_identity_changed')
        old_status = self.last_enemy_status
        if enemy['status'] != old_status and not (self.switch_requested and old_status & 7 and 0 <= enemy['status'] <= old_status):
            return self._fail('snorlax_switch_enemy_new_status')
        self.last_enemy_status = enemy['status']
        party, error = self._progress(progress)
        if error:
            return self._fail(error)
        if rows is None:
            cells=text.get('cells') if isinstance(text,dict) else None
            expected=[' '*20 for _ in range(18)];expected[0]=' SNORLAX'.ljust(20)
            known=(self.stage=='switching' and self.switch_requested
                   and (not self.seen_sendout or self.enemy_action=='headbutt' and self.seen_enemy_turn)
                   and isinstance(text,dict) and text.get('profile')==TEXT_PROFILE
                   and text.get('read_valid') is False and text.get('alignment_verified') is False
                   and text.get('window_visible') is True
                   and text.get('read_error')=='visible_tile_alignment_incomplete'
                   and isinstance(cells,(list,tuple)) and len(cells)==18
                   and all(isinstance(r,(list,tuple)) and len(r)==20
                           and all(isinstance(c,str) and len(c)==1 for c in r) for r in cells)
                   and _match(tuple(''.join(r).upper() for r in cells),tuple(expected))!='invalid'
                   and ('observation_frame' not in text or type(text['observation_frame']) is int
                        and text['observation_frame']==frame))
            if known:
                raw_packet=deepcopy((None,text,progress,location,battle_state,enemy_snapshot))
                if frame==self.last_frame:
                    if raw_packet!=self.last_packet:return self._fail('snorlax_switch_same_frame_conflict')
                    return {**self._wait('same_native_wipe_frame_no_resend'),
                            'controller_menu_verified':False,'native_decoder_read_valid':False}
                self.last_frame,self.last_packet=frame,raw_packet
                self.native_wipe_waits=getattr(self,'native_wipe_waits',0)+1
                if self.native_wipe_waits<=25:
                    return {**self._wait('await_native_switch_or_verified_headbutt_wipe'),
                            'controller_menu_verified':False,'native_decoder_read_valid':False}
            return self._fail('snorlax_switch_full_decoder_proof_required')
        self.native_wipe_waits=0
        packet = deepcopy((rows, text['window_visible'], progress, location, battle_state, enemy_snapshot))
        if frame == self.last_frame:
            return self._wait('same_frame_no_resend') if packet == self.last_packet else self._fail('snorlax_switch_same_frame_conflict')
        self.last_frame, self.last_packet = frame, packet
        if not ''.join(rows).strip():
            return self._wait('bounded_known_menu_or_animation_transition')
        if self.stage == 'command':
            command = _command(rows, party, enemy)
            if command is None or command[0] != self.original_active:
                return self._fail('snorlax_switch_initial_command_not_verified')
            cursor = command[1]
            if self.pending:
                kind, old, expected = self.pending
                if kind != 'command' or cursor not in (old, expected):
                    return self._fail('snorlax_switch_command_cursor_unexpected')
                if cursor == old:
                    return self._wait('await_requested_command_cursor_without_resend')
                self.pending = None
            if cursor == (15, 14):
                self.stage = 'party'
                return self._send('a', 'open_party', rows, None, 'open_verified_pkmn_once')
            action, expected = ('up', (cursor[0], 14)) if cursor[1] == 16 else ('right', (15, 14))
            return self._send(action, 'command', cursor, expected, 'navigate_only_to_verified_pkmn')
        if self.stage in ('party', 'submenu'):
            return self._menus(rows, party, enemy)
        return self._switching(rows, party, enemy)

    def _menus(self, rows, party, enemy):
        if self.stage == 'party' and self.pending and self.pending[0] == 'open_party':
            if rows == self.pending[1]:
                return self._wait('await_party_open_without_reconfirming_pkmn')
        if self.stage == 'submenu':
            if self.pending and self.pending[0] == 'select_member' and _match(rows, self.pending[1]) != 'invalid':
                return self._wait('await_selected_member_cursor_without_reconfirming_a')
            expected = _party_view(party, self.target_index, submenu=True)
            status = _match(rows, expected)
            if status == 'full':
                self.stage, self.switch_requested, self.pending = 'switching', True, None
                return self._hint('a', 'confirm_only_complete_switch_once')
            # Selecting a party member leaves its unfilled cursor before submenu.
            selected = list(_party_view(party, self.target_index))
            y = self.target_index * 2 + 1; selected[y] = '▷' + selected[y][1:]
            if _match(rows, tuple(selected)) != 'invalid' or status == 'partial':
                return self._wait('await_complete_switch_submenu_without_reselecting_member')
            return self._fail('snorlax_switch_submenu_unknown_or_non_switch_cursor')
        full = [(i, _match(rows, _party_view(party, i))) for i in range(4)]
        selected = [i for i, status in full if status == 'full']
        if not selected:
            if any(status == 'partial' for _, status in full):
                return self._wait('await_complete_party_names_levels_hp_and_cursor')
            return self._fail('snorlax_switch_party_menu_unknown')
        cursor = selected[0]
        if self.pending and self.pending[0] == 'party':
            _, old, expected = self.pending
            if cursor not in (old, expected):
                return self._fail('snorlax_switch_party_cursor_unexpected')
            if cursor == old:
                return self._wait('await_requested_party_cursor_without_resend')
        self.pending = None
        if cursor == self.target_index:
            self.stage = 'submenu'
            return self._send('a', 'select_member', rows, None, 'select_actual_target_member_once')
        step = 1 if cursor < self.target_index else -1
        return self._send('down' if step == 1 else 'up', 'party', cursor, cursor + step, 'navigate_one_party_row_without_reordering')

    def _switching(self, rows, party, enemy):
        # Stale selected submenu is only observed, never confirmed twice.
        if _match(rows, _party_view(self.before_party, self.target_index, submenu=True)) != 'invalid':
            return self._wait('await_switch_submenu_close_without_resend')
        inactive = list(_party_view(self.before_party, self.target_index, submenu=True))
        inactive[12] = inactive[12][:12] + '▷' + inactive[12][13:]
        if _match(rows, tuple(inactive)) != 'invalid':
            return self._wait('await_unfilled_switch_cursor_close_without_resend')
        command = _command(rows, party, enemy)
        if command is not None:
            if command[0] == self.original_active:
                return self._wait('await_actual_target_sendout_not_old_command')
            if command[0] != self.target_index or not self.seen_sendout or not self.seen_enemy_turn:
                return self._fail('snorlax_switch_sendout_or_enemy_turn_not_observed')
            self.stage = 'complete'
            mon = party[self.target_index]
            self.completion = {**self._hint('wait', 'switch_complete_on_actual_target_command'),
                'phase': 'snorlax_switch_complete', 'snorlax_switch_complete': True,
                'active_party_index': self.target_index, 'party_order_preserved': True,
                'target_hp_after_enemy_turn': mon['hp'], 'target_max_hp': mon['max_hp'],
                'target_safe_after_switch': mon['hp'] >= 60 and mon['hp'] * 3 > mon['max_hp'] * 2,
                'requires_next_capture_safety_check': True, 'completion_observation_frame': self.last_frame,
                'evidence_scope': 'latched normal switch receipt; no attack, ball, RUN or later packet validation'}
            return deepcopy(self.completion)
        return self._dialogue(rows, party, enemy)

    def _dialogue(self, rows, party, enemy):
        if _marks(rows, '▶') or _marks(rows, '▷') or _marks(rows, '▼') not in ([], [(18, 16)]):
            return self._fail('snorlax_switch_unknown_animation_menu')
        active = _hud(rows, party, enemy, allow_hp_decrease_index=self.target_index)
        name, target = self.before_party[self.original_active]['species_name'], NAMES[self.target_species]
        passive = {
            ('GO! ' + target + '!', ''): 'sendout', ('DO IT! ' + target + '!', ''): 'sendout',
            ("GET'M! " + target + '!', ''): 'sendout', ("THE ENEMY'S WEAK!", "GET'M! " + target + '!'): 'sendout',
            (name + ' ENOUGH!', 'COME BACK!'): 'retreat', (name + ' OK!', 'COME BACK!'): 'retreat',
            (name + ' GOOD!', 'COME BACK!'): 'retreat', (name, 'COME BACK!'): 'retreat',
            ('ENEMY SNORLAX', 'USED HEADBUTT!'): 'headbutt',
            ('ENEMY SNORLAX', 'USED AMNESIA!'): 'amnesia',
        }
        prompts = {('ENEMY SNORLAX', 'IS FAST ASLEEP!'): 'sleep', ('ENEMY SNORLAX', 'WOKE UP!'): 'wake',
                   ('CRITICAL HIT!', ''): 'critical', ('NOTHING HAPPENED!', ''): 'nothing',
                   ('BUT, IT FAILED!', ''): 'failed', ('SPECIAL', 'GREATLY ROSE!'): 'special'}
        first, second = rows[14][1:19].rstrip(), rows[16][1:19].replace('▼', ' ').rstrip()
        key = (first, second)
        expected = [[' '] * 20 for _ in range(6)]
        _put(expected, 1, 2, first); _put(expected, 1, 4, second)
        if _marks(rows, '▼'):
            expected[4][18] = '▼'
        if rows[12:] != tuple(''.join(r) for r in expected):
            return self._fail('snorlax_switch_dialogue_geometry_unknown')
        prompt = bool(_marks(rows, '▼'))
        known = key in passive or key in prompts or (not prompt and any(
            a.startswith(first) and b.startswith(second) for a, b in (*passive, *prompts)))
        if not known:
            return self._fail('snorlax_switch_unknown_or_unsupported_enemy_dialogue')
        visible_hp = re.fullmatch(r'\s*(\d+)\s*/\s*(\d+)\s*', rows[10])
        if visible_hp and int(visible_hp.group(1)) == 0:
            return self._fail('snorlax_switch_visible_fainted_hp')
        if active not in (self.original_active, self.target_index):
            # Full source HUDs may be cleared while rendering. Only a blank or
            # known original HUD prefix can wait; never press A on partial HUD.
            upper = tuple(''.join(' ' if c == '#' and (x < 8 and 5 <= y < 12 or 12 <= x < 19 and y < 7)
                                 else c for x, c in enumerate(r)) for y, r in enumerate(rows[:12]))
            target_upper = [[' '] * 20 for _ in range(12)]
            m = party[self.target_index]
            for x, y, value in ((1, 0, 'SNORLAX'), (5, 1, _status(enemy['status'], 30)),
                                (10, 7, m['species_name']), (15, 8, _status(m['status'], m['level'])),
                                (11, 10, f"{m['hp']:3}/{m['max_hp']:3}")):
                _put(target_upper, x, y, value)
            if any(_match(upper, expected) != 'invalid' for expected in
                   (self.original_upper, tuple(''.join(r) for r in target_upper))):
                return self._wait('await_complete_known_animation_hud_without_a')
            return self._fail('snorlax_switch_animation_hud_not_verified')
        if key in passive and not prompt:
            event = passive[key]
            if event == 'sendout':
                self.seen_sendout = True
            if event in ('headbutt', 'amnesia'):
                if not self.seen_sendout or active != self.target_index or self.enemy_action not in (None, event):
                    return self._fail('snorlax_switch_enemy_action_sequence_unknown')
                self.enemy_action, self.seen_enemy_turn = event, True
            return self._wait('observe_automatic_' + event + '_without_a')
        if key in prompts and prompt:
            event = prompts[key]
            if not self.seen_sendout or active != self.target_index:
                return self._fail('snorlax_switch_enemy_prompt_before_target_sendout')
            if event == 'critical' and self.enemy_action != 'headbutt' or event == 'special' and self.enemy_action != 'amnesia':
                return self._fail('snorlax_switch_enemy_prompt_without_known_action')
            if event in ('nothing', 'failed') and self.enemy_action is None:
                return self._fail('snorlax_switch_enemy_prompt_without_known_action')
            if event in ('sleep', 'wake'):
                if not self.before_enemy['status'] & 7:
                    return self._fail('snorlax_switch_sleep_text_without_sleep_baseline')
                self.seen_enemy_turn = True
            if key in self.prompt_pages:
                return self._wait('await_enemy_prompt_close_without_resending_a')
            self.prompt_pages.add(key)
            return self._hint('a', 'confirm_only_source_enemy_prompt_once')
        # Only a prefix of a known fixed message is a known typing transition.
        if not prompt and any(a.startswith(first) and b.startswith(second) for a, b in (*passive, *prompts)):
            return self._wait('await_known_switch_or_enemy_message_typing')
        return self._fail('snorlax_switch_unknown_or_unsupported_enemy_dialogue')
