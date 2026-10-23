"""固定紅版Safari導航用正常RUN；純唯讀證據與有界子目標，不投球。"""
from collections.abc import Mapping
from copy import deepcopy
import math

from .observation import PROFILE as TEXT_PROFILE

SOURCE_COMMIT = 'a53671100ec22e5394ff26ec028d0812a238dae2'
SOURCE = f'https://github.com/pret/pokered/blob/{SOURCE_COMMIT}/engine/battle/core.asm'
PROFILE = 'red-en-safari-run-source-v1'
SAFARI_PROFILE = 'red-en-safari-source-v1'
INTENT = {'kind': 'safari_run_only'}
OUTDOORS = {217, 218, 219, 220}
SDK_ANCHORS = {'CURRENT_OPPONENT_ADDRESS': 0xD059, 'BATTLE_TYPE_ADDRESS': 0xD05A,
               'EVENT_FLAGS_ADDRESS': 0xD747, 'STATUS_FLAGS3_ADDRESS': 0xD72D,
               'OBTAINED_BADGES_ADDRESS': 0xD356}
# 固定四區紅版草叢物種聯集；不是一般捕捉支援名單。
NAMES = {2: 'KANGASKHAN', 3: 'NIDORAN M', 12: 'EXEGGCUTE', 15: 'NIDORAN F',
         18: 'RHYHORN', 26: 'SCYTHER', 40: 'CHANSEY', 46: 'PARASECT', 60: 'TAUROS',
         65: 'VENONAT', 70: 'DODUO', 109: 'PARAS', 119: 'VENOMOTH',
         167: 'NIDORINO', 168: 'NIDORINA'}
CURSORS = {(1, 14), (13, 14), (1, 16), (13, 16)}


def _display(species):
    return {3: 'NIDORAN♂', 15: 'NIDORAN♀'}.get(species, NAMES.get(species))


def _name(value):
    return (value.upper().replace('♂', 'M').replace('♀', 'F').replace('_', '').replace(' ', '')
            if isinstance(value, str) else None)


def _byte(value):
    if type(value) is not int or not 0 <= value <= 255:
        raise ValueError('byte_invalid')
    return value


def read_safari_battle_signal(pyboy, *, observation_frame, expected_location, constants):
    """雙讀同幀來源欄位；沒有tick、setter、檔案／模型IO或部分有效封包。"""
    def unknown(reason):
        return {'profile': PROFILE, 'source_commit': SOURCE_COMMIT, 'read_valid': False,
                'unknown_reason': reason}
    try:
        for key, expected in SDK_ANCHORS.items():
            value = constants.get(key) if isinstance(constants, Mapping) else getattr(constants, key, None)
            if type(value) is not int or value != expected:
                return unknown('safari_run_sdk_anchor_unverified')
        events = constants.get('EVENT_FLAGS') if isinstance(constants, Mapping) else getattr(constants, 'EVENT_FLAGS', None)
        if (not isinstance(events, Mapping)
                or any(type(events.get(k)) is not int or events[k] != v
                       for k, v in {'in_safari_zone': 591, 'safari_game_over': 590}.items())):
            return unknown('safari_run_event_source_unverified')
        if (not isinstance(expected_location, dict)
                or any(type(expected_location.get(k)) is not int or not 0 <= expected_location[k] <= 255
                       for k in ('map_id', 'x', 'y'))):
            return unknown('safari_run_location_invalid')
        before = pyboy.frame_count
        if type(observation_frame) is not int or type(before) is not int or before != observation_frame or before < 0:
            return unknown('safari_run_frame_unverified')
        addresses = (0xD057, 0xD05A, 0xD790, 0xDA47, 0xD70D, 0xD70E,
                     0xD35E, 0xD362, 0xD361, 0xCFE5, 0xCFF3)
        first = tuple(_byte(pyboy.memory[a]) for a in addresses)
        second = tuple(_byte(pyboy.memory[a]) for a in addresses)
        after = pyboy.frame_count
        if type(after) is not int or before != after or first != second:
            return unknown('safari_run_observation_changed')
        raw, kind, flags, balls, hi, lo, mid, x, y, species, level = first
        location = {'map_id': mid, 'x': x, 'y': y}
        if location != {k: expected_location[k] for k in location}:
            return unknown('safari_run_location_disagrees')
        if raw not in {0, 1, 2, 255} or kind not in {0, 1, 2} or balls > 30 or (hi << 8 | lo) > 502:
            return unknown('safari_run_source_values_invalid')
        if raw == 1 and kind == 2 and (species not in NAMES or not 1 <= level <= 100):
            return unknown('safari_run_enemy_unverified')
        return {'profile': PROFILE, 'source_commit': SOURCE_COMMIT, 'read_valid': True,
                'unknown_reason': None, 'observation_frame': before, 'location': location,
                'raw': raw, 'battle_type': kind, 'flags_raw': flags,
                'in_safari': bool(flags & 128), 'game_over': bool(flags & 64),
                'balls': balls, 'steps': hi << 8 | lo,
                'enemy_species': species if raw == 1 and kind == 2 else None,
                'enemy_level': level if raw == 1 and kind == 2 else None}
    except Exception as error:
        return unknown(str(error) if isinstance(error, ValueError) else 'safari_run_read_failed')


def _rows(text):
    if (not isinstance(text, dict) or text.get('profile') != TEXT_PROFILE
            or text.get('read_valid') is not True or text.get('alignment_verified') is not True
            or text.get('read_error') is not None or type(text.get('window_visible')) is not bool):
        return None
    cells = text.get('cells')
    if (not isinstance(cells, (list, tuple)) or len(cells) != 18
            or any(not isinstance(r, (str, list, tuple)) or len(r) != 20
                   or any(not isinstance(c, str) or len(c) != 1 for c in r) for r in cells)):
        return None
    return [''.join(row).upper() for row in cells]


def _menu(rows, *, inactive=False):
    marks = [(x, y, c) for y, row in enumerate(rows) for x, c in enumerate(row) if c in '▶▷▼']
    if len(marks) != 1 or marks[0][:2] not in CURSORS or marks[0][2] != ('▷' if inactive else '▶'):
        return None
    expected = [[' '] * 20 for _ in range(6)]
    for x, y, label in [(2, 14, 'BALL×'), (7, 14, '30'), (14, 14, 'BAIT'),
                        (2, 16, 'THROW ROCK'), (14, 16, 'RUN')]:
        expected[y - 12][x:x + len(label)] = label
    x, y, marker = marks[0]
    expected[y - 12][x] = marker
    return (x, y) if rows[12:] == [''.join(row) for row in expected] else None


def _lower(rows):
    if any(c != ' ' and not (y in {14, 16} and 1 <= x <= 18)
           for y, row in enumerate(rows[12:], 12) for x, c in enumerate(row)):
        return None
    words = ' '.join(' '.join(rows[12:]).split())
    if words.count('▼') > 1 or '▼' in words and not words.endswith('▼'):
        return None
    return words.removesuffix('▼').strip()


class SafariRunController:
    """每場有界正常逃跑；pending保留到真游標／頁面改變，不重送舊輸入。"""

    def __init__(self, intent):
        self.intent = deepcopy(intent)
        self.stage = 'start'
        self.error = None
        self.base = None
        self.started = self.last_now = None
        self.last_frame = -1
        self.last_packet = None
        self.calls = self.waits = 0
        self.pending = None
        self.run_sent = self.intro_sent = self.receipt_sent = False
        self.message_seen = False
        self.closed_frames = []

    def fail(self, reason):
        self.error = reason
        return {'phase': 'campaign_review', 'objective': 'Wait.', 'available_actions': ['wait'],
                'review_reason': reason}

    def wait(self, reason):
        self.waits += 1
        if self.waits > 25:
            return self.fail('safari_run_wait_budget_exhausted')
        return {'phase': 'safari_battle', 'objective': 'Wait.', 'available_actions': ['wait'],
                'safari_run_stage': reason, 'source': SOURCE}

    def action(self, button, stage):
        self.waits = 0
        return {'phase': 'safari_battle', 'objective': 'Confirm the current selection.' if button == 'a'
                else f'Move {button.upper()}.', 'available_actions': [button, 'wait'],
                'controller_menu_verified': True, 'safari_run_stage': stage, 'source': SOURCE}

    def context(self, text, *, location, battle_state, safari, battle_signal, frame, now, overworld_ready=False):
        if self.error:
            return self.fail(self.error)
        if (self.intent != INTENT or type(frame) is not int or frame < 0
                or type(now) not in {int, float} or not math.isfinite(now) or now < 0
                or self.last_now is not None and now < self.last_now):
            return self.fail('safari_run_intent_frame_or_clock_unverified')
        self.started = now if self.started is None else self.started
        self.last_now = now
        self.calls += 1
        if self.calls > 150 or now - self.started > 60:
            return self.fail('safari_run_budget_exhausted')
        if not isinstance(battle_signal, dict) or battle_signal.get('read_valid') is not True:
            return self.fail('safari_run_signal_unverified')
        s = battle_signal
        if (s.get('profile') != PROFILE or s.get('source_commit') != SOURCE_COMMIT
                or type(s.get('observation_frame')) is not int or s['observation_frame'] != frame
                or not isinstance(location, dict) or s.get('location') != {k: location.get(k) for k in ('map_id', 'x', 'y')}
                or any(type(location.get(k)) is not int for k in ('map_id', 'x', 'y'))
                or any(type(s.get(k)) is not int for k in ('raw', 'battle_type', 'flags_raw', 'balls', 'steps'))
                or not 0 <= s['flags_raw'] <= 255 or not 0 <= s['steps'] <= 502
                or type(s.get('in_safari')) is not bool or type(s.get('game_over')) is not bool
                or s['in_safari'] != bool(s['flags_raw'] & 128)
                or s['game_over'] != bool(s['flags_raw'] & 64)):
            return self.fail('safari_run_source_contract_unverified')
        if self.base is None and location['map_id'] not in OUTDOORS and not s['in_safari']:
            return None
        if (location['map_id'] not in OUTDOORS or not s['in_safari'] or s['game_over'] or s['balls'] != 30
                or not isinstance(safari, dict) or safari.get('profile') != SAFARI_PROFILE
                or safari.get('read_valid') is not True or type(safari.get('observation_frame')) is not int
                or safari['observation_frame'] != frame or safari.get('in_safari') is not True
                or safari.get('game_over') is not False or type(safari.get('balls')) is not int
                or safari['balls'] != s['balls'] or type(safari.get('steps')) is not int
                or safari['steps'] != s['steps']):
            return self.fail('safari_run_safari_or_ball_accounting_unverified')
        if (not isinstance(battle_state, dict) or type(battle_state.get('raw')) is not int
                or battle_state['raw'] != s['raw'] or type(battle_state.get('observation_frame')) is not int
                or battle_state['observation_frame'] != frame
                or not (s['raw'] == 1 and s['battle_type'] == 2 and battle_state.get('active') is True
                        and battle_state.get('kind') == 'wild'
                        or self.run_sent and s['raw'] == 0 and s['battle_type'] in {0, 2}
                        and battle_state.get('active') is False and battle_state.get('kind') == 'none')):
            return self.fail('safari_run_battle_type_disagrees')
        if self.base is None:
            if type(s.get('enemy_species')) is not int or s['enemy_species'] not in NAMES or type(s.get('enemy_level')) is not int or not 1 <= s['enemy_level'] <= 100:
                return self.fail('safari_run_initial_enemy_unverified')
            self.base = deepcopy({k: s[k] for k in ('location', 'steps', 'enemy_species', 'enemy_level')})
        if s['raw'] == 1 and _name(battle_state.get('opponent_species')) != _name(NAMES.get(s.get('enemy_species'))):
            return self.fail('safari_run_enemy_signal_disagrees')
        if (s['location'] != self.base['location'] or s['steps'] != self.base['steps']
                or s['raw'] == 1 and any(s.get(k) != self.base[k] or type(s.get(k)) is not int
                                       for k in ('enemy_species', 'enemy_level'))):
            return self.fail('safari_run_encounter_changed')
        packet = deepcopy((text, location, battle_state, safari, battle_signal, overworld_ready))
        if frame < self.last_frame or frame == self.last_frame and packet != self.last_packet:
            return self.fail('safari_run_frame_or_packet_changed')
        if frame == self.last_frame:
            return self.wait('same_observation_no_resend')
        self.last_frame, self.last_packet = frame, packet
        rows = _rows(text)
        if rows is None:
            self.closed_frames.clear()
            if ((self.run_sent or not self.intro_sent and self.stage=='start')
                    and isinstance(text, dict) and text.get('profile') == TEXT_PROFILE
                    and text.get('read_error') in {'visible_display_disabled', 'visible_tile_alignment_incomplete'}):
                return self.wait('native_exit_animation_unreadable' if self.run_sent else 'native_intro_animation_unreadable')
            return self.fail('safari_run_decoder_unverified')
        if s['raw'] == 0 and not ''.join(rows).strip() and text['window_visible'] is False and overworld_ready is True:
            self.closed_frames.append(frame)
            if len(self.closed_frames) < 2:
                return self.wait('first_closed_overworld')
            self.stage = 'complete'
            return {'phase': 'overworld', 'objective': 'Wait.', 'available_actions': ['wait'],
                    'safari_run_complete': True, 'safari_run_message_seen': self.message_seen, 'source': SOURCE}
        self.closed_frames.clear()
        # 入場橫條使用字碼9的圖塊；橫條也可能只剩下半部。
        if (not self.intro_sent and not self.run_sent and self.stage=='start'
                and any('9' in row for row in rows)
                and all(c in {' ','9'} for row in rows for c in row)):
            return self.wait('native_intro_stripe_wipe')
        name, level = _display(self.base['enemy_species']), self.base['enemy_level']
        upper = [[' '] * 20 for _ in range(12)]
        upper[0][1:1 + len(name)] = name
        upper[1][5:5 + len(str(level))] = str(level)
        if rows[:12] not in ([''.join(r) for r in upper], [' ' * 20] * 12):
            return self.fail('safari_run_upper_layout_unverified')
        cursor = _menu(rows)
        if cursor is not None:
            if self.run_sent:
                if cursor != (13, 16):
                    return self.fail('safari_run_cursor_changed_after_confirmation')
                return self.wait('run_pressed_old_menu')
            if self.pending:
                old, expected = self.pending
                if cursor == old:
                    return self.wait('await_cursor_move')
                if cursor != expected:
                    return self.fail('safari_run_cursor_moved_unexpectedly')
                self.pending = None
            self.stage = 'menu'
            if cursor[0] == 1:
                self.pending = (cursor, (13, cursor[1]))
                return self.action('right', 'select_right_column')
            if cursor[1] == 14:
                self.pending = (cursor, (13, 16))
                return self.action('down', 'select_run_row')
            self.run_sent = True
            self.stage = 'running'
            return self.action('a', 'confirm_exact_run')
        if self.run_sent and _menu(rows, inactive=True) == (13, 16):
            return self.wait('native_run_inactive_cursor')
        lower = _lower(rows)
        if lower is None:
            return self.fail('safari_run_menu_or_dialogue_polluted')
        intro = f'WILD {name} APPEARED!'
        if not self.run_sent and lower == intro:
            if self.intro_sent:
                return self.wait('await_native_menu_after_intro')
            self.intro_sent = True
            self.stage = 'intro'
            return self.action('a', 'advance_complete_wild_appeared')
        if not self.run_sent and intro.startswith(lower):
            return self.wait('wild_appeared_typing_or_menu_drawing')
        if self.run_sent and lower == 'GOT AWAY SAFELY!':
            self.message_seen = True
            if self.receipt_sent:
                return self.wait('await_native_world_after_receipt')
            self.receipt_sent = True
            return self.action('a', 'advance_complete_got_away')
        if self.run_sent and 'GOT AWAY SAFELY!'.startswith(lower):
            return self.wait('native_run_receipt_typing_or_transition')
        return self.fail('safari_run_unknown_visible_page')
