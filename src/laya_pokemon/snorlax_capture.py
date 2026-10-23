"""Route12卡比獸只投超級球的有界純候選；不操作實況、不負責收服結尾。

四人限定7/35/102及剛好一隻9或154。弱血先review，尚不自動切換；
捕獲第一頁只交capture_completion，不替任何未讀數值補值或改觀測。
"""
from copy import deepcopy
import re

from .capture_completion import _rows, _int, _clock, _inventory, _battle, _stance
from .observation import PROFILE as TEXT_PROFILE


SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
ENEMY_PROFILE = 'red-en-sdk-2.8.1-enemy-source-v1-unvalidated'
INTENT = {'kind': 'capture_route12_snorlax_with_great_balls', 'map_id': 23, 'x': 10, 'y': 61,
          'species': 132, 'level': 30, 'ball_item': 3, 'initial_great_balls': 20,
          'starter_species': 'one_of_9_154', 'no_attack': True, 'no_run': True}
_NAMES = {7: 'NIDOKING', 9: 'IVYSAUR', 154: 'VENUSAUR', 35: 'FEAROW', 102: 'EEVEE'}
_STATUS = {*range(8), 8, 16, 32, 64}
_POSSESSIVE_TILE = '\ue000'  # SDK的0xBD一格顯示"'s"；只供內部保留tile座標。


def _capture_rows(text, frame):
    rows = _rows(text, frame)
    if rows is not None:
        return None if any(_POSSESSIVE_TILE in r for r in rows) else rows
    if (not isinstance(text, dict) or text.get('profile') != TEXT_PROFILE
            or text.get('read_valid') is not True or text.get('alignment_verified') is not True
            or type(text.get('window_visible')) is not bool or text.get('read_error') is not None
            or 'observation_frame' in text and (type(text['observation_frame']) is not int
                                                or text['observation_frame'] != frame)):
        return None
    cells = text.get('cells')
    if (not isinstance(cells, (list, tuple)) or len(cells) != 18
            or any(not isinstance(r, (list, tuple)) or len(r) != 20
                   or any(not isinstance(c, str) or _POSSESSIVE_TILE in c
                          or len(c) != 1 and c != "'s" for c in r) for r in cells)):
        return None
    special = [(x, y) for y, r in enumerate(cells) for x, c in enumerate(r) if c == "'s"]
    if special not in ([(14, 14)], [(14, 13)]): return None
    possessive_row = special[0][1]
    if (cells[possessive_row][0] != ' '
            or ''.join(cells[possessive_row][1:14]).upper() != 'ENEMY SNORLAX'
            or any(c != ' ' for c in cells[possessive_row][15:])):
        return None
    raw = tuple(''.join(r) for r in cells)
    if 'lines' in text or 'line_rows' in text:
        selected = [(i, r.rstrip()) for i, r in enumerate(raw) if re.search(r'[A-Za-z0-9]{2,}', r)][:12]
        if text.get('lines') != [r for _, r in selected] or text.get('line_rows') != [i for i, _ in selected]:
            return None
    # 不改原觀測或拿轉換結果去冒充其他控制器的decoder證明。
    return tuple(''.join(_POSSESSIVE_TILE if c == "'s" else c.upper() for c in r) for r in cells)
_ITEM_LABELS = {
    1: "MASTER BALL",
    2: "ULTRA BALL",
    3: "GREAT BALL",
    4: "POKÉ BALL",
    5: "TOWN MAP",
    6: "BICYCLE",
    8: "SAFARI BALL",
    9: "POKÉDEX",
    10: "MOON STONE",
    11: "ANTIDOTE",
    12: "BURN HEAL",
    13: "ICE HEAL",
    14: "AWAKENING",
    15: "PARLYZ HEAL",
    16: "FULL RESTORE",
    17: "MAX POTION",
    18: "HYPER POTION",
    19: "SUPER POTION",
    20: "POTION",
    21: "BOULDERBADGE",
    22: "CASCADEBADGE",
    23: "THUNDERBADGE",
    24: "RAINBOWBADGE",
    25: "SOULBADGE",
    26: "MARSHBADGE",
    27: "VOLCANOBADGE",
    28: "EARTHBADGE",
    29: "ESCAPE ROPE",
    30: "REPEL",
    31: "OLD AMBER",
    32: "FIRE STONE",
    33: "THUNDERSTONE",
    34: "WATER STONE",
    35: "HP UP",
    36: "PROTEIN",
    37: "IRON",
    38: "CARBOS",
    39: "CALCIUM",
    40: "RARE CANDY",
    41: "DOME FOSSIL",
    42: "HELIX FOSSIL",
    43: "SECRET KEY",
    45: "BIKE VOUCHER",
    46: "X ACCURACY",
    47: "LEAF STONE",
    48: "CARD KEY",
    49: "NUGGET",
    50: "PP UP",
    51: "POKÉ DOLL",
    52: "FULL HEAL",
    53: "REVIVE",
    54: "MAX REVIVE",
    55: "GUARD SPEC.",
    56: "SUPER REPEL",
    57: "MAX REPEL",
    58: "DIRE HIT",
    59: "COIN",
    60: "FRESH WATER",
    61: "SODA POP",
    62: "LEMONADE",
    63: "S.S.TICKET",
    64: "GOLD TEETH",
    65: "X ATTACK",
    66: "X DEFEND",
    67: "X SPEED",
    68: "X SPECIAL",
    69: "COIN CASE",
    70: "OAK'S PARCEL",
    71: "ITEMFINDER",
    72: "SILPH SCOPE",
    73: "POKÉ FLUTE",
    74: "LIFT KEY",
    75: "EXP.ALL",
    76: "OLD ROD",
    77: "GOOD ROD",
    78: "SUPER ROD",
    79: "PP UP",
    80: "ETHER",
    81: "MAX ETHER",
    82: "ELIXER",
    83: "MAX ELIXER",
}
_ITEM_LABELS.update({i: f'HM{i - 195:02d}' for i in range(196, 201)})
_ITEM_LABELS.update({i: f'TM{i - 200:02d}' for i in range(201, 251)})
_KEY_ITEMS = {5, 6, 7, 8, 9, 21, 22, 23, 24, 25, 26, 27, 28, 31, 41, 42, 43, 44, 45, 48, 63, 64, 69, 70, 71, 72, 73, 74, 76, 77, 78, *range(196, 201)}
_FAILURES = {
    'missed': ((1, 14, 'YOU MISSED THE'), (1, 16, 'POKÉMON!')),
    'broke_free': ((1, 14, 'DARN! THE POKÉMON'), (1, 16, 'BROKE FREE!')),
    'appeared_caught': ((1, 14, 'AWW! IT APPEARED'), (1, 16, 'TO BE CAUGHT!')),
    'close': ((1, 14, 'SHOOT! IT WAS SO'), (1, 16, 'CLOSE TOO!')),
}
_CAUGHT = ((1, 14, 'ALL RIGHT!'), (1, 16, 'SNORLAX WAS'))
_ENEMY_PROMPTS = {
    'asleep': ((1, 14, 'ENEMY SNORLAX'), (1, 16, 'IS FAST ASLEEP!')),
    'woke': ((1, 14, 'ENEMY SNORLAX'), (1, 16, 'WOKE UP!')),
    'health': ((1, 14, 'ENEMY SNORLAX'), (1, 16, 'REGAINED HEALTH!')),
    'rest_cont': ((1, 14, 'ENEMY SNORLAX'), (1, 16, 'FELL ASLEEP AND')),
    'missed': ((1, 14, "ENEMY SNORLAX'S"), (1, 16, 'ATTACK MISSED!')),
    'critical': ((1, 14, 'CRITICAL HIT!'),),
    'special': ((1, 14, 'SPECIAL'), (1, 16, 'GREATLY ROSE!')),
    'failed': ((1, 14, 'BUT, IT FAILED!'),),
    'nothing': ((1, 14, 'NOTHING HAPPENED!'),),
}
_PASSIVE = {
    'headbutt': ((1, 14, 'ENEMY SNORLAX'), (1, 16, 'USED HEADBUTT!')),
    'amnesia': ((1, 14, 'ENEMY SNORLAX'), (1, 16, 'USED AMNESIA!')),
    'rest': ((1, 14, 'ENEMY SNORLAX'), (1, 16, 'USED REST!')),
    'rest_sleep': ((1, 14, 'ENEMY SNORLAX'), (1, 16, 'STARTED SLEEPING!')),
    'rest_healthy': ((1, 14, 'FELL ASLEEP AND'), (1, 16, 'BECAME HEALTHY!')),
    'stat_intro': ((1, 14, "ENEMY SNORLAX'S"), (1, 16, 'SPECIAL')),
}


def _party(progress):
    if (not isinstance(progress, dict) or progress.get('profile') != 'gen1-wrapper-ram-progress-v1-unvalidated'
            or progress.get('party_read_valid') is not True or progress.get('initialization_candidate') is not True
            or type(progress.get('party_count')) is not int or progress['party_count'] != 4
            or not isinstance(progress.get('party'), list) or len(progress['party']) != 4
            or progress.get('player_name_raw') != 'KEVIN'):
        return None
    party = progress['party']
    for mon in party:
        if (not isinstance(mon, dict) or type(mon.get('species')) is not int or mon['species'] not in _NAMES
                or mon.get('species_name') != _NAMES[mon['species']]
                or not _int(mon.get('level'), 1, 100) or not _int(mon.get('exp'), 0, 0xFFFFFF)
                or not _int(mon.get('max_hp'), 1, 999) or not _int(mon.get('hp'), 0, mon['max_hp'])
                or type(mon.get('status')) is not int or mon['status'] not in _STATUS
                or any(not isinstance(mon.get(k), list) or len(mon[k]) != 4
                       or any(not _int(v, 0, cap) for v in mon[k]) for k, cap in (('moves', 165), ('pp', 255)))):
            return None
    species = {m['species'] for m in party}
    return party if len(species) == 4 and {7, 35, 102} <= species and len(species & {9, 154}) == 1 else None


def _enemy(snapshot, frame, *, allow_zero_transition=False):
    if (not isinstance(snapshot, dict) or snapshot.get('profile') != ENEMY_PROFILE
            or snapshot.get('source_commit') != SOURCE_COMMIT or snapshot.get('live_calibrated') is not False
            or type(snapshot.get('observation_frame')) is not int or snapshot['observation_frame'] != frame):
        return None
    if allow_zero_transition and snapshot.get('read_valid') is False and snapshot.get('enemy') is None:
        return 'zero_transition' if snapshot.get('unknown_reason') == 'enemy_zero_hp_transition' else None
    if (snapshot.get('read_valid') is not True or snapshot.get('unknown_reason') is not None
            or snapshot.get('battle_kind') != 'wild' or not _stance(snapshot.get('location'))):
        return None
    enemy = snapshot.get('enemy')
    if (not isinstance(enemy, dict) or any(type(enemy.get(k)) is not int for k in ('species', 'level', 'hp', 'max_hp', 'status'))
            or enemy['species'] != 132 or enemy.get('internal_id') != 132 or type(enemy.get('internal_id')) is not int
            or enemy.get('species_name') != 'SNORLAX' or enemy['level'] != 30
            or not _int(enemy['max_hp'], 136, 145) or not _int(enemy['hp'], 1, enemy['max_hp'])
            or enemy['status'] not in _STATUS):
        return None
    return {k: enemy[k] for k in ('species', 'level', 'hp', 'max_hp', 'status')}


def _markers(rows, char):
    return [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == char]


def _put(rows, x, y, value):
    rows[y][x:x + len(value)] = list(value)


def _safe(mon):
    return mon['hp'] >= 60 and mon['hp'] * 3 > mon['max_hp'] * 2


class SnorlaxCaptureController:
    """只投20顆以內Great Ball；弱血換人尚未實作，會review而非冒險續投。

    context的enemy_snapshot須直接來自經審查的wild_opponent reader原物件。
    同一執行緒採樣、沒有其他人／controller按鍵是caller前置，本類不加鎖。
    """
    def __init__(self, intent, *, max_calls=240, max_seconds=60, max_waits=120, max_throws=20):
        if (not isinstance(intent, dict) or intent != INTENT
                or any(type(intent[k]) is not type(INTENT[k]) for k in INTENT)):
            raise ValueError('只允許Route12指定四人及20顆Great Ball的保守捕捉意圖')
        if (not _int(max_calls, 1, 240) or not _int(max_waits, 1, 240) or not _int(max_throws, 1, 20)
                or not _clock(max_seconds) or not 0 < max_seconds <= 60):
            raise ValueError('上限240calls、240waits、60秒、20次投球請求')
        self.intent, self._contract = deepcopy(intent), deepcopy(INTENT)
        self.max_calls, self.max_waits, self.max_seconds, self.max_throws = max_calls, max_waits, max_seconds, max_throws
        self.calls = self.waits = self.throws = self.scrolls = 0
        self.stage, self.error, self.handoff = 'command', None, None
        self.started_at = self.last_now = self.last_frame = self.last_packet = None
        self.party_identity = self.party_hp = self.initial_items = self.current_items = None
        self.active_index = self.command_pending = self.bag_pending = None
        self.hud_text = self.hud_rows = self.hud_frame = self.menu_party = self.menu_enemy = None
        self.last_throw = self.throw_bag = None
        self.prompt_pending = self.failure_pending = None
        self.enemy_prompts_seen = set()

    def _hint(self, action, tactic, **extra):
        meta = {'snorlax_capture_controller': 'great_ball_candidate', 'capture_stage': self.stage,
                'capture_tactic': tactic, 'source_commit': SOURCE_COMMIT, 'capture_complete': False,
                'ball_throw_requests': self.throws, 'controller_menu_verified': True, **extra}
        objectives = {'a': 'Confirm the current selection.', 'left': 'Move LEFT.',
                      'up': 'Move UP.', 'down': 'Move DOWN.', 'wait': 'Wait.'}
        return {'phase': 'snorlax_capture_menu', 'objective': objectives[action],
                'available_actions': ['wait'] if action == 'wait' else [action, 'wait'], **meta}

    def _fail(self, reason, **extra):
        self.error = reason
        return {**self._hint('wait', 'stop_for_review', **extra), 'phase': 'campaign_review',
                'controller_menu_verified': False, 'review_reason': reason}

    def _wait(self, tactic):
        self.waits += 1
        return self._fail('snorlax_capture_wait_budget_exhausted') if self.waits > self.max_waits else self._hint('wait', tactic)

    def _safety(self, party, index):
        if index is not None and not _safe(party[index]):
            candidates = [i for i, m in enumerate(party) if i != index and _safe(m)]
            return self._fail('snorlax_capture_safe_switch_requires_review', active_party_index=index,
                healthy_switch_candidates=candidates, switch_implemented=False)
        return None

    def _hud(self, rows, party, enemy, *, damage_countdown=False):
        """只解析原可見HUD；沒有改造觀測來通過其他控制器。"""
        clean = [list(row) for row in rows[:12]]
        for y, row in enumerate(clean):
            for x, c in enumerate(row):
                if c == '#' and (x < 8 and 5 <= y < 12 or 12 <= x < 19 and y < 7):
                    row[x] = ' '
        clean = [''.join(row) for row in clean]
        matches = [i for i, m in enumerate(party) if clean[7].strip() == m['species_name']]
        if len(matches) != 1 or clean[0].strip() != 'SNORLAX':
            return None
        index, mon = matches[0], party[matches[0]]
        def status(value, level):
            return 'SLP' if value & 7 else {8: 'PSN', 16: 'BRN', 32: 'FRZ', 64: 'PAR'}.get(value, str(level))
        hp = re.fullmatch(r'\s*(\d+)\s*/\s*(\d+)\s*', clean[10])
        observed_hp = tuple(map(int, hp.groups())) if hp is not None else None
        hp_verified = (observed_hp == (mon['hp'], mon['max_hp']) if not damage_countdown else
                       observed_hp is not None and observed_hp[1] == mon['max_hp']
                       and 1 <= observed_hp[0] <= mon['hp'])
        if (clean[1].strip() != status(enemy['status'], 30) or clean[8].strip() != status(mon['status'], mon['level'])
                or not hp_verified
                or any(clean[y].strip() for y in (2, 3, 4, 5, 6, 9, 11))
                or any(c in ''.join(rows[:12]) for c in '▶▷▼')):
            return None
        return index

    def _command_cursor(self, rows):
        cursors = _markers(rows, '▶')
        if len(cursors) != 1 or cursors[0] not in {(9, 14), (15, 14), (9, 16), (15, 16)}:
            return None
        expected = [[' '] * 20 for _ in range(6)]
        for x, y, value in ((10, 2, 'FIGHT'), (10, 4, 'ITEM'), (16, 4, 'RUN')):
            _put(expected, x, y, value)
        x, y = cursors[0]; expected[y - 12][x] = '▶'
        return cursors[0] if rows[12:] == tuple(''.join(row) for row in expected) else None

    def _body(self, rows, slots, *, prompt, upper):
        slots = tuple((x, y, value.replace("'S", _POSSESSIVE_TILE) if _POSSESSIVE_TILE in rows[y] else value)
                      for x, y, value in slots)
        expected = [[' '] * 20 for _ in range(18)]
        expected[:12] = [list(row) for row in upper]
        for x, y, value in slots: _put(expected, x, y, value)
        arrows = _markers(rows, '▼')
        if (_markers(rows, '▶') or _markers(rows, '▷') or arrows not in ([], [(18, 16)])
                or arrows and not prompt):
            return 'invalid'
        clean = [row.replace('▼', ' ') for row in rows]
        if any(c != ' ' and c != expected[y][x] for y, row in enumerate(clean) for x, c in enumerate(row)):
            return 'invalid'
        if any(not value.startswith(clean[y][x:x + len(value)].rstrip()) for x, y, value in slots):
            return 'invalid'
        full = all(clean[y][x:x + len(value)] == value for x, y, value in slots)
        if arrows and not full: return 'invalid'
        return 'full' if full and bool(arrows) == prompt else 'partial'

    def context(self, text, progress, *, location, battle_state, enemy_snapshot, frame, now, intent=None):
        """回單一步驟子目標；失敗與handoff鎖存，從不執行按鍵。"""
        if self.handoff is not None: return deepcopy(self.handoff)
        if self.error: return self._fail(self.error)
        self.calls += 1
        if self.intent != self._contract or intent is not None and intent != self._contract:
            return self._fail('snorlax_capture_intent_changed')
        if (not _int(frame, 0, 2**63 - 1) or not _clock(now)
                or self.last_frame is not None and frame < self.last_frame
                or self.last_now is not None and now < self.last_now):
            return self._fail('snorlax_capture_clock_or_frame_invalid')
        if self.started_at is None: self.started_at = now
        if self.calls > self.max_calls or now - self.started_at > self.max_seconds:
            return self._fail('snorlax_capture_transaction_budget_exhausted')
        self.last_now = now
        rows, party, items = _capture_rows(text, frame), _party(progress), _inventory(progress)
        if not _stance(location) or _battle(battle_state) != 'wild':
            return self._fail('snorlax_capture_fixed_wild_location_required')
        for packet in (progress, location, battle_state):
            if not isinstance(packet, dict) or 'observation_frame' in packet and (
                    type(packet['observation_frame']) is not int or packet['observation_frame'] != frame):
                return self._fail('snorlax_capture_observation_frame_conflict')
        if party is None or items is None or any(i not in _ITEM_LABELS for i, _ in items):
            return self._fail('snorlax_capture_party_or_inventory_unverified')
        if any(m['hp'] == 0 for m in party): return self._fail('snorlax_capture_any_party_fainted')
        identity = [{k: deepcopy(v) for k, v in m.items() if k != 'hp'} for m in party]
        if self.party_identity is not None and identity != self.party_identity:
            return self._fail('snorlax_capture_party_identity_order_or_non_hp_data_changed')
        if self.party_hp is not None and any(m['hp'] > hp for m, hp in zip(party, self.party_hp)):
            return self._fail('snorlax_capture_unexpected_party_healing')
        if self.initial_items is None:
            if items.count((3, 20)) != 1 or items.count((73, 1)) != 1:
                return self._fail('snorlax_capture_initial_twenty_great_balls_and_flute_required')
        else:
            quantities = dict(items)
            expected = [(i, 20 - self.throws if i == 3 else q) for i, q in self.initial_items if i != 3 or self.throws < 20]
            before_last = [(i, 21 - self.throws if i == 3 else q) for i, q in self.initial_items]
            allowed = [expected]
            if self.stage in {'await_result', 'enemy_turn'}: allowed.append(before_last)
            if items not in allowed: return self._fail('snorlax_capture_inventory_outside_single_throw_accounting')
            if quantities.get(3, 0) == 0: return self._fail('snorlax_capture_great_balls_exhausted')
        if rows is None:
            # 原生頭錘位移動畫會讓字型對齊驗證暫時失敗；不升格成
            # read_valid，也不確認任何頁，只在精確已知來源文句下有界WAIT。
            lower = text.get('cells') if isinstance(text, dict) else None
            enemy = _enemy(enemy_snapshot, frame)
            expected_lower = [' ' * 20 for _ in range(6)]
            expected_lower[2] = ' ENEMY SNORLAX'.ljust(20)
            expected_lower[4] = ' USED HEADBUTT!'.ljust(20)
            known = (self.stage == 'enemy_turn' and self.last_throw is not None and isinstance(text, dict)
                and text.get('profile') == TEXT_PROFILE and text.get('read_valid') is False
                and text.get('alignment_verified') is False and text.get('window_visible') is True
                and text.get('read_error') == 'visible_tile_alignment_incomplete'
                and isinstance(lower, (list, tuple)) and len(lower) == 18
                and all(isinstance(r, (list, tuple)) and len(r) == 20
                        and all(isinstance(c, str) and len(c) == 1 for c in r) for r in lower)
                and [''.join(r).upper() for r in lower[12:]] == expected_lower
                and enemy == self.last_throw['enemy']
                and items == [(i, 20 - self.throws if i == 3 else q) for i, q in self.initial_items]
                and ('observation_frame' not in text or type(text['observation_frame']) is int
                     and text['observation_frame'] == frame))
            if known:
                safety = self._safety(party, self.active_index)
                if safety: return safety
                raw_packet=deepcopy((None,text,progress,location,battle_state,enemy_snapshot))
                if frame==self.last_frame:
                    if raw_packet!=self.last_packet:return self._fail('snorlax_capture_same_frame_changed_packet')
                    return {**self._wait('same_native_animation_frame_no_resend'),
                            'controller_menu_verified':False,'native_decoder_read_valid':False}
                self.last_frame,self.last_packet=frame,raw_packet
                self.native_animation_waits = getattr(self, 'native_animation_waits', 0) + 1
                if self.native_animation_waits <= 25:
                    return {**self._wait('await_verified_headbutt_native_animation'),
                            'controller_menu_verified': False, 'native_decoder_read_valid': False}
            return self._fail('snorlax_capture_decoder_proof_required')
        self.native_animation_waits = 0
        packet = (rows, deepcopy(progress), deepcopy(location), deepcopy(battle_state), deepcopy(enemy_snapshot), text['window_visible'])
        if frame == self.last_frame:
            if packet != self.last_packet: return self._fail('snorlax_capture_same_frame_changed_packet')
            return self._wait('same_frame_no_resend')
        self.last_frame, self.last_packet = frame, packet
        self.party_identity, self.party_hp = identity, [m['hp'] for m in party]
        if self.initial_items is None: self.initial_items, self.current_items = items, items
        safety = self._safety(party, self.active_index)
        if safety: return safety
        caught = (self.stage == 'await_result' and self.last_throw is not None
                  and self._body(rows, _CAUGHT, prompt=True, upper=self.hud_rows[:12]) == 'full')
        enemy = _enemy(enemy_snapshot, frame, allow_zero_transition=caught)
        if enemy is None: return self._fail('snorlax_capture_real_same_frame_enemy_snapshot_required')
        if caught:
            if items != self.current_items or party != self.last_throw['progress']['party']:
                return self._fail('snorlax_capture_caught_before_expected_baseline_preserved')
            if enemy != 'zero_transition' and enemy != self.last_throw['enemy']:
                return self._fail('snorlax_capture_caught_enemy_fingerprint_conflict')
            self.stage = 'handoff'
            self.handoff = {**self._hint('wait', 'handoff_complete_caught_first_page_without_advancing'),
                'phase': 'snorlax_capture_handoff', 'capture_completion_handoff': True,
                'last_throw': deepcopy(self.last_throw), 'caught_first_page': deepcopy(text),
                'handoff_observation_frame': frame, 'capture_complete': False}
            return deepcopy(self.handoff)
        if enemy == 'zero_transition': return self._fail('snorlax_capture_unknown_enemy_transition')
        if not ''.join(rows).strip(): return self._wait('await_bounded_known_battle_or_menu_transition')
        cursor, active = self._command_cursor(rows), self._hud(rows, party, enemy)
        if (self.stage == 'command' and self.throws == 0 and self.hud_rows is None
                and self.command_pending is None and active is not None
                and self._body(rows, ((1, 14, f"GO! {party[active]['species_name']}!"),),
                               prompt=False, upper=rows[:12]) == 'full'):
            safety = self._safety(party, active)
            if safety: return safety
            self.active_index = active
            return self._wait('await_native_complete_go_text_auto_transition_to_command')
        if cursor is not None and active is not None:
            return self._command(text, rows, progress, enemy, active, cursor, items, frame)
        if self.stage in {'bag_opening', 'bag'}:
            return self._bag(rows, progress, location, battle_state, enemy, items, frame, now)
        if self.stage == 'await_result':
            return self._result(rows, party, enemy, items)
        if self.stage == 'enemy_turn':
            return self._enemy_turn(rows, party, enemy, items)
        return self._fail('snorlax_capture_unrecognized_initial_command')

    def _command(self, text, rows, progress, enemy, active, cursor, items, frame):
        if self.stage in {'await_result', 'bag'}:
            return self._fail('snorlax_capture_command_before_verified_throw_result')
        if self.stage == 'enemy_turn' and items == self.current_items:
            return self._fail('snorlax_capture_failure_ball_not_deducted_before_next_command')
        if self.stage == 'bag_opening':
            if cursor != (9, 16): return self._fail('snorlax_capture_command_cursor_changed_after_item_request')
            return self._wait('await_bag_without_reconfirming_item')
        safety = self._safety(progress['party'], active)
        if safety: return safety
        if self.active_index is not None and self.active_index != active:
            return self._fail('snorlax_capture_unrequested_active_switch')
        if self.command_pending is not None:
            old, expected = self.command_pending
            if cursor == old: return self._wait('await_command_cursor_move_without_resend')
            if cursor != expected: return self._fail('snorlax_capture_command_cursor_wrong_move')
            self.command_pending = None
        self.stage, self.active_index, self.current_items = 'command', active, items
        self.prompt_pending = self.failure_pending = None
        self.enemy_prompts_seen.clear()
        self.hud_text, self.hud_rows, self.hud_frame = deepcopy(text), rows, frame
        self.menu_party, self.menu_enemy = deepcopy(progress['party']), deepcopy(enemy)
        if self.throws >= self.max_throws: return self._fail('snorlax_capture_twenty_throw_request_limit')
        if cursor == (9, 16):
            self.stage, self.bag_pending, self.scrolls = 'bag_opening', None, 0
            return self._hint('a', 'select_only_verified_item_command', menu_label='ITEM')
        action = 'left' if cursor[0] == 15 else 'down'
        expected = (9, cursor[1]) if action == 'left' else (9, 16)
        self.command_pending = (cursor, expected)
        return self._hint(action, 'move_command_cursor_only_toward_item')

    def _bag_parse(self, rows, items):
        expected = [list(row) for row in self.hud_rows]
        for y in range(12, 18): expected[y] = [' '] * 20
        for y in range(2, 13): expected[y][4:20] = [' '] * 16
        markers = _markers(rows, '▶') + _markers(rows, '▷')
        if len(markers) != 1 or markers[0][0] != 5 or markers[0][1] not in (4, 6, 8): return None
        _put(expected, *markers[0], rows[markers[0][1]][5])
        visible, cancel = [], False
        for y in (4, 6, 8, 10):
            label = rows[y][6:19].strip()
            if label == 'CANCEL':
                cancel = True; _put(expected, 6, y, 'CANCEL'); break
            matches = [(i, q) for i, q in items if _ITEM_LABELS[i] == label]
            if len(matches) != 1: return None
            item, qty = matches[0]; visible.append(item); _put(expected, 6, y, _ITEM_LABELS[item])
            if item not in _KEY_ITEMS: _put(expected, 14, y + 1, f'×{qty:2d}')
        # 原生捲動裝飾可在完整清單上暫時不顯示；只接受其固定格，
        # 所有商品、數量、游標及保留下來的背景仍須逐格吻合。
        if not cancel:
            if rows[11][18] not in (' ', '▼'): return None
            _put(expected, 18, 11, rows[11][18])
        if rows != tuple(''.join(row) for row in expected): return None
        offsets = [i for i in range(len(items) - len(visible) + 1)
                   if [x for x, _ in items[i:i + len(visible)]] == visible
                   and (not cancel or i + len(visible) == len(items))]
        if len(offsets) != 1 or not visible: return None
        current = offsets[0] + (markers[0][1] - 4) // 2
        if current >= len(items): return None
        return current, rows[markers[0][1]][5] == '▶'

    def _bag(self, rows, progress, location, battle, enemy, items, frame, now):
        if items != self.current_items or progress['party'] != self.menu_party or enemy != self.menu_enemy:
            return self._fail('snorlax_capture_snapshot_changed_while_selecting_ball')
        parsed = self._bag_parse(rows, items)
        if parsed is None: return self._fail('snorlax_capture_bag_layout_labels_quantities_or_background_unverified')
        current, active = parsed
        if not active: return self._wait('await_active_verified_bag_cursor')
        if self.bag_pending is not None:
            old, expected = self.bag_pending
            if current == old: return self._wait('await_bag_cursor_move_without_resend')
            if current != expected: return self._fail('snorlax_capture_bag_cursor_wrong_move')
            self.bag_pending = None
        target = next(i for i, (item, _) in enumerate(items) if item == 3)
        self.stage = 'bag'
        if current == target:
            if self.throws >= self.max_throws: return self._fail('snorlax_capture_twenty_throw_request_limit')
            self.last_throw = {'frame': frame, 'now': now, 'hud_frame': self.hud_frame, 'ball_item': 3,
                'progress': deepcopy(progress), 'location': deepcopy(location), 'battle_state': deepcopy(battle),
                'enemy': deepcopy(enemy), 'battle_text': deepcopy(self.hud_text)}
            self.throw_bag, self.stage = rows, 'await_result'
            self.throws += 1
            return self._hint('a', 'throw_only_verified_great_ball_once', ball_item=3)
        if self.scrolls >= 20: return self._fail('snorlax_capture_bag_scroll_budget_exhausted')
        self.scrolls += 1
        action = 'down' if current < target else 'up'
        self.bag_pending = (current, current + (1 if action == 'down' else -1))
        return self._hint(action, 'scroll_only_verified_bag_toward_great_ball')

    def _result(self, rows, party, enemy, items):
        if items != self.current_items or party != self.last_throw['progress']['party'] or enemy != self.last_throw['enemy']:
            return self._fail('snorlax_capture_result_before_prompt_fingerprint_changed')
        if self._bag_parse(rows, items) is not None:
            parsed = self._bag_parse(rows, items)
            target = next(i for i, (item, _) in enumerate(items) if item == 3)
            if parsed[0] != target: return self._fail('snorlax_capture_bag_changed_after_throw_request')
            return self._wait('await_throw_result_without_reselecting_ball')
        # 固定text_7.asm的ItemUseText001/002＋text_low：正常自動結束，
        # 包括逐字頁都只WAIT；不確認、不再投球。
        if self._body(rows, ((1, 14, 'KEVIN USED'), (1, 16, 'GREAT BALL!')),
                      prompt=False, upper=self.hud_rows[:12]) != 'invalid':
            return self._wait('await_source_great_ball_use_text_without_resending_throw')
        for name, slots in {'caught': _CAUGHT, **_FAILURES}.items():
            result = self._body(rows, slots, prompt=True, upper=self.hud_rows[:12])
            if result == 'full' and name != 'caught':
                self.stage, self.failure_pending = 'enemy_turn', name
                return self._hint('a', 'confirm_complete_ball_failure_prompt_once', ball_failure=name)
            if result == 'partial': return self._wait('await_complete_known_ball_result')
        if all(c == ' ' or c == self.hud_rows[y][x] for y, row in enumerate(rows) for x, c in enumerate(row)):
            return self._wait('await_known_ball_animation')
        return self._fail('snorlax_capture_unknown_ball_result')

    def _enemy_turn(self, rows, party, enemy, items):
        # 固定core MainInBattleLoop先同步BattleMon→Party才開command。
        # 同步前的頭錘HP倒數只WAIT；開袋仍走預設的嚴格HUD==Party驗證。
        countdown = self._hud(rows, party, enemy, damage_countdown=True)
        if (countdown is not None and countdown == self.active_index
                and self._body(rows, _PASSIVE['headbutt'], prompt=False, upper=rows[:12]) != 'invalid'):
            return self._wait('await_headbutt_hp_countdown_before_native_party_sync')
        if countdown is not None and countdown == self.active_index and self.failure_pending:
            critical = self._body(rows, _ENEMY_PROMPTS['critical'], prompt=True, upper=rows[:12])
            if critical == 'partial': return self._wait('await_complete_critical_before_native_party_sync')
            if critical == 'full':
                if 'critical' in self.enemy_prompts_seen:
                    return self._wait('await_critical_close_without_resending_confirm')
                self.enemy_prompts_seen.add('critical')
                return self._hint('a', 'confirm_complete_critical_only_to_finish_enemy_turn')
        active = self._hud(rows, party, enemy)
        upper = rows[:12] if active is not None else self.hud_rows[:12]
        if active is not None:
            if active != self.active_index: return self._fail('snorlax_capture_unrequested_active_switch')
            safety = self._safety(party, active)
            if safety: return safety
        if self.failure_pending:
            result = self._body(rows, _FAILURES[self.failure_pending], prompt=True, upper=upper)
            if result != 'invalid': return self._wait('await_enemy_turn_without_reconfirming_ball_failure')
        # cont捲動一個tile的實機中間幀，仍保留原格位置；僅WAIT，
        # 不把row13/15當成可確認的完成頁。
        if self._body(rows, ((1, 13, "ENEMY SNORLAX'S"), (1, 15, 'SPECIAL')),
                      prompt=False, upper=upper) != 'invalid':
            return self._wait('await_source_amnesia_one_tile_text_scroll')
        for name, slots in _ENEMY_PROMPTS.items():
            if name == 'critical': continue  # 只有上方完整正數HUD分支可確認。
            result = self._body(rows, slots, prompt=True, upper=upper)
            if result == 'full':
                if active is None or active != self.active_index:
                    return self._fail('snorlax_capture_complete_prompt_requires_current_full_hud')
                if name in self.enemy_prompts_seen: return self._wait('await_next_enemy_page_without_resending_confirm')
                self.prompt_pending = name
                self.enemy_prompts_seen.add(name)
                return self._hint('a', 'confirm_complete_known_enemy_prompt_once', enemy_prompt=name)
            if result == 'partial': return self._wait('await_complete_known_enemy_prompt')
        for name, slots in _PASSIVE.items():
            if name == 'headbutt': continue  # 僅由上面的完整HUD／傷害倒數專用分支處理。
            if self._body(rows, slots, prompt=False, upper=upper) != 'invalid':
                return self._wait('observe_source_passive_enemy_' + name)
        if not ''.join(rows[12:]).strip() and (active is not None or all(
                c == ' ' or c == self.hud_rows[y][x] for y, row in enumerate(rows[:12]) for x, c in enumerate(row))):
            return self._wait('await_bounded_enemy_animation_or_command')
        return self._fail('snorlax_capture_unknown_enemy_turn_ui')
